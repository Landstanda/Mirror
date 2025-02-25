#!/usr/bin/env python3
import time
import os
from picamera2 import Picamera2, Preview
from libcamera import Transform

# Set up Qt environment variables
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/usr/lib/aarch64-linux-gnu/qt5/plugins/platforms"
os.environ["QT_QPA_PLATFORM"] = "xcb"

def test_camera_preview():
    print("Initializing camera...")
    picam2 = Picamera2()
    
    # Create video configuration
    video_config = picam2.create_video_configuration(
        main={"size": (1100, 1100), "format": "RGB888"},
        transform=Transform(hflip=False, vflip=True)
    )
    
    print("Configuring camera...")
    picam2.configure(video_config)
    
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
    
    print("Camera preview should be visible now.")
    print("Press Ctrl+C to exit.")
    
    try:
        # Keep the script running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping camera...")
    finally:
        try:
            picam2.stop_preview()
        except:
            pass
        picam2.stop()
        print("Camera stopped")

if __name__ == "__main__":
    try:
        test_camera_preview()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc() 