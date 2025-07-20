#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main application for Fabric CNC: DXF import, toolpath generation, visualization, and motor control UI.
Runs in simulation mode on non-RPi systems (no GPIO required).
"""

import os
import sys
import logging
import customtkinter as ctk
import threading
import platform
import time
import math
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox

# Try to import ezdxf for DXF parsing
try:
    from ezdxf.filemanagement import readfile
    import ezdxf
    EZDXF_AVAILABLE = True
    from ezdxf.math import Vec3
except ImportError:
    ezdxf = None
    EZDXF_AVAILABLE = False
    Vec3 = None

# Import motor control modules
try:
    from motor_control.motor_controller import MotorController
    MOTOR_IMPORTS_AVAILABLE = True
except ImportError:
    MOTOR_IMPORTS_AVAILABLE = False

# Import GPIO only if on Raspberry Pi
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

ON_RPI = platform.system() == 'Linux' and (os.uname().machine.startswith('arm') or os.uname().machine.startswith('aarch'))
SIMULATION_MODE = not ON_RPI or not MOTOR_IMPORTS_AVAILABLE

INCH_TO_MM = 25.4
X_MAX_MM = 68 * INCH_TO_MM
Y_MAX_MM = 45 * INCH_TO_MM
Z_MAX_MM = 2.5 * INCH_TO_MM
Z_UP_MM = 0.0
Z_DOWN_MM = 1.0
PLOT_BUFFER_IN = 1.0

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fabric_cnc.main_app")

# Material Design-inspired color palette (updated to user spec)
PRIMARY_COLOR = '#2196F3'  # Blue 500
PRIMARY_VARIANT = '#1976D2'  # Blue 700
SECONDARY_COLOR = '#4FC3F7'  # Light Blue 300
BACKGROUND = '#F5F5F5'
SURFACE = '#F5F5F5'
ON_PRIMARY = '#ffffff'
ON_SURFACE = '#222222'
ERROR_COLOR = '#b00020'

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# --- Motor simulation logic ---
class SimulatedMotorController:
    def __init__(self):
        self.position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'ROT': 0.0}
        self.lock = threading.Lock()
        self.is_homing = False

    def _clamp(self, axis, value):
        if axis == 'X':
            return max(-X_MAX_MM, min(value, X_MAX_MM))  # Allow negative X positions
        elif axis == 'Y':
            return max(-Y_MAX_MM, min(value, Y_MAX_MM))  # Allow negative Y positions
        elif axis == 'Z':
            return max(0.0, min(value, Z_MAX_MM))  # Keep Z positive only
        else:
            return value

    def jog(self, axis, delta):
        with self.lock:
            new_val = self.position[axis] + delta
            self.position[axis] = self._clamp(axis, new_val)
            logger.info(f"Jogged {axis} by {delta}mm. New pos: {self.position[axis]:.2f}")

    def home(self, axis):
        with self.lock:
            if self.is_homing:
                return False
            self.is_homing = True
            # Simulate homing delay
            time.sleep(2)
            if axis == 'X' or axis == 'Y':
                self.position[axis] = 0.0
            self.is_homing = False
            logger.info(f"Homed {axis} axis.")
            return True

    def home_all_synchronous(self):
        """Home all axes simultaneously (simulated)."""
        with self.lock:
            if self.is_homing:
                return False
            self.is_homing = True
            # Simulate homing delay
            time.sleep(2)
            self.position['X'] = 0.0
            self.position['Y'] = 0.0
            self.position['Z'] = 0.0
            self.position['ROT'] = 0.0
            self.is_homing = False
            logger.info("Homed all axes simultaneously.")
            return True

    def get_position(self):
        with self.lock:
            return dict(self.position)

    def estop(self):
        logger.warning("EMERGENCY STOP triggered (simulated)")

    def cleanup(self):
        """Clean up resources (simulated)."""
        logger.info("Simulated motor controller cleanup")

    def move_to(self, x=None, y=None, z=None, rot=None):
        with self.lock:
            if x is not None:
                self.position['X'] = self._clamp('X', x)
            if y is not None:
                self.position['Y'] = self._clamp('Y', y)
            if z is not None:
                self.position['Z'] = self._clamp('Z', z)
            if rot is not None:
                self.position['ROT'] = rot
            logger.info(f"Simulated move_to: X={self.position['X']:.2f}, Y={self.position['Y']:.2f}, Z={self.position['Z']:.2f}, ROT={self.position['ROT']:.2f}")

    def stop_movement(self):
        pass

# --- Real Motor Controller Wrapper ---
class RealMotorController:
    def __init__(self):
        self.motor_controller = MotorController()
        self.lock = threading.Lock()
        self.is_homing = False
        self.position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'ROT': 0.0}  # Track position manually

    def _clamp(self, axis, value):
        if axis == 'X':
            return max(-X_MAX_MM, min(value, X_MAX_MM))  # Allow negative X positions
        elif axis == 'Y':
            return max(-Y_MAX_MM, min(value, Y_MAX_MM))  # Allow negative Y positions
        elif axis == 'Z':
            return max(-Z_MAX_MM, min(value, Z_MAX_MM))  # Allow negative Z positions
        else:
            return value

    def jog(self, axis, delta):
        with self.lock:
            try:
                new_val = self.position[axis] + delta
                clamped_val = self._clamp(axis, new_val)
                move_delta = clamped_val - self.position[axis]
                if abs(move_delta) > 1e-6:
                    if axis == 'X':
                        self.motor_controller.move_distance(move_delta, 'X')
                    elif axis == 'Y':
                        self.motor_controller.move_distance(move_delta, 'Y')
                    elif axis == 'Z':
                        self.motor_controller.move_distance(move_delta, 'Z')
                    elif axis == 'ROT':
                        self.motor_controller.move_distance(move_delta, 'ROT')
                    self.position[axis] = clamped_val
                    logger.info(f"Jogged {axis} by {move_delta}mm")
            except Exception as e:
                logger.error(f"Jog error on {axis}: {e}")

    def home(self, axis):
        with self.lock:
            if self.is_homing:
                return False
            self.is_homing = True
            try:
                if axis == 'X':
                    self.motor_controller.home_axis('X')
                    self.position['X'] = 0.0
                    success = True
                elif axis == 'Y':
                    self.motor_controller.home_axis('Y')
                    self.position['Y'] = 0.0
                    success = True
                elif axis == 'Z':
                    self.motor_controller.home_axis('Z')
                    self.position['Z'] = 0.0
                    success = True
                elif axis == 'ROT':
                    self.motor_controller.home_axis('ROT')
                    self.position['ROT'] = 0.0
                    success = True
                else:
                    success = False
                self.is_homing = False
                return success
            except Exception as e:
                logger.error(f"Home error on {axis}: {e}")
                self.is_homing = False
                return False

    def home_all_synchronous(self):
        """Home all axes simultaneously."""
        with self.lock:
            if self.is_homing:
                return False
            self.is_homing = True
            try:
                self.motor_controller.home_all_synchronous()
                # Reset all positions to 0 after successful homing
                self.position['X'] = 0.0
                self.position['Y'] = 0.0
                self.position['Z'] = 0.0
                self.position['ROT'] = 0.0
                self.is_homing = False
                return True
            except Exception as e:
                logger.error(f"Synchronous home error: {e}")
                self.is_homing = False
                return False

    def get_position(self):
        with self.lock:
            return dict(self.position)
    
    def get_sensor_states(self):
        """Get current sensor states for debugging."""
        with self.lock:
            return self.motor_controller.get_sensor_states()

    def estop(self):
        try:
            # Emergency stop - stop movement and disable all motors
            self.motor_controller.stop_movement()
            self.motor_controller.cleanup()
            logger.warning("EMERGENCY STOP triggered - all motors disabled")
        except Exception as e:
            logger.error(f"E-stop error: {e}")

    def stop_movement(self):
        """Stop any ongoing movement immediately."""
        try:
            self.motor_controller.stop_movement()
            logger.info("Movement stopped")
        except Exception as e:
            logger.error(f"Stop movement error: {e}")

    def cleanup(self):
        try:
            # Use the motor controller's cleanup method to disable motors
            self.motor_controller.cleanup()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    def move_to(self, x=None, y=None, z=None, rot=None):
        with self.lock:
            # Calculate deltas for all axes
            delta_x = 0
            delta_y = 0
            delta_z = 0
            delta_rot = 0
            
            if x is not None:
                delta_x = x - self.position['X']
            if y is not None:
                delta_y = y - self.position['Y']
            if z is not None:
                delta_z = z - self.position['Z']
            if rot is not None:
                delta_rot = rot - self.position['ROT']
                logger.info(f"Rotation calculation: current={self.position['ROT']:.1f}°, target={rot:.1f}°, delta={delta_rot:.1f}°")
            
            # Use coordinated movement for X and Y, individual for Z and ROT
            if abs(delta_x) > 1e-6 or abs(delta_y) > 1e-6:
                logger.info(f"Calling coordinated movement: delta_x={delta_x:.2f}mm, delta_y={delta_y:.2f}mm, delta_rot={delta_rot:.2f}°")
                self.motor_controller.move_coordinated(
                    x_distance_mm=delta_x,
                    y_distance_mm=delta_y,
                    z_distance_mm=delta_z,
                    rot_distance_mm=delta_rot
                )
            else:
                # Only Z or ROT movement needed
                if abs(delta_z) > 1e-6:
                    self.motor_controller.move_distance(delta_z, 'Z')
                if abs(delta_rot) > 1e-6:
                    self.motor_controller.move_distance(delta_rot, 'ROT')
            
            # Update position tracking
            if x is not None:
                self.position['X'] = x
            if y is not None:
                self.position['Y'] = y
            if z is not None:
                self.position['Z'] = z
            if rot is not None:
                self.position['ROT'] = rot
            # logger.info(f"Real move_to: X={self.position['X']:.2f}, Y={self.position['Y']:.2f}, Z={self.position['Z']:.2f}, ROT={self.position['ROT']:.2f}")

class FabricCNCApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Fabric CNC (Material Design)")
        # Force fullscreen on startup - try multiple approaches
        try:
            self.root.attributes('-fullscreen', True)
        except:
            try:
                self.root.state('zoomed')
            except:
                pass
        self.root.configure(bg=BACKGROUND)
        self.jog_speed = 1.0 * INCH_TO_MM  # Default to 1 inch
        self.jog_speed_var = ctk.DoubleVar(value=1.0)  # Default to 1 inch
        self._arrow_key_state = {}
        self._arrow_key_after_ids = {}
        self._current_toolpath_idx = [0, 0]
        self._toolpath_step_count = 0
        self._current_toolpath_pos = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'ROT': 0.0}
        self.toolpaths = []
        self.motor_ctrl = SimulatedMotorController() if SIMULATION_MODE else RealMotorController()
        self._jog_in_progress = {'X': False, 'Y': False, 'Z': False, 'ROT': False}
        self._arrow_key_repeat_delay = 100
        # Initialize DXF-related attributes
        self.dxf_doc = None
        self.dxf_entities = []
        self.toolpath = []
        self._setup_ui()
        self._bind_arrow_keys()
        self._update_position_display()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        # Force fullscreen after UI setup
        self.root.after(100, lambda: self.root.attributes('-fullscreen', True))

    def _setup_ui(self):
        # App Bar
        self.app_bar = ctk.CTkFrame(self.root, fg_color=PRIMARY_COLOR, corner_radius=0, height=56)
        self.app_bar.pack(fill="x", side="top")
        self.title = ctk.CTkLabel(self.app_bar, text="Fabric CNC", text_color=ON_PRIMARY, font=("Arial", 16, "bold"))
        self.title.pack(side="left", padx=24, pady=12)
        
        # Close button
        close_button = ctk.CTkButton(self.app_bar, text="✕", width=40, height=30, 
                                   command=self._close_app, fg_color="transparent", 
                                   text_color=ON_PRIMARY, hover_color="#ff5a5f", corner_radius=6)
        close_button.pack(side="right", padx=24, pady=12)

        # Main layout
        self.main_frame = ctk.CTkFrame(self.root, fg_color=BACKGROUND)
        self.main_frame.pack(expand=True, fill="both", padx=0, pady=(0, 0))
        self.main_frame.grid_columnconfigure(1, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        # Left Toolbar
        self.left_toolbar = ctk.CTkFrame(self.main_frame, fg_color=SURFACE, corner_radius=12, width=180)
        self.left_toolbar.grid(row=0, column=0, sticky="nsw", padx=(24, 12), pady=24)
        # File & DXF section
        file_section = ctk.CTkFrame(self.left_toolbar, fg_color="#d0d0d0", corner_radius=8)
        file_section.pack(fill="x", padx=16, pady=(20, 10))
        ctk.CTkLabel(file_section, text="File & DXF", font=("Arial", 16, "bold"), text_color=PRIMARY_COLOR).pack(pady=(10, 10))
        ctk.CTkButton(file_section, text="Import DXF", command=self._import_dxf, fg_color=PRIMARY_COLOR, text_color=ON_PRIMARY, hover_color=PRIMARY_VARIANT, corner_radius=8, height=40, font=("Arial", 16, "bold")).pack(fill="x", padx=10, pady=6)
        ctk.CTkButton(file_section, text="Generate Toolpath", command=self._generate_toolpath, fg_color=SECONDARY_COLOR, text_color=ON_SURFACE, hover_color=PRIMARY_COLOR, corner_radius=8, height=40, font=("Arial", 16, "bold")).pack(fill="x", padx=10, pady=6)
        ctk.CTkButton(file_section, text="Preview Toolpath", command=self._preview_toolpath, fg_color=SURFACE, text_color=PRIMARY_COLOR, hover_color=SECONDARY_COLOR, corner_radius=8, height=40, font=("Arial", 16, "bold")).pack(fill="x", padx=10, pady=6)
        ctk.CTkButton(file_section, text="Run Toolpath", command=self._run_toolpath, fg_color=PRIMARY_COLOR, text_color=ON_PRIMARY, hover_color=PRIMARY_VARIANT, corner_radius=8, height=40, font=("Arial", 16, "bold")).pack(fill="x", padx=10, pady=6)
        ctk.CTkButton(file_section, text="E-Stop", command=self._estop, fg_color=ERROR_COLOR, text_color=ON_PRIMARY, hover_color="#ff5a5f", corner_radius=8, height=40, font=("Arial", 16, "bold")).pack(fill="x", padx=10, pady=(6, 10))
        
        # Status section
        status_section = ctk.CTkFrame(self.left_toolbar, fg_color="#d0d0d0", corner_radius=8)
        status_section.pack(fill="x", padx=16, pady=10)
        ctk.CTkLabel(status_section, text="Status:", font=("Arial", 16, "bold"), text_color=PRIMARY_COLOR).pack(pady=(10, 5))
        self.status_label = ctk.CTkLabel(status_section, text="Ready", font=("Arial", 16, "bold"), text_color=ON_SURFACE)
        self.status_label.pack(pady=(0, 10))

        # Center Canvas
        self.center_frame = ctk.CTkFrame(self.main_frame, fg_color=SURFACE, corner_radius=12)
        self.center_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 12), pady=24)
        self.center_frame.grid_columnconfigure(0, weight=1)
        self.center_frame.grid_rowconfigure(0, weight=1)
        self._setup_center_canvas()

        # Right Toolbar
        self.right_toolbar = ctk.CTkFrame(self.main_frame, fg_color=SURFACE, corner_radius=12, width=220)
        self.right_toolbar.grid(row=0, column=2, sticky="nse", padx=(12, 24), pady=24)
        ctk.CTkLabel(self.right_toolbar, text="Motor Controls", font=("Arial", 16, "bold"), text_color=PRIMARY_COLOR).pack(pady=(20, 10))
        # Jog controls section
        jog_section = ctk.CTkFrame(self.right_toolbar, fg_color="#d0d0d0", corner_radius=8)
        jog_section.pack(fill=ctk.X, padx=10, pady=8)
        # Configure grid for centered layout
        jog_section.grid_columnconfigure(0, weight=1)
        jog_section.grid_columnconfigure(1, weight=1)
        jog_section.grid_columnconfigure(2, weight=1)
        jog_section.grid_rowconfigure(0, weight=1)
        jog_section.grid_rowconfigure(1, weight=1)
        jog_section.grid_rowconfigure(2, weight=1)
        # Center the arrow buttons
        self._add_jog_button(jog_section, "↑", lambda: self._jog('Y', +self.jog_speed)).grid(row=0, column=1, padx=4, pady=4, sticky="nsew")
        self._add_jog_button(jog_section, "←", lambda: self._jog('X', -self.jog_speed)).grid(row=1, column=0, padx=4, pady=4, sticky="nsew")
        self._add_jog_button(jog_section, "→", lambda: self._jog('X', +self.jog_speed)).grid(row=1, column=2, padx=4, pady=4, sticky="nsew")
        self._add_jog_button(jog_section, "↓", lambda: self._jog('Y', -self.jog_speed)).grid(row=2, column=1, padx=4, pady=4, sticky="nsew")
        # Z and ROT controls section
        zrot_section = ctk.CTkFrame(self.right_toolbar, fg_color="#d0d0d0", corner_radius=8)
        zrot_section.pack(fill=ctk.X, padx=10, pady=(0, 8))
        # Configure grid for centered layout
        zrot_section.grid_columnconfigure(0, weight=1)
        zrot_section.grid_columnconfigure(1, weight=1)
        zrot_section.grid_columnconfigure(2, weight=1)
        zrot_section.grid_columnconfigure(3, weight=1)
        zrot_section.grid_rowconfigure(0, weight=1)
        # Center the Z and ROT buttons
        self._add_jog_button(zrot_section, "Z+", lambda: self._jog('Z', +1)).grid(row=0, column=0, padx=4, pady=4, sticky="nsew")
        self._add_jog_button(zrot_section, "Z-", lambda: self._jog('Z', -1)).grid(row=0, column=1, padx=4, pady=4, sticky="nsew")
        self._add_jog_button(zrot_section, "ROT+", lambda: self._jog('ROT', +5)).grid(row=0, column=2, padx=4, pady=4, sticky="nsew")
        self._add_jog_button(zrot_section, "ROT-", lambda: self._jog('ROT', -5)).grid(row=0, column=3, padx=4, pady=4, sticky="nsew")
        # Speed adjustment section
        speed_section = ctk.CTkFrame(self.right_toolbar, fg_color="#d0d0d0", corner_radius=8)
        speed_section.pack(fill=ctk.X, padx=10, pady=(0, 8))
        ctk.CTkLabel(speed_section, text="Jog Step (in)", font=("Arial", 16, "bold")).pack(side=ctk.LEFT, padx=10, pady=10)
        # Use range 0.1 to 5.0 inches with 0.1 increments
        self._jog_slider_scale = 0.1
        # Calculate initial slider value (1.0 inch = 10 steps)
        initial_slider_value = int(self.jog_speed_var.get() / self._jog_slider_scale)
        speed_slider = ctk.CTkSlider(speed_section, from_=1, to=50, number_of_steps=49, variable=None, width=120, command=lambda v: self._on_jog_slider(v))
        speed_slider.set(initial_slider_value)
        speed_slider.pack(side=ctk.LEFT, padx=5)
        speed_entry = ctk.CTkEntry(speed_section, textvariable=self.jog_speed_var, width=50)
        speed_entry.pack(side=ctk.LEFT, padx=5)
        self.jog_speed_var.trace_add('write', lambda *a: self._update_jog_speed())
        # Home controls section
        home_section = ctk.CTkFrame(self.right_toolbar, fg_color="#d0d0d0", corner_radius=8)
        home_section.pack(fill=ctk.X, padx=10, pady=8)
        ctk.CTkButton(home_section, text="Home X", command=lambda: self._home('X'), height=35, font=("Arial", 16, "bold")).pack(fill=ctk.X, padx=10, pady=2)
        ctk.CTkButton(home_section, text="Home Y", command=lambda: self._home('Y'), height=35, font=("Arial", 16, "bold")).pack(fill=ctk.X, padx=10, pady=2)
        ctk.CTkButton(home_section, text="Home Z", command=lambda: self._home('Z'), height=35, font=("Arial", 16, "bold")).pack(fill=ctk.X, padx=10, pady=2)
        ctk.CTkButton(home_section, text="Home ROT", command=lambda: self._home('ROT'), height=35, font=("Arial", 16, "bold")).pack(fill=ctk.X, padx=10, pady=2)
        ctk.CTkButton(home_section, text="Home All (Sync)", command=self._home_all, height=35, font=("Arial", 16, "bold")).pack(fill=ctk.X, padx=10, pady=2)
        # Coordinates display section
        coord_section = ctk.CTkFrame(self.right_toolbar, fg_color="#d0d0d0", corner_radius=8)
        coord_section.pack(fill=ctk.X, padx=10, pady=8)
        self.coord_label = ctk.CTkLabel(coord_section, text="", font=("Consolas", 16, "bold"), text_color=ON_SURFACE)
        self.coord_label.pack(pady=10)

    def _bind_arrow_keys(self):
        self.root.bind('<KeyPress-Left>', lambda e: self._on_arrow_press('Left'))
        self.root.bind('<KeyRelease-Left>', lambda e: self._on_arrow_release('Left'))
        self.root.bind('<KeyPress-Right>', lambda e: self._on_arrow_press('Right'))
        self.root.bind('<KeyRelease-Right>', lambda e: self._on_arrow_release('Right'))
        self.root.bind('<KeyPress-Up>', lambda e: self._on_arrow_press('Up'))
        self.root.bind('<KeyRelease-Up>', lambda e: self._on_arrow_release('Up'))
        self.root.bind('<KeyPress-Down>', lambda e: self._on_arrow_press('Down'))
        self.root.bind('<KeyRelease-Down>', lambda e: self._on_arrow_release('Down'))
        # Z axis controls
        self.root.bind('<KeyPress-Prior>', lambda e: self._on_arrow_press('Page_Up'))  # Page Up for Z+
        self.root.bind('<KeyRelease-Prior>', lambda e: self._on_arrow_release('Page_Up'))
        self.root.bind('<KeyPress-Next>', lambda e: self._on_arrow_press('Page_Down'))  # Page Down for Z-
        self.root.bind('<KeyRelease-Next>', lambda e: self._on_arrow_release('Page_Down'))
        # Rotation controls
        self.root.bind('<KeyPress-Home>', lambda e: self._on_arrow_press('Home'))  # Home key for ROT+
        self.root.bind('<KeyRelease-Home>', lambda e: self._on_arrow_release('Home'))
        self.root.bind('<KeyPress-End>', lambda e: self._on_arrow_press('End'))  # End key for ROT-
        self.root.bind('<KeyRelease-End>', lambda e: self._on_arrow_release('End'))
        # Bind Escape key to stop movement
        self.root.bind('<KeyPress-Escape>', lambda e: self._stop_movement())
        # Bind F11 to toggle full screen
        self.root.bind('<KeyPress-F11>', lambda e: self._toggle_fullscreen())
        # Bind Ctrl+Q to close app
        self.root.bind('<Control-q>', lambda e: self._close_app())
        # Bind window close button
        self.root.protocol("WM_DELETE_WINDOW", self._close_app)

    def _on_arrow_press(self, key):
        if not self._arrow_key_state.get(key, False):
            self._arrow_key_state[key] = True
            self._arrow_jog_loop(key)

    def _arrow_jog_loop(self, key):
        if not self._arrow_key_state.get(key, False):
            return
        axis = None
        delta = 0
        if key == 'Left':
            axis = 'X'
            delta = -self.jog_speed
        elif key == 'Right':
            axis = 'X'
            delta = self.jog_speed
        elif key == 'Up':
            axis = 'Y'
            delta = self.jog_speed
        elif key == 'Down':
            axis = 'Y'
            delta = -self.jog_speed
        elif key == 'Page_Up':
            axis = 'Z'
            delta = 1.0 * INCH_TO_MM  # 1 inch up
        elif key == 'Page_Down':
            axis = 'Z'
            delta = -1.0 * INCH_TO_MM  # 1 inch down
        elif key == 'Home':
            axis = 'ROT'
            delta = 5.0  # 5 degrees clockwise
        elif key == 'End':
            axis = 'ROT'
            delta = -5.0  # 5 degrees counter-clockwise
        if axis:
            if not self._jog_in_progress.get(axis, False):
                self._jog_in_progress[axis] = True
                self._jog_with_flag(axis, delta, key)
        # Schedule next iteration and store the after_id
        self._arrow_key_after_ids[key] = self.root.after(self._arrow_key_repeat_delay, lambda: self._arrow_jog_loop(key))

    def _jog_with_flag(self, axis, delta, key):
        try:
            self._jog(axis, delta)
        finally:
            self._jog_in_progress[axis] = False

    def _on_arrow_release(self, key):
        self._arrow_key_state[key] = False
        # Cancel any pending after() call for this key
        if self._arrow_key_after_ids.get(key) is not None:
            self.root.after_cancel(self._arrow_key_after_ids[key])
            self._arrow_key_after_ids[key] = None
        # Reset jog-in-progress for the axis
        if key in ['Left', 'Right']:
            self._jog_in_progress['X'] = False
        elif key in ['Up', 'Down']:
            self._jog_in_progress['Y'] = False
        elif key in ['Page_Up', 'Page_Down']:
            self._jog_in_progress['Z'] = False
        elif key in ['Home', 'End']:
            self._jog_in_progress['ROT'] = False



    # --- Center Canvas: DXF/toolpath/position ---
    def _setup_center_canvas(self):
        # Setup canvas with proper sizing and drawing - using original working approach
        self.canvas = ctk.CTkCanvas(self.center_frame, bg=SURFACE, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.center_frame.bind("<Configure>", self._on_canvas_resize)
        # Initialize canvas dimensions
        self.canvas_width = 800
        self.canvas_height = 600
        self.canvas_scale = 1.0
        self.canvas_offset = (0, 0)
        # Draw initial canvas
        self._draw_canvas()

    def _on_canvas_resize(self, event):
        self.canvas_width = event.width
        self.canvas_height = event.height
        self._draw_canvas()

    def _draw_canvas(self):
        self.canvas.delete("all")
        # Draw axes in inches
        self._draw_axes_in_inches()
        # Draw DXF entities if loaded
        if self.dxf_doc and self.dxf_entities:
            self._draw_dxf_entities_inches()
        # Draw toolpath if generated
        if self.toolpath:
            self._draw_toolpath_inches()
        # Draw current tool head position (all axes)
        pos = self.motor_ctrl.get_position()
        x = max(0.0, min(pos['X'], X_MAX_MM))
        y = max(0.0, min(pos['Y'], Y_MAX_MM))
        clamped_pos = {'X': x, 'Y': y}
        self._draw_tool_head_inches(clamped_pos)

    def _draw_axes_in_inches(self):
        # Draw X and Y axes with inch ticks and labels, with buffer
        inch_tick = 5
        
        # Draw X-axis ticks (horizontal axis at bottom)
        for x_in in range(0, 69, inch_tick):
            x_px, y_px = self._inches_to_canvas(x_in, 0)
            # Ensure we're within canvas bounds
            if 0 <= x_px <= self.canvas_width and 0 <= y_px <= self.canvas_height:
                # Draw tick mark pointing up from bottom
                self.canvas.create_line(x_px, y_px, x_px, y_px + 10, fill=PRIMARY_VARIANT, width=2)
                # Draw label below tick (ensure it's visible)
                # For X-axis labels, position them at a fixed distance from the bottom
                label_y = self.canvas_height - 35
                # Always draw labels, they should be visible - use same format as Y-axis
                self.canvas.create_text(x_px, label_y, text=f"{x_in}", fill=ON_SURFACE, font=("Arial", 9), anchor="n")
                # Debug: log first few labels to see positioning
                if x_in <= 15:
                    logger.debug(f"X-axis label {x_in}: canvas_pos=({x_px:.1f}, {y_px:.1f}), label_y={label_y:.1f}, canvas_height={self.canvas_height}")
        
        # Draw Y-axis ticks (vertical axis on left)
        for y_in in range(0, 46, inch_tick):
            x_px, y_px = self._inches_to_canvas(0, y_in)
            # Ensure we're within canvas bounds
            if 0 <= x_px <= self.canvas_width and 0 <= y_px <= self.canvas_height:
                # Draw tick mark pointing right from left edge
                self.canvas.create_line(x_px, y_px, x_px + 10, y_px, fill=PRIMARY_VARIANT, width=2)
                # Draw label to the left of tick (ensure it's visible)
                label_x = max(x_px - 5, 15)
                self.canvas.create_text(label_x, y_px, text=f"{y_in}", fill=ON_SURFACE, font=("Arial", 9), anchor="e")
        
        # Draw border
        self.canvas.create_rectangle(0, 0, self.canvas_width, self.canvas_height, outline=PRIMARY_COLOR, width=2)

    def _inches_to_canvas(self, x_in, y_in):
        # Convert inches to canvas coordinates with home at bottom-left
        plot_width_in = 68 + 2 * PLOT_BUFFER_IN
        plot_height_in = 45 + 2 * PLOT_BUFFER_IN
        sx = self.canvas_width / plot_width_in
        sy = self.canvas_height / plot_height_in
        ox = PLOT_BUFFER_IN * sx
        oy = PLOT_BUFFER_IN * sy
        # Y coordinate: 0 at bottom, 45 at top (Tkinter Y is top-down)
        y_canvas = (45 - y_in) * sy + oy
        return x_in * sx + ox, y_canvas

    def _draw_tool_head_inches(self, pos):
        # Draw a small circle at the current tool head position (in inches)
        y_in = pos['Y'] / INCH_TO_MM
        x_in = pos['X'] / INCH_TO_MM
        x_c, y_c = self._inches_to_canvas(x_in, y_in)
        
        # Make tool head more visible
        r = 10  # Larger radius
        # Draw outer circle (background)
        self.canvas.create_oval(x_c - r - 2, y_c - r - 2, x_c + r + 2, y_c + r + 2, fill=PRIMARY_COLOR, outline=PRIMARY_COLOR, width=1)
        # Draw inner circle (tool head)
        self.canvas.create_oval(x_c - r, y_c - r, x_c + r, y_c + r, fill=SECONDARY_COLOR, outline=PRIMARY_COLOR, width=2)
        # Draw coordinates
        self.canvas.create_text(x_c, y_c - r - 15, text=f"(X={x_in:.2f}, Y={y_in:.2f})", fill=PRIMARY_VARIANT, font=("Arial", 10, "bold"))
        
        # Debug: log position for troubleshooting
        logger.debug(f"Tool head at canvas pos: ({x_c:.1f}, {y_c:.1f}), inches: ({x_in:.2f}, {y_in:.2f})")

    def _draw_dxf_entities_inches(self):
        # Draw DXF entities, converting mm to inches for plotting
        if not (self.dxf_doc and self.dxf_entities):
            logger.debug("No DXF entities to draw")
            return
        scale = getattr(self, 'dxf_unit_scale', 1.0)
        
        # Use the offset calculated during import
        dx, dy = getattr(self, 'dxf_offset', (0, 0))
        
        logger.debug(f"Drawing DXF entities: scale={scale}, offset=({dx:.3f}, {dy:.3f}), entities={len(self.dxf_entities)}")

        # If toolpaths exist, use their shapes for color grouping
        color_cycle = [PRIMARY_COLOR, PRIMARY_VARIANT, SECONDARY_COLOR, '#cc7700', '#aa00cc', '#cc2222', '#0a0', '#f0a', '#0af', '#fa0', '#a0f', '#0fa', '#af0', '#f00', '#00f', '#0ff', '#ff0', '#f0f', '#888', '#444']
        if hasattr(self, 'toolpaths') and self.toolpaths:
            for i, path in enumerate(self.toolpaths):
                color = color_cycle[i % len(color_cycle)]
                # Draw as a polyline of all (x, y) points in the shape
                points = [(x, y) for x, y, angle, z in path if z == 0]
                if len(points) < 2:
                    continue
                flat = []
                for x, y in points:
                    x_c, y_c = self._inches_to_canvas(x, y)
                    flat.extend([x_c, y_c])
                self.canvas.create_line(flat, fill=color, width=2)
            return  # Don't double-plot entities if toolpaths are present

        # Fallback: plot all entities in gray if toolpaths not yet generated
        for e in self.dxf_entities:
            t = e.dxftype()
            if t == 'LINE':
                x1, y1 = e.dxf.start.x, e.dxf.start.y
                x2, y2 = e.dxf.end.x, e.dxf.end.y
                # Apply scale and offset
                x1_norm = x1 * scale - dx
                y1_norm = y1 * scale - dy
                x2_norm = x2 * scale - dx
                y2_norm = y2 * scale - dy
                x1c, y1c = self._inches_to_canvas(x1_norm, y1_norm)
                x2c, y2c = self._inches_to_canvas(x2_norm, y2_norm)
                self.canvas.create_line(x1c, y1c, x2c, y2c, fill=PRIMARY_VARIANT, width=2)
            elif t == 'LWPOLYLINE':
                points = [(p[0], p[1]) for p in e.get_points()]
                flat = []
                for x, y in points:
                    # Apply scale and offset
                    x_norm = x * scale - dx
                    y_norm = y * scale - dy
                    x_c, y_c = self._inches_to_canvas(x_norm, y_norm)
                    flat.extend([x_c, y_c])
                self.canvas.create_line(flat, fill=PRIMARY_VARIANT, width=2)
            elif t == 'POLYLINE':
                points = [(v.dxf.x, v.dxf.y) for v in e.vertices()]
                flat = []
                for x, y in points:
                    # Apply scale and offset
                    x_norm = x * scale - dx
                    y_norm = y * scale - dy
                    x_c, y_c = self._inches_to_canvas(x_norm, y_norm)
                    flat.extend([x_c, y_c])
                self.canvas.create_line(flat, fill=PRIMARY_VARIANT, width=2)
            elif t == 'SPLINE':
                points = list(e.flattening(0.1))
                flat = []
                for x, y, *_ in points:
                    # Apply scale and offset
                    x_norm = x * scale - dx
                    y_norm = y * scale - dy
                    x_c, y_c = self._inches_to_canvas(x_norm, y_norm)
                    flat.extend([x_c, y_c])
                self.canvas.create_line(flat, fill=PRIMARY_VARIANT, width=2)
            elif t == 'ARC':
                center = e.dxf.center
                r = e.dxf.radius
                start = math.radians(e.dxf.start_angle)
                end = math.radians(e.dxf.end_angle)
                if end < start:
                    end += 2 * math.pi
                n = 32
                points = []
                for i in range(n+1):
                    angle = start + (end - start) * i / n
                    x = center.x + r * math.cos(angle)
                    y = center.y + r * math.sin(angle)
                    # Apply scale and offset
                    x_norm = x * scale - dx
                    y_norm = y * scale - dy
                    x_c, y_c = self._inches_to_canvas(x_norm, y_norm)
                    points.append((x_c, y_c))
                self.canvas.create_line(*[coord for pt in points for coord in pt], fill=PRIMARY_VARIANT, width=2)
            elif t == 'CIRCLE':
                center = e.dxf.center
                r = e.dxf.radius
                n = 32
                points = []
                for i in range(n+1):
                    angle = 2 * math.pi * i / n
                    x = center.x + r * math.cos(angle)
                    y = center.y + r * math.sin(angle)
                    # Apply scale and offset
                    x_norm = x * scale - dx
                    y_norm = y * scale - dy
                    x_c, y_c = self._inches_to_canvas(x_norm, y_norm)
                    points.append((x_c, y_c))
                self.canvas.create_line(*[coord for pt in points for coord in pt], fill=PRIMARY_VARIANT, width=2)

    def _draw_toolpath_inches(self):
        # Draw toolpath in inches
        if not hasattr(self, 'toolpaths') or not self.toolpaths:
            return
        color_cycle = [PRIMARY_COLOR, PRIMARY_VARIANT, SECONDARY_COLOR, '#cc7700', '#aa00cc', '#cc2222', '#0a0', '#f0a', '#0af', '#fa0', '#a0f', '#0fa', '#af0', '#f00', '#00f', '#0ff', '#ff0', '#f0f', '#888', '#444']
        for i, path in enumerate(self.toolpaths):
            color = color_cycle[i % len(color_cycle)]
            # Draw as a polyline of all (x, y) points where z==0 (cutting)
            points = [(x, y) for x, y, angle, z in path if z == 0]
            if len(points) < 2:
                continue
            flat = []
            for x, y in points:
                x_in, y_in = x / INCH_TO_MM, y / INCH_TO_MM
                x_c, y_c = self._inches_to_canvas(x_in, y_in)
                flat.extend([x_c, y_c])
            self.canvas.create_line(flat, fill=color, width=2, dash=(4, 2))

    # --- DXF Import/Toolpath ---
    def _import_dxf(self):
        if ezdxf is None:
            messagebox.showerror("Missing Dependency", "ezdxf is not installed. Please install it to import DXF files.")
            return
        initial_dir = os.path.expanduser("~/Desktop/DXF")
        file_path = filedialog.askopenfilename(initialdir=initial_dir, filetypes=[("DXF Files", "*.dxf")])
        if not file_path:
            return
        try:
            doc = readfile(file_path)
            msp = doc.modelspace()
            # Support LINE, LWPOLYLINE, POLYLINE, SPLINE, ARC, CIRCLE
            entities = []
            for e in msp:
                t = e.dxftype()
                if t in ('LINE', 'LWPOLYLINE', 'POLYLINE', 'SPLINE', 'ARC', 'CIRCLE'):
                    entities.append(e)
            if not entities:
                messagebox.showerror("DXF Import Error", "No supported entities (LINE, LWPOLYLINE, POLYLINE, SPLINE, ARC, CIRCLE) found in DXF file.")
                return
            # Detect units
            insunits = doc.header.get('$INSUNITS', 0)
            # 1 = inches, 4 = mm, 0 = unitless (assume inches)
            if insunits == 4:
                self.dxf_unit_scale = 1.0 / 25.4  # mm to in
            else:
                self.dxf_unit_scale = 1.0  # inches or unitless
            # Normalize all points to inches and (0,0) bottom left
            all_x, all_y = [], []
            for e in entities:
                t = e.dxftype()
                if t == 'LINE':
                    all_x.extend([e.dxf.start.x * self.dxf_unit_scale, e.dxf.end.x * self.dxf_unit_scale])
                    all_y.extend([e.dxf.start.y * self.dxf_unit_scale, e.dxf.end.y * self.dxf_unit_scale])
                elif t in ('LWPOLYLINE', 'POLYLINE'):
                    pts = [p[:2] for p in e.get_points()] if t == 'LWPOLYLINE' else [(v.dxf.x, v.dxf.y) for v in e.vertices()]
                    for x, y in pts:
                        all_x.append(x * self.dxf_unit_scale)
                        all_y.append(y * self.dxf_unit_scale)
                elif t == 'CIRCLE':
                    center = e.dxf.center
                    all_x.append(center.x * self.dxf_unit_scale)
                    all_y.append(center.y * self.dxf_unit_scale)
            min_x = min(all_x)
            min_y = min(all_y)
            max_x = max(all_x)
            max_y = max(all_y)
            
            # Add 1-inch buffer around the DXF content
            buffer_inches = 1.0
            self.dxf_offset = (min_x - buffer_inches, min_y - buffer_inches)
            
            # Store the buffered extents for reference
            self.dxf_buffered_extents = (
                min_x - buffer_inches,  # buffered_min_x
                min_y - buffer_inches,  # buffered_min_y
                max_x + buffer_inches,  # buffered_max_x
                max_y + buffer_inches   # buffered_max_y
            )
            self.dxf_doc = doc
            self.dxf_entities = entities
            self.toolpath = []
            # Debug logging
            logger.info(f"DXF imported successfully:")
            logger.info(f"  - Entities found: {len(entities)}")
            logger.info(f"  - Unit scale: {self.dxf_unit_scale}")
            logger.info(f"  - Original extents: min_x={min_x:.3f}, min_y={min_y:.3f}, max_x={max_x:.3f}, max_y={max_y:.3f}")
            logger.info(f"  - Buffered extents: min_x={self.dxf_buffered_extents[0]:.3f}, min_y={self.dxf_buffered_extents[1]:.3f}, max_x={self.dxf_buffered_extents[2]:.3f}, max_y={self.dxf_buffered_extents[3]:.3f}")
            logger.info(f"  - Offset with buffer: dx={self.dxf_offset[0]:.3f}, dy={self.dxf_offset[1]:.3f}")
            self._draw_canvas()
        except Exception as e:
            logger.error(f"Failed to load DXF: {e}")
            messagebox.showerror("DXF Import Error", str(e))

    def _get_dxf_extents_inches(self):
        # Use normalized points for extents
        scale = getattr(self, 'dxf_unit_scale', 1.0)
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')
        for e in self.dxf_entities:
            t = e.dxftype()
            if t == 'LINE':
                xs = [e.dxf.start.x, e.dxf.end.x]
                ys = [e.dxf.start.y, e.dxf.end.y]
            elif t == 'LWPOLYLINE':
                pts = [p[:2] for p in e.get_points()]
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
            elif t == 'POLYLINE':
                pts = [(v.dxf.x, v.dxf.y) for v in e.vertices()]
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
            elif t == 'SPLINE':
                pts = list(e.flattening(0.1))
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
            elif t == 'ARC' or t == 'CIRCLE':
                center = e.dxf.center
                r = e.dxf.radius
                n = 32
                if t == 'ARC':
                    start = math.radians(e.dxf.start_angle)
                    end = math.radians(e.dxf.end_angle)
                    if end < start:
                        end += 2 * math.pi
                    pts = [(center.x + r * math.cos(start + (end - start) * i / n),
                            center.y + r * math.sin(start + (end - start) * i / n)) for i in range(n+1)]
                else:
                    pts = [(center.x + r * math.cos(2 * math.pi * i / n),
                            center.y + r * math.sin(2 * math.pi * i / n)) for i in range(n+1)]
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
            xs = [(x * scale) - self.dxf_offset[0] for x in xs]
            ys = [(y * scale) - self.dxf_offset[1] for y in ys]
            min_x = min(min_x, min(xs))
            max_x = max(max_x, max(xs))
            min_y = min(min_y, min(ys))
            max_y = max(max_y, max(ys))
        return min_x, min_y, max_x, max_y

    def _generate_toolpath(self):
        if not self.dxf_entities:
            messagebox.showwarning("No DXF", "Import a DXF file first.")
            return
        scale = getattr(self, 'dxf_unit_scale', 1.0)
        min_x, min_y, max_x, max_y = self._get_dxf_extents_inches()
        # No Y flip, just offset
        dx, dy = self.dxf_offset
        # --- Flatten all entities into segments ---
        segments = []
        for e in self.dxf_entities:
            t = e.dxftype()
            if t == 'LINE':
                x1, y1 = e.dxf.start.x, e.dxf.start.y
                x2, y2 = e.dxf.end.x, e.dxf.end.y
                segments.append(((x1, y1), (x2, y2)))
            elif t == 'LWPOLYLINE':
                pts = [p[:2] for p in e.get_points()]
                for i in range(1, len(pts)):
                    segments.append((pts[i-1], pts[i]))
                if getattr(e, 'closed', False) or (len(pts) > 2 and pts[0] == pts[-1]):
                    segments.append((pts[-1], pts[0]))
            elif t == 'POLYLINE':
                pts = [(v.dxf.x, v.dxf.y) for v in e.vertices()]
                for i in range(1, len(pts)):
                    segments.append((pts[i-1], pts[i]))
                if getattr(e, 'is_closed', False) or (len(pts) > 2 and pts[0] == pts[-1]):
                    segments.append((pts[-1], pts[0]))
            elif t == 'SPLINE':
                pts = [(p[0], p[1]) for p in e.flattening(0.1)]
                for i in range(1, len(pts)):
                    segments.append((pts[i-1], pts[i]))
            elif t == 'ARC':
                center = e.dxf.center
                r = e.dxf.radius
                start = math.radians(e.dxf.start_angle)
                end = math.radians(e.dxf.end_angle)
                if end < start:
                    end += 2 * math.pi
                n = 32
                pts = [(center.x + r * math.cos(start + (end - start) * i / n),
                        center.y + r * math.sin(start + (end - start) * i / n)) for i in range(n+1)]
                for i in range(1, len(pts)):
                    segments.append((pts[i-1], pts[i]))
            elif t == 'CIRCLE':
                center = e.dxf.center
                r = e.dxf.radius
                n = 32
                pts = [(center.x + r * math.cos(2 * math.pi * i / n),
                        center.y + r * math.sin(2 * math.pi * i / n)) for i in range(n+1)]
                for i in range(1, len(pts)):
                    segments.append((pts[i-1], pts[i]))
        # --- Group segments into shapes by connectivity ---
        from collections import defaultdict, deque
        point_map = defaultdict(list)
        seg_indices = list(range(len(segments)))
        for idx, (p1, p2) in enumerate(segments):
            p1r = (round(p1[0], 6), round(p1[1], 6))
            p2r = (round(p2[0], 6), round(p2[1], 6))
            point_map[p1r].append((idx, p2r))
            point_map[p2r].append((idx, p1r))
        visited = set()
        shapes = []
        for idx in seg_indices:
            if idx in visited:
                continue
            seg = segments[idx]
            p_start = (round(seg[0][0], 6), round(seg[0][1], 6))
            p_end = (round(seg[1][0], 6), round(seg[1][1], 6))
            shape = [p_start, p_end]
            visited.add(idx)
            cur = p_end
            while True:
                found = False
                for next_idx, next_pt in point_map[cur]:
                    if next_idx not in visited:
                        shape.append(next_pt)
                        visited.add(next_idx)
                        cur = next_pt
                        found = True
                        break
                if not found:
                    break
            cur = p_start
            while True:
                found = False
                for next_idx, next_pt in point_map[cur]:
                    if next_idx not in visited:
                        shape = [next_pt] + shape
                        visited.add(next_idx)
                        cur = next_pt
                        found = True
                        break
                if not found:
                    break
            deduped = [shape[0]]
            for pt in shape[1:]:
                if pt != deduped[-1]:
                    deduped.append(pt)
            shapes.append(deduped)
        toolpaths = []
        for pts in shapes:
            if len(pts) < 2:
                continue
            def is_closed(pts):
                x0, y0 = pts[0]
                x1, y1 = pts[-1]
                return abs(x0 - x1) < 1e-5 and abs(y0 - y1) < 1e-5
            def signed_area(pts):
                area = 0.0
                n = len(pts)
                for i in range(n-1):
                    x0, y0 = pts[i]
                    x1, y1 = pts[i+1]
                    area += (x0 * y1 - x1 * y0)
                return area / 2.0
            closed = is_closed(pts)
            pts_ccw = pts
            if closed:
                area = signed_area(pts)
                if area < 0:
                    pts_ccw = list(reversed(pts))
            else:
                pts_ccw = pts
            # Transform all points to inches and (0,0) bottom left
            pts_t = [((x * scale) - dx, (y * scale) - dy) for x, y in pts_ccw]
            
            # Remove duplicate consecutive points and closing duplicates
            pts_clean = [pts_t[0]]
            for i in range(1, len(pts_t)):
                x_prev, y_prev = pts_clean[-1]
                x_curr, y_curr = pts_t[i]
                # Skip if this point is the same as the previous point
                if abs(x_curr - x_prev) > 1e-6 or abs(y_curr - y_prev) > 1e-6:
                    # Also skip if this point is the same as the first point (closing duplicate)
                    x_first, y_first = pts_t[0]
                    if abs(x_curr - x_first) > 1e-6 or abs(y_curr - y_first) > 1e-6:
                        pts_clean.append(pts_t[i])
            
            pts_t = pts_clean
            
            # Debug: Print original shape points
            print(f"\n=== SHAPE DEBUG ===")
            print(f"Original shape has {len(pts_ccw)} points:")
            for i, (x, y) in enumerate(pts_ccw):
                print(f"  Point {i}: ({x:.3f}, {y:.3f})")
            print(f"Transformed shape has {len(pts_t)} points:")
            for i, (x, y) in enumerate(pts_t):
                print(f"  Point {i}: ({x:.3f}, {y:.3f})")
            
            path = []
            # Angle change threshold for Z control (2 degrees)
            angle_change_threshold_deg = 2.0
            n = len(pts_t)
            if n < 2:
                continue
            # Calculate absolute angles from vertical (home orientation)
            angles = []
            for i in range(n):
                if i < n-1:
                    # Calculate angle for segment from point i to point i+1
                    x0, y0 = pts_t[i]
                    x1, y1 = pts_t[i+1]
                    # Calculate relative angle between points
                    relative_angle = math.atan2(y1 - y0, x1 - x0)
                    # Convert to absolute angle from vertical (home orientation)
                    # Vertical is 0°, clockwise is positive, counter-clockwise is negative
                    absolute_angle = -(math.degrees(relative_angle) - 90.0)
                    # Normalize to -180 to +180 range
                    while absolute_angle > 180:
                        absolute_angle -= 360
                    while absolute_angle < -180:
                        absolute_angle += 360
                    angles.append(math.radians(absolute_angle))
                else:
                    # For the last point, calculate angle from last point to first point
                    x0, y0 = pts_t[i]
                    x1, y1 = pts_t[0]  # Back to first point
                    relative_angle = math.atan2(y1 - y0, x1 - x0)
                    absolute_angle = -(math.degrees(relative_angle) - 90.0)
                    while absolute_angle > 180:
                        absolute_angle -= 360
                    while absolute_angle < -180:
                        absolute_angle += 360
                    angles.append(math.radians(absolute_angle))
            
            # Start with first point
            path.append((pts_t[0][0], pts_t[0][1], angles[0], 1))  # Z up
            path.append((pts_t[0][0], pts_t[0][1], angles[0], 0))  # Z down
            
            for i in range(1, n):
                x0, y0 = pts_t[i-1]
                x1, y1 = pts_t[i]
                current_angle = angles[i-1]  # Angle for current segment (from i-1 to i)
                prev_angle = angles[i-2] if i > 1 else angles[-1]  # Angle for previous segment
                
                # Calculate angle change in degrees
                angle_change_rad = abs(current_angle - prev_angle)
                # Normalize to handle angle wrapping (e.g., 179° to -179°)
                if angle_change_rad > math.pi:
                    angle_change_rad = 2 * math.pi - angle_change_rad
                angle_change_deg = math.degrees(angle_change_rad)
                
                # Z up if angle change > 2 degrees, Z down if cutting (small angle change)
                if angle_change_deg > 2.0:
                    path.append((x0, y0, current_angle, 1))  # Z up for large angle change
                    path.append((x0, y0, current_angle, 0))  # Z down to continue cutting
                
                path.append((x1, y1, current_angle, 0))  # Move/cut
            
            # For closed shapes, add the final segment back to the start point
            if closed and n >= 3:
                x0, y0 = pts_t[-1]  # Last point
                x1, y1 = pts_t[0]   # First point
                final_angle = angles[-1]  # Angle for segment from last to first
                prev_angle = angles[-2]   # Angle for previous segment (from second-to-last to last)
                
                # Calculate angle change in degrees for final segment
                angle_change_rad = abs(final_angle - prev_angle)
                # Normalize to handle angle wrapping (e.g., 179° to -179°)
                if angle_change_rad > math.pi:
                    angle_change_rad = 2 * math.pi - angle_change_rad
                angle_change_deg = math.degrees(angle_change_rad)
                
                # Z up if angle change > 2 degrees, Z down if cutting (small angle change)
                if angle_change_deg > 2.0:
                    path.append((x0, y0, final_angle, 1))  # Z up for large angle change
                    path.append((x0, y0, final_angle, 0))  # Z down to continue cutting
                
                path.append((x1, y1, final_angle, 0))  # Move/cut back to start
                
                # End with first point (Z up) - this is the final position
                path.append((pts_t[0][0], pts_t[0][1], angles[0], 1))  # Z up at end (point 0)
            else:
                # End with last point (Z up) for open shapes
                path.append((pts_t[-1][0], pts_t[-1][1], angles[-1], 1))  # Z up at end
            toolpaths.append(path)
        self.toolpaths = toolpaths
        
        # Debug: Print toolpath coordinates
        print("\n=== TOOLPATH DEBUG INFO ===")
        print(f"Generated {len(toolpaths)} toolpath(s)")
        for i, path in enumerate(toolpaths):
            print(f"\nToolpath {i+1} - {len(path)} points:")
            for j, (x, y, angle, z) in enumerate(path):
                x_mm = x * INCH_TO_MM
                y_mm = y * INCH_TO_MM
                angle_deg = math.degrees(angle)
                z_pos = "UP" if z == 1 else "DOWN"
                print(f"  Point {j+1}: X={x_mm:.2f}mm ({x:.3f}in), Y={y_mm:.2f}mm ({y:.3f}in), Angle={angle_deg:.1f}°, Z={z_pos}")
        
        # Check for positions that might be beyond machine limits
        print(f"\n=== MACHINE LIMITS ===")
        print(f"X limits: {-X_MAX_MM:.2f}mm to {X_MAX_MM:.2f}mm")
        print(f"Y limits: {-Y_MAX_MM:.2f}mm to {Y_MAX_MM:.2f}mm")
        
        # Check if any points are beyond limits
        beyond_limits = []
        for i, path in enumerate(toolpaths):
            for j, (x, y, angle, z) in enumerate(path):
                x_mm = x * INCH_TO_MM
                y_mm = y * INCH_TO_MM
                if abs(x_mm) > X_MAX_MM or abs(y_mm) > Y_MAX_MM:
                    beyond_limits.append((i+1, j+1, x_mm, y_mm))
        
        if beyond_limits:
            print(f"\n⚠️  WARNING: {len(beyond_limits)} points beyond machine limits:")
            for toolpath_idx, point_idx, x_mm, y_mm in beyond_limits:
                print(f"  Toolpath {toolpath_idx}, Point {point_idx}: X={x_mm:.2f}mm, Y={y_mm:.2f}mm")
        else:
            print("\n✅ All points within machine limits")
        
        print("=== END DEBUG INFO ===\n")
        
        self._draw_canvas()

    def _preview_toolpath(self):
        if not hasattr(self, 'toolpaths') or not self.toolpaths:
            messagebox.showwarning("No Toolpath", "Generate a toolpath first.")
            return
        self._draw_canvas()  # Clear previous preview only once
        def animate_shape(shape_idx=0):
            if shape_idx >= len(self.toolpaths):
                return
            path = self.toolpaths[shape_idx]
            def animate_step(idx=0):
                steps_per_tick = 1  # Animate 1 step per timer tick for smoothness
                if idx >= len(path):
                    self.root.after(50, animate_shape, shape_idx+1)  # Short pause between shapes
                    return
                for j in range(steps_per_tick):
                    if idx + j >= len(path):
                        break
                    x, y, angle, z = path[idx + j]
                    r = 0.5  # radius in inches
                    x_c, y_c = self._inches_to_canvas(x, y)
                    # Draw blue dot if Z=0, then grey dot if Z=1 (slightly larger)
                    if z == 0:
                        self.canvas.create_oval(x_c-6, y_c-6, x_c+6, y_c+6, fill=PRIMARY_COLOR, outline=PRIMARY_VARIANT)
                    if z == 1:
                        self.canvas.create_oval(x_c-8, y_c-8, x_c+8, y_c+8, fill=ON_SURFACE, outline=PRIMARY_VARIANT)
                    # Draw orientation line (wheel direction)
                    x2 = x + r * math.cos(angle)
                    y2 = y + r * math.sin(angle)
                    x2_c, y2_c = self._inches_to_canvas(x2, y2)
                    self.canvas.create_line(x_c, y_c, x2_c, y2_c, fill=SECONDARY_COLOR, width=3)
                self.root.after(2, animate_step, idx + steps_per_tick)  # Smoother animation
            animate_step()
        animate_shape()

    def _run_toolpath(self):
        if not hasattr(self, 'toolpaths') or not self.toolpaths:
            messagebox.showwarning("No Toolpath", "Generate a toolpath first.")
            return
            
        # Debug: Print machine limits and first toolpath point
        print(f"\n=== TOOLPATH EXECUTION DEBUG ===")
        print(f"Machine limits: X=±{X_MAX_MM:.2f}mm, Y=±{Y_MAX_MM:.2f}mm")
        
        # Debug: Check sensor states before starting toolpath
        if MOTOR_IMPORTS_AVAILABLE:
            sensor_states = self.motor_ctrl.get_sensor_states()
            print(f"\n=== SENSOR STATES BEFORE TOOLPATH ===")
            for motor, state in sensor_states.items():
                print(f"{motor}: raw={state['raw']}, debounced={state['debounced']}, last_trigger_time={state['last_trigger_time']:.3f}s, readings={state['readings']}")
        
        if self.toolpaths and self.toolpaths[0]:
            first_point = self.toolpaths[0][0]
            x, y, angle, z = first_point
            x_mm = x * INCH_TO_MM
            y_mm = y * INCH_TO_MM
            print(f"First toolpath point: X={x:.3f}in ({x_mm:.2f}mm), Y={y:.3f}in ({y_mm:.2f}mm)")
            if abs(x_mm) > X_MAX_MM or abs(y_mm) > Y_MAX_MM:
                print(f"⚠️  WARNING: First point beyond machine limits!")
                return
            

        
        self._running_toolpath = True
        self._current_toolpath_pos = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'ROT': 0.0}
        self._current_toolpath_idx = [0, 0]  # [shape_idx, step_idx]
        self._toolpath_total_steps = sum(len(path) for path in self.toolpaths)
        self._toolpath_step_count = 0
        
        # Start with travel move to first point
        if self.toolpaths and self.toolpaths[0]:
            first_point = self.toolpaths[0][0]
            x, y, angle, z = first_point
            self._travel_to_start(x * INCH_TO_MM, y * INCH_TO_MM)
        else:
            self._run_toolpath_step()

    def _travel_to_start(self, x_mm, y_mm):
        """Travel from home to the start position of the toolpath."""
        # Move to start position with Z up
        if MOTOR_IMPORTS_AVAILABLE:
            self.motor_ctrl.move_to(x=x_mm, y=y_mm, z=Z_UP_MM, rot=0.0)
        
        # Update position and display
        self._current_toolpath_pos['X'] = x_mm
        self._current_toolpath_pos['Y'] = y_mm
        self._current_toolpath_pos['Z'] = Z_UP_MM
        self._current_toolpath_pos['ROT'] = 0.0
        
        self._update_position_display()
        self._draw_canvas()
        
        # Wait a moment, then start the toolpath
        self.root.after(500, self._run_toolpath_step)

    def _run_toolpath_step(self):
        if not self._running_toolpath:
            return
        shape_idx, step_idx = self._current_toolpath_idx
        if shape_idx >= len(self.toolpaths):
            self._running_toolpath = False
            return
        path = self.toolpaths[shape_idx]
        if step_idx >= len(path):
            # Move to next shape
            self._current_toolpath_idx = [shape_idx + 1, 0]
            self.root.after(100, self._run_toolpath_step)  # Longer pause between shapes
            return
        x, y, angle, z = path[step_idx]
        # Set toolpath position directly (no swap)
        x_mm = x * INCH_TO_MM
        y_mm = y * INCH_TO_MM
        self._current_toolpath_pos['X'] = x_mm
        self._current_toolpath_pos['Y'] = y_mm
        self._current_toolpath_pos['Z'] = Z_DOWN_MM if z == 0 else Z_UP_MM
        self._current_toolpath_pos['ROT'] = math.degrees(angle)
        
        # Debug: print toolpath coordinates in both units
        print(f"[DEBUG] Toolpath step {step_idx}: X={x:.3f}in ({x_mm:.2f}mm), Y={y:.3f}in ({y_mm:.2f}mm)")
        
        if MOTOR_IMPORTS_AVAILABLE:
            self.motor_ctrl.move_to(
                x=self._current_toolpath_pos['X'],
                y=self._current_toolpath_pos['Y'],
                z=self._current_toolpath_pos['Z'],
                rot=self._current_toolpath_pos['ROT']
            )
        # Debug: print both toolpath and actual motor position
        actual_pos = self.motor_ctrl.get_position()
        print(f"[DEBUG] Toolpath pos: X={self._current_toolpath_pos['X']:.2f} Y={self._current_toolpath_pos['Y']:.2f} | Motor pos: X={actual_pos['X']:.2f} Y={actual_pos['Y']:.2f}")
        
        # Check if coordinates are within machine limits
        if abs(x_mm) > X_MAX_MM or abs(y_mm) > Y_MAX_MM:
            print(f"[WARNING] Coordinates beyond machine limits! X={x_mm:.2f}mm (limit: ±{X_MAX_MM:.2f}mm), Y={y_mm:.2f}mm (limit: ±{Y_MAX_MM:.2f}mm)")
        self._update_position_display()  # Force update after each move
        self._draw_canvas()
        # Next step
        self._current_toolpath_idx[1] += 1
        self._toolpath_step_count += 1
        self.root.after(50, self._run_toolpath_step)  # Slower execution (50ms instead of 5ms)

    def _draw_live_tool_head_inches(self, pos):
        # Draw a blue dot and orientation line at the current tool head position (in inches)
        x_in = pos['X'] / INCH_TO_MM
        y_in = pos['Y'] / INCH_TO_MM
        rot_rad = math.radians(pos.get('ROT', 0.0))
        x_c, y_c = self._inches_to_canvas(x_in, y_in)
        r = 7
        self.canvas.create_oval(x_c - r, y_c - r, x_c + r, y_c + r, fill=PRIMARY_COLOR, outline=PRIMARY_VARIANT, width=2)
        r_dir = 0.5  # 0.5 inch
        x2 = x_in + r_dir * math.cos(rot_rad)
        y2 = y_in + r_dir * math.sin(rot_rad)
        x2_c, y2_c = self._inches_to_canvas(x2, y2)
        self.canvas.create_line(x_c, y_c, x2_c, y2_c, fill=SECONDARY_COLOR, width=3)

    # --- Right Toolbar: Motor controls ---
    def _setup_right_toolbar(self):
        ctk.CTkLabel(self.right_toolbar, text="Motor Controls", font=("Arial", 16, "bold"), text_color=PRIMARY_COLOR).pack(pady=(20, 10))
        
        # Jog controls (arrow key layout)
        jog_frame = ctk.CTkFrame(self.right_toolbar, fg_color=SURFACE, corner_radius=12)
        jog_frame.pack(fill=ctk.X, padx=10, pady=8)
        # 3x3 grid for arrow keys
        jog_frame.grid_columnconfigure(0, minsize=32)
        jog_frame.grid_columnconfigure(1, minsize=32)
        jog_frame.grid_columnconfigure(2, minsize=32)
        jog_frame.grid_rowconfigure(0, minsize=32)
        jog_frame.grid_rowconfigure(1, minsize=32)
        jog_frame.grid_rowconfigure(2, minsize=32)
        # Top: Up arrow
        self._add_jog_button(jog_frame, "↑", lambda: self._jog('Y', +self.jog_speed)).grid(row=0, column=1, padx=2, pady=2)
        # Middle: Left and Right arrows
        self._add_jog_button(jog_frame, "←", lambda: self._jog('X', -self.jog_speed)).grid(row=1, column=0, padx=2, pady=2)
        self._add_jog_button(jog_frame, "→", lambda: self._jog('X', +self.jog_speed)).grid(row=1, column=2, padx=2, pady=2)
        # Bottom: Down arrow
        self._add_jog_button(jog_frame, "↓", lambda: self._jog('Y', -self.jog_speed)).grid(row=2, column=1, padx=2, pady=2)
        
        # Z and ROT controls section
        zrot_section = ctk.CTkFrame(self.right_toolbar, fg_color="#d0d0d0", corner_radius=8)
        zrot_section.pack(fill=ctk.X, padx=10, pady=(0, 8))
        # Configure grid for centered layout
        zrot_section.grid_columnconfigure(0, weight=1)
        zrot_section.grid_columnconfigure(1, weight=1)
        zrot_section.grid_columnconfigure(2, weight=1)
        zrot_section.grid_columnconfigure(3, weight=1)
        zrot_section.grid_rowconfigure(0, weight=1)
        # Center the Z and ROT buttons
        self._add_jog_button(zrot_section, "Z+", lambda: self._jog('Z', +1)).grid(row=0, column=0, padx=4, pady=4, sticky="nsew")
        self._add_jog_button(zrot_section, "Z-", lambda: self._jog('Z', -1)).grid(row=0, column=1, padx=4, pady=4, sticky="nsew")
        self._add_jog_button(zrot_section, "ROT+", lambda: self._jog('ROT', +5)).grid(row=0, column=2, padx=4, pady=4, sticky="nsew")
        self._add_jog_button(zrot_section, "ROT-", lambda: self._jog('ROT', -5)).grid(row=0, column=3, padx=4, pady=4, sticky="nsew")
        
        # Speed adjustment section
        speed_section = ctk.CTkFrame(self.right_toolbar, fg_color="#d0d0d0", corner_radius=8)
        speed_section.pack(fill=ctk.X, padx=10, pady=(0, 8))
        ctk.CTkLabel(speed_section, text="Jog Step (in)", font=("Arial", 16, "bold")).pack(side=ctk.LEFT, padx=10, pady=10)
        self._jog_slider_scale = 0.01
        speed_slider = ctk.CTkSlider(speed_section, from_=1, to=200, number_of_steps=199, variable=None, width=120, command=lambda v: self._on_jog_slider(v))
        speed_slider.pack(side=ctk.LEFT, padx=5)
        speed_entry = ctk.CTkEntry(speed_section, textvariable=self.jog_speed_var, width=50)
        speed_entry.pack(side=ctk.LEFT, padx=5)
        self.jog_speed_var.trace_add('write', lambda *a: self._update_jog_speed())
        
        # Home controls section
        home_section = ctk.CTkFrame(self.right_toolbar, fg_color="#f0f0f0", corner_radius=8)
        home_section.pack(fill=ctk.X, padx=10, pady=8)
        # Home controls
        home_frame = ctk.CTkFrame(home_section, fg_color=SURFACE, corner_radius=12)
        home_frame.pack(fill=ctk.X, padx=10, pady=10)
        ctk.CTkButton(home_frame, text="Home X", command=lambda: self._home('X'), height=35, font=("Arial", 16, "bold")).pack(fill=ctk.X, pady=2)
        ctk.CTkButton(home_frame, text="Home Y", command=lambda: self._home('Y'), height=35, font=("Arial", 16, "bold")).pack(fill=ctk.X, pady=2)
        ctk.CTkButton(home_frame, text="Home Z", command=lambda: self._home('Z'), height=35, font=("Arial", 16, "bold")).pack(fill=ctk.X, pady=2)
        ctk.CTkButton(home_frame, text="Home ROT", command=lambda: self._home('ROT'), height=35, font=("Arial", 16, "bold")).pack(fill=ctk.X, pady=2)
        ctk.CTkButton(home_frame, text="Home All (Sync)", command=self._home_all, height=35, font=("Arial", 16, "bold")).pack(fill=ctk.X, pady=2)
        
        # Coordinates display section
        coord_section = ctk.CTkFrame(self.right_toolbar, fg_color="#d0d0d0", corner_radius=8)
        coord_section.pack(fill=ctk.X, padx=10, pady=8)
        self.coord_label = ctk.CTkLabel(coord_section, text="", font=("Consolas", 16, "bold"), text_color=ON_SURFACE)
        self.coord_label.pack(pady=10)

    def _add_jog_button(self, parent, text, cmd):
        # Use larger font for arrow buttons
        font_size = 20 if text in ["↑", "↓", "←", "→"] else 16
        btn = ctk.CTkButton(parent, text=text, command=cmd, width=50, height=40, fg_color=PRIMARY_COLOR, text_color=ON_PRIMARY, hover_color=PRIMARY_VARIANT, corner_radius=8, font=("Arial", font_size, "bold"))
        return btn

    def _jog(self, axis, delta):
        self.motor_ctrl.jog(axis, delta)
        self._draw_canvas()
        self._update_position_display()

    def _home(self, axis):
        success = self.motor_ctrl.home(axis)
        if success:
            self.status_label.configure(text=f"{axis} axis homed", text_color="green")
        else:
            self.status_label.configure(text=f"Failed to home {axis}", text_color="red")
        self._draw_canvas()
        self._update_position_display()
        # Clear status after 2 seconds
        self.root.after(2000, lambda: self.status_label.configure(text="Ready", text_color=ON_SURFACE))

    def _home_all(self):
        success = self.motor_ctrl.home_all_synchronous()
        if success:
            self.status_label.configure(text="All axes homed", text_color="green")
        else:
            self.status_label.configure(text="Homing failed", text_color="red")
        self._draw_canvas()
        self._update_position_display()
        # Clear status after 2 seconds
        self.root.after(2000, lambda: self.status_label.configure(text="Ready", text_color=ON_SURFACE))

    def _stop_movement(self):
        """Stop all movement and cancel any pending arrow key operations."""
        # Stop any ongoing motor movement
        self.motor_ctrl.stop_movement()
        
        # Cancel all pending arrow key operations
        for key in self._arrow_key_after_ids:
            if self._arrow_key_after_ids[key] is not None:
                self.root.after_cancel(self._arrow_key_after_ids[key])
                self._arrow_key_after_ids[key] = None
            self._arrow_key_state[key] = False
        
        logger.info("All movement stopped")

    def _estop(self):
        self.motor_ctrl.estop()
        self.status_label.configure(text="EMERGENCY STOP", text_color="red")
        # Clear status after 3 seconds
        self.root.after(3000, lambda: self.status_label.configure(text="Ready", text_color=ON_SURFACE))

    def _update_position_display(self):
        pos = self.motor_ctrl.get_position()
        x_disp = pos['X']/INCH_TO_MM
        y_disp = pos['Y']/INCH_TO_MM
        z_disp = pos['Z']/INCH_TO_MM  # Convert Z to inches
        rot_disp = pos['ROT']
        text = f"X: {x_disp:.2f} in\nY: {y_disp:.2f} in\nZ: {z_disp:.2f} in\nROT: {rot_disp:.1f}°"
        self.coord_label.configure(text=text)
        self.root.after(200, self._update_position_display)

    def _update_jog_speed(self):
        try:
            self.jog_speed = self.jog_speed_var.get() * INCH_TO_MM
        except Exception:
            pass

    def _on_jog_slider(self, value):
        # Convert int slider value to float inches
        self.jog_speed_var.set(int(value) * self._jog_slider_scale)

    def _toggle_fullscreen(self):
        """Toggle full screen mode."""
        try:
            current_state = self.root.attributes('-fullscreen')
            self.root.attributes('-fullscreen', not current_state)
        except:
            try:
                current_state = self.root.state()
                if current_state == 'zoomed':
                    self.root.state('normal')
                else:
                    self.root.state('zoomed')
            except:
                pass

    def _close_app(self):
        """Close the application."""
        self._on_close()

    def _on_close(self):
        """Clean up resources before closing."""
        try:
            if hasattr(self.motor_ctrl, 'cleanup'):
                self.motor_ctrl.cleanup()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        self.root.destroy()

# --- Main entry point ---
def main():
    root = ctk.CTk()
    app = FabricCNCApp(root)
    root.mainloop()

    # In main(), print debug info for simulation mode
    print(f"[DEBUG] ON_RPI={ON_RPI}")
    print(f"[DEBUG] MOTOR_IMPORTS_AVAILABLE={MOTOR_IMPORTS_AVAILABLE}")
    print(f"[DEBUG] SIMULATION_MODE={SIMULATION_MODE}")

if __name__ == "__main__":
    main() 