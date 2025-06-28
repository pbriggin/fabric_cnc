#!/bin/bash

# Fabric CNC Motor Test Launcher
# This script activates the virtual environment and launches the motor test UI

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Fabric CNC Motor Test Launcher ==="
echo "Script directory: $SCRIPT_DIR"
echo ""

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

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing package in development mode..."
pip install -e . > /dev/null 2>&1

echo "Launching Motor Test UI..."
echo ""

# Run the motor test UI
python src/fabric_cnc/motor_control/motor_test_ui.py

# Keep terminal open if there's an error
if [ $? -ne 0 ]; then
    echo ""
    echo "Motor Test UI exited with an error."
    read -p "Press Enter to exit..."
fi 