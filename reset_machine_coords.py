#!/usr/bin/env python3
"""
Reset machine coordinates to fix persistent alarm state.
"""

import serial
import time

def reset_coords():
    try:
        print("Connecting to GRBL...")
        ser = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
        time.sleep(2)
        
        print("The issue: Machine thinks it's at -76.2mm (outside normal range)")
        print("Solution: Force reset machine coordinates to current position")
        
        # Method: Use G92 to reset coordinates
        print("\n1. Disabling hard limits temporarily...")
        ser.write(b'$21=0\n')
        time.sleep(0.5)
        
        print("2. Clearing alarm...")
        ser.write(b'$X\n')
        time.sleep(0.5)
        
        # Check if alarm cleared
        ser.write(b'?\n')
        time.sleep(0.2)
        while ser.in_waiting:
            status = ser.readline().decode().strip()
            if status.startswith('<'):
                print(f"   Status: {status}")
                if 'Alarm' not in status:
                    print("   ✅ Alarm cleared!")
                    
                    print("3. Resetting machine coordinates to 0,0,0,0...")
                    # Use G92 to set current position as 0,0,0,0
                    ser.write(b'G92 X0 Y0 Z0 A0\n')
                    time.sleep(0.5)
                    
                    # Check new position
                    ser.write(b'?\n')
                    time.sleep(0.2)
                    while ser.in_waiting:
                        new_status = ser.readline().decode().strip()
                        if new_status.startswith('<'):
                            print(f"   New status: {new_status}")
                            break
                    
                    print("4. Re-enabling hard limits...")
                    ser.write(b'$21=1\n')
                    time.sleep(0.5)
                    
                    # Final status check
                    ser.write(b'?\n')
                    time.sleep(0.2)
                    while ser.in_waiting:
                        final_status = ser.readline().decode().strip()
                        if final_status.startswith('<'):
                            print(f"   Final status: {final_status}")
                            if 'Alarm' not in final_status:
                                print("   🎉 SUCCESS! Ready for homing!")
                                
                                # Try homing
                                proceed = input("\n   Try X-axis homing now? (y/n): ").lower().strip()
                                if proceed in ['y', 'yes']:
                                    print("   Sending $HX...")
                                    ser.write(b'$HX\n')
                                    time.sleep(10)
                                    
                                    # Check homing result
                                    ser.write(b'?\n')
                                    time.sleep(0.2)
                                    while ser.in_waiting:
                                        home_status = ser.readline().decode().strip()
                                        if home_status.startswith('<'):
                                            print(f"   Homing result: {home_status}")
                                            break
                            break
                    
                break
        
        ser.close()
        print("\nDisconnected from GRBL")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    reset_coords()