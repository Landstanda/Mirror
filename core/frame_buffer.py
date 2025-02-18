from collections import deque
import threading
import numpy as np

class FrameBuffer:
    """
    Optimized frame buffer with minimal copying
    
    Features:
    - Thread-safe frame storage
    - Efficient frame access
    - Automatic buffer size management
    - Zero-copy frame retrieval for performance
    """
    
    def __init__(self, buffer_size=3):
        """
        Initialize frame buffer
        Args:
            buffer_size: Maximum number of frames to store
        """
        self.frames = deque(maxlen=buffer_size)
        self.lock = threading.Lock()
        
    def add_frame(self, frame: np.ndarray):
        """
        Add a new frame to the buffer without copying
        Args:
            frame: numpy array containing the frame data
        """
        if frame is not None:
            with self.lock:
                # Only copy if we need to preserve the original frame
                # In our case, the camera provides a new array each time
                self.frames.append(frame)
                
    def get_latest_frame(self) -> np.ndarray:
        """
        Get the most recent frame from the buffer without copying
        Returns:
            Reference to the most recent frame, or None if buffer is empty
        """
        with self.lock:
            return self.frames[-1] if self.frames else None
            
    def clear(self):
        """Clear all frames from the buffer"""
        with self.lock:
            self.frames.clear()
            
    @property
    def is_empty(self) -> bool:
        """Check if buffer is empty"""
        with self.lock:
            return len(self.frames) == 0
            
    @property
    def size(self) -> int:
        """Get current number of frames in buffer"""
        with self.lock:
            return len(self.frames) 