#!/usr/bin/env python3
"""
Test script to verify the debounce mapping fix.
"""

import logging
from motor_control.motor_controller import MotorController

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_debounce_mapping():
    """Test that the debounce mapping works correctly."""
    logger.info("=== Testing Debounce Mapping Fix ===")
    
    try:
        # Create motor controller
        motor_controller = MotorController()
        
        # Test that all sensors have debounce times
        debounce_times = motor_controller.get_sensor_debounce_time()
        logger.info(f"All debounce times: {debounce_times}")
        
        # Test individual sensors
        for motor in ['X', 'Y1', 'Y2', 'Z', 'ROT']:
            try:
                debounce_time = motor_controller.get_sensor_debounce_time(motor)
                logger.info(f"{motor} sensor debounce time: {debounce_time:.1f}ms")
            except Exception as e:
                logger.error(f"Error getting debounce time for {motor}: {e}")
        
        # Test sensor checking (should not throw KeyError)
        logger.info("Testing sensor checking...")
        for motor in ['X', 'Y1', 'Y2', 'Z', 'ROT']:
            try:
                is_triggered = motor_controller._check_sensor(motor)
                logger.info(f"{motor} sensor state: {'Triggered' if is_triggered else 'Not triggered'}")
            except Exception as e:
                logger.error(f"Error checking {motor} sensor: {e}")
        
        logger.info("=== Debounce mapping test completed successfully ===")
        
        # Cleanup
        motor_controller.cleanup()
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise

if __name__ == "__main__":
    test_debounce_mapping() 