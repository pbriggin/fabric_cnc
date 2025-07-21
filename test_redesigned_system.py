#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for the redesigned Fabric CNC system.
Verifies that all components work correctly in simulation mode.
"""

import sys
import time
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_config_manager():
    """Test the configuration manager."""
    print("Testing ConfigManager...")
    
    try:
        from config_manager import config_manager
        
        # Test basic configuration loading
        assert config_manager.machine_config.name == "fabric_cnc_v1"
        assert config_manager.machine_config.units == "mm"
        
        # Test axis configuration
        x_config = config_manager.get_axis_config('X')
        assert x_config.step_pin == 24
        assert x_config.dir_pin == 23
        assert x_config.steps_per_mm == 80
        
        # Test work area
        work_area = config_manager.get_work_area()
        assert work_area['X'] == 1727
        assert work_area['Y'] == 1143
        
        # Test position validation
        assert config_manager.validate_position('X', 100)
        assert not config_manager.validate_position('X', 2000)  # Out of bounds
        
        print("✓ ConfigManager tests passed")
        return True
        
    except Exception as e:
        print(f"✗ ConfigManager test failed: {e}")
        return False

def test_motor_control():
    """Test the motor control system."""
    print("Testing Motor Control...")
    
    try:
        from motor_control import MultiAxisController, Position, MovementType
        
        # Create controller in simulation mode
        controller = MultiAxisController(simulation_mode=True)
        
        # Test basic operations
        controller.enable_all()
        
        # Test position management
        pos = controller.get_position()
        assert isinstance(pos, Position)
        assert pos.x == 0.0 and pos.y == 0.0 and pos.z == 0.0 and pos.a == 0.0
        
        # Test position validation
        valid_pos = Position(x=100, y=100, z=10, a=0)
        assert controller.validate_position(valid_pos)
        
        invalid_pos = Position(x=2000, y=100, z=10, a=0)  # X out of bounds
        assert not controller.validate_position(invalid_pos)
        
        # Test movement (simulation mode)
        controller.move_to_position(valid_pos, speed=20)
        
        # Test status
        status = controller.get_status()
        assert len(status) == 5  # X, Y1, Y2, Z, A
        
        controller.cleanup()
        print("✓ Motor Control tests passed")
        return True
        
    except Exception as e:
        print(f"✗ Motor Control test failed: {e}")
        return False

def test_toolpath_planning():
    """Test the toolpath planning system."""
    print("Testing Toolpath Planning...")
    
    try:
        from toolpath_planning import (
            MotionPlanner, ToolpathOptimizer, ToolpathPoint,
            GCodeGenerator, GCodeSettings
        )
        from motor_control import MultiAxisController
        
        # Create dependencies
        controller = MultiAxisController(simulation_mode=True)
        planner = MotionPlanner(controller)
        optimizer = ToolpathOptimizer()
        generator = GCodeGenerator()
        
        # Test toolpath point creation
        point = ToolpathPoint(x=100, y=100, z=5, a=0, feed_rate=100, tool_down=False)
        assert point.x == 100 and point.y == 100
        
        # Test toolpath optimization
        toolpath = [
            ToolpathPoint(x=0, y=0, z=5, a=0, feed_rate=100, tool_down=False),
            ToolpathPoint(x=100, y=100, z=5, a=0, feed_rate=100, tool_down=False),
        ]
        
        optimized = optimizer.optimize_toolpath(toolpath)
        assert len(optimized) >= len(toolpath)
        
        # Test G-code generation
        gcode = generator.generate_from_toolpath(toolpath)
        assert "G21" in gcode  # Should contain unit setting
        assert "G90" in gcode  # Should contain absolute positioning
        
        # Test G-code settings
        settings = GCodeSettings(feed_rate=150, precision=2)
        assert settings.feed_rate == 150
        assert settings.precision == 2
        
        controller.cleanup()
        print("✓ Toolpath Planning tests passed")
        return True
        
    except Exception as e:
        print(f"✗ Toolpath Planning test failed: {e}")
        return False

def test_main_application():
    """Test the main application."""
    print("Testing Main Application...")
    
    try:
        from main_app_redesigned import FabricCNCApp
        
        # Create application in simulation mode
        app = FabricCNCApp(simulation_mode=True)
        
        # Test application lifecycle
        app.start()
        assert app.is_running
        
        # Test status
        status = app.get_status()
        assert status['is_running']
        assert status['simulation_mode']
        
        # Test movement
        app.move_to_position(x=50, y=50, z=10)
        
        # Test toolpath execution
        from toolpath_planning import ToolpathPoint
        
        simple_toolpath = [
            ToolpathPoint(x=0, y=0, z=5, a=0, feed_rate=100, tool_down=False),
            ToolpathPoint(x=10, y=10, z=5, a=0, feed_rate=100, tool_down=False),
        ]
        
        app.execute_toolpath(simple_toolpath, optimize=False)
        
        # Test G-code generation
        output_file = Path("test_output.gcode")
        app.generate_gcode_file(simple_toolpath, output_file)
        assert output_file.exists()
        output_file.unlink()  # Clean up
        
        app.cleanup()
        assert not app.is_running
        
        print("✓ Main Application tests passed")
        return True
        
    except Exception as e:
        print(f"✗ Main Application test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Fabric CNC - Redesigned System Tests")
    print("=" * 50)
    
    tests = [
        test_config_manager,
        test_motor_control,
        test_toolpath_planning,
        test_main_application
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The redesigned system is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 