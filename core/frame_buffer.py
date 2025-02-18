from collections import deque
import threading
import numpy as np
from typing import Optional
import queue

class FrameBuffer:
    """
    Optimized frame buffer with minimal locking and atomic operations
    
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
        self._frames = queue.Queue(maxsize=buffer_size)
        self._latest_frame = None  # Atomic latest frame reference
        self._latest_frame_lock = threading.Lock()  # Separate lock for latest frame
        
    def add_frame(self, frame: np.ndarray):
        """Add a new frame, dropping oldest if buffer is full"""
        if frame is not None:
            # Update latest frame atomically
            with self._latest_frame_lock:
                self._latest_frame = frame
            
            # Try to add to queue without blocking
            try:
                self._frames.put_nowait(frame)
            except queue.Full:
                # Queue is full, remove oldest frame
                try:
                    self._frames.get_nowait()
                    self._frames.put_nowait(frame)
                except (queue.Empty, queue.Full):
                    pass  # Race condition handled gracefully
                
    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Get latest frame with minimal locking"""
        with self._latest_frame_lock:
            return self._latest_frame
            
    def clear(self):
        """Clear buffer efficiently"""
        while not self._frames.empty():
            try:
                self._frames.get_nowait()
            except queue.Empty:
                break
        with self._latest_frame_lock:
            self._latest_frame = None
            
    @property
    def is_empty(self) -> bool:
        """Check if buffer is empty without locking"""
        return self._frames.empty() and self._latest_frame is None
            
    @property
    def size(self) -> int:
        """Get approximate size without locking"""
        return self._frames.qsize() 