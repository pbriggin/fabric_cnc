# Fabric CNC Main App Launcher (Raspberry Pi)

This directory contains launcher scripts to easily start the Fabric CNC Main Application on Raspberry Pi systems.

## Prerequisites

### GPIO Setup
```bash
# Add user to gpio group
sudo usermod -a -G gpio $USER

# Add user to i2c group (if using I2C sensors)
sudo usermod -a -G i2c $USER

# Reboot to apply changes
sudo reboot
```

### Python Environment
```bash
# Install required packages
sudo apt update
sudo apt install -y python3-pip python3-venv python3-tk

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

## Files

- `launch_motor_test.sh` - Main launcher script for Raspberry Pi (runs main_app.py)
- `fabric-cnc-motor-test.desktop` - Desktop entry file for Raspberry Pi OS
- `LAUNCHER_README.md` - This file

## Quick Start

### Option 1: Direct Script Execution
```bash
./launch_motor_test.sh
```

### Option 2: Create Desktop Icon (Raspberry Pi OS)

1. **Copy the desktop file to applications:**
   ```bash
   cp fabric-cnc-motor-test.desktop ~/.local/share/applications/
   ```

2. **Make it executable:**
   ```bash
   chmod +x ~/.local/share/applications/fabric-cnc-motor-test.desktop
   ```

3. **Search for "Fabric CNC Main App" in the Raspberry Pi menu**

### Option 3: Add to Desktop
```bash
# Copy to desktop for easy access
cp fabric-cnc-motor-test.desktop ~/Desktop/
chmod +x ~/Desktop/fabric-cnc-motor-test.desktop
```

## What the Launcher Does

1. **Checks system:**
   - Verifies running on Raspberry Pi
   - Checks GPIO group membership
   - Validates virtual environment and files

2. **Activates environment:**
   - Activates the Python virtual environment
   - Installs package in development mode

3. **Launches the main app:**
   - Runs the main Fabric CNC application (main_app.py)
   - Provides GPIO access warnings if needed

## Hardware Requirements

- **Raspberry Pi 4** (recommended)
- **GPIO connections** for stepper motors
- **Hall effect sensors** for homing
- **TB6600 motor drivers**
- **5V power supply** for motors

## Troubleshooting

### "User not in gpio group"
```bash
sudo usermod -a -G gpio $USER
sudo reboot
```

### "Virtual environment not found"
```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

### "Permission denied"
```bash
chmod +x launch_motor_test.sh
```

### "GPIO access denied"
- Ensure user is in gpio group
- Check hardware connections
- Verify motor driver connections

### "Main app not found"
Make sure you're running the script from the fabric_cnc project root directory.

## GPIO Pin Configuration

The main app uses these GPIO pins:

- **X Motor**: STEP=5, DIR=6, EN=13, HALL=20
- **Y1 Motor**: STEP=10, DIR=9, EN=11, HALL=21
- **Y2 Motor**: STEP=17, DIR=27, EN=22, HALL=16
- **Z_LIFT**: STEP=12, DIR=11, EN=13, HALL=22
- **Z_ROTATE**: STEP=15, DIR=14, EN=16, HALL=23

## Safety Notes

- **Always use emergency stop** when testing motors
- **Check motor connections** before powering on
- **Start with low speeds** and gradually increase
- **Monitor motor temperature** during extended use
- **Keep hands clear** of moving parts during operation

## Customization

### Change Icon
Replace the `Icon=` line in the .desktop file:
- `Icon=applications-engineering` (default)
- `Icon=applications-development`
- `Icon=applications-science`
- Or use a custom .png file path

### Change Terminal Behavior
- Remove `Terminal=true` to run without terminal window
- Add `StartupNotify=true` for startup notification

### Add to System Menu
```bash
sudo cp fabric-cnc-motor-test.desktop /usr/share/applications/
```

## Performance Tips

- **Close other applications** when running the main app
- **Use wired network** instead of WiFi for better performance
- **Monitor CPU temperature** during extended operation
- **Consider using a heatsink** on the Raspberry Pi 