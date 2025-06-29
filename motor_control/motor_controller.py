#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Motor controller for Fabric CNC machine.
Handles movement and homing of X and Y motors.
"""

import math
import time
import logging
import RPi.GPIO as GPIO
from config import MOTOR_CONFIG, MACHINE_CONFIG

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Disable GPIO warnings
GPIO.setwarnings(False)

class MotorController:
    """Controls the X and Y motors of the Fabric CNC machine."""
    
    def __init__(self):
        """Initialize the motor controller."""
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        
        # Initialize motors
        self.motors = {
            'X': MOTOR_CONFIG['X'],
            'Y1': MOTOR_CONFIG['Y1'],
            'Y2': MOTOR_CONFIG['Y2']
        }
        
        # Setup motor pins
        self._setup_motors()
        
        # Setup hall effect sensors
        self._setup_sensors()
        
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

    def _setup_sensors(self):
        """Setup hall effect sensors as inputs with pull-up resistors."""
        for motor, config in self.motors.items():
            GPIO.setup(config['HALL'], GPIO.IN, pull_up_down=GPIO.PUD_UP)
            logger.info(f"Setup {motor} hall effect sensor")

    def _check_sensor(self, motor):
        """Check if hall effect sensor is triggered."""
        return GPIO.input(self.motors[motor]['HALL']) == GPIO.LOW

    def _step_motor(self, motor, direction, delay):
        """Step a single motor."""
        config = self.motors[motor]
        GPIO.output(config['DIR'], GPIO.HIGH if direction else GPIO.LOW)
        GPIO.output(config['STEP'], GPIO.HIGH)
        time.sleep(delay/2)
        GPIO.output(config['STEP'], GPIO.LOW)
        time.sleep(delay/2)

    def _step_y_axis(self, direction, delay):
        """Step both Y motors together to maintain sync."""
        # Set directions (Y1 is reversed)
        GPIO.output(self.motors['Y1']['DIR'], GPIO.HIGH if direction else GPIO.LOW)  # Y1 is reversed
        GPIO.output(self.motors['Y2']['DIR'], GPIO.LOW if direction else GPIO.HIGH)  # Y2 is normal
        
        # Step both motors together
        GPIO.output(self.motors['Y1']['STEP'], GPIO.HIGH)
        GPIO.output(self.motors['Y2']['STEP'], GPIO.HIGH)
        time.sleep(delay/2)
        GPIO.output(self.motors['Y1']['STEP'], GPIO.LOW)
        GPIO.output(self.motors['Y2']['STEP'], GPIO.LOW)
        time.sleep(delay/2)

    def move_distance(self, distance_mm, axis='X'):
        """Move the specified distance with acceleration/deceleration."""
        try:
            if axis == 'X':
                self._move_x(distance_mm)
            elif axis == 'Y':
                self._move_y(distance_mm)
            else:
                raise ValueError(f"Invalid axis: {axis}")
            
        except Exception as e:
            logger.error(f"Error during movement: {e}")
            raise
        finally:
            # Disable motors
            for motor, config in self.motors.items():
                GPIO.output(config['EN'], GPIO.HIGH)
                GPIO.output(config['STEP'], GPIO.LOW)
                GPIO.output(config['DIR'], GPIO.LOW)

    def _move_x(self, distance_mm):
        """Move X axis the specified distance."""
        config = self.motors['X']
        
        # Convert mm to steps
        revolutions = distance_mm / config['MM_PER_REV']
        total_steps = int(revolutions * config['PULSES_PER_REV'])
        
        # Acceleration parameters
        accel_steps = min(total_steps // 4, 100)
        decel_steps = min(total_steps // 4, 100)
        cruise_steps = total_steps - accel_steps - decel_steps
        
        # Movement loop with acceleration/deceleration
        for i in range(total_steps):
            # Calculate current delay based on position in movement
            if i < accel_steps:
                delay = config['STEP_DELAY'] * (1 + (accel_steps - i) / accel_steps)
            elif i >= total_steps - decel_steps:
                delay = config['STEP_DELAY'] * (1 + (i - (total_steps - decel_steps)) / decel_steps)
            else:
                delay = config['STEP_DELAY']
            
            # Check sensor before moving
            if self._check_sensor('X'):
                logger.warning("X sensor triggered during movement - stopping")
                break
            
            # Step motor
            self._step_motor('X', distance_mm > 0, delay)
            
            # Comment out or remove per-step logger.info statements
            # logger.info(f"X Step {i}/{total_steps}")

    def _move_y(self, distance_mm):
        """Move Y axis the specified distance."""
        config = self.motors['Y1']  # Use Y1 config for calculations
        
        # Convert mm to steps
        revolutions = distance_mm / config['MM_PER_REV']
        total_steps = int(revolutions * config['PULSES_PER_REV'])
        
        # Acceleration parameters
        accel_steps = min(total_steps // 4, 100)
        decel_steps = min(total_steps // 4, 100)
        cruise_steps = total_steps - accel_steps - decel_steps
        
        # Movement loop with acceleration/deceleration
        for i in range(total_steps):
            # Calculate current delay based on position in movement
            if i < accel_steps:
                delay = config['STEP_DELAY'] * (1 + (accel_steps - i) / accel_steps)
            elif i >= total_steps - decel_steps:
                delay = config['STEP_DELAY'] * (1 + (i - (total_steps - decel_steps)) / decel_steps)
            else:
                delay = config['STEP_DELAY']
            
            # Check sensors before moving
            if self._check_sensor('Y1') or self._check_sensor('Y2'):
                logger.warning("Y sensor triggered during movement - stopping")
                break
            
            # Step both Y motors together
            self._step_y_axis(distance_mm > 0, delay)
            
            # Comment out or remove per-step logger.info statements
            # logger.info(f"Y Step {i}/{total_steps}")

    def home_axis(self, axis='X'):
        """Home the specified axis."""
        try:
            if axis == 'X':
                self._home_x()
            elif axis == 'Y':
                self._home_y()
            else:
                raise ValueError(f"Invalid axis: {axis}")
            
        except Exception as e:
            logger.error(f"Error during homing: {e}")
            raise
        finally:
            # Disable motors
            for motor, config in self.motors.items():
                GPIO.output(config['EN'], GPIO.HIGH)
                GPIO.output(config['STEP'], GPIO.LOW)
                GPIO.output(config['DIR'], GPIO.LOW)

    def _home_x(self):
        """Home the X axis."""
        config = self.motors['X']
        # Comment out or remove logger.info statements for homing routines
        # logger.info("Starting X axis homing sequence")
        
        # Move towards home until sensor is triggered
        while not self._check_sensor('X'):
            self._step_motor('X', config['HOME_DIRECTION'] < 0, config['HOME_SPEED'])
        
        # Comment out or remove logger.info statements for homing routines
        # logger.info("X home sensor triggered")
        
        # Move away from sensor
        for _ in range(int(MACHINE_CONFIG['HOMING_OFFSET'] * config['PULSES_PER_REV'] / config['MM_PER_REV'])):
            self._step_motor('X', config['HOME_DIRECTION'] > 0, config['HOME_SPEED'])
        
        # Move back slowly to verify position
        while not self._check_sensor('X'):
            self._step_motor('X', config['HOME_DIRECTION'] < 0, config['VERIFY_SPEED'])
        
        # Comment out or remove logger.info statements for homing routines
        # logger.info("X axis homing complete")

    def _home_y(self):
        """Home the Y axis."""
        config = self.motors['Y1']  # Use Y1 config for calculations
        # Comment out or remove logger.info statements for homing routines
        # logger.info("Starting Y axis homing sequence")
        
        # Move towards home until either sensor is triggered
        while not (self._check_sensor('Y1') or self._check_sensor('Y2')):
            self._step_y_axis(config['HOME_DIRECTION'] < 0, config['HOME_SPEED'])
        
        # Comment out or remove logger.info statements for homing routines
        # logger.info("Y home sensor triggered")
        
        # Move away from sensor
        for _ in range(int(MACHINE_CONFIG['HOMING_OFFSET'] * config['PULSES_PER_REV'] / config['MM_PER_REV'])):
            self._step_y_axis(config['HOME_DIRECTION'] > 0, config['HOME_SPEED'])
        
        # Move back slowly to verify position
        while not (self._check_sensor('Y1') or self._check_sensor('Y2')):
            self._step_y_axis(config['HOME_DIRECTION'] < 0, config['VERIFY_SPEED'])
        
        # Comment out or remove logger.info statements for homing routines
        # logger.info("Y axis homing complete")

def main():
    """Main entry point."""
    try:
        controller = MotorController()
        
        # Test homing
        logger.info("Testing X axis homing")
        controller.home_axis('X')
        time.sleep(1)
        
        logger.info("Testing Y axis homing")
        controller.home_axis('Y')
        
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