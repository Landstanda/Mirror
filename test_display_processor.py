import os
import time
from core.camera_manager import CameraManager, ZoomLevel
from core.face_processor import CameraFaceProcessor
from core.display_processor import DisplayProcessor

# Set up environment variables
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
os.environ["MEDIAPIPE_USE_GPU"] = "true"
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/usr/lib/aarch64-linux-gnu/qt5/plugins/platforms"
os.environ["QT_QPA_PLATFORM"] = "xcb"

# Check if DISPLAY is set
display = os.environ.get('DISPLAY')
if not display:
    print("WARNING: DISPLAY environment variable not set")
    os.environ['DISPLAY'] = ':0'
else:
    print(f"DISPLAY is set to: {display}")

def main():
    # Initialize components
    print("Initializing camera...")
    camera = CameraManager()
    
    print("Initializing face processor...")
    face_processor = CameraFaceProcessor(camera)
    
    print("Initializing display processor...")
    display_processor = DisplayProcessor(camera, face_processor)
    
    try:
        # Start all components
        print("Starting camera...")
        camera.start()
        
        print("Starting face processor...")
        face_processor.start()
        
        print("Starting display processor...")
        display_processor.start()
        
        # Give everything time to initialize
        time.sleep(2)
        
        print("\nDisplay Processor Test")
        print("--------------------")
        print("Press these keys to control zoom:")
        print("1 - Zoom to eyes")
        print("2 - Zoom to lips")
        print("3 - Zoom to face")
        print("4 - Wide view")
        print("Press Ctrl+C to quit\n")
        
        # Main control loop
        while True:
            key = input().strip()
            if key == "1":
                display_processor.set_zoom_level(ZoomLevel.EYES)
            elif key == "2":
                display_processor.set_zoom_level(ZoomLevel.LIPS)
            elif key == "3":
                display_processor.set_zoom_level(ZoomLevel.FACE)
            elif key == "4":
                display_processor.set_zoom_level(ZoomLevel.WIDE)
                
    except KeyboardInterrupt:
        print("\nStopping test...")
    finally:
        # Clean up
        print("Stopping all components...")
        display_processor.stop()
        face_processor.stop()
        camera.stop()

if __name__ == "__main__":
    main() 