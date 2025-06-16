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
import queue

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
        
        # Disable key repeat
        self.root.option_add('*TEntry*repeatRate', 0)
        self.root.option_add('*TEntry*repeatDelay', 0)
        
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
        self.last_event_time = {}  # Track last event time for each key
        self.event_delay = 0.5  # Minimum time between events in seconds
        self.motor_thread = threading.Thread(target=self._motor_control_loop, daemon=True)
        self.motor_thread.start()
        
        # Bind arrow keys
        self._bind_keys()
        
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
        up_btn.bind('<ButtonPress>', lambda e: self._handle_key_event(tk.Event(type='2', keysym='Up')))
        up_btn.bind('<ButtonRelease>', lambda e: self._handle_key_event(tk.Event(type='3', keysym='Up')))
        
        down_btn = ttk.Button(frame, text="↓")
        down_btn.grid(row=2, column=1, padx=2, pady=2)
        down_btn.bind('<ButtonPress>', lambda e: self._handle_key_event(tk.Event(type='2', keysym='Down')))
        down_btn.bind('<ButtonRelease>', lambda e: self._handle_key_event(tk.Event(type='3', keysym='Down')))
        
        left_btn = ttk.Button(frame, text="←")
        left_btn.grid(row=1, column=0, padx=2, pady=2)
        left_btn.bind('<ButtonPress>', lambda e: self._handle_key_event(tk.Event(type='2', keysym='Left')))
        left_btn.bind('<ButtonRelease>', lambda e: self._handle_key_event(tk.Event(type='3', keysym='Left')))
        
        right_btn = ttk.Button(frame, text="→")
        right_btn.grid(row=1, column=2, padx=2, pady=2)
        right_btn.bind('<ButtonPress>', lambda e: self._handle_key_event(tk.Event(type='2', keysym='Right')))
        right_btn.bind('<ButtonRelease>', lambda e: self._handle_key_event(tk.Event(type='3', keysym='Right')))
        
        # Z-axis controls
        pgup_btn = ttk.Button(frame, text="PgUp")
        pgup_btn.grid(row=0, column=3, padx=2, pady=2)
        pgup_btn.bind('<ButtonPress>', lambda e: self._handle_key_event(tk.Event(type='2', keysym='Prior')))
        pgup_btn.bind('<ButtonRelease>', lambda e: self._handle_key_event(tk.Event(type='3', keysym='Prior')))
        
        pgdn_btn = ttk.Button(frame, text="PgDn")
        pgdn_btn.grid(row=2, column=3, padx=2, pady=2)
        pgdn_btn.bind('<ButtonPress>', lambda e: self._handle_key_event(tk.Event(type='2', keysym='Next')))
        pgdn_btn.bind('<ButtonRelease>', lambda e: self._handle_key_event(tk.Event(type='3', keysym='Next')))
        
        home_btn = ttk.Button(frame, text="Home")
        home_btn.grid(row=0, column=4, padx=2, pady=2)
        home_btn.bind('<ButtonPress>', lambda e: self._handle_key_event(tk.Event(type='2', keysym='Home')))
        home_btn.bind('<ButtonRelease>', lambda e: self._handle_key_event(tk.Event(type='3', keysym='Home')))
        
        end_btn = ttk.Button(frame, text="End")
        end_btn.grid(row=2, column=4, padx=2, pady=2)
        end_btn.bind('<ButtonPress>', lambda e: self._handle_key_event(tk.Event(type='2', keysym='End')))
        end_btn.bind('<ButtonRelease>', lambda e: self._handle_key_event(tk.Event(type='3', keysym='End')))
        
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
        self.root.bind_all('<Key>', self._handle_key_event)
        self.root.bind_all('<KeyRelease>', self._handle_key_event)

    def _handle_key_event(self, event):
        """Handle all key events."""
        if event.keysym in self.key_map:
            current_time = time.time()
            motor, direction = self.key_map[event.keysym]
            
            if event.type == '2':  # KeyPress
                # Only filter key press events
                if event.keysym in self.last_event_time:
                    time_since_last = current_time - self.last_event_time[event.keysym]
                    if time_since_last < self.event_delay:
                        return
                
                self.last_event_time[event.keysym] = current_time
                
                if event.keysym not in self.key_state:
                    self.key_state[event.keysym] = True
                    if not self.motor_state['active']:
                        self.motor_state['active'] = True
                        self.motor_state['motor'] = motor
                        self.motor_state['direction'] = direction
                        self.motor_state['last_change'] = current_time
                        logger.info(f"Starting continuous jog for {motor} {'forward' if direction else 'reverse'}")
            
            elif event.type == '3':  # KeyRelease
                # Always process key release events
                if event.keysym in self.key_state:
                    del self.key_state[event.keysym]
                    if not self.key_state and self.motor_state['active'] and self.motor_state['motor'] == motor:
                        self.motor_state['active'] = False
                        self.motor_state['motor'] = None
                        self.motor_state['direction'] = None
                        logger.info("Stopping jog")

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

    def _disable_all_motors(self):
        """Disable all motors and cleanup GPIO."""
        try:
            # Stop the motor control thread
            self.stop_event.set()
            
            # Set GPIO mode before cleanup
            GPIO.setmode(GPIO.BCM)
            
            # Disable all motors
            for name, pins in self.motors.items():
                GPIO.output(pins['STEP'], GPIO.LOW)
                GPIO.output(pins['DIR'], GPIO.LOW)
                GPIO.output(pins['EN'], GPIO.HIGH)  # Disable motor
            
            # Double-check Y motors
            GPIO.output(self.motors['Y1']['STEP'], GPIO.LOW)
            GPIO.output(self.motors['Y1']['DIR'], GPIO.LOW)
            GPIO.output(self.motors['Y1']['EN'], GPIO.HIGH)
            GPIO.output(self.motors['Y2']['STEP'], GPIO.LOW)
            GPIO.output(self.motors['Y2']['DIR'], GPIO.LOW)
            GPIO.output(self.motors['Y2']['EN'], GPIO.HIGH)
            
            # Cleanup GPIO
            GPIO.cleanup()
            logger.info("All motors disabled and GPIO cleaned up")
        except Exception as e:
            logger.error(f"Error during motor cleanup: {e}")
            raise

    def _emergency_stop(self):
        """Emergency stop all motors."""
        try:
            # Stop the motor control thread
            self.stop_event.set()
            
            # Set GPIO mode before cleanup
            GPIO.setmode(GPIO.BCM)
            
            # Disable all motors
            for name, pins in self.motors.items():
                GPIO.output(pins['STEP'], GPIO.LOW)
                GPIO.output(pins['DIR'], GPIO.LOW)
                GPIO.output(pins['EN'], GPIO.HIGH)  # Disable motor
            
            # Double-check Y motors
            GPIO.output(self.motors['Y1']['STEP'], GPIO.LOW)
            GPIO.output(self.motors['Y1']['DIR'], GPIO.LOW)
            GPIO.output(self.motors['Y1']['EN'], GPIO.HIGH)
            GPIO.output(self.motors['Y2']['STEP'], GPIO.LOW)
            GPIO.output(self.motors['Y2']['DIR'], GPIO.LOW)
            GPIO.output(self.motors['Y2']['EN'], GPIO.HIGH)
            
            # Don't cleanup GPIO to keep pins in disabled state
            # GPIO.cleanup()
            
            logger.warning("Emergency stop activated")
        except Exception as e:
            logger.error(f"Error during emergency stop: {e}")
            messagebox.showerror("Motor Error", str(e))

    def on_closing(self):
        """Handle window closing."""
        try:
            self._emergency_stop()
            logger.info("Application closed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            messagebox.showerror("Error", str(e))
        finally:
            self.root.destroy()

def main():
    """Main entry point."""
    root = tk.Tk()
    app = MotorTestUI(root)
    try:
        root.mainloop()
    finally:
        # Use emergency stop to ensure motors are disabled
        app._emergency_stop()

if __name__ == "__main__":
    main() 