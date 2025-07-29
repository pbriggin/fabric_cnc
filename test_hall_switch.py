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
                'status_raw': status_line
            }
        else:
            return {
                'x_limit': False,
                'y_limit': False,
                'z_limit': False,
                'status_raw': status_line
            }
    
    def test_hall_switch(self):
        """Test the X-axis hall effect switch."""
        print("\n" + "="*60)
        print("X-AXIS HALL EFFECT SWITCH TEST")
        print("="*60)
        
        if not self.connect():
            return False
        
        # Get GRBL info
        print("\nGetting GRBL information...")
        info = self.send_command('$I')
        if info:
            for line in info:
                if 'FIRMWARE' in line or 'VER:' in line:
                    print(f"  {line}")
        
        print("\nTesting hall effect switch...")
        print("\nINSTRUCTIONS:")
        print("1. Watch the 'X Limit' status below")
        print("2. Manually trigger the X-axis hall effect sensor")
        print("3. You should see 'X Limit' change from OFF to ON")
        print("4. Release the sensor - it should change back to OFF")
        print("5. Press Ctrl+C to exit when done")
        
        print("\nMonitoring switch status (press Ctrl+C to exit):")
        print("-" * 50)
        
        last_x_state = None
        
        try:
            while True:
                status = self.get_status()
                if status:
                    parsed = self.parse_status(status)
                    if parsed:
                        x_state = parsed['x_limit']
                        
                        # Only print when state changes or every 20 iterations
                        if x_state != last_x_state:
                            state_text = "ON " if x_state else "OFF"
                            symbol = "●" if x_state else "○"
                            print(f"X Limit: {symbol} {state_text}  ", end="")
                            
                            if x_state != last_x_state and last_x_state is not None:
                                if x_state:
                                    print("← SENSOR TRIGGERED!")
                                else:
                                    print("← SENSOR RELEASED!")
                            else:
                                print()
                            
                            last_x_state = x_state
                
                time.sleep(0.1)  # Check 10 times per second
                
        except KeyboardInterrupt:
            print("\n\nTest completed!")
            
        finally:
            if self.serial:
                self.serial.close()
                print("Disconnected from GRBL")
    
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