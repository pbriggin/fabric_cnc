#!/bin/bash

# Fabric CNC Launcher Script
# This script launches the Fabric CNC application

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activate virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Change to the script directory
cd "$SCRIPT_DIR"

# Run the main application
python main_app.py 