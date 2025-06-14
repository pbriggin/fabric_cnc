#!/usr/bin/env/ python3
# -*- coding: utf-8 -*-
"""
FILE: setup.py
FILE THEME: GUI to test motors.
PROJECT: fabric_cnc
ORIGINAL AUTHOR: pbriggs
DATE CREATED: 14 June 2025
"""

import tkinter as tk
from fabric_cnc.motor_control.driver import StepperMotor
from fabric_cnc.config import GPIO_PINS, STEPS_PER_MM


class MotorTestUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Motor Test UI")

        self.motors = {
            name: StepperMotor(pins['DIR'], pins['STEP'], pins['EN'], name)
            for name, pins in GPIO_PINS.items()
            if 'DIR' in pins
        }

        row = 0
        for name, motor in self.motors.items():
            label = tk.Label(root, text=f"{name} Axis")
            label.grid(row=row, column=0)

            btn_fwd = tk.Button(root, text="Forward", command=lambda m=motor: self.move_motor(m, True))
            btn_rev = tk.Button(root, text="Reverse", command=lambda m=motor: self.move_motor(m, False))
            btn_fwd.grid(row=row, column=1)
            btn_rev.grid(row=row, column=2)
            row += 1

    def move_motor(self, motor, direction):
        steps = int(STEPS_PER_MM[motor.name] * 10)  # move 10 mm
        motor.step(direction, steps, 0.001)


if __name__ == "__main__":
    root = tk.Tk()
    app = MotorTestUI(root)
    root.mainloop()
