#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test program to move X motor 12 inches with smooth acceleration.
"""

import math
import time
import logging
import RPi.GPIO as GPIO

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Disable GPIO warnings
GPIO.setwarnings(False)

# Motor configuration
PULSES_PER_REV = 800  # DIP switches set for 800 steps per revolution
STEP_DELAY = 0.0005  # 0.5ms between pulses = 1000 steps/sec
MM_PER_REV = 2  # 2mm per revolution (adjust based on your setup)

class XMotorTest:
    """Test X motor movement."""
    
    def __init__(self):
        """Initialize the X motor test."""
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        
        # Initialize X motor
        self.motor = {'STEP': 5, 'DIR': 6, 'EN': 13}
        
        # Setup motor pins
        self._setup_motor()
        
        logger.info("X motor test initialized")

    def _setup_motor(self):
        """Setup GPIO pins for X motor."""
        GPIO.setup(self.motor['STEP'], GPIO.OUT)
        GPIO.setup(self.motor['DIR'], GPIO.OUT)
        GPIO.setup(self.motor['EN'], GPIO.OUT)
        GPIO.output(self.motor['EN'], GPIO.LOW)  # Enable motor
        GPIO.output(self.motor['STEP'], GPIO.LOW)
        GPIO.output(self.motor['DIR'], GPIO.LOW)
        logger.info("Setup X motor pins")

    def _step_motor(self, direction):
        """Step the motor in the specified direction."""
        # Set direction (X is reversed)
        GPIO.output(self.motor['DIR'], GPIO.HIGH if not direction else GPIO.LOW)
        
        # Step pulse
        GPIO.output(self.motor['STEP'], GPIO.HIGH)
        time.sleep(STEP_DELAY/2)
        GPIO.output(self.motor['STEP'], GPIO.LOW)
        time.sleep(STEP_DELAY/2)

    def move_distance(self, distance_mm):
        """Move the specified distance with acceleration/deceleration."""
        try:
            # Convert mm to steps
            total_steps = int(distance_mm * PULSES_PER_REV / MM_PER_REV)
            logger.info(f"Moving {distance_mm}mm ({total_steps} steps)")
            
            # Acceleration parameters
            accel_steps = min(total_steps // 4, 100)  # Accelerate for first 1/4 of movement
            decel_steps = min(total_steps // 4, 100)  # Decelerate for last 1/4 of movement
            cruise_steps = total_steps - accel_steps - decel_steps
            
            # Movement loop with acceleration/deceleration
            for i in range(total_steps):
                # Calculate current delay based on position in movement
                if i < accel_steps:
                    # Accelerate
                    delay = STEP_DELAY * (1 + (accel_steps - i) / accel_steps)
                elif i >= total_steps - decel_steps:
                    # Decelerate
                    delay = STEP_DELAY * (1 + (i - (total_steps - decel_steps)) / decel_steps)
                else:
                    # Cruise at constant speed
                    delay = STEP_DELAY
                
                # Step motor
                self._step_motor(True)  # True for positive direction
                time.sleep(delay)
                
                # Log progress every 1000 steps
                if i % 1000 == 0:
                    logger.info(f"Step {i}/{total_steps}")
            
            logger.info("Movement completed")
            
        except Exception as e:
            logger.error(f"Error during movement: {e}")
            raise
        finally:
            # Disable motor
            GPIO.output(self.motor['EN'], GPIO.HIGH)
            GPIO.output(self.motor['STEP'], GPIO.LOW)
            GPIO.output(self.motor['DIR'], GPIO.LOW)

def main():
    """Main entry point."""
    try:
        test = XMotorTest()
        
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