#!/usr/bin/env python3
import time
from core.distance_sensor import DistanceSensor

def test_distance_sensor():
    print("Initializing distance sensor...")
    ds = DistanceSensor(trigger_pin=23, echo_pin=24)
    
    print("Distance-focus mapping:")
    for distance, focus in sorted(ds.distance_focus_map.items()):
        print(f"  {distance:.1f}cm -> {focus:.2f}")
    
    print("\nStarting distance sensor...")
    ds.start()
    
    print("Reading distance and calculating focus for 10 seconds...")
    try:
        for i in range(10):
            time.sleep(1)
            distance = ds.get_current_distance()
            focus = ds.get_current_focus()
            print(f"Distance: {distance:.1f}cm, Focus: {focus:.2f}")
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    finally:
        print("Stopping distance sensor...")
        ds.stop()
        print("Test complete")

if __name__ == "__main__":
    test_distance_sensor() 