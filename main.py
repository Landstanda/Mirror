import os
import time
from core.camera_manager import CameraManager, ZoomLevel
from core.face_processor import CameraFaceProcessor
from core.display_processor import DisplayProcessor
from core.voice_controller import VoiceController, VoiceCommand
from core.distance_sensor import DistanceSensor
from core.async_helper import AsyncHelper

# Set up Qt environment variables
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/usr/lib/aarch64-linux-gnu/qt5/plugins/platforms"
os.environ["QT_QPA_PLATFORM"] = "xcb"

def main():
    print("Initializing Mirror System...")
    
    # Initialize shared components
    async_helper = AsyncHelper(max_workers=6)  # Increased workers for all components
    
    # Initialize core components
    camera = CameraManager()
    face_processor = CameraFaceProcessor(camera)
    display_processor = DisplayProcessor(camera, face_processor)
    
    # Initialize distance sensor (GPIO pins 23 and 24)
    try:
        distance_sensor = DistanceSensor(
            trigger_pin=23,
            echo_pin=24,
            async_helper=async_helper
        )
        distance_sensor_initialized = True
        print("Distance sensor initialized successfully")
    except Exception as e:
        print(f"Warning: Distance sensor initialization failed: {e}")
        print("System will continue without distance sensing")
        distance_sensor_initialized = False
        distance_sensor = None
    
    # Define voice command callbacks
    def create_voice_callbacks(camera, display_processor):
        return {
            VoiceCommand.EYES: lambda: display_processor.set_zoom_level(ZoomLevel.EYES),
            VoiceCommand.LIPS: lambda: display_processor.set_zoom_level(ZoomLevel.LIPS),
            VoiceCommand.FACE: lambda: display_processor.set_zoom_level(ZoomLevel.FACE),
            VoiceCommand.ZOOM_OUT: lambda: display_processor.set_zoom_level(ZoomLevel.WIDE),
            VoiceCommand.FOCUS: lambda: camera.set_focus(10.0)  # Default focus for now
        }
    
    # Initialize voice controller with callbacks
    try:
        voice_callbacks = create_voice_callbacks(camera, display_processor)
        voice_controller = VoiceController(voice_callbacks, async_helper)
        voice_controller_initialized = True
        print("Voice controller initialized successfully")
    except Exception as e:
        print(f"Warning: Voice controller initialization failed: {e}")
        print("System will continue without voice control")
        voice_controller_initialized = False
        voice_controller = None
    
    try:
        # Start components in sequence
        print("Starting async helper...")
        async_helper.start()
        
        print("Starting camera...")
        camera.start()
        time.sleep(1)  # Wait for camera initialization
        
        print("Starting face processor...")
        face_processor.start()
        
        print("Starting display processor...")
        display_processor.start()
        
        # Start distance sensor if initialized
        if distance_sensor_initialized:
            print("Starting distance sensor...")
            # Set up focus update callback
            def focus_callback(focus_value):
                if focus_value is not None:
                    camera.set_focus(focus_value)
            distance_sensor._update_focus = focus_callback
            
            # Start the sensor
            distance_sensor.start()
            print("Distance sensor started with focus callback")
        
        # Start voice controller if initialized
        if voice_controller_initialized:
            print("Starting voice controller...")
            voice_controller.start()
        
        print("\nSystem running. Press Ctrl+C to quit.")
        
        # Main loop - keep the program running
        while True:
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Clean up in reverse order
        if voice_controller_initialized:
            print("Stopping voice controller...")
            voice_controller.stop()
            
        if distance_sensor_initialized:
            print("Stopping distance sensor...")
            distance_sensor.stop()
        
        print("Stopping display processor...")
        display_processor.stop()
        
        print("Stopping face processor...")
        face_processor.stop()
        
        print("Stopping camera...")
        camera.stop()
        
        print("Stopping async helper...")
        async_helper.stop()
        
        print("Shutdown complete")

if __name__ == "__main__":
    main() 