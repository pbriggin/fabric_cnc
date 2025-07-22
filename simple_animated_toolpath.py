#!/usr/bin/env python3
"""
Simple Animated Toolpath Visualizer

Shows 2D XY layout with shapes and animates GCODE execution.
"""

import re
import math
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
from dxf_processor import DXFProcessor

def load_shapes(dxf_file):
    """Load shapes from DXF file."""
    processor = DXFProcessor()
    shapes = processor.process_dxf(dxf_file)
    print(f"Loaded {len(shapes)} shapes from DXF")
    return shapes

def load_gcode(gcode_file):
    """Load and parse GCODE file."""
    toolpath_points = []
    z_colors = []
    corner_indices = []
    current_pos = {'X': 0, 'Y': 0, 'Z': 0, 'A': 0}
    previous_z = 0
    
    with open(gcode_file, 'r') as f:
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
                toolpath_points.append(current_pos.copy())
                
                # Check for Z changes (corners)
                if abs(current_pos['Z'] - previous_z) > 0.1:  # Z changed significantly
                    corner_indices.append(len(toolpath_points) - 1)
                
                previous_z = current_pos['Z']
                
                # Determine color based on Z height
                if current_pos['Z'] < -1.0:
                    z_colors.append('red')      # Cutting
                elif current_pos['Z'] > 1.0:
                    z_colors.append('green')    # Safe height
                else:
                    z_colors.append('orange')   # Transition
    
    print(f"Loaded {len(toolpath_points)} toolpath points")
    print(f"Found {len(corner_indices)} corners (Z changes)")
    return toolpath_points, z_colors, corner_indices

def create_static_plot(shapes, toolpath_points, z_colors):
    """Create a static plot showing the complete toolpath."""
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))
    ax.set_aspect('equal')
    ax.set_xlabel('X (mm)')
    ax.set_ylabel('Y (mm)')
    ax.set_title('Complete Toolpath with Shapes\nRed=Cutting, Green=Safe Height, Orange=Transition')
    ax.grid(True, alpha=0.3)
    
    # Plot all shapes in background
    for shape_name, points in shapes.items():
        if len(points) > 1:
            x_coords = [p[0] for p in points]
            y_coords = [p[1] for p in points]
            ax.plot(x_coords, y_coords, 'k-', linewidth=0.5, alpha=0.3)
    
    # Extract toolpath data
    x_coords = [p['X'] for p in toolpath_points]
    y_coords = [p['Y'] for p in toolpath_points]
    
    # Plot complete toolpath with colors
    ax.scatter(x_coords, y_coords, c=z_colors, s=5, alpha=0.7)
    
    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='red', label='Cutting (Z < -1mm)'),
        Patch(facecolor='green', label='Safe Height (Z > 1mm)'),
        Patch(facecolor='orange', label='Transition')
    ]
    ax.legend(handles=legend_elements, loc='upper right')
    
    plt.tight_layout()
    plt.savefig('complete_toolpath.png', dpi=300, bbox_inches='tight')
    print("Static plot saved as complete_toolpath.png")
    plt.show()

def create_simple_animation(shapes, toolpath_points, z_colors, corner_indices):
    """Create a simple animation."""
    # Set up the figure
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))
    ax.set_aspect('equal')
    ax.set_xlabel('X (mm)')
    ax.set_ylabel('Y (mm)')
    ax.set_title('Toolpath Animation with Z-Axis Orientation\nRed=Cutting, Green=Safe Height, Orange=Transition')
    ax.grid(True, alpha=0.3)
    
    # Plot all shapes in background
    for shape_name, points in shapes.items():
        if len(points) > 1:
            x_coords = [p[0] for p in points]
            y_coords = [p[1] for p in points]
            ax.plot(x_coords, y_coords, 'k-', linewidth=0.5, alpha=0.3)
    
    # Extract toolpath data
    x_coords = [p['X'] for p in toolpath_points]
    y_coords = [p['Y'] for p in toolpath_points]
    a_coords = [p['A'] for p in toolpath_points]
    
    # Set plot limits
    ax.set_xlim(min(x_coords) - 5, max(x_coords) + 5)
    ax.set_ylim(min(y_coords) - 5, max(y_coords) + 5)
    
    # Create lines for animation
    toolpath_line, = ax.plot([], [], 'b-', linewidth=2, alpha=0.7)
    current_point, = ax.plot([], [], 'ro', markersize=10)
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
    
    def animate(frame):
        # Update toolpath line
        toolpath_line.set_data(x_coords[:frame+1], y_coords[:frame+1])
        
        # Update current point
        if frame < len(x_coords):
            current_point.set_data([x_coords[frame]], [y_coords[frame]])
            current_point.set_color(z_colors[frame])
            
            # Update Z-axis orientation line
            if frame > 0:
                # Calculate movement direction
                dx = x_coords[frame] - x_coords[frame-1]
                dy = y_coords[frame] - y_coords[frame-1]
                length = math.sqrt(dx*dx + dy*dy)
                
                if length > 0:
                    # Normalize movement vector
                    dx_norm = dx / length
                    dy_norm = dy / length
                    
                    # Blade direction is perpendicular to movement (90 degrees)
                    blade_length = 3.0
                    blade_dx = -dy_norm * blade_length
                    blade_dy = dx_norm * blade_length
                    
                    # Draw blade orientation line
                    z_axis_line.set_data([x_coords[frame] - blade_dx, x_coords[frame] + blade_dx],
                                       [y_coords[frame] - blade_dy, y_coords[frame] + blade_dy])
                else:
                    z_axis_line.set_data([], [])
            else:
                z_axis_line.set_data([], [])
        
        return toolpath_line, current_point, z_axis_line
    
    # Create animation with fewer frames for better performance
    step = max(1, len(toolpath_points) // 500)  # Limit to 500 frames
    frames = list(range(0, len(toolpath_points), step))
    
    anim = animation.FuncAnimation(fig, animate, frames=frames, 
                                 interval=100, blit=False, repeat=True)
    
    plt.tight_layout()
    
    # Save animation as GIF
    try:
        output_file = 'animated_toolpath.gif'
        anim.save(output_file, writer='pillow', fps=10)
        print(f"Animation saved as {output_file}")
    except Exception as e:
        print(f"Could not save animation: {e}")
    
    print("Showing animation in window...")
    plt.show()

def main():
    """Main function."""
    dxf_file = "/Users/peterbriggs/Downloads/test_2.dxf"
    gcode_file = "toolpath_test_2.gcode"
    
    print("Loading DXF shapes...")
    shapes = load_shapes(dxf_file)
    
    print("Loading GCODE...")
    toolpath_points, z_colors, corner_indices = load_gcode(gcode_file)
    
    # Print summary
    z_coords = [p['Z'] for p in toolpath_points]
    cutting = sum(1 for z in z_coords if z < -1.0)
    safe = sum(1 for z in z_coords if z > 1.0)
    transition = sum(1 for z in z_coords if -1.0 <= z <= 1.0)
    
    print("\n" + "="*50)
    print("TOOLPATH SUMMARY")
    print("="*50)
    print(f"Shapes loaded: {len(shapes)}")
    print(f"Toolpath points: {len(toolpath_points)}")
    print(f"Corners detected: {len(corner_indices)}")
    print(f"Cutting points: {cutting}")
    print(f"Safe height points: {safe}")
    print(f"Transition points: {transition}")
    print("="*50)
    
    print("Creating static plot...")
    create_static_plot(shapes, toolpath_points, z_colors)
    
    print("Creating animation...")
    create_simple_animation(shapes, toolpath_points, z_colors, corner_indices)

if __name__ == "__main__":
    main() 