from picamera2 import Picamera2, Preview
from libcamera import Transform, controls
from enum import Enum
import numpy as np
import cv2
from core.frame_buffer import FrameBuffer
from core.async_helper import AsyncHelper

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
        self.configure_camera()
        
    def configure_camera(self):
        """Configure camera with hardware-accelerated settings"""
        print("Configuring camera...")
        # Create video configuration for streaming
        video_config = self.picam2.create_video_configuration(
            {"size": (1100, 1100)},
            transform=Transform(hflip=False, vflip=True),
            buffer_count=4,  # Reduced for lower latency
            queue=True,     # Enable frame queueing
            controls={"NoiseReductionMode": controls.draft.NoiseReductionModeEnum.Off}  # Reduce processing overhead
        )
        print("Setting camera configuration...")
        self.picam2.configure(video_config)
        
        # Set high priority for camera thread
        self.picam2.options["priority"] = 0
        
        print("Setting camera controls...")
        # Set additional camera controls
        self.picam2.set_controls({
            "AfMode": 0,          # Manual mode
            "AfSpeed": 1,         # Fast
            "AfTrigger": 0,       # Stop
            "LensPosition": 10.0,  # Initial focus position
            "FrameDurationLimits": (16666, 16666),  # Target 60fps
            "NoiseReductionMode": 0  # Off
        })
        print("Camera configuration complete")
        
    def start(self):
        """Start the camera and frame capture"""
        if not self.running:
            self.running = True
            print("Starting async helper...")
            self.async_helper.start()
            
            print("Starting camera preview...")
            try:
                print("Starting preview...")
                self.picam2.start_preview(Preview.QT, x=10, y=0, width=1100, height=1100)
                print("Preview started successfully")
            except Exception as e:
                print(f"Preview start error: {e}")
                print("Trying fallback preview...")
                try:
                    self.picam2.start_preview(Preview.NULL)
                    print("Fallback preview started")
                except Exception as e:
                    print(f"Fallback preview error: {e}")
            
            print("Starting camera...")
            self.picam2.pre_callback = self._camera_callback
            self.picam2.start()
            print("Camera started successfully")
            
    def stop(self):
        """Stop the camera and frame capture"""
        if self.running:
            self.running = False
            self.async_helper.stop()
            self.picam2.stop()
            
    def _process_frame(self, frame):
        """Process frame in thread pool"""
        if frame.ndim == 3 and frame.shape[2] == 4:
            return cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
        return frame
            
    def _camera_callback(self, request):
        """High priority callback for frame capture"""
        if not self.running:
            return
            
        # Get frame from camera
        frame = request.make_array("main")
        if frame is None:
            return
            
        # Schedule frame processing with high priority
        task_id = self.async_helper.schedule_task(
            self._process_frame,
            priority=0,  # Highest priority
            frame=frame
        )
        
        # Get processed frame (if available)
        processed_frame = self.async_helper.get_result(task_id)
        if processed_frame is not None:
            self.frame_buffer.add_frame(processed_frame)
            
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