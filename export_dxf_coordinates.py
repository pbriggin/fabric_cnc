#!/usr/bin/env python3
"""
Export raw DXF coordinates to CSV for Excel plotting.
"""

import csv
from dxf_processor import DXFProcessor
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def export_dxf_coordinates(dxf_path: str, output_csv: str = None):
    """Export DXF coordinates to CSV file."""
    
    if output_csv is None:
        output_csv = f"{dxf_path.replace('.dxf', '_coordinates.csv')}"
    
    # Process DXF file
    dxf_processor = DXFProcessor()
    shapes = dxf_processor.process_dxf(dxf_path)
    
    if not shapes:
        print("No shapes found in DXF file")
        return
    
    # Export to CSV
    with open(output_csv, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        
        # Write header
        writer.writerow(['Shape', 'Point_Index', 'X_mm', 'Y_mm'])
        
        # Write coordinates for each shape
        for shape_name, points in shapes.items():
            print(f"Exporting {len(points)} points from {shape_name}")
            
            for i, (x, y) in enumerate(points):
                writer.writerow([shape_name, i, f"{x:.6f}", f"{y:.6f}"])
    
    print(f"\nCoordinates exported to: {output_csv}")
    print(f"Total points: {sum(len(points) for points in shapes.values())}")
    
    # Print summary
    print("\nShape Summary:")
    for shape_name, points in shapes.items():
        print(f"  {shape_name}: {len(points)} points")
        if points:
            x_coords = [p[0] for p in points]
            y_coords = [p[1] for p in points]
            print(f"    X range: {min(x_coords):.3f} to {max(x_coords):.3f}")
            print(f"    Y range: {min(y_coords):.3f} to {max(y_coords):.3f}")
    
    # Also print coordinates to console for quick reference
    print("\n" + "="*60)
    print("FIRST 20 COORDINATES:")
    print("="*60)
    for shape_name, points in shapes.items():
        print(f"\n{shape_name}:")
        for i, (x, y) in enumerate(points[:20]):
            print(f"  Point {i:3d}: ({x:8.3f}, {y:8.3f})")
        if len(points) > 20:
            print(f"  ... and {len(points) - 20} more points")

def main():
    """Main function."""
    dxf_path = "test_2.dxf"
    
    try:
        export_dxf_coordinates(dxf_path)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 