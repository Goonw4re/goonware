import os
import logging
import traceback
import zipfile
from io import BytesIO
import random
import tkinter as tk
from PIL import Image, ImageTk
import time
from concurrent.futures import as_completed

from .base_loader import MediaLoaderBase

logger = logging.getLogger(__name__)

class ImageLoader(MediaLoaderBase):
    def __init__(self, display):
        super().__init__(display)
        self.image_cache = {}  # Cache for frequently used images
        self.cache_size_limit = 20  # Maximum number of images to cache
        self.preloaded_images = {}  # Store preloaded images
    
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
            
            # Check if the file is a zip or gmodel archive
            is_archive = False
            if isinstance(image_path, tuple) and len(image_path) == 2:
                zip_path, internal_path = image_path
                is_archive = True
                logger.debug(f"Image is in archive: {zip_path}/{internal_path}")
            elif isinstance(image_path, str) and (image_path.lower().endswith('.zip') or image_path.lower().endswith('.gmodel')):
                # Note: Both .zip and .gmodel files use the same format
                is_archive = True
                zip_path = image_path
                logger.debug(f"Image path is an archive: {zip_path}")
            
            # Use a preloaded image if available, otherwise load synchronously
            if image_path in self.preloaded_images:
                logger.debug(f"Using preloaded image: {image_path}")
                photo_image, width, height = self.preloaded_images.pop(image_path)
            else:
                # Process based on path type
                photo_image, width, height = self._load_image(image_path, is_archive)
                
            if not photo_image:
                return None
            
            # CRITICAL FIX: Check again if new popups are prevented or display is stopped
            if (hasattr(self.display, 'prevent_new_popups') and self.display.prevent_new_popups) or not self.display.running:
                logger.info("Display stopped or new popups prevented while loading image, skipping window creation")
                return None
            
            # Create window
            window = self._get_window_from_pool()
            
            # Create label to display image with transparent background
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
            
            # Start preloading the next batch of images
            self._start_preloading()
            
            return window
            
        except Exception as e:
            logger.error(f"Error displaying image: {e}\n{traceback.format_exc()}")
            return None
    
    def _start_preloading(self):
        """Preload images in background threads"""
        if not self.display.image_paths or len(self.preloaded_images) >= 5:
            return  # Already have enough preloaded images
            
        # Choose a few random paths to preload
        num_to_preload = min(3, len(self.display.image_paths))
        paths_to_preload = random.sample(self.display.image_paths, num_to_preload)
        
        def preload_processor(path):
            """Process a single path for preloading"""
            try:
                # Check if in archive
                is_archive = False
                if isinstance(path, tuple) and len(path) == 2:
                    is_archive = True
                elif isinstance(path, str) and (path.lower().endswith('.zip') or path.lower().endswith('.gmodel')):
                    is_archive = True
                
                # Load image
                photo_image, width, height = self._load_image(path, is_archive)
                if photo_image:
                    return (path, (photo_image, width, height))
                return None
            except Exception as e:
                logger.error(f"Error preloading image {path}: {e}")
                return None
        
        # Submit preload tasks to thread pool
        def on_preload_complete(results):
            """Handle preloaded results"""
            for result in results:
                if result:
                    path, image_data = result
                    self.preloaded_images[path] = image_data
                    logger.debug(f"Preloaded image: {path}")
        
        # Use the thread pool for preloading
        self.preload_media(paths_to_preload, preload_processor, on_preload_complete)
    
    def _load_image(self, image_path, is_archive):
        """Load image and return PhotoImage, width, height"""
        try:
            photo_image = None
            width = 0
            height = 0
            
            if is_archive:
                # Handle both tuple format (zip_path, internal_path) and string format paths
                if isinstance(image_path, tuple) and len(image_path) == 2:
                    zip_path, internal_path = image_path
                    logger.info(f"Loading image from zip: {zip_path}/{internal_path}")
                    
                    # Check if this tuple path is in cache
                    cache_key = f"{zip_path}:{internal_path}"
                    if cache_key in self.image_cache:
                        logger.info(f"Using cached image: {cache_key}")
                        photo_image = self.image_cache[cache_key]
                        width, height = photo_image.width(), photo_image.height()
                    else:
                        # Load from zip file
                        photo_image, width, height = self._load_from_zip(zip_path, internal_path, cache_key)
                elif isinstance(image_path, str):
                    logger.info(f"Loading image: {image_path}")
                    
                    # Check if image is in cache
                    if image_path in self.image_cache:
                        logger.info(f"Using cached image: {image_path}")
                        photo_image = self.image_cache[image_path]
                        width, height = photo_image.width(), photo_image.height()
                    else:
                        # Load image data from zip file
                        if image_path.startswith("zip://"):
                            # Parse archive path format: zip://archive-file.zip/path/to/image.jpg
                            parts = image_path[6:].split('/', 1)
                            if len(parts) != 2:
                                logger.error(f"Invalid archive path format: {image_path}")
                                return None, 0, 0
                            
                            zip_file, internal_path = parts
                            photo_image, width, height = self._load_from_zip(zip_file, internal_path, image_path)
                        else:
                            # Regular file path
                            photo_image, width, height = self._load_from_file(image_path)
                else:
                    logger.error(f"Unsupported image path format: {image_path}")
                    return None, 0, 0
            else:
                # Regular file path
                photo_image, width, height = self._load_from_file(image_path)
                
            return photo_image, width, height
                
        except Exception as e:
            logger.error(f"Error loading image: {e}\n{traceback.format_exc()}")
            return None, 0, 0
    
    def _load_from_zip(self, zip_path, internal_path, cache_key):
        """Load image from zip file"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                with zf.open(internal_path) as f:
                    image_data = f.read()
                    
                    # Use BytesIO to avoid writing to disk
                    image = Image.open(BytesIO(image_data))
                    
                    # Handle transparency properly
                    if image.mode == 'RGBA':
                        # Keep image in RGBA mode to preserve transparency
                        pass
                    elif image.mode != 'RGB':
                        # Convert other modes to RGBA for better display
                        image = image.convert('RGBA')
                    
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
                    
                    return photo_image, width, height
        except Exception as e:
            logger.error(f"Error loading image from zip: {e}\n{traceback.format_exc()}")
            return None, 0, 0
    
    def _load_from_file(self, image_path):
        """Load image from file"""
        try:
            image = Image.open(image_path)
            image = self.display.scale_image(image)
            width, height = image.size
            photo_image = ImageTk.PhotoImage(image)
            
            # Cache the image
            if len(self.image_cache) < self.cache_size_limit:
                self.image_cache[image_path] = photo_image
            
            return photo_image, width, height
        except Exception as e:
            logger.error(f"Error loading image file: {e}\n{traceback.format_exc()}")
            return None, 0, 0
            
    def batch_process_images(self, paths, max_workers=4):
        """Process multiple images in parallel and return results
        
        This is useful for bulk operations like checking which images are valid
        or generating thumbnails.
        """
        results = []
        
        # Define processor function
        def process_image(path):
            try:
                # Check if in archive
                is_archive = False
                if isinstance(path, tuple) and len(path) == 2:
                    is_archive = True
                elif isinstance(path, str) and (path.lower().endswith('.zip') or path.lower().endswith('.gmodel')):
                    is_archive = True
                
                # Load image but don't cache
                start_time = time.time()
                photo_image, width, height = self._load_image(path, is_archive)
                load_time = time.time() - start_time
                
                if photo_image:
                    return {
                        'path': path,
                        'width': width,
                        'height': height,
                        'success': True,
                        'load_time': load_time
                    }
                else:
                    return {
                        'path': path,
                        'success': False,
                        'load_time': load_time
                    }
            except Exception as e:
                logger.error(f"Error processing image {path}: {e}")
                return {
                    'path': path,
                    'success': False,
                    'error': str(e)
                }
        
        # Use batch processing from base class
        return self.process_batch(paths, process_image, max_workers)
    
    def cleanup(self):
        """Clean up resources"""
        # Clear cache
        self.image_cache.clear()
        self.preloaded_images.clear()
        
        # Call parent cleanup
        super().cleanup() 