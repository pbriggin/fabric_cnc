#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Motion planner for Fabric CNC machine.
Integrates with the redesigned motor control system for smooth toolpath execution.
"""

import logging
import math
import time
import threading
from dataclasses import dataclass
from typing import List, Optional, Callable, Tuple, Dict, Any
from enum import Enum

from config_manager import config_manager
from motor_control import MultiAxisController, Position, MovementType

logger = logging.getLogger(__name__)

class ToolpathType(Enum):
    """Type of toolpath."""
    LINE = "line"
    ARC = "arc"
    SPLINE = "spline"
    CIRCLE = "circle"

@dataclass
class ToolpathPoint:
    """A point in a toolpath."""
    x: float
    y: float
    z: float
    a: float
    feed_rate: float
    tool_down: bool = False

@dataclass
class ToolpathSegment:
    """A segment of a toolpath."""
    start_point: ToolpathPoint
    end_point: ToolpathPoint
    segment_type: ToolpathType
    parameters: Dict[str, Any] = None

class MotionPlanner:
    """Motion planner for smooth toolpath execution."""
    
    def __init__(self, controller: MultiAxisController):
        """Initialize motion planner.
        
        Args:
            controller: Multi-axis controller instance
        """
        self.controller = controller
        self.planner_config = config_manager.machine_config.planner
        
        # Execution state
        self.is_executing = False
        self.current_toolpath = None
        self.execution_thread = None
        self._stop_requested = False
        
        # Callbacks
        self.progress_callback = None
        self.status_callback = None
        
        logger.info("Motion planner initialized")
    
    def execute_toolpath(
        self,
        toolpath: List[ToolpathPoint],
        progress_callback: Optional[Callable[[float], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None
    ) -> None:
        """Execute a toolpath.
        
        Args:
            toolpath: List of toolpath points
            progress_callback: Optional callback for progress updates
            status_callback: Optional callback for status updates
        """
        if self.is_executing:
            logger.warning("Already executing toolpath")
            return
        
        self.current_toolpath = toolpath
        self.progress_callback = progress_callback
        self.status_callback = status_callback
        self._stop_requested = False
        
        self.execution_thread = threading.Thread(
            target=self._execute_toolpath_thread
        )
        self.execution_thread.start()
    
    def _execute_toolpath_thread(self) -> None:
        """Thread function for toolpath execution."""
        try:
            self.is_executing = True
            
            if self.status_callback:
                self.status_callback("Starting toolpath execution")
            
            # Validate toolpath
            if not self._validate_toolpath():
                raise ValueError("Invalid toolpath")
            
            # Execute each point
            total_points = len(self.current_toolpath)
            for i, point in enumerate(self.current_toolpath):
                if self._stop_requested:
                    break
                
                # Move to point
                target_position = Position(
                    x=point.x,
                    y=point.y,
                    z=point.z,
                    a=point.a
                )
                
                # Validate position
                if not self.controller.validate_position(target_position):
                    raise ValueError(f"Position {target_position} out of bounds")
                
                # Execute movement
                self._move_to_point(target_position, point.feed_rate)
                
                # Handle tool state
                if point.tool_down:
                    self._tool_down()
                else:
                    self._tool_up()
                
                # Report progress
                if self.progress_callback:
                    progress = (i + 1) / total_points
                    self.progress_callback(progress)
                
                if self.status_callback:
                    self.status_callback(f"Executing point {i + 1}/{total_points}")
            
            if self._stop_requested:
                if self.status_callback:
                    self.status_callback("Toolpath execution stopped")
            else:
                if self.status_callback:
                    self.status_callback("Toolpath execution completed")
                
        except Exception as e:
            logger.error(f"Toolpath execution error: {e}")
            if self.status_callback:
                self.status_callback(f"Error: {str(e)}")
        finally:
            self.is_executing = False
    
    def _validate_toolpath(self) -> bool:
        """Validate the current toolpath."""
        if not self.current_toolpath:
            return False
        
        for point in self.current_toolpath:
            position = Position(x=point.x, y=point.y, z=point.z, a=point.a)
            if not self.controller.validate_position(position):
                logger.error(f"Invalid position in toolpath: {position}")
                return False
        
        return True
    
    def _move_to_point(self, position: Position, feed_rate: float) -> None:
        """Move to a specific point."""
        # Use linear movement for toolpath execution
        self.controller.move_to_position(
            target_position=position,
            speed=feed_rate,
            movement_type=MovementType.LINEAR
        )
        
        # Wait for movement to complete
        while self.controller.is_moving:
            time.sleep(0.01)
    
    def _tool_down(self) -> None:
        """Lower the tool."""
        current_pos = self.controller.get_position()
        target_pos = Position(
            x=current_pos.x,
            y=current_pos.y,
            z=current_pos.z - config_manager.machine_config.motion.lift_height,
            a=current_pos.a
        )
        
        self.controller.move_to_position(
            target_position=target_pos,
            speed=config_manager.machine_config.motion.default_speed,
            movement_type=MovementType.LINEAR
        )
        
        while self.controller.is_moving:
            time.sleep(0.01)
    
    def _tool_up(self) -> None:
        """Raise the tool."""
        current_pos = self.controller.get_position()
        target_pos = Position(
            x=current_pos.x,
            y=current_pos.y,
            z=current_pos.z + config_manager.machine_config.motion.lift_height,
            a=current_pos.a
        )
        
        self.controller.move_to_position(
            target_position=target_pos,
            speed=config_manager.machine_config.motion.default_speed,
            movement_type=MovementType.LINEAR
        )
        
        while self.controller.is_moving:
            time.sleep(0.01)
    
    def stop_execution(self) -> None:
        """Stop toolpath execution."""
        self._stop_requested = True
        self.controller.stop()
        
        if self.execution_thread and self.execution_thread.is_alive():
            self.execution_thread.join(timeout=1.0)
        
        self.is_executing = False
        logger.info("Toolpath execution stopped")
    
    def is_executing_toolpath(self) -> bool:
        """Check if currently executing a toolpath."""
        return self.is_executing
    
    def get_execution_status(self) -> Dict[str, Any]:
        """Get current execution status."""
        return {
            'is_executing': self.is_executing,
            'stop_requested': self._stop_requested,
            'current_position': self.controller.get_position(),
            'machine_status': self.controller.get_status()
        }

class ToolpathOptimizer:
    """Optimizes toolpaths for smooth execution."""
    
    def __init__(self):
        """Initialize toolpath optimizer."""
        self.planner_config = config_manager.machine_config.planner
    
    def optimize_toolpath(self, toolpath: List[ToolpathPoint]) -> List[ToolpathPoint]:
        """Optimize a toolpath for smooth execution.
        
        Args:
            toolpath: Original toolpath
            
        Returns:
            Optimized toolpath
        """
        if not toolpath:
            return toolpath
        
        optimized = []
        
        for i, point in enumerate(toolpath):
            if i == 0:
                # First point - add as is
                optimized.append(point)
                continue
            
            # Check if we need to add intermediate points for smooth motion
            prev_point = toolpath[i - 1]
            
            # Calculate distance between points
            distance = math.sqrt(
                (point.x - prev_point.x) ** 2 +
                (point.y - prev_point.y) ** 2 +
                (point.z - prev_point.z) ** 2
            )
            
            # If distance is large, add intermediate points
            if distance > self.planner_config.segment_tolerance:
                intermediate_points = self._generate_intermediate_points(
                    prev_point, point
                )
                optimized.extend(intermediate_points)
            else:
                optimized.append(point)
        
        return optimized
    
    def _generate_intermediate_points(
        self,
        start_point: ToolpathPoint,
        end_point: ToolpathPoint
    ) -> List[ToolpathPoint]:
        """Generate intermediate points for smooth motion."""
        points = []
        
        # Calculate number of intermediate points needed
        distance = math.sqrt(
            (end_point.x - start_point.x) ** 2 +
            (end_point.y - start_point.y) ** 2 +
            (end_point.z - start_point.z) ** 2
        )
        
        num_segments = max(1, int(distance / self.planner_config.segment_tolerance))
        
        for i in range(1, num_segments + 1):
            t = i / (num_segments + 1)
            
            # Linear interpolation
            x = start_point.x + t * (end_point.x - start_point.x)
            y = start_point.y + t * (end_point.y - start_point.y)
            z = start_point.z + t * (end_point.z - start_point.z)
            a = start_point.a + t * (end_point.a - start_point.a)
            
            # Interpolate feed rate
            feed_rate = start_point.feed_rate + t * (end_point.feed_rate - start_point.feed_rate)
            
            # Keep tool state from start point for intermediate points
            tool_down = start_point.tool_down
            
            point = ToolpathPoint(
                x=x, y=y, z=z, a=a,
                feed_rate=feed_rate,
                tool_down=tool_down
            )
            points.append(point)
        
        return points 