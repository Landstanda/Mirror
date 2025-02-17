import os
import time
import threading
import queue
import cv2
import numpy as np
import mediapipe as mp
from enum import Enum
from dataclasses import dataclass
from typing import Tuple, List, Optional
from picamera2 import Picamera2, Preview
from libcamera import Transform, controls
from collections import deque
from vosk import Model, KaldiRecognizer
import pyaudio
import json

# Suppress TF logs and enable GPU
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
os.environ["MEDIAPIPE_USE_GPU"] = "true"
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/usr/lib/aarch64-linux-gnu/qt5/plugins/platforms"
os.environ["QT_QPA_PLATFORM"] = "xcb"

class ZoomLevel(Enum):
    EYES = 1
    LIPS = 2
    FACE = 3
    WIDE = 4

@dataclass
class FaceData:
    bbox: List[float]  # [xmin, ymin, width, height]
    landmarks: List[Tuple[float, float]]
    confidence: float

class FrameBuffer:
    """Dedicated class for high-priority frame capture and buffering"""
    def __init__(self, buffer_size=3):
        self.frames = deque(maxlen=buffer_size)
        self.lock = threading.Lock()

    def add_frame(self, frame):
        with self.lock:
            self.frames.append(frame)

    def get_latest_frame(self):
        with self.lock:
            return self.frames[-1].copy() if self.frames else None

class CameraManager:
    def __init__(self):
        # Define focus rage constants first
        self.min_focus = 8.0  # Minimum focus position for makeup range
        self.max_focus = 12.5  # Maximum focus position for makeup range
        
        # Focus tuning parameters
        self.coarse_step = 0.1      # Step size for initial coarse search
        self.fine_step = 0.05       # Step size for fine-tuning
        self.coarse_delay = 0.2     # Delay after each coarse movement
        self.fine_delay = 0.3       # Delay after each fine movement
        self.fine_tune_range = 0.3  # How far back to search during fine-tuning
        
        # Initialize camera components
        self.picam2 = Picamera2()
        self.frame_buffer = FrameBuffer(buffer_size=2)
        self.configure_camera()
        self.stop_event = threading.Event()

    def _measure_focus(self, frame) -> float:
        """Measure the focus quality of an image using Laplacian variance"""
        if frame is None:
            return 0.0
        # Convert to grayscale if needed
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        else:
            gray = frame
        # Calculate Laplacian variance
        return cv2.Laplacian(gray, cv2.CV_64F).var()

    def find_best_focus(self):
        """Full focus range search - used at startup and for voice commands"""
        print("Searching for best focus...")
        
        # Get current position and initial focus score
        current_position = self.picam2.capture_metadata()['LensPosition']
        frame = self.get_latest_frame()
        best_focus_score = self._measure_focus(frame)
        best_position = current_position
        print(f"Starting at position {current_position:.1f}: focus score = {best_focus_score:.1f}")
        
        # First phase: Search forward in coarse increments
        consecutive_drops = 0
        max_drops = 2  # Number of consecutive drops before reversing
        
        for position in np.arange(current_position, self.max_focus + self.coarse_step, self.coarse_step):
            self.picam2.set_controls({"LensPosition": float(position)})
            time.sleep(self.coarse_delay)
            
            frame = self.get_latest_frame()
            focus_score = self._measure_focus(frame)
            print(f"Position {position:.1f}: focus score = {focus_score:.1f}")
            
            if focus_score > best_focus_score:
                best_focus_score = focus_score
                best_position = position
                consecutive_drops = 0
            else:
                consecutive_drops += 1
                if consecutive_drops >= max_drops:
                    print("Focus score dropping, reversing direction for fine-tuning")
                    break
        
        # Second phase: Fine-tune by searching backward in smaller increments
        fine_max = best_position + self.coarse_step
        fine_min = max(self.min_focus, best_position - self.fine_tune_range)
        
        for position in np.arange(fine_max, fine_min - self.fine_step, -self.fine_step):
            self.picam2.set_controls({"LensPosition": float(position)})
            time.sleep(self.fine_delay)
            
            frame = self.get_latest_frame()
            focus_score = self._measure_focus(frame)
            print(f"Fine tune {position:.2f}: focus score = {focus_score:.1f}")
            
            if focus_score > best_focus_score:
                best_focus_score = focus_score
                best_position = position
        
        # Set the best focus position
        print(f"Best focus found at position: {best_position:.1f} with score: {best_focus_score:.1f}")
        self.adjust_focus(best_position)
        return best_position

    def configure_camera(self):
        print("Configuring camera...")
        # Use video configuration for better performance
        video_config = self.picam2.create_video_configuration(
            {"size": (1100, 1100)},
            transform=Transform(hflip=False, vflip=True),
            buffer_count=4,  # Reduced for lower latency
            queue=True,     # Enable frame queueing
            controls={"NoiseReductionMode": controls.draft.NoiseReductionModeEnum.Off}  # Reduce processing overhead
        )
        print("Setting camera configuration...")
        self.picam2.configure(video_config)
        
        # Set high priority for the camera callback
        self.picam2.options["priority"] = 0  # Highest priority
        
        print("Setting camera controls...")
        # Initialize with middle of makeup range
        self.picam2.set_controls({
            "AfMode": 0,  # Manual mode
            "AfSpeed": 1,  # Fast
            "AfTrigger": 0,  # Stop
            "LensPosition": (self.min_focus + self.max_focus) / 2,  # Middle of makeup range
            "FrameDurationLimits": (16666, 16666),  # Target 60fps
            "NoiseReductionMode": 0  # Off
        })
        print("Camera configuration complete")

    def adjust_focus(self, position: float):
        """
        Adjust the manual focus position.
        Args:
            position: Focus position (0.0 to 32.0)
        """
        position = max(0.0, min(32.0, position))  # Clamp to valid range
        self.picam2.set_controls({"LensPosition": position})
        print(f"Focus position set to: {position}")

    def start(self):
        print("Starting camera preview...")
        try:
            self.picam2.start_preview(Preview.QTGL, x=10, y=0, width=1100, height=1100)
            print("Preview started successfully")
        except Exception as e:
            print(f"Error starting preview: {e}")
            
        print("Starting camera...")
        self.picam2.pre_callback = self._camera_callback
        self.picam2.start()
        print("Camera started successfully")

    def _camera_callback(self, request):
        """High priority callback for frame capture"""
        frame = request.make_array("main")
        if frame.ndim == 3 and frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
        self.frame_buffer.add_frame(frame)

    def get_latest_frame(self):
        return self.frame_buffer.get_latest_frame()

    def test_focus(self):
        """Test function to cycle through focus positions"""
        print("Starting focus test cycle...")
        try:
            for position in range(0, 33, 2):  # 0 to 32 in steps of 2
                print(f"\nSetting focus position to: {position}")
                self.picam2.set_controls({
                    "AfMode": 0,  # Manual mode
                    "LensPosition": float(position)
                })
                time.sleep(2)  # Wait 2 seconds at each position
        except Exception as e:
            print(f"Error during focus test: {e}")

    def stop(self):
        self.stop_event.set()
        self.picam2.stop()

class FaceTracker:
    def __init__(self, camera_manager: CameraManager):
        self.camera_manager = camera_manager
        self.mp_face_detection = mp.solutions.face_detection
        self.face_detector = self.mp_face_detection.FaceDetection(
            model_selection=0,
            min_detection_confidence=0.3
        )
        self.current_face_data: Optional[FaceData] = None
        self.smoothing_factor = 0.4
        self.stop_event = threading.Event()

    def start(self):
        self.tracking_thread = threading.Thread(target=self._tracking_loop, daemon=True)
        self.tracking_thread.start()

    def stop(self):
        self.stop_event.set()
        self.tracking_thread.join(timeout=1.0)

    def _tracking_loop(self):
        while not self.stop_event.is_set():
            frame = self.camera_manager.get_latest_frame()
            if frame is None:
                time.sleep(0.01)
                continue

            results = self.face_detector.process(frame)
            if results.detections:
                detection = results.detections[0]
                rel_box = detection.location_data.relative_bounding_box
                landmarks = [(kp.x, kp.y) for kp in detection.location_data.relative_keypoints]
                
                new_face_data = FaceData(
                    bbox=[rel_box.xmin, rel_box.ymin, rel_box.width, rel_box.height],
                    landmarks=landmarks,
                    confidence=detection.score[0]
                )
                
                self._smooth_face_data(new_face_data)
            
            time.sleep(0.2)  # Reduced from 50fps to 5fps tracking rate

    def _smooth_face_data(self, new_data: FaceData):
        if self.current_face_data is None:
            self.current_face_data = new_data
            return

        # Smooth bbox
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

class FocusController:
    def __init__(self, camera_manager: CameraManager):
        self.camera_manager = camera_manager
        self.last_focus_time = 0
        self.min_focus_interval = 2.0  # Minimum time between focus adjustments
        self.size_change_threshold = 0.20  # Increased threshold for distance changes
        self.focus_thread = None
        self.is_focusing = False
        self.stop_event = threading.Event()
        self.last_face_size = None
        self.current_lens_position = (self.camera_manager.min_focus + self.camera_manager.max_focus) / 2
        self.initial_focus_done = False

    def start(self):
        self.stop_event.clear()

    def stop(self):
        self.stop_event.set()
        if self.focus_thread and self.focus_thread.is_alive():
            self.focus_thread.join(timeout=1.0)

    def trigger_focus_if_needed(self, size_change: float):
        """Trigger focus on initial startup and significant face distance changes"""
        current_time = time.monotonic()
        if self.is_focusing or current_time - self.last_focus_time < self.min_focus_interval:
            return

        # Handle initial focus
        if not self.initial_focus_done:
            print("Initial face detection - performing focus search...")
            self.focus_thread = threading.Thread(target=self._focus_thread, daemon=True)
            self.focus_thread.start()
            self.last_focus_time = current_time
            return

        # Check if face distance changed significantly
        if abs(size_change) > self.size_change_threshold:
            print(f"Significant face distance change detected ({size_change:.2f}) - refocusing...")
            self.focus_thread = threading.Thread(target=self._focus_thread, daemon=True)
            self.focus_thread.start()
            self.last_focus_time = current_time

    def _focus_thread(self):
        """Run focus search"""
        self.is_focusing = True
        try:
            self.current_lens_position = self.camera_manager.find_best_focus()
            self.initial_focus_done = True
        finally:
            self.is_focusing = False

class DisplayProcessor:
    def __init__(self, camera_manager: CameraManager, face_tracker: FaceTracker):
        self.camera_manager = camera_manager
        self.face_tracker = face_tracker
        self.current_zoom = ZoomLevel.FACE
        self.stop_event = threading.Event()
        
        # Add tracking state variables
        self.current_crop = None  # [x, y, size]
        self.deadzone_factor = 0.10
        self.size_deadzone_factor = 0.1
        self.crop_smoothing = 0.05
        self.size_smoothing = 0.05
        
        # Zoom factors for different landmarks (larger number = more zoomed in)
        self.zoom_factors = {
            ZoomLevel.EYES: 1.5,   # Show 40% of face height for eyes
            ZoomLevel.LIPS: 1.7,   # Show 33% of face height for lips
            ZoomLevel.FACE: 1.0,   # Show full face
            ZoomLevel.WIDE: 0.6    # Show twice the face size
        }
        
        # Add focus controller
        self.focus_controller = FocusController(camera_manager)

    def start(self):
        self.display_thread = threading.Thread(target=self._display_loop, daemon=True)
        self.focus_controller.start()  # Start focus controller
        self.display_thread.start()

    def stop(self):
        self.stop_event.set()
        self.focus_controller.stop()  # Stop focus controller
        if hasattr(self, 'display_thread'):
            self.display_thread.join(timeout=1.0)

    def set_zoom_level(self, level: ZoomLevel):
        self.current_zoom = level

    def _display_loop(self):
        """Main display loop that processes and displays frames"""
        last_process_time = time.monotonic()
        skip_threshold = 1.0 / 60  # More aggressive frame skipping
        
        while not self.stop_event.is_set():
            frame = self.camera_manager.get_latest_frame()
            
            if frame is None or self.face_tracker.current_face_data is None:
                time.sleep(0.001)
                continue
            
            current_time = time.monotonic()
            # Process every frame unless we're severely behind
            if current_time - last_process_time < skip_threshold:
                processed_frame = self._process_frame(frame)
                if processed_frame is not None:
                    # Direct RGB to RGBA conversion without intermediate steps
                    processed_frame = cv2.cvtColor(processed_frame, cv2.COLOR_RGB2RGBA)
                    self.camera_manager.picam2.set_overlay(processed_frame)
            
            last_process_time = current_time
            # Minimal sleep to prevent CPU overuse while maintaining responsiveness
            time.sleep(0.001)

    def _get_landmark_center(self, face_data: FaceData, zoom_level: ZoomLevel) -> Tuple[float, float]:
        """Get the center point for a specific facial landmark"""
        landmarks = face_data.landmarks
        if zoom_level == ZoomLevel.EYES:
            # Average position between eyes (landmarks[0] is right eye, landmarks[1] is left eye)
            center_x = (landmarks[0][0] + landmarks[1][0]) / 2
            center_y = (landmarks[0][1] + landmarks[1][1]) / 2
        elif zoom_level == ZoomLevel.LIPS:
            # Use mouth landmark (landmarks[3])
            center_x = landmarks[3][0]
            center_y = landmarks[3][1]
        else:  # FACE
            # Use center of bounding box
            bbox = face_data.bbox
            center_x = bbox[0] + bbox[2] / 2
            center_y = bbox[1] + bbox[3] / 2
        
        return center_x, center_y

    def _process_frame(self, frame: np.ndarray) -> Optional[np.ndarray]:
        face_data = self.face_tracker.current_face_data
        if face_data is None:
            return None

        h, w = frame.shape[:2]
        bbox = face_data.bbox
        
        # Convert normalized coordinates to pixel coordinates
        face_x = int(bbox[0] * w)
        face_y = int(bbox[1] * h)
        face_w = int(bbox[2] * w)
        face_h = int(bbox[3] * h)

        # Get center point based on current zoom level
        center_x, center_y = self._get_landmark_center(face_data, self.current_zoom)
        center_x = int(center_x * w)
        center_y = int(center_y * h)

        # Calculate crop size based on zoom level (multiply by zoom factor to zoom in)
        zoom_factor = self.zoom_factors[self.current_zoom]
        base_size = max(face_w, face_h)
        target_size = int(base_size / zoom_factor)
        target_x = center_x - target_size // 2
        target_y = center_y - target_size // 2

        # Initialize current_crop if needed
        if self.current_crop is None:
            self.current_crop = [target_x, target_y, target_size]
            
        # Calculate how far the target has moved relative to current crop
        current_x, current_y, current_size = self.current_crop
        
        # Calculate the center points
        current_center_x = current_x + current_size // 2
        current_center_y = current_y + current_size // 2
        
        # Calculate movement as a fraction of the crop size
        dx = abs(current_center_x - center_x) / current_size
        dy = abs(current_center_y - center_y) / current_size
        size_change = abs(target_size - current_size) / current_size

        # Combined smoothing for both position and size
        if dx > self.deadzone_factor or dy > self.deadzone_factor or size_change > self.size_deadzone_factor:
            # Calculate new size with smoothing
            new_size = int(current_size + (target_size - current_size) * self.size_smoothing)
            
            # Calculate new position with smoothing, relative to the target center
            new_center_x = current_center_x + int((center_x - current_center_x) * self.crop_smoothing)
            new_center_y = current_center_y + int((center_y - current_center_y) * self.crop_smoothing)
            
            # Convert back to top-left coordinates
            new_x = new_center_x - new_size // 2
            new_y = new_center_y - new_size // 2
            
            # Update all values simultaneously
            self.current_crop = [
                max(0, min(w - new_size, new_x)),
                max(0, min(h - new_size, new_y)),
                new_size
            ]
            
            # Trigger focus adjustment if size changed significantly
            if size_change > self.size_deadzone_factor:
                self.focus_controller.trigger_focus_if_needed(size_change)

        # Extract the crop using current_crop values
        x, y, size = self.current_crop
        x = max(0, min(w - size, x))
        y = max(0, min(h - size, y))
        
        cropped = frame[y:y+size, x:x+size]
        return cv2.resize(cropped, (1500, 1500))

class VoiceController:
    def __init__(self, display_processor: DisplayProcessor, camera_manager: CameraManager):
        self.display_processor = display_processor
        self.camera_manager = camera_manager
        self.stop_event = threading.Event()
        
        # Initialize Vosk
        model_path = "vosk-model-small-en-us-0.15"
        self.model = Model(model_path)
        self.recognizer = KaldiRecognizer(self.model, 16000)
        
        # Initialize PyAudio
        self.mic = pyaudio.PyAudio()
        self.stream = self.mic.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=4000
        )
        
        # Command mapping
        self.commands = {
            "focus": self._trigger_focus,
            "eyes": self._zoom_to_eyes,
            "lips": self._zoom_to_lips,
            "face": self._zoom_to_face,
            "zoom out": self._zoom_out,
        }

    def _trigger_focus(self):
        """Trigger a focus search"""
        print("Voice command: triggering focus search")
        self.camera_manager.find_best_focus()

    def _zoom_to_eyes(self):
        """Zoom to eyes region"""
        print("Voice command: zooming to eyes")
        self.display_processor.set_zoom_level(ZoomLevel.EYES)

    def _zoom_to_lips(self):
        """Zoom to lips region"""
        print("Voice command: zooming to lips")
        self.display_processor.set_zoom_level(ZoomLevel.LIPS)

    def _zoom_to_face(self):
        """Zoom to full face"""
        print("Voice command: zooming to face")
        self.display_processor.set_zoom_level(ZoomLevel.FACE)

    def _zoom_out(self):
        """Zoom out to wide view"""
        print("Voice command: zooming out wide")
        self.display_processor.set_zoom_level(ZoomLevel.WIDE)

    def _voice_loop(self):
        self.stream.start_stream()
        
        while not self.stop_event.is_set():
            try:
                data = self.stream.read(4000, exception_on_overflow=False)
                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    text = result.get("text", "").lower()
                    
                    # Check for commands
                    if text:
                        print(f"Heard: {text}")
                        for command, action in self.commands.items():
                            if command in text:
                                action()
                                break
                                
            except Exception as e:
                print(f"Voice recognition error: {e}")
                continue

    def start(self):
        self.voice_thread = threading.Thread(target=self._voice_loop, daemon=True)
        self.voice_thread.start()

    def stop(self):
        self.stop_event.set()
        if hasattr(self, 'voice_thread'):
            self.voice_thread.join(timeout=1.0)
        if hasattr(self, 'stream'):
            self.stream.stop_stream()
            self.stream.close()
        if hasattr(self, 'mic'):
            self.mic.terminate()

class SmartMirror:
    def __init__(self):
        self.camera_manager = CameraManager()
        self.face_tracker = FaceTracker(self.camera_manager)
        self.display_processor = DisplayProcessor(self.camera_manager, self.face_tracker)
        self.voice_controller = VoiceController(self.display_processor, self.camera_manager)

    def start(self):
        print("Starting Smart Mirror...")
        self.camera_manager.start()
        self.face_tracker.start()
        self.display_processor.start()
        self.voice_controller.start()
        
        # Initial focus search after startup
        print("Waiting 2 seconds before initial focus search...")
        time.sleep(2)
        self.camera_manager.find_best_focus()
        print("Smart Mirror initialization complete")

    def stop(self):
        print("Stopping Smart Mirror...")
        self.voice_controller.stop()
        self.display_processor.stop()
        self.face_tracker.stop()
        self.camera_manager.stop()

if __name__ == "__main__":
    print("Checking environment...")
    # Check if DISPLAY is set
    display = os.environ.get('DISPLAY')
    if not display:
        print("WARNING: DISPLAY environment variable not set")
        os.environ['DISPLAY'] = ':0'
    else:
        print(f"DISPLAY is set to: {display}")
        
    print("Starting Smart Mirror application...")
    mirror = SmartMirror()
    try:
        mirror.start()
        print("Smart Mirror started successfully")
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nShutting down Smart Mirror...")
        mirror.stop()
    except Exception as e:
        print(f"Error running Smart Mirror: {e}")
        mirror.stop() 