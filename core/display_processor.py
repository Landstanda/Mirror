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
        
        # Get reference to ScalerCropController from camera_manager
        self.scaler_crop_controller = None
        if hasattr(camera_manager, 'scaler_crop_controller'):
            self.scaler_crop_controller = camera_manager.scaler_crop_controller
        
        # Camera sensor constants
        self.SENSOR_WIDTH = 9152   # Full sensor width
        self.SENSOR_HEIGHT = 6944  # Full sensor height
        
        # Simple position tracking
        self.current_position = None  # [x, y, size]
        self.smoothing_factor = 0.08  # Smoothing factor for movement
        self.movement_threshold = 0.05  # 5% of size for movement threshold
        
        # Frame timing for display
        self.min_display_interval = 0.016  # Target ~60 FPS for display
        self.last_display_update = 0
        self.last_debug_print = 0
        self.debug_print_interval = 1.0  # Print debug info every second
        
        # Simple fixed ratios relative to face bbox
        self.zoom_ratios = {
            ZoomLevel.EYES: 0.5,   # 40% of face bbox - zoomed in
            ZoomLevel.LIPS: 0.6,   # 60% of face bbox
            ZoomLevel.FACE: 1.0,   # 100% of face bbox
            ZoomLevel.WIDE: 1.6    # 160% of face bbox - zoomed out
        }
        
        # Eye tracking parameters
        self.center_threshold = 0.20     # Distance from center to consider a point "centered"
        
        # In __init__, add this new attribute:
        self.fixed_eye_zoom_size = None
        
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
        """Change the zoom level and coordinate with ScalerCropController"""
        print(f"\nDEBUG: DisplayProcessor.set_zoom_level called with {level}")
        print(f"DEBUG: Current zoom level before change: {self.current_zoom}")
        
        self.current_zoom = level
        if level != ZoomLevel.EYES:
            self.fixed_eye_zoom_size = None
            
        # Coordinate with ScalerCropController if available
        if self.scaler_crop_controller:
            print("DEBUG: ScalerCropController found, updating zoom level")
            self.scaler_crop_controller.set_zoom_level(level)
            # Force an immediate crop update if we have face data
            face_data = self.face_processor.get_current_face_data()
            if face_data:
                print("DEBUG: Face data available, forcing crop update")
                self.scaler_crop_controller.update_target_crop(face_data)
            else:
                print("DEBUG: No face data available for crop update")
        else:
            print("DEBUG: No ScalerCropController found")
            
        print(f"DEBUG: Zoom level change complete. New level: {self.current_zoom}")
        
    def _get_landmark_center(self, landmarks: List[Tuple[float, float]], zoom_level: ZoomLevel) -> Tuple[float, float]:
        """Get center point for the current zoom level using simple midpoint calculations"""
        # landmarks[0] is left eye, landmarks[1] is right eye, landmarks[2] is nose, landmarks[3] is mouth
        if zoom_level == ZoomLevel.EYES:
            # Simple midpoint between eyes
            return (
                (landmarks[0][0] + landmarks[1][0]) / 2,
                (landmarks[0][1] + landmarks[1][1]) / 2
            )
        elif zoom_level == ZoomLevel.LIPS:
            # Use mouth landmark directly
            return landmarks[3]
        else:  # FACE or WIDE
            # Use nose as center point
            return landmarks[2]
            
    def _get_eye_region_center(self, landmarks: List[Tuple[float, float]]) -> Tuple[float, float]:
        """Determine the center point for eye tracking with stability logic"""
        left_eye = landmarks[0]
        right_eye = landmarks[1]
        midpoint = (
            (left_eye[0] + right_eye[0]) / 2,
            (left_eye[1] + right_eye[1]) / 2
        )
        screen_center = (0.5, 0.5)
        
        # Calculate distances from center for all three points
        def dist_from_center(point):
            return ((point[0] - screen_center[0])**2 + (point[1] - screen_center[1])**2)**0.5
            
        left_dist = dist_from_center(left_eye)
        right_dist = dist_from_center(right_eye)
        mid_dist = dist_from_center(midpoint)
        
        # If any point is near center, use the nearest one
        if min(left_dist, right_dist, mid_dist) < self.center_threshold:
            # Return the closest point to center
            if left_dist < right_dist and left_dist < mid_dist:
                return left_eye
            elif right_dist < mid_dist:
                return right_eye
            else:
                return midpoint
        
        # If no point is near center, return midpoint to trigger recentering
        return midpoint
    
    def _should_update_crop(self, current_center: Tuple[float, float], target_center: Tuple[float, float]) -> bool:
        """Determine if the crop should be updated based on movement thresholds"""
        # Calculate distance between current and target centers
        distance = ((current_center[0] - target_center[0])**2 + 
                   (current_center[1] - target_center[1])**2)**0.5
        
        # Only update if movement is significant
        return distance > self.movement_threshold
        
    def _convert_to_sensor_coordinates(self, x: int, y: int, size: int, frame_width: int, frame_height: int) -> Tuple[int, int, int]:
        """Convert frame coordinates to sensor coordinates maintaining absolute square ratio"""
        # Force square sensor region
        sensor_dim = min(self.SENSOR_WIDTH, self.SENSOR_HEIGHT)
        
        # Calculate scaling based on the minimum sensor dimension to ensure square
        frame_scale = sensor_dim / max(frame_width, frame_height)

        # Scale coordinates to sensor space while preserving the original crop size ratio
        sensor_x = int(x * frame_scale)
        sensor_y = int(y * frame_scale)
        sensor_size = int(size * frame_scale)  # Scale size proportionally with frame
        
        # Center in the actual sensor area (which may be non-square)
        if self.SENSOR_WIDTH > sensor_dim:
            # Center horizontally in the wider sensor
            extra_width = self.SENSOR_WIDTH - sensor_dim
            sensor_x += int(extra_width / 2)
            
        if self.SENSOR_HEIGHT > sensor_dim:
            # Center vertically in the taller sensor
            extra_height = self.SENSOR_HEIGHT - sensor_dim
            sensor_y += int(extra_height / 2)
        
        # Debug logging for sensor coordinate conversion
        current_time = time.monotonic()
        if current_time - self.last_debug_print >= self.debug_print_interval:
            print("\nSensor Coordinate Conversion Debug:")
            print(f"Input frame coords: x={x}, y={y}, size={size}")
            print(f"Frame dimensions: {frame_width}x{frame_height}")
            print(f"Sensor dimensions: {self.SENSOR_WIDTH}x{self.SENSOR_HEIGHT}")
            print(f"Frame scale: {frame_scale}")
            print(f"Pre-bounds sensor coords: x={sensor_x}, y={sensor_y}, size={sensor_size}")
        
        # Final bounds check
        sensor_x = max(0, min(self.SENSOR_WIDTH - sensor_size, sensor_x))
        sensor_y = max(0, min(self.SENSOR_HEIGHT - sensor_size, sensor_y))

        # Debug logging for final bounds-checked coordinates
        if current_time - self.last_debug_print >= self.debug_print_interval:
            print(f"Final sensor coords: x={sensor_x}, y={sensor_y}, size={sensor_size}")
            print(f"Crop region: {sensor_x}:{sensor_x+sensor_size}, {sensor_y}:{sensor_y+sensor_size}")
            self.last_debug_print = current_time
        
        return sensor_x, sensor_y, sensor_size

    def _display_loop(self):
        """Main display loop running at camera FPS"""
        while self.running:
            current_time = time.monotonic()
            
            # Only update at target frame rate
            if current_time - self.last_display_update >= self.min_display_interval:
                frame = self.camera_manager.get_latest_frame_direct()  # Use direct frame access
                if frame is not None:
                    # Apply tighter software crop for display
                    display_frame = self._software_crop_for_display(frame)
                    # Display the frame directly
                    self.display_frame(display_frame)

                self.last_display_update = current_time
            
            # Small sleep to prevent CPU thrashing
            time.sleep(0.001)

    def _update_crop_with_face(self, face_data):
        """Update crop based on face detection data"""
        if face_data is None:
            return
            
        h, w = self.camera_manager.get_latest_frame().shape[:2]
        bbox = face_data.bbox
        
        conservative_zoom_ratio = 1.2
        center_x, center_y = self._get_landmark_center(face_data.landmarks, ZoomLevel.FACE)
        center_x = int(center_x * w)
        center_y = int(center_y * h)
        
        face_w = int(bbox[2] * w)
        target_size = int(face_w * conservative_zoom_ratio)
        target_size = target_size + (target_size % 2)
        
        target_position = [
            int(center_x - target_size / 2),
            int(center_y - target_size / 2),
            target_size
        ]

        current_time = time.monotonic()
        if current_time - self.last_debug_print >= self.debug_print_interval:
            print("\nEnhanced Debug Info:")
            print(f"Face bbox (normalized): {bbox}")
            print(f"Face bbox (pixels): width={face_w}px")
            print(f"Sensor crop target size: {target_size}px")
            print(f"Sensor crop position: {target_position}")
            software_crop_size = int(face_w * self.zoom_ratios[self.current_zoom])
            print(f"Software crop target size: {software_crop_size}px")
            self.last_debug_print = current_time

        if self.current_position is None:
            self.current_position = target_position
        else:
            self._smooth_position_update(target_position)
            
    def _smooth_position_update(self, target_position):
        """Simple smooth movement toward target position"""
        # Calculate movement threshold based on current size
        threshold = self.current_position[2] * self.movement_threshold
        
        # Update each component (x, y, size)
        for i in range(3):
            displacement = target_position[i] - self.current_position[i]
            
            # Only update if movement is significant
            if abs(displacement) > threshold:
                self.current_position[i] += displacement * self.smoothing_factor
                
        # Ensure integer coordinates
        self.current_position = [int(round(v)) for v in self.current_position]

        # Debug logging for smoothed position
        current_time = time.monotonic()
        if current_time - self.last_debug_print >= self.debug_print_interval:
            print("\nSmoothing Debug:")
            print(f"Target position: {target_position}")
            print(f"Current position: {self.current_position}")
            print(f"Movement threshold: {threshold}")

    def _apply_current_crop(self, frame):
        """Apply current crop to frame using hardware ScalerCrop"""
        if self.current_position is None or frame is None:
            return
            
        try:
            # Convert to sensor coordinates and update ScalerCrop
            x, y, size = self.current_position
            sensor_x, sensor_y, sensor_size = self._convert_to_sensor_coordinates(
                x, y, size, frame.shape[1], frame.shape[0]
            )
            
            # Debug logging for ScalerCrop
            current_time = time.monotonic()
            if current_time - self.last_debug_print >= self.debug_print_interval:
                print("\nScalerCrop Debug:")
                print(f"Setting ScalerCrop: ({sensor_x}, {sensor_y}, {sensor_size}, {sensor_size})")
            
            self.camera_manager.picam2.set_controls({
                "ScalerCrop": (sensor_x, sensor_y, sensor_size, sensor_size)
            })
        except Exception as e:
            print(f"ERROR in _apply_current_crop: {e}")
            pass 

    def _software_crop_for_display(self, frame):
        """Apply software cropping based on zoom level for display purposes"""
        if frame is None:
            return frame

        try:
            h, w = frame.shape[:2]
            face_data = self.face_processor.get_current_face_data()
            
            if face_data is None:
                print("DEBUG: No face data available for software crop")
                return frame
                
            bbox = face_data.bbox
            print(f"\nDEBUG: Software crop - Current zoom level: {self.current_zoom}")
            print(f"DEBUG: Face bbox: {bbox}")
            print(f"DEBUG: Zoom ratio for current level: {self.zoom_ratios[self.current_zoom]}")

            # Get center point based on current zoom level
            center_x, center_y = self._get_landmark_center(face_data.landmarks, self.current_zoom)
            center_x = int(center_x * w)
            center_y = int(center_y * h)
            print(f"DEBUG: Crop center point: ({center_x}, {center_y})")

            # Calculate target size based on zoom ratios
            face_w = int(bbox[2] * w)
            target_size = int(face_w * self.zoom_ratios[self.current_zoom])
            target_size = target_size + (target_size % 2)  # Ensure even size
            print(f"DEBUG: Target crop size: {target_size}")

            # Calculate crop coordinates ensuring they stay within frame boundaries
            x1 = max(0, center_x - target_size // 2)
            y1 = max(0, center_y - target_size // 2)
            x2 = min(w, x1 + target_size)
            y2 = min(h, y1 + target_size)
            print(f"DEBUG: Crop coordinates: ({x1}, {y1}) to ({x2}, {y2})")

            # Adjust coordinates if crop goes beyond frame boundaries
            if x2 - x1 < target_size:
                x1 = max(0, x2 - target_size)
            if y2 - y1 < target_size:
                y1 = max(0, y2 - target_size)

            cropped_frame = frame[y1:y2, x1:x2]
            resized_frame = cv2.resize(cropped_frame, (w, h), interpolation=cv2.INTER_LINEAR)
            print(f"DEBUG: Final crop shape: {cropped_frame.shape} -> {resized_frame.shape}")
            
            return resized_frame
            
        except Exception as e:
            print(f"ERROR in software crop: {e}")
            return frame

    def display_frame(self, frame):
        """Display the frame using the camera's preview"""
        if frame is not None:
            try:
                # Update the preview with the new frame
                self.camera_manager.picam2.set_preview(frame)
            except Exception as e:
                print(f"Error displaying frame: {e}") 