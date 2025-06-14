#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration management for the fabric CNC system.
Provides motor configurations, work area settings, and motion parameters.
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

@dataclass
class WorkArea:
    """Work area dimensions in millimeters."""
    x: float
    y: float

@dataclass
class MotionConfig:
    """Motion control configuration."""
    default_speed_mm_s: float
    default_accel_mm_s2: float
    lift_height_mm: float

class Config:
    """Configuration manager for the fabric CNC system."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration.
        
        Args:
            config_path: Optional path to JSON configuration file
        """
        self.gpio_pins = {
            'X': {'DIR': 2, 'STEP': 3, 'EN': 4, 'HALL': 17},
            'Y1': {'DIR': 21, 'STEP': 19, 'EN': 23},  # Left Y motor
            'Y2': {'DIR': 27, 'STEP': 17, 'EN': 22},  # Right Y motor
            'Z_LIFT': {'DIR': 11, 'STEP': 12, 'EN': 13, 'HALL': 22},
            'Z_ROTATE': {'DIR': 14, 'STEP': 15, 'EN': 16, 'HALL': 23},
        }
        
        self.steps_per_mm = {
            'X': 80,
            'Y1': 80,
            'Y2': 80,
            'Z_LIFT': 400,
            'Z_ROTATE': 10,
        }
        
        self.direction_inverted = {
            'X': False,
            'Y1': False,
            'Y2': True,
            'Z_LIFT': False,
            'Z_ROTATE': False,
        }
        
        self.work_area = WorkArea(x=1524, y=1016)
        self.motion = MotionConfig(
            default_speed_mm_s=20,
            default_accel_mm_s2=100,
            lift_height_mm=25.4
        )
        
        self.simulation_mode = self._get_bool_env('FABRIC_CNC_SIMULATION', False)
        self.step_pulse_duration = float(
            os.getenv('FABRIC_CNC_STEP_PULSE_DURATION', '0.0005')
        )
        
        if config_path and config_path.exists():
            self.load_config(config_path)
            
        self._validate_config()
        
    def _get_bool_env(self, name: str, default: bool) -> bool:
        """Get boolean value from environment variable."""
        value = os.getenv(name)
        if value is None:
            return default
        return value.lower() in ('true', '1', 'yes')
        
    def load_config(self, config_path: Path) -> None:
        """Load configuration from JSON file.
        
        Args:
            config_path: Path to JSON configuration file
        """
        try:
            with open(config_path) as f:
                config = json.load(f)
                
            if 'gpio_pins' in config:
                self.gpio_pins.update(config['gpio_pins'])
            if 'steps_per_mm' in config:
                self.steps_per_mm.update(config['steps_per_mm'])
            if 'direction_inverted' in config:
                self.direction_inverted.update(config['direction_inverted'])
            if 'work_area' in config:
                self.work_area = WorkArea(**config['work_area'])
            if 'motion' in config:
                self.motion = MotionConfig(**config['motion'])
                
            logger.info(f"Loaded configuration from {config_path}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
            
    def save_config(self, config_path: Path) -> None:
        """Save current configuration to JSON file.
        
        Args:
            config_path: Path to save configuration file
        """
        config = {
            'gpio_pins': self.gpio_pins,
            'steps_per_mm': self.steps_per_mm,
            'direction_inverted': self.direction_inverted,
            'work_area': {
                'x': self.work_area.x,
                'y': self.work_area.y
            },
            'motion': {
                'default_speed_mm_s': self.motion.default_speed_mm_s,
                'default_accel_mm_s2': self.motion.default_accel_mm_s2,
                'lift_height_mm': self.motion.lift_height_mm
            }
        }
        
        try:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Saved configuration to {config_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise
            
    def _validate_config(self) -> None:
        """Validate configuration values."""
        # Check that all motors have required pins
        required_pins = {'DIR', 'STEP', 'EN'}
        for motor, pins in self.gpio_pins.items():
            missing = required_pins - set(pins.keys())
            if missing:
                raise ValueError(
                    f"Motor {motor} missing required pins: {missing}"
                )
                
        # Check that all motors have steps_per_mm defined
        for motor in self.gpio_pins:
            if motor not in self.steps_per_mm:
                raise ValueError(
                    f"Motor {motor} missing steps_per_mm configuration"
                )
                
        # Check that all motors have direction_inverted defined
        for motor in self.gpio_pins:
            if motor not in self.direction_inverted:
                raise ValueError(
                    f"Motor {motor} missing direction_inverted configuration"
                )
                
        # Validate work area dimensions
        if self.work_area.x <= 0 or self.work_area.y <= 0:
            raise ValueError("Work area dimensions must be positive")
            
        # Validate motion parameters
        if self.motion.default_speed_mm_s <= 0:
            raise ValueError("Default speed must be positive")
        if self.motion.default_accel_mm_s2 <= 0:
            raise ValueError("Default acceleration must be positive")
        if self.motion.lift_height_mm <= 0:
            raise ValueError("Lift height must be positive")
            
        logger.info("Configuration validation successful")

# Create global configuration instance
config = Config()

# Export commonly used values for backward compatibility
GPIO_PINS = config.gpio_pins
STEPS_PER_MM = config.steps_per_mm
DIRECTION_INVERTED = config.direction_inverted
WORKAREA_MM = {'X': config.work_area.x, 'Y': config.work_area.y}
DEFAULT_SPEED_MM_S = config.motion.default_speed_mm_s
DEFAULT_ACCEL_MM_S2 = config.motion.default_accel_mm_s2
LIFT_HEIGHT_MM = config.motion.lift_height_mm
USE_SIMULATION_MODE = config.simulation_mode
STEP_PULSE_DURATION = config.step_pulse_duration 