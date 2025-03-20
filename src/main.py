import os
import sys
import logging
import traceback
import tkinter as tk
from instance_manager import InstanceManager
from app_manager import AppManager
from media_manager import MediaManager
from media.media_display import MediaDisplay
from ui_manager import UIManager
from tray_manager import TrayManager
import atexit
import signal
import winreg
import file_viewer  # Import the file_viewer module

# Set up logger
logger = logging.getLogger(__name__)

def setup_logging():
    """Set up logging configuration"""
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets')
    logs_dir = os.path.join(assets_dir, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(logs_dir, 'app.log')),
            logging.StreamHandler()
        ]
    )
    logger.info("Logging configured")
    return True

def register_file_associations():
    """Register .gmodel file associations in Windows"""
    try:
        logger.info("Registering .gmodel file associations")
        app_path = os.path.abspath(sys.executable)
        script_path = os.path.abspath(__file__)
        
        # Get the path to the assets folder for the icon
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets')
        icon_path = os.path.join(assets_dir, 'icon.ico')
        
        # If .ico doesn't exist but .png does, use the .png (Windows will handle it)
        if not os.path.exists(icon_path):
            icon_path = os.path.join(assets_dir, 'icon.png')
        
        # 1. Register the .gmodel extension
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.gmodel") as key:
            winreg.SetValue(key, "", winreg.REG_SZ, "GoonwareModel")
            
        # 2. Create file type
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\GoonwareModel") as key:
            winreg.SetValue(key, "", winreg.REG_SZ, "Goonware Model File")
            
            # Set icon
            if os.path.exists(icon_path):
                with winreg.CreateKey(key, "DefaultIcon") as icon_key:
                    winreg.SetValue(icon_key, "", winreg.REG_SZ, icon_path)
            
            # Set open command - Updated to launch the file viewer directly
            with winreg.CreateKey(key, r"shell\open\command") as cmd_key:
                # This launches the Python interpreter with file_viewer.py and the clicked model file
                file_viewer_path = os.path.join(os.path.dirname(script_path), "file_viewer.py")
                cmd = f'"{app_path}" "{file_viewer_path}" "%1"'
                winreg.SetValue(cmd_key, "", winreg.REG_SZ, cmd)
                
            # Add a "View Contents" command in the right-click menu
            with winreg.CreateKey(key, r"shell\viewcontents") as view_key:
                winreg.SetValue(view_key, "", winreg.REG_SZ, "View Model Contents")
                
                # Add icon for the command
                if os.path.exists(icon_path):
                    winreg.SetValueEx(view_key, "Icon", 0, winreg.REG_SZ, icon_path)
                
                # Set the command
                with winreg.CreateKey(view_key, "command") as view_cmd_key:
                    file_viewer_path = os.path.join(os.path.dirname(script_path), "file_viewer.py")
                    cmd = f'"{app_path}" "{file_viewer_path}" "%1"'
                    winreg.SetValue(view_cmd_key, "", winreg.REG_SZ, cmd)
                
        # 3. Register the .gmodel extension with Explorer
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.gmodel") as key:
            with winreg.CreateKey(key, "UserChoice") as choice_key:
                winreg.SetValueEx(choice_key, "ProgId", 0, winreg.REG_SZ, "GoonwareModel")
        
        # 4. Notify the system about the change
        try:
            import ctypes
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
        except:
            pass
            
        logger.info("Successfully registered .gmodel file associations")
        return True
    except Exception as e:
        logger.error(f"Error registering file associations: {e}")
        return False

# Add a function to open the file viewer directly
def open_file_viewer(file_path):
    """Open the file viewer for a specific file"""
    try:
        logger.info(f"Opening file viewer for: {file_path}")
        # Create a new tkinter root
        root = tk.Tk()
        # Disable default window decorations since file_viewer uses custom title bar
        root.overrideredirect(True)
        
        # Create the viewer
        viewer = file_viewer.GModelViewer(root, file_path)
        
        # Center the window on screen
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        
        # Calculate centered position
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        # Apply position
        root.geometry(f"+{x}+{y}")
        
        # Start the application
        root.mainloop()
        return True
    except Exception as e:
        logger.error(f"Error opening file viewer: {e}")
        return False

class GoonwareApp:
    def __init__(self):
        logger.info("Initializing GoonwareApp")
        
        # Setup directories
        self.models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models')
        os.makedirs(self.models_dir, exist_ok=True)
        
        # Register file associations
        register_file_associations()
        
        # Initialize managers
        self.instance_manager = InstanceManager()
        
        # Start message listener for inter-process communication
        self.instance_manager.start_message_listener(self.handle_ipc_message)
        
        self.app_manager = AppManager(self.models_dir)
        
        # Set application title and icon for taskbar
        self.app_manager.root.title("GOONWARE")
        
        # Set app icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'icon.png')
        try:
            # Use PhotoImage for the window icon
            icon = tk.PhotoImage(file=icon_path)
            self.app_manager.root.iconphoto(True, icon)
            logger.info(f"Set application icon from {icon_path}")
        except Exception as e:
            logger.error(f"Error setting application icon: {e}")
        
        # Create media components
        self.media_manager = MediaManager(self.models_dir, auto_load=False)
        self.media_display = MediaDisplay(parent=self.app_manager.root)
        self.media_display.set_scale_factor(0.5)
        
        # Set flags
        self._refresh_in_progress = False
        
        # Get panic key from settings or use apostrophe as default
        settings = self.media_manager.get_display_settings()
        self.panic_key = settings.get('panic_key', "'")  # Default to apostrophe key
        logger.info(f"Using panic key from settings: {self.panic_key}")
        
        # Initialize UI
        self.ui_manager = UIManager(
            self.app_manager.root,
            self.models_dir,
            self.media_display,
            self.media_manager
        )
        
        # Configure root with properties
        self.app_manager.root.panic_key = self.panic_key
        self.app_manager.root.set_panic_key = self.set_panic_key
        self.app_manager.root.is_in_startup = self.is_in_startup
        self.app_manager.root.manage_startup = self.manage_startup
        
        # Initialize UI with callbacks
        self.ui_manager.init_ui(
            self.on_zip_change,
            self.toggle_display,
            self.handle_panic,
            self.refresh_media_paths
        )
        
        # Initialize system tray
        # Directly use the icon in assets folder
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'icon.png')
        logger.info(f"Using tray icon from: {icon_path}")
        
        self.tray_manager = TrayManager(
            self.app_manager.root,
            self,
            icon_path=icon_path
        )
    
    def run(self):
        """Run the application"""
        logger.info("Starting application")
        
        try:
            # Set panic key
            self.set_panic_key(self.panic_key)
            
            # Check and apply startup setting
            self._check_startup_setting()
            
            # STABILITY FIX: Process events to ensure UI is ready
            try:
                self.app_manager.root.update_idletasks()
            except Exception as e:
                logger.error(f"Error processing events during startup: {e}")
            
            # STABILITY FIX: Start system tray in try/except block
            tray_started = False
            try:
                logger.info("Starting system tray icon")
                tray_started = self.tray_manager.start()
                if not tray_started:
                    logger.warning("System tray failed to start on first attempt")
                    # Wait a moment and try one more time
                    self.app_manager.root.after(500, lambda: self.app_manager.root.update_idletasks())
                    tray_started = self.tray_manager.start()
                    
                logger.info(f"System tray icon started: {tray_started}")
            except Exception as e:
                logger.error(f"Error starting system tray: {e}")
                # Create fallback tray icon on failure
                try:
                    if not tray_started:
                        # Recreate the tray manager with a longer initialization delay
                        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'icon.png')
                        self.tray_manager = TrayManager(self.app_manager.root, self, icon_path=icon_path)
                        self.app_manager.root.after(1000, self.tray_manager.start)
                except Exception as e2:
                    logger.error(f"Error creating fallback tray: {e2}")
            
            # STABILITY FIX: Process events again to ensure UI is ready
            try:
                self.app_manager.root.update_idletasks()
            except Exception as e:
                logger.error(f"Error processing events after tray setup: {e}")
            
            # STABILITY FIX: Use a longer delay for showing UI to ensure components are ready
            self.app_manager.root.after(800, self._show_ui_with_retry)
            
            # STABILITY FIX: Set up periodic check to verify components
            self.app_manager.root.after(5000, self._verify_components)
            
            # Start main loop
            try:
                logger.info("Starting main event loop")
                self.app_manager.root.mainloop()
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                # Try to restart main loop
                try:
                    self.app_manager.root.destroy()
                    new_root = tk.Tk()
                    self.app_manager.root = new_root
                    self.app_manager.root.withdraw()
                    self.app_manager.root.mainloop()
                except Exception as e2:
                    logger.error(f"Could not restart main loop: {e2}")
                    
        except Exception as e:
            logger.error(f"Critical error during startup: {e}")
            self.cleanup()
    
    def _show_ui_with_retry(self):
        """Show UI with retry mechanism"""
        try:
            logger.info("Attempting to show UI with retry mechanism")
            try:
                # STABILITY FIX: Make sure window exists before showing
                if not self.app_manager.root.winfo_exists():
                    logger.error("Root window does not exist, can't show UI")
                    return
                
                # First try showing UI
                self.show_ui()
            except Exception as e:
                logger.error(f"Error showing UI, will retry: {e}")
                # Wait and retry
                self.app_manager.root.after(1000, self._retry_show_ui)
        except Exception as e:
            logger.error(f"Critical error in show UI with retry: {e}")
    
    def _retry_show_ui(self):
        """Retry showing UI after a failure"""
        try:
            logger.info("Retrying show UI")
            # Process events first
            self.app_manager.root.update_idletasks()
            # Try showing again
            self.app_manager.root.deiconify()
            self.app_manager.root.attributes('-topmost', True)
            self.app_manager.root.focus_force()
            self.app_manager.root.after(100, lambda: self.app_manager.root.attributes('-topmost', False))
            # Load models after additional delay
            self.app_manager.root.after(2000, self.load_models)
        except Exception as e:
            logger.error(f"Error in UI retry: {e}")
    
    def _verify_components(self):
        """Periodically verify components are working correctly"""
        try:
            # Check system tray
            if hasattr(self, 'tray_manager'):
                if not self.tray_manager.tray_thread or not self.tray_manager.tray_thread.is_alive():
                    logger.warning("Tray thread not alive, attempting restart")
                    try:
                        # Restart tray
                        self.tray_manager.stop()
                        self.app_manager.root.after(500, self.tray_manager.start)
                    except Exception as e:
                        logger.error(f"Error restarting tray: {e}")
            
            # Reschedule check
            self.app_manager.root.after(30000, self._verify_components)
        except Exception as e:
            logger.error(f"Error in component verification: {e}")
            # Reschedule anyway
            try:
                self.app_manager.root.after(30000, self._verify_components)
            except:
                pass
    
    def show_ui(self):
        """Show the UI"""
        try:
            self.app_manager.root.deiconify()
            self.app_manager.root.lift()
            self.app_manager.root.focus_force()
            self.ui_manager.show()
            
            # Load models after UI is shown
            self.app_manager.root.after(2000, self.load_models)
        except Exception as e:
            logger.error(f"Error showing UI: {e}")
            # Fallback method
            try:
                self.app_manager.root.update()
                self.app_manager.root.deiconify()
            except Exception as e2:
                logger.error(f"Fallback UI show failed: {e2}")
    
    def load_models(self):
        """Load models after UI is shown"""
        if not self._refresh_in_progress:
            self._refresh_in_progress = True
            self.media_manager.refresh_media_files()
            self.app_manager.root.after(1000, self._reset_refresh_flag)
    
    def _reset_refresh_flag(self):
        """Reset the refresh in progress flag"""
        self._refresh_in_progress = False
    
    def on_zip_change(self, zip_file, is_selected):
        """Handle zip file selection changes"""
        try:
            if is_selected:
                self.media_manager.load_zip(zip_file)
            else:
                self.media_manager.unload_zip(zip_file)
        except Exception as e:
            logger.error(f"Error handling zip change: {e}")
    
    def toggle_display(self):
        """Toggle display on/off"""
        try:
            # Check if display is running
            is_running = self.media_display.running if hasattr(self.media_display, 'running') else False
            
            if is_running:
                # Stop display
                self.media_display.stop()
                is_running = False
            else:
                # Start display
                # Get settings from UI
                interval = self.ui_manager.get_interval()
                max_popups = self.ui_manager.get_max_popups()
                popup_probability = self.ui_manager.get_popup_probability()
                bounce_enabled = self.ui_manager.get_bounce_enabled()
                
                # CRITICAL FIX: Get active monitors directly from settings
                # This ensures we use what was saved in the config
                active_monitors = None
                if hasattr(self, 'media_manager'):
                    settings = self.media_manager.get_display_settings()
                    active_monitors = settings.get('active_monitors', [0])
                    print(f"DEBUG MAIN: Got active_monitors from settings: {active_monitors}")
                
                # If not in settings, get from UI
                if not active_monitors:
                    active_monitors = self.ui_manager.get_active_monitors()
                
                print(f"DEBUG MAIN: Starting display with settings: interval={interval}, max_popups={max_popups}, probability={popup_probability}, bounce={bounce_enabled}, monitors={active_monitors}")
                
                # Check if we have any loaded zip files
                loaded_zips = self.media_manager.get_loaded_zips()
                if not loaded_zips:
                    import tkinter.messagebox as messagebox
                    messagebox.showwarning(
                        "No Models Selected",
                        "No models are selected. Please select at least one model in the Media Files panel."
                    )
                    return
                
                # Set selected zip files directly to media display before getting paths
                self.media_display.set_selected_zip_files(loaded_zips)
                
                # Start display with settings
                self.media_display.set_display_interval(interval)
                self.media_display.set_max_windows(max_popups)
                self.media_display.set_popup_duration(15)  # Default popup duration
                self.media_display.set_bounce_enabled(bounce_enabled)
                
                # Set active monitors - ensure this happens before starting display
                if active_monitors:
                    print(f"DEBUG MAIN: Setting active monitors to {active_monitors}")
                    self.media_display.set_active_monitors(active_monitors)
                    print(f"DEBUG MAIN: Active monitors set to {self.media_display.active_monitors}")
                else:
                    print("DEBUG MAIN: No active monitors selected, defaulting to primary")
                    self.media_display.set_active_monitors([0])
                
                # Refresh media paths directly
                self.media_display.refresh_media_paths()
                
                # Check if we have any media loaded
                if (not self.media_display.image_paths and 
                    not self.media_display.gif_paths and 
                    not self.media_display.video_paths):
                    logger.warning("No media files to display")
                    import tkinter.messagebox as messagebox
                    messagebox.showwarning(
                        "No Media Files",
                        "No media files could be loaded from the selected models."
                    )
                    return
                
                logger.info(f"Starting display with {len(self.media_display.image_paths)} images, {len(self.media_display.gif_paths)} GIFs, {len(self.media_display.video_paths)} videos")
                
                # Start the display
                self.media_display.start()
                
                # Hide the UI when starting the display
                self.app_manager.root.withdraw()
                is_running = True
            
            # Update UI
            self.ui_manager.set_running(is_running)
            
        except Exception as e:
            logger.error(f"Error toggling display: {e}")
            # Try to set UI to stopped state
            try:
                self.ui_manager.set_running(False)
            except:
                pass
            
            # Show error message
            try:
                import tkinter.messagebox as messagebox
                messagebox.showerror(
                    "Display Error",
                    f"Error toggling display: {str(e)}\nPlease check the logs for details."
                )
            except:
                pass
    
    def handle_panic(self, event=None, show_ui=None, hide_ui=None):
        """Handle panic button press"""
        try:
            logger.info(f"Panic button pressed (show_ui={show_ui}, hide_ui={hide_ui})")
            
            # Stop event propagation if this is an event
            if event:
                logger.info("Stopping event propagation")
                event.widget.focus_set()  # Set focus to ensure key event is captured
            
            # CRITICAL FIX: If hide_ui is explicitly set to True, hide the UI regardless of other parameters
            if hide_ui is True:
                logger.info("Explicit request to hide UI")
                try:
                    self.ui_manager.hide()
                except Exception as e:
                    logger.error(f"Error hiding UI: {e}")
                # Return a tuple with "break" and False (no popups closed)
                return ("break" if event else None, False)
            
            # If show_ui is explicitly set to False, only close popups without showing UI
            # OR if show_ui is set to True, we still only close popups (removing UI opening functionality)
            if show_ui is False or show_ui is True:
                logger.info("Panic key pressed: Closing popups only")
                # Close popups and get whether any were actually closed
                popups_were_closed = self._close_popups_only()
                logger.info(f"Popups were {'closed' if popups_were_closed else 'not closed'}")
                
                # Return a tuple with "break" and whether popups were running
                return ("break" if event else None, popups_were_closed)
            
            # Legacy behavior for direct calls without show_ui parameter
            # Check if UI is visible using a more reliable method
            ui_visible = False
            try:
                if hasattr(self, 'app_manager') and hasattr(self.app_manager, 'root'):
                    state = self.app_manager.root.state()
                    ui_visible = state in ('normal', 'zoomed')
                    logger.info(f"UI visibility check: state='{state}', is_visible={ui_visible}")
            except Exception as e:
                logger.error(f"Error checking UI visibility: {e}")
                # Fallback to ui_manager method
                ui_visible = self.ui_manager.is_visible()
                
            # If UI is visible, hide it
            if ui_visible:
                logger.info("UI is visible, hiding")
                try:
                    self.ui_manager.hide()
                except Exception as e:
                    logger.error(f"Error hiding UI: {e}")
                # Return a tuple with "break" and False (no popups closed)
                return ("break" if event else None, False)
            
            # UI is not visible, close popups only
            logger.info("UI is not visible, closing popups only")
            popups_were_closed = self._close_popups_only()
            logger.info(f"Popups were {'closed' if popups_were_closed else 'not closed'}")
            
            # Return "break" to prevent event propagation if this is an event
            return ("break" if event else None, popups_were_closed)
            
        except Exception as e:
            logger.error(f"Error in panic button handler: {e}")
            # Return a tuple with "break" and False (error occurred)
            return ("break" if event else None, False)
    
    def _close_popups_only(self):
        """Close all popups without showing UI"""
        try:
            logger.info("Closing all popups without showing UI")
            
            # CRITICAL FIX: Do NOT cancel the reset timer or reset the press count
            # This allows the double-press detection to work properly
            
            # Check if display is running before stopping it
            is_running = False
            popups_were_closed = False
            
            if hasattr(self, 'media_display'):
                is_running = self.media_display.running
                
                # Check if there are any windows open before closing
                window_count_before = 0
                if hasattr(self.media_display, 'window_manager'):
                    if hasattr(self.media_display.window_manager, 'current_windows'):
                        window_count_before += len(self.media_display.window_manager.current_windows)
                    if hasattr(self.media_display.window_manager, 'gif_windows'):
                        window_count_before += len(self.media_display.window_manager.gif_windows)
                    if hasattr(self.media_display.window_manager, 'video_windows'):
                        window_count_before += len(self.media_display.window_manager.video_windows)
                
                logger.info(f"Found {window_count_before} windows before cleanup")
                popups_were_closed = window_count_before > 0 or is_running
            
            # CRITICAL FIX: Always force stop display regardless of running state
            if hasattr(self, 'media_display'):
                logger.info("Stopping media display regardless of running state")
                try:
                    # CRITICAL FIX: Stop update logic first by setting running flag to false
                    logger.info("Setting running flag to false to stop update logic")
                    self.media_display.running = False
                    
                    # CRITICAL FIX: Set display_event to signal the display thread to exit
                    if hasattr(self.media_display, 'display_event'):
                        self.media_display.display_event.set()
                        logger.info("Set display_event to signal thread exit")
                    
                    # CRITICAL FIX: Wait for a small amount of time to ensure update logic has stopped
                    self.app_manager.root.after(50, lambda: self.app_manager.root.update_idletasks())
                    
                    # CRITICAL FIX: Stop animation thread first to prevent new window updates
                    if hasattr(self.media_display, 'animation_manager'):
                        logger.info("Stopping animation thread")
                        self.media_display.animation_manager.stop_bounce_thread()
                        # Wait for thread to stop
                        self.app_manager.root.after(50, lambda: self.app_manager.root.update_idletasks())
                    
                    # CRITICAL FIX: Cancel any scheduled window creations
                    if hasattr(self.app_manager, 'root'):
                        # Get all after callbacks and cancel them
                        try:
                            for after_id in self.app_manager.root.tk.call('after', 'info'):
                                try:
                                    self.app_manager.root.after_cancel(after_id)
                                    logger.info(f"Canceled scheduled task: {after_id}")
                                except Exception as e:
                                    logger.error(f"Error canceling after task {after_id}: {e}")
                            logger.info("Canceled all scheduled tasks")
                        except Exception as e:
                            logger.error(f"Error canceling scheduled tasks: {e}")
                    
                    # CRITICAL FIX: Force close all windows directly on window_manager
                    if hasattr(self.media_display, 'window_manager'):
                        logger.info("Calling force_close_all directly on window_manager")
                        self.media_display.window_manager.force_close_all()
                    
                    # CRITICAL FIX: Process events to ensure windows are closed
                    self.app_manager.root.update_idletasks()
                    
                    # Also call on media_display as a backup
                    logger.info("Calling force_close_all on media_display")
                    self.media_display.force_close_all()
                    
                    # Process events again
                    self.app_manager.root.update_idletasks()
                    
                    # Fully stop the display with all cleanup
                    logger.info("Stopping media display")
                    self.media_display.stop()
                    
                    # Process events one more time
                    self.app_manager.root.update_idletasks()
                        
                    # Reset counter to ensure no windows are tracked
                    self.media_display.currently_displayed = 0
                    
                    
                    # CRITICAL FIX: Verify all windows are closed
                    if hasattr(self.media_display, 'window_manager'):
                        window_count = 0
                        if hasattr(self.media_display.window_manager, 'current_windows'):
                            window_count += len(self.media_display.window_manager.current_windows)
                        if hasattr(self.media_display.window_manager, 'gif_windows'):
                            window_count += len(self.media_display.window_manager.gif_windows)
                        if hasattr(self.media_display.window_manager, 'video_windows'):
                            window_count += len(self.media_display.window_manager.video_windows)
                        
                        if window_count > 0:
                            logger.warning(f"Still have {window_count} windows after cleanup, forcing close again")
                            # Try one more time with direct window destruction
                            try:
                                self.media_display.window_manager.force_close_all()
                                self.app_manager.root.update_idletasks()
                            except Exception as e:
                                logger.error(f"Error in final window cleanup: {e}")
                except Exception as e:
                    logger.error(f"Error stopping display in panic: {e}")
            else:
                logger.info("Media display not found, nothing to stop")
                
            # Return whether popups were actually closed
            return popups_were_closed
        except Exception as e:
            logger.error(f"Error in _close_popups_only: {e}")
            return False
    
    def _show_ui_after_cleanup(self):
        """Show UI after cleaning up popups"""
        try:
            # First close all popups
            popups_were_closed = self._close_popups_only()
            logger.info(f"Popups were {'closed' if popups_were_closed else 'not closed'} before showing UI")
            
            # Then show UI
            logger.info("Showing UI after cleanup")
            try:
                # Make sure display is fully stopped if it was running
                if hasattr(self, 'media_display'):
                    self.media_display.running = False
                    # CRITICAL FIX: Set prevent_new_popups flag to prevent any new popups
                    self.media_display.prevent_new_popups = True
                
                # CRITICAL FIX: Force UI to be visible
                self.app_manager.root.deiconify()
                self.app_manager.root.attributes('-topmost', True)
                self.app_manager.root.focus_force()
                
                # Update UI state
                self.ui_manager.set_running(False)
                
                # Show UI
                self.ui_manager.show()
                
                # CRITICAL FIX: Process events to ensure UI is shown
                self.app_manager.root.update_idletasks()
                
                # Reset topmost after a short delay
                self.app_manager.root.after(100, lambda: self.app_manager.root.attributes('-topmost', False))
            except Exception as e:
                logger.error(f"Error showing UI: {e}")
                # Fallback to after_idle method
                self.app_manager.root.after_idle(self._show_ui_safely)
        except Exception as e:
            logger.error(f"Error in _show_ui_after_cleanup: {e}")
    
    def _show_ui_safely(self):
        """Helper method to show UI safely after cleanup"""
        try:
            logger.info("Showing UI safely after cleanup")
            
            # Only stop display if it's actually running
            if hasattr(self, 'media_display') and self.media_display.running:
                logger.info("Media display is running, stopping it")
                self.media_display.running = False
                self.media_display.force_close_all()
                self.media_display.stop()
            else:
                logger.info("Media display is not running, no need to stop it")
            
            # Now it's safe to show the UI
            logger.info("Showing UI")
            self.ui_manager.show()
            
        except Exception as e:
            logger.error(f"Error showing UI safely: {e}")
            # Last resort: try to show UI directly
            try:
                self.app_manager.root.deiconify()
                self.app_manager.root.attributes('-topmost', True)
                self.app_manager.root.focus_force()
                self.app_manager.root.after(100, lambda: self.app_manager.root.attributes('-topmost', False))
            except Exception as e2:
                logger.error(f"Last resort UI show failed: {e2}")
    
    def refresh_media_paths(self):
        """Refresh media paths"""
        if not self._refresh_in_progress:
            self._refresh_in_progress = True
            self.media_manager.refresh_media_files()
            self.app_manager.root.after(1000, self._reset_refresh_flag)
    
    def set_panic_key(self, key):
        """Set the panic key hotkey"""
        # IMPROVEMENT: Allow any key to be set as the panic key, not just apostrophe
        logger.info(f"Setting panic key to: {key}")
        self.panic_key = key
        
        # Set the panic key in app manager with proper callback
        success = self.app_manager.set_panic_key(key, self.handle_panic)
        
        # CRITICAL FIX: Only bind directly to KeyPress events, not KeyRelease
        try:
            # Unbind any existing bindings first
            try:
                self.app_manager.root.unbind_all(f'<KeyPress-{key}>')
            except:
                pass
                
            # Bind directly to root window for redundancy
            self.app_manager.root.bind_all(f'<KeyPress-{key}>', self.handle_panic)
            logger.info(f"Bound panic key '{key}' directly to root window")
        except Exception as e:
            logger.error(f"Error binding panic key directly: {e}")
        
        # Save in settings
        settings = self.media_manager.get_display_settings()
        settings['panic_key'] = key
        self.media_manager.update_display_settings(settings)
        
        return success
    
    def is_in_startup(self):
        """Check if application is set to run on Windows startup"""
        try:
            # Get the absolute path to start.bat in assets folder
            app_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'start.bat'))
            
            # Open the registry key for current user startup
            registry_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_READ
            )
            
            try:
                # Try to get the Goonware value
                value, _ = winreg.QueryValueEx(registry_key, "Goonware")
                winreg.CloseKey(registry_key)
                
                # Check if the paths match
                return value == f'"{app_path}"'
            except WindowsError:
                # Key doesn't exist
                winreg.CloseKey(registry_key)
                return False
                
        except Exception as e:
            logger.error(f"Error checking startup status: {e}")
            return False
    
    def manage_startup(self, enable):
        """Add or remove application from Windows startup"""
        try:
            # Get the absolute path to start.bat in assets folder
            app_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'start.bat'))
            
            # Open the registry key for current user startup
            registry_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE | winreg.KEY_READ
            )
            
            if enable:
                # Add to startup
                winreg.SetValueEx(registry_key, "Goonware", 0, winreg.REG_SZ, f'"{app_path}"')
                logger.info(f"Added application to startup: {app_path}")
            else:
                # Remove from startup
                try:
                    winreg.DeleteValue(registry_key, "Goonware")
                    logger.info("Removed application from startup")
                except WindowsError:
                    # Key doesn't exist, nothing to remove
                    pass
                    
            winreg.CloseKey(registry_key)
            return True
                
        except Exception as e:
            logger.error(f"Error managing startup: {e}")
            return False
    
    def _check_startup_setting(self):
        """Check and apply startup setting from config"""
        try:
            # Get startup setting from config
            settings = self.media_manager.get_display_settings()
            startup_enabled = bool(int(settings.get('startup_enabled', 0)))
            
            # Check current registry state
            registry_state = self.is_in_startup()
            
            # If there's a mismatch, apply the setting from config
            if startup_enabled != registry_state:
                logger.info(f"Applying startup setting: {startup_enabled}")
                self.manage_startup(startup_enabled)
        except Exception as e:
            logger.error(f"Error checking startup setting: {e}")
    
    def handle_ipc_message(self, message_type, message_data):
        """Handle messages from other instances"""
        try:
            logger.info(f"Handling IPC message: {message_type}, data: {message_data}")
            
            if message_type == "open_model":
                # Check if the file exists and has .gmodel extension
                if os.path.exists(message_data) and message_data.lower().endswith('.gmodel'):
                    # Show the UI first
                    self.app_manager.root.deiconify()
                    self.app_manager.root.lift()
                    self.app_manager.root.focus_force()
                    
                    # Schedule the file viewer to open
                    self.app_manager.root.after(500, lambda: open_file_viewer(message_data))
                    
                    # Also load the model into the app
                    if hasattr(self, 'media_manager'):
                        # May need to wait for UI to be ready
                        def load_model():
                            try:
                                self.media_manager.load_zip(message_data)
                                logger.info(f"Loaded model file from IPC message: {message_data}")
                            except Exception as e:
                                logger.error(f"Error loading model from IPC message: {e}")
                        
                        # Schedule loading after UI is ready
                        self.app_manager.root.after(1000, load_model)
                    else:
                        logger.warning("Cannot load model, media_manager not initialized")
                else:
                    logger.warning(f"Invalid model file path: {message_data}")
        except Exception as e:
            logger.error(f"Error handling IPC message: {e}")
    
    def cleanup(self):
        """Clean up resources"""
        try:
            # Stop message listener
            if hasattr(self, 'instance_manager'):
                try:
                    self.instance_manager.stop_message_listener()
                except:
                    pass
            
            # Stop system tray icon if it exists
            if hasattr(self, 'tray_manager'):
                try:
                    self.tray_manager.stop()
                except:
                    pass
            
            # Stop media display
            if hasattr(self, 'media_display'):
                try:
                    self.media_display.stop()
                except:
                    pass
            
            # Clean up app manager
            if hasattr(self, 'app_manager'):
                try:
                    self.app_manager.cleanup()
                except:
                    pass
            
            # Clean up instance manager
            if hasattr(self, 'instance_manager'):
                try:
                    if not self.instance_manager.cleanup():
                        self.instance_manager.force_cleanup()
                except:
                    # Direct removal as last resort
                    try:
                        lock_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'instance.lock')
                        if os.path.exists(lock_file):
                            os.remove(lock_file)
                    except:
                        pass
            
            # Exit the application
            if hasattr(self, 'app_manager') and hasattr(self.app_manager, 'root'):
                self.app_manager.root.quit()
                self.app_manager.root.destroy()
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            # Force exit but try to remove lock file first
            try:
                lock_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'instance.lock')
                if os.path.exists(lock_file):
                    os.remove(lock_file)
            except:
                pass
            import os
            os._exit(1)

def main():
    """Main entry point for the application"""
    try:
        # Set up logging
        setup_logging()
        
        # Initialize instance manager
        instance_manager = InstanceManager()
        
        # Handle command line arguments
        if len(sys.argv) > 1:
            if sys.argv[1] == '--check-instance':
                sys.exit(0 if instance_manager.check_instance() else 1)
            elif sys.argv[1] == '--show-ui':
                instance_manager.show_existing_window()
                sys.exit(0)
            elif sys.argv[1] == '--open-model':
                # Open a .gmodel file directly
                if len(sys.argv) > 2:
                    model_path = sys.argv[2]
                    if os.path.exists(model_path) and model_path.lower().endswith('.gmodel'):
                        logger.info(f"Opening model file: {model_path}")
                        # If another instance is running, tell it to open the file
                        if instance_manager.check_instance():
                            logger.info("Sending file open request to existing instance")
                            instance_manager.send_message(f"open_model:{model_path}")
                            sys.exit(0)
                        
                        # Launch file viewer directly instead of continuing app launch
                        open_file_viewer(model_path)
                        sys.exit(0)
                    else:
                        logger.error(f"Invalid model file: {model_path}")
                        sys.exit(1)
        
        # Check for existing instance
        if instance_manager.check_instance():
            logger.info("Another instance is already running")
            sys.exit(0)
            
        # Register cleanup on exit
        def cleanup_on_exit():
            try:
                if not instance_manager.cleanup():
                    instance_manager.force_cleanup()
            except:
                # Try direct removal
                try:
                    lock_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'instance.lock')
                    if os.path.exists(lock_file):
                        os.remove(lock_file)
                except:
                    pass
        
        atexit.register(cleanup_on_exit)
        
        # Register signal handlers
        def signal_handler(signum, frame):
            cleanup_on_exit()
            sys.exit(1)
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGBREAK'):  # Windows-specific
            signal.signal(signal.SIGBREAK, signal_handler)
        
        # Create and run the application
        app = GoonwareApp()
        
        # If we were launched to open a model file, tell the app to load it
        if len(sys.argv) > 2 and sys.argv[1] == '--open-model':
            model_path = sys.argv[2]
            if os.path.exists(model_path) and model_path.lower().endswith('.gmodel'):
                # Add this file to the loaded models
                if hasattr(app, 'media_manager'):
                    app.media_manager.load_zip(model_path)
                    logger.info(f"Added model file to loaded models: {model_path}")
        
        app.run()
        
    except Exception as e:
        logger.critical(f"Critical error: {e}\n{traceback.format_exc()}")
        # Show error window
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Error", f"Critical error: {e}")
        except:
            pass
        
        # Clean up lock file
        try:
            if 'instance_manager' in locals():
                if not instance_manager.cleanup():
                    instance_manager.force_cleanup()
        except:
            # Direct removal
            try:
                lock_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'instance.lock')
                if os.path.exists(lock_file):
                    os.remove(lock_file)
            except:
                pass
        sys.exit(1)

if __name__ == "__main__":
    main() 