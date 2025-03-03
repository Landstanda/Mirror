from picamera2 import Picamera2
import time
import json
from libcamera import controls as libcamera_controls

def format_sensor_mode(mode):
    """Format sensor mode information into a readable string"""
    info = {}
    try:
        # Handle mode if it's a dictionary
        if isinstance(mode, dict):
            info["size"] = f"{mode.get('size', [0, 0])[0]}x{mode.get('size', [0, 0])[1]}"
            info["format"] = str(mode.get('format', 'unknown'))
            if 'fps' in mode:
                info["fps"] = mode['fps']
        else:
            # Handle mode if it's an object
            info["size"] = f"{mode.size[0]}x{mode.size[1]}" if hasattr(mode, 'size') else "unknown"
            info["format"] = str(mode.format) if hasattr(mode, 'format') else "unknown"
            if hasattr(mode, 'fps'):
                info["fps"] = mode.fps
        return info
    except Exception as e:
        return f"Error formatting mode: {str(e)}"

def calculate_fov_info(properties, current_config):
    """Calculate FOV and resolution information"""
    try:
        sensor_width, sensor_height = properties['PixelArraySize']
        current_crop = properties.get('ScalerCrop', [[0,0,0,0]])[0]
        crop_x, crop_y, crop_w, crop_h = current_crop
        
        print("\n=== FOV and Resolution Analysis ===")
        print(f"Full Sensor Resolution: {sensor_width}x{sensor_height}")
        print(f"Current Crop Window: {crop_w}x{crop_h} at position ({crop_x}, {crop_y})")
        
        # Calculate percentage of sensor being used
        width_percentage = (crop_w / sensor_width) * 100
        height_percentage = (crop_h / sensor_height) * 100
        print(f"\nSensor Usage:")
        print(f"Width: {width_percentage:.1f}% of sensor width")
        print(f"Height: {height_percentage:.1f}% of sensor height")
        print(f"Area: {(width_percentage * height_percentage / 100):.1f}% of sensor area")
        
        # Calculate scaling ratio
        if 'main' in current_config and 'size' in current_config['main']:
            output_w, output_h = current_config['main']['size']
            print(f"\nScaling:")
            print(f"Crop region: {crop_w}x{crop_h}")
            print(f"Output size: {output_w}x{output_h}")
            print(f"Scaling ratio: {crop_w/output_w:.2f}x{crop_h/output_h:.2f}")
    except Exception as e:
        print(f"Error in FOV calculation: {str(e)}")

def print_camera_info():
    picam2 = Picamera2()
    
    try:
        # Get camera information
        print("\n=== Camera Hardware Information ===")
        properties = picam2.camera_properties
        print(json.dumps(properties, indent=2))
        
        # Get available camera modes
        print("\n=== Available Camera Configurations ===")
        configs = picam2.sensor_modes
        print(f"Number of available modes: {len(configs)}")
        for i, config in enumerate(configs):
            print(f"\nMode {i}:")
            mode_info = format_sensor_mode(config)
            print(json.dumps(mode_info, indent=2))
        
        # Create our specific video configuration
        print("\n=== Creating Test Configuration ===")
        video_config = picam2.create_video_configuration(
            main={"size": (1100, 1100), "format": "RGB888"},
            controls={
                "NoiseReductionMode": libcamera_controls.draft.NoiseReductionModeEnum.Off,
                "FrameRate": 60.0
            }
        )
        print("Video configuration created:")
        # Only print the parts of video_config that are JSON serializable
        safe_config = {
            "main": video_config["main"],
            "controls": str(video_config.get("controls", {})),
            "buffer_count": video_config.get("buffer_count", None),
            "queue": video_config.get("queue", None)
        }
        print(json.dumps(safe_config, indent=2))
        
        # Configure and start camera
        print("\n=== Starting Camera ===")
        picam2.configure(video_config)
        picam2.start()
        time.sleep(1)  # Give camera time to settle
        
        # Get actual camera state
        print("\n=== Current Camera State ===")
        print("Camera Properties:")
        print(json.dumps(properties, indent=2))
        print("\nCamera Controls:")
        camera_controls = {k: str(v) for k, v in picam2.camera_controls.items()}
        print(json.dumps(camera_controls, indent=2))
        
        # Calculate and display FOV information
        calculate_fov_info(properties, video_config)
        
        # Capture a test frame to get actual frame properties
        print("\n=== Test Frame Properties ===")
        frame = picam2.capture_array()
        print(f"Frame shape: {frame.shape}")
        print(f"Frame dtype: {frame.dtype}")
        
        # Get current camera configuration
        print("\n=== Current Configuration ===")
        current_config = picam2.camera_config
        print(f"Current config: {current_config}")
        
    except Exception as e:
        print(f"Error during camera diagnostics: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            picam2.stop()
        except:
            pass

if __name__ == "__main__":
    print_camera_info() 