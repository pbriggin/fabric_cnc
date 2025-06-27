# EMI Troubleshooting Guide for Hall Effect Sensors

## Problem: Motor Current Interference with Hall Sensors

Your NJK-5002C hall effect sensors are being triggered prematurely by electromagnetic interference (EMI) from the stepper motor current. This is a common issue in CNC applications.

## Quick Diagnostic Tests

### 1. Test for EMI Interference
```bash
# Run the enhanced hall sensor test with motor interference testing
python -m fabric_cnc.motor_control.hall_sensor_test --test-motor-interference
```

### 2. Monitor Sensors with EMI Resistance
```bash
# Run the EMI-resistant sensor monitor
python -m fabric_cnc.motor_control.emi_resistant_homing
```

## Hardware Solutions (Priority Order)

### 1. Cable Routing & Shielding (Most Important)
- **Separate motor and sensor cables** by at least 6 inches
- **Cross cables at 90° angles** when they must intersect
- **Use shielded cables** for hall sensor wiring
- **Keep sensor wires as short as possible**

### 2. Ferrite Beads & EMI Filters
- Add **ferrite beads** on sensor signal lines
- Use **0.1µF ceramic capacitors** between signal and ground
- Add **common mode chokes** for additional filtering

### 3. Power Supply Isolation
- **Separate power supplies** for motors and sensors
- Use **isolated DC-DC converters** for sensor power
- Add **decoupling capacitors** near sensors

### 4. Grounding Improvements
- **Star grounding** - single ground point for all components
- **Separate analog and digital grounds**
- **Thick ground wires** for motor power

## Software Solutions

### 1. Enhanced Hall Sensor Test
The updated `hall_sensor_test.py` includes:
- **Debouncing** (50ms default)
- **Filtering** (5-sample majority voting)
- **Interference detection** (rapid trigger counting)
- **Motor interference testing**

### 2. EMI-Resistant Homing System
The new `emi_resistant_homing.py` provides:
- **Configurable debounce time** (100ms default)
- **7-sample filtering** (odd number for majority voting)
- **Interference threshold detection** (3 rapid triggers)
- **Homing verification** (move away and back)

## Configuration Recommendations

### For Severe EMI Issues:
```python
# In your homing system
homing = EMIResistantHoming(
    debounce_ms=200,           # Longer debounce
    filter_samples=9,          # More samples for filtering
    interference_threshold=2,  # Lower threshold
    verify_distance_mm=10.0    # Longer verification distance
)
```

### For Moderate EMI Issues:
```python
# Standard configuration
homing = EMIResistantHoming(
    debounce_ms=100,           # Standard debounce
    filter_samples=7,          # 7-sample filtering
    interference_threshold=3,  # Standard threshold
    verify_distance_mm=5.0     # Standard verification
)
```

## Testing Procedure

### 1. Baseline Test
```bash
# Test sensors without motors running
python -m fabric_cnc.motor_control.hall_sensor_test
```

### 2. Motor Interference Test
```bash
# Test sensors while motors are running
python -m fabric_cnc.motor_control.hall_sensor_test --test-motor-interference
```

### 3. EMI-Resistant Monitoring
```bash
# Monitor with filtering and interference detection
python -m fabric_cnc.motor_control.emi_resistant_homing
```

## Troubleshooting Steps

### Step 1: Identify the Problem
- Run the motor interference test
- Note which sensors are affected
- Check if interference occurs during specific motor movements

### Step 2: Apply Hardware Fixes
1. **Re-route cables** - separate motor and sensor wiring
2. **Add ferrite beads** to sensor signal lines
3. **Install EMI filters** near sensors
4. **Improve grounding** - star ground configuration

### Step 3: Adjust Software Parameters
1. **Increase debounce time** if sensors trigger multiple times
2. **Increase filter samples** for more robust filtering
3. **Lower interference threshold** for earlier detection
4. **Add verification steps** to confirm home position

### Step 4: Verify Solutions
1. **Re-run interference tests** after hardware changes
2. **Test homing reliability** with new parameters
3. **Monitor during normal operation** for false triggers

## Common Issues & Solutions

### Issue: Sensors trigger during motor acceleration
**Solution**: Increase debounce time to 150-200ms

### Issue: Sensors trigger randomly during operation
**Solution**: Add ferrite beads and improve cable routing

### Issue: Homing fails intermittently
**Solution**: Increase filter samples to 9-11 and add verification

### Issue: Sensors trigger when motors are enabled but not moving
**Solution**: Check power supply isolation and grounding

## Advanced Solutions

### 1. Optical Isolation
- Use **opto-isolators** between sensors and Raspberry Pi
- Provides complete electrical isolation

### 2. Differential Signaling
- Use **differential pairs** for sensor signals
- More resistant to common-mode interference

### 3. Shielding Enclosures
- **Metal enclosures** around sensitive electronics
- **Faraday cages** for extreme EMI environments

## Monitoring & Maintenance

### Regular Checks
- **Monthly**: Run interference tests
- **Quarterly**: Check cable routing and shielding
- **Annually**: Verify grounding connections

### Warning Signs
- **Increased false triggers** during operation
- **Intermittent homing failures**
- **Sensors triggering during motor movement**
- **Random position errors**

## Emergency Procedures

### If Homing Fails Due to EMI:
1. **Stop all movement immediately**
2. **Disable motors** to reduce interference
3. **Manually verify sensor operation**
4. **Check for loose connections**
5. **Restart with increased filtering parameters**

### If Sensors Are Completely Unreliable:
1. **Switch to manual homing mode**
2. **Use limit switches as backup**
3. **Implement software position tracking**
4. **Schedule hardware improvements**

## Contact Information

For persistent EMI issues:
- Check motor driver specifications
- Consult with electrical engineer
- Consider professional EMI testing
- Review machine grounding system

---

**Remember**: EMI issues are often solved through a combination of hardware and software approaches. Start with hardware fixes, then fine-tune software parameters for optimal performance. 