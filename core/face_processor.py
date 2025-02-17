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
        """
        Process a single frame to detect faces
        Returns FaceData if face detected, None otherwise
        """
        if frame is None:
            return None
            
        # Convert to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_detector.process(rgb_frame)
        
        if not results.detections:
            return None
            
        # Get the first (most prominent) face
        detection = results.detections[0]
        rel_bbox = detection.location_data.relative_bounding_box
        
        # Extract face landmarks
        landmarks = [(kp.x, kp.y) 
                    for kp in detection.location_data.relative_keypoints]
        
        # Create face data
        face_data = FaceData(
            bbox=[rel_bbox.xmin, rel_bbox.ymin, 
                  rel_bbox.width, rel_bbox.height],
            landmarks=landmarks,
            confidence=detection.score[0]
        )
        
        return face_data
        
    def _smooth_face_data(self, new_data: FaceData):
        """Apply smoothing to face tracking data"""
        if self.current_face_data is None:
            with self.lock:
                self.current_face_data = new_data
            return
            
        # Smooth bounding box
        with self.lock:
            for i in range(4):
                self.current_face_data.bbox[i] = (
                    self.smoothing_factor * new_data.bbox[i] +
                    (1 - self.smoothing_factor) * self.current_face_data.bbox[i]
                )
                
            # Smooth landmarks
            for i in range(len(new_data.landmarks)):
                x = (self.smoothing_factor * new_data.landmarks[i][0] +
                     (1 - self.smoothing_factor) * self.current_face_data.landmarks[i][0])
                y = (self.smoothing_factor * new_data.landmarks[i][1] +
                     (1 - self.smoothing_factor) * self.current_face_data.landmarks[i][1])
                self.current_face_data.landmarks[i] = (x, y)
                
            # Update confidence
            self.current_face_data.confidence = new_data.confidence
            
    def _processing_loop(self):
        """Main processing loop running in separate thread"""
        while self.running:
            current_time = time.monotonic()
            
            # Limit processing rate
            if current_time - self.last_process_time < self.min_process_interval:
                time.sleep(0.001)  # Small sleep to prevent CPU thrashing
                continue
                
            # Get frame from camera
            frame = self._get_frame_for_processing()
            if frame is None:
                continue
                
            # Process frame
            face_data = self.process_frame(frame)
            if face_data:
                self._smooth_face_data(face_data)
                
            self.last_process_time = current_time
            
    def _get_frame_for_processing(self) -> Optional[np.ndarray]:
        """
        Get a frame for processing - this method should be overridden
        by the main application to provide frames from the camera
        """
        # This will be connected to the camera manager later
        return None

class CameraFaceProcessor(FaceProcessor):
    """Face processor that connects to our CameraManager"""
    
    def __init__(self, camera_manager, min_detection_confidence=0.3):
        super().__init__(min_detection_confidence)
        self.camera_manager = camera_manager
        
    def _get_frame_for_processing(self) -> Optional[np.ndarray]:
        """Get frame from camera manager for processing"""
        return self.camera_manager.get_latest_frame() 