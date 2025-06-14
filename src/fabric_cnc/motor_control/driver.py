#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stepper motor driver implementation for fabric CNC machine.
Provides hardware abstraction and safety features for motor control.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional, Protocol

try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None

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
        self.enabled = False
        self._is_moving = False
        
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
        self.enabled = True
        logger.debug(f"Motor {self.config.name} enabled")

    def disable(self) -> None:
        """Disable the motor driver."""
        if not self.simulation_mode and self.gpio:
            self.gpio.output(self.config.en_pin, self.gpio.HIGH)
        self.enabled = False
        logger.debug(f"Motor {self.config.name} disabled")

    def step(
        self,
        direction: bool,
        steps: int,
        delay: float,
        step_pulse_duration: float = 0.0005
    ) -> None:
        """Step the motor a specified number of steps.
        
        Args:
            direction: True for forward, False for reverse
            steps: Number of steps to move
            delay: Delay between steps in seconds
            step_pulse_duration: Duration of step pulse in seconds
        """
        if not self.enabled:
            self.enable()

        if self._is_moving:
            logger.warning(f"Motor {self.config.name} is already moving")
            return

        self._is_moving = True
        try:
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
                    time.sleep(step_pulse_duration)
                    self.gpio.output(self.config.step_pin, self.gpio.LOW)
                time.sleep(delay)
                
                if step % 100 == 0:  # Log progress every 100 steps
                    logger.debug(
                        f"Motor {self.config.name} step {step}/{steps}"
                    )
        finally:
            self._is_moving = False

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
        steps = int(distance_mm * self.config.steps_per_mm)
        delay = 1.0 / (speed_mm_s * self.config.steps_per_mm)
        logger.info(
            f"Moving motor {self.config.name} {distance_mm}mm "
            f"at {speed_mm_s}mm/s ({steps} steps)"
        )
        self.step(direction, steps, delay)

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