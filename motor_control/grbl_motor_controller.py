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
        self.serial_lock = threading.Lock()  # Protect serial access
        self.connection_healthy = True
        self.alarm_detected = False
        self.last_error_time = 0
        self.response_callback = None  # Callback for manual command responses
        self.is_homed = False  # Track if machine is homed
        self.machine_state = "Unknown"  # Track GRBL state (Idle, Run, Hold, Alarm, etc.)

        self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.writer_thread = threading.Thread(target=self._write_loop, daemon=True)
        self.poll_thread = threading.Thread(target=self._poll_loop, daemon=True)

        self.reader_thread.start()
        self.writer_thread.start()
        self.poll_thread.start()
        
        # Wait for GRBL to initialize and check/clear alarms FIRST
        time.sleep(2)  # Wait for GRBL to initialize
        
        # Robust alarm clearing sequence at startup
        self._startup_alarm_clear()
        
        # Initialize GRBL settings and reset work coordinates
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
                return
            except serial.SerialException as e:
                if "Device or resource busy" in str(e) or "Permission denied" in str(e):
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
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except Exception as e:
                logger.warning(f"Error scanning processes: {e}")
            
            # Kill the blocking processes
            for pid in set(blocking_pids):  # Remove duplicates
                try:
                    process = psutil.Process(pid)
                    process.terminate()
                    
                    # Wait up to 3 seconds for graceful termination
                    try:
                        process.wait(timeout=3)
                    except psutil.TimeoutExpired:
                        process.kill()
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
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
                        # Deauthorize and reauthorize the USB device
                        subprocess.run(['sudo', 'sh', '-c', f'echo 0 > {reset_path}'], timeout=2)
                        time.sleep(0.5)
                        subprocess.run(['sudo', 'sh', '-c', f'echo 1 > {reset_path}'], timeout=2)
                        time.sleep(1.0)
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                pass
                
        except Exception:
            pass

    def _configure_grbl_settings(self):
        """Configure comprehensive GRBL settings for proper operation.""" 
        try:
            # Configure GRBL settings
            
            # Define all required settings
            settings = {
                # Basic settings
                "$0": "5.0",      # Step pulse time
                "$1": "25",       # Step idle delay
                "$2": "0",        # Step pulse invert
                "$3": "11",       # Step direction invert (X=1, Y=2, A=8, total=11, Z not inverted)
                "$4": "15",       # Step enable invert
                "$5": "15",       # Limit pins invert
                "$6": "0",        # Probe pin invert
                "$9": "1",        # PWM spindle mode
                "$10": "2",       # Status report options: WPos only (1=MPos, 2=WPos, 3=both)
                "$11": "0.010",   # Junction deviation
                "$12": "0.002",   # Arc tolerance
                "$13": "0",       # Report inches
                "$15": "0",       # Work area alarm
                "$16": "0",       # Work area alarm
                "$18": "0",       # Tool change mode
                "$19": "0",       # Laser mode
                "$20": "0",       # Soft limits
                "$21": "0",       # Hard limits disable (prevent A-axis limit issues)
                "$22": "1",       # Homing cycle enable
                "$23": "3",       # Homing direction mask (X=1, Y=1, Z=0, A=0 - X&Y home positive, Z&A home negative)
                "$24": "500.0",   # Homing seek rate (swapped - this implementation uses for first approach)
                "$25": "1500.0",  # Homing feed rate (swapped - this implementation uses for second approach)
                "$26": "250",     # Homing debounce
                "$27": "5.715",   # Homing pull-off (0.225 inches)
                "$28": "0.000",   # Homing locate feed rate
                "$29": "0.0",     # Homing search seek rate
                "$30": "1000.000", # Spindle max rpm
                "$31": "0.000",   # Spindle min rpm
                "$32": "0",       # Laser mode enable
                "$33": "5000.0",  # Spindle PWM frequency
                "$34": "0.0",     # Spindle PWM off value
                "$35": "0.0",     # Spindle PWM min value
                "$36": "100.0",   # Spindle PWM max value
                "$37": "0",       # Stepper deenergize mask
                "$39": "1",       # Enable legacy RT commands
                "$40": "0",       # Limit/control pins pull-up disable
                "$43": "1",       # Homing passes
                "$44": "4",       # Homing cycle mask
                "$45": "11",      # Homing cycle pulloff mask
                "$46": "0",       # Homing cycle allow manual
                "$47": "0",       # Homing cycle mpos set
                "$62": "0",       # Sleep enable
                "$63": "3",       # Feed hold actions
                "$64": "0",       # Force init alarm
                "$65": "0",       # Probe allow feed override
                
                # Steps per unit (inches)
                "$100": "40.00000",   # X steps/inch
                "$101": "40.00000",   # Y steps/inch  
                "$102": "200.00000",  # Z steps/inch
                "$103": "252.00000",  # A steps/inch
                
                # Maximum rates (inches/min)
                "$110": "3000.000",   # X max rate
                "$111": "3000.000",   # Y max rate
                "$112": "1500.000",   # Z max rate (increased to allow full homing seek speed)
                "$113": "1500.000",   # A max rate (increased to allow full homing seek speed)
                
                # Acceleration (inches/sec²)
                "$120": "100.000",    # X acceleration
                "$121": "100.000",    # Y acceleration
                "$122": "50.000",     # Z acceleration (increased for better homing performance)
                "$123": "50.000",     # A acceleration (increased for better homing performance)
                
                # Maximum travel (mm for GRBL)
                "$130": "1727.000",   # X max travel
                "$131": "1143.000",   # Y max travel
                "$132": "127.000",    # Z max travel
                "$133": "200.000",    # A max travel
                
                # Additional grblHAL settings
                "$341": "0",       # Tool change mode
                "$342": "30.0",    # Tool change probing distance
                "$343": "25.0",    # Tool change locate feed rate
                "$344": "200.0",   # Tool change search seek rate
                "$345": "200.0",   # Tool change probe pull-off rate
                "$346": "1",       # Restore position after M6
                "$370": "0",       # Invert I/O Port inputs
                "$376": "0",       # Invert I/O Port outputs
                "$384": "0",       # Disable G92 persistence
                "$394": "0.0",     # I/O Port analog input deadband
                "$398": "100",     # Planner buffer blocks
                "$481": "0",       # Autoreporting interval
                "$485": "0",       # Multi-axis step pulse delay
                "$486": "0",       # Step pulse delay
                "$538": "0",       # Encoders enabled
                "$539": "0.0",     # Encoder step rate
                "$650": "0",       # WebUI heap size
                "$673": "0.0",     # Tool change probing overrides
                "$676": "3",       # WiFi mode
                "$680": "0"        # Modbus enable
            }
            
            # Send all settings with small delays
            for setting, value in settings.items():
                self.send(f"{setting}={value}")
                time.sleep(0.1)  # Small delay between settings
            
            # All GRBL settings configured
            
            # Wait for all settings to be processed
            time.sleep(2.0)
            
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
            "error:37": "The G43.1 dynamic tool length offset command cannot apply an offset to an axis other than its configured axis. The Grbl default axis is the Z-axis.",
            "error:79": "Homing not enabled in settings, or emergency stop/limit switch triggered during unlock attempt."
        }
        
        return error_codes.get(error_str, "Unknown GRBL error")

    def _read_loop(self):
        buffer = b""
        while self.running:
            try:
                # Skip if connection is unhealthy
                if not self.connection_healthy:
                    time.sleep(0.1)
                    continue
                    
                if self.serial and self.serial.is_open and self.serial.in_waiting:
                    buffer += self.serial.read(self.serial.in_waiting)
                    lines = buffer.split(b'\n')
                    buffer = lines[-1]  # keep incomplete line
                    for line in lines[:-1]:
                        decoded = line.decode('utf-8').strip()
                        if decoded.startswith("<"):
                            self._last_status_line = decoded  # Store for direct parsing during homing
                            self._parse_status(decoded)
                        else:
                            if self.debug_mode:
                                print(f"[GRBL RESP] {decoded}")
                            elif not decoded.strip() == "ok":  # Only log non-"ok" responses in non-debug mode
                                if decoded.startswith("error:"):
                                    error_msg = self._interpret_grbl_error(decoded)
                                    logger.error(f"GRBL {decoded}: {error_msg}")
                                    
                                    # Send to GUI if callback is set
                                    if self.response_callback:
                                        self.response_callback(f"ERROR: {decoded} - {error_msg}")
                                    
                                    # Auto-clear alarm if error:9 (alarm state) or error:79 (unlock failed)
                                    if decoded == "error:9" or decoded == "error:79":
                                        current_time = time.time()
                                        # Only try to clear alarm once every 5 seconds to avoid spam
                                        if current_time - self.last_error_time > 5.0:
                                            self.last_error_time = current_time
                                            if decoded == "error:9":
                                                logger.info("Auto-clearing alarm state (error:9)...")
                                                self.send("$X")  # Send unlock command
                                            elif decoded == "error:79":
                                                logger.info("Unlock failed (error:79) - trying reset + unlock...")
                                                self.send_immediate("\x18")  # Soft reset
                                                time.sleep(1)
                                                self.send("$X")  # Try unlock after reset
                                else:
                                    logger.info(f"GRBL: {decoded}")
                                    # Send non-error responses to GUI if callback is set
                                    if self.response_callback:
                                        self.response_callback(decoded)
                            else:
                                # Send "ok" responses to GUI if callback is set
                                if self.response_callback:
                                    self.response_callback("ok")
            except (serial.SerialException, OSError, TypeError) as e:
                if self.running and self.connection_healthy:
                    logger.warning(f"Serial read error in background thread: {e}")
                    self.connection_healthy = False
                time.sleep(0.1)
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"Unexpected error in read loop: {e}")
                time.sleep(0.1)
                continue
            time.sleep(0.01)

    def _write_loop(self):
        while self.running:
            try:
                cmd = self.command_queue.get(timeout=0.1)
                if self.connection_healthy and self.serial and self.serial.is_open:
                    self.serial.write((cmd + "\n").encode('utf-8'))
                self.command_queue.task_done()
            except queue.Empty:
                continue
            except (serial.SerialException, OSError) as e:
                if self.running and self.connection_healthy:
                    logger.warning(f"Serial write error in background thread: {e}")
                    self.connection_healthy = False
                self.command_queue.task_done()
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"Unexpected error in write loop: {e}")
                self.command_queue.task_done()
                continue

    def _poll_loop(self):
        while self.running:
            try:
                if self.connection_healthy and self.serial and self.serial.is_open:
                    self.serial.write(b"?\n")
            except (serial.SerialException, OSError) as e:
                if self.running and self.connection_healthy:
                    logger.warning(f"Serial poll error in background thread: {e}")
                    self.connection_healthy = False
            except Exception as e:
                if self.running:
                    logger.error(f"Unexpected error in poll loop: {e}")
            time.sleep(0.2)

    def _parse_status(self, line):
        # Parse GRBL state from status line (e.g., <Idle|WPos:0,0,0,0|...)
        state_match = re.search(r"<([^|]+)", line)
        if state_match:
            with self.status_lock:
                self.machine_state = state_match.group(1)
                # Machine is considered homed if not in Alarm state and has valid coordinates
                # GRBL doesn't explicitly report "homed" status, but Alarm state usually means not homed
                self.is_homed = self.machine_state not in ["Alarm", "Unknown"]
        
        # Try to parse work coordinates first (WPos), then fall back to machine coordinates (MPos)
        wpos_match = re.search(r"WPos:([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)", line)
        mpos_match = re.search(r"MPos:([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)", line)
        
        if wpos_match:
            # Use work coordinates directly
            with self.status_lock:
                old_position = self.position.copy()
                self.position = [float(wpos_match.group(i)) for i in range(1, 5)]
                if self.debug_mode:
                    print(f"[GRBL DEBUG] Raw position from GRBL (WPos): {self.position}")
                    
                # Log position changes for debugging in debug mode only
                if self.debug_mode and old_position != self.position:
                    print(f"[GRBL DEBUG] Position (WPos): X={self.position[0]:.3f}, Y={self.position[1]:.3f}, Z={self.position[2]:.3f}, A={self.position[3]:.3f}")
                    print(f"[GRBL DEBUG] Using WPos coordinates for position display")
        elif mpos_match:
            # Convert machine coordinates to work coordinates using stored offsets
            with self.status_lock:
                old_position = self.position.copy()
                mpos = [float(mpos_match.group(i)) for i in range(1, 5)]
                
                # Simple approach: always use work_offset if available
                if hasattr(self, 'work_offset') and self.work_offset is not None:
                    # Calculate work coordinates by subtracting the offset
                    self.position = [mpos[i] - self.work_offset[i] for i in range(4)]
                else:
                    # No work offset - use machine coordinates directly
                    self.position = mpos
                
                if self.debug_mode:
                    print(f"[GRBL DEBUG] Converted MPos {mpos} to WPos {self.position}")
                    
                # Log position changes for debugging in debug mode only
                if self.debug_mode and old_position != self.position:
                    print(f"[GRBL DEBUG] Position (WPos from MPos): X={self.position[0]:.3f}, Y={self.position[1]:.3f}, Z={self.position[2]:.3f}, A={self.position[3]:.3f}")
                    print(f"[GRBL DEBUG] Using converted WPos coordinates for position display")

    def send(self, gcode_line):
        self.command_queue.put(gcode_line)
    
    def set_response_callback(self, callback):
        """Set callback function to receive GRBL responses for manual commands."""
        self.response_callback = callback
    
    def clear_response_callback(self):
        """Clear the response callback."""
        self.response_callback = None

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
        logger.info("Starting home all axes sequence...")
        self.send("$H")
        
        # Wait for homing to complete - this is critical timing
        time.sleep(10)  # Extended wait for all axes homing and pushoff
        
        # Wait for machine to stabilize and get final MACHINE position
        logger.info("Waiting for machine to stabilize after homing...")
        stable_machine_position = None
        for attempt in range(10):  # Try up to 10 times to get stable position
            self.send_immediate("?")  # Send directly to get raw response
            time.sleep(0.5)
            
            # Parse the last received line to get machine coordinates directly
            if hasattr(self, '_last_status_line'):
                mpos_match = re.search(r"MPos:([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)", self._last_status_line)
                if mpos_match:
                    current_machine_pos = [float(mpos_match.group(i)) for i in range(1, 5)]
                    
                    if stable_machine_position is None:
                        stable_machine_position = current_machine_pos
                    elif all(abs(stable_machine_position[i] - current_machine_pos[i]) < 0.25 for i in range(4)):
                        # Position is stable - same for 2 consecutive readings (0.25mm tolerance)
                        break
                    else:
                        stable_machine_position = current_machine_pos
        
        # Store the stable homed MACHINE position as work offset
        if stable_machine_position:
            with self.status_lock:
                self.work_offset = stable_machine_position.copy()
        else:
            # Fallback - use current position but this shouldn't happen
            with self.status_lock:
                self.work_offset = self.position.copy()
        
        logger.info(f"Home all completed - work offset set to {self.work_offset}")
        
        # Set GRBL work coordinate system to origin at current position
        # This tells GRBL that the current (homed) position should be (0,0,0,0) in work coordinates
        self.send("G10 P1 L20 X0 Y0 Z0 A0")  # Set work coordinate system origin
        time.sleep(0.5)
        
        # Select work coordinate system 1 (G54)
        self.send("G54")
        time.sleep(0.5)
        
        # Force immediate position update to apply the new offset
        self.send("?")
        time.sleep(0.5)
        
        # Mark as homed after successful homing
        with self.status_lock:
            self.is_homed = True
    
    def is_machine_homed(self) -> bool:
        """Check if the machine is currently homed."""
        with self.status_lock:
            return self.is_homed and self.machine_state not in ["Alarm", "Unknown"]
    
    def get_machine_state(self) -> str:
        """Get the current GRBL machine state."""
        with self.status_lock:
            return self.machine_state
    
    def ensure_homed(self) -> bool:
        """Ensure machine is homed. Home if necessary. Returns True if homed successfully."""
        try:
            # Check current status
            self.send_immediate("?")
            time.sleep(0.5)
            
            if self.is_machine_homed():
                logger.info("Machine is already homed")
                return True
            
            logger.info(f"Machine not homed (state: {self.get_machine_state()}). Initiating homing sequence...")
            
            # Clear any alarms first
            if self.machine_state == "Alarm":
                logger.info("Clearing alarm state before homing...")
                self.send("$X")
                time.sleep(1)
            
            # Perform homing
            self.home_all()
            
            # Verify homing was successful
            time.sleep(1)
            self.send_immediate("?")
            time.sleep(0.5)
            
            if self.is_machine_homed():
                logger.info("Homing completed successfully")
                return True
            else:
                logger.error(f"Homing failed. Machine state: {self.get_machine_state()}")
                return False
                
        except Exception as e:
            logger.error(f"Error during homing check/execution: {e}")
            return False

    def check_limit_switches(self):
        """Check the current status of limit switches."""
        try:
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
                    pass
            
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
            self.send("$$")  # Request all settings
            time.sleep(1)  # Wait for response
            
        except Exception as e:
            logger.error(f"Failed to get GRBL settings: {e}")
    
    def get_grbl_info(self):
        """Get GRBL version and build info."""
        try:
            self.send("$I")  # Request build info
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Failed to get GRBL info: {e}")
    
    def clear_alarms_simple(self):
        """Simple alarm clearing that doesn't disrupt threads."""
        try:
            self.send("$X")  # Send unlock command through normal queue
            return True
        except Exception as e:
            logger.error(f"Failed to clear alarms: {e}")
            return False
    
    def _startup_alarm_clear(self):
        """Robust alarm clearing sequence for startup."""
        try:
            # Comprehensive alarm clearing sequence
            
            # Method 1: Try simple unlock first
            self.send("$X")
            time.sleep(2)
            
            # Method 2: If still in alarm, try soft reset + unlock
            self.send_immediate("\x18")  # Ctrl-X soft reset
            time.sleep(3)  # Wait for reset
            
            # Wait for startup messages
            start_time = time.time()
            while time.time() - start_time < 2.0:
                if self.serial.in_waiting:
                    try:
                        msg = self.serial.readline().decode('utf-8').strip()
                    except:
                        pass
                time.sleep(0.1)
            
            # Send unlock after reset
            self.send("$X")
            time.sleep(1)
            
            # Method 3: Try unlock (hard limits already disabled at startup)
            self.send("$X")     # Try unlock
            time.sleep(1)
            
            # Method 4: Final attempt with position reset
            self.send("G10 P1 L20 X0 Y0 Z0 A0")  # Reset work coordinates
            time.sleep(0.5)
            self.send("$X")  # Final unlock attempt
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Failed during startup alarm clearing: {e}")
    
    def diagnose_homing_issue(self):
        """Diagnose why homing isn't working."""
        try:
            logger.info("🔍 COMPREHENSIVE HOMING DIAGNOSTICS")
            logger.info("=" * 60)
            
            # 1. Check alarm state first
            logger.info("1. Checking alarm state...")
            self.send_immediate("?")
            time.sleep(1)
            
            # 2. Test individual axis movement
            logger.info("2. Testing individual axis movement...")
            axes_to_test = ['X', 'Z']  # Focus on problem axes
            for axis in axes_to_test:
                logger.info(f"   Testing {axis}-axis...")
                if self.test_motor_movement(axis, 0.1):
                    logger.info(f"   ✅ {axis}-axis motor works")
                else:
                    logger.error(f"   ❌ {axis}-axis motor failed - check wiring/config")
            
            # 3. Check GRBL settings
            logger.info("3. Checking critical GRBL settings...")
            self.send("$$")  # Request all settings
            time.sleep(3)  # Wait for settings to print
            
            # 4. Check limit switch status
            logger.info("4. Checking limit switch status...")
            try:
                self.send("$Pins")  # grblHAL pin status
                time.sleep(1)
            except:
                logger.info("   $Pins command not supported")
            
            # 5. Test homing sequence step by step
            logger.info("5. Testing homing sequence components...")
            
            # Check if homing is enabled
            logger.info("   Checking if homing is enabled ($22)...")
            self.send("$22")
            time.sleep(0.5)
            
            # Check hard limits setting
            logger.info("   Checking hard limits setting ($21)...")
            self.send("$21")
            time.sleep(0.5)
            
            # Check homing direction mask
            logger.info("   Checking homing direction mask ($23)...")
            self.send("$23")
            time.sleep(0.5)
            
            # 6. Manual limit switch test
            logger.info("6. MANUAL LIMIT SWITCH TEST:")
            logger.info("   Please manually press each limit switch and observe:")
            logger.info("   - X-axis limit switch")
            logger.info("   - Z-axis limit switch")
            logger.info("   Watch for pin state changes in the status output above")
            
            # 7. Recommendations
            logger.info("7. TROUBLESHOOTING RECOMMENDATIONS:")
            logger.info("   Common issues and solutions:")
            logger.info("   • Motor doesn't move: Check $100,$110,$120 settings")
            logger.info("   • Motor moves but error:5: Check limit switch wiring")
            logger.info("   • Wrong direction: Adjust $23 (homing direction mask)")
            logger.info("   • Homing disabled: Set $22=1")
            logger.info("   • Hard limits disabled: Set $21=1")
            logger.info("   • Speed too high: Lower $24 (seek) and $25 (feed)")
            
            logger.info("=" * 60)
            logger.info("🔍 DIAGNOSTICS COMPLETE")
            
        except Exception as e:
            logger.error(f"Failed to run diagnostics: {e}")
    
    def test_axis_homing_individually(self, axis):
        """Test homing for a specific axis with detailed feedback."""
        try:
            logger.info(f"🎯 TESTING {axis}-AXIS HOMING")
            logger.info("-" * 30)
            
            # Step 1: Test jogging in both directions
            logger.info(f"Step 1: Testing {axis}-axis movement in both directions...")
            logger.info(f"   Testing {axis}+ direction...")
            if self.test_motor_movement(axis, 0.1):
                logger.info(f"   ✅ {axis}+ movement works")
            else:
                logger.error(f"   ❌ {axis}+ movement failed")
            
            logger.info(f"   Testing {axis}- direction...")
            if self.test_motor_movement(axis, -0.1):
                logger.info(f"   ✅ {axis}- movement works")
            else:
                logger.error(f"   ❌ {axis}- movement failed")
            
            # Step 2: Check homing direction setting
            logger.info(f"Step 2: Checking homing direction for {axis}-axis...")
            axis_bit = {'X': 0, 'Y': 1, 'Z': 2, 'A': 3}[axis]
            logger.info(f"   Current $23 setting controls homing direction")
            logger.info(f"   Bit {axis_bit} in $23 controls {axis}-axis direction:")
            logger.info(f"   • 0 = Home towards negative direction ({axis}-)")
            logger.info(f"   • 1 = Home towards positive direction ({axis}+)")
            self.send("$23")
            time.sleep(1)
            
            # Step 3: Check current status
            logger.info(f"Step 3: Checking machine status before homing...")
            self.send_immediate("?")
            time.sleep(0.5)
            
            # Step 4: Attempt homing with monitoring
            logger.info(f"Step 4: Attempting {axis}-axis homing...")
            logger.warning(f"⚠️  Watch if motor actually moves during homing!")
            
            # Get position before homing
            pos_before = self.get_position()
            logger.info(f"   Position before homing: {pos_before}")
            
            self.send(f"$H{axis}")
            
            # Monitor position during homing
            for i in range(10):  # Check position every 0.8 seconds for 8 seconds
                time.sleep(0.8)
                pos_current = self.get_position()
                axis_idx = {'X': 0, 'Y': 1, 'Z': 2, 'A': 3}[axis]
                movement = abs(pos_current[axis_idx] - pos_before[axis_idx])
                if movement > 0.01:  # Motor moved more than 0.01 inches
                    logger.info(f"   ✅ Motor IS moving! Current position: {pos_current}")
                    break
            else:
                logger.error(f"   ❌ Motor NOT moving during homing!")
                logger.error(f"   This suggests wrong homing direction in $23 setting")
            
            # Step 5: Check final status
            logger.info(f"Step 5: Checking status after homing attempt...")
            self.send_immediate("?")
            time.sleep(0.5)
            pos_after = self.get_position()
            logger.info(f"   Position after homing: {pos_after}")
            
            logger.info(f"🎯 {axis}-AXIS HOMING TEST COMPLETE")
            return True
            
        except Exception as e:
            logger.error(f"Failed to test {axis}-axis homing: {e}")
            return False
    
    def test_motor_movement(self, axis='X', distance=0.1):
        """Test if a motor can move at all."""
        try:
            logger.info(f"🧪 Testing {axis}-axis motor movement ({distance} inches)...")
            
            # Get current position
            current_pos = self.get_position()
            logger.info(f"   Current position: {current_pos}")
            
            # Try to move
            self.send("G91")  # Relative mode
            self.send(f"G1 {axis}{distance} F100")  # Move slowly
            self.send("G90")  # Back to absolute mode
            
            # Wait and check new position
            time.sleep(3)
            new_pos = self.get_position()
            logger.info(f"   New position: {new_pos}")
            
            # Check if movement occurred
            axis_index = {'X': 0, 'Y': 1, 'Z': 2, 'A': 3}[axis]
            movement = abs(new_pos[axis_index] - current_pos[axis_index])
            
            if movement > 0.001:  # Moved more than 0.001 inches
                logger.info(f"   ✅ {axis}-axis motor CAN move! Moved {movement:.4f} inches")
                return True
            else:
                logger.error(f"   ❌ {axis}-axis motor did NOT move!")
                return False
                
        except Exception as e:
            logger.error(f"Failed to test {axis}-axis movement: {e}")
            return False
    
    def reset_controller(self):
        """Perform a soft reset of the GRBL controller."""
        try:
            self.send_immediate("\x18")  # Ctrl-X soft reset
            time.sleep(2.0)  # Wait for reset to complete
            
            # Reconfigure settings after reset
            self._configure_grbl_settings()
            self.send("G20")  # Set inches mode
            self.send("G90")  # Set absolute positioning
            self.send("G10 P1 L20 X0 Y0 Z0 A0")  # Reset work coordinates
            self.send("G54")  # Select work coordinate system 1
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset controller: {e}")
            return False

    def run_gcode_file(self, filepath):
        """Stream G-code file with robust error handling and recovery."""
        
        # Preprocess G-code file
        gcode_lines = self._preprocess_gcode(filepath)
        if not gcode_lines:
            logger.warning("No valid G-code lines to execute")
            return
        
        logger.info(f"Starting G-code stream: {len(gcode_lines)} commands")
        
        # Check for alarms and unlock if needed
        if not self._ensure_ready_for_streaming():
            logger.error("Machine not ready for G-code streaming")
            return
        
        # Use simpler, more robust streaming approach
        try:
            self._stream_gcode_robust(gcode_lines)
            logger.info("G-code streaming completed successfully")
        except Exception as e:
            logger.error(f"G-code streaming failed: {e}")
            raise
    
    def _preprocess_gcode(self, filepath):
        """Preprocess G-code file: strip comments, validate lines, remove ultra-short segments."""
        processed_lines = []
        
        with open(filepath, 'r') as f:
            for line_num, line in enumerate(f, 1):
                # Strip whitespace and comments
                clean = line.strip()
                if ';' in clean:
                    clean = clean.split(';')[0].strip()
                
                # Skip empty lines
                if not clean:
                    continue
                
                # Validate line length (≤80 characters)
                if len(clean) > 80:
                    logger.warning(f"Line {line_num} too long ({len(clean)} chars), truncating: {clean[:50]}...")
                    clean = clean[:80]
                
                # Skip ultra-short segments (could be optimized further)
                if self._is_ultra_short_segment(clean):
                    if self.debug_mode:
                        logger.debug(f"Skipping ultra-short segment: {clean}")
                    continue
                
                processed_lines.append(clean)
        
        logger.info(f"Preprocessed {len(processed_lines)} valid G-code lines")
        return processed_lines
    
    def _is_ultra_short_segment(self, gcode_line):
        """Check if G-code line represents an ultra-short movement segment."""
        # Simple heuristic: check for very small coordinate values
        import re
        
        # Extract coordinate values
        coords = re.findall(r'[XYZ]([-+]?\d*\.?\d+)', gcode_line.upper())
        if not coords:
            return False
        
        # Check if all movements are very small (< 0.001 inches)
        for coord in coords:
            try:
                if abs(float(coord)) > 0.001:
                    return False
            except ValueError:
                continue
        
        return len(coords) > 0  # Only flag as ultra-short if we found coordinates
    
    def _ensure_ready_for_streaming(self):
        """Ensure machine is ready for G-code streaming."""
        try:
            # Send status query
            self.send_immediate("?")
            time.sleep(0.1)
            
            # Check machine state
            with self.status_lock:
                state = self.machine_state
            
            if state == "Alarm":
                logger.info("Machine in alarm state, attempting unlock...")
                self.send_immediate("$X")  # Unlock
                time.sleep(1.0)
                
                # Check again
                self.send_immediate("?")
                time.sleep(0.1)
                
                with self.status_lock:
                    if self.machine_state == "Alarm":
                        logger.error("Failed to clear alarm state")
                        return False
            
            logger.info(f"Machine ready for streaming (state: {state})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to check machine readiness: {e}")
            return False
    
    def _stream_gcode_with_flow_control(self, gcode_lines):
        """Stream G-code with sliding window flow control."""
        WINDOW_SIZE = 16  # Maximum commands in flight
        sent_lines = {}   # Track sent lines waiting for ack
        line_index = 0    # Current line to send
        completed = 0     # Lines completed
        
        last_status_time = time.time()
        STATUS_INTERVAL = 0.05  # 20 Hz max status queries
        
        while completed < len(gcode_lines) or sent_lines:
            current_time = time.time()
            
            # Send new lines if window has space
            while len(sent_lines) < WINDOW_SIZE and line_index < len(gcode_lines):
                line = gcode_lines[line_index]
                
                try:
                    self.serial.write((line + "\n").encode('utf-8'))
                    self.serial.flush()
                    sent_lines[line_index] = {
                        'line': line,
                        'sent_time': current_time
                    }
                    
                    if self.debug_mode:
                        logger.debug(f"Sent line {line_index + 1}: {line}")
                    
                    line_index += 1
                    
                except (serial.SerialException, OSError) as e:
                    if "device reports readiness to read but returned no data" in str(e) or "port that is not open" in str(e):
                        logger.warning(f"Serial disconnection detected while sending line {line_index + 1}: {e}")
                        
                        # Attempt to recover from disconnection
                        if self._attempt_streaming_recovery():
                            logger.info("Serial recovery successful, retrying send...")
                            # Clear any pending sent_lines since connection was lost
                            sent_lines.clear()
                            logger.info(f"Cleared pending commands, retrying from line {line_index + 1}")
                            continue  # Retry sending this line
                        else:
                            logger.error("Serial recovery failed during send")
                            raise Exception("Serial connection lost and recovery failed")
                    else:
                        logger.error(f"Serial error sending line {line_index + 1}: {e}")
                        raise
            
            # Process responses
            try:
                if self.serial.in_waiting > 0:
                    response = self.serial.readline().decode('utf-8').strip()
                    
                    if response == "ok":
                        # Find oldest sent line and mark as completed
                        if sent_lines:
                            oldest_index = min(sent_lines.keys())
                            del sent_lines[oldest_index]
                            completed += 1
                            
                            # Progress reporting
                            if completed % 50 == 0 or completed == len(gcode_lines):
                                progress = (completed / len(gcode_lines)) * 100
                                logger.info(f"G-code progress: {completed}/{len(gcode_lines)} ({progress:.1f}%)")
                    
                    elif response.startswith("error:"):
                        error_msg = self._interpret_grbl_error(response)
                        logger.error(f"GRBL error: {response} - {error_msg}")
                        
                        # Remove the failed line from tracking
                        if sent_lines:
                            oldest_index = min(sent_lines.keys())
                            failed_line = sent_lines[oldest_index]['line']
                            logger.error(f"Failed line {oldest_index + 1}: {failed_line}")
                            del sent_lines[oldest_index]
                            completed += 1  # Count as processed even if failed
                    
                    elif response.startswith("ALARM:"):
                        logger.error(f"GRBL ALARM: {response}")
                        logger.error("Stopping G-code streaming due to alarm")
                        raise Exception(f"GRBL alarm during streaming: {response}")
                    
                    elif response and self.debug_mode:
                        logger.debug(f"GRBL response: {response}")
            
            except (serial.SerialException, OSError) as e:
                if "device reports readiness to read but returned no data" in str(e):
                    logger.warning(f"Serial disconnection detected during streaming: {e}")
                    
                    # Attempt to recover from disconnection
                    if self._attempt_streaming_recovery():
                        logger.info("Serial recovery successful, continuing stream...")
                        # Clear any pending sent_lines since connection was lost
                        sent_lines.clear()
                        logger.info(f"Cleared pending commands, resuming from line {line_index + 1}")
                        continue  # Continue the streaming loop
                    else:
                        logger.error("Serial recovery failed, stopping stream")
                        raise Exception("Serial connection lost and recovery failed")
                else:
                    logger.error(f"Serial error reading response: {e}")
                    raise
            
            # Periodic status query (max 20 Hz)
            if current_time - last_status_time >= STATUS_INTERVAL:
                try:
                    if len(sent_lines) > 0:  # Only query status if commands are in flight
                        self.serial.write(b"?\n")
                    last_status_time = current_time
                except (serial.SerialException, OSError):
                    pass  # Ignore status query failures
            
            # Check for timeouts
            for idx, info in list(sent_lines.items()):
                if current_time - info['sent_time'] > 10.0:  # 10 second timeout
                    logger.warning(f"Timeout on line {idx + 1}: {info['line']}")
                    del sent_lines[idx]
                    completed += 1  # Count as processed to avoid hanging
            
            # Small sleep to prevent busy waiting
            time.sleep(0.001)
    
    def _attempt_streaming_recovery(self):
        """Attempt to recover from serial disconnection during streaming."""
        try:
            logger.info("Attempting serial recovery during streaming...")
            
            # Give device time to reset
            time.sleep(2.0)
            
            # Try to reopen the serial connection
            if self.serial and self.serial.is_open:
                try:
                    self.serial.close()
                except:
                    pass
            
            # Wait for device to be ready
            time.sleep(3.0)
            
            # Reopen with cleanup
            self._open_serial_with_cleanup()
            
            if not self.serial or not self.serial.is_open:
                logger.error("Failed to reopen serial connection")
                return False
            
            # Wait for GRBL to initialize
            time.sleep(2.0)
            
            # Reconfigure GRBL (minimal settings for recovery)
            try:
                self.send("G20")  # Set inches mode
                time.sleep(0.5)
                self.send("G90")  # Set absolute positioning
                time.sleep(0.5)
                self.send("G54")  # Select work coordinate system
                time.sleep(0.5)
                
                # Check if machine is responsive
                self.send_immediate("?")
                time.sleep(0.5)
                
                logger.info("Serial recovery completed successfully")
                return True
                
            except Exception as e:
                logger.error(f"Failed to reconfigure GRBL after recovery: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Serial recovery failed: {e}")
            return False
    
    def _stream_gcode_robust(self, gcode_lines):
        """Robust G-code streaming with automatic recovery."""
        MAX_RETRIES = 3
        BATCH_SIZE = 8  # Smaller batches for more reliable streaming
        
        line_index = 0
        total_lines = len(gcode_lines)
        
        while line_index < total_lines:
            # Determine batch size (remaining lines or BATCH_SIZE, whichever is smaller)
            batch_end = min(line_index + BATCH_SIZE, total_lines)
            batch = gcode_lines[line_index:batch_end]
            
            # Try to send this batch with retries
            success = False
            for attempt in range(MAX_RETRIES):
                try:
                    if self._send_gcode_batch(batch, line_index):
                        success = True
                        break
                    else:
                        logger.warning(f"Batch failed on attempt {attempt + 1}")
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(1.0)  # Brief pause before retry
                except Exception as e:
                    if "device reports readiness to read but returned no data" in str(e):
                        logger.warning(f"Connection lost during batch {line_index}-{batch_end}, attempt {attempt + 1}")
                        if self._simple_reconnect():
                            logger.info("Reconnected successfully, retrying batch...")
                            continue
                        else:
                            raise Exception("Failed to reconnect after connection loss")
                    else:
                        raise
            
            if not success:
                raise Exception(f"Failed to send batch {line_index}-{batch_end} after {MAX_RETRIES} attempts")
            
            line_index = batch_end
            
            # Progress reporting
            if line_index % 50 == 0 or line_index == total_lines:
                progress = (line_index / total_lines) * 100
                logger.info(f"G-code progress: {line_index}/{total_lines} ({progress:.1f}%)")
    
    def _send_gcode_batch(self, batch, start_index):
        """Send a small batch of G-code lines with acknowledgment."""
        try:
            with self.serial_lock:
                if not self.serial or not self.serial.is_open:
                    raise serial.SerialException("Serial connection not available")
                
                # Send each line in the batch
                for i, line in enumerate(batch):
                    line_num = start_index + i + 1
                    
                    # Send the line
                    self.serial.write((line + "\n").encode('utf-8'))
                    self.serial.flush()
                    
                    # Wait for acknowledgment with timeout
                    ack_received = False
                    start_time = time.time()
                    
                    while time.time() - start_time < 10.0:  # 10 second timeout
                        if self.serial.in_waiting > 0:
                            response = self.serial.readline().decode('utf-8').strip()
                            
                            if response == "ok":
                                ack_received = True
                                break
                            elif response.startswith("error:"):
                                error_msg = self._interpret_grbl_error(response)
                                logger.error(f"GRBL error on line {line_num}: {response} - {error_msg}")
                                # Continue with next line (don't fail entire batch for one error)
                                ack_received = True
                                break
                            elif response.startswith("ALARM:"):
                                logger.error(f"GRBL ALARM on line {line_num}: {response}")
                                raise Exception(f"GRBL alarm during streaming: {response}")
                            elif response.startswith("<"):
                                # Status message - parse and continue waiting
                                self._parse_status(response)
                            # Ignore other responses and keep waiting for ack
                        
                        time.sleep(0.001)  # Small sleep to prevent busy waiting
                    
                    if not ack_received:
                        logger.warning(f"Timeout waiting for ack on line {line_num}: {line}")
                        return False
                
                return True
                
        except (serial.SerialException, OSError) as e:
            if "device reports readiness to read but returned no data" in str(e):
                # This will be caught by the caller for reconnection
                raise
            else:
                logger.error(f"Serial error in batch send: {e}")
                return False
        except Exception as e:
            logger.error(f"Unexpected error in batch send: {e}")
            return False
    
    def _simple_reconnect(self):
        """Simple, reliable reconnection method."""
        try:
            logger.info("Attempting simple reconnection...")
            
            # Stop background threads temporarily
            with self.serial_lock:
                self.connection_healthy = False
                
                # Close existing connection
                if self.serial and self.serial.is_open:
                    try:
                        self.serial.close()
                    except:
                        pass
                
                # Wait for device reset
                time.sleep(3.0)
                
                # Reopen connection
                self._open_serial_with_cleanup()
                
                if not self.serial or not self.serial.is_open:
                    logger.error("Failed to reopen serial connection")
                    return False
                
                # Wait for GRBL initialization
                time.sleep(2.0)
                
                # Basic reconfiguration
                self.serial.write(b"G20\n")  # Inches
                time.sleep(0.5)
                self.serial.write(b"G90\n")  # Absolute
                time.sleep(0.5)
                self.serial.write(b"G54\n")  # Work coordinates
                time.sleep(0.5)
                
                # Mark connection as healthy
                self.connection_healthy = True
                
            logger.info("Simple reconnection successful")
            return True
            
        except Exception as e:
            logger.error(f"Simple reconnection failed: {e}")
            self.connection_healthy = False
            return False

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
                
        except Exception as e:
            logger.error(f"Error closing GRBL controller: {e}")
