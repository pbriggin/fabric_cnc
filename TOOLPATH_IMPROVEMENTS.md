# Fabric CNC Toolpath Improvements

## Overview

The toolpath generation system has been significantly improved to provide **ultra-smooth continuous motion** for all types of DXF entities, including complex curves, splines, and circles.

## Key Improvements

### 1. Enhanced Spline Handling
- **Adaptive step sizing** based on curvature
- **High-precision flattening** (0.001" tolerance)
- **Smooth angle transitions** with no sharp corners
- **Curvature-based point density** - more points in high-curvature regions

### 2. Improved Circle/Arc Generation
- **Angle-based step sizing** for perfect circular motion
- **1-degree maximum angle steps** for ultra-smooth curves
- **Parametric equations** for mathematically perfect circles
- **No segmentation** - true continuous motion

### 3. Better Polyline Processing
- **Smooth transitions** between line segments
- **Consistent step sizing** across all segments
- **Proper angle calculations** for tool orientation

### 4. Unified Toolpath Generation
- **Single continuous motion** for each entity
- **No stopping between segments**
- **Consistent Z-height management**
- **Optimized G-code generation**

## Technical Details

### Step Size Optimization
- **Default step size**: 0.05" (reduced from 0.1" for smoother motion)
- **Maximum angle step**: 1.0° (configurable)
- **Spline precision**: 0.001" (high precision for smooth curves)

### Angle Calculations
- **Tangent angle calculation** for proper tool orientation
- **Absolute angle conversion** from vertical home position
- **Angle normalization** to prevent discontinuities
- **Smooth angle transitions** throughout the path

### Curvature Analysis
- **Three-point curvature estimation** for splines
- **Adaptive point density** based on local curvature
- **Maximum 3x point density** in high-curvature regions
- **Minimum 128 points** for any spline

## Testing

### Test Scripts
1. **`create_test_dxf.py`** - Creates test DXF files with various shapes
2. **`test_toolpath_generation.py`** - Tests toolpath generation and smoothness

### Running Tests
```bash
# Create test DXF files
python create_test_dxf.py

# Test toolpath generation
python test_toolpath_generation.py

# Test in main application
python main_app.py
```

### Test Files Created
- `test_circle.dxf` - Simple circle
- `test_spline.dxf` - Smooth spline curve
- `test_polyline.dxf` - Star-shaped polyline
- `test_complex.dxf` - Multiple shapes
- `test_arc.dxf` - Various arcs

## Usage

### In Main Application
1. **Import DXF file** - Supports LINE, LWPOLYLINE, POLYLINE, SPLINE, ARC, CIRCLE
2. **Generate toolpath** - Creates ultra-smooth continuous motion
3. **Preview motion** - See the smooth toolpath animation
4. **Run toolpath** - Execute the continuous motion

### Programmatic Usage
```python
from toolpath_planning import ContinuousToolpathGenerator

# Create generator with custom parameters
generator = ContinuousToolpathGenerator(
    feed_rate=100,
    z_up=5,
    z_down=-1,
    step_size=0.05,
    max_angle_step_deg=1.0,
    spline_precision=0.001
)

# Generate toolpath for a circle
circle_toolpath = generator.generate_continuous_circle_path((0, 0), 10)

# Generate G-code
gcode = generator.generate_gcode_continuous([circle_toolpath])
```

## Configuration

### Toolpath Parameters
```python
TOOLPATH_CONFIG = {
    'DEFAULT_FEED_RATE': 100,
    'DEFAULT_Z_UP': 5,
    'DEFAULT_Z_DOWN': -1,
    'DEFAULT_STEP_SIZE': 0.05,  # Reduced for smoother motion
    'SPLINE_FLATTENING_PRECISION': 0.001,  # High precision
    'CIRCLE_STEPS_MIN': 64,
    'CIRCLE_STEPS_MAX': 512,
    'SPLINE_STEPS_MIN': 128,
    'SPLINE_STEPS_MAX': 1024,
    'MAX_ANGLE_STEP_RADIANS': 0.017453,  # 1.0 degrees
}
```

## Performance

### Smoothness Metrics
- **Maximum angle change**: < 2.0° for circles, < 5.0° for splines
- **Average angle change**: Typically < 1.0°
- **Point density**: Adaptive based on curvature
- **Motion continuity**: No stopping between segments

### Memory Usage
- **Efficient point generation** with adaptive density
- **Streaming G-code generation** for large files
- **Optimized angle calculations** with minimal overhead

## Compatibility

### DXF Entity Support
- ✅ **LINE** - Straight lines with smooth motion
- ✅ **LWPOLYLINE** - Lightweight polylines
- ✅ **POLYLINE** - Traditional polylines
- ✅ **SPLINE** - Smooth spline curves
- ✅ **ARC** - Circular arcs
- ✅ **CIRCLE** - Full circles

### File Formats
- **DXF R2010** - Primary format
- **DXF R2007** - Backward compatible
- **DXF R2004** - Backward compatible

## Troubleshooting

### Common Issues
1. **Sharp corners in curves** - Increase spline precision
2. **Too many points** - Increase step size
3. **Not enough points** - Decrease step size
4. **Angle discontinuities** - Check angle normalization

### Debug Information
The system provides detailed logging for:
- **Entity processing** - What entities are found
- **Toolpath generation** - Number of points generated
- **Smoothness analysis** - Angle change statistics
- **G-code generation** - Command count and structure

## Future Enhancements

### Planned Improvements
- **Bezier curve support** - Native Bezier curve processing
- **Variable feed rates** - Speed changes based on curvature
- **Tool compensation** - Automatic tool diameter compensation
- **Multi-pass support** - Multiple cutting passes
- **Optimization algorithms** - Path optimization for efficiency

### Performance Optimizations
- **Parallel processing** - Multi-threaded toolpath generation
- **GPU acceleration** - CUDA/OpenCL for complex calculations
- **Memory optimization** - Streaming processing for large files
- **Caching** - Cache frequently used calculations 