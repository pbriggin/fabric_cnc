#!/usr/bin/env python3
"""
X Sensor Debounce Demonstration
This script demonstrates the improved debouncing system for the X hall effect sensor.
"""

import time
import logging
from motor_control.motor_controller import MotorController

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def demonstrate_x_debounce():
    """Demonstrate the X sensor debouncing improvements."""
    logger.info("=== X Sensor Debounce Demonstration ===")
    
    # Create motor controller
    motor_controller = MotorController()
    
    # Show current settings
    logger.info(f"X sensor debounce time: {motor_controller.get_sensor_debounce_time('X'):.1f}ms")
    logger.info(f"Reading count required: {motor_controller._sensor_reading_count}")
    logger.info(f"All sensor debounce times: {motor_controller.get_sensor_debounce_time()}")
    
    logger.info("\nMonitoring X sensor for 10 seconds...")
    logger.info("Move a magnet near the X hall effect sensor to see debouncing in action")
    logger.info("Press Ctrl+C to stop early\n")
    
    start_time = time.time()
    trigger_count = 0
    last_trigger_time = 0
    
    try:
        while time.time() - start_time < 10:
            # Check sensor with enhanced debouncing
            is_triggered = motor_controller._check_sensor('X')
            
            if is_triggered:
                current_time = time.time()
                time_since_last = current_time - last_trigger_time
                
                if time_since_last > 0.05:  # Only log if >50ms since last trigger
                    trigger_count += 1
                    logger.info(f"Trigger #{trigger_count}: X sensor triggered (debounced)")
                    last_trigger_time = current_time
            
            time.sleep(0.01)  # 10ms polling interval
            
    except KeyboardInterrupt:
        logger.info("\nDemonstration stopped by user")
    
    logger.info(f"\nDemonstration complete!")
    logger.info(f"Total triggers detected: {trigger_count}")
    logger.info(f"Average trigger rate: {trigger_count / 10:.1f} triggers/second")
    
    # Cleanup
    motor_controller.cleanup()

def show_debounce_improvements():
    """Show what improvements were made to the debouncing system."""
    logger.info("=== Debounce Improvements Summary ===")
    logger.info("1. Individual debounce times per sensor:")
    logger.info("   - X sensor: 25ms (increased from 10ms)")
    logger.info("   - Y sensors: 15ms")
    logger.info("   - Z sensors: 20ms")
    logger.info("")
    logger.info("2. Multi-reading confirmation:")
    logger.info("   - Takes 3 readings per check")
    logger.info("   - Requires majority (2/3) to be consistent")
    logger.info("   - Maintains history of readings for stability")
    logger.info("")
    logger.info("3. Enhanced noise immunity:")
    logger.info("   - Prevents false triggers from electrical noise")
    logger.info("   - More reliable homing operations")
    logger.info("   - Configurable via config.py")
    logger.info("")
    logger.info("4. Configuration options:")
    logger.info("   - Adjust debounce times per sensor")
    logger.info("   - Change reading count requirements")
    logger.info("   - Environment variable support")

if __name__ == "__main__":
    show_debounce_improvements()
    print("\n" + "="*50 + "\n")
    demonstrate_x_debounce() 