import os
import logging
import tkinter as tk
from tkinter import ttk

# Configure logging
logger = logging.getLogger(__name__)

class TitleBar:
    """Custom title bar that matches other Goonware applications"""
    
    def __init__(self, parent, window, title="GMODEL Viewer"):
        # Store the main window reference
        self.window = window
        
        # Create the title bar frame
        self.frame = ttk.Frame(parent, style='TitleBar.TFrame')
        
        # Configure styles
        style = ttk.Style()
        style.configure('TitleBar.TFrame',
                       background='#1a1a1a',  # Darker background color
                       relief='flat')
        style.configure('TitleBar.TLabel',
                       background='#1a1a1a',  # Match the new background
                       foreground='#BB86FC',
                       font=('Segoe UI', 12, 'bold'))
        
        # New styles for buttons
        style.configure('TitleBarButton.TLabel',
                       background='#1a1a1a',  # Match the new background
                       foreground='#FFFFFF',
                       font=('Segoe UI', 10, 'bold')
        )
        style.configure('ExitButton.TLabel',
                       background='#1a1a1a',  # Match the new background
                       foreground='#FF5252',  # Red color for exit
                       font=('Segoe UI', 10, 'bold')
        )
        
        # Load icon
        try:
            # Determine the path to the icon
            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(script_dir))
            icon_path = os.path.join(project_root, "assets", "icon.png")
            
            # Create PhotoImage
            self.icon = tk.PhotoImage(file=icon_path)
            
            # Scale down the icon
            original_width = self.icon.width()
            original_height = self.icon.height()
            scale_factor = 0.02  # Adjust this to make the icon smaller
            scaled_width = int(original_width * scale_factor)
            scaled_height = int(original_height * scale_factor)
            self.icon = self.icon.subsample(
                original_width // scaled_width, 
                original_height // scaled_height
            )
            
            # Icon label
            self.icon_label = ttk.Label(
                self.frame, 
                image=self.icon,
                style='TitleBar.TLabel'
            )
            self.icon_label.pack(side=tk.LEFT, padx=(10, 5), pady=5)
        except Exception as e:
            logger.error(f"Error loading title bar icon: {e}")
            self.icon = None
        
        # Title label
        self.title_label = ttk.Label(
            self.frame,
            text=title,
            style='TitleBar.TLabel'
        )
        self.title_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # Button frame to align buttons
        button_frame = ttk.Frame(self.frame, style='TitleBar.TFrame')
        button_frame.pack(side=tk.RIGHT, padx=10, pady=0)  # Remove vertical padding
        
        # Use a container to help with vertical centering
        button_container = ttk.Frame(button_frame, style='TitleBar.TFrame')
        button_container.pack(expand=True, fill=tk.BOTH)
        
        # Exit button
        self.exit_button = ttk.Label(
            button_container,
            text="✕",  # Use a more minimalist close symbol
            style='ExitButton.TLabel',
            cursor="hand2"
        )
        self.exit_button.pack(side=tk.RIGHT, padx=(5, 0), anchor='center')
        
        # Bind events
        self.exit_button.bind('<Button-1>', self._on_exit)
        self.exit_button.bind('<Enter>', lambda e: self._on_hover(e, '#8B0000', 'ExitButton.TLabel'))
        self.exit_button.bind('<Leave>', lambda e: self._on_leave(e, 'ExitButton.TLabel'))
        
        # Initialize drag variables
        self._drag_data = {"x": 0, "y": 0, "dragging": False}
        
        # Bind dragging events to frame and title
        self.frame.bind('<Button-1>', self._start_drag)
        self.frame.bind('<ButtonRelease-1>', self._stop_drag)
        self.frame.bind('<B1-Motion>', self._on_drag)
        
        self.title_label.bind('<Button-1>', self._start_drag)
        self.title_label.bind('<ButtonRelease-1>', self._stop_drag)
        self.title_label.bind('<B1-Motion>', self._on_drag)
        
        # Bind window events to handle show/hide
        self.window.bind('<Map>', lambda e: self._reset_drag())
        self.window.bind('<Unmap>', lambda e: self._reset_drag())
    
    def _on_exit(self, event):
        """Exit the application completely"""
        self._reset_drag()
        try:
            # Ensure we're not in the middle of a drag operation
            if not self._drag_data["dragging"]:
                self.window.destroy()
        except Exception as e:
            logger.error(f"Error exiting application: {e}")
    
    def _on_hover(self, event, color, style):
        """Change background color on hover"""
        event.widget.configure(foreground=color)
    
    def _on_leave(self, event, style):
        """Restore original color"""
        if style == 'ExitButton.TLabel':
            event.widget.configure(foreground='#FF5252')
    
    def _reset_drag(self):
        """Reset drag state"""
        self._drag_data = {"x": 0, "y": 0, "dragging": False}
    
    def _start_drag(self, event):
        """Start window drag"""
        self._drag_data = {
            "x": event.x_root - self.window.winfo_x(),
            "y": event.y_root - self.window.winfo_y(),
            "dragging": True
        }
    
    def _stop_drag(self, event):
        """Stop window drag"""
        self._drag_data["dragging"] = False
    
    def _on_drag(self, event):
        """Handle window dragging"""
        if self._drag_data["dragging"]:
            # Calculate new position
            x = event.x_root - self._drag_data["x"]
            y = event.y_root - self._drag_data["y"]
            
            # Get window size
            window_width = self.window.winfo_width()
            window_height = self.window.winfo_height()
            
            # Get screen dimensions - refresh every time to handle multi-monitor setups
            screen_width = self.window.winfo_screenwidth()
            screen_height = self.window.winfo_screenheight()
            
            # Calculate strict clamping to keep window fully on screen
            # Left edge cannot be less than 0
            x = max(0, x)
            
            # Top edge cannot be less than 0
            y = max(0, y)
            
            # Right edge cannot exceed screen width
            x = min(x, screen_width - window_width)
            
            # Bottom edge cannot exceed screen height
            y = min(y, screen_height - window_height)
            
            # Apply the new position
            self.window.geometry(f"+{x}+{y}")
    
    def pack(self, **kwargs):
        """Pack the frame"""
        self.frame.pack(**kwargs)
        
    def grid(self, **kwargs):
        """Grid the frame"""
        self.frame.grid(**kwargs)
    
    def set_title(self, title):
        """Update the title bar text"""
        try:
            self.title_label.config(text=title)
        except Exception as e:
            logger.error(f"Error setting title: {e}") 