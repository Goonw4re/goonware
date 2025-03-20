import logging
import tkinter as tk
import traceback

logger = logging.getLogger(__name__)

class UIManager:
    def __init__(self, root, models_dir, media_display, media_manager):
        self.root = root
        self.models_dir = models_dir
        self.media_display = media_display
        self.media_manager = media_manager
        self._window_positioned = False
        self.control_panel = None
        
        # Configure root window
        self.root.title("Goonware")
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        
        # Store media components in root for access by UI components
        if media_display:
            self.root.media_display = media_display
        if media_manager:
            self.root.media_manager = media_manager
        
    def init_ui(self, on_zip_change, toggle_display, handle_panic, refresh_media):
        """Initialize UI components"""
        try:
            logger.info("Initializing UI components...")
            
            # Ensure required modules are imported only when needed
            try:
                from ui.control_panel import ControlPanel
                logger.info("Successfully imported ControlPanel")
            except ImportError as e:
                logger.error(f"Failed to import ControlPanel: {e}")
                return False
            
            # Initialize control panel if not already done
            if not self.control_panel:
                try:
                    self.control_panel = ControlPanel(
                        self.root,
                        self.models_dir,
                        on_zip_change,
                        toggle_display,
                        handle_panic,
                        refresh_media
                    )
                    logger.info("Control panel initialized")
                except Exception as e:
                    logger.error(f"Error creating control panel: {e}\n{traceback.format_exc()}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error initializing UI: {e}\n{traceback.format_exc()}")
            return False

    def show(self):
        """Show the UI"""
        try:
            logger.info("Showing UI")
            
            # Always stop display regardless of running state
            if hasattr(self, 'media_display'):
                logger.info("Stopping media display before showing UI")
                # Force running flag to false to prevent any display activity
                self.media_display.running = False
                
                # Signal the display thread to exit
                if hasattr(self.media_display, 'display_event'):
                    self.media_display.display_event.set()
                    logger.info("Set display_event to signal thread exit")
                
                # Cancel any scheduled tasks
                if hasattr(self.root, 'tk'):
                    try:
                        # Get all after callbacks and cancel them
                        for after_id in self.root.tk.call('after', 'info'):
                            try:
                                self.root.after_cancel(after_id)
                                logger.debug(f"Canceled scheduled task: {after_id}")
                            except Exception as e:
                                logger.error(f"Error canceling after task {after_id}: {e}")
                        logger.info("Canceled all scheduled tasks")
                    except Exception as e:
                        logger.error(f"Error canceling scheduled tasks: {e}")
                
                # Stop animation threads if they exist
                if hasattr(self.media_display, 'animation_manager'):
                    try:
                        logger.info("Stopping animation thread in UI show")
                        self.media_display.animation_manager.stop_bounce_thread()
                    except Exception as e:
                        logger.error(f"Error stopping animation thread in UI show: {e}")
                
                # Force close any remaining windows
                try:
                    logger.info("Force closing windows in UI show")
                    self.media_display.force_close_all()
                except Exception as e:
                    logger.error(f"Error closing windows in UI show: {e}")
                
                # Process events to ensure windows are closed
                try:
                    self.root.update_idletasks()
                except Exception as e:
                    logger.error(f"Error updating root: {e}")
            else:
                logger.info("Media display not available, nothing to stop")
            
            # Show the UI
            try:
                self.root.deiconify()
                self.root.attributes('-topmost', True)
                self.root.focus_force()
                
                # Update UI state if control panel exists
                if hasattr(self, 'control_panel') and self.control_panel:
                    # Check if media display is actually running and reflect it in the UI
                    is_running = False
                    if hasattr(self, 'media_display') and hasattr(self.media_display, 'running'):
                        is_running = self.media_display.running
                        logger.info(f"Setting UI running state to match media_display.running: {is_running}")
                    self.set_running(is_running)
                
                # Reset topmost after a short delay
                self.root.after(100, lambda: self.root.attributes('-topmost', False))
                
                logger.info("UI shown successfully")
            except Exception as e:
                logger.error(f"Error showing UI: {e}")
        except Exception as e:
            logger.error(f"Error in show method: {e}\n{traceback.format_exc()}")
    
    def _recreate_window(self):
        """Last resort method to recreate the window if it can't be shown"""
        try:
            logger.info("Attempting to recreate window...")
            
            # Store old window state
            old_geometry = self.root.geometry()
            
            # Reset window state
            self.root.withdraw()
            self._window_positioned = False
            
            # Position and show window
            self._position_window()
            self.root.deiconify()
            self.root.update_idletasks()
            
            logger.info("Window recreated successfully")
        except Exception as e:
            logger.error(f"Error recreating window: {e}\n{traceback.format_exc()}")
            
    def hide(self):
        """Hide the UI window"""
        try:
            logger.info("Hiding UI window...")
            self.root.withdraw()
            logger.info("UI window hidden")
        except Exception as e:
            logger.error(f"Error hiding UI: {e}\n{traceback.format_exc()}")

    def _position_window(self):
        """Position the window on screen"""
        try:
            # Get screen dimensions
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            
            # Set window size
            window_width = 397
            window_height = 635
            
            # Calculate center position
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            
            # Set window size and position
            self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
            
            # Prevent resizing
            self.root.resizable(False, False)
            
            # Ensure window is visible
            self.root.update_idletasks()
            
            # Mark as positioned
            self._window_positioned = True
            
            logger.info(f"Window positioned at {x},{y} with size {window_width}x{window_height}")
            
        except Exception as e:
            logger.error(f"Error positioning window: {e}\n{traceback.format_exc()}")
            # Try a simpler approach as fallback
            try:
                self.root.geometry("440x680+100+100")
                self._window_positioned = True
                logger.info("Used fallback window positioning")
            except Exception as e2:
                logger.error(f"Error in fallback window positioning: {e2}")

    def get_bounce_enabled(self):
        """Get bounce enabled setting from display settings panel"""
        if hasattr(self, 'display_settings_panel'):
            return self.display_settings_panel.get_bounce_enabled()
        return False

    def get_interval(self):
        """Get interval from control panel"""
        if self.control_panel:
            try:
                return self.control_panel.get_interval()
            except Exception as e:
                logger.error(f"Error getting interval: {e}")
        return 0.1

    def get_max_popups(self):
        """Get max popups from control panel"""
        if self.control_panel:
            try:
                return self.control_panel.get_max_popups()
            except Exception as e:
                logger.error(f"Error getting max popups: {e}")
        return 25

    def get_popup_probability(self):
        """Get popup probability from control panel"""
        if self.control_panel:
            try:
                return self.control_panel.get_popup_probability()
            except Exception as e:
                logger.error(f"Error getting popup probability: {e}")
        return 5

    def set_running(self, is_running):
        """Set running state in control panel"""
        if self.control_panel:
            try:
                self.control_panel.set_running(is_running)
            except Exception as e:
                logger.error(f"Error setting running state: {e}")

    def get_active_monitors(self):
        """Get active monitors from display settings panel"""
        if hasattr(self, 'display_settings_panel'):
            return self.display_settings_panel.get_active_monitors()
        return [0]  # Default to primary monitor if panel doesn't exist 

    def is_visible(self):
        """Check if the UI is visible"""
        try:
            # CRITICAL FIX: Check if root exists
            if not hasattr(self, 'root') or not self.root:
                logger.info("No root window exists, UI is not visible")
                return False
            
            # CRITICAL FIX: Check if root is destroyed
            try:
                if not self.root.winfo_exists():
                    logger.info("Root window doesn't exist, UI is not visible")
                    return False
            except tk.TclError:
                logger.info("Root window has been destroyed, UI is not visible")
                return False
                
            # Check window state - most reliable method
            try:
                state = self.root.state()
                # If state is 'normal' or 'zoomed', window is visible
                is_visible = state in ('normal', 'zoomed')
                logger.info(f"UI visibility check: state='{state}', is_visible={is_visible}")
                return is_visible
            except Exception as e:
                logger.error(f"Error checking window state: {e}")
                
                # Fallback method: check if window is mapped
                try:
                    is_viewable = bool(self.root.winfo_viewable())
                    logger.info(f"UI visibility fallback check: winfo_viewable={is_viewable}")
                    return is_viewable
                except Exception as e2:
                    logger.error(f"Error checking window viewable: {e2}")
                    
                    # Last resort: check if window exists and is not withdrawn
                    try:
                        exists = bool(self.root.winfo_exists())
                        withdrawn = self.root.winfo_ismapped() == 0
                        logger.info(f"UI visibility last resort check: exists={exists}, withdrawn={withdrawn}")
                        return exists and not withdrawn
                    except:
                        # Last resort: assume not visible if we can't check
                        logger.info("All visibility checks failed, assuming UI is not visible")
                        return False
        except Exception as e:
            logger.error(f"Error in is_visible: {e}")
            return False 