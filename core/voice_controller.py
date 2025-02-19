import os
import time
import threading
import json
from typing import Optional, Dict, Callable, Deque
from collections import deque
from vosk import Model, KaldiRecognizer
import pyaudio
from enum import Enum
from core.async_helper import AsyncHelper

class VoiceCommand(Enum):
    EYES = "eye"
    LIPS = "lips"
    FACE = "face"
    ZOOM_OUT = "zoom out"
    FOCUS = "focus"

class VoiceController:
    """
    Asynchronous voice command processing using Vosk
    
    Features:
    - Keyword detection for zoom and focus commands
    - Non-blocking command processing
    - Command queue management
    - Performance monitoring
    - Async command processing
    - Resource cleanup
    
    Commands:
    - "eye" -> zoom to eyes
    - "lips" -> zoom to lips
    - "face" -> zoom to face
    - "zoom out" -> wide view
    - "focus" -> trigger focus search
    """
    
    def __init__(self, command_callbacks: Dict[VoiceCommand, Callable[[], None]], async_helper: AsyncHelper):
        self.command_callbacks = command_callbacks
        self.async_helper = async_helper
        self.running = False
        self.thread = None
        
        # Performance monitoring
        self.process_times = deque(maxlen=60)  # Store last 60 processing times
        self.last_stats_print = 0
        self.stats_print_interval = 5.0  # Print stats every 5 seconds
        
        # Initialize audio system
        self._initialize_audio_system()
        
    def _initialize_audio_system(self):
        """Initialize Vosk and audio system with error handling"""
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
            raise FileNotFoundError(
                "Vosk model not found. Please download it from "
                "https://alphacephei.com/vosk/models and place in ~/.vosk/models/"
            )
        
        print(f"Loading Vosk model from {model_path}...")
        try:
            self.model = Model(model_path)
            self.recognizer = KaldiRecognizer(self.model, 16000)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Vosk: {e}")
            
        # Initialize PyAudio with error handling
        try:
            self.audio = pyaudio.PyAudio()
            
            # Find appropriate input device
            input_device_index = None
            for i in range(self.audio.get_device_count()):
                device_info = self.audio.get_device_info_by_index(i)
                if device_info['maxInputChannels'] > 0:
                    input_device_index = i
                    break
                    
            if input_device_index is None:
                raise RuntimeError("No audio input device found")
                
            # Configure audio stream
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=input_device_index,
                frames_per_buffer=4000,
                stream_callback=self._audio_callback
            )
            print(f"Audio initialized using device {input_device_index}")
            
        except Exception as e:
            if hasattr(self, 'audio'):
                self.audio.terminate()
            raise RuntimeError(f"Failed to initialize audio: {e}")
            
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Handle audio data asynchronously"""
        if self.running:
            # Schedule audio processing in async helper
            self.async_helper.schedule_task(
                self._process_audio_data,
                2,  # priority
                f"audio_{time.monotonic()}",  # task_id
                in_data  # audio data as positional argument
            )
        return (None, pyaudio.paContinue)
        
    def _process_audio_data(self, audio_data):
        """Process audio data in async helper thread"""
        try:
            start_time = time.monotonic()
            
            if self.recognizer.AcceptWaveform(audio_data):
                result = json.loads(self.recognizer.Result())
                text = result.get("text", "")
                
                if text:
                    self._process_command(text)
                    
            # Record processing time
            process_time = time.monotonic() - start_time
            self.process_times.append(process_time)
            
            # Print stats periodically
            current_time = time.monotonic()
            if current_time - self.last_stats_print >= self.stats_print_interval:
                self._print_performance_stats()
                self.last_stats_print = current_time
                
        except Exception as e:
            print(f"Error processing audio: {e}")
            
    def _print_performance_stats(self):
        """Print voice processing performance statistics"""
        if len(self.process_times) > 0:
            avg_process_time = sum(self.process_times) / len(self.process_times) * 1000
            print(f"Voice Processing: Avg processing time: {avg_process_time:.1f}ms")
            
    def _process_command(self, text: str):
        """Process recognized text for commands"""
        text = text.lower()
        print(f"Heard: {text}")
        
        # Schedule command execution in async helper
        for command in VoiceCommand:
            if command.value in text:
                callback = self.command_callbacks.get(command)
                if callback:
                    print(f"Executing command: {command.name}")
                    self.async_helper.schedule_task(
                        callback,
                        priority=1,  # Lower priority for command execution
                        task_id=f"cmd_{command.name}_{time.monotonic()}"
                    )
                break
                
    def start(self):
        """Start voice recognition"""
        if not self.running:
            print("Starting voice controller...")
            self.running = True
            self.stream.start_stream()
            
    def stop(self):
        """Stop voice recognition and cleanup"""
        print("Stopping voice controller...")
        self.running = False
        
        if hasattr(self, 'stream'):
            self.stream.stop_stream()
            self.stream.close()
            
        if hasattr(self, 'audio'):
            self.audio.terminate()
            
        print("Voice controller stopped") 