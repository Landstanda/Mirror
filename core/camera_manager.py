from picamera2 import Picamera2, Preview
from libcamera import Transform, controls
from threading import Lock
from collections import deque
from enum import Enum
import numpy as np
import cv2

class ZoomLevel(Enum):
    WIDE = 1
    FACE = 2
    EYES = 3
    LIPS = 4

class RingBuffer:
    """Thread-safe ring buffer for frame storage"""
    def __init__(self, buffer_size=3):
        self.buffer = deque(maxlen=buffer_size)
        self.lock = Lock()
        
    def push(self, frame):
        with self.lock:
            self.buffer.append(frame)
            
    def get_latest(self):
        with self.lock:
            return self.buffer[-1] if len(self.buffer) > 0 else None
            
    def is_full(self):
        with self.lock:
            return len(self.buffer) == self.buffer.maxlen

class CameraManager:
    """
    Manages PiCamera2 operations using threading for optimal performance
    """
    def __init__(self):
        self.picam2 = Picamera2()
        self.frame_buffer = RingBuffer(buffer_size=3)
        self.focus_range = (8.0, 12.5)
        self.current_zoom = ZoomLevel.FACE
        self.frame_drop_threshold = 0.8
        self.running = False
        self.configure_camera()
        
    def configure_camera(self):
        """Configure camera with hardware-accelerated settings"""
        # Create video configuration for streaming
        video_config = self.picam2.create_video_configuration(
            {"size": (1100, 1100)},
            transform=Transform(hflip=False, vflip=True),
            buffer_count=4,
            queue=True,
            controls={"NoiseReductionMode": controls.draft.NoiseReductionModeEnum.Off}
        )
        
        # Apply the configuration
        self.picam2.configure(video_config)
        
        # Set additional camera controls
        self.picam2.set_controls({
            "AfMode": 0,          # Manual mode
            "AfSpeed": 1,         # Fast
            "AfTrigger": 0,       # Stop
            "LensPosition": 10.0,  # Initial focus position
            "FrameDurationLimits": (16666, 16666),  # Target 60fps
            "NoiseReductionMode": 0  # Off
        })
        
        # Set high priority for camera thread
        self.picam2.options["priority"] = 0
        
    def start(self):
        """Start the camera and frame capture"""
        if not self.running:
            self.running = True
            try:
                print("Starting preview...")
                self.picam2.start_preview(Preview.QTGL, x=10, y=0, width=1100, height=1100)
                print("Preview started successfully")
            except Exception as e:
                print(f"Preview start error: {e}")
            
            print("Starting camera...")
            self.picam2.start()
            print("Camera started successfully")
            # Set up callback for frame capture
            self.picam2.post_callback = self._camera_callback
            
    def stop(self):
        """Stop the camera and frame capture"""
        if self.running:
            self.running = False
            self.picam2.stop()
            
    def _camera_callback(self, request):
        """Callback function for frame capture"""
        if not self.running:
            return
            
        # Only store frame if buffer isn't too full
        if not self.frame_buffer.is_full() or np.random.random() > self.frame_drop_threshold:
            frame = request.make_array("main")
            if frame.ndim == 3 and frame.shape[2] == 4:  # Convert RGBA to RGB if needed
                frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
            self.frame_buffer.push(frame)
            
    def get_latest_frame(self):
        """Get the most recent frame from the buffer"""
        return self.frame_buffer.get_latest()
        
    def set_focus(self, focus_value):
        """Set camera focus within valid range"""
        focus_value = max(min(focus_value, self.focus_range[1]), self.focus_range[0])
        self.picam2.set_controls({"LensPosition": focus_value})
        
    def set_zoom_level(self, zoom_level: ZoomLevel):
        """Set the zoom level of the camera"""
        self.current_zoom = zoom_level
        # TODO: Implement actual zoom logic based on zoom_level 