#!/bin/bash

# Exit on error
set -e

echo "Installing Fabric CNC on Raspberry Pi 4..."

# Update system
echo "Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install required packages
echo "Installing required packages..."
sudo apt install -y python3-pip python3-venv python3-tk

# Create and activate virtual environment
echo "Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install package
echo "Installing Fabric CNC package..."
pip install -e ".[dev]"

# Configure GPIO permissions
echo "Configuring GPIO permissions..."
sudo usermod -a -G gpio $USER
sudo usermod -a -G i2c $USER

echo "Installation complete!"
echo "Please reboot your Raspberry Pi to apply GPIO permission changes:"
echo "sudo reboot" 