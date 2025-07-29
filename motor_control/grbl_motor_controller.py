# motor_control/grbl_motor_controller.py
import serial
import threading
import time
import queue
import re

class GrblMotorController:
    def __init__(self, port='/dev/ttyACM0', baudrate=115200):
        self.serial = serial.Serial(port, baudrate, timeout=1)
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
        
        # Initialize GRBL to use inches and reset work coordinates
        time.sleep(2)  # Wait for GRBL to initialize
        self.send("G20")  # Set units to inches
        self.send("G90")  # Set absolute positioning
        self.send("G10 P1 L20 X0 Y0 Z0 A0")  # Reset work coordinates to 0,0,0,0
        self.send("G54")  # Select work coordinate system 1

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
                        print(f"[GRBL RESP] {decoded}")
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

    def send(self, gcode_line):
        self.command_queue.put(gcode_line)

    def send_immediate(self, gcode_line):
        self.serial.write((gcode_line + "\n").encode('utf-8'))

    def jog(self, axis, delta, feedrate=100):
        if axis not in "XYZA":
            raise ValueError("Invalid axis")
        # Use G20 for inches instead of G21 for mm
        self.send(f"$J=G91 G20 {axis}{delta:.3f} F{feedrate}")

    def home_all(self):
        self.send("$H")
        # After homing, reset work coordinates to 0,0,0,0
        time.sleep(1)  # Wait for homing to complete
        self.send("G10 P1 L20 X0 Y0 Z0 A0")  # Set work coordinate system origin
        self.send("G54")  # Select work coordinate system 1

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
                                print(f"[GRBL ERROR] {resp}")
                                ack_event.set()
                                break

                    ack_event.clear()
                    self.serial.write((clean + "\n").encode('utf-8'))
                    wait_for_ack()
                    if not ack_event.wait(timeout=2):
                        print(f"[TIMEOUT] No ack for: {clean}")
                        break

    def get_position(self):
        with self.status_lock:
            return tuple(self.position)

    def close(self):
        self.running = False
        self.serial.close()
