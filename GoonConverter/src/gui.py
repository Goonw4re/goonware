import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import logging
import shutil
from .converter import GoonConverter

logger = logging.getLogger(__name__)

class CustomTitleBar(ttk.Frame):
    """Custom title bar implementation"""
    
    def __init__(self, parent, title, on_close=None):
        super().__init__(parent, style='TitleBar.TFrame')
        
        # Style for title bar
        style = ttk.Style()
        style.configure('TitleBar.TFrame', background='#1a1a1a')
        style.configure('TitleBar.TLabel', 
                        background='#1a1a1a', 
                        foreground='#BB86FC',
                        font=('Segoe UI', 10, 'bold'))
        style.configure('CloseBtn.TLabel',
                        background='#1a1a1a',
                        foreground='#FF5252',
                        font=('Segoe UI', 10, 'bold'))
        style.map('CloseBtn.TLabel',
                  foreground=[('active', '#FF5252')])
        
        # Parent reference and callbacks
        self.parent = parent
        self.root = self._get_root(parent)
        self.on_close = on_close if on_close else self._default_close
        
        # Track mouse position for dragging
        self._x = 0
        self._y = 0
        
        # Create title bar contents
        self.pack(fill=tk.X)
        
        # Load icon
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(script_dir))  # Go up to project root
            icon_path = os.path.join(project_root, "assets", "icon.png")
            
            # Create PhotoImage
            self.icon = tk.PhotoImage(file=icon_path)
            
            # Scale down the icon
            original_width = self.icon.width()
            original_height = self.icon.height()
            scale_factor = 0.02  # Reduced from 0.6 to 0.02
            scaled_width = int(original_width * scale_factor)
            scaled_height = int(original_height * scale_factor)
            self.icon = self.icon.subsample(
                original_width // scaled_width, 
                original_height // scaled_height
            )
            
            # Icon label
            self.icon_label = ttk.Label(
                self, 
                image=self.icon,
                style='TitleBar.TLabel'
            )
            self.icon_label.pack(side=tk.LEFT, padx=(5, 0), pady=5)
        except Exception as e:
            logger.error(f"Error loading title bar icon: {e}")
            self.icon = None
        
        # Title label
        self.title_label = ttk.Label(
            self, 
            text=title,
            style='TitleBar.TLabel'
        )
        self.title_label.pack(side=tk.LEFT, padx=(0, 10), pady=0)
        
        # Close button
        self.close_btn = ttk.Label(
            self,
            text="✕",
            style='CloseBtn.TLabel',
            cursor="hand2"
        )
        self.close_btn.pack(side=tk.RIGHT, padx=10, pady=0)
        
        # Bind events
        self._bind_events()
    
    def _get_root(self, widget):
        """Get the toplevel window containing this widget"""
        root = widget.winfo_toplevel()
        return root
    
    def _default_close(self):
        """Default close behavior - destroy the window and exit if it's the main window"""
        root = self.root
        if root.winfo_class() == 'Tk':  # Is this the main Tk instance?
            root.quit()  # Stop mainloop
            root.destroy()  # Destroy the window
        else:
            root.destroy()  # Just destroy the Toplevel
    
    def _bind_events(self):
        """Bind all necessary events for dragging and buttons"""
        # Bind dragging events to all parts of the title bar
        for widget in [self, self.title_label]:
            widget.bind("<ButtonPress-1>", self.start_move)
            widget.bind("<B1-Motion>", self.on_move)
        
        # Bind close button events
        self.close_btn.bind("<ButtonPress-1>", lambda e: self.on_close())
        self.close_btn.bind("<Enter>", lambda e: self.close_btn.configure(foreground="#8B0000"))
        self.close_btn.bind("<Leave>", lambda e: self.close_btn.configure(foreground="#FF5252"))
    
    def start_move(self, event):
        """Record starting position for dragging"""
        self._x = event.x_root - self.root.winfo_x()
        self._y = event.y_root - self.root.winfo_y()
    
    def on_move(self, event):
        """Handle window dragging"""
        x = event.x_root - self._x
        y = event.y_root - self._y
        
        # Get window dimensions
        window = self.root
        width = window.winfo_width()
        height = window.winfo_height()
        
        # Get screen dimensions
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        
        # Clamp position to keep window on screen
        x = max(0, min(x, screen_width - width))
        y = max(0, min(y, screen_height - height))
        
        # Apply the new position
        window.geometry(f"+{x}+{y}")

class ConverterPanel(ttk.Frame):
    """GUI panel for the GoonConverter functionality"""
    
    def __init__(self, parent, models_dir=None):
        super().__init__(parent, style='Modern.TFrame')
        
        # Configure styles for this panel
        style = ttk.Style()
        style.configure('Modern.TFrame', background='#1e1e1e')
        style.configure('Modern.TLabel', 
                        background='#1e1e1e', 
                        foreground='white',
                        font=('Segoe UI', 10))
        style.configure('Header.TLabel',
                        background='#1e1e1e',
                        foreground='#BB86FC',  # Light purple accent
                        font=('Segoe UI', 14, 'bold'))
        style.configure('Modern.TButton', 
                        font=('Segoe UI', 10),
                        padding=6)
        style.map('Modern.TButton',
                  background=[('active', '#BB86FC'), ('!active', '#353535')],
                  foreground=[('active', 'black'), ('!active', 'black')])
        style.configure('Status.TLabel',
                        background='#1e1e1e',
                        foreground='#03DAC6',  # Teal for status
                        font=('Segoe UI', 10))
        style.configure('Info.TLabel',
                        background='#1e1e1e',
                        foreground='#BBBBBB',  # Light gray for info
                        font=('Segoe UI', 9))
        style.configure('Modern.TCheckbutton', 
                        background='#1e1e1e', 
                        foreground='white',
                        font=('Segoe UI', 10))
        style.configure('Progress.Horizontal.TProgressbar',
                        troughcolor='#353535',
                        background='#BB86FC')
        
        # Get root window
        self.root = parent.winfo_toplevel()
        
        # Initialize converter
        if models_dir is None:
            self.models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'models')
        else:
            self.models_dir = models_dir
            
        self.converter = GoonConverter(self.models_dir)
        
        # Variables
        self.delete_original_var = tk.BooleanVar(value=False)
        self.compress_files_var = tk.BooleanVar(value=True)  # Default to True for compression
        self.status_var = tk.StringVar(value="Ready to convert ZIP files to GMODEL format")
        self.progress_var = tk.DoubleVar(value=0.0)
        self.is_converting = False
        
        # Main layout
        self._create_header()
        self._create_controls()
        self._create_info_section()
        self._create_progress_section()
        self._create_status_bar()
    
    def _create_header(self):
        """Create header with logo and title"""
        header_frame = ttk.Frame(self, style='Modern.TFrame')
        header_frame.pack(fill=tk.X, padx=15, pady=(10, 5))  # Reduced top padding
        
        # App title
        title_label = ttk.Label(
            header_frame,
            text="GMODEL CONVERTER",
            style='Header.TLabel'
        )
        title_label.pack(anchor=tk.W)
        
        # Subtitle
        subtitle_label = ttk.Label(
            header_frame,
            text="Convert ZIP model files to GMODEL format",
            style='Info.TLabel'
        )
        subtitle_label.pack(anchor=tk.W, pady=(0, 3))  # Reduced bottom padding
        
        # Separator
        separator = ttk.Separator(self, orient='horizontal')
        separator.pack(fill=tk.X, padx=10, pady=(0, 5))  # Reduced padding
    
    def _create_controls(self):
        """Create control buttons and options"""
        controls_frame = ttk.Frame(self, style='Modern.TFrame')
        controls_frame.pack(fill=tk.X, padx=15, pady=3)  # Reduced vertical padding
        
        # Button frame for main controls
        button_frame = ttk.Frame(controls_frame, style='Modern.TFrame')
        button_frame.pack(fill=tk.X, pady=(3, 5))  # Reduced vertical padding
        
        # Single file conversion button
        convert_btn = ttk.Button(
            button_frame,
            text="Convert Single ZIP File",
            style='Modern.TButton',
            command=self._convert_single_file
        )
        convert_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Batch conversion button
        batch_btn = ttk.Button(
            button_frame,
            text="Convert All ZIP Files",
            style='Modern.TButton',
            command=self._convert_batch
        )
        batch_btn.pack(side=tk.LEFT)
        
        # Options frame
        options_frame = ttk.Frame(controls_frame, style='Modern.TFrame')
        options_frame.pack(fill=tk.X, pady=3)  # Reduced vertical padding
        
        # Delete original checkbox
        delete_checkbox = ttk.Checkbutton(
            options_frame,
            text="Delete original ZIP files after conversion",
            variable=self.delete_original_var,
            style="Modern.TCheckbutton"
        )
        delete_checkbox.pack(side=tk.LEFT)
        
        # Compression checkbox
        compress_checkbox = ttk.Checkbutton(
            options_frame,
            text="Compress files",
            variable=self.compress_files_var,
            style="Modern.TCheckbutton"
        )
        compress_checkbox.pack(side=tk.LEFT)
    
    def _create_info_section(self):
        """Create information section"""
        info_frame = ttk.Frame(self, style='Modern.TFrame')
        info_frame.pack(fill=tk.X, padx=15, pady=3)  # Reduced vertical padding
        
        # Directory info
        dir_label = ttk.Label(
            info_frame,
            text=f"Models Directory: {os.path.basename(self.models_dir)}",
            style='Info.TLabel'
        )
        dir_label.pack(anchor=tk.W, pady=(0, 3))  # Reduced vertical padding
        
        # Information about .gmodel files
        info_text = (
            "GMODEL files are ZIP files with a different extension and optional compression.\n"
            "Using compression can reduce file size but may take longer to convert.\n"
            "Converted files will be assigned a custom purple icon for easy identification."
        )
        info_label = ttk.Label(
            info_frame,
            text=info_text,
            style='Info.TLabel',
            wraplength=380,
            justify=tk.LEFT
        )
        info_label.pack(anchor=tk.W)
    
    def _create_progress_section(self):
        """Create progress section with progress bar"""
        progress_frame = ttk.Frame(self, style='Modern.TFrame')
        progress_frame.pack(fill=tk.X, padx=15, pady=5)  # Reduced vertical padding
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            orient=tk.HORIZONTAL,
            mode='determinate',
            variable=self.progress_var,
            style='Progress.Horizontal.TProgressbar'
        )
        self.progress_bar.pack(fill=tk.X, pady=(5, 0))
        
        # Hide initially
        self.progress_bar.pack_forget()
    
    def _create_status_bar(self):
        """Create status bar with conversion status"""
        status_frame = ttk.Frame(self, style='Modern.TFrame')
        status_frame.pack(fill=tk.X, padx=15, pady=5)  # Reduced vertical padding
        
        # Status label
        self.status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            style='Status.TLabel'
        )
        self.status_label.pack(anchor=tk.W)
    
    def _show_progress(self):
        """Show the progress bar"""
        self.progress_var.set(0)
        self.progress_bar.pack(fill=tk.X, pady=(5, 0))
    
    def _hide_progress(self):
        """Hide the progress bar"""
        self.progress_bar.pack_forget()
    
    def _update_progress(self, value):
        """Update progress bar value"""
        self.progress_var.set(value)
        self.root.update_idletasks()
    
    def _convert_single_file(self):
        """Handle single file conversion"""
        if self.is_converting:
            messagebox.showinfo("Conversion in Progress", "Please wait for the current conversion to complete.")
            return
            
        # Open file dialog to select ZIP file
        zip_path = filedialog.askopenfilename(
            title="Select ZIP File to Convert",
            filetypes=[("ZIP Files", "*.zip")],
            initialdir=self.models_dir
        )
        
        if not zip_path:
            return  # User cancelled
        
        # Show progress bar
        self._show_progress()
        self._update_progress(20)
            
        # Start conversion in a separate thread
        self.is_converting = True
        self.status_var.set("Converting file...")
        
        thread = threading.Thread(
            target=self._run_single_conversion,
            args=(zip_path, self.delete_original_var.get())
        )
        thread.daemon = True
        thread.start()
    
    def _run_single_conversion(self, zip_path, delete_original):
        """Run single file conversion in a separate thread"""
        try:
            # Update progress
            self.after(100, lambda: self._update_progress(30))
            
            # Convert the file
            compress = self.compress_files_var.get()
            result = self.converter.convert_to_gmodel(zip_path, delete_original, compress)
            
            # Update progress
            self.after(200, lambda: self._update_progress(100))
            
            # Update UI on main thread
            self.after(300, lambda: self._conversion_complete(result))
            
        except Exception as e:
            logger.error(f"Error in conversion thread: {e}")
            self.after(0, lambda: self._conversion_error(str(e)))
    
    def _convert_batch(self):
        """Handle batch conversion"""
        if self.is_converting:
            messagebox.showinfo("Conversion in Progress", "Please wait for the current conversion to complete.")
            return
            
        # Confirm batch conversion
        confirm = messagebox.askyesno(
            "Batch Convert",
            "This will convert all ZIP files in the models directory to GMODEL format. Continue?"
        )
        
        if not confirm:
            return
        
        # Show progress bar
        self._show_progress()
        self._update_progress(10)
            
        # Start conversion in a separate thread
        self.is_converting = True
        self.status_var.set("Converting all files...")
        
        thread = threading.Thread(
            target=self._run_batch_conversion,
            args=(self.delete_original_var.get(),)
        )
        thread.daemon = True
        thread.start()
    
    def _run_batch_conversion(self, delete_originals):
        """Run batch conversion in a separate thread"""
        try:
            # Scan directory first
            self.after(100, lambda: self._update_progress(20))
            
            # Get ZIP files
            zip_files = [f for f in os.listdir(self.models_dir) if f.lower().endswith('.zip')]
            
            if not zip_files:
                self.after(0, lambda: self._batch_conversion_complete({'total': 0, 'success': 0, 'failures': 0, 'skipped': 0}))
                return
            
            # Initialize stats
            stats = {'total': len(zip_files), 'success': 0, 'failures': 0, 'skipped': 0}
            compress = self.compress_files_var.get()
            
            # Process each file
            for i, zip_file in enumerate(zip_files):
                try:
                    zip_path = os.path.join(self.models_dir, zip_file)
                    base_name = os.path.splitext(zip_file)[0]
                    gmodel_path = os.path.join(self.models_dir, f"{base_name}.gmodel")
                    
                    # Skip if destination exists
                    if os.path.exists(gmodel_path):
                        stats['skipped'] += 1
                        continue
                    
                    # Convert file
                    result = self.converter.convert_to_gmodel(zip_path, delete_originals, compress)
                    
                    if result:
                        stats['success'] += 1
                    else:
                        stats['failures'] += 1
                    
                    # Update progress based on completion percentage
                    progress = 20 + (70 * (i + 1) / len(zip_files))
                    self.after(0, lambda p=progress: self._update_progress(p))
                    
                except Exception as e:
                    logger.error(f"Error converting {zip_file}: {e}")
                    stats['failures'] += 1
            
            # Update progress
            self.after(300, lambda: self._update_progress(100))
            
            # Update UI on main thread
            self.after(400, lambda: self._batch_conversion_complete(stats))
            
        except Exception as e:
            logger.error(f"Error in batch conversion thread: {e}")
            self.after(0, lambda: self._conversion_error(str(e)))
    
    def _conversion_complete(self, result):
        """Handle completion of single file conversion"""
        self.is_converting = False
        
        if result:
            self.status_var.set(f"Conversion completed: {os.path.basename(result)}")
            
            # Refresh media files if app has media manager
            if hasattr(self.root, 'media_manager'):
                self.root.media_manager.refresh_media_files()
                
                # Also refresh the media files panel if it exists
                if hasattr(self.root, 'media_files_panel'):
                    self.root.media_files_panel.refresh_models()
        else:
            self.status_var.set("Conversion failed. File may already exist or is invalid.")
        
        # Hide progress bar after a short delay
        self.after(500, self._hide_progress)
    
    def _batch_conversion_complete(self, stats):
        """Handle completion of batch conversion"""
        self.is_converting = False
        
        # Format status message
        if stats['total'] == 0:
            status = "No ZIP files found in models directory."
        else:
            status = f"Batch conversion completed: {stats['success']} converted, {stats['failures']} failed"
        
        self.status_var.set(status)
        
        # Refresh media files if app has media manager
        if hasattr(self.root, 'media_manager'):
            self.root.media_manager.refresh_media_files()
            
            # Also refresh the media files panel if it exists
            if hasattr(self.root, 'media_files_panel'):
                self.root.media_files_panel.refresh_models()
        
        # Hide progress bar after a short delay
        self.after(500, self._hide_progress)
    
    def _conversion_error(self, error_message):
        """Handle conversion error"""
        self.is_converting = False
        self.status_var.set("Conversion error occurred")
        messagebox.showerror("Conversion Error", f"Error during conversion: {error_message}")
        
        # Hide progress bar
        self._hide_progress()


def open_converter_window(parent, models_dir=None):
    """Open a standalone converter window"""
    window = tk.Toplevel(parent)
    window.title("GMODEL Converter")
    window.geometry("450x360")  # Reduced height to match launcher
    window.resizable(False, False)
    window.configure(bg='#1e1e1e')  # Match the dark theme
    window.overrideredirect(True)  # Remove system title bar
    
    # Set window icon if available
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(script_dir))  # Go up to project root
        icon_path = os.path.join(project_root, "assets", "icon.png")
        
        if os.path.exists(icon_path):
            # Create a PhotoImage and set as icon
            icon = tk.PhotoImage(file=icon_path)
            window.iconphoto(True, icon)
    except Exception as e:
        logger.error(f"Error setting window icon: {e}")
    
    # Define exit function
    def close_window():
        window.grab_release()  # Release modal state
        window.destroy()
    
    # Create main frame to hold everything
    main_frame = ttk.Frame(window, style='Modern.TFrame')
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Add custom title bar with explicit close function
    title_bar = CustomTitleBar(main_frame, "GMODEL Converter", on_close=close_window)
    
    # Create converter panel in the window
    converter_panel = ConverterPanel(main_frame, models_dir)
    converter_panel.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
    
    # Center the window on screen with clamping
    window.update_idletasks()
    width = window.winfo_width()
    height = window.winfo_height()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    
    # Calculate centered position with clamping
    x = max(0, min((screen_width - width) // 2, screen_width - width))
    y = max(0, min((screen_height - height) // 2, screen_height - height))
    
    # Set the window position
    window.geometry(f'{width}x{height}+{x}+{y}')
    
    # Add escape key binding to close window
    window.bind("<Escape>", lambda e: close_window())
    
    # Make window modal
    window.transient(parent)
    window.grab_set()
    
    return window 