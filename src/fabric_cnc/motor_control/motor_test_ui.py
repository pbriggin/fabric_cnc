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

# Disable GPIO warnings
GPIO.setwarnings(False)

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
        
        # Setup motor pins
        self._setup_motors()
        
        # Create jog controls
        self._create_jog_controls()
        
        # Create emergency stop button
        self._create_emergency_stop()
        
        # Initialize motor control
        self.stop_event = threading.Event()
        self.motor_state = {
            'active': False,
            'motor': None,
            'direction': None,
            'last_change': 0
        }
        self.key_state = {}  # Track key states
        self.motor_thread = threading.Thread(target=self._motor_control_loop, daemon=True)
        self.motor_thread.start()
        
        # Bind arrow keys
        self._bind_keys()
        
        logger.info("Motor test UI initialized")

    def _bind_keys(self):
        """Bind arrow keys for jogging."""
        # Map keys to motor/direction
        self.key_map = {
            'Left': ('X', False),
            'Right': ('X', True),
            'Up': ('y_axis', True),
            'Down': ('y_axis', False),
            'Prior': ('Z_LIFT', True),  # Page Up
            'Next': ('Z_LIFT', False),  # Page Down
            'Home': ('Z_ROTATE', True),
            'End': ('Z_ROTATE', False)
        }
        
        # Bind all key events
        for key in self.key_map:
            self.root.bind(f'<{key}>', lambda e, k=key: self._handle_key_press(k))
            self.root.bind(f'<KeyRelease-{key}>', lambda e, k=key: self._handle_key_release(k))

    def _handle_key_press(self, key):
        """Handle key press events."""
        if key in self.key_map and key not in self.key_state:
            motor, direction = self.key_map[key]
            self.key_state[key] = True
            
            if not self.motor_state['active']:
                self.motor_state['active'] = True
                self.motor_state['motor'] = motor
                self.motor_state['direction'] = direction
                self.motor_state['last_change'] = time.time()
                logger.info(f"Starting continuous jog for {motor} {'forward' if direction else 'reverse'}")

    def _handle_key_release(self, key):
        """Handle key release events."""
        if key in self.key_map and key in self.key_state:
            motor, _ = self.key_map[key]
            del self.key_state[key]
            
            if not self.key_state and self.motor_state['active'] and self.motor_state['motor'] == motor:
                self.motor_state['active'] = False
                self.motor_state['motor'] = None
                self.motor_state['direction'] = None
                logger.info("Stopping jog")

    def _create_jog_controls(self):
        """Create jog control frame with arrow buttons."""
        frame = ttk.LabelFrame(self.main_frame, text="Jog Controls")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # Create arrow buttons in a grid
        up_btn = ttk.Button(frame, text="↑")
        up_btn.grid(row=0, column=1, padx=2, pady=2)
        up_btn.bind('<ButtonPress>', lambda e: self._handle_key_press('Up'))
        up_btn.bind('<ButtonRelease>', lambda e: self._handle_key_release('Up'))
        
        down_btn = ttk.Button(frame, text="↓")
        down_btn.grid(row=2, column=1, padx=2, pady=2)
        down_btn.bind('<ButtonPress>', lambda e: self._handle_key_press('Down'))
        down_btn.bind('<ButtonRelease>', lambda e: self._handle_key_release('Down'))
        
        left_btn = ttk.Button(frame, text="←")
        left_btn.grid(row=1, column=0, padx=2, pady=2)
        left_btn.bind('<ButtonPress>', lambda e: self._handle_key_press('Left'))
        left_btn.bind('<ButtonRelease>', lambda e: self._handle_key_release('Left'))
        
        right_btn = ttk.Button(frame, text="→")
        right_btn.grid(row=1, column=2, padx=2, pady=2)
        right_btn.bind('<ButtonPress>', lambda e: self._handle_key_press('Right'))
        right_btn.bind('<ButtonRelease>', lambda e: self._handle_key_release('Right'))
        
        # Z-axis controls
        pgup_btn = ttk.Button(frame, text="PgUp")
        pgup_btn.grid(row=0, column=3, padx=2, pady=2)
        pgup_btn.bind('<ButtonPress>', lambda e: self._handle_key_press('Prior'))
        pgup_btn.bind('<ButtonRelease>', lambda e: self._handle_key_release('Prior'))
        
        pgdn_btn = ttk.Button(frame, text="PgDn")
        pgdn_btn.grid(row=2, column=3, padx=2, pady=2)
        pgdn_btn.bind('<ButtonPress>', lambda e: self._handle_key_press('Next'))
        pgdn_btn.bind('<ButtonRelease>', lambda e: self._handle_key_release('Next'))
        
        home_btn = ttk.Button(frame, text="Home")
        home_btn.grid(row=0, column=4, padx=2, pady=2)
        home_btn.bind('<ButtonPress>', lambda e: self._handle_key_press('Home'))
        home_btn.bind('<ButtonRelease>', lambda e: self._handle_key_release('Home'))
        
        end_btn = ttk.Button(frame, text="End")
        end_btn.grid(row=2, column=4, padx=2, pady=2)
        end_btn.bind('<ButtonPress>', lambda e: self._handle_key_press('End'))
        end_btn.bind('<ButtonRelease>', lambda e: self._handle_key_release('End'))
        
        # Add key binding hints
        ttk.Label(frame, text="Use arrow keys to jog X/Y").grid(row=3, column=0, columnspan=3, pady=5)
        ttk.Label(frame, text="PgUp/Dn: Z Lift, Home/End: Z Rotate").grid(row=3, column=3, columnspan=2, pady=5)
        
        return frame

    def _motor_control_loop(self):
        """Main motor control loop."""
        while not self.stop_event.is_set():
            try:
                if not self.motor_state['active']:
                    time.sleep(0.001)  # Small delay when idle
                    continue
                
                if self.motor_state['motor'] == 'y_axis':
                    # Set directions (Y1 is reversed)
                    GPIO.output(self.motors['Y1']['DIR'], GPIO.LOW if self.motor_state['direction'] else GPIO.HIGH)
                    GPIO.output(self.motors['Y2']['DIR'], GPIO.HIGH if self.motor_state['direction'] else GPIO.LOW)
                    
                    # Step both motors
                    GPIO.output(self.motors['Y1']['STEP'], GPIO.HIGH)
                    GPIO.output(self.motors['Y2']['STEP'], GPIO.HIGH)
                    time.sleep(STEP_DELAY/2)
                    GPIO.output(self.motors['Y1']['STEP'], GPIO.LOW)
                    GPIO.output(self.motors['Y2']['STEP'], GPIO.LOW)
                    time.sleep(STEP_DELAY/2)
                else:
                    pins = self.motors[self.motor_state['motor']]
                    
                    # Set direction (reverse for Y1 and X)
                    if self.motor_state['motor'] in ['Y1', 'X']:
                        direction = not self.motor_state['direction']
                    else:
                        direction = self.motor_state['direction']
                    GPIO.output(pins['DIR'], GPIO.HIGH if direction else GPIO.LOW)
                    
                    # Step pulse
                    GPIO.output(pins['STEP'], GPIO.HIGH)
                    time.sleep(STEP_DELAY/2)
                    GPIO.output(pins['STEP'], GPIO.LOW)
                    time.sleep(STEP_DELAY/2)
                
            except Exception as e:
                logger.error(f"Error in motor control loop: {e}")
                self.motor_state['active'] = False
                self.motor_state['motor'] = None
                self.motor_state['direction'] = None

    def _setup_motors(self):
        """Setup GPIO pins for all motors."""
        for motor, pins in self.motors.items():
            GPIO.setup(pins['STEP'], GPIO.OUT)
            GPIO.setup(pins['DIR'], GPIO.OUT)
            GPIO.setup(pins['EN'], GPIO.OUT)
            GPIO.output(pins['EN'], GPIO.LOW)  # Enable motors
            GPIO.output(pins['STEP'], GPIO.LOW)
            GPIO.output(pins['DIR'], GPIO.LOW)
            logger.info(f"Setup {motor} motor pins")

    def _create_emergency_stop(self):
        """Create emergency stop button."""
        frame = ttk.Frame(self.main_frame)
        frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        stop_btn = ttk.Button(frame, text="EMERGENCY STOP", style='Emergency.TButton')
        stop_btn.grid(row=0, column=0, sticky=(tk.W, tk.E))
        stop_btn.bind('<Button-1>', self._emergency_stop)
        
        # Create emergency stop style
        style = ttk.Style()
        style.configure('Emergency.TButton', background='red', foreground='white')
        
        return frame

    def _emergency_stop(self, event=None):
        """Handle emergency stop button press."""
        logger.warning("Emergency stop activated")
        self.stop_event.set()
        self.motor_state['active'] = False
        self.motor_state['motor'] = None
        self.motor_state['direction'] = None
        
        # Disable all motors
        for motor, pins in self.motors.items():
            GPIO.output(pins['EN'], GPIO.HIGH)  # Disable motors
            GPIO.output(pins['STEP'], GPIO.LOW)
            GPIO.output(pins['DIR'], GPIO.LOW)
        
        messagebox.showerror("Emergency Stop", "All motors have been stopped!")
        self.root.destroy()

    def on_closing(self):
        """Handle window closing."""
        logger.info("Application closed")
        self.stop_event.set()
        self.root.destroy()

def main():
    """Main entry point."""
    root = tk.Tk()
    app = MotorTestUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 