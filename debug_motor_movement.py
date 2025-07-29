#!/usr/bin/env python3
"""
Debug script to test and calibrate motor movements.
This script focuses solely on getting GRBL motor controller movements correct.
"""

import time
import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from motor_control.grbl_motor_controller import GrblMotorController

def test_grbl_settings(grbl):
    """Query and display GRBL settings"""
    print("=== GRBL Settings ===")
    grbl.send("$$")  # Request all settings
    time.sleep(2)
    print()

def test_grbl_status(grbl):
    """Query and display GRBL status"""
    print("=== GRBL Status ===")
    grbl.send_immediate("?")  # Request status
    time.sleep(1)
    print()

def test_movement_calibration(grbl):
    """Test actual vs expected movement"""
    print("=== Movement Calibration Test ===")
    
    # Get initial position
    print("Getting initial position...")
    grbl.send_immediate("?")
    time.sleep(1)
    
    print("\nTesting different movement commands:")
    
    # Test 1: 1mm movement in G21 mode
    print("Test 1: 1mm movement in G21 (mm) mode")
    grbl.send("G21")  # Set to mm mode
    grbl.send("G90")  # Absolute positioning
    grbl.send_immediate("?")  # Get position
    time.sleep(1)
    
    print("Sending: $J=G91 G21 X1.0 F100")
    grbl.send("$J=G91 G21 X1.0 F100")
    time.sleep(3)
    grbl.send_immediate("?")  # Get new position
    time.sleep(1)
    
    # Test 2: 1 inch (25.4mm) movement in G21 mode
    print("\nTest 2: 25.4mm movement in G21 (mm) mode (should equal 1 inch)")
    print("Sending: $J=G91 G21 X25.4 F100")
    grbl.send("$J=G91 G21 X25.4 F100")
    time.sleep(3)
    grbl.send_immediate("?")  # Get new position
    time.sleep(1)
    
    # Test 3: 1 inch movement in G20 mode
    print("\nTest 3: 1 inch movement in G20 (inch) mode")
    grbl.send("G20")  # Set to inch mode
    print("Sending: $J=G91 G20 X1.0 F4")
    grbl.send("$J=G91 G20 X1.0 F4")
    time.sleep(3)
    grbl.send_immediate("?")  # Get new position
    time.sleep(1)

def interactive_jog_test(grbl):
    """Interactive jogging to test movements"""
    print("=== Interactive Jog Test ===")
    print("Commands:")
    print("  x+ : Jog X positive 1 unit")
    print("  x- : Jog X negative 1 unit")
    print("  y+ : Jog Y positive 1 unit")
    print("  y- : Jog Y negative 1 unit")
    print("  ? : Get position")
    print("  mm : Switch to mm mode")
    print("  in : Switch to inch mode")
    print("  q : Quit")
    print()
    
    current_mode = "mm"
    
    while True:
        cmd = input(f"[{current_mode}] Enter command: ").strip().lower()
        
        if cmd == 'q':
            break
        elif cmd == '?':
            grbl.send_immediate("?")
            time.sleep(1)
        elif cmd == 'mm':
            grbl.send("G21")
            current_mode = "mm"
            print("Switched to mm mode")
        elif cmd == 'in':
            grbl.send("G20")
            current_mode = "in"
            print("Switched to inch mode")
        elif cmd == 'x+':
            if current_mode == "mm":
                grbl.send("$J=G91 G21 X1.0 F100")
                print("Sent: $J=G91 G21 X1.0 F100")
            else:
                grbl.send("$J=G91 G20 X0.1 F4")
                print("Sent: $J=G91 G20 X0.1 F4")
            time.sleep(2)
        elif cmd == 'x-':
            if current_mode == "mm":
                grbl.send("$J=G91 G21 X-1.0 F100")
                print("Sent: $J=G91 G21 X-1.0 F100")
            else:
                grbl.send("$J=G91 G20 X-0.1 F4")
                print("Sent: $J=G91 G20 X-0.1 F4")
            time.sleep(2)
        elif cmd == 'y+':
            if current_mode == "mm":
                grbl.send("$J=G91 G21 Y1.0 F100")
                print("Sent: $J=G91 G21 Y1.0 F100")
            else:
                grbl.send("$J=G91 G20 Y0.1 F4")
                print("Sent: $J=G91 G20 Y0.1 F4")
            time.sleep(2)
        elif cmd == 'y-':
            if current_mode == "mm":
                grbl.send("$J=G91 G21 Y-1.0 F100")
                print("Sent: $J=G91 G21 Y-1.0 F100")
            else:
                grbl.send("$J=G91 G20 Y-0.1 F4")
                print("Sent: $J=G91 G20 Y-0.1 F4")
            time.sleep(2)
        else:
            print("Unknown command")

def main():
    print("GRBL Motor Movement Debug Script")
    print("===============================")
    
    try:
        # Connect to GRBL
        print("Connecting to GRBL...")
        grbl = GrblMotorController()
        print("Connected!")
        time.sleep(3)  # Let it initialize
        
        # Test sequence
        test_grbl_settings(grbl)
        test_grbl_status(grbl)
        test_movement_calibration(grbl)
        interactive_jog_test(grbl)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            grbl.close()
        except:
            pass

if __name__ == "__main__":
    main()