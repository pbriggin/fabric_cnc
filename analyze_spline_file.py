#!/usr/bin/env python3
"""
Analyze the specific spline-based circle file to identify center line issues.
"""

import sys
import os
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
    from toolpath_planning import generate_continuous_spline_toolpath
    TOOLPATH_AVAILABLE = True
except ImportError:
    TOOLPATH_AVAILABLE = False
    print("Error: toolpath_planning module not found")
    sys.exit(1)

def analyze_spline_file(file_path):
    """Analyze the specific spline file in detail."""
    print(f"\n🔍 Detailed Analysis of: {file_path}")
    print("=" * 80)
    
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
        
        # Analyze splines in detail
        splines = []
        for e in all_entities:
            if e.dxftype() == 'SPLINE':
                splines.append(e)
        
        print(f"\n📊 Analyzing {len(splines)} SPLINE entities:")
        
        for i, spline in enumerate(splines):
            print(f"\n  SPLINE {i+1}:")
            
            # Get control points
            try:
                control_points = list(spline.control_points)
                print(f"    Control points: {len(control_points)}")
                for j, point in enumerate(control_points[:5]):  # Show first 5
                    print(f"      Control {j+1}: ({point.x:.3f}, {point.y:.3f})")
                if len(control_points) > 5:
                    print(f"      ... and {len(control_points)-5} more control points")
            except:
                print(f"    Could not get control points")
            
            # Flatten spline to points
            try:
                flattened_points = list(spline.flattening(0.1))
                print(f"    Flattened points: {len(flattened_points)}")
                
                # Show first and last few points
                print(f"    First 5 points:")
                for j, point in enumerate(flattened_points[:5]):
                    if len(point) >= 2:
                        print(f"      Point {j+1}: ({point[0]:.3f}, {point[1]:.3f})")
                
                print(f"    Last 5 points:")
                for j, point in enumerate(flattened_points[-5:]):
                    if len(point) >= 2:
                        print(f"      Point {len(flattened_points)-4+j}: ({point[0]:.3f}, {point[1]:.3f})")
                
                # Check if spline forms a closed loop
                if len(flattened_points) >= 2:
                    first_point = flattened_points[0]
                    last_point = flattened_points[-1]
                    if len(first_point) >= 2 and len(last_point) >= 2:
                        distance = math.sqrt((first_point[0] - last_point[0])**2 + (first_point[1] - last_point[1])**2)
                        print(f"    Distance from first to last point: {distance:.3f}")
                        if distance < 0.1:
                            print(f"    ✅ SPLINE appears to be closed")
                        else:
                            print(f"    ⚠️  SPLINE is not closed (gap: {distance:.3f})")
                
                # Check for any points near origin (0,0)
                center_threshold = 0.5
                center_points = []
                for j, point in enumerate(flattened_points):
                    if len(point) >= 2:
                        distance = math.sqrt(point[0]**2 + point[1]**2)
                        if distance < center_threshold:
                            center_points.append((j+1, point[0], point[1], distance))
                
                if center_points:
                    print(f"    ⚠️  Found {len(center_points)} points near origin:")
                    for point_num, x, y, dist in center_points[:3]:  # Show first 3
                        print(f"      Point {point_num}: ({x:.3f}, {y:.3f}) - {dist:.3f} from origin")
                    if len(center_points) > 3:
                        print(f"      ... and {len(center_points)-3} more")
                else:
                    print(f"    ✅ No points near origin (threshold: {center_threshold})")
                
                # Generate toolpath for this spline
                print(f"\n    🔧 Generating toolpath for SPLINE {i+1}:")
                try:
                    toolpath = generate_continuous_spline_toolpath(spline, step_size=0.05)
                    print(f"    Generated {len(toolpath)} toolpath points")
                    
                    if toolpath:
                        print(f"    First 5 toolpath points:")
                        for j, (x, y, angle, z) in enumerate(toolpath[:5]):
                            angle_deg = math.degrees(angle)
                            print(f"      Point {j+1}: X={x:.3f}, Y={y:.3f}, Angle={angle_deg:.1f}°, Z={z}")
                        
                        print(f"    Last 5 toolpath points:")
                        for j, (x, y, angle, z) in enumerate(toolpath[-5:]):
                            angle_deg = math.degrees(angle)
                            print(f"      Point {len(toolpath)-4+j}: X={x:.3f}, Y={y:.3f}, Angle={angle_deg:.1f}°, Z={z}")
                        
                        # Check for any toolpath points near origin
                        center_toolpath_points = []
                        for j, (x, y, angle, z) in enumerate(toolpath):
                            distance = math.sqrt(x**2 + y**2)
                            if distance < center_threshold:
                                center_toolpath_points.append((j+1, x, y, distance))
                        
                        if center_toolpath_points:
                            print(f"    ⚠️  Found {len(center_toolpath_points)} toolpath points near origin:")
                            for point_num, x, y, dist in center_toolpath_points[:3]:
                                print(f"      Toolpath Point {point_num}: ({x:.3f}, {y:.3f}) - {dist:.3f} from origin")
                            if len(center_toolpath_points) > 3:
                                print(f"      ... and {len(center_toolpath_points)-3} more")
                        else:
                            print(f"    ✅ No toolpath points near origin")
                        
                        # Check for large angle changes that might indicate straight lines
                        large_angle_changes = []
                        for j in range(1, len(toolpath)):
                            prev_angle = toolpath[j-1][2]
                            curr_angle = toolpath[j][2]
                            angle_diff = abs(curr_angle - prev_angle)
                            
                            # Normalize angle difference
                            while angle_diff > math.pi:
                                angle_diff = 2 * math.pi - angle_diff
                            
                            if math.degrees(angle_diff) > 15:  # More than 15 degrees
                                large_angle_changes.append((j+1, math.degrees(angle_diff)))
                        
                        if large_angle_changes:
                            print(f"    ⚠️  Found {len(large_angle_changes)} large angle changes:")
                            for point_num, angle_change in large_angle_changes[:3]:
                                print(f"      Point {point_num}: {angle_change:.1f}° change")
                            if len(large_angle_changes) > 3:
                                print(f"      ... and {len(large_angle_changes)-3} more")
                        else:
                            print(f"    ✅ No large angle changes detected")
                    
                except Exception as e:
                    print(f"    ❌ Error generating toolpath: {e}")
                
            except Exception as e:
                print(f"    ❌ Error flattening spline: {e}")
        
        return splines
        
    except Exception as e:
        print(f"Error analyzing file: {e}")
        return []

def main():
    """Main function to analyze the specific file."""
    file_path = "/Users/peterbriggs/Downloads/circle_test_formatted.dxf"
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return
    
    print("🔧 Detailed Spline Analysis Tool")
    print("=" * 80)
    
    splines = analyze_spline_file(file_path)
    
    print(f"\n🎯 Analysis Complete!")
    print(f"\n💡 Recommendations:")
    print(f"1. The file contains SPLINE entities instead of a CIRCLE entity")
    print(f"2. SPLINES may not form perfect circles and can have gaps or center lines")
    print(f"3. Try using a file with a proper CIRCLE entity instead")
    print(f"4. Or use the clean circle file: /Users/peterbriggs/Downloads/circle_test.dxf")

if __name__ == "__main__":
    main() 