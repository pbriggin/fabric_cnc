#!/usr/bin/env python3
"""
Fix the homing issue by properly clearing alarms and handling negative positions.
"""

import serial
import time

class HomingFixer:
    def __init__(self, port='/dev/ttyACM0', baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        
    def connect(self):
        """Connect to GRBL controller."""
        try:
            print(f"Connecting to GRBL on {self.port}...")
            self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)
            print("✓ Connected to GRBL")
            return True
        except Exception as e:
            print(f"✗ Failed to connect: {e}")
            return False
    
    def send_command(self, command, wait_time=0.5):
        """Send a command to GRBL and get response."""
        try:
            print(f"Sending: {command}")
            self.serial.write((command + '\n').encode())
            time.sleep(wait_time)
            
            responses = []
            while self.serial.in_waiting:
                line = self.serial.readline().decode().strip()
                if line:
                    responses.append(line)
                    if 'error' in line.lower():
                        print(f"  ❌ {line}")
                    elif line == 'ok':
                        print(f"  ✓ {line}")
                    else:
                        print(f"  📄 {line}")
            
            return responses
        except Exception as e:
            print(f"Command error: {e}")
            return []
    
    def get_status(self):
        """Get machine status."""
        try:
            self.serial.write(b'?\n')
            time.sleep(0.1)
            
            while self.serial.in_waiting:
                line = self.serial.readline().decode().strip()
                if line.startswith('<') and line.endswith('>'):
                    return line
            return None
        except:
            return None
    
    def fix_homing_issue(self):
        """Fix the homing issue step by step."""
        print("="*60)
        print("FIXING HOMING ISSUE")
        print("="*60)
        
        if not self.connect():
            return
        
        try:
            # Step 1: Check current status
            print("\n1. Checking current machine status...")
            status = self.get_status()
            if status:
                print(f"   Status: {status}")
                if 'Alarm' in status:
                    print("   ⚠️  Machine is in alarm state")
                else:
                    print("   ✓ Machine is not in alarm state")
            
            # Step 2: Clear alarm state
            print("\n2. Clearing alarm state...")
            self.send_command('$X')
            
            # Step 3: Check status after clearing alarm
            print("\n3. Checking status after alarm clear...")
            status = self.get_status()
            if status:
                print(f"   Status: {status}")
            
            # Step 4: Reset work coordinates to current position
            print("\n4. Setting current position as work coordinate zero...")
            print("   This tells GRBL 'wherever you are now is position 0,0,0,0'")
            self.send_command('G10 P1 L20 X0 Y0 Z0 A0')
            
            # Step 5: Check status again
            print("\n5. Checking position after coordinate reset...")
            status = self.get_status()
            if status:
                print(f"   Status: {status}")
            
            # Step 6: Now try homing
            print("\n6. Now attempting X-axis homing...")
            print("   ⚠️  Make sure X-axis can move freely!")
            print("   The machine will move X-axis until it hits the limit switch")
            
            proceed = input("\n   Proceed with homing? (y/n): ").lower().strip()
            
            if proceed in ['y', 'yes']:
                print("\n   Sending $HX command...")
                responses = self.send_command('$HX', wait_time=10.0)  # Longer wait for homing
                
                # Check final status
                print("\n7. Checking final status...")
                final_status = self.get_status()
                if final_status:
                    print(f"   Status: {final_status}")
                    
                    if 'Alarm' not in final_status:
                        print("\n🎉 SUCCESS! Homing appears to have worked!")
                    else:
                        print("\n❌ Still in alarm state. Check:")
                        print("     - Is limit switch properly positioned?")
                        print("     - Can X-axis move freely in both directions?")
                        print("     - Is limit switch wiring correct?")
            else:
                print("   Homing cancelled by user")
                
        except KeyboardInterrupt:
            print("\n⚠️  Operation cancelled by user")
            
        finally:
            if self.serial:
                self.serial.close()
                print("\nDisconnected from GRBL")

def main():
    fixer = HomingFixer()
    fixer.fix_homing_issue()

if __name__ == "__main__":
    main()