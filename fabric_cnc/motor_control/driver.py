#!/usr/bin/env/ python3
# -*- coding: utf-8 -*-
"""
FILE: driver.py
FILE THEME: Drives the stepper motors.
PROJECT: fabric_cnc
ORIGINAL AUTHOR: pbriggs
DATE CREATED: 14 June 2025
"""

import time
try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None

from fabric_cnc.config import STEP_PULSE_DURATION, USE_SIMULATION_MODE


class StepperMotor:
    def __init__(self, dir_pin, step_pin, en_pin, name=''):
        self.dir_pin = dir_pin
        self.step_pin = step_pin
        self.en_pin = en_pin
        self.name = name
        self.enabled = False

        if not USE_SIMULATION_MODE and GPIO:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.dir_pin, GPIO.OUT)
            GPIO.setup(self.step_pin, GPIO.OUT)
            GPIO.setup(self.en_pin, GPIO.OUT)
            GPIO.output(self.en_pin, GPIO.HIGH)

    def enable(self):
        if not USE_SIMULATION_MODE and GPIO:
            GPIO.output(self.en_pin, GPIO.LOW)
        self.enabled = True

    def disable(self):
        if not USE_SIMULATION_MODE and GPIO:
            GPIO.output(self.en_pin, GPIO.HIGH)
        self.enabled = False

    def step(self, direction, steps, delay):
        if not self.enabled:
            self.enable()

        if not USE_SIMULATION_MODE and GPIO:
            GPIO.output(self.dir_pin, GPIO.HIGH if direction else GPIO.LOW)

        for _ in range(steps):
            if not USE_SIMULATION_MODE and GPIO:
                GPIO.output(self.step_pin, GPIO.HIGH)
                time.sleep(STEP_PULSE_DURATION)
                GPIO.output(self.step_pin, GPIO.LOW)
            time.sleep(delay)

    def cleanup(self):
        if not USE_SIMULATION_MODE and GPIO:
            GPIO.cleanup([self.dir_pin, self.step_pin, self.en_pin])
