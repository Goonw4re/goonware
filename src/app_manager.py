import os
import sys
import logging
import signal
import atexit
import traceback
import keyboard
import win32api
import win32con
import win32gui
import tkinter as tk
import threading
import time

logger = logging.getLogger(__name__)

class AppManager:
    def __init__(self, models_dir):
        self.models_dir = models_dir
        self.is_running = False
        self._window_positioned = False
        self.selected_zips = set()
        self.panic_hotkey = None
        self.current_panic_key = None  # Track the current panic key
        
        # Initialize Tkinter root
        self.root = tk.Tk()
        self.root.withdraw()
        
        # Set up cleanup handlers
        atexit.register(self.cleanup)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def set_panic_key(self, key, callback):
        """Set the panic key hotkey"""
        try:
            logger.info(f"Setting panic key to '{key}'")
            
            # Unbind any existing panic key first
            try:
                if hasattr(self.root, 'panic_key') and self.root.panic_key:
                    self.root.unbind(f'<KeyPress-{self.root.panic_key}>')
                    self.root.unbind_all(f'<KeyPress-{self.root.panic_key}>')
                    self.root.unbind(f'<KeyRelease-{self.root.panic_key}>')
                    self.root.unbind_all(f'<KeyRelease-{self.root.panic_key}>')
                    logger.info(f"Unbound previous panic key: {self.root.panic_key}")
            except Exception as e:
                logger.error(f"Error unbinding previous panic key: {e}")
            
            # Store the key
            self.root.panic_key = key
            
            # Initialize double-press detection variables
            self.last_panic_press_time = 0
            self.panic_press_count = 0
            self.last_key_event_id = None  # Track event ID to prevent double triggering
            self.reset_timer_id = None  # Track the reset timer
            
            # Create a wrapper function that implements double-press detection
            def panic_key_wrapper(event=None):
                # CRITICAL FIX: Prevent the same physical key press from triggering multiple events
                current_time = time.time()
                
                # If this is an event, check if it's a duplicate
                if event:
                    # Generate a unique ID for this event
                    event_id = f"{event.serial}-{event.time}"
                    
                    # If we've seen this event or one very close in time, ignore it
                    if hasattr(self, 'last_key_event_id') and self.last_key_event_id:
                        if event_id == self.last_key_event_id:
                            logger.info(f"Ignoring duplicate key event: {event_id}")
                            return "break"
                        
                        # Also check if the event happened too close to the previous one
                        if current_time - self.last_panic_press_time < 0.05:  # 50ms debounce
                            logger.info(f"Ignoring key event too close to previous: {current_time - self.last_panic_press_time:.3f}s")
                            return "break"
                    
                    # Store this event ID
                    self.last_key_event_id = event_id
                
                # Update last press time
                self.last_panic_press_time = current_time
                
                # CRITICAL FIX: Check if UI is visible - if so, hide it with a single press
                ui_visible = False
                try:
                    if hasattr(self.root, 'state'):
                        state = self.root.state()
                        ui_visible = state in ('normal', 'zoomed')
                        logger.info(f"UI visibility check: state='{state}', is_visible={ui_visible}")
                except Exception as e:
                    logger.error(f"Error checking UI visibility: {e}")
                
                if ui_visible:
                    logger.info("UI is visible, hiding with single press")
                    try:
                        # Call the callback to close popups
                        result, popups_closed = callback(event, show_ui=False, hide_ui=True)
                        return result
                    except Exception as e:
                        logger.error(f"Error in panic key callback (hide UI): {e}")
                        return "break" if event else None
                
                # CRITICAL FIX: Cancel any existing reset timer
                if hasattr(self, 'reset_timer_id') and self.reset_timer_id:
                    try:
                        self.root.after_cancel(self.reset_timer_id)
                        self.reset_timer_id = None
                    except Exception as e:
                        logger.error(f"Error canceling reset timer: {e}")
                
                # When the panic key is pressed, only close popups, never show UI
                try:
                    logger.info("Panic key pressed: Closing popups only")
                    # Call the callback to close popups
                    result, popups_closed = callback(event, show_ui=False, hide_ui=False)
                    return result
                except Exception as e:
                    logger.error(f"Error in panic key callback: {e}")
                    return "break" if event else None
            
            # Only bind to KeyPress to prevent double triggering
            # Bind to KeyPress event on root window
            self.root.bind(f'<KeyPress-{key}>', panic_key_wrapper)
            
            # Bind to all windows using bind_all
            self.root.bind_all(f'<KeyPress-{key}>', panic_key_wrapper)
            
            # Use keyboard module as a fallback for global hotkey
            try:
                # Remove any existing hotkey
                if hasattr(self, 'panic_hotkey') and self.panic_hotkey:
                    try:
                        keyboard.remove_hotkey(self.panic_hotkey)
                    except:
                        pass
                
                # Add global hotkey that works even when app doesn't have focus
                self.panic_hotkey = keyboard.add_hotkey(key, panic_key_wrapper, suppress=False)
                logger.info(f"Added global hotkey for panic key '{key}'")
            except Exception as e:
                logger.error(f"Error setting up global hotkey: {e}")
            
            # Bind to all toplevel windows that might be created
            def bind_to_new_toplevel(event):
                try:
                    if event.widget.winfo_class() == 'Toplevel':
                        event.widget.bind(f'<KeyPress-{key}>', panic_key_wrapper)
                        logger.info(f"Bound panic key to new toplevel window")
                except:
                    pass
            
            # Bind to toplevel creation events
            self.root.bind_all('<Map>', bind_to_new_toplevel)
            
            logger.info(f"Panic key set to '{key}' successfully")
            return True
        
        except Exception as e:
            logger.error(f"Error setting panic key: {e}")
            return False

    def _convert_key_for_binding(self, key):
        """Convert key string to Tkinter binding format"""
        try:
            # Special key conversions
            key_map = {
                'space': 'space',
                'enter': 'Return',
                'return': 'Return',
                'tab': 'Tab',
                'escape': 'Escape',
                'esc': 'Escape',
                'backspace': 'BackSpace',
                'delete': 'Delete',
                'up': 'Up',
                'down': 'Down',
                'left': 'Left',
                'right': 'Right',
                'home': 'Home',
                'end': 'End',
                'page up': 'Prior',
                'page down': 'Next'
            }
            
            # Check if the key is in our map
            if key.lower() in key_map:
                return key_map[key.lower()]
            
            # If it's a function key (F1-F12)
            if key.lower().startswith('f') and key[1:].isdigit() and 1 <= int(key[1:]) <= 12:
                return key.upper()
            
            # For a single character, just return it
            if len(key) == 1:
                return key
                
            # If it's a combo key like Ctrl+C, convert each part
            if '+' in key:
                parts = key.split('+')
                modifiers = []
                for part in parts[:-1]:
                    part = part.lower().strip()
                    if part in ('ctrl', 'control'):
                        modifiers.append('Control')
                    elif part in ('alt', 'option'):
                        modifiers.append('Alt')
                    elif part in ('shift'):
                        modifiers.append('Shift')
                    else:
                        modifiers.append(part.capitalize())
                
                # Join with hyphen and add the key
                return '-'.join(modifiers + [self._convert_key_for_binding(parts[-1])])
            
            # Return the key capitalized for other cases
            return key.capitalize()
        except Exception as e:
            logger.error(f"Error converting key for binding: {e}")
            # Return the key unchanged
            return key

    def cleanup(self):
        """Clean up resources"""
        try:
            logger.info("Cleaning up resources...")
            
            # Set running flag to false
            self.is_running = False
            
            # CRITICAL FIX: Cancel any pending reset timer
            if hasattr(self, 'reset_timer_id') and self.reset_timer_id:
                try:
                    self.root.after_cancel(self.reset_timer_id)
                    self.reset_timer_id = None
                    logger.info("Canceled pending reset timer")
                except Exception as e:
                    logger.error(f"Error canceling reset timer: {e}")
            
            # Remove panic key hotkey
            if self.panic_hotkey:
                try:
                    keyboard.remove_hotkey(self.panic_hotkey)
                    logger.info("Removed panic key hotkey")
                except Exception as e:
                    logger.error(f"Error removing panic key hotkey: {e}")
            
            # Destroy root window last
            if hasattr(self, 'root') and self.root:
                try:
                    self.root.quit()
                    self.root.destroy()
                    logger.info("Root window destroyed")
                except Exception as e:
                    logger.error(f"Error destroying root window: {e}")
            
            logger.info("Cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}\n{traceback.format_exc()}")

    def _signal_handler(self, signum, frame):
        """Handle system signals"""
        logger.info(f"Received signal {signum}")
        self.cleanup() 