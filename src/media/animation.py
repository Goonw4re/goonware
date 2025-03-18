import time
import random
import logging
import threading
import traceback
import cv2
from PIL import ImageTk
import numpy as np
import tkinter as tk

logger = logging.getLogger(__name__)

class AnimationManager:
    """
    Manages animations for media windows, including:
    - Bounce animations for windows
    - GIF frame animation
    - Video playback
    """
    
    def __init__(self, display):
        """
        Initialize the AnimationManager.
        
        Args:
            display: Reference to the MediaDisplay instance
        """
        self.display = display
        self.bounce_thread = None
        self.bounce_event = threading.Event()
        self.bounce_running = False
        
        # Bounce settings - CRITICAL FIX: Increase default velocities
        self.bounce_interval = 0.04  # seconds between bounce updates (25fps)
        self.max_velocity = 10  # Maximum bounce velocity
        
        # Performance optimizations
        self.last_bounce_update = 0
        self.batch_size = 10  # Process windows in batches
        self.update_interval = 0.04  # 25 FPS
        
        # CRITICAL FIX: Force start the bounce thread on initialization
        print("DEBUG BOUNCE_INIT: Animation manager initialized")
    
    def start_bounce_thread(self):
        """Start the bounce animation thread"""
        # CRITICAL FIX: Completely refactored to ensure thread starts properly
        if self.bounce_running and self.bounce_thread and self.bounce_thread.is_alive():
            logger.warning("Bounce thread already running")
            print("DEBUG BOUNCE_THREAD: Thread already running, not starting again")
            return
            
        # Stop any existing thread first
        self.stop_bounce_thread()
        
        # Start a new thread
        logger.info("Starting bounce animation thread")
        print("DEBUG BOUNCE_THREAD: Starting new animation thread")
        self.bounce_running = True
        self.bounce_event.clear()
        
        self.bounce_thread = threading.Thread(target=self._bounce_loop, daemon=True)
        self.bounce_thread.start()
        
        # CRITICAL FIX: Verify thread started
        if self.bounce_thread.is_alive():
            print("DEBUG BOUNCE_THREAD: Thread started successfully")
        else:
            print("DEBUG BOUNCE_THREAD: Failed to start thread")
    
    def stop_bounce_thread(self):
        """Stop the bounce animation thread"""
        try:
            logger.info("Stopping bounce animation thread")
            
            # CRITICAL FIX: Check if thread is already stopped
            if not hasattr(self, 'bounce_running') or not self.bounce_running:
                logger.info("Bounce thread already stopped")
                return
            
            # Set flag to false first to signal thread to exit
            self.bounce_running = False
            
            # CRITICAL FIX: Set event to signal thread to exit
            if hasattr(self, 'bounce_event'):
                logger.info("Setting bounce event to signal thread exit")
                self.bounce_event.set()
            
            # Clear all window velocities to prevent further animation
            try:
                # CRITICAL FIX: Clear velocities from window_manager
                if hasattr(self.display, 'window_manager') and hasattr(self.display.window_manager, 'window_velocities'):
                    logger.info("Clearing window velocities")
                    self.display.window_manager.window_velocities.clear()
            except Exception as e:
                logger.error(f"Error clearing window velocities: {e}")
            
            # Join thread with short timeout to avoid blocking UI
            try:
                if hasattr(self, 'bounce_thread') and self.bounce_thread and self.bounce_thread.is_alive():
                    logger.info("Waiting for bounce thread to exit")
                    # CRITICAL FIX: Try to join with a timeout
                    self.bounce_thread.join(timeout=0.2)
                    
                    # CRITICAL FIX: Check if thread is still alive
                    if self.bounce_thread.is_alive():
                        logger.warning("Bounce thread did not terminate properly, forcing exit")
                        # Force thread to exit by setting daemon flag (if possible)
                        try:
                            self.bounce_thread.daemon = True
                        except:
                            pass
                    else:
                        logger.info("Bounce thread terminated successfully")
            except Exception as e:
                logger.error(f"Error stopping bounce thread: {e}")
            
            # CRITICAL FIX: Reset thread reference and ensure velocities are cleared
            self.bounce_thread = None
            
            # CRITICAL FIX: Double-check velocities are cleared
            try:
                if hasattr(self.display, 'window_manager') and hasattr(self.display.window_manager, 'window_velocities'):
                    self.display.window_manager.window_velocities.clear()
            except:
                pass
            
            logger.info("Bounce animation thread stopped")
        except Exception as e:
            logger.error(f"Error in stop_bounce_thread: {e}")
            # CRITICAL FIX: Last resort: try to reset thread state
            try:
                self.bounce_running = False
                self.bounce_thread = None
                if hasattr(self.display, 'window_manager') and hasattr(self.display.window_manager, 'window_velocities'):
                    self.display.window_manager.window_velocities.clear()
            except:
                pass
    
    def _bounce_loop(self):
        """Main loop for bouncing windows"""
        logger.info("Bounce animation thread started")
        print("DEBUG BOUNCE_THREAD: Animation thread started")
        
        # Track last debug time to avoid excessive logging
        last_debug_time = time.time()
        
        while self.bounce_running:
            try:
                # Throttle updates to maintain consistent frame rate
                current_time = time.time()
                elapsed = current_time - self.last_bounce_update
                
                if elapsed < self.update_interval:
                    # Sleep for the remaining time to maintain frame rate
                    sleep_time = max(0.001, self.update_interval - elapsed)
                    time.sleep(sleep_time)
                    continue
                
                # Update timestamp
                self.last_bounce_update = current_time
                
                # Debug logging (throttled)
                should_debug = (current_time - last_debug_time) > 5.0  # Debug every 5 seconds
                
                if should_debug:
                    # Update debug timestamp
                    last_debug_time = current_time
                    
                    # Log bounce status
                    bounce_enabled = getattr(self.display, 'bounce_enabled', False)
                    window_count = len(self.display.window_manager.window_velocities) if hasattr(self.display, 'window_manager') else 0
                    print(f"DEBUG BOUNCE_LOOP: Bounce enabled: {bounce_enabled}, Bouncing windows: {window_count}")
                
                # Process windows with velocities (regardless of bounce_enabled)
                if (hasattr(self.display, 'window_manager') and 
                    hasattr(self.display.window_manager, 'window_velocities') and
                    self.display.window_manager.window_velocities):
                    
                    # Get all windows with velocities
                    windows = list(self.display.window_manager.window_velocities.keys())
                    
                    if should_debug:
                        print(f"DEBUG BOUNCE_LOOP: Processing {len(windows)} bouncing windows")
                    
                    # Process windows in batches for better performance
                    for i in range(0, len(windows), self.batch_size):
                        batch = windows[i:i+self.batch_size]
                        self._process_bounce_batch(batch, should_debug)
                        
                        # Small sleep between batches to prevent UI freezing
                        if len(windows) > self.batch_size:
                            time.sleep(0.001)
                
                # Check if we should exit
                if self.bounce_event.is_set():
                    break
                    
            except Exception as e:
                logger.error(f"Error in bounce loop: {e}\n{traceback.format_exc()}")
                time.sleep(0.1)  # Prevent rapid error loops
        
        logger.info("Bounce animation thread stopped")
        print("DEBUG BOUNCE_THREAD: Animation thread stopped")
    
    def _process_bounce_batch(self, windows, should_debug):
        """Process a batch of bouncing windows"""
        for window in windows:
            try:
                # Skip if window no longer exists
                if not window.winfo_exists():
                    if should_debug:
                        print(f"DEBUG BOUNCE_LOOP: Window no longer exists, removing from tracking")
                    if window in self.display.window_manager.window_velocities:
                        del self.display.window_manager.window_velocities[window]
                    continue
                    
                # Get current position and velocity
                x, y = window.winfo_x(), window.winfo_y()
                dx, dy = self.display.window_manager.window_velocities[window]
                
                # Get window dimensions
                width = window.winfo_width()
                height = window.winfo_height()
                
                # Get the monitor this window belongs to
                monitor_idx = self.display.window_manager.window_monitors.get(window, 0)
                
                # Get the monitor boundaries
                if hasattr(self.display, 'monitors') and monitor_idx < len(self.display.monitors):
                    monitor = self.display.monitors[monitor_idx]
                    
                    # Define monitor boundaries
                    min_x = monitor.x
                    max_x = monitor.x + monitor.width
                    min_y = monitor.y
                    max_y = monitor.y + monitor.height
                    
                    if should_debug and random.random() < 0.01:  # Only log occasionally
                        print(f"DEBUG BOUNCE_MONITOR: Window on monitor {monitor_idx}: {min_x},{min_y} to {max_x},{max_y}")
                else:
                    # Fallback to full screen if monitor info not available
                    min_x = 0
                    max_x = window.winfo_screenwidth()
                    min_y = 0
                    max_y = window.winfo_screenheight()
                
                # Calculate new position
                new_x = x + dx
                new_y = y + dy
                
                # Check for collisions with monitor edges
                hit_edge = False
                
                # Handle horizontal collisions with monitor boundaries
                if new_x <= min_x:
                    # Hit left edge of monitor
                    dx = abs(dx) * random.uniform(0.9, 1.1)  # Bounce right with slight randomness
                    new_x = min_x
                    hit_edge = True
                    if should_debug:
                        print(f"DEBUG BOUNCE_COLLISION: Window hit left edge of monitor {monitor_idx}, new dx: {dx:.1f}")
                elif new_x + width >= max_x:
                    # Hit right edge of monitor
                    dx = -abs(dx) * random.uniform(0.9, 1.1)  # Bounce left with slight randomness
                    new_x = max_x - width
                    hit_edge = True
                    if should_debug:
                        print(f"DEBUG BOUNCE_COLLISION: Window hit right edge of monitor {monitor_idx}, new dx: {dx:.1f}")
                    
                # Handle vertical collisions with monitor boundaries
                if new_y <= min_y:
                    # Hit top edge of monitor
                    dy = abs(dy) * random.uniform(0.9, 1.1)  # Bounce down with slight randomness
                    new_y = min_y
                    hit_edge = True
                    if should_debug:
                        print(f"DEBUG BOUNCE_COLLISION: Window hit top edge of monitor {monitor_idx}, new dy: {dy:.1f}")
                elif new_y + height >= max_y:
                    # Hit bottom edge of monitor
                    dy = -abs(dy) * random.uniform(0.9, 1.1)  # Bounce up with slight randomness
                    new_y = max_y - height
                    hit_edge = True
                    if should_debug:
                        print(f"DEBUG BOUNCE_COLLISION: Window hit bottom edge of monitor {monitor_idx}, new dy: {dy:.1f}")
                
                # Add a small random variation to make movement more natural
                if not hit_edge and random.random() < 0.1:  # Only 10% of the time
                    dx += random.uniform(-0.2, 0.2)
                    dy += random.uniform(-0.2, 0.2)
                
                # Ensure minimum velocity
                min_speed = 5.0
                if abs(dx) < min_speed:
                    dx = min_speed if dx > 0 else -min_speed
                if abs(dy) < min_speed:
                    dy = min_speed if dy > 0 else -min_speed
                
                # Limit maximum velocity
                max_speed = 20
                dx = max(-max_speed, min(max_speed, dx))
                dy = max(-max_speed, min(max_speed, dy))
                
                # Update velocity
                self.display.window_manager.window_velocities[window] = (dx, dy)
                
                # Ensure the window stays within its monitor boundaries
                new_x = max(min_x, min(max_x - width, new_x))
                new_y = max(min_y, min(max_y - height, new_y))
                
                # Move window
                try:
                    window.geometry(f"+{int(new_x)}+{int(new_y)}")
                except Exception as e:
                    if should_debug:
                        print(f"DEBUG BOUNCE_ERROR: Failed to move window: {e}")
                
            except Exception as e:
                logger.error(f"Error processing bouncing window: {e}")
                # Remove problematic window from tracking
                if window in self.display.window_manager.window_velocities:
                    del self.display.window_manager.window_velocities[window]
    
    def animate_gif(self, window):
        """Animate a GIF by updating frames at specified intervals"""
        try:
            if window not in self.display.window_manager.gif_windows or not window.winfo_exists():
                return
                
            # Get GIF data
            gif_data = self.display.window_manager.gif_windows.get(window)
            if not gif_data:
                return
                
            frames = gif_data['frames']
            current_frame = gif_data['current_frame']
            label = gif_data['label']
            delay = gif_data['delay'] / 1000.0  # Convert from milliseconds to seconds
            
            # Ensure delay is reasonable
            if delay < 0.01:
                delay = 0.1  # Default 10 FPS if delay is too small
                
            # Update frame
            if 0 <= current_frame < len(frames):
                try:
                    label.configure(image=frames[current_frame])
                    
                    # Update current frame
                    current_frame = (current_frame + 1) % len(frames)
                    self.display.window_manager.gif_windows[window]['current_frame'] = current_frame
                    
                    # Schedule next frame update
                    window.after(int(delay * 1000), lambda: self.animate_gif(window))
                except Exception as e:
                    logger.error(f"Error updating GIF frame: {e}")
            else:
                logger.warning(f"Invalid GIF frame index: {current_frame}")
                
        except Exception as e:
            logger.error(f"Error in GIF animation: {e}\n{traceback.format_exc()}")
            
    def play_video(self, window):
        """Play a video in the window by reading frames from the video capture"""
        try:
            if window not in self.display.window_manager.video_windows or not window.winfo_exists():
                return
                
            # Get video data
            video_data = self.display.window_manager.video_windows.get(window)
            if not video_data:
                return
                
            cap = video_data['cap']
            label = video_data['label']
            width = video_data['width']
            height = video_data['height']
            fps = max(1, video_data['fps'])  # Ensure at least 1 FPS
            
            # Calculate frame delay
            delay = int(1000 / fps)  # in milliseconds
            
            # Read frame from video
            ret, frame = cap.read()
            
            if ret:
                # Convert frame from OpenCV BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Resize frame if needed
                if frame_rgb.shape[1] != width or frame_rgb.shape[0] != height:
                    frame_rgb = cv2.resize(frame_rgb, (width, height))
                
                # Convert to PIL Image and then to PhotoImage
                img = ImageTk.PhotoImage(image=np.array(frame_rgb))
                
                # Update label
                label.configure(image=img)
                label.image = img  # Keep reference to prevent garbage collection
                
                # Schedule next frame
                window.after(delay, lambda: self.play_video(window))
            else:
                # End of video, restart from beginning
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                window.after(delay, lambda: self.play_video(window))
                
        except Exception as e:
            logger.error(f"Error in video playback: {e}\n{traceback.format_exc()}")
            # Don't reschedule if there's an error
            try:
                # Remove video from active list
                if window in self.display.window_manager.video_windows:
                    if 'cap' in self.display.window_manager.video_windows[window]:
                        try:
                            self.display.window_manager.video_windows[window]['cap'].release()
                        except:
                            pass
            except:
                pass 