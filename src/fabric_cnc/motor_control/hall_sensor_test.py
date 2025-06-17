#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test program to read hall effect sensors.
Reads sensors on pins 16, 20, and 21.
"""

import time
import logging
import RPi.GPIO as GPIO
from fabric_cnc.config import MOTOR_CONFIG

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Disable GPIO warnings
GPIO.setwarnings(False)

class HallSensorTest:
    """Test hall effect sensors."""
    
    def __init__(self):
        """Initialize the hall sensor test."""
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        
        # Define sensor pins
        self.sensor_pins = {
            'X': 16,
            'Y1': 20,
            'Y2': 21
        }
        
        # Setup sensor pins as inputs with pull-up resistors
        for name, pin in self.sensor_pins.items():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            logger.info(f"Setup {name} sensor on pin {pin}")
        
        logger.info("Hall sensor test initialized")

    def read_sensors(self):
        """Read all sensor states."""
        states = {}
        for name, pin in self.sensor_pins.items():
            # Read sensor state (LOW when magnet is detected)
            state = GPIO.input(pin)
            states[name] = "DETECTED" if state == GPIO.LOW else "CLEAR"
        return states

    def monitor_sensors(self):
        """Monitor sensors continuously."""
        try:
            print("\nMonitoring hall effect sensors...")
            print("Press Ctrl+C to exit")
            print("\nSensor States:")
            print("-------------")
            
            while True:
                states = self.read_sensors()
                # Clear previous lines and print current states
                print("\033[F" * 4)  # Move cursor up 4 lines
                print("\nSensor States:")
                print("-------------")
                for name, state in states.items():
                    print(f"{name}: {state}")
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
        test = HallSensorTest()
        test.monitor_sensors()
        
    except Exception as e:
        logger.error(f"Error: {e}")
        GPIO.cleanup()

if __name__ == "__main__":
    main() 