# motor_control/grbl_motor_controller.py
import serial
import threading
import time
import queue
import re
import subprocess
import os
import psutil
import logging

logger = logging.getLogger(__name__)

class GrblMotorController:
    def __init__(self, port='/dev/ttyACM0', baudrate=115200, debug_mode=False):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.debug_mode = debug_mode
        
        # Try to open the serial connection with cleanup
        self._open_serial_with_cleanup()
        self.command_queue = queue.Queue()
        self.running = True
        self.position = [0.0, 0.0, 0.0, 0.0]  # X, Y, Z, A
        self.status_lock = threading.Lock()

        self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.writer_thread = threading.Thread(target=self._write_loop, daemon=True)
        self.poll_thread = threading.Thread(target=self._poll_loop, daemon=True)

        self.reader_thread.start()
        self.writer_thread.start()
        self.poll_thread.start()
        
        # Initialize GRBL settings and reset work coordinates
        time.sleep(2)  # Wait for GRBL to initialize
        self._configure_grbl_settings()
        self.send("G20")  # Set GRBL to inches mode
        self.send("G90")  # Set absolute positioning
        self.send("G10 P1 L20 X0 Y0 Z0 A0")  # Reset work coordinates to 0,0,0,0
        self.send("G54")  # Select work coordinate system 1
        # Reset position tracking
        with self.status_lock:
            self.position = [0.0, 0.0, 0.0, 0.0]

    def _open_serial_with_cleanup(self):
        """Open serial connection with device cleanup and retry logic."""
        max_retries = 3
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
                logger.info(f"Successfully opened {self.port}")
                return
            except serial.SerialException as e:
                if "Device or resource busy" in str(e) or "Permission denied" in str(e):
                    logger.warning(f"Attempt {attempt + 1}: {self.port} is busy, attempting cleanup...")
                    
                    if attempt < max_retries - 1:  # Don't cleanup on last attempt
                        self._cleanup_device_processes()
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        logger.error(f"Failed to open {self.port} after {max_retries} attempts")
                        raise
                else:
                    logger.error(f"Serial connection error: {e}")
                    raise
    
    def _cleanup_device_processes(self):
        """Kill processes that might be blocking the ACM0 device."""
        try:
            # Find processes using the device
            blocking_pids = []
            
            # Method 1: Use lsof to find processes using the device
            try:
                result = subprocess.run(['lsof', self.port], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')[1:]  # Skip header
                    for line in lines:
                        if line.strip():
                            pid = int(line.split()[1])
                            blocking_pids.append(pid)
                            logger.info(f"Found process {pid} using {self.port}")
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError):
                pass
            
            # Method 2: Find Python processes that might be using serial ports
            try:
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        if proc.info['name'] and 'python' in proc.info['name'].lower():
                            cmdline = ' '.join(proc.info['cmdline'] or [])
                            # Look for serial/GRBL related processes
                            if any(keyword in cmdline.lower() for keyword in 
                                   ['grbl', 'serial', 'ttyacm', 'arduino', 'cnc']):
                                if proc.info['pid'] != os.getpid():  # Don't kill ourselves
                                    blocking_pids.append(proc.info['pid'])
                                    logger.info(f"Found potential blocking process {proc.info['pid']}: {cmdline}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except Exception as e:
                logger.warning(f"Error scanning processes: {e}")
            
            # Kill the blocking processes
            for pid in set(blocking_pids):  # Remove duplicates
                try:
                    process = psutil.Process(pid)
                    logger.info(f"Terminating process {pid} ({process.name()})")
                    process.terminate()
                    
                    # Wait up to 3 seconds for graceful termination
                    try:
                        process.wait(timeout=3)
                    except psutil.TimeoutExpired:
                        logger.warning(f"Force killing process {pid}")
                        process.kill()
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    logger.warning(f"Could not terminate process {pid}: {e}")
            
            # Additional cleanup: reset the USB device if possible
            self._reset_usb_device()
            
        except Exception as e:
            logger.error(f"Error during device cleanup: {e}")
    
    def _reset_usb_device(self):
        """Attempt to reset the USB device."""
        try:
            # Find USB device path for ACM0
            usb_path = None
            try:
                result = subprocess.run(['readlink', '-f', '/sys/class/tty/ttyACM0/device'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    usb_path = result.stdout.strip()
                    
                    # Navigate to USB device reset
                    reset_path = None
                    path_parts = usb_path.split('/')
                    for i, part in enumerate(path_parts):
                        if part.startswith('usb'):
                            reset_path = '/'.join(path_parts[:i+2]) + '/authorized'
                            break
                    
                    if reset_path and os.path.exists(reset_path):
                        logger.info(f"Attempting USB device reset via {reset_path}")
                        # Deauthorize and reauthorize the USB device
                        subprocess.run(['sudo', 'sh', '-c', f'echo 0 > {reset_path}'], timeout=2)
                        time.sleep(0.5)
                        subprocess.run(['sudo', 'sh', '-c', f'echo 1 > {reset_path}'], timeout=2)
                        time.sleep(1.0)
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                pass
                
        except Exception as e:
            logger.warning(f"USB reset failed: {e}")

    def _configure_grbl_settings(self):
        """Configure essential GRBL settings for proper operation.""" 
        try:
            # Enable hard limits ($21=1) - must be set before homing
            self.send("$21=1")
            if self.debug_mode:
                logger.info("Enabled GRBL hard limits ($21=1)")
            
            # Enable homing cycle ($22=1)
            self.send("$22=1")
            if self.debug_mode:
                logger.info("Enabled GRBL homing cycle ($22=1)")
            
            # Set homing direction mask - customize based on your limit switch setup
            # $23=0 means all axes home in negative direction (typical)
            self.send("$23=0")
            
            # Set homing seek rate - GRBL uses mm/min internally, convert from inches
            # 20 inches/min = ~508 mm/min for initial search
            self.send("$24=508")
            
            # Set homing feed rate - slower for precision
            # 2 inches/min = ~51 mm/min for final approach
            self.send("$25=51")
            
            # Set homing debounce delay ($26=250 ms)
            self.send("$26=250")
            
            # Set homing pull-off distance - GRBL uses mm internally
            # 0.04 inches = ~1.0 mm back off from limit after homing
            self.send("$27=1.0")
            
            # Set travel limits based on your fabric CNC machine dimensions
            # Your machine: 68" x 45" work area, convert to mm for GRBL
            # 68 inches = ~1727 mm, 45 inches = ~1143 mm
            self.send("$130=1727.0")  # X max travel (68 inches in mm)
            self.send("$131=1143.0")  # Y max travel (45 inches in mm)  
            self.send("$132=127.0")   # Z max travel (~5 inches in mm) - adjust for your Z travel
            
            if self.debug_mode:
                logger.info("Configured GRBL homing settings")
            
            # Wait longer for settings to be processed
            time.sleep(1.0)
            
        except Exception as e:
            logger.error(f"Failed to configure GRBL settings: {e}")

    def _interpret_grbl_error(self, error_str):
        """Interpret GRBL error codes for better debugging."""
        error_codes = {
            "error:1": "G-code words consist of a letter and a value. Letter was not found.",
            "error:2": "Numeric value format is not valid or missing an expected value.",
            "error:3": "Grbl '$' system command was not recognized or supported.",
            "error:4": "Negative value received for an expected positive value.",
            "error:5": "Homing cycle not completed due to limit switch not triggered within search distance.",
            "error:6": "Minimum step pulse time must be greater than 3usec",
            "error:7": "EEPROM read/write failed.",
            "error:8": "Grbl '$' command cannot be used unless Grbl is IDLE.",
            "error:9": "G-code locked out during alarm or jog state",
            "error:10": "Soft limits cannot be enabled without homing also enabled.",
            "error:11": "Max characters per line exceeded. Line was not processed and executed.",
            "error:12": "Grbl '$' setting value exceeds the maximum step rate supported.",
            "error:13": "Safety door detected as opened and door state initiated.",
            "error:14": "Build info or startup line exceeded EEPROM line length limit.",
            "error:15": "Jog target exceeds machine travel. Command ignored.",
            "error:16": "Jog command with no '=' or contains prohibited g-code.",
            "error:17": "Laser mode requires PWM output.",
            "error:20": "Unsupported or invalid g-code command found in block.",
            "error:21": "More than one g-code command from same modal group found in block.",
            "error:22": "Feed rate has not yet been set or is undefined.",
            "error:23": "G-code command in block requires an integer value.",
            "error:24": "Two G-code commands that both require the use of the XYZ axis words were detected in the block.",
            "error:25": "A G-code word was repeated in the block.",
            "error:26": "A G-code command implicitly or explicitly requires XYZ axis words in the block, but none were detected.",
            "error:27": "N line number value is not within the valid range of 1 - 9,999,999.",
            "error:28": "A G-code command was sent, but is missing some required P or L value words in the line.",
            "error:29": "Grbl supports six work coordinate systems G54-G59. G59.1, G59.2, and G59.3 are not supported.",
            "error:30": "The G53 G-code command requires either a G0 seek or G1 feed motion mode to be active. A different motion was active.",
            "error:31": "There are unused axis words in the block and G80 motion mode cancel is active.",
            "error:32": "A G2 or G3 arc was commanded but there are no XYZ axis words in the selected plane to trace the arc.",
            "error:33": "The motion command has an invalid target. G2, G3, and G38.2 generates this error, if the arc is impossible to generate or if the probe target is the current position.",
            "error:34": "A G2 or G3 arc, traced with the radius definition, had a mathematical error when computing the arc geometry. Try either breaking up the arc into semi-circles or quadrants, or redefine them with the arc offset definition.",
            "error:35": "A G2 or G3 arc, traced with the offset definition, is missing the IJK offset word in the selected plane to trace the arc.",
            "error:36": "There are unused, leftover G-code words that aren't used by any command in the block.",
            "error:37": "The G43.1 dynamic tool length offset command cannot apply an offset to an axis other than its configured axis. The Grbl default axis is the Z-axis."
        }
        
        return error_codes.get(error_str, "Unknown GRBL error")

    def _read_loop(self):
        buffer = b""
        while self.running:
            if self.serial.in_waiting:
                buffer += self.serial.read(self.serial.in_waiting)
                lines = buffer.split(b'\n')
                buffer = lines[-1]  # keep incomplete line
                for line in lines[:-1]:
                    decoded = line.decode('utf-8').strip()
                    if decoded.startswith("<"):
                        self._parse_status(decoded)
                    else:
                        if self.debug_mode:
                            print(f"[GRBL RESP] {decoded}")
                        elif not decoded.strip() == "ok":  # Only log non-"ok" responses in non-debug mode
                            if decoded.startswith("error:"):
                                error_msg = self._interpret_grbl_error(decoded)
                                logger.error(f"GRBL {decoded}: {error_msg}")
                            else:
                                logger.info(f"GRBL: {decoded}")
            time.sleep(0.01)

    def _write_loop(self):
        while self.running:
            try:
                cmd = self.command_queue.get(timeout=0.1)
                self.serial.write((cmd + "\n").encode('utf-8'))
                self.command_queue.task_done()
            except queue.Empty:
                continue

    def _poll_loop(self):
        while self.running:
            self.send_immediate("?")
            time.sleep(0.2)

    def _parse_status(self, line):
        match = re.search(r"MPos:([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)", line)
        if match:
            with self.status_lock:
                self.position = [float(match.group(i)) for i in range(1, 5)]
                if self.debug_mode:
                    print(f"[GRBL DEBUG] Raw position from GRBL: {self.position}")

    def send(self, gcode_line):
        self.command_queue.put(gcode_line)

    def send_immediate(self, gcode_line):
        self.serial.write((gcode_line + "\n").encode('utf-8'))

    def jog(self, axis, delta, feedrate=100):
        if axis not in "XYZA":
            raise ValueError("Invalid axis")
        # Use G91 for relative movement, let GRBL use current unit mode
        command = f"$J=G91 {axis}{delta:.3f} F{feedrate}"
        if self.debug_mode:
            print(f"[GRBL DEBUG] Sending jog command: {command}")
        self.send(command)

    def home_all(self):
        """Home all axes using $H command."""
        self.send("$H")
        # After homing, reset work coordinates to 0,0,0,0
        time.sleep(2)  # Wait for homing to complete
        self.send("G10 P1 L20 X0 Y0 Z0 A0")  # Set work coordinate system origin
        self.send("G54")  # Select work coordinate system 1
        # Reset position tracking
        with self.status_lock:
            self.position = [0.0, 0.0, 0.0, 0.0]
    
    def home_axis(self, axis):
        """Home a single axis using $H<axis> command (grblHAL)."""
        if axis not in "XYZA":
            raise ValueError(f"Invalid axis: {axis}")
        
        # Pre-homing diagnostics
        logger.info(f"Preparing to home {axis} axis...")
        self.get_grbl_info()
        self.check_limit_switches()
        
        command = f"$H{axis}"
        logger.info(f"Sending homing command: {command}")
        logger.warning(f"Ensure {axis}-axis limit switch is connected and working before homing!")
        
        if self.debug_mode:
            logger.info(f"Note: Ensure limit switch for {axis} axis is properly connected and configured")
        
        self.send(command)
        # Wait for homing to complete (individual axis is faster)
        time.sleep(5)  # Longer wait to ensure homing completes or fails properly
        
        # Reset work coordinate for this axis only
        if axis == 'X':
            self.send("G10 P1 L20 X0")
        elif axis == 'Y':
            self.send("G10 P1 L20 Y0")
        elif axis == 'Z':
            self.send("G10 P1 L20 Z0")
        elif axis == 'A':
            self.send("G10 P1 L20 A0")
        
        self.send("G54")  # Select work coordinate system 1
        
        # Update position tracking for this axis
        with self.status_lock:
            axis_index = {'X': 0, 'Y': 1, 'Z': 2, 'A': 3}[axis]
            self.position[axis_index] = 0.0
            
        logger.info(f"Homing sequence completed for {axis} axis")

    def check_limit_switches(self):
        """Check the current status of limit switches."""
        try:
            logger.info("Checking limit switch status...")
            # Send real-time status request to get current machine state
            self.send_immediate("?")
            time.sleep(0.2)
            
            # Try different pin state commands for grblHAL
            try:
                self.send("$Pins")  # grblHAL pin state command
                time.sleep(0.3)
            except:
                try:
                    self.send("$#")  # Alternative status command
                    time.sleep(0.3)
                except:
                    logger.warning("Could not query pin states - command not supported")
            
        except Exception as e:
            logger.error(f"Failed to check limit switches: {e}")
    
    def test_limit_switch_connection(self):
        """Test if limit switches are properly connected and readable."""
        try:
            logger.info("=== LIMIT SWITCH CONNECTION TEST ===")
            logger.info("Please manually trigger the X-axis limit switch and observe the output...")
            
            # Get initial status
            logger.info("Getting initial machine status...")
            self.send_immediate("?")
            time.sleep(0.5)
            
            # Instructions for manual testing
            logger.info("INSTRUCTIONS:")
            logger.info("1. Physically press/trigger the X-axis limit switch")
            logger.info("2. Watch the status messages for any change")
            logger.info("3. Release the limit switch")
            logger.info("4. Check if the status changes back")
            
            # Monitor for changes over a few seconds
            for i in range(10):
                self.send_immediate("?")
                time.sleep(0.5)
                
            logger.info("=== LIMIT SWITCH TEST COMPLETE ===")
            
        except Exception as e:
            logger.error(f"Limit switch test failed: {e}")
    
    def get_grbl_settings(self):
        """Query and display current GRBL settings."""
        try:
            logger.info("Querying GRBL settings...")
            self.send("$$")  # Request all settings
            time.sleep(1)  # Wait for response
            
        except Exception as e:
            logger.error(f"Failed to get GRBL settings: {e}")
    
    def get_grbl_info(self):
        """Get GRBL version and build info."""
        try:
            logger.info("Getting GRBL version info...")
            self.send("$I")  # Request build info
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Failed to get GRBL info: {e}")
    
    def check_and_clear_alarms(self):
        """Check for active alarms and clear them if found."""
        try:
            logger.info("Checking for active alarms...")
            
            # Send status request
            self.send_immediate("?")
            time.sleep(0.5)
            
            # Read any pending responses to check for alarm state
            alarm_detected = False
            responses = []
            
            # Collect responses for a short time
            start_time = time.time()
            while time.time() - start_time < 1.0:
                if self.serial.in_waiting:
                    try:
                        response = self.serial.readline().decode('utf-8').strip()
                        if response:
                            responses.append(response)
                            if 'Alarm' in response:
                                alarm_detected = True
                                logger.warning(f"Alarm detected: {response}")
                    except:
                        pass
                time.sleep(0.1)
            
            if alarm_detected:
                logger.info("Clearing alarm state...")
                # Soft reset first
                self.send_immediate("\x18")  # Ctrl-X soft reset
                time.sleep(1.0)
                
                # Clear alarm
                self.send("$X")
                time.sleep(0.5)
                
                # Verify alarm is cleared
                self.send_immediate("?")
                time.sleep(0.5)
                
                # Check final status
                final_responses = []
                start_time = time.time()
                while time.time() - start_time < 1.0:
                    if self.serial.in_waiting:
                        try:
                            response = self.serial.readline().decode('utf-8').strip()
                            if response:
                                final_responses.append(response)
                        except:
                            pass
                    time.sleep(0.1)
                
                still_alarmed = any('Alarm' in resp for resp in final_responses)
                if still_alarmed:
                    logger.warning("Alarm state persists after clearing attempt")
                    return False
                else:
                    logger.info("Alarm state successfully cleared")
                    return True
            else:
                logger.info("No active alarms detected")
                return True
                
        except Exception as e:
            logger.error(f"Failed to check/clear alarms: {e}")
            return False
    
    def reset_controller(self):
        """Perform a soft reset of the GRBL controller."""
        try:
            logger.info("Performing GRBL soft reset...")
            self.send_immediate("\x18")  # Ctrl-X soft reset
            time.sleep(2.0)  # Wait for reset to complete
            
            # Reconfigure settings after reset
            self._configure_grbl_settings()
            self.send("G20")  # Set inches mode
            self.send("G90")  # Set absolute positioning
            self.send("G10 P1 L20 X0 Y0 Z0 A0")  # Reset work coordinates
            self.send("G54")  # Select work coordinate system 1
            
            logger.info("GRBL soft reset completed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset controller: {e}")
            return False

    def run_gcode_file(self, filepath):
        with open(filepath, 'r') as f:
            for line in f:
                clean = line.strip()
                if clean and not clean.startswith(";"):
                    ack_event = threading.Event()

                    def wait_for_ack():
                        while True:
                            resp = self.serial.readline().decode('utf-8').strip()
                            if resp == "ok":
                                ack_event.set()
                                break
                            elif resp.startswith("error:"):
                                logger.error(f"GRBL error: {resp}")
                                if self.debug_mode:
                                    print(f"[GRBL ERROR] {resp}")
                                ack_event.set()
                                break

                    ack_event.clear()
                    self.serial.write((clean + "\n").encode('utf-8'))
                    wait_for_ack()
                    if not ack_event.wait(timeout=2):
                        logger.warning(f"GRBL timeout, no ack for: {clean}")
                        if self.debug_mode:
                            print(f"[TIMEOUT] No ack for: {clean}")
                        break

    def get_position(self):
        with self.status_lock:
            return tuple(self.position)

    def close(self):
        """Safely close the GRBL motor controller connection."""
        try:
            self.running = False
            
            # Wait for threads to finish
            if hasattr(self, 'reader_thread') and self.reader_thread.is_alive():
                self.reader_thread.join(timeout=2)
            if hasattr(self, 'writer_thread') and self.writer_thread.is_alive():
                self.writer_thread.join(timeout=2)
            if hasattr(self, 'poll_thread') and self.poll_thread.is_alive():
                self.poll_thread.join(timeout=2)
            
            # Close serial connection
            if self.serial and self.serial.is_open:
                self.serial.close()
                logger.info(f"Closed connection to {self.port}")
                
        except Exception as e:
            logger.error(f"Error closing GRBL controller: {e}")
