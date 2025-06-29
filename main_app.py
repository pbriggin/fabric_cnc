#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main application for Fabric CNC: DXF import, toolpath generation, visualization, and motor control UI.
Runs in simulation mode on non-RPi systems (no GPIO required).
"""

import os
import sys
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import platform
import time
import math

# Try to import ezdxf for DXF parsing
try:
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

# Simulation mode if not on Raspberry Pi or motor imports failed
ON_RPI = platform.system() == 'Linux' and (os.uname().machine.startswith('arm') or os.uname().machine.startswith('aarch'))
SIMULATION_MODE = not ON_RPI or not MOTOR_IMPORTS_AVAILABLE

# Add these constants near the top of the file, after imports
INCH_TO_MM = 25.4
X_MAX_MM = 68 * INCH_TO_MM
Y_MAX_MM = 45 * INCH_TO_MM
Z_MAX_MM = 2 * INCH_TO_MM
PLOT_BUFFER_IN = 1.0  # 1.0 inch buffer on all sides (was 0.5)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fabric_cnc.main_app")

# --- Motor simulation logic ---
class SimulatedMotorController:
    def __init__(self):
        self.position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'ROT': 0.0}
        self.lock = threading.Lock()
        self.is_homing = False

    def _clamp(self, axis, value):
        if axis == 'X':
            return max(0.0, min(value, X_MAX_MM))
        elif axis == 'Y':
            return max(0.0, min(value, Y_MAX_MM))
        elif axis == 'Z':
            return max(0.0, min(value, Z_MAX_MM))
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

# --- Real Motor Controller Wrapper ---
class RealMotorController:
    def __init__(self):
        self.motor_controller = MotorController()
        self.lock = threading.Lock()
        self.is_homing = False
        self.position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'ROT': 0.0}  # Track position manually

    def _clamp(self, axis, value):
        if axis == 'X':
            return max(0.0, min(value, X_MAX_MM))
        elif axis == 'Y':
            return max(0.0, min(value, Y_MAX_MM))
        elif axis == 'Z':
            return max(0.0, min(value, Z_MAX_MM))
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
                        logger.warning("Z axis not implemented")
                    elif axis == 'ROT':
                        logger.warning("Rotation axis not implemented")
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
                    logger.warning("Z axis homing not implemented")
                    success = False
                elif axis == 'ROT':
                    logger.warning("Rotation axis homing not implemented")
                    success = False
                else:
                    success = False
                self.is_homing = False
                return success
            except Exception as e:
                logger.error(f"Home error on {axis}: {e}")
                self.is_homing = False
                return False

    def get_position(self):
        with self.lock:
            return dict(self.position)

    def estop(self):
        try:
            if GPIO_AVAILABLE:
                # Emergency stop - disable all motors
                for motor, config in self.motor_controller.motors.items():
                    GPIO.output(config['EN'], GPIO.HIGH)
                    GPIO.output(config['STEP'], GPIO.LOW)
                    GPIO.output(config['DIR'], GPIO.LOW)
            logger.warning("EMERGENCY STOP triggered")
        except Exception as e:
            logger.error(f"E-stop error: {e}")

    def cleanup(self):
        try:
            if GPIO_AVAILABLE:
                GPIO.cleanup()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    def move_to(self, x=None, y=None, z=None, rot=None):
        with self.lock:
            # Move X and Y axes if needed
            if x is not None:
                delta_x = x - self.position['X']
                if abs(delta_x) > 1e-6:
                    self.motor_controller.move_distance(delta_x, 'X')
                    self.position['X'] = x
            if y is not None:
                delta_y = y - self.position['Y']
                if abs(delta_y) > 1e-6:
                    self.motor_controller.move_distance(delta_y, 'Y')
                    self.position['Y'] = y
            # Z and ROT are not implemented in hardware, just update the value
            if z is not None:
                self.position['Z'] = z
            if rot is not None:
                self.position['ROT'] = rot
            # logger.info(f"Real move_to: X={self.position['X']:.2f}, Y={self.position['Y']:.2f}, Z={self.position['Z']:.2f}, ROT={self.position['ROT']:.2f}")

# --- Main App ---
class FabricCNCApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Fabric CNC Main App")
        # Maximize window by default (cross-platform)
        maximized = False
        try:
            self.root.state('zoomed')  # Windows, some Linux
            maximized = True
        except Exception:
            pass
        if not maximized:
            try:
                self.root.attributes('-zoomed', True)  # Some Linux
                maximized = True
            except Exception:
                pass
        if not maximized:
            try:
                self.root.attributes('-fullscreen', True)  # Fallback: true fullscreen
                maximized = True
            except Exception:
                pass
        if not maximized:
            # Fallback: set to screen size
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            self.root.geometry(f"{screen_width}x{screen_height}+0+0")
        
        # Initialize motor controller based on system
        if SIMULATION_MODE:
            self.motor_ctrl = SimulatedMotorController()
        else:
            self.motor_ctrl = RealMotorController()
        
        self.dxf_doc = None
        self.dxf_entities = []
        self.toolpath = []
        self.jog_speed = 0.25 * INCH_TO_MM  # 0.25 inch per jog, in mm internally
        self._arrow_key_state = {'Left': False, 'Right': False, 'Up': False, 'Down': False}
        self._arrow_key_repeat_delay = 60  # ms between jogs when holding key
        self._setup_ui()
        self._bind_arrow_keys()
        self._update_position_display()
        self.motor_ctrl.position['X'] = 0.0
        self.motor_ctrl.position['Y'] = 0.0

    def _bind_arrow_keys(self):
        self.root.bind('<KeyPress-Left>', lambda e: self._on_arrow_press('Left'))
        self.root.bind('<KeyRelease-Left>', lambda e: self._on_arrow_release('Left'))
        self.root.bind('<KeyPress-Right>', lambda e: self._on_arrow_press('Right'))
        self.root.bind('<KeyRelease-Right>', lambda e: self._on_arrow_release('Right'))
        self.root.bind('<KeyPress-Up>', lambda e: self._on_arrow_press('Up'))
        self.root.bind('<KeyRelease-Up>', lambda e: self._on_arrow_release('Up'))
        self.root.bind('<KeyPress-Down>', lambda e: self._on_arrow_press('Down'))
        self.root.bind('<KeyRelease-Down>', lambda e: self._on_arrow_release('Down'))

    def _on_arrow_press(self, key):
        if not self._arrow_key_state[key]:
            self._arrow_key_state[key] = True
            self._arrow_jog_loop(key)

    def _on_arrow_release(self, key):
        self._arrow_key_state[key] = False

    def _arrow_jog_loop(self, key):
        if not self._arrow_key_state[key]:
            return
        if key == 'Left':
            self._jog('X', -self.jog_speed)
        elif key == 'Right':
            self._jog('X', self.jog_speed)
        elif key == 'Up':
            self._jog('Y', self.jog_speed)
        elif key == 'Down':
            self._jog('Y', -self.jog_speed)
        self.root.after(self._arrow_key_repeat_delay, lambda: self._arrow_jog_loop(key))

    def _setup_ui(self):
        self.root.geometry("1200x700")
        self.root.minsize(1000, 600)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(0, weight=1)

        # Left toolbar (DXF tools)
        self.left_toolbar = ttk.Frame(self.main_frame, width=180)
        self.left_toolbar.grid(row=0, column=0, sticky="nsw")
        self._setup_left_toolbar()

        # Center canvas (DXF/toolpath/position)
        self.center_frame = ttk.Frame(self.main_frame)
        self.center_frame.grid(row=0, column=1, sticky="nsew")
        self.center_frame.rowconfigure(0, weight=1)
        self.center_frame.columnconfigure(0, weight=1)
        self._setup_center_canvas()

        # Right toolbar (motor controls)
        self.right_toolbar = ttk.Frame(self.main_frame, width=220)
        self.right_toolbar.grid(row=0, column=2, sticky="nse")
        self._setup_right_toolbar()

    # --- Left Toolbar: DXF tools ---
    def _setup_left_toolbar(self):
        ttk.Label(self.left_toolbar, text="DXF Tools", font=("Arial", 14, "bold")).pack(pady=(20, 10))
        self.import_btn = ttk.Button(self.left_toolbar, text="Import DXF File", command=self._import_dxf)
        self.import_btn.pack(pady=(10, 4), padx=10, fill=tk.X)
        self.gen_toolpath_btn = ttk.Button(self.left_toolbar, text="Generate Toolpath", command=self._generate_toolpath, state=tk.DISABLED)
        self.gen_toolpath_btn.pack(pady=4, padx=10, fill=tk.X)
        self.preview_btn = ttk.Button(self.left_toolbar, text="Preview Toolpath", command=self._preview_toolpath, state=tk.DISABLED)
        self.preview_btn.pack(pady=4, padx=10, fill=tk.X)
        self.run_btn = ttk.Button(self.left_toolbar, text="Run Toolpath", command=self._run_toolpath, state=tk.DISABLED)
        self.run_btn.pack(pady=4, padx=10, fill=tk.X)
        ttk.Separator(self.left_toolbar, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=20)
        
        # System status
        status_frame = ttk.LabelFrame(self.left_toolbar, text="System Status")
        status_frame.pack(fill=tk.X, padx=10, pady=10)
        
        mode_text = "SIMULATION" if SIMULATION_MODE else "REAL MOTORS"
        mode_color = "red" if SIMULATION_MODE else "green"
        self.status_label = ttk.Label(status_frame, text=f"Mode: {mode_text}", foreground=mode_color)
        self.status_label.pack(pady=5)
        
        if not MOTOR_IMPORTS_AVAILABLE:
            ttk.Label(status_frame, text="Motor modules not found", foreground="orange").pack(pady=2)
        if not ON_RPI:
            ttk.Label(status_frame, text="Not on Raspberry Pi", foreground="orange").pack(pady=2)

    # --- Center Canvas: DXF/toolpath/position ---
    def _setup_center_canvas(self):
        self.canvas = tk.Canvas(self.center_frame, bg="#f8f8f8", highlightthickness=1, relief=tk.SUNKEN)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.center_frame.bind("<Configure>", self._on_canvas_resize)
        self.canvas_width = 800
        self.canvas_height = 600
        self.canvas_scale = 1.0
        self.canvas_offset = (0, 0)
        self._draw_canvas()

    def _on_canvas_resize(self, event):
        self.canvas_width = event.width
        self.canvas_height = event.height
        self._draw_canvas()

    def _draw_canvas(self, live_toolpath=False):
        self.canvas.delete("all")
        # Draw axes in inches
        self._draw_axes_in_inches()
        # Draw DXF entities if loaded
        if self.dxf_doc and self.dxf_entities:
            self._draw_dxf_entities_inches()
        # Draw toolpath if generated
        if self.toolpath:
            self._draw_toolpath_inches()
        # Draw current tool head position
        if live_toolpath and hasattr(self, '_current_toolpath_pos'):
            pos = self._current_toolpath_pos
            self._draw_live_tool_head_inches(pos)
        else:
            pos = self.motor_ctrl.get_position()
            x = max(0.0, min(pos['X'], X_MAX_MM))
            y = max(0.0, min(pos['Y'], Y_MAX_MM))
            clamped_pos = {'X': x, 'Y': y}
            self._draw_tool_head_inches(clamped_pos)

    def _draw_axes_in_inches(self):
        # Draw X and Y axes with inch ticks and labels, with buffer
        inch_tick = 5
        for x_in in range(0, 69, inch_tick):
            x_px, _ = self._inches_to_canvas(x_in, 0)
            self.canvas.create_line(x_px, self.canvas_height, x_px, self.canvas_height-10, fill="#888")
            self.canvas.create_text(x_px, self.canvas_height-20, text=f"{x_in}", fill="#444", font=("Arial", 9))
        for y_in in range(0, 46, inch_tick):
            _, y_px = self._inches_to_canvas(0, y_in)
            y_px = self.canvas_height - y_px
            self.canvas.create_line(0, y_px, 10, y_px, fill="#888")
            self.canvas.create_text(25, y_px, text=f"{y_in}", fill="#444", font=("Arial", 9), anchor="w")
        # Draw border
        self.canvas.create_rectangle(0, 0, self.canvas_width, self.canvas_height, outline="#333", width=2)
        # Draw home position indicator (red cross at 0,0)
        home_x, home_y = self._inches_to_canvas(0, 0)
        home_y = self.canvas_height - home_y  # Mirror Y for the red X
        size = 10
        self.canvas.create_line(home_x - size, home_y - size, home_x + size, home_y + size, fill="#d00", width=2)
        self.canvas.create_line(home_x - size, home_y + size, home_x + size, home_y - size, fill="#d00", width=2)

    def _inches_to_canvas(self, x_in, y_in):
        # Add buffer to all sides
        plot_width_in = 68 + 2 * PLOT_BUFFER_IN
        plot_height_in = 45 + 2 * PLOT_BUFFER_IN
        sx = self.canvas_width / plot_width_in
        sy = self.canvas_height / plot_height_in
        ox = PLOT_BUFFER_IN * sx
        oy = PLOT_BUFFER_IN * sy
        return x_in * sx + ox, y_in * sy + oy

    def _draw_tool_head_inches(self, pos):
        # Draw a small circle at the current tool head position (in inches)
        x_in = pos['X'] / INCH_TO_MM
        y_in = pos['Y'] / INCH_TO_MM
        x_c, y_c = self._inches_to_canvas(x_in, y_in)
        y_c = self.canvas_height - y_c  # Mirror Y for the green dot only
        r = 7
        self.canvas.create_oval(x_c - r, y_c - r, x_c + r, y_c + r, fill="#0a0", outline="#080", width=2)
        self.canvas.create_text(x_c, y_c - 18, text=f"({x_in:.2f}, {y_in:.2f})", fill="#080", font=("Arial", 10, "bold"))

    def _draw_dxf_entities_inches(self):
        # Draw DXF entities, converting mm to inches for plotting
        if not (self.dxf_doc and self.dxf_entities):
            return
        scale = getattr(self, 'dxf_unit_scale', 1.0)
        min_x, min_y, max_x, max_y = self._get_dxf_extents_inches()
        if min_x is not None and max_y is not None:
            dx = min_x - PLOT_BUFFER_IN
            dy = max_y + PLOT_BUFFER_IN
        else:
            dx, dy = 0, 0

        # If toolpaths exist, use their shapes for color grouping
        color_cycle = [
            '#d00', '#0077cc', '#00aa88', '#cc7700', '#aa00cc', '#cc2222', '#0a0', '#f0a', '#0af', '#fa0',
            '#a0f', '#0fa', '#af0', '#f00', '#00f', '#0ff', '#ff0', '#f0f', '#888', '#444'
        ]
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
                x1c, y1c = self._inches_to_canvas(x1 * scale - dx, dy - y1 * scale)
                x2c, y2c = self._inches_to_canvas(x2 * scale - dx, dy - y2 * scale)
                self.canvas.create_line(x1c, y1c, x2c, y2c, fill="#888", width=2)
            elif t == 'LWPOLYLINE':
                points = [(p[0], p[1]) for p in e.get_points()]
                flat = []
                for x, y in points:
                    x_c, y_c = self._inches_to_canvas(x * scale - dx, dy - y * scale)
                    flat.extend([x_c, y_c])
                self.canvas.create_line(flat, fill="#888", width=2)
            elif t == 'POLYLINE':
                points = [(v.dxf.x, v.dxf.y) for v in e.vertices()]
                flat = []
                for x, y in points:
                    x_c, y_c = self._inches_to_canvas(x * scale - dx, dy - y * scale)
                    flat.extend([x_c, y_c])
                self.canvas.create_line(flat, fill="#888", width=2)
            elif t == 'SPLINE':
                points = list(e.flattening(0.1))
                flat = []
                for x, y, *_ in points:
                    x_transformed = x * scale - dx
                    y_transformed = dy - y * scale
                    x_c, y_c = self._inches_to_canvas(x_transformed, y_transformed)
                    flat.extend([x_c, y_c])
                self.canvas.create_line(flat, fill="#888", width=2)
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
                    x_transformed = x * scale - dx
                    y_transformed = dy - y * scale
                    x_c, y_c = self._inches_to_canvas(x_transformed, y_transformed)
                    points.append((x_c, y_c))
                self.canvas.create_line(*[coord for pt in points for coord in pt], fill="#888", width=2)
            elif t == 'CIRCLE':
                center = e.dxf.center
                r = e.dxf.radius
                n = 32
                points = []
                for i in range(n+1):
                    angle = 2 * math.pi * i / n
                    x = center.x + r * math.cos(angle)
                    y = center.y + r * math.sin(angle)
                    x_transformed = x * scale - dx
                    y_transformed = dy - y * scale
                    x_c, y_c = self._inches_to_canvas(x_transformed, y_transformed)
                    points.append((x_c, y_c))
                self.canvas.create_line(*[coord for pt in points for coord in pt], fill="#888", width=2)

    def _draw_toolpath_inches(self):
        # Draw toolpath in inches
        if not hasattr(self, 'toolpaths') or not self.toolpaths:
            return
        # Color cycle for up to 20 shapes
        color_cycle = [
            '#d00', '#0077cc', '#00aa88', '#cc7700', '#aa00cc', '#cc2222', '#0a0', '#f0a', '#0af', '#fa0',
            '#a0f', '#0fa', '#af0', '#f00', '#00f', '#0ff', '#ff0', '#f0f', '#888', '#444'
        ]
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
                y_c = self.canvas_height - y_c
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
            doc = ezdxf.readfile(file_path)
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
            self.dxf_doc = doc
            self.dxf_entities = entities
            self.toolpath = []
            self.gen_toolpath_btn.config(state=tk.NORMAL)
            # Auto-orient to top-left, no scaling
            self._auto_orient_dxf_top_left(debug=True)
            self._draw_canvas()
        except Exception as e:
            logger.error(f"Failed to load DXF: {e}")
            messagebox.showerror("DXF Import Error", str(e))

    def _get_dxf_extents_inches(self):
        """Get global extents across all DXF entities, supporting all entity types."""
        scale = getattr(self, 'dxf_unit_scale', 1.0)
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')
        found = False
        
        for e in self.dxf_entities:
            t = e.dxftype()
            xs, ys = [], []
            
            if t == 'LINE':
                xs = [e.dxf.start.x * scale, e.dxf.end.x * scale]
                ys = [e.dxf.start.y * scale, e.dxf.end.y * scale]
            elif t == 'LWPOLYLINE':
                pts = [p[:2] for p in e.get_points()]
                if pts:
                    xs = [p[0] * scale for p in pts]
                    ys = [p[1] * scale for p in pts]
            elif t == 'POLYLINE':
                pts = [(v.dxf.x * scale, v.dxf.y * scale) for v in e.vertices()]
                if pts:
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
            elif t == 'SPLINE':
                pts = list(e.flattening(0.1))
                if pts:
                    xs = [p[0] * scale for p in pts]
                    ys = [p[1] * scale for p in pts]
            elif t == 'ARC' or t == 'CIRCLE':
                center = e.dxf.center
                r = e.dxf.radius
                if t == 'ARC':
                    start = math.radians(e.dxf.start_angle)
                    end = math.radians(e.dxf.end_angle)
                    if end < start:
                        end += 2 * math.pi
                    n = 32
                    pts = [(center.x + r * math.cos(start + (end - start) * i / n),
                            center.y + r * math.sin(start + (end - start) * i / n)) for i in range(n+1)]
                else:
                    n = 32
                    pts = [(center.x + r * math.cos(2 * math.pi * i / n),
                            center.y + r * math.sin(2 * math.pi * i / n)) for i in range(n+1)]
                xs = [p[0] * scale for p in pts]
                ys = [p[1] * scale for p in pts]
            
            if xs and ys:
                min_x = min(min_x, min(xs))
                max_x = max(max_x, max(xs))
                min_y = min(min_y, min(ys))
                max_y = max(max_y, max(ys))
                found = True
        
        if not found:
            return None, None, None, None
        return min_x, min_y, max_x, max_y

    def _auto_orient_dxf_top_left(self, debug=False):
        # No-op: do not transform entities at import, only at plot time
        pass

    def _generate_toolpath(self):
        """Generate toolpaths for each shape, with tangent angle and Z (lift at corners)."""
        if not self.dxf_entities:
            messagebox.showwarning("No DXF", "Import a DXF file first.")
            return
        scale = getattr(self, 'dxf_unit_scale', 1.0)
        min_x, min_y, max_x, max_y = self._get_dxf_extents_inches()
        dx = min_x - PLOT_BUFFER_IN if min_x is not None else 0
        dy = max_y + PLOT_BUFFER_IN if max_y is not None else 0

        # --- Flatten all entities into segments ---
        segments = []  # Each segment is ((x1, y1), (x2, y2))
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
            # Start a new shape
            seg = segments[idx]
            p_start = (round(seg[0][0], 6), round(seg[0][1], 6))
            p_end = (round(seg[1][0], 6), round(seg[1][1], 6))
            shape = [p_start, p_end]
            visited.add(idx)
            # Extend forwards
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
            # Extend backwards
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
            # Remove duplicate consecutive points
            deduped = [shape[0]]
            for pt in shape[1:]:
                if pt != deduped[-1]:
                    deduped.append(pt)
            shapes.append(deduped)
        # --- Generate toolpaths from shapes ---
        toolpaths = []
        for pts in shapes:
            if len(pts) < 2:
                continue
            # Ensure CCW for closed shapes
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
            # Transform all points
            pts_t = [(x * scale - dx, dy - y * scale) for x, y in pts_ccw]
            path = []
            # Angle threshold for corners (in radians)
            angle_thresh = math.radians(30)
            n = len(pts_t)
            # Start: move to first point, Z up, then Z down
            if n < 2:
                continue
            angle0 = math.atan2(pts_t[1][1] - pts_t[0][1], pts_t[1][0] - pts_t[0][0])
            path.append((pts_t[0][0], pts_t[0][1], angle0, 1))  # Z up
            path.append((pts_t[0][0], pts_t[0][1], angle0, 0))  # Z down
            for i in range(1, n):
                x0, y0 = pts_t[i-1]
                x1, y1 = pts_t[i]
                angle = math.atan2(y1 - y0, x1 - x0)
                # Detect corners for polylines (not for smooth curves)
                is_corner = False
                if 1 <= i < n-1:
                    # Compute angle between previous, current, next
                    x_prev, y_prev = pts_t[i-2] if i-2 >= 0 else pts_t[i-1]
                    x_next, y_next = pts_t[i+1] if i+1 < n else pts_t[i]
                    v1 = (x0 - x_prev, y0 - y_prev)
                    v2 = (x1 - x0, y1 - y0)
                    len1 = math.hypot(*v1)
                    len2 = math.hypot(*v2)
                    if len1 > 1e-8 and len2 > 1e-8:
                        dot = v1[0]*v2[0] + v1[1]*v2[1]
                        cos_theta = dot / (len1 * len2)
                        cos_theta = max(-1.0, min(1.0, cos_theta))
                        theta = math.acos(cos_theta)
                        if theta > angle_thresh:
                            is_corner = True
                if is_corner:
                    path.append((x0, y0, angle, 1))  # Z up at corner
                    path.append((x0, y0, angle, 0))  # Z down at corner
                path.append((x1, y1, angle, 0))  # Move/cut
            # End: Z up at last point
            path.append((pts_t[-1][0], pts_t[-1][1], angle, 1))  # Z up at end
            toolpaths.append(path)
        self.toolpaths = toolpaths
        self._draw_canvas()
        self.preview_btn.config(state=tk.NORMAL)
        self.run_btn.config(state=tk.NORMAL)

    def _preview_toolpath(self):
        """Animate the toolpath preview, showing the end effector moving with orientation and Z state, one shape at a time, with debug output and shape highlighting."""
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
                    # Draw green dot first if Z=0, then grey dot if Z=1 (slightly larger)
                    if z == 0:
                        self.canvas.create_oval(x_c-6, y_c-6, x_c+6, y_c+6, fill="#0a0", outline="#000")
                    if z == 1:
                        self.canvas.create_oval(x_c-8, y_c-8, x_c+8, y_c+8, fill="#aaa", outline="#000")
                    # Draw orientation line (wheel direction)
                    x2 = x + r * math.cos(angle)
                    y2 = y + r * math.sin(angle)
                    x2_c, y2_c = self._inches_to_canvas(x2, y2)
                    self.canvas.create_line(x_c, y_c, x2_c, y2_c, fill="#f0a", width=3)
                self.root.after(2, animate_step, idx + steps_per_tick)  # Smoother animation
            animate_step()
        animate_shape()

    def _run_toolpath(self):
        """Command the motors to follow the toolpath, updating the green dot and orientation line in real time."""
        if not hasattr(self, 'toolpaths') or not self.toolpaths:
            messagebox.showwarning("No Toolpath", "Generate a toolpath first.")
            return
        self.import_btn.config(state=tk.DISABLED)
        self.gen_toolpath_btn.config(state=tk.DISABLED)
        self.preview_btn.config(state=tk.DISABLED)
        self.run_btn.config(state=tk.DISABLED)
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
            self.motor_ctrl.move_to(x=x_mm, y=y_mm, z=Z_MAX_MM, rot=0.0)
        
        # Update position and display
        self._current_toolpath_pos['X'] = x_mm
        self._current_toolpath_pos['Y'] = y_mm
        self._current_toolpath_pos['Z'] = Z_MAX_MM
        self._current_toolpath_pos['ROT'] = 0.0
        
        self._update_position_display()
        self._draw_canvas(live_toolpath=True)
        
        # Wait a moment, then start the toolpath
        self.root.after(500, self._run_toolpath_step)

    def _run_toolpath_step(self):
        if not self._running_toolpath:
            return
        shape_idx, step_idx = self._current_toolpath_idx
        if shape_idx >= len(self.toolpaths):
            self._running_toolpath = False
            self.import_btn.config(state=tk.NORMAL)
            self.gen_toolpath_btn.config(state=tk.NORMAL)
            self.preview_btn.config(state=tk.NORMAL)
            self.run_btn.config(state=tk.NORMAL)
            return
        path = self.toolpaths[shape_idx]
        if step_idx >= len(path):
            # Move to next shape
            self._current_toolpath_idx = [shape_idx + 1, 0]
            self.root.after(100, self._run_toolpath_step)  # Longer pause between shapes
            return
        x, y, angle, z = path[step_idx]
        # Swap x and y for correct display
        self._current_toolpath_pos['X'] = y * INCH_TO_MM
        self._current_toolpath_pos['Y'] = x * INCH_TO_MM
        self._current_toolpath_pos['Z'] = 0.0 if z == 0 else Z_MAX_MM
        self._current_toolpath_pos['ROT'] = math.degrees(angle)
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
        self._update_position_display()  # Force update after each move
        self._draw_canvas(live_toolpath=True)
        # Next step
        self._current_toolpath_idx[1] += 1
        self._toolpath_step_count += 1
        self.root.after(50, self._run_toolpath_step)  # Slower execution (50ms instead of 5ms)

    def _draw_live_tool_head_inches(self, pos):
        # Draw a green dot and orientation line at the current tool head position (in inches)
        x_in = pos['X'] / INCH_TO_MM
        y_in = pos['Y'] / INCH_TO_MM
        rot_rad = math.radians(pos.get('ROT', 0.0))
        x_c, y_c = self._inches_to_canvas(x_in, y_in)
        r = 7
        self.canvas.create_oval(x_c - r, y_c - r, x_c + r, y_c + r, fill="#0a0", outline="#000", width=2)
        # Draw orientation line
        r_dir = 0.5  # 0.5 inch
        x2 = x_in + r_dir * math.cos(rot_rad)
        y2 = y_in + r_dir * math.sin(rot_rad)
        x2_c, y2_c = self._inches_to_canvas(x2, y2)
        self.canvas.create_line(x_c, y_c, x2_c, y2_c, fill="#f0a", width=3)

    # --- Right Toolbar: Motor controls ---
    def _setup_right_toolbar(self):
        ttk.Label(self.right_toolbar, text="Motor Controls", font=("Arial", 14, "bold")).pack(pady=(20, 10))
        
        # Jog controls (arrow key layout)
        jog_frame = ttk.LabelFrame(self.right_toolbar, text="Jog")
        jog_frame.pack(fill=tk.X, padx=10, pady=8)
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
        
        # Z and ROT jogs below
        zrot_frame = ttk.Frame(self.right_toolbar)
        zrot_frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        self._add_jog_button(zrot_frame, "Z+", lambda: self._jog('Z', +1)).grid(row=0, column=0, padx=2, pady=2)
        self._add_jog_button(zrot_frame, "Z-", lambda: self._jog('Z', -1)).grid(row=0, column=1, padx=2, pady=2)
        self._add_jog_button(zrot_frame, "ROT+", lambda: self._jog('ROT', +5)).grid(row=0, column=2, padx=2, pady=2)
        self._add_jog_button(zrot_frame, "ROT-", lambda: self._jog('ROT', -5)).grid(row=0, column=3, padx=2, pady=2)
        
        # Speed adjustment
        speed_frame = ttk.Frame(self.right_toolbar)
        speed_frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Label(speed_frame, text="Jog Step (in)").pack(side=tk.LEFT)
        self.jog_speed_var = tk.DoubleVar(value=self.jog_speed / INCH_TO_MM)
        speed_spin = ttk.Spinbox(speed_frame, from_=0.01, to=2.0, increment=0.01, textvariable=self.jog_speed_var, width=5, command=self._update_jog_speed)
        speed_spin.pack(side=tk.LEFT, padx=5)
        self.jog_speed_var.trace_add('write', lambda *a: self._update_jog_speed())
        
        # Home controls
        home_frame = ttk.LabelFrame(self.right_toolbar, text="Home")
        home_frame.pack(fill=tk.X, padx=10, pady=8)
        ttk.Button(home_frame, text="Home X", command=lambda: self._home('X')).pack(fill=tk.X, pady=2)
        ttk.Button(home_frame, text="Home Y", command=lambda: self._home('Y')).pack(fill=tk.X, pady=2)
        ttk.Button(home_frame, text="Home Z", command=lambda: self._home('Z')).pack(fill=tk.X, pady=2)
        ttk.Button(home_frame, text="Home ROT", command=lambda: self._home('ROT')).pack(fill=tk.X, pady=2)
        ttk.Button(home_frame, text="Home All", command=self._home_all).pack(fill=tk.X, pady=2)
        
        # E-stop
        ttk.Separator(self.right_toolbar, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        estop_btn = ttk.Button(self.right_toolbar, text="EMERGENCY STOP", command=self._estop)
        estop_btn.pack(fill=tk.X, padx=10, pady=10)
        
        # Coordinates display
        ttk.Separator(self.right_toolbar, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        self.coord_label = ttk.Label(self.right_toolbar, text="", font=("Consolas", 13, "bold"), foreground="#333")
        self.coord_label.pack(pady=10)

    def _add_jog_button(self, parent, text, cmd):
        btn = ttk.Button(parent, text=text, command=cmd, width=5)
        return btn

    def _jog(self, axis, delta):
        self.motor_ctrl.jog(axis, delta)
        self._draw_canvas()
        self._update_position_display()

    def _home(self, axis):
        success = self.motor_ctrl.home(axis)
        if success:
            messagebox.showinfo("Homing Complete", f"{axis} axis homed successfully")
        else:
            messagebox.showerror("Homing Failed", f"Failed to home {axis} axis")
        self._draw_canvas()
        self._update_position_display()

    def _home_all(self):
        """Home all axes in sequence"""
        axes = ['X', 'Y', 'Z', 'ROT']
        for axis in axes:
            if axis in ['Z', 'ROT']:
                # Skip unimplemented axes
                continue
            success = self.motor_ctrl.home(axis)
            if not success:
                messagebox.showerror("Homing Failed", f"Failed to home {axis} axis")
                return
        messagebox.showinfo("Homing Complete", "All axes homed successfully")
        self._draw_canvas()
        self._update_position_display()

    def _estop(self):
        self.motor_ctrl.estop()
        messagebox.showwarning("EMERGENCY STOP", "All motors stopped")

    def _update_position_display(self):
        # Use toolpath position if running, otherwise use motor controller position
        if hasattr(self, '_running_toolpath') and self._running_toolpath and hasattr(self, '_current_toolpath_pos'):
            pos = self._current_toolpath_pos
        else:
            pos = self.motor_ctrl.get_position()
        text = f"X: {pos['X']/INCH_TO_MM:.2f} in\nY: {pos['Y']/INCH_TO_MM:.2f} in\nZ: {pos['Z']/INCH_TO_MM:.2f} in\nROT: {pos['ROT']:.1f}°"
        self.coord_label.config(text=text)
        self.root.after(200, self._update_position_display)

    def _update_jog_speed(self):
        try:
            self.jog_speed = self.jog_speed_var.get() * INCH_TO_MM
        except tk.TclError:
            pass

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
    root = tk.Tk()
    # Use ttk theme for modern look
    style = ttk.Style(root)
    if sys.platform == "darwin":
        style.theme_use("aqua")
    else:
        style.theme_use("clam")
    # Custom style for E-stop
    style.configure("Danger.TButton", foreground="#fff", background="#d00", font=("Arial", 12, "bold"))
    app = FabricCNCApp(root)
    root.mainloop()

    # In main(), print debug info for simulation mode
    print(f"[DEBUG] ON_RPI={ON_RPI}")
    print(f"[DEBUG] MOTOR_IMPORTS_AVAILABLE={MOTOR_IMPORTS_AVAILABLE}")
    print(f"[DEBUG] SIMULATION_MODE={SIMULATION_MODE}")

if __name__ == "__main__":
    main() 