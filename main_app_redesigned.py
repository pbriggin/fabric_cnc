#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main application for the redesigned Fabric CNC system.
Demonstrates the new motor control and toolpath planning capabilities.
"""

import logging
import time
import threading
from pathlib import Path
from typing import Optional

from config_manager import config_manager
from motor_control import MultiAxisController, Position, MovementType
from toolpath_planning import (
    MotionPlanner, ToolpathOptimizer, ToolpathPoint,
    GCodeGenerator, GCodeSettings
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FabricCNCApp:
    """Main application for Fabric CNC machine."""
    
    def __init__(self, simulation_mode: bool = False):
        """Initialize the Fabric CNC application.
        
        Args:
            simulation_mode: If True, run in simulation mode
        """
        self.simulation_mode = simulation_mode
        
        # Initialize motor control
        self.controller = MultiAxisController(simulation_mode=simulation_mode)
        
        # Initialize motion planner
        self.motion_planner = MotionPlanner(self.controller)
        
        # Initialize toolpath optimizer
        self.toolpath_optimizer = ToolpathOptimizer()
        
        # Initialize G-code generator
        self.gcode_generator = GCodeGenerator()
        
        # Application state
        self.is_running = False
        self.current_operation = None
        
        logger.info("Fabric CNC application initialized")
        logger.info(f"Simulation mode: {simulation_mode}")
        logger.info(f"Machine: {config_manager.machine_config.name}")
        logger.info(f"Work area: {config_manager.get_work_area()}")
    
    def start(self) -> None:
        """Start the application."""
        if self.is_running:
            logger.warning("Application already running")
            return
        
        self.is_running = True
        
        # Enable all motors
        self.controller.enable_all()
        
        logger.info("Fabric CNC application started")
    
    def stop(self) -> None:
        """Stop the application."""
        if not self.is_running:
            return
        
        # Stop any ongoing operations
        if self.motion_planner.is_executing_toolpath():
            self.motion_planner.stop_execution()
        
        self.controller.stop()
        
        # Disable all motors
        self.controller.disable_all()
        
        self.is_running = False
        logger.info("Fabric CNC application stopped")
    
    def home_machine(self, callback: Optional[callable] = None) -> None:
        """Home all axes of the machine."""
        if not self.is_running:
            logger.error("Application not running")
            return
        
        def homing_callback(status: str, progress: float):
            logger.info(f"Homing: {status} - {progress:.1%}")
            if callback:
                callback(status, progress)
        
        self.controller.home_all(callback=homing_callback)
    
    def move_to_position(
        self,
        x: float = None,
        y: float = None,
        z: float = None,
        a: float = None,
        speed: float = None,
        movement_type: MovementType = MovementType.LINEAR
    ) -> None:
        """Move to a specific position.
        
        Args:
            x: X coordinate (mm)
            y: Y coordinate (mm)
            z: Z coordinate (mm)
            a: A coordinate (degrees)
            speed: Movement speed (mm/s)
            movement_type: Type of movement
        """
        if not self.is_running:
            logger.error("Application not running")
            return
        
        # Get current position
        current_pos = self.controller.get_position()
        
        # Update only specified coordinates
        target_pos = Position(
            x=x if x is not None else current_pos.x,
            y=y if y is not None else current_pos.y,
            z=z if z is not None else current_pos.z,
            a=a if a is not None else current_pos.a
        )
        
        # Use default speed if not specified
        if speed is None:
            speed = config_manager.machine_config.motion.default_speed
        
        # Validate position
        if not self.controller.validate_position(target_pos):
            logger.error(f"Invalid position: {target_pos}")
            return
        
        logger.info(f"Moving to position: {target_pos}")
        self.controller.move_to_position(
            target_position=target_pos,
            speed=speed,
            movement_type=movement_type
        )
    
    def execute_toolpath(
        self,
        toolpath: list[ToolpathPoint],
        optimize: bool = True
    ) -> None:
        """Execute a toolpath.
        
        Args:
            toolpath: List of toolpath points
            optimize: Whether to optimize the toolpath
        """
        if not self.is_running:
            logger.error("Application not running")
            return
        
        if optimize:
            logger.info("Optimizing toolpath...")
            toolpath = self.toolpath_optimizer.optimize_toolpath(toolpath)
        
        def progress_callback(progress: float):
            logger.info(f"Toolpath progress: {progress:.1%}")
        
        def status_callback(status: str):
            logger.info(f"Toolpath status: {status}")
        
        logger.info(f"Executing toolpath with {len(toolpath)} points")
        self.motion_planner.execute_toolpath(
            toolpath=toolpath,
            progress_callback=progress_callback,
            status_callback=status_callback
        )
    
    def generate_and_execute_circle(
        self,
        center_x: float,
        center_y: float,
        radius: float,
        feed_rate: float = 100.0
    ) -> None:
        """Generate and execute a circle toolpath.
        
        Args:
            center_x: X coordinate of circle center
            center_y: Y coordinate of circle center
            radius: Circle radius
            feed_rate: Feed rate for cutting
        """
        # Generate circle toolpath
        num_points = max(32, int(2 * 3.14159 * radius / 1.0))  # 1mm spacing
        toolpath = []
        
        for i in range(num_points + 1):
            angle = 2 * 3.14159 * i / num_points
            x = center_x + radius * (angle)
            y = center_y + radius * (angle)
            
            point = ToolpathPoint(
                x=x, y=y, z=-1.0,  # Cutting depth
                a=0.0, feed_rate=feed_rate,
                tool_down=True
            )
            toolpath.append(point)
        
        # Execute toolpath
        self.execute_toolpath(toolpath)
    
    def generate_gcode_file(
        self,
        toolpath: list[ToolpathPoint],
        output_file: Path,
        settings: Optional[GCodeSettings] = None
    ) -> None:
        """Generate G-code file from toolpath.
        
        Args:
            toolpath: List of toolpath points
            output_file: Output file path
            settings: G-code generation settings
        """
        if settings is None:
            settings = GCodeSettings()
        
        gcode = self.gcode_generator.generate_from_toolpath(
            toolpath=toolpath,
            output_file=output_file
        )
        
        logger.info(f"G-code generated and saved to {output_file}")
    
    def get_status(self) -> dict:
        """Get current application status."""
        return {
            'is_running': self.is_running,
            'simulation_mode': self.simulation_mode,
            'current_position': self.controller.get_position(),
            'machine_status': self.controller.get_status(),
            'toolpath_executing': self.motion_planner.is_executing_toolpath(),
            'work_area': config_manager.get_work_area()
        }
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop()
        self.controller.cleanup()
        logger.info("Application cleanup completed")

def main():
    """Main function to demonstrate the redesigned system."""
    print("Fabric CNC - Redesigned System Demo")
    print("=" * 50)
    
    # Create application in simulation mode for demo
    app = FabricCNCApp(simulation_mode=True)
    
    try:
        # Start the application
        app.start()
        
        # Get initial status
        status = app.get_status()
        print(f"Machine status: {status}")
        
        # Demo: Move to different positions
        print("\nDemo 1: Moving to different positions")
        app.move_to_position(x=100, y=100, z=10)
        time.sleep(2)
        
        app.move_to_position(x=200, y=150, z=5)
        time.sleep(2)
        
        app.move_to_position(x=150, y=200, z=15)
        time.sleep(2)
        
        # Demo: Generate and execute a simple toolpath
        print("\nDemo 2: Executing a simple toolpath")
        toolpath = [
            ToolpathPoint(x=100, y=100, z=5, a=0, feed_rate=100, tool_down=False),
            ToolpathPoint(x=100, y=100, z=-1, a=0, feed_rate=100, tool_down=True),
            ToolpathPoint(x=200, y=100, z=-1, a=0, feed_rate=100, tool_down=True),
            ToolpathPoint(x=200, y=200, z=-1, a=0, feed_rate=100, tool_down=True),
            ToolpathPoint(x=100, y=200, z=-1, a=0, feed_rate=100, tool_down=True),
            ToolpathPoint(x=100, y=100, z=-1, a=0, feed_rate=100, tool_down=True),
            ToolpathPoint(x=100, y=100, z=5, a=0, feed_rate=100, tool_down=False),
        ]
        
        app.execute_toolpath(toolpath)
        
        # Demo: Generate G-code file
        print("\nDemo 3: Generating G-code file")
        output_file = Path("demo_toolpath.gcode")
        app.generate_gcode_file(toolpath, output_file)
        
        # Final status
        final_status = app.get_status()
        print(f"\nFinal machine status: {final_status}")
        
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"Demo error: {e}")
        logger.error(f"Demo error: {e}")
    finally:
        app.cleanup()
        print("Demo completed")

if __name__ == "__main__":
    main() 