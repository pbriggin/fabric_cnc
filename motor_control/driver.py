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
    """Stepper motor controller with safety features."""
    
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
        
        if not self.simulation_mode and self.gpio:
            self._setup_gpio()
        logger.info(f"Initialized motor {config.name}")

    def _setup_gpio(self) -> None:
        """Set up GPIO pins for the motor."""
        if not self.gpio:
            logger.error("GPIO module not available")
            return
            
        try:
            self.gpio.setmode(self.gpio.BCM)
            logger.info(f"Setting up {self.config.name} motor pins:")
            logger.info(f"  DIR pin: {self.config.dir_pin}")
            logger.info(f"  STEP pin: {self.config.step_pin}")
            
            self.gpio.setup(self.config.dir_pin, self.gpio.OUT)
            self.gpio.setup(self.config.step_pin, self.gpio.OUT)
            
            # Initialize pins to safe state
            self.gpio.output(self.config.dir_pin, self.gpio.LOW)
            self.gpio.output(self.config.step_pin, self.gpio.LOW)
            
            logger.info(f"Successfully set up {self.config.name} motor pins")
        except Exception as e:
            logger.error(f"Error setting up {self.config.name} motor pins: {e}")
            raise

    def step(self, direction: bool) -> None:
        """Step the motor once in the specified direction.
        
        Args:
            direction: True for forward, False for reverse
        """
        if not self.simulation_mode and self.gpio:
            try:
                # Set direction
                actual_direction = direction != self.config.direction_inverted
                self.gpio.output(
                    self.config.dir_pin,
                    self.gpio.HIGH if actual_direction else self.gpio.LOW
                )
                
                # Step pulse
                self.gpio.output(self.config.step_pin, self.gpio.HIGH)
                time.sleep(0.001)  # 1ms pulse
                self.gpio.output(self.config.step_pin, self.gpio.LOW)
                time.sleep(0.001)  # 1ms delay
                
                # Update position
                step_distance = 1.0 / self.config.steps_per_mm
                if direction:
                    self._current_position += step_distance
                else:
                    self._current_position -= step_distance
                    
            except Exception as e:
                logger.error(f"Error stepping {self.config.name} motor: {e}")
                raise
        else:
            logger.debug(f"Simulated step for {self.config.name} motor")

    def move_mm(self, direction: bool, distance_mm: float, speed_mm_s: float) -> None:
        """Move the motor by a specified distance.
        
        Args:
            direction: True for forward, False for reverse
            distance_mm: Distance to move in millimeters
            speed_mm_s: Speed in millimeters per second
        """
        if distance_mm <= 0:
            raise ValueError("Distance must be positive")
            
        if speed_mm_s <= 0:
            raise ValueError("Speed must be positive")
            
        steps = int(distance_mm * self.config.steps_per_mm)
        logger.info(
            f"Moving {self.config.name} motor "
            f"{'forward' if direction else 'reverse'} {distance_mm}mm "
            f"({steps} steps)"
        )
        
        for _ in range(steps):
            self.step(direction)
            
        logger.info(
            f"Moved {self.config.name} motor "
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
            pins = [self.config.dir_pin, self.config.step_pin]
            self.gpio.cleanup(pins)
        logger.info(f"Cleaned up {self.config.name} motor resources")

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
        
        logger.info("Initialized Y-axis controller")
        
    def step(self, direction: bool) -> None:
        """Step both motors once in sync.
        
        Args:
            direction: True for forward, False for reverse
        """
        self.y1_motor.step(direction)
        self.y2_motor.step(direction)
        
    def move_mm(self, direction: bool, distance_mm: float, speed_mm_s: float) -> None:
        """Move both motors by a specified distance.
        
        Args:
            direction: True for forward, False for reverse
            distance_mm: Distance to move in millimeters
            speed_mm_s: Speed in millimeters per second
        """
        if distance_mm <= 0:
            raise ValueError("Distance must be positive")
            
        if speed_mm_s <= 0:
            raise ValueError("Speed must be positive")
            
        steps = int(distance_mm * self.y1_motor.config.steps_per_mm)
        logger.info(
            f"Moving Y-axis "
            f"{'forward' if direction else 'reverse'} {distance_mm}mm "
            f"({steps} steps)"
        )
        
        for _ in range(steps):
            self.step(direction)
            
        logger.info(
            f"Moved Y-axis "
            f"{'forward' if direction else 'reverse'} {distance_mm}mm"
        )
        
    def get_position(self) -> float:
        """Get current Y-axis position in millimeters."""
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