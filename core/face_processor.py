import os
import threading
import time
from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np
import mediapipe as mp
import cv2

# Enable GPU acceleration for MediaPipe if available
os.environ["MEDIAPIPE_USE_GPU"] = "true"

@dataclass
class FaceData:
    """Data class to hold face detection results"""
    bbox: List[float]  # [xmin, ymin, width, height]
    landmarks: List[Tuple[float, float]]  # [(x1,y1), (x2,y2), ...]
    confidence: float
    
    def copy(self):
        """Create a deep copy of the face data"""
        return FaceData(
            bbox=self.bbox.copy(),
            landmarks=self.landmarks.copy(),
            confidence=self.confidence
        )

class FaceProcessor:
    """
    MediaPipe-based face detection and tracking
    
    Features:
    - Runs in separate thread
    - Frame sampling to reduce CPU load
    - Smooth tracking with motion prediction
    - Early detection abandonment for overloaded conditions
    """
    
    def __init__(self, min_detection_confidence=0.3):
        # Initialize MediaPipe face detection
        self.mp_face_detection = mp.solutions.face_detection
        self.face_detector = self.mp_face_detection.FaceDetection(
            model_selection=0,  # 0 for close-range, 1 for far-range
            min_detection_confidence=min_detection_confidence
        )
        
        # Threading controls
        self.running = False
        self.processing_thread = None
        self.lock = threading.Lock()
        
        # Face tracking state
        self.current_face_data: Optional[FaceData] = None
        self.smoothing_factor = 0.4  # Lower = smoother but more latency
        self.last_process_time = 0
        self.min_process_interval = 0.2  # 5 FPS target for face detection
        
    def start(self):
        """Start the face processing thread"""
        if not self.running:
            self.running = True
            self.processing_thread = threading.Thread(
                target=self._processing_loop,
                daemon=True
            )
            self.processing_thread.start()
            
    def stop(self):
        """Stop the face processing thread"""
        self.running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=1.0)
            
    def get_current_face_data(self) -> Optional[FaceData]:
        """Thread-safe access to current face data"""
        with self.lock:
            return self.current_face_data.copy() if self.current_face_data else None
            
    def process_frame(self, frame: np.ndarray) -> Optional[FaceData]:
        """Process a single frame to detect faces"""
        if frame is None:
            return None
            
        # Convert to RGB for MediaPipe
        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        except Exception as e:
            print(f"ERROR: Frame conversion failed: {e}")
            return None
            
        try:
            results = self.face_detector.process(rgb_frame)
            
            if not results.detections:
                return None
                
            # Get the first face
            detection = results.detections[0]
            rel_bbox = detection.location_data.relative_bounding_box
            
            # Extract face landmarks
            try:
                landmarks = [(kp.x, kp.y) 
                            for kp in detection.location_data.relative_keypoints]
            except Exception as e:
                print(f"ERROR: Failed to extract landmarks: {e}")
                return None
            
            # Create face data with validation
            face_data = FaceData(
                bbox=[
                    max(0.0, min(1.0, rel_bbox.xmin)),
                    max(0.0, min(1.0, rel_bbox.ymin)),
                    max(0.0, min(1.0, rel_bbox.width)),
                    max(0.0, min(1.0, rel_bbox.height))
                ],
                landmarks=landmarks,
                confidence=detection.score[0]
            )
            
            return face_data
            
        except Exception as e:
            print(f"ERROR in face processing: {e}")
            return None
        
    def _smooth_face_data(self, new_data: FaceData):
        """Apply smoothing to face tracking data with minimal locking"""
        if self.current_face_data is None:
            # First face detection, just set it directly
            with self.lock:
                self.current_face_data = new_data
            return
            
        # Calculate smoothed values without holding the lock
        smoothed_bbox = []
        for i in range(4):
            current = self.current_face_data.bbox[i]  # Read once
            smoothed = (
                self.smoothing_factor * new_data.bbox[i] +
                (1 - self.smoothing_factor) * current
            )
            smoothed_bbox.append(smoothed)
            
        # Calculate smoothed landmarks without holding the lock
        smoothed_landmarks = []
        for i in range(len(new_data.landmarks)):
            current_x = self.current_face_data.landmarks[i][0]  # Read once
            current_y = self.current_face_data.landmarks[i][1]  # Read once
            
            x = (self.smoothing_factor * new_data.landmarks[i][0] +
                 (1 - self.smoothing_factor) * current_x)
            y = (self.smoothing_factor * new_data.landmarks[i][1] +
                 (1 - self.smoothing_factor) * current_y)
            smoothed_landmarks.append((x, y))
            
        # Create new face data object
        smoothed_data = FaceData(
            bbox=smoothed_bbox,
            landmarks=smoothed_landmarks,
            confidence=new_data.confidence
        )
        
        # Minimal lock time: just for the assignment
        with self.lock:
            self.current_face_data = smoothed_data
            
    def _processing_loop(self):
        """Main processing loop running in separate thread"""
        print("Starting face processing loop...")
        last_process_time = time.monotonic()
        
        while self.running:
            current_time = time.monotonic()
            
            # Get frame from camera
            frame = self.camera_manager.get_latest_frame()
            if frame is None:
                time.sleep(0.001)
                continue
                
            # Only process frame if enough time has passed (5 FPS)
            if current_time - last_process_time >= self.min_process_interval:
                # Process frame
                face_data = self.process_frame(frame)
                if face_data:
                    self._smooth_face_data(face_data)
                last_process_time = current_time
            
            # Small sleep to prevent CPU thrashing
            time.sleep(0.001)

    def update_scaler_crop(self, face_data):
        """Update ScalerCrop settings based on face data."""
        if face_data:
            # Calculate new ScalerCrop settings based on face_data
            # This is a placeholder for actual calculation logic
            new_scaler_crop_settings = self.calculate_scaler_crop_settings(face_data)
            # Update the camera's ScalerCrop settings
            self.camera_manager.update_scaler_crop_settings(new_scaler_crop_settings)

class CameraFaceProcessor(FaceProcessor):
    """Face processor that connects to our CameraManager"""
    
    def __init__(self, camera_manager, scaler_crop_controller, min_detection_confidence=0.3):
        super().__init__(min_detection_confidence)
        self.camera_manager = camera_manager
        self.scaler_crop_controller = scaler_crop_controller
        
    def _processing_loop(self):
        """Main processing loop running in separate thread"""
        last_process_time = time.monotonic()
        
        while self.running:
            current_time = time.monotonic()
            
            # Get frame from camera
            frame = self.camera_manager.get_latest_frame()
            if frame is None:
                time.sleep(0.001)
                continue
                
            # Only process frame if enough time has passed (5 FPS)
            if current_time - last_process_time >= self.min_process_interval:
                # Process frame
                face_data = self.process_frame(frame)
                if face_data:
                    self._smooth_face_data(face_data)
                    # Update ScalerCropController with new face data
                    self.scaler_crop_controller.update_target_crop(face_data)
                last_process_time = current_time
            
            # Small sleep to prevent CPU thrashing
            time.sleep(0.001) 