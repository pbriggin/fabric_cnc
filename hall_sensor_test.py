#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time

# List of GPIO pins to test
PINS = [20, 16, 12, 1, 7, 8]

GPIO.setmode(GPIO.BCM)
for pin in PINS:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("Monitoring hall effect sensor pins (Ctrl+C to exit):")
try:
    while True:
        states = [(pin, GPIO.input(pin)) for pin in PINS]
        print(" ".join([f"Pin {pin}: {'LOW' if state == 0 else 'HIGH'}" for pin, state in states]))
        time.sleep(0.5)
except KeyboardInterrupt:
    print("\nExiting...")
finally:
    GPIO.cleanup() 