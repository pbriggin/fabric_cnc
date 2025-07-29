#!/usr/bin/env python3
"""
Fix GRBL settings for correct motor movement
"""

import serial
import time

class GrblSettingsFix:
    def __init__(self, port='/dev/ttyACM0', baudrate=115200):
        self.serial = serial.Serial(port, baudrate, timeout=1)
        time.sleep(2)
        
        # Clear startup messages
        while self.serial.in_waiting:
            line = self.serial.readline().decode('utf-8').strip()
            print(f"Startup: {line}")
    
    def send_command(self, command):
        """Send command and wait for response"""
        print(f"Sending: {command}")
        self.serial.write((command + "\n").encode('utf-8'))
        
        timeout = time.time() + 5
        while time.time() < timeout:
            if self.serial.in_waiting:
                response = self.serial.readline().decode('utf-8').strip()
                print(f"Response: {response}")
                if response == "ok" or response.startswith("error"):
                    return response
        return "TIMEOUT"
    
    def get_current_settings(self):
        """Get current GRBL settings"""
        print("Current GRBL Settings:")
        self.send_command("$$")
        time.sleep(2)
    
    def fix_steps_per_mm(self):
        """Fix the steps/mm settings based on observed behavior"""
        print("\n=== Fixing Steps/mm Settings ===")
        
        # Current setting: $100=250 (X steps/mm)
        # Observed: 1mm command = 1" actual movement
        # 1" = 25.4mm, so we need 250/25.4 = ~9.84 steps/mm
        
        correct_steps_per_mm = 250 / 25.4  # ~9.84
        
        print(f"Current X steps/mm: 250")
        print(f"Calculated correct X steps/mm: {correct_steps_per_mm:.2f}")
        print(f"Setting $100={correct_steps_per_mm:.2f}")
        
        # Set the corrected value
        self.send_command(f"$100={correct_steps_per_mm:.2f}")
        
        # Also fix Y axes (assuming same issue)
        print(f"Setting Y axes to same value...")
        self.send_command(f"$101={correct_steps_per_mm:.2f}")  # Y1
        self.send_command(f"$102={correct_steps_per_mm:.2f}")  # Y2 or Z
        
        # Keep rotation axis as is (probably correct)
        print("Keeping $103 (rotation) unchanged")
        
        # Save settings
        print("Saving settings to EEPROM...")
        # Settings are automatically saved in GRBL
        
    def test_corrected_movement(self):
        """Test movement after correction"""
        print("\n=== Testing Corrected Movement ===")
        
        # Get position
        self.send_command("?")
        time.sleep(1)
        
        # Reset work coordinates
        self.send_command("G10 P1 L20 X0 Y0 Z0 A0")
        
        # Test 1mm movement
        print("Testing 1mm X movement...")
        self.send_command("$J=G91 G21 X1.0 F100")
        time.sleep(2)
        self.send_command("?")
        time.sleep(1)
        
        # Test 25.4mm movement (should be 1 inch)
        print("Testing 25.4mm X movement (should be 1 inch)...")
        self.send_command("$J=G91 G21 X25.4 F100")
        time.sleep(3)
        self.send_command("?")
        time.sleep(1)
    
    def close(self):
        self.serial.close()

def main():
    print("GRBL Settings Fix Script")
    print("========================")
    
    try:
        grbl = GrblSettingsFix()
        
        # Show current settings
        grbl.get_current_settings()
        
        # Ask for confirmation
        print("\nThis will change your GRBL $100, $101, $102 settings.")
        print("Current X steps/mm: 250")
        print("New X steps/mm: ~9.84")
        confirm = input("Continue? (y/N): ").strip().lower()
        
        if confirm == 'y':
            grbl.fix_steps_per_mm()
            grbl.test_corrected_movement()
            print("\nSettings updated! Test the movement and see if 1mm = 1mm now.")
        else:
            print("Cancelled.")
        
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