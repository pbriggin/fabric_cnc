#!/usr/bin/env python3
"""
Enhanced G-code generator for continuous motion CNC cutting.
Processes DXF files and generates G-code with ultra-smooth continuous motion.
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

# Import the improved continuous toolpath generator
from .continuous_toolpath_generator import ContinuousToolpathGenerator

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

def generate_continuous_circle_toolpath(center, radius, start_angle=0, end_angle=2*math.pi, step_size=0.05):
    """
    Generate smooth continuous toolpath for a circle using the improved generator.
    
    Args:
        center: (x, y) center point
        radius: radius of circle
        start_angle: starting angle in radians (default: 0)
        end_angle: ending angle in radians (default: 2π for full circle)
        step_size: distance between points in inches (default: 0.05" for ultra-smooth motion)
    
    Returns:
        List of (x, y, angle, z) tuples for continuous cutting
    """
    generator = ContinuousToolpathGenerator(step_size=step_size)
    return generator.generate_continuous_circle_path(center, radius, start_angle, end_angle)

def generate_continuous_spline_toolpath(spline, step_size=0.05):
    """
    Generate smooth continuous toolpath for a spline using the improved generator.
    
    Args:
        spline: ezdxf spline entity
        step_size: distance between points in inches (default: 0.05" for ultra-smooth motion)
    
    Returns:
        List of (x, y, angle, z) tuples for continuous cutting
    """
    generator = ContinuousToolpathGenerator(step_size=step_size)
    return generator.generate_continuous_spline_path(spline)

def generate_continuous_polyline_toolpath(polyline, step_size=0.05):
    """
    Generate smooth continuous toolpath for a polyline using the improved generator.
    
    Args:
        polyline: ezdxf polyline entity
        step_size: distance between points in inches (default: 0.05" for ultra-smooth motion)
    
    Returns:
        List of (x, y, angle, z) tuples for continuous cutting
    """
    generator = ContinuousToolpathGenerator(step_size=step_size)
    return generator.generate_continuous_polyline_path(polyline)

def generate_continuous_line_toolpath(line, step_size=0.05):
    """
    Generate smooth continuous toolpath for a line using the improved generator.
    
    Args:
        line: ezdxf line entity
        step_size: distance between points in inches (default: 0.05" for ultra-smooth motion)
    
    Returns:
        List of (x, y, angle, z) tuples for continuous cutting
    """
    generator = ContinuousToolpathGenerator(step_size=step_size)
    return generator.generate_continuous_line_path(line)

def generate_gcode_continuous_motion(toolpaths, feed_rate=100, z_up=5, z_down=-1):
    """
    Generate G-code for continuous motion using the improved generator.
    
    Args:
        toolpaths: List of toolpath lists, each containing (x, y, angle, z) tuples
        feed_rate: Feed rate in mm/min
        z_up: Z height when tool is up (mm)
        z_down: Z height when tool is down (mm)
    
    Returns:
        List of G-code commands
    """
    generator = ContinuousToolpathGenerator(feed_rate, z_up, z_down)
    return generator.generate_gcode_continuous(toolpaths)

def process_dxf_file(dxf_path, output_path=None, feed_rate=100, z_up=5, z_down=-1):
    """
    Process a DXF file and generate continuous motion G-code.
    
    Args:
        dxf_path: Path to input DXF file
        output_path: Path to output G-code file (optional)
        feed_rate: Feed rate in mm/min
        z_up: Z height when tool is up (mm)
        z_down: Z height when tool is down (mm)
    
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
                continuous_path = generate_continuous_spline_toolpath(e, step_size=0.05)
                
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
                    step_size=0.05
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
                    step_size=0.05
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