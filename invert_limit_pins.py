#!/usr/bin/env python3
"""
Invert limit switch pins to match your hardware wiring.

Since Y, Z, A switches are reading opposite (normally closed instead of normally open),
we need to invert those pins in GRBL settings.
"""

import serial
import time

class LimitPinInverter:
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
    
    def get_current_invert_setting(self):
        """Get current limit pin invert mask setting."""
        print("Getting current limit pin invert mask setting ($5)...")
        
        responses = self.send_command('$$', wait_time=1.0)
        
        for line in responses:
            if line.startswith('$5='):
                current_value = line.split('=')[1]
                print(f"Current $5 (limit pins invert mask): {current_value}")
                return int(current_value)
        
        print("Could not find $5 setting")
        return None
    
    def explain_invert_mask(self):
        """Explain how the invert mask works."""
        print("\n" + "="*60)
        print("LIMIT PIN INVERT MASK EXPLANATION")
        print("="*60)
        print()
        print("The invert mask ($5) is a binary number where each bit represents an axis:")
        print("  Bit 0 (value 1)  = X-axis limit pin")
        print("  Bit 1 (value 2)  = Y-axis limit pin") 
        print("  Bit 2 (value 4)  = Z-axis limit pin")
        print("  Bit 3 (value 8)  = A-axis limit pin")
        print("  Bit 4 (value 16) = B-axis limit pin")
        print("  Bit 5 (value 32) = C-axis limit pin")
        print()
        print("Based on your test results:")
        print("  ✓ X-axis is correct (normally open)")
        print("  ✗ Y-axis needs inversion (normally closed)")
        print("  ✗ Z-axis needs inversion (normally closed)")
        print("  ✗ A-axis needs inversion (normally closed)")
        print()
        print("We need to invert Y(2) + Z(4) + A(8) = 14")
        print()
    
    def invert_limit_pins(self):
        """Invert the Y, Z, A limit pins."""
        print("="*60)
        print("INVERTING LIMIT SWITCH PINS")
        print("="*60)
        
        if not self.connect():
            return
        
        try:
            # Show explanation
            self.explain_invert_mask()
            
            # Get current setting
            current_value = self.get_current_invert_setting()
            if current_value is None:
                print("❌ Could not get current invert mask setting")
                return
            
            # Calculate new value
            # We want to invert Y(2), Z(4), A(8) = 2 + 4 + 8 = 14
            new_value = 14
            
            print(f"\nProposed change:")
            print(f"  Current $5 value: {current_value}")
            print(f"  New $5 value: {new_value}")
            print(f"  This will invert: Y, Z, A limit pins")
            print(f"  X-axis will remain unchanged")
            
            # Ask for confirmation
            proceed = input(f"\nApply this setting? (y/n): ").lower().strip()
            
            if proceed in ['y', 'yes']:
                print(f"\nSetting $5={new_value}...")
                self.send_command(f'$5={new_value}')
                
                print("\n✅ Limit pin invert mask updated!")
                print("\nNow test your switches again:")
                print("  python test_hall_switch.py")
                print("\nAll switches should now read OFF when not triggered")
                print("and ON only when physically activated.")
                
            else:
                print("Setting not changed.")
                
        except KeyboardInterrupt:
            print("\n⚠️  Operation cancelled by user")
            
        finally:
            if self.serial:
                self.serial.close()
                print("\nDisconnected from GRBL")
    
    def test_after_inversion(self):
        """Quick test after pin inversion."""
        print("="*60)
        print("TESTING AFTER PIN INVERSION")
        print("="*60)
        
        if not self.connect():
            return
        
        try:
            print("Getting current switch states...")
            
            # Get status a few times to see current state
            for i in range(3):
                self.serial.write(b'?\n')
                time.sleep(0.1)
                
                while self.serial.in_waiting:
                    line = self.serial.readline().decode().strip()
                    if line.startswith('<') and line.endswith('>'):
                        print(f"  Status {i+1}: {line}")
                        
                        # Parse pins
                        if 'Pn:' in line:
                            pins = line.split('Pn:')[1].split('|')[0]
                            if pins:
                                print(f"    Active pins: {pins}")
                            else:
                                print("    ✅ No pins active - switches reading correctly!")
                        else:
                            print("    ✅ No pins active - switches reading correctly!")
                        break
                
                time.sleep(0.5)
            
            print("\nIf all switches now show 'No pins active' when not triggered,")
            print("the inversion was successful!")
            
        finally:
            if self.serial:
                self.serial.close()
                print("\nDisconnected from GRBL")

def main():
    import sys
    
    inverter = LimitPinInverter()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        inverter.test_after_inversion()
    else:
        inverter.invert_limit_pins()

if __name__ == "__main__":
    main()