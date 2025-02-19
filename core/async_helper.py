import threading
import asyncio
import queue
from typing import Any, Callable, Optional
from concurrent.futures import ThreadPoolExecutor
import time

class AsyncHelper:
    """
    Utility class for managing asynchronous operations and event coordination
    
    Features:
    - Event-driven architecture for better performance
    - Thread pool for CPU-intensive tasks
    - Non-blocking operation queues
    - Priority-based task scheduling
    - Automatic resource cleanup
    """
    
    def __init__(self, max_workers: int = 2):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.loop = asyncio.new_event_loop()
        self.thread = None
        self.running = False
        self.task_queue = queue.PriorityQueue()
        self.results = {}
        self.lock = threading.Lock()
        
    def start(self):
        """Start the async helper thread"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run_event_loop, daemon=True)
            self.thread.start()
            
    def stop(self):
        """Stop the async helper and cleanup resources"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        self.executor.shutdown(wait=False)
        
    def _run_event_loop(self):
        """Main event loop for processing async tasks"""
        asyncio.set_event_loop(self.loop)
        while self.running:
            try:
                # Process any pending tasks
                while not self.task_queue.empty():
                    priority, task_id, func, args, kwargs = self.task_queue.get_nowait()
                    self._process_task(task_id, func, args, kwargs)
                    self.task_queue.task_done()
                
                # Small sleep to prevent CPU thrashing
                time.sleep(0.001)
                
            except Exception as e:
                print(f"Error in event loop: {e}")
                
    def _process_task(self, task_id: str, func: Callable, args: tuple, kwargs: dict):
        """Process a single task in the thread pool with minimal locking"""
        try:
            future = self.executor.submit(func, *args, **kwargs)
            result = future.result(timeout=1.0)
            
            # Use non-blocking dictionary update
            if result is not None:
                self.results[task_id] = result
                
        except Exception as e:
            print(f"Error processing task {task_id}: {e}")
            
    def schedule_task(self, func: Callable, priority: int = 1, 
                     task_id: Optional[str] = None, *args, **kwargs) -> str:
        """
        Schedule task with minimal blocking
        
        Args:
            func: Function to execute
            priority: Task priority (lower number = higher priority)
            task_id: Optional task identifier
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
        """
        if task_id is None:
            task_id = str(time.monotonic())
            
        try:
            # Convert args and kwargs to proper format
            task_args = args if args else ()
            task_kwargs = kwargs if kwargs else {}
            
            # Remove 'args' and 'kwargs' from task_kwargs if they exist
            task_kwargs.pop('args', None)
            task_kwargs.pop('kwargs', None)
            
            self.task_queue.put_nowait((priority, task_id, func, task_args, task_kwargs))
        except queue.Full:
            print(f"Warning: Task queue full, dropping task {task_id}")
            
        return task_id
        
    def get_result(self, task_id: str, clear: bool = True) -> Any:
        """Get result with minimal locking using dict.pop()"""
        if clear:
            return self.results.pop(task_id, None)
        return self.results.get(task_id)
        
    def clear_results(self):
        """Clear results without locking"""
        self.results.clear()
            
    @property
    def pending_tasks(self) -> int:
        """Get number of pending tasks"""
        return self.task_queue.qsize()
        
    @property
    def has_results(self) -> bool:
        """Check if there are any results available"""
        with self.lock:
            return len(self.results) > 0 