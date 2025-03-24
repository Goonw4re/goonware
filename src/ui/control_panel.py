import tkinter as tk
from tkinter import ttk
import random
import logging
import traceback
import time

logger = logging.getLogger(__name__)

from .styles import configure_styles
from .components.media_files_panel import MediaFilesPanel
from .components.display_settings_panel import DisplaySettingsPanel
from .components.panic_key_panel import PanicKeyPanel
from .components.title_bar import TitleBar

class ControlPanel:
    def __init__(self, root, models_dir, on_zip_change, on_toggle, on_panic, on_refresh=None):
        try:
            logger.info("Initializing ControlPanel...")
            
            # Configure window
            self.frame = ttk.Frame(root, padding="0")  # Remove padding to eliminate border
            self.frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            
            # Store callbacks
            self.on_zip_change = on_zip_change
            self.on_toggle = on_toggle
            self.on_panic = on_panic
            self.on_refresh = on_refresh
            
            # Flag to prevent multiple refreshes
            self._refresh_in_progress = False
            self._last_window_shown_time = 0  # Add timestamp to track last window shown event
            
            # Remove window decorations and set fixed size
            root.overrideredirect(True)
            root.geometry("397x705")  # Reduced height to match more compact panic key panel
            root.resizable(False, False)  # Prevent resizing
            
            # Initialize variables
            self.interval = tk.DoubleVar(value=0.1)
            self.max_popups = tk.IntVar(value=25)
            self.popup_probability = tk.IntVar(value=5)
            
            # Import UI components only when needed
            try:
                from .styles import configure_styles
                from .components.media_files_panel import MediaFilesPanel
                from .components.display_settings_panel import DisplaySettingsPanel
                from .components.panic_key_panel import PanicKeyPanel
                from .components.title_bar import TitleBar
                
                logger.info("Successfully imported UI components")
            except ImportError as e:
                logger.error(f"Failed to import UI components: {e}\n{traceback.format_exc()}")
                raise
            
            # Configure modern styles
            configure_styles()
            
            # Create main content frame with padding
            self.content_frame = ttk.Frame(self.frame, style='Modern.TFrame', padding="10")  # Reduced padding
            self.content_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            
            # Add title bar
            self.title_bar = TitleBar(self.frame, root)
            self.title_bar.grid(row=0, column=0, sticky=(tk.W, tk.E))
            
            # Create UI components
            self.media_panel = MediaFilesPanel(
                self.content_frame,
                models_dir,
                on_zip_change,
                self._safe_refresh  # Use safe refresh wrapper
            )
            self.media_panel.grid(
                row=0,
                column=0,
                sticky=(tk.W, tk.E, tk.N, tk.S),
                pady=(0, 5)  # Reduced spacing between panels
            )
            
            self.settings_panel = DisplaySettingsPanel(
                self.content_frame,
                self.interval,
                self.max_popups,
                self.popup_probability,
                on_toggle,
                on_panic
            )
            self.settings_panel.grid(
                row=1,
                column=0,
                sticky=(tk.W, tk.E, tk.N, tk.S),
                pady=(0, 5)  # Reduced spacing between panels
            )
            
            # Add the new panic key panel
            self.panic_key_panel = PanicKeyPanel(
                self.content_frame,
                on_panic
            )
            self.panic_key_panel.grid(
                row=2,
                column=0,
                sticky=(tk.W, tk.E, tk.N, tk.S),
                pady=(0, 5)  # Reduced spacing between panels
            )
            
            # Configure grid weights
            self.frame.grid_columnconfigure(0, weight=1)
            self.content_frame.grid_columnconfigure(0, weight=1)
            
            # Bind window events
            root.bind('<Escape>', lambda e: root.withdraw())  # Hide window on Escape
            root.bind('<Map>', self._on_window_shown)  # Refresh when window is shown
            
            # Center window on screen
            self._center_window(root)
            
            logger.info("ControlPanel initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing ControlPanel: {e}\n{traceback.format_exc()}")
            raise
    
    def _safe_refresh(self):
        """Safe wrapper for refresh callback to prevent infinite loops"""
        if self.on_refresh and not self._refresh_in_progress:
            try:
                self._refresh_in_progress = True
                self.on_refresh()
            finally:
                # Reset flag after a short delay to prevent rapid successive calls
                if hasattr(self.frame, 'after'):
                    self.frame.after(500, self._reset_refresh_flag)
    
    def _reset_refresh_flag(self):
        """Reset the refresh in progress flag"""
        self._refresh_in_progress = False
        logger.debug("Refresh flag reset")
    
    def _center_window(self, window):
        """Center the window on the screen"""
        try:
            window.update_idletasks()
            width = window.winfo_width()
            height = window.winfo_height()
            
            # Get screen dimensions
            screen_width = window.winfo_screenwidth()
            screen_height = window.winfo_screenheight()
            
            # Calculate centered position with clamping to ensure window stays on screen
            x = max(0, min((screen_width - width) // 2, screen_width - width))
            y = max(0, min((screen_height - height) // 2, screen_height - height))
            
            # Set position
            window.geometry(f"{width}x{height}+{x}+{y}")
            logger.info(f"Window centered at {x},{y} with size {width}x{height}")
            
            # Add protocol to check window position after any movement
            self._add_position_check(window)
        except Exception as e:
            logger.error(f"Error centering window: {e}\n{traceback.format_exc()}")
    
    def _add_position_check(self, window):
        """Add a periodic check to ensure window stays on screen"""
        try:
            # Function to check and correct window position
            def check_window_position():
                if not window.winfo_exists():
                    return
                
                # Get current position and size
                x = window.winfo_x()
                y = window.winfo_y()
                width = window.winfo_width()
                height = window.winfo_height()
                
                # Get screen dimensions
                screen_width = window.winfo_screenwidth()
                screen_height = window.winfo_screenheight()
                
                # Check if window needs repositioning
                needs_reposition = False
                
                # Clamp x position
                new_x = max(0, min(x, screen_width - width))
                if new_x != x:
                    x = new_x
                    needs_reposition = True
                
                # Clamp y position
                new_y = max(0, min(y, screen_height - height))
                if new_y != y:
                    y = new_y
                    needs_reposition = True
                
                # Reposition if needed
                if needs_reposition:
                    window.geometry(f"+{x}+{y}")
                    logger.debug(f"Repositioned window to {x},{y}")
                
                # Schedule next check
                window.after(500, check_window_position)
            
            # Start the periodic check
            window.after(500, check_window_position)
            
        except Exception as e:
            logger.error(f"Error setting up position check: {e}\n{traceback.format_exc()}")

    def _set_popup_position(self, window):
        """Set the position of the popup window"""
        try:
            screen_width = window.winfo_screenwidth()
            screen_height = window.winfo_screenheight()
            x = random.randint(0, screen_width - 400)  # Spawn closer to edges
            y = random.randint(0, screen_height - 400)  # Spawn closer to edges
            window.overrideredirect(True)  # Remove borders
            window.geometry(f"400x400+{x}+{y}")
        except Exception as e:
            logger.error(f"Error setting popup position: {e}\n{traceback.format_exc()}")

    def update_zip_list(self, zip_files):
        """Update the list of available zip files"""
        try:
            if hasattr(self, 'media_panel'):
                self.media_panel.update_file_list(zip_files)
        except Exception as e:
            logger.error(f"Error updating zip list: {e}\n{traceback.format_exc()}")
    
    def set_running(self, is_running):
        """Update the running state in the UI"""
        try:
            if hasattr(self, 'settings_panel'):
                self.settings_panel.set_running(is_running)
        except Exception as e:
            logger.error(f"Error setting running state: {e}\n{traceback.format_exc()}")
    
    def get_interval(self):
        """Get the current interval value"""
        try:
            return self.interval.get()
        except Exception as e:
            logger.error(f"Error getting interval: {e}\n{traceback.format_exc()}")
            return 0.1
    
    def get_max_popups(self):
        """Get the current max popups value"""
        try:
            return self.max_popups.get()
        except Exception as e:
            logger.error(f"Error getting max popups: {e}\n{traceback.format_exc()}")
            return 25

    def get_popup_probability(self):
        """Get the current popup probability value"""
        try:
            return self.popup_probability.get()
        except Exception as e:
            logger.error(f"Error getting popup probability: {e}\n{traceback.format_exc()}")
            return 5

    def get_bounce_enabled(self):
        """Get the bounce enabled state"""
        try:
            if hasattr(self, 'settings_panel'):
                return self.settings_panel.get_bounce_enabled()
        except Exception as e:
            logger.error(f"Error getting bounce enabled: {e}\n{traceback.format_exc()}")
        return False

    def _on_window_shown(self, event=None):
        """Called when the window is shown/mapped"""
        try:
            # Debounce mechanism - only process if at least 1 second has passed since last event
            current_time = time.time()
            if current_time - self._last_window_shown_time < 1.0:
                return
                
            self._last_window_shown_time = current_time
            logger.info("Window shown event triggered")
            
            # Refresh the media files panel to ensure correct model selection
            if hasattr(self, 'media_panel') and not self._refresh_in_progress:
                self._refresh_in_progress = True
                
                # Use refresh_models instead of update_file_list
                if hasattr(self.media_panel, 'refresh_models'):
                    self.media_panel.refresh_models()
                elif hasattr(self.media_panel, 'update_file_list'):
                    # Fallback to old method if it exists
                    self.media_panel.update_file_list()
                else:
                    logger.warning("MediaFilesPanel has neither refresh_models nor update_file_list method")
                
                # Call refresh callback if available, but only once
                self._safe_refresh()
                
                # Reset flag after a delay
                if hasattr(self.frame, 'after'):
                    self.frame.after(500, self._reset_refresh_flag)
        except Exception as e:
            logger.error(f"Error handling window shown event: {e}\n{traceback.format_exc()}")
            self._refresh_in_progress = False
