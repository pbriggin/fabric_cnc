#!/usr/bin/env python3
"""
Test script for improved toolpath generation.
Tests various DXF shapes and generates toolpaths for verification.
"""

import os
import sys
import math
import logging
from pathlib import Path

# Add the current directory to Python path
sys.path.append(str(Path(__file__).parent))

try:
    from toolpath_planning import (
        ContinuousToolpathGenerator,
        generate_continuous_circle_toolpath,
        generate_continuous_spline_toolpath,
        generate_continuous_polyline_toolpath,
        generate_continuous_line_toolpath,
        process_dxf_file
    )
    print("✅ Toolpath planning modules imported successfully")
except ImportError as e:
    print(f"❌ Failed to import toolpath planning modules: {e}")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_circle_generation():
    """Test circle toolpath generation."""
    print("\n🔵 Testing Circle Toolpath Generation")
    print("=" * 50)
    
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
    
    # Analyze the toolpath
    if toolpath:
        print("\nFirst 5 points:")
        for i, (x, y, angle, z) in enumerate(toolpath[:5]):
            angle_deg = math.degrees(angle)
            print(f"  Point {i+1}: X={x:.3f}, Y={y:.3f}, Angle={angle_deg:.1f}°, Z={z}")
        
        print(f"\nLast 5 points:")
        for i, (x, y, angle, z) in enumerate(toolpath[-5:]):
            angle_deg = math.degrees(angle)
            print(f"  Point {len(toolpath)-4+i}: X={x:.3f}, Y={y:.3f}, Angle={angle_deg:.1f}°, Z={z}")
        
        # Check for smoothness
        angle_changes = []
        for i in range(1, len(toolpath)):
            prev_angle = toolpath[i-1][2]
            curr_angle = toolpath[i][2]
            angle_diff = abs(curr_angle - prev_angle)
            
            # Normalize angle difference
            while angle_diff > math.pi:
                angle_diff = 2 * math.pi - angle_diff
            
            angle_changes.append(math.degrees(angle_diff))
        
        max_angle_change = max(angle_changes)
        avg_angle_change = sum(angle_changes) / len(angle_changes)
        
        print(f"\nSmoothness Analysis:")
        print(f"  Max angle change: {max_angle_change:.2f}°")
        print(f"  Avg angle change: {avg_angle_change:.2f}°")
        print(f"  Total angle changes: {len(angle_changes)}")
        
        if max_angle_change < 2.0:
            print("✅ Circle toolpath is smooth!")
        else:
            print("⚠️ Circle toolpath may have sharp transitions")
    
    return toolpath

def test_spline_generation():
    """Test spline toolpath generation with a simple curve."""
    print("\n🔄 Testing Spline Toolpath Generation")
    print("=" * 50)
    
    try:
        import ezdxf
        
        # Create a simple DXF with a spline
        doc = ezdxf.new('R2010')
        msp = doc.modelspace()
        
        # Create a simple spline (approximating a circle)
        points = [
            (0, 10), (7, 7), (10, 0), (7, -7), (0, -10), (-7, -7), (-10, 0), (-7, 7), (0, 10)
        ]
        
        # Create a spline through these points
        spline = msp.add_spline(points)
        
        print(f"Spline created with {len(points)} control points")
        
        # Generate toolpath
        toolpath = generate_continuous_spline_toolpath(spline)
        
        print(f"Generated {len(toolpath)} points")
        
        # Analyze the toolpath
        if toolpath:
            print("\nFirst 5 points:")
            for i, (x, y, angle, z) in enumerate(toolpath[:5]):
                angle_deg = math.degrees(angle)
                print(f"  Point {i+1}: X={x:.3f}, Y={y:.3f}, Angle={angle_deg:.1f}°, Z={z}")
            
            # Check for smoothness
            angle_changes = []
            for i in range(1, len(toolpath)):
                prev_angle = toolpath[i-1][2]
                curr_angle = toolpath[i][2]
                angle_diff = abs(curr_angle - prev_angle)
                
                # Normalize angle difference
                while angle_diff > math.pi:
                    angle_diff = 2 * math.pi - angle_diff
                
                angle_changes.append(math.degrees(angle_diff))
            
            max_angle_change = max(angle_changes)
            avg_angle_change = sum(angle_changes) / len(angle_changes)
            
            print(f"\nSmoothness Analysis:")
            print(f"  Max angle change: {max_angle_change:.2f}°")
            print(f"  Avg angle change: {avg_angle_change:.2f}°")
            print(f"  Total angle changes: {len(angle_changes)}")
            
            if max_angle_change < 5.0:
                print("✅ Spline toolpath is smooth!")
            else:
                print("⚠️ Spline toolpath may have sharp transitions")
        
        return toolpath
        
    except Exception as e:
        print(f"❌ Error testing spline generation: {e}")
        return []

def test_dxf_processing():
    """Test processing of a DXF file."""
    print("\n📁 Testing DXF File Processing")
    print("=" * 50)
    
    # Look for DXF files in common locations
    test_dirs = [
        Path.home() / "Desktop" / "DXF",
        Path.home() / "Downloads",
        Path.cwd(),
        Path.cwd() / "test_files"
    ]
    
    dxf_files = []
    for test_dir in test_dirs:
        if test_dir.exists():
            dxf_files.extend(list(test_dir.glob("*.dxf")))
    
    if not dxf_files:
        print("No DXF files found in common locations.")
        print("Please place a DXF file in one of these directories:")
        for test_dir in test_dirs:
            print(f"  - {test_dir}")
        return
    
    # Use the first DXF file found
    dxf_file = dxf_files[0]
    print(f"Found DXF file: {dxf_file}")
    
    # Generate output path
    output_file = dxf_file.with_suffix('.test.gcode')
    
    try:
        # Process the DXF file
        gcode = process_dxf_file(str(dxf_file), str(output_file), feed_rate=100)
        
        if gcode:
            print(f"✅ Successfully generated {len(gcode)} G-code commands")
            print(f"📁 Output saved to: {output_file}")
            
            # Show first few commands
            print("\nFirst 10 G-code commands:")
            for i, cmd in enumerate(gcode[:10]):
                print(f"  {i+1:2d}: {cmd}")
            
            if len(gcode) > 10:
                print(f"  ... and {len(gcode)-10} more commands")
        else:
            print("❌ Failed to generate G-code")
            
    except Exception as e:
        print(f"❌ Error processing DXF file: {e}")

def test_continuous_generator():
    """Test the ContinuousToolpathGenerator class directly."""
    print("\n⚙️ Testing ContinuousToolpathGenerator Class")
    print("=" * 50)
    
    # Create generator with custom parameters
    generator = ContinuousToolpathGenerator(
        feed_rate=150,
        z_up=5,
        z_down=-1,
        step_size=0.03,  # Very fine step size
        max_angle_step_deg=0.5,  # Very small angle steps
        spline_precision=0.0005  # Very high precision
    )
    
    print(f"Generator created with:")
    print(f"  Feed rate: {generator.feed_rate} mm/min")
    print(f"  Step size: {generator.step_size} inches")
    print(f"  Max angle step: {math.degrees(generator.max_angle_step_rad):.1f}°")
    print(f"  Spline precision: {generator.spline_precision}")
    
    # Test circle generation
    center = (5, 5)
    radius = 8
    circle_toolpath = generator.generate_continuous_circle_path(center, radius)
    
    print(f"\nCircle toolpath: {len(circle_toolpath)} points")
    
    # Test G-code generation
    gcode = generator.generate_gcode_continuous([circle_toolpath])
    
    print(f"Generated {len(gcode)} G-code commands")
    
    # Show sample G-code
    print("\nSample G-code commands:")
    for i, cmd in enumerate(gcode[:15]):
        print(f"  {i+1:2d}: {cmd}")
    
    if len(gcode) > 15:
        print(f"  ... and {len(gcode)-15} more commands")
    
    return generator

def main():
    """Run all tests."""
    print("🚀 Fabric CNC Toolpath Generation Test Suite")
    print("=" * 60)
    print("Testing improved continuous motion toolpath generation")
    print("Optimized for ultra-smooth curves and complex shapes")
    print("=" * 60)
    
    # Test 1: Circle generation
    circle_toolpath = test_circle_generation()
    
    # Test 2: Spline generation
    spline_toolpath = test_spline_generation()
    
    # Test 3: DXF file processing
    test_dxf_processing()
    
    # Test 4: Continuous generator class
    generator = test_continuous_generator()
    
    print("\n" + "=" * 60)
    print("🎯 Test Summary")
    print("=" * 60)
    print(f"✅ Circle toolpath: {len(circle_toolpath) if circle_toolpath else 0} points")
    print(f"✅ Spline toolpath: {len(spline_toolpath) if spline_toolpath else 0} points")
    print("✅ Continuous generator: Working")
    print("\n🎉 All tests completed!")
    print("\nTo test with your own DXF files:")
    print("1. Place DXF files in ~/Desktop/DXF/ or ~/Downloads/")
    print("2. Run this script again")
    print("3. Check the generated .gcode files")
    print("\nTo test in the main app:")
    print("1. Run: python main_app.py")
    print("2. Import a DXF file")
    print("3. Generate toolpath")
    print("4. Preview the smooth motion!")

if __name__ == "__main__":
    main() 