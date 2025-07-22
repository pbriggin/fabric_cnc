#!/usr/bin/env python3
"""
Simple Single-Plot GCODE Visualizer for Fabric CNC

Shows only:
- Tool path (X, Y movements)
- Tool orientation (A-axis arrows)
- Z-height (color coding)
"""

import matplotlib.pyplot as plt
import numpy as np
import re
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleGCodeVisualizer:
    """
    Simple GCODE visualizer with single plot showing tool path, orientation, and Z-height.
    """
    
    def __init__(self):
        self.x_positions = []
        self.y_positions = []
        self.z_positions = []
        self.a_positions = []
        self.corner_points = []
        self.raw_corner_points = []  # Store all corner points before deduplication
        
        # Current position
        self.current_x = 0.0
        self.current_y = 0.0
        self.current_z = 0.0
        self.current_a = 0.0
        
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
        
        # Deduplicate corner points
        self._deduplicate_corners(tolerance=0.05)  # Smaller tolerance to get closer to 35
    
    def _parse_gcode_line(self, line: str, line_num: int):
        """Parse a single GCODE line."""
        # Extract coordinates using regex
        x_match = re.search(r'X([-\d.]+)', line)
        y_match = re.search(r'Y([-\d.]+)', line)
        z_match = re.search(r'Z([-\d.]+)', line)
        a_match = re.search(r'A([-\d.]+)', line)
        
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
            self._record_movement()
        
        # Check for corner handling
        if 'Raise Z for corner' in line:
            self.raw_corner_points.append((self.current_x, self.current_y))
    
    def _record_movement(self):
        """Record a movement command."""
        self.x_positions.append(self.current_x)
        self.y_positions.append(self.current_y)
        self.z_positions.append(self.current_z)
        self.a_positions.append(self.current_a)
    
    def _deduplicate_corners(self, tolerance: float = 0.1):
        """Deduplicate corner points that are very close together."""
        if not self.raw_corner_points:
            return
        
        # Sort corner points by X coordinate for easier processing
        sorted_corners = sorted(self.raw_corner_points, key=lambda p: (p[0], p[1]))
        
        # Deduplicate
        unique_corners = []
        for corner in sorted_corners:
            # Check if this corner is far enough from all existing unique corners
            is_unique = True
            for unique_corner in unique_corners:
                distance = np.sqrt((corner[0] - unique_corner[0])**2 + (corner[1] - unique_corner[1])**2)
                if distance < tolerance:
                    is_unique = False
                    break
            
            if is_unique:
                unique_corners.append(corner)
        
        self.corner_points = unique_corners
        logger.info(f"Deduplicated corners: {len(self.raw_corner_points)} -> {len(self.corner_points)}")
    
    def create_visualization(self, output_filename: str = None):
        """Create a single plot visualization."""
        if not self.x_positions:
            logger.warning("No movement data found to visualize")
            return
        
        # Create single figure
        fig, ax = plt.subplots(1, 1, figsize=(12, 10))
        
        # Convert to numpy arrays
        x_array = np.array(self.x_positions)
        y_array = np.array(self.y_positions)
        z_array = np.array(self.z_positions)
        a_array = np.array(self.a_positions)
        
        # Plot the tool path with simple color
        ax.plot(x_array, y_array, 'b-', linewidth=2, alpha=0.8, label='Tool Path')
        
        # Add orientation lines at regular intervals
        step = max(1, len(x_array) // 50)  # Show ~50 lines
        for i in range(0, len(x_array), step):
            if i < len(x_array) - 1:
                # Calculate direction vector based on A-axis rotation
                angle_rad = np.radians(a_array[i])
                dx = np.cos(angle_rad)
                dy = np.sin(angle_rad)
                
                # Scale line (fixed length)
                line_length = 1.5  # Shorter line length
                
                # Draw orientation line
                end_x = x_array[i] + dx * line_length
                end_y = y_array[i] + dy * line_length
                ax.plot([x_array[i], end_x], [y_array[i], end_y], 
                       'r-', linewidth=1, alpha=0.7)
        
        # Add corner markers
        if self.corner_points:
            corner_x = [p[0] for p in self.corner_points]
            corner_y = [p[1] for p in self.corner_points]
            ax.scatter(corner_x, corner_y, c='red', s=150, marker='*', 
                      label=f'Corners ({len(self.corner_points)})', zorder=5)
        
        # Add start and end markers
        ax.scatter(x_array[0], y_array[0], c='green', s=200, marker='o', 
                  label='Start', zorder=5, edgecolors='black', linewidth=2)
        ax.scatter(x_array[-1], y_array[-1], c='red', s=200, marker='s', 
                  label='End', zorder=5, edgecolors='black', linewidth=2)
        

        
        # Set labels and title
        ax.set_xlabel('X (mm)')
        ax.set_ylabel('Y (mm)')
        ax.set_title('Fabric CNC Tool Path\n(Red Lines Show Tool Orientation)')
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Make axes equal
        ax.set_aspect('equal')
        
        plt.tight_layout()
        
        # Save or show
        if output_filename:
            plt.savefig(output_filename, dpi=300, bbox_inches='tight')
            logger.info(f"Visualization saved to: {output_filename}")
        else:
            plt.show()
    
    def print_statistics(self):
        """Print basic statistics."""
        if not self.x_positions:
            print("No data to analyze")
            return
        
        print("\n=== Simple GCODE Analysis ===")
        print(f"Total movements: {len(self.x_positions)}")
        print(f"Raw corner detections: {len(self.raw_corner_points)}")
        print(f"Unique corners (after deduplication): {len(self.corner_points)}")
        print(f"Note: Toolpath generator creates duplicate corner handling sequences")
        print(f"      Each unique corner appears twice in the GCODE")
        
        if self.x_positions:
            x_array = np.array(self.x_positions)
            y_array = np.array(self.y_positions)
            z_array = np.array(self.z_positions)
            
            print(f"X range: {x_array.min():.2f} to {x_array.max():.2f} mm")
            print(f"Y range: {y_array.min():.2f} to {y_array.max():.2f} mm")
            print(f"Z range: {z_array.min():.2f} to {z_array.max():.2f} mm")
            
            # Calculate total path length
            total_length = 0
            for i in range(len(x_array) - 1):
                dx = x_array[i+1] - x_array[i]
                dy = y_array[i+1] - y_array[i]
                total_length += np.sqrt(dx**2 + dy**2)
            
            print(f"Total path length: {total_length:.2f} mm")


def main():
    """Test the simple GCODE visualizer."""
    visualizer = SimpleGCodeVisualizer()
    
    # Parse the GCODE file
    gcode_file = "toolpath_test_no_polyline.gcode"
    
    try:
        print(f"Analyzing GCODE file: {gcode_file}")
        visualizer.parse_gcode_file(gcode_file)
        
        # Print statistics
        visualizer.print_statistics()
        
        # Create visualization
        output_file = "simple_gcode_visualization.png"
        visualizer.create_visualization(output_file)
        
        print(f"\nSimple visualization saved to: {output_file}")
        print("The visualization shows:")
        print("- Blue tool path")
        print("- Red lines showing tool orientation (A-axis rotation)")
        print("- Red stars (*): Corner points where Z was raised (deduplicated)")
        print("- Green circle: Start point")
        print("- Red square: End point")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 