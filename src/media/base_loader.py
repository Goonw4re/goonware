import tkinter as tk
import logging
import random
import concurrent.futures
from typing import List, Callable, Any, Optional

logger = logging.getLogger(__name__)

class MediaLoaderBase:
    """Base class for all media loaders with common window functionality"""
    
    def __init__(self, display):
        self.display = display
        # Create window pool for reusing windows
        self.window_pool = []
        self.max_pool_size = 30
        
        # Create thread pool executor for parallel processing
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self.pending_tasks = []
    
    def _get_window_from_pool(self):
        """Get a window from the pool or create a new one"""
        if self.window_pool:
            window = self.window_pool.pop()
            return window
        else:
            return self._create_base_window()
    
    def _return_window_to_pool(self, window):
        """Return a window to the pool for reuse"""
        if len(self.window_pool) < self.max_pool_size:
            try:
                # Clear window contents
                for widget in window.winfo_children():
                    widget.destroy()
                # Reset window properties
                window.withdraw()
                self.window_pool.append(window)
                return True
            except:
                return False
        return False
    
    def _create_base_window(self):
        """Create a new window with base configuration"""
        window = tk.Toplevel()
        window.overrideredirect(True)  # Remove window decorations
        window.attributes('-alpha', 0.95)  # Slight transparency
        window.withdraw()  # Hide window initially
        return window
    
    def _position_window(self, window, width, height):
        """Position window at random screen position"""
        x, y, monitor_idx = self.display.get_random_screen_position(width, height)
        window.geometry(f"{width}x{height}+{x}+{y}")
        return window
    
    def submit_task(self, func: Callable, *args, **kwargs) -> concurrent.futures.Future:
        """Submit a task to the thread pool and track it"""
        future = self.executor.submit(func, *args, **kwargs)
        self.pending_tasks.append(future)
        future.add_done_callback(lambda f: self.pending_tasks.remove(f) if f in self.pending_tasks else None)
        return future
    
    def process_batch(self, items: List[Any], processor_func: Callable, max_parallel: int = 4) -> List[Any]:
        """Process a batch of items in parallel and return results
        
        Args:
            items: List of items to process
            processor_func: Function to process each item
            max_parallel: Maximum number of parallel tasks
            
        Returns:
            List of results in the same order as items
        """
        # Use a smaller pool for this specific batch
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
            futures = [executor.submit(processor_func, item) for item in items]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        return results
    
    def preload_media(self, paths: List[str], loader_func: Callable, callback: Optional[Callable] = None):
        """Preload media files in background threads
        
        Args:
            paths: List of media paths to preload
            loader_func: Function to load each media item
            callback: Optional callback when all preloading is complete
        """
        if not paths:
            if callback:
                callback([])
            return
            
        # Select a sample of paths to preload (up to 10)
        sample_size = min(10, len(paths))
        sample_paths = random.sample(paths, sample_size)
        
        def on_complete(futures):
            try:
                # Get results, ignoring any failures
                results = []
                for future in futures:
                    try:
                        if future.done():
                            result = future.result()
                            if result:
                                results.append(result)
                    except Exception as e:
                        logger.error(f"Error in preload task: {e}")
                
                # Call callback with results
                if callback:
                    callback(results)
            except Exception as e:
                logger.error(f"Error processing preload results: {e}")
        
        # Submit preload tasks
        futures = [self.submit_task(loader_func, path) for path in sample_paths]
        
        # Submit a callback task once all are complete
        if callback:
            callback_future = self.executor.submit(
                lambda: on_complete(futures)
            )
        
    def cleanup(self):
        """Clean up resources"""
        # Cancel all pending tasks
        for task in self.pending_tasks:
            if not task.done():
                task.cancel()
        
        # Shutdown executor
        self.executor.shutdown(wait=False)
        
        # Clear window pool
        for window in self.window_pool:
            try:
                window.destroy()
            except:
                pass
        self.window_pool.clear() 