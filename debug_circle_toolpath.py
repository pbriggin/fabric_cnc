#!/usr/bin/env python3
"""
Debug script to analyze circle toolpath generation and identify center line issues.
"""

import sys
import os
import logging
import math

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import ezdxf
    from ezdxf import readfile
    EZDXF_AVAILABLE = True
except ImportError:
    EZDXF_AVAILABLE = False
    print("Error: ezdxf not found. Install with: pip install ezdxf")
    sys.exit(1)

try:
    from toolpath_planning import generate_continuous_circle_toolpath
    TOOLPATH_AVAILABLE = True
except ImportError:
    TOOLPATH_AVAILABLE = False
    print("Error: toolpath_planning module not found")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def analyze_dxf_file(file_path):
    """Analyze a DXF file to identify all entities and their properties."""
    print(f"\n🔍 Analyzing DXF file: {file_path}")
    print("=" * 60)
    
    try:
        doc = readfile(file_path)
        msp = doc.modelspace()
        
        # Find all entities
        all_entities = []
        for e in msp:
            all_entities.append(e)
        
        print(f"Total entities in DXF: {len(all_entities)}")
        
        # Analyze entity types
        entity_types = {}
        for e in all_entities:
            t = e.dxftype()
            entity_types[t] = entity_types.get(t, 0) + 1
        
        print(f"Entity types found: {entity_types}")
        
        # Analyze supported entities in detail
        supported_entities = []
        for e in all_entities:
            t = e.dxftype()
            if t in ('LINE', 'LWPOLYLINE', 'POLYLINE', 'SPLINE', 'ARC', 'CIRCLE'):
                supported_entities.append(e)
                
                if t == 'LINE':
                    start = e.dxf.start
                    end = e.dxf.end
                    print(f"  LINE: ({start.x:.3f}, {start.y:.3f}) to ({end.x:.3f}, {end.y:.3f})")
                    
                elif t == 'CIRCLE':
                    center = e.dxf.center
                    radius = e.dxf.radius
                    print(f"  CIRCLE: center=({center.x:.3f}, {center.y:.3f}), radius={radius:.3f}")
                    
                elif t == 'ARC':
                    center = e.dxf.center
                    radius = e.dxf.radius
                    start_angle = e.dxf.start_angle
                    end_angle = e.dxf.end_angle
                    print(f"  ARC: center=({center.x:.3f}, {center.y:.3f}), radius={radius:.3f}, angles={start_angle:.1f}° to {end_angle:.1f}°")
                    
                elif t in ('LWPOLYLINE', 'POLYLINE'):
                    if t == 'LWPOLYLINE':
                        points = [p[:2] for p in e.get_points()]
                    else:
                        points = [(v.dxf.x, v.dxf.y) for v in e.vertices()]
                    print(f"  {t}: {len(points)} points")
                    if len(points) <= 4:
                        for i, (x, y) in enumerate(points):
                            print(f"    Point {i+1}: ({x:.3f}, {y:.3f})")
                    
                elif t == 'SPLINE':
                    print(f"  SPLINE: {len(list(e.flattening(0.1)))} flattened points")
        
        print(f"\nSupported entities for toolpath generation: {len(supported_entities)}")
        
        return supported_entities
        
    except Exception as e:
        print(f"Error analyzing DXF file: {e}")
        return []

def test_circle_toolpath_generation():
    """Test circle toolpath generation with detailed analysis."""
    print(f"\n🔵 Testing Circle Toolpath Generation")
    print("=" * 60)
    
    # Test parameters
    center = (0, 0)
    radius = 10
    start_angle = 0
    end_angle = 2 * math.pi
    
    print(f"Circle: center={center}, radius={radius}")
    print(f"Angles: {math.degrees(start_angle):.1f}° to {math.degrees(end_angle):.1f}°")
    
    # Generate toolpath
    toolpath = generate_continuous_circle_toolpath(center, radius, start_angle, end_angle)
    
    print(f"Generated {len(toolpath)} points")
    
    # Analyze the toolpath for potential issues
    if toolpath:
        print(f"\nFirst 10 points:")
        for i, (x, y, angle, z) in enumerate(toolpath[:10]):
            angle_deg = math.degrees(angle)
            print(f"  Point {i+1}: X={x:.3f}, Y={y:.3f}, Angle={angle_deg:.1f}°, Z={z}")
        
        print(f"\nLast 10 points:")
        for i, (x, y, angle, z) in enumerate(toolpath[-10:]):
            angle_deg = math.degrees(angle)
            print(f"  Point {len(toolpath)-9+i}: X={x:.3f}, Y={y:.3f}, Angle={angle_deg:.1f}°, Z={z}")
        
        # Check for any points at or near the center
        center_threshold = 0.1  # 0.1 inch from center
        center_points = []
        for i, (x, y, angle, z) in enumerate(toolpath):
            distance_from_center = math.sqrt(x*x + y*y)
            if distance_from_center < center_threshold:
                center_points.append((i+1, x, y, distance_from_center))
        
        if center_points:
            print(f"\n⚠️  WARNING: Found {len(center_points)} points near the center:")
            for point_num, x, y, dist in center_points:
                print(f"  Point {point_num}: ({x:.3f}, {y:.3f}) - {dist:.3f} from center")
        else:
            print(f"\n✅ No points found near the center (threshold: {center_threshold} inch)")
        
        # Check for any straight lines (large angle changes)
        large_angle_changes = []
        for i in range(1, len(toolpath)):
            prev_angle = toolpath[i-1][2]
            curr_angle = toolpath[i][2]
            angle_diff = abs(curr_angle - prev_angle)
            
            # Normalize angle difference
            while angle_diff > math.pi:
                angle_diff = 2 * math.pi - angle_diff
            
            if math.degrees(angle_diff) > 10:  # More than 10 degrees
                large_angle_changes.append((i+1, math.degrees(angle_diff)))
        
        if large_angle_changes:
            print(f"\n⚠️  WARNING: Found {len(large_angle_changes)} large angle changes:")
            for point_num, angle_change in large_angle_changes[:5]:  # Show first 5
                print(f"  Point {point_num}: {angle_change:.1f}° change")
            if len(large_angle_changes) > 5:
                print(f"  ... and {len(large_angle_changes)-5} more")
        else:
            print(f"\n✅ No large angle changes detected")

def main():
    """Main function to run the debug analysis."""
    print("🔧 Fabric CNC Circle Toolpath Debug Tool")
    print("=" * 60)
    
    # Test basic circle toolpath generation
    test_circle_toolpath_generation()
    
    # Analyze test files if they exist
    test_files = [
        "test_files/test_circle.dxf",
        "test_files/test_complex.dxf"
    ]
    
    for test_file in test_files:
        if os.path.exists(test_file):
            analyze_dxf_file(test_file)
    
    # Check for user's DXF files
    user_dirs = [
        os.path.expanduser("~/Desktop/DXF"),
        os.path.expanduser("~/Downloads")
    ]
    
    for user_dir in user_dirs:
        if os.path.exists(user_dir):
            dxf_files = [f for f in os.listdir(user_dir) if f.lower().endswith('.dxf')]
            if dxf_files:
                print(f"\n📁 Found DXF files in {user_dir}:")
                for dxf_file in dxf_files[:3]:  # Show first 3
                    file_path = os.path.join(user_dir, dxf_file)
                    analyze_dxf_file(file_path)
                if len(dxf_files) > 3:
                    print(f"  ... and {len(dxf_files)-3} more files")
    
    print(f"\n🎯 Debug Analysis Complete!")
    print(f"\nTo fix the center line issue:")
    print(f"1. Check if your DXF contains multiple entities")
    print(f"2. Look for LINE entities that might go through the center")
    print(f"3. Ensure your circle is a single CIRCLE entity, not multiple lines")
    print(f"4. Try importing a simple circle DXF file")

if __name__ == "__main__":
    main() 