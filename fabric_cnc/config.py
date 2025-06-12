# fabric_cnc/config.py

GPIO_PINS = {
    'X': {'DIR': 2, 'STEP': 3, 'EN': 4, 'HALL': 17},
    'Y1': {'DIR': 5, 'STEP': 6, 'EN': 7, 'HALL': 27},
    'Y2': {'DIR': 8, 'STEP': 9, 'EN': 10},
    'Z_LIFT': {'DIR': 11, 'STEP': 12, 'EN': 13, 'HALL': 22},
    'Z_ROTATE': {'DIR': 14, 'STEP': 15, 'EN': 16, 'HALL': 23},
}

STEPS_PER_MM = {
    'X': 80,
    'Y1': 80,
    'Y2': 80,
    'Z_LIFT': 400,
    'Z_ROTATE': 10,
}

DIRECTION_INVERTED = {
    'X': False,
    'Y1': False,
    'Y2': True,
    'Z_LIFT': False,
    'Z_ROTATE': False,
}

DEFAULT_SPEED_MM_S = 20
DEFAULT_ACCEL_MM_S2 = 100
LIFT_HEIGHT_MM = 25.4

WORKAREA_MM = {
    'X': 1524,
    'Y': 1016,
}

USE_SIMULATION_MODE = False
STEP_PULSE_DURATION = 0.0005
