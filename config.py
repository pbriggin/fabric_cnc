#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration management for the fabric CNC system.
Provides motor configurations, work area settings, and motion parameters.
"""

import json
import logging
import os
import platform
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
            'X': {'DIR': 23, 'STEP': 24, 'EN': 9, 'HALL': 16},  # X hall sensor on pin 16
            'Y1': {'DIR': 27, 'STEP': 22, 'EN': 17, 'HALL': 1},  # Left Y motor hall sensor on pin 1
            'Y2': {'DIR': 5, 'STEP': 6, 'EN': 10, 'HALL': 20},  # Right Y motor hall sensor on pin 20
            'Z_LIFT': {'DIR': 7, 'STEP': 18, 'EN': 8, 'HALL': 25},  # Z hall sensor on pin 25 - matches motor_drive_universal.py
            'Z_ROTATE': {'DIR': 19, 'STEP': 26, 'EN': 13, 'HALL': 12},  # ROT hall sensor on pin 12 - matches hall_sensor_test.py
        }
        
        self.steps_per_mm = {
            'X': 80,
            'Y1': 80,
            'Y2': 80,
            'Z_LIFT': 400,
            'Z_ROTATE': 10,
        }
        
        self.direction_inverted = {
            'X': True,  # Invert X direction to fix flipped axis
            'Y1': True,  # Invert Y1 to fix Y direction
            'Y2': False,  # Keep Y2 normal (opposite of Y1 for sync)
            'Z_LIFT': False,
            'Z_ROTATE': True,  # Invert direction to fix one-way rotation issue
        }
        
        self.work_area = WorkArea(x=1524, y=1016)
        self.motion = MotionConfig(
            default_speed_mm_s=20,
            default_accel_mm_s2=100,
            lift_height_mm=25.4
        )
        
        self.simulation_mode = self._get_bool_env('FABRIC_CNC_SIMULATION', False)
        self.step_pulse_duration = float(
            os.getenv('FABRIC_CNC_STEP_PULSE_DURATION', '0.001')
        )
        
        # Sensor debounce configuration (in milliseconds)
        self.sensor_debounce_times = {
            'X': 15,      # 15ms for X sensor (reduced from 25ms for better responsiveness)
            'Y1': 10,     # 10ms for Y1 sensor
            'Y2': 10,     # 10ms for Y2 sensor
            'Z_LIFT': 40, # 40ms for Z sensor (increased for maximum noise immunity)
            'Z_ROTATE': 25 # 25ms for ROT sensor (increased for better noise immunity)
        }
        
        # Sensor reading count for multi-reading debounce
        self.sensor_reading_count = 2  # Reduced from 3 to 2 for faster response
        
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

# System detection
ON_RPI = platform.system() == 'Linux' and (os.uname().machine.startswith('arm') or os.uname().machine.startswith('aarch'))

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

# Simulation mode detection
SIMULATION_MODE = not ON_RPI or config.simulation_mode

# Motor configuration - Updated to match tested pin assignments
MOTOR_CONFIG = {
    'X': {
        'PULSES_PER_REV': 800,  # DIP switches set for 800 steps per revolution
        'MM_PER_REV': 20,  # 20mm per revolution (adjusted based on observed movement)
        'STEP_DELAY': 0.00025,  # 0.25ms between pulses = 2000 steps/sec (2x faster)
        'STEP': 24,  # GPIO24 (Pin 18) - Motor 3 (X)
        'DIR': 23,   # GPIO23 (Pin 16) - Motor 3 (X)
        'EN': 9,     # GPIO9 (Pin 21) - Motor 3 (X)
        'HALL': 16,  # GPIO16 (Pin 36) - Hall effect sensor pin
        'HOME_DIRECTION': 1,  # Positive direction for homing
        'HOME_SPEED': 0.0005,  # Original homing speed (0.5ms between pulses)
        'VERIFY_SPEED': 0.002  # Original verification speed (2ms between pulses)
    },
    'Y1': {
        'PULSES_PER_REV': 800,
        'MM_PER_REV': 20,
        'STEP_DELAY': 0.00025,  # 0.25ms between pulses = 2000 steps/sec (2x faster)
        'STEP': 22,  # GPIO22 (Pin 15) - Motor 2 (Left Y)
        'DIR': 27,   # GPIO27 (Pin 13) - Motor 2 (Left Y)
        'EN': 17,    # GPIO17 (Pin 11) - Motor 2 (Left Y)
        'HALL': 1,   # GPIO1 (Pin 28) - Hall effect sensor pin (Left Y)
        'HOME_DIRECTION': 1,
        'HOME_SPEED': 0.0005,  # Original homing speed
        'VERIFY_SPEED': 0.002  # Original verification speed
    },
    'Y2': {
        'PULSES_PER_REV': 800,
        'MM_PER_REV': 20,
        'STEP_DELAY': 0.00025,  # 0.25ms between pulses = 2000 steps/sec (2x faster)
        'STEP': 6,   # GPIO6 (Pin 31) - Motor 1 (Right Y)
        'DIR': 5,    # GPIO5 (Pin 29) - Motor 1 (Right Y)
        'EN': 10,    # GPIO10 (Pin 19) - Motor 1 (Right Y) - Changed from GPIO4
        'HALL': 20,  # GPIO20 (Pin 38) - Hall effect sensor pin (Right Y)
        'HOME_DIRECTION': 1,
        'HOME_SPEED': 0.0005,  # Original homing speed
        'VERIFY_SPEED': 0.002  # Original verification speed
    },
    'Z_LIFT': {
        'PULSES_PER_REV': 800,
        'MM_PER_REV': 5,  # 5mm per revolution for Z axis
        'STEP_DELAY': 0.00025,  # 0.25ms between pulses = 2000 steps/sec (4x faster than original)
        'STEP': 18,  # GPIO18 (Pin 12) - Motor 4 (Z) - matches motor_drive_universal.py
        'DIR': 7,    # GPIO7 (Pin 26) - Motor 4 (Z) - matches motor_drive_universal.py
        'EN': 8,     # GPIO8 (Pin 24) - Motor 4 (Z) - matches motor_drive_universal.py
        'HALL': 25,  # GPIO25 (Pin 22) - Hall effect sensor pin - matches hall_sensor_test.py
        'HOME_DIRECTION': -1,
        'HOME_SPEED': 0.001,  # Original homing speed
        'VERIFY_SPEED': 0.004  # Original verification speed
    },
    'Z_ROTATE': {
        'PULSES_PER_REV': 1600,  # Updated to match actual motor driver setting
        'MM_PER_REV': 360,  # 360 degrees per revolution
        'STEP_DELAY': 0.00025,  # 0.25ms between pulses = 2000 steps/sec (4x faster)
        'STEP': 26,  # GPIO26 (Pin 37) - Motor 5 (Rotation) - matches motor_drive_universal.py
        'DIR': 19,   # GPIO19 (Pin 35) - Motor 5 (Rotation) - matches motor_drive_universal.py
        'EN': 13,    # GPIO13 (Pin 33) - Motor 5 (Rotation) - matches motor_drive_universal.py
        'HALL': 12,  # GPIO12 (Pin 32) - Hall effect sensor pin - matches hall_sensor_test.py
        'HOME_DIRECTION': -1,
        'HOME_SPEED': 0.001,  # Original homing speed
        'VERIFY_SPEED': 0.004  # Original verification speed
    }
}

# Machine configuration
MACHINE_CONFIG = {
    'MAX_X': 1000,  # Maximum X travel in mm
    'MAX_Y': 1000,  # Maximum Y travel in mm
    'HOMING_OFFSET': 5,  # Distance to move after hitting home sensor (mm)
    'VERIFICATION_DISTANCE': 10  # Distance to move for verification (mm)
}

# GUI configuration
GUI_CONFIG = {
    'WINDOW_SIZE': (800, 600),
    'UPDATE_RATE': 100,  # ms between updates
    'MOVE_INCREMENT': 10,  # mm per button press
    'HOMING_BUTTON_COLOR': '#FFA500'  # Orange color for homing button
}

# Application configuration
APP_CONFIG = {
    'INCH_TO_MM': 25.4,
    'X_MAX_MM': 68 * 25.4,  # 68 inches
    'Y_MAX_MM': 45 * 25.4,  # 45 inches
    'Z_MAX_MM': 2.5 * 25.4,  # 2.5 inches
    'Z_UP_MM': -19.05,  # -0.75 inches
    'Z_DOWN_MM': -19.05,  # Same as hover height for testing
    'PLOT_BUFFER_IN': 1.0,
    'ANGLE_CHANGE_THRESHOLD_DEG': 2.0,
    'STEP_SIZE_INCHES': 0.1,
    'ARROW_KEY_REPEAT_DELAY': 100,
    'JOG_SLIDER_SCALE': 0.1,
    'CANVAS_WIDTH': 800,
    'CANVAS_HEIGHT': 600,
    'CANVAS_SCALE': 1.0,
    'TOOL_HEAD_RADIUS': 10,
    'LIVE_TOOL_HEAD_RADIUS': 7,
    'LIVE_TOOL_HEAD_DIR_RADIUS': 0.5,
    'ANIMATION_STEPS_PER_TICK': 1,
    'ANIMATION_TOOL_RADIUS': 0.5,
    'PLOT_BUFFER_PX': 50,  # Buffer around the plot in pixels
}

# UI Color scheme
UI_COLORS = {
    'PRIMARY_COLOR': '#2196F3',  # Blue 500
    'PRIMARY_VARIANT': '#1976D2',  # Blue 700
    'SECONDARY_COLOR': '#4FC3F7',  # Light Blue 300
    'BACKGROUND': '#F5F5F5',
    'SURFACE': '#F5F5F5',
    'ON_PRIMARY': '#ffffff',
    'ON_SURFACE': '#222222',
    'ERROR_COLOR': '#b00020',
    # Modern button styling
    'BUTTON_PRIMARY': '#3B82F6',  # Modern blue
    'BUTTON_PRIMARY_HOVER': '#2563EB',  # Darker blue on hover
    'BUTTON_SECONDARY': '#6B7280',  # Modern gray
    'BUTTON_SECONDARY_HOVER': '#4B5563',  # Darker gray on hover
    'BUTTON_SUCCESS': '#10B981',  # Modern green
    'BUTTON_SUCCESS_HOVER': '#059669',  # Darker green on hover
    'BUTTON_WARNING': '#F59E0B',  # Modern orange
    'BUTTON_WARNING_HOVER': '#D97706',  # Darker orange on hover
    'BUTTON_DANGER': '#EF4444',  # Modern red
    'BUTTON_DANGER_HOVER': '#DC2626',  # Darker red on hover
    'BUTTON_TEXT': '#FFFFFF',  # White text on buttons
    'BUTTON_SHADOW': '#E5E7EB',  # Light shadow color
}

# UI Padding constants for consistent spacing
UI_PADDING = {
    'SMALL': 10,
    'MEDIUM': 12,
    'LARGE': 16,
    'XLARGE': 20,
    'XXLARGE': 24,
    'SECTION_SPACING': 16,
    'BUTTON_SPACING': 8,
    'FRAME_PADDING': 16,
    'CANVAS_PADDING': 20
}

# Toolpath configuration
TOOLPATH_CONFIG = {
    'DEFAULT_FEED_RATE': 100,
    'DEFAULT_Z_UP': 5,
    'DEFAULT_Z_DOWN': -1,
    'DEFAULT_STEP_SIZE': 0.1,
    'SPLINE_FLATTENING_PRECISION': 0.005,
    'CIRCLE_STEPS_MIN': 32,
    'CIRCLE_STEPS_MAX': 256,
    'SPLINE_STEPS_MIN': 64,
    'SPLINE_STEPS_MAX': 512,
    'MAX_ANGLE_STEP_RADIANS': 0.026179,  # 1.5 degrees
} 