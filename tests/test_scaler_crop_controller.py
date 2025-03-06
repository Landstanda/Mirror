import unittest
from unittest.mock import Mock, patch
import time
from core.scaler_crop_controller import ScalerCropController
from core.camera_manager import ZoomLevel
from dataclasses import dataclass

@dataclass
class MockFaceData:
    bbox: list  # [xmin, ymin, width, height]
    landmarks: list
    confidence: float

class TestScalerCropController(unittest.TestCase):
    def setUp(self):
        # Create mock camera manager
        self.mock_camera = Mock()
        self.mock_camera.picam2 = Mock()
        self.mock_camera.picam2.camera_properties = {
            "ScalerCropMaximum": (0, 0, 4056, 3040)  # Example sensor dimensions
        }
        
        # Create controller instance
        self.controller = ScalerCropController(self.mock_camera)
        
    def test_initialization(self):
        """Test initial state of controller"""
        self.assertIsNone(self.controller.current_crop)
        self.assertIsNone(self.controller.target_crop)
        self.assertEqual(self.controller.current_zoom, ZoomLevel.FACE)
        self.assertEqual(self.controller.hardware_zoom_ratios[ZoomLevel.FACE], 1.2)
        self.assertEqual(self.controller.hardware_zoom_ratios[ZoomLevel.WIDE], 2.0)
        self.assertEqual(self.controller.hardware_zoom_ratios[ZoomLevel.EYES], 1.5)
        self.assertEqual(self.controller.hardware_zoom_ratios[ZoomLevel.LIPS], 1.5)
        
    def test_update_target_crop(self):
        """Test target crop calculation from face data"""
        # Create mock face data (centered face taking up 1/4 of frame)
        face_data = MockFaceData(
            bbox=[0.375, 0.375, 0.25, 0.25],  # Centered face
            landmarks=[],
            confidence=0.9
        )
        
        # Update target crop
        self.controller.update_target_crop(face_data)
        
        # Verify target crop calculation
        self.assertIsNotNone(self.controller.target_crop)
        x, y, w, h = self.controller.target_crop
        
        # Expected size should be face size * hardware_zoom_ratio
        expected_size = 0.25 * 1.2  # 0.25 is face width/height, 1.2 is zoom ratio
        self.assertAlmostEqual(w, expected_size)
        self.assertAlmostEqual(h, expected_size)
        
        # Center should be at face center
        face_center_x = 0.375 + 0.25/2  # face_x + face_width/2
        face_center_y = 0.375 + 0.25/2
        self.assertAlmostEqual(x + w/2, face_center_x)
        self.assertAlmostEqual(y + h/2, face_center_y)
        
    def test_smooth_crop_update(self):
        """Test smooth transition between crop positions"""
        # Set initial crop
        initial_crop = (0.3, 0.3, 0.3, 0.3)
        target_crop = (0.4, 0.4, 0.3, 0.3)
        
        self.controller.current_crop = initial_crop
        self.controller.target_crop = target_crop
        
        # Calculate smoothed position
        smoothed = self.controller._smooth_crop_update()
        
        # Verify smoothing
        for i in range(4):
            # New position should be between initial and target
            self.assertTrue(initial_crop[i] <= smoothed[i] <= target_crop[i] or
                          target_crop[i] <= smoothed[i] <= initial_crop[i])
            
    def test_convert_to_sensor_coordinates(self):
        """Test conversion from normalized to sensor coordinates"""
        normalized_crop = (0.25, 0.25, 0.5, 0.5)  # Quarter of frame centered
        
        sensor_crop = self.controller._convert_to_sensor_coordinates(normalized_crop)
        
        # Verify sensor coordinates
        self.assertEqual(len(sensor_crop), 4)
        self.assertTrue(all(isinstance(x, int) for x in sensor_crop))
        
        # Check bounds
        sensor_width = self.mock_camera.picam2.camera_properties["ScalerCropMaximum"][2]
        sensor_height = self.mock_camera.picam2.camera_properties["ScalerCropMaximum"][3]
        
        x, y, w, h = sensor_crop
        self.assertTrue(0 <= x <= sensor_width - w)
        self.assertTrue(0 <= y <= sensor_height - h)
        self.assertTrue(0 < w <= sensor_width)
        self.assertTrue(0 < h <= sensor_height)
        
    @patch('time.monotonic')
    def test_update_rate_limiting(self, mock_time):
        """Test that updates are rate-limited to 5 FPS"""
        # Mock initial time
        initial_time = 0.0
        mock_time.return_value = initial_time
        
        # Reset controller's last update time
        self.controller.last_update_time = initial_time - self.controller.min_update_interval
        
        # First update should proceed
        self.assertTrue(self.controller._should_update())
        self.assertEqual(self.controller.last_update_time, initial_time)
        
        # Update immediately after should not proceed
        mock_time.return_value = initial_time + 0.1  # Less than min_update_interval
        self.assertFalse(self.controller._should_update())
        self.assertEqual(self.controller.last_update_time, initial_time)  # Should not change
        
        # Update after min_update_interval should proceed
        mock_time.return_value = initial_time + self.controller.min_update_interval
        self.assertTrue(self.controller._should_update())
        self.assertEqual(self.controller.last_update_time, mock_time.return_value)
        
    def test_thread_safety(self):
        """Test thread safety of crop updates"""
        import threading
        import queue
        
        # Queue to collect any exceptions from threads
        exceptions = queue.Queue()
        
        def update_crop():
            try:
                for i in range(100):
                    face_data = MockFaceData(
                        bbox=[0.375 + i/1000, 0.375, 0.25, 0.25],
                        landmarks=[],
                        confidence=0.9
                    )
                    self.controller.update_target_crop(face_data)
            except Exception as e:
                exceptions.put(e)
                
        # Create multiple threads updating the crop simultaneously
        threads = [threading.Thread(target=update_crop) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
            
        # Check for any exceptions
        self.assertTrue(exceptions.empty(), f"Threads raised exceptions: {list(exceptions.queue)}")

if __name__ == '__main__':
    unittest.main() 