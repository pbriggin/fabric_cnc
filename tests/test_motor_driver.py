#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the stepper motor driver implementation.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from fabric_cnc.motor_control.driver import MotorConfig, StepperMotor


class MockGPIO:
    """Mock GPIO interface for testing."""
    
    BCM = 11
    OUT = 0
    IN = 1
    HIGH = 1
    LOW = 0
    
    def __init__(self):
        self.setup_calls = []
        self.output_calls = []
        self.cleanup_calls = []
        
    def setmode(self, mode):
        pass
        
    def setup(self, pin, mode):
        self.setup_calls.append((pin, mode))
        
    def output(self, pin, value):
        self.output_calls.append((pin, value))
        
    def cleanup(self, pins=None):
        self.cleanup_calls.append(pins)


@pytest.fixture
def mock_gpio():
    """Create a mock GPIO interface."""
    return MockGPIO()


@pytest.fixture
def motor_config():
    """Create a test motor configuration."""
    return MotorConfig(
        dir_pin=1,
        step_pin=2,
        en_pin=3,
        name="TEST",
        steps_per_mm=80,
        direction_inverted=False
    )


def test_motor_initialization(mock_gpio, motor_config):
    """Test motor initialization."""
    motor = StepperMotor(
        config=motor_config,
        gpio=mock_gpio,
        simulation_mode=False
    )
    
    # Check GPIO setup
    assert len(mock_gpio.setup_calls) == 3
    assert (motor_config.dir_pin, MockGPIO.OUT) in mock_gpio.setup_calls
    assert (motor_config.step_pin, MockGPIO.OUT) in mock_gpio.setup_calls
    assert (motor_config.en_pin, MockGPIO.OUT) in mock_gpio.setup_calls
    
    # Check initial state
    assert not motor.enabled
    assert not motor._is_moving


def test_motor_enable_disable(mock_gpio, motor_config):
    """Test motor enable/disable functionality."""
    motor = StepperMotor(
        config=motor_config,
        gpio=mock_gpio,
        simulation_mode=False
    )
    
    # Enable motor
    motor.enable()
    assert motor.enabled
    assert (motor_config.en_pin, MockGPIO.LOW) in mock_gpio.output_calls
    
    # Disable motor
    motor.disable()
    assert not motor.enabled
    assert (motor_config.en_pin, MockGPIO.HIGH) in mock_gpio.output_calls


def test_motor_step(mock_gpio, motor_config):
    """Test motor stepping functionality."""
    motor = StepperMotor(
        config=motor_config,
        gpio=mock_gpio,
        simulation_mode=False
    )
    
    # Step motor
    steps = 10
    delay = 0.001
    motor.step(True, steps, delay)
    
    # Check direction pin
    assert (motor_config.dir_pin, MockGPIO.HIGH) in mock_gpio.output_calls
    
    # Check step pulses
    step_pulses = [
        call for call in mock_gpio.output_calls
        if call[0] == motor_config.step_pin
    ]
    assert len(step_pulses) == steps * 2  # HIGH and LOW for each step


def test_motor_move_mm(mock_gpio, motor_config):
    """Test motor movement in millimeters."""
    motor = StepperMotor(
        config=motor_config,
        gpio=mock_gpio,
        simulation_mode=False
    )
    
    # Move motor
    distance = 10.0  # mm
    speed = 20.0  # mm/s
    motor.move_mm(True, distance, speed)
    
    # Calculate expected steps
    expected_steps = int(distance * motor_config.steps_per_mm)
    
    # Check step pulses
    step_pulses = [
        call for call in mock_gpio.output_calls
        if call[0] == motor_config.step_pin
    ]
    assert len(step_pulses) == expected_steps * 2  # HIGH and LOW for each step


def test_motor_cleanup(mock_gpio, motor_config):
    """Test motor cleanup."""
    motor = StepperMotor(
        config=motor_config,
        gpio=mock_gpio,
        simulation_mode=False
    )
    
    # Cleanup motor
    motor.cleanup()
    
    # Check cleanup call
    assert len(mock_gpio.cleanup_calls) == 1
    assert set(mock_gpio.cleanup_calls[0]) == {
        motor_config.dir_pin,
        motor_config.step_pin,
        motor_config.en_pin
    }


def test_motor_context_manager(mock_gpio, motor_config):
    """Test motor context manager functionality."""
    with StepperMotor(
        config=motor_config,
        gpio=mock_gpio,
        simulation_mode=False
    ) as motor:
        assert motor.enabled
        
    # Check cleanup was called
    assert len(mock_gpio.cleanup_calls) == 1


def test_motor_simulation_mode(motor_config):
    """Test motor in simulation mode."""
    motor = StepperMotor(
        config=motor_config,
        simulation_mode=True
    )
    
    # Enable motor
    motor.enable()
    assert motor.enabled
    
    # Step motor
    steps = 10
    delay = 0.001
    start_time = time.time()
    motor.step(True, steps, delay)
    end_time = time.time()
    
    # Check timing
    expected_duration = steps * delay
    actual_duration = end_time - start_time
    assert abs(actual_duration - expected_duration) < 0.1


def test_motor_direction_inversion(mock_gpio, motor_config):
    """Test motor direction inversion."""
    # Create motor with inverted direction
    motor_config.direction_inverted = True
    motor = StepperMotor(
        config=motor_config,
        gpio=mock_gpio,
        simulation_mode=False
    )
    
    # Step motor forward
    motor.step(True, 1, 0.001)
    assert (motor_config.dir_pin, MockGPIO.LOW) in mock_gpio.output_calls
    
    # Step motor reverse
    motor.step(False, 1, 0.001)
    assert (motor_config.dir_pin, MockGPIO.HIGH) in mock_gpio.output_calls 