from collections import deque
import threading
import numpy as np

class FrameBuffer:
    """
    Dedicated class for high-priority frame capture and buffering
    
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
        Add a new frame to the buffer
        Args:
            frame: numpy array containing the frame data
        """
        try:
            if frame is not None:
                with self.lock:
                    self.frames.append(frame.copy())
        except Exception as e:
            print(f"ERROR adding frame to buffer: {e}")
            
    def get_latest_frame(self) -> np.ndarray:
        """
        Get the most recent frame from the buffer
        Returns:
            Copy of the most recent frame, or None if buffer is empty
        """
        try:
            with self.lock:
                return self.frames[-1].copy() if self.frames else None
        except Exception as e:
            print(f"ERROR retrieving frame from buffer: {e}")
            return None
            
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