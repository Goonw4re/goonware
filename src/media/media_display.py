import os
import logging
import threading
import random
import tkinter as tk
import traceback
from typing import List, Tuple, Dict, Any, Optional
import time
import cv2
import screeninfo
from PIL import Image

from .media_loader import ImageLoader, GifLoader, VideoLoader
from .window_manager import WindowManager
from .animation import AnimationManager
from .path_utils import MediaPathManager

# Configure logging
logger = logging.getLogger(__name__)

# Try to import screeninfo, but don't fail if it's not available
try:
    from screeninfo import get_monitors
    HAVE_SCREENINFO = True
except ImportError:
    HAVE_SCREENINFO = False
    logger.warning("screeninfo module not available, falling back to tkinter for screen information")

class MediaDisplay:
    """
    Main class for managing media display in popup windows.
    This class coordinates all media display operations, including:
    - Loading and managing media paths
    - Creating and displaying popup windows with media content
    - Handling animation effects like bouncing windows
    - Managing the lifecycle of displayed media
    """
    
    def __init__(self, parent=None, callback_on_error=None):
        """
        Initialize the MediaDisplay component.
        
        Args:
            parent: Optional parent window/widget (for tkinter integration)
            callback_on_error: Optional callback function to handle errors
        """
        logger.info("Initializing MediaDisplay")
        self.parent = parent
        self.callback_on_error = callback_on_error
        
        # Initialize state variables
        self.running = False
        self.prevent_new_popups = False  # Flag to prevent new popups from being created
        self.display_thread = None
        self.display_event = threading.Event()
        self.display_interval = 2  # seconds between displays
        self.max_windows = 5
        self.currently_displayed = 0
        self.popup_duration = 15  # seconds before auto-close
        self.max_image_size = (800, 600)  # Default max dimensions
        self.scale_factor = 1.0  # Default scale factor
        
        # Initialize bounce settings
        self.bounce_enabled = False
        self.bounce_chance = 0.0
        
        # Performance optimizations
        self.last_display_time = 0
        self.display_throttle = 0.05  # Minimum time between displays (50ms)
        self.media_cache = {}  # Cache for frequently used media
        self.cache_size_limit = 30  # Maximum number of items to cache
        
        # Initialize managers
        self.path_manager = MediaPathManager()
        self.window_manager = WindowManager(self)
        self.animation_manager = AnimationManager(self)
        
        # Initialize media loaders
        self.image_loader = ImageLoader(self)
        self.gif_loader = GifLoader(self)
        self.video_loader = VideoLoader(self)
        
        # Media paths
        self.image_paths = []
        self.gif_paths = []
        self.video_paths = []
        
        # Media chance weights (percentage)
        self.image_chance = 60
        self.gif_chance = 20
        self.video_chance = 20
        
        # Selected zip files
        self.selected_zip_files = set()
        
        # List of active monitors
        self.monitors = self._get_monitors()
        if not self.monitors:
            logger.warning("No monitors detected! Using fallback dimensions.")
            self.monitors = [screeninfo.Monitor(x=0, y=0, width=1920, height=1080, name="Primary")]
            
        # Initialize active_monitors - default to primary monitor (index 0)
        self.active_monitors = [0]
        logger.info(f"Initialized active_monitors to: {self.active_monitors}")
            
        logger.info(f"Detected {len(self.monitors)} monitors")
        for i, monitor in enumerate(self.monitors):
            logger.info(f"Monitor {i}: {monitor.width}x{monitor.height} at ({monitor.x}, {monitor.y})")
        
        # Load bounce settings from config if available
        if hasattr(parent, 'media_manager'):
            try:
                settings = parent.media_manager.get_display_settings()
                # CRITICAL FIX: Properly load bounce_enabled from settings
                self.bounce_enabled = bool(int(settings.get('bounce_enabled', 0)))
                # Load bounce chance from settings as a decimal value (convert from percentage)
                bounce_chance_pct = float(settings.get('bounce_chance', 15.0))
                self.bounce_chance = bounce_chance_pct / 100.0 if self.bounce_enabled else 0.0
                logger.info(f"Loaded bounce settings from config: enabled={self.bounce_enabled}, chance={self.bounce_chance*100}%")
                print(f"DEBUG BOUNCE_INIT: Loaded bounce settings: enabled={self.bounce_enabled}, chance={self.bounce_chance*100}%")
            except Exception as e:
                logger.error(f"Error loading bounce settings: {e}")
                print(f"DEBUG BOUNCE_INIT: Error loading bounce settings: {e}")

    def _get_monitors(self) -> List[screeninfo.Monitor]:
        """Get list of monitors with correct positions"""
        try:
            # Get raw monitor information
            raw_monitors = screeninfo.get_monitors()
            if not raw_monitors:
                print("DEBUG MONITOR: No monitors detected, using fallback")
                return [screeninfo.Monitor(x=0, y=0, width=1920, height=1080, name="Fallback")]
                
            # Create new monitor objects with fixed positions
            monitors = []
            
            # Log raw monitor information
            print(f"DEBUG MONITOR: Raw detection found {len(raw_monitors)} monitors")
            for i, m in enumerate(raw_monitors):
                print(f"DEBUG MONITOR: Raw Monitor {i}: {m.width}x{m.height} at ({m.x}, {m.y})")
            
            # CRITICAL FIX: On Windows, screeninfo often returns monitors in wrong order
            # Sort monitors by x-coordinate to ensure consistent ordering
            # Primary monitor should be at index 0
            sorted_monitors = sorted(raw_monitors, key=lambda m: m.x)
            
            # Create monitors with original positions
            for i, m in enumerate(sorted_monitors):
                # Create a new monitor with original position
                monitor = screeninfo.Monitor(
                    x=m.x,
                    y=m.y,
                    width=m.width,
                    height=m.height,
                    name=f"Monitor {i}"
                )
                monitors.append(monitor)
                print(f"DEBUG MONITOR: Fixed Monitor {i}: {monitor.width}x{monitor.height} at ({monitor.x}, {monitor.y})")
            
            # CRITICAL FIX: Verify monitor count
            print(f"DEBUG MONITOR: Final monitor count: {len(monitors)}")
            
            return monitors
            
        except Exception as e:
            print(f"DEBUG MONITOR: Error detecting monitors: {e}")
            return [screeninfo.Monitor(x=0, y=0, width=1920, height=1080, name="Fallback")]

    def start(self):
        """Start the media display thread"""
        if self.running:
            logger.warning("MediaDisplay already running")
            return
            
        logger.info("Starting MediaDisplay")
        self.running = True
        self.prevent_new_popups = False  # Reset the flag to allow popups
        self.display_event.clear()
        
        # Force refresh monitor detection before starting
        self.monitors = self._get_monitors()
        logger.info(f"Refreshed monitor detection, found {len(self.monitors)} monitors")
        for i, monitor in enumerate(self.monitors):
            logger.info(f"Monitor {i}: {monitor.width}x{monitor.height} at ({monitor.x}, {monitor.y})")
            print(f"DEBUG START: Monitor {i}: {monitor.width}x{monitor.height} at ({monitor.x}, {monitor.y})")
        
        # Log active monitors
        logger.info(f"Active monitors: {self.active_monitors}")
        print(f"DEBUG START: Active monitors: {self.active_monitors}")
        
        # CRITICAL FIX: Reload bounce settings from config to ensure they're properly initialized
        if hasattr(self.parent, 'media_manager'):
            try:
                settings = self.parent.media_manager.get_display_settings()
                bounce_setting = settings.get('bounce_enabled', 0)
                self.bounce_enabled = bool(int(bounce_setting))
                # Get bounce chance percentage and convert to decimal
                bounce_chance_pct = float(settings.get('bounce_chance', 15.0))
                self.bounce_chance = bounce_chance_pct / 100.0 if self.bounce_enabled else 0.0
                print(f"DEBUG START: Reloaded bounce_enabled={self.bounce_enabled}, chance={self.bounce_chance*100}%")
            except Exception as e:
                print(f"DEBUG START: Error reloading bounce settings: {e}")
        
        # Load media paths before starting
        self.refresh_media_paths()
        
        # Start display thread
        self.display_thread = threading.Thread(target=self._display_loop, daemon=True)
        self.display_thread.start()
        
        # Make sure bounce_enabled is properly initialized from settings
        print(f"DEBUG START: Bounce is {'enabled' if self.bounce_enabled else 'disabled'}, chance: {self.bounce_chance*100}%")
            
        # Start bounce animation thread regardless - it will check bounce_enabled internally
        self.animation_manager.start_bounce_thread()
        
        logger.info("MediaDisplay started successfully")
        
    def stop(self):
        """Stop the display"""
        try:
            # If already stopped, log warning but still clean up
            if not self.running:
                logger.warning("Media display already stopped, cleaning up anyway")
            
            # CRITICAL FIX: Set running flag to false first to prevent new windows
            self.running = False
            
            # CRITICAL FIX: Set a flag to prevent any new popups from being created
            self.prevent_new_popups = True
            
            # Signal the display thread to exit
            if hasattr(self, 'display_event'):
                self.display_event.set()
                logger.info("Set display_event to signal thread exit")
            
            # Cancel any scheduled tasks in the parent window
            if hasattr(self, 'parent') and self.parent:
                try:
                    # Get all after callbacks and cancel them
                    for after_id in self.parent.tk.call('after', 'info'):
                        try:
                            self.parent.after_cancel(after_id)
                            logger.debug(f"Canceled scheduled task: {after_id}")
                        except Exception as e:
                            logger.error(f"Error canceling after task {after_id}: {e}")
                    logger.info("Canceled all scheduled tasks in parent window")
                except Exception as e:
                    logger.error(f"Error canceling scheduled tasks: {e}")
            
            # Stop animation thread first
            try:
                if hasattr(self, 'animation_manager'):
                    self.animation_manager.stop_bounce_thread()
            except Exception as e:
                logger.error(f"Error stopping animation thread: {e}")
            
            # Force close all windows
            try:
                self.force_close_all()
            except Exception as e:
                logger.error(f"Error closing windows: {e}")
            
            # Stop display thread if it exists
            try:
                if hasattr(self, 'display_thread') and self.display_thread and self.display_thread.is_alive():
                    # Set event to signal thread to exit
                    self.display_event.set()
                    # Join with timeout
                    self.display_thread.join(timeout=0.5)
                    if self.display_thread.is_alive():
                        logger.warning("Display thread did not terminate properly")
            except Exception as e:
                logger.error(f"Error stopping display thread: {e}")
            
            # Clear any remaining resources
            try:
                if hasattr(self, 'window_manager'):
                    # Use clear_windows instead of clear
                    self.window_manager.clear_windows()
            except Exception as e:
                logger.error(f"Error clearing window manager: {e}")
            
            # Reset counter to ensure no windows are tracked
            self.currently_displayed = 0
            
            # CRITICAL FIX: Reset all media paths to prevent any new popups
            self.image_paths = []
            self.gif_paths = []
            self.video_paths = []
            
            logger.info("Media display stopped")
        except Exception as e:
            logger.error(f"Error stopping media display: {e}")
    
    def refresh_media_paths(self) -> bool:
        """Refresh the media paths from zip files"""
        try:
            logger.info("Refreshing media paths")
            media_paths = self.path_manager.get_media_paths(self.selected_zip_files)
            
            # Store the paths properly
            self.image_paths = media_paths.get('images', [])
            self.gif_paths = media_paths.get('gifs', [])
            self.video_paths = media_paths.get('videos', [])
            
            image_count = len(self.image_paths)
            gif_count = len(self.gif_paths)
            video_count = len(self.video_paths)
            total_count = image_count + gif_count + video_count
            
            logger.info(f"Found {total_count} media files: {image_count} images, {gif_count} GIFs, {video_count} videos")
            
            return total_count > 0
        except Exception as e:
            logger.error(f"Error refreshing media paths: {e}\n{traceback.format_exc()}")
            return False
    
    def clear(self):
        """Clear all display windows"""
        try:
            logger.info("Clearing all windows")
            self.window_manager.clear_windows()
            self.currently_displayed = 0
        except Exception as e:
            logger.error(f"Error clearing windows: {e}\n{traceback.format_exc()}")
    
    def force_close_all(self):
        """Force close all display windows (emergency measure)"""
        try:
            logger.info("Force closing all windows from media_display")
            
            # CRITICAL FIX: First stop all update logic by setting running flag
            self.running = False
            
            # CRITICAL FIX: Set a flag to prevent any new popups from being created
            self.prevent_new_popups = True
            
            # CRITICAL FIX: Reset all media paths to prevent any new popups
            self.image_paths = []
            self.gif_paths = []
            self.video_paths = []
            
            # CRITICAL FIX: Signal the display thread to exit
            if hasattr(self, 'display_event'):
                self.display_event.set()
                logger.info("Set display_event to signal thread exit")
            
            # CRITICAL FIX: Cancel any scheduled tasks in the parent window
            if hasattr(self, 'parent') and self.parent:
                try:
                    # Get all after callbacks and cancel them
                    for after_id in self.parent.tk.call('after', 'info'):
                        try:
                            self.parent.after_cancel(after_id)
                            logger.debug(f"Canceled scheduled task: {after_id}")
                        except Exception as e:
                            logger.error(f"Error canceling after task {after_id}: {e}")
                    logger.info("Canceled all scheduled tasks in parent window")
                except Exception as e:
                    logger.error(f"Error canceling scheduled tasks: {e}")
            
            # CRITICAL FIX: First stop animation thread to prevent new window updates
            if hasattr(self, 'animation_manager'):
                try:
                    logger.info("Stopping animation thread before closing windows")
                    self.animation_manager.stop_bounce_thread()
                except Exception as e:
                    logger.error(f"Error stopping animation thread: {e}")
            
            # CRITICAL FIX: Force update to process any pending events
            try:
                if hasattr(self, 'parent') and self.parent:
                    self.parent.update_idletasks()
            except Exception as e:
                logger.error(f"Error updating parent: {e}")
            
            # CRITICAL FIX: Directly access window_manager and call force_close_all
            if hasattr(self, 'window_manager'):
                try:
                    logger.info("Calling force_close_all on window_manager")
                    self.window_manager.force_close_all()
                except Exception as e:
                    logger.error(f"Error in window_manager.force_close_all: {e}")
                    
                    # Fallback: try to close windows directly
                    try:
                        logger.info("Fallback: trying to close windows directly")
                        # Try to close all types of windows
                        for collection_name in ['current_windows', 'gif_windows', 'video_windows']:
                            if hasattr(self.window_manager, collection_name):
                                collection = getattr(self.window_manager, collection_name)
                                # Handle different collection types
                                if isinstance(collection, dict):
                                    windows = list(collection.keys())
                                else:
                                    windows = list(collection)
                                
                                for window in windows:
                                    try:
                                        if hasattr(window, 'winfo_exists') and window.winfo_exists():
                                            window.destroy()
                                    except:
                                        pass
                    except Exception as e2:
                        logger.error(f"Error in fallback window closing: {e2}")
            
            # CRITICAL FIX: Force another update to ensure windows are closed
            try:
                if hasattr(self, 'parent') and self.parent:
                    self.parent.update_idletasks()
            except Exception as e:
                logger.error(f"Error updating parent: {e}")
            
            # Reset counter
            self.currently_displayed = 0
            
            # CRITICAL FIX: Verify all windows are closed
            window_count = 0
            if hasattr(self, 'window_manager'):
                if hasattr(self.window_manager, 'current_windows'):
                    window_count += len(self.window_manager.current_windows)
                if hasattr(self.window_manager, 'gif_windows'):
                    window_count += len(self.window_manager.gif_windows)
                if hasattr(self.window_manager, 'video_windows'):
                    window_count += len(self.window_manager.video_windows)
            
            if window_count > 0:
                logger.warning(f"Still have {window_count} windows after cleanup, resetting collections")
                # Reset all collections as a last resort
                if hasattr(self, 'window_manager'):
                    if hasattr(self.window_manager, 'current_windows'):
                        self.window_manager.current_windows = []
                    if hasattr(self.window_manager, 'gif_windows'):
                        self.window_manager.gif_windows = {}
                    if hasattr(self.window_manager, 'video_windows'):
                        self.window_manager.video_windows = {}
                    if hasattr(self.window_manager, 'window_velocities'):
                        self.window_manager.window_velocities = {}
                    if hasattr(self.window_manager, 'window_creation_times'):
                        self.window_manager.window_creation_times = {}
                    if hasattr(self.window_manager, 'window_monitors'):
                        self.window_manager.window_monitors = {}
            
            logger.info("Force close completed from media_display")
        except Exception as e:
            logger.error(f"Unexpected error in force_close_all: {e}")
            # Last resort cleanup
            try:
                if hasattr(self, 'window_manager'):
                    if hasattr(self.window_manager, 'current_windows'):
                        self.window_manager.current_windows = []
                    if hasattr(self.window_manager, 'gif_windows'):
                        self.window_manager.gif_windows = {}
                    if hasattr(self.window_manager, 'video_windows'):
                        self.window_manager.video_windows = {}
                    if hasattr(self.window_manager, 'window_velocities'):
                        self.window_manager.window_velocities = {}
                    if hasattr(self.window_manager, 'window_creation_times'):
                        self.window_manager.window_creation_times = {}
                    if hasattr(self.window_manager, 'window_monitors'):
                        self.window_manager.window_monitors = {}
                self.currently_displayed = 0
            except Exception as e2:
                logger.error(f"Error in last resort cleanup: {e2}")
    
    def set_display_interval(self, seconds: float):
        """Set the interval between media displays in seconds"""
        if seconds < 0.1:
            seconds = 0.1  # Minimum delay
        logger.info(f"Setting display interval to {seconds} seconds")
        self.display_interval = seconds
        
    def set_max_windows(self, count: int):
        """Set the maximum number of windows to display at once"""
        if count < 1:
            count = 1  # At least one window
        logger.info(f"Setting max windows to {count}")
        self.max_windows = count
        
    def set_popup_duration(self, seconds: float):
        """Set the duration before auto-closing popups"""
        if seconds < 1:
            seconds = 1  # Minimum duration
        logger.info(f"Setting popup duration to {seconds} seconds")
        self.popup_duration = seconds
        
    def set_max_image_size(self, width: int, height: int):
        """Set the maximum image dimensions"""
        logger.info(f"Setting max image size to {width}x{height}")
        self.max_image_size = (max(50, width), max(50, height))
        
    def set_scale_factor(self, factor: float):
        """Set the scale factor for media"""
        if factor < 0.1:
            factor = 0.1  # Minimum scale
        elif factor > 5.0:
            factor = 5.0  # Maximum scale
        logger.info(f"Setting scale factor to {factor}")
        self.scale_factor = factor
    
    def set_bounce_enabled(self, enabled: bool):
        """Set whether window bouncing is enabled"""
        enabled = bool(enabled)  # Force to boolean
        
        # Log the change
        logger.info(f"Setting bounce enabled to {enabled}")
        print(f"DEBUG BOUNCE_SET: Setting bounce enabled from {self.bounce_enabled} to {enabled}")
        
        # Update the settings
        self.bounce_enabled = enabled
        
        # If bounce is disabled, ensure bounce_chance is 0
        if not enabled:
            self.bounce_chance = 0.0
        
        print(f"DEBUG BOUNCE_SET: Bounce enabled set to {self.bounce_enabled}, chance: {self.bounce_chance*100}%")
        logger.info(f"Bounce chance set to {self.bounce_chance*100}%")
        
        # Ensure animation thread is running if bounce is enabled
        if enabled:
            print(f"DEBUG BOUNCE_SET: Starting animation thread because bounce was enabled")
            self.animation_manager.start_bounce_thread()
        elif not enabled:
            # If bounce is disabled, remove all velocities
            if hasattr(self.window_manager, 'window_velocities'):
                self.window_manager.window_velocities.clear()
                print(f"DEBUG BOUNCE_SET: Cleared all window velocities because bounce was disabled")
        
    def set_active_monitors(self, monitor_indices):
        """Set which monitors should display popups"""
        try:
            # Force refresh monitors
            self.monitors = self._get_monitors()
            
            # CRITICAL FIX: Print the raw input for debugging
            print(f"DEBUG MONITOR_SET: Raw input monitor_indices: {monitor_indices} (type: {type(monitor_indices)})")
            
            # Ensure monitor_indices is a list of integers
            if not isinstance(monitor_indices, list):
                monitor_indices = [int(monitor_indices)]
            else:
                # Convert each element to int
                monitor_indices = [int(idx) for idx in monitor_indices]
            
            print(f"DEBUG MONITOR_SET: Setting active monitors to {monitor_indices}")
            
            # Validate indices
            valid_indices = []
            for idx in monitor_indices:
                if idx < len(self.monitors):
                    valid_indices.append(idx)
                    print(f"DEBUG MONITOR_SET: Added valid monitor {idx}: {self.monitors[idx].width}x{self.monitors[idx].height} at ({self.monitors[idx].x}, {self.monitors[idx].y})")
                else:
                    print(f"DEBUG MONITOR_SET: Invalid monitor index {idx}, ignoring")
            
            # Default to primary if no valid indices
            if not valid_indices:
                valid_indices = [0]
                print("DEBUG MONITOR_SET: No valid monitors, defaulting to primary")
            
            # CRITICAL FIX: Ensure we're setting a new list, not a reference
            self.active_monitors = list(valid_indices)
            
            # Log final active monitors
            print(f"DEBUG MONITOR_SET: FINAL Active monitors set to {self.active_monitors}")
            
            # Verify monitor information
            for idx in self.active_monitors:
                if idx < len(self.monitors):
                    m = self.monitors[idx]
                    print(f"DEBUG MONITOR_SET: Active Monitor {idx}: {m.width}x{m.height} at ({m.x}, {m.y})")
                
        except Exception as e:
            print(f"DEBUG MONITOR_SET: Error setting active monitors: {e}")
            self.active_monitors = [0]
        
    def set_media_weights(self, image_weight: int, gif_weight: int, video_weight: int):
        """Set the relative weights for media types"""
        total = image_weight + gif_weight + video_weight
        if total <= 0:
            logger.warning("Invalid media weights, using defaults")
            self.image_chance = 60
            self.gif_chance = 20
            self.video_chance = 20
            return
            
        logger.info(f"Setting media weights: image={image_weight}, gif={gif_weight}, video={video_weight}")
        # Convert to percentages
        self.image_chance = (image_weight / total) * 100
        self.gif_chance = (gif_weight / total) * 100
        self.video_chance = (video_weight / total) * 100
        
    def set_selected_zip_files(self, zip_files: List[str]):
        """Set the list of selected zip files to use for media"""
        self.selected_zip_files = set(zip_files)
        logger.info(f"Selected {len(self.selected_zip_files)} zip files")
        # Refresh media paths with new selection
        self.refresh_media_paths()
    
    def get_random_screen_position(self, width: int, height: int) -> Tuple[int, int, int]:
        """
        Get a random position on one of the active monitors
        
        Returns:
            Tuple containing (x_position, y_position, monitor_index)
        """
        # Force refresh monitors
        self.monitors = self._get_monitors()
        
        # Validate active_monitors
        if not hasattr(self, 'active_monitors') or not self.active_monitors:
            self.active_monitors = [0]
            print("DEBUG POSITION: No active monitors, defaulting to primary")
        
        # CRITICAL FIX: Print active monitors for debugging
        print(f"DEBUG POSITION: Active monitors before validation: {self.active_monitors}")
        
        # Ensure we have valid monitor indices
        valid_monitors = []
        for idx in self.active_monitors:
            if idx < len(self.monitors):
                valid_monitors.append(idx)
                print(f"DEBUG POSITION: Valid monitor: {idx}")
            else:
                print(f"DEBUG POSITION: Invalid monitor index {idx}, ignoring")
        
        if not valid_monitors:
            valid_monitors = [0]
            print("DEBUG POSITION: No valid monitors, defaulting to primary")
        
        # CRITICAL FIX: Force true randomness by using system time as additional seed
        random.seed(time.time())
        
        # Choose a random monitor from valid monitors
        monitor_idx = valid_monitors[random.randint(0, len(valid_monitors)-1)]
        print(f"DEBUG POSITION: RANDOMLY Selected monitor {monitor_idx} from {valid_monitors}")
        
        # Get the selected monitor
        monitor = self.monitors[monitor_idx]
        print(f"DEBUG POSITION: Using monitor {monitor_idx}: {monitor.width}x{monitor.height} at ({monitor.x}, {monitor.y})")
        
        # Calculate position within monitor bounds
        margin = 20  # pixels from edge
        
        # Calculate valid position ranges
        min_x = monitor.x + margin
        max_x = monitor.x + monitor.width - width - margin
        min_y = monitor.y + margin
        max_y = monitor.y + monitor.height - height - margin
        
        # Handle case where window is larger than monitor
        if max_x <= min_x or max_y <= min_y:
            print(f"DEBUG POSITION: Window too large for monitor, using origin")
            return monitor.x + margin, monitor.y + margin, monitor_idx
        
        # Generate random position
        x_pos = random.randint(min_x, max_x)
        y_pos = random.randint(min_y, max_y)
        
        print(f"DEBUG POSITION: Final position: ({x_pos}, {y_pos}) on monitor {monitor_idx}")
        return x_pos, y_pos, monitor_idx
    
    def _display_loop(self):
        """Main loop for displaying media at intervals"""
        logger.info("Display loop started")
        
        while self.running:
            try:
                # CRITICAL FIX: Check if new popups are prevented
                if hasattr(self, 'prevent_new_popups') and self.prevent_new_popups:
                    logger.info("New popups are prevented, exiting display loop")
                    break
                
                # Throttle display creation to prevent overwhelming the system
                current_time = time.time()
                elapsed = current_time - self.last_display_time
                
                if elapsed < self.display_throttle:
                    # Sleep for a very short time to prevent CPU hogging
                    time.sleep(0.01)
                    continue
                
                # CRITICAL FIX: Always create a new window regardless of current window count
                # The window manager will enforce the max_windows limit by removing the oldest window
                
                # CRITICAL FIX: Double-check running flag and prevent_new_popups flag
                if not self.running or (hasattr(self, 'prevent_new_popups') and self.prevent_new_popups):
                    logger.info("Display stopped or new popups prevented, skipping window creation")
                    break
                
                # Choose media type based on weights
                media_type = self._choose_media_type()
                
                # Display chosen media type
                if media_type == "image" and self.image_paths:
                    self.image_loader.display_image()
                    self.currently_displayed += 1
                    self.last_display_time = time.time()
                    
                elif media_type == "gif" and self.gif_paths:
                    self.gif_loader.display_gif()
                    self.currently_displayed += 1
                    self.last_display_time = time.time()
                    
                elif media_type == "video" and self.video_paths:
                    self.video_loader.display_video()
                    self.currently_displayed += 1
                    self.last_display_time = time.time()
                
                # Wait for next display interval or until stopped
                self.display_event.wait(self.display_interval)
                
                # Check if we should exit loop
                if self.display_event.is_set():
                    break
                
            except Exception as e:
                logger.error(f"Error in display loop: {e}\n{traceback.format_exc()}")
                if self.callback_on_error:
                    try:
                        self.callback_on_error(str(e))
                    except:
                        pass
                time.sleep(1)  # Prevent rapid error loops
                
        logger.info("Display loop ended")
    
    def _choose_media_type(self) -> str:
        """Choose a media type based on configured weights"""
        # Check what types are available
        has_images = bool(self.image_paths)
        has_gifs = bool(self.gif_paths)
        has_videos = bool(self.video_paths)
        
        available_types = []
        if has_images:
            available_types.append(("image", self.image_chance))
        if has_gifs:
            available_types.append(("gif", self.gif_chance))
        if has_videos:
            available_types.append(("video", self.video_chance))
        
        if not available_types:
            logger.warning("No media available to display")
            return "none"
            
        # Normalize weights of available types
        total_weight = sum(weight for _, weight in available_types)
        if total_weight <= 0:
            # If all weights are zero, choose randomly
            return random.choice([media_type for media_type, _ in available_types])
            
        # Make weighted choice
        r = random.uniform(0, total_weight)
        cumulative_weight = 0
        
        for media_type, weight in available_types:
            cumulative_weight += weight
            if r <= cumulative_weight:
                return media_type
                
        # Fallback
        return available_types[0][0]

    def get_monitor_info(self):
        """Get information about available monitors"""
        result = []
        try:
            for i, monitor in enumerate(self.monitors):
                # Use the index as the monitor ID
                result.append((i, f"Monitor {i+1} ({monitor.width}x{monitor.height})"))
            logger.info(f"Returning monitor info: {result}")
            return result
        except Exception as e:
            logger.error(f"Error getting monitor info: {e}")
            return [(0, "Primary Monitor")]

    def scale_image(self, img):
        """Scale image to appropriate size with optimized performance"""
        width, height = img.size
        
        # First ensure neither dimension exceeds max size
        if width > self.max_image_size[0] or height > self.max_image_size[1]:
            # Calculate scale factor to fit within max size
            width_ratio = self.max_image_size[0] / width
            height_ratio = self.max_image_size[1] / height
            scale = min(width_ratio, height_ratio)
            
            width = int(width * scale)
            height = int(height * scale)
            
            # Use LANCZOS for better quality, but fall back to BILINEAR for large images
            resample_method = Image.Resampling.LANCZOS
            if width * height > 1000000:  # For very large images (>1MP)
                resample_method = Image.Resampling.BILINEAR
                
            img = img.resize((width, height), resample_method)
        
        # Then apply user's scale factor
        if self.scale_factor != 1.0:
            width = int(width * self.scale_factor)
            height = int(height * self.scale_factor)
            
            # Use BILINEAR for scaling factor changes (faster)
            img = img.resize((width, height), Image.Resampling.BILINEAR)
        
        # Ensure minimum size of 200x150
        width, height = img.size
        if width < 200 or height < 150:
            # Calculate scale to reach minimum size while maintaining aspect ratio
            width_scale = 200 / width if width < 200 else 1
            height_scale = 150 / height if height < 150 else 1
            scale = max(width_scale, height_scale)
            
            # Apply minimum size scaling
            new_width = max(200, int(width * scale))
            new_height = max(150, int(height * scale))
            img = img.resize((new_width, new_height), Image.Resampling.BILINEAR)
            logger.info(f"Applied minimum size constraint: {width}x{height} -> {new_width}x{new_height}")
            
        return img
    
    def get_media_paths(self, selected_zips=None):
        """Get all media paths from the models directory"""
        return self.path_manager.get_media_paths(selected_zips) 