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
import re
from typing import List, Tuple, Optional, Dict

# Try to import ezdxf for DXF parsing
try:
    from ezdxf.filemanagement import readfile
    import ezdxf
except ImportError:
    ezdxf = None

# Import motor control modules
try:
    from motor_control.motor_controller import MotorController
    from motor_control.smooth_motion_executor import SmoothMotionExecutor
except ImportError:
    pass

# Import new DXF processing and toolpath generation modules
try:
    from dxf_processing.dxf_processor import DXFProcessor
    from toolpath_planning.toolpath_generator import ToolpathGenerator
    from toolpath_planning.gcode_visualizer import GCodeVisualizer
    DXF_TOOLPATH_IMPORTS_AVAILABLE = True
except ImportError:
    DXF_TOOLPATH_IMPORTS_AVAILABLE = False



# Import configuration
import config
from config import (
    UI_COLORS, UI_PADDING,
    ON_RPI, SIMULATION_MODE
)



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fabric_cnc.main_app")

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")



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
            return max(-config.APP_CONFIG['X_MAX_INCH'], min(value, config.APP_CONFIG['X_MAX_INCH']))  # Allow negative X positions
        elif axis == 'Y':
            return max(-config.APP_CONFIG['Y_MAX_INCH'], min(value, config.APP_CONFIG['Y_MAX_INCH']))  # Allow negative Y positions
        elif axis == 'Z':
            return max(0.0, min(value, config.APP_CONFIG['Z_MAX_INCH']))  # Keep Z positive only
        else:
            return value

    def jog(self, axis, delta):
        with self.lock:
            new_val = self.position[axis] + delta
            self.position[axis] = self._clamp(axis, new_val)
            logger.info(f"Jogged {axis} by {delta}in. New pos: {self.position[axis]:.2f}")

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

    def move_coordinated(self, x_distance_inch=0, y_distance_inch=0, z_distance_inch=0, rot_distance_deg=0):
        """Execute coordinated movement across multiple axes (simulated)."""
        with self.lock:
            self.position['X'] += x_distance_inch
            self.position['Y'] += y_distance_inch
            self.position['Z'] += z_distance_inch
            self.position['ROT'] += rot_distance_deg
            logger.info(f"Simulated coordinated movement: X={self.position['X']:.2f}, Y={self.position['Y']:.2f}, Z={self.position['Z']:.2f}, ROT={self.position['ROT']:.2f}")

# --- Real Motor Controller Wrapper ---
class RealMotorController:
    def __init__(self):
        self.motor_controller = MotorController()
        self.lock = threading.Lock()
        self.is_homing = False
        self.position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'ROT': 0.0}  # Track position manually

    def _clamp(self, axis, value):
        if axis == 'X':
            return max(-config.APP_CONFIG['X_MAX_INCH'], min(value, config.APP_CONFIG['X_MAX_INCH']))  # Allow negative X positions
        elif axis == 'Y':
            return max(-config.APP_CONFIG['Y_MAX_INCH'], min(value, config.APP_CONFIG['Y_MAX_INCH']))  # Allow negative Y positions
        elif axis == 'Z':
            return max(-config.APP_CONFIG['Z_MAX_INCH'], min(value, config.APP_CONFIG['Z_MAX_INCH']))  # Allow negative Z positions
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
                    logger.info(f"Jogged {axis} by {move_delta}in")
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
                logger.info(f"Position reset after homing: {self.position}")
                
                # Debug sensor states after homing - removed non-existent module
                
                self.is_homing = False
                return True
            except Exception as e:
                logger.error(f"Synchronous home error: {e}")
                self.is_homing = False
                return False

    def get_position(self):
        # Use motor controller's actual position tracking
        if hasattr(self.motor_controller, 'get_position'):
            motor_pos = self.motor_controller.get_position()
            # Motor controller now tracks position in inches internally
            return motor_pos
        else:
            # Fallback to internal position tracking
            with self.lock:
                return dict(self.position)
    
    def sync_position(self):
        """Sync position tracking with actual motor controller position."""
        try:
            # Since motor controller doesn't track position, just reset to 0 after homing
            with self.lock:
                self.position = {
                    'X': 0.0,
                    'Y': 0.0, 
                    'Z': 0.0,
                    'ROT': 0.0
                }
            logger.info(f"Position synced to home: {self.position}")
        except Exception as e:
            logger.warning(f"Could not sync position: {e}")
    
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
        # Calculate deltas for all axes (get current position with lock)
        with self.lock:
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
        
        logger.info(f"MOVE_TO: current=({self.position['X']:.1f},{self.position['Y']:.1f},{self.position['Z']:.1f},{self.position['ROT']:.1f}) -> target=({x or self.position['X']:.1f},{y or self.position['Y']:.1f},{z or self.position['Z']:.1f},{rot or self.position['ROT']:.1f}) -> delta=({delta_x:.2f},{delta_y:.2f},{delta_z:.2f},{delta_rot:.2f})")
        
        # Use coordinated movement for X and Y, individual for Z and ROT
        if abs(delta_x) > 1e-6 or abs(delta_y) > 1e-6:
            self.move_coordinated(
                x_distance_inch=delta_x,
                y_distance_inch=delta_y,
                z_distance_inch=delta_z,
                rot_distance_deg=delta_rot
            )
        else:
            # Only Z or ROT movement needed
            if abs(delta_z) > 1e-6:
                # Motor controller now works in inches directly
                self.motor_controller.move_distance(delta_z, 'Z')
            if abs(delta_rot) > 1e-6:
                self.motor_controller.move_distance(delta_rot, 'ROT')
        
        # Update position tracking with ACTUAL achieved positions (not requested)
        # The motor controller may limit movements, so we need to track what was actually achieved
        with self.lock:
            if x is not None:
                self.position['X'] = x
            if y is not None:
                self.position['Y'] = y
            if z is not None:
                # Check if Z movement was limited by the motor controller
                # If the target Z position is below -1.35 inches, limit it to -1.35 inches
                if z < -1.35:  # -1.35 inch limit
                    actual_z = -1.35  # Limit target to -1.35 inches
                    logger.warning(f"Z target limited: requested {z:.2f} inches, actual {actual_z:.2f} inches")
                    self.position['Z'] = actual_z
                else:
                    self.position['Z'] = z
            if rot is not None:
                self.position['ROT'] = rot

    def move_coordinated(self, x_distance_inch=0, y_distance_inch=0, z_distance_inch=0, rot_distance_deg=0):
        """Execute coordinated movement across multiple axes."""
        try:
            # Motor controller now works in inches directly
            self.motor_controller.move_coordinated(
                x_distance_inch=x_distance_inch,
                y_distance_inch=y_distance_inch,
                z_distance_inch=z_distance_inch,
                rot_distance_deg=rot_distance_deg
            )
            
            # Update position tracking (use lock only for position update)
            with self.lock:
                self.position['X'] += x_distance_inch
                self.position['Y'] += y_distance_inch
                self.position['Z'] += z_distance_inch
                self.position['ROT'] += rot_distance_deg
            
        except Exception as e:
            logger.error(f"Coordinated movement error: {e}")
            raise

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
        self.jog_speed = 1.0  # Default to 1 inch
        self.jog_speed_var = ctk.DoubleVar(value=1.0)  # Default to 1 inch
        self._jog_slider_scale = 0.1  # Scale factor for slider (0.1 inch increments)
        self._arrow_key_state = {}
        self._arrow_key_after_ids = {}

        self.motor_ctrl = SimulatedMotorController() if SIMULATION_MODE else RealMotorController()
        self._jog_in_progress = {'X': False, 'Y': False, 'Z': False, 'ROT': False}
        self._arrow_key_repeat_delay = config.APP_CONFIG['ARROW_KEY_REPEAT_DELAY']
        
        # Initialize new DXF processing and toolpath generation
        if DXF_TOOLPATH_IMPORTS_AVAILABLE:
            self.dxf_processor = DXFProcessor()
            self.toolpath_generator = ToolpathGenerator(
                cutting_height=-1.35,  # Updated: -1.35 inches for deeper cuts
                safe_height=-0.5,  # Safe height is -0.5 inches (above cutting height)
                corner_angle_threshold=10.0,  # 10-degree threshold
                feed_rate=1000.0,
                plunge_rate=200.0
            )
            self.smooth_motion_executor = SmoothMotionExecutor(self.motor_ctrl)
            self.gcode_visualizer = GCodeVisualizer()
        else:
            self.dxf_processor = None
            self.toolpath_generator = None
            self.smooth_motion_executor = None
            self.gcode_visualizer = None
        

        
        # New DXF processing attributes
        self.processed_shapes = {}
        self.generated_gcode = ""
        self.gcode_file_path = ""
        self._setup_ui()
        self._bind_arrow_keys()
        self._update_position_display()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        # Force fullscreen after UI setup
        self.root.after(100, lambda: self.root.attributes('-fullscreen', True))

    def _wrap_status_text(self, text, max_chars=20):
        """Wrap status text at specified character limit to prevent horizontal expansion."""
        if len(text) <= max_chars:
            return text
        
        # First try word wrapping - try to break at word boundaries
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            # If a single word is longer than max_chars, we need to break it
            if len(word) > max_chars:
                # If we have content in current_line, add it to lines first
                if current_line:
                    lines.append(current_line)
                    current_line = ""
                
                # Break the long word into chunks
                for i in range(0, len(word), max_chars):
                    chunk = word[i:i + max_chars]
                    lines.append(chunk)
            elif len(current_line) + len(word) + 1 <= max_chars:
                if current_line:
                    current_line += " " + word
                else:
                    current_line = word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return "\n".join(lines)

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
            ("Preview Toolpath", self._preview_toolpath, "secondary"),
            ("Run Toolpath", self._run_toolpath, "success"),
            ("Stop Execution", self._stop_execution, "warning"),
            ("E-Stop", self._estop, "danger")
        ]
        
        for text, command, button_type in file_buttons:
            btn = self._create_stylish_button(file_section, text, command, button_type)
            btn.pack(fill="x", padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'])
        
        # Status section - fills width but wraps height around text
        status_section = ctk.CTkFrame(self.left_column, fg_color="#d0d0d0", corner_radius=8)
        status_section.grid(row=1, column=0, sticky="ew", padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'])
        
        ctk.CTkLabel(status_section, text="Status:", font=("Arial", 16, "bold"), text_color=UI_COLORS['PRIMARY_COLOR']).pack(pady=UI_PADDING['SMALL'])
        self.status_label = ctk.CTkLabel(status_section, text="Ready", font=("Arial", 16, "bold"), text_color=UI_COLORS['ON_SURFACE'], wraplength=300)
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
            delta = +self.jog_speed
        elif key == 'Up':
            axis = 'Y'
            delta = self.jog_speed
        elif key == 'Down':
            axis = 'Y'
            delta = -self.jog_speed
        elif key == 'Page_Up':
            axis = 'Z'
            delta = 1.0  # 1 inch up
        elif key == 'Page_Down':
            axis = 'Z'
            delta = -1.0  # 1 inch down
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
        
        # Draw processed shapes from new DXF processor
        if self.processed_shapes:
            self._draw_processed_shapes()
        

        

        
        # Draw new toolpath preview if available
        if hasattr(self, 'toolpath_data') and self.toolpath_data:
            self._draw_toolpath_inches()
        
        # Draw current tool head position (all axes)
        pos = self.motor_ctrl.get_position()
        # Positions are already in inches, so clamp using inch limits
        x_max_inches = config.APP_CONFIG['X_MAX_INCH']
        y_max_inches = config.APP_CONFIG['Y_MAX_INCH']
        x = max(0.0, min(pos['X'], x_max_inches))
        y = max(0.0, min(pos['Y'], y_max_inches))
        clamped_pos = {'X': x, 'Y': y}
        self._draw_tool_head_inches(clamped_pos)

    def _draw_processed_shapes(self):
        """Draw processed shapes from the new DXF processor."""
        if not self.processed_shapes:
            return
        
        # Color palette for different shapes
        shape_colors = [
            '#FF6B6B',  # Red
            '#4ECDC4',  # Teal
            '#45B7D1',  # Blue
            '#96CEB4',  # Green
            '#FFEAA7',  # Yellow
            '#DDA0DD',  # Plum
            '#98D8C8',  # Mint
            '#F7DC6F',  # Gold
            '#BB8FCE',  # Purple
            '#85C1E9',  # Sky Blue
            '#F8C471',  # Orange
            '#82E0AA',  # Light Green
            '#F1948A',  # Salmon
            '#85C1E9',  # Light Blue
            '#FAD7A0',  # Peach
        ]
        
        # DXF processor now outputs coordinates in inches directly
        for i, (shape_name, points) in enumerate(self.processed_shapes.items()):
            if not points or len(points) < 2:
                continue
            
            # Select color for this shape
            color = shape_colors[i % len(shape_colors)]
            
            # Convert points to canvas coordinates
            canvas_points = []
            for x_in, y_in in points:
                x_canvas, y_canvas = self._inches_to_canvas(x_in, y_in)
                canvas_points.extend([x_canvas, y_canvas])
            
            # Draw the shape as a polyline
            if len(canvas_points) >= 4:  # Need at least 2 points (4 coordinates)
                self.canvas.create_line(canvas_points, 
                                      fill=color, 
                                      width=2)
                
                # Draw shape name at the first point
                if canvas_points:
                    x_canvas, y_canvas = canvas_points[0], canvas_points[1]
                    self.canvas.create_text(x_canvas + 10, y_canvas - 10, 
                                          text=shape_name, 
                                          fill=color,
                                          font=("Arial", 8, "bold"))
        
        logger.debug(f"Drew {len(self.processed_shapes)} processed shapes with unique colors")



    def _draw_axes_in_inches(self):
        # Draw full-height canvas with gridlines and numbers
        # Use 5-inch spacing for gridlines and numbers
        inch_tick = 5
        
        # Configure plot dimensions from config file
        plot_width_in = config.APP_CONFIG['X_MAX_INCH']  # Already in inches
        plot_height_in = config.APP_CONFIG['Y_MAX_INCH']  # Already in inches
        
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
        plot_width_in = config.APP_CONFIG['X_MAX_INCH']  # Already in inches
        plot_height_in = config.APP_CONFIG['Y_MAX_INCH']  # Already in inches
        
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
        # Positions are already in inches from RealMotorController.get_position()
        y_in = pos['Y']
        x_in = pos['X']
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



    def _draw_toolpath_inches(self):
        """Draw toolpath with arrows and corner markers on the canvas."""
        if not hasattr(self, 'toolpath_data') or not self.toolpath_data:
            return
        
        # Draw the main toolpath line
        if self.toolpath_data.get('positions'):
            positions = self.toolpath_data['positions']
            if len(positions) >= 2:
                canvas_points = []
                for x_in, y_in in positions:
                    x_canvas, y_canvas = self._inches_to_canvas(x_in, y_in)
                    canvas_points.extend([x_canvas, y_canvas])
                
                # Draw main toolpath line
                self.canvas.create_line(canvas_points, fill='blue', width=2, tags='toolpath')
        
        # Draw corner markers
        if self.toolpath_data.get('corners'):
            for x_in, y_in in self.toolpath_data['corners']:
                x_canvas, y_canvas = self._inches_to_canvas(x_in, y_in)
                # Draw red star for corners
                size = 8
                self.canvas.create_polygon(
                    x_canvas, y_canvas - size,
                    x_canvas + size * 0.5, y_canvas - size * 0.5,
                    x_canvas + size, y_canvas,
                    x_canvas + size * 0.5, y_canvas + size * 0.5,
                    x_canvas, y_canvas + size,
                    x_canvas - size * 0.5, y_canvas + size * 0.5,
                    x_canvas - size, y_canvas,
                    x_canvas - size * 0.5, y_canvas - size * 0.5,
                    fill='red', outline='darkred', tags='toolpath'
                )
        
        # Draw tool orientation arrows
        if self.toolpath_data.get('orientations'):
            orientations = self.toolpath_data['orientations']
            positions = self.toolpath_data.get('positions', [])
            
            # Draw arrows every 1.0 inches along the path
            arrow_spacing_inches = 1.0
            arrow_indices = []
            
            if len(positions) > 1:
                # Calculate cumulative distance along the path
                cumulative_distance = 0.0
                last_pos = positions[0]
                
                for i, pos in enumerate(positions):
                    if i > 0:
                        # Calculate distance to previous point
                        dx = pos[0] - last_pos[0]
                        dy = pos[1] - last_pos[1]
                        segment_distance = math.sqrt(dx*dx + dy*dy)
                        cumulative_distance += segment_distance
                        
                        # Check if we should place an arrow here
                        if cumulative_distance >= arrow_spacing_inches:
                            arrow_indices.append(i)
                            cumulative_distance = 0.0  # Reset for next 0.5" interval
                    
                    last_pos = pos
            
            logger.info(f"Drawing arrows: {len(positions)} positions, {len(orientations)} orientations, {len(arrow_indices)} arrows at 0.5\" intervals")
            for i in arrow_indices:
                if i < len(positions):
                    x_in, y_in = positions[i]
                    a_deg = orientations[i]
                    x_canvas, y_canvas = self._inches_to_canvas(x_in, y_in)
                    
                    # Calculate arrow direction
                    arrow_length = 15
                    # Adjust for tool starting parallel to Y-axis (subtract 90 degrees)
                    adjusted_angle_deg = a_deg - 90.0
                    angle_rad = math.radians(adjusted_angle_deg)
                    
                    # Account for canvas Y-axis inversion (Tkinter Y is top-down)
                    # In machine coordinates: positive Y is up, positive X is right
                    # In canvas coordinates: positive Y is down, positive X is right
                    # So we need to flip the Y component of the arrow
                    dx = arrow_length * math.cos(angle_rad)
                    dy = -arrow_length * math.sin(angle_rad)  # Flip Y component
                    
                    # Draw arrow
                    self.canvas.create_line(
                        x_canvas, y_canvas,
                        x_canvas + dx, y_canvas + dy,
                        fill='green', width=3, arrow='last', tags='toolpath'
                    )
            
            logger.info(f"Drew {len(arrow_indices)} arrows")

    # --- DXF Import/Toolpath ---
    def _import_dxf(self):
        """Import DXF file using the new DXF processor."""
        if not DXF_TOOLPATH_IMPORTS_AVAILABLE:
            logger.error("DXF processing modules not available. Please install required dependencies.")
            self.status_label.configure(text=self._wrap_status_text("Missing DXF dependencies"), text_color="red")
            return
        
        initial_dir = os.path.expanduser("~/Desktop/DXF")
        file_path = filedialog.askopenfilename(initialdir=initial_dir, filetypes=[("DXF Files", "*.dxf")])
        if not file_path:
            return
        
        try:
            # Process DXF using the new processor (now works entirely in inches)
            self.processed_shapes = self.dxf_processor.process_dxf(file_path)
            
            if not self.processed_shapes:
                logger.error("No shapes found in DXF file.")
                self.status_label.configure(text=self._wrap_status_text("No shapes found in DXF"), text_color="red")
                return
            
            # Store the file path for later use
            self.dxf_file_path = file_path
            
            # Clear previous toolpath data
            self.generated_gcode = ""
            self.gcode_file_path = ""
            self.toolpath = []
            self.toolpath_data = None
            
            # Update status
            logger.info(f"DXF imported successfully:")
            logger.info(f"  - File: {file_path}")
            logger.info(f"  - Shapes found: {len(self.processed_shapes)}")
            
            # Update status label
            self.status_label.configure(text=self._wrap_status_text(f"DXF imported: {len(self.processed_shapes)} shapes"), text_color="green")
            
            # Redraw canvas to show imported shapes
            self._draw_canvas()
            
        except Exception as e:
            logger.error(f"Failed to load DXF: {e}")
            self.status_label.configure(text=self._wrap_status_text(f"DXF import failed: {str(e)}"), text_color="red")
    




    def _generate_toolpath(self):
        """Generate toolpath using the new toolpath generator."""
        if not DXF_TOOLPATH_IMPORTS_AVAILABLE:
            logger.error("Toolpath generation modules not available.")
            self.status_label.configure(text=self._wrap_status_text("Missing toolpath dependencies"), text_color="red")
            return
        
        if not self.processed_shapes:
            logger.warning("No DXF imported. Import a DXF file first.")
            self.status_label.configure(text=self._wrap_status_text("Import DXF first"), text_color="orange")
            return
        
        try:
            # Generate G-code using the toolpath generator
            self.generated_gcode = self.toolpath_generator.generate_toolpath(self.processed_shapes)
            
            if not self.generated_gcode:
                logger.error("Failed to generate G-code.")
                self.status_label.configure(text=self._wrap_status_text("Toolpath generation failed"), text_color="red")
                return
            
            # Create timestamp for filename
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Get original DXF filename without extension
            base_name = os.path.splitext(os.path.basename(self.dxf_file_path))[0]
            
            # Save G-code to gcode folder with timestamp
            self.gcode_file_path = f"gcode/{base_name}_{timestamp}.gcode"
            
            # Ensure gcode directory exists
            os.makedirs("gcode", exist_ok=True)
            
            with open(self.gcode_file_path, 'w') as f:
                f.write(self.generated_gcode)
            
            # Count lines and corners for status
            gcode_lines = self.generated_gcode.split('\n')
            total_lines = len([line for line in gcode_lines if line.strip() and not line.strip().startswith(';')])
            corner_count = len([line for line in gcode_lines if 'Raise Z for corner' in line])
            
            logger.info(f"Toolpath generated successfully:")
            logger.info(f"  - G-code file: {self.gcode_file_path}")
            logger.info(f"  - Total lines: {total_lines}")
            logger.info(f"  - Corners detected: {corner_count}")
            
            # Update status label
            self.status_label.configure(text=self._wrap_status_text(f"Toolpath generated: {total_lines} lines, {corner_count} corners"), text_color="green")
            
            # Redraw canvas to show toolpath
            self._draw_canvas()
            
        except Exception as e:
            logger.error(f"Failed to generate toolpath: {e}")
            self.status_label.configure(text=self._wrap_status_text(f"Toolpath generation failed: {str(e)}"), text_color="red")
    
    def _generate_toolpath_internal(self):
        """Internal method to generate toolpath without UI status updates."""
        if not DXF_TOOLPATH_IMPORTS_AVAILABLE:
            logger.error("Toolpath generation modules not available.")
            raise Exception("Missing toolpath dependencies")
        
        if not self.processed_shapes:
            logger.warning("No DXF imported. Import a DXF file first.")
            raise Exception("Import DXF first")
        
        try:
            # Generate G-code using the toolpath generator
            self.generated_gcode = self.toolpath_generator.generate_toolpath(self.processed_shapes)
            
            if not self.generated_gcode:
                logger.error("Failed to generate G-code.")
                raise Exception("Toolpath generation failed")
            
            # Create timestamp for filename
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Get original DXF filename without extension
            base_name = os.path.splitext(os.path.basename(self.dxf_file_path))[0]
            
            # Save G-code to gcode folder with timestamp
            self.gcode_file_path = f"gcode/{base_name}_{timestamp}.gcode"
            
            # Ensure gcode directory exists
            os.makedirs("gcode", exist_ok=True)
            
            with open(self.gcode_file_path, 'w') as f:
                f.write(self.generated_gcode)
            
            # Count lines and corners for logging
            gcode_lines = self.generated_gcode.split('\n')
            total_lines = len([line for line in gcode_lines if line.strip() and not line.strip().startswith(';')])
            corner_count = len([line for line in gcode_lines if 'Raise Z for corner' in line])
            
            logger.info(f"Toolpath generated successfully:")
            logger.info(f"  - G-code file: {self.gcode_file_path}")
            logger.info(f"  - Total lines: {total_lines}")
            logger.info(f"  - Corners detected: {corner_count}")
            
        except Exception as e:
            logger.error(f"Failed to generate toolpath: {e}")
            raise
    


    def _preview_toolpath(self):
        """Preview toolpath with arrows and corner analysis in the main GUI."""
        if not DXF_TOOLPATH_IMPORTS_AVAILABLE:
            logger.error("G-code visualization modules not available.")
            self.status_label.configure(text=self._wrap_status_text("Missing visualization dependencies"), text_color="red")
            return
        
        if not self.processed_shapes:
            logger.warning("No DXF imported. Import a DXF file first.")
            self.status_label.configure(text=self._wrap_status_text("Import DXF first"), text_color="orange")
            return
        
        try:
            # Always generate a new toolpath for preview (with timestamp)
            logger.info("Generating toolpath for preview...")
            self._generate_toolpath_internal()
            
            # Parse GCODE and extract toolpath data
            self._parse_gcode_for_preview(self.gcode_file_path)
            
            # Redraw canvas to show toolpath
            self._draw_canvas()
            
            # Update status with preview info
            corner_count = len(self.toolpath_data.get('corners', []))
            point_count = len(self.toolpath_data.get('positions', []))
            self.status_label.configure(text=self._wrap_status_text(f"Preview saved: {os.path.basename(self.gcode_file_path)}"), text_color="green")
            
        except Exception as e:
            logger.error(f"Failed to create toolpath preview: {e}")
            self.status_label.configure(text=self._wrap_status_text(f"Preview failed: {str(e)}"), text_color="red")
    
    def _parse_gcode_for_preview(self, gcode_file_path: str):
        """Parse GCODE file and extract toolpath data for canvas display."""
        logger.info(f"Parsing GCODE for preview: {gcode_file_path}")
        
        # Initialize toolpath data structure
        self.toolpath_data = {
            'positions': [],
            'orientations': [],
            'corners': [],
            'z_changes': []
        }
        
        # Current position tracking
        current_x = 0.0
        current_y = 0.0
        current_z = 0.0
        current_a = 0.0
        pending_corner = False
        
        with open(gcode_file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith(';'):
                    continue
                
                        # Extract coordinates using regex
                x_match = re.search(r'X([-\d.]+)', line)
                y_match = re.search(r'Y([-\d.]+)', line)
                z_match = re.search(r'Z([-\d.]+)', line)
                a_match = re.search(r'A([-\d.]+)', line)
                
                # Update current position if coordinates found
                if x_match:
                    current_x = float(x_match.group(1))
                if y_match:
                    current_y = float(y_match.group(1))
                if z_match:
                    current_z = float(z_match.group(1))
                if a_match:
                    current_a = float(a_match.group(1))
                
                # Check if this is a movement command
                if line.startswith('G0') or line.startswith('G1'):
                    # Record position and orientation
                    self.toolpath_data['positions'].append((current_x, current_y))
                    self.toolpath_data['orientations'].append(current_a)
                    
                    # Check for corner handling
                    if pending_corner:
                        self.toolpath_data['corners'].append((current_x, current_y))
                        pending_corner = False
                
                # Check for corner handling
                if 'Raise Z for corner' in line:
                    pending_corner = True
                
                # Check for Z changes
                if z_match and abs(current_z - self.toolpath_data.get('last_z', 0)) > 0.1:
                    self.toolpath_data['z_changes'].append((current_x, current_y, current_z))
                    self.toolpath_data['last_z'] = current_z
        
        logger.info(f"Parsed toolpath data:")
        logger.info(f"  - Positions: {len(self.toolpath_data['positions'])}")
        logger.info(f"  - Corners: {len(self.toolpath_data['corners'])}")
        logger.info(f"  - Z changes: {len(self.toolpath_data['z_changes'])}")

    def _run_toolpath(self):
        """Run toolpath using the new G-code executor."""
        if not DXF_TOOLPATH_IMPORTS_AVAILABLE:
            logger.error("G-code execution modules not available.")
            self.status_label.configure(text=self._wrap_status_text("Missing execution dependencies"), text_color="red")
            return
        
        if not self.gcode_file_path or not os.path.exists(self.gcode_file_path):
            logger.warning("No G-code file. Generate a toolpath first.")
            self.status_label.configure(text=self._wrap_status_text("Generate toolpath first"), text_color="orange")
            return
        
        try:
            # Execute G-code in a separate thread to avoid blocking the UI
            def execute_gcode():
                try:
                    def progress_callback(progress, status):
                        # Update UI with progress (this will be called from the thread)
                        self.root.after(0, lambda: self._update_execution_progress(progress, status))
                    
                    logger.info(f"Starting smooth motion execution: {self.gcode_file_path}")
                    
                    # Read GCODE file and add debug prints
                    with open(self.gcode_file_path, 'r') as f:
                        gcode_lines = f.readlines()
                    
                    # Add debug prints for G-code vs motor controller position comparison
                    self._add_gcode_debug_prints(gcode_lines)
                    
                    self.smooth_motion_executor.execute_toolpath_from_gcode(gcode_lines, progress_callback)
                    logger.info("Smooth motion execution completed successfully")
                    
                    # Update UI on completion
                    self.root.after(0, lambda: self.status_label.configure(text=self._wrap_status_text("Execution completed"), text_color="green"))
                except Exception as e:
                    logger.error(f"Error during smooth motion execution: {e}")
                    error_msg = str(e)
                    self.root.after(0, lambda: self.status_label.configure(text=self._wrap_status_text(f"Execution failed: {error_msg}"), text_color="red"))
            
            # Start execution thread
            execution_thread = threading.Thread(target=execute_gcode, daemon=True)
            execution_thread.start()
            
            # Update status to show execution started
            self.status_label.configure(text=self._wrap_status_text("Toolpath execution started"), text_color="blue")
            
        except Exception as e:
            logger.error(f"Failed to start G-code execution: {e}")
            self.status_label.configure(text=self._wrap_status_text(f"Failed to start execution: {str(e)}"), text_color="red")
    
    def _add_gcode_debug_prints(self, gcode_lines):
        """Add debug prints to compare G-code positions with motor controller positions."""
        print("\n" + "="*80)
        print("G-CODE vs MOTOR CONTROLLER POSITION COMPARISON")
        print("="*80)
        
        current_gcode_pos = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'A': 0.0}
        
        for line_num, line in enumerate(gcode_lines, 1):
            line = line.strip()
            if not line or line.startswith(';'):
                continue
            
            # Parse G-code line for position updates
            x_match = re.search(r'X([-\d.]+)', line)
            y_match = re.search(r'Y([-\d.]+)', line)
            z_match = re.search(r'Z([-\d.]+)', line)
            a_match = re.search(r'A([-\d.]+)', line)
            
            # Update G-code position tracking
            if x_match:
                current_gcode_pos['X'] = float(x_match.group(1))
            if y_match:
                current_gcode_pos['Y'] = float(y_match.group(1))
            if z_match:
                current_gcode_pos['Z'] = float(z_match.group(1))
            if a_match:
                current_gcode_pos['A'] = float(a_match.group(1))
            
            # Get current motor controller position
            motor_pos = self.motor_ctrl.get_position()
            
            # Print comparison for movement commands
            if line.startswith('G0') or line.startswith('G1'):
                print(f"Line {line_num:3d}: {line}")
                print(f"  GCODE pos: X={current_gcode_pos['X']:6.3f} Y={current_gcode_pos['Y']:6.3f} Z={current_gcode_pos['Z']:6.3f} A={current_gcode_pos['A']:6.3f}")
                print(f"  MOTOR pos: X={motor_pos['X']:6.3f} Y={motor_pos['Y']:6.3f} Z={motor_pos['Z']:6.3f} R={motor_pos['ROT']:6.3f}")
                
                # Highlight differences
                if abs(current_gcode_pos['X'] - motor_pos['X']) > 0.001:
                    print(f"  *** X DIFFERENCE: GCODE={current_gcode_pos['X']:.3f} vs MOTOR={motor_pos['X']:.3f} ***")
                if abs(current_gcode_pos['Y'] - motor_pos['Y']) > 0.001:
                    print(f"  *** Y DIFFERENCE: GCODE={current_gcode_pos['Y']:.3f} vs MOTOR={motor_pos['Y']:.3f} ***")
                if abs(current_gcode_pos['Z'] - motor_pos['Z']) > 0.001:
                    print(f"  *** Z DIFFERENCE: GCODE={current_gcode_pos['Z']:.3f} vs MOTOR={motor_pos['Z']:.3f} ***")
                if abs(current_gcode_pos['A'] - motor_pos['ROT']) > 0.001:
                    print(f"  *** A/ROT DIFFERENCE: GCODE={current_gcode_pos['A']:.3f} vs MOTOR={motor_pos['ROT']:.3f} ***")
                print()
        
        print("="*80)
        print("END OF COMPARISON")
        print("="*80 + "\n")
    
    def _update_execution_progress(self, progress, status):
        """Update UI with execution progress."""
        # This method can be expanded to show progress in the UI
        logger.info(f"Execution progress: {progress:.1f}% - {status}")
    
    def _stop_execution(self):
        """Stop G-code execution."""
        if not DXF_TOOLPATH_IMPORTS_AVAILABLE:
            logger.error("G-code execution modules not available.")
            self.status_label.configure(text=self._wrap_status_text("Missing execution dependencies"), text_color="red")
            return
        
        if not self.smooth_motion_executor or not self.smooth_motion_executor.is_executing:
            logger.info("No G-code execution is currently running.")
            self.status_label.configure(text=self._wrap_status_text("No execution running"), text_color="orange")
            return
        
        try:
            self.smooth_motion_executor.stop_execution()
            logger.info("G-code execution stopped by user")
            self.status_label.configure(text=self._wrap_status_text("Execution stopped"), text_color="orange")
        except Exception as e:
            logger.error(f"Failed to stop G-code execution: {e}")
            self.status_label.configure(text=self._wrap_status_text(f"Stop failed: {str(e)}"), text_color="red")









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
            self.status_label.configure(text=self._wrap_status_text(f"{axis} axis homed"), text_color="green")
        else:
            self.status_label.configure(text=self._wrap_status_text(f"Failed to home {axis}"), text_color="red")
        self._draw_canvas()
        self._update_position_display()
        # Clear status after 2 seconds
        self.root.after(2000, lambda: self.status_label.configure(text=self._wrap_status_text("Ready"), text_color=UI_COLORS['ON_SURFACE']))

    def _home_all(self):
        success = self.motor_ctrl.home_all_synchronous()
        if success:
            self.status_label.configure(text=self._wrap_status_text("All axes homed"), text_color="green")
        else:
            self.status_label.configure(text=self._wrap_status_text("Homing failed"), text_color="red")
        self._draw_canvas()
        self._update_position_display()
        # Clear status after 2 seconds
        self.root.after(2000, lambda: self.status_label.configure(text=self._wrap_status_text("Ready"), text_color=UI_COLORS['ON_SURFACE']))

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
        self.status_label.configure(text=self._wrap_status_text("EMERGENCY STOP"), text_color="red")
        # Clear status after 3 seconds
        self.root.after(3000, lambda: self.status_label.configure(text=self._wrap_status_text("Ready"), text_color=UI_COLORS['ON_SURFACE']))

    def _update_position_display(self):
        pos = self.motor_ctrl.get_position()
        # Positions are already in inches from RealMotorController.get_position()
        x_disp = pos['X']
        y_disp = pos['Y']
        z_disp = pos['Z']
        rot_disp = pos['ROT']
        text = f"X:{x_disp:.1f}\nY:{y_disp:.1f}\nZ:{z_disp:.1f}\nR:{rot_disp:.0f}°"
        self.coord_label.configure(text=text)
        self.root.after(200, self._update_position_display)



    def _on_jog_slider(self, value):
        # Convert slider value to float inches
        speed_inches = float(value) * self._jog_slider_scale
        self.jog_speed_var.set(speed_inches)
        # Update the display label
        self.jog_speed_label.configure(text=f"{speed_inches:.1f} in")
        # Update the actual jog speed
        self.jog_speed = speed_inches

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
    print(f"[DEBUG] SIMULATION_MODE={SIMULATION_MODE}")

# G-code generation functions moved to toolpath_planning package

# G-code generation functions moved to toolpath_planning package

# G-code file operations moved to toolpath_planning package



if __name__ == "__main__":
    main() 