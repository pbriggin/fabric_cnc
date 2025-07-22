#!/usr/bin/env python3
"""
Corner Analyzer - Debug script to understand corner detection
"""

import re

def analyze_corners():
    """Analyze corner coordinates in the GCODE file."""
    
    corner_coords = []
    
    with open("toolpath_test_no_polyline.gcode", 'r') as f:
        lines = f.readlines()
    
    current_x = 0.0
    current_y = 0.0
    
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        
        # Extract coordinates
        x_match = re.search(r'X([-\d.]+)', line)
        y_match = re.search(r'Y([-\d.]+)', line)
        
        if x_match:
            current_x = float(x_match.group(1))
        if y_match:
            current_y = float(y_match.group(1))
        
        # Check for corner handling
        if 'Raise Z for corner' in line:
            corner_coords.append((current_x, current_y, line_num))
    
    print(f"Found {len(corner_coords)} corner detections:")
    print()
    
    # Group by coordinates
    coord_groups = {}
    for x, y, line_num in corner_coords:
        coord_key = f"{x:.3f}, {y:.3f}"
        if coord_key not in coord_groups:
            coord_groups[coord_key] = []
        coord_groups[coord_key].append(line_num)
    
    print("Corner coordinates (with line numbers):")
    for coord, line_nums in sorted(coord_groups.items()):
        print(f"  {coord}: lines {line_nums} ({len(line_nums)} occurrences)")
    
    print()
    print(f"Unique corner coordinates: {len(coord_groups)}")
    
    # Show duplicates
    duplicates = {coord: lines for coord, lines in coord_groups.items() if len(lines) > 1}
    if duplicates:
        print(f"Duplicate coordinates ({len(duplicates)}):")
        for coord, line_nums in duplicates.items():
            print(f"  {coord}: {len(line_nums)} times at lines {line_nums}")

if __name__ == "__main__":
    analyze_corners() 