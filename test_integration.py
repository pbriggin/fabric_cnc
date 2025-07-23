#!/usr/bin/env python3
"""
Test script to verify the integration of DXF processor, toolpath generator, and G-code executor.
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_dxf_processing():
    """Test DXF processing integration."""
    try:
        from dxf_processing.dxf_processor import DXFProcessor
        from toolpath_planning.toolpath_generator import ToolpathGenerator
        
        # Initialize processors
        dxf_processor = DXFProcessor()
        toolpath_generator = ToolpathGenerator(
            cutting_height=-2.0,
            safe_height=5.0,
            corner_angle_threshold=10.0,
            feed_rate=1000.0,
            plunge_rate=200.0
        )
        
        # Test with a simple DXF file
        test_dxf_path = "outputs/test_2.dxf"
        if not os.path.exists(test_dxf_path):
            logger.warning(f"Test DXF file not found: {test_dxf_path}")
            return False
        
        # Process DXF
        logger.info("Processing DXF file...")
        processed_shapes = dxf_processor.process_dxf(test_dxf_path)
        
        if not processed_shapes:
            logger.error("No shapes found in DXF file")
            return False
        
        logger.info(f"Successfully processed {len(processed_shapes)} shapes")
        
        # Generate G-code
        logger.info("Generating G-code...")
        gcode = toolpath_generator.generate_toolpath(processed_shapes)
        
        if not gcode:
            logger.error("Failed to generate G-code")
            return False
        
        # Save G-code
        gcode_path = "outputs/test_integration.gcode"
        with open(gcode_path, 'w') as f:
            f.write(gcode)
        
        logger.info(f"G-code saved to: {gcode_path}")
        
        # Count lines and corners
        gcode_lines = gcode.split('\n')
        total_lines = len([line for line in gcode_lines if line.strip() and not line.strip().startswith(';')])
        corner_count = len([line for line in gcode_lines if 'Raise Z for corner' in line])
        
        logger.info(f"G-code statistics:")
        logger.info(f"  - Total lines: {total_lines}")
        logger.info(f"  - Corners detected: {corner_count}")
        
        return True
        
    except Exception as e:
        logger.error(f"DXF processing test failed: {e}")
        return False

def test_gcode_visualization():
    """Test G-code visualization integration."""
    try:
        from toolpath_planning.gcode_visualizer import GCodeVisualizer
        
        gcode_path = "outputs/test_integration.gcode"
        if not os.path.exists(gcode_path):
            logger.warning(f"G-code file not found: {gcode_path}")
            return False
        
        # Create visualization
        visualizer = GCodeVisualizer()
        visualizer.parse_gcode_file(gcode_path)
        
        output_path = "outputs/test_integration_visualization.png"
        visualizer.create_visualization(output_path)
        
        if os.path.exists(output_path):
            logger.info(f"Visualization created: {output_path}")
            return True
        else:
            logger.error("Failed to create visualization")
            return False
            
    except Exception as e:
        logger.error(f"G-code visualization test failed: {e}")
        return False

def test_gcode_executor():
    """Test G-code executor integration."""
    try:
        from main_app import GCodeExecutor, SimulatedMotorController
        
        # Create simulated motor controller and G-code executor
        motor_controller = SimulatedMotorController()
        gcode_executor = GCodeExecutor(motor_controller)
        
        gcode_path = "outputs/test_integration.gcode"
        if not os.path.exists(gcode_path):
            logger.warning(f"G-code file not found: {gcode_path}")
            return False
        
        # Test parsing (don't actually execute)
        with open(gcode_path, 'r') as f:
            gcode_lines = f.readlines()
        
        # Parse first few lines to test
        test_lines = gcode_lines[:10]  # Just test first 10 lines
        
        def progress_callback(progress, status):
            logger.info(f"Progress: {progress:.1f}% - {status}")
        
        # Test parsing without execution
        logger.info("Testing G-code parsing...")
        for line in test_lines:
            if line.strip() and not line.strip().startswith(';'):
                gcode_executor._execute_gcode_line(line.strip())
        
        logger.info("G-code parsing test successful")
        return True
        
    except Exception as e:
        logger.error(f"G-code executor test failed: {e}")
        return False

def main():
    """Run all integration tests."""
    logger.info("Starting integration tests...")
    
    # Ensure outputs directory exists
    os.makedirs("outputs", exist_ok=True)
    
    tests = [
        ("DXF Processing", test_dxf_processing),
        ("G-code Visualization", test_gcode_visualization),
        ("G-code Executor", test_gcode_executor),
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"Running {test_name} test...")
        logger.info(f"{'='*50}")
        
        try:
            result = test_func()
            results.append((test_name, result))
            if result:
                logger.info(f"✅ {test_name} test PASSED")
            else:
                logger.error(f"❌ {test_name} test FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name} test FAILED with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info(f"\n{'='*50}")
    logger.info("INTEGRATION TEST SUMMARY")
    logger.info(f"{'='*50}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All integration tests passed!")
        return 0
    else:
        logger.error("💥 Some integration tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 