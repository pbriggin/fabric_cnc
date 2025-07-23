#!/usr/bin/env python3
"""
Test script to verify DXF processing fix
"""

import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(__file__))

def test_dxf_processing():
    """Test DXF processing with the fixed code"""
    print("=== Testing DXF Processing Fix ===")
    
    try:
        from dxf_processing.dxf_processor import DXFProcessor
        
        # Test with the same DXF file
        dxf_file = "/Users/peterbriggs/Downloads/test_4.dxf"
        
        print(f"Processing DXF file: {dxf_file}")
        
        # Process DXF
        processor = DXFProcessor()
        shapes = processor.process_dxf(dxf_file)
        
        if not shapes:
            print("❌ No shapes found in DXF file")
            return False
        
        print(f"✓ DXF processing completed successfully")
        print(f"  - Shapes found: {len(shapes)}")
        
        # Print details about the first shape
        for shape_name, points in shapes.items():
            print(f"  - {shape_name}: {len(points)} points")
            if points:
                print(f"    First point: {points[0]}")
                print(f"    Last point: {points[-1]}")
                
                # Check for sharp corners (angle changes > 10 degrees)
                corner_count = 0
                for i in range(1, len(points) - 1):
                    # Calculate angle between three consecutive points
                    p1 = points[i-1]
                    p2 = points[i]
                    p3 = points[i+1]
                    
                    # Calculate vectors
                    v1 = (p2[0] - p1[0], p2[1] - p1[1])
                    v2 = (p3[0] - p2[0], p3[1] - p2[1])
                    
                    # Calculate magnitudes
                    mag1 = (v1[0]**2 + v1[1]**2)**0.5
                    mag2 = (v2[0]**2 + v2[1]**2)**0.5
                    
                    if mag1 > 0 and mag2 > 0:
                        # Calculate dot product
                        dot_product = v1[0] * v2[0] + v1[1] * v2[1]
                        cos_angle = dot_product / (mag1 * mag2)
                        cos_angle = max(-1, min(1, cos_angle))  # Clamp to [-1, 1]
                        angle_degrees = abs(math.degrees(math.acos(cos_angle)))
                        
                        if angle_degrees > 10:
                            corner_count += 1
                
                print(f"    Sharp corners detected: {corner_count}")
                break  # Only show first shape
        
        return True
        
    except Exception as e:
        print(f"❌ Error during DXF processing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import math
    success = test_dxf_processing()
    if success:
        print("\n🎉 DXF processing test completed successfully!")
    else:
        print("\n💥 DXF processing test failed!")
        sys.exit(1) 