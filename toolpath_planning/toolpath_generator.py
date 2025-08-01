#!/usr/bin/env python3
"""
Toolpath Generator for Fabric CNC

Takes output from DXF processor and generates GCODE with:
- X, Y positioning
- Z height management (raise at corners with angle changes > 5 degrees)
- Z rotation (cutting blade parallel to current segment)
- Corner handling: raise Z → rotate Z → lower Z
"""

import math
import logging
from typing import Dict, List, Tuple, Optional
from dxf_processing.dxf_processor import DXFProcessor

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ToolpathGenerator:
    """
    Generates GCODE toolpaths from DXF shapes with intelligent Z-axis management.
    """
    
    def __init__(self, 
                 cutting_height: float = -0.5,  # Plunge depth below work surface
                 safe_height: float = 0.0,  # Safe height at work surface level
                 corner_angle_threshold: float = 15.0,  # Increased from 5.0 to be less sensitive to curves
                 feed_rate: float = 1000.0,
                 plunge_rate: float = 200.0):
        """
        Initialize the toolpath generator.
        
        Args:
            cutting_height: Z height when cutting (negative = below work surface)
            safe_height: Z height when moving between cuts (0 = at work surface level)
            corner_angle_threshold: Angle in degrees above which to raise Z at corners
            feed_rate: Feed rate for cutting moves (inches/min)
            plunge_rate: Feed rate for Z plunges (inches/min)
        """
        self.cutting_height = cutting_height
        self.safe_height = safe_height
        self.corner_angle_threshold_radians = math.radians(corner_angle_threshold)
        self.feed_rate = feed_rate
        self.plunge_rate = plunge_rate
        self.current_z = safe_height  # Track current Z position
        self.current_a = 0.0  # Track current A position for continuous rotation
        
    def generate_toolpath(self, shapes: Dict[str, List[Tuple[float, float]]]) -> str:
        """
        Generate GCODE from DXF shapes.
        
        Args:
            shapes: Dictionary of shape names to point lists from DXF processor
            
        Returns:
            GCODE string
        """
        gcode_lines = []
        
        # Add header
        gcode_lines.extend(self._generate_header())
        
        # Process each shape
        for shape_name, points in shapes.items():
            logger.info(f"Generating toolpath for {shape_name} with {len(points)} points")
            # Reset A position tracking for each new shape
            self.current_a = 0.0
            shape_gcode = self._generate_shape_toolpath(shape_name, points)
            gcode_lines.extend(shape_gcode)
        
        # Add footer
        gcode_lines.extend(self._generate_footer())
        
        return '\n'.join(gcode_lines)
    
    def _generate_header(self) -> List[str]:
        """Generate GCODE header."""
        return [
            "; Fabric CNC Toolpath",
            "; Generated by ToolpathGenerator",
            "; Machine homing is automatically verified before execution",
            "",
            "G20 ; Set units to inches",
            "G90 ; Set absolute positioning", 
            "G54 ; Use work coordinate system (WCS)",
            "G17 ; Select XY plane",
            "G94 ; Feed rate mode (units per minute)",
            "",
            f"G0 Z{self.safe_height} ; Move to safe height",
            ""
        ]
    
    def _generate_footer(self) -> List[str]:
        """Generate GCODE footer."""
        return [
            "",
            f"G0 Z{self.safe_height} ; Return to safe height",
            "G0 X0 Y0 ; Return to work coordinate origin",
            "M5 ; Spindle off (if applicable)",
            "M2 ; End program"
        ]
    
    def _generate_shape_toolpath(self, shape_name: str, points: List[Tuple[float, float]]) -> List[str]:
        """
        Generate GCODE for a single shape.
        
        Args:
            shape_name: Name of the shape
            points: List of (x, y) coordinate tuples
            
        Returns:
            List of GCODE lines for this shape
        """
        if len(points) < 2:
            logger.warning(f"Shape {shape_name} has less than 2 points, skipping")
            return []
        
        gcode_lines = []
        
        # Add shape comment
        gcode_lines.append(f"; Shape: {shape_name}")
        
        # Start at first point
        first_point = points[0]
        gcode_lines.append(f"G0 X{first_point[0]:.3f} Y{first_point[1]:.3f} ; Move to start")
        
        # Set initial A rotation for first segment
        if len(points) > 1:
            first_a_raw = self._calculate_z_rotation(first_point, points[1])
            first_a_position = self._calculate_continuous_a(first_a_raw)
            gcode_lines.append(f"G0 A{first_a_position:.4f} ; Set initial cutting wheel position")
        
        # First plunge - use G0 to ensure Z movement completes before XY movement
        gcode_lines.append(f"G0 Z{self.cutting_height} ; Plunge to cutting height")
        
        # Process each segment
        for i in range(len(points) - 1):
            current_point = points[i]
            next_point = points[i + 1]
            
            # Calculate angle between current segment and next segment
            angle_change = self._calculate_angle_change(points, i)
            
            # Determine if we need to raise Z at this corner using simple angle detection
            should_raise_z = self._is_genuine_corner(points, i)
            
            # Calculate A rotation for the next segment
            a_raw = self._calculate_z_rotation(current_point, next_point)
            a_position = self._calculate_continuous_a(a_raw)
            
            if should_raise_z:
                # For corners: raise Z, rotate A, lower Z, move to next point
                gcode_lines.append(f"G0 Z{self.safe_height} ; Raise Z for corner")
                gcode_lines.append(f"G0 A{a_position:.4f} ; Rotate A for corner")
                gcode_lines.append(f"G0 Z{self.cutting_height} ; Lower Z to cutting height")
                gcode_lines.append(f"G0 X{next_point[0]:.3f} Y{next_point[1]:.3f} ; Move to next point")
            else:
                # For curves: combine A rotation with cutting move
                gcode_lines.append(f"G1 X{next_point[0]:.3f} Y{next_point[1]:.3f} A{a_position:.4f} F{self.feed_rate} ; Cut to next point")
        
        # For closed shapes, the main loop already handles all segments correctly
        # No additional handling needed
        
        # Raise tool to safe height before homing
        gcode_lines.append(f"G0 Z{self.safe_height} ; Raise tool to safe height")
        
        # Add blank line for spacing
        gcode_lines.append("")
        
        return gcode_lines
    
    def _calculate_angle_change(self, points: List[Tuple[float, float]], point_index: int) -> float:
        """
        Calculate the angle change at a specific point.
        
        Args:
            points: List of points
            point_index: Index of the point to calculate angle change at
            
        Returns:
            Angle change in radians
        """
        if point_index == 0 or point_index >= len(points) - 1:
            return 0.0
        
        # Get three consecutive points
        prev_point = points[point_index - 1]
        current_point = points[point_index]
        next_point = points[point_index + 1]
        
        # Calculate vectors
        v1 = (current_point[0] - prev_point[0], current_point[1] - prev_point[1])
        v2 = (next_point[0] - current_point[0], next_point[1] - current_point[1])
        
        # Calculate magnitudes
        mag1 = math.sqrt(v1[0]**2 + v1[1]**2)
        mag2 = math.sqrt(v2[0]**2 + v2[1]**2)
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
        
        # Calculate dot product
        dot_product = v1[0] * v2[0] + v1[1] * v2[1]
        
        # Calculate angle
        cos_angle = dot_product / (mag1 * mag2)
        cos_angle = max(-1, min(1, cos_angle))  # Clamp to [-1, 1]
        
        angle = math.acos(cos_angle)
        
        # Determine sign using cross product
        cross_product = v1[0] * v2[1] - v1[1] * v2[0]
        if cross_product < 0:
            angle = -angle
        
        return angle
    
    def _is_genuine_corner(self, points: List[Tuple[float, float]], point_index: int) -> bool:
        """
        Determine if a point represents a corner using simple angle-based detection.
        
        Args:
            points: List of points
            point_index: Index of the point to check
            
        Returns:
            True if this is a corner (angle > 5 degrees), False otherwise
        """
        if point_index == 0 or point_index >= len(points) - 1:
            return False
        
        # Get three consecutive points
        prev_point = points[point_index - 1]
        current_point = points[point_index]
        next_point = points[point_index + 1]
        
        # Calculate vectors
        v1 = (current_point[0] - prev_point[0], current_point[1] - prev_point[1])
        v2 = (next_point[0] - current_point[0], next_point[1] - current_point[1])
        
        # Calculate magnitudes
        mag1 = math.sqrt(v1[0]**2 + v1[1]**2)
        mag2 = math.sqrt(v2[0]**2 + v2[1]**2)
        
        if mag1 == 0 or mag2 == 0:
            return False
        
        # Calculate dot product
        dot_product = v1[0] * v2[0] + v1[1] * v2[1]
        
        # Calculate angle using the exact formula from Google Sheets
        cos_angle = dot_product / (mag1 * mag2)
        cos_angle = max(-1, min(1, cos_angle))  # Clamp to [-1, 1]
        
        angle_radians = math.acos(cos_angle)
        angle_degrees = math.degrees(angle_radians)
        
        # Debug output
        if angle_degrees > 5.0:
            # Corner detected
            pass
        else:
            # Not a corner
            pass
        
        # Use the configured corner angle threshold
        return angle_degrees > math.degrees(self.corner_angle_threshold_radians)
    
    def _calculate_z_rotation(self, point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
        """
        Calculate A-axis position to make cutting blade parallel to line segment.
        Tool starts parallel to Y-axis, so we need to adjust by 90 degrees.
        
        Args:
            point1: First point (x, y)
            point2: Second point (x, y)
            
        Returns:
            A-axis position in inches (1 inch = 360 degrees)
        """
        dx = point2[0] - point1[0]
        dy = point2[1] - point1[1]
        
        # Calculate angle from X-axis (negate to fix direction)
        angle_radians = math.atan2(dy, dx)
        
        # Convert to degrees and negate to flip direction
        angle_degrees = -math.degrees(angle_radians)
        
        # Adjust for tool starting parallel to Y-axis (add 90 degrees)
        adjusted_angle = angle_degrees + 90.0
        
        # Normalize angle to 0-360 range
        while adjusted_angle < 0:
            adjusted_angle += 360.0
        while adjusted_angle >= 360:
            adjusted_angle -= 360.0
        
        # Convert to inches: 1 inch = 360 degrees
        a_position_inches = adjusted_angle / 360.0
        
        # Round to 4 decimal places to reduce precision issues
        return round(a_position_inches, 4)
    
    def _calculate_continuous_a(self, target_a: float) -> float:
        """
        Calculate continuous A-axis position to avoid unnecessary 360° rotations.
        
        Args:
            target_a: Target A position (0.0 to 1.0)
            
        Returns:
            Continuous A position that takes shortest path from current position
        """
        # Calculate the difference between target and current
        diff = target_a - (self.current_a % 1.0)  # Normalize current_a to 0-1 range
        
        # If difference is greater than 0.5, it's shorter to go the other way
        if diff > 0.5:
            # Go backwards (subtract 1.0)
            continuous_a = self.current_a + diff - 1.0
        elif diff < -0.5:
            # Go forwards (add 1.0)
            continuous_a = self.current_a + diff + 1.0
        else:
            # Direct path is shortest
            continuous_a = self.current_a + diff
        
        # Update current position
        self.current_a = continuous_a
        
        return round(continuous_a, 4)


def main():
    """Test the toolpath generator with the DXF processor output."""
    # Initialize processors
    dxf_processor = DXFProcessor()
    toolpath_generator = ToolpathGenerator(
        cutting_height=-0.5,
        safe_height=0.0,
        corner_angle_threshold=5.0,
        feed_rate=1000.0,
        plunge_rate=200.0
    )
    
    # Process DXF file
    dxf_path = "test_2.dxf"
    
    try:
        # Get shapes from DXF processor
        shapes = dxf_processor.process_dxf(dxf_path)
        
        if not shapes:
            print("No shapes found in DXF file")
            return
        
        print(f"Processing {len(shapes)} shapes for toolpath generation...")
        
        # Generate toolpath
        gcode = toolpath_generator.generate_toolpath(shapes)
        
        # Save GCODE to file
        output_filename = f"toolpath_{dxf_path.split('/')[-1].replace('.dxf', '.gcode')}"
        with open(output_filename, 'w') as f:
            f.write(gcode)
        
        print(f"Toolpath saved to: {output_filename}")
        print(f"Generated {len(gcode.split(chr(10)))} lines of GCODE")
        
        # Show first few lines as preview
        print("\nGCODE Preview (first 20 lines):")
        print("-" * 50)
        lines = gcode.split('\n')
        for i, line in enumerate(lines[:20]):
            print(f"{i+1:3d}: {line}")
        if len(lines) > 20:
            print("...")
        
    except Exception as e:
        print(f"Error generating toolpath: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 