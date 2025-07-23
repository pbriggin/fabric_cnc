#!/usr/bin/env python3
"""
Test pipeline for test_2.dxf
Runs the complete pipeline: DXF processor -> toolpath generator -> visualizer
"""

import sys
import os
import time

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

def test_complete_pipeline():
    """Test the complete pipeline with test_2.dxf"""
    print("=== Testing Complete Pipeline with test_2.dxf ===")
    print(f"Working directory: {os.getcwd()}")
    print(f"Script location: {__file__}")
    
    try:
        # Import the required modules
        from dxf_processing.dxf_processor import DXFProcessor
        from toolpath_planning.toolpath_generator import ToolpathGenerator
        from toolpath_planning.gcode_visualizer import GCodeVisualizer
        
        # Input file (relative to outputs folder)
        dxf_file = "/Users/peterbriggs/Downloads/test_2.dxf"
        
        print(f"\n1. Processing DXF file: {dxf_file}")
        print("-" * 50)
        
        # Step 1: DXF Processing
        start_time = time.time()
        processor = DXFProcessor()
        shapes = processor.process_dxf(dxf_file)
        dxf_time = time.time() - start_time
        
        print(f"✓ DXF processing completed in {dxf_time:.2f}s")
        print(f"  - Shapes found: {len(shapes)}")
        
        if not shapes:
            print("❌ No shapes found in DXF file")
            return False
        
        # Step 2: Toolpath Generation
        print(f"\n2. Generating toolpath")
        print("-" * 50)
        
        start_time = time.time()
        generator = ToolpathGenerator()
        gcode_file = "test_2_pipeline.gcode"
        
        # Generate toolpath
        gcode_content = generator.generate_toolpath(shapes)
        toolpath_time = time.time() - start_time
        
        if gcode_content:
            # Save G-code to file
            with open(gcode_file, 'w') as f:
                f.write(gcode_content)
            
            print(f"✓ Toolpath generation completed in {toolpath_time:.2f}s")
            print(f"  - G-code file: {gcode_file}")
            
            # Get statistics
            lines = gcode_content.split('\n')
            print(f"  - Total lines: {len(lines)}")
            
            # Count corners and Z changes
            corners = sum(1 for line in lines if "CORNER" in line)
            z_changes = sum(1 for line in lines if line.startswith("G0 Z") or line.startswith("G1 Z"))
            
            print(f"  - Corners detected: {corners}")
            print(f"  - Z-height changes: {z_changes}")
            
        else:
            print("❌ Toolpath generation failed")
            return False
        
        # Step 3: Visualization
        print(f"\n3. Creating visualization")
        print("-" * 50)
        
        start_time = time.time()
        visualizer = GCodeVisualizer()
        viz_file = "test_2_pipeline_visualization.png"
        
        # Parse the G-code file
        visualizer.parse_gcode_file(gcode_file)
        
        # Create visualization
        visualizer.create_visualization(viz_file)
        viz_time = time.time() - start_time
        
        print(f"✓ Visualization completed in {viz_time:.2f}s")
        print(f"  - Image file: {viz_file}")
        
        # Print statistics
        visualizer.print_statistics()
        
        # Summary
        total_time = dxf_time + toolpath_time + viz_time
        print(f"\n=== Pipeline Summary ===")
        print(f"✓ Complete pipeline successful!")
        print(f"  - Total time: {total_time:.2f}s")
        print(f"  - DXF processing: {dxf_time:.2f}s")
        print(f"  - Toolpath generation: {toolpath_time:.2f}s")
        print(f"  - Visualization: {viz_time:.2f}s")
        print(f"  - Output files:")
        print(f"    * {gcode_file}")
        print(f"    * {viz_file}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running this from the correct directory")
        return False
    except Exception as e:
        print(f"❌ Error during pipeline execution: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_complete_pipeline()
    if success:
        print("\n🎉 Pipeline test completed successfully!")
    else:
        print("\n💥 Pipeline test failed!")
        sys.exit(1) 