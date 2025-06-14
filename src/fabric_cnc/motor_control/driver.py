#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stepper motor driver implementation for fabric CNC machine.
Provides hardware abstraction and safety features for motor control.
"""

import logging
import math
import time
from dataclasses import dataclass
from typing import Optional, Protocol

try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None

from fabric_cnc.config import config

logger = logging.getLogger(__name__)

@dataclass
class MotorConfig:
    """Configuration for a stepper motor."""
    dir_pin: int
    step_pin: int
    en_pin: int
    name: str
    steps_per_mm: float
    direction_inverted: bool = False
    hall_pin: Optional[int] = None

class GPIOInterface(Protocol):
    """Protocol defining the interface for GPIO operations."""
    def setup(self, pin: int, mode: int) -> None: ...
    def output(self, pin: int, value: int) -> None: ...
    def cleanup(self, pins: Optional[list[int]] = None) -> None: ...

class StepperMotor:
    """Stepper motor controller with safety features and hardware abstraction."""
    
    def __init__(
        self,
        config: MotorConfig,
        gpio: Optional[GPIOInterface] = None,
        simulation_mode: bool = False
    ):
        """Initialize the stepper motor controller.
        
        Args:
            config: Motor configuration
            gpio: GPIO interface (defaults to RPi.GPIO if available)
            simulation_mode: If True, no actual GPIO operations are performed
        """
        self.config = config
        self.gpio = gpio or GPIO
        self.simulation_mode = simulation_mode
        self._enabled = False
        self._current_position = 0.0  # mm
        self._target_position = 0.0  # mm
        
        if not self.simulation_mode and self.gpio:
            self._setup_gpio()
        logger.info(f"Initialized motor {config.name}")

    def _setup_gpio(self) -> None:
        """Set up GPIO pins for the motor."""
        if not self.gpio:
            return
            
        self.gpio.setmode(self.gpio.BCM)
        self.gpio.setup(self.config.dir_pin, self.gpio.OUT)
        self.gpio.setup(self.config.step_pin, self.gpio.OUT)
        self.gpio.setup(self.config.en_pin, self.gpio.OUT)
        if self.config.hall_pin:
            self.gpio.setup(self.config.hall_pin, self.gpio.IN)
        self.gpio.output(self.config.en_pin, self.gpio.HIGH)

    def enable(self) -> None:
        """Enable the motor driver."""
        if not self.simulation_mode and self.gpio:
            self.gpio.output(self.config.en_pin, self.gpio.LOW)
        self._enabled = True
        logger.debug(f"Motor {self.config.name} enabled")

    def disable(self) -> None:
        """Disable the motor driver."""
        if not self.simulation_mode and self.gpio:
            self.gpio.output(self.config.en_pin, self.gpio.HIGH)
        self._enabled = False
        logger.debug(f"Motor {self.config.name} disabled")

    def move_mm(
        self,
        direction: bool,
        distance_mm: float,
        speed_mm_s: float
    ) -> None:
        """Move the motor a specified distance in millimeters.
        
        Args:
            direction: True for forward, False for reverse
            distance_mm: Distance to move in millimeters
            speed_mm_s: Speed in millimeters per second
        """
        if not self._enabled:
            self.enable()

        if distance_mm <= 0:
            raise ValueError("Distance must be positive")

        if speed_mm_s <= 0:
            raise ValueError("Speed must be positive")

        steps = int(distance_mm * self.config.steps_per_mm)
        step_delay = 1.0 / (speed_mm_s * self.config.steps_per_mm)
        logger.info(
            f"Moving motor {self.config.name} {distance_mm}mm "
            f"at {speed_mm_s}mm/s ({steps} steps)"
        )

        # Apply direction inversion if configured
        actual_direction = direction != self.config.direction_inverted
        
        if not self.simulation_mode and self.gpio:
            self.gpio.output(
                self.config.dir_pin,
                self.gpio.HIGH if actual_direction else self.gpio.LOW
            )

        for step in range(steps):
            if not self.simulation_mode and self.gpio:
                self.gpio.output(self.config.step_pin, self.gpio.HIGH)
                time.sleep(step_delay)
                self.gpio.output(self.config.step_pin, self.gpio.LOW)
            time.sleep(step_delay)
            
            if step % 100 == 0:  # Log progress every 100 steps
                logger.debug(
                    f"Motor {self.config.name} step {step}/{steps}"
                )

        # Update position
        if direction:
            self._current_position += distance_mm
        else:
            self._current_position -= distance_mm
            
        logger.info(
            f"Moved motor {self.config.name} "
            f"{'forward' if direction else 'reverse'} {distance_mm}mm"
        )

    def get_position(self) -> float:
        """Get current position in millimeters."""
        return self._current_position

    def set_position(self, position: float) -> None:
        """Set current position in millimeters."""
        self._current_position = position
        logger.info(f"Set {self.config.name} motor position to {position}mm")

    def cleanup(self) -> None:
        """Clean up GPIO resources."""
        if not self.simulation_mode and self.gpio:
            pins = [
                self.config.dir_pin,
                self.config.step_pin,
                self.config.en_pin
            ]
            if self.config.hall_pin:
                pins.append(self.config.hall_pin)
            self.gpio.cleanup(pins)
        logger.info(f"Cleaned up motor {self.config.name}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup."""
        self.cleanup()

class YAxisController:
    """Controller for synchronized Y-axis movement using two motors."""
    
    def __init__(
        self,
        y1_motor: StepperMotor,
        y2_motor: StepperMotor,
        simulation_mode: bool = False
    ):
        """Initialize Y-axis controller.
        
        Args:
            y1_motor: First Y-axis motor
            y2_motor: Second Y-axis motor
            simulation_mode: If True, simulate motor movement without hardware
        """
        self.y1_motor = y1_motor
        self.y2_motor = y2_motor
        self.simulation_mode = simulation_mode
        self._enabled = False
        
        logger.info("Initialized Y-axis controller")
        
    def enable(self) -> None:
        """Enable both Y-axis motors."""
        self.y1_motor.enable()
        self.y2_motor.enable()
        self._enabled = True
        logger.info("Enabled Y-axis motors")
        
    def disable(self) -> None:
        """Disable both Y-axis motors."""
        self.y1_motor.disable()
        self.y2_motor.disable()
        self._enabled = False
        logger.info("Disabled Y-axis motors")
        
    def move_mm(self, direction: bool, distance: float, speed: float) -> None:
        """Move both Y-axis motors in sync.
        
        Args:
            direction: True for forward, False for reverse
            distance: Distance to move in millimeters
            speed: Movement speed in mm/s
        """
        if not self._enabled:
            raise RuntimeError("Y-axis motors are not enabled")
            
        if distance <= 0:
            raise ValueError("Distance must be positive")
            
        if speed <= 0:
            raise ValueError("Speed must be positive")
            
        # Calculate steps and delay for each motor
        y1_steps = int(distance * self.y1_motor.config.steps_per_mm)
        y2_steps = int(distance * self.y2_motor.config.steps_per_mm)
        
        # Use the slower motor's timing to ensure synchronization
        y1_step_delay = 1.0 / (speed * self.y1_motor.config.steps_per_mm)
        y2_step_delay = 1.0 / (speed * self.y2_motor.config.steps_per_mm)
        step_delay = max(y1_step_delay, y2_step_delay)
        
        # Set directions
        if not self.simulation_mode:
            GPIO.output(
                self.y1_motor.config.dir_pin,
                GPIO.HIGH if direction != self.y1_motor.config.direction_inverted
                else GPIO.LOW
            )
            GPIO.output(
                self.y2_motor.config.dir_pin,
                GPIO.HIGH if direction != self.y2_motor.config.direction_inverted
                else GPIO.LOW
            )
            
        # Move motors in sync
        for _ in range(max(y1_steps, y2_steps)):
            if not self.simulation_mode:
                # Step Y1 motor
                if _ < y1_steps:
                    GPIO.output(self.y1_motor.config.step_pin, GPIO.HIGH)
                time.sleep(step_delay / 2)
                
                # Step Y2 motor
                if _ < y2_steps:
                    GPIO.output(self.y2_motor.config.step_pin, GPIO.HIGH)
                time.sleep(step_delay / 2)
                
                # Reset step pins
                GPIO.output(self.y1_motor.config.step_pin, GPIO.LOW)
                GPIO.output(self.y2_motor.config.step_pin, GPIO.LOW)
                time.sleep(step_delay / 2)
            else:
                time.sleep(step_delay)
                
        # Update positions
        if direction:
            self.y1_motor._current_position += distance
            self.y2_motor._current_position += distance
        else:
            self.y1_motor._current_position -= distance
            self.y2_motor._current_position -= distance
            
        logger.info(
            f"Moved Y-axis "
            f"{'forward' if direction else 'reverse'} {distance}mm"
        )
        
    def get_position(self) -> float:
        """Get current Y-axis position in millimeters.
        
        Returns the average position of both motors.
        """
        return (self.y1_motor.get_position() + self.y2_motor.get_position()) / 2
        
    def set_position(self, position: float) -> None:
        """Set current Y-axis position in millimeters."""
        self.y1_motor.set_position(position)
        self.y2_motor.set_position(position)
        logger.info(f"Set Y-axis position to {position}mm")
        
    def cleanup(self) -> None:
        """Clean up GPIO resources."""
        self.y1_motor.cleanup()
        self.y2_motor.cleanup()
        logger.info("Cleaned up Y-axis resources") 