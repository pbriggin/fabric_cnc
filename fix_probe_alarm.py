#!/usr/bin/env python3
"""
Fix the probe pin alarm issue preventing homing.
"""

import serial
import time

class ProbeAlarmFixer:
    def __init__(self, port='/dev/ttyACM0', baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        
    def connect(self):
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
    
    def fix_probe_alarm(self):
        print("="*60)
        print("FIXING PROBE PIN ALARM ISSUE")
        print("="*60)
        
        if not self.connect():
            return
        
        try:
            # Check current status
            print("\n1. Current status:")
            status = self.get_status()
            if status:
                print(f"   {status}")
                if 'Pn:P' in status:
                    print("   ⚠️  Probe pin (P) is active - this prevents alarm clearing")
            
            print("\n2. Solutions to try:")
            print("   Option A: Disable probe pin temporarily")
            print("   Option B: Force unlock (more aggressive)")
            
            # Option A: Disable probe pin
            print("\n3. Trying Option A: Temporarily disable probe pin...")
            print("   Note: This disables probe functionality until re-enabled")
            
            # Get current probe setting
            responses = self.send_command('$$', wait_time=1.0)
            probe_setting = None
            for line in responses:
                if line.startswith('$6='):
                    probe_setting = line.split('=')[1]
                    print(f"   Current $6 (probe pin enable): {probe_setting}")
                    break
            
            if probe_setting != '0':
                print("   Disabling probe pin temporarily...")
                self.send_command('$6=0')  # Disable probe pin
                time.sleep(0.5)
                
                # Try to clear alarm now
                print("   Attempting to clear alarm...")
                self.send_command('$X')
                time.sleep(0.5)
                
                # Check status
                status = self.get_status()
                if status:
                    print(f"   Status after probe disable: {status}")
                    
                    if 'Alarm' not in status:
                        print("   ✅ Alarm cleared! Now attempting homing...")
                        
                        # Try homing
                        proceed = input("   Proceed with X-axis homing? (y/n): ").lower().strip()
                        if proceed in ['y', 'yes']:
                            print("   Sending $HX...")
                            self.send_command('$HX', wait_time=10.0)
                            
                            # Check final status
                            final_status = self.get_status()
                            if final_status:
                                print(f"   Final status: {final_status}")
                                
                        # Re-enable probe if it was originally enabled
                        if probe_setting and probe_setting != '0':
                            print(f"   Re-enabling probe pin ($6={probe_setting})...")
                            self.send_command(f'$6={probe_setting}')
                    else:
                        print("   ❌ Still in alarm. Trying more aggressive approach...")
                        self.force_unlock()
            else:
                print("   Probe pin already disabled. Trying force unlock...")
                self.force_unlock()
                
        except KeyboardInterrupt:
            print("\n⚠️  Operation cancelled by user")
            
        finally:
            if self.serial:
                self.serial.close()
                print("\nDisconnected from GRBL")
    
    def force_unlock(self):
        """More aggressive unlock attempt."""
        print("\n4. Force unlock attempt:")
        print("   Temporarily disabling hard limits...")
        
        # Disable hard limits
        self.send_command('$21=0')
        
        # Try unlock again
        print("   Attempting unlock with hard limits disabled...")
        self.send_command('$X')
        time.sleep(0.5)
        
        # Check status
        status = self.get_status()
        if status:
            print(f"   Status: {status}")
            
            if 'Alarm' not in status:
                print("   ✅ Unlocked! Re-enabling hard limits...")
                self.send_command('$21=1')
                
                print("   Now try homing...")
                proceed = input("   Proceed with X-axis homing? (y/n): ").lower().strip()
                if proceed in ['y', 'yes']:
                    self.send_command('$HX', wait_time=10.0)
                    final_status = self.get_status()
                    if final_status:
                        print(f"   Final status: {final_status}")
            else:
                print("   ❌ Still locked. Check hardware connections.")
                print("   Re-enabling hard limits...")
                self.send_command('$21=1')

def main():
    fixer = ProbeAlarmFixer()
    fixer.fix_probe_alarm()

if __name__ == "__main__":
    main()