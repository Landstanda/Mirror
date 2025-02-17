#!/usr/bin/env python3

import vosk
import sounddevice as sd
import queue
import json
import threading
from pathlib import Path
import sys
import os
from pynput import keyboard
from pynput.keyboard import Controller, Key
import argparse

class DictationSystem:
    def __init__(self, model_name="vosk-model-small-en-us"):
        """Initialize the dictation system"""
        self.keyboard = Controller()
        self.audio_queue = queue.Queue()
        self.is_listening = False
        self.running = True
        self.is_typing = False  # New flag to track when we're typing
        
        # Custom word replacements
        self.word_replacements = {
            'github': 'GitHub',
            'get hub': 'GitHub',
            'get home': 'GitHub',
            'huh': '',  # Remove 'huh' completely
            'an l p': 'NLP',
            'n l p': 'NLP',
            'and lp': 'NLP',
            'an lp': 'NLP',
            'chat gp t': 'ChatGPT',
            'church gp t': 'ChatGPT',
            'chad gp t': 'ChatGPT',
        }
        
        # Initialize audio settings
        self.samplerate = 16000
        self.blocksize = 8000
        
        # Load the model
        model_path = self._get_model_path(model_name)
        if not os.path.exists(model_path):
            self._download_model(model_path)
            
        try:
            print("\nLoading speech recognition model...")
            self.model = vosk.Model(model_path)
            self.recognizer = vosk.KaldiRecognizer(self.model, self.samplerate)
            print("Model loaded successfully!")
            
            # Get default input device
            device_info = sd.query_devices(None, 'input')
            print(f"\nUsing audio device: {device_info['name']}")
            
        except Exception as e:
            print(f"Error initializing: {str(e)}")
            sys.exit(1)
    
    def _get_model_path(self, model_name):
        """Get the path where the model should be stored"""
        home = str(Path.home())
        return os.path.join(home, '.vosk', 'models', model_name)
    
    def _download_model(self, model_path):
        """Download the Vosk model"""
        print("\nDownloading speech recognition model (this may take a few minutes)...")
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        # Download small model for testing
        import urllib.request
        import zipfile
        url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
        zip_path = model_path + ".zip"
        
        try:
            print("Downloading...")
            urllib.request.urlretrieve(url, zip_path)
            print("Extracting...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(os.path.dirname(model_path))
            
            # Rename the extracted folder to our standard name
            extracted_dir = os.path.join(os.path.dirname(model_path), "vosk-model-small-en-us-0.15")
            os.rename(extracted_dir, model_path)
            
            # Cleanup
            os.remove(zip_path)
            print("Model downloaded and installed successfully!")
            
        except Exception as e:
            print(f"Error downloading model: {str(e)}")
            print("\nPlease try:")
            print("1. Check your internet connection")
            print("2. Download manually from https://alphacephei.com/vosk/models")
            print(f"3. Extract to: {model_path}")
            sys.exit(1)
    
    def audio_callback(self, indata, frames, time, status):
        """Callback for audio input"""
        if status:
            print(f"Audio status: {status}")
        if self.is_listening:
            self.audio_queue.put(bytes(indata))
    
    def _process_text(self, text):
        """Process recognized text with custom rules"""
        # Basic number components
        units = {
            'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
            'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
            'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13,
            'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17,
            'eighteen': 18, 'nineteen': 19
        }
        
        tens = {
            'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50,
            'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90
        }
        
        # Custom word replacements
        words = text.lower().split()
        result_words = []
        i = 0
        
        while i < len(words):
            current_word = words[i].strip('-')  # Remove any hyphens
            
            # Try to process as a number
            if current_word in tens and i + 1 < len(words):
                next_word = words[i + 1].strip('-')
                if next_word in units:
                    # Combine tens and units (e.g., "twenty" + "three" = 23)
                    number = tens[current_word] + units[next_word]
                    result_words.append(str(number))
                    i += 2
                    continue
                else:
                    # Just tens (e.g., "twenty")
                    result_words.append(str(tens[current_word]))
                    i += 1
                    continue
            elif current_word in units:
                # Single unit or teen number
                result_words.append(str(units[current_word]))
                i += 1
                continue
            
            # Check for three-word replacements
            if i + 2 < len(words):
                three_words = f"{current_word} {words[i + 1]} {words[i + 2]}"
                if three_words in self.word_replacements:
                    if self.word_replacements[three_words]:  # Only add if not empty
                        result_words.append(self.word_replacements[three_words])
                    i += 3
                    continue
            
            # Check for two-word replacements
            if i + 1 < len(words):
                two_words = f"{current_word} {words[i + 1]}"
                if two_words in self.word_replacements:
                    if self.word_replacements[two_words]:  # Only add if not empty
                        result_words.append(self.word_replacements[two_words])
                    i += 2
                    continue
            
            # Check for single word replacements
            if current_word in self.word_replacements:
                if self.word_replacements[current_word]:  # Only add if not empty
                    result_words.append(self.word_replacements[current_word])
            else:
                # Keep original word if no replacement found
                result_words.append(words[i])
            i += 1
        
        return ' '.join(result_words)

    def process_audio(self):
        """Process audio from the queue"""
        while self.is_listening:
            try:
                data = self.audio_queue.get(timeout=0.5)
                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    if result["text"]:
                        # Process the text before typing
                        processed_text = self._process_text(result["text"]) + " "
                        print(f"→ {processed_text}")
                        self.is_typing = True  # Set flag before typing
                        self.keyboard.type(processed_text)
                        self.is_typing = False  # Reset flag after typing
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error processing audio: {e}")
    
    def start_listening(self):
        """Start dictation"""
        if not self.is_listening:
            self.is_listening = True
            # Clear any old data from the queue
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    break
            # Start processing thread
            self.process_thread = threading.Thread(target=self.process_audio)
            self.process_thread.daemon = True  # Make thread daemon so it exits when main thread exits
            self.process_thread.start()
            print("\n[RECORDING] Dictation active - speak naturally")
    
    def stop_listening(self):
        """Stop dictation"""
        if self.is_listening:
            self.is_listening = False
            # Process any remaining audio before stopping
            try:
                # Give a short time for any final processing
                self.process_thread.join(timeout=0.5)
            except:
                pass
            print("\n[STOPPED] Dictation paused")
    
    def on_press(self, key):
        """Handle key press events"""
        # Ignore keyboard events if we're currently typing
        if self.is_typing:
            return
            
        try:
            # Use F9 to start dictation
            if key == Key.f9:
                self.start_listening()
            # Use Esc to exit
            elif key == Key.esc:
                print("\nExiting...")
                self.running = False
                self.is_listening = False
                return False
            # Any other key press stops dictation
            elif self.is_listening:
                self.stop_listening()
        except AttributeError:
            # For non-special keys, stop dictation if it's active
            if self.is_listening:
                self.stop_listening()
    
    def run(self):
        """Main loop"""
        print("\nDictation System Ready!")
        print("----------------------")
        print("Controls:")
        print(" F9: Start dictation")
        print(" Any key: Pause dictation")
        print(" ESC: Exit")
        print("----------------------")
        
        try:
            # Start audio stream
            with sd.RawInputStream(samplerate=self.samplerate,
                                 blocksize=self.blocksize,
                                 dtype='int16',
                                 channels=1,
                                 callback=self.audio_callback):
                # Start keyboard listener
                with keyboard.Listener(on_press=self.on_press) as listener:
                    listener.join()
        except Exception as e:
            print(f"\nError: {str(e)}")
            print("Please check your microphone settings and try again.")
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Local Dictation System")
    parser.add_argument("--model", default="vosk-model-small-en-us",
                       help="Name of the Vosk model to use")
    args = parser.parse_args()
    
    try:
        dictation = DictationSystem(model_name=args.model)
        dictation.run()
    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    main() 