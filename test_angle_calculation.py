#!/usr/bin/env python3
"""
Test angle calculation with exact coordinates from CSV
"""

import math

def calculate_angle_change(points, point_index):
    """Calculate angle change at a specific point using the same logic as toolpath_generator."""
    if point_index == 0 or point_index >= len(points) - 1:
        return 0.0
    
    # Get three consecutive points
    prev_point = points[point_index - 1]
    current_point = points[point_index]
    next_point = points[point_index + 1]
    
    # Calculate vectors
    v1 = (current_point[0] - prev_point[0], current_point[1] - prev_point[1])
    v2 = (next_point[0] - current_point[0], next_point[1] - current_point[1])
    
    # Calculate magnitudes
    mag1 = math.sqrt(v1[0]**2 + v1[1]**2)
    mag2 = math.sqrt(v2[0]**2 + v2[1]**2)
    
    if mag1 == 0 or mag2 == 0:
        return 0.0
    
    # Calculate dot product
    dot_product = v1[0] * v2[0] + v1[1] * v2[1]
    
    # Calculate angle
    cos_angle = dot_product / (mag1 * mag2)
    cos_angle = max(-1, min(1, cos_angle))  # Clamp to [-1, 1]
    
    angle = math.acos(cos_angle)
    
    # Determine sign using cross product
    cross_product = v1[0] * v2[1] - v1[1] * v2[0]
    if cross_product < 0:
        angle = -angle
    
    return angle

# Test with exact coordinates from CSV
points = [
    (-10.443153, -22.802624),  # Point 0
    (-10.443153, -23.927624),  # Point 1
    (-10.443153, -38.852624),  # Point 2 - end of vertical line
    (-5.375440, -38.852624),   # Point 3 - start of horizontal line
    (-5.375440, -25.977624),   # Point 4 - end of horizontal line
    (-5.376626, -25.885279),   # Point 5 - start of curve
    (-5.379161, -25.819503),   # Point 6
    (-5.384213, -25.740841),   # Point 7
    (-5.393610, -25.636360),   # Point 8
    (-5.410000, -25.507000),   # Point 9
    (-5.438000, -25.353000),   # Point 10
    (-5.474000, -25.200000),   # Point 11
    (-5.531000, -25.000000),   # Point 12
    (-5.622000, -24.756000),   # Point 13
    (-5.736000, -24.522000),   # Point 14
    (-5.842000, -24.342000),   # Point 15
    (-5.928000, -24.210000),   # Point 16
    (-6.020000, -24.083000),   # Point 17
    (-6.103000, -23.980000),   # Point 18
    (-6.173000, -23.900000),   # Point 19
    (-6.240000, -23.850000),   # Point 20
    (-6.300000, -23.820000),   # Point 21
    (-6.350000, -23.800000),   # Point 22
    (-6.400000, -23.790000),   # Point 23
    (-6.450000, -23.785000),   # Point 24
    (-6.500000, -23.783000),   # Point 25
    (-6.550000, -23.785000),   # Point 26
    (-6.600000, -23.790000),   # Point 27
    (-6.650000, -23.800000),   # Point 28
    (-6.700000, -23.820000),   # Point 29
    (-6.750000, -23.850000),   # Point 30
    (-6.800000, -23.900000),   # Point 31
    (-6.850000, -23.980000),   # Point 32
    (-6.900000, -24.083000),   # Point 33
    (-7.000000, -24.210000),   # Point 34
    (-7.100000, -24.342000),   # Point 35
    (-7.200000, -24.522000),   # Point 36
    (-7.300000, -24.756000),   # Point 37
    (-7.400000, -25.000000),   # Point 38
    (-7.500000, -25.200000),   # Point 39
    (-7.600000, -25.353000),   # Point 40
    (-7.700000, -25.507000),   # Point 41
    (-8.407015, -22.810997),   # Point 38
    (-8.487479, -22.806176),   # Point 39
    (-8.554759, -22.803756),   # Point 40
    (-8.608694, -22.802786),   # Point 41 - last curve point
    (-10.443153, -22.802624),  # Point 42 - final point (should be corner)
]

print("Angle calculations:")
for i in range(1, len(points) - 1):
    angle_rad = calculate_angle_change(points, i)
    angle_deg = math.degrees(abs(angle_rad))
    print(f"Point {i}: {angle_deg:.3f}°")
    
    # Print the three points being used
    prev = points[i-1]
    curr = points[i]
    next_pt = points[i+1]
    print(f"  Using: ({prev[0]:.3f}, {prev[1]:.3f}) -> ({curr[0]:.3f}, {curr[1]:.3f}) -> ({next_pt[0]:.3f}, {next_pt[1]:.3f})")
    print() 