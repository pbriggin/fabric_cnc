#!/usr/bin/env python3
"""
GRBL HAL Diagnostic Test
Shows exactly how GRBL HAL responds to commands and position requests
"""

import serial
import time
import re

class GrblDiagnostic:
    def __init__(self, port='/dev/ttyACM0', baudrate=115200):
        print("Connecting to GRBL...")
        self.serial = serial.Serial(port, baudrate, timeout=1)
        time.sleep(2)
        
        # Clear startup messages
        while self.serial.in_waiting:
            line = self.serial.readline().decode('utf-8').strip()
            print(f"[STARTUP] {line}")
        
        print("GRBL connection established\n")
    
    def send_and_show_response(self, command, wait_time=1):
        """Send command and show all responses"""
        print(f">>> SENDING: {command}")
        self.serial.write((command + "\n").encode('utf-8'))
        
        time.sleep(wait_time)
        
        responses = []
        while self.serial.in_waiting:
            response = self.serial.readline().decode('utf-8').strip()
            responses.append(response)
            print(f"<<< RESPONSE: {response}")
            
            # Parse position if it's a status response
            if response.startswith('<') and 'MPos:' in response:
                match = re.search(r"MPos:([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)", response)
                if match:
                    pos = [float(match.group(i)) for i in range(1, 5)]
                    print(f"    PARSED POSITION: X={pos[0]}, Y={pos[1]}, Z={pos[2]}, A={pos[3]}")
        
        if not responses:
            print("<<< NO RESPONSE")
        
        print()
        return responses
    
    def diagnostic_sequence(self):
        """Run complete diagnostic sequence"""
        print("=== GRBL HAL DIAGNOSTIC SEQUENCE ===\n")
        
        # 1. Get initial status
        print("1. Getting initial status...")
        self.send_and_show_response("?")
        
        # 2. Reset work coordinates
        print("2. Resetting work coordinates...")
        self.send_and_show_response("G10 P1 L20 X0 Y0 Z0 A0")
        self.send_and_show_response("?")
        
        # 3. Set to mm mode
        print("3. Setting to mm mode (G21)...")
        self.send_and_show_response("G21")
        self.send_and_show_response("?")
        
        # 4. Small movement test
        print("4. Small movement test (1mm X)...")
        self.send_and_show_response("$J=G91 G21 X1.0 F100", wait_time=2)
        self.send_and_show_response("?")
        
        # 5. Wait for movement to complete and check again
        print("5. Wait and check position again...")
        time.sleep(2)
        self.send_and_show_response("?")
        
        # 6. Another small movement
        print("6. Another movement test (5mm X)...")
        self.send_and_show_response("$J=G91 G21 X5.0 F100", wait_time=3)
        time.sleep(2)
        self.send_and_show_response("?")
        
        # 7. Try inch mode
        print("7. Testing inch mode (G20)...")
        self.send_and_show_response("G20")
        self.send_and_show_response("?")
        
        # 8. Movement in inch mode
        print("8. Movement in inch mode (0.1 inch X)...")
        self.send_and_show_response("$J=G91 G20 X0.1 F4", wait_time=3)
        time.sleep(2)
        self.send_and_show_response("?")
        
        # 9. Back to mm mode
        print("9. Back to mm mode...")
        self.send_and_show_response("G21")
        self.send_and_show_response("?")
        
        # 10. Final position check
        print("10. Final position check...")
        self.send_and_show_response("?")
        
        print("=== END DIAGNOSTIC ===")
    
    def interactive_test(self):
        """Interactive testing"""
        print("\n=== INTERACTIVE TEST ===")
        print("Commands: ? (status), x+ (move +1mm), x- (move -1mm), q (quit)")
        
        while True:
            cmd = input("Enter command: ").strip().lower()
            
            if cmd == 'q':
                break
            elif cmd == '?':
                self.send_and_show_response("?")
            elif cmd == 'x+':
                self.send_and_show_response("$J=G91 G21 X1.0 F100", wait_time=2)
                time.sleep(1)
                self.send_and_show_response("?")
            elif cmd == 'x-':
                self.send_and_show_response("$J=G91 G21 X-1.0 F100", wait_time=2)
                time.sleep(1)
                self.send_and_show_response("?")
            else:
                print("Unknown command")
    
    def close(self):
        self.serial.close()

def main():
    print("GRBL HAL Diagnostic Test")
    print("========================")
    
    try:
        grbl = GrblDiagnostic()
        grbl.diagnostic_sequence()
        grbl.interactive_test()
        
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