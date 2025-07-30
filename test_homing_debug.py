#!/usr/bin/env python3
"""
Debug script for homing issues.
Run this to diagnose why X-axis homing isn't working.
"""

import time
import logging
from motor_control.grbl_motor_controller import GrblMotorController

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

def main():
    try:
        print("🔧 HOMING DEBUG TOOL")
        print("=" * 50)
        
        # Initialize GRBL controller
        print("1. Connecting to GRBL...")
        controller = GrblMotorController(debug_mode=True)  # Enable debug mode
        time.sleep(3)  # Let it initialize
        
        print("\n2. Running comprehensive diagnostics...")
        controller.diagnose_homing_issue()
        
        print("\n3. Testing basic X-axis movement...")
        if controller.test_motor_movement('X', 0.1):
            print("   ✅ X-axis motor is working - homing issue is likely limit switch related")
        else:
            print("   ❌ X-axis motor not working - check motor configuration")
        
        print("\n4. Manual Tests:")
        print("   Try these commands manually in the terminal:")
        print("   - Can you jog X-axis from the GUI?")
        print("   - Does the X-axis limit switch trigger when pressed?")
        print("   - Check the GRBL settings printed above")
        
        # Keep connection open for manual testing
        input("\nPress Enter to close connection...")
        
        controller.close()
        
    except Exception as e:
        logger.error(f"Debug script failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()