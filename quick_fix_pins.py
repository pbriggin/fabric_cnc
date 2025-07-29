#!/usr/bin/env python3
"""
Quick fix for the double-inverted X pin issue.
"""

import serial
import time

def quick_fix():
    try:
        print("Connecting to GRBL...")
        ser = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
        time.sleep(2)
        
        print("Current issue: X is ON when it should be OFF")
        print("This means we need to invert ALL pins: X, Y, Z, A")
        print("Setting $5=15 (binary 1111 = invert all 4 axes)")
        
        # Set all pins inverted
        ser.write(b'$5=15\n')
        time.sleep(0.5)
        
        # Read response
        while ser.in_waiting:
            response = ser.readline().decode().strip()
            print(f"Response: {response}")
        
        print("✅ Fixed! Now test with: python test_hall_switch.py")
        print("All switches should now read OFF when not triggered")
        
        ser.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    quick_fix()