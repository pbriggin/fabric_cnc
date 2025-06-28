# Fabric CNC Motor Test Launcher

This directory contains launcher scripts to easily start the Fabric CNC Motor Test UI.

## Files

- `launch_motor_test.sh` - Main launcher script
- `fabric-cnc-motor-test.desktop` - Desktop entry file for Linux
- `LAUNCHER_README.md` - This file

## Quick Start

### Option 1: Direct Script Execution
```bash
./launch_motor_test.sh
```

### Option 2: Create Desktop Icon (Linux)

1. **Copy the desktop file to applications:**
   ```bash
   cp fabric-cnc-motor-test.desktop ~/.local/share/applications/
   ```

2. **Make it executable:**
   ```bash
   chmod +x ~/.local/share/applications/fabric-cnc-motor-test.desktop
   ```

3. **Search for "Fabric CNC Motor Test" in your applications menu**

### Option 3: Create Desktop Icon (macOS)

1. **Create an AppleScript:**
   - Open "Script Editor" (Applications > Utilities)
   - Create new script with:
   ```applescript
   tell application "Terminal"
       do script "cd /Users/peterbriggs/Code/fabric_cnc && ./launch_motor_test.sh"
   end tell
   ```
   - Save as "Fabric CNC Motor Test.scpt"

2. **Create Application:**
   - In Script Editor, go to File > Export
   - Choose "Application" as file format
   - Save to Desktop

## What the Launcher Does

1. **Checks prerequisites:**
   - Virtual environment exists
   - Motor test UI file exists

2. **Activates environment:**
   - Activates the Python virtual environment
   - Installs package in development mode

3. **Launches the UI:**
   - Runs the motor test interface
   - Keeps terminal open if errors occur

## Troubleshooting

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

### "Motor test UI not found"
Make sure you're running the script from the fabric_cnc project root directory.

## Customization

### Change Icon (Linux)
Replace the `Icon=` line in the .desktop file with your preferred icon:
- `Icon=applications-engineering` (default)
- `Icon=applications-development`
- `Icon=applications-science`
- Or use a custom .png file path

### Change Terminal Behavior
- Remove `Terminal=true` to run without terminal window
- Add `StartupNotify=true` for startup notification

### Add to System Menu (Linux)
```bash
sudo cp fabric-cnc-motor-test.desktop /usr/share/applications/
``` 