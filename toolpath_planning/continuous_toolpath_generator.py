#!/usr/bin/env python3
"""
Continuous Toolpath Generator - Enhanced for Ultra-Smooth Motion
Generates truly continuous motion without any stopping between segments.
Optimized for smooth curves, splines, and complex shapes.
"""

import math
import logging
import sys
from pathlib import Path
from typing import List, Tuple, Optional, Callable
import numpy as np

try:
    import ezdxf
    from ezdxf import readfile
    from ezdxf.math import Vec3, BSpline
except ImportError:
    print("Error: ezdxf not found. Install with: pip install ezdxf")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class ContinuousToolpathGenerator:
    """
    Generates truly continuous toolpaths without any segmentation or stopping.
    Each entity becomes a single continuous motion path with ultra-smooth curves.
    """
    
    def __init__(self, feed_rate=100, z_up=5, z_down=-1, step_size=0.05, 
                 max_angle_step_deg=1.0, spline_precision=0.001):
        self.feed_rate = feed_rate
        self.z_up = z_up
        self.z_down = z_down
        self.step_size = step_size  # Reduced for smoother motion
        self.max_angle_step_rad = math.radians(max_angle_step_deg)
        self.spline_precision = spline_precision
    
    def _calculate_tangent_angle(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        """
        Calculate the tangent angle between two points.
        Returns angle in radians, normalized to -π to π.
        """
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        angle = math.atan2(dy, dx)
        
        # Normalize to -π to π
        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi
            
        return angle
    
    def _convert_to_absolute_angle(self, tangent_angle: float) -> float:
        """
        Convert tangent angle to absolute angle from vertical (home orientation).
        Returns angle in radians, normalized to -π to π.
        """
        # Convert to degrees, adjust for home orientation (vertical = 0°)
        absolute_angle_deg = -(math.degrees(tangent_angle) - 90.0)
        
        # Normalize to -180° to +180°
        while absolute_angle_deg > 180:
            absolute_angle_deg -= 360
        while absolute_angle_deg < -180:
            absolute_angle_deg += 360
            
        return math.radians(absolute_angle_deg)
    
    def generate_continuous_spline_path(self, spline) -> List[Tuple[float, float, float, float]]:
        """
        Generate a single continuous path for a spline with ultra-smooth motion.
        Uses adaptive step sizing based on curvature for optimal smoothness.
        Returns: List of (x, y, angle, z) tuples for continuous motion
        """
        try:
            # Use high-resolution flattening for maximum smoothness
            points = list(spline.flattening(self.spline_precision))
            
            if len(points) < 2:
                return []
            
            # Calculate curvature-based adaptive step sizing
            toolpath = []
            
            # For splines, we need to ensure smooth angle transitions
            # Use more points for higher curvature regions
            total_length = 0
            curvatures = []
            
            # Calculate total length and estimate curvature at each point
            for i in range(len(points)):
                if i > 0:
                    dx = points[i][0] - points[i-1][0]
                    dy = points[i][1] - points[i-1][1]
                    segment_length = math.sqrt(dx*dx + dy*dy)
                    total_length += segment_length
                
                # Estimate curvature using three points
                if i > 0 and i < len(points) - 1:
                    p1 = points[i-1]
                    p2 = points[i]
                    p3 = points[i+1]
                    
                    # Calculate angle change
                    angle1 = self._calculate_tangent_angle(p1, p2)
                    angle2 = self._calculate_tangent_angle(p2, p3)
                    angle_diff = abs(angle2 - angle1)
                    
                    # Normalize angle difference
                    while angle_diff > math.pi:
                        angle_diff = 2 * math.pi - angle_diff
                    
                    curvatures.append(angle_diff)
                else:
                    curvatures.append(0)
            
            # Adaptive step sizing based on curvature
            max_curvature = max(curvatures) if curvatures else 0
            base_steps = max(128, min(1024, int(total_length / self.step_size)))
            
            if max_curvature > 0:
                # Increase steps in high-curvature regions
                curvature_factor = min(3.0, max_curvature / (math.pi / 6))  # Cap at 3x
                num_steps = int(base_steps * curvature_factor)
            else:
                num_steps = base_steps
            
            logger.info(f"Spline: {len(points)} points, {total_length:.3f} length, "
                       f"max curvature: {math.degrees(max_curvature):.2f}°, {num_steps} steps")
            
            # Generate smooth waypoints along the spline
            for i in range(num_steps + 1):
                t = i / num_steps
                
                # Find the segment and interpolate within it
                segment_idx = int(t * (len(points) - 1))
                segment_t = t * (len(points) - 1) - segment_idx
                
                if segment_idx >= len(points) - 1:
                    segment_idx = len(points) - 2
                    segment_t = 1.0
                
                # Linear interpolation between points
                p1 = points[segment_idx]
                p2 = points[segment_idx + 1]
                x = p1[0] + segment_t * (p2[0] - p1[0])
                y = p1[1] + segment_t * (p2[1] - p1[1])
                
                # Calculate tangent angle
                tangent_angle = self._calculate_tangent_angle(p1, p2)
                absolute_angle = self._convert_to_absolute_angle(tangent_angle)
                
                # Z=0 for continuous cutting (no lifting)
                toolpath.append((x, y, absolute_angle, 0))
            
            return toolpath
            
        except Exception as e:
            logger.error(f"Error generating continuous spline path: {e}")
            return []
    
    def generate_continuous_circle_path(self, center, radius, start_angle=0, end_angle=2*math.pi) -> List[Tuple[float, float, float, float]]:
        """
        Generate a single continuous path for a circle/arc with ultra-smooth motion.
        Uses angle-based step sizing for perfect circular motion.
        Returns: List of (x, y, angle, z) tuples for continuous motion
        """
        cx, cy = center
        toolpath = []
        
        # Use angle-based step sizing for perfect smoothness
        # Calculate total angle to cover
        total_angle = abs(end_angle - start_angle)
        if end_angle < start_angle:
            total_angle = 2*math.pi - total_angle
        
        # Calculate number of steps based on angle change threshold
        num_steps = max(64, min(512, int(total_angle / self.max_angle_step_rad)))
        
        logger.info(f"Circle: radius={radius:.3f}, angles={math.degrees(start_angle):.1f}° to "
                   f"{math.degrees(end_angle):.1f}°, {num_steps} steps")
        
        # Generate continuous waypoints using parametric equations
        for i in range(num_steps + 1):
            t = i / num_steps
            angle = start_angle + t * (end_angle - start_angle)
            
            # Parametric equations for circle
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            
            # Calculate cutting blade orientation (tangent to circle)
            # For circles, the cutting blade should be tangent to the circle
            # The angle parameter is the angle around the circle (counterclockwise)
            # For counterclockwise circle motion, cutting blade should rotate clockwise to stay tangent
            cutting_angle = angle - math.pi/2  # -90° from radius = tangent to circle (correct direction)
            # Convert to machine coordinate system (vertical = 0°)
            absolute_angle = cutting_angle
            
            # Z=0 for continuous cutting (no lifting)
            toolpath.append((x, y, absolute_angle, 0))
        
        return toolpath
    
    def generate_continuous_polyline_path(self, polyline) -> List[Tuple[float, float, float, float]]:
        """
        Generate a single continuous path for a polyline with smooth transitions.
        Returns: List of (x, y, angle, z) tuples for continuous motion
        """
        try:
            # Get polyline points
            if polyline.dxftype() == 'LWPOLYLINE':
                points = [p[:2] for p in polyline.get_points()]
            else:  # POLYLINE
                points = [(v.dxf.x, v.dxf.y) for v in polyline.vertices()]
            
            if len(points) < 2:
                return []
            
            toolpath = []
            
            # Generate continuous path through all segments
            for i in range(len(points) - 1):
                start_point = points[i]
                end_point = points[i + 1]
                
                # Calculate segment length
                dx = end_point[0] - start_point[0]
                dy = end_point[1] - start_point[1]
                segment_length = math.sqrt(dx*dx + dy*dy)
                
                # Calculate number of steps for this segment
                num_steps = max(16, int(segment_length / self.step_size))
                
                # Generate points along this segment
                for j in range(num_steps + 1):
                    t = j / num_steps
                    x = start_point[0] + t * dx
                    y = start_point[1] + t * dy
                    
                    # Calculate tangent angle
                    tangent_angle = self._calculate_tangent_angle(start_point, end_point)
                    absolute_angle = self._convert_to_absolute_angle(tangent_angle)
                    
                    # Z=0 for continuous cutting
                    toolpath.append((x, y, absolute_angle, 0))
            
            return toolpath
            
        except Exception as e:
            logger.error(f"Error generating continuous polyline path: {e}")
            return []
    
    def generate_continuous_line_path(self, line) -> List[Tuple[float, float, float, float]]:
        """
        Generate a single continuous path for a line with smooth motion.
        Returns: List of (x, y, angle, z) tuples for continuous motion
        """
        try:
            start_point = (line.dxf.start.x, line.dxf.start.y)
            end_point = (line.dxf.end.x, line.dxf.end.y)
            
            # Calculate line length
            dx = end_point[0] - start_point[0]
            dy = end_point[1] - start_point[1]
            line_length = math.sqrt(dx*dx + dy*dy)
            
            # Calculate number of steps
            num_steps = max(16, int(line_length / self.step_size))
            
            toolpath = []
            
            # Generate points along the line
            for i in range(num_steps + 1):
                t = i / num_steps
                x = start_point[0] + t * dx
                y = start_point[1] + t * dy
                
                # Calculate tangent angle
                tangent_angle = self._calculate_tangent_angle(start_point, end_point)
                absolute_angle = self._convert_to_absolute_angle(tangent_angle)
                
                # Z=0 for continuous cutting
                toolpath.append((x, y, absolute_angle, 0))
            
            return toolpath
            
        except Exception as e:
            logger.error(f"Error generating continuous line path: {e}")
            return []
    
    def generate_gcode_continuous(self, toolpaths: List[List[Tuple[float, float, float, float]]]) -> List[str]:
        """
        Generate G-code for truly continuous motion without any stopping.
        Each toolpath is executed as a single continuous motion.
        """
        gcode = []
        
        # Initialize
        gcode.append("; Continuous Motion G-code - Ultra-Smooth Motion")
        gcode.append(f"; Feed rate: {self.feed_rate} mm/min")
        gcode.append("G21 ; Set units to mm")
        gcode.append("G90 ; Absolute positioning")
        gcode.append("G28 ; Home all axes")
        gcode.append(f"G0 Z{self.z_up} ; Move to safe Z height")
        
        current_x = 0
        current_y = 0
        current_z = self.z_up
        
        for i, toolpath in enumerate(toolpaths):
            if not toolpath:
                continue
            
            gcode.append(f"; Continuous Toolpath {i + 1} - {len(toolpath)} points")
            
            # Move to start position
            start_x, start_y, start_angle, start_z = toolpath[0]
            gcode.append(f"G0 X{start_x:.3f} Y{start_y:.3f} ; Move to start")
            
            # Lower Z for continuous cutting
            gcode.append(f"G1 Z{self.z_down} F{self.feed_rate} ; Lower for continuous cutting")
            current_z = self.z_down
            
            # Generate continuous motion commands - NO STOPPING
            for j, (x, y, angle, z) in enumerate(toolpath):
                if j == 0:
                    continue  # Skip first point (already positioned)
                
                # Continuous cutting motion - no Z changes during path
                gcode.append(f"G1 X{x:.3f} Y{y:.3f} F{self.feed_rate} ; Continuous motion")
                current_x = x
                current_y = y
            
            # Raise tool at end of continuous path
            gcode.append(f"G1 Z{self.z_up} F{self.feed_rate} ; Raise tool")
            current_z = self.z_up
        
        # Final commands
        gcode.append("G0 X0 Y0 ; Return to origin")
        gcode.append("G28 ; Home all axes")
        gcode.append("M2 ; End program")
        
        return gcode

def process_dxf_continuous(dxf_path: str, output_path: Optional[str] = None, 
                         feed_rate: int = 100, z_up: int = 5, z_down: int = -1) -> List[str]:
    """
    Process DXF file and generate truly continuous toolpaths without any stopping.
    """
    logger.info(f"Processing DXF file for continuous motion: {dxf_path}")
    
    try:
        # Read DXF file
        doc = readfile(dxf_path)
        msp = doc.modelspace()
        
        # Find supported entities
        entities = []
        for e in msp:
            t = e.dxftype()
            if t in ('LINE', 'LWPOLYLINE', 'POLYLINE', 'SPLINE', 'ARC', 'CIRCLE'):
                entities.append(e)
        
        if not entities:
            logger.error("No supported entities found in DXF file")
            return []
        
        logger.info(f"Found {len(entities)} entities for continuous processing")
        
        # Detect units
        insunits = doc.header.get('$INSUNITS', 0)
        if insunits == 4:
            unit_scale = 1.0 / 25.4  # mm to inches
        else:
            unit_scale = 1.0  # inches or unitless
        
        # Calculate bounding box for centering
        all_x, all_y = [], []
        for e in entities:
            t = e.dxftype()
            if t == 'LINE':
                all_x.extend([e.dxf.start.x * unit_scale, e.dxf.end.x * unit_scale])
                all_y.extend([e.dxf.start.y * unit_scale, e.dxf.end.y * unit_scale])
            elif t in ('LWPOLYLINE', 'POLYLINE'):
                pts = [p[:2] for p in e.get_points()] if t == 'LWPOLYLINE' else [(v.dxf.x, v.dxf.y) for v in e.vertices()]
                for x, y in pts:
                    all_x.append(x * unit_scale)
                    all_y.append(y * unit_scale)
            elif t == 'CIRCLE':
                center = e.dxf.center
                radius = e.dxf.radius
                for i in range(64):
                    angle = 2 * math.pi * i / 64
                    x = center.x + radius * math.cos(angle)
                    y = center.y + radius * math.sin(angle)
                    all_x.append(x * unit_scale)
                    all_y.append(y * unit_scale)
            elif t == 'SPLINE':
                points = list(e.flattening(0.01))
                for pt in points:
                    if len(pt) >= 2:
                        all_x.append(pt[0] * unit_scale)
                        all_y.append(pt[1] * unit_scale)
        
        if not all_x or not all_y:
            logger.error("No valid points found for bounding box")
            return []
        
        # Calculate offset to center the design
        min_x, min_y = min(all_x), min(all_y)
        max_x, max_y = max(all_x), max(all_y)
        dx = -(min_x + max_x) / 2  # Center X
        dy = -(min_y + max_y) / 2  # Center Y
        
        logger.info(f"Design bounds: X({min_x:.3f}, {max_x:.3f}), Y({min_y:.3f}, {max_y:.3f})")
        logger.info(f"Offset: dx={dx:.3f}, dy={dy:.3f}")
        
        # Initialize continuous toolpath generator
        generator = ContinuousToolpathGenerator(feed_rate, z_up, z_down)
        
        # Generate continuous toolpaths
        continuous_toolpaths = []
        
        for i, e in enumerate(entities):
            t = e.dxftype()
            logger.info(f"Processing entity {i+1}/{len(entities)}: {t}")
            
            if t == 'SPLINE':
                # Generate single continuous path for spline
                continuous_path = generator.generate_continuous_spline_path(e)
                
                # Transform coordinates
                transformed_path = []
                for x, y, angle, z in continuous_path:
                    tx = (x * unit_scale) + dx
                    ty = (y * unit_scale) + dy
                    transformed_path.append((tx, ty, angle, z))
                
                if transformed_path:
                    continuous_toolpaths.append(transformed_path)
                    logger.info(f"  Generated {len(transformed_path)} continuous waypoints")
                
            elif t == 'CIRCLE':
                center = e.dxf.center
                radius = e.dxf.radius
                
                # Generate single continuous path for full circle
                continuous_path = generator.generate_continuous_circle_path(
                    (center.x, center.y), radius
                )
                
                # Transform coordinates
                transformed_path = []
                for x, y, angle, z in continuous_path:
                    tx = (x * unit_scale) + dx
                    ty = (y * unit_scale) + dy
                    transformed_path.append((tx, ty, angle, z))
                
                if transformed_path:
                    continuous_toolpaths.append(transformed_path)
                    logger.info(f"  Generated {len(transformed_path)} continuous waypoints")
                
            elif t == 'ARC':
                center = e.dxf.center
                radius = e.dxf.radius
                start_angle = math.radians(e.dxf.start_angle)
                end_angle = math.radians(e.dxf.end_angle)
                
                # Handle angle wrapping
                if end_angle < start_angle:
                    end_angle += 2 * math.pi
                
                # Generate single continuous path for arc
                continuous_path = generator.generate_continuous_circle_path(
                    (center.x, center.y), radius,
                    start_angle=start_angle, end_angle=end_angle
                )
                
                # Transform coordinates
                transformed_path = []
                for x, y, angle, z in continuous_path:
                    tx = (x * unit_scale) + dx
                    ty = (y * unit_scale) + dy
                    transformed_path.append((tx, ty, angle, z))
                
                if transformed_path:
                    continuous_toolpaths.append(transformed_path)
                    logger.info(f"  Generated {len(transformed_path)} continuous waypoints")
            
            elif t in ('LWPOLYLINE', 'POLYLINE'):
                # Generate single continuous path for polyline
                continuous_path = generator.generate_continuous_polyline_path(e)
                
                # Transform coordinates
                transformed_path = []
                for x, y, angle, z in continuous_path:
                    tx = (x * unit_scale) + dx
                    ty = (y * unit_scale) + dy
                    transformed_path.append((tx, ty, angle, z))
                
                if transformed_path:
                    continuous_toolpaths.append(transformed_path)
                    logger.info(f"  Generated {len(transformed_path)} continuous waypoints")
        
        # Generate G-code for continuous motion
        logger.info(f"Generating continuous G-code for {len(continuous_toolpaths)} toolpaths")
        gcode = generator.generate_gcode_continuous(continuous_toolpaths)
        
        # Save to file if output path provided
        if output_path:
            try:
                with open(output_path, 'w') as f:
                    for command in gcode:
                        f.write(command + '\n')
                logger.info(f"Continuous G-code saved to: {output_path}")
            except Exception as e:
                logger.error(f"Failed to save G-code: {e}")
        
        return gcode
        
    except Exception as e:
        logger.error(f"Failed to process DXF file: {e}")
        return []

def main():
    """Main function for command-line usage."""
    if len(sys.argv) < 2:
        print("Usage: python continuous_toolpath_generator.py <dxf_file> [output_file] [feed_rate]")
        print("  dxf_file: Input DXF file path")
        print("  output_file: Output G-code file path (optional)")
        print("  feed_rate: Feed rate in mm/min (default: 100)")
        sys.exit(1)
    
    dxf_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    feed_rate = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    
    if not Path(dxf_path).exists():
        print(f"Error: DXF file not found: {dxf_path}")
        sys.exit(1)
    
    if output_path is None:
        output_path = Path(dxf_path).with_suffix('.continuous.gcode')
    
    print(f"🔄 Processing: {dxf_path}")
    print(f"📁 Output: {output_path}")
    print(f"⚡ Feed rate: {feed_rate} mm/min")
    print("🚀 Generating TRULY CONTINUOUS motion - NO STOPPING between segments!")
    print("=" * 60)
    
    gcode = process_dxf_continuous(dxf_path, output_path, feed_rate)
    
    if gcode:
        print(f"✅ Successfully generated {len(gcode)} continuous G-code commands")
        print(f"📁 Saved to: {output_path}")
        print("🎯 Each entity is now a SINGLE CONTINUOUS MOTION PATH!")
    else:
        print("❌ Failed to generate continuous G-code")
        sys.exit(1)

if __name__ == "__main__":
    main() 