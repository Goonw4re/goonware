#!/usr/bin/env python3
"""
GMODEL Viewer - Launcher script for the file viewer

This script provides a convenient way to launch the GMODEL Viewer
directly from the src directory. It handles importing the necessary
modules and starting the viewer with a specified file if provided.
"""

import os
import sys
import argparse
import logging
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def show_error_dialog(title, message):
    """Show an error dialog using tkinter if available, otherwise print to console"""
    try:
        import tkinter as tk
        from tkinter import messagebox
        
        root = tk.Tk()
        root.withdraw()  # Hide the root window
        messagebox.showerror(title, message)
        root.destroy()
    except ImportError:
        print(f"\n=== {title} ===")
        print(message)
        print("=" * (len(title) + 8))

def check_dependencies(install_deps):
    """Check if required dependencies are installed"""
    missing = []
    
    try:
        import tkinter
    except ImportError:
        missing.append("tkinter (usually included with Python)")
    
    try:
        import PIL
    except ImportError:
        missing.append("pillow")
        
    try:
        import cv2
    except ImportError:
        missing.append("opencv-python")
    
    try:
        import zipfile
    except ImportError:
        missing.append("zipfile (should be part of Python standard library)")
    
    # Optional dependencies
    try:
        import pygame
    except ImportError:
        logger.warning("pygame not available - audio playback will be disabled")
    
    if missing:
        error_msg = (
            f"The following dependencies are missing:\n"
            f"{', '.join(missing)}\n\n"
            f"Please install them using:\n"
            f"pip install -r assets/requirements.txt"
        )
        show_error_dialog("Missing Dependencies", error_msg)
        return False
    
    return True

def main():
    """Main function to launch the viewer"""
    parser = argparse.ArgumentParser(description='GMODEL Viewer')
    parser.add_argument('file', nargs='?', help='GMODEL file to open')
    parser.add_argument('--install-deps', action='store_true', help='Automatically install missing dependencies')
    args = parser.parse_args()
    
    # Check for dependencies
    check_dependencies(args.install_deps)
    
    try:
        # Import the viewer (only after checking dependencies)
        from file_viewer.viewer import GModelViewer
        
        # Create the viewer
        if args.file:
            # Validate file path
            file_path = os.path.abspath(args.file)
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                print(f"Error: File not found: {file_path}")
                return 1
                
            # Validate file extension
            if not file_path.lower().endswith('.gmodel'):
                logger.error(f"Invalid file extension: {file_path}")
                print(f"Error: File must have .gmodel extension: {file_path}")
                return 1
                
            # Open the viewer with the file
            logger.info(f"Opening file: {file_path}")
            viewer = GModelViewer(file_path=file_path)
        else:
            # Open the viewer without a file
            viewer = GModelViewer()
            
        # This will enter the Tkinter main loop and block until the window is closed
        return 0
    except Exception as e:
        logger.error(f"Error launching viewer: {e}")
        logger.error(traceback.format_exc())
        show_error_dialog("Error launching viewer", str(e))
        return 1

if __name__ == "__main__":
    sys.exit(main())
