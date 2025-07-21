# Fabric CNC - Redesigned System

This is a complete redesign of the Fabric CNC motor control and toolpath planning system, following the stepperpi + TB6600 drivers approach as specified in the multi-axis plan.

## Overview

The redesigned system provides:

- **Modern Motor Control**: Individual stepper drivers with TB6600 compatibility
- **Multi-Axis Coordination**: Coordinated movement across X, Y, Z, and A axes
- **Advanced Motion Planning**: Smooth toolpath execution with optimization
- **G-Code Generation**: Modern G-code generation with configurable settings
- **YAML Configuration**: Clean, human-readable machine configuration
- **Simulation Mode**: Safe testing and development without hardware

## Architecture

### Core Components

1. **ConfigManager** (`config_manager.py`)
   - Loads machine configuration from YAML
   - Provides validation and access to machine settings
   - Handles system detection and simulation mode

2. **Motor Control** (`motor_control/`)
   - `StepperDriver`: Individual axis control with TB6600 compatibility
   - `MultiAxisController`: Coordinates all axes for smooth movement
   - Thread-safe operations with proper resource management

3. **Toolpath Planning** (`toolpath_planning/`)
   - `MotionPlanner`: Executes toolpaths with the motor control system
   - `ToolpathOptimizer`: Optimizes toolpaths for smooth execution
   - `GCodeGenerator`: Generates standard G-code files

4. **Main Application** (`main_app_redesigned.py`)
   - Demonstrates the complete system
   - Provides high-level interface for machine operations

## Machine Configuration

The system uses a YAML configuration file (`machine_config.yaml`) that defines:

```yaml
machine:
  name: fabric_cnc_v1
  units: mm
  axes:
    X: {step: 24, dir: 23, ena: 9, invert_dir: true, steps_per_mm: 80, hall: 16}
    Y1: {step: 22, dir: 27, ena: 17, invert_dir: true, steps_per_mm: 80, hall: 1}
    Y2: {step: 6, dir: 5, ena: 10, invert_dir: false, steps_per_mm: 80, hall: 20}
    Z: {step: 18, dir: 7, ena: 8, invert_dir: false, steps_per_mm: 400, hall: 25}
    A: {step: 26, dir: 19, ena: 13, invert_dir: true, steps_per_deg: 10, hall: 12}
  limits:
    X: {min: 0, max: 1727}
    Y: {min: 0, max: 1143}
    Z: {min: 0, max: 63.5}
    A: {min: -9999, max: 9999}
  motion:
    default_speed: 20
    max_speed: 100
    default_accel: 100
    lift_height: 25.4
```

## Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements_redesigned.txt
   ```

2. **Install pigpio** (on Raspberry Pi):
   ```bash
   sudo apt-get update
   sudo apt-get install pigpio python3-pigpio
   sudo systemctl enable pigpiod
   sudo systemctl start pigpiod
   ```

3. **Configure Machine**:
   - Edit `machine_config.yaml` to match your hardware setup
   - Verify GPIO pin assignments and motor parameters

## Usage

### Basic Usage

```python
from main_app_redesigned import FabricCNCApp

# Create application (simulation mode for testing)
app = FabricCNCApp(simulation_mode=True)

# Start the application
app.start()

# Home the machine
app.home_machine()

# Move to a position
app.move_to_position(x=100, y=100, z=10)

# Execute a toolpath
from toolpath_planning import ToolpathPoint

toolpath = [
    ToolpathPoint(x=100, y=100, z=5, a=0, feed_rate=100, tool_down=False),
    ToolpathPoint(x=100, y=100, z=-1, a=0, feed_rate=100, tool_down=True),
    ToolpathPoint(x=200, y=100, z=-1, a=0, feed_rate=100, tool_down=True),
    # ... more points
]

app.execute_toolpath(toolpath)

# Clean up
app.cleanup()
```

### Advanced Usage

```python
from motor_control import MultiAxisController, Position, MovementType
from toolpath_planning import MotionPlanner, GCodeGenerator

# Direct motor control
controller = MultiAxisController(simulation_mode=False)
controller.enable_all()

# Move with coordinated motion
target = Position(x=100, y=100, z=10, a=0)
controller.move_to_position(target, speed=50, movement_type=MovementType.LINEAR)

# Motion planning
planner = MotionPlanner(controller)
planner.execute_toolpath(toolpath)

# G-code generation
generator = GCodeGenerator()
gcode = generator.generate_from_toolpath(toolpath, output_file="output.gcode")
```

## Key Features

### 1. Individual Stepper Drivers
- Each axis has its own `StepperDriver` instance
- TB6600 driver compatibility with proper step/direction signals
- Hall sensor integration for homing
- Thread-safe operations

### 2. Multi-Axis Coordination
- `MultiAxisController` coordinates all axes
- Linear and rapid movement types
- Position validation against machine limits
- Synchronized homing operations

### 3. Motion Planning
- `MotionPlanner` executes toolpaths smoothly
- Progress and status callbacks
- Tool up/down management
- Automatic position validation

### 4. Toolpath Optimization
- `ToolpathOptimizer` adds intermediate points for smooth motion
- Configurable segment tolerance
- Maintains tool state through optimization

### 5. G-Code Generation
- Standard G-code output
- Configurable settings (feed rate, precision, etc.)
- Support for lines, circles, and rectangles
- Comments and line numbers

## GPIO Pin Mapping

| Axis | STEP | DIR | ENA | HALL | Steps/Unit | Invert DIR |
|------|------|-----|-----|------|------------|------------|
| X    | 24   | 23  | 9   | 16   | 80 steps/mm | True       |
| Y1   | 22   | 27  | 17  | 1    | 80 steps/mm | True       |
| Y2   | 6    | 5   | 10  | 20   | 80 steps/mm | False      |
| Z    | 18   | 7   | 8   | 25   | 400 steps/mm | False      |
| A    | 26   | 19  | 13  | 12   | 10 steps/deg | True       |

## Safety Features

1. **Position Validation**: All movements are validated against machine limits
2. **Emergency Stop**: Immediate stop functionality
3. **Resource Management**: Proper cleanup of GPIO resources
4. **Simulation Mode**: Safe testing without hardware
5. **Thread Safety**: All operations are thread-safe

## Development

### Running Tests
```bash
pytest tests/
```

### Code Formatting
```bash
black .
flake8 .
mypy .
```

### Adding New Features
1. Follow the existing architecture patterns
2. Add proper type hints and documentation
3. Include tests for new functionality
4. Update this README as needed

## Troubleshooting

### Common Issues

1. **pigpio Connection Error**:
   - Ensure pigpiod is running: `sudo systemctl status pigpiod`
   - Check permissions: `sudo usermod -a -G gpio $USER`

2. **GPIO Pin Conflicts**:
   - Verify pin assignments in `machine_config.yaml`
   - Check for conflicts with other software

3. **Motor Direction Issues**:
   - Adjust `invert_dir` settings in configuration
   - Verify TB6600 driver DIP switch settings

4. **Homing Problems**:
   - Check hall sensor connections
   - Verify sensor pull-up resistors
   - Test sensors individually

## Migration from Old System

The redesigned system is not backward compatible with the old motor control system. To migrate:

1. Update configuration to use YAML format
2. Replace direct motor control calls with new API
3. Update toolpath generation to use new classes
4. Test thoroughly in simulation mode first

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the code documentation
3. Create an issue with detailed information
4. Include logs and configuration details 