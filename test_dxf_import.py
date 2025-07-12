#!/usr/bin/env python3
"""
Test script for DXF import functionality.
This script helps debug DXF import issues by testing the import logic independently.
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_dxf_import():
    """Test DXF import functionality."""
    try:
        # Try to import ezdxf
        import ezdxf
        from ezdxf.math import Vec3
        logger.info("ezdxf imported successfully")
    except ImportError:
        logger.error("ezdxf not available. Install with: pip install ezdxf")
        return False
    
    # Test with a simple DXF file
    test_dxf_content = """0
SECTION
2
HEADER
9
$ACADVER
1
AC1014
9
$INSUNITS
70
4
0
ENDSEC
0
SECTION
2
ENTITIES
0
LINE
8
0
10
0.0
20
0.0
11
10.0
21
10.0
0
LINE
8
0
10
10.0
20
10.0
11
10.0
21
0.0
0
LINE
8
0
10
10.0
20
0.0
11
0.0
21
0.0
0
ENDSEC
0
EOF"""
    
    # Create a temporary DXF file
    test_file = "test_square.dxf"
    with open(test_file, 'w') as f:
        f.write(test_dxf_content)
    
    try:
        # Test import
        doc = ezdxf.readfile(test_file)
        msp = doc.modelspace()
        
        # Check for supported entities
        entities = []
        for e in msp:
            t = e.dxftype()
            logger.info(f"Found entity: {t}")
            if t in ('LINE', 'LWPOLYLINE', 'POLYLINE', 'SPLINE', 'ARC', 'CIRCLE'):
                entities.append(e)
        
        logger.info(f"Supported entities found: {len(entities)}")
        
        if not entities:
            logger.error("No supported entities found")
            return False
        
        # Test unit detection
        insunits = doc.header.get('$INSUNITS', 0)
        logger.info(f"INSUNITS: {insunits}")
        
        if insunits == 4:
            unit_scale = 1.0 / 25.4  # mm to in
        else:
            unit_scale = 1.0  # inches or unitless
        
        logger.info(f"Unit scale: {unit_scale}")
        
        # Test coordinate extraction
        all_x, all_y = [], []
        for e in entities:
            t = e.dxftype()
            if t == 'LINE':
                all_x += [e.dxf.start.x * unit_scale, e.dxf.end.x * unit_scale]
                all_y += [e.dxf.start.y * unit_scale, e.dxf.end.y * unit_scale]
                logger.info(f"LINE: ({e.dxf.start.x}, {e.dxf.start.y}) to ({e.dxf.end.x}, {e.dxf.end.y})")
        
        if all_x and all_y:
            min_x = min(all_x)
            min_y = min(all_y)
            max_x = max(all_x)
            max_y = max(all_y)
            logger.info(f"Extents: min_x={min_x:.3f}, min_y={min_y:.3f}, max_x={max_x:.3f}, max_y={max_y:.3f}")
            logger.info(f"Offset: dx={min_x:.3f}, dy={min_y:.3f}")
        else:
            logger.error("No coordinates extracted")
            return False
        
        logger.info("DXF import test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"DXF import test failed: {e}")
        return False
    finally:
        # Clean up
        if os.path.exists(test_file):
            os.remove(test_file)

def test_real_dxf_file(file_path):
    """Test with a real DXF file."""
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return False
    
    try:
        import ezdxf
        doc = ezdxf.readfile(file_path)
        msp = doc.modelspace()
        
        entities = []
        for e in msp:
            t = e.dxftype()
            if t in ('LINE', 'LWPOLYLINE', 'POLYLINE', 'SPLINE', 'ARC', 'CIRCLE'):
                entities.append(e)
        
        logger.info(f"Real DXF file analysis:")
        logger.info(f"  - File: {file_path}")
        logger.info(f"  - Supported entities: {len(entities)}")
        logger.info(f"  - Total entities: {len(list(msp))}")
        
        # Show entity types
        entity_types = {}
        for e in msp:
            t = e.dxftype()
            entity_types[t] = entity_types.get(t, 0) + 1
        
        logger.info("Entity types found:")
        for t, count in entity_types.items():
            logger.info(f"  - {t}: {count}")
        
        return len(entities) > 0
        
    except Exception as e:
        logger.error(f"Real DXF test failed: {e}")
        return False

if __name__ == "__main__":
    logger.info("=== DXF Import Test ===")
    
    # Test with generated DXF
    success = test_dxf_import()
    logger.info(f"Generated DXF test: {'PASSED' if success else 'FAILED'}")
    
    # Test with real DXF if provided
    if len(sys.argv) > 1:
        real_file = sys.argv[1]
        success = test_real_dxf_file(real_file)
        logger.info(f"Real DXF test: {'PASSED' if success else 'FAILED'}")
    else:
        logger.info("No real DXF file provided. Usage: python test_dxf_import.py <dxf_file>") 