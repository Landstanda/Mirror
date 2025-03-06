# MirrorAphrodite Implementation Instructions

This document provides detailed instructions for implementing the MirrorAphrodite smart mirror system, combining threading, multiprocessing, and async operations for optimal performance.

## 1. Core Components Overview

### 1.1 Project Structure
```
MirrorSystem/
├── core/
│   ├── camera_manager.py      # PiCamera2 management and frame capture
│   ├── face_processor.py      # MediaPipe face detection in separate process
│   ├── distance_sensor.py     # Async distance sensor control
│   ├── voice_controller.py    # Async voice command processing
│   ├── display_manager.py     # Display and zoom control
│   └── frame_buffer.py        # Thread-safe frame buffering
├── utils/
│   ├── async_helpers.py       # Async utility functions
│   ├── focus_mapper.py        # Distance-to-focus mapping
│   └── config.py             # System configuration
└── main.py                    # System orchestration
```

### 1.2 Data Flow Architecture
```
High Priority:
Camera Feed (Thread) → Frame Buffer (Ring Buffer) ←→ Display Manager
                                               ↘ Frame Sampler → Face Processor (Multiprocess)

Lower Priority:
Distance Sensor (Async) → Focus Control → Camera Manager
Voice Commands (Async) → Command Queue → System Controller
```

### 1.3 Performance Strategy
```
Priority Levels:
1. Display Pipeline (30 fps target)
   Camera → Buffer → Display
   
2. Focus Control (10 fps target)
   Distance Sensor → Focus Adjustment
   
3. Feature Detection (5-10 fps target)
   Sampled Frames → Face Processing
   
4. Voice Commands (As needed)
   Audio → Command Processing
```

## 2. Detailed Component Specifications

### 2.1 Camera System (Threading-based)
```python
class CameraManager:
    """
    Manages PiCamera2 operations using threading for optimal performance
    
    Key Features:
    - Runs in main thread with high priority
    - Maintains frame buffer
    - Handles focus control
    - Processes distance sensor input
    
    Optimization Features:
    - Direct memory mapping for frame buffer
    - Hardware-accelerated preview pipeline
    - Automatic frame dropping when system is overwhelmed
    - Dynamic resolution scaling based on system load
    
    Configuration:
    - Resolution: 1100x1100 (scalable)
    - Frame Rate: 30 fps target for display
    - Focus Range: 8.0-12.5
    - Manual focus mode
    - Zero-copy operation where possible
    """
    
    def __init__(self):
        self.picam2 = Picamera2()
        self.frame_buffer = RingBuffer(buffer_size=3)  # Changed to ring buffer
        self.focus_range = (8.0, 12.5)
        self.current_zoom = ZoomLevel.FACE
        self.frame_drop_threshold = 0.8  # Drop frames if buffer is 80% full
        
    def configure_camera(self):
        # Hardware-accelerated configuration
        video_config = self.picam2.create_video_configuration(
            buffer_count=4,
            queue=True,
            controls={"NoiseReductionMode": 0}  # Disable noise reduction for speed
        )
        
    def _camera_callback(self):
        # High-priority frame capture callback
        pass
```

### 2.2 Face Processing (Multiprocessing)
```python
class FaceProcessor:
    """
    MediaPipe face detection in separate process
    
    Optimization Features:
    - Frame sampling to reduce processing load
    - Early detection abandonment for overloaded conditions
    - GPU acceleration for MediaPipe when available
    - Landmark prediction for smoother tracking
    
    Processing Flow:
    1. Sample frames (reduce processing rate)
    2. Detect face and landmarks
    3. Predict movement for skipped frames
    4. Return results via queue
    """
    
    def __init__(self, num_workers=2):
        self.process_pool = ProcessPoolExecutor(max_workers=num_workers)
        self.frame_queue = multiprocessing.Queue(maxsize=4)
        self.result_queue = multiprocessing.Queue()
```

### 2.3 Distance Sensor Control (Async)
```python
class DistanceSensor:
    """
    Asynchronous distance sensor management
    
    Features:
    - Non-blocking operation with asyncio
    - Direct mapping to focus values
    - Continuous monitoring
    - 100ms sampling rate
    
    Hardware Setup:
    - GPIO Trigger Pin
    - GPIO Echo Pin
    - 3.3V power supply
    """
    
    def __init__(self, gpio_trigger, gpio_echo):
        self.trigger = gpio_trigger
        self.echo = gpio_echo
        self.running = False
```

### 2.4 Voice Control (Async)
```python
class VoiceController:
    """
    Asynchronous voice command processing
    
    Features:
    - Vosk keyword detection
    - Non-blocking command processing
    - Command queue management
    
    Commands:
    - "eye" -> ZoomLevel.EYES
    - "lips" -> ZoomLevel.LIPS
    - "face" -> ZoomLevel.FACE
    - "zoom out" -> ZoomLevel.WIDE
    """
    
    def __init__(self):
        self.model = Model(model_path)
        self.recognizer = KaldiRecognizer(self.model, 16000)
        self.command_queue = asyncio.Queue()
```

## 3. System Integration

### 3.1 Main System Controller
```python
class MirrorSystem:
    """
    Main system orchestration
    
    Responsibilities:
    - Component initialization
    - Inter-component communication
    - System lifecycle management
    - Resource coordination
    """
    
    def __init__(self):
        self.camera = CameraManager()
        self.face_processor = FaceProcessor()
        self.distance_sensor = DistanceSensor(TRIGGER_PIN, ECHO_PIN)
        self.voice_controller = VoiceController()
        self.display = DisplayManager()
```

### 3.2 Configuration Parameters
```python
class Config:
    """
    System configuration parameters
    
    Display:
    - CAMERA_RESOLUTION = (1100, 1100)
    - FRAME_BUFFER_SIZE = 3
    
    Focus:
    - FOCUS_RANGE = (8.0, 12.5)
    - DISTANCE_SENSOR_INTERVAL = 0.1
    
    Audio:
    - VOICE_SAMPLE_RATE = 16000
    
    Processing:
    - ML_WORKERS = 2
    """
```

## 4. Implementation Sequence

### Phase 1: Core Camera System
1. Implement CameraManager
   - Set up PiCamera2 configuration
   - Implement frame buffer
   - Configure focus control
   - Test basic display output

### Phase 2: Face Processing
1. Implement FaceProcessor
   - Set up multiprocessing pools
   - Implement frame queues
   - Add MediaPipe integration
   - Test face detection performance

### Phase 3: Distance Sensor
1. Implement DistanceSensor
   - Set up GPIO connections
   - Create async reading loop
   - Implement focus mapping
   - Test sensor accuracy

### Phase 4: Voice Control
1. Implement VoiceController
   - Set up Vosk recognition
   - Create command processing
   - Implement zoom control
   - Test command accuracy

### Phase 5: System Integration
1. Implement MirrorSystem
   - Connect all components
   - Test system performance
   - Optimize resource usage
   - Fine-tune parameters

## 5. Performance Considerations

### 5.1 Priority Management
- Camera thread: Real-time priority (SCHED_FIFO)
- Display update: High priority
- Face processing: Normal priority, limited CPU share
- Sensor/Voice: Background priority

### 5.2 Buffer Management
- Ring buffer implementation for zero-copy operations
- Frame dropping strategy:
  * Drop ML processing first
  * Reduce face detection frequency
  * Maintain display pipeline at all costs
- Adaptive processing based on system load

### 5.3 Resource Usage
- CPU Core Allocation:
  * Core 0: Camera and display pipeline
  * Core 1: Face processing
  * Core 2: Distance sensor and focus control
  * Core 3: Voice processing and system management
- Memory Management:
  * Pre-allocated buffers
  * Minimal copying
  * Direct memory access where possible

### 5.4 Thermal Management
- Monitor CPU temperature
- Implement thermal throttling:
  1. Reduce face processing frequency
  2. Increase frame dropping threshold
- Ensure proper cooling solution

## 6. Error Handling and Recovery

### 6.1 Component Failures
- Implement graceful degradation
- Add automatic component restart
- Include error logging

### 6.2 Resource Exhaustion
- Monitor memory usage
- Manage process pools
- Prevent buffer overflows

### 6.3 Performance Degradation Handling
- Monitor frame rate and processing times
- Implement graceful degradation:
  1. Reduce face processing frequency
  2. Simplify face detection model
  3. Increase frame dropping threshold
- Auto-recovery when load reduces

## 7. Testing and Validation

### 7.1 Component Testing
1. Test each component individually
2. Verify component interfaces
3. Measure performance metrics

### 7.2 Integration Testing
1. Test component interactions
2. Verify system performance
3. Measure end-to-end latency

### 7.3 User Experience Testing
1. Test voice command reliability
2. Verify focus adjustment accuracy
3. Measure display update smoothness

## 8. Optimization Guidelines

### 8.1 Performance Optimization
1. Profile CPU usage
2. Monitor memory allocation
3. Measure frame processing time
4. Track command response time

### 8.2 Resource Optimization
1. Adjust buffer sizes
2. Fine-tune worker counts
3. Optimize frame processing
4. Balance resource usage

## 9. Raspberry Pi 5 Specific Optimizations

### 9.1 Hardware Utilization
- Enable VideoCore GPU for camera pipeline
- Use hardware JPEG decoder
- Utilize DMA for memory transfers
- Enable OpenGL ES acceleration for display

### 9.2 System Configuration
```bash
# Add to /boot/config.txt
gpu_mem=256
over_voltage=2
arm_freq=2400
```

### 9.3 Operating System Tuning
```bash
# Real-time priorities for camera process
sudo chrt -f -p 99 $CAMERA_PID

# Disable CPU throttling
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Optimize SD card performance
sudo hdparm -J /dev/mmcblk0
```

### 9.4 Process Priority Management
```python
def set_process_priorities():
    """Set process priorities for optimal performance"""
    # Camera and display processes
    os.sched_setaffinity(0, {0})  # Pin to CPU 0
    os.sched_param(os.SCHED_FIFO, 99)
    
    # Face detection process
    os.sched_setaffinity(face_pid, {1})  # Pin to CPU 1
    os.nice(10)  # Lower priority
    
    # Sensor and voice processes
    os.sched_setaffinity(sensor_pid, {2, 3})  # Allow floating
    os.nice(15)  # Lowest priority
```

This implementation guide provides a structured approach to building the MirrorAphrodite system. Follow the phases in sequence, ensuring each component is thoroughly tested before moving to the next phase. Pay special attention to performance considerations and error handling throughout the implementation process. 


Bottlenecks and Issues
  Frame Buffer Copying:
    - Every frame is copied twice (on add and retrieve)
    - Unnecessary memory operations slowing down pipeline
  Low Processing Rates:
    - Face and display processors locked at 5 FPS
    - Display updates tied to face detection rate
    - No need for display to wait for face detection
  Synchronization Overhead:
    - Too many locks and thread synchronization points
    - Excessive thread creation and management
  Camera Configuration:
    - Buffer count of 4 might be too high
    - Noise reduction disabled but other camera optimizations missing
  Display Processing:
    - Converting frames to RGBA for overlay is expensive
    - Software cropping fallback is inefficient

    (remember to remove laden see tracking code from the camera manager: it's 39 lines of code, tracking the latency of every frame and printing it every second.. Lines: 8 - 10, # Performance monitoring 29 - 35, calc & store then def print_performance 143 - 171 minuse 154 & 155)

### Latency Tests
  Baseline:   
    - Camera Performance: 31.3 FPS, Latency: 10.3ms
    - Camera Performance: 30.5 FPS, Latency: 10.7ms
    - Camera Performance: 29.7 FPS, Latency: 11.2ms
    - Camera Performance: 29.6 FPS, Latency: 11.0ms
   Apprearance: Lagging behind, not smooth

  No Double Copy:
    - Camera Performance: 31.4 FPS, Latency: 10.3ms
    - Camera Performance: 30.4 FPS, Latency: 10.5ms
    - Camera Performance: 31.2 FPS, Latency: 10.7ms
    - Camera Performance: 30.0 FPS, Latency: 11.1ms
   Appearance: Not really any better noticably

  Display Processor De-couple from feed
    - Camera Performance: 32.9 FPS, Latency: 10.6ms
    - Camera Performance: 33.3 FPS, Latency: 10.2ms
    - Camera Performance: 32.8 FPS, Latency: 10.3ms
    - Camera Performance: 32.9 FPS, Latency: 10.2ms
   Appearance: More FPS by a lot. Little more live; still room to grow
   **PROBLEM** --> Display distorts (narrows) Need ratio fixture

  Fix the distortion problem (which isn't necessarily be part of this optimization process but i think in the process the latency decreased enough that it should be noted.)
    - Camera Performance: 41.7 FPS, Latency: 7.8ms
    - Camera Performance: 40.9 FPS, Latency: 8.0ms
    - Camera Performance: 40.7 FPS, Latency: 8.2ms
    - Camera Performance: 40.7 FPS, Latency: 7.8ms
   Appearance: It's going pretty great now, but since we got the less to let's keep optimizing.

   Over synched & threaded
    - Camera Performance: 41.3 FPS, Latency: 7.8ms
    - Camera Performance: 41.4 FPS, Latency: 8.0ms
    - Camera Performance: 41.8 FPS, Latency: 7.7ms
    - Camera Performance: 41.1 FPS, Latency: 8.0ms
   Appearance: I think a bit more live!
  
  Buffer Reduction
    - Camera Performance: 26.0 FPS, Latency: 7.6ms
    - Camera Performance: 29.1 FPS, Latency: 6.5ms
    - Camera Performance: 28.8 FPS, Latency: 6.5ms
    - Camera Performance: 28.4 FPS, Latency: 6.3ms
   Appearance: Mirror like!!

  Color Correction
    - Camera Performance: 30.1 FPS, Latency: 2.3ms
    - Camera Performance: 30.1 FPS, Latency: 2.3ms
    - Camera Performance: 29.9 FPS, Latency: 2.3ms
    - Camera Performance: 29.7 FPS, Latency: 2.2ms
   Appearance: Phenomenal..!!

To-Do List
1. Simplify Smoothing System
  - Remove spring-damper physics simulation
  - Implement simple linear interpolation between positions
  - Remove velocity and acceleration tracking
2. Remove Motion Prediction
  - Remove predictive motion calculations
  - Implement simple reactive tracking
  - Use basic movement thresholds
3. Simplify Zoom Levels
  - Remove complex zoom factor calculations
  - Implement fixed ratios based on face bbox
  - Simplify zoom level state management
4. Simplify Stability Logic
  - Implement single, simple threshold for movement
  - Remove complex distance calculations
  - Create straightforward stability check
5. Simplify Eye Centering
  - Always use midpoint between eyes
  - Remove complex eye-selection logic
  - Implement simple center point calculation
6