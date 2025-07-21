# Multi-Axis Stepper Control Plan (stepperpi + TB6600 Drivers)

This document consolidates all the key details and planning required for controlling X, Y, Z, and Z-Rotation motors using `stepperpi` and TB6600 drivers. It includes configuration, pin mapping, motion parameters, and a YAML configuration ready for Cursor.

---

## Machine Details from `config.py`
- **Work Area:** X = 68 in (1727 mm), Y = 45 in (1143 mm)
- **Motors & Steps:**
  - **X:** STEP=24, DIR=23, EN=9, HALL=16, 800 pulses/rev, 20 mm/rev, 80 steps/mm, invert_dir=True.
  - **Y1:** STEP=22, DIR=27, EN=17, HALL=1, 800 pulses/rev, 20 mm/rev, 80 steps/mm, invert_dir=True.
  - **Y2:** STEP=6, DIR=5, EN=10, HALL=20, 800 pulses/rev, 20 mm/rev, 80 steps/mm, invert_dir=False.
  - **Z_LIFT:** STEP=18, DIR=7, EN=8, HALL=25, 800 pulses/rev, 5 mm/rev, 400 steps/mm, invert_dir=False.
  - **Z_ROTATE:** STEP=26, DIR=19, EN=13, HALL=12, 1600 pulses/rev, 360 deg/rev, 10 steps/deg, invert_dir=True.
- **Motion Defaults:** default_speed = 20 mm/s, default_accel = 100 mm/s², lift_height = 25.4 mm.

---

## GPIO Pin Map
| Axis      | STEP GPIO | DIR GPIO | ENA GPIO | HALL | Steps/unit  | Invert DIR |
|-----------|-----------|----------|----------|------|-------------|------------|
| X         | 24        | 23       | 9        | 16   | 80 steps/mm  | True       |
| Y1        | 22        | 27       | 17       | 1    | 80 steps/mm  | True       |
| Y2        | 6         | 5        | 10       | 20   | 80 steps/mm  | False      |
| Z_LIFT    | 18        | 7        | 8        | 25   | 400 steps/mm | False      |
| Z_ROTATE  | 26        | 19       | 13       | 12   | 10 steps/deg | True       |

---

## Motion Parameters
- **Max feed (initial):** 100 mm/s (safe start = 20 mm/s)
- **Acceleration:** 100 mm/s²
- **Lift height:** 25.4 mm

---

## Homing & Limits
- Hall sensors: X=16, Y1=1, Y2=20, Z=25, Z_ROT=12
- HOMING_OFFSET = 5 mm
- VERIFICATION_DISTANCE = 10 mm

---

## Integration Notes
```python
AXES = {
    'X': {'step':24, 'dir':23, 'ena':9, 'invert':True, 'steps_per_mm':80},
    'Y1':{'step':22, 'dir':27, 'ena':17, 'invert':True, 'steps_per_mm':80},
    'Y2':{'step':6,  'dir':5,  'ena':10, 'invert':False,'steps_per_mm':80},
    'Z': {'step':18, 'dir':7,  'ena':8,  'invert':False,'steps_per_mm':400},
    'A': {'step':26, 'dir':19, 'ena':13, 'invert':True, 'steps_per_deg':10},
}
```

**Work Envelope:** {X: 1727 mm, Y: 1143 mm, Z: 63.5 mm (2.5 in), A: continuous}

---

## Configuration YAML
```yaml
machine:
  name: fabric_cnc_v1
  units: mm
  planner:
    max_accel: {x: 100, y: 100, z: 50, a: 300}
    junction_deviation: 0.05
    segment_tolerance: 0.05
  gpio:
    use_pigpio: true
  axes:
    X: {step:24, dir:23, ena:9, invert_dir:true, steps_per_mm:80, hall:16}
    Y1:{step:22, dir:27, ena:17, invert_dir:true, steps_per_mm:80, hall:1}
    Y2:{step:6,  dir:5,  ena:10, invert_dir:false, steps_per_mm:80, hall:20}
    Z: {step:18, dir:7,  ena:8,  invert_dir:false, steps_per_mm:400, hall:25}
    A: {step:26, dir:19, ena:13, invert_dir:true, steps_per_deg:10, hall:12}
  limits:
    X: {min:0, max:1727}
    Y: {min:0, max:1143}
    Z: {min:0, max:63.5}
    A: {min:-9999, max:9999}
```

---

## Next Steps
- Copy this plan to `multi_axis_plan.md`.
- Upload it to Cursor.
- Use the included YAML as the machine config.
