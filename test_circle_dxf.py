#!/usr/bin/env python3
import ezdxf
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_dxf_loading(filename):
    """Test DXF loading and entity processing"""
    try:
        # Load DXF file
        doc = ezdxf.readfile(filename)
        msp = doc.modelspace()
        entities = list(msp)
        
        logger.info(f"DXF file loaded successfully")
        logger.info(f"Found {len(entities)} entities")
        
        # Process entities
        all_x, all_y = [], []
        for e in entities:
            t = e.dxftype()
            logger.info(f"Processing entity type: {t}")
            
            if t == 'LINE':
                all_x.extend([e.dxf.start.x, e.dxf.end.x])
                all_y.extend([e.dxf.start.y, e.dxf.end.y])
                logger.info(f"  LINE: ({e.dxf.start.x}, {e.dxf.start.y}) -> ({e.dxf.end.x}, {e.dxf.end.y})")
            elif t in ('LWPOLYLINE', 'POLYLINE'):
                pts = [p[:2] for p in e.get_points()] if t == 'LWPOLYLINE' else [(v.dxf.x, v.dxf.y) for v in e.vertices()]
                for x, y in pts:
                    all_x.append(x)
                    all_y.append(y)
                logger.info(f"  {t}: {len(pts)} points")
            elif t == 'CIRCLE':
                center = e.dxf.center
                r = e.dxf.radius
                logger.info(f"  CIRCLE: center=({center.x}, {center.y}), radius={r}")
                # Generate points around the circle circumference
                import math
                n = 32
                for i in range(n):
                    angle = 2 * math.pi * i / n
                    x = center.x + r * math.cos(angle)
                    y = center.y + r * math.sin(angle)
                    all_x.append(x)
                    all_y.append(y)
                logger.info(f"  Generated {n} points around circle circumference")
            elif t == 'SPLINE':
                logger.info(f"  SPLINE: flattening to points")
                # Flatten spline to points for bounding box calculation
                pts = list(e.flattening(0.1))
                for pt in pts:
                    if len(pt) >= 2:
                        all_x.append(pt[0])
                        all_y.append(pt[1])
                logger.info(f"  Generated {len(pts)} points from spline")
            elif t == 'HATCH':
                logger.info(f"  HATCH: skipping (no geometry for bounding box)")
        
        logger.info(f"Collected {len(all_x)} points for bounding box calculation")
        
        if not all_x or not all_y:
            logger.error("No valid points found in DXF file")
            return False
            
        min_x = min(all_x)
        min_y = min(all_y)
        max_x = max(all_x)
        max_y = max(all_y)
        
        logger.info(f"Bounding box: min_x={min_x:.3f}, min_y={min_y:.3f}, max_x={max_x:.3f}, max_y={max_y:.3f}")
        return True
        
    except Exception as e:
        logger.error(f"Error processing DXF: {e}")
        return False

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        test_dxf_loading(filename)
    else:
        print("Usage: python test_circle_dxf.py <dxf_file>") 