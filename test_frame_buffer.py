import time
import threading
import numpy as np
from core.frame_buffer import FrameBuffer

def test_frame_buffer():
    print("\nFrame Buffer Test")
    print("----------------")
    
    # Initialize frame buffer
    print("Initializing frame buffer...")
    buffer = FrameBuffer(buffer_size=3)
    
    # Test basic operations
    print("\nTesting basic operations:")
    
    # Test empty buffer
    print("- Testing empty buffer...")
    assert buffer.is_empty, "Buffer should be empty initially"
    assert buffer.size == 0, "Buffer size should be 0"
    assert buffer.get_latest_frame() is None, "Empty buffer should return None"
    print("  ✓ Empty buffer tests passed")
    
    # Test adding frames
    print("- Testing frame addition...")
    frame1 = np.zeros((100, 100, 3), dtype=np.uint8)  # Black frame
    frame2 = np.ones((100, 100, 3), dtype=np.uint8) * 255  # White frame
    frame3 = np.ones((100, 100, 3), dtype=np.uint8) * 128  # Gray frame
    
    buffer.add_frame(frame1)
    assert buffer.size == 1, "Buffer should have 1 frame"
    assert not buffer.is_empty, "Buffer should not be empty"
    
    buffer.add_frame(frame2)
    assert buffer.size == 2, "Buffer should have 2 frames"
    
    buffer.add_frame(frame3)
    assert buffer.size == 3, "Buffer should have 3 frames"
    print("  ✓ Frame addition tests passed")
    
    # Test buffer size limit
    print("- Testing buffer size limit...")
    frame4 = np.zeros((100, 100, 3), dtype=np.uint8)
    buffer.add_frame(frame4)
    assert buffer.size == 3, "Buffer should maintain max size of 3"
    print("  ✓ Buffer size limit test passed")
    
    # Test frame retrieval
    print("- Testing frame retrieval...")
    latest = buffer.get_latest_frame()
    assert latest is not None, "Should get a frame"
    assert np.array_equal(latest, frame4), "Should get the most recent frame"
    print("  ✓ Frame retrieval test passed")
    
    # Test thread safety
    print("\nTesting thread safety:")
    
    def producer():
        for i in range(100):
            frame = np.ones((100, 100, 3), dtype=np.uint8) * i
            buffer.add_frame(frame)
            time.sleep(0.001)
    
    def consumer():
        frames_received = 0
        for i in range(50):
            frame = buffer.get_latest_frame()
            if frame is not None:
                frames_received += 1
            time.sleep(0.002)
        return frames_received
    
    # Create and start threads
    producer_thread = threading.Thread(target=producer)
    consumer_thread = threading.Thread(target=consumer)
    
    print("- Running concurrent access test...")
    producer_thread.start()
    consumer_thread.start()
    
    producer_thread.join()
    consumer_thread.join()
    
    print("  ✓ Thread safety test completed")
    
    # Test clear operation
    print("\nTesting clear operation:")
    buffer.clear()
    assert buffer.is_empty, "Buffer should be empty after clear"
    assert buffer.size == 0, "Buffer size should be 0 after clear"
    print("  ✓ Clear operation test passed")
    
    print("\nAll tests completed successfully!")

if __name__ == "__main__":
    try:
        test_frame_buffer()
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    else:
        print("\n✓ All tests passed successfully!") 