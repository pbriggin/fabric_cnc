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
        
        # Add homing buttons below jog controls
        self._create_homing_buttons()
        
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
        
        # Initialize key state
        self.key_state = {
            'Left': False,
            'Right': False,
            'Up': False,
            'Down': False,
            'Prior': False,  # Page Up
            'Next': False,   # Page Down
            'Home': False,
            'End': False
        }
        
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
        
        # Bind keys
        self._bind_keys()
        
        # Start control threads
        self.motor_thread = threading.Thread(target=self._motor_control_loop, daemon=True)
        self.motor_thread.start()
        self.key_thread = threading.Thread(target=self._key_poll_loop, daemon=True)
        self.key_thread.start()
        
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
        up_btn.bind('<ButtonPress>', lambda e: self._update_key_state('Up', True))
        up_btn.bind('<ButtonRelease>', lambda e: self._update_key_state('Up', False))
        
        down_btn = ttk.Button(frame, text="↓")
        down_btn.grid(row=2, column=1, padx=2, pady=2)
        down_btn.bind('<ButtonPress>', lambda e: self._update_key_state('Down', True))
        down_btn.bind('<ButtonRelease>', lambda e: self._update_key_state('Down', False))
        
        left_btn = ttk.Button(frame, text="←")
        left_btn.grid(row=1, column=0, padx=2, pady=2)
        left_btn.bind('<ButtonPress>', lambda e: self._update_key_state('Left', True))
        left_btn.bind('<ButtonRelease>', lambda e: self._update_key_state('Left', False))
        
        right_btn = ttk.Button(frame, text="→")
        right_btn.grid(row=1, column=2, padx=2, pady=2)
        right_btn.bind('<ButtonPress>', lambda e: self._update_key_state('Right', True))
        right_btn.bind('<ButtonRelease>', lambda e: self._update_key_state('Right', False))
        
        # Z-axis controls
        pgup_btn = ttk.Button(frame, text="PgUp")
        pgup_btn.grid(row=0, column=3, padx=2, pady=2)
        pgup_btn.bind('<ButtonPress>', lambda e: self._update_key_state('Prior', True))
        pgup_btn.bind('<ButtonRelease>', lambda e: self._update_key_state('Prior', False))
        
        pgdn_btn = ttk.Button(frame, text="PgDn")
        pgdn_btn.grid(row=2, column=3, padx=2, pady=2)
        pgdn_btn.bind('<ButtonPress>', lambda e: self._update_key_state('Next', True))
        pgdn_btn.bind('<ButtonRelease>', lambda e: self._update_key_state('Next', False))
        
        home_btn = ttk.Button(frame, text="Home")
        home_btn.grid(row=0, column=4, padx=2, pady=2)
        home_btn.bind('<ButtonPress>', lambda e: self._update_key_state('Home', True))
        home_btn.bind('<ButtonRelease>', lambda e: self._update_key_state('Home', False))
        
        end_btn = ttk.Button(frame, text="End")
        end_btn.grid(row=2, column=4, padx=2, pady=2)
        end_btn.bind('<ButtonPress>', lambda e: self._update_key_state('End', True))
        end_btn.bind('<ButtonRelease>', lambda e: self._update_key_state('End', False))
        
        # Add key binding hints
        ttk.Label(frame, text="Use arrow keys to jog X/Y").grid(row=3, column=0, columnspan=3, pady=5)
        ttk.Label(frame, text="PgUp/Dn: Z Lift, Home/End: Z Rotate").grid(row=3, column=3, columnspan=2, pady=5)
        
        return frame

    def _create_homing_buttons(self):
        """Create homing buttons for X and Y axes."""
        home_frame = ttk.Frame(self.main_frame)
        home_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        ttk.Label(home_frame, text="Homing Controls:", font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=3, pady=(0, 5))
        ttk.Button(home_frame, text="Home X Axis", command=self._home_x_axis, style="Accent.TButton").grid(row=1, column=0, padx=10, pady=5)
        ttk.Button(home_frame, text="Home Y Axis", command=self._home_y_axis, style="Accent.TButton").grid(row=1, column=1, padx=10, pady=5)
        ttk.Button(home_frame, text="Move Away (X)", command=self._move_away_x, style="Accent.TButton").grid(row=2, column=0, padx=10, pady=5)
        ttk.Button(home_frame, text="Move Away (Y)", command=self._move_away_y, style="Accent.TButton").grid(row=2, column=1, padx=10, pady=5)

    def _create_emergency_stop(self):
        """Create emergency stop button."""
        ttk.Button(
            self.main_frame,
            text="EMERGENCY STOP",
            command=self._emergency_stop,
            style="Emergency.TButton"
        ).grid(row=2, column=0, sticky=(tk.W, tk.E), padx=5, pady=10)

    def _bind_keys(self):
        """Bind arrow keys for jogging."""
        for key in self.key_map:
            self.root.bind(f'<{key}>', lambda e, k=key: self._update_key_state(k, True))
            self.root.bind(f'<KeyRelease-{key}>', lambda e, k=key: self._update_key_state(k, False))

    def _update_key_state(self, key, state):
        """Update the state of a key."""
        if key in self.key_state:
            self.key_state[key] = state

    def _key_poll_loop(self):
        """Poll key states and update motor control."""
        while not self.stop_event.is_set():
            try:
                # Check for active keys
                active_keys = [k for k, v in self.key_state.items() if v]
                
                if active_keys:
                    # Get the first active key
                    key = active_keys[0]
                    motor, direction = self.key_map[key]
                    
                    # Start motor if not already running
                    if not self.motor_state['active']:
                        self.motor_state['active'] = True
                        self.motor_state['motor'] = motor
                        self.motor_state['direction'] = direction
                        self.motor_state['last_change'] = time.time()
                        logger.info(f"Starting continuous jog for {motor} {'forward' if direction else 'reverse'}")
                else:
                    # Stop motor if no keys are pressed
                    if self.motor_state['active']:
                        self.motor_state['active'] = False
                        self.motor_state['motor'] = None
                        self.motor_state['direction'] = None
                        logger.info("Stopping jog")
                
                time.sleep(0.01)  # Poll every 10ms
                
            except Exception as e:
                logger.error(f"Error in key poll loop: {e}")
                self.motor_state['active'] = False
                self.motor_state['motor'] = None
                self.motor_state['direction'] = None

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

    def _home_x_axis(self):
        """Home the X axis using hall effect sensor on pin 20."""
        HALL_X = 20
        MOTOR = self.motors['X']
        logger.info("Starting X homing...")
        GPIO.setup(HALL_X, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.output(MOTOR['EN'], GPIO.LOW)
        
        # Homing parameters
        FAST_DELAY = 0.0005  # 0.5ms for fast movement (was 0.2ms)
        SLOW_DELAY = 0.001   # 1ms for precise homing
        BACKOFF_STEPS = 500  # Steps to back off from sensor
        
        print(f"[HALL X] Initial state: {'LOW (triggered)' if GPIO.input(HALL_X) == GPIO.LOW else 'HIGH (not triggered)'}")
        
        # Test sensor before starting
        print(f"[HALL X] Pre-movement sensor test:")
        for i in range(5):
            sensor_state = GPIO.input(HALL_X)
            print(f"  Test {i+1}: {'LOW' if sensor_state == GPIO.LOW else 'HIGH'}")
            time.sleep(0.1)
        
        # Step 1: Fast approach to find sensor
        print(f"[HALL X] Step 1: Fast approach to find sensor...")
        GPIO.output(MOTOR['DIR'], GPIO.HIGH)  # Negative direction (toward home)
        
        steps_count = 0
        sensor_triggered = False
        while not sensor_triggered and steps_count < 10000:
            GPIO.output(MOTOR['STEP'], GPIO.HIGH)
            time.sleep(FAST_DELAY/2)
            GPIO.output(MOTOR['STEP'], GPIO.LOW)
            time.sleep(FAST_DELAY/2)
            steps_count += 1
            
            # Check sensor state
            sensor_state = GPIO.input(HALL_X)
            if sensor_state == GPIO.LOW:
                sensor_triggered = True
                print(f"[HALL X] Sensor found at step {steps_count}!")
                break
            
            # Print progress every 1000 steps
            if steps_count % 1000 == 0:
                print(f"[HALL X] Fast approach: {steps_count} steps - Sensor: {'LOW' if sensor_state == GPIO.LOW else 'HIGH'}")
        
        if not sensor_triggered:
            print(f"[HALL X] Homing failed - sensor not found in fast approach")
            logger.warning("X homing failed - sensor not found")
            messagebox.showwarning("Homing Failed", "X axis homing failed - sensor not found")
            return
        
        # Step 2: Back off from sensor
        print(f"[HALL X] Step 2: Backing off {BACKOFF_STEPS} steps from sensor...")
        GPIO.output(MOTOR['DIR'], GPIO.LOW)  # Positive direction (away from home)
        
        for i in range(BACKOFF_STEPS):
            GPIO.output(MOTOR['STEP'], GPIO.HIGH)
            time.sleep(FAST_DELAY/2)
            GPIO.output(MOTOR['STEP'], GPIO.LOW)
            time.sleep(FAST_DELAY/2)
            
            if i % 100 == 0:
                print(f"[HALL X] Backoff progress: {i}/{BACKOFF_STEPS} steps")
        
        # Verify sensor is no longer triggered
        sensor_state = GPIO.input(HALL_X)
        print(f"[HALL X] After backoff - Sensor: {'LOW' if sensor_state == GPIO.LOW else 'HIGH'}")
        
        # Step 3: Slow re-home for precise positioning
        print(f"[HALL X] Step 3: Slow re-home for precise positioning...")
        GPIO.output(MOTOR['DIR'], GPIO.HIGH)  # Negative direction (toward home)
        
        final_steps = 0
        sensor_triggered = False
        while not sensor_triggered and final_steps < 2000:  # Limit for slow approach
            GPIO.output(MOTOR['STEP'], GPIO.HIGH)
            time.sleep(SLOW_DELAY/2)
            GPIO.output(MOTOR['STEP'], GPIO.LOW)
            time.sleep(SLOW_DELAY/2)
            final_steps += 1
            
            # Check sensor state
            sensor_state = GPIO.input(HALL_X)
            if sensor_state == GPIO.LOW:
                sensor_triggered = True
                print(f"[HALL X] Precise home position found at {final_steps} slow steps!")
                break
            
            if final_steps % 100 == 0:
                print(f"[HALL X] Slow approach: {final_steps} steps - Sensor: {'LOW' if sensor_state == GPIO.LOW else 'HIGH'}")
        
        # Final analysis
        total_steps = steps_count + BACKOFF_STEPS + final_steps
        print(f"[HALL X] Final analysis:")
        print(f"  Fast approach: {steps_count} steps")
        print(f"  Backoff: {BACKOFF_STEPS} steps")
        print(f"  Slow re-home: {final_steps} steps")
        print(f"  Total steps: {total_steps}")
        print(f"  Final sensor state: {'LOW' if GPIO.input(HALL_X) == GPIO.LOW else 'HIGH'}")
        
        # Test sensor stability after homing
        print(f"[HALL X] Post-homing sensor test:")
        for i in range(5):
            sensor_state = GPIO.input(HALL_X)
            print(f"  Test {i+1}: {'LOW' if sensor_state == GPIO.LOW else 'HIGH'}")
            time.sleep(0.1)
        
        if sensor_triggered:
            print(f"[HALL X] Homing completed successfully!")
            logger.info(f"X homed successfully in {total_steps} total steps")
            messagebox.showinfo("Homing Complete", f"X axis homed successfully!\nFast: {steps_count} steps\nBackoff: {BACKOFF_STEPS} steps\nSlow: {final_steps} steps\nTotal: {total_steps} steps")
        else:
            print(f"[HALL X] Homing failed - sensor not found in slow approach")
            logger.warning("X homing failed - sensor not found in slow approach")
            messagebox.showwarning("Homing Failed", "X axis homing failed - sensor not found in slow approach")

    def _home_y_axis(self):
        """Home the Y axis using hall effect sensors on pins 21 (Y1) and 16 (Y2)."""
        HALL_Y1 = 21
        HALL_Y2 = 16
        MOTOR1 = self.motors['Y1']
        MOTOR2 = self.motors['Y2']
        logger.info("Starting Y homing...")
        GPIO.setup(HALL_Y1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(HALL_Y2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.output(MOTOR1['EN'], GPIO.LOW)
        GPIO.output(MOTOR2['EN'], GPIO.LOW)
        
        # Homing parameters
        FAST_DELAY = 0.0005  # 0.5ms for fast movement (was 0.2ms)
        SLOW_DELAY = 0.001   # 1ms for precise homing
        BACKOFF_STEPS = 500  # Steps to back off from sensor
        
        print(f"[HALL Y] Initial state - Y1: {'LOW' if GPIO.input(HALL_Y1) == GPIO.LOW else 'HIGH'}, Y2: {'LOW' if GPIO.input(HALL_Y2) == GPIO.LOW else 'HIGH'}")
        
        # Test sensors before starting
        print(f"[HALL Y] Pre-movement sensor test:")
        for i in range(5):
            y1_state = GPIO.input(HALL_Y1)
            y2_state = GPIO.input(HALL_Y2)
            print(f"  Test {i+1}: Y1:{'LOW' if y1_state == GPIO.LOW else 'HIGH'}, Y2:{'LOW' if y2_state == GPIO.LOW else 'HIGH'}")
            time.sleep(0.1)
        
        # Step 1: Fast approach to find sensors
        print(f"[HALL Y] Step 1: Fast approach to find sensors...")
        GPIO.output(MOTOR1['DIR'], GPIO.LOW)   # Negative direction for Y1
        GPIO.output(MOTOR2['DIR'], GPIO.HIGH)  # Negative direction for Y2
        
        steps_count = 0
        y1_triggered = False
        y2_triggered = False
        
        while not (y1_triggered or y2_triggered) and steps_count < 10000:
            GPIO.output(MOTOR1['STEP'], GPIO.HIGH)
            GPIO.output(MOTOR2['STEP'], GPIO.HIGH)
            time.sleep(FAST_DELAY/2)
            GPIO.output(MOTOR1['STEP'], GPIO.LOW)
            GPIO.output(MOTOR2['STEP'], GPIO.LOW)
            time.sleep(FAST_DELAY/2)
            steps_count += 1
            
            # Check sensor states
            y1_state = GPIO.input(HALL_Y1)
            y2_state = GPIO.input(HALL_Y2)
            
            if y1_state == GPIO.LOW and not y1_triggered:
                y1_triggered = True
                print(f"[HALL Y] Y1 sensor found at step {steps_count}!")
            
            if y2_state == GPIO.LOW and not y2_triggered:
                y2_triggered = True
                print(f"[HALL Y] Y2 sensor found at step {steps_count}!")
            
            # Print progress every 1000 steps
            if steps_count % 1000 == 0:
                print(f"[HALL Y] Fast approach: {steps_count} steps - Y1:{'LOW' if y1_state == GPIO.LOW else 'HIGH'}, Y2:{'LOW' if y2_state == GPIO.LOW else 'HIGH'}")
        
        if not (y1_triggered or y2_triggered):
            print(f"[HALL Y] Homing failed - sensors not found in fast approach")
            logger.warning("Y homing failed - sensors not found")
            messagebox.showwarning("Homing Failed", "Y axis homing failed - sensors not found")
            return
        
        # Step 2: Back off from sensors
        print(f"[HALL Y] Step 2: Backing off {BACKOFF_STEPS} steps from sensors...")
        GPIO.output(MOTOR1['DIR'], GPIO.HIGH)  # Positive direction for Y1
        GPIO.output(MOTOR2['DIR'], GPIO.LOW)   # Positive direction for Y2
        
        for i in range(BACKOFF_STEPS):
            GPIO.output(MOTOR1['STEP'], GPIO.HIGH)
            GPIO.output(MOTOR2['STEP'], GPIO.HIGH)
            time.sleep(FAST_DELAY/2)
            GPIO.output(MOTOR1['STEP'], GPIO.LOW)
            GPIO.output(MOTOR2['STEP'], GPIO.LOW)
            time.sleep(FAST_DELAY/2)
            
            if i % 100 == 0:
                print(f"[HALL Y] Backoff progress: {i}/{BACKOFF_STEPS} steps")
        
        # Verify sensors are no longer triggered
        y1_state = GPIO.input(HALL_Y1)
        y2_state = GPIO.input(HALL_Y2)
        print(f"[HALL Y] After backoff - Y1: {'LOW' if y1_state == GPIO.LOW else 'HIGH'}, Y2: {'LOW' if y2_state == GPIO.LOW else 'HIGH'}")
        
        # Step 3: Slow re-home for precise positioning
        print(f"[HALL Y] Step 3: Slow re-home for precise positioning...")
        GPIO.output(MOTOR1['DIR'], GPIO.LOW)   # Negative direction for Y1
        GPIO.output(MOTOR2['DIR'], GPIO.HIGH)  # Negative direction for Y2
        
        final_steps = 0
        y1_triggered = False
        y2_triggered = False
        
        while not (y1_triggered or y2_triggered) and final_steps < 2000:  # Limit for slow approach
            GPIO.output(MOTOR1['STEP'], GPIO.HIGH)
            GPIO.output(MOTOR2['STEP'], GPIO.HIGH)
            time.sleep(SLOW_DELAY/2)
            GPIO.output(MOTOR1['STEP'], GPIO.LOW)
            GPIO.output(MOTOR2['STEP'], GPIO.LOW)
            time.sleep(SLOW_DELAY/2)
            final_steps += 1
            
            # Check sensor states
            y1_state = GPIO.input(HALL_Y1)
            y2_state = GPIO.input(HALL_Y2)
            
            if y1_state == GPIO.LOW and not y1_triggered:
                y1_triggered = True
                print(f"[HALL Y] Y1 precise home position found at {final_steps} slow steps!")
            
            if y2_state == GPIO.LOW and not y2_triggered:
                y2_triggered = True
                print(f"[HALL Y] Y2 precise home position found at {final_steps} slow steps!")
            
            if final_steps % 100 == 0:
                print(f"[HALL Y] Slow approach: {final_steps} steps - Y1:{'LOW' if y1_state == GPIO.LOW else 'HIGH'}, Y2:{'LOW' if y2_state == GPIO.LOW else 'HIGH'}")
        
        # Final analysis
        total_steps = steps_count + BACKOFF_STEPS + final_steps
        print(f"[HALL Y] Final analysis:")
        print(f"  Fast approach: {steps_count} steps")
        print(f"  Backoff: {BACKOFF_STEPS} steps")
        print(f"  Slow re-home: {final_steps} steps")
        print(f"  Total steps: {total_steps}")
        print(f"  Y1 triggered: {y1_triggered}")
        print(f"  Y2 triggered: {y2_triggered}")
        print(f"  Final Y1 state: {'LOW' if GPIO.input(HALL_Y1) == GPIO.LOW else 'HIGH'}")
        print(f"  Final Y2 state: {'LOW' if GPIO.input(HALL_Y2) == GPIO.LOW else 'HIGH'}")
        
        # Test sensor stability after homing
        print(f"[HALL Y] Post-homing sensor test:")
        for i in range(5):
            y1_state = GPIO.input(HALL_Y1)
            y2_state = GPIO.input(HALL_Y2)
            print(f"  Test {i+1}: Y1:{'LOW' if y1_state == GPIO.LOW else 'HIGH'}, Y2:{'LOW' if y2_state == GPIO.LOW else 'HIGH'}")
            time.sleep(0.1)
        
        GPIO.output(MOTOR1['EN'], GPIO.HIGH)
        GPIO.output(MOTOR2['EN'], GPIO.HIGH)
        
        if y1_triggered or y2_triggered:
            print(f"[HALL Y] Homing completed successfully!")
            logger.info(f"Y homed successfully in {total_steps} total steps")
            messagebox.showinfo("Homing Complete", f"Y axis homed successfully!\nFast: {steps_count} steps\nBackoff: {BACKOFF_STEPS} steps\nSlow: {final_steps} steps\nTotal: {total_steps} steps")
        else:
            print(f"[HALL Y] Homing failed - sensors not found in slow approach")
            logger.warning("Y homing failed - sensors not found in slow approach")
            messagebox.showwarning("Homing Failed", "Y axis homing failed - sensors not found in slow approach")

    def _move_away_x(self):
        """Move X axis away from home position for testing."""
        MOTOR = self.motors['X']
        logger.info("Moving X axis away from home...")
        
        # Enable motor
        GPIO.output(MOTOR['EN'], GPIO.LOW)
        
        # Move in positive direction (away from home)
        GPIO.output(MOTOR['DIR'], GPIO.LOW)  # Positive direction
        
        # Move 2000 steps (about 25mm)
        steps = 2000
        delay = 0.0005  # 0.5ms delay
        
        print(f"[MOVE X] Moving {steps} steps away from home...")
        for i in range(steps):
            GPIO.output(MOTOR['STEP'], GPIO.HIGH)
            time.sleep(delay/2)
            GPIO.output(MOTOR['STEP'], GPIO.LOW)
            time.sleep(delay/2)
            
            if i % 500 == 0:
                print(f"[MOVE X] Progress: {i}/{steps} steps")
        
        # Disable motor
        GPIO.output(MOTOR['EN'], GPIO.HIGH)
        print(f"[MOVE X] Moved {steps} steps away from home")
        logger.info(f"X axis moved {steps} steps away from home")
        messagebox.showinfo("Move Complete", f"X axis moved {steps} steps away from home")

    def _move_away_y(self):
        """Move Y axis away from home position for testing."""
        MOTOR1 = self.motors['Y1']
        MOTOR2 = self.motors['Y2']
        logger.info("Moving Y axis away from home...")
        
        # Enable motors
        GPIO.output(MOTOR1['EN'], GPIO.LOW)
        GPIO.output(MOTOR2['EN'], GPIO.LOW)
        
        # Move in positive direction (away from home)
        GPIO.output(MOTOR1['DIR'], GPIO.HIGH)  # Positive direction for Y1
        GPIO.output(MOTOR2['DIR'], GPIO.LOW)   # Positive direction for Y2
        
        # Move 2000 steps (about 25mm)
        steps = 2000
        delay = 0.0005  # 0.5ms delay
        
        print(f"[MOVE Y] Moving {steps} steps away from home...")
        for i in range(steps):
            GPIO.output(MOTOR1['STEP'], GPIO.HIGH)
            GPIO.output(MOTOR2['STEP'], GPIO.HIGH)
            time.sleep(delay/2)
            GPIO.output(MOTOR1['STEP'], GPIO.LOW)
            GPIO.output(MOTOR2['STEP'], GPIO.LOW)
            time.sleep(delay/2)
            
            if i % 500 == 0:
                print(f"[MOVE Y] Progress: {i}/{steps} steps")
        
        # Disable motors
        GPIO.output(MOTOR1['EN'], GPIO.HIGH)
        GPIO.output(MOTOR2['EN'], GPIO.HIGH)
        print(f"[MOVE Y] Moved {steps} steps away from home")
        logger.info(f"Y axis moved {steps} steps away from home")
        messagebox.showinfo("Move Complete", f"Y axis moved {steps} steps away from home")

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