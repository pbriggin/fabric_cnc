#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple test program for X motor to diagnose jitter issues.
"""

import RPi.GPIO as GPIO
import time
import signal
import sys

# Motor pins
X_STEP = 5
X_DIR = 6
X_EN = 13

# Timing
STEP_DELAY = 0.00025  # 0.25ms between pulses = 2000 steps/sec

def setup():
    """Setup GPIO pins."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(X_STEP, GPIO.OUT)
    GPIO.setup(X_DIR, GPIO.OUT)
    GPIO.setup(X_EN, GPIO.OUT)
    
    # Initialize pins
    GPIO.output(X_STEP, GPIO.LOW)
    GPIO.output(X_DIR, GPIO.LOW)
    GPIO.output(X_EN, GPIO.LOW)  # Enable motor

def cleanup():
    """Cleanup GPIO pins."""
    GPIO.output(X_STEP, GPIO.LOW)
    GPIO.output(X_DIR, GPIO.LOW)
    GPIO.output(X_EN, GPIO.HIGH)  # Disable motor
    GPIO.cleanup()

def step_motor(direction, steps):
    """Step the motor a specified number of times."""
    GPIO.output(X_DIR, GPIO.HIGH if direction else GPIO.LOW)
    
    for _ in range(steps):
        # Step pulse
        GPIO.output(X_STEP, GPIO.HIGH)
        time.sleep(STEP_DELAY/2)
        GPIO.output(X_STEP, GPIO.LOW)
        time.sleep(STEP_DELAY/2)

def signal_handler(sig, frame):
    """Handle Ctrl+C."""
    print("\nStopping motor...")
    cleanup()
    sys.exit(0)

def main():
    """Main test program."""
    # Setup signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Setup GPIO
    setup()
    
    print("X Motor Test Program")
    print("Press Ctrl+C to stop")
    print("\nMoving motor forward...")
    
    try:
        while True:
            # Move forward
            step_motor(True, 10000)  # 10000 steps forward
            print("Moving backward...")
            time.sleep(0.5)  # Pause between directions
            
            # Move backward
            step_motor(False, 10000)  # 10000 steps backward
            print("Moving forward...")
            time.sleep(0.5)  # Pause between directions
            
    except KeyboardInterrupt:
        print("\nStopping motor...")
    finally:
        cleanup()

if __name__ == "__main__":
    main() 