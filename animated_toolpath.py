#!/usr/bin/env python3
"""
Animated Toolpath Visualizer

Shows 2D XY layout with shapes and animates GCODE execution.
"""

import re
import math
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
from dxf_processor import DXFProcessor

class AnimatedToolpathVisualizer:
    def __init__(self, dxf_file, gcode_file):
        self.dxf_file = dxf_file
        self.gcode_file = gcode_file
        self.shapes = {}
        self.toolpath_points = []
        self.z_colors = []
        self.corner_indices = []
        
    def load_shapes(self):
        """Load shapes from DXF file."""
        processor = DXFProcessor()
        self.shapes = processor.process_dxf(self.dxf_file)
        print(f"Loaded {len(self.shapes)} shapes from DXF")
        
    def load_gcode(self):
        """Load and parse GCODE file."""
        current_pos = {'X': 0, 'Y': 0, 'Z': 0, 'A': 0}
        previous_z = 0
        
        with open(self.gcode_file, 'r') as f:
            for line in f:
                # Remove comments
                line = re.sub(r';.*$', '', line).strip()
                if not line:
                    continue
                
                # Parse coordinates
                for axis in ['X', 'Y', 'Z', 'A']:
                    match = re.search(f'{axis}([+-]?\\d*\\.?\\d+)', line)
                    if match:
                        current_pos[axis] = float(match.group(1))
                
                # Only record points with X or Y movement
                if 'X' in line or 'Y' in line:
                    self.toolpath_points.append(current_pos.copy())
                    
                    # Check for Z changes (corners)
                    if abs(current_pos['Z'] - previous_z) > 0.1:  # Z changed significantly
                        self.corner_indices.append(len(self.toolpath_points) - 1)
                    
                    previous_z = current_pos['Z']
                    
                    # Determine color based on Z height
                    if current_pos['Z'] < -1.0:
                        self.z_colors.append('red')      # Cutting
                    elif current_pos['Z'] > 1.0:
                        self.z_colors.append('green')    # Safe height
                    else:
                        self.z_colors.append('orange')   # Transition
        
        print(f"Loaded {len(self.toolpath_points)} toolpath points")
        print(f"Found {len(self.corner_indices)} corners (Z changes)")
        
    def create_animation(self):
        """Create animated visualization."""
        if not self.shapes or not self.toolpath_points:
            print("Error: No shapes or toolpath data available")
            return
            
        # Set up the figure
        fig, ax = plt.subplots(1, 1, figsize=(12, 10))
        ax.set_aspect('equal')
        ax.set_xlabel('X (mm)')
        ax.set_ylabel('Y (mm)')
        ax.set_title('2D Toolpath Animation with Z-Axis Orientation\nRed=Cutting, Green=Safe Height, Orange=Transition')
        ax.grid(True, alpha=0.3)
        
        # Plot all shapes in background
        for shape_name, points in self.shapes.items():
            if len(points) > 1:
                x_coords = [p[0] for p in points]
                y_coords = [p[1] for p in points]
                ax.plot(x_coords, y_coords, 'k-', linewidth=0.5, alpha=0.3)
        
        # Extract toolpath data
        x_coords = [p['X'] for p in self.toolpath_points]
        y_coords = [p['Y'] for p in self.toolpath_points]
        a_coords = [p['A'] for p in self.toolpath_points]
        z_coords = [p['Z'] for p in self.toolpath_points]
        
        # Set plot limits
        ax.set_xlim(min(x_coords) - 5, max(x_coords) + 5)
        ax.set_ylim(min(y_coords) - 5, max(y_coords) + 5)
        
        # Create lines for animation
        toolpath_line, = ax.plot([], [], 'b-', linewidth=2, alpha=0.7)
        current_point, = ax.plot([], [], 'ro', markersize=10)
        
        # Create Z-axis orientation line (shows blade direction)
        z_axis_line, = ax.plot([], [], 'r-', linewidth=3, alpha=0.8)
        
        # Add legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='red', label='Cutting (Z < -1mm)'),
            Patch(facecolor='green', label='Safe Height (Z > 1mm)'),
            Patch(facecolor='orange', label='Transition'),
            Patch(facecolor='red', label='Z-Axis Orientation (Blade Direction)')
        ]
        ax.legend(handles=legend_elements, loc='upper right')
        
        # Create frames with pauses at corners
        frames = []
        current_frame = 0
        
        for i in range(len(self.toolpath_points)):
            frames.append(i)
            
            # If this is a corner, add extra frames for pause
            if i in self.corner_indices:
                # Add 5 extra frames for pause at corners
                for _ in range(5):
                    frames.append(i)
        
        def animate(frame_idx):
            # Get the actual toolpath index
            actual_idx = frames[frame_idx] if frame_idx < len(frames) else len(self.toolpath_points) - 1
            
            # Update toolpath line
            toolpath_line.set_data(x_coords[:actual_idx+1], y_coords[:actual_idx+1])
            
            # Update current point
            if actual_idx < len(x_coords):
                current_point.set_data([x_coords[actual_idx]], [y_coords[actual_idx]])
                current_point.set_color(self.z_colors[actual_idx])
                
                # Update Z-axis orientation line
                # Draw a line showing the blade direction (perpendicular to movement direction)
                if actual_idx > 0:
                    # Calculate movement direction
                    dx = x_coords[actual_idx] - x_coords[actual_idx-1]
                    dy = y_coords[actual_idx] - y_coords[actual_idx-1]
                    length = math.sqrt(dx*dx + dy*dy)
                    
                    if length > 0:
                        # Normalize movement vector
                        dx_norm = dx / length
                        dy_norm = dy / length
                        
                        # Blade direction is perpendicular to movement (90 degrees)
                        blade_length = 3.0  # Length of orientation line
                        blade_dx = -dy_norm * blade_length
                        blade_dy = dx_norm * blade_length
                        
                        # Draw blade orientation line
                        z_axis_line.set_data([x_coords[actual_idx] - blade_dx, x_coords[actual_idx] + blade_dx],
                                           [y_coords[actual_idx] - blade_dy, y_coords[actual_idx] + blade_dy])
                    else:
                        # No movement, hide orientation line
                        z_axis_line.set_data([], [])
                else:
                    # First point, hide orientation line
                    z_axis_line.set_data([], [])
            
            return toolpath_line, current_point, z_axis_line
        
        # Create animation with variable timing
        def get_interval(frame_idx):
            """Return interval based on whether we're at a corner."""
            if frame_idx < len(frames):
                actual_idx = frames[frame_idx]
                if actual_idx in self.corner_indices:
                    return 500  # Pause longer at corners (500ms)
                else:
                    return 50   # Normal speed (50ms)
            return 50
        
        # Create animation with custom interval function
        anim = animation.FuncAnimation(fig, animate, frames=len(frames), 
                                     interval=50, blit=False, repeat=True)
        
        plt.tight_layout()
        
        # Save animation as GIF (since MP4 requires ffmpeg)
        try:
            output_file = f'animated_toolpath_{self.gcode_file.replace(".gcode", "")}.gif'
            anim.save(output_file, writer='pillow', fps=10)
            print(f"Animation saved as {output_file}")
        except Exception as e:
            print(f"Could not save animation: {e}")
            print("Showing animation in window instead...")
        
        plt.show()
        
    def print_summary(self):
        """Print summary statistics."""
        if not self.toolpath_points:
            return
            
        z_coords = [p['Z'] for p in self.toolpath_points]
        cutting = sum(1 for z in z_coords if z < -1.0)
        safe = sum(1 for z in z_coords if z > 1.0)
        transition = sum(1 for z in z_coords if -1.0 <= z <= 1.0)
        
        print("\n" + "="*50)
        print("ANIMATED TOOLPATH SUMMARY")
        print("="*50)
        print(f"DXF file: {self.dxf_file}")
        print(f"GCODE file: {self.gcode_file}")
        print(f"Shapes loaded: {len(self.shapes)}")
        print(f"Toolpath points: {len(self.toolpath_points)}")
        print(f"Corners detected: {len(self.corner_indices)}")
        print(f"Cutting points: {cutting}")
        print(f"Safe height points: {safe}")
        print(f"Transition points: {transition}")
        print(f"Z rotation range: {min([p['A'] for p in self.toolpath_points]):.1f}° to {max([p['A'] for p in self.toolpath_points]):.1f}°")
        print(f"Z height range: {min(z_coords):.1f} to {max(z_coords):.1f} mm")
        print("="*50)

def main():
    """Main function."""
    dxf_file = "/Users/peterbriggs/Downloads/test_2.dxf"
    gcode_file = "toolpath_test_2.gcode"
    
    visualizer = AnimatedToolpathVisualizer(dxf_file, gcode_file)
    
    print("Loading DXF shapes...")
    visualizer.load_shapes()
    
    print("Loading GCODE...")
    visualizer.load_gcode()
    
    visualizer.print_summary()
    
    print("Creating animation...")
    visualizer.create_animation()

if __name__ == "__main__":
    main() 