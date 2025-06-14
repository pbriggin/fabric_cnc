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

def step_motor(direction, steps=1):
    """Step the motor once in the specified direction."""
    try:
        # Set direction
        logger.debug(f"Setting direction pin {DIR_PIN} to {'HIGH' if direction else 'LOW'}")
        GPIO.output(DIR_PIN, GPIO.HIGH if direction else GPIO.LOW)
        
        for i in range(steps):
            # Step pulse
            logger.debug(f"Step {i+1}/{steps}: Setting step pin {STEP_PIN} to HIGH")
            GPIO.output(STEP_PIN, GPIO.HIGH)
            time.sleep(0.002)  # 2ms pulse
            logger.debug(f"Step {i+1}/{steps}: Setting step pin {STEP_PIN} to LOW")
            GPIO.output(STEP_PIN, GPIO.LOW)
            time.sleep(0.002)  # 2ms delay
            
    except Exception as e:
        logger.error(f"Error stepping motor: {e}")
        raise

def cleanup():
    """Clean up GPIO resources."""
    GPIO.cleanup([DIR_PIN, STEP_PIN, EN_PIN])
    logger.info("GPIO cleanup complete")

def main():
    """Main test function."""
    try:
        setup_gpio()
        
        # Test forward movement
        logger.info("Testing forward movement (100 steps)")
        step_motor(True, 100)
        time.sleep(2)  # Wait 2 seconds between directions
        
        # Test reverse movement
        logger.info("Testing reverse movement (100 steps)")
        step_motor(False, 100)
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        cleanup()

if __name__ == "__main__":
    main() 