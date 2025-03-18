import tkinter as tk
from tkinter import ttk
import os
import subprocess
import logging
import traceback
import sys

logger = logging.getLogger(__name__)

class MediaFilesPanel(ttk.Frame):
    def __init__(self, parent, models_dir=None, on_zip_change=None, on_refresh=None):
        super().__init__(parent, style='Modern.TFrame')
        
        # Configure styles for this panel
        style = ttk.Style()
        style.configure('MediaFiles.TFrame', background='#1e1e1e')
        style.configure('MediaFiles.TLabel', 
                        background='#1e1e1e', 
                        foreground='white',
                        font=('Segoe UI', 10))
        style.configure('MediaFiles.TCheckbutton', 
                        background='#1e1e1e', 
                        foreground='white',
                        font=('Segoe UI', 10))
        
        # Get root window to access media manager
        self.root = parent.winfo_toplevel()
        
        # Set models directory
        if models_dir is None:
            self.models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'models')
        else:
            self.models_dir = models_dir
        
        # Set callbacks
        self.on_zip_change = on_zip_change
        self.on_refresh = on_refresh
        
        # Initialize variables
        self.zip_vars = {}
        self.zip_checkboxes = {}
        self.active_count_var = tk.StringVar(value="Active: 0/0")
        
        # Create panel title
        title_label = ttk.Label(
            self,
            text="Media Files",
            style='Modern.TLabel',
            font=('Segoe UI', 12, 'bold')
        )
        title_label.pack(anchor=tk.W, padx=5, pady=(5, 0))
        
        # Create controls
        self._create_controls()
        
        # Create file list
        self._create_file_list()
        
        # Create status bar
        self._create_status_bar()
        
        # Schedule initial loading after UI is created
        self.after(100, self._load_initial_zips)
    
    def _create_controls(self):
        # Button frame for controls
        button_frame = ttk.Frame(self, style='MediaFiles.TFrame')
        button_frame.pack(fill=tk.X, pady=(0, 5))  # Reduced padding
        
        # Refresh button
        refresh_btn = ttk.Button(
            button_frame,
            text="🔄 Refresh Models",
            style='Modern.TButton',
            command=self.on_refresh_click
        )
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        # Open folder button
        folder_btn = ttk.Button(
            button_frame,
            text="📁 Open Folder",
            style='Modern.TButton',
            command=self.open_models_folder
        )
        folder_btn.pack(side=tk.LEFT, padx=5)
        
        # Info label
        ttk.Label(
            self,
            text="Select Models:",
            style='MediaFiles.TLabel'
        ).pack(fill=tk.X, padx=5, pady=(10, 5))
    
    def _create_file_list(self):
        # Create frame for file list with scrollbar
        list_frame = ttk.Frame(self, style='MediaFiles.TFrame')
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))  # Reduced padding
        
        # Create canvas without visible scrollbar
        canvas = tk.Canvas(
            list_frame,
            height=180,  # Increased height for better visibility
            bg='#1e1e1e',
            highlightthickness=0,
            borderwidth=0
        )
        
        # Create scrollbar but don't display it visually
        # We still need it for the scrolling functionality
        scrollbar = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=canvas.yview
        )
        
        # Configure canvas scrolling
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack canvas only (don't pack scrollbar to hide it)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Create frame for file list items
        self.file_list_frame = ttk.Frame(canvas, style='MediaFiles.TFrame')
        
        # Add file list frame to canvas
        canvas_window = canvas.create_window(
            (0, 0),
            window=self.file_list_frame,
            anchor="nw",
            width=canvas.winfo_reqwidth()
        )
        
        # Configure canvas scrolling
        def _configure_canvas(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())
        
        self.file_list_frame.bind("<Configure>", _configure_canvas)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=canvas.winfo_width()))
        
        # Add mouse wheel scrolling with improved sensitivity
        def _on_mousewheel(event):
            # Scroll direction depends on the platform
            scroll_amount = 3  # Increased scroll amount for smoother scrolling
            
            if event.num == 4 or event.delta > 0:
                canvas.yview_scroll(-scroll_amount, "units")  # Scroll up
            elif event.num == 5 or event.delta < 0:
                canvas.yview_scroll(scroll_amount, "units")   # Scroll down
            return "break"  # Prevent event propagation
        
        # Bind mouse wheel events to canvas
        canvas.bind("<MouseWheel>", _on_mousewheel)  # Windows and macOS
        canvas.bind("<Button-4>", _on_mousewheel)    # Linux scroll up
        canvas.bind("<Button-5>", _on_mousewheel)    # Linux scroll down
        
        # Add keyboard navigation
        canvas.bind("<Up>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind("<Down>", lambda e: canvas.yview_scroll(1, "units"))
        canvas.bind("<Prior>", lambda e: canvas.yview_scroll(-5, "units"))  # Page Up
        canvas.bind("<Next>", lambda e: canvas.yview_scroll(5, "units"))    # Page Down
        canvas.bind("<Home>", lambda e: canvas.yview_moveto(0.0))
        canvas.bind("<End>", lambda e: canvas.yview_moveto(1.0))
        
        # Make canvas focusable for keyboard navigation
        canvas.config(takefocus=1)
        
        # Store references for later use
        self.canvas = canvas
        self.list_frame = list_frame
        
        # Store the mousewheel handler for binding to new widgets
        self._on_mousewheel = _on_mousewheel
    
    def _create_status_bar(self):
        """Create status bar with active count"""
        status_frame = ttk.Frame(self, style='MediaFiles.TFrame')
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Active count label
        self.active_label = ttk.Label(
            status_frame,
            textvariable=self.active_count_var,
            style='MediaFiles.TLabel'
        )
        self.active_label.pack(side=tk.LEFT)
    
    def _load_initial_zips(self):
        """Load initial zip files from media manager"""
        try:
            logger.info("Loading initial zip files")
            # Check if media manager is available
            if hasattr(self.root, 'media_manager') and self.root.media_manager:
                # Refresh the models list
                self.refresh_models()
                # Update the active zips display
                self.update_active_zips()
                
                logger.info("Initial zip files loaded successfully")
            else:
                logger.warning("Media manager not available for initial loading")
        except Exception as e:
            logger.error(f"Error loading initial zip files: {e}\n{traceback.format_exc()}")
    
    def refresh_models(self):
        """Refresh the list of available models"""
        try:
            # Clear existing file list
            for widget in self.file_list_frame.winfo_children():
                widget.destroy()
            
            # Clear our tracking variables
            self.zip_vars.clear()
            self.zip_checkboxes.clear()
            
            # Get available zips from media manager
            available_zips = self.root.media_manager.available_zips
            
            if not available_zips:
                no_models_label = ttk.Label(
                    self.file_list_frame,
                    text="No models found in models folder",
                    style="MediaFiles.TLabel"
                )
                no_models_label.pack(pady=10)
                # Bind mousewheel to the label
                no_models_label.bind("<MouseWheel>", self._on_mousewheel)
                no_models_label.bind("<Button-4>", self._on_mousewheel)
                no_models_label.bind("<Button-5>", self._on_mousewheel)
                return
            
            # Create a checkbox for each zip file
            for i, (zip_name, zip_path) in enumerate(available_zips.items()):
                # Create a variable for the checkbox
                var = tk.BooleanVar(value=zip_name in self.root.media_manager.loaded_zips)
                self.zip_vars[zip_name] = var
                
                # Create a frame for this zip entry
                zip_frame = ttk.Frame(self.file_list_frame, style="MediaFiles.TFrame")
                zip_frame.pack(fill=tk.X, padx=5, pady=2)
                
                # Create the checkbox
                checkbox = ttk.Checkbutton(
                    zip_frame,
                    text=zip_name,
                    variable=var,
                    style="MediaFiles.TCheckbutton",
                    command=lambda zn=zip_name: self.toggle_zip(zn)
                )
                checkbox.pack(side=tk.LEFT, padx=5)
                self.zip_checkboxes[zip_name] = checkbox
                
                # Bind mousewheel events to the new widgets
                zip_frame.bind("<MouseWheel>", self._on_mousewheel)
                zip_frame.bind("<Button-4>", self._on_mousewheel)
                zip_frame.bind("<Button-5>", self._on_mousewheel)
                checkbox.bind("<MouseWheel>", self._on_mousewheel)
                checkbox.bind("<Button-4>", self._on_mousewheel)
                checkbox.bind("<Button-5>", self._on_mousewheel)
            
            logger.info(f"Refreshed models list with {len(available_zips)} models")
        except Exception as e:
            logger.error(f"Error refreshing models: {e}\n{traceback.format_exc()}")
    
    def toggle_zip(self, zip_name):
        """Toggle a zip file on or off"""
        try:
            # Get the current state of the checkbox
            is_checked = self.zip_vars[zip_name].get()
            
            if is_checked:
                # Load the zip
                success = self.root.media_manager.load_zip(zip_name)
                if not success:
                    # If loading failed, uncheck the box
                    self.zip_vars[zip_name].set(False)
                    logger.warning(f"Failed to load zip: {zip_name}")
            else:
                # Unload the zip
                success = self.root.media_manager.unload_zip(zip_name)
                if not success:
                    # If unloading failed, check the box again
                    self.zip_vars[zip_name].set(True)
                    logger.warning(f"Failed to unload zip: {zip_name}")
            
            # Update the UI to reflect the current state
            self.update_active_zips()
            
            logger.info(f"Toggled zip {zip_name} to {'loaded' if is_checked else 'unloaded'}")
        except Exception as e:
            logger.error(f"Error toggling zip {zip_name}: {e}\n{traceback.format_exc()}")
    
    def update_active_zips(self):
        """Update the UI to reflect the currently active zips"""
        try:
            # Get the current loaded zips from the media manager
            loaded_zips = self.root.media_manager.loaded_zips
            
            # Update the checkbox variables to match
            for zip_name, var in self.zip_vars.items():
                var.set(zip_name in loaded_zips)
            
            # Update the active count label
            self.active_count_var.set(f"Active: {len(loaded_zips)}/{len(self.zip_vars)}")
            
            logger.info(f"Updated active zips display: {len(loaded_zips)} active")
        except Exception as e:
            logger.error(f"Error updating active zips: {e}\n{traceback.format_exc()}")
    
    def on_refresh_click(self):
        """Handle refresh button click"""
        try:
            # Refresh the media files in the media manager
            self.root.media_manager.refresh_media_files()
            
            # Refresh the UI
            self.refresh_models()
            
            # Update the active zips display
            self.update_active_zips()
            
            logger.info("Refreshed models from refresh button click")
        except Exception as e:
            logger.error(f"Error in refresh button handler: {e}\n{traceback.format_exc()}")
    
    def open_models_folder(self):
        """Open the models folder in the file explorer"""
        try:
            models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'models')
            if os.path.exists(models_dir):
                # Use the appropriate command based on the OS
                if os.name == 'nt':  # Windows
                    os.startfile(models_dir)
                elif os.name == 'posix':  # macOS or Linux
                    if sys.platform == 'darwin':  # macOS
                        subprocess.call(['open', models_dir])
                    else:  # Linux
                        subprocess.call(['xdg-open', models_dir])
                
                logger.info(f"Opened models folder: {models_dir}")
            else:
                logger.warning(f"Models directory does not exist: {models_dir}")
        except Exception as e:
            logger.error(f"Error opening models folder: {e}\n{traceback.format_exc()}")
