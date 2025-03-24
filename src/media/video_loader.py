import os
import logging
import traceback
import zipfile
import random
import tempfile
import time
import tkinter as tk
import cv2
from PIL import Image, ImageTk
import threading
import numpy as np
import shutil  # For better file operations

from .base_loader import MediaLoaderBase

logger = logging.getLogger(__name__)

class VideoLoader(MediaLoaderBase):
    def __init__(self, display):
        super().__init__(display)
        self.videos = {}  # Track video players
        
        # IMPROVEMENT: Preload frames in a separate thread for smoother playback
        self.preload_threads = {}
        self.preload_amount = 10  # Number of frames to preload
        
        # IMPROVEMENT: Frame cache for faster display
        self.frame_cache_size = 30  # Maximum frames to keep in cache per video
        
        # IMPROVEMENT: Adjust video quality based on system performance
        self.quality_mode = 'auto'  # 'auto', 'high', 'medium', 'low'
        
        # CRITICAL FIX: Add a lock for thread-safe VideoCapture access
        self.video_capture_lock = threading.Lock()
        
        # CRITICAL FIX: Set OpenCV parameters to avoid thread assertion errors
        # Use safer threading mode to prevent FFmpeg pthread_frame.c assertion errors
        cv2.setNumThreads(1)  # Limit OpenCV internal threads
        
        # CRITICAL FIX: Better FFmpeg parameters for improved compatibility
        os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'enable_drm=0:rtsp_transport=tcp:timeout=10000000:allowed_media_types=video'
        
        # List of supported video formats for better compatibility checks
        self.supported_formats = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']
        
        # Temp directory for extracted videos
        self.temp_dir = os.path.join(tempfile.gettempdir(), 'goonware_videos')
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Try to clear existing temp files
        try:
            for file in os.listdir(self.temp_dir):
                file_path = os.path.join(self.temp_dir, file)
                if os.path.isfile(file_path):
                    try:
                        os.remove(file_path)
                    except:
                        pass
        except:
            pass
        
    def display_video(self):
        """Display a random video from the available paths"""
        try:
            # Log entry into display_video function
            logger.info("Starting display_video function")
            
            # CRITICAL FIX: Check if new popups are prevented
            if hasattr(self.display, 'prevent_new_popups') and self.display.prevent_new_popups:
                logger.info("New popups are prevented, skipping video display")
                return None
                
            # Check if display is still running
            if not self.display.running:
                logger.info("Display is not running, skipping video display")
                return None
                
            # Check if we have any video paths
            if not self.display.video_paths:
                logger.warning("No video paths available")
                return None
            
            # Get a list of video paths to try
            paths_to_try = self.display.video_paths.copy()
            random.shuffle(paths_to_try)  # Randomize the order
            
            # Try to display videos until one works
            for i in range(min(5, len(paths_to_try))):  # Try up to 5 videos
                video_path = paths_to_try[i]
                logger.info(f"Attempting to display video {i+1}/{min(5, len(paths_to_try))}: {video_path}")
                
                # Create window
                window = self._get_window_from_pool()
                
                # Process video path based on type
                if isinstance(video_path, tuple) and len(video_path) == 2:
                    # Zip file format
                    zip_path, video_name = video_path
                    logger.info(f"Selected video from zip: {zip_path}/{video_name}")
                    result = self._handle_zip_video(window, zip_path, video_name)
                    if result:
                        return result
                    # Continue to next video on failure
                    
                elif isinstance(video_path, str):
                    # String path format
                    logger.info(f"Selected video: {video_path}")
                    
                    # Handle zip:// format
                    if video_path.startswith("zip://"):
                        # Parse archive path format: zip://archive-file.zip/path/to/video.mp4
                        parts = video_path[6:].split('/', 1)
                        if len(parts) == 2:
                            zip_file, internal_path = parts
                            result = self._handle_zip_video(window, zip_file, internal_path)
                            if result:
                                return result
                    else:
                        # Regular file
                        result = self._handle_file_video(window, video_path)
                        if result:
                            return result
                else:
                    logger.error(f"Unsupported video path format: {video_path}")
                    window.destroy()
                
                # If we got here, the video failed to display, continue to next
                logger.warning(f"Failed to display video, trying next one")
                try:
                    window.destroy()
                except:
                    pass
            
            # If all videos failed, log error
            logger.error("All video display attempts failed")
            return None
                
        except Exception as e:
            logger.error(f"Error in display_video: {e}\n{traceback.format_exc()}")
            return None
            
    def _handle_zip_video(self, window, zip_path, video_name):
        """Handle video from a zip file"""
        # Verify the zip file exists
        if not os.path.exists(zip_path):
            logger.error(f"Zip file does not exist: {zip_path}")
            window.destroy()
            return None
            
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # Verify the video exists in the zip
                if video_name not in zf.namelist():
                    logger.error(f"Video {video_name} not found in zip {zip_path}")
                    window.destroy()
                    return None
                
                # Get file extension and check if it's supported
                _, file_ext = os.path.splitext(video_name.lower())
                if file_ext not in self.supported_formats:
                    # Try to make an educated guess about the format
                    if '.mp4' in video_name.lower():
                        file_ext = '.mp4'
                    else:
                        # Default to mp4 if we can't determine
                        file_ext = '.mp4'
                    logger.warning(f"Unknown video format for {video_name}, assuming {file_ext}")
                
                # CRITICAL FIX: Use a more reliable temp directory
                temp_filename = f"gmodel_vid_{int(time.time())}_{random.randint(1000, 9999)}{file_ext}"
                temp_file = os.path.join(self.temp_dir, temp_filename)
                
                # CRITICAL FIX: More robust extraction
                try:
                    # Extract video to temp file
                    with zf.open(video_name) as f_in, open(temp_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                        
                    # Verify extracted file
                    if not os.path.exists(temp_file) or os.path.getsize(temp_file) == 0:
                        logger.error(f"Failed to extract video or file is empty: {temp_file}")
                        window.destroy()
                        return None
                        
                    logger.info(f"Extracted video to {temp_file} ({os.path.getsize(temp_file)} bytes)")
                except Exception as e:
                    logger.error(f"Error extracting video: {e}\n{traceback.format_exc()}")
                    try:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                    except:
                        pass
                    window.destroy()
                    return None
                
                # Check if we can still display
                if (hasattr(self.display, 'prevent_new_popups') and self.display.prevent_new_popups) or not self.display.running:
                    logger.info("Display stopped or new popups prevented, cleaning up")
                    try:
                        os.remove(temp_file)
                    except:
                        pass
                    return None
                
                # Try to create a video window
                try:
                    window = self._create_video_window(temp_file)
                except Exception as e:
                    logger.error(f"Error creating video window: {e}\n{traceback.format_exc()}")
                    try:
                        os.remove(temp_file)
                    except:
                        pass
                    return None
                    
                if not window:
                    logger.error("Failed to create video window")
                    try:
                        os.remove(temp_file)
                    except:
                        pass
                    return None
                
                # Store temp file path for cleanup
                if window in self.display.window_manager.video_windows:
                    self.display.window_manager.video_windows[window]['temp_file'] = temp_file
                
                # Add window to manager and schedule removal
                self.display.window_manager.add_window(window, enable_bounce=True)
                self.display.window_manager.remove_after_delay(window)
                
                return window
                
        except zipfile.BadZipFile as e:
            logger.error(f"Bad archive file {zip_path}: {e}")
            window.destroy()
            # Remove this archive from the paths to prevent future errors
            self.display.video_paths = [p for p in self.display.video_paths if not (isinstance(p, tuple) and p[0] == zip_path)]
            return None
        except Exception as e:
            logger.error(f"Error loading video from {zip_path}/{video_name}: {e}\n{traceback.format_exc()}")
            try:
                window.destroy()
            except:
                pass
            return None
            
    def _handle_file_video(self, window, video_path):
        """Handle video from a file path"""
        # Handle string format paths (for future compatibility)
        if video_path.startswith("zip://"):
            # Parse archive path format: zip://archive-file.zip/path/to/video.mp4
            # Note: Both .zip and .gmodel files use the same format
            parts = video_path[6:].split('/', 1)
            if len(parts) != 2:
                logger.error(f"Invalid archive path format: {video_path}")
                window.destroy()
                return None
            
            zip_file, internal_path = parts
            return self._handle_zip_video(window, zip_file, internal_path)
        else:
            # Regular file path
            # CRITICAL FIX: Check again if new popups are prevented or display is stopped
            if (hasattr(self.display, 'prevent_new_popups') and self.display.prevent_new_popups) or not self.display.running:
                logger.info("Display stopped or new popups prevented while loading video, skipping window creation")
                return None
                
            # Create video window
            window = self._create_video_window(video_path)
            if not window:
                return None
                
            # Add to window manager
            self.display.window_manager.add_window(window, enable_bounce=True)
            
            # Schedule removal after delay
            self.display.window_manager.remove_after_delay(window)
            
            logger.info(f"Successfully displayed video: {video_path}")
            return window
    
    def _create_video_window(self, video_path):
        """Create a window for video display"""
        try:
            logger.info(f"Opening video file: {video_path}")
            
            # Check if video file exists and has valid size
            if not os.path.exists(video_path):
                logger.error(f"Video file does not exist: {video_path}")
                return None
            
            if os.path.getsize(video_path) == 0:
                logger.error(f"Video file is empty: {video_path}")
                return None
            
            # Get file extension
            _, file_ext = os.path.splitext(video_path.lower())
            if file_ext not in self.supported_formats:
                logger.warning(f"Video file has unsupported extension: {file_ext}")
                # We'll try to play it anyway
            
            # Create the base window first
            window = tk.Toplevel()
            window.withdraw()  # Hide until ready
            window.title("Video")
            window.protocol("WM_DELETE_WINDOW", lambda: None)  # Prevent user from closing
            window.overrideredirect(True)  # No window decorations
            window.attributes('-topmost', True)  # Keep on top
            
            # Prevent window from appearing in Taskbar
            try:
                # Set window to be a tool window (no taskbar icon)
                window.attributes('-toolwindow', True)
                # Set window to be a popup (no taskbar icon)
                window.attributes('-alpha', 1.0)  # Ensure full opacity
                
                # Find existing root or toplevel to be the parent
                parent = None
                try:
                    if hasattr(self.display, 'root'):
                        parent = self.display.root
                    elif hasattr(self.display, 'window_manager') and hasattr(self.display.window_manager, 'root'):
                        parent = self.display.window_manager.root
                except Exception as e:
                    logger.warning(f"Could not find parent window: {e}")
                
                # Set as transient of the parent window if available
                if parent:
                    try:
                        window.transient(parent)  # Attach to parent window
                    except:
                        window.transient()  # Fall back to generic transient
                else:
                    window.transient()  # Generic transient (no parent)
                
                # Windows-specific: Set window style to hide from taskbar
                try:
                    import ctypes
                    GWL_EXSTYLE = -20
                    WS_EX_TOOLWINDOW = 0x00000080
                    WS_EX_NOACTIVATE = 0x08000000
                    WS_EX_APPWINDOW = 0x00040000  # This style makes windows appear in taskbar
                    
                    hwnd = window.winfo_id()
                    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    style = style | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE  # Add tool window style
                    style = style & ~WS_EX_APPWINDOW  # Remove app window style
                    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
                    
                    # Additional Windows API call to hide from taskbar
                    try:
                        user32 = ctypes.windll.user32
                        user32.ShowWindow(hwnd, 0)  # Hide window first
                        # SW_SHOWNOACTIVATE = 4
                        user32.ShowWindow(hwnd, 4)  # Show without activating
                    except Exception as e:
                        logger.warning(f"Could not use ShowWindow API: {e}")
                        
                except Exception as e:
                    logger.warning(f"Could not set Windows-specific window style: {e}")
            except Exception as e:
                logger.warning(f"Could not set window attributes to hide from taskbar: {e}")
            
            # Attempt to open the video
            try:
                # CRITICAL FIX: Use a lock when creating and accessing VideoCapture objects
                with self.video_capture_lock:
                    # Try to open with FFMPEG first
                    cap = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG)
                    
                    # Set buffer size for faster loading
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
                    
                    # Check if opened successfully
                    if not cap.isOpened():
                        logger.error(f"Failed to open video with FFMPEG: {video_path}")
                        # Try again with default backend as fallback
                        cap.release()
                        cap = cv2.VideoCapture(video_path)
                        
                        if not cap.isOpened():
                            logger.error(f"Failed to open video with default backend: {video_path}")
                            window.destroy()
                            return None
                    
                    # Get video properties
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    
                    # Validate video properties
                    if width <= 0 or height <= 0:
                        logger.warning(f"Invalid video dimensions: {width}x{height}, using defaults")
                        width = 320 if width <= 0 else width
                        height = 240 if height <= 0 else height
                    
                    if fps <= 0 or fps > 60:
                        logger.warning(f"Invalid FPS: {fps}, using default")
                        fps = 30.0
                    
                    # Read the first frame
                    ret, first_frame = cap.read()
                    if not ret or first_frame is None:
                        logger.error(f"Failed to read first frame: {video_path}")
                        cap.release()
                        window.destroy()
                        return None
                    
                    # Reset position
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                
                # Process the first frame outside the lock
                try:
                    first_frame = cv2.cvtColor(first_frame, cv2.COLOR_BGR2RGB)
                except Exception as e:
                    logger.error(f"Error converting frame color: {e}")
                    cap.release()
                    window.destroy()
                    return None
            except Exception as e:
                logger.error(f"Error opening video: {e}\n{traceback.format_exc()}")
                try:
                    cap.release()
                except:
                    pass
                window.destroy()
                return None
            
            # Calculate display size based on video properties
            display_width = min(width, 640)  # Limit max width
            display_height = min(height, 480)  # Limit max height
            
            # Maintain aspect ratio
            aspect_ratio = width / height
            if display_width / display_height > aspect_ratio:
                # Width constrained by height
                display_width = int(display_height * aspect_ratio)
            else:
                # Height constrained by width
                display_height = int(display_width / aspect_ratio)
            
            # Apply scale factor from display settings
            if hasattr(self.display, 'scale_factor'):
                scale_factor = self.display.scale_factor
                display_width = max(100, int(display_width * scale_factor))
                display_height = max(100, int(display_height * scale_factor))
            
            # Set window size
            window.geometry(f"{display_width}x{display_height}")
            
            # Create canvas for the video
            canvas = tk.Canvas(window, width=display_width, height=display_height,
                              bg='black', highlightthickness=0)
            canvas.pack(fill=tk.BOTH, expand=True)
            
            # Process first frame for display
            first_frame_resized = cv2.resize(first_frame, (display_width, display_height))
            photo = ImageTk.PhotoImage(image=Image.fromarray(first_frame_resized))
            
            # Create image on canvas
            image_id = canvas.create_image(0, 0, image=photo, anchor=tk.NW)
            
            # Store reference to prevent garbage collection
            canvas.image = photo
            
            # Position window on screen
            screen_x, screen_y, monitor_idx = self.display.get_random_screen_position(display_width, display_height)
            window.geometry(f"{display_width}x{display_height}+{screen_x}+{screen_y}")
            
            # Create unique ID for this video
            video_id = id(window)
            
            # Store video info
            self.videos[video_id] = {
                'cap': cap,
                'canvas': canvas,
                'width': display_width,
                'height': display_height,
                'fps': fps,
                'frame_count': frame_count,
                'last_update': time.time(),
                'last_frame_time': time.time(),
                'running': True,
                'image_id': image_id,
                'current_photo': photo
            }
            
            # Store window in window manager
            self.display.window_manager.window_monitors[window] = monitor_idx
            self.display.window_manager.window_creation_times[window] = time.time()
            self.display.window_manager.video_windows[window] = {
                'video_id': video_id,
                'cleanup': lambda: self._close_video(window, video_id),
                'path': video_path,
                'temp_file': None
            }
            
            # Show the window
            window.deiconify()
            window.update_idletasks()
            
            # Start playing the video
            success = self._play_video(window, canvas, cap, display_width, display_height, fps, image_id)
            
            if not success:
                logger.error(f"Failed to start video playback: {video_path}")
                self._close_video(window, video_id)
                return None
                
            return window
            
        except Exception as e:
            logger.error(f"Error creating video window: {e}\n{traceback.format_exc()}")
            return None
            
    def _start_frame_preloading(self, video_id, cap, width, height, frame_count):
        """Start preloading frames in a background thread for smoother playback"""
        if video_id in self.preload_threads:
            return  # Already preloading
            
        # Define preloading thread
        def preload_frames():
            try:
                # Store preloaded frames
                preloaded_frames = []
                
                # CRITICAL FIX: Use lock for thread-safe VideoCapture access
                with self.video_capture_lock:
                    # Get current position to restore later
                    current_pos = cap.get(cv2.CAP_PROP_POS_FRAMES)
                    
                    # Skip to first frame
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    
                    # Preload frames
                    for i in range(min(frame_count, 10)):  # Limit to 10 frames max for safety
                        ret, frame = cap.read()
                        if not ret or frame is None:
                            break
                        
                        # Convert and resize frame
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_LINEAR)
                        
                        # Add to preloaded frames
                        preloaded_frames.append(frame)
                    
                    # Restore position
                    cap.set(cv2.CAP_PROP_POS_FRAMES, current_pos)
                
                # Store preloaded frames
                if video_id in self.videos and preloaded_frames:
                    logger.info(f"Preloaded {len(preloaded_frames)} frames for video {video_id}")
                    self.videos[video_id]['preloaded_frames'] = preloaded_frames
                    self.videos[video_id]['next_preloaded'] = 0
            except Exception as e:
                logger.error(f"Error preloading frames: {e}")
                
            # Clean up thread reference
            if video_id in self.preload_threads:
                del self.preload_threads[video_id]
        
        # Start thread
        preload_thread = threading.Thread(target=preload_frames, daemon=True)
        self.preload_threads[video_id] = preload_thread
        preload_thread.start()

    def _play_video(self, window, canvas, cap, width, height, fps, image_id=None):
        """Play video in the given window"""
        try:
            # Get the unique ID for this video
            video_id = id(window)
            
            # Verify video is properly initialized
            if video_id not in self.videos:
                logger.error(f"Video {video_id} not properly initialized")
                return False
            
            # Calculate frame interval
            frame_interval = 1.0 / fps  # in seconds
            delay = int(frame_interval * 1000)  # Convert to milliseconds
            
            # Define a more robust frame update function
            def update_frame():
                nonlocal image_id
                
                try:
                    # Check if window and canvas still exist
                    if not window.winfo_exists() or not canvas.winfo_exists():
                        logger.debug(f"Window or canvas no longer exists for video {video_id}")
                        if video_id in self.videos:
                            self.videos[video_id]['running'] = False
                        return
                    
                    # Check if we should still be playing
                    if not self.videos.get(video_id, {}).get('running', False):
                        logger.debug(f"Video {video_id} is no longer running")
                        return
                    
                    # Read the next frame
                    with self.video_capture_lock:
                        ret, frame = cap.read()
                        
                        # Handle end of video
                        if not ret or frame is None:
                            logger.debug(f"End of video {video_id}, looping back")
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            ret, frame = cap.read()
                            if not ret or frame is None:
                                logger.error(f"Failed to restart video {video_id}")
                                self.videos[video_id]['running'] = False
                                return
                    
                    # Process the frame
                    try:
                        # Convert from BGR to RGB
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        
                        # Resize to window dimensions
                        frame = cv2.resize(frame, (width, height))
                        
                        # Convert to PIL Image and then Tkinter PhotoImage
                        img = Image.fromarray(frame)
                        photo = ImageTk.PhotoImage(image=img)
                        
                        # Update existing image or create new one
                        if image_id is not None and canvas.winfo_exists():
                            try:
                                canvas.itemconfig(image_id, image=photo)
                            except tk.TclError as e:
                                logger.warning(f"Canvas update failed: {e}")
                                # Try to create new image
                                image_id = canvas.create_image(0, 0, image=photo, anchor=tk.NW)
                                self.videos[video_id]['image_id'] = image_id
                        else:
                            image_id = canvas.create_image(0, 0, image=photo, anchor=tk.NW)
                            self.videos[video_id]['image_id'] = image_id
                        
                        # CRITICAL: Store reference to the photo to prevent garbage collection
                        self.videos[video_id]['current_photo'] = photo
                        
                        # Update metrics
                        self.videos[video_id]['last_update'] = time.time()
                        
                    except Exception as e:
                        logger.error(f"Error processing video frame: {e}\n{traceback.format_exc()}")
                        # Try to continue anyway
                    
                    # Schedule next frame update if still running and window exists
                    if (video_id in self.videos and 
                        self.videos[video_id].get('running', True) and 
                        window.winfo_exists() and 
                        canvas.winfo_exists()):
                        next_update = window.after(delay, update_frame)
                        self.videos[video_id]['next_update_id'] = next_update
                    
                except Exception as e:
                    logger.error(f"Error in update_frame: {e}\n{traceback.format_exc()}")
                    # Try to continue despite errors if window still exists
                    if (video_id in self.videos and 
                        self.videos[video_id].get('running', True) and 
                        window.winfo_exists() and 
                        canvas.winfo_exists()):
                        next_update = window.after(delay, update_frame)
                        self.videos[video_id]['next_update_id'] = next_update
            
            # Create and register window close handler
            def on_window_close():
                try:
                    logger.debug(f"Closing video {video_id}")
                    
                    # Cancel any pending updates
                    if video_id in self.videos and 'next_update_id' in self.videos[video_id]:
                        try:
                            window.after_cancel(self.videos[video_id]['next_update_id'])
                        except:
                            pass
                    
                    # Mark as not running
                    if video_id in self.videos:
                        self.videos[video_id]['running'] = False
                    
                    # Release video capture
                    with self.video_capture_lock:
                        try:
                            cap.release()
                        except:
                            pass
                    
                    # Clean up resources
                    self._close_video(window, video_id)
                    
                except Exception as e:
                    logger.error(f"Error in on_window_close: {e}")
                    # Ensure window is destroyed in any case
                    try:
                        window.destroy()
                    except:
                        pass
            
            # Register the close handler
            window.protocol("WM_DELETE_WINDOW", on_window_close)
            self.videos[video_id]['close_handler'] = on_window_close
            
            # Start the update loop
            first_update = window.after(10, update_frame)
            self.videos[video_id]['next_update_id'] = first_update
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting up video playback: {e}\n{traceback.format_exc()}")
            return False
            
    def _close_video(self, window, video_id):
        """Clean up video resources properly"""
        try:
            logger.info(f"Cleaning up video resources for {video_id}")
            
            # Check if video exists in tracking dict
            if video_id not in self.videos:
                logger.warning(f"Video {video_id} not found in tracking dict")
                try:
                    # Still try to destroy window
                    window.destroy()
                except:
                    pass
                return
            
            # Get video info
            video_info = self.videos[video_id]
            
            # Cancel any scheduled updates
            if 'next_update_id' in video_info:
                try:
                    window.after_cancel(video_info['next_update_id'])
                    logger.debug(f"Canceled scheduled update for video {video_id}")
                except Exception as e:
                    logger.error(f"Error canceling update: {e}")
            
            # Mark as not running
            video_info['running'] = False
            
            # Release video capture if present
            if 'cap' in video_info and video_info['cap'] is not None:
                try:
                    with self.video_capture_lock:
                        video_info['cap'].release()
                    logger.debug(f"Released video capture for {video_id}")
                except Exception as e:
                    logger.error(f"Error releasing capture: {e}")
            
            # Clean up temporary files
            try:
                if window in self.display.window_manager.video_windows:
                    temp_file = self.display.window_manager.video_windows[window].get('temp_file')
                    if temp_file and os.path.exists(temp_file):
                        if os.path.isdir(temp_file):
                            shutil.rmtree(temp_file, ignore_errors=True)
                        else:
                            os.unlink(temp_file)
                        logger.debug(f"Removed temp file: {temp_file}")
            except Exception as e:
                logger.error(f"Error removing temp file: {e}")
            
            # Clear references to prevent memory leaks
            if 'current_photo' in video_info:
                video_info['current_photo'] = None
            
            # Remove from tracking
            del self.videos[video_id]
            
            # Remove from window manager
            try:
                self.display.window_manager.remove_window(window)
            except Exception as e:
                logger.debug(f"Error removing from window manager: {e}")
            
            # Destroy window
            try:
                window.destroy()
                logger.debug(f"Destroyed window for video {video_id}")
            except Exception as e:
                logger.error(f"Error destroying window: {e}")
                
            logger.info(f"Successfully cleaned up video {video_id}")
            
        except Exception as e:
            logger.error(f"Error in _close_video: {e}\n{traceback.format_exc()}")
            try:
                window.destroy()
            except:
                pass

    def _get_window_from_pool(self):
        """Get a window from the pool or create a new one"""
        # Create a new Toplevel window
        window = tk.Toplevel()
        window.withdraw()  # Hide until ready
        window.overrideredirect(True)  # Remove window decorations
        window.attributes('-topmost', True)  # Keep on top
        
        # Prevent window from appearing in Taskbar
        try:
            # Set window to be a tool window (no taskbar icon)
            window.attributes('-toolwindow', True)
            # Set window to be a popup (no taskbar icon)
            window.attributes('-alpha', 1.0)  # Ensure full opacity
            # Set window to be a transient window (no taskbar icon)
            window.transient()
            
            # Windows-specific: Set window style to hide from taskbar
            try:
                import ctypes
                GWL_EXSTYLE = -20
                WS_EX_TOOLWINDOW = 0x00000080
                WS_EX_NOACTIVATE = 0x08000000
                WS_EX_APPWINDOW = 0x00040000  # This style makes windows appear in taskbar
                
                hwnd = window.winfo_id()
                style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                style = style | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE  # Add tool window style
                style = style & ~WS_EX_APPWINDOW  # Remove app window style
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
                
                # Additional Windows API call to hide from taskbar
                try:
                    user32 = ctypes.windll.user32
                    user32.ShowWindow(hwnd, 0)  # Hide window first
                    # SW_SHOWNOACTIVATE = 4
                    user32.ShowWindow(hwnd, 4)  # Show without activating
                except Exception as e:
                    logger.warning(f"Could not use ShowWindow API: {e}")
                    
            except Exception as e:
                logger.warning(f"Could not set Windows-specific window style: {e}")
        except Exception as e:
            logger.warning(f"Could not set window attributes to hide from taskbar: {e}")
        
        # Set the background to black for better looking video
        window.configure(bg='black')
        
        return window

    def _test_video_format(self, video_path):
        """Test if a video file can be opened and read successfully"""
        if not os.path.exists(video_path):
            logger.warning(f"Video file does not exist: {video_path}")
            return False
            
        try:
            # Try to open with OpenCV
            with self.video_capture_lock:
                cap = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG)
                if not cap.isOpened():
                    logger.warning(f"Could not open video with FFMPEG: {video_path}")
                    cap.release()
                    # Try default backend
                    cap = cv2.VideoCapture(video_path)
                    if not cap.isOpened():
                        logger.warning(f"Could not open video with default backend: {video_path}")
                        return False
                
                # Try to read a frame
                ret, frame = cap.read()
                cap.release()
                
                if not ret or frame is None:
                    logger.warning(f"Could not read frame from video: {video_path}")
                    return False
                    
                return True
        except Exception as e:
            logger.warning(f"Error testing video format: {e}")
            return False

    def release_all_resources(self):
        """Release all video resources"""
        logger.info("Releasing all video resources")
        
        # Copy the video IDs to avoid modifying during iteration
        video_ids = list(self.videos.keys())
        
        for video_id in video_ids:
            try:
                if video_id in self.videos:
                    # Stop video playback
                    self.videos[video_id]['running'] = False
                    
                    # Cancel any pending updates
                    if 'next_update_id' in self.videos[video_id]:
                        try:
                            window = next((w for w, data in self.display.window_manager.video_windows.items() 
                                         if data.get('video_id') == video_id), None)
                            if window:
                                window.after_cancel(self.videos[video_id]['next_update_id'])
                        except:
                            pass
                    
                    # Release capture
                    if 'cap' in self.videos[video_id]:
                        # CRITICAL FIX: Use lock for thread-safe VideoCapture access
                        with self.video_capture_lock:
                            self.videos[video_id]['cap'].release()
                            
                    # Clean up any stored frames to free memory
                    if 'preloaded_frames' in self.videos[video_id]:
                        del self.videos[video_id]['preloaded_frames']
                    
                    # Remove from tracking dict
                    del self.videos[video_id]
                    
                    # Clean up temp file if it exists
                    if window in self.display.window_manager.video_windows and 'temp_file' in self.display.window_manager.video_windows[window]:
                        temp_file = self.display.window_manager.video_windows[window]['temp_file']
                        try:
                            if os.path.exists(temp_file):
                                os.unlink(temp_file)
                                logger.info(f"Deleted temp file: {temp_file}")
                        except Exception as e:
                            logger.error(f"Error deleting temp file: {e}")
                    
                    # Remove from window manager
                    try:
                        self.display.window_manager.remove_window(window)
                    except:
                        pass
                    
                    logger.info(f"Closed video player {video_id}")
            except Exception as e:
                logger.error(f"Error releasing video resources: {e}") 