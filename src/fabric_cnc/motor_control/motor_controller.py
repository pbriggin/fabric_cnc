#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Motor controller for the CNC machine.
Handles stepper motor control with acceleration/deceleration.
"""

import math
import time
import logging
import RPi.GPIO as GPIO
import threading
from fabric_cnc.config import MOTOR_CONFIG

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Disable GPIO warnings
GPIO.setwarnings(False)

class MotorController:
    """Controls stepper motors with acceleration/deceleration."""
    
    def __init__(self):
        """Initialize the motor controller."""
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        
        # Initialize motors
        self.motors = MOTOR_CONFIG
        
        # Setup motor pins
        self._setup_motors()
        
        # Initialize state
        self.stop_event = threading.Event()
        self.current_position = {'X': 0, 'Y': 0}  # Current position in steps
        
        logger.info("Motor controller initialized")

    def _setup_motors(self):
        """Setup GPIO pins for all motors."""
        for motor, config in self.motors.items():
            GPIO.setup(config['STEP'], GPIO.OUT)
            GPIO.setup(config['DIR'], GPIO.OUT)
            GPIO.setup(config['EN'], GPIO.OUT)
            GPIO.output(config['EN'], GPIO.LOW)  # Enable motors
            GPIO.output(config['STEP'], GPIO.LOW)
            GPIO.output(config['DIR'], GPIO.LOW)
            logger.info(f"Setup {motor} motor pins")

    def _step_motor(self, motor, direction):
        """Step a single motor in the specified direction."""
        config = self.motors[motor]
        
        # Set direction (reverse for Y1 and X)
        if motor in ['Y1', 'X']:
            direction = not direction
        GPIO.output(config['DIR'], GPIO.HIGH if direction else GPIO.LOW)
        
        # Step pulse
        GPIO.output(config['STEP'], GPIO.HIGH)
        time.sleep(config['STEP_DELAY']/2)
        GPIO.output(config['STEP'], GPIO.LOW)
        time.sleep(config['STEP_DELAY']/2)
        
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
        GPIO.output(self.motors['Y1']['DIR'], GPIO.HIGH if direction else GPIO.LOW)  # Y1 is reversed
        GPIO.output(self.motors['Y2']['DIR'], GPIO.LOW if direction else GPIO.HIGH)  # Y2 is normal
        
        # Step both motors together
        GPIO.output(self.motors['Y1']['STEP'], GPIO.HIGH)
        GPIO.output(self.motors['Y2']['STEP'], GPIO.HIGH)
        time.sleep(self.motors['Y1']['STEP_DELAY']/2)
        GPIO.output(self.motors['Y1']['STEP'], GPIO.LOW)
        GPIO.output(self.motors['Y2']['STEP'], GPIO.LOW)
        time.sleep(self.motors['Y1']['STEP_DELAY']/2)
        
        # Update position
        self.current_position['Y'] += 1 if direction else -1

    def _move_to_position(self, target_x, target_y):
        """Move to target position in steps with acceleration/deceleration."""
        # Calculate total distance
        dx = target_x - self.current_position['X']
        dy = target_y - self.current_position['Y']
        total_steps = max(abs(dx), abs(dy))
        
        if total_steps == 0:
            return
            
        # Acceleration parameters
        accel_steps = min(total_steps // 4, 100)  # Accelerate for first 1/4 of movement
        decel_steps = min(total_steps // 4, 100)  # Decelerate for last 1/4 of movement
        cruise_steps = total_steps - accel_steps - decel_steps
        
        # Movement loop with acceleration/deceleration
        for i in range(total_steps):
            if self.stop_event.is_set():
                break
                
            # Calculate current delay based on position in movement
            if i < accel_steps:
                # Accelerate
                delay = self.motors['X']['STEP_DELAY'] * (1 + (accel_steps - i) / accel_steps)
            elif i >= total_steps - decel_steps:
                # Decelerate
                delay = self.motors['X']['STEP_DELAY'] * (1 + (i - (total_steps - decel_steps)) / decel_steps)
            else:
                # Cruise at constant speed
                delay = self.motors['X']['STEP_DELAY']
                
            # Move X
            if abs(dx) > 0:
                self._step_motor('X', dx > 0)
            
            # Move Y (both motors together)
            if abs(dy) > 0:
                self._step_y_axis(dy > 0)
            
            time.sleep(delay)

    def move_distance(self, motor, distance_mm):
        """Move the specified motor the given distance with acceleration/deceleration."""
        try:
            config = self.motors[motor]
            
            # Convert mm to steps
            revolutions = distance_mm / config['MM_PER_REV']
            total_steps = int(revolutions * config['PULSES_PER_REV'])
            
            logger.info(f"Movement calculations for {motor}:")
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
                if self.stop_event.is_set():
                    break
                    
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
                
                # Step motor
                self._step_motor(motor, distance_mm > 0)
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
            GPIO.output(config['EN'], GPIO.HIGH)
            GPIO.output(config['STEP'], GPIO.LOW)
            GPIO.output(config['DIR'], GPIO.LOW)

    def stop(self):
        """Stop all motors."""
        self.stop_event.set()
        # Disable motors
        for motor, config in self.motors.items():
            GPIO.output(config['EN'], GPIO.HIGH)
            GPIO.output(config['STEP'], GPIO.LOW)
            GPIO.output(config['DIR'], GPIO.LOW)

def main():
    """Main entry point."""
    try:
        controller = MotorController()
        
        # Test X motor movement
        controller.move_distance('X', 304.8)  # 12 inches
        
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