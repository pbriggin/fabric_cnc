#!/usr/bin/env python3
"""
Enhanced debounce test script for hall effect sensors.
This script demonstrates the improved debouncing system with individual sensor times
and multi-reading confirmation.
"""

import time
import RPi.GPIO as GPIO
import logging
from motor_control.motor_controller import MotorController

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Disable GPIO warnings
GPIO.setwarnings(False)

class EnhancedDebounceTester:
    def __init__(self):
        self.motor_controller = MotorController()
        self.test_duration = 30  # seconds
        self.trigger_count = 0
        self.false_trigger_count = 0
        
    def test_x_sensor_debounce(self):
        """Test the X sensor with enhanced debouncing."""
        logger.info("=== Enhanced X Sensor Debounce Test ===")
        logger.info(f"Test duration: {self.test_duration} seconds")
        logger.info(f"X sensor debounce time: {self.motor_controller.get_sensor_debounce_time('X'):.1f}ms")
        logger.info(f"Reading count required: {self.motor_controller._sensor_reading_count}")
        logger.info("Monitoring X sensor (Ctrl+C to exit early)...")
        
        start_time = time.time()
        last_trigger_time = 0
        
        try:
            while time.time() - start_time < self.test_duration:
                # Check sensor with enhanced debouncing
                is_triggered = self.motor_controller._check_sensor('X')
                
                if is_triggered:
                    current_time = time.time()
                    time_since_last = current_time - last_trigger_time
                    
                    if time_since_last > 0.1:  # Only count as new trigger if >100ms since last
                        self.trigger_count += 1
                        logger.info(f"Trigger #{self.trigger_count}: X sensor triggered at {current_time - start_time:.2f}s")
                        last_trigger_time = current_time
                    else:
                        self.false_trigger_count += 1
                        logger.warning(f"False trigger detected (debounced): {time_since_last*1000:.1f}ms since last trigger")
                
                time.sleep(0.01)  # 10ms polling interval
                
        except KeyboardInterrupt:
            logger.info("Test interrupted by user")
        
        # Print results
        elapsed_time = time.time() - start_time
        logger.info("=== Test Results ===")
        logger.info(f"Test duration: {elapsed_time:.1f} seconds")
        logger.info(f"Valid triggers: {self.trigger_count}")
        logger.info(f"False triggers (debounced): {self.false_trigger_count}")
        logger.info(f"Trigger rate: {self.trigger_count / elapsed_time:.2f} triggers/second")
        
        if self.false_trigger_count > 0:
            logger.info(f"Debounce effectiveness: {self.false_trigger_count} false triggers prevented")
    
    def test_debounce_settings(self):
        """Test different debounce settings."""
        logger.info("=== Testing Different Debounce Settings ===")
        
        # Test original 10ms debounce
        logger.info("Testing 10ms debounce time...")
        self.motor_controller.set_sensor_debounce_time(10, 'X')
        time.sleep(2)
        
        # Test 25ms debounce (current setting)
        logger.info("Testing 25ms debounce time...")
        self.motor_controller.set_sensor_debounce_time(25, 'X')
        time.sleep(2)
        
        # Test 50ms debounce
        logger.info("Testing 50ms debounce time...")
        self.motor_controller.set_sensor_debounce_time(50, 'X')
        time.sleep(2)
        
        # Reset to recommended setting
        self.motor_controller.set_sensor_debounce_time(25, 'X')
        logger.info("Reset to 25ms debounce time")
    
    def test_reading_count(self):
        """Test different reading count requirements."""
        logger.info("=== Testing Different Reading Counts ===")
        
        # Test with 2 readings
        logger.info("Testing with 2 readings required...")
        self.motor_controller.set_sensor_reading_count(2)
        time.sleep(2)
        
        # Test with 3 readings (current setting)
        logger.info("Testing with 3 readings required...")
        self.motor_controller.set_sensor_reading_count(3)
        time.sleep(2)
        
        # Test with 5 readings
        logger.info("Testing with 5 readings required...")
        self.motor_controller.set_sensor_reading_count(5)
        time.sleep(2)
        
        # Reset to recommended setting
        self.motor_controller.set_sensor_reading_count(3)
        logger.info("Reset to 3 readings required")
    
    def cleanup(self):
        """Clean up GPIO and motor controller."""
        try:
            self.motor_controller.cleanup()
            logger.info("Cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def main():
    """Main test function."""
    tester = EnhancedDebounceTester()
    
    try:
        # Test different settings
        tester.test_debounce_settings()
        tester.test_reading_count()
        
        # Run main debounce test
        tester.test_x_sensor_debounce()
        
    except Exception as e:
        logger.error(f"Test error: {e}")
    finally:
        tester.cleanup()

if __name__ == "__main__":
    main() 