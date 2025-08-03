# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Installation and Setup
```bash
# Quick installation (Raspberry Pi)
chmod +x install.sh && ./install.sh

# Manual setup with virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -e .

# Launch application
./launch_motor_test.sh
# or
python main_app.py
```

### Development Tools
```bash
# Install development dependencies
pip install -e .[dev]

# Code formatting and linting (available but commented in requirements.txt)
# pip install black flake8 pytest
# black .
# flake8 .
# pytest
```

## Code Architecture

### Core Components

**main_app.py** - Main GUI application using CustomTkinter. Handles DXF import, toolpath visualization, motor control interface, and real-time position display. Automatically runs in simulation mode on non-Raspberry Pi systems.

**config.py** - Centralized configuration management containing:
- GPIO pin assignments for 5 stepper motors (X, Y1, Y2, Z_LIFT, A)
- Motor steps per inch and direction settings
- Work area dimensions (68" x 45")
- Motion parameters (speed, acceleration)
- Hall effect sensor configurations with debounce settings

**motor_control/** - Motor control subsystem:
- `motor_controller.py` - Main motor controller with GPIO control
- `smooth_motion_executor.py` - Smooth motion execution
- `driver.py` and `stepper_driver.py` - Low-level motor drivers

**dxf_processing/** - DXF file processing:
- `dxf_processor.py` - Extracts shapes from DXF files using ezdxf

**toolpath_planning/** - Toolpath generation:
- `toolpath_generator.py` - Converts DXF shapes to G-code with Z-axis management
- `gcode_visualizer.py` - Visualization of generated toolpaths

### Hardware Configuration

The system controls a 5-axis fabric cutting CNC machine:
- **X/Y axes**: Fabric positioning (68" x 45" work area)
- **Y1/Y2**: Dual Y-axis motors for gantry stability
- **Z_LIFT**: Cutting head vertical movement
- **A**: Cutting blade rotation for angle cuts

Each axis has hall effect sensors (NJK-5002C) for homing with EMI-resistant debouncing.

### Key Features

- **Simulation Mode**: Automatically enabled on non-Raspberry Pi systems
- **Homing System**: Hall effect sensor-based with verification
- **Toolpath Generation**: Automatic G-code generation from DXF files
- **Safety Features**: Emergency stop, bounds checking, sensor debouncing
- **Real-time Control**: Live position display and manual jogging

### Development Notes

- All motor configurations are in `config.py` with direction inversion flags
- GPIO pins are configurable per motor in the configuration
- System automatically detects Raspberry Pi hardware vs simulation mode
- Work area dimensions and motion parameters are centrally configured
- Generated G-code files are saved to `gcode/` directory