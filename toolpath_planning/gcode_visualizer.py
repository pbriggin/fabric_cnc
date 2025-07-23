#!/usr/bin/env python3
"""
2D GCODE Visualizer for Fabric CNC

Parses GCODE files and displays:
- Tool path (X, Y movements)
- Tool orientation (A-axis rotation)
- Z-height changes (color coding)
- Corner handling (special markers)
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import re
import argparse
from typing import List, Tuple, Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GCodeVisualizer:
    """
    Visualizes GCODE files in 2D with tool orientation and Z-height information.
    """
    
    def __init__(self):
        self.x_positions = []
        self.y_positions = []
        self.z_positions = []
        self.a_positions = []
        self.feed_rates = []
        self.commands = []
        self.corner_points = []
        self.z_changes = []
        
        # Current position
        self.current_x = 0.0
        self.current_y = 0.0
        self.current_z = 0.0
        self.current_a = 0.0
        
        # Movement state
        self.is_moving = False
        self.last_z = 0.0
        self.pending_corner = False
        
    def parse_gcode_file(self, filename: str):
        """Parse a GCODE file and extract movement data."""
        logger.info(f"Parsing GCODE file: {filename}")
        
        with open(filename, 'r') as f:
            lines = f.readlines()
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith(';'):
                continue
                
            self._parse_gcode_line(line, line_num)
    
    def _parse_gcode_line(self, line: str, line_num: int):
        """Parse a single GCODE line."""
        # Extract coordinates using regex
        x_match = re.search(r'X([-\d.]+)', line)
        y_match = re.search(r'Y([-\d.]+)', line)
        z_match = re.search(r'Z([-\d.]+)', line)
        a_match = re.search(r'A([-\d.]+)', line)
        f_match = re.search(r'F([-\d.]+)', line)
        
        # Update current position if coordinates found
        if x_match:
            self.current_x = float(x_match.group(1))
        if y_match:
            self.current_y = float(y_match.group(1))
        if z_match:
            self.current_z = float(z_match.group(1))
        if a_match:
            self.current_a = float(a_match.group(1))
        
        # Check if this is a movement command
        if line.startswith('G0') or line.startswith('G1'):
            self._record_movement(line, f_match.group(1) if f_match else None)
        
        # Check for corner handling
        if 'Raise Z for corner' in line:
            # Store the corner position to be added after the next movement
            self.pending_corner = True
        
        # Check for Z changes
        if z_match and abs(self.current_z - self.last_z) > 0.1:
            self.z_changes.append((self.current_x, self.current_y, self.current_z, line_num))
            self.last_z = self.current_z
    
    def _record_movement(self, line: str, feed_rate: Optional[str]):
        """Record a movement command."""
        self.x_positions.append(self.current_x)
        self.y_positions.append(self.current_y)
        self.z_positions.append(self.current_z)
        self.a_positions.append(self.current_a)
        self.feed_rates.append(float(feed_rate) if feed_rate else 0.0)
        self.commands.append(line)
        self.is_moving = True
        
        # If we have a pending corner, add it at the current position
        if self.pending_corner:
            self.corner_points.append((self.current_x, self.current_y, len(self.commands)))
            self.pending_corner = False
    
    def create_visualization(self, output_filename: Optional[str] = None):
        """Create the 2D visualization."""
        if not self.x_positions:
            logger.warning("No movement data found to visualize")
            return
        
        # Create single plot for tool orientation only
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        
        # Convert to numpy arrays
        x_array = np.array(self.x_positions)
        y_array = np.array(self.y_positions)
        z_array = np.array(self.z_positions)
        a_array = np.array(self.a_positions)
        
        # Plot tool orientation
        self._plot_tool_orientation(ax, x_array, y_array, a_array)
        
        # Add corner markers
        if self.corner_points:
            corner_x = [p[0] for p in self.corner_points]
            corner_y = [p[1] for p in self.corner_points]
            ax.scatter(corner_x, corner_y, c='red', s=100, marker='*', 
                       label=f'Corners ({len(self.corner_points)})', zorder=5)
        
        # Z-change markers removed - only showing corners
        
        # Add legend
        ax.legend()
        
        # Set title and labels
        ax.set_title('Tool Orientation (A-Axis)')
        ax.set_xlabel('X (inches)')
        ax.set_ylabel('Y (inches)')
        ax.grid(True, alpha=0.3)
        
        # Make axes equal
        ax.set_aspect('equal')
        
        plt.tight_layout()
        
        # Save or show
        if output_filename:
            plt.savefig(output_filename, dpi=300, bbox_inches='tight')
            logger.info(f"Visualization saved to: {output_filename}")
        else:
            plt.show()
    
    def _plot_tool_path(self, ax, x_array, y_array, z_array):
        """Plot tool path with Z-height color coding."""
        # Create color map based on Z height
        z_min, z_max = z_array.min(), z_array.max()
        z_normalized = (z_array - z_min) / (z_max - z_min) if z_max > z_min else np.zeros_like(z_array)
        
        # Create color map (blue for low Z, red for high Z)
        colors = plt.cm.coolwarm(z_normalized)
        
        # Plot the path with color coding
        for i in range(len(x_array) - 1):
            ax.plot([x_array[i], x_array[i+1]], [y_array[i], y_array[i+1]], 
                   color=colors[i], linewidth=2, alpha=0.8)
        
        # Add start and end markers
        ax.scatter(x_array[0], y_array[0], c='green', s=100, marker='o', 
                  label='Start', zorder=5)
        ax.scatter(x_array[-1], y_array[-1], c='red', s=100, marker='s', 
                  label='End', zorder=5)
        
        # Add colorbar
        sm = plt.cm.ScalarMappable(cmap=plt.cm.coolwarm, 
                                  norm=plt.Normalize(vmin=z_min, vmax=z_max))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax)
        cbar.set_label('Z Height (inches)')
    
    def _plot_tool_orientation(self, ax, x_array, y_array, a_array):
        """Plot tool orientation with direction arrows."""
        # Plot the path
        ax.plot(x_array, y_array, 'b-', linewidth=1, alpha=0.5, label='Tool Path')
        
        # Add orientation arrows at regular intervals
        step = max(1, len(x_array) // 20)  # Show ~20 arrows
        for i in range(0, len(x_array), step):
            if i < len(x_array) - 1:
                # Calculate direction vector
                dx = x_array[i+1] - x_array[i]
                dy = y_array[i+1] - y_array[i]
                
                # Normalize
                length = np.sqrt(dx**2 + dy**2)
                if length > 0:
                    dx /= length
                    dy /= length
                    
                    # Scale arrow
                    arrow_length = min(5.0, length * 0.5)
                    
                    # Draw arrow
                    ax.arrow(x_array[i], y_array[i], 
                            dx * arrow_length, dy * arrow_length,
                            head_width=1.0, head_length=1.0, 
                            fc='blue', ec='blue', alpha=0.7)
        
        # Add start and end markers
        ax.scatter(x_array[0], y_array[0], c='green', s=100, marker='o', 
                  label='Start', zorder=5)
        ax.scatter(x_array[-1], y_array[-1], c='red', s=100, marker='s', 
                  label='End', zorder=5)
    
    def get_statistics(self):
        """Get statistics about the GCODE file as a dictionary."""
        if not self.x_positions:
            return {
                'total_movements': 0,
                'corners': 0,
                'z_changes': 0,
                'x_range': (0, 0),
                'y_range': (0, 0),
                'z_range': (0, 0),
                'total_path_length': 0
            }
        
        x_array = np.array(self.x_positions)
        y_array = np.array(self.y_positions)
        z_array = np.array(self.z_positions)
        
        # Calculate total path length
        total_length = 0
        for i in range(len(x_array) - 1):
            dx = x_array[i+1] - x_array[i]
            dy = y_array[i+1] - y_array[i]
            total_length += np.sqrt(dx**2 + dy**2)
        
        return {
            'total_movements': len(self.x_positions),
            'corners': len(self.corner_points),
            'z_changes': len(self.z_changes),
            'x_range': (float(x_array.min()), float(x_array.max())),
            'y_range': (float(y_array.min()), float(y_array.max())),
            'z_range': (float(z_array.min()), float(z_array.max())),
            'total_path_length': float(total_length)
        }
    
    def print_statistics(self):
        """Print statistics about the GCODE file."""
        if not self.x_positions:
            print("No data to analyze")
            return
        
        stats = self.get_statistics()
        
        print("\n=== GCODE Analysis ===")
        print(f"Total movements: {stats['total_movements']}")
        print(f"Corners detected: {stats['corners']}")
        print(f"Z-height changes: {stats['z_changes']}")
        
        print(f"\nX range: {stats['x_range'][0]:.2f} to {stats['x_range'][1]:.2f} inches")
        print(f"Y range: {stats['y_range'][0]:.2f} to {stats['y_range'][1]:.2f} inches")
        print(f"Z range: {stats['z_range'][0]:.2f} to {stats['z_range'][1]:.2f} inches")
        print(f"Total path length: {stats['total_path_length']:.2f} inches")


def main():
    """Main function to run the GCODE visualizer."""
    parser = argparse.ArgumentParser(description='2D GCODE Visualizer for Fabric CNC')
    parser.add_argument('gcode_file', help='Path to the GCODE file')
    parser.add_argument('-o', '--output', help='Output image filename')
    parser.add_argument('--no-display', action='store_true', help='Don\'t display the plot')
    
    args = parser.parse_args()
    
    # Create visualizer
    visualizer = GCodeVisualizer()
    
    try:
        # Parse GCODE file
        visualizer.parse_gcode_file(args.gcode_file)
        
        # Print statistics
        visualizer.print_statistics()
        
        # Create visualization
        if args.output or not args.no_display:
            visualizer.create_visualization(args.output)
        
    except FileNotFoundError:
        print(f"Error: File '{args.gcode_file}' not found")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 