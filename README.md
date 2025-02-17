# MirrorAphrodite

A smart mirror application for Raspberry Pi that uses the Arducam 64MP Hawkeyes camera. Features face tracking, voice commands, and automatic focus adjustment.

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
mv vosk-model-small-en-us-0.15 vosk-model-small-en-us
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