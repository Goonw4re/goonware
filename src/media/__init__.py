"""
Media module for Goonware.
This module provides functionality for displaying media popups.
"""

# Import core components for easier access
from .media_loader import MediaLoaderBase, ImageLoader, GifLoader, VideoLoader
from .media_display import MediaDisplay
from .window_manager import WindowManager
from .animation import AnimationManager
from .path_utils import MediaPathManager

# Expose all classes
__all__ = [
    'MediaLoaderBase', 
    'ImageLoader', 
    'GifLoader', 
    'VideoLoader',
    'MediaDisplay',
    'WindowManager', 
    'AnimationManager',
    'MediaPathManager'
] 