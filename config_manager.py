#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration manager for the redesigned Fabric CNC system.
Loads machine configuration from YAML and provides clean interfaces.
"""

import os
import platform
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional

@dataclass
class AxisConfig:
    """Configuration for a single axis."""
    step_pin: int
    dir_pin: int
    ena_pin: int
    invert_dir: bool
    steps_per_mm: float
    hall_pin: int
    steps_per_deg: Optional[float] = None

@dataclass
class MotionConfig:
    """Motion control configuration."""
    default_speed: float
    max_speed: float
    default_accel: float
    lift_height: float

@dataclass
class HomingConfig:
    """Homing configuration."""
    offset: float
    verification_distance: float
    speeds: Dict[str, float]

@dataclass
class PlannerConfig:
    """Motion planner configuration."""
    max_accel: Dict[str, float]
    junction_deviation: float
    segment_tolerance: float

@dataclass
class MachineConfig:
    """Complete machine configuration."""
    name: str
    units: str
    axes: Dict[str, AxisConfig]
    limits: Dict[str, Dict[str, float]]
    motion: MotionConfig
    homing: HomingConfig
    planner: PlannerConfig
    gpio: Dict[str, Any]

class ConfigManager:
    """Manages machine configuration loading and validation."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration manager.
        
        Args:
            config_path: Path to YAML configuration file
        """
        if config_path is None:
            config_path = Path(__file__).parent / "machine_config.yaml"
        
        self.config_path = config_path
        self.machine_config = self._load_config()
        
        # System detection
        self.on_rpi = platform.system() == 'Linux' and (
            os.uname().machine.startswith('arm') or 
            os.uname().machine.startswith('aarch')
        )
        
        # Simulation mode detection
        self.simulation_mode = self._get_bool_env('FABRIC_CNC_SIMULATION', False)
        
    def _load_config(self) -> MachineConfig:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            data = yaml.safe_load(f)
        
        # Parse axes configuration
        axes = {}
        for axis_name, axis_data in data['machine']['axes'].items():
            axes[axis_name] = AxisConfig(
                step_pin=axis_data['step'],
                dir_pin=axis_data['dir'],
                ena_pin=axis_data['ena'],
                invert_dir=axis_data['invert_dir'],
                steps_per_mm=axis_data.get('steps_per_mm', 0),
                hall_pin=axis_data['hall'],
                steps_per_deg=axis_data.get('steps_per_deg')
            )
        
        # Parse motion configuration
        motion_data = data['machine']['motion']
        motion = MotionConfig(
            default_speed=motion_data['default_speed'],
            max_speed=motion_data['max_speed'],
            default_accel=motion_data['default_accel'],
            lift_height=motion_data['lift_height']
        )
        
        # Parse homing configuration
        homing_data = data['machine']['homing']
        homing = HomingConfig(
            offset=homing_data['offset'],
            verification_distance=homing_data['verification_distance'],
            speeds=homing_data['speeds']
        )
        
        # Parse planner configuration
        planner_data = data['machine']['planner']
        planner = PlannerConfig(
            max_accel=planner_data['max_accel'],
            junction_deviation=planner_data['junction_deviation'],
            segment_tolerance=planner_data['segment_tolerance']
        )
        
        return MachineConfig(
            name=data['machine']['name'],
            units=data['machine']['units'],
            axes=axes,
            limits=data['machine']['limits'],
            motion=motion,
            homing=homing,
            planner=planner,
            gpio=data['machine']['gpio']
        )
    
    def _get_bool_env(self, name: str, default: bool) -> bool:
        """Get boolean value from environment variable."""
        value = os.getenv(name)
        if value is None:
            return default
        return value.lower() in ('true', '1', 'yes')
    
    def get_axis_config(self, axis_name: str) -> AxisConfig:
        """Get configuration for a specific axis."""
        if axis_name not in self.machine_config.axes:
            raise ValueError(f"Unknown axis: {axis_name}")
        return self.machine_config.axes[axis_name]
    
    def get_axis_names(self) -> list[str]:
        """Get list of all axis names."""
        return list(self.machine_config.axes.keys())
    
    def get_limits(self, axis_name: str) -> Dict[str, float]:
        """Get limits for a specific axis."""
        if axis_name not in self.machine_config.limits:
            raise ValueError(f"Unknown axis: {axis_name}")
        return self.machine_config.limits[axis_name]
    
    def validate_position(self, axis_name: str, position: float) -> bool:
        """Validate if a position is within axis limits."""
        limits = self.get_limits(axis_name)
        return limits['min'] <= position <= limits['max']
    
    def get_work_area(self) -> Dict[str, float]:
        """Get work area dimensions."""
        return {
            'X': self.machine_config.limits['X']['max'],
            'Y': self.machine_config.limits['Y']['max'],
            'Z': self.machine_config.limits['Z']['max']
        }

# Global configuration instance
config_manager = ConfigManager() 