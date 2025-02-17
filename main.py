import os
from core.camera_manager import CameraManager, ZoomLevel
import time

# Set up Qt environment variables
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/usr/lib/aarch64-linux-gnu/qt5/plugins/platforms"
os.environ["QT_QPA_PLATFORM"] = "xcb"

def main():
    # Initialize the camera manager
    camera = CameraManager()
    
    try:
        # Start the camera
        print("Starting camera...")
        camera.start()
        
        # Give camera time to initialize
        time.sleep(2)
        
        print("Camera started. Press Ctrl+C to quit.")
        
        # Main loop - just keep the program running
        while True:
            time.sleep(0.1)
                
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        # Clean up
        print("Stopping camera...")
        camera.stop()

if __name__ == "__main__":
    main() 