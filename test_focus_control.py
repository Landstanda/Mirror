#!/usr/bin/env python3
import time
import os
from picamera2 import Picamera2, Preview
from libcamera import Transform
from core.distance_sensor import DistanceSensor

# Set up Qt environment variables
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/usr/lib/aarch64-linux-gnu/qt5/plugins/platforms"
os.environ["QT_QPA_PLATFORM"] = "xcb"

def test_focus_control():
    """Test the distance sensor controlling the camera focus"""
    print("Initializing camera...")
    picam2 = Picamera2()
    
    # Create video configuration
    video_config = picam2.create_video_configuration(
        main={"size": (1100, 1100), "format": "RGB888"},
        transform=Transform(hflip=False, vflip=True)
    )
    
    print("Configuring camera...")
    picam2.configure(video_config)
    
    # Set manual focus mode
    picam2.set_controls({
        "AfMode": 0,          # Manual focus
        "LensPosition": 10.0,  # Initial focus position
    })
    
    print("Starting preview...")
    try:
        # Method 1: Using Preview.QT
        picam2.start_preview(Preview.QT, x=10, y=10, width=1100, height=1100)
        print("Preview started with Preview.QT")
    except Exception as e:
        print(f"Error starting preview with Preview.QT: {e}")
        try:
            # Method 2: Using string "qt"
            picam2.start_preview("qt")
            print("Preview started with string 'qt'")
        except Exception as e2:
            print(f"Error starting preview with string 'qt': {e2}")
            print("Both preview methods failed")
    
    print("Starting camera...")
    picam2.start()
    print("Camera started")
    
    # Initialize distance sensor
    print("Initializing distance sensor...")
    distance_sensor = DistanceSensor(trigger_pin=23, echo_pin=24)
    distance_sensor.focus_smoothing_enabled = True
    distance_sensor.sample_interval = 0.1  # 10Hz
    
    # Start distance sensor
    print("Starting distance sensor...")
    distance_sensor.start()
    
    print("\nDistance sensor is now controlling camera focus.")
    print("Move closer to or farther from the camera to see focus changes.")
    print("Press Ctrl+C to exit.")
    
    try:
        # Main loop - update focus based on distance sensor
        last_print_time = 0
        print_interval = 0.5  # Only print every 0.5 seconds to reduce console spam
        
        while True:
            current_time = time.monotonic()
            
            # Get current distance and focus
            distance = distance_sensor.get_current_distance()
            focus = distance_sensor.get_current_focus()
            
            # Update camera focus
            picam2.set_controls({"LensPosition": focus})
            
            # Print current values (but not too often)
            if current_time - last_print_time >= print_interval:
                print(f"Distance: {distance:.1f}cm, Focus: {focus:.2f}", end="\r", flush=True)
                last_print_time = current_time
            
            # Short delay
            time.sleep(0.05)  # Reduced from 0.1 to be more responsive but not print as often
            
    except KeyboardInterrupt:
        print("\n\nStopping test...")
    finally:
        # Clean up
        print("Stopping distance sensor...")
        distance_sensor.stop()
        
        print("Stopping camera...")
        try:
            picam2.stop_preview()
        except:
            pass
        picam2.stop()
        
        print("Test complete")

if __name__ == "__main__":
    try:
        test_focus_control()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc() 