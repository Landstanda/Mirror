import time
import threading
import RPi.GPIO as GPIO
import numpy as np
from typing import Optional, Callable

class DistanceSensor:
    """
    Asynchronous distance sensor management with focus mapping
    
    Features:
    - Non-blocking operation in separate thread
    - Direct mapping to focus values
    - 5Hz sampling rate (200ms interval)
    - Linear interpolation for focus mapping
    
    Hardware Setup:
    - GPIO Trigger Pin
    - GPIO Echo Pin
    - 3.3V power supply
    """
    
    def __init__(self, trigger_pin: int, echo_pin: int, callback: Optional[Callable[[float], None]] = None):
        # GPIO setup
        self.trigger_pin = trigger_pin
        self.echo_pin = echo_pin
        self.callback = callback
        
        # Threading controls
        self.running = False
        self.thread = None
        
        # Distance and focus parameters
        self.current_distance = 0.0
        self.min_distance = 20.0  # cm
        self.max_distance = 150.0  # cm
        self.sample_interval = 0.2  # 200ms = 5Hz
        
        # Focus mapping parameters (based on provided measurements)
        self.distance_focus_map = {
            50.0: 12.0,  # At 50cm, focus = 12
            100.0: 9.0   # At 100cm, focus = 9
        }
        
        # Initialize GPIO
        self._setup_gpio()
        
    def _setup_gpio(self):
        """Initialize GPIO pins"""
        print(f"Setting up GPIO: Trigger={self.trigger_pin}, Echo={self.echo_pin}")
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.trigger_pin, GPIO.OUT)
        GPIO.setup(self.echo_pin, GPIO.IN)
        GPIO.output(self.trigger_pin, False)
        time.sleep(0.1)  # Give sensor time to settle
        print("GPIO setup complete")
        
    def _measure_distance(self) -> float:
        """
        Measure distance using ultrasonic sensor
        Returns: distance in centimeters
        """
        # Reset trigger
        GPIO.output(self.trigger_pin, False)
        time.sleep(0.05)  # Give sensor time to settle
        
        # Send trigger pulse
        GPIO.output(self.trigger_pin, True)
        time.sleep(0.00001)  # 10 microseconds
        GPIO.output(self.trigger_pin, False)
        
        # Wait for echo to start
        pulse_start = time.time()
        timeout = pulse_start + 0.1  # 100ms timeout
        
        # Debug echo pin state
        echo_state = GPIO.input(self.echo_pin)
        print(f"Initial echo pin state: {echo_state}")
        
        # Wait for echo to go HIGH
        while GPIO.input(self.echo_pin) == 0:
            pulse_start = time.time()
            if pulse_start > timeout:
                print("Timeout waiting for echo start")
                return self.current_distance
        
        # Wait for echo to go LOW
        pulse_end = time.time()
        while GPIO.input(self.echo_pin) == 1:
            pulse_end = time.time()
            if pulse_end > timeout:
                print("Timeout waiting for echo end")
                return self.current_distance
        
        # Calculate distance
        pulse_duration = pulse_end - pulse_start
        distance = pulse_duration * 17150  # Speed of sound = 343m/s
        
        # Debug pulse information
        print(f"Pulse duration: {pulse_duration*1000:.3f}ms")
        print(f"Raw distance: {distance:.1f}cm")
        
        # Clamp to valid range
        distance = max(self.min_distance, min(self.max_distance, distance))
        return distance
        
    def _map_distance_to_focus(self, distance: float) -> float:
        """
        Map distance to focus value using linear interpolation
        Args:
            distance: Distance in centimeters
        Returns:
            focus: Focus value
        """
        # Sort distance-focus pairs
        distances = sorted(self.distance_focus_map.keys())
        
        # Handle out of range values
        if distance <= distances[0]:
            return self.distance_focus_map[distances[0]]
        if distance >= distances[-1]:
            return self.distance_focus_map[distances[-1]]
        
        # Find surrounding points for interpolation
        for i in range(len(distances) - 1):
            d1, d2 = distances[i], distances[i + 1]
            if d1 <= distance <= d2:
                f1 = self.distance_focus_map[d1]
                f2 = self.distance_focus_map[d2]
                # Linear interpolation
                return f1 + (f2 - f1) * (distance - d1) / (d2 - d1)
        
        return self.distance_focus_map[distances[0]]  # Fallback
        
    def _sensor_loop(self):
        """Main sensor reading loop"""
        last_read_time = 0
        
        while self.running:
            current_time = time.monotonic()
            
            # Check if it's time for a new reading
            if current_time - last_read_time >= self.sample_interval:
                # Measure distance
                distance = self._measure_distance()
                self.current_distance = distance
                
                # Calculate focus value
                focus = self._map_distance_to_focus(distance)
                
                # Notify callback if set
                if self.callback:
                    self.callback(focus)
                    
                last_read_time = current_time
            
            # Small sleep to prevent CPU thrashing
            time.sleep(0.01)
            
    def start(self):
        """Start the distance sensor"""
        if not self.running:
            print("Starting distance sensor thread")
            self.running = True
            self.thread = threading.Thread(target=self._sensor_loop, daemon=True)
            self.thread.start()
            
    def stop(self):
        """Stop the distance sensor"""
        print("Stopping distance sensor")
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        GPIO.cleanup([self.trigger_pin, self.echo_pin])
        print("Distance sensor stopped")
        
    def get_current_distance(self) -> float:
        """Get the most recent distance measurement"""
        return self.current_distance
        
    def get_current_focus(self) -> float:
        """Get the focus value for the current distance"""
        return self._map_distance_to_focus(self.current_distance) 