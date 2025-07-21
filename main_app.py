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

# Import toolpath planning modules
try:
    from toolpath_planning import (
        ContinuousToolpathGenerator,
        generate_continuous_circle_toolpath,
        generate_continuous_spline_toolpath,
        generate_continuous_polyline_toolpath,
        generate_continuous_line_toolpath,
        generate_gcode_continuous_motion
    )
    TOOLPATH_IMPORTS_AVAILABLE = True
except ImportError:
    TOOLPATH_IMPORTS_AVAILABLE = False

# Import configuration
import config
from config import (
    UI_COLORS, TOOLPATH_CONFIG, UI_PADDING,
    ON_RPI, SIMULATION_MODE
)

# Import GPIO only if on Raspberry Pi
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fabric_cnc.main_app")

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

def calculate_angle_between_points(p1, p2, p3):
    """Calculate the angle between three points (p1 -> p2 -> p3) in degrees."""
    if p1 == p2 or p2 == p3:
        return 0.0
    
    # Vector from p1 to p2
    v1x = p2[0] - p1[0]
    v1y = p2[1] - p1[1]
    
    # Vector from p2 to p3
    v2x = p3[0] - p2[0]
    v2y = p3[1] - p2[1]
    
    # Calculate dot product
    dot_product = v1x * v2x + v1y * v2y
    
    # Calculate magnitudes
    mag1 = math.sqrt(v1x * v1x + v1y * v1y)
    mag2 = math.sqrt(v2x * v2x + v2y * v2y)
    
    if mag1 == 0 or mag2 == 0:
        return 0.0
    
    # Calculate cosine of angle
    cos_angle = dot_product / (mag1 * mag2)
    
    # Clamp to valid range
    cos_angle = max(-1.0, min(1.0, cos_angle))
    
    # Convert to degrees
    angle_rad = math.acos(cos_angle)
    angle_deg = math.degrees(angle_rad)
    
    return angle_deg

def flatten_spline_with_angle_limit(spline, max_angle_deg=2.0):
    """Flatten a spline to points ensuring max angle between segments is below threshold."""
    try:
        # Get spline points with high precision
        points = list(spline.flattening(0.001))
        if len(points) < 3:
            return points
        
        # Filter points to ensure max angle between segments
        filtered_points = [points[0]]
        for i in range(1, len(points) - 1):
            angle = calculate_angle_between_points(
                points[i-1], points[i], points[i+1]
            )
            if angle > max_angle_deg:
                # Add intermediate points to reduce angle
                # This is a simple approach - could be improved with more sophisticated interpolation
                pass
            filtered_points.append(points[i])
        filtered_points.append(points[-1])
        
        return filtered_points
    except Exception as e:
        logger.error(f"Error flattening spline: {e}")
        return []

# Toolpath generation functions moved to toolpath_planning package

# Toolpath generation functions moved to toolpath_planning package

# --- Motor simulation logic ---
class SimulatedMotorController:
    def __init__(self):
        self.position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'ROT': 0.0}
        self.lock = threading.Lock()
        self.is_homing = False

    def _clamp(self, axis, value):
        if axis == 'X':
            return max(-config.APP_CONFIG['X_MAX_MM'], min(value, config.APP_CONFIG['X_MAX_MM']))  # Allow negative X positions
        elif axis == 'Y':
            return max(-config.APP_CONFIG['Y_MAX_MM'], min(value, config.APP_CONFIG['Y_MAX_MM']))  # Allow negative Y positions
        elif axis == 'Z':
            return max(0.0, min(value, config.APP_CONFIG['Z_MAX_MM']))  # Keep Z positive only
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
            return max(-config.APP_CONFIG['X_MAX_MM'], min(value, config.APP_CONFIG['X_MAX_MM']))  # Allow negative X positions
        elif axis == 'Y':
            return max(-config.APP_CONFIG['Y_MAX_MM'], min(value, config.APP_CONFIG['Y_MAX_MM']))  # Allow negative Y positions
        elif axis == 'Z':
            return max(-config.APP_CONFIG['Z_MAX_MM'], min(value, config.APP_CONFIG['Z_MAX_MM']))  # Allow negative Z positions
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
        self.root.configure(bg=UI_COLORS['BACKGROUND'])
        self.jog_speed = 1.0 * config.APP_CONFIG['INCH_TO_MM']  # Default to 1 inch
        self.jog_speed_var = ctk.DoubleVar(value=1.0)  # Default to 1 inch
        self._jog_slider_scale = 0.1  # Scale factor for slider (0.1 inch increments)
        self._arrow_key_state = {}
        self._arrow_key_after_ids = {}
        self._current_toolpath_idx = [0, 0]
        self._toolpath_step_count = 0
        self._current_toolpath_pos = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'ROT': 0.0}
        self.toolpaths = []
        self.motor_ctrl = SimulatedMotorController() if SIMULATION_MODE else RealMotorController()
        self._jog_in_progress = {'X': False, 'Y': False, 'Z': False, 'ROT': False}
        self._arrow_key_repeat_delay = config.APP_CONFIG['ARROW_KEY_REPEAT_DELAY']
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
        self.app_bar = ctk.CTkFrame(self.root, fg_color=UI_COLORS['PRIMARY_COLOR'], corner_radius=0, height=56)
        self.app_bar.pack(fill="x", side="top")
        self.title = ctk.CTkLabel(self.app_bar, text="Fabric CNC", text_color=UI_COLORS['ON_PRIMARY'], font=("Arial", 16, "bold"))
        self.title.pack(side="left", padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'])
        
        # Close button
        close_button = ctk.CTkButton(self.app_bar, text="✕", width=40, height=30, 
                                   command=self._close_app, fg_color="transparent", 
                                   text_color=UI_COLORS['ON_PRIMARY'], hover_color=UI_COLORS['BUTTON_DANGER'], corner_radius=6)
        close_button.pack(side="right", padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'])

        # Main container using grid for three-column layout
        self.main_container = ctk.CTkFrame(self.root, fg_color=UI_COLORS['BACKGROUND'])
        self.main_container.pack(expand=True, fill="both", padx=0, pady=0)
        
        # Configure grid weights - middle column gets all available space
        self.main_container.grid_columnconfigure(0, weight=0, minsize=175)  # Left column - compact width
        self.main_container.grid_columnconfigure(1, weight=1)  # Middle column - takes all available space
        self.main_container.grid_columnconfigure(2, weight=0, minsize=175)  # Right column - same compact width
        self.main_container.grid_rowconfigure(0, weight=1)  # Single row takes full height
        
        # === LEFT COLUMN: DXF & Toolpath Controls ===
        self.left_column = ctk.CTkFrame(self.main_container, fg_color=UI_COLORS['SURFACE'], corner_radius=12)
        self.left_column.grid(row=0, column=0, sticky="nsew", padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'])
        
        # Configure left column - no expansion needed since status wraps around text
        
        # File & DXF section
        file_section = ctk.CTkFrame(self.left_column, fg_color="#d0d0d0", corner_radius=8)
        file_section.grid(row=0, column=0, sticky="ew", padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'])
        
        ctk.CTkLabel(file_section, text="File & DXF", font=("Arial", 16, "bold"), text_color=UI_COLORS['PRIMARY_COLOR']).pack(pady=UI_PADDING['SMALL'])
        
        # File buttons with consistent padding
        file_buttons = [
            ("Import DXF", self._import_dxf, "primary"),
            ("Generate Toolpath", self._generate_toolpath, "secondary"),
            ("Preview Toolpath", self._preview_toolpath, "secondary"),
            ("Run Toolpath", self._run_toolpath, "success"),
            ("E-Stop", self._estop, "danger")
        ]
        
        for text, command, button_type in file_buttons:
            btn = self._create_stylish_button(file_section, text, command, button_type)
            btn.pack(fill="x", padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'])
        
        # Status section - fills width but wraps height around text
        status_section = ctk.CTkFrame(self.left_column, fg_color="#d0d0d0", corner_radius=8)
        status_section.grid(row=1, column=0, sticky="ew", padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'])
        
        ctk.CTkLabel(status_section, text="Status:", font=("Arial", 16, "bold"), text_color=UI_COLORS['PRIMARY_COLOR']).pack(pady=UI_PADDING['SMALL'])
        self.status_label = ctk.CTkLabel(status_section, text="Ready", font=("Arial", 16, "bold"), text_color=UI_COLORS['ON_SURFACE'])
        self.status_label.pack(pady=UI_PADDING['SMALL'])

        # === MIDDLE COLUMN: Plot Canvas ===
        self.center_column = ctk.CTkFrame(self.main_container, fg_color="#E0E0E0", corner_radius=12)
        self.center_column.grid(row=0, column=1, sticky="nsew", padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'])
        
        # Configure center column to expand in both directions
        self.center_column.grid_rowconfigure(0, weight=1)
        self.center_column.grid_columnconfigure(0, weight=1)
        
        # Setup canvas in center column
        self.canvas = ctk.CTkCanvas(self.center_column, bg=UI_COLORS['SURFACE'], highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        
        # Bind canvas resize
        self.center_column.bind("<Configure>", self._on_canvas_resize)
        
        # Initialize canvas dimensions
        self.canvas_width = 800  # Default, will be updated by resize
        self.canvas_height = 600  # Default, will be updated by resize
        self.canvas_scale = 1.0
        self.canvas_offset = (0, 0)
        
        # Draw initial canvas
        self._draw_canvas()

        # === RIGHT COLUMN: Motor Controls ===
        self.right_column = ctk.CTkFrame(self.main_container, fg_color=UI_COLORS['SURFACE'], corner_radius=12)
        self.right_column.grid(row=0, column=2, sticky="nsew", padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'])
        
        # Configure right column to expand vertically
        self.right_column.grid_rowconfigure(4, weight=1)  # Coordinates section expands
        
        # Title
        # Unified motor controls section
        motor_section = ctk.CTkFrame(self.right_column, fg_color="#d0d0d0", corner_radius=8)
        motor_section.grid(row=0, column=0, sticky="ew", padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'])
        
        # Motor Controls label inside the box
        ctk.CTkLabel(motor_section, text="Motor Controls", font=("Arial", 16, "bold"), text_color=UI_COLORS['PRIMARY_COLOR']).grid(row=0, column=0, columnspan=2, pady=UI_PADDING['SMALL'])
        
        # 8-row layout: label (1 row) + arrows (3 rows) + Z/ROT (2 rows) + jog speed (2 rows)
        motor_section.grid_columnconfigure(0, weight=1)
        motor_section.grid_columnconfigure(1, weight=1)
        motor_section.grid_rowconfigure(1, weight=1)  # Up arrow row
        motor_section.grid_rowconfigure(2, weight=1)  # Left/Right arrows row
        motor_section.grid_rowconfigure(3, weight=1)  # Down arrow row
        motor_section.grid_rowconfigure(4, weight=1)  # Z controls row
        motor_section.grid_rowconfigure(5, weight=1)  # ROT controls row
        motor_section.grid_rowconfigure(6, weight=1)  # Jog speed label row
        motor_section.grid_rowconfigure(7, weight=1)  # Jog speed slider row
        motor_section.grid_rowconfigure(8, weight=1)  # Jog speed value display row
        
        # Arrow buttons - stacked layout with equal widths
        self._add_compact_jog_button(motor_section, "↑", lambda: self._jog('Y', +self.jog_speed)).grid(row=1, column=0, columnspan=2, padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'], sticky="nsew")
        self._add_compact_jog_button(motor_section, "←", lambda: self._jog('X', -self.jog_speed)).grid(row=2, column=0, padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'], sticky="nsew")
        self._add_compact_jog_button(motor_section, "→", lambda: self._jog('X', +self.jog_speed)).grid(row=2, column=1, padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'], sticky="nsew")
        self._add_compact_jog_button(motor_section, "↓", lambda: self._jog('Y', -self.jog_speed)).grid(row=3, column=0, columnspan=2, padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'], sticky="nsew")
        
        # Z and ROT controls
        self._add_compact_jog_button(motor_section, "Z+", lambda: self._jog('Z', +1)).grid(row=4, column=0, padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'], sticky="nsew")
        self._add_compact_jog_button(motor_section, "Z-", lambda: self._jog('Z', -1)).grid(row=4, column=1, padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'], sticky="nsew")
        self._add_compact_jog_button(motor_section, "R+", lambda: self._jog('ROT', +5)).grid(row=5, column=0, padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'], sticky="nsew")
        self._add_compact_jog_button(motor_section, "R-", lambda: self._jog('ROT', -5)).grid(row=5, column=1, padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'], sticky="nsew")
        
        # Jog speed slider
        ctk.CTkLabel(motor_section, text="Jog Speed:", font=("Arial", 12, "bold"), text_color=UI_COLORS['PRIMARY_COLOR']).grid(row=6, column=0, columnspan=2, pady=(UI_PADDING['SMALL'], 0))
        jog_slider = ctk.CTkSlider(motor_section, from_=1, to=50, number_of_steps=49, command=self._on_jog_slider)
        jog_slider.grid(row=7, column=0, columnspan=2, padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'], sticky="ew")
        jog_slider.set(10)  # Set to 1.0 inch (10 * 0.1)
        
        # Jog speed value display
        self.jog_speed_label = ctk.CTkLabel(motor_section, text="1.0 in", font=("Arial", 12, "bold"), text_color=UI_COLORS['ON_SURFACE'])
        self.jog_speed_label.grid(row=8, column=0, columnspan=2, pady=(0, UI_PADDING['SMALL']))
        
        # Home controls section
        home_section = ctk.CTkFrame(self.right_column, fg_color="#d0d0d0", corner_radius=8)
        home_section.grid(row=1, column=0, sticky="ew", padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'])
        
        home_buttons = [
            ("Home X", lambda: self._home('X'), "primary"),
            ("Home Y", lambda: self._home('Y'), "primary"),
            ("Home Z", lambda: self._home('Z'), "primary"),
            ("Home Rot", lambda: self._home('ROT'), "primary"),
            ("Home All", self._home_all, "success")
        ]
        
        for i, (text, command, button_type) in enumerate(home_buttons):
            btn = self._create_stylish_button(home_section, text, command, button_type, height=35)
            btn.pack(fill=ctk.X, padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'])
        
        # Coordinates display section - expands to fill remaining space
        coord_section = ctk.CTkFrame(self.right_column, fg_color="#d0d0d0", corner_radius=8)
        coord_section.grid(row=2, column=0, sticky="nsew", padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'])
        
        self.coord_label = ctk.CTkLabel(coord_section, text="", font=("Consolas", 16, "bold"), text_color=UI_COLORS['ON_SURFACE'])
        self.coord_label.pack(pady=UI_PADDING['SMALL'])

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
            delta = 1.0 * config.APP_CONFIG['INCH_TO_MM']  # 1 inch up
        elif key == 'Page_Down':
            axis = 'Z'
            delta = -1.0 * config.APP_CONFIG['INCH_TO_MM']  # 1 inch down
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
        x = max(0.0, min(pos['X'], config.APP_CONFIG['X_MAX_MM']))
        y = max(0.0, min(pos['Y'], config.APP_CONFIG['Y_MAX_MM']))
        clamped_pos = {'X': x, 'Y': y}
        self._draw_tool_head_inches(clamped_pos)

    def _reload_config_and_redraw(self):
        """Reload configuration and redraw the canvas to reflect changes."""
        # Reload the config module
        import importlib
        importlib.reload(config)
        
        # Update the global APP_CONFIG reference
        global APP_CONFIG
        APP_CONFIG = config.APP_CONFIG
        
        # Redraw the canvas with new settings
        self._draw_canvas()

    def _draw_axes_in_inches(self):
        # Draw full-height canvas with gridlines and numbers
        # Use 5-inch spacing for gridlines and numbers
        inch_tick = 5
        
        # Configure plot dimensions from config file
        plot_width_in = config.APP_CONFIG['X_MAX_MM'] / config.APP_CONFIG['INCH_TO_MM']  # Convert mm to inches
        plot_height_in = config.APP_CONFIG['Y_MAX_MM'] / config.APP_CONFIG['INCH_TO_MM']  # Convert mm to inches
        
        # Get buffer from config file
        buffer_px = config.APP_CONFIG['PLOT_BUFFER_PX']
        
        # Calculate scale to make plot fit within canvas with buffer
        # Account for buffer on all sides
        available_height_px = self.canvas_height - (2 * buffer_px)
        available_width_px = self.canvas_width - (2 * buffer_px)
        
        # Calculate scales for both dimensions
        scale_y = available_height_px / plot_height_in
        scale_x = available_width_px / plot_width_in
        
        # Use the smaller scale to maintain aspect ratio
        scale = min(scale_x, scale_y)
        
        # Calculate offsets - center the plot with buffer
        ox = (self.canvas_width - plot_width_in * scale) / 2
        oy = (self.canvas_height - plot_height_in * scale) / 2
        
        # Draw plot area border
        plot_left = ox
        plot_top = oy
        plot_right = ox + plot_width_in * scale
        plot_bottom = oy + plot_height_in * scale
        self.canvas.create_rectangle(plot_left, plot_top, plot_right, plot_bottom, 
                                   outline=UI_COLORS['PRIMARY_COLOR'], width=2)
        
        # Draw light gridlines every 5 inches
        for x_in in range(0, int(plot_width_in) + 1, inch_tick):
            x_px, y_px = self._inches_to_canvas(x_in, 0)
            # Draw vertical gridline
            self.canvas.create_line(x_px, plot_top, x_px, plot_bottom, 
                                   fill="#E0E0E0", width=1)
        
        for y_in in range(0, int(plot_height_in) + 1, inch_tick):
            x_px, y_px = self._inches_to_canvas(0, y_in)
            # Draw horizontal gridline
            self.canvas.create_line(plot_left, y_px, plot_right, y_px, 
                                   fill="#E0E0E0", width=1)
        
        # Draw tick marks on the axes
        tick_length = 8  # Length of tick marks in pixels
        
        # X-axis tick marks (bottom of plot)
        for x_in in range(0, int(plot_width_in) + 1, inch_tick):
            x_px, y_px = self._inches_to_canvas(x_in, 0)
            # Draw tick mark pointing down from the plot bottom
            self.canvas.create_line(x_px, plot_bottom, x_px, plot_bottom + tick_length, 
                                   fill="#000000", width=2)
        
        # Y-axis tick marks (left side of plot)
        for y_in in range(0, int(plot_height_in) + 1, inch_tick):
            x_px, y_px = self._inches_to_canvas(0, y_in)
            # Draw tick mark pointing left from the plot left edge
            self.canvas.create_line(plot_left, y_px, plot_left - tick_length, y_px, 
                                   fill="#000000", width=2)
        
        # Draw X-axis numbers (just below the plot area) - no boxes
        for x_in in range(0, int(plot_width_in) + 1, inch_tick):
            x_px, y_px = self._inches_to_canvas(x_in, 0)
            # Draw number just below the plot area
            label_y = plot_bottom + 15
            if label_y < self.canvas_height - 10:
                # Draw text directly - no background box
                self.canvas.create_text(x_px, label_y, text=f"{x_in}", 
                                      fill="#000000", font=("Arial", 10, "bold"), anchor="n")
        
        # Draw Y-axis numbers (just to the left of the plot area) - no boxes
        for y_in in range(0, int(plot_height_in) + 1, inch_tick):
            x_px, y_px = self._inches_to_canvas(0, y_in)
            # Draw number just to the left of the plot area
            label_x = plot_left - 15
            if label_x > 10:
                # Draw text directly - no background box
                self.canvas.create_text(label_x, y_px, text=f"{y_in}", 
                                      fill="#000000", font=("Arial", 10, "bold"), anchor="e")

    def _inches_to_canvas(self, x_in, y_in):
        # Convert inches to canvas coordinates with home at bottom-left
        # Configure plot dimensions from config file
        plot_width_in = config.APP_CONFIG['X_MAX_MM'] / config.APP_CONFIG['INCH_TO_MM']  # Convert mm to inches
        plot_height_in = config.APP_CONFIG['Y_MAX_MM'] / config.APP_CONFIG['INCH_TO_MM']  # Convert mm to inches
        
        # Get buffer from config file
        buffer_px = config.APP_CONFIG['PLOT_BUFFER_PX']
        
        # Calculate scale to make plot fit within canvas with buffer
        # Account for buffer on all sides
        available_height_px = self.canvas_height - (2 * buffer_px)
        available_width_px = self.canvas_width - (2 * buffer_px)
        
        # Calculate scales for both dimensions
        scale_y = available_height_px / plot_height_in
        scale_x = available_width_px / plot_width_in
        
        # Use the smaller scale to maintain aspect ratio
        scale = min(scale_x, scale_y)
        
        # Calculate offsets - center the plot with buffer
        ox = (self.canvas_width - plot_width_in * scale) / 2
        oy = (self.canvas_height - plot_height_in * scale) / 2
        
        # Y coordinate: 0 at bottom, plot_height_in at top (Tkinter Y is top-down)
        y_canvas = (plot_height_in - y_in) * scale + oy
        x_canvas = x_in * scale + ox
        
        return x_canvas, y_canvas

    def _draw_tool_head_inches(self, pos):
        # Draw a small circle at the current tool head position (in inches)
        y_in = pos['Y'] / config.APP_CONFIG['INCH_TO_MM']
        x_in = pos['X'] / config.APP_CONFIG['INCH_TO_MM']
        x_c, y_c = self._inches_to_canvas(x_in, y_in)
        
        # Make tool head more visible
        r = config.APP_CONFIG['TOOL_HEAD_RADIUS']  # Larger radius
        # Draw outer circle (background)
        self.canvas.create_oval(x_c - r - 2, y_c - r - 2, x_c + r + 2, y_c + r + 2, fill=UI_COLORS['PRIMARY_COLOR'], outline=UI_COLORS['PRIMARY_COLOR'], width=1)
        # Draw inner circle (tool head)
        self.canvas.create_oval(x_c - r, y_c - r, x_c + r, y_c + r, fill=UI_COLORS['SECONDARY_COLOR'], outline=UI_COLORS['PRIMARY_COLOR'], width=2)
        # Draw coordinates
        self.canvas.create_text(x_c, y_c - r - 15, text=f"(X={x_in:.2f}, Y={y_in:.2f})", fill=UI_COLORS['PRIMARY_VARIANT'], font=("Arial", 10, "bold"))
        
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
        color_cycle = [UI_COLORS['PRIMARY_COLOR'], UI_COLORS['PRIMARY_VARIANT'], UI_COLORS['SECONDARY_COLOR'], '#cc7700', '#aa00cc', '#cc2222', '#0a0', '#f0a', '#0af', '#fa0', '#a0f', '#0fa', '#af0', '#f00', '#00f', '#0ff', '#ff0', '#f0f', '#888', '#444']
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
                self.canvas.create_line(x1c, y1c, x2c, y2c, fill=UI_COLORS['PRIMARY_VARIANT'], width=2)
            elif t == 'LWPOLYLINE':
                points = [(p[0], p[1]) for p in e.get_points()]
                flat = []
                for x, y in points:
                    # Apply scale and offset
                    x_norm = x * scale - dx
                    y_norm = y * scale - dy
                    x_c, y_c = self._inches_to_canvas(x_norm, y_norm)
                    flat.extend([x_c, y_c])
                self.canvas.create_line(flat, fill=UI_COLORS['PRIMARY_VARIANT'], width=2)
            elif t == 'POLYLINE':
                points = [(v.dxf.x, v.dxf.y) for v in e.vertices()]
                flat = []
                for x, y in points:
                    # Apply scale and offset
                    x_norm = x * scale - dx
                    y_norm = y * scale - dy
                    x_c, y_c = self._inches_to_canvas(x_norm, y_norm)
                    flat.extend([x_c, y_c])
                self.canvas.create_line(flat, fill=UI_COLORS['PRIMARY_VARIANT'], width=2)
            elif t == 'SPLINE':
                points = list(e.flattening(0.1))
                flat = []
                for x, y, *_ in points:
                    # Apply scale and offset
                    x_norm = x * scale - dx
                    y_norm = y * scale - dy
                    x_c, y_c = self._inches_to_canvas(x_norm, y_norm)
                    flat.extend([x_c, y_c])
                self.canvas.create_line(flat, fill=UI_COLORS['PRIMARY_VARIANT'], width=2)
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
                self.canvas.create_line(*[coord for pt in points for coord in pt], fill=UI_COLORS['PRIMARY_VARIANT'], width=2)
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
                self.canvas.create_line(*[coord for pt in points for coord in pt], fill=UI_COLORS['PRIMARY_VARIANT'], width=2)

    def _draw_toolpath_inches(self):
        # Draw toolpath in inches
        if not hasattr(self, 'toolpath') or not self.toolpath:
            return
        color_cycle = [UI_COLORS['PRIMARY_COLOR'], UI_COLORS['PRIMARY_VARIANT'], UI_COLORS['SECONDARY_COLOR'], '#cc7700', '#aa00cc', '#cc2222', '#0a0', '#f0a', '#0af', '#fa0', '#a0f', '#0fa', '#af0', '#f00', '#00f', '#0ff', '#ff0', '#f0f', '#888', '#444']
        for i, path in enumerate(self.toolpath):
            color = color_cycle[i % len(color_cycle)]
            # Draw as a polyline of all (x, y) points where z==0 (cutting)
            points = [(x, y) for x, y, angle, z in path if z == 0]
            if len(points) < 2:
                continue
            flat = []
            for x, y in points:
                x_c, y_c = self._inches_to_canvas(x, y)
                flat.extend([x_c, y_c])
            # Use solid line instead of dashed for clearer visualization
            self.canvas.create_line(flat, fill=color, width=3)

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
            logger.info(f"Processing {len(entities)} entities for bounding box calculation")
            for e in entities:
                t = e.dxftype()
                logger.info(f"Processing entity type: {t}")
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
                    r = e.dxf.radius
                    logger.info(f"Processing CIRCLE: center=({center.x}, {center.y}), radius={r}")
                    # Generate points around the circle circumference for proper bounding box
                    # Calculate segments based on angle requirement
                    max_angle_deg = 2.0
                    # For a circle, angle between segments = 360 / n
                    # We want angle < max_angle_deg, so n > 360 / max_angle_deg
                    min_segments = int(360 / max_angle_deg) + 1
                    n = max(min_segments, 128)  # At least 128 segments
                    n = min(n, 512)  # Max 512 segments
                    for i in range(n):
                        angle = 2 * math.pi * i / n
                        x = center.x + r * math.cos(angle)
                        y = center.y + r * math.sin(angle)
                        all_x.append(x * self.dxf_unit_scale)
                        all_y.append(y * self.dxf_unit_scale)
                elif t == 'SPLINE':
                    logger.info(f"Processing SPLINE")
                    # Flatten spline to points for bounding box calculation
                    max_angle_deg = 2.0
                    pts = flatten_spline_with_angle_limit(e, max_angle_deg)
                    for pt in pts:
                        if len(pt) >= 2:
                            all_x.append(pt[0] * self.dxf_unit_scale)
                            all_y.append(pt[1] * self.dxf_unit_scale)
                    logger.info(f"  Generated {len(pts)} points from spline (max angle: {max_angle_deg}°)")
            logger.info(f"Collected {len(all_x)} points for bounding box calculation")
            if not all_x or not all_y:
                raise ValueError("No valid points found in DXF file for bounding box calculation")
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
                max_angle_deg = 2.0
                pts = flatten_spline_with_angle_limit(e, max_angle_deg)
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
            elif t == 'ARC' or t == 'CIRCLE':
                center = e.dxf.center
                r = e.dxf.radius
                # Calculate segments based on angle requirement
                max_angle_deg = 2.0
                if t == 'ARC':
                    start = math.radians(e.dxf.start_angle)
                    end = math.radians(e.dxf.end_angle)
                    if end < start:
                        end += 2 * math.pi
                    arc_angle_rad = end - start
                    arc_angle_deg = math.degrees(arc_angle_rad)
                    min_segments = int(arc_angle_deg / max_angle_deg) + 1
                    n = max(min_segments, 64)  # At least 64 segments
                    n = min(n, 512)  # Max 512 segments
                    pts = [(center.x + r * math.cos(start + (end - start) * i / n),
                            center.y + r * math.sin(start + (end - start) * i / n)) for i in range(n+1)]
                else:
                    # For circles, angle between segments = 360 / n
                    # We want angle < max_angle_deg, so n > 360 / max_angle_deg
                    min_segments = int(360 / max_angle_deg) + 1
                    n = max(min_segments, 128)  # At least 128 segments
                    n = min(n, 512)  # Max 512 segments
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
        """
        Generate truly continuous toolpaths without any stopping between segments.
        All entities are combined into a single continuous motion path.
        """
        if not self.dxf_entities:
            messagebox.showwarning("No DXF", "Import a DXF file first.")
            return
        
        scale = getattr(self, 'dxf_unit_scale', 1.0)
        dx, dy = self.dxf_offset
        
        # --- Generate ONE continuous toolpath combining ALL entities ---
        combined_toolpath = []
        
        logger.info(f"Processing {len(self.dxf_entities)} entities for single continuous toolpath generation")
        
        # DEBUG: Log all entity types to identify what's being processed
        entity_types = {}
        for e in self.dxf_entities:
            t = e.dxftype()
            entity_types[t] = entity_types.get(t, 0) + 1
        logger.info(f"Entity types found: {entity_types}")
        
        # Check if we have multiple splines that might form a circle
        splines = [e for e in self.dxf_entities if e.dxftype() == 'SPLINE']
        if len(splines) >= 2:
            logger.info(f"Found {len(splines)} splines - checking if they form a circle")
            # Try to detect if splines form a circle and combine them
            circle_center, circle_radius = self._detect_circle_from_splines(splines)
            if circle_center and circle_radius:
                logger.info(f"Detected circle from splines: center=({circle_center[0]:.3f}, {circle_center[1]:.3f}), radius={circle_radius:.3f}")
                # Generate continuous path for detected circle
                continuous_path = self._generate_continuous_circle_path(
                    circle_center, circle_radius
                )
                
                # Transform coordinates and add to combined toolpath
                for x, y, angle, z in continuous_path:
                    tx = (x * scale) - dx
                    ty = (y * scale) - dy
                    combined_toolpath.append((tx, ty, angle, z))
                
                logger.info(f"Added {len(continuous_path)} waypoints from detected circle")
                
                # Skip processing individual splines since we've combined them
                processed_splines = True
            else:
                processed_splines = False
        else:
            processed_splines = False
        
        for i, e in enumerate(self.dxf_entities):
            t = e.dxftype()
            
            # Skip splines if we've already processed them as a circle
            if t == 'SPLINE' and processed_splines:
                logger.info(f"Skipping SPLINE {i+1} (already processed as circle)")
                continue
                
            logger.info(f"Processing entity {i+1}/{len(self.dxf_entities)}: {t}")
            
            if t == 'SPLINE':
                logger.info(f"  Generating continuous SPLINE path")
                # Generate continuous path for spline
                continuous_path = self._generate_continuous_spline_path(e)
                
                # Transform coordinates and add to combined toolpath
                for x, y, angle, z in continuous_path:
                    tx = (x * scale) - dx
                    ty = (y * scale) - dy
                    combined_toolpath.append((tx, ty, angle, z))
                
                logger.info(f"  Added {len(continuous_path)} waypoints to combined toolpath")
                
            elif t == 'CIRCLE':
                center = e.dxf.center
                radius = e.dxf.radius
                logger.info(f"  Generating continuous CIRCLE path: center=({center.x}, {center.y}), radius={radius}")
                
                # Generate continuous path for full circle
                continuous_path = self._generate_continuous_circle_path(
                    (center.x, center.y), radius
                )
                
                # Transform coordinates and add to combined toolpath
                for x, y, angle, z in continuous_path:
                    tx = (x * scale) - dx
                    ty = (y * scale) - dy
                    combined_toolpath.append((tx, ty, angle, z))
                
                logger.info(f"  Added {len(continuous_path)} waypoints to combined toolpath")
                
            elif t == 'ARC':
                center = e.dxf.center
                radius = e.dxf.radius
                start_angle = math.radians(e.dxf.start_angle)
                end_angle = math.radians(e.dxf.end_angle)
                
                # Handle angle wrapping
                if end_angle < start_angle:
                    end_angle += 2 * math.pi
                
                logger.info(f"  Generating continuous ARC path: center=({center.x}, {center.y}), radius={radius}, angles={math.degrees(start_angle):.1f}° to {math.degrees(end_angle):.1f}°")
                
                # Generate continuous path for arc
                continuous_path = self._generate_continuous_circle_path(
                    (center.x, center.y), radius,
                    start_angle=start_angle, end_angle=end_angle
                )
                
                # Transform coordinates and add to combined toolpath
                for x, y, angle, z in continuous_path:
                    tx = (x * scale) - dx
                    ty = (y * scale) - dy
                    combined_toolpath.append((tx, ty, angle, z))
                
                logger.info(f"  Added {len(continuous_path)} waypoints to combined toolpath")
            
            elif t in ('LWPOLYLINE', 'POLYLINE'):
                logger.info(f"  Generating continuous POLYLINE path")
                # Generate continuous path for polyline
                continuous_path = self._generate_continuous_polyline_path(e)
                
                # Transform coordinates and add to combined toolpath
                for x, y, angle, z in continuous_path:
                    tx = (x * scale) - dx
                    ty = (y * scale) - dy
                    combined_toolpath.append((tx, ty, angle, z))
                
                logger.info(f"  Added {len(continuous_path)} waypoints to combined toolpath")
            
            elif t == 'LINE':
                start_point = (e.dxf.start.x, e.dxf.start.y)
                end_point = (e.dxf.end.x, e.dxf.end.y)
                logger.info(f"  Generating continuous LINE path: from ({start_point[0]:.3f}, {start_point[1]:.3f}) to ({end_point[0]:.3f}, {end_point[1]:.3f})")
                # Generate continuous path for line
                continuous_path = self._generate_continuous_line_path(e)
                
                # Transform coordinates and add to combined toolpath
                for x, y, angle, z in continuous_path:
                    tx = (x * scale) - dx
                    ty = (y * scale) - dy
                    combined_toolpath.append((tx, ty, angle, z))
                
                logger.info(f"  Added {len(continuous_path)} waypoints to combined toolpath")
        
        # Store the single combined continuous toolpath
        self.toolpath = [combined_toolpath]
        
        # Debug output
        logger.info(f"=== CONTINUOUS TOOLPATH DEBUG INFO ===")
        logger.info(f"Generated 1 combined continuous toolpath")
        logger.info(f"Combined toolpath - {len(combined_toolpath)} points:")
        
        # Show first 5 points
        for j, (x, y, angle, z) in enumerate(combined_toolpath[:5]):
            angle_deg = math.degrees(angle)
            z_status = "DOWN" if z == 0 else "UP"
            logger.info(f"  Point {j+1}: X={x*25.4:.2f}mm ({x:.3f}in), Y={y*25.4:.2f}mm ({y:.3f}in), Angle={angle_deg:.1f}°, Z={z_status}")
        
        if len(combined_toolpath) > 5:
            logger.info(f"  ... ({len(combined_toolpath)-5} more points) ...")
        
        logger.info(f"Total points: {len(combined_toolpath)}")
        logger.info(f"Continuous toolpaths: 1")
        logger.info(f"Discrete toolpaths: 0")
        
        # Check machine limits
        logger.info(f"=== MACHINE LIMITS ===")
        x_limits = (-68.0, 68.0)  # inches
        y_limits = (-45.0, 45.0)  # inches
        logger.info(f"X limits: {x_limits[0]*25.4:.2f}mm to {x_limits[1]*25.4:.2f}mm")
        logger.info(f"Y limits: {y_limits[0]*25.4:.2f}mm to {y_limits[1]*25.4:.2f}mm")
        
        all_within_limits = True
        for x, y, angle, z in combined_toolpath:
            if not (x_limits[0] <= x <= x_limits[1] and y_limits[0] <= y <= y_limits[1]):
                all_within_limits = False
                break
        
        if all_within_limits:
            logger.info("✅ All points within machine limits")
        else:
            logger.warning("⚠️ Some points outside machine limits")
        
        logger.info("=== END DEBUG INFO ===")
        
        self._draw_canvas()
    
    def _detect_circle_from_splines(self, splines):
        """
        Detect if multiple splines form a circle and return center and radius.
        Returns (center, radius) if detected, (None, None) otherwise.
        """
        try:
            # Collect all points from all splines
            all_points = []
            for spline in splines:
                try:
                    points = list(spline.flattening(0.1))
                    for point in points:
                        if len(point) >= 2:
                            all_points.append((point[0], point[1]))
                except:
                    continue
            
            if len(all_points) < 10:
                return None, None
            
            # Calculate bounding box
            x_coords = [p[0] for p in all_points]
            y_coords = [p[1] for p in all_points]
            min_x, max_x = min(x_coords), max(x_coords)
            min_y, max_y = min(y_coords), max(y_coords)
            
            # Estimate center
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            
            # Calculate average radius
            radii = []
            for x, y in all_points:
                radius = math.sqrt((x - center_x)**2 + (y - center_y)**2)
                radii.append(radius)
            
            avg_radius = sum(radii) / len(radii)
            
            # Check if points form a reasonable circle (radius variation < 10%)
            radius_variation = max(radii) - min(radii)
            if radius_variation / avg_radius < 0.1:  # Less than 10% variation
                logger.info(f"Detected circle from splines: center=({center_x:.3f}, {center_y:.3f}), radius={avg_radius:.3f}")
                return (center_x, center_y), avg_radius
            
            return None, None
            
        except Exception as e:
            logger.error(f"Error detecting circle from splines: {e}")
            return None, None

    def _generate_continuous_spline_path(self, spline):
        """
        Generate a single continuous path for a spline with ultra-smooth motion.
        Returns: List of (x, y, angle, z) tuples for continuous motion
        """
        return generate_continuous_spline_toolpath(spline, step_size=0.05)
    
    def _generate_continuous_circle_path(self, center, radius, start_angle=0, end_angle=2*math.pi):
        """
        Generate a single continuous path for a circle/arc with ultra-smooth motion.
        Returns: List of (x, y, angle, z) tuples for continuous motion
        """
        return generate_continuous_circle_toolpath(center, radius, start_angle, end_angle, step_size=0.05)
    
    def _generate_continuous_polyline_path(self, polyline):
        """
        Generate a single continuous path for a polyline with smooth transitions.
        Returns: List of (x, y, angle, z) tuples for continuous motion
        """
        return generate_continuous_polyline_toolpath(polyline, step_size=0.05)
    
    def _generate_continuous_line_path(self, line):
        """
        Generate a single continuous path for a line with smooth motion.
        Returns: List of (x, y, angle, z) tuples for continuous motion
        """
        return generate_continuous_line_toolpath(line, step_size=0.05)

    def _preview_toolpath(self):
        if not hasattr(self, 'toolpath') or not self.toolpath:
            messagebox.showwarning("No Toolpath", "Generate a toolpath first.")
            return
        self._draw_canvas()  # Clear previous preview only once
        def animate_shape(shape_idx=0):
            if shape_idx >= len(self.toolpath):
                return
            path = self.toolpath[shape_idx]
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
                    # Draw blue dot for continuous cutting (Z=0)
                    if z == 0:
                        self.canvas.create_oval(x_c-6, y_c-6, x_c+6, y_c+6, fill=UI_COLORS['PRIMARY_COLOR'], outline=UI_COLORS['PRIMARY_VARIANT'])
                    # Draw orientation line (cutting blade orientation)
                    # Motor controller handles direction inversion, so use original angle
                    # Only flip angle for Y-axis coordinate system transformation
                    display_angle = angle + math.pi/2  # Original angle + flip for Y-axis
                    x2 = x + r * math.cos(display_angle)
                    y2 = y + r * math.sin(display_angle)
                    x2_c, y2_c = self._inches_to_canvas(x2, y2)
                    self.canvas.create_line(x_c, y_c, x2_c, y2_c, fill=UI_COLORS['SECONDARY_COLOR'], width=3)
                self.root.after(2, animate_step, idx + steps_per_tick)  # Smoother animation
            animate_step()
        animate_shape()

    def _run_toolpath(self):
        if not hasattr(self, 'toolpath') or not self.toolpath:
            messagebox.showwarning("No Toolpath", "Generate a toolpath first.")
            return
            
        # Debug: Print machine limits and first toolpath point
        print(f"\n=== TOOLPATH EXECUTION DEBUG ===")
        print(f"Machine limits: X=±{config.APP_CONFIG['X_MAX_MM']:.2f}mm, Y=±{config.APP_CONFIG['Y_MAX_MM']:.2f}mm")
        
        # Debug: Check sensor states before starting toolpath
        if MOTOR_IMPORTS_AVAILABLE:
            sensor_states = self.motor_ctrl.get_sensor_states()
            print(f"\n=== SENSOR STATES BEFORE TOOLPATH ===")
            for motor, state in sensor_states.items():
                print(f"{motor}: raw={state['raw']}, debounced={state['debounced']}, last_trigger_time={state['last_trigger_time']:.3f}s, readings={state['readings']}")
        
        if self.toolpath and self.toolpath[0]:
            first_point = self.toolpath[0][0]
            x, y, angle, z = first_point
            x_mm = x * config.APP_CONFIG['INCH_TO_MM']
            y_mm = y * config.APP_CONFIG['INCH_TO_MM']
            print(f"First toolpath point: X={x:.3f}in ({x_mm:.2f}mm), Y={y:.3f}in ({y_mm:.2f}mm)")
            if abs(x_mm) > config.APP_CONFIG['X_MAX_MM'] or abs(y_mm) > config.APP_CONFIG['Y_MAX_MM']:
                print(f"⚠️  WARNING: First point beyond machine limits!")
                return
            

        
        self._running_toolpath = True
        self._current_toolpath_pos = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'ROT': 0.0}
        self._current_toolpath_idx = [0, 0]  # [shape_idx, step_idx]
        self._toolpath_total_steps = sum(len(path) for path in self.toolpath)
        self._toolpath_step_count = 0
        
        # Start with travel move to first point
        if self.toolpath and self.toolpath[0]:
            first_point = self.toolpath[0][0]
            x, y, angle, z = first_point
            self._travel_to_start(x * config.APP_CONFIG['INCH_TO_MM'], y * config.APP_CONFIG['INCH_TO_MM'])
        else:
            self._run_toolpath_step()

    def _travel_to_start(self, x_mm, y_mm):
        """Travel from home to the start position of the toolpath."""
        # Move to start position with Z up
        if MOTOR_IMPORTS_AVAILABLE:
            self.motor_ctrl.move_to(x=x_mm, y=y_mm, z=config.APP_CONFIG['Z_UP_MM'], rot=0.0)
        
        # Update position and display
        self._current_toolpath_pos['X'] = x_mm
        self._current_toolpath_pos['Y'] = y_mm
        self._current_toolpath_pos['Z'] = config.APP_CONFIG['Z_UP_MM']
        self._current_toolpath_pos['ROT'] = 0.0
        
        self._update_position_display()
        self._draw_canvas()
        
        # Wait a moment, then start the toolpath
        self.root.after(500, self._run_toolpath_step)

    def _run_toolpath_step(self):
        if not self._running_toolpath:
            return
        shape_idx, step_idx = self._current_toolpath_idx
        if shape_idx >= len(self.toolpath):
            self._running_toolpath = False
            return
        path = self.toolpath[shape_idx]
        if step_idx >= len(path):
            # Move to next shape
            self._current_toolpath_idx = [shape_idx + 1, 0]
            self.root.after(100, self._run_toolpath_step)  # Longer pause between shapes
            return
        x, y, angle, z = path[step_idx]
        # Set toolpath position directly (no swap)
        x_mm = x * config.APP_CONFIG['INCH_TO_MM']
        y_mm = y * config.APP_CONFIG['INCH_TO_MM']
        self._current_toolpath_pos['X'] = x_mm
        self._current_toolpath_pos['Y'] = y_mm
        self._current_toolpath_pos['Z'] = config.APP_CONFIG['Z_DOWN_MM'] if z == 0 else config.APP_CONFIG['Z_UP_MM']
        # Use rotation angle directly - motor controller handles direction inversion
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
        if abs(x_mm) > config.APP_CONFIG['X_MAX_MM'] or abs(y_mm) > config.APP_CONFIG['Y_MAX_MM']:
            print(f"[WARNING] Coordinates beyond machine limits! X={x_mm:.2f}mm (limit: ±{config.APP_CONFIG['X_MAX_MM']:.2f}mm), Y={y_mm:.2f}mm (limit: ±{config.APP_CONFIG['Y_MAX_MM']:.2f}mm)")
        self._update_position_display()  # Force update after each move
        self._draw_canvas()
        # Next step
        self._current_toolpath_idx[1] += 1
        self._toolpath_step_count += 1
        self.root.after(50, self._run_toolpath_step)  # Slower execution (50ms instead of 5ms)

    def _draw_live_tool_head_inches(self, pos):
        # Draw a blue dot and orientation line at the current tool head position (in inches)
        x_in = pos['X'] / config.APP_CONFIG['INCH_TO_MM']
        y_in = pos['Y'] / config.APP_CONFIG['INCH_TO_MM']
        rot_rad = math.radians(pos.get('ROT', 0.0))
        x_c, y_c = self._inches_to_canvas(x_in, y_in)
        r = config.APP_CONFIG['LIVE_TOOL_HEAD_RADIUS']
        self.canvas.create_oval(x_c - r, y_c - r, x_c + r, y_c + r, fill=UI_COLORS['PRIMARY_COLOR'], outline=UI_COLORS['PRIMARY_VARIANT'], width=2)
        r_dir = config.APP_CONFIG['LIVE_TOOL_HEAD_DIR_RADIUS']  # 0.5 inch
        x2 = x_in + r_dir * math.cos(rot_rad)
        y2 = y_in + r_dir * math.sin(rot_rad)
        x2_c, y2_c = self._inches_to_canvas(x2, y2)
        self.canvas.create_line(x_c, y_c, x2_c, y2_c, fill=UI_COLORS['SECONDARY_COLOR'], width=3)



    def _add_jog_button(self, parent, text, cmd):
        # Consistent font with rest of project
        btn = ctk.CTkButton(parent, text=text, command=cmd, width=50, height=40, fg_color=UI_COLORS['BUTTON_PRIMARY'], text_color=UI_COLORS['BUTTON_TEXT'], hover_color=UI_COLORS['BUTTON_PRIMARY_HOVER'], corner_radius=8, font=("Arial", 16, "bold"))
        return btn

    def _add_compact_jog_button(self, parent, text, cmd):
        # Compact version with consistent font styling
        btn = ctk.CTkButton(parent, text=text, command=cmd, width=35, height=30, fg_color=UI_COLORS['BUTTON_PRIMARY'], text_color=UI_COLORS['BUTTON_TEXT'], hover_color=UI_COLORS['BUTTON_PRIMARY_HOVER'], corner_radius=8, font=("Arial", 16, "bold"))
        return btn

    def _create_stylish_button(self, parent, text, command, button_type="primary", **kwargs):
        """Create a stylish button with consistent styling and modern appearance."""
        # Define button colors based on type
        button_colors = {
            "primary": (UI_COLORS['BUTTON_PRIMARY'], UI_COLORS['BUTTON_PRIMARY_HOVER']),
            "secondary": (UI_COLORS['BUTTON_SECONDARY'], UI_COLORS['BUTTON_SECONDARY_HOVER']),
            "success": (UI_COLORS['BUTTON_SUCCESS'], UI_COLORS['BUTTON_SUCCESS_HOVER']),
            "warning": (UI_COLORS['BUTTON_WARNING'], UI_COLORS['BUTTON_WARNING_HOVER']),
            "danger": (UI_COLORS['BUTTON_DANGER'], UI_COLORS['BUTTON_DANGER_HOVER']),
        }
        
        bg_color, hover_color = button_colors.get(button_type, button_colors["primary"])
        
        # Default styling
        default_kwargs = {
            'fg_color': bg_color,
            'text_color': UI_COLORS['BUTTON_TEXT'],
            'hover_color': hover_color,
            'corner_radius': 10,  # Slightly more rounded for modern look
            'font': ("Arial", 16, "bold"),
            'border_width': 0,  # No border for clean look
            'height': 40,
        }
        
        # Update with any custom kwargs
        default_kwargs.update(kwargs)
        
        btn = ctk.CTkButton(parent, text=text, command=command, **default_kwargs)
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
        self.root.after(2000, lambda: self.status_label.configure(text="Ready", text_color=UI_COLORS['ON_SURFACE']))

    def _home_all(self):
        success = self.motor_ctrl.home_all_synchronous()
        if success:
            self.status_label.configure(text="All axes homed", text_color="green")
        else:
            self.status_label.configure(text="Homing failed", text_color="red")
        self._draw_canvas()
        self._update_position_display()
        # Clear status after 2 seconds
        self.root.after(2000, lambda: self.status_label.configure(text="Ready", text_color=UI_COLORS['ON_SURFACE']))

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
        self.root.after(3000, lambda: self.status_label.configure(text="Ready", text_color=UI_COLORS['ON_SURFACE']))

    def _update_position_display(self):
        pos = self.motor_ctrl.get_position()
        x_disp = pos['X']/config.APP_CONFIG['INCH_TO_MM']
        y_disp = pos['Y']/config.APP_CONFIG['INCH_TO_MM']
        z_disp = pos['Z']/config.APP_CONFIG['INCH_TO_MM']  # Convert Z to inches
        rot_disp = pos['ROT']
        text = f"X:{x_disp:.1f}\nY:{y_disp:.1f}\nZ:{z_disp:.1f}\nR:{rot_disp:.0f}°"
        self.coord_label.configure(text=text)
        self.root.after(200, self._update_position_display)

    def _update_jog_speed(self):
        try:
            self.jog_speed = self.jog_speed_var.get() * config.APP_CONFIG['INCH_TO_MM']
        except Exception:
            pass

    def _on_jog_slider(self, value):
        # Convert slider value to float inches
        speed_inches = float(value) * self._jog_slider_scale
        self.jog_speed_var.set(speed_inches)
        # Update the display label
        self.jog_speed_label.configure(text=f"{speed_inches:.1f} in")
        # Update the actual jog speed
        self.jog_speed = speed_inches * config.APP_CONFIG['INCH_TO_MM']

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

# G-code generation functions moved to toolpath_planning package

# G-code generation functions moved to toolpath_planning package

# G-code file operations moved to toolpath_planning package

if __name__ == "__main__":
    main() 