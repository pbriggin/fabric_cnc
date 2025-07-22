#!/usr/bin/env python3
"""
Plot raw DXF file with interactive corner selection.
"""

import matplotlib.pyplot as plt
import numpy as np
from dxf_processor import DXFProcessor
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def plot_raw_dxf(dxf_path: str):
    """Plot the raw DXF file with interactive corner selection."""
    
    # Process DXF file
    dxf_processor = DXFProcessor()
    shapes = dxf_processor.process_dxf(dxf_path)
    
    if not shapes:
        print("No shapes found in DXF file")
        return
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # Plot each shape
    for shape_name, points in shapes.items():
        if len(points) < 2:
            continue
            
        # Extract x and y coordinates
        x_coords = [p[0] for p in points]
        y_coords = [p[1] for p in points]
        
        # Plot the shape
        ax.plot(x_coords, y_coords, 'b-', linewidth=2, label=f'Shape: {shape_name}')
        
        # Plot points
        ax.scatter(x_coords, y_coords, c='blue', s=20, alpha=0.6)
        
        # Mark start and end points
        ax.scatter(x_coords[0], y_coords[0], c='green', s=100, marker='o', 
                  label='Start', zorder=5, edgecolors='black', linewidth=2)
        ax.scatter(x_coords[-1], y_coords[-1], c='red', s=100, marker='s', 
                  label='End', zorder=5, edgecolors='black', linewidth=2)
    
    # Set up the plot
    ax.set_xlabel('X (mm)')
    ax.set_ylabel('Y (mm)')
    ax.set_title('Raw DXF File - Click where corners should be')
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.set_aspect('equal')
    
    # Store clicked points
    clicked_points = []
    
    def on_click(event):
        if event.inaxes != ax:
            return
        
        # Get click coordinates
        x, y = event.xdata, event.ydata
        
        if x is not None and y is not None:
            # Add to clicked points
            clicked_points.append((x, y))
            
            # Plot the clicked point
            ax.scatter(x, y, c='orange', s=150, marker='*', zorder=10)
            
            # Add text label
            ax.text(x + 0.5, y + 0.5, f'Corner {len(clicked_points)}', 
                   fontsize=10, color='orange', weight='bold')
            
            print(f"Corner {len(clicked_points)} clicked at: ({x:.3f}, {y:.3f})")
            
            # Redraw
            plt.draw()
    
    # Connect the click event
    fig.canvas.mpl_connect('button_press_event', on_click)
    
    # Show instructions
    print("\n" + "="*60)
    print("INSTRUCTIONS:")
    print("1. Look at the DXF plot")
    print("2. Click on each point where you think there should be a corner")
    print("3. Orange stars will mark your selected corners")
    print("4. Press 'q' to close the plot when done")
    print("="*60)
    
    plt.tight_layout()
    plt.show()
    
    # Print summary
    if clicked_points:
        print(f"\nYou selected {len(clicked_points)} corners:")
        for i, (x, y) in enumerate(clicked_points, 1):
            print(f"  Corner {i}: ({x:.3f}, {y:.3f})")
    else:
        print("\nNo corners were selected.")

def main():
    """Main function."""
    dxf_path = "test_no_polyline.dxf"
    
    try:
        plot_raw_dxf(dxf_path)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 