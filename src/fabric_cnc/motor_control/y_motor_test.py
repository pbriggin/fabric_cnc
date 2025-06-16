#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test program to move Y motors 12 inches with smooth acceleration.
Moves both Y motors together to maintain sync.
"""

import math
import time
import logging
import RPi.GPIO as GPIO
from fabric_cnc.config import MOTOR_CONFIG

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Disable GPIO warnings
GPIO.setwarnings(False)

class YMotorTest:
    """Test Y motor movement."""
    
    def __init__(self):
        """Initialize the Y motor test."""
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        
        # Initialize Y motors
        self.motors = {
            'Y1': MOTOR_CONFIG['Y1'],
            'Y2': MOTOR_CONFIG['Y2']
        }
        
        # Setup motor pins
        self._setup_motors()
        
        logger.info("Y motor test initialized")

    def _setup_motors(self):
        """Setup GPIO pins for Y motors."""
        for motor, config in self.motors.items():
            GPIO.setup(config['STEP'], GPIO.OUT)
            GPIO.setup(config['DIR'], GPIO.OUT)
            GPIO.setup(config['EN'], GPIO.OUT)
            GPIO.output(config['EN'], GPIO.LOW)  # Enable motors
            GPIO.output(config['STEP'], GPIO.LOW)
            GPIO.output(config['DIR'], GPIO.LOW)
            logger.info(f"Setup {motor} motor pins")

    def _step_y_axis(self, direction):
        """Step both Y motors together to maintain sync."""
        # Set directions (Y1 is reversed)
        GPIO.output(self.motors['Y1']['DIR'], GPIO.HIGH if direction else GPIO.LOW)  # Y1 is reversed
        GPIO.output(self.motors['Y2']['DIR'], GPIO.LOW if direction else GPIO.HIGH)  # Y2 is normal
        
        # Step both motors together
        GPIO.output(self.motors['Y1']['STEP'], GPIO.HIGH)
        GPIO.output(self.motors['Y2']['STEP'], GPIO.HIGH)
        time.sleep(self.motors['Y1']['STEP_DELAY']/2)
        GPIO.output(self.motors['Y1']['STEP'], GPIO.LOW)
        GPIO.output(self.motors['Y2']['STEP'], GPIO.LOW)
        time.sleep(self.motors['Y1']['STEP_DELAY']/2)

    def move_distance(self, distance_mm):
        """Move the specified distance with acceleration/deceleration."""
        try:
            # Use Y1 config for calculations (both motors have same settings)
            config = self.motors['Y1']
            
            # Convert mm to steps
            revolutions = distance_mm / config['MM_PER_REV']
            total_steps = int(revolutions * config['PULSES_PER_REV'])
            
            logger.info(f"Movement calculations:")
            logger.info(f"  Distance: {distance_mm}mm")
            logger.info(f"  Revolutions needed: {revolutions:.2f}")
            logger.info(f"  Steps per revolution: {config['PULSES_PER_REV']}")
            logger.info(f"  Total steps: {total_steps}")
            
            # Acceleration parameters
            accel_steps = min(total_steps // 4, 100)  # Accelerate for first 1/4 of movement
            decel_steps = min(total_steps // 4, 100)  # Decelerate for last 1/4 of movement
            cruise_steps = total_steps - accel_steps - decel_steps
            
            logger.info(f"Movement profile:")
            logger.info(f"  Acceleration steps: {accel_steps}")
            logger.info(f"  Cruise steps: {cruise_steps}")
            logger.info(f"  Deceleration steps: {decel_steps}")
            
            # Movement loop with acceleration/deceleration
            for i in range(total_steps):
                # Calculate current delay based on position in movement
                if i < accel_steps:
                    # Accelerate
                    delay = config['STEP_DELAY'] * (1 + (accel_steps - i) / accel_steps)
                elif i >= total_steps - decel_steps:
                    # Decelerate
                    delay = config['STEP_DELAY'] * (1 + (i - (total_steps - decel_steps)) / decel_steps)
                else:
                    # Cruise at constant speed
                    delay = config['STEP_DELAY']
                
                # Step both motors together
                self._step_y_axis(distance_mm > 0)
                time.sleep(delay)
                
                # Log progress every 1000 steps
                if i % 1000 == 0:
                    logger.info(f"Step {i}/{total_steps}")
            
            logger.info("Movement completed")
            
        except Exception as e:
            logger.error(f"Error during movement: {e}")
            raise
        finally:
            # Disable motors
            for motor, config in self.motors.items():
                GPIO.output(config['EN'], GPIO.HIGH)
                GPIO.output(config['STEP'], GPIO.LOW)
                GPIO.output(config['DIR'], GPIO.LOW)

def main():
    """Main entry point."""
    try:
        test = YMotorTest()
        
        # Move 12 inches (304.8mm)
        test.move_distance(304.8)
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        # Cleanup
        GPIO.cleanup()
        logger.info("Program finished")

if __name__ == "__main__":
    main() 