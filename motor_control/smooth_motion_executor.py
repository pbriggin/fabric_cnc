#!/usr/bin/env python3
"""
Smooth Motion Executor for Fabric CNC

This module provides smooth motion execution similar to 3D printers,
only stopping at genuine corners rather than at every GCODE line.
"""

import math
import time
import logging
import threading
from typing import List, Tuple, Dict, Optional, Callable
from .motor_controller import MotorController

logger = logging.getLogger(__name__)

class SmoothMotionExecutor:
    """
    Executes toolpaths with smooth motion, only stopping at genuine corners.
    """
    
    def __init__(self, motor_controller: MotorController):
        """
        Initialize the smooth motion executor.
        
        Args:
            motor_controller: The motor controller instance
        """
        self.motor_controller = motor_controller
        self.is_executing = False
        self.stop_requested = False
        self.current_position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'ROT': 0.0}
        
    def execute_toolpath_from_gcode(self, gcode_lines: List[str], progress_callback: Optional[Callable] = None):
        """
        Execute a toolpath from GCODE lines with smooth motion.
        
        Args:
            gcode_lines: List of GCODE lines
            progress_callback: Optional callback for progress updates
        """
        try:
            self.is_executing = True
            self.stop_requested = False
            
            # Parse GCODE into motion segments
            motion_segments = self._parse_gcode_to_segments(gcode_lines)
            
            logger.info(f"Parsed {len(motion_segments)} motion segments from GCODE")
            
            # Execute motion segments
            self._execute_motion_segments(motion_segments, progress_callback)
            
        except Exception as e:
            logger.error(f"Error during smooth motion execution: {e}")
            raise
        finally:
            self.is_executing = False
    
    def _parse_gcode_to_segments(self, gcode_lines: List[str]) -> List[Dict]:
        """
        Parse GCODE lines into motion segments.
        
        Args:
            gcode_lines: List of GCODE lines
            
        Returns:
            List of motion segment dictionaries
        """
        segments = []
        current_segment = None
        
        for line_num, line in enumerate(gcode_lines):
            if self.stop_requested:
                break
                
            line = line.strip()
            if not line or line.startswith(';'):
                continue
            
            # Parse GCODE line
            parsed = self._parse_gcode_line(line)
            if not parsed:
                continue
            
            command, params = parsed
            
            # Handle different command types
            if command == 'G0':  # Rapid positioning (potential corner)
                if current_segment:
                    segments.append(current_segment)
                
                # Start new segment
                current_segment = {
                    'type': 'rapid',
                    'start_pos': self.current_position.copy(),
                    'target_pos': self._calculate_target_position(params),
                    'is_corner': True,  # G0 moves are always corners
                    'line_number': line_num + 1
                }
                
            elif command == 'G1':  # Linear interpolation (smooth motion)
                if current_segment and current_segment['type'] == 'linear':
                    # Continue current linear segment
                    current_segment['target_pos'] = self._calculate_target_position(params)
                else:
                    # Start new linear segment
                    if current_segment:
                        segments.append(current_segment)
                    
                    current_segment = {
                        'type': 'linear',
                        'start_pos': self.current_position.copy(),
                        'target_pos': self._calculate_target_position(params),
                        'is_corner': False,  # G1 moves are smooth
                        'line_number': line_num + 1
                    }
            
            elif command == 'G28':  # Home
                if current_segment:
                    segments.append(current_segment)
                segments.append({
                    'type': 'home',
                    'start_pos': self.current_position.copy(),
                    'target_pos': {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'ROT': 0.0},
                    'is_corner': True,
                    'line_number': line_num + 1
                })
                current_segment = None
            
            # Update current position
            if current_segment:
                self.current_position = current_segment['target_pos'].copy()
        
        # Add final segment if exists
        if current_segment:
            segments.append(current_segment)
        
        return segments
    
    def _parse_gcode_line(self, line: str) -> Optional[Tuple[str, Dict[str, float]]]:
        """
        Parse a single GCODE line.
        
        Args:
            line: GCODE line to parse
            
        Returns:
            Tuple of (command, parameters) or None if invalid
        """
        import re
        
        # Remove comments
        line = line.split(';')[0].strip()
        if not line:
            return None
        
        # Parse command
        cmd_match = re.match(r'^([GM]\d+)(.*)$', line.upper())
        if not cmd_match:
            return None
        
        command = cmd_match.group(1)
        params = cmd_match.group(2)
        
        # Parse parameters
        params_dict = {}
        for param_match in re.finditer(r'([XYZAF])([+-]?\d*\.?\d*)', params):
            axis = param_match.group(1)
            value = float(param_match.group(2)) if param_match.group(2) else 0.0
            params_dict[axis] = value
        
        return command, params_dict
    
    def _calculate_target_position(self, params: Dict[str, float]) -> Dict[str, float]:
        """
        Calculate target position from parameters.
        
        Args:
            params: GCODE parameters
            
        Returns:
            Target position dictionary
        """
        target_pos = self.current_position.copy()
        
        for axis, value in params.items():
            if axis == 'F':  # Feed rate - ignore for position calculation
                continue
            elif axis == 'A':  # Map GCODE 'A' to internal 'ROT'
                target_pos['ROT'] = value
            else:
                target_pos[axis] = value
        
        return target_pos
    
    def _execute_motion_segments(self, segments: List[Dict], progress_callback: Optional[Callable] = None):
        """
        Execute motion segments with smooth motion.
        
        Args:
            segments: List of motion segments
            progress_callback: Optional callback for progress updates
        """
        total_segments = len(segments)
        
        for i, segment in enumerate(segments):
            if self.stop_requested:
                logger.info("Smooth motion execution stopped by user")
                break
            
            try:
                logger.info(f"Executing segment {i+1}/{total_segments}: {segment['type']} at line {segment['line_number']}")
                
                if segment['type'] == 'home':
                    self._execute_home_segment(segment)
                elif segment['type'] == 'rapid':
                    self._execute_rapid_segment(segment)
                elif segment['type'] == 'linear':
                    self._execute_linear_segment(segment)
                
                # Update progress
                if progress_callback:
                    progress = ((i + 1) / total_segments) * 100
                    progress_callback(progress, f"Segment {i+1}/{total_segments}")
                
            except Exception as e:
                logger.error(f"Error executing segment {i+1}: {e}")
                raise
    
    def _execute_home_segment(self, segment: Dict):
        """Execute a home segment."""
        logger.info("Executing home command")
        self.motor_controller.home_all_synchronous()
        
        # Sync position tracking after homing - get actual motor controller position
        if hasattr(self.motor_controller, 'get_position'):
            actual_pos = self.motor_controller.get_position()
            self.current_position = actual_pos.copy()
            logger.info(f"Position synced after homing: {self.current_position}")
        else:
            self.current_position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'ROT': 0.0}
            logger.info(f"Position reset to home: {self.current_position}")
    
    def _execute_rapid_segment(self, segment: Dict):
        """Execute a rapid positioning segment (corner)."""
        start_pos = segment['start_pos']
        target_pos = segment['target_pos']
        
        logger.info(f"RAPID: ({self.current_position['X']:.1f},{self.current_position['Y']:.1f},{self.current_position['Z']:.1f},{self.current_position['ROT']:.1f}) -> ({target_pos['X']:.1f},{target_pos['Y']:.1f},{target_pos['Z']:.1f},{target_pos['ROT']:.1f})")
        
        # Execute rapid movement to corner
        self.motor_controller.move_to(
            x=target_pos['X'],
            y=target_pos['Y'], 
            z=target_pos['Z'],
            rot=target_pos['ROT']
        )
        
        # Sync with actual motor controller position after movement
        if hasattr(self.motor_controller, 'get_position'):
            actual_pos = self.motor_controller.get_position()
            self.current_position = actual_pos.copy()
            logger.info(f"Position synced after rapid: {self.current_position}")
            
            # Debug print for Z position comparison
            if abs(target_pos['Z'] - actual_pos['Z']) > 0.001:
                print(f"*** Z POSITION MISMATCH: Target={target_pos['Z']:.3f}, Actual={actual_pos['Z']:.3f} ***")
        else:
            self.current_position = target_pos.copy()
    
    def _execute_linear_segment(self, segment: Dict):
        """Execute a linear interpolation segment (smooth motion)."""
        start_pos = segment['start_pos']
        target_pos = segment['target_pos']
        
        # Calculate deltas
        delta_x = target_pos['X'] - start_pos['X']
        delta_y = target_pos['Y'] - start_pos['Y']
        delta_z = target_pos['Z'] - start_pos['Z']
        delta_rot = target_pos['ROT'] - start_pos['ROT']
        
        logger.info(f"LINEAR: ({start_pos['X']:.1f},{start_pos['Y']:.1f},{start_pos['Z']:.1f},{start_pos['ROT']:.1f}) -> ({target_pos['X']:.1f},{target_pos['Y']:.1f},{target_pos['Z']:.1f},{target_pos['ROT']:.1f}) = delta({delta_x:.2f},{delta_y:.2f},{delta_z:.2f},{delta_rot:.2f})")
        
        # Execute smooth coordinated movement
        self.motor_controller.move_coordinated(
            x_distance_mm=delta_x,
            y_distance_mm=delta_y,
            z_distance_mm=delta_z,
            rot_distance_mm=delta_rot
        )
        
        # Sync with actual motor controller position after movement
        if hasattr(self.motor_controller, 'get_position'):
            actual_pos = self.motor_controller.get_position()
            self.current_position = actual_pos.copy()
            logger.info(f"Position synced after linear: {self.current_position}")
            
            # Debug print for Z position comparison
            if abs(target_pos['Z'] - actual_pos['Z']) > 0.001:
                print(f"*** Z POSITION MISMATCH: Target={target_pos['Z']:.3f}, Actual={actual_pos['Z']:.3f} ***")
        else:
            self.current_position = target_pos.copy()
    
    def stop_execution(self):
        """Stop smooth motion execution."""
        self.stop_requested = True
        self.motor_controller.stop_movement()
        logger.info("Smooth motion execution stopped") 