#!/usr/bin/env python3
"""
Fix position syncing issues in main_app.py
Based on diagnostic findings that GRBL HAL works correctly but GUI syncing is broken
"""

import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def apply_position_sync_fixes():
    """Apply fixes to main_app.py for better position syncing"""
    
    main_app_path = "main_app.py"
    
    print("Reading main_app.py...")
    with open(main_app_path, 'r') as f:
        content = f.read()
    
    # Fix 1: Improve get_position() method reliability
    old_get_position = '''    def get_position(self):
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
            return pos
        except:
            # Fallback to internal position tracking (already in inches)
            with self.lock:
                fallback_pos = dict(self.position)
                print(f"[MAIN DEBUG] get_position() fallback: {fallback_pos}")
                return fallback_pos'''
    
    new_get_position = '''    def get_position(self):
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
    
    # Fix 2: Improve jog method to better sync position
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
                    self.position[axis] = clamped_val
                    logger.info(f"Jogged {axis} by {move_delta:.3f}in")
            except Exception as e:
                logger.error(f"Jog error on {axis}: {e}")'''
    
    new_jog = '''    def jog(self, axis, delta):
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
    
    # Fix 3: Improve position display update frequency
    old_update_display = '''    def _update_position_display(self):
        pos = self.motor_ctrl.get_position()
        # Positions are already in inches from RealMotorController.get_position()
        x_disp = pos['X']
        y_disp = pos['Y']
        z_disp = pos['Z']
        rot_disp = pos['ROT']
        text = f"X:{x_disp:.1f}in\\nY:{y_disp:.1f}in\\nZ:{z_disp:.1f}in\\nR:{rot_disp:.0f}°"
        self.coord_label.configure(text=text)
        self.root.after(200, self._update_position_display)'''
    
    new_update_display = '''    def _update_position_display(self):
        pos = self.motor_ctrl.get_position()
        # Positions are already in inches from RealMotorController.get_position()
        x_disp = pos['X']
        y_disp = pos['Y']
        z_disp = pos['Z']
        rot_disp = pos['ROT']
        text = f"X:{x_disp:.3f}in\\nY:{y_disp:.3f}in\\nZ:{z_disp:.3f}in\\nR:{rot_disp:.1f}°"
        self.coord_label.configure(text=text)
        # Update more frequently for better responsiveness
        self.root.after(100, self._update_position_display)'''
    
    # Apply fixes
    fixes_applied = 0
    
    if old_get_position in content:
        content = content.replace(old_get_position, new_get_position)
        print("✓ Fixed get_position() method")
        fixes_applied += 1
    else:
        print("⚠ Could not find get_position() method to fix")
    
    if old_jog in content:
        content = content.replace(old_jog, new_jog)
        print("✓ Fixed jog() method") 
        fixes_applied += 1
    else:
        print("⚠ Could not find jog() method to fix")
    
    if old_update_display in content:
        content = content.replace(old_update_display, new_update_display)
        print("✓ Fixed _update_position_display() method")
        fixes_applied += 1
    else:
        print("⚠ Could not find _update_position_display() method to fix")
    
    if fixes_applied > 0:
        # Write back to file
        with open(main_app_path, 'w') as f:
            f.write(content)
        print(f"\\n✓ Applied {fixes_applied} fixes to main_app.py")
        return True
    else:
        print("\\n✗ No fixes could be applied")
        return False

def main():
    print("Position Sync Fix Script")
    print("========================")
    
    if apply_position_sync_fixes():
        print("\\nFixes applied successfully!")
        print("The changes should:")
        print("1. Improve position syncing between GRBL and GUI")
        print("2. Update display more frequently (100ms vs 200ms)")
        print("3. Show position with more precision (3 decimal places)")
        print("4. Better handle jog command synchronization")
        print("\\nTest the GUI now to see if position syncing is improved.")
    else:
        print("\\nNo fixes could be applied. Check the file manually.")

if __name__ == "__main__":
    main()