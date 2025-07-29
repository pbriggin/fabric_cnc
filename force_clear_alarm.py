#!/usr/bin/env python3
"""
Force clear the persistent alarm state.
"""

import serial
import time

def force_clear_alarm():
    try:
        print("Connecting to GRBL...")
        ser = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
        time.sleep(2)
        
        print("Attempting aggressive alarm clearing sequence...")
        
        # Method 1: Disable hard limits, clear alarm, re-enable
        print("\n1. Temporarily disabling hard limits...")
        ser.write(b'$21=0\n')
        time.sleep(0.5)
        
        print("2. Clearing alarm with hard limits disabled...")
        ser.write(b'$X\n')
        time.sleep(0.5)
        
        # Check status
        ser.write(b'?\n')
        time.sleep(0.2)
        while ser.in_waiting:
            status = ser.readline().decode().strip()
            if status.startswith('<'):
                print(f"   Status: {status}")
                break
        
        print("3. Re-enabling hard limits...")
        ser.write(b'$21=1\n')
        time.sleep(0.5)
        
        # Try soft reset to completely clear state
        print("4. Performing soft reset...")
        ser.write(b'\x18')  # Ctrl+X soft reset
        time.sleep(3)  # Wait for reset
        
        print("5. Checking status after reset...")
        ser.write(b'?\n')
        time.sleep(0.2)
        while ser.in_waiting:
            status = ser.readline().decode().strip()
            if status.startswith('<'):
                print(f"   Status: {status}")
                if 'Alarm' not in status:
                    print("   ✅ SUCCESS! Alarm cleared!")
                    print("\n   Now try homing:")
                    print("   Send: $HX")
                    
                    # Try homing immediately
                    proceed = input("\n   Try X-axis homing now? (y/n): ").lower().strip()
                    if proceed in ['y', 'yes']:
                        print("   Sending $HX...")
                        ser.write(b'$HX\n')
                        time.sleep(10)  # Wait for homing
                        
                        # Check final result
                        ser.write(b'?\n')
                        time.sleep(0.2)
                        while ser.in_waiting:
                            final_status = ser.readline().decode().strip()
                            if final_status.startswith('<'):
                                print(f"   Final status: {final_status}")
                                if 'Alarm' not in final_status:
                                    print("   🎉 HOMING SUCCESSFUL!")
                                break
                else:
                    print("   ❌ Still in alarm state")
                    print("   This may indicate a hardware issue:")
                    print("   - Check that X-axis can move freely")
                    print("   - Verify limit switch is positioned correctly")
                    print("   - Ensure no mechanical obstructions")
                break
        
        ser.close()
        print("\nDisconnected from GRBL")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    force_clear_alarm()