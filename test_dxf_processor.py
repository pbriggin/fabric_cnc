#!/usr/bin/env python3
"""
Test script for the DXF processor with the user's specific file.
"""

import sys
import os
from dxf_processor import DXFProcessor
import matplotlib.pyplot as plt
import numpy as np

def test_dxf_file(dxf_path):
    """Test the DXF processor with a specific file."""
    print(f"Testing DXF file: {dxf_path}")
    print("=" * 50)
    
    # Check if file exists
    if not os.path.exists(dxf_path):
        print(f"Error: File {dxf_path} does not exist!")
        return
    
    # Initialize processor
    processor = DXFProcessor(max_angle_change_degrees=0.1)
    
    try:
        # Process the DXF file
        shapes = processor.process_dxf(dxf_path)
        
        print(f"Successfully processed DXF file!")
        print(f"Found {len(shapes)} shapes:")
        print()
        
        # Display information about each shape
        for shape_name, points in shapes.items():
            print(f"{shape_name}:")
            print(f"  Number of points: {len(points)}")
            if points:
                print(f"  First point: {points[0]}")
                print(f"  Last point: {points[-1]}")
                
                # Calculate bounds
                x_coords = [p[0] for p in points]
                y_coords = [p[1] for p in points]
                x_min, x_max = min(x_coords), max(x_coords)
                y_min, y_max = min(y_coords), max(y_coords)
                
                print(f"  Bounds: X({x_min:.3f}, {x_max:.3f}), Y({y_min:.3f}, {y_max:.3f})")
                print(f"  Width: {x_max - x_min:.3f}, Height: {y_max - y_min:.3f}")
                
                # Check if shape is closed
                if len(points) > 2:
                    first_point = points[0]
                    last_point = points[-1]
                    distance = ((first_point[0] - last_point[0])**2 + 
                              (first_point[1] - last_point[1])**2)**0.5
                    is_closed = distance < 0.001
                    print(f"  Closed shape: {is_closed}")
            print()
        
        # Plot the shapes
        plot_shapes(shapes, dxf_path)
        
    except Exception as e:
        print(f"Error processing DXF file: {e}")
        import traceback
        traceback.print_exc()

def plot_shapes(shapes, dxf_path):
    """Plot the extracted shapes using matplotlib."""
    if not shapes:
        print("No shapes to plot.")
        return
    
    plt.figure(figsize=(12, 10))
    
    # Use different colors for each shape
    colors = plt.cm.Set3(np.linspace(0, 1, len(shapes)))
    
    for i, (shape_name, points) in enumerate(shapes.items()):
        if len(points) < 2:
            continue
            
        x_coords = [p[0] for p in points]
        y_coords = [p[1] for p in points]
        
        plt.plot(x_coords, y_coords, 
                color=colors[i], 
                linewidth=2, 
                label=shape_name,
                marker='o', 
                markersize=3)
    
    plt.title(f'DXF Shapes from {os.path.basename(dxf_path)}')
    plt.xlabel('X Coordinate')
    plt.ylabel('Y Coordinate')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.axis('equal')
    
    # Save the plot
    output_filename = f"dxf_plot_{os.path.splitext(os.path.basename(dxf_path))[0]}.png"
    plt.savefig(output_filename, dpi=300, bbox_inches='tight')
    print(f"Plot saved as: {output_filename}")
    
    plt.show()

if __name__ == "__main__":
    # Test with the user's specific file
    dxf_path = "/Users/peterbriggs/Downloads/test_2.dxf"
    test_dxf_file(dxf_path) 