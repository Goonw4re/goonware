"""
GMODEL File Viewer Package

This package provides a viewer for GMODEL files (.gmodel), which are specially packaged zip files.
"""

import os
import sys

# Make sure our directory is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import main class
from .viewer import GModelViewer

__all__ = ['GModelViewer'] 