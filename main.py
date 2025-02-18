import os
import time
from core.camera_manager import CameraManager
from core.face_processor import CameraFaceProcessor
from core.display_processor import DisplayProcessor

# Set up Qt environment variables
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/usr/lib/aarch64-linux-gnu/qt5/plugins/platforms"
os.environ["QT_QPA_PLATFORM"] = "xcb"

def main():
    print("Initializing Mirror System...")
    
    # Initialize components
    camera = CameraManager()
    face_processor = CameraFaceProcessor(camera)
    display_processor = DisplayProcessor(camera, face_processor)
    
    try:
        # Start components in sequence
        print("Starting camera...")
        camera.start()
        time.sleep(1)  # Wait for camera initialization
        
        print("Starting face processor...")
        face_processor.start()
        
        print("Starting display processor...")
        display_processor.start()
        
        print("\nSystem running. Press Ctrl+C to quit.")
        
        # Main loop - keep the program running
        while True:
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Clean up in reverse order
        print("Stopping display processor...")
        display_processor.stop()
        
        print("Stopping face processor...")
        face_processor.stop()
        
        print("Stopping camera...")
        camera.stop()
        
        print("Shutdown complete")

if __name__ == "__main__":
    main() 