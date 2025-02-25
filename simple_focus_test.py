#!/usr/bin/env python3
import time
from picamera2 import Picamera2, Preview
from libcamera import Transform
import os

class SimpleFocusTester:
    """
    Simple tool to test different focus values for the Arducam 64MP camera
    """
    
    def __init__(self):
        # Set up Qt environment variables
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/usr/lib/aarch64-linux-gnu/qt5/plugins/platforms"
        os.environ["QT_QPA_PLATFORM"] = "xcb"
        
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
        self.current_focus = 10.0  # Start in the middle
        
        # Zoom state
        self.current_zoom_level = 1  # 1 = normal, 2 = 2x zoom, 3 = 3x zoom
        self.max_zoom_level = 3
        self.zoom_center = (550, 550)  # Center of the frame (1100x1100)
    
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
    
    def set_focus(self, focus_value):
        """Set camera focus"""
        # Ensure focus is within valid range
        focus_value = max(min(focus_value, self.max_focus), self.min_focus)
        self.picam2.set_controls({"LensPosition": focus_value})
        self.current_focus = focus_value
        print(f"Focus set to: {focus_value:.2f}")
        return focus_value
    
    def run_test(self):
        """Run the focus test"""
        try:
            self.start_camera()
            
            print("\n=== Simple Focus Test ===")
            print("Use the following keys to adjust focus:")
            print("  + or = : Increase focus (move closer)")
            print("  - or _ : Decrease focus (move farther)")
            print("  f     : Fine adjustment mode (0.05 steps)")
            print("  c     : Coarse adjustment mode (0.2 steps)")
            print("  n     : Normal adjustment mode (0.1 steps)")
            print("  z     : Toggle zoom level (1x, 2x, 3x)")
            print("  d     : Display current focus value")
            print("  q     : Quit")
            
            step_size = 0.1
            
            # Set initial focus
            self.set_focus(self.current_focus)
            
            while True:
                key = input("Command: ").strip().lower()
                
                if key in ['+', '=']:
                    self.set_focus(self.current_focus + step_size)
                elif key in ['-', '_']:
                    self.set_focus(self.current_focus - step_size)
                elif key == 'f':
                    step_size = 0.05
                    print("Fine adjustment mode (0.05 steps)")
                elif key == 'c':
                    step_size = 0.2
                    print("Coarse adjustment mode (0.2 steps)")
                elif key == 'n':
                    step_size = 0.1
                    print("Normal adjustment mode (0.1 steps)")
                elif key == 'z':
                    # Cycle through zoom levels
                    next_zoom = (self.current_zoom_level % self.max_zoom_level) + 1
                    self.set_zoom(next_zoom)
                elif key == 'd':
                    print(f"Current focus: {self.current_focus:.2f}, Zoom: {self.current_zoom_level}x")
                elif key == 'q':
                    print("Quitting focus test")
                    break
                else:
                    print("Unknown command. Type '+', '-', 'f', 'c', 'n', 'z', 'd', or 'q'")
        
        finally:
            # Reset zoom before exiting
            try:
                self.set_zoom(1)
            except:
                pass
            self.stop_camera()

if __name__ == "__main__":
    try:
        tester = SimpleFocusTester()
        tester.run_test()
    except KeyboardInterrupt:
        print("\nFocus test interrupted by user")
    except Exception as e:
        print(f"Error during focus test: {e}")
        import traceback
        traceback.print_exc()  # Print full traceback for debugging
    finally:
        print("Focus test ended") 