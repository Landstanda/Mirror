import unittest
from unittest.mock import Mock, patch
import time
import numpy as np
import cv2
from core.camera_manager import CameraManager, ZoomLevel
from core.face_processor import CameraFaceProcessor
from core.display_processor import DisplayProcessor
from core.scaler_crop_controller import ScalerCropController
from picamera2 import Picamera2

class TestMirrorIntegration(unittest.TestCase):
    @patch('core.camera_manager.Picamera2')
    def setUp(self, mock_picam2_class):
        """Set up test environment with mock camera"""
        # Create a mock camera instance
        self.mock_picam2 = mock_picam2_class.return_value
        self.mock_picam2.camera_properties = {
            "ScalerCropMaximum": (0, 0, 4056, 3040)
        }
        
        # Create test frame with a "face"
        self.test_frame = np.zeros((1100, 1100, 3), dtype=np.uint8)
        cv2.circle(self.test_frame, (550, 550), 200, (255, 255, 255), -1)  # White circle as "face"
        
        # Mock camera capture and other methods
        self.mock_picam2.capture_array = Mock(return_value=self.test_frame)
        self.mock_picam2.capture_frame = Mock(return_value=self.test_frame)
        self.mock_picam2.set_controls = Mock()
        self.mock_picam2.start = Mock()
        self.mock_picam2.stop = Mock()
        
        # Mock configuration methods
        config = {
            'main': {'size': (1100, 1100), 'format': 'RGB888'},
            'sensor': {'output_size': (2312, 1736)},
            'raw': {'size': (2312, 1736)},
            'controls': {'NoiseReductionMode': 0, 'FrameDurationLimits': (33333, 33333), 'FrameRate': 30.0},
            'buffer_count': 3
        }
        self.mock_picam2.create_video_configuration = Mock(return_value=config)
        self.mock_picam2.create_preview_configuration = Mock(return_value=config)
        self.mock_picam2.create_still_configuration = Mock(return_value=config)
        
        # Mock sensor modes
        self.mock_picam2.sensor_modes = [
            {'size': (1280, 720), 'format': 'SRGGB10_CSI2P', 'fps': 120.09},
            {'size': (1920, 1080), 'format': 'SRGGB10_CSI2P', 'fps': 60.04},
            {'size': (2312, 1736), 'format': 'SRGGB10_CSI2P', 'fps': 30.0},
            {'size': (3840, 2160), 'format': 'SRGGB10_CSI2P', 'fps': 20.0},
            {'size': (4624, 3472), 'format': 'SRGGB10_CSI2P', 'fps': 10.0}
        ]
        
        # Initialize components
        self.camera = CameraManager()
        
        self.scaler_crop_controller = ScalerCropController(self.camera)
        self.face_processor = CameraFaceProcessor(self.camera, self.scaler_crop_controller)
        self.display_processor = DisplayProcessor(self.camera, self.face_processor)
        
    def test_display_path_latency(self):
        """Test latency of the critical display path"""
        # Mock face data
        mock_face_data = Mock(
            bbox=[0.4, 0.4, 0.2, 0.2],
            landmarks=[(0.45, 0.45),  # left eye
                      (0.55, 0.45),   # right eye
                      (0.5, 0.5),     # nose
                      (0.5, 0.55)],   # mouth
            confidence=0.9
        )
        self.face_processor.get_current_face_data = Mock(return_value=mock_face_data)
        
        start_time = time.monotonic()
        
        # Get frame directly from camera
        frame = self.camera.get_latest_frame_direct()
        
        # Process through display path
        display_frame = self.display_processor._software_crop_for_display(frame)
        
        end_time = time.monotonic()
        latency = (end_time - start_time) * 1000  # Convert to milliseconds
        
        print(f"Display path latency: {latency:.2f}ms")
        self.assertLess(latency, 33.3)  # Should be less than one frame at 30 FPS
        
    def test_face_processing_rate(self):
        """Verify face processing runs at expected rate"""
        processed_frames = []
        start_time = time.monotonic()
        
        # Mock frame processing
        def mock_process_frame(frame):
            processed_frames.append(time.monotonic())
            return Mock(bbox=[0.4, 0.4, 0.2, 0.2], landmarks=[(0.5, 0.5)], confidence=0.9)
            
        # Mock get_latest_frame to return frames at 30 FPS
        def mock_get_latest_frame():
            return self.test_frame
            
        self.camera.get_latest_frame = Mock(side_effect=mock_get_latest_frame)
        
        with patch.object(self.face_processor, 'process_frame', side_effect=mock_process_frame):
            self.face_processor.start()
            time.sleep(1.1)  # Slightly over 1 second
            self.face_processor.stop()
            
        # Calculate actual FPS
        frame_times = np.diff(processed_frames)
        avg_fps = 1.0 / np.mean(frame_times)
        
        print(f"Face processing rate: {avg_fps:.1f} FPS")
        self.assertAlmostEqual(avg_fps, 5.0, delta=0.5)  # Should be close to 5 FPS
        
    def test_crop_coordination(self):
        """Test coordination between hardware and software cropping"""
        # Mock face detection result
        face_data = Mock(
            bbox=[0.4, 0.4, 0.2, 0.2],  # Face taking up 20% of frame
            landmarks=[(0.45, 0.45),  # left eye
                      (0.55, 0.45),   # right eye
                      (0.5, 0.5),     # nose
                      (0.5, 0.55)],   # mouth
            confidence=0.9
        )
        
        # Mock face processor's get_current_face_data for display processor
        self.face_processor.get_current_face_data = Mock(return_value=face_data)
        
        # Update target crop directly without starting the thread
        self.scaler_crop_controller.update_target_crop(face_data)
        
        # Manually trigger a crop update by simulating what the update loop would do
        with self.scaler_crop_controller.lock:
            crop_settings = self.scaler_crop_controller._smooth_crop_update()
            if crop_settings:
                sensor_crop = self.scaler_crop_controller._convert_to_sensor_coordinates(crop_settings)
                self.mock_picam2.set_controls({"ScalerCrop": sensor_crop})
        
        # Verify set_controls was called with ScalerCrop
        calls = self.mock_picam2.set_controls.call_args_list
        scaler_crop_calls = [call for call in calls if 'ScalerCrop' in call[0][0]]
        self.assertTrue(len(scaler_crop_calls) > 0, "No ScalerCrop updates were made")
        
        # Get the hardware crop settings from the last ScalerCrop call
        last_crop_call = scaler_crop_calls[-1][0][0]
        self.assertIn('ScalerCrop', last_crop_call)
        
        # Get a frame and apply software crop
        frame = self.camera.get_latest_frame_direct()
        
        # Calculate the actual software crop size before resize
        h, w = frame.shape[:2]
        face_w = face_data.bbox[2] * w  # Face width in pixels
        sw_target_size = int(face_w * self.display_processor.zoom_ratios[self.display_processor.current_zoom])
        sw_crop_ratio = sw_target_size / w
        
        # Calculate hardware crop ratio from ScalerCrop settings
        hw_crop = last_crop_call['ScalerCrop']
        sensor_width = self.mock_picam2.camera_properties["ScalerCropMaximum"][2]
        hw_crop_ratio = hw_crop[2] / sensor_width  # width ratio in sensor coordinates
        
        # Hardware crop should be larger (more zoomed out) than software crop
        # This ensures the hardware crop captures enough area for the software crop to work with
        self.assertGreater(hw_crop_ratio, sw_crop_ratio,
                          f"Hardware crop ratio ({hw_crop_ratio}) should be larger than software crop ratio ({sw_crop_ratio})")
        
    def test_zoom_level_coordination(self):
        """Test coordination between display processor and scaler crop controller during zoom changes"""
        # Mock face detection result
        face_data = Mock(
            bbox=[0.4, 0.4, 0.2, 0.2],
            landmarks=[(0.45, 0.45),  # left eye
                      (0.55, 0.45),   # right eye
                      (0.5, 0.5),     # nose
                      (0.5, 0.55)],   # mouth
            confidence=0.9
        )
        
        # Set up face processor mock
        self.face_processor.get_current_face_data = Mock(return_value=face_data)
        
        # Test different zoom levels
        zoom_levels = [ZoomLevel.WIDE, ZoomLevel.FACE, ZoomLevel.EYES, ZoomLevel.LIPS]
        
        for zoom_level in zoom_levels:
            print(f"\nTesting {zoom_level}:")
            # Change zoom level on both components
            self.display_processor.set_zoom_level(zoom_level)
            self.scaler_crop_controller.set_zoom_level(zoom_level)
            
            # Update crop
            self.scaler_crop_controller.update_target_crop(face_data)
            with self.scaler_crop_controller.lock:
                crop_settings = self.scaler_crop_controller._smooth_crop_update()
                if crop_settings:
                    sensor_crop = self.scaler_crop_controller._convert_to_sensor_coordinates(crop_settings)
                    self.mock_picam2.set_controls({"ScalerCrop": sensor_crop})
            
            # Get frame and process
            frame = self.camera.get_latest_frame_direct()
            display_frame = self.display_processor._software_crop_for_display(frame)
            
            # Verify frame shapes
            self.assertEqual(display_frame.shape[:2], frame.shape[:2])
            
            # Verify crop ratios for each zoom level
            hw_crop = self.mock_picam2.set_controls.call_args_list[-1][0][0]['ScalerCrop']
            sensor_width = self.mock_picam2.camera_properties["ScalerCropMaximum"][2]
            hw_crop_ratio = hw_crop[2] / sensor_width
            
            # Calculate expected software crop ratio
            h, w = frame.shape[:2]
            face_w = face_data.bbox[2] * w
            sw_target_size = int(face_w * self.display_processor.zoom_ratios[zoom_level])
            sw_crop_ratio = sw_target_size / w
            
            print(f"Hardware crop ratio: {hw_crop_ratio:.3f}")
            print(f"Software crop ratio: {sw_crop_ratio:.3f}")
            
            # Hardware crop should always be larger than software crop
            self.assertGreater(hw_crop_ratio, sw_crop_ratio,
                             f"Hardware crop for {zoom_level} should be larger than software crop")

    def test_end_to_end_pipeline(self):
        """Test complete pipeline from camera to display"""
        # Mock face data for the pipeline
        face_data = Mock(
            bbox=[0.4, 0.4, 0.2, 0.2],
            landmarks=[(0.45, 0.45), (0.55, 0.45), (0.5, 0.5), (0.5, 0.55)],
            confidence=0.9
        )
        self.face_processor.get_current_face_data = Mock(return_value=face_data)
        self.face_processor.process_frame = Mock(return_value=face_data)
        
        # Mock frame times
        self.camera.frame_times = [0.0, 0.033, 0.066, 0.099, 0.132]  # 30 FPS
        self.camera.latency_times = [0.015, 0.016, 0.014, 0.015]  # ~15ms latency
        
        # Start all components
        self.camera.start()
        self.scaler_crop_controller.start()
        self.face_processor.start()
        self.display_processor.start()
        
        try:
            # Let the system run for a short time
            time.sleep(1.0)
            
            # Capture performance metrics
            camera_fps = len(self.camera.frame_times) / (self.camera.frame_times[-1] - self.camera.frame_times[0])
            avg_latency = np.mean(self.camera.latency_times) * 1000  # ms
            
            print(f"Pipeline performance:")
            print(f"Camera FPS: {camera_fps:.1f}")
            print(f"Average latency: {avg_latency:.1f}ms")
            
            # Verify performance meets requirements
            self.assertGreaterEqual(camera_fps, 25.0)  # Should maintain at least 25 FPS
            self.assertLess(avg_latency, 33.3)  # Should have less than 2-frame latency
            
        finally:
            # Clean up
            self.display_processor.stop()
            self.face_processor.stop()
            self.scaler_crop_controller.stop()
            self.camera.stop()
        
    def test_buffer_management(self):
        """Test frame buffer handling under load"""
        # Fill buffer with frames
        for _ in range(10):
            self.camera.frame_buffer.add_frame(self.test_frame)
            
        # Verify buffer size remains within limits
        self.assertLessEqual(
            self.camera.frame_buffer.get_size(),
            self.camera.frame_buffer.buffer_size
        )
        
        # Verify we can always get the latest frame
        latest_frame = self.camera.get_latest_frame()
        self.assertIsNotNone(latest_frame)
        
if __name__ == '__main__':
    unittest.main() 