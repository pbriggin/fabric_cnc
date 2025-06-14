#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI for testing and controlling stepper motors.
Provides manual control interface with safety features and status feedback.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Optional
import time
import os

from fabric_cnc.config import config
from fabric_cnc.motor_control.driver import (
    MotorConfig,
    StepperMotor,
    YAxisController
)

logger = logging.getLogger(__name__)

class MotorTestUI:
    """GUI for testing and controlling stepper motors."""
    
    def __init__(self, root: tk.Tk):
        """Initialize the motor test UI.
        
        Args:
            root: Tkinter root window
        """
        self.root = root
        self.root.title("Fabric CNC Motor Test")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Configure logging
        self._setup_logging()
        
        # Create main frame
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Create status bar
        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ttk.Label(
            self.main_frame,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            padding="5"
        )
        self.status_bar.grid(
            row=0,
            column=0,
            columnspan=3,
            sticky=(tk.W, tk.E),
            pady=(0, 10)
        )
        
        # Initialize motors
        self.motors: Dict[str, StepperMotor] = {}
        self.motor_frames: Dict[str, ttk.Frame] = {}
        self.y_axis: Optional[YAxisController] = None
        self._init_motors()
        
        # Create control buttons
        self._create_control_buttons()
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        
        logger.info("Motor test UI initialized")
        
    def _setup_logging(self) -> None:
        """Set up logging configuration."""
        # Get log level from environment or default to INFO
        log_level = os.getenv('FABRIC_CNC_LOG_LEVEL', 'INFO').upper()
        numeric_level = getattr(logging, log_level, logging.INFO)
        
        # Configure root logger
        logging.basicConfig(
            level=numeric_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Set specific logger levels
        logging.getLogger('fabric_cnc.motor_control.driver').setLevel(numeric_level)
        logging.getLogger('fabric_cnc.motor_control.motor_test_ui').setLevel(numeric_level)
        
        logger.info(f"Logging level set to {log_level}")
        
    def _init_motors(self) -> None:
        """Initialize motor controllers and create UI elements."""
        row = 1
        
        # Initialize X motor
        x_pins = config.gpio_pins['X']
        x_config = MotorConfig(
            dir_pin=x_pins['DIR'],
            step_pin=x_pins['STEP'],
            en_pin=x_pins['EN'],
            name='X',
            steps_per_mm=config.steps_per_mm['X'],
            direction_inverted=config.direction_inverted['X'],
            hall_pin=x_pins.get('HALL')
        )
        x_motor = StepperMotor(
            config=x_config,
            simulation_mode=config.simulation_mode
        )
        self.motors['X'] = x_motor
        self._create_motor_frame(self.main_frame, x_motor, 'X')
        row += 1
        
        # Initialize Y motors and Y-axis controller
        y1_pins = config.gpio_pins['Y1']
        y1_config = MotorConfig(
            dir_pin=y1_pins['DIR'],
            step_pin=y1_pins['STEP'],
            en_pin=y1_pins['EN'],
            name='Y1',
            steps_per_mm=config.steps_per_mm['Y1'],
            direction_inverted=config.direction_inverted['Y1'],
            hall_pin=y1_pins.get('HALL')
        )
        y1_motor = StepperMotor(
            config=y1_config,
            simulation_mode=config.simulation_mode
        )
        self.motors['Y1'] = y1_motor
        self._create_motor_frame(self.main_frame, y1_motor, 'Y1')
        row += 1
        
        y2_pins = config.gpio_pins['Y2']
        y2_config = MotorConfig(
            dir_pin=y2_pins['DIR'],
            step_pin=y2_pins['STEP'],
            en_pin=y2_pins['EN'],
            name='Y2',
            steps_per_mm=config.steps_per_mm['Y2'],
            direction_inverted=config.direction_inverted['Y2'],
            hall_pin=y2_pins.get('HALL')
        )
        y2_motor = StepperMotor(
            config=y2_config,
            simulation_mode=config.simulation_mode
        )
        self.motors['Y2'] = y2_motor
        self._create_motor_frame(self.main_frame, y2_motor, 'Y2')
        row += 1
        
        # Create Y-axis controller
        self.y_axis = YAxisController(
            y1_motor=y1_motor,
            y2_motor=y2_motor,
            simulation_mode=config.simulation_mode
        )
        
        # Create Y-axis frame
        y_frame = ttk.LabelFrame(
            self.main_frame,
            text="Y Axis (Synchronized)",
            padding="5"
        )
        y_frame.grid(
            row=row,
            column=0,
            sticky=(tk.W, tk.E),
            pady=5
        )
        y_frame.columnconfigure(0, weight=1)
        y_frame.columnconfigure(1, weight=1)
        y_frame.columnconfigure(2, weight=1)
        
        ttk.Button(
            y_frame,
            text="Forward",
            command=lambda: self.move_y_axis(True)
        ).grid(row=0, column=0, padx=5)
        
        ttk.Button(
            y_frame,
            text="Stop",
            command=self.stop_y_axis
        ).grid(row=0, column=1, padx=5)
        
        ttk.Button(
            y_frame,
            text="Reverse",
            command=lambda: self.move_y_axis(False)
        ).grid(row=0, column=2, padx=5)
        
        status_var = tk.StringVar(value="Ready")
        ttk.Label(
            y_frame,
            textvariable=status_var
        ).grid(row=1, column=0, columnspan=3, pady=5)
        
        row += 1
        
        # Initialize Z motors
        for z_name in ['Z_LIFT', 'Z_ROTATE']:
            z_pins = config.gpio_pins[z_name]
            z_config = MotorConfig(
                dir_pin=z_pins['DIR'],
                step_pin=z_pins['STEP'],
                en_pin=z_pins['EN'],
                name=z_name,
                steps_per_mm=config.steps_per_mm[z_name],
                direction_inverted=config.direction_inverted[z_name],
                hall_pin=z_pins.get('HALL')
            )
            z_motor = StepperMotor(
                config=z_config,
                simulation_mode=config.simulation_mode
            )
            self.motors[z_name] = z_motor
            self._create_motor_frame(self.main_frame, z_motor, z_name)
            row += 1
            
    def _create_motor_frame(self, parent, motor, name):
        """Create a frame for a single motor's controls."""
        frame = ttk.LabelFrame(parent, text=f"{name} Motor")
        frame.pack(padx=5, pady=5, fill="x")
        
        # Movement buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(padx=5, pady=5)
        
        ttk.Button(btn_frame, text="Forward", 
                  command=lambda: self._move_motor(motor, 10)).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Reverse", 
                  command=lambda: self._move_motor(motor, -10)).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Stop", 
                  command=lambda: self._stop_motor(motor)).pack(side="left", padx=2)
        
        return frame
            
    def _create_control_buttons(self) -> None:
        """Create the control buttons frame."""
        frame = ttk.LabelFrame(
            self.main_frame,
            text="Control",
            padding="5"
        )
        frame.grid(
            row=0,
            column=1,
            sticky=(tk.N, tk.S, tk.E, tk.W),
            padx=5,
            pady=5
        )
        
        # Emergency stop button
        ttk.Button(
            frame,
            text="EMERGENCY STOP",
            command=self._emergency_stop,
            style="Emergency.TButton"
        ).pack(fill="x", padx=5, pady=5)
        
        # Status display
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(
            frame,
            textvariable=self.status_var,
            wraplength=200
        ).pack(fill="x", padx=5, pady=5)
        
    def move_motor(self, motor: StepperMotor, direction: bool) -> None:
        """Move a motor in the specified direction.
        
        Args:
            motor: Motor to move
            direction: True for forward, False for reverse
        """
        try:
            distance = 10.0  # mm
            speed = config.motion.default_speed_mm_s
            
            self.status_var.set(
                f"Moving {motor.config.name} "
                f"{'forward' if direction else 'reverse'}"
            )
            
            motor.move_mm(direction, distance, speed)
            
            self.status_var.set("Ready")
            logger.info(
                f"Moved {motor.config.name} "
                f"{'forward' if direction else 'reverse'} {distance}mm"
            )
        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")
            logger.error(f"Error moving motor: {e}")
            messagebox.showerror("Motor Error", str(e))
            
    def move_y_axis(self, direction: bool) -> None:
        """Move both Y motors in sync.
        
        Args:
            direction: True for forward, False for reverse
        """
        if not self.y_axis:
            return
            
        try:
            # Enable motors if they're not already enabled
            if not self.y_axis._enabled:
                self.y_axis.enable()
                self.status_var.set("Enabled Y-axis motors")
                time.sleep(0.1)  # Give motors time to enable
                
            distance = 10.0  # mm
            speed = config.motion.default_speed_mm_s
            
            self.status_var.set(
                f"Moving Y-axis "
                f"{'forward' if direction else 'reverse'}"
            )
            
            self.y_axis.move_mm(direction, distance, speed)
            
            self.status_var.set("Ready")
            logger.info(
                f"Moved Y-axis "
                f"{'forward' if direction else 'reverse'} {distance}mm"
            )
        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")
            logger.error(f"Error moving Y-axis: {e}")
            messagebox.showerror("Motor Error", str(e))
            
    def stop_motor(self, motor: StepperMotor) -> None:
        """Stop a motor.
        
        Args:
            motor: Motor to stop
        """
        try:
            motor.disable()
            self.status_var.set(f"Stopped {motor.config.name}")
            logger.info(f"Stopped {motor.config.name}")
        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")
            logger.error(f"Error stopping motor: {e}")
            messagebox.showerror("Motor Error", str(e))
            
    def stop_y_axis(self) -> None:
        """Stop both Y motors."""
        if not self.y_axis:
            return
            
        try:
            self.y_axis.disable()
            self.status_var.set("Stopped Y-axis")
            logger.info("Stopped Y-axis")
        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")
            logger.error(f"Error stopping Y-axis: {e}")
            messagebox.showerror("Motor Error", str(e))
            
    def _emergency_stop(self) -> None:
        """Emergency stop all motors."""
        try:
            for motor in self.motors.values():
                motor.disable()
            if self.y_axis:
                self.y_axis.disable()
            self.status_var.set("EMERGENCY STOP")
            logger.warning("Emergency stop activated")
            messagebox.showwarning(
                "Emergency Stop",
                "All motors have been disabled"
            )
        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")
            logger.error(f"Error during emergency stop: {e}")
            messagebox.showerror("Motor Error", str(e))
            
    def on_closing(self) -> None:
        """Handle window closing."""
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            try:
                for motor in self.motors.values():
                    motor.cleanup()
                if self.y_axis:
                    self.y_axis.cleanup()
                logger.info("Application closed")
                self.root.destroy()
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
                messagebox.showerror("Error", str(e))
                self.root.destroy()

def main() -> None:
    """Main entry point for the motor test UI."""
    root = tk.Tk()
    app = MotorTestUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 