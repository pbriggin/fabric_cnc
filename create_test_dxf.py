#!/usr/bin/env python3
"""
Create test DXF files with various shapes for testing toolpath generation.
"""

import ezdxf
import math
from pathlib import Path

def create_test_circle():
    """Create a DXF file with a circle."""
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    # Add a circle
    msp.add_circle((0, 0), radius=10)
    
    # Save the file
    output_path = Path("test_circle.dxf")
    doc.saveas(str(output_path))
    print(f"✅ Created {output_path}")
    return output_path

def create_test_spline():
    """Create a DXF file with a spline."""
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    # Create control points for a smooth curve
    points = [
        (0, 10), (7, 7), (10, 0), (7, -7), (0, -10), (-7, -7), (-10, 0), (-7, 7), (0, 10)
    ]
    
    # Add a spline
    msp.add_spline(points)
    
    # Save the file
    output_path = Path("test_spline.dxf")
    doc.saveas(str(output_path))
    print(f"✅ Created {output_path}")
    return output_path

def create_test_polyline():
    """Create a DXF file with a polyline."""
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    # Create a polyline (star shape)
    points = [
        (0, 10), (2, 2), (10, 2), (4, -2), (6, -10), (0, -6), (-6, -10), (-4, -2), (-10, 2), (-2, 2), (0, 10)
    ]
    
    # Add a polyline
    msp.add_lwpolyline(points)
    
    # Save the file
    output_path = Path("test_polyline.dxf")
    doc.saveas(str(output_path))
    print(f"✅ Created {output_path}")
    return output_path

def create_test_complex():
    """Create a DXF file with multiple shapes."""
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    # Add a circle
    msp.add_circle((0, 0), radius=8)
    
    # Add a smaller circle inside
    msp.add_circle((0, 0), radius=4)
    
    # Add a polyline (square)
    square_points = [(-6, -6), (6, -6), (6, 6), (-6, 6), (-6, -6)]
    msp.add_lwpolyline(square_points)
    
    # Add some lines
    msp.add_line((-10, 0), (10, 0))
    msp.add_line((0, -10), (0, 10))
    
    # Save the file
    output_path = Path("test_complex.dxf")
    doc.saveas(str(output_path))
    print(f"✅ Created {output_path}")
    return output_path

def create_test_arc():
    """Create a DXF file with arcs."""
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    # Add a full circle
    msp.add_circle((0, 0), radius=10)
    
    # Add a quarter circle arc
    msp.add_arc((20, 0), radius=8, start_angle=0, end_angle=90)
    
    # Add a half circle arc
    msp.add_arc((-20, 0), radius=6, start_angle=0, end_angle=180)
    
    # Save the file
    output_path = Path("test_arc.dxf")
    doc.saveas(str(output_path))
    print(f"✅ Created {output_path}")
    return output_path

def main():
    """Create all test DXF files."""
    print("🎨 Creating Test DXF Files")
    print("=" * 40)
    
    # Create test files
    files = []
    files.append(create_test_circle())
    files.append(create_test_spline())
    files.append(create_test_polyline())
    files.append(create_test_complex())
    files.append(create_test_arc())
    
    print("\n" + "=" * 40)
    print("📁 Test Files Created:")
    for file_path in files:
        print(f"  - {file_path}")
    
    print("\n🎯 You can now test these files with:")
    print("  python test_toolpath_generation.py")
    print("  python main_app.py")
    
    # Create a test directory
    test_dir = Path("test_files")
    test_dir.mkdir(exist_ok=True)
    
    # Move files to test directory
    for file_path in files:
        if file_path.exists():
            new_path = test_dir / file_path.name
            file_path.rename(new_path)
            print(f"  Moved {file_path.name} to test_files/")

if __name__ == "__main__":
    main() 