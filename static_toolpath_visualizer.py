#!/usr/bin/env python3
"""
Static Toolpath Visualizer

Shows 2D XY layout with shapes, complete toolpath, Z-axis orientation, and corner highlights.
"""

import re
import math
import matplotlib.pyplot as plt
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
                
                # Check for Z changes (corners) - only when significant change
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
    
    # Now detect corners based on angle changes > 2 degrees
    corner_indices = detect_angle_corners(toolpath_points, threshold_degrees=2.0)
    
    print(f"Loaded {len(toolpath_points)} toolpath points")
    print(f"Found {len(corner_indices)} corners (angle changes > 2°)")
    return toolpath_points, z_colors, corner_indices

def detect_angle_corners(toolpath_points, threshold_degrees=2.0):
    """Detect corners where angle change is greater than threshold."""
    corner_indices = []
    threshold_radians = math.radians(threshold_degrees)
    
    for i in range(1, len(toolpath_points) - 1):
        # Get three consecutive points
        prev_point = toolpath_points[i - 1]
        curr_point = toolpath_points[i]
        next_point = toolpath_points[i + 1]
        
        # Calculate vectors
        vec1_x = curr_point['X'] - prev_point['X']
        vec1_y = curr_point['Y'] - prev_point['Y']
        vec2_x = next_point['X'] - curr_point['X']
        vec2_y = next_point['Y'] - curr_point['Y']
        
        # Calculate magnitudes
        mag1 = math.sqrt(vec1_x**2 + vec1_y**2)
        mag2 = math.sqrt(vec2_x**2 + vec2_y**2)
        
        if mag1 > 0 and mag2 > 0:
            # Calculate dot product
            dot_product = vec1_x * vec2_x + vec1_y * vec2_y
            
            # Calculate angle
            cos_angle = dot_product / (mag1 * mag2)
            cos_angle = max(-1.0, min(1.0, cos_angle))  # Clamp to [-1, 1]
            angle = math.acos(cos_angle)
            
            # Check if angle change is greater than threshold
            if angle > threshold_radians:
                corner_indices.append(i)
    
    return corner_indices

def create_comprehensive_plot(shapes, toolpath_points, z_colors, corner_indices):
    """Create a comprehensive static plot."""
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))
    
    # Extract toolpath data
    x_coords = [p['X'] for p in toolpath_points]
    y_coords = [p['Y'] for p in toolpath_points]
    z_coords = [p['Z'] for p in toolpath_points]
    a_coords = [p['A'] for p in toolpath_points]
    
    # Plot: Complete toolpath with shapes and Z-axis orientation
    ax.set_aspect('equal')
    ax.set_xlabel('X (mm)')
    ax.set_ylabel('Y (mm)')
    ax.set_title('Complete Toolpath with Z-Axis Orientation\nRed=Cutting, Green=Safe Height, Orange=Transition')
    ax.grid(True, alpha=0.3)
    
    # Plot all shapes in background
    for shape_name, points in shapes.items():
        if len(points) > 1:
            shape_x = [p[0] for p in points]
            shape_y = [p[1] for p in points]
            ax.plot(shape_x, shape_y, 'k-', linewidth=0.5, alpha=0.3)
    
    # Plot complete toolpath with colors
    ax.scatter(x_coords, y_coords, c=z_colors, s=3, alpha=0.7)
    
    # Add Z-axis orientation lines at regular intervals (PARALLEL to path)
    step = max(1, len(toolpath_points) // 100)  # Show 100 orientation lines
    for i in range(0, len(toolpath_points), step):
        if i > 0:
            # Calculate movement direction
            dx = x_coords[i] - x_coords[i-1]
            dy = y_coords[i] - y_coords[i-1]
            length = math.sqrt(dx*dx + dy*dy)
            
            if length > 0:
                # Normalize movement vector
                dx_norm = dx / length
                dy_norm = dy / length
                
                # Blade direction is PARALLEL to movement (not perpendicular)
                blade_length = 2.0
                blade_dx = dx_norm * blade_length
                blade_dy = dy_norm * blade_length
                
                # Draw blade orientation line (parallel to path)
                ax.plot([x_coords[i] - blade_dx, x_coords[i] + blade_dx],
                        [y_coords[i] - blade_dy, y_coords[i] + blade_dy],
                        'r-', linewidth=1, alpha=0.6)
    
    # Highlight corners with larger markers
    corner_x = [x_coords[i] for i in corner_indices]
    corner_y = [y_coords[i] for i in corner_indices]
    ax.scatter(corner_x, corner_y, c='purple', s=50, alpha=0.8, marker='s', label='Corners (angle > 2°)')
    
    # Set plot limits
    ax.set_xlim(min(x_coords) - 5, max(x_coords) + 5)
    ax.set_ylim(min(y_coords) - 5, max(y_coords) + 5)
    
    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='red', label='Cutting (Z < -1mm)'),
        Patch(facecolor='green', label='Safe Height (Z > 1mm)'),
        Patch(facecolor='orange', label='Transition'),
        Patch(facecolor='purple', label='Corners (angle > 2°)')
    ]
    ax.legend(handles=legend_elements, loc='upper right')
    
    plt.tight_layout()
    plt.savefig('comprehensive_toolpath_analysis.png', dpi=300, bbox_inches='tight')
    print("Comprehensive analysis saved as comprehensive_toolpath_analysis.png")
    plt.show()

def create_corner_analysis(toolpath_points, corner_indices):
    """Create detailed corner analysis."""
    fig, ax = plt.subplots(1, 1, figsize=(12, 8))
    
    # Extract data around corners
    corner_data = []
    for idx in corner_indices:
        if idx > 0 and idx < len(toolpath_points) - 1:
            before = toolpath_points[idx - 1]
            at = toolpath_points[idx]
            after = toolpath_points[idx + 1]
            
            corner_data.append({
                'index': idx,
                'before_z': before['Z'],
                'at_z': at['Z'],
                'after_z': after['Z'],
                'z_change': at['Z'] - before['Z'],
                'before_a': before['A'],
                'at_a': at['A'],
                'after_a': after['A'],
                'a_change': at['A'] - before['A']
            })
    
    if corner_data:
        # Plot Z changes at corners
        indices = [d['index'] for d in corner_data]
        z_changes = [d['z_change'] for d in corner_data]
        a_changes = [d['a_change'] for d in corner_data]
        
        ax.scatter(indices, z_changes, c='red', s=50, alpha=0.7, label='Z Height Change')
        ax.scatter(indices, a_changes, c='blue', s=50, alpha=0.7, label='Z Rotation Change')
        
        ax.set_xlabel('Toolpath Point Index')
        ax.set_ylabel('Change Value')
        ax.set_title('Corner Analysis: Z Height and Rotation Changes')
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Add horizontal line at zero
        ax.axhline(y=0, color='k', linestyle='-', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig('corner_analysis.png', dpi=300, bbox_inches='tight')
        print("Corner analysis saved as corner_analysis.png")
        plt.show()
        
        # Print corner statistics
        print("\n" + "="*50)
        print("CORNER ANALYSIS")
        print("="*50)
        print(f"Total corners: {len(corner_data)}")
        if corner_data:
            z_changes_abs = [abs(d['z_change']) for d in corner_data]
            a_changes_abs = [abs(d['a_change']) for d in corner_data]
            print(f"Average Z change: {sum(z_changes_abs)/len(z_changes_abs):.2f} mm")
            print(f"Average rotation change: {sum(a_changes_abs)/len(a_changes_abs):.2f} degrees")
            print(f"Max Z change: {max(z_changes_abs):.2f} mm")
            print(f"Max rotation change: {max(a_changes_abs):.2f} degrees")
        print("="*50)

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
    print(f"Z rotation range: {min([p['A'] for p in toolpath_points]):.1f}° to {max([p['A'] for p in toolpath_points]):.1f}°")
    print(f"Z height range: {min(z_coords):.1f} to {max(z_coords):.1f} mm")
    print("="*50)
    
    print("Creating comprehensive analysis...")
    create_comprehensive_plot(shapes, toolpath_points, z_colors, corner_indices)
    
    print("Creating corner analysis...")
    create_corner_analysis(toolpath_points, corner_indices)

if __name__ == "__main__":
    main() 