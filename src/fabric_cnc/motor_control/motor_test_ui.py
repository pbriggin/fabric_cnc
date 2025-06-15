#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI for testing and controlling stepper motors.
Provides manual control interface with safety features and status feedback.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
import time
import RPi.GPIO as GPIO

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Motor configuration
PULSES_PER_REV = 3200
STEP_DELAY = 0.00025  # 0.25ms between pulses = 2000 steps/sec
JOG_STEPS = 100  # Number of steps for each jog movement

class MotorTestUI:
    """Simple UI for testing individual motors."""
    
    def __init__(self, root: tk.Tk):
        """Initialize the motor test UI."""
        self.root = root
        self.root.title("Motor Test")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        
        # Create main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        
        # Initialize motors
        self.motors = {
            'X': {'STEP': 5, 'DIR': 6, 'EN': 13},
            'Y1': {'STEP': 10, 'DIR': 9, 'EN': 11},
            'Y2': {'STEP': 17, 'DIR': 27, 'EN': 22},
            'Z_LIFT': {'STEP': 12, 'DIR': 11, 'EN': 13},
            'Z_ROTATE': {'STEP': 15, 'DIR': 14, 'EN': 16}
        }
        
        # Setup motor pins and create UI
        self._setup_motors()
        
        # Create jog controls
        self._create_jog_controls()
        
        # Create emergency stop button
        self._create_emergency_stop()
        
        # Bind arrow keys
        self.root.bind('<Up>', lambda e: self._jog_y_axis(True))
        self.root.bind('<Down>', lambda e: self._jog_y_axis(False))
        self.root.bind('<Left>', lambda e: self._jog_motor('X', False))
        self.root.bind('<Right>', lambda e: self._jog_motor('X', True))
        self.root.bind('<Prior>', lambda e: self._jog_motor('Z_LIFT', True))  # Page Up
        self.root.bind('<Next>', lambda e: self._jog_motor('Z_LIFT', False))  # Page Down
        self.root.bind('<Home>', lambda e: self._jog_motor('Z_ROTATE', True))
        self.root.bind('<End>', lambda e: self._jog_motor('Z_ROTATE', False))
        
        logger.info("Motor test UI initialized")
        
    def _setup_motors(self):
        """Setup GPIO pins for all motors and create UI elements."""
        for i, (name, pins) in enumerate(self.motors.items()):
            # Setup GPIO pins
            GPIO.setup(pins['STEP'], GPIO.OUT)
            GPIO.setup(pins['DIR'], GPIO.OUT)
            GPIO.setup(pins['EN'], GPIO.OUT)
            
            # Initialize pins to safe state
            GPIO.output(pins['STEP'], GPIO.LOW)
            GPIO.output(pins['DIR'], GPIO.LOW)
            GPIO.output(pins['EN'], GPIO.LOW)  # Enable motor
            
            # Create UI frame
            self._create_motor_frame(name, pins, i)
            
        # Create synchronized Y-axis frame
        self._create_y_axis_frame()
            
    def _create_motor_frame(self, name, pins, row):
        """Create a frame for a single motor's controls."""
        frame = ttk.LabelFrame(self.main_frame, text=f"{name} Motor")
        frame.grid(row=row, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # Movement buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=0, column=0, padx=5, pady=5)
        
        ttk.Button(btn_frame, text="Forward", 
                  command=lambda: self._step_motor(name, pins, True)).grid(row=0, column=0, padx=2)
        ttk.Button(btn_frame, text="Reverse", 
                  command=lambda: self._step_motor(name, pins, False)).grid(row=0, column=1, padx=2)
        
        # Status label
        status_var = tk.StringVar(value="Ready")
        ttk.Label(frame, textvariable=status_var).grid(row=1, column=0, pady=5)
        
        return frame

    def _create_y_axis_frame(self):
        """Create frame for synchronized Y-axis control."""
        frame = ttk.LabelFrame(self.main_frame, text="Synchronized Y-Axis")
        frame.grid(row=2, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # Movement buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=0, column=0, padx=5, pady=5)
        
        ttk.Button(btn_frame, text="Forward", 
                  command=lambda: self._step_y_axis(True)).grid(row=0, column=0, padx=2)
        ttk.Button(btn_frame, text="Reverse", 
                  command=lambda: self._step_y_axis(False)).grid(row=0, column=1, padx=2)
        
        # Status label
        status_var = tk.StringVar(value="Ready")
        ttk.Label(frame, textvariable=status_var).grid(row=1, column=0, pady=5)
        
        return frame

    def _create_jog_controls(self):
        """Create jog control frame with arrow buttons."""
        frame = ttk.LabelFrame(self.main_frame, text="Jog Controls")
        frame.grid(row=3, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # Create arrow buttons in a grid
        ttk.Button(frame, text="↑", command=lambda: self._jog_y_axis(True)).grid(row=0, column=1, padx=2, pady=2)
        ttk.Button(frame, text="↓", command=lambda: self._jog_y_axis(False)).grid(row=2, column=1, padx=2, pady=2)
        ttk.Button(frame, text="←", command=lambda: self._jog_motor('X', False)).grid(row=1, column=0, padx=2, pady=2)
        ttk.Button(frame, text="→", command=lambda: self._jog_motor('X', True)).grid(row=1, column=2, padx=2, pady=2)
        
        # Z-axis controls
        ttk.Button(frame, text="PgUp", command=lambda: self._jog_motor('Z_LIFT', True)).grid(row=0, column=3, padx=2, pady=2)
        ttk.Button(frame, text="PgDn", command=lambda: self._jog_motor('Z_LIFT', False)).grid(row=2, column=3, padx=2, pady=2)
        ttk.Button(frame, text="Home", command=lambda: self._jog_motor('Z_ROTATE', True)).grid(row=0, column=4, padx=2, pady=2)
        ttk.Button(frame, text="End", command=lambda: self._jog_motor('Z_ROTATE', False)).grid(row=2, column=4, padx=2, pady=2)
        
        # Add key binding hints
        ttk.Label(frame, text="Use arrow keys to jog X/Y").grid(row=3, column=0, columnspan=3, pady=5)
        ttk.Label(frame, text="PgUp/Dn: Z Lift, Home/End: Z Rotate").grid(row=3, column=3, columnspan=2, pady=5)
        
        return frame
        
    def _create_emergency_stop(self):
        """Create emergency stop button."""
        ttk.Button(
            self.main_frame,
            text="EMERGENCY STOP",
            command=self._emergency_stop,
            style="Emergency.TButton"
        ).grid(row=6, column=0, sticky=(tk.W, tk.E), padx=5, pady=10)
        
    def _step_motor(self, name, pins, direction):
        """Step a motor in the specified direction."""
        try:
            logger.info(f"Stepping {name} {'forward' if direction else 'reverse'}")
            
            # Set direction
            GPIO.output(pins['DIR'], GPIO.HIGH if direction else GPIO.LOW)
            
            # Step sequence
            for _ in range(PULSES_PER_REV):
                GPIO.output(pins['STEP'], GPIO.HIGH)
                time.sleep(STEP_DELAY)
                GPIO.output(pins['STEP'], GPIO.LOW)
                time.sleep(STEP_DELAY)
                
        except Exception as e:
            logger.error(f"Error stepping motor: {e}")
            messagebox.showerror("Motor Error", str(e))

    def _jog_motor(self, name, direction):
        """Jog a motor a small amount in the specified direction."""
        try:
            logger.info(f"Jogging {name} {'forward' if direction else 'reverse'}")
            pins = self.motors[name]
            
            # Set direction
            GPIO.output(pins['DIR'], GPIO.HIGH if direction else GPIO.LOW)
            
            # Step sequence
            for _ in range(JOG_STEPS):
                GPIO.output(pins['STEP'], GPIO.HIGH)
                time.sleep(STEP_DELAY)
                GPIO.output(pins['STEP'], GPIO.LOW)
                time.sleep(STEP_DELAY)
                
        except Exception as e:
            logger.error(f"Error jogging motor: {e}")
            messagebox.showerror("Motor Error", str(e))

    def _step_y_axis(self, direction):
        """Step both Y motors in sync."""
        try:
            logger.info(f"Stepping Y-axis {'forward' if direction else 'reverse'}")
            
            # Set directions (Y1 is reversed)
            GPIO.output(self.motors['Y1']['DIR'], GPIO.LOW if direction else GPIO.HIGH)
            GPIO.output(self.motors['Y2']['DIR'], GPIO.HIGH if direction else GPIO.LOW)
            
            # Step sequence
            for _ in range(PULSES_PER_REV):
                # Step both motors
                GPIO.output(self.motors['Y1']['STEP'], GPIO.HIGH)
                GPIO.output(self.motors['Y2']['STEP'], GPIO.HIGH)
                time.sleep(STEP_DELAY)
                GPIO.output(self.motors['Y1']['STEP'], GPIO.LOW)
                GPIO.output(self.motors['Y2']['STEP'], GPIO.LOW)
                time.sleep(STEP_DELAY)
                
        except Exception as e:
            logger.error(f"Error stepping Y-axis: {e}")
            messagebox.showerror("Motor Error", str(e))

    def _jog_y_axis(self, direction):
        """Jog both Y motors in sync."""
        try:
            logger.info(f"Jogging Y-axis {'forward' if direction else 'reverse'}")
            
            # Set directions (Y1 is reversed)
            GPIO.output(self.motors['Y1']['DIR'], GPIO.LOW if direction else GPIO.HIGH)
            GPIO.output(self.motors['Y2']['DIR'], GPIO.HIGH if direction else GPIO.LOW)
            
            # Step sequence
            for _ in range(JOG_STEPS):
                # Step both motors
                GPIO.output(self.motors['Y1']['STEP'], GPIO.HIGH)
                GPIO.output(self.motors['Y2']['STEP'], GPIO.HIGH)
                time.sleep(STEP_DELAY)
                GPIO.output(self.motors['Y1']['STEP'], GPIO.LOW)
                GPIO.output(self.motors['Y2']['STEP'], GPIO.LOW)
                time.sleep(STEP_DELAY)
                
        except Exception as e:
            logger.error(f"Error jogging Y-axis: {e}")
            messagebox.showerror("Motor Error", str(e))
            
    def _emergency_stop(self):
        """Emergency stop all motors."""
        try:
            for pins in self.motors.values():
                GPIO.output(pins['EN'], GPIO.HIGH)  # Disable all motors
            logger.warning("Emergency stop activated")
            messagebox.showwarning(
                "Emergency Stop",
                "All motors have been stopped"
            )
        except Exception as e:
            logger.error(f"Error during emergency stop: {e}")
            messagebox.showerror("Motor Error", str(e))
            
    def on_closing(self):
        """Handle window closing."""
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            try:
                # Disable all motors
                for pins in self.motors.values():
                    GPIO.output(pins['EN'], GPIO.HIGH)
                GPIO.cleanup()
                logger.info("Application closed")
                self.root.destroy()
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
                messagebox.showerror("Error", str(e))

def main():
    """Main entry point."""
    root = tk.Tk()
    app = MotorTestUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 