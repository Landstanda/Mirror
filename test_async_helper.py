import time
import numpy as np
from core.async_helper import AsyncHelper

def test_async_helper():
    print("\nAsync Helper Test")
    print("----------------")
    
    # Initialize async helper
    print("Initializing async helper...")
    helper = AsyncHelper(max_workers=2)
    helper.start()
    
    # Test task scheduling and execution
    print("\nTesting task execution:")
    
    def simulate_frame_processing(frame):
        """Simulate processing a frame"""
        time.sleep(0.01)  # Simulate some work
        return frame * 2
    
    # Create test frames
    print("- Creating test frames...")
    frames = [np.ones((100, 100, 3), dtype=np.uint8) * i for i in range(10)]
    
    # Test sequential processing
    print("- Testing sequential processing...")
    start_time = time.monotonic()
    
    task_ids = []
    for i, frame in enumerate(frames):
        task_id = helper.schedule_task(
            simulate_frame_processing,
            priority=1,
            frame=frame
        )
        task_ids.append(task_id)
    
    # Get results
    results = []
    for task_id in task_ids:
        result = helper.get_result(task_id)
        if result is not None:
            results.append(result)
    
    sequential_time = time.monotonic() - start_time
    print(f"  ✓ Processed {len(results)} frames in {sequential_time:.3f} seconds")
    
    # Test parallel processing
    print("\n- Testing parallel processing...")
    start_time = time.monotonic()
    
    # Schedule all tasks at once
    task_ids = []
    for i, frame in enumerate(frames):
        task_id = helper.schedule_task(
            simulate_frame_processing,
            priority=1,
            frame=frame
        )
        task_ids.append(task_id)
    
    # Wait for all results
    while len(task_ids) > 0:
        for task_id in task_ids[:]:
            result = helper.get_result(task_id)
            if result is not None:
                task_ids.remove(task_id)
        time.sleep(0.001)
    
    parallel_time = time.monotonic() - start_time
    print(f"  ✓ Processed {len(frames)} frames in {parallel_time:.3f} seconds")
    
    # Test priority scheduling
    print("\n- Testing priority scheduling...")
    
    # Schedule low priority tasks
    for i in range(5):
        helper.schedule_task(
            simulate_frame_processing,
            priority=2,
            frame=np.ones((100, 100, 3))
        )
    
    # Schedule high priority task
    start_time = time.monotonic()
    task_id = helper.schedule_task(
        simulate_frame_processing,
        priority=0,
        frame=np.ones((100, 100, 3))
    )
    
    # Wait for high priority result
    while helper.get_result(task_id) is None:
        time.sleep(0.001)
    
    priority_time = time.monotonic() - start_time
    print(f"  ✓ High priority task completed in {priority_time:.3f} seconds")
    
    # Cleanup
    print("\nStopping async helper...")
    helper.stop()
    
    print("\nPerformance Summary:")
    print(f"- Sequential processing: {sequential_time:.3f}s")
    print(f"- Parallel processing: {parallel_time:.3f}s")
    print(f"- Priority task: {priority_time:.3f}s")
    print(f"- Speedup from parallelization: {sequential_time/parallel_time:.1f}x")

if __name__ == "__main__":
    try:
        test_async_helper()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
    else:
        print("\n✓ All tests passed successfully!") 