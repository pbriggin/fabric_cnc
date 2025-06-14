# Fabric CNC

A Python-based control system for a CNC fabric cutting machine using Raspberry Pi 4. This project provides tools for loading DXF files, planning toolpaths, and controlling stepper motors via TB6600 drivers.

## Features

- Control of 5 stepper motors (X, Y1, Y2, Z_LIFT, Z_ROTATE) using GPIO pins
- Tkinter-based GUI for manual motor control and testing
- Hardware abstraction layer for testing without physical hardware
- Configurable motor parameters (steps/mm, direction, etc.)
- Support for DXF file processing and toolpath planning

## Requirements

- Python 3.11 or higher
- Raspberry Pi 4 (for hardware control)
- TB6600 stepper motor drivers
- 5 stepper motors

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/fabric_cnc.git
cd fabric_cnc
```

2. Create and activate a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the package in development mode:
```bash
pip install -e ".[dev]"
```

## Usage

### Testing Motors

To test the motors using the GUI:

```bash
python -m fabric_cnc.motor_control.motor_test_ui
```

### Configuration

Motor settings can be configured in `src/fabric_cnc/config.py`:
- GPIO pin mappings
- Steps per millimeter
- Motor direction settings
- Work area dimensions
- Speed and acceleration parameters

### Development

1. Install development dependencies:
```bash
pip install -e ".[dev]"
```

2. Run tests:
```bash
pytest
```

3. Format code:
```bash
black src tests
isort src tests
```

## Project Structure

```
fabric_cnc/
├── src/
│   └── fabric_cnc/
│       ├── motor_control/
│       │   ├── __init__.py
│       │   ├── driver.py
│       │   └── motor_test_ui.py
│       ├── __init__.py
│       └── config.py
├── tests/
├── pyproject.toml
└── README.md
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
