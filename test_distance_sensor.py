import time
from core.distance_sensor import DistanceSensor

# GPIO pins for the ultrasonic sensor
TRIGGER_PIN = 23  # Physical pin 16 (orange)
ECHO_PIN = 24    # Physical pin 18 (yellow)

def main():
    # Initialize distance sensor without camera for simple testing
    print("Initializing distance sensor...")
    sensor = DistanceSensor(TRIGGER_PIN, ECHO_PIN)
    
    try:
        print("Starting distance sensor...")
        sensor.start()
        
        print("\nDistance Sensor Test")
        print("-------------------")
        print("Reading distances every 2 seconds")
        print("Press Ctrl+C to quit\n")
        
        # Main loop - print distance every 2 seconds
        while True:
            print("\nTaking measurement...")
            distance = sensor.get_current_distance()
            focus = sensor.get_current_focus()
            print(f"Result: Distance = {distance:4.1f} cm  ->  Focus = {focus:4.2f}")
            print("-" * 50)
            time.sleep(2.0)
            
    except KeyboardInterrupt:
        print("\nStopping test...")
    finally:
        # Clean up
        sensor.stop()

if __name__ == "__main__":
    main() 