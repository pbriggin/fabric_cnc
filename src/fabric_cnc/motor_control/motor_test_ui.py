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
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
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
        self._create_motor_frame(x_motor, row)
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
            self._create_motor_frame(z_motor, row)
            row += 1
            
    def _create_motor_frame(self, motor: StepperMotor, row: int) -> None:
        """Create a frame for a single motor.
        
        Args:
            motor: Motor to create frame for
            row: Grid row for the frame
        """
        frame = ttk.LabelFrame(
            self.main_frame,
            text=f"{motor.config.name} Axis",
            padding="5"
        )
        frame.grid(
            row=row,
            column=0,
            sticky=(tk.W, tk.E),
            pady=5
        )
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        
        ttk.Button(
            frame,
            text="Forward",
            command=lambda m=motor: self.move_motor(m, True)
        ).grid(row=0, column=0, padx=5)
        
        ttk.Button(
            frame,
            text="Stop",
            command=lambda m=motor: self.stop_motor(m)
        ).grid(row=0, column=1, padx=5)
        
        ttk.Button(
            frame,
            text="Reverse",
            command=lambda m=motor: self.move_motor(m, False)
        ).grid(row=0, column=2, padx=5)
        
        status_var = tk.StringVar(value="Ready")
        ttk.Label(
            frame,
            textvariable=status_var
        ).grid(row=1, column=0, columnspan=3, pady=5)
        
        self.motor_frames[motor.config.name] = frame
            
    def _create_control_buttons(self) -> None:
        """Create global control buttons."""
        control_frame = ttk.Frame(self.main_frame)
        control_frame.grid(
            row=len(self.motors) + 1,
            column=0,
            sticky=(tk.W, tk.E),
            pady=10
        )
        
        ttk.Button(
            control_frame,
            text="Enable All",
            command=self.enable_all_motors
        ).grid(row=0, column=0, padx=5)
        
        ttk.Button(
            control_frame,
            text="Disable All",
            command=self.disable_all_motors
        ).grid(row=0, column=1, padx=5)
        
        ttk.Button(
            control_frame,
            text="Emergency Stop",
            command=self.emergency_stop,
            style="Emergency.TButton"
        ).grid(row=0, column=2, padx=5)
        
        # Configure emergency stop button style
        style = ttk.Style()
        style.configure(
            "Emergency.TButton",
            background="red",
            foreground="white"
        )
        
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
            
    def enable_all_motors(self) -> None:
        """Enable all motors."""
        try:
            for motor in self.motors.values():
                motor.enable()
            if self.y_axis:
                self.y_axis.enable()
            self.status_var.set("All motors enabled")
            logger.info("All motors enabled")
        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")
            logger.error(f"Error enabling motors: {e}")
            messagebox.showerror("Motor Error", str(e))
            
    def disable_all_motors(self) -> None:
        """Disable all motors."""
        try:
            for motor in self.motors.values():
                motor.disable()
            if self.y_axis:
                self.y_axis.disable()
            self.status_var.set("All motors disabled")
            logger.info("All motors disabled")
        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")
            logger.error(f"Error disabling motors: {e}")
            messagebox.showerror("Motor Error", str(e))
            
    def emergency_stop(self) -> None:
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