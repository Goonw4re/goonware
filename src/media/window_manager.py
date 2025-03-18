import tkinter as tk
import logging
import random
import traceback
import os
import time
import cv2

logger = logging.getLogger(__name__)

class WindowManager:
    def __init__(self, display):
        self.display = display
        self.current_windows = []
        self.gif_windows = {}
        self.video_windows = {}
        self.window_velocities = {}
        
        # Performance optimization: track window creation times
        self.window_creation_times = {}
        
        # Track which monitor each window belongs to
        self.window_monitors = {}
        
        # Batch processing for window updates
        self.pending_updates = []
        self.last_batch_update = 0
    
    def window_count(self):
        """Get the total number of active windows"""
        return len(self.current_windows)
    
    def has_windows(self):
        """Check if there are any active windows"""
        return self.window_count() > 0
    
    def get_random_screen_position(self, width, height):
        """Get a random position on one of the active monitors"""
        try:
            # Get position from MediaDisplay
            print(f"DEBUG WINDOW_MGR: Getting position for window {width}x{height}")
            print(f"DEBUG WINDOW_MGR: Active monitors: {self.display.active_monitors}")
            
            # Delegate to MediaDisplay
            position = self.display.get_random_screen_position(width, height)
            
            print(f"DEBUG WINDOW_MGR: Got position: {position}")
            return position
            
        except Exception as e:
            print(f"DEBUG WINDOW_MGR: Error getting position: {e}")
            # Return a safe default position
            return 100, 100
        
    def create_close_button(self, window):
        """Create a smaller close button with a black background"""
        close_frame = tk.Frame(window, bg='black', width=14, height=14)
        close_frame.place(relx=1.0, x=-18, y=3)
        close_frame.pack_propagate(False)

        close_btn = tk.Label(
            close_frame,
            text="×",
            font=('Segoe UI', 9, 'bold'),
            fg='white',
            bg='black',
            cursor='hand2',
            padx=1,
            pady=0
        )
        close_btn.pack(expand=True, fill='both')

        # Close functionality
        def close_window(event):
            self.remove_window(window)

        close_btn.bind('<Button-1>', close_window)
        close_frame.bind('<Button-1>', close_window)

        # Hover effects
        def on_enter(e):
            close_btn.configure(fg='red')

        def on_leave(e):
            close_btn.configure(fg='white')

        close_btn.bind('<Enter>', on_enter)
        close_btn.bind('<Leave>', on_leave)
        close_frame.bind('<Enter>', on_enter)
        close_frame.bind('<Leave>', on_leave)

        return close_frame
        
    def add_window(self, window, enable_bounce=False):
        """Add a window to the management list"""
        # Add window to tracking list
        self.current_windows.append(window)
        
        # Track creation time for performance optimization
        self.window_creation_times[window] = time.time()
        
        print(f"DEBUG WINDOW_ADD: Added window to tracking, current count: {len(self.current_windows)}")
        
        # Handle bouncing
        if enable_bounce:
            # CRITICAL FIX: Directly access bounce_enabled and bounce_chance
            bounce_enabled = False
            bounce_chance = 0.0
            
            if hasattr(self.display, 'bounce_enabled'):
                bounce_enabled = self.display.bounce_enabled
                bounce_chance = getattr(self.display, 'bounce_chance', 0.15 if bounce_enabled else 0.0)
            
            print(f"DEBUG WINDOW_BOUNCE: Window added with bounce_enabled={bounce_enabled}, bounce_chance={bounce_chance:.2f}")
            
            if bounce_enabled:
                # Determine if this window should bounce based on random chance (15%)
                bounce_roll = random.random()
                should_bounce = bounce_roll < bounce_chance
                
                print(f"DEBUG WINDOW_BOUNCE: Bounce roll: {bounce_roll:.3f}, threshold: {bounce_chance:.3f}, should_bounce: {should_bounce}")
                
                if should_bounce:
                    # Set initial velocity - higher values for more noticeable movement
                    velocity_x = random.choice([-1, 1]) * random.randint(10, 20)
                    velocity_y = random.choice([-1, 1]) * random.randint(10, 20)
                    
                    # Add to velocity tracking
                    self.window_velocities[window] = (velocity_x, velocity_y)
                    
                    print(f"DEBUG WINDOW_BOUNCE: Added bouncing to window with velocity: ({velocity_x}, {velocity_y})")
                    logger.info(f"Added bouncing to window with velocity: ({velocity_x}, {velocity_y})")
                    
                    # Ensure animation thread is running
                    if hasattr(self.display, 'animation_manager'):
                        print(f"DEBUG WINDOW_BOUNCE: Starting animation thread for new bouncing window")
                        self.display.animation_manager.start_bounce_thread()
                else:
                    print(f"DEBUG WINDOW_BOUNCE: Window not selected for bouncing (roll: {bounce_roll:.3f})")
        
        # Remove oldest windows if we exceed the maximum
        self._enforce_window_limit()
    
    def _enforce_window_limit(self):
        """Enforce the maximum window limit by removing oldest windows"""
        max_windows = getattr(self.display, 'max_windows', 5)
        
        # Sort windows by creation time if we need to remove any
        if len(self.current_windows) > max_windows:
            # Create a list of (window, creation_time) tuples
            windows_with_times = []
            for window in self.current_windows:
                creation_time = self.window_creation_times.get(window, 0)
                windows_with_times.append((window, creation_time))
            
            # Sort by creation time (oldest first)
            windows_with_times.sort(key=lambda x: x[1])
            
            # Remove oldest windows until we're under the limit
            windows_to_remove = windows_with_times[:len(self.current_windows) - max_windows]
            
            for window, _ in windows_to_remove:
                logger.info(f"Removing oldest window, exceeding max_windows ({max_windows})")
                print(f"DEBUG WINDOW_ADD: Removing oldest window, exceeding max_windows ({max_windows})")
                self.remove_window(window)
    
    def remove_window(self, window):
        """Remove a window and clean up resources"""
        try:
            # Check if this is a video window
            if window in self.video_windows:
                # Release video capture
                info = self.video_windows[window]
                if 'cap' in info:
                    info['cap'].release()
                
                # Clean up temporary file if it exists
                if 'temp_file' in info and info['temp_file'] and os.path.exists(info['temp_file']):
                    try:
                        os.remove(info['temp_file'])
                        logger.info(f"Removed temporary video file: {info['temp_file']}")
                    except Exception as e:
                        logger.error(f"Error removing temporary video file: {e}")
                
                # Remove from video windows
                del self.video_windows[window]
            
            # Remove from GIF windows
            if window in self.gif_windows:
                del self.gif_windows[window]
            
            # Remove from velocity tracking
            if window in self.window_velocities:
                del self.window_velocities[window]
            
            # Remove from creation time tracking
            if window in self.window_creation_times:
                del self.window_creation_times[window]
            
            # Remove from monitor tracking
            if window in self.window_monitors:
                del self.window_monitors[window]
            
            # Remove from current windows
            if window in self.current_windows:
                self.current_windows.remove(window)
            
            # Destroy window if it still exists
            try:
                if window.winfo_exists():
                    window.destroy()
            except Exception as e:
                logger.error(f"Error destroying window: {e}")
                
        except tk.TclError:
            # Window already destroyed
            pass
        except Exception as e:
            logger.error(f"Error removing window: {e}\n{traceback.format_exc()}")
    
    def remove_window_safely(self, window):
        """Safely remove a window after its display time has elapsed"""
        try:
            if not self.display.running:
                # If display is stopped, don't bother with cleanup
                return
                
            logger.info(f"Removing window after delay")
            
            # Check if window still exists before attempting to remove it
            try:
                if not window.winfo_exists():
                    logger.info("Window no longer exists, skipping removal")
                    return
            except tk.TclError:
                logger.info("Window reference is invalid, skipping removal")
                return
                
            # Check if window still exists in our tracking lists
            if (window not in self.current_windows and 
                window not in self.video_windows and 
                window not in self.gif_windows):
                logger.info("Window already removed from tracking")
                return
                
            # Remove the window
            self.remove_window(window)
            
        except Exception as e:
            logger.error(f"Error removing window after delay: {e}\n{traceback.format_exc()}")
            # Try one more time with basic approach
            try:
                if window.winfo_exists():
                    window.destroy()
            except:
                pass
    
    def remove_after_delay(self, window):
        """Schedule a window to be removed after a delay based on media type"""
        import threading
        
        try:
            # Determine appropriate delay based on media type
            if window in self.video_windows:
                # For videos, use a longer delay based on video duration if available
                info = self.video_windows[window]
                if 'cap' in info and info['cap'].isOpened():
                    # Get video duration in seconds
                    fps = info.get('fps', 30)
                    if fps <= 0:
                        fps = 30  # Default to 30fps if invalid
                    
                    frame_count = int(info['cap'].get(cv2.CAP_PROP_FRAME_COUNT))
                    duration = frame_count / fps
                    
                    # Use video duration with a minimum of 10 seconds and maximum of 60 seconds
                    delay = min(max(duration * 0.95, 10.0), 60.0)
                    logger.info(f"Video window will be removed after {delay:.1f} seconds (duration: {duration:.1f}s)")
                else:
                    # Default video delay if duration can't be determined
                    delay = random.uniform(15.0, 30.0)
                    logger.info(f"Video window will be removed after {delay:.1f} seconds (default)")
            elif window in self.gif_windows:
                # For GIFs, use a medium delay
                delay = random.uniform(10.0, 20.0)
                logger.info(f"GIF window will be removed after {delay:.1f} seconds")
            else:
                # For images, use a shorter delay
                delay = random.uniform(8.0, 15.0)
                logger.info(f"Image window will be removed after {delay:.1f} seconds")
            
            # Schedule window removal with the calculated delay
            timer = threading.Timer(delay, lambda: self.remove_window_safely(window))
            timer.daemon = True
            timer.start()
            
        except Exception as e:
            logger.error(f"Error scheduling window removal: {e}\n{traceback.format_exc()}")
    
    def clear_windows(self):
        """Clear all windows using safe methods"""
        try:
            logger.info("Clearing all windows...")
            
            # Save references to all windows
            windows_to_close = []
            for window_dict in [self.gif_windows, self.video_windows]:
                windows_to_close.extend(list(window_dict.keys()))
            windows_to_close.extend(list(self.current_windows))
            
            # Close windows safely one by one
            for window in windows_to_close:
                try:
                    if hasattr(window, 'winfo_exists') and window.winfo_exists():
                        # Hide window first
                        window.withdraw()
                        # Then destroy it
                        window.destroy()
                except Exception as e:
                    logger.error(f"Error safely closing window: {e}")
            
            # Clear tracking dictionaries
            self.gif_windows.clear()
            self.video_windows.clear()
            self.current_windows.clear()
            self.window_velocities.clear()
            self.window_creation_times.clear()
            self.window_monitors.clear()
            
            logger.info("All windows cleared successfully")
        except Exception as e:
            logger.error(f"Error clearing windows: {e}\n{traceback.format_exc()}")
    
    def force_close_all(self):
        """Emergency force close of all popup windows"""
        try:
            logger.info("Emergency force close of all popup windows")
            
            # CRITICAL FIX: Get a copy of window lists to avoid modification during iteration
            windows_to_close = []
            try:
                # Collect all windows from all tracking collections
                if hasattr(self, 'gif_windows'):
                    windows_to_close.extend(list(self.gif_windows.keys()))
                if hasattr(self, 'video_windows'):
                    windows_to_close.extend(list(self.video_windows.keys()))
                if hasattr(self, 'current_windows'):
                    windows_to_close.extend(list(self.current_windows))
                
                # Log the number of windows to close
                logger.info(f"Found {len(windows_to_close)} windows to force close")
            except Exception as e:
                logger.error(f"Error collecting windows to close: {e}")
            
            # CRITICAL FIX: First clear all velocities to prevent animation updates
            try:
                if hasattr(self, 'window_velocities'):
                    self.window_velocities.clear()
                    logger.info("Cleared window velocities")
            except Exception as e:
                logger.error(f"Error clearing window velocities: {e}")
            
            # CRITICAL FIX: Close all windows immediately without update_idletasks
            for window in windows_to_close:
                try:
                    if hasattr(window, 'winfo_exists') and window.winfo_exists():
                        # Force destroy with error handling
                        try:
                            # CRITICAL FIX: Use destroy() directly without withdraw
                            logger.debug(f"Destroying window {window}")
                            window.destroy()
                        except Exception as e:
                            logger.error(f"Error destroying window: {e}")
                            # Last resort: try to withdraw then destroy
                            try:
                                window.withdraw()
                                window.destroy()
                            except Exception as e2:
                                logger.error(f"Error in fallback window destruction: {e2}")
                except Exception as e:
                    logger.error(f"Error checking window existence: {e}")
            
            # CRITICAL FIX: Force update to ensure windows are closed
            try:
                if hasattr(self.display, 'parent') and self.display.parent:
                    self.display.parent.update_idletasks()
            except Exception as e:
                logger.error(f"Error updating parent: {e}")
            
            # CRITICAL FIX: Clear tracking dictionaries after destroying windows
            try:
                # Clear all collections
                if hasattr(self, 'gif_windows'):
                    self.gif_windows.clear()
                if hasattr(self, 'video_windows'):
                    self.video_windows.clear()
                if hasattr(self, 'current_windows'):
                    self.current_windows.clear()
                if hasattr(self, 'window_velocities'):
                    self.window_velocities.clear()
                if hasattr(self, 'window_creation_times'):
                    self.window_creation_times.clear()
                if hasattr(self, 'window_monitors'):
                    self.window_monitors.clear()
                
                # Reset currently_displayed counter in the display
                if hasattr(self.display, 'currently_displayed'):
                    self.display.currently_displayed = 0
                
                logger.info(f"Cleared all window tracking collections")
            except Exception as e:
                logger.error(f"Error clearing window collections: {e}")
            
            # CRITICAL FIX: Verify all windows are closed
            window_count = 0
            if hasattr(self, 'current_windows'):
                window_count += len(self.current_windows)
            if hasattr(self, 'gif_windows'):
                window_count += len(self.gif_windows)
            if hasattr(self, 'video_windows'):
                window_count += len(self.video_windows)
            
            if window_count > 0:
                logger.warning(f"Still have {window_count} windows after cleanup, resetting collections")
                # Reset all collections as a last resort
                if hasattr(self, 'gif_windows'):
                    self.gif_windows = {}
                if hasattr(self, 'video_windows'):
                    self.video_windows = {}
                if hasattr(self, 'current_windows'):
                    self.current_windows = []
                if hasattr(self, 'window_velocities'):
                    self.window_velocities = {}
                if hasattr(self, 'window_creation_times'):
                    self.window_creation_times = {}
                if hasattr(self, 'window_monitors'):
                    self.window_monitors = {}
                if hasattr(self.display, 'currently_displayed'):
                    self.display.currently_displayed = 0
            
            logger.info(f"Emergency force close completed ({len(windows_to_close)} windows)")
        except Exception as e:
            logger.error(f"Unexpected error in force_close_all: {e}")
            # CRITICAL FIX: Last resort cleanup
            try:
                if hasattr(self, 'gif_windows'):
                    self.gif_windows = {}
                if hasattr(self, 'video_windows'):
                    self.video_windows = {}
                if hasattr(self, 'current_windows'):
                    self.current_windows = []
                if hasattr(self, 'window_velocities'):
                    self.window_velocities = {}
                if hasattr(self, 'window_creation_times'):
                    self.window_creation_times = {}
                if hasattr(self, 'window_monitors'):
                    self.window_monitors = {}
                if hasattr(self.display, 'currently_displayed'):
                    self.display.currently_displayed = 0
            except Exception as e2:
                logger.error(f"Error in last resort cleanup: {e2}") 