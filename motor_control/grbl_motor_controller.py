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
        self.send("$H")
        # After homing, reset work coordinates to 0,0,0,0
        time.sleep(2)  # Wait for homing to complete
        self.send("G10 P1 L20 X0 Y0 Z0 A0")  # Set work coordinate system origin
        self.send("G54")  # Select work coordinate system 1
        # Reset position tracking
        with self.status_lock:
            self.position = [0.0, 0.0, 0.0, 0.0]

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
