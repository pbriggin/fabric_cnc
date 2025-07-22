#!/usr/bin/env python3
"""
Script to plot the output of the DXF processor.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from dxf_processor import DXFProcessor
import numpy as np

def plot_dxf_shapes(dxf_path, save_plot=True, show_plot=True):
    """
    Plot the shapes extracted from a DXF file.
    
    Args:
        dxf_path: Path to the DXF file
        save_plot: Whether to save the plot as an image
        show_plot: Whether to display the plot
    """
    # Process the DXF file
    processor = DXFProcessor()
    shapes = processor.process_dxf(dxf_path)
    
    if not shapes:
        print("No shapes found in the DXF file.")
        return
    
    # Create the plot
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # Define colors for different shapes
    colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']
    
    # Plot each shape
    for i, (shape_name, points) in enumerate(shapes.items()):
        if len(points) < 2:
            continue
            
        # Convert points to numpy arrays for easier plotting
        x_coords = [p[0] for p in points]
        y_coords = [p[1] for p in points]
        
        # Choose color
        color = colors[i % len(colors)]
        
        # Plot the shape
        if len(points) == 2:
            # Line
            ax.plot(x_coords, y_coords, color=color, linewidth=2, label=f'{shape_name} (Line)')
        else:
            # Polygon or curve
            ax.plot(x_coords, y_coords, color=color, linewidth=1, alpha=0.7, label=f'{shape_name} ({len(points)} points)')
        
        # Plot all points
        ax.scatter(x_coords, y_coords, color=color, s=20, alpha=0.8, edgecolors='black', linewidth=0.5)
        
        # Mark the first point with a different marker
        ax.plot(x_coords[0], y_coords[0], 'o', color=color, markersize=10, markeredgecolor='black', linewidth=2, label=f'{shape_name} start')
        
        # Mark the last point if different from first
        if len(points) > 1 and points[0] != points[-1]:
            ax.plot(x_coords[-1], y_coords[-1], 's', color=color, markersize=8, markeredgecolor='black', linewidth=2, label=f'{shape_name} end')
    
    # Set up the plot
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    ax.set_xlabel('X Coordinate')
    ax.set_ylabel('Y Coordinate')
    ax.set_title(f'DXF Shapes from {dxf_path.split("/")[-1]}')
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    # Calculate bounds with some padding
    all_x = []
    all_y = []
    for points in shapes.values():
        all_x.extend([p[0] for p in points])
        all_y.extend([p[1] for p in points])
    
    if all_x and all_y:
        x_min, x_max = min(all_x), max(all_x)
        y_min, y_max = min(all_y), max(all_y)
        
        # Add padding
        x_padding = (x_max - x_min) * 0.1
        y_padding = (y_max - y_min) * 0.1
        
        ax.set_xlim(x_min - x_padding, x_max + x_padding)
        ax.set_ylim(y_min - y_padding, y_max + y_padding)
    
    # Adjust layout to prevent label cutoff
    plt.tight_layout()
    
    # Save the plot
    if save_plot:
        filename = f"dxf_plot_{dxf_path.split('/')[-1].replace('.dxf', '')}.png"
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"Plot saved as {filename}")
    
    # Show the plot
    if show_plot:
        plt.show()
    
    # Print summary
    print(f"\nSummary for {dxf_path}:")
    print(f"Total shapes: {len(shapes)}")
    for shape_name, points in shapes.items():
        print(f"  {shape_name}: {len(points)} points")
        if points:
            print(f"    Bounds: X({min(p[0] for p in points):.3f}, {max(p[0] for p in points):.3f})")
            print(f"           Y({min(p[1] for p in points):.3f}, {max(p[1] for p in points):.3f})")
            
            # Print first 10 and last 10 points
            print(f"    First 10 points:")
            for i, point in enumerate(points[:10]):
                print(f"      {i}: ({point[0]:.6f}, {point[1]:.6f})")
            
            if len(points) > 20:
                print(f"    ... ({len(points) - 20} more points) ...")
                print(f"    Last 10 points:")
                for i, point in enumerate(points[-10:], len(points) - 10):
                    print(f"      {i}: ({point[0]:.6f}, {point[1]:.6f})")
            elif len(points) > 10:
                print(f"    Remaining points:")
                for i, point in enumerate(points[10:], 10):
                    print(f"      {i}: ({point[0]:.6f}, {point[1]:.6f})")
            print()

def main():
    """Main function to plot the test DXF file."""
    # Test with the provided DXF file
    dxf_path = "/Users/peterbriggs/Downloads/test_2.dxf"
    
    try:
        plot_dxf_shapes(dxf_path, save_plot=True, show_plot=False)  # Don't show plot, just save it
    except Exception as e:
        print(f"Error plotting DXF file: {e}")

if __name__ == "__main__":
    main() 