# Focus Calibration for MirrorAphrodite

This guide explains how to calibrate the distance-to-focus mapping for the Arducam 64MP Hawkeyes camera used in the MirrorAphrodite smart mirror system.

## Prerequisites

1. Raspberry Pi with the Arducam 64MP Hawkeyes camera connected
2. HC-SR04 ultrasonic distance sensor connected to GPIO pins 23 (trigger) and 24 (echo)
3. Required Python packages installed (see requirements-calibration.txt)

## Installation

1. Install system dependencies:
   ```bash
   sudo apt update
   sudo apt install -y python3-picamera2 python3-gpiozero python3-matplotlib python3-numpy
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements-calibration.txt
   ```

## Running the Calibration

1. Run the calibration script:
   ```bash
   python3 calibrate_focus.py
   ```

2. Follow the on-screen instructions to calibrate focus at different distances.

## Calibration Process

The calibration process involves the following steps:

1. **Measure Distance**: The script uses the ultrasonic sensor to measure your current distance from the camera.

2. **Adjust Focus**: You'll interactively adjust the focus value until the image appears perfectly sharp.

3. **Save Calibration Point**: The distance and optimal focus value are saved as a calibration point.

4. **Repeat**: Move to different distances and repeat the process to build a comprehensive calibration curve.

5. **Generate Mapping**: After collecting enough data points, the script can generate the optimal distance-to-focus mapping.

## Calibration Tips

1. **Collect Diverse Data Points**: Try to collect data points at various distances, especially at:
   - Very close range (20-30cm)
   - Close range (40-60cm)
   - Medium range (70-100cm)
   - Far range (110-150cm)

2. **Consistent Lighting**: Maintain consistent lighting conditions during calibration.

3. **Face Position**: Keep your face centered in the frame during calibration.

4. **Fine Adjustments**: Use the fine adjustment mode ('f' key) for precise focus tuning.

5. **Verify Results**: After calibration, test the generated focus mapping at various distances.

## Understanding the Output

The calibration script produces several outputs:

1. **JSON Data File**: `focus_calibration.json` contains all calibration points.

2. **Calibration Curve**: `focus_calibration_curve.png` shows the relationship between distance and focus.

3. **Code Snippet**: `distance_focus_map_code.txt` contains the code to update in your distance_sensor.py file.

## Applying the Calibration

After calibration, copy the generated `distance_focus_map` from the code snippet into the `distance_sensor.py` file to update the focus mapping.

## Troubleshooting

- **Distance Sensor Issues**: Ensure the HC-SR04 sensor is properly connected and not obstructed.
- **Camera Issues**: Make sure the camera is properly connected and recognized by the system.
- **Focus Problems**: If focus adjustment doesn't seem to work, restart the script and try again. 