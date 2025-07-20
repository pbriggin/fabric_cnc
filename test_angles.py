#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to debug angle calculation logic with test.dxf
"""

import os
import sys
import math
import ezdxf
from ezdxf.filemanagement import readfile

# Constants
INCH_TO_MM = 25.4

def test_angle_calculation():
    """Test angle calculation with the test DXF file"""
    
    # Load the DXF file
    dxf_path = "/home/fabric/Desktop/DXF/test.dxf"
    if not os.path.exists(dxf_path):
        print(f"DXF file not found: {dxf_path}")
        return
    
    try:
        doc = readfile(dxf_path)
        msp = doc.modelspace()
        print(f"DXF loaded successfully")
        print(f"Entities found: {len(msp)}")
        
        # Get all entities
        entities = list(msp)
        
        # Process entities into segments
        segments = []
        for e in entities:
            t = e.dxftype()
            if t == 'LINE':
                x1, y1 = e.dxf.start.x, e.dxf.start.y
                x2, y2 = e.dxf.end.x, e.dxf.end.y
                segments.append(((x1, y1), (x2, y2)))
                print(f"LINE: ({x1:.3f}, {y1:.3f}) -> ({x2:.3f}, {y2:.3f})")
            elif t == 'LWPOLYLINE':
                pts = [p[:2] for p in e.get_points()]
                print(f"LWPOLYLINE: {len(pts)} points")
                for i in range(1, len(pts)):
                    segments.append((pts[i-1], pts[i]))
                if getattr(e, 'closed', False) or (len(pts) > 2 and pts[0] == pts[-1]):
                    segments.append((pts[-1], pts[0]))
            elif t == 'POLYLINE':
                pts = [(v.dxf.x, v.dxf.y) for v in e.vertices()]
                print(f"POLYLINE: {len(pts)} points")
                for i in range(1, len(pts)):
                    segments.append((pts[i-1], pts[i]))
                if getattr(e, 'is_closed', False) or (len(pts) > 2 and pts[0] == pts[-1]):
                    segments.append((pts[-1], pts[0]))
        
        print(f"\nTotal segments: {len(segments)}")
        
        # Group segments into shapes by connectivity
        from collections import defaultdict, deque
        point_map = defaultdict(list)
        seg_indices = list(range(len(segments)))
        for idx, (p1, p2) in enumerate(segments):
            p1r = (round(p1[0], 6), round(p1[1], 6))
            p2r = (round(p2[0], 6), round(p2[1], 6))
            point_map[p1r].append((idx, p2r))
            point_map[p2r].append((idx, p1r))
        
        visited = set()
        shapes = []
        for idx in seg_indices:
            if idx in visited:
                continue
            seg = segments[idx]
            p_start = (round(seg[0][0], 6), round(seg[0][1], 6))
            p_end = (round(seg[1][0], 6), round(seg[1][1], 6))
            shape = [p_start, p_end]
            visited.add(idx)
            cur = p_end
            while True:
                found = False
                for next_idx, next_pt in point_map[cur]:
                    if next_idx not in visited:
                        shape.append(next_pt)
                        visited.add(next_idx)
                        cur = next_pt
                        found = True
                        break
                if not found:
                    break
            cur = p_start
            while True:
                found = False
                for next_idx, next_pt in point_map[cur]:
                    if next_idx not in visited:
                        shape = [next_pt] + shape
                        visited.add(next_idx)
                        cur = next_pt
                        found = True
                        break
                if not found:
                    break
            
            # Remove duplicates
            deduped = [shape[0]]
            for pt in shape[1:]:
                if pt != deduped[-1]:
                    deduped.append(pt)
            shapes.append(deduped)
        
        print(f"\nFound {len(shapes)} shapes")
        
        # Test angle calculation for each shape
        for shape_idx, pts in enumerate(shapes):
            print(f"\n=== SHAPE {shape_idx + 1} ===")
            print(f"Original points: {len(pts)}")
            for i, (x, y) in enumerate(pts):
                print(f"  Point {i}: ({x:.3f}, {y:.3f})")
            
            # Remove duplicate consecutive points and closing duplicates
            pts_clean = [pts[0]]
            for i in range(1, len(pts)):
                x_prev, y_prev = pts_clean[-1]
                x_curr, y_curr = pts[i]
                # Skip if this point is the same as the previous point
                if abs(x_curr - x_prev) > 1e-6 or abs(y_curr - y_prev) > 1e-6:
                    # Also skip if this point is the same as the first point (closing duplicate)
                    x_first, y_first = pts[0]
                    if abs(x_curr - x_first) > 1e-6 or abs(y_curr - y_first) > 1e-6:
                        pts_clean.append(pts[i])
                    else:
                        print(f"  Skipping closing duplicate: ({x_curr:.3f}, {y_curr:.3f})")
                else:
                    print(f"  Skipping consecutive duplicate: ({x_curr:.3f}, {y_curr:.3f})")
            
            print(f"Cleaned points: {len(pts_clean)}")
            for i, (x, y) in enumerate(pts_clean):
                print(f"  Point {i}: ({x:.3f}, {y:.3f})")
            
            # Apply the same transformation as main_app.py with buffer
            # Get extents for offset calculation
            min_x = min(x for x, y in pts_clean)
            min_y = min(y for x, y in pts_clean)
            max_x = max(x for x, y in pts_clean)
            max_y = max(y for x, y in pts_clean)
            
            # Calculate offset with 1-inch buffer (same as main_app.py)
            buffer_inches = 1.0
            dx = min_x - buffer_inches
            dy = min_y - buffer_inches
            
            # Transform points to project reference frame (same as main_app.py)
            pts_transformed = []
            for x, y in pts_clean:
                x_transformed = x - dx
                y_transformed = y - dy
                pts_transformed.append((x_transformed, y_transformed))
            
            print(f"\nProject reference frame (after transformation):")
            print(f"Offset: dx={dx:.3f}, dy={dy:.3f}")
            for i, (x, y) in enumerate(pts_transformed):
                print(f"  Point {i}: ({x:.3f}, {y:.3f})")
            
            # Use transformed points for angle calculation
            pts_clean = pts_transformed
            
            # Calculate absolute angles from vertical (home orientation)
            n = len(pts_clean)
            if n < 2:
                continue
                
            angles = []
            for i in range(n):
                if i < n-1:
                    # Calculate angle for segment from point i to point i+1
                    x0, y0 = pts_clean[i]
                    x1, y1 = pts_clean[i+1]
                    # Calculate relative angle between points
                    relative_angle = math.atan2(y1 - y0, x1 - x0)
                    # Convert to absolute angle from vertical (home orientation)
                    # Vertical is 0°, clockwise is positive, counter-clockwise is negative
                    absolute_angle = -(math.degrees(relative_angle) - 90.0)
                    # Normalize to -180 to +180 range
                    while absolute_angle > 180:
                        absolute_angle -= 360
                    while absolute_angle < -180:
                        absolute_angle += 360
                    angles.append(math.radians(absolute_angle))
                else:
                    # For the last point, calculate angle from last point to first point
                    x0, y0 = pts_clean[i]
                    x1, y1 = pts_clean[0]  # Back to first point
                    relative_angle = math.atan2(y1 - y0, x1 - x0)
                    absolute_angle = -(math.degrees(relative_angle) - 90.0)
                    while absolute_angle > 180:
                        absolute_angle -= 360
                    while absolute_angle < -180:
                        absolute_angle += 360
                    angles.append(math.radians(absolute_angle))
            
            print(f"Calculated angles:")
            for i, angle in enumerate(angles):
                angle_deg = math.degrees(angle)
                print(f"  Point {i}: {angle_deg:.1f}°")
            
            # Generate toolpath
            path = []
            # Angle change threshold for Z control (2 degrees)
            angle_change_threshold_deg = 2.0
            
            # Start with first point
            path.append((pts_clean[0][0], pts_clean[0][1], angles[0], 1))  # Z up
            path.append((pts_clean[0][0], pts_clean[0][1], angles[0], 0))  # Z down
            
            for i in range(1, n):
                x0, y0 = pts_clean[i-1]
                x1, y1 = pts_clean[i]
                current_angle = angles[i-1]  # Angle for current segment (from i-1 to i)
                prev_angle = angles[i-2] if i > 1 else angles[-1]  # Angle for previous segment
                
                # Calculate angle change in degrees
                angle_change_rad = abs(current_angle - prev_angle)
                # Normalize to handle angle wrapping (e.g., 179° to -179°)
                if angle_change_rad > math.pi:
                    angle_change_rad = 2 * math.pi - angle_change_rad
                angle_change_deg = math.degrees(angle_change_rad)
                
                # Z up if angle change > 2 degrees, Z down if cutting (small angle change)
                if angle_change_deg > angle_change_threshold_deg:
                    path.append((x0, y0, current_angle, 1))  # Z up for large angle change
                    path.append((x0, y0, current_angle, 0))  # Z down to continue cutting
                
                path.append((x1, y1, current_angle, 0))  # Move/cut
            
            # End with last point (Z up)
            path.append((pts_clean[-1][0], pts_clean[-1][1], angles[-1], 1))  # Z up at end
            
            print(f"Generated toolpath: {len(path)} points")
            for j, (x, y, angle, z) in enumerate(path):
                x_mm = x * INCH_TO_MM
                y_mm = y * INCH_TO_MM
                angle_deg = math.degrees(angle)
                z_pos = "UP" if z == 1 else "DOWN"
                print(f"  Point {j+1}: X={x_mm:.2f}mm ({x:.3f}in), Y={y_mm:.2f}mm ({y:.3f}in), Angle={angle_deg:.1f}°, Z={z_pos}")
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_angle_calculation() 