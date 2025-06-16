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
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Motor configuration
PULSES_PER_REV = 3200
STEP_DELAY = 0.00025  # 0.25ms between pulses = 2000 steps/sec
STEP_PULSE_WIDTH = 0.0001  # 0.1ms pulse width
STEP_CYCLE_DELAY = 0.0001  # 0.1ms delay after each step cycle
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
        
        # Setup motor pins
        self._setup_motors()
        
        # Create jog controls
        self._create_jog_controls()
        
        # Create emergency stop button
        self._create_emergency_stop()
        
        # Initialize jogging state
        self.jogging = False
        self.jog_thread = None
        
        # Bind arrow keys
        self.root.bind('<KeyPress>', self._handle_key_press)
        self.root.bind('<KeyRelease>', self._handle_key_release)
        
        logger.info("Motor test UI initialized")
        
    def _setup_motors(self):
        """Setup GPIO pins for all motors."""
        for name, pins in self.motors.items():
            # Setup GPIO pins
            GPIO.setup(pins['STEP'], GPIO.OUT)
            GPIO.setup(pins['DIR'], GPIO.OUT)
            GPIO.setup(pins['EN'], GPIO.OUT)
            
            # Initialize pins to safe state
            GPIO.output(pins['STEP'], GPIO.LOW)
            GPIO.output(pins['DIR'], GPIO.LOW)
            GPIO.output(pins['EN'], GPIO.LOW)  # Enable motor
            
    def _create_jog_controls(self):
        """Create jog control frame with arrow buttons."""
        frame = ttk.LabelFrame(self.main_frame, text="Jog Controls")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # Create arrow buttons in a grid
        up_btn = ttk.Button(frame, text="↑")
        up_btn.grid(row=0, column=1, padx=2, pady=2)
        up_btn.bind('<ButtonPress>', lambda e: self._start_jog_y_axis(True))
        up_btn.bind('<ButtonRelease>', lambda e: self._stop_jogging())
        
        down_btn = ttk.Button(frame, text="↓")
        down_btn.grid(row=2, column=1, padx=2, pady=2)
        down_btn.bind('<ButtonPress>', lambda e: self._start_jog_y_axis(False))
        down_btn.bind('<ButtonRelease>', lambda e: self._stop_jogging())
        
        left_btn = ttk.Button(frame, text="←")
        left_btn.grid(row=1, column=0, padx=2, pady=2)
        left_btn.bind('<ButtonPress>', lambda e: self._start_jog_motor('X', False))
        left_btn.bind('<ButtonRelease>', lambda e: self._stop_jogging())
        
        right_btn = ttk.Button(frame, text="→")
        right_btn.grid(row=1, column=2, padx=2, pady=2)
        right_btn.bind('<ButtonPress>', lambda e: self._start_jog_motor('X', True))
        right_btn.bind('<ButtonRelease>', lambda e: self._stop_jogging())
        
        # Z-axis controls
        pgup_btn = ttk.Button(frame, text="PgUp")
        pgup_btn.grid(row=0, column=3, padx=2, pady=2)
        pgup_btn.bind('<ButtonPress>', lambda e: self._start_jog_motor('Z_LIFT', True))
        pgup_btn.bind('<ButtonRelease>', lambda e: self._stop_jogging())
        
        pgdn_btn = ttk.Button(frame, text="PgDn")
        pgdn_btn.grid(row=2, column=3, padx=2, pady=2)
        pgdn_btn.bind('<ButtonPress>', lambda e: self._start_jog_motor('Z_LIFT', False))
        pgdn_btn.bind('<ButtonRelease>', lambda e: self._stop_jogging())
        
        home_btn = ttk.Button(frame, text="Home")
        home_btn.grid(row=0, column=4, padx=2, pady=2)
        home_btn.bind('<ButtonPress>', lambda e: self._start_jog_motor('Z_ROTATE', True))
        home_btn.bind('<ButtonRelease>', lambda e: self._stop_jogging())
        
        end_btn = ttk.Button(frame, text="End")
        end_btn.grid(row=2, column=4, padx=2, pady=2)
        end_btn.bind('<ButtonPress>', lambda e: self._start_jog_motor('Z_ROTATE', False))
        end_btn.bind('<ButtonRelease>', lambda e: self._stop_jogging())
        
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
        ).grid(row=1, column=0, sticky=(tk.W, tk.E), padx=5, pady=10)

    def _handle_key_press(self, event):
        """Handle key press events for continuous jogging."""
        if self.jogging:
            return
            
        if event.keysym == 'Up':
            self._start_jog_y_axis(True)
        elif event.keysym == 'Down':
            self._start_jog_y_axis(False)
        elif event.keysym == 'Left':
            self._start_jog_motor('X', False)
        elif event.keysym == 'Right':
            self._start_jog_motor('X', True)
        elif event.keysym == 'Prior':  # Page Up
            self._start_jog_motor('Z_LIFT', True)
        elif event.keysym == 'Next':   # Page Down
            self._start_jog_motor('Z_LIFT', False)
        elif event.keysym == 'Home':
            self._start_jog_motor('Z_ROTATE', True)
        elif event.keysym == 'End':
            self._start_jog_motor('Z_ROTATE', False)

    def _handle_key_release(self, event):
        """Handle key release events to stop jogging."""
        if event.keysym in ['Up', 'Down', 'Left', 'Right', 'Prior', 'Next', 'Home', 'End']:
            self._stop_jogging()

    def _start_jog_motor(self, name, direction):
        """Start continuous jogging for a single motor."""
        if self.jogging:
            return
            
        self.jogging = True
        self.jog_thread = threading.Thread(
            target=self._jog_motor_continuous,
            args=(name, direction),
            daemon=True
        )
        self.jog_thread.start()

    def _start_jog_y_axis(self, direction):
        """Start continuous jogging for Y axis."""
        if self.jogging:
            return
            
        self.jogging = True
        self.jog_thread = threading.Thread(
            target=self._jog_y_axis_continuous,
            args=(direction,),
            daemon=True
        )
        self.jog_thread.start()

    def _stop_jogging(self):
        """Stop continuous jogging."""
        self.jogging = False
        if self.jog_thread:
            self.jog_thread.join(timeout=0.1)
            self.jog_thread = None

    def _jog_motor_continuous(self, name, direction):
        """Continuously jog a motor until stopped."""
        try:
            logger.info(f"Starting continuous jog for {name} {'forward' if direction else 'reverse'}")
            pins = self.motors[name]
            
            # Set direction (reverse for Y1 and X)
            if name in ['Y1', 'X']:
                direction = not direction
            GPIO.output(pins['DIR'], GPIO.HIGH if direction else GPIO.LOW)
            time.sleep(0.001)  # Small delay after direction change
            
            # Step sequence
            while self.jogging:
                # Step pulse
                GPIO.output(pins['STEP'], GPIO.HIGH)
                time.sleep(STEP_PULSE_WIDTH)
                GPIO.output(pins['STEP'], GPIO.LOW)
                
                # Wait for next step
                time.sleep(STEP_DELAY - STEP_PULSE_WIDTH)
                
                # Small delay after each step cycle
                time.sleep(STEP_CYCLE_DELAY)
                
        except Exception as e:
            logger.error(f"Error jogging motor: {e}")
            messagebox.showerror("Motor Error", str(e))
        finally:
            self.jogging = False

    def _jog_y_axis_continuous(self, direction):
        """Continuously jog both Y motors until stopped."""
        try:
            logger.info(f"Starting continuous Y-axis jog {'forward' if direction else 'reverse'}")
            
            # Set directions (Y1 is reversed)
            GPIO.output(self.motors['Y1']['DIR'], GPIO.LOW if direction else GPIO.HIGH)
            GPIO.output(self.motors['Y2']['DIR'], GPIO.HIGH if direction else GPIO.LOW)
            time.sleep(0.001)  # Small delay after direction change
            
            # Step sequence
            while self.jogging:
                # Step both motors
                GPIO.output(self.motors['Y1']['STEP'], GPIO.HIGH)
                GPIO.output(self.motors['Y2']['STEP'], GPIO.HIGH)
                time.sleep(STEP_PULSE_WIDTH)
                GPIO.output(self.motors['Y1']['STEP'], GPIO.LOW)
                GPIO.output(self.motors['Y2']['STEP'], GPIO.LOW)
                
                # Wait for next step
                time.sleep(STEP_DELAY - STEP_PULSE_WIDTH)
                
                # Small delay after each step cycle
                time.sleep(STEP_CYCLE_DELAY)
                
        except Exception as e:
            logger.error(f"Error jogging Y-axis: {e}")
            messagebox.showerror("Motor Error", str(e))
        finally:
            self.jogging = False
            
    def _emergency_stop(self):
        """Emergency stop all motors."""
        try:
            self._stop_jogging()
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
                self._stop_jogging()
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