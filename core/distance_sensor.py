import time
import threading
import os
from typing import Optional, Deque
from collections import deque
from gpiozero import DistanceSensor as GPIOZeroDistance
from core.async_helper import AsyncHelper

# Tell gpiozero to use lgpio by default
os.environ['GPIOZERO_PIN_FACTORY'] = 'lgpio'

class DistanceSensor:
    """
    Asynchronous distance sensor management with focus mapping
    
    Features:
    - Non-blocking operation using gpiozero
    - Direct mapping to focus values
    - 5Hz sampling rate (200ms interval)
    - Performance monitoring
    - Resource cleanup
    """
    
    def __init__(self, trigger_pin: int, echo_pin: int, async_helper: Optional[AsyncHelper] = None):
        # GPIO setup
        self.trigger_pin = trigger_pin
        self.echo_pin = echo_pin
        self.async_helper = async_helper
        
        # Threading controls
        self.running = False
        self.thread = None
        
        # Distance and focus parameters
        self.current_distance = 0.0
        self.min_distance = 30.0  # cm - adjusted to match calibration range
        self.max_distance = 90.0  # cm - adjusted to match calibration range
        self.sample_interval = 0.1  # 100ms = 10Hz - more responsive
        
        # Focus smoothing
        self.focus_history = deque(maxlen=5)  # Store last 5 focus values
        self.focus_smoothing_enabled = True
        
        # Performance monitoring
        self.measure_times = deque(maxlen=60)  # Store last 60 measurements
        self.last_stats_print = 0
        self.stats_print_interval = 30.0  # Print stats every 30 seconds (increased from 10)
        
        # Focus mapping parameters (based on camera characteristics)
        self.distance_focus_map = {
            32.9: 11.00,  # Closest focus
            43.0: 10.30,
            50.6: 10.30,
            60.7: 9.60,
            87.1: 9.50,  # Farthest focus
        }
        
        # Initialize sensor
        print(f"Initializing HC-SR04 distance sensor on pins: Trigger={trigger_pin}, Echo={echo_pin}")
        try:
            # Note: gpiozero expects echo_pin first, then trigger_pin
            self.sensor = GPIOZeroDistance(
                echo=echo_pin,
                trigger=trigger_pin,
                max_distance=2.0,  # Maximum distance in meters
                threshold_distance=0.3  # Threshold for when_in_range
            )
            print("Distance sensor initialized successfully")
        except Exception as e:
            print(f"Failed to initialize distance sensor: {e}")
            raise
            
    def _measure_distance(self) -> float:
        """
        Measure distance using ultrasonic sensor
        Returns: distance in centimeters
        """
        try:
            start_time = time.monotonic()
            
            # Get distance in meters and convert to cm
            distance_cm = self.sensor.distance * 100
            
            # Clamp to valid range
            distance_cm = max(self.min_distance, min(self.max_distance, distance_cm))
            
            # Record measurement time
            measure_time = time.monotonic() - start_time
            self.measure_times.append(measure_time)
            
            return distance_cm
            
        except Exception as e:
            print(f"Error in distance measurement: {e}")
            return self.current_distance
            
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
            raw_focus = self.distance_focus_map[distances[0]]
        elif distance >= distances[-1]:
            raw_focus = self.distance_focus_map[distances[-1]]
        else:
            # Find surrounding points for interpolation
            for i in range(len(distances) - 1):
                d1, d2 = distances[i], distances[i + 1]
                if d1 <= distance <= d2:
                    f1 = self.distance_focus_map[d1]
                    f2 = self.distance_focus_map[d2]
                    # Linear interpolation
                    raw_focus = f1 + (f2 - f1) * (distance - d1) / (d2 - d1)
                    break
            else:
                raw_focus = self.distance_focus_map[distances[0]]  # Fallback
        
        # Apply smoothing if enabled
        if self.focus_smoothing_enabled:
            # Add current focus to history
            self.focus_history.append(raw_focus)
            
            # Calculate weighted average (more weight to recent values)
            if len(self.focus_history) > 0:
                weights = [0.1, 0.15, 0.2, 0.25, 0.3]  # More weight to recent values
                weights = weights[-len(self.focus_history):]  # Adjust weights to match history length
                
                # Normalize weights
                weight_sum = sum(weights)
                weights = [w / weight_sum for w in weights]
                
                # Calculate weighted average
                smoothed_focus = sum(f * w for f, w in zip(self.focus_history, weights))
                return smoothed_focus
        
        return raw_focus
        
    def _sensor_loop(self):
        """Main sensor reading loop"""
        last_read_time = 0
        
        while self.running:
            current_time = time.monotonic()
            
            # Check if it's time for a new reading
            if current_time - last_read_time >= self.sample_interval:
                try:
                    # Measure distance
                    distance = self._measure_distance()
                    self.current_distance = distance
                    
                    # Calculate focus value
                    focus = self._map_distance_to_focus(distance)
                    
                    # Schedule focus update if using AsyncHelper
                    if self.async_helper is not None:
                        self.async_helper.schedule_task(
                            lambda f=focus: self._update_focus(f),
                            priority=3,
                            task_id=f"focus_update_{current_time}"
                        )
                    
                    last_read_time = current_time
                    
                    # Print performance stats periodically
                    if current_time - self.last_stats_print >= self.stats_print_interval:
                        self._print_performance_stats()
                        self.last_stats_print = current_time
                        
                except Exception as e:
                    print(f"Error in sensor loop: {e}")
            
            # Small sleep to prevent CPU thrashing
            time.sleep(0.01)
            
    def _print_performance_stats(self):
        """Print performance statistics"""
        if len(self.measure_times) > 0:
            avg_time = sum(self.measure_times) / len(self.measure_times) * 1000
            current_distance = self.get_current_distance()
            current_focus = self.get_current_focus()
            
            # Calculate raw focus for comparison
            raw_focus = None
            distances = sorted(self.distance_focus_map.keys())
            if current_distance <= distances[0]:
                raw_focus = self.distance_focus_map[distances[0]]
            elif current_distance >= distances[-1]:
                raw_focus = self.distance_focus_map[distances[-1]]
            else:
                for i in range(len(distances) - 1):
                    d1, d2 = distances[i], distances[i + 1]
                    if d1 <= current_distance <= d2:
                        f1 = self.distance_focus_map[d1]
                        f2 = self.distance_focus_map[d2]
                        raw_focus = f1 + (f2 - f1) * (current_distance - d1) / (d2 - d1)
                        break
            
            print(f"\n=== Distance Sensor Status ===")
            print(f"Distance: {current_distance:.1f}cm")
            print(f"Focus Setting: {current_focus:.2f}" + (f" (Raw: {raw_focus:.2f})" if raw_focus is not None else ""))
            print(f"Avg measurement time: {avg_time:.1f}ms")
            print("===========================\n")
            
    def _update_focus(self, focus_value: float):
        """Update focus value (placeholder for callback)"""
        pass  # This will be set by the main program
        
    def start(self):
        """Start the distance sensor"""
        if not self.running:
            print("Starting distance sensor thread")
            self.running = True
            self.thread = threading.Thread(target=self._sensor_loop, daemon=True)
            self.thread.start()
            
    def stop(self):
        """Stop the distance sensor and cleanup"""
        print("Stopping distance sensor")
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            
        # Cleanup sensor
        try:
            self.sensor.close()
        except Exception as e:
            print(f"Sensor cleanup warning: {e}")
            
        print("Distance sensor stopped")
        
    def get_current_distance(self) -> float:
        """Get the most recent distance measurement"""
        return self.current_distance
        
    def get_current_focus(self) -> float:
        """Get the focus value for the current distance"""
        return self._map_distance_to_focus(self.current_distance) 