#!/bin/bash

# Fabric CNC Motor Test Launcher for Raspberry Pi
# This script activates the virtual environment and launches the motor test UI

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Fabric CNC Motor Test Launcher (Raspberry Pi) ==="
echo "Script directory: $SCRIPT_DIR"
echo ""

# Check if we're running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "Warning: This appears to be running on a non-Raspberry Pi system."
    echo "GPIO functionality may not work correctly."
    echo ""
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found!"
    echo "Please run: python3 -m venv venv"
    echo "Then: source venv/bin/activate && pip install -e ."
    read -p "Press Enter to exit..."
    exit 1
fi

# Check if the motor test UI file exists
if [ ! -f "src/fabric_cnc/motor_control/motor_test_ui.py" ]; then
    echo "Error: Motor test UI not found!"
    echo "Expected: src/fabric_cnc/motor_control/motor_test_ui.py"
    read -p "Press Enter to exit..."
    exit 1
fi

# Check if user is in gpio group (for GPIO access)
if ! groups $USER | grep -q gpio; then
    echo "Warning: User not in gpio group. GPIO access may be limited."
    echo "To fix: sudo usermod -a -G gpio $USER"
    echo ""
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing package in development mode..."
pip install -e . > /dev/null 2>&1

echo "Launching Motor Test UI..."
echo "Note: This requires GPIO access for motor control"
echo ""

# Run the motor test UI
python3 src/fabric_cnc/motor_control/motor_test_ui.py

# Keep terminal open if there's an error
if [ $? -ne 0 ]; then
    echo ""
    echo "Motor Test UI exited with an error."
    echo "Check GPIO permissions and hardware connections."
    read -p "Press Enter to exit..."
fi 