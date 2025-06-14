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

from fabric_cnc.config import config
from fabric_cnc.motor_control.driver import MotorConfig, StepperMotor

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
        for name, pins in config.gpio_pins.items():
            if 'DIR' not in pins:
                continue
                
            # Create motor frame
            frame = ttk.LabelFrame(
                self.main_frame,
                text=f"{name} Axis",
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
            
            # Create motor config
            motor_config = MotorConfig(
                dir_pin=pins['DIR'],
                step_pin=pins['STEP'],
                en_pin=pins['EN'],
                name=name,
                steps_per_mm=config.steps_per_mm[name],
                direction_inverted=config.direction_inverted[name],
                hall_pin=pins.get('HALL')
            )
            
            # Create motor controller
            motor = StepperMotor(
                config=motor_config,
                simulation_mode=config.simulation_mode
            )
            self.motors[name] = motor
            self.motor_frames[name] = frame
            
            # Create control buttons
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
            
            # Create status label
            status_var = tk.StringVar(value="Ready")
            ttk.Label(
                frame,
                textvariable=status_var
            ).grid(row=1, column=0, columnspan=3, pady=5)
            
            row += 1
            
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
            
    def enable_all_motors(self) -> None:
        """Enable all motors."""
        try:
            for motor in self.motors.values():
                motor.enable()
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