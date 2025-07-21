#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stepper motor driver for Fabric CNC using stepperpi approach.
Provides individual axis control with TB6600 driver compatibility.
"""

import logging
import math
import time
import threading
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any
from enum import Enum

try:
    import pigpio
except ImportError:
    pigpio = None

from config_manager import config_manager, AxisConfig

logger = logging.getLogger(__name__)

class Direction(Enum):
    """Motor direction enumeration."""
    FORWARD = 1
    REVERSE = -1

class MotorState(Enum):
    """Motor state enumeration."""
    IDLE = "idle"
    MOVING = "moving"
    HOMING = "homing"
    ERROR = "error"

@dataclass
class MotorStatus:
    """Status information for a motor."""
    position: float
    state: MotorState
    enabled: bool
    last_error: Optional[str] = None

class StepperDriver:
    """Individual stepper motor driver with TB6600 compatibility."""
    
    def __init__(
        self,
        axis_name: str,
        axis_config: AxisConfig,
        simulation_mode: bool = False
    ):
        """Initialize stepper driver.
        
        Args:
            axis_name: Name of the axis (X, Y1, Y2, Z, A)
            axis_config: Configuration for this axis
            simulation_mode: If True, no actual GPIO operations
        """
        self.axis_name = axis_name
        self.config = axis_config
        self.simulation_mode = simulation_mode
        
        # Motor state
        self.position = 0.0  # Current position in mm or degrees
        self.state = MotorState.IDLE
        self.enabled = False
        self.last_error = None
        
        # GPIO interface
        self.pi = None
        self._setup_gpio()
        
        # Movement control
        self._stop_requested = False
        self._movement_thread = None
        self._lock = threading.Lock()
        
        logger.info(f"Initialized {axis_name} stepper driver")
    
    def _setup_gpio(self) -> None:
        """Set up GPIO pins for the motor."""
        if self.simulation_mode:
            logger.info(f"Simulation mode: {self.axis_name} GPIO setup skipped")
            return
        
        if pigpio is None:
            logger.error("pigpio not available")
            self.last_error = "pigpio not available"
            return
        
        try:
            self.pi = pigpio.pi()
            if not self.pi.connected:
                raise RuntimeError("Failed to connect to pigpio daemon")
            
            # Set up pins
            self.pi.set_mode(self.config.step_pin, pigpio.OUTPUT)
            self.pi.set_mode(self.config.dir_pin, pigpio.OUTPUT)
            self.pi.set_mode(self.config.ena_pin, pigpio.OUTPUT)
            
            # Set up hall sensor pin
            self.pi.set_mode(self.config.hall_pin, pigpio.INPUT)
            self.pi.set_pull_up_down(self.config.hall_pin, pigpio.PUD_UP)
            
            # Initialize to safe state
            self.pi.write(self.config.step_pin, 0)
            self.pi.write(self.config.dir_pin, 0)
            self.pi.write(self.config.ena_pin, 0)  # Enable motor (LOW = enabled)
            
            logger.info(f"GPIO setup complete for {self.axis_name}")
            
        except Exception as e:
            logger.error(f"GPIO setup failed for {self.axis_name}: {e}")
            self.last_error = str(e)
            raise
    
    def enable(self) -> None:
        """Enable the motor."""
        with self._lock:
            if not self.simulation_mode and self.pi:
                self.pi.write(self.config.ena_pin, 0)  # LOW = enabled
            self.enabled = True
            logger.info(f"{self.axis_name} motor enabled")
    
    def disable(self) -> None:
        """Disable the motor."""
        with self._lock:
            if not self.simulation_mode and self.pi:
                self.pi.write(self.config.ena_pin, 1)  # HIGH = disabled
            self.enabled = False
            logger.info(f"{self.axis_name} motor disabled")
    
    def is_enabled(self) -> bool:
        """Check if motor is enabled."""
        return self.enabled
    
    def get_status(self) -> MotorStatus:
        """Get current motor status."""
        return MotorStatus(
            position=self.position,
            state=self.state,
            enabled=self.enabled,
            last_error=self.last_error
        )
    
    def set_position(self, position: float) -> None:
        """Set the current position (for homing)."""
        with self._lock:
            self.position = position
            logger.info(f"{self.axis_name} position set to {position}")
    
    def get_position(self) -> float:
        """Get current position."""
        return self.position
    
    def step(self, direction: Direction, steps: int = 1, delay: float = 0.001) -> None:
        """Execute a single step or multiple steps.
        
        Args:
            direction: Direction to step
            steps: Number of steps to execute
            delay: Delay between steps in seconds
        """
        if not self.enabled:
            logger.warning(f"{self.axis_name} motor not enabled")
            return
        
        if self.simulation_mode:
            # Update position in simulation
            step_distance = 1.0 / self.config.steps_per_mm
            if self.config.steps_per_deg:
                step_distance = 1.0 / self.config.steps_per_deg
            
            self.position += direction.value * steps * step_distance
            return
        
        if not self.pi:
            logger.error(f"{self.axis_name} GPIO not available")
            return
        
        try:
            # Set direction
            actual_direction = direction.value
            if self.config.invert_dir:
                actual_direction = -actual_direction
            
            self.pi.write(self.config.dir_pin, 1 if actual_direction > 0 else 0)
            
            # Execute steps
            for _ in range(steps):
                self.pi.write(self.config.step_pin, 1)
                time.sleep(delay / 2)
                self.pi.write(self.config.step_pin, 0)
                time.sleep(delay / 2)
                
                # Update position
                step_distance = 1.0 / self.config.steps_per_mm
                if self.config.steps_per_deg:
                    step_distance = 1.0 / self.config.steps_per_deg
                
                self.position += direction.value * step_distance
                
        except Exception as e:
            logger.error(f"Step error for {self.axis_name}: {e}")
            self.last_error = str(e)
            self.state = MotorState.ERROR
    
    def move_to_position(
        self,
        target_position: float,
        speed: float,
        callback: Optional[Callable[[str, float], None]] = None
    ) -> None:
        """Move to a target position.
        
        Args:
            target_position: Target position in mm or degrees
            speed: Speed in mm/s or deg/s
            callback: Optional callback function(status, progress)
        """
        if self._movement_thread and self._movement_thread.is_alive():
            logger.warning(f"{self.axis_name} already moving")
            return
        
        self._stop_requested = False
        self._movement_thread = threading.Thread(
            target=self._move_to_position_thread,
            args=(target_position, speed, callback)
        )
        self._movement_thread.start()
    
    def _move_to_position_thread(
        self,
        target_position: float,
        speed: float,
        callback: Optional[Callable[[str, float], None]]
    ) -> None:
        """Thread function for position movement."""
        try:
            self.state = MotorState.MOVING
            
            # Calculate distance and direction
            distance = target_position - self.position
            if abs(distance) < 0.001:  # Already at target
                self.state = MotorState.IDLE
                if callback:
                    callback("complete", 1.0)
                return
            
            direction = Direction.FORWARD if distance > 0 else Direction.REVERSE
            total_distance = abs(distance)
            
            # Calculate step delay based on speed
            if self.config.steps_per_deg:
                # Angular movement
                steps_per_second = speed * self.config.steps_per_deg
            else:
                # Linear movement
                steps_per_second = speed * self.config.steps_per_mm
            
            step_delay = 1.0 / steps_per_second if steps_per_second > 0 else 0.001
            
            # Execute movement
            steps_executed = 0
            total_steps = int(total_distance * (self.config.steps_per_mm or self.config.steps_per_deg))
            
            while steps_executed < total_steps and not self._stop_requested:
                self.step(direction, 1, step_delay)
                steps_executed += 1
                
                # Report progress
                if callback and total_steps > 0:
                    progress = steps_executed / total_steps
                    callback("moving", progress)
            
            if self._stop_requested:
                self.state = MotorState.IDLE
                if callback:
                    callback("stopped", steps_executed / total_steps)
            else:
                self.state = MotorState.IDLE
                if callback:
                    callback("complete", 1.0)
                    
        except Exception as e:
            logger.error(f"Movement error for {self.axis_name}: {e}")
            self.last_error = str(e)
            self.state = MotorState.ERROR
            if callback:
                callback("error", 0.0)
    
    def stop(self) -> None:
        """Stop current movement."""
        self._stop_requested = True
        if self._movement_thread and self._movement_thread.is_alive():
            self._movement_thread.join(timeout=1.0)
        self.state = MotorState.IDLE
        logger.info(f"{self.axis_name} movement stopped")
    
    def is_moving(self) -> bool:
        """Check if motor is currently moving."""
        return self.state == MotorState.MOVING
    
    def read_hall_sensor(self) -> bool:
        """Read hall sensor state."""
        if self.simulation_mode:
            return False  # Simulated sensors always return False
        
        if not self.pi:
            return False
        
        try:
            return self.pi.read(self.config.hall_pin) == 0  # Active low
        except Exception as e:
            logger.error(f"Hall sensor read error for {self.axis_name}: {e}")
            return False
    
    def home(
        self,
        speed: float,
        callback: Optional[Callable[[str, float], None]] = None
    ) -> None:
        """Home the axis.
        
        Args:
            speed: Homing speed in mm/s or deg/s
            callback: Optional callback function(status, progress)
        """
        if self._movement_thread and self._movement_thread.is_alive():
            logger.warning(f"{self.axis_name} already moving")
            return
        
        self._stop_requested = False
        self._movement_thread = threading.Thread(
            target=self._home_thread,
            args=(speed, callback)
        )
        self._movement_thread.start()
    
    def _home_thread(
        self,
        speed: float,
        callback: Optional[Callable[[str, float], None]]
    ) -> None:
        """Thread function for homing."""
        try:
            self.state = MotorState.HOMING
            
            if callback:
                callback("homing", 0.0)
            
            # Move until hall sensor is triggered
            homing_direction = Direction.REVERSE  # Default homing direction
            step_delay = 1.0 / (speed * (self.config.steps_per_mm or self.config.steps_per_deg))
            
            while not self.read_hall_sensor() and not self._stop_requested:
                self.step(homing_direction, 1, step_delay)
                if callback:
                    callback("homing", 0.5)
            
            if self._stop_requested:
                self.state = MotorState.IDLE
                if callback:
                    callback("stopped", 0.0)
                return
            
            # Move offset distance
            offset = config_manager.machine_config.homing.offset
            if self.config.steps_per_deg:
                offset_steps = int(offset * self.config.steps_per_deg)
            else:
                offset_steps = int(offset * self.config.steps_per_mm)
            
            for _ in range(offset_steps):
                if self._stop_requested:
                    break
                self.step(Direction.FORWARD, 1, step_delay)
                if callback:
                    callback("homing", 0.5 + 0.5 * (_ / offset_steps))
            
            # Set position to zero
            self.position = 0.0
            
            self.state = MotorState.IDLE
            if callback:
                callback("complete", 1.0)
                
        except Exception as e:
            logger.error(f"Homing error for {self.axis_name}: {e}")
            self.last_error = str(e)
            self.state = MotorState.ERROR
            if callback:
                callback("error", 0.0)
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop()
        if not self.simulation_mode and self.pi:
            self.pi.stop()
        logger.info(f"{self.axis_name} driver cleaned up") 