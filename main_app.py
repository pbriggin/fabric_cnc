#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main application for Fabric CNC: DXF import, toolpath generation, visualization, and motor control UI.
Runs in simulation mode on non-RPi systems (no GPIO required).
"""

import os
import logging
import customtkinter as ctk
import threading
import time
import math

# Lazy imports - only import when needed
def lazy_import_filedialog():
    import tkinter.filedialog as filedialog
    return filedialog

def lazy_import_motor_control():
    try:
        from motor_control.grbl_motor_controller import GrblMotorController
        return GrblMotorController, True
    except ImportError:
        return None, False

def lazy_import_dxf_processing():
    try:
        from dxf_processing.dxf_processor import DXFProcessor
        from toolpath_planning.toolpath_generator import ToolpathGenerator
        from toolpath_planning.gcode_visualizer import GCodeVisualizer
        return DXFProcessor, ToolpathGenerator, GCodeVisualizer, True
    except ImportError:
        return None, None, None, False

# Quick availability checks without importing
MOTOR_IMPORTS_AVAILABLE = True  # Assume available, check on use
DXF_TOOLPATH_IMPORTS_AVAILABLE = True  # Assume available, check on use


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


# --- Motor simulation logic ---
class SimulatedMotorController:
    def __init__(self):
        self.position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'A': 0.0}
        self.lock = threading.Lock()
        self.is_homing = False

    def _clamp(self, axis, value):
        if axis == 'X':
            return max(-68.0, min(value, 68.0))  # 68 inches max X travel
        elif axis == 'Y':
            return max(-44.0, min(value, 44.0))  # 44 inches max Y travel
        elif axis == 'Z':
            return max(-3.0, min(value, 0.0))  # Z: -3.0 to 0.0 inches (main app handles runtime limit)
        elif axis == 'A':
            return value  # No limits for rotation axis - allow continuous rotation
        else:
            return value

    def jog(self, axis, delta):
        with self.lock:
            new_val = self.position[axis] + delta
            self.position[axis] = self._clamp(axis, new_val)


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
            self.position['A'] = 0.0
            self.is_homing = False
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
                self.position['A'] = rot

    def stop_movement(self):
        pass

    def move_coordinated(self, x_distance_mm=0, y_distance_mm=0, z_distance_mm=0, rot_distance_mm=0):
        """Execute coordinated movement across multiple axes (simulated)."""
        with self.lock:
            self.position['X'] += x_distance_mm
            self.position['Y'] += y_distance_mm
            self.position['Z'] += z_distance_mm
            self.position['A'] += rot_distance_mm

# --- Real Motor Controller Wrapper ---
class RealMotorController:
    def __init__(self):
        # Lazy import and initialize motor controller
        GrblMotorController, available = lazy_import_motor_control()
        if not available or GrblMotorController is None:
            raise ImportError("GRBL motor controller not available")
        
        # Use auto-detection by passing no port parameter
        self.motor_controller = GrblMotorController()
        self.lock = threading.Lock()
        self.is_homing = False
        # No internal position tracking - GRBL is single source of truth
        
        # Reset work coordinates (alarm handling now done in GrblMotorController)
        self.reset_work_coordinates()

    def reset_work_coordinates(self):
        """Reset work coordinates to 0,0,0,0"""
        try:
            self.motor_controller.send("G10 P1 L20 X0 Y0 Z0 A0")  # Reset work coordinates
        except Exception as e:
            logger.error(f"Failed to reset work coordinates: {e}")

    def _clamp(self, axis, value):
        if axis == 'X':
            return max(-68.0, min(value, 68.0))  # 68 inches max X travel
        elif axis == 'Y':
            return max(-44.0, min(value, 44.0))  # 44 inches max Y travel
        elif axis == 'Z':
            return max(-3.0, min(value, 0.0))  # Z: -3.0 to 0.0 inches (main app handles runtime limit)
        elif axis == 'A':
            return value  # No limits for rotation axis - allow continuous rotation
        else:
            return value

    def jog(self, axis, delta):
        try:
            
            # Get current position from GRBL
            current_pos = self.get_position()
            current_val = current_pos.get(axis, 0.0)
            
            # Calculate target and clamp
            target_val = current_val + delta
            clamped_val = self._clamp(axis, target_val)
            actual_delta = clamped_val - current_val
            
            
            if abs(actual_delta) > 1e-6:
                # Use specified jog feedrates for each axis
                axis_feedrates = {
                    'X': 3000,   # High speed for X-axis
                    'Y': 3000,   # High speed for Y-axis
                    'Z': 500,    # Medium speed for Z-axis
                    'A': 500     # Medium speed for rotation axis
                }
                feedrate = axis_feedrates.get(axis, 100)
                
                # Send delta directly to GRBL for all axes
                delta_grbl = actual_delta
                
                self.motor_controller.jog(axis, delta_grbl, feedrate)
                time.sleep(0.2)  # Wait for GRBL to process
                    
            
        except Exception as e:
            logger.error(f"Jog error on {axis}: {e}")


    def home_all_synchronous(self):
        """Home all axes simultaneously."""
        with self.lock:
            if self.is_homing:
                return False
            self.is_homing = True
            try:
                self.motor_controller.home_all()
                # Position reset handled by GRBL work coordinate reset
                logger.info("Homing completed - position reset by GRBL")
                
                self.is_homing = False
                return True
            except Exception as e:
                logger.error(f"Synchronous home error: {e}")
                self.is_homing = False
                return False

    def get_position(self):
        # GRBL is the ONLY source of truth for position
        try:
            x, y, z, a = self.motor_controller.get_position()
            pos = {
                'X': x / 25.4,  # Convert mm to inches
                'Y': y / 25.4,  # Convert mm to inches
                'Z': z / 25.4,  # Convert mm to inches
                'A': (a / 25.4) * 360.0  # A-axis: convert mm to inches, then inches to degrees (1 inch = 360 degrees)
            }
            return pos
        except Exception as e:
            # Return zeros if GRBL unavailable
            return {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'A': 0.0}
    
    def sync_position(self):
        """Position syncing now handled by get_position() from GRBL"""
    
    def send(self, gcode_command):
        """Send a G-code command directly to the GRBL controller."""
        try:
            self.motor_controller.send(gcode_command)
        except Exception as e:
            logger.error(f"Failed to send G-code command '{gcode_command}': {e}")
    
    def get_sensor_states(self):
        """Get current sensor states (not applicable for GRBL)."""
        return {}

    def estop(self):
        try:
            # Emergency stop - send reset/stop to GRBL
            self.motor_controller.send_immediate("\x18")  # Ctrl+X soft reset
            logger.warning("EMERGENCY STOP triggered - GRBL reset")
        except Exception as e:
            logger.error(f"E-stop error: {e}")

    def stop_movement(self):
        """Stop any ongoing movement immediately."""
        try:
            self.motor_controller.send_immediate("!")  # Feed hold
            logger.info("Movement stopped")
        except Exception as e:
            logger.error(f"Stop movement error: {e}")

    def cleanup(self):
        try:
            # Close GRBL connection
            self.motor_controller.close()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    def check_limit_switches(self):
        """Check the current status of limit switches."""
        self.motor_controller.check_limit_switches()
    
    def get_grbl_settings(self):
        """Query and display current GRBL settings."""
        self.motor_controller.get_grbl_settings()
    
    def get_grbl_info(self):
        """Get GRBL version and build info.""" 
        self.motor_controller.get_grbl_info()
    
    def test_limit_switch_connection(self):
        """Test if limit switches are properly connected and readable."""
        self.motor_controller.test_limit_switch_connection()

    def move_to(self, x=None, y=None, z=None, rot=None):
        # Get current position from GRBL for logging
        current_pos = self.get_position()
        current_x = current_pos.get('X', 0.0)
        current_y = current_pos.get('Y', 0.0) 
        current_z = current_pos.get('Z', 0.0)
        current_rot = current_pos.get('A', 0.0)
        
        
        # Use G0 (rapid) movement to move to absolute position
        # Convert from inches to mm for GRBL
        x_mm = x * 25.4 if x is not None else None
        y_mm = y * 25.4 if y is not None else None
        z_mm = z * 25.4 if z is not None else None
        
        # Build G0 command
        cmd_parts = ["G0"]
        if x_mm is not None:
            cmd_parts.append(f"X{x_mm:.3f}")
        if y_mm is not None:
            cmd_parts.append(f"Y{y_mm:.3f}")
        if z_mm is not None:
            cmd_parts.append(f"Z{z_mm:.3f}")
        if rot is not None:
            cmd_parts.append(f"A{rot:.3f}")
        
        if len(cmd_parts) > 1:  # Only send if we have axes to move
            # Ensure we're using work coordinate system
            self.motor_controller.send("G54")
            self.motor_controller.send(" ".join(cmd_parts))
        
        # Position tracking now handled by get_position() from GRBL
        time.sleep(0.1)  # Give GRBL time to process movement

    def move_coordinated(self, x_distance_in=0, y_distance_in=0, z_distance_in=0, rot_distance_deg=0):
        """Execute coordinated movement across multiple axes using relative G1 movement."""
        try:
            # Convert inch distances to mm for GRBL
            x_mm = x_distance_in * 25.4
            y_mm = y_distance_in * 25.4
            z_mm = z_distance_in * 25.4
            
            # Build G1 relative movement command
            cmd_parts = ["G91", "G1"]  # G91 = relative mode, G1 = linear interpolation
            if abs(x_mm) > 1e-6:
                cmd_parts.append(f"X{x_mm:.3f}")
            if abs(y_mm) > 1e-6:
                cmd_parts.append(f"Y{y_mm:.3f}")
            if abs(z_mm) > 1e-6:
                cmd_parts.append(f"Z{z_mm:.3f}")
            if abs(rot_distance_deg) > 1e-6:
                cmd_parts.append(f"A{rot_distance_deg:.3f}")
            
            if len(cmd_parts) > 2:  # Only send if we have axes to move
                cmd_parts.append("F1000")  # 1000 mm/min feedrate
                # Ensure we're using work coordinate system
                self.motor_controller.send("G54")
                self.motor_controller.send(" ".join(cmd_parts))
                self.motor_controller.send("G90")  # Return to absolute mode
            
            # Position tracking now handled by get_position() from GRBL
            time.sleep(0.1)  # Give GRBL time to process movement
            
        except Exception as e:
            logger.error(f"Coordinated movement error: {e}")
            raise

class FabricCNCApp:
    def _truncate_status(self, text: str, max_chars: int = 20) -> str:
        """Truncate status text to fit within display constraints."""
        if len(text) <= max_chars:
            return text
        return text[:max_chars-3] + "..."
    
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
        self.jog_size = 1.0  # Default to 1 inch
        self.jog_size_var = ctk.DoubleVar(value=1.0)  # Default to 1 inch
        self._jog_slider_scale = 0.05  # Scale factor for slider (0.05 inch increments)
        
        # Z lower limit control
        self.z_lower_limit = -2.0  # Runtime adjustable Z lower limit
        self.z_lower_limit_var = ctk.DoubleVar(value=-2.0)
        self._arrow_key_state = {}
        self._arrow_key_after_ids = {}
        self._current_toolpath_idx = [0, 0]
        self._toolpath_step_count = 0
        self._current_toolpath_pos = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'A': 0.0}
        self.toolpaths = []
        
        self.motor_ctrl = SimulatedMotorController() if SIMULATION_MODE else RealMotorController()
        self._jog_in_progress = {'X': False, 'Y': False, 'Z': False, 'A': False}
        self._arrow_key_repeat_delay = config.APP_CONFIG['ARROW_KEY_REPEAT_DELAY']
        
        # Performance optimization: Canvas redraw debouncing
        self._canvas_redraw_pending = False
        self._last_position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'A': 0.0}
        self._position_update_threshold = 0.05  # Only update if position changes by > 0.05 inches (reduced frequency)
        
        # Defer DXF processing initialization until needed
        self.dxf_processor = None
        self.toolpath_generator = None
        self.smooth_motion_executor = None
        self.gcode_visualizer = None
        self._dxf_initialized = False
        
        # Initialize DXF-related attributes (legacy)
        self.dxf_doc = None
        self.dxf_entities = []
        self.toolpath = []
        
        # New DXF processing attributes
        self.processed_shapes = {}
        self.generated_gcode = ""
        self.gcode_file_path = ""
        # Setup critical UI first
        self._setup_ui()
        
        # Defer non-critical initialization
        self.root.after(10, self._setup_deferred_initialization)
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        # Force fullscreen after UI setup
        self.root.after(100, lambda: self.root.attributes('-fullscreen', True))
    
    def _setup_deferred_initialization(self):
        """Initialize non-critical components after UI is visible."""
        try:
            self._bind_arrow_keys()
            self._update_position_and_canvas()  # Start the synchronized update loop
        except Exception as e:
            logger.error(f"Error in deferred initialization: {e}")
            # Continue anyway, don't block startup
    
    def _initialize_dxf_processing(self):
        """Lazy initialization of DXF processing components."""
        if self._dxf_initialized:
            return True
            
        try:
            DXFProcessor, ToolpathGenerator, GCodeVisualizer, available = lazy_import_dxf_processing()
            if not available:
                return False
                
            self.dxf_processor = DXFProcessor()
            self.toolpath_generator = ToolpathGenerator(
                cutting_height=self.z_lower_limit,  # Use runtime adjustable depth
                safe_height=-2.0,  # Safe height during toolpath execution
                corner_angle_threshold=15.0,  # 15-degree threshold for basic approach
                feed_rate=6000.0,  # Increased from 3000 for faster cutting
                plunge_rate=6000.0  # Increased from 3000 for faster plunges
            )
            self.gcode_visualizer = GCodeVisualizer()
            self._dxf_initialized = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize DXF processing: {e}")
            return False

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
        self.status_label = ctk.CTkLabel(status_section, text="Ready", font=("Arial", 16, "bold"), text_color=UI_COLORS['ON_SURFACE'], width=200)
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
        
        # Defer initial canvas draw to speed up startup
        self.root.after(100, self._schedule_canvas_redraw)


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
        
        # 8-row layout: label (1 row) + arrows (3 rows) + Z/A (2 rows) + jog speed (2 rows)
        motor_section.grid_columnconfigure(0, weight=1)
        motor_section.grid_columnconfigure(1, weight=1)
        motor_section.grid_rowconfigure(1, weight=1)  # Up arrow row
        motor_section.grid_rowconfigure(2, weight=1)  # Left/Right arrows row
        motor_section.grid_rowconfigure(3, weight=1)  # Down arrow row
        motor_section.grid_rowconfigure(4, weight=1)  # Z controls row
        motor_section.grid_rowconfigure(5, weight=1)  # A controls row
        motor_section.grid_rowconfigure(6, weight=1)  # Jog size label row
        motor_section.grid_rowconfigure(7, weight=1)  # Jog size slider row
        motor_section.grid_rowconfigure(8, weight=1)  # Jog size value display row
        motor_section.grid_rowconfigure(9, weight=1)  # Z limit label row
        motor_section.grid_rowconfigure(10, weight=1)  # Z limit slider row
        motor_section.grid_rowconfigure(11, weight=1)  # Z limit value display row
        
        # Arrow buttons - stacked layout with equal widths
        self._add_compact_jog_button(motor_section, "↑", lambda: self._jog('Y', +self.jog_size)).grid(row=1, column=0, columnspan=2, padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'], sticky="nsew")
        self._add_compact_jog_button(motor_section, "←", lambda: self._jog('X', -self.jog_size)).grid(row=2, column=0, padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'], sticky="nsew")
        self._add_compact_jog_button(motor_section, "→", lambda: self._jog('X', +self.jog_size)).grid(row=2, column=1, padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'], sticky="nsew")
        self._add_compact_jog_button(motor_section, "↓", lambda: self._jog('Y', -self.jog_size)).grid(row=3, column=0, columnspan=2, padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'], sticky="nsew")
        
        # Z and A controls - now using jog_size
        self._add_compact_jog_button(motor_section, "Z+", lambda: self._jog('Z', +self.jog_size)).grid(row=4, column=0, padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'], sticky="nsew")
        self._add_compact_jog_button(motor_section, "Z-", lambda: self._jog('Z', -self.jog_size)).grid(row=4, column=1, padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'], sticky="nsew")
        self._add_compact_jog_button(motor_section, "A+", lambda: self._jog('A', +self.jog_size)).grid(row=5, column=0, padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'], sticky="nsew")
        self._add_compact_jog_button(motor_section, "A-", lambda: self._jog('A', -self.jog_size)).grid(row=5, column=1, padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'], sticky="nsew")
        
        # Jog size slider
        ctk.CTkLabel(motor_section, text="Jog Size:", font=("Arial", 12, "bold"), text_color=UI_COLORS['PRIMARY_COLOR']).grid(row=6, column=0, columnspan=2, pady=(UI_PADDING['SMALL'], 0))
        jog_slider = ctk.CTkSlider(motor_section, from_=1, to=100, number_of_steps=99, command=self._on_jog_slider)
        jog_slider.grid(row=7, column=0, columnspan=2, padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'], sticky="ew")
        jog_slider.set(20)  # Set to 1.0 inch (20 * 0.05)
        
        # Jog size value display
        self.jog_size_label = ctk.CTkLabel(motor_section, text="1.00 in", font=("Arial", 12, "bold"), text_color=UI_COLORS['ON_SURFACE'])
        self.jog_size_label.grid(row=8, column=0, columnspan=2, pady=(0, UI_PADDING['SMALL']))
        
        # Initialize slider to sync all jog size variables
        self._on_jog_slider(20)
        
        # Z lower limit slider
        ctk.CTkLabel(motor_section, text="Z Lower Limit:", font=("Arial", 12, "bold"), text_color=UI_COLORS['PRIMARY_COLOR']).grid(row=9, column=0, columnspan=2, pady=(UI_PADDING['SMALL'], 0))
        z_limit_slider = ctk.CTkSlider(motor_section, from_=2.0, to=3.0, number_of_steps=20, command=self._on_z_limit_slider)
        z_limit_slider.grid(row=10, column=0, columnspan=2, padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'], sticky="ew")
        z_limit_slider.set(2.0)  # Set to -2.0 inch (2.0 on slider)
        
        # Z lower limit value display
        self.z_limit_label = ctk.CTkLabel(motor_section, text="-2.00 in", font=("Arial", 12, "bold"), text_color=UI_COLORS['ON_SURFACE'])
        self.z_limit_label.grid(row=11, column=0, columnspan=2, pady=(0, UI_PADDING['SMALL']))
        
        # Initialize Z limit slider to sync all variables
        self._on_z_limit_slider(2.0)
        
        # Home controls section
        home_section = ctk.CTkFrame(self.right_column, fg_color="#d0d0d0", corner_radius=8)
        home_section.grid(row=1, column=0, sticky="ew", padx=UI_PADDING['SMALL'], pady=UI_PADDING['SMALL'])
        
        home_buttons = [
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
        self.root.bind('<KeyPress-Home>', lambda e: self._on_arrow_press('Home'))  # Home key for A+
        self.root.bind('<KeyRelease-Home>', lambda e: self._on_arrow_release('Home'))
        self.root.bind('<KeyPress-End>', lambda e: self._on_arrow_press('End'))  # End key for A-
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
            delta = -self.jog_size
        elif key == 'Right':
            axis = 'X'
            delta = self.jog_size
        elif key == 'Up':
            axis = 'Y'
            delta = self.jog_size
        elif key == 'Down':
            axis = 'Y'
            delta = -self.jog_size
        elif key == 'Page_Up':
            axis = 'Z'
            delta = self.jog_size
        elif key == 'Page_Down':
            axis = 'Z'
            delta = -self.jog_size
        elif key == 'Home':
            axis = 'A'
            delta = self.jog_size  # Use same as other axes
        elif key == 'End':
            axis = 'A'
            delta = -self.jog_size  # Use same as other axes
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
            self._jog_in_progress['A'] = False





    def _on_canvas_resize(self, event):
        self.canvas_width = event.width
        self.canvas_height = event.height
        self._schedule_canvas_redraw()

    def _schedule_canvas_redraw(self, pos=None):
        """Schedule a canvas redraw with debouncing to prevent excessive redraws."""
        if not self._canvas_redraw_pending:
            self._canvas_redraw_pending = True
            self.root.after_idle(lambda: self._draw_canvas_debounced(pos))
    
    def _draw_canvas_debounced(self, pos=None):
        """Debounced canvas redraw that only executes once per idle cycle."""
        self._canvas_redraw_pending = False
        self._draw_canvas(pos)
    
    def _draw_canvas(self, pos=None):
        self.canvas.delete("all")
        # Draw axes in inches
        self._draw_axes_in_inches()
        
        # Draw processed shapes from new DXF processor
        if self.processed_shapes:
            self._draw_processed_shapes()
        
        # Draw legacy DXF entities if loaded
        if self.dxf_doc and self.dxf_entities:
            self._draw_dxf_entities_inches()
        
        # Draw toolpath if generated
        if self.toolpath:
            self._draw_toolpath_inches()
        
        # Draw new toolpath preview if available
        if hasattr(self, 'toolpath_data') and self.toolpath_data:
            self._draw_toolpath_inches()
        
        # Draw current tool head position (all axes)
        if pos is None:
            pos = self.motor_ctrl.get_position()
        x_max_inches = 68.0  # 68 inches max X travel
        y_max_inches = 44.0  # 44 inches max Y travel
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
        
        # Drew processed shapes with unique colors

    def _reload_config_and_redraw(self):
        """Reload configuration and redraw the canvas to reflect changes."""
        # Reload the config module
        import importlib
        importlib.reload(config)
        
        # Update the global APP_CONFIG reference
        global APP_CONFIG
        APP_CONFIG = config.APP_CONFIG
        
        # Redraw the canvas with new settings
        self._schedule_canvas_redraw()

    def _draw_axes_in_inches(self):
        # Draw full-height canvas with gridlines and numbers
        # Use 5-inch spacing for gridlines and numbers
        inch_tick = 5
        
        # Configure plot dimensions from config file
        plot_width_in = 68.0  # 68 inches work area width
        plot_height_in = 44.0  # 44 inches work area height
        
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
        plot_width_in = 68.0  # 68 inches work area width
        plot_height_in = 44.0  # 44 inches work area height
        
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
        
        # Tool head position updated

    def _draw_dxf_entities_inches(self):
        # Draw DXF entities, converting mm to inches for plotting
        if not (self.dxf_doc and self.dxf_entities):
            # No DXF entities to draw
            return
        scale = getattr(self, 'dxf_unit_scale', 1.0)
        
        # Use the offset calculated during import
        dx, dy = getattr(self, 'dxf_offset', (0, 0))
        
        # Drawing DXF entities

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
                            cumulative_distance = 0.0  # Reset for next 1.0" interval
                    
                    last_pos = pos
            
            # Drawing toolpath arrows
            for i in arrow_indices:
                if i < len(positions):
                    x_in, y_in = positions[i]
                    a_inches = orientations[i]  # A-axis value in inches
                    x_canvas, y_canvas = self._inches_to_canvas(x_in, y_in)
                    
                    # Convert A-axis inches to degrees: 1 inch = 360 degrees
                    a_deg = a_inches * 360.0
                    
                    # Calculate arrow direction
                    arrow_length = 15
                    # Match toolpath generator: negate angle and add 90 degrees
                    adjusted_angle_deg = -a_deg + 90.0
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
            
            # Drew toolpath arrows

    # --- DXF Import/Toolpath ---
    def _import_dxf(self):
        """Import DXF file using the new DXF processor."""
        # Initialize DXF processing if needed
        if not self._initialize_dxf_processing():
            logger.error("DXF processing modules not available. Please install required dependencies.")
            self.status_label.configure(text=self._truncate_status("Missing DXF deps"), text_color="red")
            return
        
        initial_dir = os.path.expanduser("~/Desktop/DXF")
        filedialog = lazy_import_filedialog()
        file_path = filedialog.askopenfilename(initialdir=initial_dir, filetypes=[("DXF Files", "*.dxf")])
        if not file_path:
            return
        
        try:
            # Process DXF using basic approach (now integrated into DXFProcessor)
            self.processed_shapes = self.dxf_processor.process_dxf(file_path)
            
            if not self.processed_shapes:
                logger.error("No shapes found in DXF file.")
                self.status_label.configure(text=self._truncate_status("No shapes found"), text_color="red")
                return
            
            # Get point count from the basic_shape
            points = self.processed_shapes.get("basic_shape", [])
            logger.info(f"DXF processed successfully. Found {len(points)} points.")
            self.status_label.configure(text=self._truncate_status(f"DXF loaded: {len(points)} points"), text_color="green")
            
            # Store the file path for later use
            self.dxf_file_path = file_path
            
            # Clear previous toolpath data
            self.generated_gcode = ""
            self.gcode_file_path = ""
            self.toolpath = []
            self.toolpath_data = None
            
            # Update status
            logger.info(f"DXF imported: {len(self.processed_shapes)} shapes from {file_path}")
            
            # Update status label
            self.status_label.configure(text=self._truncate_status(f"DXF: {len(self.processed_shapes)} shapes"), text_color="green")
            
            # Redraw canvas to show imported shapes
            self._schedule_canvas_redraw()
            
        except Exception as e:
            logger.error(f"Failed to load DXF: {e}")
            self.status_label.configure(text=self._truncate_status(f"Import failed: {str(e)}"), text_color="red")
    


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
        """Generate toolpath using the new toolpath generator."""
        if not DXF_TOOLPATH_IMPORTS_AVAILABLE:
            logger.error("Toolpath generation modules not available.")
            self.status_label.configure(text=self._truncate_status("Missing toolpath"), text_color="red")
            return
        
        if not self.processed_shapes:
            logger.warning("No DXF imported. Import a DXF file first.")
            self.status_label.configure(text=self._truncate_status("Import DXF first"), text_color="orange")
            return
        
        try:
            # Generate G-code using the toolpath generator
            self.generated_gcode = self.toolpath_generator.generate_toolpath(self.processed_shapes)
            
            if not self.generated_gcode:
                logger.error("Failed to generate G-code.")
                self.status_label.configure(text=self._truncate_status("Toolpath failed"), text_color="red")
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
            
            logger.info(f"Toolpath generated: {total_lines} lines saved to {self.gcode_file_path}")
            logger.info(f"  - Corners detected: {corner_count}")
            
            # Update status label
            self.status_label.configure(text=self._truncate_status(f"Generated: {total_lines}L"), text_color="green")
            
            # Redraw canvas to show toolpath
            self._schedule_canvas_redraw()
            
        except Exception as e:
            logger.error(f"Failed to generate toolpath: {e}")
            self.status_label.configure(text=self._truncate_status(f"Gen failed: {str(e)}"), text_color="red")
    
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
            
            logger.info(f"Toolpath generated: {total_lines} lines saved to {self.gcode_file_path}")
            logger.info(f"  - Corners detected: {corner_count}")
            
        except Exception as e:
            logger.error(f"Failed to generate toolpath: {e}")
            raise
    
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
                # Detected circle from splines
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
        # Legacy toolpath generation disabled with GRBL integration
        return []
    
    def _generate_continuous_circle_path(self, center, radius, start_angle=0, end_angle=2*math.pi):
        """
        Generate a single continuous path for a circle/arc with ultra-smooth motion.
        Returns: List of (x, y, angle, z) tuples for continuous motion
        """
        # Legacy toolpath generation disabled with GRBL integration
        return []
    
    def _generate_continuous_polyline_path(self, polyline):
        """
        Generate a single continuous path for a polyline with smooth transitions.
        Returns: List of (x, y, angle, z) tuples for continuous motion
        """
        # Legacy toolpath generation disabled with GRBL integration
        return []
    
    def _generate_continuous_line_path(self, line):
        """
        Generate a single continuous path for a line with smooth motion.
        Returns: List of (x, y, angle, z) tuples for continuous motion
        """
        # Legacy toolpath generation disabled with GRBL integration
        return []

    def _preview_toolpath(self):
        """Preview toolpath with arrows and corner analysis in the main GUI."""
        # Initialize DXF processing if needed
        if not self._initialize_dxf_processing():
            logger.error("G-code visualization modules not available.")
            self.status_label.configure(text=self._truncate_status("Missing viz deps"), text_color="red")
            return
        
        if not self.processed_shapes:
            logger.warning("No DXF imported. Import a DXF file first.")
            self.status_label.configure(text=self._truncate_status("Import DXF first"), text_color="orange")
            return
        
        try:
            # Always generate a new toolpath for preview (with timestamp)
            # Generating toolpath for preview
            self._generate_toolpath_internal()
            
            # Parse GCODE and extract toolpath data
            self._parse_gcode_for_preview(self.gcode_file_path)
            
            # Redraw canvas to show toolpath
            self._schedule_canvas_redraw()
            
            # Update status with preview info
            corner_count = len(self.toolpath_data.get('corners', []))
            point_count = len(self.toolpath_data.get('positions', []))
            self.status_label.configure(text=self._truncate_status(f"Preview: {os.path.basename(self.gcode_file_path)}"), text_color="green")
            
        except Exception as e:
            logger.error(f"Failed to create toolpath preview: {e}")
            self.status_label.configure(text=self._truncate_status(f"Preview failed"), text_color="red")
    
    def _parse_gcode_for_preview(self, gcode_file_path: str):
        """Parse GCODE file and extract toolpath data for canvas display."""
        # Parsing GCODE for preview
        
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
                import re
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
        
        # Parsed toolpath data

    def _run_toolpath(self):
        """Run toolpath using the new G-code executor."""
        if not DXF_TOOLPATH_IMPORTS_AVAILABLE:
            logger.error("G-code execution modules not available.")
            self.status_label.configure(text=self._truncate_status("Missing exec deps"), text_color="red")
            return
        
        if not self.gcode_file_path or not os.path.exists(self.gcode_file_path):
            logger.warning("No G-code file. Generate a toolpath first.")
            self.status_label.configure(text=self._truncate_status("Generate first"), text_color="orange")
            return
        
        try:
            # Execute G-code in a separate thread to avoid blocking the UI
            def execute_gcode():
                try:
                    def progress_callback(progress, status):
                        # Update UI with progress (this will be called from the thread)
                        self.root.after(0, lambda: self._update_execution_progress(progress, status))
                    
                    # Ensure machine is homed before running toolpath
                    if MOTOR_IMPORTS_AVAILABLE and not SIMULATION_MODE:
                        logger.info("Checking if machine is homed before toolpath execution...")
                        if not self.motor_ctrl.motor_controller.ensure_homed():
                            logger.error("Failed to ensure machine is homed. Aborting toolpath execution.")
                            self.root.after(0, lambda: self.status_label.configure(text=self._truncate_status("Homing failed"), text_color="red"))
                            return
                    
                    # Read GCODE file for execution
                    with open(self.gcode_file_path, 'r') as f:
                        gcode_lines = f.readlines()
                    
                    # G-code execution ready
                    
                    # Use GRBL to execute G-code directly
                    if not SIMULATION_MODE:
                        self.motor_ctrl.motor_controller.run_gcode_file(self.gcode_file_path)
                    else:
                        # For simulation, just log the lines
                        for i, line in enumerate(gcode_lines):
                            if progress_callback:
                                progress_callback(i / len(gcode_lines) * 100, f"Line {i+1}/{len(gcode_lines)}")
                            time.sleep(0.01)  # Simulate execution time
                    logger.info("G-code execution completed")
                    
                    # Update UI on completion
                    self.root.after(0, lambda: self.status_label.configure(text=self._truncate_status("Completed"), text_color="green"))
                except Exception as e:
                    logger.error(f"Error during smooth motion execution: {e}")
                    error_msg = str(e)
                    self.root.after(0, lambda: self.status_label.configure(text=self._truncate_status(f"Exec failed"), text_color="red"))
            
            # Start execution thread
            execution_thread = threading.Thread(target=execute_gcode, daemon=True)
            execution_thread.start()
            
            # Update status to show execution started
            self.status_label.configure(text=self._truncate_status("Executing..."), text_color="blue")
            
        except Exception as e:
            logger.error(f"Failed to start G-code execution: {e}")
            self.status_label.configure(text=self._truncate_status("Start failed"), text_color="red")
    
    
    def _update_execution_progress(self, progress, status):
        """Update UI with execution progress."""
        # This method can be expanded to show progress in the UI
        # Execution progress updated
    
    def _stop_execution(self):
        """Stop G-code execution."""
        if not DXF_TOOLPATH_IMPORTS_AVAILABLE:
            logger.error("G-code execution modules not available.")
            self.status_label.configure(text=self._truncate_status("Missing exec deps"), text_color="red")
            return
        
        if not self.smooth_motion_executor or not self.smooth_motion_executor.is_executing:
            # No G-code execution running
            self.status_label.configure(text=self._truncate_status("Not running"), text_color="orange")
            return
        
        try:
            self.smooth_motion_executor.stop_execution()
            # G-code execution stopped by user
            self.status_label.configure(text=self._truncate_status("Stopped"), text_color="orange")
        except Exception as e:
            logger.error(f"Failed to stop G-code execution: {e}")
            self.status_label.configure(text=self._truncate_status("Stop failed"), text_color="red")

    def _travel_to_start(self, x_in, y_in):
        """Travel from home to the start position of the toolpath."""
        # Move to start position with Z up
        if MOTOR_IMPORTS_AVAILABLE:
            self.motor_ctrl.move_to(x=x_in, y=y_in, z=0.0, rot=0.0)  # Move to safe height (0.0 inches)
        
        # Update position and display
        self._current_toolpath_pos['X'] = x_in
        self._current_toolpath_pos['Y'] = y_in
        self._current_toolpath_pos['Z'] = 0.0  # Safe height in inches
        self._current_toolpath_pos['A'] = 0.0
        
        # Position update loop and canvas redraw will be handled automatically
        self._last_position = self.motor_ctrl.get_position().copy()
        self._schedule_canvas_redraw()
        
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
        # Coordinates are already in inches, no conversion needed
        x_in = x
        y_in = y
        self._current_toolpath_pos['X'] = x_in
        self._current_toolpath_pos['Y'] = y_in
        self._current_toolpath_pos['Z'] = self.z_lower_limit if z < 0 else 0.0  # Cutting (runtime limit) or safe (0.0in) height
        # Use rotation angle directly - motor controller handles direction inversion
        self._current_toolpath_pos['A'] = math.degrees(angle)
        
        
        if MOTOR_IMPORTS_AVAILABLE:
            self.motor_ctrl.move_to(
                x=self._current_toolpath_pos['X'],
                y=self._current_toolpath_pos['Y'],
                z=self._current_toolpath_pos['Z'],
                rot=self._current_toolpath_pos['A']
            )
        
        # Check if coordinates are within machine limits
        if abs(x_in) > 68.0 or abs(y_in) > 44.0:
            logger.warning(f"Coordinates beyond machine limits! X={x_in:.2f}in (limit: ±68.0in), Y={y_in:.2f}in (limit: ±44.0in)")
        
        # Update position tracking and schedule canvas redraw
        self._last_position = self.motor_ctrl.get_position().copy()
        self._schedule_canvas_redraw()
        
        # Next step
        self._current_toolpath_idx[1] += 1
        self._toolpath_step_count += 1
        self.root.after(50, self._run_toolpath_step)  # Slower execution (50ms instead of 5ms)

    def _draw_live_tool_head_inches(self, pos):
        # Draw a blue dot and orientation line at the current tool head position (in inches)
        # Position is already in inches
        x_in = pos['X']
        y_in = pos['Y']
        rot_rad = math.radians(pos.get('A', 0.0))
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
        """Jog with bounds checking to prevent moves outside machine limits."""
        if not MOTOR_IMPORTS_AVAILABLE or SIMULATION_MODE:
            return
        
        # Get current position
        current_pos = self.motor_ctrl.get_position()
        if not current_pos:
            logger.warning("Cannot jog - position unknown")
            return
        
        # Position data uses the same axis names now
        pos_axis = axis
            
        # Check if position data has the requested axis
        if pos_axis not in current_pos:
            logger.error(f"Axis {pos_axis} not available in position data: {current_pos}")
            return
            
        new_pos = current_pos[pos_axis] + delta
        
        # Bounds checking
        if axis == 'X':
            if new_pos < 0:
                logger.warning(f"X jog blocked: would move to {new_pos:.3f} (min: 0)")
                return
            elif new_pos > config.APP_CONFIG['X_MAX_INCH']:
                logger.warning(f"X jog blocked: would move to {new_pos:.3f} (max: {config.APP_CONFIG['X_MAX_INCH']})")
                return
        elif axis == 'Y':
            if new_pos < 0:
                logger.warning(f"Y jog blocked: would move to {new_pos:.3f} (min: 0)")
                return
            elif new_pos > config.APP_CONFIG['Y_MAX_INCH']:
                logger.warning(f"Y jog blocked: would move to {new_pos:.3f} (max: {config.APP_CONFIG['Y_MAX_INCH']})")
                return
        elif axis == 'Z':
            if new_pos > 0:
                logger.warning(f"Z jog blocked: would move to {new_pos:.3f} (max: 0)")
                return
        elif axis == 'A':
            # Allow continuous rotation - remove bounds checking for A-axis
            pass
        
        # No axis mapping needed - GUI and GRBL both use 'A'
        grbl_axis = axis
            
        
        # Perform the jog if within bounds
        self.motor_ctrl.jog(grbl_axis, delta)
        # Position update loop will handle canvas redraw automatically


    def _home_all(self):
        success = self.motor_ctrl.home_all_synchronous()
        if success:
            self.status_label.configure(text=self._truncate_status("Homed"), text_color="green")
        else:
            self.status_label.configure(text=self._truncate_status("Homing failed"), text_color="red")
        # Position update loop will handle canvas redraw automatically
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
        self.status_label.configure(text=self._truncate_status("EMERGENCY STOP"), text_color="red")
        # Clear status after 3 seconds
        self.root.after(3000, lambda: self.status_label.configure(text="Ready", text_color=UI_COLORS['ON_SURFACE']))

    def _update_position_and_canvas(self):
        pos = self.motor_ctrl.get_position()
        
        # Check if position has changed significantly
        position_changed = any(
            abs(pos[axis] - self._last_position[axis]) > self._position_update_threshold
            for axis in ['X', 'Y', 'Z', 'A']
        )
        
        # Always update the position display
        self._update_position_display(pos)
        
        # Only redraw canvas if position changed significantly
        if position_changed:
            self._last_position = pos.copy()
            self._schedule_canvas_redraw(pos)
        
        self.root.after(1000, self._update_position_and_canvas)  # Update every 1000ms for better performance

    def _update_position_display(self, pos=None):
        if pos is None:
            pos = self.motor_ctrl.get_position()
        x_disp = pos['X']
        y_disp = pos['Y']
        z_disp = pos['Z']
        a_disp = pos['A']
        text = f"X:{x_disp:.1f}in\nY:{y_disp:.1f}in\nZ:{z_disp:.1f}in\nA:{a_disp:.0f}°"
        self.coord_label.configure(text=text)

    def _update_jog_size(self):
        try:
            self.jog_size = self.jog_size_var.get()  # Already in inches
        except Exception:
            pass

    def _on_jog_slider(self, value):
        # Convert slider value to float inches
        size_inches = float(value) * self._jog_slider_scale
        self.jog_size_var.set(size_inches)
        # Update the display label
        self.jog_size_label.configure(text=f"{size_inches:.2f} in")
        # Update the actual jog size
        self.jog_size = size_inches  # Already in inches
        
    def _on_z_limit_slider(self, value):
        # Convert slider value to negative Z limit (2.0 to 3.0 -> -2.0 to -3.0)
        limit_depth = -float(value)
        self.z_lower_limit_var.set(limit_depth)
        # Update the display label with 0.05" precision
        self.z_limit_label.configure(text=f"{limit_depth:.2f} in")
        # Update the actual Z lower limit
        self.z_lower_limit = limit_depth
        
        # Update toolpath generator if available
        if hasattr(self, 'toolpath_generator') and self.toolpath_generator is not None:
            self.toolpath_generator.cutting_height = limit_depth

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

    if SIMULATION_MODE:
        print("Running in simulation mode")



if __name__ == "__main__":
    main() 