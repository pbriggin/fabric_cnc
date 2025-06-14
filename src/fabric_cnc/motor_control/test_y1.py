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
STEP = 17
DIR = 27
EN = 22  # Enable pin (active low)

# Motor configuration
PULSES_PER_REV = 3200
STEP_DELAY = 0.00025  # 0.5 ms between pulses = 2000 steps/sec

GPIO.setmode(GPIO.BCM)
GPIO.setup(STEP, GPIO.OUT)
GPIO.setup(DIR, GPIO.OUT)
GPIO.setup(EN, GPIO.OUT)

# Enable driver
GPIO.output(EN, GPIO.LOW)

# Set direction
GPIO.output(DIR, GPIO.HIGH)

try:
    print("Stepping one full revolution...")
    for _ in range(PULSES_PER_REV):
        GPIO.output(STEP, GPIO.HIGH)
        time.sleep(STEP_DELAY)
        GPIO.output(STEP, GPIO.LOW)
        time.sleep(STEP_DELAY)

    print("Done!")
    GPIO.output(EN, GPIO.HIGH)  # Optional: disable motor after move

except KeyboardInterrupt:
    GPIO.output(EN, GPIO.HIGH)
    print("Interrupted!")

finally:
    GPIO.cleanup() 