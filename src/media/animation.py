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
        
        # IMPROVED: Faster bouncing with better physics
        self.bounce_interval = 0.03  # seconds between bounce updates (33fps instead of 20fps)
        self.max_velocity = 12  # Maximum bounce velocity (increased from 6)
        self.min_velocity = 5  # Minimum bounce velocity (increased from 3)
        
        # Performance optimizations
        self.last_bounce_update = 0
        self.batch_size = 20  # Process more windows in batches (increased from 10) 
        self.update_interval = 0.025  # 40 FPS (faster than previous 25 FPS)
        
        # Additional physics properties for smoother bouncing
        self.rebound_factor = 1.05  # Slightly faster after bouncing (energy gain)
        self.friction = 0.995  # Very low friction to maintain speed
        
        # CRITICAL FIX: Force start the bounce thread on initialization
        print("DEBUG BOUNCE_INIT: Animation manager initialized with faster bouncing")
    
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
                    self.bounce_thread.join(timeout=0.1)  # Reduced timeout to avoid UI blocking
                    
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
        
        # IMPROVEMENT: Use a more efficient time approach with fixed timestep
        fixed_timestep = self.update_interval
        accumulated_time = 0
        last_time = time.time()
        
        while self.bounce_running:
            try:
                # IMPROVEMENT: More efficient timing logic
                current_time = time.time()
                frame_time = current_time - last_time
                last_time = current_time
                
                # Prevent spiral of death if frame_time is too large
                if frame_time > 0.1:
                    frame_time = 0.1
                
                accumulated_time += frame_time
                
                # Update as many times as needed to catch up
                update_count = 0
                while accumulated_time >= fixed_timestep and update_count < 3:  # Limit to 3 updates per frame
                    self._update_bouncing_windows()
                    accumulated_time -= fixed_timestep
                    update_count += 1
                
                # Debug logging (throttled)
                should_debug = (current_time - last_debug_time) > 10.0  # Reduced debug frequency to every 10 seconds
                
                if should_debug:
                    # Update debug timestamp
                    last_debug_time = current_time
                    
                    # Log bounce status
                    bounce_enabled = getattr(self.display, 'bounce_enabled', False)
                    window_count = len(self.display.window_manager.window_velocities) if hasattr(self.display, 'window_manager') else 0
                    print(f"DEBUG BOUNCE_LOOP: Bounce enabled: {bounce_enabled}, Bouncing windows: {window_count}")
                
                # Check if we should exit
                if self.bounce_event.is_set():
                    break
                
                # Sleep for a small amount to prevent excessive CPU usage
                # IMPROVEMENT: Adaptive sleep based on time remaining until next update
                remaining_time = fixed_timestep - (accumulated_time % fixed_timestep)
                sleep_time = max(0.001, remaining_time * 0.9)  # Sleep slightly less than needed to avoid missing frames
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            except Exception as e:
                logger.error(f"Error in bounce loop: {e}\n{traceback.format_exc()}")
                time.sleep(0.1)  # Prevent rapid error loops
        
        logger.info("Bounce animation thread stopped")
        print("DEBUG BOUNCE_THREAD: Animation thread stopped")
    
    def _update_bouncing_windows(self):
        """Update all bouncing windows in one step"""
        # Skip if no window manager available
        if not hasattr(self.display, 'window_manager') or not hasattr(self.display.window_manager, 'window_velocities'):
            return
            
        # Get all windows with velocities
        velocities = self.display.window_manager.window_velocities
        if not velocities:
            return
            
        windows = list(velocities.keys())
        
        # Process windows in batches for better performance
        for i in range(0, len(windows), self.batch_size):
            batch = windows[i:i+self.batch_size]
            self._process_bounce_batch(batch, False)  # Set debug to False for speed
            
            # Small sleep between batches to prevent UI freezing
            if len(windows) > self.batch_size * 2:  # Only sleep if many windows
                time.sleep(0.0005)  # Reduced sleep time from 0.001 to 0.0005
    
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
                
                # IMPROVEMENT: Apply very slight friction to simulate air resistance
                dx *= self.friction
                dy *= self.friction
                
                # Calculate new position
                new_x = x + dx
                new_y = y + dy
                
                # IMPROVED: Better collision physics for more natural bouncing
                hit_edge = False
                
                # Handle horizontal collisions with monitor boundaries
                if new_x <= min_x:
                    # Hit left edge of monitor
                    dx = abs(dx) * self.rebound_factor  # Bounce right with energy gain 
                    new_x = min_x + 1  # Offset by 1 pixel to prevent sticking
                    hit_edge = True
                elif new_x + width >= max_x:
                    # Hit right edge of monitor
                    dx = -abs(dx) * self.rebound_factor  # Bounce left with energy gain
                    new_x = max_x - width - 1  # Offset by 1 pixel to prevent sticking
                    hit_edge = True
                    
                # Handle vertical collisions with monitor boundaries
                if new_y <= min_y:
                    # Hit top edge of monitor
                    dy = abs(dy) * self.rebound_factor  # Bounce down with energy gain
                    new_y = min_y + 1  # Offset by 1 pixel to prevent sticking
                    hit_edge = True
                elif new_y + height >= max_y:
                    # Hit bottom edge of monitor
                    dy = -abs(dy) * self.rebound_factor  # Bounce up with energy gain
                    new_y = max_y - height - 1  # Offset by 1 pixel to prevent sticking
                    hit_edge = True
                
                # IMPROVEMENT: Occasionally add a burst of speed for more dynamic movement
                if hit_edge and random.random() < 0.2:  # 20% chance on collision
                    speed_boost = random.uniform(1.1, 1.3)  # 10-30% speed boost
                    dx *= speed_boost
                    dy *= speed_boost
                    if should_debug:
                        print(f"DEBUG BOUNCE_PHYSICS: Speed boost applied: {speed_boost:.2f}x")
                
                # Add a small random variation to make movement more natural - only when not hitting edges
                if not hit_edge and random.random() < 0.05:  # Reduced chance from 10% to 5%
                    dx += random.uniform(-0.3, 0.3)  # Increased randomness for more liveliness
                    dy += random.uniform(-0.3, 0.3)
                
                # Ensure minimum velocity
                if abs(dx) < self.min_velocity:
                    dx = self.min_velocity if dx > 0 else -self.min_velocity
                if abs(dy) < self.min_velocity:
                    dy = self.min_velocity if dy > 0 else -self.min_velocity
                
                # Limit maximum velocity
                dx = max(-self.max_velocity, min(self.max_velocity, dx))
                dy = max(-self.max_velocity, min(self.max_velocity, dy))
                
                # Update velocity
                self.display.window_manager.window_velocities[window] = (dx, dy)
                
                # Ensure the window stays within its monitor boundaries
                new_x = max(min_x, min(max_x - width, new_x))
                new_y = max(min_y, min(max_y - height, new_y))
                
                # Move window - use integer positions for better performance
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