#!/usr/bin/env python3
"""
Test script for sensor debouncing.
This script monitors the X sensor and shows when it triggers with debouncing.
"""

import time
import RPi.GPIO as GPIO
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Disable GPIO warnings
GPIO.setwarnings(False)

class SensorDebounceTester:
    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        
        # X sensor pin
        self.x_sensor_pin = 16  # GPIO 16
        
        # Setup sensor
        GPIO.setup(self.x_sensor_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        # Debouncing variables
        self.debounce_time = 0.01  # 10ms
        self.last_trigger_time = 0
        self.last_state = False
        
        logger.info("Sensor debounce tester initialized")
        logger.info(f"Monitoring X sensor on GPIO {self.x_sensor_pin}")
        logger.info(f"Debounce time: {self.debounce_time * 1000:.1f}ms")
        
    def check_sensor_debounced(self):
        """Check sensor with debouncing."""
        current_time = time.time()
        
        # Read current sensor state
        current_state = GPIO.input(self.x_sensor_pin) == GPIO.LOW
        
        # If sensor is triggered (LOW)
        if current_state:
            # Check if this is a new trigger (not within debounce time)
            if current_time - self.last_trigger_time > self.debounce_time:
                # This is a valid trigger
                self.last_trigger_time = current_time
                self.last_state = True
                return True
            else:
                # Still within debounce time, return last known state
                return self.last_state
        else:
            # Sensor is not triggered (HIGH)
            # Reset the trigger time when sensor is not triggered
            if self.last_state:
                self.last_trigger_time = 0
            self.last_state = False
            return False
    
    def check_sensor_raw(self):
        """Check sensor without debouncing (for comparison)."""
        return GPIO.input(self.x_sensor_pin) == GPIO.LOW
    
    def run_test(self, duration=30):
        """Run the debounce test for the specified duration."""
        logger.info(f"Starting debounce test for {duration} seconds...")
        logger.info("Press Ctrl+C to stop early")
        
        start_time = time.time()
        trigger_count = 0
        raw_trigger_count = 0
        
        try:
            while time.time() - start_time < duration:
                # Check both debounced and raw sensor states
                debounced_state = self.check_sensor_debounced()
                raw_state = self.check_sensor_raw()
                
                # Count triggers
                if debounced_state:
                    trigger_count += 1
                    logger.info(f"DEBOUNCED TRIGGER #{trigger_count} - Raw: {raw_state}")
                
                if raw_state:
                    raw_trigger_count += 1
                
                # Show status every 5 seconds
                elapsed = time.time() - start_time
                if int(elapsed) % 5 == 0 and elapsed > 0:
                    logger.info(f"Status: Debounced triggers: {trigger_count}, Raw triggers: {raw_trigger_count}")
                
                time.sleep(0.001)  # 1ms polling
                
        except KeyboardInterrupt:
            logger.info("Test stopped by user")
        
        # Final results
        logger.info("=== FINAL RESULTS ===")
        logger.info(f"Test duration: {time.time() - start_time:.1f} seconds")
        logger.info(f"Debounced triggers: {trigger_count}")
        logger.info(f"Raw triggers: {raw_trigger_count}")
        logger.info(f"Debouncing prevented {raw_trigger_count - trigger_count} false triggers")
        
        if raw_trigger_count > 0:
            reduction_percent = ((raw_trigger_count - trigger_count) / raw_trigger_count) * 100
            logger.info(f"Trigger reduction: {reduction_percent:.1f}%")
    
    def set_debounce_time(self, debounce_time_ms):
        """Set the debounce time in milliseconds."""
        self.debounce_time = debounce_time_ms / 1000.0
        logger.info(f"Debounce time set to {debounce_time_ms}ms")
    
    def cleanup(self):
        """Clean up GPIO."""
        GPIO.cleanup()
        logger.info("GPIO cleanup completed")

def main():
    tester = SensorDebounceTester()
    
    try:
        # Test with different debounce times
        debounce_times = [5, 10, 20, 50]  # milliseconds
        
        for debounce_time in debounce_times:
            logger.info(f"\n=== Testing with {debounce_time}ms debounce ===")
            tester.set_debounce_time(debounce_time)
            tester.run_test(duration=10)  # 10 seconds per test
            time.sleep(2)  # Pause between tests
            
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    finally:
        tester.cleanup()

if __name__ == "__main__":
    main() 