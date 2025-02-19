import time
import os
from gpiozero import DistanceSensor as GPIOZeroDistance

# Tell gpiozero to use lgpio by default
os.environ['GPIOZERO_PIN_FACTORY'] = 'lgpio'

# GPIO pins for the ultrasonic sensor (using BCM numbering)
TRIGGER_PIN = 23  # Physical pin 16 (orange)
ECHO_PIN = 24    # Physical pin 18 (yellow)

def main():
    print("Initializing HC-SR04 distance sensor...")
    print(f"Using pins: Trigger={TRIGGER_PIN}, Echo={ECHO_PIN}")
    
    # Initialize sensor with gpiozero
    # Note: gpiozero expects the echo_pin first, then trigger_pin
    sensor = GPIOZeroDistance(echo=ECHO_PIN, trigger=TRIGGER_PIN,
                            max_distance=2.0,  # Maximum distance in meters
                            threshold_distance=0.3)  # Threshold for when_in_range
    
    try:
        print("\nDistance Sensor Test")
        print("-------------------")
        print("Reading distances every 2 seconds")
        print("Press Ctrl+C to quit\n")
        
        # Main loop - print distance every 2 seconds
        while True:
            print("\nTaking measurement...")
            try:
                # gpiozero returns distance in meters, convert to cm
                distance = sensor.distance * 100
                # Calculate focus based on distance
                if distance <= 20:
                    focus = 12.5
                elif distance >= 150:
                    focus = 8.0
                else:
                    # Linear interpolation between focus values
                    focus = 12.5 - (distance - 20) * (12.5 - 8.0) / (150 - 20)
                
                print(f"Result: Distance = {distance:4.1f} cm  ->  Focus = {focus:4.2f}")
            except Exception as e:
                print(f"Measurement error: {e}")
                print("Make sure the sensor is connected correctly:")
                print(f"- Trigger (orange) -> GPIO{TRIGGER_PIN}")
                print(f"- Echo (yellow) -> GPIO{ECHO_PIN}")
                print("- VCC (red) -> 5V")
                print("- GND (brown) -> Ground")
            print("-" * 50)
            time.sleep(2.0)
            
    except KeyboardInterrupt:
        print("\nStopping test...")
    finally:
        # gpiozero handles cleanup automatically
        sensor.close()
        print("Test complete")

if __name__ == "__main__":
    main() 