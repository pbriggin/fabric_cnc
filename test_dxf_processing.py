#!/usr/bin/env python3

import os
import sys
import math
import logging
from collections import defaultdict

# Add the current directory to the path so we can import ezdxf
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import ezdxf
    from ezdxf import readfile
except ImportError:
    print("ezdxf not found. Please install it: pip install ezdxf")
    sys.exit(1)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

def calculate_angle_between_points(p1, p2, p3):
    """Calculate the angle between three points (p1 -> p2 -> p3) in degrees."""
    if p1 == p2 or p2 == p3:
        return 0.0
    
    # Calculate vectors
    v1 = (p1[0] - p2[0], p1[1] - p2[1])
    v2 = (p3[0] - p2[0], p3[1] - p2[1])
    
    # Calculate dot product
    dot_product = v1[0] * v2[0] + v1[1] * v2[1]
    
    # Calculate magnitudes
    mag1 = math.sqrt(v1[0]**2 + v1[1]**2)
    mag2 = math.sqrt(v2[0]**2 + v2[1]**2)
    
    if mag1 == 0 or mag2 == 0:
        return 0.0
    
    # Calculate angle
    cos_angle = dot_product / (mag1 * mag2)
    cos_angle = max(-1.0, min(1.0, cos_angle))  # Clamp to [-1, 1]
    angle_rad = math.acos(cos_angle)
    angle_deg = math.degrees(angle_rad)
    
    return angle_deg

def flatten_spline_with_angle_limit(spline, max_angle_deg=2.0):
    """Flatten a spline ensuring maximum angle between segments is less than max_angle_deg."""
    # Start with a coarse tolerance to get initial points
    coarse_tolerance = 0.1
    points = list(spline.flattening(coarse_tolerance))
    
    if len(points) < 3:
        return points
    
    # Refine points to meet angle requirement
    refined_points = [points[0]]
    
    for i in range(1, len(points) - 1):
        p1 = refined_points[-1]
        p2 = points[i]
        p3 = points[i + 1]
        
        angle = calculate_angle_between_points(p1, p2, p3)
        
        if angle > max_angle_deg:
            # Need to add more points between p1 and p2
            # Use finer tolerance for this segment
            fine_tolerance = 0.001
            segment_points = list(spline.flattening(fine_tolerance))
            
            # Find points between p1 and p2
            start_idx = None
            end_idx = None
            
            for j, pt in enumerate(segment_points):
                if abs(pt[0] - p1[0]) < 0.001 and abs(pt[1] - p1[1]) < 0.001:
                    start_idx = j
                if abs(pt[0] - p2[0]) < 0.001 and abs(pt[1] - p2[1]) < 0.001:
                    end_idx = j
                    break
            
            if start_idx is not None and end_idx is not None:
                # Add intermediate points
                for k in range(start_idx + 1, end_idx):
                    refined_points.append(segment_points[k])
        
        refined_points.append(p2)
    
    # Add the last point
    refined_points.append(points[-1])
    
    return refined_points

def test_dxf_processing(dxf_file_path):
    """Test DXF processing logic without GUI dependencies."""
    
    print(f"Testing DXF file: {dxf_file_path}")
    print("=" * 60)
    
    try:
        doc = readfile(dxf_file_path)
        msp = doc.modelspace()
        
        # Support LINE, LWPOLYLINE, POLYLINE, SPLINE, ARC, CIRCLE
        entities = []
        for e in msp:
            t = e.dxftype()
            if t in ('LINE', 'LWPOLYLINE', 'POLYLINE', 'SPLINE', 'ARC', 'CIRCLE'):
                entities.append(e)
        
        if not entities:
            print("ERROR: No supported entities found in DXF file.")
            return
        
        print(f"Found {len(entities)} supported entities:")
        for i, e in enumerate(entities):
            print(f"  {i+1}. {e.dxftype()}")
        
        # Detect units
        insunits = doc.header.get('$INSUNITS', 0)
        # 1 = inches, 4 = mm, 0 = unitless (assume inches)
        if insunits == 4:
            dxf_unit_scale = 1.0 / 25.4  # mm to in
        else:
            dxf_unit_scale = 1.0  # inches or unitless
        
        print(f"Unit scale: {dxf_unit_scale}")
        
        # Normalize all points to inches and calculate bounding box
        all_x, all_y = [], []
        print(f"\nProcessing {len(entities)} entities for bounding box calculation")
        
        for i, e in enumerate(entities):
            t = e.dxftype()
            print(f"Processing entity {i+1}/{len(entities)}: {t}")
            
            if t == 'LINE':
                all_x.extend([e.dxf.start.x * dxf_unit_scale, e.dxf.end.x * dxf_unit_scale])
                all_y.extend([e.dxf.start.y * dxf_unit_scale, e.dxf.end.y * dxf_unit_scale])
                
            elif t in ('LWPOLYLINE', 'POLYLINE'):
                pts = [p[:2] for p in e.get_points()] if t == 'LWPOLYLINE' else [(v.dxf.x, v.dxf.y) for v in e.vertices()]
                for x, y in pts:
                    all_x.append(x * dxf_unit_scale)
                    all_y.append(y * dxf_unit_scale)
                    
            elif t == 'CIRCLE':
                center = e.dxf.center
                r = e.dxf.radius
                print(f"  CIRCLE: center=({center.x}, {center.y}), radius={r}")
                # Calculate segments based on angle requirement
                max_angle_deg = 2.0
                circumference = 2 * math.pi * r
                # For a circle, angle between segments = 360 / n
                # We want angle < max_angle_deg, so n > 360 / max_angle_deg
                min_segments = int(360 / max_angle_deg) + 1
                n = max(min_segments, 128)  # At least 128 segments
                n = min(n, 512)  # Max 512 segments
                print(f"    Circle segments: {n} (max angle: {360/n:.2f}°)")
                for i in range(n):
                    angle = 2 * math.pi * i / n
                    x = center.x + r * math.cos(angle)
                    y = center.y + r * math.sin(angle)
                    all_x.append(x * dxf_unit_scale)
                    all_y.append(y * dxf_unit_scale)
                    
            elif t == 'SPLINE':
                print(f"  Processing SPLINE")
                max_angle_deg = 2.0
                pts = flatten_spline_with_angle_limit(e, max_angle_deg)
                for pt in pts:
                    if len(pt) >= 2:
                        all_x.append(pt[0] * dxf_unit_scale)
                        all_y.append(pt[1] * dxf_unit_scale)
                print(f"    Generated {len(pts)} points from spline (max angle: {max_angle_deg}°)")
        
        print(f"Collected {len(all_x)} points for bounding box calculation")
        
        if not all_x or not all_y:
            print("ERROR: No valid points found in DXF file for bounding box calculation")
            return
            
        min_x = min(all_x)
        min_y = min(all_y)
        max_x = max(all_x)
        max_y = max(all_y)
        
        # Add 1-inch buffer around the DXF content
        buffer_inches = 1.0
        dxf_offset = (min_x - buffer_inches, min_y - buffer_inches)
        
        print(f"\nBounding box results:")
        print(f"  Original extents: min_x={min_x:.3f}, min_y={min_y:.3f}, max_x={max_x:.3f}, max_y={max_y:.3f}")
        print(f"  Buffered extents: min_x={min_x - buffer_inches:.3f}, min_y={min_y - buffer_inches:.3f}, max_x={max_x + buffer_inches:.3f}, max_y={max_y + buffer_inches:.3f}")
        print(f"  Offset with buffer: dx={dxf_offset[0]:.3f}, dy={dxf_offset[1]:.3f}")
        
        # Now test toolpath generation
        print(f"\n" + "=" * 60)
        print("TESTING TOOLPATH GENERATION")
        print("=" * 60)
        
        # Flatten all entities into segments
        segments = []
        print(f"Flattening {len(entities)} entities into segments")
        
        for i, e in enumerate(entities):
            t = e.dxftype()
            print(f"Processing entity {i+1}/{len(entities)}: {t}")
            
            if t == 'LINE':
                x1, y1 = e.dxf.start.x, e.dxf.start.y
                x2, y2 = e.dxf.end.x, e.dxf.end.y
                segments.append(((x1, y1), (x2, y2)))
                
            elif t == 'LWPOLYLINE':
                pts = [p[:2] for p in e.get_points()]
                for i in range(1, len(pts)):
                    segments.append((pts[i-1], pts[i]))
                if getattr(e, 'closed', False) or (len(pts) > 2 and pts[0] == pts[-1]):
                    segments.append((pts[-1], pts[0]))
                    
            elif t == 'POLYLINE':
                pts = [(v.dxf.x, v.dxf.y) for v in e.vertices()]
                for i in range(1, len(pts)):
                    segments.append((pts[i-1], pts[i]))
                if getattr(e, 'is_closed', False) or (len(pts) > 2 and pts[0] == pts[-1]):
                    segments.append((pts[-1], pts[0]))
                    
            elif t == 'SPLINE':
                max_angle_deg = 2.0
                pts = flatten_spline_with_angle_limit(e, max_angle_deg)
                pts = [(p[0], p[1]) for p in pts]
                print(f"  SPLINE: flattened to {len(pts)} points (max angle: {max_angle_deg}°)")
                for i in range(1, len(pts)):
                    segments.append((pts[i-1], pts[i]))
                    
            elif t == 'ARC':
                center = e.dxf.center
                r = e.dxf.radius
                start = math.radians(e.dxf.start_angle)
                end = math.radians(e.dxf.end_angle)
                if end < start:
                    end += 2 * math.pi
                
                # Calculate segments based on angle requirement
                max_angle_deg = 2.0
                arc_angle_rad = end - start
                arc_angle_deg = math.degrees(arc_angle_rad)
                min_segments = int(arc_angle_deg / max_angle_deg) + 1
                n = max(min_segments, 64)  # At least 64 segments
                n = min(n, 512)  # Max 512 segments
                print(f"  ARC: {arc_angle_deg:.1f}° arc, {n} segments (max angle: {arc_angle_deg/n:.2f}°)")
                
                pts = [(center.x + r * math.cos(start + (end - start) * i / n),
                        center.y + r * math.sin(start + (end - start) * i / n)) for i in range(n+1)]
                for i in range(1, len(pts)):
                    segments.append((pts[i-1], pts[i]))
                    
            elif t == 'CIRCLE':
                center = e.dxf.center
                r = e.dxf.radius
                # Calculate segments based on angle requirement
                max_angle_deg = 2.0
                min_segments = int(360 / max_angle_deg) + 1
                n = max(min_segments, 128)  # At least 128 segments
                n = min(n, 512)  # Max 512 segments
                print(f"  Circle: radius={r:.3f}, radius_inches={r * dxf_unit_scale:.3f}, segments={n} (max angle: {360/n:.2f}°)")
                pts = [(center.x + r * math.cos(2 * math.pi * i / n),
                        center.y + r * math.sin(2 * math.pi * i / n)) for i in range(n+1)]
                for i in range(1, len(pts)):
                    segments.append((pts[i-1], pts[i]))
                print(f"    Added {len(pts)-1} circle segments")
        
        print(f"Total segments created: {len(segments)}")
        
        # Group segments into shapes by connectivity
        point_map = defaultdict(list)
        seg_indices = list(range(len(segments)))
        
        for idx, (p1, p2) in enumerate(segments):
            p1r = (round(p1[0], 6), round(p1[1], 6))
            p2r = (round(p2[0], 6), round(p2[1], 6))
            point_map[p1r].append((idx, p2r))
            point_map[p2r].append((idx, p1r))
        
        visited = set()
        shapes = []
        
        print(f"Processing {len(segments)} segments into shapes")
        
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
                    
            deduped = [shape[0]]
            for pt in shape[1:]:
                if pt != deduped[-1]:
                    deduped.append(pt)
                    
            shapes.append(deduped)
            print(f"Created shape {len(shapes)} with {len(deduped)} points")
        
        print(f"Total shapes created: {len(shapes)}")
        
        # Test the shape merging logic
        print(f"\nTesting shape merging logic...")
        
        if len(shapes) > 1:
            print("Checking for similar shapes to merge...")
            merged_shapes = []
            used_indices = set()
            
            for i, shape1 in enumerate(shapes):
                if i in used_indices:
                    continue
                    
                print(f"  Checking shape {i+1} against others...")
                
                # Check if this shape is similar to any other shape
                similar_found = False
                for j, shape2 in enumerate(shapes[i+1:], i+1):
                    if j in used_indices:
                        continue
                        
                    print(f"    Comparing shape {i+1} ({len(shape1)} points) with shape {j+1} ({len(shape2)} points)")
                    
                    # Check if shapes are similar (same number of points and similar bounding box)
                    if len(shape1) == len(shape2):
                        # Calculate bounding boxes
                        x1_min, y1_min = min(p[0] for p in shape1), min(p[1] for p in shape1)
                        x1_max, y1_max = max(p[0] for p in shape1), max(p[1] for p in shape1)
                        x2_min, y2_min = min(p[0] for p in shape2), min(p[1] for p in shape2)
                        x2_max, y2_max = max(p[0] for p in shape2), max(p[1] for p in shape2)
                        
                        print(f"      Shape {i+1} bbox: ({x1_min:.3f}, {y1_min:.3f}) to ({x1_max:.3f}, {y1_max:.3f})")
                        print(f"      Shape {j+1} bbox: ({x2_min:.3f}, {y2_min:.3f}) to ({x2_max:.3f}, {y2_max:.3f})")
                        
                        # Check if bounding boxes are very similar (within 0.1 inches)
                        x_diff = abs(x1_min - x2_min) + abs(x1_max - x2_max)
                        y_diff = abs(y1_min - y2_min) + abs(y1_max - y2_max)
                        
                        print(f"      Differences: x={x_diff:.3f}, y={y_diff:.3f}")
                        
                        if (abs(x1_min - x2_min) < 0.1 and abs(y1_min - y2_min) < 0.1 and
                            abs(x1_max - x2_max) < 0.1 and abs(y1_max - y2_max) < 0.1):
                            print(f"      Found similar shapes {i+1} and {j+1}, merging...")
                            # Use the first shape and mark the second as used
                            used_indices.add(j)
                            similar_found = True
                            break
                        else:
                            print(f"      Shapes are different")
                
                # Always add the current shape to merged_shapes (either it's unique or it's the one we're keeping)
                print(f"    Adding shape {i+1} to merged shapes")
                merged_shapes.append(shape1)
                used_indices.add(i)
            
            shapes = merged_shapes
            print(f"After merging: {len(shapes)} shapes remaining")
        else:
            print("Only one shape, no merging needed")
        
        print(f"\nFinal result: {len(shapes)} shapes")
        for i, shape in enumerate(shapes):
            print(f"  Shape {i+1}: {len(shape)} points")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    dxf_file = "/home/fabric/Desktop/DXF/circle_test_formatted.dxf"
    test_dxf_processing(dxf_file) 