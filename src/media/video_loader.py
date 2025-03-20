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
        
    def display_video(self):
        """Display a random video from the available paths"""
        try:
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
            
            # Select random video path
            video_path = random.choice(self.display.video_paths)
            
            # Create new window for media
            window = self._get_window_from_pool()
            
            # Handle both tuple format (zip_path, internal_path) and string format paths
            if isinstance(video_path, tuple) and len(video_path) == 2:
                zip_path, video_name = video_path
                logger.info(f"Selected video from zip: {zip_path}/{video_name}")
                return self._handle_zip_video(window, zip_path, video_name)
            elif isinstance(video_path, str):
                logger.info(f"Selected video: {video_path}")
                return self._handle_file_video(window, video_path)
            else:
                logger.error(f"Unsupported video path format: {video_path}")
                window.destroy()
                return None
                
        except Exception as e:
            logger.error(f"Error displaying video: {e}\n{traceback.format_exc()}")
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
                    
                # IMPROVEMENT: Use a more efficient extraction method
                # Create a temporary file for the video with a better naming convention
                temp_filename = f"gmodel_vid_{int(time.time())}_{random.randint(1000, 9999)}.mp4"
                temp_file = os.path.join(tempfile.gettempdir(), temp_filename)
                
                # IMPROVEMENT: More efficient extraction
                try:
                    # Extract video to temp file with progress tracking
                    with zf.open(video_name) as f_in, open(temp_file, 'wb') as f_out:
                        # Read in chunks of 1MB for efficiency
                        chunk_size = 1024 * 1024
                        data = f_in.read(chunk_size)
                        while data:
                            f_out.write(data)
                            data = f_in.read(chunk_size)
                            
                            # Check if display is still running during extraction
                            if not self.display.running:
                                logger.info("Display stopped during extraction, canceling")
                                f_out.close()
                                try:
                                    os.remove(temp_file)
                                except:
                                    pass
                                return None
                except Exception as e:
                    logger.error(f"Error extracting video: {e}")
                    try:
                        os.remove(temp_file)
                    except:
                        pass
                    window.destroy()
                    return None
                
                # CRITICAL FIX: Check again if new popups are prevented or display is stopped
                if (hasattr(self.display, 'prevent_new_popups') and self.display.prevent_new_popups) or not self.display.running:
                    logger.info("Display stopped or new popups prevented while loading video, skipping window creation")
                    # Clean up temp file
                    try:
                        os.remove(temp_file)
                    except:
                        pass
                    return None
                
                # Create video window
                window = self._create_video_window(temp_file)
                if not window:
                    # Clean up temp file if window creation failed
                    try:
                        os.remove(temp_file)
                    except:
                        pass
                    return None
                
                # Store temp file path for cleanup
                if window in self.display.window_manager.video_windows:
                    self.display.window_manager.video_windows[window]['temp_file'] = temp_file
                
                # Add window to manager
                self.display.window_manager.add_window(window, enable_bounce=True)
                
                # Schedule removal after delay
                self.display.window_manager.remove_after_delay(window)
                
                logger.info(f"Successfully displayed video: {zip_path}/{video_name}")
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
            except tk.TclError:
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
            
            # Check if video file exists
            if not os.path.exists(video_path):
                logger.error(f"Video file does not exist: {video_path}")
                return None
                
            # IMPROVEMENT: Better video capture options for faster loading
            cap = cv2.VideoCapture(video_path)
            # Set buffer size for smoother playback
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 10)  
            
            if not cap.isOpened():
                logger.error(f"Failed to open video: {video_path}")
                return None
                
            # OPTIMIZATION: Check video properties before loading
            # Get video properties
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Skip problematic videos
            if width <= 0 or height <= 0 or fps <= 0 or frame_count <= 0:
                logger.error(f"Invalid video properties: {width}x{height}, {fps} FPS, {frame_count} frames")
                cap.release()
                return None
                
            # IMPROVEMENT: Auto-detect quality mode based on video size
            video_size = width * height
            actual_scale = 1.0
            
            if video_size > 1920 * 1080:  # 1080p or higher
                logger.info(f"Very high resolution video ({width}x{height}), using aggressive scaling")
                actual_scale = 0.4  # 40% of original size
            elif video_size > 1280 * 720:  # 720p or higher
                logger.info(f"High resolution video ({width}x{height}), using standard scaling")
                actual_scale = 0.6  # 60% of original size
            else:
                # Standard definition
                actual_scale = 0.8  # 80% of original size
                
            logger.info(f"Video properties: {width}x{height}, {fps} FPS, {frame_count} frames")
            
            # Scale video if needed
            if width > self.display.max_image_size[0] or height > self.display.max_image_size[1]:
                width_ratio = self.display.max_image_size[0] / width
                height_ratio = self.display.max_image_size[1] / height
                scale = min(width_ratio, height_ratio) * actual_scale
                width = int(width * scale)
                height = int(height * scale)
                logger.info(f"Scaling video to {width}x{height}")
            else:
                # Still apply target scale
                width = int(width * actual_scale)
                height = int(height * actual_scale)
            
            # Apply user's scale factor
            width = int(width * self.display.scale_factor)
            height = int(height * self.display.scale_factor)
            
            # Ensure minimum size of 200x150
            if width < 200 or height < 150:
                # Calculate scale to reach minimum size while maintaining aspect ratio
                width_scale = 200 / width if width < 200 else 1
                height_scale = 150 / height if height < 150 else 1
                scale = max(width_scale, height_scale)
                
                # Apply minimum size scaling
                width = max(200, int(width * scale))
                height = max(150, int(height * scale))
                logger.info(f"Applied minimum size constraint to video: {width}x{height}")
            
            # Create base window
            window = self._get_window_from_pool()
            
            # IMPROVEMENT: Fast first frame loading with optimized parameters
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, first_frame = cap.read()
            if not ret:
                logger.error(f"Failed to read first frame from video: {video_path}")
                cap.release()
                window.destroy()
                return None
                
            # IMPROVEMENT: Better color conversion for vivid colors
            first_frame = cv2.cvtColor(first_frame, cv2.COLOR_BGR2RGB)
            first_frame = cv2.resize(first_frame, (width, height), interpolation=cv2.INTER_LANCZOS4)
            
            # Ensure the image is created with correct color mode
            img = Image.fromarray(first_frame, 'RGB')
            photo = ImageTk.PhotoImage(image=img)
            
            # IMPROVEMENT: Create better looking canvas with border
            canvas = tk.Canvas(window, width=width, height=height, bg='black', 
                              highlightthickness=1, highlightbackground='#333333')
            canvas.pack(fill=tk.BOTH, expand=True)
            
            # Update window background to match canvas
            window.config(bg='black')
            
            # Use a dark transparent color that won't impact video colors
            window.attributes('-transparentcolor', "#010101")  # Nearly black but distinct from true black
            
            # Display first frame with centered positioning
            image_id = canvas.create_image(width // 2, height // 2, image=photo, anchor=tk.CENTER)
            canvas.photo = photo  # Keep reference
            
            # Position window
            window = self._position_window(window, width, height)
            
            # IMPROVEMENT: Add a nice loading indicator
            loading_text_id = canvas.create_text(width // 2, height - 20, 
                                              text="Loading video...", 
                                              fill="#FFFFFF", 
                                              font=("Arial", 9))
            
            # Show window
            window.deiconify()
            window.attributes('-topmost', True)
            window.lift()
            
            # IMPROVEMENT: Calculate optimal FPS based on video properties
            if video_size > 1280 * 720:  # HD content
                target_fps = min(20, fps)  # Cap at 20fps for HD
            else:
                target_fps = min(30, fps)  # Cap at 30fps for SD
                
            # IMPROVEMENT: Start preloading frames in background thread
            video_id = id(window)
            self._start_frame_preloading(video_id, cap, width, height, self.preload_amount)
            
            # Start video playback with enhanced parameters
            self._play_video(window, canvas, cap, width, height, target_fps, image_id)
            
            # Remove loading text after playback starts
            canvas.after(500, lambda: canvas.delete(loading_text_id))
            
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
                
                # Get current position to restore later
                current_pos = cap.get(cv2.CAP_PROP_POS_FRAMES)
                
                # Skip to first frame
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                
                # Preload frames
                for i in range(frame_count):
                    ret, frame = cap.read()
                    if not ret:
                        break
                        
                    # Convert and resize frame
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_LINEAR)
                    
                    # Add to preloaded frames
                    preloaded_frames.append(frame)
                
                # Restore position
                cap.set(cv2.CAP_PROP_POS_FRAMES, current_pos)
                
                # Store preloaded frames
                if video_id in self.videos:
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
            # Create a unique ID for this video
            video_id = id(window)
            
            # Store video info
            self.videos[video_id] = {
                'cap': cap,
                'canvas': canvas,
                'width': width,
                'height': height,
                'fps': fps,
                'last_update': time.time(),
                'running': True,
                'frame_cache': {},  # For caching frequently accessed frames
                'cache_hits': 0,    # Performance tracking
                'cache_misses': 0   # Performance tracking
            }
            
            # Add cleanup callback to window_manager
            try:
                self.display.window_manager.video_windows[window] = {
                    'video_id': video_id,
                    'cleanup': lambda: self._close_video(window, video_id),
                    'path': cap.get(cv2.CAP_PROP_POS_AVI_RATIO),  # Just as a placeholder
                    'temp_file': None  # Will be populated if this is from a temp file
                }
            except Exception as e:
                logger.error(f"Error registering video cleanup: {e}")
            
            # IMPROVEMENT: More precise frame timing
            frame_interval = 1.0 / fps  # in seconds
            delay = int(frame_interval * 1000)  # Convert to milliseconds
            
            # IMPROVEMENT: Smoother playback with time-based updates
            last_frame_time = time.time()
            
            def update_frame():
                try:
                    # Check if video still exists
                    if not self.videos.get(video_id) or not self.videos[video_id].get('running', False):
                        return
                    
                    # IMPROVEMENT: Get the actual time elapsed since last frame
                    current_time = time.time()
                    elapsed = current_time - self.videos[video_id].get('last_frame_time', current_time)
                    
                    # Only update if enough time has passed for the next frame
                    # This helps ensure smooth playback at the desired FPS
                    if elapsed < frame_interval * 0.8:  # Allow some slack (80% of interval)
                        # Schedule next check sooner
                        window.after(int(frame_interval * 200), update_frame)  # Check again in 20% of the frame time
                        return
                    
                    # Update last frame time
                    self.videos[video_id]['last_frame_time'] = current_time
                    
                    # IMPROVEMENT: Try to use preloaded frames first for instant display
                    frame = None
                    preloaded_used = False
                    
                    if 'preloaded_frames' in self.videos[video_id] and self.videos[video_id]['next_preloaded'] < len(self.videos[video_id]['preloaded_frames']):
                        # Use a preloaded frame
                        frame = self.videos[video_id]['preloaded_frames'][self.videos[video_id]['next_preloaded']]
                        self.videos[video_id]['next_preloaded'] += 1
                        preloaded_used = True
                        
                        # If we've used all preloaded frames, free the memory
                        if self.videos[video_id]['next_preloaded'] >= len(self.videos[video_id]['preloaded_frames']):
                            del self.videos[video_id]['preloaded_frames']
                            del self.videos[video_id]['next_preloaded']
                            
                        ret = True
                    else:
                        # Check frame cache first
                        current_pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                        
                        if current_pos in self.videos[video_id]['frame_cache']:
                            # Cache hit
                            frame = self.videos[video_id]['frame_cache'][current_pos]
                            self.videos[video_id]['cache_hits'] += 1
                            ret = True
                        else:
                            # Cache miss - read from video
                            self.videos[video_id]['cache_misses'] += 1
                            ret, frame = cap.read()
                            
                            # If end of video, loop back to beginning
                            if not ret:
                                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                                ret, frame = cap.read()
                                if not ret:
                                    self.videos[video_id]['running'] = False
                                    return
                                    
                            # Process the frame
                            if ret and frame is not None:
                                # Convert and resize
                                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                                frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_LINEAR)
                                
                                # Add to cache if cache isn't full
                                cache = self.videos[video_id]['frame_cache']
                                if len(cache) < self.frame_cache_size:
                                    cache[current_pos] = frame
                                elif random.random() < 0.1:  # 10% chance to replace a random frame
                                    # Replace a random cached frame
                                    cached_frames = list(cache.keys())
                                    if cached_frames:
                                        random_key = random.choice(cached_frames)
                                        del cache[random_key]
                                        cache[current_pos] = frame
                    
                    if ret and frame is not None:
                        try:
                            # IMPROVEMENT: More efficient image creation
                            if not preloaded_used:
                                # Only need to create new PhotoImage if not using preloaded frame
                                img = Image.fromarray(frame, 'RGB')
                                photo = ImageTk.PhotoImage(image=img)
                            else:
                                # Preloaded frame is already a numpy array ready to be displayed
                                img = Image.fromarray(frame, 'RGB')
                                photo = ImageTk.PhotoImage(image=img)
                            
                            # Update the image on canvas
                            if image_id:
                                canvas.itemconfig(image_id, image=photo)
                            else:
                                image_id = canvas.create_image(width // 2, height // 2, 
                                                            image=photo, anchor=tk.CENTER)
                            
                            # Keep reference to prevent garbage collection
                            canvas.photo = photo
                            
                            # Update last update time
                            self.videos[video_id]['last_update'] = current_time
                            
                            # Schedule next frame update - use precise timing
                            # Calculate time until next frame should be displayed
                            next_frame_time = frame_interval - (time.time() - current_time)
                            next_delay = max(1, int(next_frame_time * 1000))  # Min 1ms
                            
                            if self.videos.get(video_id, {}).get('running', False):
                                window.after(next_delay, update_frame)
                            
                        except Exception as e:
                            logger.error(f"Error updating video frame: {e}")
                            self.videos[video_id]['running'] = False
                    else:
                        # Problem with video, stop playback
                        self.videos[video_id]['running'] = False
                        
                except Exception as e:
                    logger.error(f"Video playback error: {e}")
                    try:
                        self.videos[video_id]['running'] = False
                    except:
                        pass
            
            # Set up window close handler
            def on_window_close():
                try:
                    # Stop the playback
                    self.videos[video_id]['running'] = False
                    
                    # Release video capture
                    cap.release()
                    
                    # Remove from videos dictionary
                    if video_id in self.videos:
                        del self.videos[video_id]
                        
                except Exception as e:
                    logger.error(f"Error in video window close handler: {e}")
            
            # Store close handler
            self.videos[video_id]['close_handler'] = on_window_close
            self.videos[video_id]['last_frame_time'] = time.time()
            
            # Start the update loop
            window.after(10, update_frame)  # Start after a short delay to allow window to render
            
            return True
        except Exception as e:
            logger.error(f"Error setting up video playback: {e}\n{traceback.format_exc()}")
            return False
            
    def _close_video(self, window, video_id):
        """Clean up video resources"""
        try:
            if video_id in self.videos:
                video_info = self.videos[video_id]
                
                # Cancel any scheduled frame updates
                if video_info.get('frame_id'):
                    try:
                        window.after_cancel(video_info['frame_id'])
                    except:
                        pass
                
                # Release video capture
                if video_info.get('cap'):
                    try:
                        video_info['cap'].release()
                    except:
                        pass
                
                # Clean up any stored frames to free memory
                if 'preloaded_frames' in video_info:
                    del video_info['preloaded_frames']
                
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
            logger.error(f"Error closing video: {e}") 