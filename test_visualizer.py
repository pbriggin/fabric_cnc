#!/usr/bin/env python3
"""
Test script for the GCODE Visualizer
"""

from gcode_visualizer import GCodeVisualizer

def main():
    """Test the GCODE visualizer with the generated toolpath."""
    
    # Create visualizer
    visualizer = GCodeVisualizer()
    
    # Parse the GCODE file
    gcode_file = "toolpath_test_2.gcode"
    
    try:
        print(f"Analyzing GCODE file: {gcode_file}")
        visualizer.parse_gcode_file(gcode_file)
        
        # Print statistics
        visualizer.print_statistics()
        
        # Create visualization
        output_file = "gcode_visualization_detailed.png"
        visualizer.create_visualization(output_file)
        
        print(f"\nVisualization saved to: {output_file}")
        print("The visualization shows:")
        print("- Left plot: Tool path with Z-height color coding (blue=low Z, red=high Z)")
        print("- Right plot: Tool orientation with direction arrows")
        print("- Red stars (*): Corner points where Z was raised")
        print("- Colored circles: Z-height changes (green=positive Z, orange=negative Z)")
        print("- Green circle: Start point")
        print("- Red square: End point")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 