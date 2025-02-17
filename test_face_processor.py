import os
import time
import cv2
import numpy as np
from core.camera_manager import CameraManager
from core.face_processor import CameraFaceProcessor

# Set up Qt environment variables
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/usr/lib/aarch64-linux-gnu/qt5/plugins/platforms"
os.environ["QT_QPA_PLATFORM"] = "xcb"

def draw_face_data(frame, face_data):
    """Draw face detection visualization on frame"""
    if face_data is None:
        return None
    
    h, w = frame.shape[:2]
    bbox = face_data.bbox
    
    # Create a transparent overlay
    overlay = np.zeros((h, w, 4), dtype=np.uint8)
    
    # Convert normalized coordinates to pixel coordinates
    x = int(bbox[0] * w)
    y = int(bbox[1] * h)
    width = int(bbox[2] * w)
    height = int(bbox[3] * h)
    
    # Draw bounding box (green with alpha)
    cv2.rectangle(overlay, (x, y), (x + width, y + height), (0, 255, 0, 255), 2)
    
    # Draw landmarks (red with alpha)
    for lm in face_data.landmarks:
        lm_x = int(lm[0] * w)
        lm_y = int(lm[1] * h)
        cv2.circle(overlay, (lm_x, lm_y), 5, (0, 0, 255, 255), -1)
    
    # Draw confidence text
    cv2.putText(overlay, f"Conf: {face_data.confidence:.2f}", 
                (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 
                0.5, (0, 255, 0, 255), 2)
    
    return overlay

def main():
    # Initialize camera and face processor
    camera = CameraManager()
    face_processor = CameraFaceProcessor(camera)
    
    try:
        # Start both components
        print("Starting camera and face processor...")
        camera.start()
        face_processor.start()
        
        # Give camera time to initialize
        time.sleep(2)
        
        print("Running. Press Ctrl+C to quit.")
        print("You should see:")
        print("1. Camera feed in a window")
        print("2. Green rectangle around detected faces")
        print("3. Red dots for facial landmarks")
        print("4. Confidence score above the face")
        
        last_overlay_time = 0
        overlay_interval = 0.2  # Update overlay at 5fps
        
        # Main loop - update overlay with face detection
        while True:
            current_time = time.monotonic()
            
            # Only update overlay at specified interval
            if current_time - last_overlay_time >= overlay_interval:
                face_data = face_processor.get_current_face_data()
                if face_data:
                    frame = camera.get_latest_frame()
                    if frame is not None:
                        overlay = draw_face_data(frame, face_data)
                        if overlay is not None:
                            camera.picam2.set_overlay(overlay)
                last_overlay_time = current_time
            
            # Small sleep to prevent CPU thrashing
            time.sleep(0.001)
                
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        # Clean up
        print("Stopping camera and face processor...")
        face_processor.stop()
        camera.stop()

if __name__ == "__main__":
    main() 