#!/usr/bin/env python3
"""
Simple script to check DXF coordinates and understand the scale.
"""

import ezdxf
import sys

def check_dxf_coordinates(dxf_path):
    """Check the coordinates in a DXF file to understand the scale."""
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        print(f"Checking DXF file: {dxf_path}")
        print("=" * 50)
        
        # Check header for units
        try:
            insunits = doc.header.get('$INSUNITS', 'Not found')
            measurement = doc.header.get('$MEASUREMENT', 'Not found')
            print(f"INSUNITS: {insunits}")
            print(f"MEASUREMENT: {measurement}")
        except:
            print("Could not read header units")
        
        print()
        
        # Collect all coordinates
        all_x = []
        all_y = []
        entity_count = 0
        
        for entity in msp:
            entity_count += 1
            entity_type = entity.dxftype()
            
            if entity_type == 'LINE':
                all_x.extend([entity.dxf.start.x, entity.dxf.end.x])
                all_y.extend([entity.dxf.start.y, entity.dxf.end.y])
            elif entity_type == 'LWPOLYLINE':
                points = entity.get_points()
                for point in points:
                    all_x.append(point[0])
                    all_y.append(point[1])
            elif entity_type == 'CIRCLE':
                center = entity.dxf.center
                radius = entity.dxf.radius
                all_x.extend([center.x - radius, center.x + radius])
                all_y.extend([center.y - radius, center.y + radius])
            elif entity_type == 'ARC':
                center = entity.dxf.center
                radius = entity.dxf.radius
                all_x.extend([center.x - radius, center.x + radius])
                all_y.extend([center.y - radius, center.y + radius])
            elif entity_type == 'SPLINE':
                try:
                    points = list(entity.flattening(0.1))
                    for point in points:
                        if len(point) >= 2:
                            all_x.append(point[0])
                            all_y.append(point[1])
                except:
                    pass
        
        if all_x and all_y:
            min_x, max_x = min(all_x), max(all_x)
            min_y, max_y = min(all_y), max(all_y)
            
            print(f"Entity count: {entity_count}")
            print(f"Coordinate ranges:")
            print(f"  X: {min_x:.3f} to {max_x:.3f} (range: {max_x - min_x:.3f})")
            print(f"  Y: {min_y:.3f} to {max_y:.3f} (range: {max_y - min_y:.3f})")
            
            # Try to determine scale
            x_range = max_x - min_x
            y_range = max_y - min_y
            
            print(f"\nScale analysis:")
            print(f"  If coordinates are in inches:")
            print(f"    X range: {x_range:.3f} inches = {x_range * 25.4:.3f} mm")
            print(f"    Y range: {y_range:.3f} inches = {y_range * 25.4:.3f} mm")
            
            print(f"  If coordinates are in millimeters:")
            print(f"    X range: {x_range:.3f} mm = {x_range / 25.4:.3f} inches")
            print(f"    Y range: {y_range:.3f} mm = {y_range / 25.4:.3f} inches")
            
            print(f"  If coordinates are in meters:")
            print(f"    X range: {x_range:.3f} m = {x_range * 1000:.3f} mm")
            print(f"    Y range: {y_range:.3f} m = {y_range * 1000:.3f} mm")
            
        else:
            print("No coordinates found in DXF file")
            
    except Exception as e:
        print(f"Error reading DXF file: {e}")

if __name__ == "__main__":
    dxf_path = "outputs/test_2.dxf"
    check_dxf_coordinates(dxf_path) 