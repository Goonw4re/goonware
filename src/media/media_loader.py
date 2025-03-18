import os
import tkinter as tk
import random
import logging
import traceback
from PIL import Image, ImageTk, ImageSequence
from io import BytesIO
import zipfile
import cv2

logger = logging.getLogger(__name__)

class MediaLoaderBase:
    def __init__(self, display):
        self.display = display
    
    def _create_base_window(self):
        """Create a base popup window with common properties"""
        window = tk.Toplevel()
        window.withdraw()  # Hide window while setting up
        window.overrideredirect(True)  # Remove borders
        window.attributes('-toolwindow', True)  # Hide from taskbar
        
        # Configure window for transparency
        window.attributes('-alpha', 1.0)  # Make window fully opaque
        window.config(bg='#F0F0F0')  # Set window background to light gray instead of transparent black
        
        # Optimize window creation
        window.update_idletasks()  # Process pending events
        
        return window
    
    def _position_window(self, window, width, height):
        """Position a window on the screen and add a close button"""
        position_result = self.display.get_random_screen_position(width, height)
        
        # Handle both old and new return formats for backward compatibility
        if len(position_result) == 3:
            x_pos, y_pos, monitor_idx = position_result
            # Store the monitor index for this window
            self.display.window_manager.window_monitors[window] = monitor_idx
            logger.info(f"Positioned window at: {x_pos},{y_pos} on monitor {monitor_idx}")
        else:
            x_pos, y_pos = position_result
            logger.info(f"Positioned window at: {x_pos},{y_pos}")
        
        window.geometry(f"{width}x{height}+{x_pos}+{y_pos}")
        
        # Create the close button frame - always visible
        close_frame = tk.Frame(window, bg='#F0F0F0', width=16, height=16)
        close_frame.place(x=3, y=3)
        close_frame.pack_propagate(False)
        
        close_btn = tk.Label(
            close_frame,
            text="×",
            font=('Segoe UI', 10, 'bold'),
            fg='black',
            bg='#F0F0F0',
            cursor='hand2',
            padx=1,
            pady=0
        )
        close_btn.pack(expand=True, fill='both')
        
        # Close functionality - use direct window destruction for reliability
        def close_window(event):
            try:
                logger.info(f"Close button clicked, destroying window directly")
                # First remove from window manager to prevent callbacks
                self.display.window_manager.remove_window(window)
                # Then destroy the window
                window.destroy()
            except Exception as e:
                logger.error(f"Error closing window from close button: {e}")
                # Fallback: try direct destruction
                try:
                    window.destroy()
                except:
                    pass
            
        close_btn.bind('<Button-1>', close_window)
        close_frame.bind('<Button-1>', close_window)
        
        # Add hover effect for better UX
        def on_enter(e):
            close_btn.configure(fg='red')
            
        def on_leave(e):
            close_btn.configure(fg='black')
            
        # Bind hover events to the button itself
        close_btn.bind('<Enter>', on_enter)
        close_btn.bind('<Leave>', on_leave)
        close_frame.bind('<Enter>', on_enter)
        close_frame.bind('<Leave>', on_leave)
        
        return window

class ImageLoader(MediaLoaderBase):
    def __init__(self, display):
        super().__init__(display)
        self.image_cache = {}  # Cache for frequently used images
        self.cache_size_limit = 20  # Maximum number of images to cache
    
    def display_image(self):
        """Display a random image from the available paths"""
        try:
            # CRITICAL FIX: Check if new popups are prevented
            if hasattr(self.display, 'prevent_new_popups') and self.display.prevent_new_popups:
                logger.info("New popups are prevented, skipping image display")
                return None
                
            # Check if display is still running
            if not self.display.running:
                logger.info("Display is not running, skipping image display")
                return None
                
            # Check if we have any image paths
            if not self.display.image_paths:
                logger.warning("No image paths available")
                return None
            
            # Choose a random image path
            image_path = random.choice(self.display.image_paths)
            
            # Handle both tuple format (zip_path, internal_path) and string format paths
            if isinstance(image_path, tuple) and len(image_path) == 2:
                zip_path, internal_path = image_path
                logger.info(f"Displaying image from zip: {zip_path}/{internal_path}")
                
                # Check if this tuple path is in cache
                cache_key = f"{zip_path}:{internal_path}"
                if cache_key in self.image_cache:
                    logger.info(f"Using cached image: {cache_key}")
                    photo_image = self.image_cache[cache_key]
                    width, height = photo_image.width(), photo_image.height()
                else:
                    # Load from zip file
                    try:
                        with zipfile.ZipFile(zip_path, 'r') as zf:
                            with zf.open(internal_path) as f:
                                image_data = f.read()
                                
                                # Use BytesIO to avoid writing to disk
                                image = Image.open(BytesIO(image_data))
                                
                                # CRITICAL FIX: Properly handle transparency
                                if image.mode == 'RGBA':
                                    # Create a light gray background
                                    background = Image.new('RGB', image.size, (240, 240, 240))
                                    # Paste the image using alpha as mask
                                    background.paste(image, (0, 0), image)
                                    image = background
                                
                                # Scale image
                                image = self.display.scale_image(image)
                                
                                # Get dimensions
                                width, height = image.size
                                
                                # Convert to PhotoImage
                                photo_image = ImageTk.PhotoImage(image)
                                
                                # Cache the image if we haven't reached the limit
                                if len(self.image_cache) < self.cache_size_limit:
                                    self.image_cache[cache_key] = photo_image
                                elif self.image_cache and random.random() < 0.2:
                                    # 20% chance to replace a random cached image
                                    old_key = random.choice(list(self.image_cache.keys()))
                                    del self.image_cache[old_key]
                                    self.image_cache[cache_key] = photo_image
                    except Exception as e:
                        logger.error(f"Error loading image from zip: {e}\n{traceback.format_exc()}")
                        return None
            elif isinstance(image_path, str):
                logger.info(f"Displaying image: {image_path}")
                
                # Check if image is in cache
                if image_path in self.image_cache:
                    logger.info(f"Using cached image: {image_path}")
                    photo_image = self.image_cache[image_path]
                    width, height = photo_image.width(), photo_image.height()
                else:
                    # Load image data from zip file
                    if image_path.startswith("zip://"):
                        # Parse zip path format: zip://zipfile.zip/path/to/image.jpg
                        parts = image_path[6:].split('/', 1)
                        if len(parts) != 2:
                            logger.error(f"Invalid zip path format: {image_path}")
                            return None
                        
                        zip_file, internal_path = parts
                        
                        try:
                            with zipfile.ZipFile(zip_file, 'r') as zf:
                                with zf.open(internal_path) as f:
                                    image_data = f.read()
                                    
                                    # Use BytesIO to avoid writing to disk
                                    image = Image.open(BytesIO(image_data))
                                    
                                    # CRITICAL FIX: Properly handle transparency
                                    if image.mode == 'RGBA':
                                        # Create a light gray background
                                        background = Image.new('RGB', image.size, (240, 240, 240))
                                        # Paste the image using alpha as mask
                                        background.paste(image, (0, 0), image)
                                        image = background
                                    
                                    # Scale image
                                    image = self.display.scale_image(image)
                                    
                                    # Get dimensions
                                    width, height = image.size
                                    
                                    # Convert to PhotoImage
                                    photo_image = ImageTk.PhotoImage(image)
                                    
                                    # Cache the image if we haven't reached the limit
                                    if len(self.image_cache) < self.cache_size_limit:
                                        self.image_cache[image_path] = photo_image
                                    elif self.image_cache and random.random() < 0.2:
                                        # 20% chance to replace a random cached image
                                        old_key = random.choice(list(self.image_cache.keys()))
                                        del self.image_cache[old_key]
                                        self.image_cache[image_path] = photo_image
                        except Exception as e:
                            logger.error(f"Error loading image from zip: {e}\n{traceback.format_exc()}")
                            return None
                    else:
                        # Regular file path
                        try:
                            image = Image.open(image_path)
                            image = self.display.scale_image(image)
                            width, height = image.size
                            photo_image = ImageTk.PhotoImage(image)
                            
                            # Cache the image
                            if len(self.image_cache) < self.cache_size_limit:
                                self.image_cache[image_path] = photo_image
                        except Exception as e:
                            logger.error(f"Error loading image: {e}\n{traceback.format_exc()}")
                            return None
            else:
                logger.error(f"Unsupported image path format: {image_path}")
                return None
            
            # CRITICAL FIX: Check again if new popups are prevented or display is stopped
            if (hasattr(self.display, 'prevent_new_popups') and self.display.prevent_new_popups) or not self.display.running:
                logger.info("Display stopped or new popups prevented while loading image, skipping window creation")
                return None
            
            # Create window
            window = self._create_base_window()
            
            # Create label to display image
            label = tk.Label(window, image=photo_image, bg='#F0F0F0', bd=0)
            label.image = photo_image  # Keep a reference to prevent garbage collection
            label.pack(fill=tk.BOTH, expand=True)
            
            # Position window
            window = self._position_window(window, width, height)
            
            # Show window
            window.deiconify()
            window.attributes('-topmost', True)
            window.lift()
            
            # Add to window manager
            self.display.window_manager.add_window(window, enable_bounce=True)
            
            # Schedule auto-close
            popup_duration = getattr(self.display, 'popup_duration', 15)
            window.after(int(popup_duration * 1000), lambda: self.display.window_manager.remove_window_safely(window))
            
            return window
            
        except Exception as e:
            logger.error(f"Error displaying image: {e}\n{traceback.format_exc()}")
            return None

class GifLoader(MediaLoaderBase):
    def __init__(self, display):
        super().__init__(display)
    
    def display_gif(self):
        """Display a random GIF from the available paths"""
        try:
            # CRITICAL FIX: Check if new popups are prevented
            if hasattr(self.display, 'prevent_new_popups') and self.display.prevent_new_popups:
                logger.info("New popups are prevented, skipping GIF display")
                return None
                
            # Check if display is still running
            if not self.display.running:
                logger.info("Display is not running, skipping GIF display")
                return None
                
            # Check if we have any GIF paths
            if not self.display.gif_paths:
                logger.warning("No GIF paths available")
                return None
            
            # Select random GIF path
            gif_path = random.choice(self.display.gif_paths)
            
            # Create new window for media
            window = self._create_base_window()
            
            # Handle both tuple format (zip_path, internal_path) and string format paths
            if isinstance(gif_path, tuple) and len(gif_path) == 2:
                zip_path, gif_name = gif_path
                logger.info(f"Selected GIF from zip: {zip_path}/{gif_name}")
                
                # Load and display GIF from zip
                try:
                    # Verify the zip file exists
                    if not os.path.exists(zip_path):
                        logger.error(f"Zip file does not exist: {zip_path}")
                        window.destroy()
                        return None
                        
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        # Verify the GIF exists in the zip
                        if gif_name not in zf.namelist():
                            logger.error(f"GIF {gif_name} not found in zip {zip_path}")
                            window.destroy()
                            return None
                            
                        # Extract GIF to memory
                        with zf.open(gif_name) as f:
                            gif_data = BytesIO(f.read())
                            
                        # CRITICAL FIX: Check again if new popups are prevented or display is stopped
                        if (hasattr(self.display, 'prevent_new_popups') and self.display.prevent_new_popups) or not self.display.running:
                            logger.info("Display stopped or new popups prevented while loading GIF, skipping window creation")
                            return None
                            
                        # Create GIF window
                        window = self._create_gif_window(gif_data)
                        if not window:
                            return None
                            
                        # Add window to manager
                        self.display.window_manager.add_window(window, enable_bounce=True)
                        
                        # Schedule removal after delay
                        self.display.window_manager.remove_after_delay(window)
                        
                        logger.info(f"Successfully displayed GIF: {zip_path}/{gif_name}")
                        return window
                        
                except zipfile.BadZipFile as e:
                    logger.error(f"Bad zip file {zip_path}: {e}")
                    window.destroy()
                    # Remove this zip from the paths to prevent future errors
                    self.display.gif_paths = [p for p in self.display.gif_paths if not (isinstance(p, tuple) and p[0] == zip_path)]
                    return None
                except Exception as e:
                    logger.error(f"Error loading GIF from {zip_path}/{gif_name}: {e}\n{traceback.format_exc()}")
                    try:
                        window.destroy()
                    except tk.TclError:
                        pass
                    return None
            elif isinstance(gif_path, str):
                logger.info(f"Selected GIF: {gif_path}")
                
                # Handle string format paths (for future compatibility)
                if gif_path.startswith("zip://"):
                    # Parse zip path format: zip://zipfile.zip/path/to/gif.gif
                    parts = gif_path[6:].split('/', 1)
                    if len(parts) != 2:
                        logger.error(f"Invalid zip path format: {gif_path}")
                        window.destroy()
                        return None
                    
                    zip_file, internal_path = parts
                    
                    try:
                        with zipfile.ZipFile(zip_file, 'r') as zf:
                            with zf.open(internal_path) as f:
                                gif_data = BytesIO(f.read())
                                
                            # CRITICAL FIX: Check again if new popups are prevented or display is stopped
                            if (hasattr(self.display, 'prevent_new_popups') and self.display.prevent_new_popups) or not self.display.running:
                                logger.info("Display stopped or new popups prevented while loading GIF, skipping window creation")
                                return None
                                
                            # Create GIF window
                            window = self._create_gif_window(gif_data)
                            if not window:
                                return None
                                
                            # Add window to manager
                            self.display.window_manager.add_window(window, enable_bounce=True)
                            
                            # Schedule removal after delay
                            self.display.window_manager.remove_after_delay(window)
                            
                            logger.info(f"Successfully displayed GIF: {gif_path}")
                            return window
                    except Exception as e:
                        logger.error(f"Error loading GIF from {gif_path}: {e}\n{traceback.format_exc()}")
                        window.destroy()
                        return None
                else:
                    # Regular file path
                    try:
                        with open(gif_path, 'rb') as f:
                            gif_data = BytesIO(f.read())
                            
                        # CRITICAL FIX: Check again if new popups are prevented or display is stopped
                        if (hasattr(self.display, 'prevent_new_popups') and self.display.prevent_new_popups) or not self.display.running:
                            logger.info("Display stopped or new popups prevented while loading GIF, skipping window creation")
                            return None
                            
                        # Create GIF window
                        window = self._create_gif_window(gif_data)
                        if not window:
                            return None
                            
                        # Add window to manager
                        self.display.window_manager.add_window(window, enable_bounce=True)
                        
                        # Schedule removal after delay
                        self.display.window_manager.remove_after_delay(window)
                        
                        logger.info(f"Successfully displayed GIF: {gif_path}")
                        return window
                    except Exception as e:
                        logger.error(f"Error loading GIF from {gif_path}: {e}\n{traceback.format_exc()}")
                        window.destroy()
                        return None
            else:
                logger.error(f"Unsupported GIF path format: {gif_path}")
                window.destroy()
                return None
                
        except Exception as e:
            logger.error(f"Error displaying GIF: {e}\n{traceback.format_exc()}")
            return None
    
    def _create_gif_window(self, gif_data):
        """Create a window for GIF display"""
        try:
            window = self._create_base_window()
            
            # Create GIF window
            gif = Image.open(gif_data)
            
            # Store original dimensions
            width, height = gif.size
            logger.info(f"Loaded GIF: size={width}x{height}, format={gif.format}")
            
            # Scale if needed
            if width > self.display.max_image_size[0] or height > self.display.max_image_size[1]:
                width_ratio = self.display.max_image_size[0] / width
                height_ratio = self.display.max_image_size[1] / height
                scale = min(width_ratio, height_ratio)
                width = int(width * scale)
                height = int(height * scale)
                logger.info(f"Scaling GIF to {width}x{height}")
            
            # Apply user's scale factor
            width = int(width * self.display.scale_factor)
            height = int(height * self.display.scale_factor)
            
            # Process all frames
            frames = []
            try:
                for frame in ImageSequence.Iterator(gif):
                    frame = frame.copy()
                    frame = frame.resize((width, height), Image.Resampling.LANCZOS)
                    frames.append(ImageTk.PhotoImage(frame))
                logger.info(f"Processed {len(frames)} GIF frames")
            except Exception as e:
                logger.error(f"Error processing GIF frames: {e}\n{traceback.format_exc()}")
                window.destroy()
                return None
            
            # Create label for GIF display
            label = tk.Label(window, bg='#F0F0F0')
            label.pack(fill=tk.BOTH, expand=True)
            
            # Position window
            window = self._position_window(window, width, height)
            
            # Show window
            window.deiconify()
            window.attributes('-topmost', True)
            window.lift()
            
            # Store animation info
            self.display.window_manager.gif_windows[window] = {
                'frames': frames,
                'current_frame': 0,
                'label': label,
                'delay': gif.info.get('duration', 100)  # Default to 100ms if not specified
            }
            
            # Start animation
            self.display.animation_manager.animate_gif(window)
            
            # Add to window manager
            self.display.window_manager.add_window(window, enable_bounce=True)
            
            return window
            
        except Exception as e:
            logger.error(f"Error creating GIF window: {e}\n{traceback.format_exc()}")
            if window and window.winfo_exists():
                window.destroy()
            return None

class VideoLoader(MediaLoaderBase):
    def __init__(self, display):
        super().__init__(display)
        self.videos = {}  # Track video players
    
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
            window = self._create_base_window()
            
            # Handle both tuple format (zip_path, internal_path) and string format paths
            if isinstance(video_path, tuple) and len(video_path) == 2:
                zip_path, video_name = video_path
                logger.info(f"Selected video from zip: {zip_path}/{video_name}")
                
                # Load and display video from zip
                try:
                    # Verify the zip file exists
                    if not os.path.exists(zip_path):
                        logger.error(f"Zip file does not exist: {zip_path}")
                        window.destroy()
                        return None
                        
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        # Verify the video exists in the zip
                        if video_name not in zf.namelist():
                            logger.error(f"Video {video_name} not found in zip {zip_path}")
                            window.destroy()
                            return None
                            
                        # Extract video to temporary file
                        import tempfile
                        import time
                        
                        # Create a unique temporary file
                        temp_dir = tempfile.gettempdir()
                        temp_filename = f"goonware_temp_{int(time.time())}_{os.path.basename(video_name)}"
                        temp_path = os.path.join(temp_dir, temp_filename)
                        
                        # Extract video to temp file
                        with zf.open(video_name) as f_in, open(temp_path, 'wb') as f_out:
                            f_out.write(f_in.read())
                        
                        # CRITICAL FIX: Check again if new popups are prevented or display is stopped
                        if (hasattr(self.display, 'prevent_new_popups') and self.display.prevent_new_popups) or not self.display.running:
                            logger.info("Display stopped or new popups prevented while loading video, skipping window creation")
                            # Clean up temp file
                            try:
                                os.remove(temp_path)
                            except:
                                pass
                            return None
                        
                        # Create video window
                        window = self._create_video_window(temp_path)
                        if not window:
                            # Clean up temp file if window creation failed
                            try:
                                os.remove(temp_path)
                            except:
                                pass
                            return None
                        
                        # Store temp file path for cleanup
                        if window in self.display.window_manager.video_windows:
                            self.display.window_manager.video_windows[window]['temp_file'] = temp_path
                        
                        # Add window to manager
                        self.display.window_manager.add_window(window, enable_bounce=True)
                        
                        # Schedule removal after delay
                        self.display.window_manager.remove_after_delay(window)
                        
                        logger.info(f"Successfully displayed video: {zip_path}/{video_name}")
                        return window
                        
                except zipfile.BadZipFile as e:
                    logger.error(f"Bad zip file {zip_path}: {e}")
                    window.destroy()
                    # Remove this zip from the paths to prevent future errors
                    self.display.video_paths = [p for p in self.display.video_paths if not (isinstance(p, tuple) and p[0] == zip_path)]
                    return None
                except Exception as e:
                    logger.error(f"Error loading video from {zip_path}/{video_name}: {e}\n{traceback.format_exc()}")
                    try:
                        window.destroy()
                    except tk.TclError:
                        pass
                    return None
            elif isinstance(video_path, str):
                logger.info(f"Selected video: {video_path}")
                
                # Handle string format paths (for future compatibility)
                if video_path.startswith("zip://"):
                    # Parse zip path format: zip://zipfile.zip/path/to/video.mp4
                    parts = video_path[6:].split('/', 1)
                    if len(parts) != 2:
                        logger.error(f"Invalid zip path format: {video_path}")
                        window.destroy()
                        return None
                    
                    zip_file, internal_path = parts
                    
                    try:
                        # Extract to temp file and play
                        import tempfile
                        import time
                        
                        # Create a unique temporary file
                        temp_dir = tempfile.gettempdir()
                        temp_filename = f"goonware_temp_{int(time.time())}_{os.path.basename(internal_path)}"
                        temp_path = os.path.join(temp_dir, temp_filename)
                        
                        with zipfile.ZipFile(zip_file, 'r') as zf:
                            with zf.open(internal_path) as f_in, open(temp_path, 'wb') as f_out:
                                f_out.write(f_in.read())
                        
                        # CRITICAL FIX: Check again if new popups are prevented or display is stopped
                        if (hasattr(self.display, 'prevent_new_popups') and self.display.prevent_new_popups) or not self.display.running:
                            logger.info("Display stopped or new popups prevented while loading video, skipping window creation")
                            # Clean up temp file
                            try:
                                os.remove(temp_path)
                            except:
                                pass
                            return None
                        
                        # Create video window
                        window = self._create_video_window(temp_path)
                        if not window:
                            # Clean up temp file if window creation failed
                            try:
                                os.remove(temp_path)
                            except:
                                pass
                            return None
                        
                        # Store temp file path for cleanup
                        if window in self.display.window_manager.video_windows:
                            self.display.window_manager.video_windows[window]['temp_file'] = temp_path
                        
                        # Add window to manager
                        self.display.window_manager.add_window(window, enable_bounce=True)
                        
                        # Schedule removal after delay
                        self.display.window_manager.remove_after_delay(window)
                        
                        logger.info(f"Successfully displayed video: {video_path}")
                        return window
                    except Exception as e:
                        logger.error(f"Error loading video from {video_path}: {e}\n{traceback.format_exc()}")
                        window.destroy()
                        return None
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
            else:
                logger.error(f"Unsupported video path format: {video_path}")
                window.destroy()
                return None
                
        except Exception as e:
            logger.error(f"Error displaying video: {e}\n{traceback.format_exc()}")
            return None
    
    def _create_video_window(self, video_path):
        """Create a window for video display"""
        try:
            logger.info(f"Opening video file: {video_path}")
            
            # Check if video file exists
            if not os.path.exists(video_path):
                logger.error(f"Video file does not exist: {video_path}")
                return None
                
            # Open video file
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"Failed to open video: {video_path}")
                return None
                
            # Get video properties
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            logger.info(f"Video properties: {width}x{height}, {fps} FPS, {frame_count} frames")
            
            # Scale video if needed
            if width > self.display.max_image_size[0] or height > self.display.max_image_size[1]:
                width_ratio = self.display.max_image_size[0] / width
                height_ratio = self.display.max_image_size[1] / height
                scale = min(width_ratio, height_ratio)
                width = int(width * scale)
                height = int(height * scale)
                logger.info(f"Scaling video to {width}x{height}")
            
            # Apply user's scale factor
            width = int(width * self.display.scale_factor)
            height = int(height * self.display.scale_factor)
            
            # Create base window
            window = self._create_base_window()
            
            # Create canvas for video display
            canvas = tk.Canvas(window, width=width, height=height, bg='#F0F0F0', 
                                highlightthickness=0)
            canvas.pack(fill=tk.BOTH, expand=True)
            
            # Position window
            window = self._position_window(window, width, height)
            
            # Show window
            window.deiconify()
            window.attributes('-topmost', True)
            window.lift()
            
            # Start video playback
            self._play_video(window, canvas, cap, width, height, fps)
            
            return window
            
        except Exception as e:
            logger.error(f"Error creating video window: {e}\n{traceback.format_exc()}")
            return None 

    def _play_video(self, window, canvas, cap, width, height, fps):
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
                'playing': True,
                'frame_id': None
            }
            
            # Set delay between frames (ms)
            delay = int(1000 / max(1, fps))
            
            # Function to update frames
            def update_frame():
                if video_id not in self.videos:
                    return  # Video was closed
                    
                video_info = self.videos[video_id]
                
                if not video_info['playing']:
                    return  # Video playback stopped
                    
                # Get next frame
                ret, frame = video_info['cap'].read()
                
                if ret:
                    # Convert frame from BGR to RGB
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # Resize frame
                    frame = cv2.resize(frame, (video_info['width'], video_info['height']))
                    
                    # Convert to PhotoImage
                    img = Image.fromarray(frame)
                    photo = ImageTk.PhotoImage(image=img)
                    
                    # Update canvas
                    canvas.config(width=video_info['width'], height=video_info['height'])
                    if 'image_id' in video_info:
                        canvas.itemconfig(video_info['image_id'], image=photo)
                    else:
                        video_info['image_id'] = canvas.create_image(
                            video_info['width'] // 2, 
                            video_info['height'] // 2, 
                            image=photo, 
                            anchor=tk.CENTER
                        )
                    
                    # Keep reference to prevent garbage collection
                    canvas.photo = photo
                    
                    # Schedule next frame
                    video_info['frame_id'] = window.after(delay, update_frame)
                else:
                    # Video ended, close window after short delay
                    window.after(500, lambda: self._close_video(window, video_id))
            
            # Function to handle window close
            def on_window_close():
                self._close_video(window, video_id)
                window.destroy()
            
            # Bind close event
            window.protocol("WM_DELETE_WINDOW", on_window_close)
            
            # Start playback
            update_frame()
            
        except Exception as e:
            logger.error(f"Error in video playback: {e}\n{traceback.format_exc()}")
            
    def _close_video(self, window, video_id):
        """Clean up video resources"""
        try:
            if video_id in self.videos:
                video_info = self.videos[video_id]
                
                # Cancel any scheduled frame updates
                if video_info.get('frame_id'):
                    window.after_cancel(video_info['frame_id'])
                
                # Release video capture
                if video_info.get('cap'):
                    video_info['cap'].release()
                
                # Remove from tracking dict
                del self.videos[video_id]
                
                # Remove from window manager
                try:
                    self.display.window_manager.remove_window(window)
                except:
                    pass
                    
                logger.info(f"Closed video player {video_id}")
        except Exception as e:
            logger.error(f"Error closing video: {e}") 