#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced test program to read hall effect sensors with EMI resistance.
Reads sensors on pins 16, 20, and 21 with debouncing and filtering.
"""

import time
import logging
import RPi.GPIO as GPIO
from fabric_cnc.config import MOTOR_CONFIG
from collections import deque

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Disable GPIO warnings
GPIO.setwarnings(False)

class EMIResistantHallSensorTest:
    """Test hall effect sensors with EMI resistance features."""
    
    def __init__(self, debounce_ms=50, filter_samples=5):
        """Initialize the hall sensor test.
        
        Args:
            debounce_ms: Debounce time in milliseconds
            filter_samples: Number of samples for filtering
        """
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        
        # Define sensor pins
        self.sensor_pins = {
            'Y2': 16,
            'X': 20,
            'Y1': 21
        }
        
        # EMI resistance parameters
        self.debounce_ms = debounce_ms
        self.filter_samples = filter_samples
        self.last_trigger_time = {name: 0 for name in self.sensor_pins.keys()}
        self.sensor_history = {name: deque(maxlen=filter_samples) for name in self.sensor_pins.keys()}
        
        # Setup sensor pins as inputs with pull-up resistors
        for name, pin in self.sensor_pins.items():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            logger.info(f"Setup {name} sensor on pin {pin}")
        
        logger.info(f"Enhanced hall sensor test initialized (debounce: {debounce_ms}ms, filter: {filter_samples} samples)")

    def read_sensor_raw(self, name):
        """Read raw sensor state without filtering."""
        pin = self.sensor_pins[name]
        return GPIO.input(pin) == GPIO.LOW  # True if magnet detected

    def read_sensor_filtered(self, name):
        """Read sensor state with filtering to reduce EMI noise."""
        current_time = time.time() * 1000  # Convert to milliseconds
        
        # Check debounce
        if current_time - self.last_trigger_time[name] < self.debounce_ms:
            return False
        
        # Read current state
        current_state = self.read_sensor_raw(name)
        self.sensor_history[name].append(current_state)
        
        # Apply filter: require majority of recent samples to be True
        if len(self.sensor_history[name]) >= self.filter_samples:
            true_count = sum(self.sensor_history[name])
            filtered_state = true_count > (self.filter_samples // 2)
            
            # Update trigger time if filtered state is True
            if filtered_state:
                self.last_trigger_time[name] = current_time
            
            return filtered_state
        
        return current_state

    def read_sensors(self, use_filtering=True):
        """Read all sensor states."""
        states = {}
        for name in self.sensor_pins.keys():
            if use_filtering:
                detected = self.read_sensor_filtered(name)
            else:
                detected = self.read_sensor_raw(name)
            states[name] = "DETECTED" if detected else "CLEAR"
        return states

    def test_motor_interference(self, motor_pins):
        """Test for motor interference by running motors and monitoring sensors."""
        print(f"\nTesting motor interference...")
        print(f"Motor pins: {motor_pins}")
        
        # Setup motor pins
        for pin_type, pin in motor_pins.items():
            if pin_type in ['STEP', 'DIR', 'EN']:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)
        
        # Enable motors
        if 'EN' in motor_pins:
            GPIO.output(motor_pins['EN'], GPIO.LOW)  # Enable
        
        try:
            print("Running motors for 5 seconds while monitoring sensors...")
            start_time = time.time()
            
            while time.time() - start_time < 5:
                # Generate some motor pulses
                for _ in range(10):
                    GPIO.output(motor_pins['STEP'], GPIO.HIGH)
                    time.sleep(0.001)
                    GPIO.output(motor_pins['STEP'], GPIO.LOW)
                    time.sleep(0.001)
                
                # Check sensors
                states = self.read_sensors(use_filtering=False)  # Raw reading for interference detection
                for name, state in states.items():
                    if state == "DETECTED":
                        print(f"⚠️  INTERFERENCE DETECTED: {name} sensor triggered during motor operation!")
                
                time.sleep(0.1)
                
        finally:
            # Disable motors
            if 'EN' in motor_pins:
                GPIO.output(motor_pins['EN'], GPIO.HIGH)  # Disable
            print("Motor interference test completed")

    def monitor_sensors(self, test_motor_interference=False):
        """Monitor sensors continuously with EMI resistance."""
        try:
            print("\nMonitoring hall effect sensors with EMI resistance...")
            print("Press Ctrl+C to exit")
            print("\nSensor States (Filtered/Raw):")
            print("-----------------------------")
            
            while True:
                filtered_states = self.read_sensors(use_filtering=True)
                raw_states = self.read_sensors(use_filtering=False)
                
                # Clear previous lines and print current states
                print("\033[F" * 6)  # Move cursor up 6 lines
                print("\nSensor States (Filtered/Raw):")
                print("-----------------------------")
                for name in self.sensor_pins.keys():
                    filtered = filtered_states[name]
                    raw = raw_states[name]
                    status = f"{name}: {filtered}/{raw}"
                    
                    # Highlight differences between filtered and raw
                    if filtered != raw:
                        status += " ⚠️"
                    
                    print(status)
                
                time.sleep(0.1)  # Small delay to prevent CPU hogging
                
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        finally:
            # Cleanup
            GPIO.cleanup()
            logger.info("Program finished")

def main():
    """Main entry point."""
    try:
        # Create test instance with EMI resistance
        test = EMIResistantHallSensorTest(debounce_ms=50, filter_samples=5)
        
        # Test motor interference if requested
        if len(sys.argv) > 1 and sys.argv[1] == "--test-motor-interference":
            # Test with X motor pins
            motor_pins = {
                'STEP': MOTOR_CONFIG['X']['STEP'],
                'DIR': MOTOR_CONFIG['X']['DIR'],
                'EN': MOTOR_CONFIG['X']['EN']
            }
            test.test_motor_interference(motor_pins)
        else:
            test.monitor_sensors()
        
    except Exception as e:
        logger.error(f"Error: {e}")
        GPIO.cleanup()

if __name__ == "__main__":
    import sys
    main() 