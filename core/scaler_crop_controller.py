import threading
import time
from typing import Optional, Tuple
from core.camera_manager import ZoomLevel

class ScalerCropController:
    """
    Controls the hardware ScalerCrop based on face detection data.
    Runs at 5 FPS to update camera crop settings.
    """
    
    def __init__(self, camera_manager):
        self.camera_manager = camera_manager
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        
        # Crop settings
        self.current_crop = None  # (x, y, width, height)
        self.target_crop = None
        self.smoothing_factor = 0.15  # Reduced from 0.3 for smoother transitions. NOTE: May need further tuning with faster update interval.
        self.min_update_interval = 0.0333  # Target 30 FPS updates (1 / 30) - Changed from 0.2 (5 FPS)
        self.last_update_time = 0
        self.movement_threshold_ratio = 0.10 # Only start panning if target center moves > 10% of current crop width/height
        
        # Hardware zoom ratios for different zoom levels (relative to face size)
        self.hardware_zoom_ratios = {
            ZoomLevel.WIDE: 1.2,   # Much wider view for context
            ZoomLevel.FACE: 1.0,   # Slightly larger than face
            ZoomLevel.EYES: 0.6,   # Wider view of eyes region
            ZoomLevel.LIPS: 0.5    # Wider view of lips region
        }
        self.current_zoom = ZoomLevel.FACE
        
    def start(self):
        """Start the ScalerCrop controller thread"""
        if not self.running:
            print("Starting ScalerCrop controller...")
            self.running = True
            self.thread = threading.Thread(target=self._update_loop, daemon=True)
            self.thread.start()
            
    def stop(self):
        """Stop the ScalerCrop controller thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            
    def set_zoom_level(self, zoom_level: ZoomLevel):
        """Update zoom level for hardware crop"""
        print(f"\nChanging zoom to: {zoom_level}")
        # Use lock to ensure atomicity of zoom level change and crop reset
        with self.lock:
            self.current_zoom = zoom_level
            # Reset current_crop to None. This forces _smooth_crop_update
            # to immediately adopt the new target_crop (reflecting the new zoom)
            # on the next update cycle, bypassing the dead zone check for the transition.
            self.current_crop = None
        
    def update_target_crop(self, face_data) -> None:
        """Update the target crop based on face detection data"""
        if not face_data:
            return
            
        # Calculate crop centered on face with zoom based on current level
        bbox = face_data.bbox  # [xmin, ymin, width, height]
        center_x = bbox[0] + bbox[2] / 2
        center_y = bbox[1] + bbox[3] / 2
        
        # Use the larger of width/height to ensure face fits in crop
        base_size = max(bbox[2], bbox[3])
        size = base_size * self.hardware_zoom_ratios[self.current_zoom]
        
        # Calculate crop coordinates
        x = center_x - size / 2
        y = center_y - size / 2
        
        # Update target crop with thread safety
        with self.lock:
            self.target_crop = (x, y, size, size)
            
    def _smooth_crop_update(self) -> Optional[Tuple[float, float, float, float]]:
        """Calculate smoothed crop settings, applying a dead zone for stability."""
        if self.target_crop is None:
            return None
            
        if self.current_crop is None:
            # First update, set current directly to target
            self.current_crop = self.target_crop
            return self.current_crop

        # Calculate centers
        current_center_x = self.current_crop[0] + self.current_crop[2] / 2
        current_center_y = self.current_crop[1] + self.current_crop[3] / 2
        target_center_x = self.target_crop[0] + self.target_crop[2] / 2
        target_center_y = self.target_crop[1] + self.target_crop[3] / 2

        # Calculate distance between centers
        delta_x = target_center_x - current_center_x
        delta_y = target_center_y - current_center_y
        distance = (delta_x**2 + delta_y**2)**0.5

        # Calculate movement threshold based on current crop size (using width, assuming square)
        threshold_distance = self.current_crop[2] * self.movement_threshold_ratio
        
        # Only apply smoothing if movement exceeds threshold
        if distance > threshold_distance:
            # Smooth transition to target
            new_crop = []
            for i in range(4):
                current = self.current_crop[i]
                target = self.target_crop[i]
                smoothed = current + (target - current) * self.smoothing_factor
                new_crop.append(smoothed)
            self.current_crop = tuple(new_crop)
        # Else: self.current_crop remains unchanged, creating the dead zone

        return self.current_crop # Return the (potentially unchanged) current crop
        
    def _update_loop(self):
        """Main loop for updating ScalerCrop settings"""
        while self.running:
            current_time = time.monotonic()
            
            # Update at 5 FPS
            if current_time - self.last_update_time >= self.min_update_interval:
                with self.lock:
                    if self.target_crop is not None:
                        crop_settings = self._smooth_crop_update()
                        if crop_settings:
                            try:
                                # Convert normalized coordinates to sensor coordinates
                                sensor_crop = self._convert_to_sensor_coordinates(crop_settings)
                                self.camera_manager.picam2.set_controls({
                                    "ScalerCrop": sensor_crop
                                })
                            except Exception as e:
                                print(f"Error updating ScalerCrop: {e}")
                                
                self.last_update_time = current_time
                
            time.sleep(0.001)  # Prevent CPU thrashing
            
    def _convert_to_sensor_coordinates(self, normalized_crop: Tuple[float, float, float, float]) -> Tuple[int, int, int, int]:
        """Convert normalized coordinates to sensor coordinates while maintaining aspect ratio"""
        sensor_width = self.camera_manager.picam2.camera_properties["ScalerCropMaximum"][2]
        sensor_height = self.camera_manager.picam2.camera_properties["ScalerCropMaximum"][3]
        
        x, y, w, h = normalized_crop
        
        # First convert the center point to sensor coordinates
        center_x = (x + w/2) * sensor_width
        center_y = (y + h/2) * sensor_height
        
        # Calculate the crop size in sensor coordinates
        # Use height as the base size since we want a square crop
        sensor_size = int(h * sensor_height)
        
        # Calculate the crop coordinates centered on the face
        sensor_x = int(center_x - sensor_size/2)
        sensor_y = int(center_y - sensor_size/2)
        
        # Ensure coordinates are within bounds
        sensor_x = max(0, min(sensor_width - sensor_size, sensor_x))
        sensor_y = max(0, min(sensor_height - sensor_size, sensor_y))
        
        return (sensor_x, sensor_y, sensor_size, sensor_size)

    def _should_update(self) -> bool:
        """Check if enough time has passed for the next update"""
        current_time = time.monotonic()
        if current_time - self.last_update_time >= self.min_update_interval:
            self.last_update_time = current_time
            return True
        return False