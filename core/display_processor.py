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
        
        # Camera sensor constants
        self.SENSOR_WIDTH = 9152   # Full sensor width
        self.SENSOR_HEIGHT = 6944  # Full sensor height
        
        # Tracking state with spring-damper smoothing
        self.current_crop = None  # [x, y, size]
        self.target_crop = None   # [x, y, size]
        self.velocity = [0, 0, 0]  # Velocity for x, y, and size
        self.spring_constant = 2.0  # Reduced for smoother motion
        self.damping = 4.0  # Increased damping to reduce small adjustments
        self.max_velocity = 100  # Limit maximum velocity to prevent overshooting
        self.deadzone_factor = 0.2
        self.size_deadzone_factor = 0.2
        
        # Separate face detection from display updates
        self.last_face_data = None
        self.last_face_update = 0
        self.face_data_valid_duration = 0.5  # Consider face data valid for 500ms
        
        # Frame timing for display
        self.min_display_interval = 0.016  # Target ~60 FPS for display
        self.last_display_update = 0
        
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
            
    def _convert_to_sensor_coordinates(self, x: int, y: int, size: int, frame_width: int, frame_height: int) -> Tuple[int, int, int]:
        """Convert frame coordinates to sensor coordinates maintaining absolute square ratio"""
        # Force square sensor region
        sensor_dim = min(self.SENSOR_WIDTH, self.SENSOR_HEIGHT)
        
        # Calculate scaling based on the minimum sensor dimension to ensure square
        frame_scale = sensor_dim / max(frame_width, frame_height)

        # Scale size while maintaining square, but respect camera's max height
        MAX_CAMERA_HEIGHT = 4320  # Camera's maximum supported height
        sensor_size = int(size * frame_scale)
        sensor_size = min(sensor_size, sensor_dim, MAX_CAMERA_HEIGHT)  # Ensure it fits within all constraints
        
        # Calculate center point and scale
        center_x = x + (size / 2)
        center_y = y + (size / 2)
        
        # Scale and center the crop in the square sensor region
        sensor_center_x = int(center_x * frame_scale)
        sensor_center_y = int(center_y * frame_scale)
        
        # Calculate final coordinates
        sensor_x = sensor_center_x - (sensor_size // 2)
        sensor_y = sensor_center_y - (sensor_size // 2)
        
        # Center in the actual sensor area (which may be non-square)
        if self.SENSOR_WIDTH > sensor_dim:
            # Center horizontally in the wider sensor
            extra_width = self.SENSOR_WIDTH - sensor_dim
            sensor_x += int(extra_width / 2)
            
        if self.SENSOR_HEIGHT > sensor_dim:
            # Center vertically in the taller sensor
            extra_height = self.SENSOR_HEIGHT - sensor_dim
            sensor_y += int(extra_height / 2)
        
        # Final bounds check
        sensor_x = max(0, min(self.SENSOR_WIDTH - sensor_size, sensor_x))
        sensor_y = max(0, min(self.SENSOR_HEIGHT - sensor_size, sensor_y))
        
        return sensor_x, sensor_y, sensor_size

    def _display_loop(self):
        """Main display loop running at full camera FPS"""
        while self.running:
            current_time = time.monotonic()
            
            # Check if it's time for a display update
            if current_time - self.last_display_update >= self.min_display_interval:
                frame = self.camera_manager.get_latest_frame()
                if frame is not None:
                    # Get latest face data if available
                    face_data = self.face_processor.get_current_face_data()
                    if face_data is not None:
                        self.last_face_data = face_data
                        self.last_face_update = current_time
                    
                    # Use last known face data if it's still valid
                    if (self.last_face_data is not None and 
                        current_time - self.last_face_update < self.face_data_valid_duration):
                        self._update_crop_with_face(self.last_face_data)
                    
                    # Apply current crop to frame
                    self._apply_current_crop(frame)
                    self.last_display_update = current_time
            
            # Small sleep to prevent CPU thrashing
            time.sleep(0.001)

    def _update_crop_with_face(self, face_data):
        """Update crop based on face detection data with critically damped smoothing"""
        if face_data is None:
            return
            
        h, w = self.camera_manager.get_latest_frame().shape[:2]
        bbox = face_data.bbox
        
        # Get center point based on current zoom level
        center_x, center_y = self._get_landmark_center(face_data.landmarks, self.current_zoom)
        center_x = int(center_x * w)
        center_y = int(center_y * h)
        
        # Convert bbox percentages to pixel coordinates first
        face_x = int(bbox[0] * w)
        face_y = int(bbox[1] * h)
        face_w = int(bbox[2] * w)
        face_h = int(bbox[3] * h)
        
        # Calculate crop size based on face width with dynamic zoom
        # As face gets smaller (further away), we crop tighter
        base_size = face_w  # Use face width as base
        frame_diagonal = (w * w + h * h) ** 0.5  # Screen diagonal for reference
        relative_face_size = face_w / frame_diagonal  # How big the face is relative to screen
        
        # Dynamic zoom factor: zoom in more when face is smaller
        dynamic_zoom = max(1.2, 2.0 - relative_face_size * 10)  # Adjust these constants to tune behavior
        zoom_factor = self.zoom_factors[self.current_zoom] * dynamic_zoom
        
        target_size = int(base_size / zoom_factor)
        # Ensure even size
        target_size = target_size + (target_size % 2)
        
        # Calculate crop position ensuring perfect square
        target_x = int(center_x - target_size / 2)
        target_y = int(center_y - target_size / 2)
        
        # Initialize crops and velocity if needed
        if self.target_crop is None:
            self.target_crop = [target_x, target_y, target_size]
            self.velocity = [0, 0, 0]
        if self.current_crop is None:
            self.current_crop = self.target_crop.copy()
            
        # Update target crop
        self.target_crop = [target_x, target_y, target_size]
        
        # Apply critically damped smoothing
        dt = 1/5.0  # Time step (5 FPS)
        for i in range(3):  # For x, y, and size
            # Calculate spring force
            displacement = self.target_crop[i] - self.current_crop[i]
            spring_force = self.spring_constant * displacement
            
            # Apply damping force
            damping_force = -self.damping * self.velocity[i]
            
            # Update velocity with limiting
            self.velocity[i] += (spring_force + damping_force) * dt
            
            # Limit velocity magnitude
            self.velocity[i] = max(-self.max_velocity, min(self.max_velocity, self.velocity[i]))
            
            # If very close to target and moving slowly, just stop
            if abs(displacement) < 1.0 and abs(self.velocity[i]) < 0.5:
                self.velocity[i] = 0
                self.current_crop[i] = self.target_crop[i]
            else:
                # Update position
                self.current_crop[i] += self.velocity[i] * dt
            
        # Ensure integer coordinates
        self.current_crop = [int(v) for v in self.current_crop]
        
        # Bound check while maintaining square
        self.current_crop[0] = max(0, min(w - self.current_crop[2], self.current_crop[0]))
        self.current_crop[1] = max(0, min(h - self.current_crop[2], self.current_crop[1]))

    def _apply_current_crop(self, frame):
        """Apply current crop to frame using hardware ScalerCrop when possible"""
        if self.current_crop is None or frame is None:
            return
            
        try:
            # Convert to sensor coordinates and update ScalerCrop
            x, y, size = self.current_crop
            sensor_x, sensor_y, sensor_size = self._convert_to_sensor_coordinates(
                x, y, size, frame.shape[1], frame.shape[0]
            )
            self.camera_manager.picam2.set_controls({
                "ScalerCrop": (sensor_x, sensor_y, sensor_size, sensor_size)
            })
        except Exception as e:
            # If hardware crop fails, we don't fall back to software crop
            # This keeps the display pipeline fast
            pass 