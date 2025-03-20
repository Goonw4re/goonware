#!/usr/bin/env python3
"""
GMODEL Viewer - A standalone application for viewing GMODEL files (.gmodel)
"""

import os
import sys
import argparse
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    """Main entry point for the GMODEL Viewer"""
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description="GMODEL Viewer")
    parser.add_argument("file", nargs="?", help="Path to a .gmodel file to open")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set logging level based on debug flag
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Make sure we can import the viewer
    try:
        from .viewer import GModelViewer
    except ImportError:
        # We might be running the script directly
        # Add the parent directory to the path
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        # Try importing again
        try:
            from file_viewer.viewer import GModelViewer
        except ImportError:
            logger.error("Could not import the GModelViewer. Make sure you're running from the correct directory.")
            sys.exit(1)
    
    # Check if a file was specified
    file_path = None
    if args.file:
        file_path = os.path.abspath(args.file)
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            sys.exit(1)
        
        # Check if it's a .gmodel or .zip file
        if not file_path.lower().endswith(('.gmodel', '.zip')):
            logger.error(f"Unsupported file type: {file_path}")
            sys.exit(1)
    
    # Create and launch the viewer
    logger.info(f"Launching GMODEL Viewer with file: {file_path}" if file_path else "Launching GMODEL Viewer")
    viewer = GModelViewer(file_path=file_path)

if __name__ == "__main__":
    main() 