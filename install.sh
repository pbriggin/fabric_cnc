#!/bin/bash

# Fabric CNC Raspberry Pi Installation Script
# This script installs the Fabric CNC system on a Raspberry Pi

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running on Raspberry Pi
check_raspberry_pi() {
    if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
        print_warning "This script is designed for Raspberry Pi systems."
        print_warning "Some features may not work on other systems."
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        print_success "Raspberry Pi detected"
    fi
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "This script should not be run as root"
        print_error "Please run as a regular user with sudo privileges"
        exit 1
    fi
}

# Update system packages
update_system() {
    print_status "Updating system packages..."
    sudo apt update
    sudo apt upgrade -y
    print_success "System packages updated"
}

# Install required packages
install_packages() {
    print_status "Installing required packages..."
    
    # Core packages
    sudo apt install -y \
        python3 \
        python3-pip \
        python3-venv \
        python3-tk \
        git \
        build-essential \
        python3-dev \
        libffi-dev \
        libssl-dev
    
    # GPIO and hardware support
    sudo apt install -y \
        python3-gpiozero \
        i2c-tools \
        python3-smbus
    
    print_success "Required packages installed"
    print_status "Note: python3-tk is required for the GUI interface"
}

# Setup GPIO permissions
setup_gpio() {
    print_status "Setting up GPIO permissions..."
    
    # Add user to required groups
    sudo usermod -a -G gpio $USER
    sudo usermod -a -G i2c $USER
    sudo usermod -a -G spi $USER
    
    # Create udev rules for GPIO access
    sudo tee /etc/udev/rules.d/99-gpio.rules > /dev/null <<EOF
SUBSYSTEM=="bcm2835-gpiomem", GROUP="gpio", MODE="0660"
SUBSYSTEM=="gpio", GROUP="gpio", MODE="0660"
EOF
    
    print_success "GPIO permissions configured"
}

# Create virtual environment
setup_venv() {
    print_status "Setting up Python virtual environment..."
    
    if [ -d "venv" ]; then
        print_warning "Virtual environment already exists. Removing..."
        rm -rf venv
    fi
    
    python3 -m venv venv
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip setuptools wheel
    
    print_success "Virtual environment created"
}

# Install Fabric CNC
install_fabric_cnc() {
    print_status "Installing Fabric CNC..."
    
    # Install in development mode
    pip install -e .
    
    print_success "Fabric CNC installed"
}

# Setup desktop launcher
setup_launcher() {
    print_status "Setting up desktop launcher..."
    
    # Make launcher script executable
    chmod +x launch_motor_test.sh
    
    # Copy desktop file to applications
    cp fabric-cnc-motor-test.desktop ~/.local/share/applications/
    chmod +x ~/.local/share/applications/fabric-cnc-motor-test.desktop
    
    # Also copy to desktop for easy access
    cp fabric-cnc-motor-test.desktop ~/Desktop/
    chmod +x ~/Desktop/fabric-cnc-motor-test.desktop
    
    print_success "Desktop launcher configured"
}

# Enable required interfaces
enable_interfaces() {
    print_status "Enabling required interfaces..."
    
    # Enable I2C
    sudo raspi-config nonint do_i2c 0
    
    # Enable SPI (if needed)
    sudo raspi-config nonint do_spi 0
    
    # Enable GPIO
    sudo raspi-config nonint do_gpio 0
    
    print_success "Interfaces enabled"
}

# Create systemd service (optional)
create_service() {
    print_status "Creating systemd service..."
    
    sudo tee /etc/systemd/system/fabric-cnc.service > /dev/null <<EOF
[Unit]
Description=Fabric CNC Control System
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/venv/bin
ExecStart=$(pwd)/venv/bin/python src/fabric_cnc/main_app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    
    # Enable service (but don't start yet)
    sudo systemctl enable fabric-cnc.service
    
    print_success "Systemd service created (disabled by default)"
}

# Main installation function
main() {
    echo "=========================================="
    echo "    Fabric CNC Raspberry Pi Installer"
    echo "=========================================="
    echo
    
    check_root
    check_raspberry_pi
    
    print_status "Starting installation..."
    
    update_system
    install_packages
    setup_gpio
    setup_venv
    install_fabric_cnc
    setup_launcher
    enable_interfaces
    create_service
    
    echo
    echo "=========================================="
    print_success "Installation completed successfully!"
    echo "=========================================="
    echo
    print_status "Next steps:"
    echo "1. Reboot your Raspberry Pi:"
    echo "   sudo reboot"
    echo
    echo "2. After reboot, launch Fabric CNC:"
    echo "   - Double-click the desktop icon, or"
    echo "   - Run: ./launch_motor_test.sh"
    echo
    echo "3. To start as a service (optional):"
    echo "   sudo systemctl start fabric-cnc"
    echo
    print_warning "Please reboot to apply GPIO permission changes!"
    echo

    # Check if the main app file exists
    if [ ! -f "main_app.py" ]; then
        echo "Error: Main app not found!"
        echo "Expected: main_app.py"
        read -p "Press Enter to exit..."
        exit 1
    fi

    # Run the main app
    python3 main_app.py
}

# Run main function
main "$@" 