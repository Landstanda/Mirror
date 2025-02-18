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
        
        # Tracking state with improved smoothing
        self.current_crop = None  # [x, y, size]
        self.target_crop = None   # [x, y, size]
        self.deadzone_factor = 0.05  # Reduced from 0.10 for smoother tracking
        self.size_deadzone_factor = 0.05
        self.position_smoothing = 0.15  # Increased for smoother movement
        self.size_smoothing = 0.1
        
        # Frame timing
        self.last_process_time = 0
        self.min_process_interval = 0.2  # 5 FPS to match face processor
        
        # Zoom factors for different landmarks
        self.zoom_factors = {
            ZoomLevel.EYES: 1.5,
            ZoomLevel.LIPS: 1.7,
            ZoomLevel.FACE: 1.0,
            ZoomLevel.WIDE: 0.6
        }
        
    def start(self):
        """Start the display processor"""
        if not self.running:
            print("Starting display processor...")
            self.running = True
            self.thread = threading.Thread(target=self._display_loop, daemon=True)
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
        self.current_zoom = level
        
    def _get_landmark_center(self, landmarks: List[Tuple[float, float]], zoom_level: ZoomLevel) -> Tuple[float, float]:
        """Get the center point for the current zoom level"""
        if zoom_level == ZoomLevel.EYES:
            # Average position between eyes
            return (
                (landmarks[0][0] + landmarks[1][0]) / 2,
                (landmarks[0][1] + landmarks[1][1]) / 2
            )
        elif zoom_level == ZoomLevel.LIPS:
            # Use mouth landmark
            return landmarks[3]
        else:  # FACE or WIDE
            # Use nose landmark for center
            return landmarks[2]
            
    def _process_frame(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """Process a single frame with improved tracking"""
        if frame is None:
            return None
            
        face_data = self.face_processor.get_current_face_data()
        if face_data is None:
            return frame
            
        h, w = frame.shape[:2]
        bbox = face_data.bbox
        
        # Get center point based on current zoom level
        center_x, center_y = self._get_landmark_center(face_data.landmarks, self.current_zoom)
        center_x = int(center_x * w)
        center_y = int(center_y * h)
        
        # Calculate target crop size based on face size and zoom level
        face_size = max(bbox[2] * w, bbox[3] * h)
        zoom_factor = self.zoom_factors[self.current_zoom]
        target_size = int(face_size / zoom_factor)
        
        # Calculate target crop position
        target_x = center_x - target_size // 2
        target_y = center_y - target_size // 2
        
        # Initialize crops if needed
        if self.target_crop is None:
            self.target_crop = [target_x, target_y, target_size]
        if self.current_crop is None:
            self.current_crop = self.target_crop.copy()
            
        # Update target crop
        self.target_crop = [target_x, target_y, target_size]
        
        # Calculate relative movement
        current_x, current_y, current_size = self.current_crop
        dx = (target_x - current_x) / current_size
        dy = (target_y - current_y) / current_size
        dsize = abs(target_size - current_size) / current_size
        
        # Apply movement only if it exceeds deadzone
        if abs(dx) > self.deadzone_factor or abs(dy) > self.deadzone_factor or dsize > self.size_deadzone_factor:
            # Smooth position changes
            new_x = int(current_x + (target_x - current_x) * self.position_smoothing)
            new_y = int(current_y + (target_y - current_y) * self.position_smoothing)
            new_size = int(current_size + (target_size - current_size) * self.size_smoothing)
            
            # Update current crop with bounds checking
            self.current_crop = [
                max(0, min(w - new_size, new_x)),
                max(0, min(h - new_size, new_y)),
                new_size
            ]
            
            # Update camera's ScalerCrop for hardware-accelerated cropping
            try:
                x, y, size = self.current_crop
                self.camera_manager.picam2.set_controls({"ScalerCrop": (x, y, size, size)})
            except Exception as e:
                # Fall back to software cropping if hardware crop fails
                pass
                
        # Extract crop (fallback if hardware crop fails)
        x, y, size = self.current_crop
        x = max(0, min(w - size, x))
        y = max(0, min(h - size, y))
        
        try:
            cropped = frame[y:y+size, x:x+size]
            return cv2.resize(cropped, (1100, 1100))
        except Exception as e:
            return frame
            
    def _display_loop(self):
        """Main display loop synchronized with face processor"""
        last_process_time = time.monotonic()
        
        while self.running:
            current_time = time.monotonic()
            
            # Process frame at 5 FPS to match face processor
            if current_time - last_process_time >= self.min_process_interval:
                frame = self.camera_manager.get_latest_frame()
                if frame is not None:
                    processed_frame = self._process_frame(frame)
                    if processed_frame is not None:
                        # Convert to RGBA for overlay
                        processed_frame = cv2.cvtColor(processed_frame, cv2.COLOR_RGB2RGBA)
                        self.camera_manager.picam2.set_overlay(processed_frame)
                last_process_time = current_time
            
            # Small sleep to prevent CPU thrashing
            time.sleep(0.001) 