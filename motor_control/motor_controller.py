#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Motor controller for Fabric CNC machine.
Handles movement and homing of X, Y, Z, and rotation motors.
"""

import math
import time
import logging
import RPi.GPIO as GPIO
import threading
from config import MOTOR_CONFIG, MACHINE_CONFIG, DIRECTION_INVERTED, config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Disable GPIO warnings
GPIO.setwarnings(False)

class MotorController:
    """Controls the X, Y, Z, and rotation motors of the Fabric CNC machine."""
    
    def __init__(self):
        """Initialize the motor controller."""
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        
        # Initialize motors
        self.motors = {
            'X': MOTOR_CONFIG['X'],
            'Y1': MOTOR_CONFIG['Y1'],
            'Y2': MOTOR_CONFIG['Y2'],
            'Z': MOTOR_CONFIG['Z_LIFT'],
            'ROT': MOTOR_CONFIG['Z_ROTATE']
        }
        
        # Setup motor pins
        self._setup_motors()
        
        # Setup hall effect sensors
        self._setup_sensors()
        
        # Movement control
        self._stop_requested = False
        self._current_movement = None
        
        # Enhanced sensor debouncing with individual times per sensor
        # Map internal motor names to config names
        motor_to_config_map = {
            'X': 'X',
            'Y1': 'Y1', 
            'Y2': 'Y2',
            'Z': 'Z_LIFT',      # Map 'Z' to 'Z_LIFT' in config
            'ROT': 'Z_ROTATE'   # Map 'ROT' to 'Z_ROTATE' in config
        }
        
        self._sensor_debounce_times = {
            motor: config.sensor_debounce_times[config_name] / 1000.0 
            for motor, config_name in motor_to_config_map.items()
        }
        self._sensor_last_trigger_time = {
            'X': 0,
            'Y1': 0,
            'Y2': 0,
            'Z': 0,
            'ROT': 0
        }
        self._sensor_last_state = {
            'X': False,
            'Y1': False,
            'Y2': False,
            'Z': False,
            'ROT': False
        }
        # Multi-reading debounce for better noise immunity
        self._sensor_readings = {
            'X': [],
            'Y1': [],
            'Y2': [],
            'Z': [],
            'ROT': []
        }
        self._sensor_reading_count = config.sensor_reading_count  # Number of consistent readings required
        
        logger.info("Motor controller initialized")
        logger.info(f"X sensor debounce time: {self._sensor_debounce_times['X'] * 1000:.1f}ms")
        logger.info(f"Other sensors debounce time: 10-12ms")
        logger.info(f"Reading count required: {self._sensor_reading_count}")

    def _setup_motors(self):
        """Setup GPIO pins for all motors."""
        for motor, config in self.motors.items():
            GPIO.setup(config['STEP'], GPIO.OUT)
            GPIO.setup(config['DIR'], GPIO.OUT)
            GPIO.setup(config['EN'], GPIO.OUT)
            GPIO.output(config['EN'], GPIO.LOW)  # Enable motors (LOW = enabled)
            GPIO.output(config['STEP'], GPIO.LOW)
            GPIO.output(config['DIR'], GPIO.LOW)
            logger.info(f"Setup {motor} motor pins")

    def _setup_sensors(self):
        """Setup hall effect sensors as inputs with pull-up resistors."""
        for motor, config in self.motors.items():
            GPIO.setup(config['HALL'], GPIO.IN, pull_up_down=GPIO.PUD_UP)
            logger.info(f"Setup {motor} hall effect sensor")

    def _check_sensor(self, motor):
        """Check if hall effect sensor is triggered with optimized debouncing."""
        import time
        current_time = time.time()
        
        # Read current sensor state with minimal delay for performance
        current_state = GPIO.input(self.motors[motor]['HALL']) == GPIO.LOW
        
        # Add current reading to history for multi-reading debounce
        self._sensor_readings[motor].append(current_state)
        if len(self._sensor_readings[motor]) > self._sensor_reading_count:
            self._sensor_readings[motor].pop(0)  # Keep only the last N readings
        
        # Check if we have enough readings for debounce
        if len(self._sensor_readings[motor]) < self._sensor_reading_count:
            return self._sensor_last_state[motor]  # Not enough readings yet
        
        # Check if all recent readings are consistent (all True or all False)
        all_triggered = all(self._sensor_readings[motor])
        all_released = not any(self._sensor_readings[motor])
        
        # If sensor is triggered (all readings show LOW)
        if all_triggered:
            # Check if this is a new trigger (not within debounce time)
            if current_time - self._sensor_last_trigger_time[motor] > self._sensor_debounce_times[motor]:
                # This is a valid trigger
                self._sensor_last_trigger_time[motor] = current_time
                self._sensor_last_state[motor] = True
                logger.debug(f"{motor} sensor triggered (optimized debounced)")
                return True
            else:
                # Still within debounce time, return last known state
                return self._sensor_last_state[motor]
        elif all_released:
            # Sensor is consistently not triggered (all readings show HIGH)
            # Reset the trigger time when sensor is consistently released
            if self._sensor_last_state[motor]:
                self._sensor_last_trigger_time[motor] = 0
                logger.debug(f"{motor} sensor released (optimized debounced)")
            self._sensor_last_state[motor] = False
            return False
        else:
            # Inconsistent readings - return last known state
            return self._sensor_last_state[motor]

    def set_sensor_debounce_time(self, debounce_time_ms, motor=None):
        """Set the sensor debounce time in milliseconds.
        
        Args:
            debounce_time_ms: Debounce time in milliseconds
            motor: Specific motor to set debounce for ('X', 'Y1', 'Y2', 'Z', 'ROT'), or None for all
        """
        if motor is None:
            # Set for all motors
            for motor_name in self._sensor_debounce_times:
                self._sensor_debounce_times[motor_name] = debounce_time_ms / 1000.0
            logger.info(f"All sensor debounce times set to {debounce_time_ms}ms")
        elif motor in self._sensor_debounce_times:
            # Set for specific motor
            self._sensor_debounce_times[motor] = debounce_time_ms / 1000.0
            logger.info(f"{motor} sensor debounce time set to {debounce_time_ms}ms")
        else:
            raise ValueError(f"Invalid motor: {motor}")

    def get_sensor_debounce_time(self, motor=None):
        """Get the current sensor debounce time in milliseconds.
        
        Args:
            motor: Specific motor to get debounce for ('X', 'Y1', 'Y2', 'Z', 'ROT'), or None for all
            
        Returns:
            Debounce time in milliseconds (dict if motor=None, float if motor specified)
        """
        if motor is None:
            # Return all debounce times
            return {motor_name: time_ms * 1000.0 for motor_name, time_ms in self._sensor_debounce_times.items()}
        elif motor in self._sensor_debounce_times:
            # Return specific motor debounce time
            return self._sensor_debounce_times[motor] * 1000.0
        else:
            raise ValueError(f"Invalid motor: {motor}")

    def set_sensor_reading_count(self, count):
        """Set the number of consistent readings required for debounce confirmation.
        
        Args:
            count: Number of readings (recommended: 3-5)
        """
        if count < 1:
            raise ValueError("Reading count must be at least 1")
        self._sensor_reading_count = count
        logger.info(f"Sensor reading count set to {count}")

    def reset_sensor_debounce_state(self):
        """Reset all sensor debounce states to prevent carryover issues."""
        for motor in self._sensor_last_trigger_time:
            self._sensor_last_trigger_time[motor] = 0
            self._sensor_last_state[motor] = False
            self._sensor_readings[motor].clear()
        logger.info("Sensor debounce states reset")

    def reset_sensor_debounce_state_for_axis(self, axis):
        """Reset debounce state for a specific axis."""
        if axis == 'X':
            motor = 'X'
        elif axis == 'Y':
            # Reset both Y motors
            for motor in ['Y1', 'Y2']:
                self._sensor_last_trigger_time[motor] = 0
                self._sensor_last_state[motor] = False
                self._sensor_readings[motor].clear()
            logger.info("Y axis sensor debounce states reset")
            return
        elif axis == 'Z':
            motor = 'Z'
        elif axis == 'ROT':
            motor = 'ROT'
        else:
            return
        
        self._sensor_last_trigger_time[motor] = 0
        self._sensor_last_state[motor] = False
        self._sensor_readings[motor].clear()
        logger.info(f"{axis} axis sensor debounce state reset")

    def _ensure_output(self, pin):
        try:
            GPIO.setup(pin, GPIO.OUT)
        except Exception as e:
            logger.debug(f"Could not setup pin {pin} as output: {e}")
            # Try to force the pin setup
            try:
                GPIO.cleanup(pin)
                GPIO.setup(pin, GPIO.OUT)
            except Exception:
                pass  # Ignore if still can't set

    def _step_motor(self, motor, direction, delay):
        """Step a single motor."""
        config = self.motors[motor]
        # Apply direction inversion based on motor configuration
        if motor == 'X':
            inverted = DIRECTION_INVERTED.get('X', False)
        elif motor == 'Y1':
            inverted = DIRECTION_INVERTED.get('Y1', False)
        elif motor == 'Y2':
            inverted = DIRECTION_INVERTED.get('Y2', False)
        elif motor == 'Z':
            inverted = DIRECTION_INVERTED.get('Z_LIFT', False)
        elif motor == 'ROT':
            inverted = DIRECTION_INVERTED.get('Z_ROTATE', False)
        else:
            inverted = False
        
        # Apply inversion if needed
        if inverted:
            direction = not direction
            
        self._ensure_output(config['DIR'])
        GPIO.output(config['DIR'], GPIO.HIGH if direction else GPIO.LOW)
        self._ensure_output(config['STEP'])
        GPIO.output(config['STEP'], GPIO.HIGH)
        time.sleep(delay/2)
        GPIO.output(config['STEP'], GPIO.LOW)
        time.sleep(delay/2)

    def _step_y_axis(self, direction, delay):
        """Step both Y motors together to maintain sync."""
        # Apply direction inversion based on motor configuration
        y1_inverted = DIRECTION_INVERTED.get('Y1', False)
        y2_inverted = DIRECTION_INVERTED.get('Y2', False)
        
        # Apply inversion if needed
        y1_direction = not direction if y1_inverted else direction
        y2_direction = not direction if y2_inverted else direction
        
        # Set directions for both Y motors
        self._ensure_output(self.motors['Y1']['DIR'])
        self._ensure_output(self.motors['Y2']['DIR'])
        GPIO.output(self.motors['Y1']['DIR'], GPIO.HIGH if y1_direction else GPIO.LOW)
        GPIO.output(self.motors['Y2']['DIR'], GPIO.HIGH if y2_direction else GPIO.LOW)
        
        # Step both motors together
        self._ensure_output(self.motors['Y1']['STEP'])
        self._ensure_output(self.motors['Y2']['STEP'])
        GPIO.output(self.motors['Y1']['STEP'], GPIO.HIGH)
        GPIO.output(self.motors['Y2']['STEP'], GPIO.HIGH)
        time.sleep(delay/2)
        GPIO.output(self.motors['Y1']['STEP'], GPIO.LOW)
        GPIO.output(self.motors['Y2']['STEP'], GPIO.LOW)
        time.sleep(delay/2)

    def _step_y_axis_individual(self, direction, delay, y1_homed, y2_homed):
        """Step Y motors individually - only step motors that haven't found home."""
        # Apply direction inversion based on motor configuration
        y1_inverted = DIRECTION_INVERTED.get('Y1', False)
        y2_inverted = DIRECTION_INVERTED.get('Y2', False)
        
        # Apply inversion if needed
        y1_direction = not direction if y1_inverted else direction
        y2_direction = not direction if y2_inverted else direction
        
        # Set directions for both Y motors
        self._ensure_output(self.motors['Y1']['DIR'])
        self._ensure_output(self.motors['Y2']['DIR'])
        GPIO.output(self.motors['Y1']['DIR'], GPIO.HIGH if y1_direction else GPIO.LOW)
        GPIO.output(self.motors['Y2']['DIR'], GPIO.HIGH if y2_direction else GPIO.LOW)
        
        # Step motors individually - only step if not homed
        if not y1_homed:
            self._ensure_output(self.motors['Y1']['STEP'])
            GPIO.output(self.motors['Y1']['STEP'], GPIO.HIGH)
        if not y2_homed:
            self._ensure_output(self.motors['Y2']['STEP'])
            GPIO.output(self.motors['Y2']['STEP'], GPIO.HIGH)
        
        time.sleep(delay/2)
        
        if not y1_homed:
            GPIO.output(self.motors['Y1']['STEP'], GPIO.LOW)
        if not y2_homed:
            GPIO.output(self.motors['Y2']['STEP'], GPIO.LOW)
        
        time.sleep(delay/2)

    def move_distance(self, distance_mm, axis='X'):
        """Move the specified distance with acceleration/deceleration."""
        try:
            # Set current movement and reset stop flag
            self._current_movement = axis
            self._stop_requested = False
            
            if axis == 'X':
                self._move_x(distance_mm)
            elif axis == 'Y':
                self._move_y(distance_mm)
            elif axis == 'Z':
                self._move_z(distance_mm)
            elif axis == 'ROT':
                self._move_rot(distance_mm)
            else:
                raise ValueError(f"Invalid axis: {axis}")
            
        except Exception as e:
            logger.error(f"Error during movement: {e}")
            raise
        finally:
            # Keep motors enabled but reset step/dir pins
            try:
                for motor, config in self.motors.items():
                    self._ensure_output(config['EN'])
                    GPIO.output(config['EN'], GPIO.LOW)  # LOW = enabled
                    self._ensure_output(config['STEP'])
                    GPIO.output(config['STEP'], GPIO.LOW)
                    self._ensure_output(config['DIR'])
                    GPIO.output(config['DIR'], GPIO.LOW)
            except Exception as e:
                logger.warning(f"Error resetting motor pins: {e}")
            self._current_movement = None

    def move_coordinated(self, x_distance_mm=0, y_distance_mm=0, z_distance_mm=0, rot_distance_mm=0):
        """Move X and Y axes simultaneously in a coordinated manner."""
        try:
            # Set current movement and reset stop flag
            self._current_movement = 'COORDINATED'
            self._stop_requested = False
            
            # Debug: Print movement details
            logger.info(f"Coordinated movement: X={x_distance_mm:.2f}mm, Y={y_distance_mm:.2f}mm, Z={z_distance_mm:.2f}mm, ROT={rot_distance_mm:.2f}mm")
            
            # Only proceed if we have X or Y movement
            if abs(x_distance_mm) < 1e-6 and abs(y_distance_mm) < 1e-6:
                logger.info("No X/Y movement detected, handling Z and ROT only")
                # No X/Y movement, just handle Z and ROT if needed
                if abs(z_distance_mm) > 1e-6:
                    self._move_z(z_distance_mm)
                if abs(rot_distance_mm) > 1e-6:
                    self._move_rot(rot_distance_mm)
                return
            
            # Calculate steps for each axis
            x_config = self.motors['X']
            y_config = self.motors['Y1']  # Use Y1 config for calculations
            
            x_revolutions = abs(x_distance_mm) / x_config['MM_PER_REV']
            y_revolutions = abs(y_distance_mm) / y_config['MM_PER_REV']
            
            x_total_steps = int(x_revolutions * x_config['PULSES_PER_REV'])
            y_total_steps = int(y_revolutions * y_config['PULSES_PER_REV'])
            
            # Use the larger number of steps to determine the movement duration
            max_steps = max(x_total_steps, y_total_steps)
            
            if max_steps == 0:
                return
            
            # Calculate step ratios for interpolation
            x_step_ratio = x_total_steps / max_steps if max_steps > 0 else 0
            y_step_ratio = y_total_steps / max_steps if max_steps > 0 else 0
            
            # Debug: Print step calculations
            logger.info(f"Step calculations: X={x_total_steps} steps, Y={y_total_steps} steps, max_steps={max_steps}")
            logger.info(f"Step ratios: X={x_step_ratio:.3f}, Y={y_step_ratio:.3f}")
            
            # Acceleration parameters (use the faster axis for timing)
            fast_config = x_config if x_config['STEP_DELAY'] <= y_config['STEP_DELAY'] else y_config
            accel_steps = min(max_steps // 4, 100)
            decel_steps = min(max_steps // 4, 100)
            cruise_steps = max_steps - accel_steps - decel_steps
            
            # Movement loop with acceleration/deceleration
            x_step_counter = 0
            y_step_counter = 0
            
            logger.info(f"Starting coordinated movement loop with {max_steps} total steps")
            
            for i in range(max_steps):
                # Check if stop was requested
                if self._stop_requested:
                    logger.info("Stop requested - halting coordinated movement")
                    break
                
                # Calculate current delay based on position in movement
                if i < accel_steps:
                    delay = fast_config['STEP_DELAY'] * (1 + (accel_steps - i) / accel_steps)
                elif i >= max_steps - decel_steps:
                    delay = fast_config['STEP_DELAY'] * (1 + (i - (max_steps - decel_steps)) / decel_steps)
                else:
                    delay = fast_config['STEP_DELAY']
                
                # Check sensors before moving (X and Y only - ROT sensor checking removed)
                if self._check_sensor('X'):
                    logger.warning("X sensor triggered during coordinated movement - stopping")
                    break
                if self._check_sensor('Y1'):
                    logger.warning("Y1 sensor triggered during coordinated movement - stopping")
                    break
                if self._check_sensor('Y2'):
                    logger.warning("Y2 sensor triggered during coordinated movement - stopping")
                    break
                
                # Determine if we should step each axis based on interpolation
                should_step_x = False
                should_step_y = False
                
                if x_total_steps > 0:
                    target_x_steps = (i + 1) * x_step_ratio
                    if x_step_counter < target_x_steps:
                        should_step_x = True
                        x_step_counter += 1
                
                if y_total_steps > 0:
                    target_y_steps = (i + 1) * y_step_ratio
                    if y_step_counter < target_y_steps:
                        should_step_y = True
                        y_step_counter += 1
                
                # Step motors - both step functions include their own delays
                if should_step_x:
                    self._step_motor('X', x_distance_mm > 0, delay)
                if should_step_y:
                    self._step_y_axis(y_distance_mm > 0, delay)
                
                # Debug: Log every 1000 steps to show progress
                if i % 1000 == 0 and i > 0:
                    logger.info(f"Movement progress: {i}/{max_steps} steps completed")
            
            # Handle Z and ROT movement after X/Y movement
            if abs(z_distance_mm) > 1e-6:
                self._move_z(z_distance_mm)
            if abs(rot_distance_mm) > 1e-6:
                self._move_rot(rot_distance_mm)
            
        except Exception as e:
            logger.error(f"Error during coordinated movement: {e}")
            raise
        finally:
            # Keep motors enabled but reset step/dir pins
            try:
                for motor, config in self.motors.items():
                    self._ensure_output(config['EN'])
                    GPIO.output(config['EN'], GPIO.LOW)  # LOW = enabled
                    self._ensure_output(config['STEP'])
                    GPIO.output(config['STEP'], GPIO.LOW)
                    self._ensure_output(config['DIR'])
                    GPIO.output(config['DIR'], GPIO.LOW)
            except Exception as e:
                logger.warning(f"Error resetting motor pins: {e}")
            self._current_movement = None



    def _move_x(self, distance_mm):
        """Move X axis the specified distance."""
        config = self.motors['X']
        
        # Convert mm to steps (use absolute value for step count)
        revolutions = abs(distance_mm) / config['MM_PER_REV']
        total_steps = int(revolutions * config['PULSES_PER_REV'])
        
        # Acceleration parameters
        accel_steps = min(total_steps // 4, 100)
        decel_steps = min(total_steps // 4, 100)
        cruise_steps = total_steps - accel_steps - decel_steps
        
        # Movement loop with acceleration/deceleration
        for i in range(total_steps):
            # Check if stop was requested
            if self._stop_requested:
                logger.info("Stop requested - halting X movement")
                break
                
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
            
            # Step motor (direction is determined by distance_mm > 0)
            self._step_motor('X', distance_mm > 0, delay)
            
            # Comment out or remove per-step logger.info statements
            # logger.info(f"X Step {i}/{total_steps}")

    def _move_y(self, distance_mm):
        """Move Y axis the specified distance."""
        config = self.motors['Y1']  # Use Y1 config for calculations
        
        # Convert mm to steps (use absolute value for step count)
        revolutions = abs(distance_mm) / config['MM_PER_REV']
        total_steps = int(revolutions * config['PULSES_PER_REV'])
        
        # Acceleration parameters
        accel_steps = min(total_steps // 4, 100)
        decel_steps = min(total_steps // 4, 100)
        cruise_steps = total_steps - accel_steps - decel_steps
        
        # Movement loop with acceleration/deceleration
        for i in range(total_steps):
            # Check if stop was requested
            if self._stop_requested:
                logger.info("Stop requested - halting Y movement")
                break
                
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
            
            # Step both Y motors together (direction is determined by distance_mm > 0)
            self._step_y_axis(distance_mm > 0, delay)
            
            # Comment out or remove per-step logger.info statements
            # logger.info(f"Y Step {i}/{total_steps}")

    def _move_z(self, distance_mm):
        """Move Z axis the specified distance."""
        config = self.motors['Z']
        
        # Convert mm to steps (use absolute value for step count)
        revolutions = abs(distance_mm) / config['MM_PER_REV']
        total_steps = int(revolutions * config['PULSES_PER_REV'])
        
        # Check if sensor is triggered at start - allow movement away from home even if sensor is triggered
        sensor_triggered = self._check_sensor('Z')
        if sensor_triggered:
            logger.warning("Z sensor is triggered - allowing movement away from home")
            # Only prevent movement if trying to move toward home (negative distance for Z)
            if distance_mm < 0:
                logger.error("Z sensor is triggered - cannot move Z toward home.")
                return
        
        # Acceleration parameters
        accel_steps = min(total_steps // 4, 50)  # Slower acceleration for Z
        decel_steps = min(total_steps // 4, 50)
        cruise_steps = total_steps - accel_steps - decel_steps
        
        # Movement loop with acceleration/deceleration
        for i in range(total_steps):
            # Check if stop was requested
            if self._stop_requested:
                logger.info("Stop requested - halting Z movement")
                break
                
            # Calculate current delay based on position in movement
            if i < accel_steps:
                delay = config['STEP_DELAY'] * (1 + (accel_steps - i) / accel_steps)
            elif i >= total_steps - decel_steps:
                delay = config['STEP_DELAY'] * (1 + (i - (total_steps - decel_steps)) / decel_steps)
            else:
                delay = config['STEP_DELAY']
            
            # Check sensor during movement - only stop if moving toward home and sensor is triggered
            if distance_mm < 0 and self._check_sensor('Z'):
                logger.warning("Z sensor triggered during movement toward home - stopping")
                break
            
            # Step motor (direction is determined by distance_mm > 0)
            self._step_motor('Z', distance_mm > 0, delay)

    def _move_rot(self, distance_mm):
        """Move rotation axis the specified distance (degrees)."""
        config = self.motors['ROT']
        
        # Convert degrees to steps (use absolute value for step count)
        revolutions = abs(distance_mm) / config['MM_PER_REV']  # MM_PER_REV is 360 for rotation
        total_steps = int(revolutions * config['PULSES_PER_REV'])
        
        # Acceleration parameters
        accel_steps = min(total_steps // 4, 50)  # Slower acceleration for rotation
        decel_steps = min(total_steps // 4, 50)
        cruise_steps = total_steps - accel_steps - decel_steps
        
        # Movement loop with acceleration/deceleration
        for i in range(total_steps):
            # Check if stop was requested
            if self._stop_requested:
                logger.info("Stop requested - halting rotation movement")
                break
                
            # Calculate current delay based on position in movement
            if i < accel_steps:
                delay = config['STEP_DELAY'] * (1 + (accel_steps - i) / accel_steps)
            elif i >= total_steps - decel_steps:
                delay = config['STEP_DELAY'] * (1 + (i - (total_steps - decel_steps)) / decel_steps)
            else:
                delay = config['STEP_DELAY']
            
            # Step motor (direction is determined by distance_mm > 0)
            self._step_motor('ROT', distance_mm > 0, delay)

    def home_axis(self, axis='X'):
        """Home the specified axis."""
        try:
            if axis == 'X':
                self._home_x()
            elif axis == 'Y':
                self._home_y()
            elif axis == 'Z':
                self._home_z()
            elif axis == 'ROT':
                self._home_rot()
            else:
                raise ValueError(f"Invalid axis: {axis}")
            
        except Exception as e:
            logger.error(f"Error during homing: {e}")
            raise
        finally:
            # Keep motors enabled but reset step/dir pins
            for motor, config in self.motors.items():
                try:
                    self._ensure_output(config['EN'])
                    self._ensure_output(config['STEP'])
                    self._ensure_output(config['DIR'])
                    GPIO.output(config['EN'], GPIO.LOW)  # LOW = enabled
                    GPIO.output(config['STEP'], GPIO.LOW)
                    GPIO.output(config['DIR'], GPIO.LOW)
                except Exception as pin_error:
                    logger.warning(f"Could not reset {motor} motor pins after homing: {pin_error}")

    def home_all_synchronous(self):
        """Home all axes simultaneously using threading."""
        try:
            logger.info("Starting synchronous homing of all axes")
            
            # Create threads for each axis
            threads = {}
            results = {}
            
            # Create a lock for thread-safe logging
            log_lock = threading.Lock()
            
            def home_with_result(axis):
                """Home a single axis and store the result."""
                try:
                    with log_lock:
                        logger.info(f"Starting homing for {axis} axis")
                    
                    if axis == 'X':
                        self._home_x()
                    elif axis == 'Y':
                        self._home_y()
                    elif axis == 'Z':
                        self._home_z()
                    elif axis == 'ROT':
                        self._home_rot()
                    
                    results[axis] = True
                    with log_lock:
                        logger.info(f"Completed homing for {axis} axis")
                        
                except Exception as e:
                    results[axis] = False
                    with log_lock:
                        logger.error(f"Error homing {axis} axis: {e}")
            
            # Start all homing threads
            for axis in ['X', 'Y', 'Z', 'ROT']:
                thread = threading.Thread(target=home_with_result, args=(axis,))
                threads[axis] = thread
                thread.start()
            
            # Wait for all threads to complete
            for axis, thread in threads.items():
                thread.join()
            
            # Check results
            failed_axes = [axis for axis, success in results.items() if not success]
            if failed_axes:
                raise Exception(f"Homing failed for axes: {', '.join(failed_axes)}")
            
            logger.info("Synchronous homing completed successfully for all axes")
            
        except Exception as e:
            logger.error(f"Error during synchronous homing: {e}")
            raise
        finally:
            # Keep motors enabled but reset step/dir pins
            for motor, config in self.motors.items():
                try:
                    self._ensure_output(config['EN'])
                    self._ensure_output(config['STEP'])
                    self._ensure_output(config['DIR'])
                    GPIO.output(config['EN'], GPIO.LOW)  # LOW = enabled
                    GPIO.output(config['STEP'], GPIO.LOW)
                    GPIO.output(config['DIR'], GPIO.LOW)
                except Exception as pin_error:
                    logger.warning(f"Could not reset {motor} motor pins after homing: {pin_error}")

    def _home_x(self):
        """Home the X axis."""
        config = self.motors['X']
        # Reset debounce state to prevent carryover issues
        self.reset_sensor_debounce_state_for_axis('X')
        
        # Comment out or remove logger.info statements for homing routines
        # logger.info("Starting X axis homing sequence")
        
        # Move until sensor is triggered
        while not self._check_sensor('X'):
            self._step_motor('X', config['HOME_DIRECTION'] < 0, config['HOME_SPEED'])
        
        # Move back slightly to clear sensor
        logger.info("Moving back to clear sensor...")
        for _ in range(200):  # Much more extreme back-off to ensure sensors are cleared
            self._step_motor('X', config['HOME_DIRECTION'] > 0, config['VERIFY_SPEED'])
        
        # Move forward very slowly until sensor is triggered again (fine approach)
        logger.info("Fine approach to home position...")
        fine_speed = 0.005  # Much slower speed for fine approach (5ms between pulses)
        while not self._check_sensor('X'):
            self._step_motor('X', config['HOME_DIRECTION'] < 0, fine_speed)
        
        # Move back slightly again to clear sensor for second approach
        logger.info("Moving back for second approach...")
        for _ in range(100):  # Smaller back-off for second approach
            self._step_motor('X', config['HOME_DIRECTION'] > 0, config['VERIFY_SPEED'])
        
        # Second fine approach to verify sensor position
        logger.info("Second fine approach to verify home position...")
        while not self._check_sensor('X'):
            self._step_motor('X', config['HOME_DIRECTION'] < 0, fine_speed)
        
        # Move away from home position to clear sensor and allow movement
        logger.info("Moving away from home position...")
        for _ in range(100):  # Move 100 steps away from home
            self._step_motor('X', config['HOME_DIRECTION'] > 0, config['VERIFY_SPEED'])
        
        logger.info("X axis homed successfully")

    def _home_y(self):
        """Home the Y axis - stop each motor when its own sensor triggers."""
        config = self.motors['Y1']  # Use Y1 config for calculations
        # Reset debounce state to prevent carryover issues
        self.reset_sensor_debounce_state_for_axis('Y')
        
        logger.info("Starting Y axis homing sequence")
        
        # Step 1: Fast approach - Move until both sensors are triggered
        logger.info("Step 1: Fast approach to find home...")
        y1_homed = False
        y2_homed = False
        
        while not (y1_homed and y2_homed):
            # Check sensors and update homed status
            if not y1_homed and self._check_sensor('Y1'):
                y1_homed = True
                logger.info("Y1 (left) motor found home")
            if not y2_homed and self._check_sensor('Y2'):
                y2_homed = True
                logger.info("Y2 (right) motor found home")
            
            # Step motors - only step motors that haven't found home yet
            if not y1_homed or not y2_homed:
                self._step_y_axis_individual(config['HOME_DIRECTION'] < 0, config['HOME_SPEED'], y1_homed, y2_homed)
        
        # Step 2: Back off to clear sensors
        logger.info("Step 2: Moving back to clear sensors...")
        for _ in range(200):  # Much more extreme back-off to ensure sensors are cleared
            self._step_y_axis_individual(config['HOME_DIRECTION'] > 0, config['VERIFY_SPEED'], False, False)
        
        # Step 3: Fine approach - Move very slowly until both sensors are triggered again
        logger.info("Step 3: Fine approach to home position...")
        y1_homed = False
        y2_homed = False
        
        # Use much slower speed for fine approach (5ms between pulses)
        fine_speed = 0.005
        
        while not (y1_homed and y2_homed):
            # Check sensors and update homed status
            if not y1_homed and self._check_sensor('Y1'):
                y1_homed = True
                logger.info("Y1 (left) motor fine approach complete")
            if not y2_homed and self._check_sensor('Y2'):
                y2_homed = True
                logger.info("Y2 (right) motor fine approach complete")
            
            # Step motors - only step motors that haven't found home yet
            if not y1_homed or not y2_homed:
                self._step_y_axis_individual(config['HOME_DIRECTION'] < 0, fine_speed, y1_homed, y2_homed)
        
        # Step 3.5: Move back slightly again to clear sensors for second approach
        logger.info("Step 3.5: Moving back for second approach...")
        for _ in range(100):  # Smaller back-off for second approach
            self._step_y_axis_individual(config['HOME_DIRECTION'] > 0, config['VERIFY_SPEED'], False, False)
        
        # Step 4: Second fine approach to verify sensor positions
        logger.info("Step 4: Second fine approach to verify home position...")
        y1_homed = False
        y2_homed = False
        
        while not (y1_homed and y2_homed):
            # Check sensors and update homed status
            if not y1_homed and self._check_sensor('Y1'):
                y1_homed = True
                logger.info("Y1 (left) motor second fine approach complete")
            if not y2_homed and self._check_sensor('Y2'):
                y2_homed = True
                logger.info("Y2 (right) motor second fine approach complete")
            
            # Step motors - only step motors that haven't found home yet
            if not y1_homed or not y2_homed:
                self._step_y_axis_individual(config['HOME_DIRECTION'] < 0, fine_speed, y1_homed, y2_homed)
        
        # Step 5: Final back off for clearance
        logger.info("Step 5: Moving away from home position for clearance...")
        for _ in range(100):
            self._step_y_axis_individual(config['HOME_DIRECTION'] > 0, config['VERIFY_SPEED'], False, False)
        
        logger.info("Y axis homing sequence completed successfully")

    def _home_z(self):
        """Home the Z axis."""
        config = self.motors['Z']
        # Reset debounce state to prevent carryover issues
        self.reset_sensor_debounce_state_for_axis('Z')
        
        logger.info("Starting Z axis homing sequence")
        logger.info(f"Z HOME_DIRECTION: {config['HOME_DIRECTION']}, moving in direction: {config['HOME_DIRECTION'] < 0}")
        
        # Move until sensor is triggered
        step_count = 0
        while not self._check_sensor('Z'):
            self._step_motor('Z', config['HOME_DIRECTION'] < 0, config['HOME_SPEED'])
            step_count += 1
            if step_count % 1000 == 0:  # Log every 1000 steps
                logger.info(f"Z homing: {step_count} steps completed, sensor still not triggered")
        
        logger.info(f"Z sensor triggered after {step_count} steps")
        
        # Move back significantly to clear sensor
        logger.info("Moving back to clear sensor...")
        for _ in range(1000):  # Much more aggressive back-off for Z axis to ensure sensors are cleared
            self._step_motor('Z', config['HOME_DIRECTION'] > 0, config['HOME_SPEED'])
        
        # Move forward very slowly until sensor is triggered again (fine approach)
        logger.info("Fine approach to home position...")
        fine_speed = 0.005  # Much slower speed for fine approach (5ms between pulses)
        approach_step_count = 0
        while not self._check_sensor('Z'):
            self._step_motor('Z', config['HOME_DIRECTION'] < 0, fine_speed)
            approach_step_count += 1
            if approach_step_count % 100 == 0:  # Log every 100 steps
                logger.info(f"Z fine approach: {approach_step_count} steps completed")
        
        logger.info(f"Z fine approach completed after {approach_step_count} steps")
        
        # Move back slightly again to clear sensor for second approach
        logger.info("Moving back for second approach...")
        for _ in range(100):  # Minimal back-off for second approach
            self._step_motor('Z', config['HOME_DIRECTION'] > 0, config['HOME_SPEED'])
        
        # Second fine approach to verify sensor position
        logger.info("Second fine approach to verify home position...")
        second_approach_step_count = 0
        fast_fine_speed = 0.002  # Faster speed for second approach (2ms between pulses)
        while not self._check_sensor('Z'):
            self._step_motor('Z', config['HOME_DIRECTION'] < 0, fast_fine_speed)
            second_approach_step_count += 1
            if second_approach_step_count % 100 == 0:  # Log every 100 steps
                logger.info(f"Z second fine approach: {second_approach_step_count} steps completed")
        
        logger.info(f"Z second fine approach completed after {second_approach_step_count} steps")
        
        # Move away from home position to clear sensor and allow movement
        logger.info("Moving away from home position...")
        for _ in range(2000):  # Much more aggressive final back-off for Z axis to provide maximum clearance
            self._step_motor('Z', config['HOME_DIRECTION'] > 0, config['HOME_SPEED'])
        
        logger.info("Z axis homed successfully")

    def _home_rot(self):
        """Home the rotation axis."""
        config = self.motors['ROT']
        # Reset debounce state to prevent carryover issues
        self.reset_sensor_debounce_state_for_axis('ROT')
        
        # logger.info("Starting rotation axis homing sequence")
        
        # Move until sensor is triggered
        while not self._check_sensor('ROT'):
            self._step_motor('ROT', config['HOME_DIRECTION'] < 0, config['HOME_SPEED'])
        
        # Move back slightly to clear sensor
        logger.info("Moving back to clear sensor...")
        for _ in range(100):  # Reduced back-off to clear sensor
            self._step_motor('ROT', config['HOME_DIRECTION'] > 0, config['VERIFY_SPEED'])
        
        # Move forward very slowly until sensor is triggered again (fine approach)
        logger.info("Fine approach to home position...")
        fine_speed = 0.005  # Much slower speed for fine approach (5ms between pulses)
        while not self._check_sensor('ROT'):
            self._step_motor('ROT', config['HOME_DIRECTION'] < 0, fine_speed)
        
        # Move back slightly again to clear sensor for second approach
        logger.info("Moving back for second approach...")
        for _ in range(100):  # Smaller back-off for second approach
            self._step_motor('ROT', config['HOME_DIRECTION'] > 0, config['VERIFY_SPEED'])
        
        # Second fine approach to verify sensor position
        logger.info("Second fine approach to verify home position...")
        while not self._check_sensor('ROT'):
            self._step_motor('ROT', config['HOME_DIRECTION'] < 0, fine_speed)
        
        # Move away from home position to clear sensor and allow movement
        logger.info("Moving away from home position...")
        for _ in range(355):  # Move 355 steps (80 degrees) away from home - updated for 1600 PULSES_PER_REV
            self._step_motor('ROT', config['HOME_DIRECTION'] > 0, config['VERIFY_SPEED'])
        
        logger.info("Rotation axis homed successfully")

    def stop_movement(self):
        """Stop any ongoing movement immediately."""
        self._stop_requested = True
        logger.info("Stop movement requested")

    def cleanup(self):
        """Clean up resources and disable all motors."""
        try:
            for motor, config in self.motors.items():
                try:
                    self._ensure_output(config['EN'])
                    self._ensure_output(config['STEP'])
                    self._ensure_output(config['DIR'])
                    GPIO.output(config['EN'], GPIO.HIGH)  # HIGH = disabled
                    GPIO.output(config['STEP'], GPIO.LOW)
                    GPIO.output(config['DIR'], GPIO.LOW)
                except Exception as pin_error:
                    logger.warning(f"Could not control {motor} motor pins: {pin_error}")
            logger.info("Motor controller cleanup completed - all motors disabled")
        except Exception as e:
            logger.error(f"Error during motor controller cleanup: {e}")

def main():
    """Test the motor controller."""
    controller = MotorController()
    
    try:
        # Test movement
        print("Testing X axis movement...")
        controller.move_distance(10, 'X')
        
        print("Testing Y axis movement...")
        controller.move_distance(10, 'Y')
        
        print("Testing Z axis movement...")
        controller.move_distance(5, 'Z')
        
        print("Testing rotation axis movement...")
        controller.move_distance(90, 'ROT')  # 90 degrees
        
    except KeyboardInterrupt:
        print("Test interrupted")
    finally:
        controller.cleanup()

if __name__ == "__main__":
    main() 