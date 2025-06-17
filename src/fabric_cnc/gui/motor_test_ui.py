#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI for testing the Fabric CNC machine motors.
"""

import tkinter as tk
from tkinter import ttk
import logging
from fabric_cnc.motor_control.motor_controller import MotorController
from fabric_cnc.config import GUI_CONFIG

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MotorTestUI:
    """GUI for testing the Fabric CNC machine motors."""
    
    def __init__(self, root):
        """Initialize the GUI."""
        self.root = root
        self.root.title("Fabric CNC Motor Test")
        self.root.geometry(f"{GUI_CONFIG['WINDOW_SIZE'][0]}x{GUI_CONFIG['WINDOW_SIZE'][1]}")
        
        # Initialize motor controller
        self.controller = MotorController()
        
        # Create GUI elements
        self._create_widgets()
        
        # Start update loop
        self._update_loop()
        
        logger.info("GUI initialized")

    def _create_widgets(self):
        """Create GUI widgets."""
        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # X axis controls
        x_frame = ttk.LabelFrame(main_frame, text="X Axis", padding="5")
        x_frame.grid(row=0, column=0, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Button(x_frame, text="Home X", command=self._home_x, style='Homing.TButton').grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(x_frame, text="←", command=lambda: self._move_x(-GUI_CONFIG['MOVE_INCREMENT'])).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(x_frame, text="→", command=lambda: self._move_x(GUI_CONFIG['MOVE_INCREMENT'])).grid(row=0, column=2, padx=5, pady=5)
        
        # Y axis controls
        y_frame = ttk.LabelFrame(main_frame, text="Y Axis", padding="5")
        y_frame.grid(row=1, column=0, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Button(y_frame, text="Home Y", command=self._home_y, style='Homing.TButton').grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(y_frame, text="↑", command=lambda: self._move_y(GUI_CONFIG['MOVE_INCREMENT'])).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(y_frame, text="↓", command=lambda: self._move_y(-GUI_CONFIG['MOVE_INCREMENT'])).grid(row=0, column=2, padx=5, pady=5)
        
        # Status display
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(main_frame, textvariable=self.status_var)
        status_label.grid(row=2, column=0, padx=5, pady=5)
        
        # Configure styles
        style = ttk.Style()
        style.configure('Homing.TButton', background=GUI_CONFIG['HOMING_BUTTON_COLOR'])

    def _move_x(self, distance_mm):
        """Move X axis."""
        try:
            self.status_var.set(f"Moving X: {distance_mm}mm")
            self.controller.move_distance(distance_mm, 'X')
            self.status_var.set("Ready")
        except Exception as e:
            logger.error(f"Error moving X: {e}")
            self.status_var.set(f"Error: {e}")

    def _move_y(self, distance_mm):
        """Move Y axis."""
        try:
            self.status_var.set(f"Moving Y: {distance_mm}mm")
            self.controller.move_distance(distance_mm, 'Y')
            self.status_var.set("Ready")
        except Exception as e:
            logger.error(f"Error moving Y: {e}")
            self.status_var.set(f"Error: {e}")

    def _home_x(self):
        """Home X axis."""
        try:
            self.status_var.set("Homing X axis...")
            self.controller.home_axis('X')
            self.status_var.set("Ready")
        except Exception as e:
            logger.error(f"Error homing X: {e}")
            self.status_var.set(f"Error: {e}")

    def _home_y(self):
        """Home Y axis."""
        try:
            self.status_var.set("Homing Y axis...")
            self.controller.home_axis('Y')
            self.status_var.set("Ready")
        except Exception as e:
            logger.error(f"Error homing Y: {e}")
            self.status_var.set(f"Error: {e}")

    def _update_loop(self):
        """Update loop for the GUI."""
        # Add any periodic updates here
        self.root.after(GUI_CONFIG['UPDATE_RATE'], self._update_loop)

def main():
    """Main entry point."""
    root = tk.Tk()
    app = MotorTestUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 