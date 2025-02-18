import os
import cv2
import numpy as np
from core.camera_manager import CameraManager
from core.face_processor import CameraFaceProcessor
import time

# Set up environment variables
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"  # Reduce TensorFlow logging
os.environ["MEDIAPIPE_USE_GPU"] = "true"
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/usr/lib/aarch64-linux-gnu/qt5/plugins/platforms"
os.environ["QT_QPA_PLATFORM"] = "xcb"

def draw_debug_overlay(frame, face_data):
    """Draw debug visualization on frame"""
    if face_data is None or frame is None:
        return frame
    
    h, w = frame.shape[:2]
    debug_frame = frame.copy()
    
    # Draw bounding box
    bbox = face_data.bbox
    x = int(bbox[0] * w)
    y = int(bbox[1] * h)
    width = int(bbox[2] * w)
    height = int(bbox[3] * h)
    cv2.rectangle(debug_frame, (x, y), (x + width, y + height), (0, 255, 0), 2)
    
    # Draw landmarks with labels
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255)]
    labels = ['Right Eye', 'Left Eye', 'Nose', 'Mouth', 'Right Ear', 'Left Ear']
    
    # Only draw available landmarks
    for i, (lm_x, lm_y) in enumerate(face_data.landmarks):
        if i < len(colors):  # Make sure we have a color for this landmark
            px = int(lm_x * w)
            py = int(lm_y * h)
            cv2.circle(debug_frame, (px, py), 5, colors[i], -1)
            cv2.putText(debug_frame, labels[i], (px + 5, py - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, colors[i], 2)
    
    # Draw confidence
    cv2.putText(debug_frame, f"Confidence: {face_data.confidence:.2f}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    
    return debug_frame

def main():
    print("\nFace Detection Debug Test")
    print("------------------------")
    
    # Initialize components with debug logging
    print("\nInitializing camera...")
    camera = CameraManager()
    
    print("\nInitializing face processor...")
    face_processor = CameraFaceProcessor(camera, min_detection_confidence=0.2)  # Lower confidence threshold for testing
    
    try:
        print("\nStarting camera...")
        camera.start()
        time.sleep(1)  # Wait for camera
        
        print("\nStarting face processor...")
        face_processor.start()
        time.sleep(1)  # Wait for processor
        
        print("\nDebug Test Running")
        print("------------------")
        print("Press Ctrl+C to stop the test")
        
        # Performance tracking
        frame_count = 0
        face_count = 0
        start_time = time.monotonic()
        last_stats_time = start_time
        last_frame_check = start_time
        
        while True:
            frame = camera.get_latest_frame()
            current_time = time.monotonic()
            
            # Check frame acquisition every second
            if current_time - last_frame_check >= 1.0:
                if frame is not None:
                    print(f"\nFrame Info:")
                    print(f"- Shape: {frame.shape}")
                    print(f"- Type: {frame.dtype}")
                    print(f"- Range: [{frame.min()}, {frame.max()}]")
                else:
                    print("WARNING: Received None frame")
                last_frame_check = current_time
            
            if frame is not None:
                frame_count += 1
                
                # Get face data and log the result
                print("\nAttempting face detection...")
                try:
                    print("DEBUG: Before get_current_face_data call")
                    face_data = face_processor.get_current_face_data()
                    print("DEBUG: After get_current_face_data call")
                    
                    if face_data is None:
                        print("DEBUG: Face data is None, checking processor state:")
                        print(f"- Face processor running: {face_processor.running}")
                        print(f"- Processing thread alive: {face_processor.processing_thread and face_processor.processing_thread.is_alive()}")
                    else:
                        print("DEBUG: Face data retrieved successfully")
                except Exception as e:
                    print(f"ERROR in face detection: {e}")
                    import traceback
                    traceback.print_exc()
                    face_data = None
                
                if face_data is not None:
                    face_count += 1
                    print(f"\nFace Detected!")
                    print(f"- Confidence: {face_data.confidence:.2f}")
                    print(f"- Bounding Box: {[f'{x:.2f}' for x in face_data.bbox]}")
                    print(f"- Number of Landmarks: {len(face_data.landmarks)}")
                    
                    # Create debug visualization
                    try:
                        debug_frame = draw_debug_overlay(frame, face_data)
                        if debug_frame is not None:
                            # Convert to RGBA for overlay
                            debug_rgba = cv2.cvtColor(debug_frame, cv2.COLOR_BGR2RGBA)
                            camera.picam2.set_overlay(debug_rgba)
                            print("Debug overlay applied successfully")
                        else:
                            print("WARNING: Debug overlay creation failed")
                    except Exception as e:
                        print(f"ERROR: Failed to create/apply debug overlay: {e}")
                else:
                    print("No face detected in this frame")
                
                # Print performance stats every 5 seconds
                if current_time - last_stats_time >= 5.0:
                    elapsed = current_time - start_time
                    fps = frame_count / elapsed
                    face_rate = face_count / elapsed
                    
                    print(f"\nPerformance Stats:")
                    print(f"- Total Frames: {frame_count}")
                    print(f"- Faces Detected: {face_count}")
                    print(f"- Average FPS: {fps:.1f}")
                    print(f"- Face Detection Rate: {face_rate:.1f}/s")
                    print(f"- Detection Success Rate: {(face_count/frame_count)*100:.1f}%")
                    
                    # Reset counters
                    frame_count = 0
                    face_count = 0
                    start_time = current_time
                    last_stats_time = current_time
            
            time.sleep(0.01)  # Small sleep to prevent CPU thrashing
            
    except KeyboardInterrupt:
        print("\nTest stopped by user")
    finally:
        print("\nCleaning up...")
        face_processor.stop()
        camera.stop()
        print("Test complete")

if __name__ == "__main__":
    main() 