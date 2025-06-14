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
import RPi.GPIO as GPIO

from fabric_cnc.config import config
from fabric_cnc.motor_control.driver import (
    MotorConfig,
    StepperMotor,
    YAxisController
)

logger = logging.getLogger(__name__)

class MotorTestUI:
    """Simple UI for testing individual motors."""
    
    def __init__(self, root: tk.Tk):
        """Initialize the motor test UI.
        
        Args:
            root: Root window
        """
        self.root = root
        self.root.title("Motor Test")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Setup logging
        self._setup_logging()
        
        # Create main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        
        # Initialize motors
        self.motors = {}
        self._init_motors()
        
        # Create emergency stop button
        self._create_emergency_stop()
        
        logger.info("Motor test UI initialized")
        
    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logger.info("Logging level set to DEBUG")
        
    def _init_motors(self) -> None:
        """Initialize motor controllers and create UI elements."""
        # Initialize X motor
        x_pins = config.gpio_pins['X']
        x_config = MotorConfig(
            dir_pin=x_pins['DIR'],
            step_pin=x_pins['STEP'],
            en_pin=x_pins['EN'],
            name='X',
            steps_per_mm=config.steps_per_mm['X'],
            direction_inverted=config.direction_inverted['X']
        )
        x_motor = StepperMotor(
            config=x_config,
            simulation_mode=config.simulation_mode
        )
        self.motors['X'] = x_motor
        self._create_motor_frame(self.main_frame, x_motor, 'X', 0)
        
        # Initialize Y1 motor
        y1_pins = config.gpio_pins['Y1']
        y1_config = MotorConfig(
            dir_pin=y1_pins['DIR'],
            step_pin=y1_pins['STEP'],
            en_pin=y1_pins['EN'],
            name='Y1',
            steps_per_mm=config.steps_per_mm['Y1'],
            direction_inverted=config.direction_inverted['Y1']
        )
        y1_motor = StepperMotor(
            config=y1_config,
            simulation_mode=config.simulation_mode
        )
        self.motors['Y1'] = y1_motor
        self._create_motor_frame(self.main_frame, y1_motor, 'Y1', 1)
        
        # Initialize Y2 motor
        y2_pins = config.gpio_pins['Y2']
        y2_config = MotorConfig(
            dir_pin=y2_pins['DIR'],
            step_pin=y2_pins['STEP'],
            en_pin=y2_pins['EN'],
            name='Y2',
            steps_per_mm=config.steps_per_mm['Y2'],
            direction_inverted=config.direction_inverted['Y2']
        )
        y2_motor = StepperMotor(
            config=y2_config,
            simulation_mode=config.simulation_mode
        )
        self.motors['Y2'] = y2_motor
        self._create_motor_frame(self.main_frame, y2_motor, 'Y2', 2)
        
        # Initialize Z motors
        for i, z_name in enumerate(['Z_LIFT', 'Z_ROTATE']):
            z_pins = config.gpio_pins[z_name]
            z_config = MotorConfig(
                dir_pin=z_pins['DIR'],
                step_pin=z_pins['STEP'],
                en_pin=z_pins['EN'],
                name=z_name,
                steps_per_mm=config.steps_per_mm[z_name],
                direction_inverted=config.direction_inverted[z_name]
            )
            z_motor = StepperMotor(
                config=z_config,
                simulation_mode=config.simulation_mode
            )
            self.motors[z_name] = z_motor
            self._create_motor_frame(self.main_frame, z_motor, z_name, i + 3)
            
    def _create_motor_frame(self, parent, motor, name, row):
        """Create a frame for a single motor's controls."""
        frame = ttk.LabelFrame(parent, text=f"{name} Motor")
        frame.grid(row=row, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # Movement buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=0, column=0, padx=5, pady=5)
        
        ttk.Button(btn_frame, text="Forward", 
                  command=lambda: self._step_motor(motor, True)).grid(row=0, column=0, padx=2)
        ttk.Button(btn_frame, text="Reverse", 
                  command=lambda: self._step_motor(motor, False)).grid(row=0, column=1, padx=2)
        
        # Status label
        status_var = tk.StringVar(value="Ready")
        ttk.Label(frame, textvariable=status_var).grid(row=1, column=0, pady=5)
        
        return frame
        
    def _create_emergency_stop(self) -> None:
        """Create emergency stop button."""
        ttk.Button(
            self.main_frame,
            text="EMERGENCY STOP",
            command=self._emergency_stop,
            style="Emergency.TButton"
        ).grid(row=5, column=0, sticky=(tk.W, tk.E), padx=5, pady=10)
        
    def _step_motor(self, motor: StepperMotor, direction: bool) -> None:
        """Step a motor once in the specified direction.
        
        Args:
            motor: Motor to step
            direction: True for forward, False for reverse
        """
        try:
            logger.info(f"Stepping {motor.config.name} {'forward' if direction else 'reverse'}")
            motor.step(direction)
        except Exception as e:
            logger.error(f"Error stepping motor: {e}")
            messagebox.showerror("Motor Error", str(e))
            
    def _emergency_stop(self) -> None:
        """Emergency stop all motors."""
        try:
            for motor in self.motors.values():
                motor.stop()
            logger.warning("Emergency stop activated")
            messagebox.showwarning(
                "Emergency Stop",
                "All motors have been stopped"
            )
        except Exception as e:
            logger.error(f"Error during emergency stop: {e}")
            messagebox.showerror("Motor Error", str(e))
            
    def on_closing(self) -> None:
        """Handle window closing."""
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            try:
                for motor in self.motors.values():
                    motor.cleanup()
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