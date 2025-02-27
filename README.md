# MirrorAphrodite

A smart mirror application for Raspberry Pi that uses the Arducam 64MP Hawkeyes camera and a distance sensor and a round monitor to at as a next generation digital vanity mirror. Features face tracking, voice commands, and automatic focus adjustment.

## Core Components Overview

### Primary Classes
MirrorSystem/
├── core/
│   ├── camera_manager.py      # PiCamera2 management and frame capture
│   ├── face_processor.py      # MediaPipe face detection in separate thread
│   ├── distance_sensor.py     # Async distance sensor control
│   ├── voice_controller.py    # Async voice command processing
│   ├── display_processor.py   # Display and zoom control with smooth tracking
│   ├── frame_buffer.py        # High-performance thread-safe frame buffering
│   └── async_helper.py        # Async task scheduling and thread management
├── tests/
│   ├── test_frame_buffer.py   # Frame buffer validation
│   ├── test_async_helper.py   # Async helper performance testing
│   ├── test_display_processor.py # Display and tracking testing
│   ├── test_face_processor.py # Face detection testing
│   ├── test_voice_control.py  # Voice command testing
│   └── test_distance_sensor.py # Distance sensor testing
└── main.py                    # System orchestration

### System Architecture

#### Frame Processing Pipeline
```
Camera Feed (60 FPS) → Frame Buffer (3-frame ring) → Async Processing
                                                  ↳ Face Detection (5 FPS)
                                                  ↳ Display Processing (30 FPS)
```

#### Performance Components

1. **Camera Manager** (`core/camera_manager.py`):
   - Hardware-accelerated frame capture at 60 FPS
   - Configurable preview modes (QTGL, QT, NULL)
   - Manual focus control with range 8.0-12.5
   - Async frame processing with priority scheduling
   - Efficient frame conversion and buffering
   - Hardware-optimized camera configuration
   - Automatic noise reduction and frame rate control

2. **Frame Buffer** (`core/frame_buffer.py`):
   - Thread-safe ring buffer for frame storage
   - Zero-copy frame retrieval for performance
   - Automatic buffer size management
   - Efficient frame access patterns

3. **Async Helper** (`core/async_helper.py`):
   - Priority-based task scheduling
   - Thread pool for CPU-intensive tasks
   - Non-blocking operation queues
   - Resource cleanup and management

4. **Face Processor** (`core/face_processor.py`):
   - MediaPipe-based face detection
   - Efficient 5 FPS processing rate
   - Motion prediction and smoothing
   - Thread-safe face data management
   - Configurable detection confidence
   - Early detection abandonment for performance
   - Smooth landmark tracking

5. **Display Processor** (`core/display_processor.py`):
   - Smooth tracking with deadzone
   - Multiple zoom levels (eyes, lips, face, wide)
   - Motion prediction
   - Efficient frame processing
   - Configurable smoothing factors
   - Smart frame skipping
   - Adaptive zoom transitions

6. **Distance Sensor** (`core/distance_sensor.py`):
   - Async ultrasonic sensor control
   - Direct focus mapping (20cm - 150cm range)
   - 5Hz sampling rate
   - Thread-safe distance measurements
   - Linear focus interpolation
   - Configurable GPIO management
   - Automatic timeout handling

7. **Voice Controller** (`core/voice_controller.py`):
   - Vosk-based speech recognition
   - Async command processing
   - Configurable command mapping
   - Thread-safe audio handling
   - Efficient audio buffering
   - Command queue management
   - Resource cleanup on shutdown

#### Performance Optimizations

1. **Frame Rate Management**:
   - Camera capture: 60 FPS
   - Display processing: 30 FPS
   - Face detection: 5 FPS
   - Async task scheduling for optimal CPU usage

2. **Thread Priority**:
   - Camera thread: Highest priority
   - Display processing: Medium priority
   - Face detection: Lower priority
   - Background tasks: Lowest priority

3. **Memory Management**:
   - Ring buffer to prevent memory growth
   - Frame dropping under high load
   - Efficient frame copying strategies
   - Resource cleanup on shutdown

### Data Flow Architecture

```
                                    ┌─────────────────┐
                                    │  Voice Commands  │
                                    │     (Async)     │
                                    └────────┬────────┘
                                             │
┌─────────────┐    ┌──────────────┐    ┌────▼─────┐
│Camera Feed   │──→ │Frame Buffer  │←─→ │Command   │
│(60 FPS)     │    │(3-frame ring)│    │Queue     │
└─────┬───────┘    └──────┬───────┘    └────┬─────┘
      │                   │                  │
      │             ┌─────▼──────┐     ┌────▼─────┐
      │             │Face Process │     │System    │
      │             │(5 FPS)      │     │Controller│
      │             └─────┬───────┘     └────┬─────┘
┌─────▼───────┐          │                   │
│Distance     │          │                   │
│Sensor (5Hz) │    ┌─────▼───────┐          │
└─────┬───────┘    │Display      │←─────────┘
      │            │Process(30FPS)│
      │            └─────┬────────┘
      │                  │
      └──→ Focus ←───────┘
           Control

Key Data Flows:
1. Camera → Frame Buffer:
   - Raw frames at 60 FPS
   - Hardware-accelerated capture
   - Async frame processing

2. Frame Buffer → Processors:
   - Thread-safe frame distribution
   - Zero-copy frame access
   - Priority-based scheduling

3. Face Processor → Display:
   - Face detection results at 5 FPS
   - Landmark coordinates
   - Confidence scores
   - Smoothed tracking data

4. Distance Sensor → Focus:
   - Distance measurements at 5Hz
   - Focus mapping calculations
   - Async focus adjustments

5. Voice → Command Queue:
   - Speech recognition results
   - Command validation
   - Async command processing

6. System Controller:
   - Component coordination
   - Resource management
   - State synchronization
   - Error handling
```

### Performance Considerations

The system is optimized for real-time performance while maintaining stability:

#### Memory Management
- Frame Buffer uses a ring buffer to prevent memory growth
- Zero-copy frame access where possible
- Explicit garbage collection for large objects
- Memory-mapped file operations for configuration

#### CPU Optimization
- Hardware-accelerated video capture (V4L2)
- Thread pool for CPU-intensive operations
- Workload distribution across cores
- Minimal lock contention in critical paths

#### I/O Efficiency
- Async I/O for sensor readings
- Batched command processing
- Buffered logging
- Prioritized task scheduling

#### Latency Control
- Face detection rate limited to 5 FPS
- Display updates capped at 30 FPS
- Adaptive frame dropping under load
- Background task throttling

#### Resource Limits
- Maximum frame buffer size: 3 frames
- Thread pool size: CPU cores - 1
- Command queue capacity: 100 items
- Log rotation: 10MB per file

## Installation Guide

### System Requirements (Install via apt):
```bash
# Core system libraries
sudo apt update && sudo apt upgrade
sudo apt install -y \
    python3-pip python3-venv \
    python3-opencv python3-pyqt5 python3-picamera2 \
    libportaudio2 portaudio19-dev \
    libatlas-base-dev \
    libqt5gui5 \
    libcamera-dev \
    python3-libcamera \
    python3-xlib

# Make sure user is in correct groups
sudo usermod -a -G audio,video,input $USER
```

### Python Environment Setup:
```bash
# Create and activate virtual environment with system packages
cd ~/MirrorAphrodite
python3 -m venv venv --system-site-packages
source venv/bin/activate
```

### Python Packages (Install via pip in virtual environment):
```bash
# Install required Python packages
pip install \
    mediapipe \
    vosk \
    pyaudio \
    numpy \
    sounddevice \
    pynput
```

### Voice Recognition Setup:
```bash
# Create directory for Vosk model
mkdir -p ~/.vosk/models
cd ~/.vosk/models

# Download and extract Vosk model
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip
mv vosk-model-small-en-us vosk-model-small-en-us
```

### Arducam 64MP Camera Setup:
```bash
# Download and run the Arducam installation script
wget -O install_pivariety_pkgs.sh https://github.com/ArduCAM/Arducam-Pivariety-V4L2-Driver/releases/download/install_script/install_pivariety_pkgs.sh
chmod +x install_pivariety_pkgs.sh

# Install camera packages
./install_pivariety_pkgs.sh -p libcamera_dev
./install_pivariety_pkgs.sh -p libcamera_apps

# Configure the camera
# Add the following line to /boot/firmware/config.txt:
echo -e "\n[all]\ndtoverlay=arducam-64mp,cam0" | sudo tee -a /boot/firmware/config.txt

# Reboot the system
sudo reboot
```

### Important Notes:
1. **System vs Virtual Environment**:
   - Some packages (opencv, picamera2, libcamera) are better installed via apt
   - Other packages (mediapipe, vosk) work better when installed via pip in the virtual environment
   - Using `--system-site-packages` allows the virtual environment to access system-installed Python packages

2. **Dependencies Hierarchy**:
   - Install system packages first
   - Create virtual environment
   - Install Python packages in virtual environment

3. **Hardware Setup**:
   - For Arducam 64MP Hawkeyes camera:
     - Connect the camera to the Raspberry Pi's camera port
     - Make sure the camera ribbon cable is properly seated
     - After installation and reboot, verify camera detection with `libcamera-hello`
   - Microphone must be properly connected and recognized
   - User must be in the correct groups (audio, video, input)

4. **Running the Applications**:
   ```bash
   # Always activate virtual environment first
   source venv/bin/activate

   # Run dictation
   python3 dictation.py

   # Run mirror application
   python3 a-mirror2.py
   ```

5. **Troubleshooting**:
   - If pynput fails: ensure python3-xlib is installed
   - If camera fails: 
     - Check camera connection and ribbon cable
     - Verify config.txt has the correct dtoverlay entry
     - Run `libcamera-hello` to test camera detection
     - Check camera permissions with `ls -l /dev/video*`
   - If audio fails: check microphone connection and audio group membership
   - If permissions fail: logout and login again after adding groups

6. **Camera Features**:
   - The mirror application supports voice commands:
     - "focus" - triggers autofocus
     - "eyes" - zooms to eye region
     - "lips" - zooms to lip region
     - "face" - zooms to full face
     - "zoom out" - zooms out to wide view
   - Automatic focus adjustment based on face distance
   - Smooth tracking and zooming

### Troubleshooting

#### Video Feed Issues
- **Jerky Video**: Check CPU usage and reduce face detection frequency if needed
- **Delayed Feed**: Verify frame buffer size and consider reducing it
- **Black Screen**: Ensure camera permissions and V4L2 driver is loaded
- **Low FPS**: Monitor system temperature and check for thermal throttling

#### Face Detection Problems
- **Missed Faces**: Adjust confidence threshold in configuration
- **Slow Tracking**: Increase face detection frequency if CPU allows
- **False Positives**: Update MediaPipe model or adjust minimum detection size
- **Tracking Lag**: Check face processor thread priority

#### Focus Issues
- **Hunting Focus**: Adjust focus smoothing parameters
- **Wrong Distance**: Calibrate distance sensor offset
- **Slow Response**: Check distance sensor sampling rate
- **Focus Drift**: Verify focus mapping calculations

#### Voice Control
- **No Recognition**: Check microphone levels and noise threshold
- **False Triggers**: Adjust voice activation sensitivity
- **Missed Commands**: Update voice model with new samples
- **Audio Delay**: Monitor audio buffer size

#### System Performance
- **High CPU**: Profile thread usage and adjust processing rates
- **Memory Growth**: Check for frame buffer leaks
- **Slow Startup**: Review initialization sequence
- **Thread Blocking**: Monitor lock contention and deadlocks

### Testing

The system includes comprehensive test scripts for each component:

```bash
# Run individual component tests
python test_frame_buffer.py      # Test frame buffer performance
python test_async_helper.py      # Test async processing
python test_display_processor.py # Test display and tracking
python test_face_processor.py    # Test face detection
python test_voice_control.py     # Test voice commands
python test_distance_sensor.py   # Test distance sensor
```