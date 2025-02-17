import os
import time
import threading
import json
from typing import Optional, Dict, Callable
from vosk import Model, KaldiRecognizer
import pyaudio
from enum import Enum

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
    
    Commands:
    - "eye" -> zoom to eyes
    - "lips" -> zoom to lips
    - "face" -> zoom to face
    - "zoom out" -> wide view
    - "focus" -> trigger focus search
    """
    
    def __init__(self, command_callbacks: Dict[VoiceCommand, Callable[[], None]]):
        self.command_callbacks = command_callbacks
        self.running = False
        self.thread = None
        
        # Initialize Vosk
        model_path = "vosk-model-small-en-us-0.15"
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Vosk model not found at {model_path}. "
                "Please download it from https://alphacephei.com/vosk/models"
            )
        
        print("Loading Vosk model...")
        self.model = Model(model_path)
        self.recognizer = KaldiRecognizer(self.model, 16000)
        
        # Initialize PyAudio
        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=4000
        )
        print("Voice controller initialized")
        
    def _process_command(self, text: str):
        """Process recognized text for commands"""
        text = text.lower()
        print(f"Heard: {text}")
        
        # Check for each command
        for command in VoiceCommand:
            if command.value in text:
                callback = self.command_callbacks.get(command)
                if callback:
                    print(f"Executing command: {command.name}")
                    callback()
                break
                
    def _voice_loop(self):
        """Main voice processing loop"""
        print("Starting voice recognition...")
        self.stream.start_stream()
        
        while self.running:
            try:
                # Read audio data
                data = self.stream.read(4000, exception_on_overflow=False)
                
                # Process audio data
                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    text = result.get("text", "")
                    
                    # Process any detected commands
                    if text:
                        self._process_command(text)
                        
            except Exception as e:
                print(f"Voice recognition error: {e}")
                time.sleep(0.1)  # Prevent rapid error loops
                continue
                
    def start(self):
        """Start voice recognition"""
        if not self.running:
            print("Starting voice controller...")
            self.running = True
            self.thread = threading.Thread(target=self._voice_loop, daemon=True)
            self.thread.start()
            
    def stop(self):
        """Stop voice recognition and cleanup"""
        print("Stopping voice controller...")
        self.running = False
        
        if self.thread:
            self.thread.join(timeout=1.0)
            
        if hasattr(self, 'stream'):
            self.stream.stop_stream()
            self.stream.close()
            
        if hasattr(self, 'audio'):
            self.audio.terminate()
            
        print("Voice controller stopped") 