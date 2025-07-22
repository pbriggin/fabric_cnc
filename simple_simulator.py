#!/usr/bin/env python3
"""
Simple GCODE Simulator for Fabric CNC

Shows one animated plot with:
- Z rotation angle as line
- Color coding for Z height (cutting vs safe height)
- Real-time animation of toolpath execution
"""

import re
import math
import logging
from typing import List, Dict
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleGCodeSimulator:
    """
    Simple GCODE simulator with animated visualization.
    """
    
    def __init__(self, gcode_file: str):
        """
        Initialize the simulator.
        
        Args:
            gcode_file: Path to the GCODE file to simulate
        """
        self.gcode_file = gcode_file
        self.gcode_lines = []
        self.current_position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'A': 0.0}
        self.toolpath_points = []
        self.z_colors = []  # Color coding for Z height
        
    def load_gcode(self) -> bool:
        """Load and parse GCODE file."""
        try:
            with open(self.gcode_file, 'r') as f:
                self.gcode_lines = f.readlines()
            logger.info(f"Loaded {len(self.gcode_lines)} GCODE lines")
            return True
        except Exception as e:
            logger.error(f"Error loading GCODE file: {e}")
            return False
    
    def parse_gcode_line(self, line: str) -> Dict:
        """Parse a single GCODE line."""
        # Remove comments and whitespace
        line = re.sub(r';.*$', '', line).strip()
        if not line:
            return {}
        
        commands = {}
        
        # G0/G1 (rapid/linear move)
        g_match = re.search(r'G([01])', line)
        if g_match:
            commands['G'] = int(g_match.group(1))
        
        # X, Y, Z, A coordinates
        for axis in ['X', 'Y', 'Z', 'A']:
            match = re.search(f'{axis}([+-]?\\d*\\.?\\d+)', line)
            if match:
                commands[axis] = float(match.group(1))
        
        return commands
    
    def simulate_execution(self) -> bool:
        """Simulate GCODE execution and record toolpath."""
        logger.info("Starting GCODE simulation...")
        
        # Initialize toolpath
        self.toolpath_points = [self.current_position.copy()]
        self.z_colors = ['blue']  # Start color
        
        for line in self.gcode_lines:
            commands = self.parse_gcode_line(line)
            
            if not commands:
                continue
            
            # Handle movement commands
            if 'G' in commands:
                # Calculate new position
                new_position = self.current_position.copy()
                for axis in ['X', 'Y', 'Z', 'A']:
                    if axis in commands:
                        new_position[axis] = commands[axis]
                
                # Update current position
                self.current_position = new_position
                
                # Record toolpath point
                self.toolpath_points.append(self.current_position.copy())
                
                # Determine color based on Z height
                if self.current_position['Z'] < -1.0:  # Cutting
                    self.z_colors.append('red')
                elif self.current_position['Z'] > 1.0:  # Safe height
                    self.z_colors.append('green')
                else:  # Transition
                    self.z_colors.append('orange')
        
        logger.info(f"Simulation complete: {len(self.toolpath_points)} toolpath points")
        return True
    
    def create_animation(self):
        """Create animated visualization."""
        if not self.toolpath_points:
            logger.error("No toolpath data available. Run simulation first.")
            return
        
        # Extract data
        a_coords = [p['A'] for p in self.toolpath_points]
        z_coords = [p['Z'] for p in self.toolpath_points]
        timestamps = list(range(len(self.toolpath_points)))
        
        # Create figure with interactive backend
        plt.ion()  # Turn on interactive mode
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Set up the plot
        ax.set_xlim(0, len(self.toolpath_points))
        ax.set_ylim(-180, 180)
        ax.set_xlabel('Toolpath Point')
        ax.set_ylabel('Z Rotation Angle (degrees)')
        ax.set_title('GCODE Simulation: Z Rotation vs Toolpath Position\n'
                    'Colors: Red=Cutting, Green=Safe Height, Orange=Transition')
        ax.grid(True, alpha=0.3)
        
        # Plot the complete line first
        ax.plot(timestamps, a_coords, 'b-', linewidth=1, alpha=0.5, label='Z Rotation')
        
        # Create scatter plot with colors
        scatter = ax.scatter(timestamps, a_coords, c=self.z_colors, s=20, alpha=0.7)
        
        # Add legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='red', label='Cutting (Z < -1mm)'),
            Patch(facecolor='green', label='Safe Height (Z > 1mm)'),
            Patch(facecolor='orange', label='Transition')
        ]
        ax.legend(handles=legend_elements)
        
        # Save static plot
        plt.savefig(f'simple_simulation_{self.gcode_file.replace(".gcode", "")}.png', dpi=300, bbox_inches='tight')
        logger.info(f"Static plot saved as simple_simulation_{self.gcode_file.replace('.gcode', '')}.png")
        
        # Show the plot
        plt.show(block=True)
        
        # Now create a simple animation
        self._create_simple_animation(timestamps, a_coords, z_coords)
    
    def _create_simple_animation(self, timestamps, a_coords, z_coords):
        """Create a simple animation that should work."""
        try:
            # Create new figure for animation
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
            
            # Set up plots
            ax1.set_xlim(0, len(timestamps))
            ax1.set_ylim(-180, 180)
            ax1.set_ylabel('Z Rotation (degrees)')
            ax1.set_title('Z Rotation Animation')
            ax1.grid(True, alpha=0.3)
            
            ax2.set_xlim(0, len(timestamps))
            ax2.set_ylim(-3, 6)
            ax2.set_xlabel('Toolpath Point')
            ax2.set_ylabel('Z Height (mm)')
            ax2.set_title('Z Height Animation')
            ax2.grid(True, alpha=0.3)
            
            # Create lines
            line1, = ax1.plot([], [], 'b-', linewidth=2)
            line2, = ax2.plot([], [], 'g-', linewidth=2)
            
            # Create moving points
            point1, = ax1.plot([], [], 'ro', markersize=8)
            point2, = ax2.plot([], [], 'ro', markersize=8)
            
            def animate(frame):
                # Update rotation plot
                line1.set_data(timestamps[:frame+1], a_coords[:frame+1])
                if frame < len(timestamps):
                    point1.set_data([timestamps[frame]], [a_coords[frame]])
                
                # Update height plot
                line2.set_data(timestamps[:frame+1], z_coords[:frame+1])
                if frame < len(timestamps):
                    point2.set_data([timestamps[frame]], [z_coords[frame]])
                
                return line1, line2, point1, point2
            
            # Create animation with fewer frames for better performance
            step = max(1, len(timestamps) // 500)  # Limit to 500 frames
            frames = list(range(0, len(timestamps), step))
            
            anim = animation.FuncAnimation(fig, animate, frames=frames, 
                                         interval=100, blit=False, repeat=True)
            
            logger.info("Animation created successfully!")
            plt.show()
            
        except Exception as e:
            logger.error(f"Animation failed: {e}")
            logger.info("Showing static plot instead...")
    
    def print_summary(self):
        """Print simulation summary."""
        if not self.toolpath_points:
            logger.error("No toolpath data available. Run simulation first.")
            return
        
        print("\n" + "="*50)
        print("SIMPLE GCODE SIMULATION SUMMARY")
        print("="*50)
        
        # Count colors
        red_count = self.z_colors.count('red')
        green_count = self.z_colors.count('green')
        orange_count = self.z_colors.count('orange')
        
        print(f"GCODE file: {self.gcode_file}")
        print(f"Total toolpath points: {len(self.toolpath_points)}")
        print(f"Cutting points (red): {red_count}")
        print(f"Safe height points (green): {green_count}")
        print(f"Transition points (orange): {orange_count}")
        
        # Z rotation range
        a_coords = [p['A'] for p in self.toolpath_points]
        print(f"Z rotation range: {min(a_coords):.1f}° to {max(a_coords):.1f}°")
        
        # Z height range
        z_coords = [p['Z'] for p in self.toolpath_points]
        print(f"Z height range: {min(z_coords):.1f} to {max(z_coords):.1f} mm")
        
        print("="*50)


def main():
    """Main function to run the simple simulator."""
    # GCODE file to simulate
    gcode_file = "toolpath_test_2.gcode"
    
    # Create simulator
    simulator = SimpleGCodeSimulator(gcode_file)
    
    # Load GCODE
    if not simulator.load_gcode():
        print("Failed to load GCODE file")
        return
    
    # Run simulation
    if not simulator.simulate_execution():
        print("Failed to simulate GCODE execution")
        return
    
    # Print summary
    simulator.print_summary()
    
    # Create animation
    print("\nCreating animation...")
    simulator.create_animation()


if __name__ == "__main__":
    main() 