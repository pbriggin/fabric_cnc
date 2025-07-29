#!/usr/bin/env python3
"""
Simple test script for X-axis hall effect limit switch.

This script tests if the X-axis hall effect switch is properly connected
and working with your grblHAL controller.
"""

import serial
import time
import re
import sys

class SimpleHallSwitchTester:
    def __init__(self, port='/dev/ttyACM0', baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.running = True
        
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
    
    def send_command(self, command):
        """Send a command to GRBL and get response."""
        if not self.serial:
            return None
            
        try:
            self.serial.write((command + '\n').encode())
            time.sleep(0.1)
            
            response = []
            while self.serial.in_waiting:
                line = self.serial.readline().decode().strip()
                if line:
                    response.append(line)
            
            return response
        except Exception as e:
            print(f"Command error: {e}")
            return None
    
    def get_status(self):
        """Get current machine status."""
        try:
            self.serial.write(b'?\n')
            time.sleep(0.05)
            
            while self.serial.in_waiting:
                line = self.serial.readline().decode().strip()
                if line.startswith('<') and line.endswith('>'):
                    return line
            
            return None
        except:
            return None
    
    def parse_status(self, status_line):
        """Parse GRBL status line for limit switch information."""
        if not status_line:
            return None
            
        # Look for limit switch indicators in status
        # Format: <Idle|MPos:0.000,0.000,0.000,0.000|FS:0,0|Pn:XYZ>
        # Pn: shows which pins are triggered (X=X limit, Y=Y limit, etc.)
        
        pin_match = re.search(r'Pn:([^|>]*)', status_line)
        if pin_match:
            pins = pin_match.group(1)
            return {
                'x_limit': 'X' in pins,
                'y_limit': 'Y' in pins,
                'z_limit': 'Z' in pins,
                'a_limit': 'A' in pins,  # A-axis (rotation)
                'probe': 'P' in pins,    # Probe pin
                'pins_raw': pins,
                'status_raw': status_line
            }
        else:
            return {
                'x_limit': False,
                'y_limit': False,
                'z_limit': False,
                'a_limit': False,
                'probe': False,
                'pins_raw': '',
                'status_raw': status_line
            }
    
    def test_all_hall_switches(self):
        """Test all hall effect switches."""
        print("\n" + "="*70)
        print("ALL HALL EFFECT SWITCHES TEST")
        print("="*70)
        
        if not self.connect():
            return False
        
        # Get GRBL info
        print("\nGetting GRBL information...")
        info = self.send_command('$I')
        if info:
            for line in info:
                if 'FIRMWARE' in line or 'VER:' in line or 'AXS:' in line:
                    print(f"  {line}")
        
        print("\nTesting all hall effect switches...")
        print("\nINSTRUCTIONS:")
        print("1. Watch the switch status display below")
        print("2. Manually trigger each hall effect sensor one at a time")
        print("3. You should see the corresponding switch change from OFF to ON")
        print("4. Release the sensor - it should change back to OFF")
        print("5. Test all axes: X, Y, Z, and A (rotation)")
        print("6. Press Ctrl+C to exit when done")
        
        print("\nMonitoring all switches (press Ctrl+C to exit):")
        print("-" * 70)
        
        # Track last states for all switches
        last_states = {
            'x_limit': None,
            'y_limit': None, 
            'z_limit': None,
            'a_limit': None,
            'probe': None
        }
        
        # Display header
        print("X-Limit | Y-Limit | Z-Limit | A-Limit | Probe | Raw Pins")
        print("-" * 70)
        
        try:
            while True:
                status = self.get_status()
                if status:
                    parsed = self.parse_status(status)
                    if parsed:
                        current_states = {
                            'x_limit': parsed['x_limit'],
                            'y_limit': parsed['y_limit'],
                            'z_limit': parsed['z_limit'],
                            'a_limit': parsed['a_limit'],
                            'probe': parsed['probe']
                        }
                        
                        # Check if any state changed
                        state_changed = any(current_states[key] != last_states[key] for key in current_states)
                        
                        if state_changed or all(v is None for v in last_states.values()):
                            # Format display
                            x_display = "●  ON " if current_states['x_limit'] else "○ OFF "
                            y_display = "●  ON " if current_states['y_limit'] else "○ OFF "
                            z_display = "●  ON " if current_states['z_limit'] else "○ OFF "
                            a_display = "●  ON " if current_states['a_limit'] else "○ OFF "
                            p_display = "●  ON " if current_states['probe'] else "○ OFF "
                            
                            pins_display = parsed['pins_raw'] if parsed['pins_raw'] else "none"
                            
                            print(f"{x_display} | {y_display} | {z_display} | {a_display} | {p_display} | {pins_display}")
                            
                            # Show what changed
                            changes = []
                            for key in current_states:
                                if last_states[key] is not None and current_states[key] != last_states[key]:
                                    axis_name = key.replace('_limit', '').replace('probe', 'Probe').upper()
                                    if current_states[key]:
                                        changes.append(f"{axis_name} TRIGGERED")
                                    else:
                                        changes.append(f"{axis_name} RELEASED")
                            
                            if changes:
                                print(f"  → {', '.join(changes)}")
                            
                            last_states = current_states.copy()
                
                time.sleep(0.1)  # Check 10 times per second
                
        except KeyboardInterrupt:
            print("\n\nTest completed!")
            
        finally:
            if self.serial:
                self.serial.close()
                print("Disconnected from GRBL")
    
    def test_hall_switch(self):
        """Test the X-axis hall effect switch (legacy method)."""
        return self.test_all_hall_switches()
    
    def quick_status_check(self):
        """Quick check of current limit switch status."""
        print("Quick status check...")
        
        if not self.connect():
            return
            
        try:
            status = self.get_status()
            if status:
                parsed = self.parse_status(status)
                if parsed:
                    print(f"X Limit Switch: {'ON' if parsed['x_limit'] else 'OFF'}")
                    print(f"Y Limit Switch: {'ON' if parsed['y_limit'] else 'OFF'}")
                    print(f"Z Limit Switch: {'ON' if parsed['z_limit'] else 'OFF'}")
                    print(f"Raw Status: {parsed['status_raw']}")
                else:
                    print("Could not parse status")
            else:
                print("No status received")
                
        finally:
            if self.serial:
                self.serial.close()

def main():
    tester = SimpleHallSwitchTester()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        tester.quick_status_check()
    else:
        tester.test_hall_switch()

if __name__ == "__main__":
    main()