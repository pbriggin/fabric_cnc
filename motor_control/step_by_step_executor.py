#!/usr/bin/env python3
"""
Step-by-step GCODE executor for debugging
"""

import sys
import os
# Add parent directory to path to import main_app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .smooth_motion_executor import SmoothMotionExecutor
from main_app import RealMotorController

class StepByStepExecutor:
    def __init__(self):
        self.motor_ctrl = RealMotorController()
        self.executor = SmoothMotionExecutor(self.motor_ctrl)
        
    def execute_gcode_step_by_step(self, gcode_lines):
        """Execute GCODE line by line with user confirmation."""
        
        print("=== STEP-BY-STEP GCODE EXECUTION ===")
        print("Commands will be executed one by one with your confirmation.")
        print("Type 'y' to execute, 'n' to skip, 'q' to quit, 'p' to show position")
        print()
        
        for i, line in enumerate(gcode_lines):
            line = line.strip()
            if not line or line.startswith(';'):
                print(f"Line {i+1}: {line} (comment/empty - skipping)")
                continue
                
            print(f"\n--- Line {i+1}: {line} ---")
            
            # Show current position
            current_pos = self.motor_ctrl.get_position()
            print(f"Current position: {current_pos}")
            
            # Parse the command to show what it will do
            try:
                parsed = self.executor._parse_gcode_line(line)
                if parsed:
                    command, params = parsed
                    print(f"Command: {command}")
                    print(f"Parameters: {params}")
                    
                    # Calculate target position
                    if params:
                        target = self.executor._calculate_target_position(params)
                        current = self.motor_ctrl.get_position()
                        delta = {axis: target[axis] - current[axis] for axis in target}
                        print(f"Target position: {target}")
                        print(f"Delta: {delta}")
            except Exception as e:
                print(f"Parse error: {e}")
            
            # Get user confirmation
            while True:
                response = input("Execute this command? (y/n/q/p): ").lower().strip()
                
                if response == 'q':
                    print("Quitting execution.")
                    return False
                elif response == 'p':
                    pos = self.motor_ctrl.get_position()
                    print(f"Current position: {pos}")
                    continue
                elif response == 'y':
                    break
                elif response == 'n':
                    print("Skipping this command.")
                    break
                else:
                    print("Invalid response. Use y/n/q/p")
                    continue
            
            if response == 'n':
                continue
                
            # Execute the command
            try:
                print(f"Executing: {line}")
                self._execute_single_gcode_line(line)
                
                # Show new position
                new_pos = self.motor_ctrl.get_position()
                print(f"New position: {new_pos}")
                
                # Check for any issues
                if 'Z' in new_pos and new_pos['Z'] < -1.0:
                    print("⚠️  WARNING: Z position is below -1.0 limit!")
                if 'Z' in new_pos and new_pos['Z'] > 5.0:
                    print("⚠️  WARNING: Z position is above 5.0 limit!")
                    
            except Exception as e:
                print(f"❌ ERROR executing command: {e}")
                import traceback
                traceback.print_exc()
                
                response = input("Continue with next command? (y/n): ").lower().strip()
                if response != 'y':
                    return False
        
        print("\n=== EXECUTION COMPLETED ===")
        final_pos = self.motor_ctrl.get_position()
        print(f"Final position: {final_pos}")
        return True
    
    def _execute_single_gcode_line(self, line: str):
        """Execute a single GCODE line."""
        parsed = self.executor._parse_gcode_line(line)
        if not parsed:
            print(f"Could not parse line: {line}")
            return
            
        command, params = parsed
        
        if command == 'G28':  # Home
            print("Executing home command")
            self.motor_ctrl.home_all_synchronous()
            self.executor.current_position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'ROT': 0.0}
            
        elif command == 'G0':  # Rapid positioning
            target = self.executor._calculate_target_position(params)
            print(f"Rapid move to: {target}")
            self.motor_ctrl.move_to(
                x=target['X'],
                y=target['Y'],
                z=target['Z'],
                rot=target['ROT']
            )
            self.executor.current_position = target.copy()
            
        elif command == 'G1':  # Linear interpolation
            target = self.executor._calculate_target_position(params)
            current = self.motor_ctrl.get_position()
            delta_x = target['X'] - current['X']
            delta_y = target['Y'] - current['Y']
            delta_z = target['Z'] - current['Z']
            delta_rot = target['ROT'] - current['ROT']
            
            print(f"Linear move: delta({delta_x:.2f}, {delta_y:.2f}, {delta_z:.2f}, {delta_rot:.2f})")
            self.motor_ctrl.move_coordinated(
                x_distance_mm=delta_x,
                y_distance_mm=delta_y,
                z_distance_mm=delta_z,
                rot_distance_mm=delta_rot
            )
            self.executor.current_position = target.copy()
            
        else:
            print(f"Unknown command: {command}")
    
    def cleanup(self):
        """Clean up motor controller."""
        try:
            self.motor_ctrl.cleanup()
            print("Motor controller cleaned up")
        except:
            pass

def main():
    """Main function to run step-by-step execution."""
    
    # Test GCODE - you can replace this with your actual toolpath
    test_gcode = [
        "G28",           # Home all axes
        "G0 Z5.0",       # Move to safe height
        "G0 X1.0 Y1.0",  # Move to start position
        "G0 Z-1.0",      # Plunge to cutting height
        "G1 X2.0 Y2.0",  # Cut to next position
        "G0 Z5.0",       # Raise to safe height
        "G0 X1.0 Y1.0",  # Move back to start
        "G0 Z-1.0",      # Plunge again
        "G0 Z5.0",       # Raise to safe height
    ]
    
    print("Step-by-Step GCODE Executor")
    print("=" * 50)
    print("This will execute GCODE commands one by one with your confirmation.")
    print()
    
    # Ask if user wants to use test GCODE or load from file
    choice = input("Use test GCODE (t) or load from file (f)? ").lower().strip()
    
    if choice == 'f':
        filename = input("Enter GCODE filename: ").strip()
        try:
            with open(filename, 'r') as f:
                gcode_lines = f.readlines()
            print(f"Loaded {len(gcode_lines)} lines from {filename}")
        except Exception as e:
            print(f"Error loading file: {e}")
            return
    else:
        gcode_lines = test_gcode
        print("Using test GCODE")
    
    print("\nGCODE to execute:")
    for i, line in enumerate(gcode_lines):
        print(f"{i+1:2d}: {line}")
    
    print("\nStarting step-by-step execution...")
    
    executor = StepByStepExecutor()
    try:
        executor.execute_gcode_step_by_step(gcode_lines)
    finally:
        executor.cleanup()

if __name__ == "__main__":
    main() 