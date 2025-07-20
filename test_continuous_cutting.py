#!/usr/bin/env python3
"""
Standalone test script for continuous cutting functions.
Tests the new continuous cutting approach for splines, circles, and arcs.
"""

import sys
import os
import math
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def calculate_angle_between_points(p1, p2, p3):
    """Calculate the angle between three points (p1 -> p2 -> p3) in degrees."""
    if p1 == p2 or p2 == p3:
        return 0.0
    
    # Vector from p1 to p2
    v1x = p2[0] - p1[0]
    v1y = p2[1] - p1[1]
    
    # Vector from p2 to p3
    v2x = p3[0] - p2[0]
    v2y = p3[1] - p2[1]
    
    # Calculate dot product
    dot_product = v1x * v2x + v1y * v2y
    
    # Calculate magnitudes
    mag1 = math.sqrt(v1x * v1x + v1y * v1y)
    mag2 = math.sqrt(v2x * v2x + v2y * v2y)
    
    if mag1 == 0 or mag2 == 0:
        return 0.0
    
    # Calculate cosine of angle
    cos_angle = dot_product / (mag1 * mag2)
    
    # Clamp to valid range
    cos_angle = max(-1.0, min(1.0, cos_angle))
    
    # Convert to degrees
    angle_rad = math.acos(cos_angle)
    angle_deg = math.degrees(angle_rad)
    
    return angle_deg

def generate_continuous_circle_toolpath(center, radius, start_angle=0, end_angle=2*math.pi, step_size=0.01):
    """
    Generate continuous toolpath for a circle using parametric equations.
    
    Args:
        center: (x, y) center point
        radius: radius of circle
        start_angle: starting angle in radians (default: 0)
        end_angle: ending angle in radians (default: 2π for full circle)
        step_size: distance between points in inches (default: 0.01")
    
    Returns:
        List of (x, y, angle, z) tuples for continuous cutting
    """
    cx, cy = center
    toolpath = []
    
    # Calculate number of steps based on circumference and step size
    circumference = radius * abs(end_angle - start_angle)
    num_steps = max(256, int(circumference / step_size))  # Increased minimum steps for better angle continuity
    
    # Generate points using parametric equations
    for i in range(num_steps + 1):
        t = i / num_steps
        angle = start_angle + t * (end_angle - start_angle)
        
        # Parametric equations for circle
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        
        # Calculate tangent angle (perpendicular to radius)
        tangent_angle = angle + math.pi/2  # 90° from radius
        
        # Normalize angle to -180 to +180 range
        while tangent_angle > math.pi:
            tangent_angle -= 2 * math.pi
        while tangent_angle < -math.pi:
            tangent_angle += 2 * math.pi
        
        # Convert to absolute angle from vertical (home orientation)
        absolute_angle = -(math.degrees(tangent_angle) - 90.0)
        while absolute_angle > 180:
            absolute_angle -= 360
        while absolute_angle < -180:
            absolute_angle += 360
        
        # Z=0 for continuous cutting (no lifting)
        toolpath.append((x, y, math.radians(absolute_angle), 0))
    
    return toolpath

def generate_continuous_spline_toolpath(spline, step_size=0.01):
    """
    Generate continuous toolpath for a spline using high-resolution flattening.
    
    Args:
        spline: ezdxf spline entity
        step_size: distance between points in inches (default: 0.01")
    
    Returns:
        List of (x, y, angle, z) tuples for continuous cutting
    """
    toolpath = []
    
    try:
        # Use high-resolution flattening for smooth splines
        points = list(spline.flattening(0.001))  # Very high precision
        
        if len(points) < 2:
            return toolpath
        
        # Calculate total length
        total_length = 0
        for i in range(1, len(points)):
            dx = points[i][0] - points[i-1][0]
            dy = points[i][1] - points[i-1][1]
            total_length += math.sqrt(dx*dx + dy*dy)
        
        # Calculate number of steps based on length and step size
        num_steps = max(128, int(total_length / step_size))
        
        # Interpolate points along the spline
        for i in range(num_steps + 1):
            t = i / num_steps
            
            # Find the segment and interpolate within it
            segment_idx = int(t * (len(points) - 1))
            segment_t = t * (len(points) - 1) - segment_idx
            
            if segment_idx >= len(points) - 1:
                segment_idx = len(points) - 2
                segment_t = 1.0
            
            # Linear interpolation between points
            p1 = points[segment_idx]
            p2 = points[segment_idx + 1]
            x = p1[0] + segment_t * (p2[0] - p1[0])
            y = p1[1] + segment_t * (p2[1] - p1[1])
            
            # Calculate tangent vector
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            tangent_angle = math.atan2(dy, dx)
            
            # Convert to absolute angle from vertical (home orientation)
            absolute_angle = -(math.degrees(tangent_angle) - 90.0)
            while absolute_angle > 180:
                absolute_angle -= 360
            while absolute_angle < -180:
                absolute_angle += 360
            
            # Z=0 for continuous cutting (no lifting)
            toolpath.append((x, y, math.radians(absolute_angle), 0))
        
    except Exception as e:
        logger.error(f"Error generating continuous spline toolpath: {e}")
        # Fallback to discrete method
        points = list(spline.flattening(0.001))
        for i in range(1, len(points)):
            x, y = points[i][0], points[i][1]
            prev_x, prev_y = points[i-1][0], points[i-1][1]
            
            # Calculate tangent angle
            dx = x - prev_x
            dy = y - prev_y
            tangent_angle = math.atan2(dy, dx)
            
            # Convert to absolute angle
            absolute_angle = -(math.degrees(tangent_angle) - 90.0)
            while absolute_angle > 180:
                absolute_angle -= 360
            while absolute_angle < -180:
                absolute_angle += 360
            
            toolpath.append((x, y, math.radians(absolute_angle), 0))
    
    return toolpath

def test_continuous_cutting():
    """Test the new continuous cutting functions."""
    
    # Test file path
    dxf_file = "/home/fabric/Desktop/DXF/circle_test_formatted.dxf"
    
    print(f"Testing continuous cutting with file: {dxf_file}")
    print("=" * 60)
    
    try:
        # Import ezdxf here to avoid dependency issues
        import ezdxf
        
        # Load DXF file
        doc = ezdxf.readfile(dxf_file)
        msp = doc.modelspace()
        
        # Get all entities
        entities = list(msp)
        supported_entities = [e for e in entities if e.dxftype() in ['LINE', 'LWPOLYLINE', 'POLYLINE', 'SPLINE', 'ARC', 'CIRCLE']]
        
        print(f"Found {len(supported_entities)} supported entities:")
        for i, e in enumerate(supported_entities):
            print(f"  {i+1}. {e.dxftype()}")
        
        # Test continuous cutting for each entity
        for i, e in enumerate(supported_entities):
            t = e.dxftype()
            print(f"\n--- Testing {t} {i+1} ---")
            
            if t == 'SPLINE':
                print("  Generating continuous SPLINE toolpath...")
                continuous_path = generate_continuous_spline_toolpath(e, step_size=0.01)
                print(f"  Generated {len(continuous_path)} continuous points")
                
                # Show first few points
                for j, (x, y, angle, z) in enumerate(continuous_path[:5]):
                    angle_deg = math.degrees(angle)
                    z_pos = "UP" if z == 1 else "DOWN"
                    print(f"    Point {j+1}: ({x:.3f}, {y:.3f}), Angle={angle_deg:.1f}°, Z={z_pos}")
                if len(continuous_path) > 5:
                    print(f"    ... and {len(continuous_path)-5} more points")
                
            elif t == 'CIRCLE':
                center = e.dxf.center
                radius = e.dxf.radius
                print(f"  Generating continuous CIRCLE toolpath: center=({center.x}, {center.y}), radius={radius}")
                
                continuous_path = generate_continuous_circle_toolpath(
                    (center.x, center.y), radius, 
                    start_angle=0, end_angle=2*math.pi, 
                    step_size=0.01
                )
                print(f"  Generated {len(continuous_path)} continuous points")
                
                # Show first few points
                for j, (x, y, angle, z) in enumerate(continuous_path[:5]):
                    angle_deg = math.degrees(angle)
                    z_pos = "UP" if z == 1 else "DOWN"
                    print(f"    Point {j+1}: ({x:.3f}, {y:.3f}), Angle={angle_deg:.1f}°, Z={z_pos}")
                if len(continuous_path) > 5:
                    print(f"    ... and {len(continuous_path)-5} more points")
                
            elif t == 'ARC':
                center = e.dxf.center
                radius = e.dxf.radius
                start_angle = math.radians(e.dxf.start_angle)
                end_angle = math.radians(e.dxf.end_angle)
                
                if end_angle < start_angle:
                    end_angle += 2 * math.pi
                
                print(f"  Generating continuous ARC toolpath: center=({center.x}, {center.y}), radius={radius}, angles={math.degrees(start_angle):.1f}° to {math.degrees(end_angle):.1f}°")
                
                continuous_path = generate_continuous_circle_toolpath(
                    (center.x, center.y), radius,
                    start_angle=start_angle, end_angle=end_angle,
                    step_size=0.01
                )
                print(f"  Generated {len(continuous_path)} continuous points")
                
                # Show first few points
                for j, (x, y, angle, z) in enumerate(continuous_path[:5]):
                    angle_deg = math.degrees(angle)
                    z_pos = "UP" if z == 1 else "DOWN"
                    print(f"    Point {j+1}: ({x:.3f}, {y:.3f}), Angle={angle_deg:.1f}°, Z={z_pos}")
                if len(continuous_path) > 5:
                    print(f"    ... and {len(continuous_path)-5} more points")
            
            else:
                print(f"  Skipping {t} (uses discrete segmentation)")
        
        # Test angle calculations
        print(f"\n--- Testing Angle Calculations ---")
        test_points = [
            ((0, 0), (1, 0), (2, 0)),  # Straight line
            ((0, 0), (1, 0), (1, 1)),  # 90° turn
            ((0, 0), (1, 0), (0, 1)),  # -90° turn
        ]
        
        for i, (p1, p2, p3) in enumerate(test_points):
            angle = calculate_angle_between_points(p1, p2, p3)
            print(f"  Test {i+1}: {p1} -> {p2} -> {p3} = {angle:.1f}°")
        
        # Test circle generation
        print(f"\n--- Testing Circle Generation ---")
        test_circle = generate_continuous_circle_toolpath((0, 0), 1.0, step_size=0.1)
        print(f"  Generated {len(test_circle)} points for unit circle")
        
        # Check for angle continuity
        print(f"  Checking angle continuity...")
        max_angle_change = 0
        for i in range(1, len(test_circle)):
            prev_angle = math.degrees(test_circle[i-1][2])
            curr_angle = math.degrees(test_circle[i][2])
            angle_change = abs(curr_angle - prev_angle)
            # Handle angle wrapping
            if angle_change > 180:
                angle_change = 360 - angle_change
            max_angle_change = max(max_angle_change, angle_change)
        
        print(f"  Maximum angle change between consecutive points: {max_angle_change:.2f}°")
        if max_angle_change < 2.0:
            print(f"  ✅ Angle changes are all < 2° - continuous cutting achieved!")
        else:
            print(f"  ⚠️  Some angle changes > 2° - may need refinement")
        
        print(f"\n✅ Continuous cutting test completed successfully!")
        
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please install ezdxf: pip install ezdxf")
    except Exception as e:
        print(f"❌ Error testing continuous cutting: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_continuous_cutting() 