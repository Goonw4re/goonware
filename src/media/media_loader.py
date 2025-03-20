"""
Media Loader module - manages the display of images, GIFs, and videos in popup windows.
This module has been refactored into multiple files for better organization and performance.
"""

import logging

# Import all loader components
from .base_loader import MediaLoaderBase
from .image_loader import ImageLoader
from .gif_loader import GifLoader
from .video_loader import VideoLoader

# Set up logging
logger = logging.getLogger(__name__)

# Export all classes for backward compatibility
__all__ = ['MediaLoaderBase', 'ImageLoader', 'GifLoader', 'VideoLoader'] 