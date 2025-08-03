# Fabric CNC - Raspberry Pi Control System

A complete CNC fabric cutting machine control system designed specifically for Raspberry Pi 4. This system provides motor control, DXF file processing, toolpath generation, and a comprehensive GUI for machine operation.

## Features

- **Motor Control**: Full control of X, Y, Z, and rotation axes with stepper motors
- **Homing System**: EMI-resistant hall effect sensor homing with verification
- **DXF Processing**: Import and process DXF files for cutting patterns
- **Toolpath Generation**: Automatic toolpath generation from DXF entities
- **GUI Interface**: Tkinter-based interface with real-time position display
- **Raspberry Pi Optimized**: Designed specifically for Raspberry Pi GPIO control
- **Simulation Mode**: Safe development and testing on non-Raspberry Pi systems

## Hardware Requirements

- **Raspberry Pi 4** (recommended) or Raspberry Pi 3B+
- **Stepper Motors**: 5 stepper motors (X, Y1, Y2, Z_LIFT, A)
- **Motor Drivers**: TB6600 or similar stepper motor drivers
- **Hall Effect Sensors**: NJK-5002C for homing (5 sensors)
- **Power Supply**: 5V for logic, 12-24V for motors
- **GPIO Connections**: See pinout below

## GPIO Pin Configuration

| Component | Pin | Function |
|-----------|-----|----------|
| X Motor | GPIO 5 | STEP |
| X Motor | GPIO 6 | DIR |
| X Motor | GPIO 13 | ENABLE |
| X Motor | GPIO 20 | HALL Sensor |
| Y1 Motor | GPIO 10 | STEP |
| Y1 Motor | GPIO 9 | DIR |
| Y1 Motor | GPIO 11 | ENABLE |
| Y1 Motor | GPIO 21 | HALL Sensor |
| Y2 Motor | GPIO 17 | STEP |
| Y2 Motor | GPIO 27 | DIR |
| Y2 Motor | GPIO 22 | ENABLE |
| Y2 Motor | GPIO 16 | HALL Sensor |
| Z_LIFT | GPIO 12 | STEP |
| Z_LIFT | GPIO 11 | DIR |
| Z_LIFT | GPIO 13 | ENABLE |
| Z_LIFT | GPIO 22 | HALL Sensor |
| A | GPIO 15 | STEP |
| A | GPIO 14 | DIR |
| A | GPIO 16 | ENABLE |
| A | GPIO 23 | HALL Sensor |

## Quick Installation

### 1. Clone the Repository
```bash
git clone https://github.com/pbriggin/fabric_cnc.git
cd fabric_cnc
```

### 2. Run the Installation Script
```bash
chmod +x install.sh
./install.sh
```

### 3. Reboot
```bash
sudo reboot
```

### 4. Launch the Application
After reboot, you can launch Fabric CNC in several ways:
- **Desktop Icon**: Double-click the "Fabric CNC Main App" icon
- **Command Line**: `./launch_motor_test.sh`
- **System Service**: `sudo systemctl start fabric-cnc`

## Manual Installation

If you prefer manual installation:

### 1. Install Dependencies
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-tk git build-essential python3-dev
sudo apt install -y python3-gpiozero i2c-tools python3-smbus
```

**Note**: `python3-tk` is required for the GUI interface and must be installed via apt, not pip.

### 2. Setup GPIO Permissions
```bash
sudo usermod -a -G gpio,i2c,spi $USER
```

### 3. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
```

### 4. Install Fabric CNC
```bash
pip install -e .
```

### 5. Enable Interfaces
```bash
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_spi 0
# GPIO is enabled by default on Raspberry Pi
```

## Usage

### Starting the Application
```bash
# Activate virtual environment
source venv/bin/activate

# Run the main application
python main_app.py
```

### Basic Operations

1. **Homing**: Click "Home X" and "Home Y" to establish reference positions
2. **Jogging**: Use arrow keys or on-screen buttons to move motors
3. **DXF Import**: Click "Import DXF File" to load cutting patterns
4. **Toolpath Generation**: Click "Generate Toolpath" to create cutting paths
5. **Emergency Stop**: Use the red E-STOP button for immediate motor shutdown

### Keyboard Controls
- **Arrow Keys**: Jog X and Y axes
- **Speed Control**: Adjust jog speed using the spinbox
- **Homing**: Use individual axis home buttons or "Home All"

## Development

### Project Structure
```
fabric_cnc/
├── main_app.py          # Main GUI application
├── config.py            # Configuration settings
├── motor_control/
│   ├── driver.py        # Motor driver implementation
│   └── motor_controller.py  # Main motor controller
├── install.sh               # Raspberry Pi installation script
├── launch_motor_test.sh     # Application launcher
├── fabric-cnc-motor-test.desktop  # Desktop entry
├── requirements.txt         # Dependencies
├── pyproject.toml          # Package configuration
├── README.md               # Complete documentation
└── LAUNCHER_README.md      # Launcher documentation
```

### Development Mode
```bash
# Install in development mode
pip install -e .

# Run with debugging
python -m main_app
```

### Simulation Mode
The application automatically runs in simulation mode on non-Raspberry Pi systems, allowing safe development and testing without hardware.

## Configuration

### Motor Settings
Edit `config.py` to adjust:
- Motor pin assignments
- Steps per revolution
- Movement speeds
- Homing parameters

### Machine Parameters
- Maximum travel distances
- Acceleration/deceleration
- Safety limits
- Hall sensor configurations

## Troubleshooting

### Common Issues

1. **GPIO Permission Errors**
   ```bash
   sudo usermod -a -G gpio $USER
   sudo reboot
   ```

2. **Motor Not Moving**
   - Check power supply connections
   - Verify motor driver connections
   - Check enable pin states

3. **Homing Failures**
   - Verify hall sensor connections
   - Check sensor pull-up resistors
   - Test sensors individually

4. **GUI Not Starting**
   ```bash
   sudo apt install -y python3-tk
   ```

### Debug Mode
```bash
# Run with verbose logging
python -m main_app --debug
```

## Safety Notes

- **Always use emergency stop** when testing motors
- **Check motor connections** before powering on
- **Start with low speeds** and gradually increase
- **Monitor motor temperature** during extended use
- **Keep hands clear** of moving parts during operation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly on Raspberry Pi
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Check the troubleshooting section above
- Review GPIO connections and wiring
- Ensure proper power supply setup
- Verify all dependencies are installed

## Acknowledgments

- Raspberry Pi Foundation for GPIO libraries
- TB6600 motor driver community
- DXF processing community
