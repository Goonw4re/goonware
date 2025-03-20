import os
import logging
import traceback
import zipfile
from io import BytesIO
import random
import tkinter as tk
from PIL import Image, ImageTk, ImageSequence

from .base_loader import MediaLoaderBase

logger = logging.getLogger(__name__)

class GifLoader(MediaLoaderBase):
    def __init__(self, display):
        super().__init__(display)
        # Add GIF optimization settings
        self.max_frames = 48  # Limit frames for better performance
        self.gif_cache = {}  # Cache for frequently used GIFs
        self.cache_size_limit = 5  # Small cache limit to prevent memory issues
    
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
            window = self._get_window_from_pool()
            
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
                    logger.error(f"Bad archive file {zip_path}: {e}")
                    # Remove this archive from the paths to prevent future errors
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
                    # Parse archive path format: zip://archive-file.zip/path/to/gif.gif
                    # Note: Both .zip and .gmodel files use the same format
                    parts = gif_path[6:].split('/', 1)
                    if len(parts) != 2:
                        logger.error(f"Invalid archive path format: {gif_path}")
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
            window = self._get_window_from_pool()
            
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
            
            # Ensure minimum size of 200x150
            if width < 200 or height < 150:
                # Calculate scale to reach minimum size while maintaining aspect ratio
                width_scale = 200 / width if width < 200 else 1
                height_scale = 150 / height if height < 150 else 1
                scale = max(width_scale, height_scale)
                
                # Apply minimum size scaling
                width = max(200, int(width * scale))
                height = max(150, int(height * scale))
                logger.info(f"Applied minimum size constraint to GIF: {width}x{height}")
            
            # OPTIMIZATION: Limit number of frames for performance
            frames = []
            frame_count = 0
            max_frames = self.max_frames
            
            try:
                # Count total frames
                total_frames = 0
                for _ in ImageSequence.Iterator(gif):
                    total_frames += 1
                
                # Calculate frame sampling rate if too many frames
                sample_rate = max(1, total_frames // max_frames) if total_frames > max_frames else 1
                logger.info(f"GIF has {total_frames} frames, sampling every {sample_rate} frame(s)")
                
                # Process selected frames
                for i, frame in enumerate(ImageSequence.Iterator(gif)):
                    # Sample frames to reduce memory usage and improve performance
                    if i % sample_rate != 0 and i != 0:  # Always include first frame
                        continue
                        
                    # FIX: Properly handle color modes to prevent blue tint
                    frame = frame.copy()
                    
                    # Convert to RGBA if possible, or RGB as fallback to ensure proper color rendering
                    # This prevents the blue tint issue by making sure color channels are properly preserved
                    if 'A' in frame.mode or frame.mode == 'P':
                        frame = frame.convert('RGBA')
                    else:
                        frame = frame.convert('RGB')
                    
                    # Use BILINEAR for faster resizing
                    frame = frame.resize((width, height), Image.Resampling.BILINEAR)
                    frames.append(ImageTk.PhotoImage(frame))
                    frame_count += 1
                    
                    # Hard limit on frames for very long GIFs
                    if frame_count >= max_frames:
                        break
                        
                logger.info(f"Processed {frame_count} GIF frames")
            except Exception as e:
                logger.error(f"Error processing GIF frames: {e}\n{traceback.format_exc()}")
                window.destroy()
                return None
            
            # FIX: Create label with black background instead of transparent to prevent blue tint
            label = tk.Label(window, bg='black')
            label.pack(fill=tk.BOTH, expand=True)
            
            # Position window
            window = self._position_window(window, width, height)
            
            # Show window
            window.deiconify()
            window.attributes('-topmost', True)
            window.lift()
            
            # Calculate average frame delay
            # If GIF specifies per-frame delays, average them
            delays = []
            try:
                for i, frame in enumerate(ImageSequence.Iterator(gif)):
                    if i >= frame_count:
                        break
                    delays.append(frame.info.get('duration', 100))
            except:
                pass
                
            # Calculate average delay, defaulting to 100ms
            avg_delay = sum(delays) // len(delays) if delays else 100
            # Ensure reasonable delay bounds
            avg_delay = max(40, min(avg_delay, 200))  # Between 40-200ms
            
            # Store animation info
            self.display.window_manager.gif_windows[window] = {
                'frames': frames,
                'current_frame': 0,
                'label': label,
                'delay': avg_delay,
                'gif_data': None  # Don't store the gif_data to save memory
            }
            
            # Start animation
            self.display.animation_manager.animate_gif(window)
            
            # Add to window manager
            self.display.window_manager.add_window(window, enable_bounce=True)
            
            # Free up resources
            gif.close()
            gif_data.close()
            
            return window
            
        except Exception as e:
            logger.error(f"Error creating GIF window: {e}\n{traceback.format_exc()}")
            if window and window.winfo_exists():
                window.destroy()
            return None 