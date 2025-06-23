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

# Try to import ezdxf for DXF parsing
try:
    import ezdxf
except ImportError:
    ezdxf = None

# Simulation mode if not on Raspberry Pi
ON_RPI = platform.system() == 'Linux' and os.uname().machine.startswith('arm')
SIMULATION_MODE = not ON_RPI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fabric_cnc.main_app")

# --- Motor simulation logic ---
class SimulatedMotorController:
    def __init__(self):
        self.position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'ROT': 0.0}
        self.lock = threading.Lock()

    def jog(self, axis, delta):
        with self.lock:
            self.position[axis] += delta
            logger.info(f"Jogged {axis} by {delta}mm. New pos: {self.position[axis]:.2f}")

    def home(self, axis):
        with self.lock:
            self.position[axis] = 0.0
            logger.info(f"Homed {axis} axis.")

    def get_position(self):
        with self.lock:
            return dict(self.position)

    def estop(self):
        logger.warning("EMERGENCY STOP triggered (simulated)")

# --- Main App ---
class FabricCNCApp:
    def __init__(self, root):
        print("[DEBUG] FabricCNCApp.__init__ called")
        self.root = root
        self.root.title("Fabric CNC Main App")
        self.motor_ctrl = SimulatedMotorController()
        self.dxf_doc = None
        self.dxf_entities = []
        self.toolpath = []
        self.jog_speed = 10  # mm per jog, adjustable
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
        # Add more DXF/toolpath tools here as needed

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
        # Draw DXF entities if loaded
        if self.dxf_doc and self.dxf_entities:
            self._draw_dxf_entities()
        # Draw toolpath if generated
        if self.toolpath:
            self._draw_toolpath()
        # Draw current tool head position
        pos = self.motor_ctrl.get_position()
        self._draw_tool_head(pos)

    def _draw_dxf_entities(self):
        # Fit DXF extents to canvas
        min_x, min_y, max_x, max_y = self._get_dxf_extents()
        if max_x - min_x < 1e-3 or max_y - min_y < 1e-3:
            return
        scale_x = (self.canvas_width - 40) / (max_x - min_x)
        scale_y = (self.canvas_height - 40) / (max_y - min_y)
        self.canvas_scale = min(scale_x, scale_y)
        self.canvas_offset = (20 - min_x * self.canvas_scale, 20 - min_y * self.canvas_scale)
        for e in self.dxf_entities:
            if e.dxftype() == 'LINE':
                x1, y1 = self._dxf_to_canvas(e.dxf.start.x, e.dxf.start.y)
                x2, y2 = self._dxf_to_canvas(e.dxf.end.x, e.dxf.end.y)
                self.canvas.create_line(x1, self.canvas_height - y1, x2, self.canvas_height - y2, fill="#222", width=2)
            elif e.dxftype() == 'LWPOLYLINE':
                points = [self._dxf_to_canvas(p[0], p[1]) for p in e.get_points()]
                flat = []
                for x, y in points:
                    flat.extend([x, self.canvas_height - y])
                self.canvas.create_line(flat, fill="#0077cc", width=2)
            # Add more entity types as needed

    def _draw_toolpath(self):
        # For now, just draw as red lines
        for seg in self.toolpath:
            (x1, y1), (x2, y2) = seg
            x1c, y1c = self._dxf_to_canvas(x1, y1)
            x2c, y2c = self._dxf_to_canvas(x2, y2)
            self.canvas.create_line(x1c, self.canvas_height - y1c, x2c, self.canvas_height - y2c, fill="#d00", width=2, dash=(4, 2))

    def _draw_tool_head(self, pos):
        # Draw a small circle at the current tool head position
        x, y = pos['X'], pos['Y']
        x_c, y_c = self._dxf_to_canvas(x, y)
        r = 7
        self.canvas.create_oval(x_c - r, self.canvas_height - y_c - r, x_c + r, self.canvas_height - y_c + r, fill="#0a0", outline="#080", width=2)
        self.canvas.create_text(x_c, self.canvas_height - y_c - 18, text=f"({x:.1f}, {y:.1f}) mm", fill="#080", font=("Arial", 10, "bold"))

    def _dxf_to_canvas(self, x, y):
        sx, sy = self.canvas_scale, self.canvas_scale
        ox, oy = self.canvas_offset
        return x * sx + ox, y * sy + oy

    def _get_dxf_extents(self):
        min_x, min_y, max_x, max_y = 0, 0, 100, 100
        if self.dxf_entities:
            xs, ys = [], []
            for e in self.dxf_entities:
                if e.dxftype() == 'LINE':
                    xs.extend([e.dxf.start.x, e.dxf.end.x])
                    ys.extend([e.dxf.start.y, e.dxf.end.y])
                elif e.dxftype() == 'LWPOLYLINE':
                    for p in e.get_points():
                        xs.append(p[0])
                        ys.append(p[1])
            if xs and ys:
                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)
        return min_x, min_y, max_x, max_y

    # --- DXF Import/Toolpath ---
    def _import_dxf(self):
        if ezdxf is None:
            messagebox.showerror("Missing Dependency", "ezdxf is not installed. Please install it to import DXF files.")
            return
        file_path = filedialog.askopenfilename(filetypes=[("DXF Files", "*.dxf")])
        if not file_path:
            return
        try:
            doc = ezdxf.readfile(file_path)
            msp = doc.modelspace()
            entities = [e for e in msp if e.dxftype() in ('LINE', 'LWPOLYLINE')]
            self.dxf_doc = doc
            self.dxf_entities = entities
            self.toolpath = []
            self.gen_toolpath_btn.config(state=tk.NORMAL)
            logger.info(f"Loaded DXF: {file_path} ({len(entities)} entities)")
            self._draw_canvas()
        except Exception as e:
            logger.error(f"Failed to load DXF: {e}")
            messagebox.showerror("DXF Import Error", str(e))

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
        ttk.Label(speed_frame, text="Jog Speed (mm)").pack(side=tk.LEFT)
        self.jog_speed_var = tk.IntVar(value=self.jog_speed)
        speed_spin = ttk.Spinbox(speed_frame, from_=1, to=100, textvariable=self.jog_speed_var, width=5, command=self._update_jog_speed)
        speed_spin.pack(side=tk.LEFT, padx=5)
        self.jog_speed_var.trace_add('write', lambda *a: self._update_jog_speed())
        # Home controls
        home_frame = ttk.LabelFrame(self.right_toolbar, text="Home")
        home_frame.pack(fill=tk.X, padx=10, pady=8)
        ttk.Button(home_frame, text="Home X", command=lambda: self._home('X')).pack(fill=tk.X, pady=2)
        ttk.Button(home_frame, text="Home Y", command=lambda: self._home('Y')).pack(fill=tk.X, pady=2)
        ttk.Button(home_frame, text="Home Z", command=lambda: self._home('Z')).pack(fill=tk.X, pady=2)
        ttk.Button(home_frame, text="Home ROT", command=lambda: self._home('ROT')).pack(fill=tk.X, pady=2)
        # E-stop
        ttk.Separator(self.right_toolbar, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Button(self.right_toolbar, text="EMERGENCY STOP", command=self._estop, style="Danger.TButton").pack(fill=tk.X, padx=10, pady=10)
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
        self.motor_ctrl.home(axis)
        self._draw_canvas()
        self._update_position_display()

    def _estop(self):
        self.motor_ctrl.estop()
        messagebox.showwarning("EMERGENCY STOP", "All motors stopped (simulated)")

    def _update_position_display(self):
        pos = self.motor_ctrl.get_position()
        text = f"X: {pos['X']:.1f} mm\nY: {pos['Y']:.1f} mm\nZ: {pos['Z']:.1f} mm\nROT: {pos['ROT']:.1f}°"
        self.coord_label.config(text=text)
        self.root.after(200, self._update_position_display)

    def _update_jog_speed(self):
        try:
            self.jog_speed = int(self.jog_speed_var.get())
        except Exception:
            self.jog_speed = 10

    def _on_close(self):
        if messagebox.askokcancel("Quit", "Do you want to quit the Fabric CNC app?"):
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

if __name__ == "__main__":
    main() 