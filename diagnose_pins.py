#!/usr/bin/env python3
"""
Diagnose and fix pin state issues preventing homing.
"""

import serial
import time

class PinDiagnostic:
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
    
    def diagnose_pin_issue(self):
        """Diagnose why multiple pins are triggered."""
        print("="*60)
        print("PIN STATE DIAGNOSTIC")
        print("="*60)
        
        if not self.connect():
            return
        
        try:
            # Get current status
            print("\n1. Current machine status:")
            status = self.get_status()
            if status:
                print(f"   {status}")
                
                # Parse pin states
                if 'Pn:' in status:
                    pins = status.split('Pn:')[1].split('|')[0]
                    print(f"\n   Active pins: {pins}")
                    print("   Pin meanings:")
                    if 'X' in pins: print("     X = X-axis limit switch active")
                    if 'Y' in pins: print("     Y = Y-axis limit switch active") 
                    if 'Z' in pins: print("     Z = Z-axis limit switch active")
                    if 'A' in pins: print("     A = A-axis (rotation) limit switch active")
                    if 'P' in pins: print("     P = Probe pin active")
                    
                    print(f"\n   ⚠️  Problem: {len(pins)} pins are active simultaneously")
                    print("      GRBL won't home when multiple limit switches are triggered")
            
            # Possible solutions
            print("\n2. Possible causes and solutions:")
            print("   a) Limit switches wired incorrectly (normally open vs normally closed)")
            print("   b) Machine is physically against multiple limit switches")
            print("   c) Electrical noise or wiring issues")
            print("   d) Pin configuration in GRBL doesn't match your hardware")
            
            # Try to clear alarm more aggressively
            print("\n3. Attempting aggressive alarm clear...")
            
            # First disable hard limits temporarily
            print("   Temporarily disabling hard limits...")
            self.send_command('$21=0')
            
            # Clear alarm
            print("   Clearing alarm...")
            self.send_command('$X')
            
            # Check status
            status = self.get_status()
            if status:
                print(f"   Status after alarm clear: {status}")
                
                if 'Alarm' not in status:
                    print("   ✅ Alarm cleared!")
                    
                    # Re-enable hard limits
                    print("   Re-enabling hard limits...")
                    self.send_command('$21=1')
                    
                    # Try homing now
                    print("\n4. Attempting X-axis homing with cleared alarm...")
                    proceed = input("   Proceed with homing? (y/n): ").lower().strip()
                    
                    if proceed in ['y', 'yes']:
                        responses = self.send_command('$HX', wait_time=10.0)
                        
                        # Check final status
                        final_status = self.get_status()
                        if final_status:
                            print(f"   Final status: {final_status}")
                else:
                    print("   ❌ Still in alarm state")
                    print("\n   HARDWARE DIAGNOSIS NEEDED:")
                    print("   1. Check if machine is physically touching multiple limit switches")
                    print("   2. Verify limit switch wiring (all should be normally open)")
                    print("   3. Check for loose connections or electrical noise")
                    
                    # Show how to override for testing
                    print("\n   EMERGENCY OVERRIDE (for testing only):")
                    print("   You can disable hard limits entirely with: $21=0")
                    print("   Then manually move away from switches and re-enable: $21=1")
                    print("   ⚠️  WARNING: This disables crash protection!")
            
        except KeyboardInterrupt:
            print("\n⚠️  Operation cancelled by user")
            
        finally:
            if self.serial:
                self.serial.close()
                print("\nDisconnected from GRBL")

def main():
    diagnostic = PinDiagnostic()
    diagnostic.diagnose_pin_issue()

if __name__ == "__main__":
    main()