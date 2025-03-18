import os
import logging
import threading
import pystray
from PIL import Image
import tkinter as tk

logger = logging.getLogger(__name__)

class TrayManager:
    def __init__(self, root, app, icon_path=None):
        self.root = root
        self.app = app
        self.icon_path = icon_path or os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'icon.png')
        self.icon = None
        self.tray_thread = None
        self.stop_event = threading.Event()

    def create_menu(self):
        """Create the system tray menu with Show/Hide UI as the default action"""
        # The menu will be updated when the icon runs
        return pystray.Menu(
            # Set default=True to make Show/Hide UI the default action (will be bold)
            pystray.MenuItem('Show UI', self.toggle_ui, default=True),
            pystray.MenuItem('Exit', self.exit_app)
        )

    def toggle_ui(self, icon=None, item=None):
        """Toggle UI visibility when called from the tray icon"""
        try:
            # STABILITY FIX: Verify root exists
            if not hasattr(self, 'root') or not self.root:
                logger.error("Root window not available for UI toggle")
                return
                
            # STABILITY FIX: Handle possible Tkinter errors during state check
            is_visible = False
            try:
                # More robust visibility check
                if hasattr(self.root, 'winfo_exists') and self.root.winfo_exists():
                    if hasattr(self.root, 'winfo_viewable') and self.root.winfo_viewable():
                        is_visible = True
                    elif hasattr(self.root, 'state'):
                        state = self.root.state()
                        is_visible = state == 'normal' or state == 'zoomed'
                    else:
                        # Fallback for older Tkinter versions
                        is_visible = self.root.winfo_ismapped()
                logger.info(f"UI visibility check: is_visible={is_visible}")
            except Exception as e:
                logger.error(f"Error checking UI visibility: {e}")
                # Default to assuming it's not visible for safety
                is_visible = False
            
            # Toggle the UI
            if is_visible:
                # Hide UI
                logger.info("Hiding UI from tray icon")
                try:
                    self.root.withdraw()
                    # Process events to ensure UI is hidden
                    self.root.update_idletasks()
                except Exception as e:
                    logger.error(f"Error hiding UI: {e}")
                
                # Update menu text
                if icon and hasattr(icon, 'update_menu'):
                    logger.info("Updating menu text to 'Show UI'")
                    try:
                        self._update_menu_text(icon, 'Show UI')
                    except Exception as e:
                        logger.error(f"Error updating menu text: {e}")
            else:
                # Show UI - use Tkinter's after method to ensure thread safety
                logger.info("Showing UI from tray icon")
                try:
                    # First, make sure root still exists
                    if hasattr(self.root, 'winfo_exists') and self.root.winfo_exists():
                        self.root.after(0, self._show_ui_safely)
                    else:
                        logger.error("Cannot show UI - root window no longer exists")
                except Exception as e:
                    logger.error(f"Error scheduling UI show: {e}")
                
                # Update menu text
                if icon and hasattr(icon, 'update_menu'):
                    logger.info("Updating menu text to 'Hide UI'")
                    try:
                        self._update_menu_text(icon, 'Hide UI')
                    except Exception as e:
                        logger.error(f"Error updating menu text: {e}")
        except Exception as e:
            logger.error(f"Error toggling UI: {e}")
            # Fallback to just showing UI if possible
            try:
                if hasattr(self, 'root') and self.root and hasattr(self.root, 'after'):
                    self.root.after(0, self._show_ui_safely)
            except Exception as fallback_e:
                logger.error(f"Even fallback UI show failed: {fallback_e}")
                
    def _update_menu_text(self, icon, text):
        """Update the menu item text"""
        try:
            # Create updated menu
            new_menu = pystray.Menu(
                pystray.MenuItem(text, self.toggle_ui, default=True),
                pystray.MenuItem('Exit', self.exit_app)
            )
            # Update the icon's menu
            icon.menu = new_menu
            # Update the menu display
            if hasattr(icon, 'update_menu'):
                icon.update_menu()
        except Exception as e:
            logger.error(f"Failed to update menu text: {e}")

    def show_ui(self, icon=None, item=None):
        """Legacy method for backwards compatibility"""
        logger.info("Showing UI from tray icon (legacy method)")
        self.toggle_ui(icon, item)

    def _show_ui_safely(self):
        """Safely bring the UI to the front"""
        try:
            # STABILITY FIX: Check if root still exists
            if not hasattr(self, 'root') or not self.root or not hasattr(self.root, 'winfo_exists') or not self.root.winfo_exists():
                logger.error("Root window not available for showing UI")
                return
                
            # Show and bring to front
            self.root.deiconify()
            self.root.attributes('-topmost', True)
            self.root.focus_force()
            
            # Use app's show UI method if available
            if hasattr(self, 'app') and hasattr(self.app, '_show_ui_after_cleanup'):
                try:
                    self.app._show_ui_after_cleanup()
                except Exception as e:
                    logger.error(f"Error calling app's show UI method: {e}")
                    
            # Reset topmost after delay
            self.root.after(100, lambda: self.root.attributes('-topmost', False))
        except Exception as e:
            logger.error(f"Error showing UI safely: {e}")
            # Last resort attempt
            try:
                if hasattr(self, 'root') and self.root:
                    self.root.deiconify()
            except:
                pass

    def exit_app(self, icon=None, item=None):
        """Exit the application"""
        logger.info("Exiting application from tray")
        if self.icon:
            self.icon.stop()
        self.stop_event.set()
        self.root.after(0, self._exit_app_safely)

    def _exit_app_safely(self):
        try:
            self.root.quit()
            self.root.destroy()
        except Exception as e:
            logger.error(f"Error during exit: {e}")
            os._exit(0)

    def setup_icon(self):
        """Set up the system tray icon"""
        # STABILITY FIX: Validate inputs first
        if not hasattr(self, 'root') or not self.root:
            logger.error("Root window is not available, cannot set up icon")
            return False
            
        if not self.icon_path or not os.path.exists(self.icon_path):
            logger.error(f"Icon file not found: {self.icon_path}")
            # STABILITY FIX: Try to find alternative icon
            alt_paths = [
                os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'icon.png'),
                os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'icon.ico')
            ]
            for alt_path in alt_paths:
                if os.path.exists(alt_path):
                    logger.info(f"Using alternative icon: {alt_path}")
                    self.icon_path = alt_path
                    break
            else:
                logger.error("No icon file found at any expected location")
                return False

        # STABILITY FIX: Try multiple times if needed
        retry_count = 0
        max_retries = 2
        last_error = None
        
        while retry_count <= max_retries:
            try:
                logger.info(f"Loading icon from: {self.icon_path} (attempt {retry_count+1})")
                
                # Load image with error catching
                try:
                    icon_image = Image.open(self.icon_path)
                    # STABILITY FIX: Verify image loaded correctly
                    if not icon_image or not hasattr(icon_image, 'size'):
                        raise ValueError("Image loaded but appears invalid")
                    logger.info(f"Icon loaded successfully: {icon_image.format}, size: {icon_image.size}")
                except Exception as e:
                    logger.error(f"Error loading icon image: {e}")
                    retry_count += 1
                    last_error = e
                    if retry_count <= max_retries:
                        logger.info("Retrying image load after error...")
                        # Add a small delay before retry
                        import time
                        time.sleep(0.5)
                        continue
                    else:
                        return False
                
                # Create icon safely
                try:
                    # STABILITY FIX: Create a menu first and verify it works
                    menu = self.create_menu()
                    
                    # Create the icon
                    self.icon = pystray.Icon(
                        "Goonware",
                        icon_image,
                        "Goonware",  # Title/tooltip
                        menu=menu
                    )
                    
                    # Set the toggle_ui as the action for left-click
                    self.icon.on_activate = self.toggle_ui
                    
                    logger.info("Tray icon created successfully with UI toggle functionality")
                    return True
                except Exception as e:
                    logger.error(f"Error creating system tray icon: {e}")
                    retry_count += 1
                    last_error = e
                    if retry_count <= max_retries:
                        logger.info("Retrying icon creation after error...")
                        # Add a small delay before retry
                        import time
                        time.sleep(0.5)
                        continue
                    else:
                        return False
            except Exception as e:
                logger.error(f"Unexpected error in icon setup: {e}")
                retry_count += 1
                last_error = e
                if retry_count <= max_retries:
                    continue
                else:
                    return False
        
        # If we reach here, all retries failed
        logger.error(f"All attempts to create system tray icon failed. Last error: {last_error}")
        return False

    def start(self):
        """Start the system tray icon in a separate thread"""
        # STABILITY FIX: Check if already started
        if self.tray_thread and self.tray_thread.is_alive():
            logger.warning("Tray thread already running, not starting again")
            return True

        # Set up icon with retry mechanism
        icon_setup_successful = False
        retry_count = 0
        max_retries = 2
        
        while not icon_setup_successful and retry_count <= max_retries:
            logger.info(f"Setting up tray icon (attempt {retry_count+1})")
            icon_setup_successful = self.setup_icon()
            if not icon_setup_successful:
                retry_count += 1
                if retry_count <= max_retries:
                    logger.info("Retrying icon setup...")
                    # Add a small delay before retry
                    import time
                    time.sleep(0.5)
        
        if icon_setup_successful:
            # Create a new stop event if needed
            if self.stop_event.is_set():
                self.stop_event = threading.Event()
                
            # Create and start thread
            try:
                self.tray_thread = threading.Thread(target=self._run_icon, daemon=True)
                self.tray_thread.start()
                
                # STABILITY FIX: Verify thread started correctly
                if not self.tray_thread.is_alive():
                    logger.error("Tray thread created but not running")
                    return False
                    
                logger.info("Tray icon thread started successfully")
                return True
            except Exception as e:
                logger.error(f"Error starting tray thread: {e}")
                return False
        else:
            logger.error("Failed to set up system tray icon after multiple attempts")
            return False

    def _run_icon(self):
        """Run the tray icon"""
        try:
            logger.info("Starting tray icon")
            # STABILITY FIX: Verify icon is available
            if not self.icon:
                logger.error("Icon not available, cannot run")
                return
                
            # STABILITY FIX: Catch and log stop event
            try:
                # Check if we should stop before even starting
                if self.stop_event.is_set():
                    logger.info("Stop event set before icon started running")
                    return
                    
                # Run the icon with timeout monitoring
                logger.info("Running system tray icon")
                self.icon.run()
            except Exception as e:
                logger.error(f"Error while running tray icon: {e}", exc_info=True)
                # Try to restart if not explicitly stopped
                if not self.stop_event.is_set():
                    logger.info("Attempting automatic restart of tray icon")
                    try:
                        if self.icon:
                            self.icon.visible = True
                            self.icon.run()
                    except Exception as e2:
                        logger.error(f"Automatic restart failed: {e2}")
        except Exception as e:
            logger.error(f"Critical error in tray icon thread: {e}", exc_info=True)

    def stop(self):
        """Stop the system tray icon"""
        logger.info("Stopping tray icon")
        self.stop_event.set()
        if self.icon:
            self.icon.stop()
        if self.tray_thread and self.tray_thread.is_alive():
            self.tray_thread.join(timeout=1.0)
