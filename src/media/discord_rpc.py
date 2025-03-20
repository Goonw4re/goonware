import os
import json
import logging
import threading
import time
from typing import Optional, List

logger = logging.getLogger(__name__)

class DiscordRPC:
    def __init__(self):
        self.running = False
        self.current_message = None
        self._update_thread = None
        
    def start(self):
        """Start the message update thread"""
        if self.running:
            return
            
        self.running = True
        self._update_thread = threading.Thread(target=self._update_loop)
        self._update_thread.daemon = True
        self._update_thread.start()
        logger.info("Discord message update thread started")
        
    def stop(self):
        """Stop the message update thread"""
        self.running = False
        if self._update_thread:
            self._update_thread.join(timeout=1.0)
        self.current_message = None
        logger.info("Discord message update thread stopped")
            
    def update_status(self, message: str):
        """Update current message"""
        if not message:
            return
            
        self.current_message = message
        logger.info(f"Updated current message: {message}")
            
    def _update_loop(self):
        """Message update loop"""
        while self.running:
            try:
                # Just sleep - we're only storing the message in memory
                time.sleep(30)
            except Exception as e:
                logger.error(f"Error in message update loop: {e}")
                time.sleep(5) 