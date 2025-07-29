#!/usr/bin/env python3
"""
Simple GRBL test script - minimal setup to test motor movements
"""

import serial
import time
import threading

class SimpleGrblTest:
    def __init__(self, port='/dev/ttyACM0', baudrate=115200):
        self.serial = serial.Serial(port, baudrate, timeout=1)
        time.sleep(2)  # Wait for connection
        
        # Clear any startup messages
        while self.serial.in_waiting:
            line = self.serial.readline().decode('utf-8').strip()
            print(f"Startup: {line}")
        
        print("GRBL connection established")
    
    def send_command(self, command):
        """Send a command and wait for OK"""
        print(f"Sending: {command}")
        self.serial.write((command + "\n").encode('utf-8'))
        
        # Wait for response
        timeout = time.time() + 5
        while time.time() < timeout:
            if self.serial.in_waiting:
                response = self.serial.readline().decode('utf-8').strip()
                print(f"Response: {response}")
                if response == "ok" or response.startswith("error"):
                    return response
        return "TIMEOUT"
    
    def get_status(self):
        """Get current status"""
        print("Getting status...")
        self.serial.write(b"?\n")
        time.sleep(0.1)
        
        while self.serial.in_waiting:
            response = self.serial.readline().decode('utf-8').strip()
            print(f"Status: {response}")
    
    def close(self):
        self.serial.close()

def main():
    print("Simple GRBL Test")
    print("================")
    
    try:
        grbl = SimpleGrblTest()
        
        # Get initial status
        grbl.get_status()
        
        # Reset work coordinates
        print("\n--- Resetting work coordinates ---")
        grbl.send_command("G10 P1 L20 X0 Y0 Z0 A0")
        grbl.get_status()
        
        # Test different unit modes and movements
        print("\n--- Testing MM mode ---")
        grbl.send_command("G21")  # mm mode
        grbl.send_command("G90")  # absolute mode
        grbl.get_status()
        
        print("Moving 1mm in X...")
        grbl.send_command("$J=G91 G21 X1.0 F100")
        time.sleep(2)
        grbl.get_status()
        
        print("Moving 25.4mm in X (should be 1 inch)...")
        grbl.send_command("$J=G91 G21 X25.4 F100")
        time.sleep(3)
        grbl.get_status()
        
        print("\n--- Testing INCH mode ---")
        grbl.send_command("G20")  # inch mode
        grbl.get_status()
        
        print("Moving 0.1 inch in X...")
        grbl.send_command("$J=G91 G20 X0.1 F4")
        time.sleep(2)
        grbl.get_status()
        
        print("Moving 1.0 inch in X...")
        grbl.send_command("$J=G91 G20 X1.0 F4")
        time.sleep(3)
        grbl.get_status()
        
        # Check GRBL settings
        print("\n--- GRBL Settings ---")
        grbl.send_command("$$")
        time.sleep(2)
        
        # Get final status
        print("\n--- Final Status ---")
        grbl.get_status()
        
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