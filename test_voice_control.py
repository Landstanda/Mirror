import time
from core.voice_controller import VoiceController, VoiceCommand

def main():
    # Create callback functions for each command
    def on_eyes():
        print("Action: Zooming to eyes")
        
    def on_lips():
        print("Action: Zooming to lips")
        
    def on_face():
        print("Action: Zooming to face")
        
    def on_zoom_out():
        print("Action: Zooming out to wide view")
        
    def on_focus():
        print("Action: Triggering focus search")
    
    # Map commands to callbacks
    callbacks = {
        VoiceCommand.EYES: on_eyes,
        VoiceCommand.LIPS: on_lips,
        VoiceCommand.FACE: on_face,
        VoiceCommand.ZOOM_OUT: on_zoom_out,
        VoiceCommand.FOCUS: on_focus
    }
    
    # Initialize voice controller
    print("Initializing voice controller...")
    voice_controller = VoiceController(callbacks)
    
    try:
        # Start voice recognition
        voice_controller.start()
        
        print("\nVoice Control Test")
        print("----------------")
        print("Try saying these commands:")
        print("- 'eye' to zoom to eyes")
        print("- 'lips' to zoom to lips")
        print("- 'face' to zoom to face")
        print("- 'zoom out' for wide view")
        print("- 'focus' to trigger focus")
        print("\nPress Ctrl+C to quit\n")
        
        # Keep the program running
        while True:
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nStopping test...")
    finally:
        # Clean up
        voice_controller.stop()

if __name__ == "__main__":
    main() 