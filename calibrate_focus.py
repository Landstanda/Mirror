#!/usr/bin/env python3
import time
import json
import os
import numpy as np
import matplotlib.pyplot as plt
from picamera2 import Picamera2, Preview
from libcamera import Transform
from gpiozero import DistanceSensor as GPIOZeroDistance

# Tell gpiozero to use lgpio by default
os.environ['GPIOZERO_PIN_FACTORY'] = 'lgpio'

# Set up Qt environment variables
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/usr/lib/aarch64-linux-gnu/qt5/plugins/platforms"
os.environ["QT_QPA_PLATFORM"] = "xcb"

class FocusCalibrator:
    """
    Interactive tool to calibrate the distance-to-focus mapping
    for the Arducam 64MP Hawkeyes camera.
    """
    
    def __init__(self, trigger_pin=23, echo_pin=24):
        # Initialize camera
        print("Initializing camera...")
        self.picam2 = Picamera2()
        
        # Camera sensor constants (for Arducam 64MP)
        self.SENSOR_WIDTH = 9152   # Full sensor width
        self.SENSOR_HEIGHT = 6944  # Full sensor height
        
        # Create video configuration optimized for preview
        video_config = self.picam2.create_video_configuration(
            main={"size": (1100, 1100), "format": "RGB888"},
            transform=Transform(hflip=False, vflip=True),
            buffer_count=2,
            queue=True
        )
        
        print("Setting camera configuration...")
        self.picam2.configure(video_config)
        
        # Set manual focus mode
        self.picam2.set_controls({
            "AfMode": 0,          # Manual focus
            "LensPosition": 10.0,  # Initial focus position
        })
        
        # Focus range for Arducam 64MP
        self.min_focus = 8.0
        self.max_focus = 12.5
        self.focus_step = 0.1
        
        # Zoom state
        self.current_zoom_level = 1  # 1 = normal, 2 = 2x zoom, 3 = 3x zoom
        self.max_zoom_level = 3
        self.zoom_center = (550, 550)  # Center of the frame (1100x1100)
        
        # Initialize distance sensor
        print(f"Initializing distance sensor on pins: Trigger={trigger_pin}, Echo={echo_pin}")
        try:
            self.sensor = GPIOZeroDistance(
                echo=echo_pin,
                trigger=trigger_pin,
                max_distance=2.0  # Maximum distance in meters
            )
            print("Distance sensor initialized successfully")
        except Exception as e:
            print(f"Failed to initialize distance sensor: {e}")
            raise
        
        # Calibration data storage
        self.calibration_data = []
        self.output_file = "focus_calibration.json"
        
        # Load existing calibration if available
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, 'r') as f:
                    self.calibration_data = json.load(f)
                print(f"Loaded {len(self.calibration_data)} existing calibration points")
            except Exception as e:
                print(f"Error loading existing calibration: {e}")
    
    def start_camera(self):
        """Start the camera preview"""
        print("Starting camera preview...")
        try:
            # Start preview with QT
            self.picam2.start_preview(Preview.QT, x=10, y=10, width=1100, height=1100)
            print("Preview started")
            time.sleep(1)  # Give preview time to initialize
            
            # Start camera
            self.picam2.start()
            print("Camera started")
            time.sleep(1)  # Give camera time to stabilize
            
            # Apply initial zoom (no zoom)
            self.set_zoom(self.current_zoom_level)
        except Exception as e:
            print(f"Error starting preview: {e}")
            try:
                print("Trying alternative preview method...")
                self.picam2.start_preview("qt")
                self.picam2.start()
                print("Camera started with alternative preview")
            except Exception as e2:
                print(f"Alternative preview failed: {e2}")
                print("Starting camera without preview...")
                self.picam2.start()
                print("Camera started without preview")
    
    def stop_camera(self):
        """Stop the camera"""
        print("Stopping camera...")
        try:
            self.picam2.stop_preview()
        except:
            pass
        self.picam2.stop()
        print("Camera stopped")
    
    def set_zoom(self, zoom_level):
        """Set zoom level (1-3)"""
        self.current_zoom_level = max(1, min(self.max_zoom_level, zoom_level))
        
        # Calculate crop size based on zoom level
        if self.current_zoom_level == 1:
            # No zoom - reset ScalerCrop
            self.picam2.set_controls({"ScalerCrop": (0, 0, self.SENSOR_WIDTH, self.SENSOR_HEIGHT)})
            print("Zoom level: 1x (no zoom)")
            return
        
        # Calculate crop size and position
        zoom_factor = self.current_zoom_level
        
        # Calculate crop size (smaller = more zoom)
        crop_size = min(self.SENSOR_WIDTH, self.SENSOR_HEIGHT) // zoom_factor
        
        # Calculate center point in sensor coordinates
        center_x_ratio = self.zoom_center[0] / 1100  # Convert from preview to ratio
        center_y_ratio = self.zoom_center[1] / 1100
        
        sensor_center_x = int(self.SENSOR_WIDTH * center_x_ratio)
        sensor_center_y = int(self.SENSOR_HEIGHT * center_y_ratio)
        
        # Calculate crop coordinates
        crop_x = sensor_center_x - (crop_size // 2)
        crop_y = sensor_center_y - (crop_size // 2)
        
        # Ensure crop is within sensor bounds
        crop_x = max(0, min(self.SENSOR_WIDTH - crop_size, crop_x))
        crop_y = max(0, min(self.SENSOR_HEIGHT - crop_size, crop_y))
        
        # Apply crop
        self.picam2.set_controls({"ScalerCrop": (crop_x, crop_y, crop_size, crop_size)})
        print(f"Zoom level: {self.current_zoom_level}x")
    
    def measure_distance(self, num_samples=5):
        """
        Measure distance using ultrasonic sensor
        Returns: average distance in centimeters
        """
        distances = []
        print("Measuring distance...")
        
        for _ in range(num_samples):
            try:
                # Get distance in meters and convert to cm
                distance_cm = self.sensor.distance * 100
                distances.append(distance_cm)
                time.sleep(0.1)  # Short delay between measurements
            except Exception as e:
                print(f"Error in distance measurement: {e}")
        
        # Filter out any zero readings
        valid_distances = [d for d in distances if d > 0]
        
        if not valid_distances:
            print("Warning: No valid distance measurements")
            return None
        
        # Calculate average distance
        avg_distance = sum(valid_distances) / len(valid_distances)
        print(f"Average distance: {avg_distance:.1f} cm")
        return avg_distance
    
    def set_focus(self, focus_value):
        """Set camera focus"""
        # Ensure focus is within valid range
        focus_value = max(min(focus_value, self.max_focus), self.min_focus)
        self.picam2.set_controls({"LensPosition": focus_value})
        print(f"Focus set to: {focus_value:.2f}")
        return focus_value
    
    def interactive_focus_adjustment(self, initial_focus=10.0):
        """
        Interactive focus adjustment using keyboard input
        Returns: the final focus value
        """
        current_focus = initial_focus
        self.set_focus(current_focus)
        
        print("\n=== Interactive Focus Adjustment ===")
        print("Use the following keys to adjust focus:")
        print("  + or = : Increase focus (move closer)")
        print("  - or _ : Decrease focus (move farther)")
        print("  f     : Fine adjustment mode (smaller steps)")
        print("  c     : Coarse adjustment mode (larger steps)")
        print("  z     : Toggle zoom level (1x, 2x, 3x)")
        print("  Enter : Accept current focus value (just press Enter key)")
        print("  q     : Quit without saving")
        
        step_size = 0.1
        
        while True:
            print(f"Current focus: {current_focus:.2f} (step size: {step_size:.2f}, zoom: {self.current_zoom_level}x)")
            key = input("Command: ").strip().lower()
            
            if key in ['+', '=']:
                current_focus = min(current_focus + step_size, self.max_focus)
                self.set_focus(current_focus)
            elif key in ['-', '_']:
                current_focus = max(current_focus - step_size, self.min_focus)
                self.set_focus(current_focus)
            elif key == 'f':
                step_size = 0.05
                print("Fine adjustment mode (0.05 steps)")
            elif key == 'c':
                step_size = 0.2
                print("Coarse adjustment mode (0.2 steps)")
            elif key == 'z':
                # Cycle through zoom levels
                next_zoom = (self.current_zoom_level % self.max_zoom_level) + 1
                self.set_zoom(next_zoom)
            elif key == '':  # Enter key
                print(f"Focus value {current_focus:.2f} accepted")
                return current_focus
            elif key == 'q':
                print("Quitting focus adjustment")
                return None
    
    def add_calibration_point(self):
        """Add a new calibration point"""
        # Measure distance
        distance = self.measure_distance()
        if distance is None:
            print("Could not get valid distance measurement. Aborting.")
            return False
        
        # Find existing calibration point at similar distance
        for point in self.calibration_data:
            if abs(point["distance"] - distance) < 5.0:  # Within 5cm
                print(f"Warning: Similar distance ({point['distance']:.1f} cm) already calibrated")
                replace = input("Replace existing point? (y/n): ").strip().lower()
                if replace != 'y':
                    return False
                self.calibration_data.remove(point)
                break
        
        # Start with a reasonable initial focus based on existing data or default
        initial_focus = 10.0  # Default starting point
        
        # If we have existing data, estimate a good starting focus
        if self.calibration_data:
            # Sort by distance
            sorted_data = sorted(self.calibration_data, key=lambda x: x["distance"])
            
            # Find surrounding points
            lower_point = None
            upper_point = None
            
            for point in sorted_data:
                if point["distance"] <= distance:
                    lower_point = point
                if point["distance"] >= distance and upper_point is None:
                    upper_point = point
            
            # Interpolate to get initial focus
            if lower_point and upper_point:
                d1, f1 = lower_point["distance"], lower_point["focus"]
                d2, f2 = upper_point["distance"], upper_point["focus"]
                initial_focus = f1 + (f2 - f1) * (distance - d1) / (d2 - d1)
            elif lower_point:
                initial_focus = lower_point["focus"]
            elif upper_point:
                initial_focus = upper_point["focus"]
        
        # Set zoom to 2x for better focus visibility
        self.set_zoom(2)
        
        # Interactive focus adjustment
        print(f"\nAdjusting focus for distance: {distance:.1f} cm")
        print("Please adjust the focus until the image is perfectly sharp")
        print("Use the 'z' key to toggle zoom levels for better focus visibility")
        focus = self.interactive_focus_adjustment(initial_focus)
        
        # Reset zoom when done
        self.set_zoom(1)
        
        if focus is None:
            print("Focus adjustment cancelled")
            return False
        
        # Add to calibration data
        new_point = {
            "distance": distance,
            "focus": focus,
            "timestamp": time.time()
        }
        self.calibration_data.append(new_point)
        
        # Sort calibration data by distance
        self.calibration_data = sorted(self.calibration_data, key=lambda x: x["distance"])
        
        # Save calibration data
        self.save_calibration()
        
        print(f"Calibration point added: Distance={distance:.1f}cm, Focus={focus:.2f}")
        return True
    
    def save_calibration(self):
        """Save calibration data to file"""
        try:
            with open(self.output_file, 'w') as f:
                json.dump(self.calibration_data, f, indent=2)
            print(f"Calibration data saved to {self.output_file}")
            return True
        except Exception as e:
            print(f"Error saving calibration data: {e}")
            return False
    
    def plot_calibration(self):
        """Plot the calibration curve"""
        if not self.calibration_data:
            print("No calibration data to plot")
            return
        
        # Extract data points
        distances = [point["distance"] for point in self.calibration_data]
        focus_values = [point["focus"] for point in self.calibration_data]
        
        # Create figure
        plt.figure(figsize=(10, 6))
        
        # Plot calibration points
        plt.scatter(distances, focus_values, color='blue', s=50, label='Calibration Points')
        
        # If we have enough points, fit a curve
        if len(distances) >= 3:
            # Sort points by distance
            sorted_indices = np.argsort(distances)
            sorted_distances = np.array(distances)[sorted_indices]
            sorted_focus = np.array(focus_values)[sorted_indices]
            
            # Generate smooth curve for plotting
            x_smooth = np.linspace(min(distances), max(distances), 100)
            
            # Try different curve fits
            
            # 1. Polynomial fit
            poly_degree = min(3, len(distances) - 1)  # Avoid overfitting
            poly_coeffs = np.polyfit(sorted_distances, sorted_focus, poly_degree)
            poly_fit = np.polyval(poly_coeffs, x_smooth)
            plt.plot(x_smooth, poly_fit, 'r-', label=f'Polynomial (degree {poly_degree})')
            
            # 2. Exponential fit if all focus values are positive
            if all(f > 0 for f in focus_values):
                try:
                    # log(y) = a*x + b => y = exp(b) * exp(a*x)
                    exp_coeffs = np.polyfit(sorted_distances, np.log(sorted_focus), 1)
                    exp_fit = np.exp(exp_coeffs[1]) * np.exp(exp_coeffs[0] * x_smooth)
                    plt.plot(x_smooth, exp_fit, 'g--', label='Exponential')
                except:
                    pass  # Skip if fit fails
            
            # Print the polynomial equation
            eq_terms = []
            for i, coef in enumerate(poly_coeffs):
                power = poly_degree - i
                if power > 1:
                    eq_terms.append(f"{coef:.6f}*x^{power}")
                elif power == 1:
                    eq_terms.append(f"{coef:.6f}*x")
                else:
                    eq_terms.append(f"{coef:.6f}")
            
            poly_eq = " + ".join(eq_terms)
            print(f"Polynomial equation: f(x) = {poly_eq}")
            print(f"Polynomial coefficients: {poly_coeffs.tolist()}")
        
        # Set labels and title
        plt.xlabel('Distance (cm)')
        plt.ylabel('Focus Value')
        plt.title('Distance to Focus Calibration Curve')
        plt.grid(True)
        plt.legend()
        
        # Save plot
        plt.savefig('focus_calibration_curve.png')
        print("Calibration curve saved to focus_calibration_curve.png")
        
        # Show plot
        plt.show()
    
    def generate_code(self):
        """Generate code for the distance_focus_map"""
        if not self.calibration_data or len(self.calibration_data) < 2:
            print("Not enough calibration data to generate code")
            return
        
        # Extract data points
        distances = [point["distance"] for point in self.calibration_data]
        focus_values = [point["focus"] for point in self.calibration_data]
        
        # Generate code
        code = "self.distance_focus_map = {\n"
        for i, (distance, focus) in enumerate(zip(distances, focus_values)):
            comment = ""
            if i == 0:
                comment = "  # Closest focus"
            elif i == len(distances) - 1:
                comment = "  # Farthest focus"
            
            code += f"    {distance:.1f}: {focus:.2f},{comment}\n"
        code += "}"
        
        print("\n=== Generated Code for distance_focus_map ===")
        print(code)
        print("==============================================")
        
        # Save to file
        with open('distance_focus_map_code.txt', 'w') as f:
            f.write(code)
        print("Code saved to distance_focus_map_code.txt")
    
    def run_calibration(self):
        """Run the calibration process"""
        try:
            self.start_camera()
            
            while True:
                print("\n=== Focus Calibration Menu ===")
                print("1. Add calibration point")
                print("2. View current calibration data")
                print("3. Plot calibration curve")
                print("4. Generate code for distance_focus_map")
                print("5. Toggle zoom (current: {}x)".format(self.current_zoom_level))
                print("6. Exit")
                
                choice = input("Enter choice (1-6): ").strip()
                
                if choice == '1':
                    self.add_calibration_point()
                elif choice == '2':
                    if not self.calibration_data:
                        print("No calibration data available")
                    else:
                        print("\nCurrent Calibration Data:")
                        for i, point in enumerate(self.calibration_data):
                            print(f"{i+1}. Distance: {point['distance']:.1f} cm, Focus: {point['focus']:.2f}")
                elif choice == '3':
                    self.plot_calibration()
                elif choice == '4':
                    self.generate_code()
                elif choice == '5':
                    next_zoom = (self.current_zoom_level % self.max_zoom_level) + 1
                    self.set_zoom(next_zoom)
                elif choice == '6':
                    print("Exiting calibration")
                    break
                else:
                    print("Invalid choice. Please enter a number between 1 and 6.")
        
        finally:
            # Reset zoom before exiting
            try:
                self.set_zoom(1)
            except:
                pass
            
            self.stop_camera()
            try:
                self.sensor.close()
            except:
                pass

if __name__ == "__main__":
    try:
        calibrator = FocusCalibrator()
        calibrator.run_calibration()
    except KeyboardInterrupt:
        print("\nCalibration interrupted by user")
    except Exception as e:
        print(f"Error during calibration: {e}")
        import traceback
        traceback.print_exc()  # Print full traceback for debugging
    finally:
        print("Calibration process ended") 