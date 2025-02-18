import threading
import time
import cv2
import numpy as np
from typing import Optional, Tuple, List
from core.camera_manager import CameraManager, ZoomLevel
from core.face_processor import CameraFaceProcessor

class DisplayProcessor:
    """
    Handles display processing, zooming, and smooth tracking
    
    Features:
    - Smooth tracking with deadzone
    - Multiple zoom levels (eyes, lips, face, wide)
    - Efficient frame processing
    - Motion prediction
    """
    
    def __init__(self, camera_manager: CameraManager, face_processor: CameraFaceProcessor):
        self.camera_manager = camera_manager
        self.face_processor = face_processor
        self.current_zoom = ZoomLevel.FACE
        self.running = False
        self.thread = None
        
        # Tracking state
        self.current_crop = None  # [x, y, size]
        self.deadzone_factor = 0.10  # Ignore movements less than 10% of frame
        self.size_deadzone_factor = 0.1  # Ignore size changes less than 10%
        self.crop_smoothing = 0.05  # Lower = smoother but more latency
        self.size_smoothing = 0.05
        
        # Performance settings
        self.skip_threshold = 1.0 / 60  # More aggressive frame skipping
        
        # Zoom factors for different landmarks
        self.zoom_factors = {
            ZoomLevel.EYES: 1.5,   # Show 40% of face height for eyes
            ZoomLevel.LIPS: 1.7,   # Show 33% of face height for lips
            ZoomLevel.FACE: 1.0,   # Show full face
            ZoomLevel.WIDE: 0.6    # Show wider view
        }
        
    def start(self):
        """Start the display processor"""
        if not self.running:
            print("Starting display processor...")
            self.running = True
            self.thread = threading.Thread(target=self._display_loop, daemon=True)
            # Set lower thread priority
            self.thread.start()
            print("Display processor started")
            
    def stop(self):
        """Stop the display processor"""
        print("Stopping display processor...")
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            
    def set_zoom_level(self, level: ZoomLevel):
        """Change the zoom level"""
        print(f"Setting zoom level to: {level.name}")
        self.current_zoom = level
        
    def _get_landmark_center(self, landmarks: List[Tuple[float, float]], zoom_level: ZoomLevel) -> Tuple[float, float]:
        """Get the center point for the current zoom level"""
        if zoom_level == ZoomLevel.EYES:
            # Average position between eyes (landmarks[0] is right eye, landmarks[1] is left eye)
            return (
                (landmarks[0][0] + landmarks[1][0]) / 2,
                (landmarks[0][1] + landmarks[1][1]) / 2
            )
        elif zoom_level == ZoomLevel.LIPS:
            # Use mouth landmark (landmarks[3])
            return landmarks[3]
        else:  # FACE or WIDE
            # Use nose landmark (landmarks[2]) for center
            return landmarks[2]
            
    def _process_frame(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """Process a single frame with zooming and tracking"""
        if frame is None:
            return None
            
        face_data = self.face_processor.get_current_face_data()
        if face_data is None:
            return frame
            
        h, w = frame.shape[:2]
        bbox = face_data.bbox
        
        # Convert normalized coordinates to pixel coordinates
        face_x = int(bbox[0] * w)
        face_y = int(bbox[1] * h)
        face_w = int(bbox[2] * w)
        face_h = int(bbox[3] * h)
        
        # Get center point based on current zoom level
        center_x, center_y = self._get_landmark_center(face_data.landmarks, self.current_zoom)
        center_x = int(center_x * w)
        center_y = int(center_y * h)
        
        # Calculate crop size based on zoom level
        zoom_factor = self.zoom_factors[self.current_zoom]
        base_size = max(face_w, face_h)
        target_size = int(base_size / zoom_factor)
        target_x = center_x - target_size // 2
        target_y = center_y - target_size // 2
        
        # Initialize current_crop if needed
        if self.current_crop is None:
            self.current_crop = [target_x, target_y, target_size]
            
        # Calculate movement relative to current crop
        current_x, current_y, current_size = self.current_crop
        
        # Calculate centers
        current_center_x = current_x + current_size // 2
        current_center_y = current_y + current_size // 2
        
        # Calculate relative movement
        dx = abs(current_center_x - center_x) / current_size
        dy = abs(current_center_y - center_y) / current_size
        size_change = abs(target_size - current_size) / current_size
        
        # Apply smoothing only if movement exceeds deadzone
        if dx > self.deadzone_factor or dy > self.deadzone_factor or size_change > self.size_deadzone_factor:
            # Smooth size changes
            new_size = int(current_size + (target_size - current_size) * self.size_smoothing)
            
            # Smooth position changes
            new_center_x = current_center_x + int((center_x - current_center_x) * self.crop_smoothing)
            new_center_y = current_center_y + int((center_y - current_center_y) * self.crop_smoothing)
            
            # Convert back to top-left coordinates
            new_x = new_center_x - new_size // 2
            new_y = new_center_y - new_size // 2
            
            # Update crop with bounds checking
            self.current_crop = [
                max(0, min(w - new_size, new_x)),
                max(0, min(h - new_size, new_y)),
                new_size
            ]
            
        # Extract and resize the crop
        x, y, size = self.current_crop
        x = max(0, min(w - size, x))
        y = max(0, min(h - size, y))
        
        try:
            cropped = frame[y:y+size, x:x+size]
            return cv2.resize(cropped, (1100, 1100))
        except Exception as e:
            print(f"Error cropping frame: {e}")
            return frame
            
    def _display_loop(self):
        """Main display loop with performance optimizations"""
        print("Starting display loop...")
        last_process_time = time.monotonic()
        
        while self.running:
            frame = self.camera_manager.get_latest_frame()
            
            if frame is None:
                time.sleep(0.001)
                continue
            
            current_time = time.monotonic()
            # Process every frame unless we're severely behind
            if current_time - last_process_time < self.skip_threshold:
                processed_frame = self._process_frame(frame)
                if processed_frame is not None:
                    # Direct RGB to RGBA conversion
                    processed_frame = cv2.cvtColor(processed_frame, cv2.COLOR_RGB2RGBA)
                    self.camera_manager.picam2.set_overlay(processed_frame)
            
            last_process_time = current_time
            # Minimal sleep to prevent CPU overuse while maintaining responsiveness
            time.sleep(0.001) 