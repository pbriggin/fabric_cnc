#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Program to draw circles using stepper motors.
Calculates steps for a circular path and controls motors accordingly.
"""

import math
import time
import logging
import RPi.GPIO as GPIO
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Disable GPIO warnings
GPIO.setwarnings(False)

# Motor configuration
PULSES_PER_REV = 3200
STEP_DELAY = 0.00025  # 0.25ms between pulses = 2000 steps/sec
MM_PER_REV = 2  # 2mm per revolution (adjust based on your setup)

class CircleDrawer:
    """Draws circles using stepper motors."""
    
    def __init__(self):
        """Initialize the circle drawer."""
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        
        # Initialize motors
        self.motors = {
            'X': {'STEP': 5, 'DIR': 6, 'EN': 13},
            'Y1': {'STEP': 10, 'DIR': 9, 'EN': 11},
            'Y2': {'STEP': 17, 'DIR': 27, 'EN': 22}
        }
        
        # Setup motor pins
        self._setup_motors()
        
        # Initialize state
        self.stop_event = threading.Event()
        self.current_position = {'X': 0, 'Y': 0}  # Current position in steps
        
        logger.info("Circle drawer initialized")

    def _setup_motors(self):
        """Setup GPIO pins for all motors."""
        for motor, pins in self.motors.items():
            GPIO.setup(pins['STEP'], GPIO.OUT)
            GPIO.setup(pins['DIR'], GPIO.OUT)
            GPIO.setup(pins['EN'], GPIO.OUT)
            GPIO.output(pins['EN'], GPIO.LOW)  # Enable motors
            GPIO.output(pins['STEP'], GPIO.LOW)
            GPIO.output(pins['DIR'], GPIO.LOW)
            logger.info(f"Setup {motor} motor pins")

    def _step_motor(self, motor, direction):
        """Step a single motor in the specified direction."""
        pins = self.motors[motor]
        
        # Set direction (reverse for Y1 and X)
        if motor in ['Y1', 'X']:
            direction = not direction
        GPIO.output(pins['DIR'], GPIO.HIGH if direction else GPIO.LOW)
        
        # Step pulse
        GPIO.output(pins['STEP'], GPIO.HIGH)
        time.sleep(STEP_DELAY/2)
        GPIO.output(pins['STEP'], GPIO.LOW)
        time.sleep(STEP_DELAY/2)
        
        # Update position
        if motor == 'X':
            self.current_position['X'] += 1 if direction else -1
        elif motor in ['Y1', 'Y2']:
            # Y motors move in opposite directions
            if motor == 'Y1':
                self.current_position['Y'] += 1 if not direction else -1
            else:  # Y2
                self.current_position['Y'] += 1 if direction else -1

    def _step_y_axis(self, direction):
        """Step both Y motors together to maintain sync."""
        # Set directions (Y1 is reversed)
        GPIO.output(self.motors['Y1']['DIR'], GPIO.LOW if direction else GPIO.HIGH)
        GPIO.output(self.motors['Y2']['DIR'], GPIO.HIGH if direction else GPIO.LOW)
        
        # Step both motors together
        GPIO.output(self.motors['Y1']['STEP'], GPIO.HIGH)
        GPIO.output(self.motors['Y2']['STEP'], GPIO.HIGH)
        time.sleep(STEP_DELAY/2)
        GPIO.output(self.motors['Y1']['STEP'], GPIO.LOW)
        GPIO.output(self.motors['Y2']['STEP'], GPIO.LOW)
        time.sleep(STEP_DELAY/2)
        
        # Update position
        self.current_position['Y'] += 1 if direction else -1

    def _move_to_position(self, target_x, target_y):
        """Move to target position in steps."""
        while not self.stop_event.is_set():
            # Calculate remaining steps
            dx = target_x - self.current_position['X']
            dy = target_y - self.current_position['Y']
            
            # If we're close enough, stop
            if abs(dx) < 1 and abs(dy) < 1:
                break
            
            # Move X
            if abs(dx) > 0:
                self._step_motor('X', dx > 0)
            
            # Move Y (both motors together)
            if abs(dy) > 0:
                self._step_y_axis(dy > 0)
            
            time.sleep(STEP_DELAY)

    def draw_circle(self, center_x, center_y, radius, steps=360):
        """Draw a circle with given center, radius, and number of steps."""
        try:
            logger.info(f"Drawing circle: center=({center_x}, {center_y}), radius={radius}, steps={steps}")
            
            # Convert mm to steps
            center_x_steps = int(center_x * PULSES_PER_REV / MM_PER_REV)
            center_y_steps = int(center_y * PULSES_PER_REV / MM_PER_REV)
            radius_steps = int(radius * PULSES_PER_REV / MM_PER_REV)
            
            logger.info(f"Steps: center_x={center_x_steps}, center_y={center_y_steps}, radius={radius_steps}")
            
            # Calculate points on circle
            for i in range(steps + 1):
                if self.stop_event.is_set():
                    break
                
                # Calculate angle and position
                angle = 2 * math.pi * i / steps
                x = center_x_steps + radius_steps * math.cos(angle)
                y = center_y_steps + radius_steps * math.sin(angle)
                
                # Log every 45 degrees
                if i % 45 == 0:
                    logger.info(f"Step {i}: angle={angle:.2f}, x={x:.0f}, y={y:.0f}")
                
                # Move to position
                self._move_to_position(int(x), int(y))
                
                # Small delay between points
                time.sleep(0.01)
            
            logger.info("Circle drawing completed")
            
        except Exception as e:
            logger.error(f"Error drawing circle: {e}")
            raise
        finally:
            # Disable motors
            for motor, pins in self.motors.items():
                GPIO.output(pins['EN'], GPIO.HIGH)
                GPIO.output(pins['STEP'], GPIO.LOW)
                GPIO.output(pins['DIR'], GPIO.LOW)

    def stop(self):
        """Stop the current operation."""
        self.stop_event.set()
        # Disable motors
        for motor, pins in self.motors.items():
            GPIO.output(pins['EN'], GPIO.HIGH)
            GPIO.output(pins['STEP'], GPIO.LOW)
            GPIO.output(pins['DIR'], GPIO.LOW)

def main():
    """Main entry point."""
    try:
        drawer = CircleDrawer()
        
        # Draw a smaller circle first for testing
        drawer.draw_circle(50, 50, 25)  # Center at (50, 50)mm, radius 25mm
        
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