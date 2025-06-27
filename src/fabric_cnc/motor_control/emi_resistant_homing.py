#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EMI-resistant homing system for Fabric CNC.
Implements debouncing, filtering, and interference detection for hall effect sensors.
"""

import time
import logging
import RPi.GPIO as GPIO
from collections import deque
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class EMIResistantHoming:
    """EMI-resistant homing system for hall effect sensors."""
    
    def __init__(self, 
                 debounce_ms: int = 100,
                 filter_samples: int = 7,
                 interference_threshold: int = 3,
                 verify_distance_mm: float = 5.0):
        """Initialize EMI-resistant homing system.
        
        Args:
            debounce_ms: Debounce time in milliseconds
            filter_samples: Number of samples for filtering (odd number recommended)
            interference_threshold: Number of rapid triggers to indicate interference
            verify_distance_mm: Distance to move for homing verification
        """
        self.debounce_ms = debounce_ms
        self.filter_samples = filter_samples
        self.interference_threshold = interference_threshold
        self.verify_distance_mm = verify_distance_mm
        
        # Sensor state tracking
        self.sensor_history = {}
        self.last_trigger_time = {}
        self.trigger_count = {}
        self.last_trigger_count_reset = {}
        
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        
        # Define sensor pins (from config)
        self.sensor_pins = {
            'X': 20,   # GPIO20 (Pin 38)
            'Y1': 21,  # GPIO21 (Pin 40)
            'Y2': 16   # GPIO16 (Pin 36)
        }
        
        # Initialize sensor tracking
        for name in self.sensor_pins.keys():
            self.sensor_history[name] = deque(maxlen=filter_samples)
            self.last_trigger_time[name] = 0
            self.trigger_count[name] = 0
            self.last_trigger_count_reset[name] = time.time()
            
            # Setup GPIO
            GPIO.setup(self.sensor_pins[name], GPIO.IN, pull_up_down=GPIO.PUD_UP)
            logger.info(f"Setup EMI-resistant sensor {name} on pin {self.sensor_pins[name]}")
    
    def read_sensor_raw(self, sensor_name: str) -> bool:
        """Read raw sensor state without filtering."""
        pin = self.sensor_pins[sensor_name]
        return GPIO.input(pin) == GPIO.LOW  # True if magnet detected
    
    def read_sensor_filtered(self, sensor_name: str) -> bool:
        """Read sensor state with EMI filtering."""
        current_time = time.time() * 1000  # Convert to milliseconds
        
        # Check debounce
        if current_time - self.last_trigger_time[sensor_name] < self.debounce_ms:
            return False
        
        # Read current state
        current_state = self.read_sensor_raw(sensor_name)
        self.sensor_history[sensor_name].append(current_state)
        
        # Apply filter: require majority of recent samples to be True
        if len(self.sensor_history[sensor_name]) >= self.filter_samples:
            true_count = sum(self.sensor_history[sensor_name])
            filtered_state = true_count > (self.filter_samples // 2)
            
            # Update trigger time if filtered state is True
            if filtered_state:
                self.last_trigger_time[sensor_name] = current_time
                
                # Track rapid triggers for interference detection
                self.trigger_count[sensor_name] += 1
                
                # Reset counter if too much time has passed
                if current_time - self.last_trigger_count_reset[sensor_name] > 1000:  # 1 second
                    self.trigger_count[sensor_name] = 1
                    self.last_trigger_count_reset[sensor_name] = current_time
            
            return filtered_state
        
        return current_state
    
    def detect_interference(self, sensor_name: str) -> bool:
        """Detect if sensor is experiencing EMI interference."""
        current_time = time.time() * 1000
        
        # Check for rapid triggers
        if self.trigger_count[sensor_name] > self.interference_threshold:
            time_since_reset = current_time - self.last_trigger_count_reset[sensor_name]
            if time_since_reset < 1000:  # Within 1 second
                logger.warning(f"EMI interference detected on {sensor_name} sensor: "
                             f"{self.trigger_count[sensor_name]} triggers in {time_since_reset:.0f}ms")
                return True
        
        return False
    
    def wait_for_sensor(self, sensor_name: str, timeout_seconds: float = 30.0) -> bool:
        """Wait for sensor to be triggered with EMI resistance."""
        logger.info(f"Waiting for {sensor_name} sensor trigger (timeout: {timeout_seconds}s)")
        
        start_time = time.time()
        last_interference_warning = 0
        
        while time.time() - start_time < timeout_seconds:
            # Check for interference
            if self.detect_interference(sensor_name):
                current_time = time.time()
                if current_time - last_interference_warning > 5.0:  # Warn every 5 seconds
                    logger.warning(f"Continuing to monitor {sensor_name} despite EMI interference")
                    last_interference_warning = current_time
            
            # Check for valid trigger
            if self.read_sensor_filtered(sensor_name):
                logger.info(f"{sensor_name} sensor triggered successfully")
                return True
            
            time.sleep(0.001)  # 1ms delay
        
        logger.error(f"Timeout waiting for {sensor_name} sensor trigger")
        return False
    
    def verify_home_position(self, sensor_name: str, motor_controller) -> bool:
        """Verify home position by moving away and back."""
        logger.info(f"Verifying home position for {sensor_name}")
        
        # Move away from sensor
        if sensor_name == 'X':
            motor_controller.move_distance(self.verify_distance_mm, 'X')
        elif sensor_name in ['Y1', 'Y2']:
            motor_controller.move_distance(self.verify_distance_mm, 'Y')
        
        time.sleep(0.5)  # Brief pause
        
        # Move back to sensor
        if sensor_name == 'X':
            motor_controller.move_distance(-self.verify_distance_mm, 'X')
        elif sensor_name in ['Y1', 'Y2']:
            motor_controller.move_distance(-self.verify_distance_mm, 'Y')
        
        # Check if sensor triggers again
        return self.wait_for_sensor(sensor_name, timeout_seconds=10.0)
    
    def home_axis_with_emi_resistance(self, axis: str, motor_controller) -> bool:
        """Home an axis with EMI resistance."""
        logger.info(f"Starting EMI-resistant homing for {axis} axis")
        
        # Determine which sensors to monitor
        if axis == 'X':
            sensors = ['X']
        elif axis == 'Y':
            sensors = ['Y1', 'Y2']  # Monitor both Y sensors
        else:
            logger.error(f"Invalid axis: {axis}")
            return False
        
        # Reset interference counters
        for sensor in sensors:
            self.trigger_count[sensor] = 0
            self.last_trigger_count_reset[sensor] = time.time() * 1000
        
        # Start homing movement
        try:
            # Move in home direction until sensor triggers
            if axis == 'X':
                # Move X axis in home direction
                while not self.wait_for_sensor('X', timeout_seconds=1.0):
                    motor_controller.move_distance(-1.0, 'X')  # Small step
            elif axis == 'Y':
                # Move Y axis in home direction
                while not (self.wait_for_sensor('Y1', timeout_seconds=0.1) or 
                          self.wait_for_sensor('Y2', timeout_seconds=0.1)):
                    motor_controller.move_distance(-1.0, 'Y')  # Small step
            
            logger.info(f"{axis} axis homing completed")
            
            # Verify home position
            if self.verify_home_position(sensors[0], motor_controller):
                logger.info(f"{axis} axis home position verified")
                return True
            else:
                logger.warning(f"{axis} axis home position verification failed")
                return False
                
        except Exception as e:
            logger.error(f"Error during {axis} axis homing: {e}")
            return False
    
    def get_sensor_status(self) -> Dict[str, Dict]:
        """Get detailed status of all sensors."""
        status = {}
        for name in self.sensor_pins.keys():
            raw_state = self.read_sensor_raw(name)
            filtered_state = self.read_sensor_filtered(name)
            interference = self.detect_interference(name)
            
            status[name] = {
                'raw_state': raw_state,
                'filtered_state': filtered_state,
                'interference_detected': interference,
                'trigger_count': self.trigger_count[name],
                'history_samples': len(self.sensor_history[name])
            }
        
        return status
    
    def cleanup(self):
        """Clean up GPIO resources."""
        GPIO.cleanup()
        logger.info("EMI-resistant homing system cleaned up")

def main():
    """Test the EMI-resistant homing system."""
    try:
        homing = EMIResistantHoming()
        
        print("EMI-Resistant Hall Sensor Test")
        print("==============================")
        print("Press Ctrl+C to exit")
        print("\nSensor Status:")
        print("---------------")
        
        while True:
            status = homing.get_sensor_status()
            
            # Clear previous lines
            print("\033[F" * 8)
            print("\nSensor Status:")
            print("---------------")
            
            for name, info in status.items():
                raw = "DETECTED" if info['raw_state'] else "CLEAR"
                filtered = "DETECTED" if info['filtered_state'] else "CLEAR"
                interference = "⚠️ EMI" if info['interference_detected'] else "OK"
                
                print(f"{name}: {filtered}/{raw} {interference} (triggers: {info['trigger_count']})")
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nTest stopped by user")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        homing.cleanup()

if __name__ == "__main__":
    main() 