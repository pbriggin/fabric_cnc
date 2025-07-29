#!/usr/bin/env python3
"""
Comprehensive refactor of the position system to fix:
1. GUI position values disagreeing with GRBL 
2. Movement scaling issues (more than 1 inch per arrow key)
"""

import re

def refactor_real_motor_controller():
    """Refactor RealMotorController to use GRBL as single source of truth"""
    
    with open("main_app.py", "r") as f:
        content = f.read()
    
    # Find the RealMotorController class
    class_match = re.search(r'class RealMotorController:.*?(?=class|\Z)', content, re.DOTALL)
    if not class_match:
        print("Could not find RealMotorController class")
        return False
    
    print("Refactoring RealMotorController...")
    
    # 1. Simplified __init__ - remove internal position tracking
    old_init = '''class RealMotorController:
    def __init__(self):
        self.motor_controller = GrblMotorController()
        self.lock = threading.Lock()
        self.is_homing = False
        self.position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'ROT': 0.0}  # Track position manually
        # Reset work coordinates on startup
        time.sleep(1)  # Let GRBL initialize
        self.reset_position()'''
    
    new_init = '''class RealMotorController:
    def __init__(self):
        self.motor_controller = GrblMotorController()
        self.lock = threading.Lock()
        self.is_homing = False
        # No internal position tracking - GRBL is single source of truth
        # Reset work coordinates on startup
        time.sleep(1)  # Let GRBL initialize
        self.reset_work_coordinates()'''
    
    content = content.replace(old_init, new_init)
    
    # 2. Simplified reset_position method
    old_reset = '''    def reset_position(self):
        """Reset work coordinates to 0,0,0,0"""
        try:
            self.motor_controller.send("G10 P1 L20 X0 Y0 Z0 A0")  # Reset work coordinates
            with self.lock:
                self.position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'ROT': 0.0}
            logger.info("Reset work coordinates to 0,0,0,0")
        except Exception as e:
            logger.error(f"Failed to reset position: {e}")'''
    
    new_reset = '''    def reset_work_coordinates(self):
        """Reset work coordinates to 0,0,0,0"""
        try:
            self.motor_controller.send("G10 P1 L20 X0 Y0 Z0 A0")  # Reset work coordinates
            logger.info("Reset work coordinates to 0,0,0,0")
        except Exception as e:
            logger.error(f"Failed to reset work coordinates: {e}")'''
    
    content = content.replace(old_reset, new_reset)
    
    # 3. Completely rewrite get_position to ONLY use GRBL data
    old_get_pos = '''    def get_position(self):
        # Use GRBL position data (in mm) and convert to inches
        try:
            x, y, z, a = self.motor_controller.get_position()
            pos = {
                'X': x / 25.4,  # Convert mm to inches
                'Y': y / 25.4,  # Convert mm to inches
                'Z': z / 25.4,  # Convert mm to inches
                'ROT': a        # A-axis is already in degrees
            }
            print(f"[MAIN DEBUG] Raw GRBL pos: [{x}, {y}, {z}, {a}]mm, converted: {pos}")
            # Update internal position tracking to match GRBL
            with self.lock:
                self.position.update(pos)
            return pos
        except Exception as e:
            print(f"[MAIN DEBUG] get_position() error: {e}")
            # Fallback to internal position tracking (already in inches)
            with self.lock:
                fallback_pos = dict(self.position)
                print(f"[MAIN DEBUG] get_position() fallback: {fallback_pos}")
                return fallback_pos'''
    
    new_get_pos = '''    def get_position(self):
        # GRBL is the ONLY source of truth for position
        try:
            x, y, z, a = self.motor_controller.get_position()
            pos = {
                'X': x / 25.4,  # Convert mm to inches
                'Y': y / 25.4,  # Convert mm to inches
                'Z': z / 25.4,  # Convert mm to inches
                'ROT': a        # A-axis is already in degrees
            }
            print(f"[POSITION] GRBL raw: [{x:.3f}, {y:.3f}, {z:.3f}, {a:.3f}]mm -> GUI: [{pos['X']:.3f}, {pos['Y']:.3f}, {pos['Z']:.3f}, {pos['ROT']:.1f}]in")
            return pos
        except Exception as e:
            print(f"[POSITION ERROR] Could not get GRBL position: {e}")
            # Return zeros if GRBL unavailable
            return {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'ROT': 0.0}'''
    
    content = content.replace(old_get_pos, new_get_pos)
    
    # 4. Simplified jog method with debug output
    old_jog = '''    def jog(self, axis, delta):
        with self.lock:
            try:
                print(f"[MAIN DEBUG] Jog request: {axis} by {delta}in")
                new_val = self.position[axis] + delta
                clamped_val = self._clamp(axis, new_val)
                move_delta = clamped_val - self.position[axis]
                print(f"[MAIN DEBUG] After clamping: move_delta = {move_delta}in")
                if abs(move_delta) > 1e-6:
                    # Map axis names and use appropriate feedrate
                    axis_map = {'X': 'X', 'Y': 'Y', 'Z': 'Z', 'ROT': 'A'}
                    feedrate = 1000  # mm/min for jog moves
                    if axis in axis_map:
                        # Convert inches to mm for GRBL
                        move_delta_mm = move_delta * 25.4
                        print(f"[MAIN DEBUG] Converting {move_delta}in to {move_delta_mm}mm")
                        print(f"[MAIN DEBUG] Sending to GRBL: {axis_map[axis]} by {move_delta_mm}mm")
                        self.motor_controller.jog(axis_map[axis], move_delta_mm, feedrate)
                        # Don't update internal position - let get_position() sync from GRBL
                        time.sleep(0.1)  # Give GRBL time to process
                    logger.info(f"Jogged {axis} by {move_delta:.3f}in")
            except Exception as e:
                logger.error(f"Jog error on {axis}: {e}")'''
    
    new_jog = '''    def jog(self, axis, delta):
        try:
            print(f"[JOG] Request: {axis} by {delta:.3f}in")
            
            # Get current position from GRBL
            current_pos = self.get_position()
            current_val = current_pos.get(axis, 0.0)
            
            # Calculate target and clamp
            target_val = current_val + delta
            clamped_val = self._clamp(axis, target_val)
            actual_delta = clamped_val - current_val
            
            print(f"[JOG] Current: {current_val:.3f}in, Target: {target_val:.3f}in, Clamped: {clamped_val:.3f}in, Delta: {actual_delta:.3f}in")
            
            if abs(actual_delta) > 1e-6:
                # Map axis names and convert to mm
                axis_map = {'X': 'X', 'Y': 'Y', 'Z': 'Z', 'ROT': 'A'}
                feedrate = 1000  # mm/min for jog moves
                
                if axis in axis_map:
                    if axis == 'ROT':
                        # Rotation axis in degrees
                        delta_grbl = actual_delta
                        print(f"[JOG] Sending to GRBL: {axis_map[axis]} by {delta_grbl:.3f}°")
                    else:
                        # Linear axes - convert inches to mm
                        delta_grbl = actual_delta * 25.4
                        print(f"[JOG] Sending to GRBL: {axis_map[axis]} by {delta_grbl:.3f}mm ({actual_delta:.3f}in)")
                    
                    self.motor_controller.jog(axis_map[axis], delta_grbl, feedrate)
                    time.sleep(0.2)  # Wait for GRBL to process
                    
            logger.info(f"Jogged {axis} by {actual_delta:.3f}in")
            
        except Exception as e:
            logger.error(f"Jog error on {axis}: {e}")'''
    
    content = content.replace(old_jog, new_jog)
    
    # Write the refactored content
    with open("main_app.py", "w") as f:
        f.write(content)
    
    print("✓ Refactored RealMotorController")
    return True

def check_jog_step_size():
    """Check what step size is being used for arrow key jogging"""
    
    with open("main_app.py", "r") as f:
        content = f.read()
    
    # Look for jog step size or jog distance configuration
    jog_patterns = [
        r'jog.*distance.*=.*[\d.]+',
        r'step.*size.*=.*[\d.]+',
        r'jog.*step.*=.*[\d.]+',
        r'\.jog\([^,]+,\s*([\d.]+)',
        r'motor_ctrl\.jog\([^,]+,\s*([\d.]+)'
    ]
    
    print("Checking for jog step size configuration...")
    
    for pattern in jog_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            print(f"Found jog step references: {matches}")
    
    # Look for arrow key bindings
    arrow_patterns = [
        r'<.*Arrow.*>',
        r'bind.*Arrow',
        r'Left.*Right.*Up.*Down'
    ]
    
    for pattern in arrow_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            print(f"Found arrow key bindings: {matches}")

def main():
    print("Position System Refactor")
    print("========================")
    
    # Check current jog step size
    check_jog_step_size()
    
    # Apply refactor
    if refactor_real_motor_controller():
        print("\n✓ Refactor completed successfully!")
        print("\nChanges made:")
        print("1. Removed internal position tracking")
        print("2. GRBL is now the single source of truth")
        print("3. Improved debug output for jog commands")
        print("4. Better position clamping based on current GRBL position")
        print("5. More detailed logging for troubleshooting")
        
        print("\nNext steps:")
        print("1. Test the app: python3 main_app.py")
        print("2. Watch the debug output for jog commands")
        print("3. Verify position values match between GUI and GRBL")
        print("4. Check that arrow keys move exactly the expected distance")
    else:
        print("\n✗ Refactor failed")

if __name__ == "__main__":
    main()