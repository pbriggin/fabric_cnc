#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-axis controller for Fabric CNC machine.
Coordinates individual stepper drivers for coordinated movement.
"""

import logging
import math
import time
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable, Tuple
from enum import Enum

from config_manager import config_manager
from .stepper_driver import StepperDriver, Direction, MotorState, MotorStatus

logger = logging.getLogger(__name__)

class MovementType(Enum):
    """Type of movement."""
    LINEAR = "linear"
    ARC = "arc"
    RAPID = "rapid"

@dataclass
class Position:
    """Machine position in all axes."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    a: float = 0.0

@dataclass
class MovementCommand:
    """Movement command for coordinated motion."""
    target_position: Position
    speed: float
    movement_type: MovementType
    acceleration: Optional[float] = None

class MultiAxisController:
    """Multi-axis controller for coordinated movement."""
    
    def __init__(self, simulation_mode: bool = False):
        """Initialize multi-axis controller.
        
        Args:
            simulation_mode: If True, no actual GPIO operations
        """
        self.simulation_mode = simulation_mode
        
        # Initialize individual axis drivers
        self.axes: Dict[str, StepperDriver] = {}
        self._setup_axes()
        
        # Current machine position
        self.current_position = Position()
        
        # Movement control
        self._stop_requested = False
        self._movement_thread = None
        self._lock = threading.Lock()
        
        # Status tracking
        self.is_moving = False
        self.last_error = None
        
        logger.info("Multi-axis controller initialized")
    
    def _setup_axes(self) -> None:
        """Set up individual axis drivers."""
        for axis_name in config_manager.get_axis_names():
            axis_config = config_manager.get_axis_config(axis_name)
            self.axes[axis_name] = StepperDriver(
                axis_name=axis_name,
                axis_config=axis_config,
                simulation_mode=self.simulation_mode
            )
        logger.info(f"Set up {len(self.axes)} axes: {list(self.axes.keys())}")
    
    def enable_all(self) -> None:
        """Enable all motors."""
        for axis_name, driver in self.axes.items():
            driver.enable()
        logger.info("All motors enabled")
    
    def disable_all(self) -> None:
        """Disable all motors."""
        for axis_name, driver in self.axes.items():
            driver.disable()
        logger.info("All motors disabled")
    
    def get_status(self) -> Dict[str, MotorStatus]:
        """Get status of all axes."""
        return {name: driver.get_status() for name, driver in self.axes.items()}
    
    def get_position(self) -> Position:
        """Get current machine position."""
        with self._lock:
            return Position(
                x=self.axes['X'].get_position(),
                y=self.axes['Y1'].get_position(),  # Use Y1 as primary Y position
                z=self.axes['Z'].get_position(),
                a=self.axes['A'].get_position()
            )
    
    def set_position(self, position: Position) -> None:
        """Set current machine position."""
        with self._lock:
            self.axes['X'].set_position(position.x)
            self.axes['Y1'].set_position(position.y)
            self.axes['Y2'].set_position(position.y)  # Sync Y2 with Y1
            self.axes['Z'].set_position(position.z)
            self.axes['A'].set_position(position.a)
            self.current_position = position
        logger.info(f"Machine position set to {position}")
    
    def move_to_position(
        self,
        target_position: Position,
        speed: float,
        movement_type: MovementType = MovementType.LINEAR,
        callback: Optional[Callable[[str, float], None]] = None
    ) -> None:
        """Move to target position with coordinated motion.
        
        Args:
            target_position: Target position
            speed: Speed in mm/s
            movement_type: Type of movement
            callback: Optional callback function(status, progress)
        """
        if self._movement_thread and self._movement_thread.is_alive():
            logger.warning("Machine already moving")
            return
        
        self._stop_requested = False
        self._movement_thread = threading.Thread(
            target=self._move_to_position_thread,
            args=(target_position, speed, movement_type, callback)
        )
        self._movement_thread.start()
    
    def _move_to_position_thread(
        self,
        target_position: Position,
        speed: float,
        movement_type: MovementType,
        callback: Optional[Callable[[str, float], None]]
    ) -> None:
        """Thread function for coordinated movement."""
        try:
            self.is_moving = True
            
            if callback:
                callback("starting", 0.0)
            
            # Calculate movement parameters
            current_pos = self.get_position()
            distances = {
                'X': target_position.x - current_pos.x,
                'Y': target_position.y - current_pos.y,
                'Z': target_position.z - current_pos.z,
                'A': target_position.a - current_pos.a
            }
            
            # Find the longest distance for timing
            max_distance = max(abs(d) for d in distances.values())
            if max_distance < 0.001:  # Already at target
                self.is_moving = False
                if callback:
                    callback("complete", 1.0)
                return
            
            # Calculate individual axis speeds
            axis_speeds = {}
            for axis, distance in distances.items():
                if abs(distance) > 0.001:
                    # Scale speed based on distance ratio
                    axis_speeds[axis] = speed * (abs(distance) / max_distance)
                else:
                    axis_speeds[axis] = 0
            
            # Execute movement
            if movement_type == MovementType.LINEAR:
                self._execute_linear_movement(target_position, axis_speeds, callback)
            elif movement_type == MovementType.RAPID:
                self._execute_rapid_movement(target_position, axis_speeds, callback)
            else:
                raise ValueError(f"Unsupported movement type: {movement_type}")
            
            self.is_moving = False
            if callback:
                callback("complete", 1.0)
                
        except Exception as e:
            logger.error(f"Movement error: {e}")
            self.last_error = str(e)
            self.is_moving = False
            if callback:
                callback("error", 0.0)
    
    def _execute_linear_movement(
        self,
        target_position: Position,
        axis_speeds: Dict[str, float],
        callback: Optional[Callable[[str, float], None]]
    ) -> None:
        """Execute linear movement with coordinated timing."""
        # Calculate total steps needed for each axis
        axis_steps = {}
        for axis_name, speed in axis_speeds.items():
            if speed > 0:
                driver = self.axes[axis_name]
                current_pos = driver.get_position()
                target_pos = getattr(target_position, axis_name.lower())
                distance = abs(target_pos - current_pos)
                
                if driver.config.steps_per_deg:
                    total_steps = int(distance * driver.config.steps_per_deg)
                else:
                    total_steps = int(distance * driver.config.steps_per_mm)
                
                axis_steps[axis_name] = total_steps
        
        # Find the axis with the most steps
        max_steps = max(axis_steps.values()) if axis_steps else 1
        
        # Execute coordinated movement
        for step in range(max_steps):
            if self._stop_requested:
                break
            
            # Move each axis proportionally
            for axis_name, total_steps in axis_steps.items():
                if step < total_steps:
                    driver = self.axes[axis_name]
                    current_pos = driver.get_position()
                    target_pos = getattr(target_position, axis_name.lower())
                    direction = Direction.FORWARD if target_pos > current_pos else Direction.REVERSE
                    
                    driver.step(direction, 1, 0.001)  # Small delay for coordination
            
            # Report progress
            if callback and max_steps > 0:
                progress = step / max_steps
                callback("moving", progress)
    
    def _execute_rapid_movement(
        self,
        target_position: Position,
        axis_speeds: Dict[str, float],
        callback: Optional[Callable[[str, float], None]]
    ) -> None:
        """Execute rapid movement (each axis moves independently at max speed)."""
        # Start all movements simultaneously
        movement_threads = []
        
        for axis_name, speed in axis_speeds.items():
            if speed > 0:
                driver = self.axes[axis_name]
                target_pos = getattr(target_position, axis_name.lower())
                
                thread = threading.Thread(
                    target=driver.move_to_position,
                    args=(target_pos, speed)
                )
                thread.start()
                movement_threads.append(thread)
        
        # Wait for all movements to complete
        for thread in movement_threads:
            thread.join()
    
    def stop(self) -> None:
        """Stop all movement."""
        self._stop_requested = True
        for driver in self.axes.values():
            driver.stop()
        
        if self._movement_thread and self._movement_thread.is_alive():
            self._movement_thread.join(timeout=1.0)
        
        self.is_moving = False
        logger.info("All movement stopped")
    
    def home_all(
        self,
        callback: Optional[Callable[[str, float], None]] = None
    ) -> None:
        """Home all axes.
        
        Args:
            callback: Optional callback function(status, progress)
        """
        if self._movement_thread and self._movement_thread.is_alive():
            logger.warning("Machine already moving")
            return
        
        self._stop_requested = False
        self._movement_thread = threading.Thread(
            target=self._home_all_thread,
            args=(callback,)
        )
        self._movement_thread.start()
    
    def _home_all_thread(
        self,
        callback: Optional[Callable[[str, float], None]]
    ) -> None:
        """Thread function for homing all axes."""
        try:
            if callback:
                callback("homing", 0.0)
            
            # Get homing speeds from config
            homing_speeds = config_manager.machine_config.homing.speeds
            
            # Home each axis
            total_axes = len(self.axes)
            for i, (axis_name, driver) in enumerate(self.axes.items()):
                if self._stop_requested:
                    break
                
                speed = homing_speeds.get(axis_name, 10.0)
                
                # Home the axis
                driver.home(speed)
                
                # Report progress
                if callback:
                    progress = (i + 1) / total_axes
                    callback("homing", progress)
            
            # Set all positions to zero
            self.set_position(Position())
            
            if callback:
                callback("complete", 1.0)
                
        except Exception as e:
            logger.error(f"Homing error: {e}")
            self.last_error = str(e)
            if callback:
                callback("error", 0.0)
    
    def home_axis(
        self,
        axis_name: str,
        callback: Optional[Callable[[str, float], None]] = None
    ) -> None:
        """Home a specific axis.
        
        Args:
            axis_name: Name of the axis to home
            callback: Optional callback function(status, progress)
        """
        if axis_name not in self.axes:
            raise ValueError(f"Unknown axis: {axis_name}")
        
        driver = self.axes[axis_name]
        homing_speeds = config_manager.machine_config.homing.speeds
        speed = homing_speeds.get(axis_name, 10.0)
        
        driver.home(speed, callback)
    
    def read_hall_sensors(self) -> Dict[str, bool]:
        """Read all hall sensors."""
        return {name: driver.read_hall_sensor() for name, driver in self.axes.items()}
    
    def validate_position(self, position: Position) -> bool:
        """Validate if a position is within machine limits."""
        try:
            return (
                config_manager.validate_position('X', position.x) and
                config_manager.validate_position('Y', position.y) and
                config_manager.validate_position('Z', position.z) and
                config_manager.validate_position('A', position.a)
            )
        except ValueError:
            return False
    
    def get_work_area(self) -> Dict[str, float]:
        """Get work area dimensions."""
        return config_manager.get_work_area()
    
    def cleanup(self) -> None:
        """Clean up all resources."""
        self.stop()
        for driver in self.axes.values():
            driver.cleanup()
        logger.info("Multi-axis controller cleaned up") 