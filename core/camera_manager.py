from picamera2 import Picamera2, Preview
from libcamera import Transform, controls
from enum import Enum
import numpy as np
import cv2
from core.frame_buffer import FrameBuffer
from core.async_helper import AsyncHelper
import os
import time
from collections import deque

class ZoomLevel(Enum):
    WIDE = 1
    FACE = 2
    EYES = 3
    LIPS = 4

class CameraManager:
    """
    Manages PiCamera2 operations using threading for optimal performance
    """
    def __init__(self):
        self.picam2 = Picamera2()
        self.frame_buffer = FrameBuffer(buffer_size=3)
        self.async_helper = AsyncHelper(max_workers=2)
        self.focus_range = (8.0, 12.5)
        self.current_zoom = ZoomLevel.FACE
        self.running = False
        
        # Performance monitoring
        self.frame_times = deque(maxlen=60)  # Store last 60 frame timestamps
        self.latency_times = deque(maxlen=60)  # Store last 60 latency measurements
        self.last_fps_print = 0
        self.fps_print_interval = 7.0  # Print stats every 7 seconds
        
        self.configure_camera()
        
    def configure_camera(self):
        """Configure camera with optimized low-latency settings"""
        print("Configuring camera for low latency...")
        
        try:
            # Log available camera modes
            print("\nAvailable Camera Modes:")
            for i, mode in enumerate(self.picam2.sensor_modes):
                print(f"Mode {i}:")
                print(f"  Size: {mode['size']}")
                print(f"  Format: {mode['format']}")
                if 'fps' in mode:
                    print(f"  FPS: {mode['fps']}")
                    
            # Create video configuration optimized for low latency
            video_config = self.picam2.create_video_configuration(
                # Main stream configuration
                main={"size": (1100, 1100), "format": "RGB888"},  # Keep display size square
                sensor={"output_size": (2312, 1736)},  # Use Mode 2 resolution
                transform=Transform(hflip=False, vflip=True),
                buffer_count=3,  # Increased for smoother operation at higher res
                queue=True,
                controls={
                    "NoiseReductionMode": controls.draft.NoiseReductionModeEnum.Off,
                    "FrameRate": 30.0  # Match Mode 2's FPS
                },
                encode="main"  # Direct sensor-to-memory path
            )
            
            print("\nRequested Video Configuration:")
            print(f"Main stream size: {video_config['main']['size']}")
            print(f"Sensor size: {video_config['sensor']['output_size']}")
            print(f"Format: {video_config['main']['format']}")
            print(f"Buffer count: {video_config['buffer_count']}")
            print(f"Controls: {video_config['controls']}")
            
            print("\nSetting camera configuration...")
            self.picam2.configure(video_config)
            print("Camera configuration applied")
            
            # Log actual running configuration
            print("\nActual Running Configuration:")
            print(f"Camera Properties: {self.picam2.camera_properties}")
            print(f"Camera Controls: {self.picam2.camera_controls}")
            
            # Enable zero-copy operation where possible
            self.picam2.options["enable_raw"] = True
            self.picam2.options["use_dma"] = True  # Enable DMA for frame transfer
            self.picam2.options["buffer_count"] = 3  # Match the increased buffer count
            self.picam2.options["callback_format"] = "RGB888"  # Match main format
            print("\nCamera options configured:")
            print(f"Options: {self.picam2.options}")
            
        except Exception as e:
            print(f"ERROR configuring camera: {e}")
            raise
            
        print("Setting camera controls...")
        try:
            # Set only the essential controls we know are supported
            self.picam2.set_controls({
                "AfMode": 0,          # Manual focus
                "AfSpeed": 1,         # Fast AF when manual adjustment needed
                "LensPosition": 10.0,  # Initial focus position
                "FrameDurationLimits": (33333, 33333),  # Target 30fps (1/30 sec = 33333 μs)
                "NoiseReductionMode": 0  # Disable noise reduction
            })
            print("Camera controls set successfully")
            
        except Exception as e:
            print(f"ERROR setting camera controls: {e}")
            raise
            
        print("Camera configuration complete")
        
    def start(self):
        """Start the camera and frame capture"""
        if not self.running:
            self.running = True
            self.async_helper.start()
            
            try:
                self.picam2.start_preview(Preview.QT, x=10, y=0, width=1100, height=1100)
            except Exception as e:
                print(f"Preview start error: {e}")
                try:
                    self.picam2.start_preview(Preview.NULL)
                except Exception as e:
                    print(f"Fallback preview error: {e}")
            
            # Register callback BEFORE starting camera
            self.picam2.pre_callback = self._camera_callback
            self.picam2.post_callback = lambda _: None  # Silent post-callback
            
            try:
                self.picam2.start()
            except Exception as e:
                print(f"ERROR starting camera: {e}")
                raise
            
    def stop(self):
        """Stop the camera and frame capture"""
        if self.running:
            self.running = False
            self.async_helper.stop()
            self.picam2.stop()
            
    def _process_frame(self, frame):
        """Process frame in thread pool"""
        try:
            if frame.ndim == 3 and frame.shape[2] == 4:
                return cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
            return frame
        except Exception as e:
            print(f"ERROR in frame processing: {e}")
            return None
            
    def _camera_callback(self, request):
        """High priority callback for frame capture"""
        if not self.running:
            return
            
        try:
            # Record frame arrival time
            frame_time = time.monotonic()
            
            # Get frame from camera
            frame = request.make_array("main")
            if frame is None:
                return
                
            # Log frame properties periodically
            current_time = time.monotonic()
            if current_time - self.last_fps_print >= self.fps_print_interval:
                print(f"\nFrame Properties:")
                print(f"Shape: {frame.shape}")
                print(f"Data type: {frame.dtype}")
                if hasattr(request, 'metadata'):
                    print(f"Metadata: {request.metadata}")
                
            # Process frame directly
            processed_frame = self._process_frame(frame)
            if processed_frame is not None:
                self.frame_buffer.add_frame(processed_frame)
                
                # Calculate and store latency
                latency = time.monotonic() - frame_time
                self.latency_times.append(latency)
                self.frame_times.append(frame_time)
                
                # Print performance stats periodically
                current_time = time.monotonic()
                if current_time - self.last_fps_print >= self.fps_print_interval:
                    self._print_performance_stats()
                    self.last_fps_print = current_time
                
        except Exception as e:
            print(f"ERROR in camera callback: {e}")
            
    def _print_performance_stats(self):
        """Calculate and print performance statistics"""
        if len(self.frame_times) < 2:
            return
            
        # Calculate FPS
        time_diff = self.frame_times[-1] - self.frame_times[0]
        if time_diff > 0:
            fps = (len(self.frame_times) - 1) / time_diff
            
            # Calculate average latency
            avg_latency = sum(self.latency_times) / len(self.latency_times) * 1000  # Convert to ms
            
            print(f"Camera Performance: {fps:.1f} FPS, Latency: {avg_latency:.1f}ms")
            
    def get_latest_frame(self):
        """Get the most recent frame from the buffer"""
        return self.frame_buffer.get_latest_frame()
        
    def set_focus(self, focus_value):
        """Set camera focus within valid range"""
        focus_value = max(min(focus_value, self.focus_range[1]), self.focus_range[0])
        self.picam2.set_controls({"LensPosition": focus_value})
        
    def set_zoom_level(self, zoom_level: ZoomLevel):
        """Set the zoom level of the camera"""
        self.current_zoom = zoom_level
        # TODO: Implement actual zoom logic based on zoom_level 

    def get_latest_frame_direct(self):
        """Provide direct access to the latest frame from the camera."""
        return self.picam2.capture_frame()  # Assuming capture_frame() is a method that captures and returns the latest frame directly 