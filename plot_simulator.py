#!/usr/bin/env python3
"""
Simple Plot Simulator for GCODE

Just shows the Z rotation and Z height with color coding.
"""

import re
import matplotlib.pyplot as plt
import numpy as np

def parse_gcode(gcode_file):
    """Parse GCODE and extract positions."""
    positions = []
    current_pos = {'X': 0, 'Y': 0, 'Z': 0, 'A': 0}
    
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
            
            positions.append(current_pos.copy())
    
    return positions

def create_simple_plot(positions):
    """Create a simple plot showing Z rotation and height."""
    # Extract data
    a_coords = [p['A'] for p in positions]
    z_coords = [p['Z'] for p in positions]
    timestamps = list(range(len(positions)))
    
    # Determine colors based on Z height
    colors = []
    for z in z_coords:
        if z < -1.0:
            colors.append('red')      # Cutting
        elif z > 1.0:
            colors.append('green')    # Safe height
        else:
            colors.append('orange')   # Transition
    
    # Create plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Plot 1: Z Rotation
    ax1.plot(timestamps, a_coords, 'b-', linewidth=1, alpha=0.7)
    ax1.scatter(timestamps, a_coords, c=colors, s=10, alpha=0.8)
    ax1.set_ylabel('Z Rotation (degrees)')
    ax1.set_title('GCODE Simulation: Z Rotation vs Position')
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Z Height
    ax2.plot(timestamps, z_coords, 'g-', linewidth=1, alpha=0.7)
    ax2.scatter(timestamps, z_coords, c=colors, s=10, alpha=0.8)
    ax2.set_xlabel('Toolpath Point')
    ax2.set_ylabel('Z Height (mm)')
    ax2.set_title('Z Height vs Position')
    ax2.grid(True, alpha=0.3)
    
    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='red', label='Cutting (Z < -1mm)'),
        Patch(facecolor='green', label='Safe Height (Z > 1mm)'),
        Patch(facecolor='orange', label='Transition')
    ]
    ax1.legend(handles=legend_elements, loc='upper right')
    
    plt.tight_layout()
    
    # Save and show
    plt.savefig('gcode_visualization.png', dpi=300, bbox_inches='tight')
    print("Plot saved as gcode_visualization.png")
    
    # Show the plot
    plt.show()

def main():
    """Main function."""
    gcode_file = "toolpath_test_2.gcode"
    
    print(f"Loading GCODE from {gcode_file}...")
    positions = parse_gcode(gcode_file)
    print(f"Loaded {len(positions)} positions")
    
    # Count colors
    z_coords = [p['Z'] for p in positions]
    cutting = sum(1 for z in z_coords if z < -1.0)
    safe = sum(1 for z in z_coords if z > 1.0)
    transition = sum(1 for z in z_coords if -1.0 <= z <= 1.0)
    
    print(f"Cutting points: {cutting}")
    print(f"Safe height points: {safe}")
    print(f"Transition points: {transition}")
    
    print("Creating visualization...")
    create_simple_plot(positions)

if __name__ == "__main__":
    main() 