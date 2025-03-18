import tkinter as tk
from tkinter import ttk

class TitleBar:
    def __init__(self, parent, window, title="GOONWARE"):
        # Store the main window reference
        self.window = window
        
        # Set window to always be on top
        self.window.attributes('-topmost', True)
        
        # Store screen dimensions
        self.screen_width = self.window.winfo_screenwidth()
        self.screen_height = self.window.winfo_screenheight()
        
        # Create the title bar frame
        self.frame = ttk.Frame(parent, style='TitleBar.TFrame')
        
        # Configure styles
        style = ttk.Style()
        style.configure('TitleBar.TFrame',
                       background='#2d2d2d',
                       relief='flat')
        style.configure('TitleBar.TLabel',
                       background='#2d2d2d',
                       foreground='darkorchid3',
                       font=('Microsoft Sans Serif', 12))
        style.configure('TitleBarButton.TLabel',
                       background='#2d2d2d',
                       foreground='white',
                       font=('Segoe UI', 10))
        
        # Title label
        self.title_label = ttk.Label(
            self.frame,
            text=title,
            style='TitleBar.TLabel'
        )
        self.title_label.pack(side=tk.LEFT, padx=10)
        
        # Exit button
        self.exit_button = ttk.Label(
            self.frame,
            text="Exit",
            style='TitleBarButton.TLabel',
            cursor="hand2"
        )
        self.exit_button.pack(side=tk.RIGHT, padx=10)
        
        # Close/minimize button
        self.close_button = ttk.Label(
            self.frame,
            text="Hide",
            style='TitleBarButton.TLabel',
            cursor="hand2"
        )
        self.close_button.pack(side=tk.RIGHT, padx=5)
        
        # Bind events'
        self.close_button.bind('<Button-1>', self._on_close)
        self.close_button.bind('<Enter>', lambda e: self._on_hover(e, '#585757'))
        self.close_button.bind('<Leave>', lambda e: self._on_leave(e))
        
        self.exit_button.bind('<Button-1>', self._on_exit)
        self.exit_button.bind('<Enter>', lambda e: self._on_hover(e, '#ff0000'))
        self.exit_button.bind('<Leave>', lambda e: self._on_leave(e))
        
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
    
    def _on_close(self, event):
        """Hide the window instead of closing it"""
        self._reset_drag()
        # Use withdraw() to hide the window instead of destroying it
        # This ensures the application keeps running in the background
        try:
            # Ensure we're not in the middle of a drag operation
            if not self._drag_data["dragging"]:
                self.window.withdraw()
        except Exception as e:
            print(f"Error hiding window: {e}")
    
    def _on_exit(self, event):
        """Exit the application completely"""
        self._reset_drag()
        try:
            # Ensure we're not in the middle of a drag operation
            if not self._drag_data["dragging"]:
                # Try to call the quit_app method on the root window
                if hasattr(self.window, 'quit_app'):
                    self.window.quit_app()
                else:
                    # Fallback to standard Tk quit
                    self.window.quit()
                    import sys
                    sys.exit(0)
        except Exception as e:
            print(f"Error exiting application: {e}")
            # Last resort
            import os
            os._exit(0)
    
    def _on_hover(self, event, color):
        """Change background color on hover"""
        event.widget.configure(background=color)
    
    def _on_leave(self, event):
        """Restore original background color"""
        event.widget.configure(background='#2d2d2d')
    
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
            
            # Clamp position to screen boundaries
            x = max(0, min(x, self.screen_width - window_width))
            y = max(0, min(y, self.screen_height - window_height))
            
            # Update window position
            self.window.geometry(f"+{x}+{y}")
    
    def grid(self, **kwargs):
        """Grid the frame"""
        self.frame.grid(**kwargs) 