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

# --- Main App ---
class FabricCNCApp:
    def __init__(self, root):
        print("[DEBUG] FabricCNCApp.__init__ called")
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
            print("Running in SIMULATION MODE")
            self.motor_ctrl = SimulatedMotorController()
        else:
            print("Running with REAL MOTOR CONTROL")
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
        print("[DEBUG] FabricCNCApp._setup_ui called")
        # Main layout: 3 columns (left, center, right)
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
        ttk.Button(self.left_toolbar, text="Import DXF File", command=self._import_dxf).pack(fill=tk.X, padx=10, pady=8)
        self.gen_toolpath_btn = ttk.Button(self.left_toolbar, text="Generate Toolpath", command=self._generate_toolpath, state=tk.DISABLED)
        self.gen_toolpath_btn.pack(fill=tk.X, padx=10, pady=8)
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
        # Draw current tool head position
        pos = self.motor_ctrl.get_position()
        # Clamp the position to the plot area
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
        r = 7
        y_c = self.canvas_height - y_c
        self.canvas.create_oval(x_c - r, y_c - r, x_c + r, y_c + r, fill="#0a0", outline="#080", width=2)
        self.canvas.create_text(x_c, y_c - 18, text=f"({x_in:.2f}, {y_in:.2f})", fill="#080", font=("Arial", 10, "bold"))

    def _draw_dxf_entities_inches(self):
        # Draw DXF entities, converting mm to inches for plotting
        if not (self.dxf_doc and self.dxf_entities):
            return
        for e in self.dxf_entities:
            if e.dxftype() == 'LINE':
                x1, y1 = e.dxf.start.x / INCH_TO_MM, e.dxf.start.y / INCH_TO_MM
                x2, y2 = e.dxf.end.x / INCH_TO_MM, e.dxf.end.y / INCH_TO_MM
                x1c, y1c = self._inches_to_canvas(x1, y1)
                x2c, y2c = self._inches_to_canvas(x2, y2)
                y1c = self.canvas_height - y1c
                y2c = self.canvas_height - y2c
                self.canvas.create_line(x1c, y1c, x2c, y2c, fill="#222", width=2)
            elif e.dxftype() == 'LWPOLYLINE':
                points = [(p[0] / INCH_TO_MM, p[1] / INCH_TO_MM) for p in e.get_points()]
                flat = []
                for x, y in points:
                    x_c, y_c = self._inches_to_canvas(x, y)
                    y_c = self.canvas_height - y_c
                    flat.extend([x_c, y_c])
                self.canvas.create_line(flat, fill="#0077cc", width=2)

    def _draw_toolpath_inches(self):
        # Draw toolpath in inches
        for seg in self.toolpath:
            (x1, y1), (x2, y2) = seg
            x1_in, y1_in = x1 / INCH_TO_MM, y1 / INCH_TO_MM
            x2_in, y2_in = x2 / INCH_TO_MM, y2 / INCH_TO_MM
            x1c, y1c = self._inches_to_canvas(x1_in, y1_in)
            x2c, y2c = self._inches_to_canvas(x2_in, y2_in)
            y1c = self.canvas_height - y1c
            y2c = self.canvas_height - y2c
            self.canvas.create_line(x1c, y1c, x2c, y2c, fill="#d00", width=2, dash=(4, 2))

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
            entities = [e for e in msp if e.dxftype() in ('LINE', 'LWPOLYLINE')]
            if not entities:
                messagebox.showerror("DXF Import Error", "No supported entities (LINE, LWPOLYLINE) found in DXF file.")
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
            logger.info(f"Loaded DXF: {file_path} ({len(entities)} entities), units: {insunits}, scale: {self.dxf_unit_scale}")
            # Auto-orient to top-left, no scaling
            self._auto_orient_dxf_top_left(debug=True)
            self._draw_canvas()
        except Exception as e:
            logger.error(f"Failed to load DXF: {e}")
            messagebox.showerror("DXF Import Error", str(e))

    def _auto_orient_dxf_top_left(self, debug=False):
        # Find extents in inches
        scale = getattr(self, 'dxf_unit_scale', 1.0)
        min_x, min_y, max_x, max_y = self._get_dxf_extents_inches()
        if min_x is None or min_y is None or Vec3 is None:
            if debug:
                print(f"[DEBUG] No extents found: min_x={min_x}, min_y={min_y}, Vec3={Vec3}")
            return  # Nothing to orient or ezdxf not available
        dx = min_x
        dy = min_y
        y_top = 45
        if debug:
            print(f"[DEBUG] DXF extents (inches): min_x={min_x}, min_y={min_y}, max_x={max_x}, max_y={max_y}, scale={scale}")
        for i, e in enumerate(self.dxf_entities):
            if e.dxftype() == 'LINE':
                # Convert to inches, translate to (0, y_top), flip Y
                x1 = (e.dxf.start.x * scale - dx)
                y1 = (e.dxf.start.y * scale - dy)
                x2 = (e.dxf.end.x * scale - dx)
                y2 = (e.dxf.end.y * scale - dy)
                y1_flipped = y_top - y1
                y2_flipped = y_top - y2
                new_start = Vec3(x1, y1_flipped, e.dxf.start.z * scale if hasattr(e.dxf.start, 'z') else 0.0)
                new_end = Vec3(x2, y2_flipped, e.dxf.end.z * scale if hasattr(e.dxf.end, 'z') else 0.0)
                if debug and i < 5:
                    print(f"[DEBUG] LINE {i}: ({x1:.2f}, {y1_flipped:.2f}) -> ({x2:.2f}, {y2_flipped:.2f})")
                e.dxf.start = new_start
                e.dxf.end = new_end
            elif e.dxftype() == 'LWPOLYLINE':
                pts = list(e.get_points())
                new_pts = []
                for j, p in enumerate(pts):
                    x = (p[0] * scale - dx)
                    y = (p[1] * scale - dy)
                    y_flipped = y_top - y
                    if debug and i < 2 and j < 5:
                        print(f"[DEBUG] LWPOLYLINE {i} pt{j}: ({x:.2f}, {y_flipped:.2f})")
                    new_pts.append((x, y_flipped) + p[2:])
                e.points = new_pts

    def _get_dxf_extents_inches(self):
        scale = getattr(self, 'dxf_unit_scale', 1.0)
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')
        found = False
        for e in self.dxf_entities:
            if e.dxftype() == 'LINE':
                xs = [e.dxf.start.x * scale, e.dxf.end.x * scale]
                ys = [e.dxf.start.y * scale, e.dxf.end.y * scale]
            elif e.dxftype() == 'LWPOLYLINE':
                pts = [p[:2] for p in e.get_points()]
                if not pts:
                    continue
                xs = [p[0] * scale for p in pts]
                ys = [p[1] * scale for p in pts]
            else:
                continue
            if not xs or not ys:
                continue
            min_x = min(min_x, min(xs))
            max_x = max(max_x, max(xs))
            min_y = min(min_y, min(ys))
            max_y = max(max_y, max(ys))
            found = True
        if not found:
            return None, None, None, None
        return min_x, min_y, max_x, max_y

    def _generate_toolpath(self):
        # Stub: just connect all lines in order for now
        if not self.dxf_entities:
            messagebox.showwarning("No DXF", "Import a DXF file first.")
            return
        toolpath = []
        last = None
        for e in self.dxf_entities:
            if e.dxftype() == 'LINE':
                start = (e.dxf.start.x, e.dxf.start.y)
                end = (e.dxf.end.x, e.dxf.end.y)
                toolpath.append((start, end))
                last = end
            elif e.dxftype() == 'LWPOLYLINE':
                pts = [p[:2] for p in e.get_points()]
                for i in range(len(pts) - 1):
                    toolpath.append((pts[i], pts[i+1]))
                last = pts[-1]
        self.toolpath = toolpath
        logger.info(f"Generated toolpath with {len(toolpath)} segments.")
        self._draw_canvas()

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
    print("[DEBUG] Starting Fabric CNC App main()...")
    root = tk.Tk()
    print("[DEBUG] Tk root created.")
    # Use ttk theme for modern look
    style = ttk.Style(root)
    if sys.platform == "darwin":
        style.theme_use("aqua")
    else:
        style.theme_use("clam")
    print("[DEBUG] ttk theme set.")
    # Custom style for E-stop
    style.configure("Danger.TButton", foreground="#fff", background="#d00", font=("Arial", 12, "bold"))
    print("[DEBUG] Creating FabricCNCApp instance...")
    app = FabricCNCApp(root)
    print("[DEBUG] FabricCNCApp instance created. Entering mainloop...")
    root.mainloop()
    print("[DEBUG] mainloop exited.")

    # In main(), print debug info for simulation mode
    print(f"[DEBUG] ON_RPI={ON_RPI}")
    print(f"[DEBUG] MOTOR_IMPORTS_AVAILABLE={MOTOR_IMPORTS_AVAILABLE}")
    print(f"[DEBUG] SIMULATION_MODE={SIMULATION_MODE}")

if __name__ == "__main__":
    main() 