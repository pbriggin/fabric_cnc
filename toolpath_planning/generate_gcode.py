#!/usr/bin/env python3
"""
Standalone G-code generator for continuous motion CNC cutting.
Processes DXF files and generates G-code with smooth continuous motion.
"""

import math
import logging
import sys
from pathlib import Path

# Add the parent directory to Python path for imports
sys.path.append(str(Path(__file__).parent.parent))

try:
    import ezdxf
    from ezdxf import readfile
except ImportError:
    print("Error: ezdxf not found. Install with: pip install ezdxf")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def calculate_angle_between_points(p1, p2, p3):
    """Calculate the angle between three points."""
    v1 = (p1[0] - p2[0], p1[1] - p2[1])
    v2 = (p3[0] - p2[0], p3[1] - p2[1])
    
    dot_product = v1[0] * v2[0] + v1[1] * v2[1]
    mag1 = math.sqrt(v1[0]**2 + v1[1]**2)
    mag2 = math.sqrt(v2[0]**2 + v2[1]**2)
    
    if mag1 == 0 or mag2 == 0:
        return 0
    
    cos_angle = dot_product / (mag1 * mag2)
    cos_angle = max(-1, min(1, cos_angle))  # Clamp to [-1, 1]
    angle_rad = math.acos(cos_angle)
    angle_deg = math.degrees(angle_rad)
    
    return angle_deg

def generate_continuous_circle_toolpath(center, radius, start_angle=0, end_angle=2*math.pi, step_size=0.1):
    """
    Generate smooth continuous toolpath for a circle like a 3D printer.
    
    Args:
        center: (x, y) center point
        radius: radius of circle
        start_angle: starting angle in radians (default: 0)
        end_angle: ending angle in radians (default: 2π for full circle)
        step_size: distance between points in inches (default: 0.1" for smooth motion)
    
    Returns:
        List of (x, y, angle, z) tuples for continuous cutting
    """
    cx, cy = center
    toolpath = []
    
    # For circles, use angle-based step sizing to ensure smooth motion
    # Calculate angle step to keep angle changes under 2 degrees
    max_angle_step = math.radians(1.5)  # 1.5 degrees for safety margin
    
    # Calculate total angle to cover
    total_angle = abs(end_angle - start_angle)
    if end_angle < start_angle:
        total_angle = 2*math.pi - total_angle
    
    # Calculate number of steps based on angle
    num_steps = max(32, min(256, int(total_angle / max_angle_step)))
    
    # Generate smooth waypoints using parametric equations
    for i in range(num_steps + 1):
        t = i / num_steps
        angle = start_angle + t * (end_angle - start_angle)
        
        # Parametric equations for circle
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        
        # Calculate tangent angle (perpendicular to radius)
        tangent_angle = angle + math.pi/2  # 90° from radius
        
        # Normalize angle to -180 to +180 range
        while tangent_angle > math.pi:
            tangent_angle -= 2 * math.pi
        while tangent_angle < -math.pi:
            tangent_angle += 2 * math.pi
        
        # Convert to absolute angle from vertical (home orientation)
        absolute_angle = -(math.degrees(tangent_angle) - 90.0)
        while absolute_angle > 180:
            absolute_angle -= 360
        while absolute_angle < -180:
            absolute_angle += 360
        
        # Z=0 for continuous cutting (no lifting)
        toolpath.append((x, y, math.radians(absolute_angle), 0))
    
    return toolpath

def generate_continuous_spline_toolpath(spline, step_size=0.1):
    """
    Generate smooth continuous toolpath for a spline like a 3D printer.
    
    Args:
        spline: ezdxf spline entity
        step_size: distance between points in inches (default: 0.1" for smooth motion)
    
    Returns:
        List of (x, y, angle, z) tuples for continuous cutting
    """
    toolpath = []
    
    try:
        # Use moderate-resolution flattening for smooth motion
        points = list(spline.flattening(0.01))  # Moderate precision for smooth motion
        
        if len(points) < 2:
            return toolpath
        
        # Calculate total length
        total_length = 0
        for i in range(1, len(points)):
            dx = points[i][0] - points[i-1][0]
            dy = points[i][1] - points[i-1][1]
            total_length += math.sqrt(dx*dx + dy*dy)
        
        # Calculate number of steps based on length and step size
        num_steps = max(32, min(128, int(total_length / step_size)))  # Reasonable point density
        
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
            
            # Calculate tangent vector
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            tangent_angle = math.atan2(dy, dx)
            
            # Convert to absolute angle from vertical (home orientation)
            absolute_angle = -(math.degrees(tangent_angle) - 90.0)
            while absolute_angle > 180:
                absolute_angle -= 360
            while absolute_angle < -180:
                absolute_angle += 360
            
            # Z=0 for continuous cutting (no lifting)
            toolpath.append((x, y, math.radians(absolute_angle), 0))
        
    except Exception as e:
        logger.error(f"Error generating continuous spline toolpath: {e}")
        # Fallback to discrete method with reasonable density
        points = list(spline.flattening(0.01))
        for i in range(0, len(points), max(1, len(points) // 64)):  # Limit to ~64 points
            if i < len(points):
                x, y = points[i][0], points[i][1]
                
                # Calculate tangent angle from next point
                if i + 1 < len(points):
                    next_x, next_y = points[i + 1][0], points[i + 1][1]
                    dx = next_x - x
                    dy = next_y - y
                else:
                    # Use previous point for last point
                    prev_x, prev_y = points[i - 1][0], points[i - 1][1]
                    dx = x - prev_x
                    dy = y - prev_y
                
                tangent_angle = math.atan2(dy, dx)
                
                # Convert to absolute angle
                absolute_angle = -(math.degrees(tangent_angle) - 90.0)
                while absolute_angle > 180:
                    absolute_angle -= 360
                while absolute_angle < -180:
                    absolute_angle += 360
                
                toolpath.append((x, y, math.radians(absolute_angle), 0))
    
    return toolpath

def generate_gcode_continuous_motion(toolpaths, feed_rate=100, z_up=5, z_down=-1):
    """
    Generate G-code for continuous motion like a 3D printer.
    
    Args:
        toolpaths: List of toolpath segments
        feed_rate: Feed rate in mm/min
        z_up: Z height when tool is up (mm)
        z_down: Z depth when cutting (mm)
    
    Returns:
        List of G-code commands
    """
    gcode = []
    
    # Initialize
    gcode.append("; Continuous Motion G-code Generated")
    gcode.append("; Feed rate: {} mm/min".format(feed_rate))
    gcode.append("G21 ; Set units to mm")
    gcode.append("G90 ; Absolute positioning")
    gcode.append("G28 ; Home all axes")
    gcode.append("G0 Z{} ; Move to safe Z height".format(z_up))
    
    current_x = 0
    current_y = 0
    current_z = z_up
    
    for i, toolpath in enumerate(toolpaths):
        gcode.append("; Toolpath {}".format(i + 1))
        
        if not toolpath:
            continue
        
        # Move to start position
        start_x, start_y, start_angle, start_z = toolpath[0]
        gcode.append("G0 X{:.3f} Y{:.3f} ; Move to start".format(start_x, start_y))
        
        # Lower Z for cutting
        if start_z == 0:  # Continuous cutting
            gcode.append("G1 Z{} F{} ; Lower for cutting".format(z_down, feed_rate))
            current_z = z_down
        else:  # Z up
            gcode.append("G1 Z{} F{} ; Move to Z height".format(z_up, feed_rate))
            current_z = z_up
        
        # Generate continuous motion commands
        for j, (x, y, angle, z) in enumerate(toolpath):
            if j == 0:
                continue  # Skip first point (already positioned)
            
            # Check if we need to change Z
            if z == 0 and current_z != z_down:
                gcode.append("G1 Z{} F{} ; Lower for cutting".format(z_down, feed_rate))
                current_z = z_down
            elif z != 0 and current_z != z_up:
                gcode.append("G1 Z{} F{} ; Raise tool".format(z_up, feed_rate))
                current_z = z_up
            
            # Generate motion command
            if current_z == z_down:
                # Cutting motion - use G1 for linear interpolation
                gcode.append("G1 X{:.3f} Y{:.3f} F{} ; Continuous cutting".format(x, y, feed_rate))
            else:
                # Rapid motion - use G0 for rapid positioning
                gcode.append("G0 X{:.3f} Y{:.3f} ; Rapid move".format(x, y))
            
            current_x = x
            current_y = y
        
        # Raise tool at end of toolpath
        if current_z != z_up:
            gcode.append("G1 Z{} F{} ; Raise tool".format(z_up, feed_rate))
            current_z = z_up
    
    # Final commands
    gcode.append("G0 X0 Y0 ; Return to origin")
    gcode.append("G28 ; Home all axes")
    gcode.append("M2 ; End program")
    
    return gcode

def process_dxf_file(dxf_path, output_path=None, feed_rate=100, z_up=5, z_down=-1):
    """
    Process a DXF file and generate continuous motion G-code.
    
    Args:
        dxf_path: Path to input DXF file
        output_path: Path to output G-code file (optional)
        feed_rate: Feed rate in mm/min
        z_up: Z height when tool is up (mm)
        z_down: Z depth when cutting (mm)
    
    Returns:
        List of G-code commands
    """
    logger.info(f"Processing DXF file: {dxf_path}")
    
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
        
        logger.info(f"Found {len(entities)} supported entities")
        
        # Detect units
        insunits = doc.header.get('$INSUNITS', 0)
        if insunits == 4:
            unit_scale = 1.0 / 25.4  # mm to inches
        else:
            unit_scale = 1.0  # inches or unitless
        
        # Calculate bounding box for offset
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
                # Generate points around circle for bounding box
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
        
        # Generate toolpaths
        continuous_toolpaths = []
        
        for i, e in enumerate(entities):
            t = e.dxftype()
            logger.info(f"Processing entity {i+1}/{len(entities)}: {t}")
            
            if t == 'SPLINE':
                # Generate continuous toolpath for spline
                continuous_path = generate_continuous_spline_toolpath(e, step_size=0.1)
                
                # Transform coordinates
                transformed_path = []
                for x, y, angle, z in continuous_path:
                    tx = (x * unit_scale) + dx
                    ty = (y * unit_scale) + dy
                    transformed_path.append((tx, ty, angle, z))
                
                if transformed_path:
                    continuous_toolpaths.append(transformed_path)
                    logger.info(f"  Generated {len(transformed_path)} smooth waypoints")
                
            elif t == 'CIRCLE':
                center = e.dxf.center
                radius = e.dxf.radius
                
                # Generate continuous toolpath for full circle
                continuous_path = generate_continuous_circle_toolpath(
                    (center.x, center.y), radius, 
                    start_angle=0, end_angle=2*math.pi, 
                    step_size=0.1
                )
                
                # Transform coordinates
                transformed_path = []
                for x, y, angle, z in continuous_path:
                    tx = (x * unit_scale) + dx
                    ty = (y * unit_scale) + dy
                    transformed_path.append((tx, ty, angle, z))
                
                if transformed_path:
                    continuous_toolpaths.append(transformed_path)
                    logger.info(f"  Generated {len(transformed_path)} smooth waypoints")
                
            elif t == 'ARC':
                center = e.dxf.center
                radius = e.dxf.radius
                start_angle = math.radians(e.dxf.start_angle)
                end_angle = math.radians(e.dxf.end_angle)
                
                # Handle angle wrapping
                if end_angle < start_angle:
                    end_angle += 2 * math.pi
                
                # Generate continuous toolpath for arc
                continuous_path = generate_continuous_circle_toolpath(
                    (center.x, center.y), radius,
                    start_angle=start_angle, end_angle=end_angle,
                    step_size=0.1
                )
                
                # Transform coordinates
                transformed_path = []
                for x, y, angle, z in continuous_path:
                    tx = (x * unit_scale) + dx
                    ty = (y * unit_scale) + dy
                    transformed_path.append((tx, ty, angle, z))
                
                if transformed_path:
                    continuous_toolpaths.append(transformed_path)
                    logger.info(f"  Generated {len(transformed_path)} smooth waypoints")
        
        # Generate G-code
        logger.info(f"Generating G-code for {len(continuous_toolpaths)} toolpaths")
        gcode = generate_gcode_continuous_motion(continuous_toolpaths, feed_rate, z_up, z_down)
        
        # Save to file if output path provided
        if output_path:
            try:
                with open(output_path, 'w') as f:
                    for command in gcode:
                        f.write(command + '\n')
                logger.info(f"G-code saved to: {output_path}")
            except Exception as e:
                logger.error(f"Failed to save G-code: {e}")
        
        return gcode
        
    except Exception as e:
        logger.error(f"Failed to process DXF file: {e}")
        return []

def main():
    """Main function for command-line usage."""
    if len(sys.argv) < 2:
        print("Usage: python generate_gcode.py <dxf_file> [output_file] [feed_rate]")
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
        output_path = Path(dxf_path).with_suffix('.gcode')
    
    print(f"Processing: {dxf_path}")
    print(f"Output: {output_path}")
    print(f"Feed rate: {feed_rate} mm/min")
    print("=" * 50)
    
    gcode = process_dxf_file(dxf_path, output_path, feed_rate)
    
    if gcode:
        print(f"✅ Successfully generated {len(gcode)} G-code commands")
        print(f"📁 Saved to: {output_path}")
    else:
        print("❌ Failed to generate G-code")
        sys.exit(1)

if __name__ == "__main__":
    main() 