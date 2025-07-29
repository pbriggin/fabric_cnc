#!/usr/bin/env python3
"""
Check and configure GRBL settings for proper homing operation.

Since the hall effect switch is working, this script will verify
and configure GRBL settings for successful homing.
"""

import serial
import time
import sys

class GRBLConfigChecker:
    def __init__(self, port='/dev/ttyACM0', baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        
    def connect(self):
        """Connect to GRBL controller."""
        try:
            print(f"Connecting to GRBL on {self.port}...")
            self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Wait for GRBL to initialize
            print("✓ Connected to GRBL")
            return True
        except Exception as e:
            print(f"✗ Failed to connect: {e}")
            return False
    
    def send_command(self, command, wait_time=0.5):
        """Send a command to GRBL and get response."""
        if not self.serial:
            return []
            
        try:
            self.serial.write((command + '\n').encode())
            time.sleep(wait_time)
            
            response = []
            while self.serial.in_waiting:
                line = self.serial.readline().decode().strip()
                if line and line != 'ok':
                    response.append(line)
            
            return response
        except Exception as e:
            print(f"Command error: {e}")
            return []
    
    def get_current_settings(self):
        """Get current GRBL settings."""
        print("Getting current GRBL settings...")
        settings = {}
        
        responses = self.send_command('$$', wait_time=1.0)
        
        for line in responses:
            if line.startswith('$') and '=' in line:
                parts = line.split('=')
                if len(parts) == 2:
                    setting = parts[0]
                    value = parts[1]
                    settings[setting] = value
        
        return settings
    
    def check_homing_settings(self):
        """Check critical homing settings."""
        print("\n" + "="*60)
        print("GRBL HOMING CONFIGURATION CHECK")
        print("="*60)
        
        if not self.connect():
            return False
        
        try:
            settings = self.get_current_settings()
            
            if not settings:
                print("✗ Could not retrieve GRBL settings")
                return False
            
            print("\nChecking critical homing settings:")
            print("-" * 40)
            
            # Critical settings for homing
            critical_settings = {
                '$21': ('Hard limits enable', '1'),
                '$22': ('Homing cycle enable', '1'), 
                '$23': ('Homing direction invert mask', '0'),
                '$24': ('Homing seek rate (mm/min)', '508'),
                '$25': ('Homing feed rate (mm/min)', '51'),
                '$26': ('Homing debounce (ms)', '250'),
                '$27': ('Homing pull-off (mm)', '1.0'),
                '$130': ('X max travel (mm)', '1727.0'),
                '$131': ('Y max travel (mm)', '1143.0'),
                '$132': ('Z max travel (mm)', '127.0'),
            }
            
            issues = []
            
            for setting, (description, expected) in critical_settings.items():
                current = settings.get(setting, 'NOT SET')
                
                if current == expected:
                    print(f"✓ {setting} ({description}): {current}")
                else:
                    print(f"✗ {setting} ({description}): {current} (expected: {expected})")
                    issues.append((setting, expected, current))
            
            # Check if machine is in alarm state
            print(f"\nChecking machine status...")
            status_response = self.send_command('?', wait_time=0.2)
            if status_response:
                status = status_response[0] if status_response else ""
                print(f"Current status: {status}")
                
                if 'Alarm' in status:
                    print("⚠️  Machine is in ALARM state - this will prevent homing")
                    print("   Try sending '$X' to clear alarm state")
            
            if issues:
                print(f"\n⚠️  Found {len(issues)} configuration issues")
                print("\nWould you like to fix these settings? (y/n): ", end="")
                response = input().lower().strip()
                
                if response in ['y', 'yes']:
                    self.fix_settings(issues)
                else:
                    print("Settings not changed. You can run this script again to fix them.")
            else:
                print("\n✅ All homing settings look correct!")
                print("\nSince your hall effect switch works and settings are correct,")
                print("try clearing any alarm state and attempt homing:")
                print("  1. Send: $X  (clear alarm)")
                print("  2. Try homing: $HX")
                
        finally:
            if self.serial:
                self.serial.close()
    
    def fix_settings(self, issues):
        """Fix the problematic settings."""
        print(f"\nFixing {len(issues)} settings...")
        
        for setting, expected, current in issues:
            print(f"Setting {setting} = {expected} (was: {current})")
            command = f"{setting}={expected}"
            response = self.send_command(command, wait_time=0.3)
            
            # Check for errors
            if any('error' in r.lower() for r in response):
                print(f"  ✗ Error setting {setting}: {response}")
            else:
                print(f"  ✓ {setting} updated")
        
        print("\n✅ Settings updated! Try homing now:")
        print("  1. Clear any alarms: $X")
        print("  2. Home X-axis: $HX")
    
    def clear_alarm_and_test_home(self):
        """Clear alarm state and test X-axis homing."""
        print("\n" + "="*60)
        print("CLEAR ALARM AND TEST HOMING")
        print("="*60)
        
        if not self.connect():
            return
        
        try:
            # Clear alarm state
            print("Clearing alarm state...")
            self.send_command('$X')
            time.sleep(0.5)
            
            # Check status
            status_response = self.send_command('?', wait_time=0.2)
            if status_response:
                print(f"Status after alarm clear: {status_response[0]}")
            
            print("\nAttempting X-axis homing...")
            print("⚠️  Make sure the X-axis can move freely and won't crash!")
            print("Press Enter to continue or Ctrl+C to cancel: ", end="")
            input()
            
            # Attempt homing
            print("Sending $HX command...")
            response = self.send_command('$HX', wait_time=5.0)
            
            if response:
                for line in response:
                    if 'error' in line.lower():
                        print(f"❌ Homing failed: {line}")
                    else:
                        print(f"Response: {line}")
            
            # Check final status
            final_status = self.send_command('?', wait_time=0.2)
            if final_status:
                print(f"Final status: {final_status[0]}")
                
        except KeyboardInterrupt:
            print("\n⚠️  Homing test cancelled by user")
            
        finally:
            if self.serial:
                self.serial.close()

def main():
    checker = GRBLConfigChecker()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test-home":
        checker.clear_alarm_and_test_home()
    else:
        checker.check_homing_settings()

if __name__ == "__main__":
    main()