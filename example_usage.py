#!/usr/bin/env python3
"""
Example usage of the EMI-resistant homing system.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from fabric_cnc.motor_control.emi_resistant_homing import EMIResistantHoming

def main():
    """Example of how to use the EMI-resistant homing system."""
    
    # Create EMI-resistant homing system with custom parameters
    homing = EMIResistantHoming(
        debounce_ms=100,           # 100ms debounce time
        filter_samples=7,          # 7-sample filtering
        interference_threshold=3,  # 3 rapid triggers = interference
        verify_distance_mm=5.0     # 5mm verification distance
    )
    
    print("EMI-Resistant Homing System Example")
    print("===================================")
    
    # Monitor sensors for 10 seconds
    print("\nMonitoring sensors for 10 seconds...")
    import time
    start_time = time.time()
    
    while time.time() - start_time < 10:
        status = homing.get_sensor_status()
        
        # Clear screen and print status
        print("\033[F" * 8)  # Move cursor up
        print("\nSensor Status:")
        print("---------------")
        
        for name, info in status.items():
            raw = "DETECTED" if info['raw_state'] else "CLEAR"
            filtered = "DETECTED" if info['filtered_state'] else "CLEAR"
            interference = "⚠️ EMI" if info['interference_detected'] else "OK"
            
            print(f"{name}: {filtered}/{raw} {interference} (triggers: {info['trigger_count']})")
        
        time.sleep(0.1)
    
    print("\nMonitoring complete!")
    
    # Example of how to use in homing
    print("\nExample homing usage:")
    print("1. Create EMI-resistant homing system")
    print("2. Call homing.home_axis_with_emi_resistance('X', motor_controller)")
    print("3. System will automatically handle EMI filtering and verification")
    
    # Cleanup
    homing.cleanup()

if __name__ == "__main__":
    main() 