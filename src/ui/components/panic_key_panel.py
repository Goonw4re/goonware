import tkinter as tk
from tkinter import ttk
import keyboard
import logging
import threading

logger = logging.getLogger(__name__)

class PanicKeyPanel:
    def __init__(self, parent, on_panic=None):
        self.frame = ttk.LabelFrame(
            parent,
            text="Panic Key Settings",
            padding="5",
            style='Modern.TLabelframe'
        )
        
        self.on_panic = on_panic
        self.is_listening_for_key = False
        
        # Configure styles for this panel
        style = ttk.Style()
        style.configure('Modern.TLabelframe.Label',
                       background='#1e1e1e',
                       foreground='white',
                       font=('Segoe UI', 11, 'bold'))
        
        style.configure('Modern.Accent.TButton',
                       background='#0078d4',
                       foreground='black')
                       
        style.map('Modern.TButton',
                  background=[('active', '#606060'), ('!disabled', '#444444')],
                  foreground=[('active', 'black'), ('!disabled', 'black')])
        
        # Load current panic key
        self.root = parent.winfo_toplevel()
        self.current_panic_key = "'"  # Default
        
        if hasattr(self.root, 'panic_key'):
            self.current_panic_key = self.root.panic_key
            logger.info(f"Using panic key from root: {self.current_panic_key}")
        elif hasattr(self.root, 'media_manager'):
            settings = self.root.media_manager.get_display_settings()
            self.current_panic_key = settings.get('panic_key', "'")
            logger.info(f"Loaded panic key from settings: {self.current_panic_key}")
            
        # Track if panic is temporarily disabled
        self.panic_disabled = False
        self.original_handle_panic = None
        self.disable_lock = threading.Lock()
        
        # Create the UI
        self._create_ui()
        
        # Set global flag on the root window to indicate panic disabled status
        if not hasattr(self.root, 'is_panic_disabled'):
            self.root.is_panic_disabled = False
        
    def _create_ui(self):
        """Create the panic key customization UI"""
        # Main container - reduce padding
        main_frame = ttk.Frame(self.frame, style='Modern.TFrame')
        main_frame.pack(fill='both', expand=True, padx=2, pady=2)
        
        # Current key section - keep only the essential elements
        ttk.Label(
            main_frame,
            text="Current Key:",
            style='Modern.TLabel'
        ).grid(row=0, column=0, sticky='w')
        
        self.key_label = ttk.Label(
            main_frame,
            text=self._format_key_display(self.current_panic_key),
            style='Modern.TLabel',
            font=('Segoe UI', 9, 'bold'),
            width=10
        )
        self.key_label.grid(row=0, column=1, sticky='w', padx=(5, 5))
        
        # Change button
        self.change_button = ttk.Button(
            main_frame,
            text="Change Key",
            command=self._completely_disable_panic_and_listen,
            style='Modern.TButton',
            width=10
        )
        self.change_button.grid(row=0, column=2, sticky='e')
        
        # Configure grid
        for i in range(3):
            main_frame.columnconfigure(i, weight=1)
    
    def _format_key_display(self, key):
        """Format key display to be more readable"""
        if key == "'":
            return "Apostrophe"
        elif key == '"':
            return "Double Quote"
        elif key == " ":
            return "Space"
        elif key == "Escape":
            return "Esc"
        elif key == "Return":
            return "Enter"
        else:
            return key.capitalize()
    
    def _completely_disable_panic_and_listen(self):
        """Completely disable all panic functionality before listening for a key"""
        if self.is_listening_for_key:
            return
            
        with self.disable_lock:
            # Set the flag to prevent panic actions
            self.panic_disabled = True
            # Set global flag on root window
            self.root.is_panic_disabled = True
            logger.info("Completely disabling panic functionality")
            
            # Save original panic handler
            if hasattr(self.root, 'handle_panic') and not self.original_handle_panic:
                self.original_handle_panic = self.root.handle_panic
                
                # Replace with dummy function that explicitly checks the disabled flag
                def dummy_handle_panic(*args, **kwargs):
                    logger.info("Panic function called but temporarily disabled")
                    return None
                    
                self.root.handle_panic = dummy_handle_panic
                logger.info("Replaced handle_panic with dummy function")
            
            # Save and replace any other panic handlers in the application
            self._disable_all_panic_handlers()
            
            # Unbind all keyboard shortcuts
            try:
                if hasattr(self.root, 'panic_key'):
                    key = self.root.panic_key
                    logger.info(f"Unbinding panic key: {key}")
                    
                    # Unbind from root and all children
                    for widget in [self.root] + list(self._get_all_children(self.root)):
                        try:
                            widget.unbind(f"<KeyPress-{key}>")
                            widget.unbind(f"<KeyRelease-{key}>")
                        except Exception as e:
                            logger.error(f"Error unbinding from widget: {e}")
                            
                    # Unbind from all bindtags
                    try:
                        self.root.unbind_all(f"<KeyPress-{key}>")
                        self.root.unbind_all(f"<KeyRelease-{key}>")
                    except Exception as e:
                        logger.error(f"Error unbinding from all: {e}")
                
                # Also remove global hotkey via keyboard module
                try:
                    if hasattr(self.root, 'app_manager') and hasattr(self.root.app_manager, 'panic_hotkey'):
                        keyboard.remove_hotkey(self.root.app_manager.panic_hotkey)
                        logger.info("Removed global panic hotkey")
                except Exception as e:
                    logger.error(f"Error removing global hotkey: {e}")
            except Exception as e:
                logger.error(f"Error disabling panic functionality: {e}")
            
            # Start listening
            self._start_listening_for_key()
    
    def _disable_all_panic_handlers(self):
        """Disable all possible panic handlers in the application"""
        # Save handlers in app_manager if it exists
        if hasattr(self.root, 'app_manager'):
            app_manager = self.root.app_manager
            if hasattr(app_manager, 'handle_panic') and not hasattr(self, 'original_app_manager_panic'):
                self.original_app_manager_panic = app_manager.handle_panic
                app_manager.handle_panic = lambda *args, **kwargs: logger.info("App manager panic handler disabled")
                logger.info("Disabled app_manager.handle_panic")
            
            # Disable global hotkey callbacks
            if hasattr(app_manager, 'panic_callback') and not hasattr(self, 'original_panic_callback'):
                self.original_panic_callback = app_manager.panic_callback
                app_manager.panic_callback = lambda *args, **kwargs: logger.info("Panic callback disabled")
                logger.info("Disabled app_manager.panic_callback")
        
        # Disable ui_manager panic handlers if they exist
        if hasattr(self.root, 'ui_manager'):
            ui_manager = self.root.ui_manager
            if hasattr(ui_manager, 'handle_panic') and not hasattr(self, 'original_ui_manager_panic'):
                self.original_ui_manager_panic = ui_manager.handle_panic
                ui_manager.handle_panic = lambda *args, **kwargs: logger.info("UI manager panic handler disabled")
                logger.info("Disabled ui_manager.handle_panic")
    
    def _get_all_children(self, widget):
        """Recursively get all children widgets"""
        children = widget.winfo_children()
        result = list(children)
        for child in children:
            result.extend(self._get_all_children(child))
        return result
    
    def _start_listening_for_key(self):
        """Start listening for a key press to set as panic key"""
        logger.info("Starting to listen for new panic key")
        self.is_listening_for_key = True
        
        # Update UI to indicate we're listening
        self.change_button.configure(text="Listening...")
        self.change_button.configure(state="disabled")
        
        # Create temporary event filters to catch all key events
        # This ensures we capture the key press before any other handler
        self._key_listen_id = self.root.bind_all("<KeyPress>", self._handle_key_press, add="+")
        
        # Update the window to show changes
        self.root.update_idletasks()
    
    def _handle_key_press(self, event):
        """Handle key press when listening for a new panic key"""
        if not self.is_listening_for_key:
            return
            
        # Get the key
        key = event.keysym
        logger.info(f"Received key press: {key}")
        
        # Normalize the key name
        if key == "apostrophe":
            key = "'"
        elif key == "quotedbl":
            key = '"'
        elif key == "space":
            key = " "
        elif key == "Escape":
            # Cancel changing the key if Escape is pressed
            logger.info("Cancelled panic key change")
            self._stop_listening_for_key()
            return "break"
        
        # Set the new panic key
        self._set_panic_key(key)
        
        # Stop listening
        self._stop_listening_for_key()
        
        # Return "break" to prevent event propagation
        return "break"
    
    def _set_panic_key(self, key):
        """Set the new panic key"""
        logger.info(f"Setting new panic key: {key}")
        
        # Update our local reference
        self.current_panic_key = key
        
        # Update the label
        self.key_label.configure(text=self._format_key_display(key))
        
        # Save to settings
        if hasattr(self.root, 'media_manager'):
            settings = self.root.media_manager.get_display_settings()
            settings['panic_key'] = key
            self.root.media_manager.update_display_settings(settings)
            logger.info(f"Saved panic key to settings: {key}")
        
        # Apply the new key with a delay (after panic functionality is restored)
        self.root.after(500, lambda: self._delayed_apply_key(key))
    
    def _delayed_apply_key(self, key):
        """Apply the new key after a delay"""
        if hasattr(self.root, 'set_panic_key'):
            success = self.root.set_panic_key(key)
            logger.info(f"Applied new panic key: {key} (success: {success})")
        else:
            logger.warning("Could not apply new panic key: set_panic_key not available")
    
    def _stop_listening_for_key(self):
        """Stop listening for a key press"""
        self.is_listening_for_key = False
        
        # Update UI
        self.change_button.configure(text="Change Key")
        self.change_button.configure(state="normal")
        
        # Unbind the key press listener
        if hasattr(self, '_key_listen_id'):
            self.root.unbind_all("<KeyPress>", self._key_listen_id)
        
        # Restore panic functionality with a delay
        self.root.after(1000, self._restore_panic_functionality)
        
        # Update window
        self.root.update_idletasks()
    
    def _restore_panic_functionality(self):
        """Restore all panic functionality"""
        with self.disable_lock:
            logger.info("Restoring panic functionality")
            
            # Restore original panic handler
            if self.original_handle_panic and hasattr(self.root, 'handle_panic'):
                self.root.handle_panic = self.original_handle_panic
                self.original_handle_panic = None
                logger.info("Restored original handle_panic function")
            
            # Restore all other panic handlers
            self._restore_all_panic_handlers()
            
            # Reset the flags
            self.panic_disabled = False
            self.root.is_panic_disabled = False
            
            logger.info("Panic functionality restored")
    
    def _restore_all_panic_handlers(self):
        """Restore all panic handlers that were disabled"""
        # Restore app_manager handlers
        if hasattr(self.root, 'app_manager'):
            app_manager = self.root.app_manager
            if hasattr(self, 'original_app_manager_panic'):
                app_manager.handle_panic = self.original_app_manager_panic
                self.original_app_manager_panic = None
                logger.info("Restored app_manager.handle_panic")
            
            if hasattr(self, 'original_panic_callback'):
                app_manager.panic_callback = self.original_panic_callback
                self.original_panic_callback = None
                logger.info("Restored app_manager.panic_callback")
        
        # Restore ui_manager handlers
        if hasattr(self.root, 'ui_manager'):
            ui_manager = self.root.ui_manager
            if hasattr(self, 'original_ui_manager_panic'):
                ui_manager.handle_panic = self.original_ui_manager_panic
                self.original_ui_manager_panic = None
                logger.info("Restored ui_manager.handle_panic")
    
    def grid(self, **kwargs):
        """Grid the frame with the given parameters"""
        self.frame.grid(**kwargs)
    
    def pack(self, **kwargs):
        """Pack the frame with the given parameters"""
        self.frame.pack(**kwargs) 