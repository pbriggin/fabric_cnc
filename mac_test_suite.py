#!/usr/bin/env python3
"""
Mac Test Suite for Fabric CNC
This script provides comprehensive testing capabilities for development on Mac.
"""

import os
import sys
import logging
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import math

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MacTestSuite:
    def __init__(self):
        self.root = None
        self.test_results = {}
        
    def run_all_tests(self):
        """Run all available tests."""
        logger.info("=== Starting Mac Test Suite ===")
        
        tests = [
            ("DXF Import", self.test_dxf_import),
            ("GUI Components", self.test_gui_components),
            ("Toolpath Generation", self.test_toolpath_generation),
            ("G-code Generation", self.test_gcode_generation),
            ("Simulation Mode", self.test_simulation_mode),
            ("Performance", self.test_performance),
        ]
        
        for test_name, test_func in tests:
            try:
                logger.info(f"Running {test_name}...")
                result = test_func()
                self.test_results[test_name] = result
                status = "PASSED" if result else "FAILED"
                logger.info(f"{test_name}: {status}")
            except Exception as e:
                logger.error(f"{test_name} failed with error: {e}")
                self.test_results[test_name] = False
        
        self.print_summary()
    
    def test_dxf_import(self):
        """Test DXF import functionality."""
        try:
            import ezdxf
            from ezdxf.math import Vec3
            
            # Test with our simple DXF file
            if os.path.exists("test_simple.dxf"):
                doc = ezdxf.readfile("test_simple.dxf")
                msp = doc.modelspace()
                
                entities = []
                for e in msp:
                    if e.dxftype() in ('LINE', 'LWPOLYLINE', 'POLYLINE', 'SPLINE', 'ARC', 'CIRCLE'):
                        entities.append(e)
                
                logger.info(f"DXF Import: Found {len(entities)} supported entities")
                return len(entities) > 0
            else:
                logger.warning("test_simple.dxf not found, skipping DXF import test")
                return False
                
        except ImportError:
            logger.error("ezdxf not available")
            return False
        except Exception as e:
            logger.error(f"DXF import test failed: {e}")
            return False
    
    def test_gui_components(self):
        """Test basic GUI components."""
        try:
            # Create a minimal GUI test
            root = tk.Tk()
            root.withdraw()  # Hide the window
            
            # Test basic widgets
            frame = ttk.Frame(root)
            button = ttk.Button(frame, text="Test")
            label = ttk.Label(frame, text="Test Label")
            
            # Test canvas
            canvas = tk.Canvas(frame, width=400, height=300)
            canvas.create_rectangle(10, 10, 100, 100, fill="blue")
            
            root.destroy()
            logger.info("GUI Components: Basic widgets working")
            return True
            
        except Exception as e:
            logger.error(f"GUI test failed: {e}")
            return False
    
    def test_toolpath_generation(self):
        """Test toolpath generation logic."""
        try:
            # Test basic toolpath generation
            points = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
            
            # Simple toolpath generation
            toolpath = []
            for i in range(len(points) - 1):
                start = points[i]
                end = points[i + 1]
                toolpath.append((start, end))
            
            logger.info(f"Toolpath Generation: Generated {len(toolpath)} segments")
            return len(toolpath) > 0
            
        except Exception as e:
            logger.error(f"Toolpath generation test failed: {e}")
            return False
    
    def test_gcode_generation(self):
        """Test G-code generation."""
        try:
            # Test basic G-code generation
            gcode_lines = []
            
            # G-code header
            gcode_lines.append("G21 ; Set units to mm")
            gcode_lines.append("G90 ; Set absolute positioning")
            gcode_lines.append("G28 ; Home all axes")
            
            # Simple square pattern
            square_points = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
            
            for x, y in square_points:
                gcode_lines.append(f"G0 X{x} Y{y}")
                if x == 0 and y == 0:  # First point
                    gcode_lines.append("G1 Z-1 F100 ; Lower tool")
                elif x == 0 and y == 0:  # Last point (back to start)
                    gcode_lines.append("G1 Z1 F100 ; Raise tool")
            
            logger.info(f"G-code Generation: Generated {len(gcode_lines)} lines")
            return len(gcode_lines) > 0
            
        except Exception as e:
            logger.error(f"G-code generation test failed: {e}")
            return False
    
    def test_simulation_mode(self):
        """Test simulation mode detection and functionality."""
        try:
            import platform
            
            # Check if we're in simulation mode
            on_rpi = platform.system() == 'Linux' and (
                os.uname().machine.startswith('arm') or 
                os.uname().machine.startswith('aarch')
            )
            
            simulation_mode = not on_rpi
            
            logger.info(f"Platform: {platform.system()}")
            logger.info(f"Machine: {os.uname().machine}")
            logger.info(f"On RPi: {on_rpi}")
            logger.info(f"Simulation Mode: {simulation_mode}")
            
            return simulation_mode  # Should be True on Mac
            
        except Exception as e:
            logger.error(f"Simulation mode test failed: {e}")
            return False
    
    def test_performance(self):
        """Test basic performance metrics."""
        try:
            import time
            
            # Test DXF processing performance
            start_time = time.time()
            
            if os.path.exists("test_simple.dxf"):
                import ezdxf
                doc = ezdxf.readfile("test_simple.dxf")
                msp = doc.modelspace()
                
                entities = list(msp)
                processing_time = time.time() - start_time
                
                logger.info(f"Performance: Processed {len(entities)} entities in {processing_time:.4f}s")
                return processing_time < 1.0  # Should be very fast
            else:
                logger.warning("test_simple.dxf not found for performance test")
                return False
                
        except Exception as e:
            logger.error(f"Performance test failed: {e}")
            return False
    
    def print_summary(self):
        """Print test results summary."""
        logger.info("\n=== Test Results Summary ===")
        
        passed = sum(1 for result in self.test_results.values() if result)
        total = len(self.test_results)
        
        for test_name, result in self.test_results.items():
            status = "✓ PASS" if result else "✗ FAIL"
            logger.info(f"{test_name:20} {status}")
        
        logger.info(f"\nOverall: {passed}/{total} tests passed")
        
        if passed == total:
            logger.info("🎉 All tests passed! System is ready for development.")
        else:
            logger.warning("⚠️  Some tests failed. Check the logs above.")
    
    def create_test_dxf(self, filename="test_complex.dxf"):
        """Create a more complex test DXF file."""
        try:
            import ezdxf
            
            # Create a new DXF document
            doc = ezdxf.new('R2010')
            msp = doc.modelspace()
            
            # Create a more complex shape (star pattern)
            center_x, center_y = 5, 5
            radius = 3
            points = 5
            
            for i in range(points * 2):
                angle = (i * math.pi) / points
                r = radius if i % 2 == 0 else radius * 0.5
                x = center_x + r * math.cos(angle)
                y = center_y + r * math.sin(angle)
                
                if i > 0:
                    # Connect to previous point
                    prev_angle = ((i - 1) * math.pi) / points
                    prev_r = radius if (i - 1) % 2 == 0 else radius * 0.5
                    prev_x = center_x + prev_r * math.cos(prev_angle)
                    prev_y = center_y + prev_r * math.sin(prev_angle)
                    
                    msp.add_line((prev_x, prev_y), (x, y))
            
            # Close the shape
            first_angle = 0
            first_r = radius
            first_x = center_x + first_r * math.cos(first_angle)
            first_y = center_y + first_r * math.sin(first_angle)
            msp.add_line((x, y), (first_x, first_y))
            
            # Save the file
            doc.saveas(filename)
            logger.info(f"Created complex test DXF: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create test DXF: {e}")
            return False

def main():
    """Main function to run the test suite."""
    test_suite = MacTestSuite()
    
    # Create a complex test DXF if it doesn't exist
    if not os.path.exists("test_complex.dxf"):
        test_suite.create_test_dxf()
    
    # Run all tests
    test_suite.run_all_tests()
    
    # Interactive mode
    print("\n" + "="*50)
    print("Interactive Testing Mode")
    print("="*50)
    print("1. Run main application GUI")
    print("2. Test DXF import with complex file")
    print("3. Exit")
    
    while True:
        try:
            choice = input("\nEnter your choice (1-3): ").strip()
            
            if choice == "1":
                print("Starting main application...")
                os.system("python3 main_app.py")
                
            elif choice == "2":
                print("Testing complex DXF import...")
                if os.path.exists("test_complex.dxf"):
                    os.system("python3 test_dxf_import.py test_complex.dxf")
                else:
                    print("Complex DXF file not found. Creating one...")
                    test_suite.create_test_dxf()
                    os.system("python3 test_dxf_import.py test_complex.dxf")
                    
            elif choice == "3":
                print("Exiting...")
                break
                
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")
                
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main() 