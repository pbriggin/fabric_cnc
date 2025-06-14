#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple test script for Y1 motor.
"""

import logging
import time
import RPi.GPIO as GPIO

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Motor pins
DIR_PIN = 21
STEP_PIN = 19
EN_PIN = 23

# Motor configuration
PULSES_PER_REV = 3200
STEP_DELAY = 0.00025  # 0.25ms between pulses = 2000 steps/sec

def setup_gpio():
    """Set up GPIO pins for Y1 motor."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(DIR_PIN, GPIO.OUT)
    GPIO.setup(STEP_PIN, GPIO.OUT)
    GPIO.setup(EN_PIN, GPIO.OUT)
    
    # Initialize pins to safe state
    GPIO.output(DIR_PIN, GPIO.LOW)
    GPIO.output(STEP_PIN, GPIO.LOW)
    GPIO.output(EN_PIN, GPIO.LOW)  # Enable motor
    
    logger.info("GPIO pins set up successfully")

def step_motor(direction, steps=PULSES_PER_REV):
    """Step the motor in the specified direction."""
    try:
        # Set direction
        logger.debug(f"Setting direction pin {DIR_PIN} to {'HIGH' if direction else 'LOW'}")
        GPIO.output(DIR_PIN, GPIO.HIGH if direction else GPIO.LOW)
        
        logger.info(f"Stepping {'forward' if direction else 'reverse'} for {steps} steps...")
        for i in range(steps):
            # Step pulse
            GPIO.output(STEP_PIN, GPIO.HIGH)
            time.sleep(STEP_DELAY)
            GPIO.output(STEP_PIN, GPIO.LOW)
            time.sleep(STEP_DELAY)
            
        logger.info("Step sequence complete")
            
    except Exception as e:
        logger.error(f"Error stepping motor: {e}")
        raise

def cleanup():
    """Clean up GPIO resources."""
    GPIO.output(EN_PIN, GPIO.HIGH)  # Disable motor
    GPIO.cleanup([DIR_PIN, STEP_PIN, EN_PIN])
    logger.info("GPIO cleanup complete")

def main():
    """Main test function."""
    try:
        setup_gpio()
        
        # Test forward movement (one full revolution)
        logger.info("Testing forward movement (one full revolution)")
        step_motor(True)
        time.sleep(1)  # Wait 1 second between directions
        
        # Test reverse movement (one full revolution)
        logger.info("Testing reverse movement (one full revolution)")
        step_motor(False)
        
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        cleanup()

if __name__ == "__main__":
    main() 