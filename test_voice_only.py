#!/usr/bin/env python3

import os
import time
import threading
import json
import queue
import signal
import sys
from vosk import Model, KaldiRecognizer
import pyaudio
from enum import Enum

# Set up signal handling for clean exit
shutdown_requested = False

def signal_handler(sig, frame):
    global shutdown_requested
    if not shutdown_requested:
        print("\nShutdown requested. Press Ctrl+C again to force exit.")
        shutdown_requested = True
    else:
        print("\nForce exiting...")
        os._exit(1)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

class VoiceCommand(Enum):
    EYES = "eye"
    LIPS = "lips"
    FACE = "face"
    ZOOM_OUT = "zoom out"
    FOCUS = "focus"

class SimpleVoiceController:
    """
    Simplified voice controller for testing
    """
    def __init__(self):
        self.running = False
        self.audio_queue = queue.Queue()
        self.process_thread = None
        
        # Find Vosk model
        model_paths = [
            "vosk-model-small-en-us-0.15",
            os.path.expanduser("~/.vosk/models/vosk-model-small-en-us-0.15"),
            "/usr/local/share/vosk/models/vosk-model-small-en-us-0.15"
        ]
        
        model_path = None
        for path in model_paths:
            if os.path.exists(path):
                model_path = path
                break
                
        if not model_path:
            print("Vosk model not found. Please download it from https://alphacephei.com/vosk/models")
            print("and place in ~/.vosk/models/")
            sys.exit(1)
        
        print(f"Loading Vosk model from {model_path}...")
        try:
            self.model = Model(model_path)
            self.recognizer = KaldiRecognizer(self.model, 16000)  # Using 16kHz like dictation.py
            print("Model loaded successfully!")
        except Exception as e:
            print(f"Failed to initialize Vosk: {e}")
            sys.exit(1)
            
        # Initialize PyAudio
        try:
            self.audio = pyaudio.PyAudio()
            
            # List available audio devices
            print("\nAvailable Audio Devices:")
            info = self.audio.get_host_api_info_by_index(0)
            numdevices = info.get('deviceCount')
            input_device_index = None
            
            for i in range(0, numdevices):
                device_info = self.audio.get_device_info_by_index(i)
                if device_info.get('maxInputChannels') > 0:
                    print(f"Device {i}: {device_info.get('name')}")
                    print(f"  Max Input Channels: {device_info.get('maxInputChannels')}")
                    print(f"  Default Sample Rate: {int(device_info.get('defaultSampleRate'))}Hz")
                    # Prefer USB audio devices or devices with "mic" in name
                    if input_device_index is None or \
                       ('usb' in device_info.get('name').lower()) or \
                       ('mic' in device_info.get('name').lower()):
                        input_device_index = i
            
            if input_device_index is None:
                print("No audio input device found")
                sys.exit(1)
                
            print(f"\nSelected device {input_device_index} for audio input")
            
        except Exception as e:
            print(f"Failed to initialize audio: {e}")
            sys.exit(1)
    
    def audio_callback(self, in_data, frame_count, time_info, status):
        """Callback for audio input"""
        if status:
            print(f"Audio status: {status}")
        self.audio_queue.put(bytes(in_data))
        return (None, pyaudio.paContinue)
    
    def process_audio(self):
        """Process audio from the queue"""
        while self.running and not shutdown_requested:
            try:
                data = self.audio_queue.get(timeout=0.5)
                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    text = result.get("text", "")
                    
                    if text:
                        print(f"\n👂 Heard: '{text}'")
                        
                        # Check for commands
                        text = text.lower()
                        for command in VoiceCommand:
                            if command.value in text:
                                print(f"🎤 Command detected: {command.name}")
                                break
                        else:
                            print("❌ No command recognized")
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error processing audio: {e}")
                # Try to reset the recognizer
                try:
                    self.recognizer = KaldiRecognizer(self.model, 16000)
                    print("Recognizer reset after error")
                except:
                    print("Failed to reset recognizer")
    
    def start(self):
        """Start voice recognition"""
        if not self.running:
            self.running = True
            
            # Start audio stream
            try:
                self.stream = self.audio.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=16000,
                    input=True,
                    input_device_index=None,  # Use default
                    frames_per_buffer=8000,  # Larger buffer like dictation.py
                    stream_callback=self.audio_callback
                )
                self.stream.start_stream()
                print("Audio stream started")
            except Exception as e:
                print(f"Error starting audio stream: {e}")
                self.running = False
                return False
            
            # Start processing thread
            self.process_thread = threading.Thread(target=self.process_audio)
            self.process_thread.daemon = True
            self.process_thread.start()
            print("Voice recognition started")
            return True
        return False
    
    def stop(self):
        """Stop voice recognition and cleanup"""
        print("Stopping voice controller...")
        self.running = False
        
        # Wait for processing thread to finish
        if self.process_thread and self.process_thread.is_alive():
            try:
                self.process_thread.join(timeout=1.0)
            except:
                print("Warning: Could not join processing thread")
        
        # Clean up audio resources
        try:
            if hasattr(self, 'stream'):
                if self.stream.is_active():
                    try:
                        self.stream.stop_stream()
                    except Exception as e:
                        print(f"Warning: Error stopping stream: {e}")
                try:
                    self.stream.close()
                except Exception as e:
                    print(f"Warning: Error closing stream: {e}")
        except Exception as e:
            print(f"Error cleaning up stream: {e}")
            
        try:
            if hasattr(self, 'audio'):
                self.audio.terminate()
        except Exception as e:
            print(f"Error terminating audio: {e}")
            
        print("Voice controller stopped")

def main():
    print("Voice Controller Test")
    print("====================")
    print("This script tests voice recognition in isolation.")
    print("It will listen for commands: eyes, lips, face, zoom out, focus")
    print("Press Ctrl+C to exit")
    print()
    
    controller = SimpleVoiceController()
    
    try:
        if controller.start():
            print("\nListening for commands...")
            
            # Main loop
            while not shutdown_requested:
                time.sleep(0.1)
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        controller.stop()
        print("Test complete")

if __name__ == "__main__":
    main() 