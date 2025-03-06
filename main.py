import os
import time
import signal
import threading
import sys
from core.camera_manager import CameraManager, ZoomLevel
from core.face_processor import CameraFaceProcessor
from core.display_processor import DisplayProcessor
from core.voice_controller import VoiceController, VoiceCommand
from core.distance_sensor import DistanceSensor
from core.async_helper import AsyncHelper
from core.scaler_crop_controller import ScalerCropController

# Set up Qt environment variables
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/usr/lib/aarch64-linux-gnu/qt5/plugins/platforms"
os.environ["QT_QPA_PLATFORM"] = "xcb"

# Global flag for shutdown
shutdown_requested = False
force_shutdown_timer = None

def signal_handler(sig, frame):
    """Handle Ctrl+C and other termination signals"""
    global shutdown_requested, force_shutdown_timer
    
    if not shutdown_requested:
        print("\nShutdown requested. Press Ctrl+C again to force immediate exit.")
        shutdown_requested = True
        
        # Set a timer for force shutdown if normal shutdown takes too long
        force_shutdown_timer = threading.Timer(5.0, force_shutdown)
        force_shutdown_timer.daemon = True
        force_shutdown_timer.start()
    else:
        # Second Ctrl+C, force immediate exit
        force_shutdown()

def force_shutdown():
    """Force immediate shutdown"""
    print("\nForce shutdown initiated. Exiting immediately.")
    os._exit(1)  # Force exit without cleanup

def main():
    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("Initializing Mirror System...")
    
    # Initialize shared components
    async_helper = AsyncHelper(max_workers=6)
    
    # Initialize core components
    camera = CameraManager()
    scaler_crop_controller = ScalerCropController(camera)
    # Attach scaler_crop_controller to camera_manager for coordination
    camera.scaler_crop_controller = scaler_crop_controller
    face_processor = CameraFaceProcessor(camera, scaler_crop_controller)
    display_processor = DisplayProcessor(camera, face_processor)
    
    # Initialize distance sensor (GPIO pins 23 and 24)
    try:
        distance_sensor = DistanceSensor(
            trigger_pin=23,
            echo_pin=24,
            async_helper=async_helper
        )
        # Configure distance sensor
        distance_sensor.focus_smoothing_enabled = True  # Enable focus smoothing
        distance_sensor.sample_interval = 0.2  # 5Hz sampling rate (reduced from 10Hz)
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
            VoiceCommand.FOCUS: lambda: camera.set_focus(distance_sensor.get_current_focus() if distance_sensor_initialized else 10.0)
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
        
        print("Starting ScalerCrop controller...")
        scaler_crop_controller.start()
        
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
        
        print("\nSystem ready! Press Ctrl+C to exit.")
        
        # Main loop
        while not shutdown_requested:
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nShutdown requested...")
    except Exception as e:
        print(f"\nError in main loop: {e}")
    finally:
        # Cancel force shutdown timer if it's running
        if force_shutdown_timer and force_shutdown_timer.is_alive():
            force_shutdown_timer.cancel()
        
        # Ensure clean shutdown of all components
        print("Cleaning up resources...")
        
        # Shutdown components in reverse order of initialization
        if voice_controller_initialized:
            try:
                print("Stopping voice controller...")
                voice_controller.stop()
            except Exception as e:
                print(f"Error stopping voice controller: {e}")
        
        if distance_sensor_initialized:
            try:
                print("Stopping distance sensor...")
                distance_sensor.stop()
            except Exception as e:
                print(f"Error stopping distance sensor: {e}")
        
        try:
            print("Stopping display processor...")
            display_processor.stop()
        except Exception as e:
            print(f"Error stopping display processor: {e}")
        
        try:
            print("Stopping face processor...")
            face_processor.stop()
        except Exception as e:
            print(f"Error stopping face processor: {e}")
        
        try:
            print("Stopping camera...")
            camera.stop()
        except Exception as e:
            print(f"Error stopping camera: {e}")
        
        try:
            print("Stopping async helper...")
            async_helper.shutdown(wait=False)  # Don't wait for tasks to complete during emergency shutdown
        except Exception as e:
            print(f"Error stopping async helper: {e}")
        
        print("Shutdown complete")

if __name__ == "__main__":
    main() 