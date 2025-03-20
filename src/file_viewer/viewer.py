import os
import io
import logging
import tempfile
import zipfile
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import shutil
import datetime
import cv2
import threading
import time
import queue
import numpy as np

# Import components
from .title_bar import TitleBar
from .file_browser import FileBrowser
from .media_player import MediaPlayer

# Configure logging
logger = logging.getLogger(__name__)

class CustomScrollbar(ttk.Scrollbar):
    """Custom scrollbar class with transparent styling"""
    def __init__(self, parent, **kwargs):
        # Configure the style
        style = ttk.Style()
        style.configure("Transparent.Vertical.TScrollbar",
                        background="clear",
                        troughcolor="#121212",
                        arrowcolor="#666666",
                        borderwidth=0,
                        relief="flat")
        
        style.map("Transparent.Vertical.TScrollbar",
                 background=[("active", "#333333"), ("!active", "#121212")],
                 arrowcolor=[("active", "#BBBBBB"), ("!active", "#666666")])
        
        # Initialize with transparent style
        kwargs['style'] = "Transparent.Vertical.TScrollbar"
        super().__init__(parent, **kwargs)

class GModelViewer:
    """Main viewer class for GMODEL files"""
    
    def __init__(self, root=None, file_path=None):
        # Initialize variables that might be accessed during cleanup
        self.zipfile = None
        self.temp_dir = None
        self.current_file = None
        self.media_player = None
        self.file_info_frame = None
        
        # Create root window if not provided
        if root is None:
            self.root = tk.Tk()
            self.owns_root = True
        else:
            self.root = root
            self.owns_root = False
        
        # Initialize variables
        self.file_path = file_path
        
        # Set window properties
        self.root.title("GMODEL Viewer")
        self.root.geometry("1000x700")
        self.root.configure(bg="#121212")
        
        # IMPORTANT: Make window appear in taskbar
        if self.owns_root:
            # Only change these settings if we own the root window
            self.root.attributes("-alpha", 0.0)  # Hide window during setup to avoid flicker
            
            # Don't use overrideredirect at all - let the window have normal decorations
            # This ensures it will show in the taskbar
            self.root.overrideredirect(False)
            
            # Set the window icon - essential for taskbar
            self._create_icon()
            
            # Create our custom title bar
            self.use_custom_titlebar = False
            
            # Make the window visible again
            self.root.attributes("-alpha", 1.0)
        else:
            # If we don't own the root, don't change its properties
            self._create_icon()
            self.use_custom_titlebar = False
        
        # Create main container
        self.main_frame = ttk.Frame(self.root, style='Main.TFrame')
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create styles
        style = ttk.Style()
        style.configure('Main.TFrame', background='#121212')
        style.configure('TitleBar.TFrame', background='#121212')
        style.configure('TSeparator', background='#333333')
        
        # Create title bar only if using custom one
        if self.use_custom_titlebar:
            self.title_bar = TitleBar(self.main_frame, self.root)
            self.title_bar.pack(fill=tk.X)
        else:
            # Add a small padding at the top when using system title bar
            padding_frame = ttk.Frame(self.main_frame, style='Main.TFrame', height=5)
            padding_frame.pack(fill=tk.X)
        
        # Create content frame
        self.content_frame = ttk.Frame(self.main_frame, style='Main.TFrame')
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        try:
            # Create splitter - use default style
            self.paned_window = ttk.PanedWindow(
                self.content_frame, 
                orient=tk.HORIZONTAL
            )
        except Exception as e:
            logger.error(f"Error configuring styles: {e}")
            # Fallback to basic PanedWindow
            self.paned_window = ttk.PanedWindow(
                self.content_frame, 
                orient=tk.HORIZONTAL
            )
            
        # Configure invisible/transparent sash (divider)
        style.configure('TSeparator', background='#121212')
        style.configure('TPanedwindow', background='#121212')
        style.map('TPanedwindow', background=[('active', '#121212')])
        style.configure('Sash', background='#444444', gripcount=0, handlesize=3, sashthickness=3)
        style.map('Sash', background=[('active', '#666666'), ('pressed', '#888888')])
        self.paned_window.configure(style='TPanedwindow')
            
        self.paned_window.pack(fill=tk.BOTH, expand=True)
        
        # Create file browser
        self.file_browser_frame = ttk.Frame(self.paned_window, style='Main.TFrame')
        self.file_browser = FileBrowser(
            self.file_browser_frame,
            on_file_selected=self.display_file,
            on_file_deleted=self.delete_file
        )
        self.file_browser.pack(fill=tk.BOTH, expand=True)
        
        # Create preview container frame
        self.preview_container = ttk.Frame(self.paned_window, style='Main.TFrame')
        
        # Create title and button frame
        self.preview_title_frame = ttk.Frame(self.preview_container, style='Main.TFrame')
        
        # Create title label
        self.preview_title = ttk.Label(
            self.preview_title_frame,
            text="Preview",
            style='Header.TLabel',
            anchor='center'
        )
        self.preview_title.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=(10, 0))
        
        # Create close button
        style = ttk.Style()
        style.configure('Close.TButton', 
                      background='#121212',
                      foreground='#FFFFFF',  # Fix: Changed from #121212 to #FFFFFF
                      borderwidth=0)
        style.map('Close.TButton',
                 background=[('active', '#232323'), ('pressed', '#232323')],
                 foreground=[('active', '#FFFFFF')])
        
        # Create a custom dark button using Label instead of Button for better styling control
        self.close_preview_button = tk.Label(
            self.preview_title_frame,
            text="✕",
            padx=5,
            pady=2,
            background='#121212',
            foreground='#FFFFFF',
            font=('Segoe UI', 10)
        )
        
        # Bind click and hover events
        self.close_preview_button.bind("<Button-1>", lambda e: self._close_preview())
        self.close_preview_button.bind("<Enter>", lambda e: self.close_preview_button.config(background='#232323'))
        self.close_preview_button.bind("<Leave>", lambda e: self.close_preview_button.config(background='#121212'))
        
        # Pack the button
        self.close_preview_button.pack(side=tk.RIGHT, padx=(0, 10), pady=(10, 0))
        
        # Pack title frame
        self.preview_title_frame.pack(fill=tk.X)
        
        style.configure('Header.TLabel',
                       font=('Segoe UI', 14, 'bold'),
                       background='#121212',
                       foreground='#BB86FC')
        
        # Separator
        self.preview_separator = ttk.Separator(self.preview_container, orient='horizontal')
        self.preview_separator.pack(fill=tk.X, padx=10, pady=5)
        
        # Create file info frame
        self.file_info_frame = ttk.Frame(self.preview_container, style='Info.TFrame')
        style.configure('Info.TFrame', background='#121212')
        style.configure('InfoText.TLabel', 
                       background='#121212', 
                       foreground='#BBBBBB',
                       font=('Segoe UI', 9))
        style.configure('InfoTitle.TLabel', 
                       background='#121212', 
                       foreground='#FFFFFF',
                       font=('Segoe UI', 10, 'bold'))
        
        # File info details
        self.file_name_label = ttk.Label(
            self.file_info_frame, 
            text="No file selected",
            style='InfoTitle.TLabel'
        )
        self.file_name_label.pack(anchor='w', padx=10, pady=(0, 2))
        
        self.file_size_label = ttk.Label(
            self.file_info_frame, 
            text="",
            style='InfoText.TLabel'
        )
        self.file_size_label.pack(anchor='w', padx=10)
        
        self.file_date_label = ttk.Label(
            self.file_info_frame, 
            text="",
            style='InfoText.TLabel'
        )
        self.file_date_label.pack(anchor='w', padx=10, pady=(0, 5))
        
        # Pack the file info frame
        self.file_info_frame.pack(fill=tk.X)
        
        # Create media viewer
        self.media_frame = ttk.Frame(self.preview_container, style='Main.TFrame')
        self.media_player = MediaPlayer(self.media_frame)
        self.media_player.pack(fill=tk.BOTH, expand=True)
        
        # Pack the media frame
        self.media_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Add frames to paned window
        self.paned_window.add(self.file_browser_frame, weight=1)
        self.paned_window.add(self.preview_container, weight=3)
        
        # Bind events
        self.root.bind("<Escape>", lambda e: self.close())
        
        # Create temp directory for extracted files
        self.temp_dir = tempfile.mkdtemp(prefix="gmodel_")
        
        # Show splashscreen
        self._show_splashscreen()
        
        # Load file if provided
        if file_path:
            self.load_file(file_path)
        
        # Center window on screen
        self._center_window()
        
        # Start the event loop if we own the root
        if self.owns_root:
            self.root.mainloop()
    
    def _show_splashscreen(self):
        """Show a splash screen before files are loaded"""
        if not hasattr(self, 'media_player') or self.media_player is None:
            return
            
        # Update title
        self.preview_title.config(text="GMODEL Information")
        self.file_name_label.config(text=os.path.basename(self.file_path) if self.file_path else "No file selected")
        
        # If we have a file path, show its details
        if self.file_path:
            try:
                # Get file stats
                file_stat = os.stat(self.file_path)
                file_size = self._format_size(file_stat.st_size)
                file_date = datetime.datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                creation_date = datetime.datetime.fromtimestamp(file_stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
                
                # Get compression info if it's a zip file
                try:
                    with zipfile.ZipFile(self.file_path, 'r') as z:
                        file_count = len(z.namelist())
                        file_list = z.namelist()
                        uncompressed_size = sum(info.file_size for info in z.infolist())
                        compressed_size = sum(info.compress_size for info in z.infolist())
                        compression_ratio = (1 - compressed_size / uncompressed_size) * 100 if uncompressed_size > 0 else 0
                        
                        # Count file types
                        image_count = sum(1 for f in file_list if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')))
                        video_count = sum(1 for f in file_list if f.lower().endswith(('.mp4', '.avi', '.mov', '.wmv', '.webm')))
                        audio_count = sum(1 for f in file_list if f.lower().endswith(('.mp3', '.wav', '.ogg', '.flac')))
                        text_count = sum(1 for f in file_list if f.lower().endswith(('.txt', '.json', '.xml', '.html', '.md')))
                        other_count = file_count - (image_count + video_count + audio_count + text_count)
                        
                        self.file_size_label.config(text=f"Size: {file_size} • Files: {file_count} • Compression: {compression_ratio:.1f}%")
                        self.file_date_label.config(text=f"Modified: {file_date} • Created: {creation_date}")
                except Exception as e:
                    logger.error(f"Error reading zip metadata: {e}")
                    self.file_size_label.config(text=f"Size: {file_size}")
                    self.file_date_label.config(text=f"Last Modified: {file_date}")
            except Exception as e:
                logger.error(f"Error getting file stats: {e}")
                self.file_size_label.config(text="")
                self.file_date_label.config(text="")
        else:
            self.file_size_label.config(text="")
            self.file_date_label.config(text="")
            
        # Create a simple splash screen in the media panel
        self.media_player.canvas.delete("all")
        
        # Calculate canvas dimensions
        canvas_width = self.media_player.canvas.winfo_width() or 600
        canvas_height = self.media_player.canvas.winfo_height() or 400
        
        # Vertical position for info
        y_pos = 80
        
        if self.file_path:
            # Add file stats
            if 'file_count' in locals():
                # Section header
                self.media_player.canvas.create_text(
                    canvas_width // 2,
                    y_pos - 40,
                    text="GMODEL Content Summary",
                    fill="#FFFFFF",
                    font=("Segoe UI", 16, "bold")
                )
                
                # Draw horizontal separator line
                self.media_player.canvas.create_line(
                    canvas_width // 4, y_pos - 20,
                    3 * canvas_width // 4, y_pos - 20,
                    fill="#333333", width=1
                )
                
                # Model content stats
                content_text = f"Content: {image_count} images • {video_count} videos • {audio_count} audio • {text_count} text • {other_count} other"
                
                # Add detailed stats
                self.media_player.canvas.create_text(
                    canvas_width // 2,
                    y_pos,
                    text=content_text,
                    fill="#FFFFFF",
                    font=("Segoe UI", 12)
                )
                
                # Add size comparison
                original_size = self._format_size(uncompressed_size)
                current_size = self._format_size(compressed_size)
                self.media_player.canvas.create_text(
                    canvas_width // 2,
                    y_pos + 30,
                    text=f"Original size: {original_size} • Compressed size: {current_size}",
                    fill="#FFFFFF",
                    font=("Segoe UI", 12)
                )
                
                # Add space savings
                saved_space = self._format_size(uncompressed_size - compressed_size)
                self.media_player.canvas.create_text(
                    canvas_width // 2,
                    y_pos + 60,
                    text=f"Space saved: {saved_space} ({compression_ratio:.1f}%)",
                    fill="#00E676",
                    font=("Segoe UI", 14, "bold")
                )
                
                # Add content breakdown visualization if there are files
                if file_count > 0:
                    # Draw horizontal separator line
                    self.media_player.canvas.create_line(
                        canvas_width // 4, y_pos + 90,
                        3 * canvas_width // 4, y_pos + 90,
                        fill="#333333", width=1
                    )
                    
                    # Add content breakdown section header
                    self.media_player.canvas.create_text(
                        canvas_width // 2,
                        y_pos + 110,
                        text="Content Breakdown",
                        fill="#FFFFFF",
                        font=("Segoe UI", 14, "bold")
                    )
                    
                    # Calculate proportions
                    total = image_count + video_count + audio_count + text_count + other_count
                    if total > 0:
                        # Proportions
                        img_prop = image_count / total
                        vid_prop = video_count / total
                        aud_prop = audio_count / total
                        txt_prop = text_count / total
                        oth_prop = other_count / total
                        
                        # Bar width and height
                        bar_width = canvas_width * 0.6
                        bar_height = 24
                        bar_y = y_pos + 140
                        bar_x = (canvas_width - bar_width) / 2
                        
                        # Draw segments
                        img_width = bar_width * img_prop
                        vid_width = bar_width * vid_prop
                        aud_width = bar_width * aud_prop
                        txt_width = bar_width * txt_prop
                        oth_width = bar_width * oth_prop
                        
                        # Draw colored segments
                        if img_prop > 0:
                            self.media_player.canvas.create_rectangle(
                                bar_x, bar_y,
                                bar_x + img_width, bar_y + bar_height,
                                fill="#3F51B5", outline=""  # Blue for images
                            )
                        
                        if vid_prop > 0:
                            self.media_player.canvas.create_rectangle(
                                bar_x + img_width, bar_y,
                                bar_x + img_width + vid_width, bar_y + bar_height,
                                fill="#E91E63", outline=""  # Pink for videos
                            )
                        
                        if aud_prop > 0:
                            self.media_player.canvas.create_rectangle(
                                bar_x + img_width + vid_width, bar_y,
                                bar_x + img_width + vid_width + aud_width, bar_y + bar_height,
                                fill="#FFC107", outline=""  # Amber for audio
                            )
                        
                        if txt_prop > 0:
                            self.media_player.canvas.create_rectangle(
                                bar_x + img_width + vid_width + aud_width, bar_y,
                                bar_x + img_width + vid_width + aud_width + txt_width, bar_y + bar_height,
                                fill="#4CAF50", outline=""  # Green for text
                            )
                        
                        if oth_prop > 0:
                            self.media_player.canvas.create_rectangle(
                                bar_x + img_width + vid_width + aud_width + txt_width, bar_y,
                                bar_x + img_width + vid_width + aud_width + txt_width + oth_width, bar_y + bar_height,
                                fill="#9E9E9E", outline=""  # Gray for other
                            )
                        
                        # Draw legend
                        legend_y = bar_y + bar_height + 20
                        legend_spacing = 120
                        
                        # Images legend
                        if image_count > 0:
                            self.media_player.canvas.create_rectangle(
                                bar_x, legend_y, 
                                bar_x + 15, legend_y + 15, 
                                fill="#3F51B5", outline=""
                            )
                            self.media_player.canvas.create_text(
                                bar_x + 20, legend_y + 7,
                                text=f"Images: {image_count}",
                                anchor="w",
                                fill="#FFFFFF",
                                font=("Segoe UI", 10)
                            )
                        
                        # Videos legend
                        if video_count > 0:
                            self.media_player.canvas.create_rectangle(
                                bar_x + legend_spacing, legend_y, 
                                bar_x + legend_spacing + 15, legend_y + 15, 
                                fill="#E91E63", outline=""
                            )
                            self.media_player.canvas.create_text(
                                bar_x + legend_spacing + 20, legend_y + 7,
                                text=f"Videos: {video_count}",
                                anchor="w",
                                fill="#FFFFFF",
                                font=("Segoe UI", 10)
                            )
                        
                        # Audio legend
                        if audio_count > 0:
                            self.media_player.canvas.create_rectangle(
                                bar_x + 2*legend_spacing, legend_y, 
                                bar_x + 2*legend_spacing + 15, legend_y + 15, 
                                fill="#FFC107", outline=""
                            )
                            self.media_player.canvas.create_text(
                                bar_x + 2*legend_spacing + 20, legend_y + 7,
                                text=f"Audio: {audio_count}",
                                anchor="w",
                                fill="#FFFFFF",
                                font=("Segoe UI", 10)
                            )
                        
                        # Text legend
                        if text_count > 0:
                            self.media_player.canvas.create_rectangle(
                                bar_x, legend_y + 25, 
                                bar_x + 15, legend_y + 40, 
                                fill="#4CAF50", outline=""
                            )
                            self.media_player.canvas.create_text(
                                bar_x + 20, legend_y + 32,
                                text=f"Text: {text_count}",
                                anchor="w",
                                fill="#FFFFFF",
                                font=("Segoe UI", 10)
                            )
                        
                        # Other legend
                        if other_count > 0:
                            self.media_player.canvas.create_rectangle(
                                bar_x + legend_spacing, legend_y + 25, 
                                bar_x + legend_spacing + 15, legend_y + 40, 
                                fill="#9E9E9E", outline=""
                            )
                            self.media_player.canvas.create_text(
                                bar_x + legend_spacing + 20, legend_y + 32,
                                text=f"Other: {other_count}",
                                anchor="w",
                                fill="#FFFFFF",
                                font=("Segoe UI", 10)
                            )
            
            # Add instructions at the bottom
            self.media_player.canvas.create_text(
                canvas_width // 2,
                canvas_height - 40,
                text="Select a file from the browser to view its contents",
                fill="#BBBBBB",
                font=("Segoe UI", 12)
            )
        else:
            # Add instruction when no file is loaded
            self.media_player.canvas.create_text(
                canvas_width // 2,
                canvas_height // 2,
                text="No GMODEL file loaded. Open a .gmodel file to view its contents.",
                fill="#BBBBBB",
                font=("Segoe UI", 14)
            )
    
    def _center_window(self):
        """Center the window on the screen"""
        self.root.update_idletasks()
        
        # Get window size
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()
        
        # Get screen dimensions
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Calculate position
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        # Set position
        self.root.geometry(f"+{x}+{y}")
    
    def load_file(self, file_path):
        """Load a GMODEL file"""
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                self._show_error(f"File not found: {file_path}")
                return False
                
            self.file_path = file_path
            
            # Update window title
            if self.owns_root:
                window_title = f"GMODEL Viewer - {os.path.basename(file_path)}"
                self.root.title(window_title)
                
                # Update title bar if using custom one
                if hasattr(self, 'use_custom_titlebar') and self.use_custom_titlebar and hasattr(self, 'title_bar'):
                    try:
                        self.title_bar.set_title(window_title)
                    except Exception as e:
                        logger.error(f"Error updating title bar: {e}")
            
            # Clean up any existing media playback
            if hasattr(self, 'video_state') and self.video_state:
                # Stop any running video thread
                if self.video_state.get("stop_event"):
                    self.video_state["stop_event"].set()
                
                # If there's a thread, wait for it to end
                if self.video_state.get("thread") and self.video_state["thread"].is_alive():
                    self.video_state["thread"].join(timeout=0.5)
                    
                # Release any video capture resources
                if self.video_state.get("cap"):
                    self.video_state["cap"].release()
            
            # Ensure media player controls are hidden
            if hasattr(self, 'media_player') and self.media_player:
                self.media_player.hide_controls()
                
            # Remove any canvas bindings from previous warnings
            self._unbind_video_warning()
                
            # Close any existing zipfile
            if self.zipfile:
                self.zipfile.close()
                
            # Open the zipfile
            self.zipfile = zipfile.ZipFile(file_path, 'r')
            
            # Load file browser
            success = self.file_browser.load_archive(file_path)
            
            # Show splash with file information
            self._show_splashscreen()
            
            return success
        except Exception as e:
            logger.error(f"Error loading file: {e}")
            self._show_error(f"Failed to load file: {str(e)}")
            return False
    
    def display_file(self, file_path):
        """Display a file from the archive in the media player"""
        if not self.zipfile or not file_path:
            return False
            
        try:
            # First destroy any existing video/media windows immediately
            self.media_player.canvas.delete("all")
            
            # Force removal of any embedded windows in the canvas
            for child in self.media_player.canvas.winfo_children():
                child.destroy()
            
            # Clean up previous preview completely before showing new one
            if self.current_file:
                # Full cleanup of video and media resources
                self._cleanup_video_player()
                
                # Clean up temp file
                self._cleanup_temp_file(self.current_file)
                
                # Remove any canvas bindings from previous warnings
                self._unbind_video_warning()
            
            # Get file data from archive
            try:
                file_info = self.zipfile.getinfo(file_path)
                file_data = self.zipfile.read(file_path)
            except KeyError:
                self._show_error(f"File not found in archive: {file_path}")
                return False
            
            # Store current file
            self.current_file = file_path
            
            # Update title and info
            self.preview_title.config(text="Preview: " + os.path.basename(file_path))
            self._update_file_info(file_info)
            
            # Determine file type and display accordingly
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                return self._display_image(file_data, file_path)
            elif file_ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
                try:
                    return self._display_video(file_data, file_path)
                except Exception as e:
                    logger.error(f"Error displaying video: {e}")
                    self._show_error(f"Error displaying video: The video format may be unsupported or file is corrupted.\n\nError: {str(e)[:100]}")
                    return False
            elif file_ext in ['.mp3', '.wav', '.ogg', '.flac']:
                try:
                    return self._display_audio(file_data, file_path)
                except Exception as e:
                    logger.error(f"Error playing audio: {e}")
                    self._show_error(f"Error playing audio: The audio format may be unsupported or file is corrupted.\n\nError: {str(e)[:100]}")
                    return False
            elif file_ext in ['.txt', '.json', '.xml', '.html', '.css', '.js', '.md']:
                return self._display_text(file_data, file_path)
            else:
                self._show_error(f"Unsupported file type: {file_ext}")
                return False
        except Exception as e:
            logger.error(f"Error displaying file: {e}")
            self._show_error(f"Error displaying file: {str(e)}")
            return False
    
    def _update_file_info(self, file_info):
        """Update file information display"""
        try:
            # Update filename
            self.file_name_label.config(text=os.path.basename(file_info.filename))
            
            # Update file size
            size_str = self._format_size(file_info.file_size)
            compressed_size_str = self._format_size(file_info.compress_size)
            compression_ratio = (1 - (file_info.compress_size / file_info.file_size)) * 100 if file_info.file_size > 0 else 0
            self.file_size_label.config(
                text=f"Size: {size_str} (Compressed: {compressed_size_str}, {compression_ratio:.1f}% saved)"
            )
            
            # Update date
            date_time = file_info.date_time
            date_str = datetime.datetime(
                year=date_time[0], 
                month=date_time[1], 
                day=date_time[2],
                hour=date_time[3],
                minute=date_time[4],
                second=date_time[5]
            ).strftime("%Y-%m-%d %H:%M:%S")
            self.file_date_label.config(text=f"Date: {date_str}")
            
        except Exception as e:
            logger.error(f"Error updating file info: {e}")
            self.file_name_label.config(text=os.path.basename(file_info.filename))
            self.file_size_label.config(text="")
            self.file_date_label.config(text="")
    
    def _format_size(self, size_bytes):
        """Format file size in human-readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    
    def delete_file(self, file_path):
        """Delete a file from the archive"""
        if not self.zipfile or not self.file_path:
            return False
        
        try:
            logger.info(f"Deleting file: {file_path}")
            
            # Close current zipfile
            self.zipfile.close()
            self.zipfile = None
            
            # Create a new temporary zip file
            temp_zip_path = f"{self.file_path}.temp"
            
            # Open the original file
            with zipfile.ZipFile(self.file_path, 'r') as source_zip:
                # Create a new zip file
                with zipfile.ZipFile(temp_zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as target_zip:
                    # Copy all files except the one to delete
                    for item in source_zip.infolist():
                        if item.filename != file_path:
                            data = source_zip.read(item.filename)
                            target_zip.writestr(item, data)
            
            # Replace the original file
            os.remove(self.file_path)
            os.rename(temp_zip_path, self.file_path)
            
            # Reopen the file
            self.zipfile = zipfile.ZipFile(self.file_path, 'r')
            
            # If the current file is the deleted one, clear the view
            if self.current_file == file_path:
                self.current_file = None
                self._show_splashscreen()
            
            logger.info(f"File deleted successfully: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            self._show_error(f"Error deleting file:\n{str(e)}")
            
            # Attempt to reopen the original file
            try:
                if self.zipfile is None:
                    self.zipfile = zipfile.ZipFile(self.file_path, 'r')
            except:
                pass
                
            return False
    
    def _display_image(self, image_data, file_path):
        """Display an image file"""
        try:
            # Load the image in the media player
            success = self.media_player.load_image(image_data, file_path)
            return success
        except Exception as e:
            logger.error(f"Error displaying image: {e}")
            self._show_error(f"Error displaying image: {str(e)}")
            return False
            
    def _display_video(self, video_data, file_path):
        """Display a video file with better handling for preview"""
        try:
            # Create a temporary file for the video
            temp_file_path = self._create_temp_file(video_data, file_path)
            if not temp_file_path:
                return False
            
            # Get video info before loading
            try:
                import cv2
                video_size = os.path.getsize(temp_file_path)
                
                # Extract frame preview regardless of video size
                success, preview_frame = self._extract_video_preview_frame(temp_file_path)
                if not success:
                    logger.warning("Could not extract preview frame, proceeding with normal loading")
                
                # Get video dimensions and info
                vcap = cv2.VideoCapture(temp_file_path)
                if vcap.isOpened():
                    width = int(vcap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(vcap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    frame_count = int(vcap.get(cv2.CAP_PROP_FRAME_COUNT))
                    fps = vcap.get(cv2.CAP_PROP_FPS)
                    duration = frame_count / fps if fps > 0 else 0
                    duration_formatted = self._format_time_long(duration)
                    vcap.release()
                    
                    dimensions_text = f"{width}x{height}, {frame_count} frames"
                    very_high_res = width * height > 1920 * 1080
                else:
                    dimensions_text = "unknown dimensions"
                    very_high_res = False
                    duration_formatted = "unknown duration"
                
                # Determine safe size thresholds based on resolution
                MAX_SAFE_VIDEO_SIZE = 30 * 1024 * 1024  # 30MB base threshold
                VERY_LARGE_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB
                
                # Adjust thresholds based on resolution
                if very_high_res:
                    MAX_SAFE_VIDEO_SIZE = MAX_SAFE_VIDEO_SIZE // 2  # More conservative for high-res
                
                # Display enhanced preview with video info and play options
                if success and preview_frame is not None:
                    return self._display_video_preview_with_options(
                        preview_frame, 
                        temp_file_path, 
                        video_size, 
                        dimensions_text, 
                        duration_formatted,
                        is_very_large=(video_size > VERY_LARGE_VIDEO_SIZE),
                        is_large=(video_size > MAX_SAFE_VIDEO_SIZE),
                        is_high_res=very_high_res
                    )
                
                # Fallback to standard size-based warnings if preview frame extraction failed
                if video_size > VERY_LARGE_VIDEO_SIZE or (very_high_res and video_size > MAX_SAFE_VIDEO_SIZE):
                    # Show strong warning for very large videos
                    self._show_large_video_warning(
                        temp_file_path, 
                        video_size, 
                        dimensions_text, 
                        is_very_large=True
                    )
                    return True
                elif video_size > MAX_SAFE_VIDEO_SIZE:
                    # Standard warning for large videos
                    self._show_large_video_warning(
                        temp_file_path, 
                        video_size, 
                        dimensions_text, 
                        is_very_large=False
                    )
                    return True
                else:
                    # Video is a safe size, proceed with normal loading
                    return self._load_video_with_safeguards(temp_file_path)
            except Exception as e:
                logger.error(f"Error analyzing video: {e}")
                # If we can't check size, proceed with normal loading
                return self._load_video_with_safeguards(temp_file_path)
        except Exception as e:
            logger.error(f"Error displaying video: {e}")
            self._show_error(f"Error displaying video: {str(e)}")
            return False

    def _format_time_long(self, seconds):
        """Format time in HH:MM:SS format"""
        if seconds is None or seconds <= 0:
            return "unknown duration"
            
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"

    def _extract_video_preview_frame(self, video_path):
        """Extract a representative frame from the video for preview"""
        try:
            import cv2
            # Open the video file
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return False, None
            
            # Get video properties
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if frame_count <= 0:
                # Try to read at least the first frame
                ret, frame = cap.read()
                cap.release()
                return ret, frame
            
            # Try to get a frame about 20% into the video for a more representative preview
            target_frame = min(int(frame_count * 0.2), 50)  # Don't go too far in large videos
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            
            # Read the frame
            ret, frame = cap.read()
            
            # If failed, try first frame
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
            
            # Release the capture object
            cap.release()
            
            return ret, frame
        except Exception as e:
            logger.error(f"Error extracting preview frame: {e}")
            return False, None

    def _display_video_preview_with_options(self, preview_frame, video_path, 
                                           video_size, dimensions_text, duration, 
                                           is_very_large=False, is_large=False, is_high_res=False):
        """Display a video preview with play options and information"""
        try:
            self.media_player.canvas.delete("all")
            canvas_width = self.media_player.canvas.winfo_width() or 600
            canvas_height = self.media_player.canvas.winfo_height() or 400
            
            # Convert the frame to PIL Image
            frame_rgb = cv2.cvtColor(preview_frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame_rgb)
            
            # Calculate scaling to fit canvas with padding
            img_width, img_height = image.size
            scale_width = (canvas_width - 40) / img_width if img_width > 0 else 1
            scale_height = (canvas_height - 120) / img_height if img_height > 0 else 1
            scale = min(scale_width, scale_height, 1.0)  # Don't enlarge
            
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
            
            # Resize image if needed
            if scale < 1.0:
                resized_img = image.resize((new_width, new_height), Image.LANCZOS)
                preview_image = resized_img
            else:
                preview_image = image
                
            # Create PhotoImage
            photo = ImageTk.PhotoImage(preview_image)
            
            # Calculate position to center image
            x = (canvas_width - new_width) // 2
            y = 60  # Leave space for headers
            
            # Create image on canvas
            image_id = self.media_player.canvas.create_image(x, y, anchor=tk.NW, image=photo)
            
            # Store reference to prevent garbage collection
            self.media_player._preview_photo = photo
            
            # Add semi-transparent overlay at the bottom of the preview
            overlay_height = 40
            self.media_player.canvas.create_rectangle(
                x, y + new_height - overlay_height,
                x + new_width, y + new_height,
                fill="#000000",
                stipple="gray50",  # Semi-transparent effect
                outline=""
            )
            
            # Add video info to the bottom overlay
            video_size_str = self._format_size(video_size)
            info_text = f"{dimensions_text} • {duration} • {video_size_str}"
            
            self.media_player.canvas.create_text(
                x + new_width // 2,
                y + new_height - (overlay_height // 2),
                text=info_text,
                fill="#FFFFFF",
                font=("Segoe UI", 9)
            )
            
            # Create title bar
            title_height = 40
            title_y = 10
            
            # Add warning color if needed
            title_color = "#FFFFFF"
            title_bg = "#121212"
            warning_icon = ""
            
            if is_very_large:
                title_color = "#FF5252"
                title_bg = "#331111"
                warning_icon = "⚠️ "
            elif is_large:
                title_color = "#FFC107"
                title_bg = "#332211"
                warning_icon = "⚠️ "
            
            # Title background
            self.media_player.canvas.create_rectangle(
                20, title_y,
                canvas_width - 20, title_y + title_height,
                fill=title_bg,
                outline="#333333"
            )
            
            # Title text
            title_text = f"{warning_icon}Video Preview"
            if is_very_large:
                title_text += " (Very Large File)"
            elif is_large:
                title_text += " (Large File)"
                
            self.media_player.canvas.create_text(
                canvas_width // 2,
                title_y + title_height // 2,
                text=title_text,
                fill=title_color,
                font=("Segoe UI", 12, "bold")
            )
            
            # Create buttons at the bottom
            button_y = y + new_height + 20
            button_height = 36
            button_width = 180
            button_spacing = 20
            
            # Draw playback options based on video size
            if is_very_large:
                # Option 1: Play first few frames only (safest option)
                safe_play_button = self._create_canvas_button(
                    self.media_player.canvas,
                    canvas_width // 2 - button_width - button_spacing,
                    button_y,
                    button_width,
                    button_height,
                    "View Static Frame",
                    bg_color="#1b5e20",
                    outline_color="#4CAF50"
                )
                
                # Option 2: Try with safety measures (riskier)
                full_play_button = self._create_canvas_button(
                    self.media_player.canvas,
                    canvas_width // 2 + button_spacing,
                    button_y,
                    button_width,
                    button_height,
                    "Play with Safety Mode",
                    bg_color="#663c00",
                    outline_color="#FFC107"
                )
            else:
                # Normal play button (centered)
                play_button = self._create_canvas_button(
                    self.media_player.canvas,
                    canvas_width // 2 - button_width // 2,
                    button_y,
                    button_width,
                    button_height,
                    "Play Video",
                    bg_color="#1a237e",
                    outline_color="#3F51B5"
                )
            
            # Bind canvas click event for buttons
            def on_canvas_click(event):
                x, y = event.x, event.y
                
                # Get button positions based on video size
                if is_very_large:
                    # Check if click is on safe play button
                    safe_btn_x1 = canvas_width // 2 - button_width - button_spacing
                    safe_btn_x2 = safe_btn_x1 + button_width
                    safe_btn_y1 = button_y
                    safe_btn_y2 = button_y + button_height
                    
                    # Check if click is on full play button
                    full_btn_x1 = canvas_width // 2 + button_spacing
                    full_btn_x2 = full_btn_x1 + button_width
                    full_btn_y1 = button_y
                    full_btn_y2 = button_y + button_height
                    
                    if safe_btn_x1 <= x <= safe_btn_x2 and safe_btn_y1 <= y <= safe_btn_y2:
                        # Static frame option
                        self._unbind_video_warning()
                        self._display_video_first_frame(video_path)
                    elif full_btn_x1 <= x <= full_btn_x2 and full_btn_y1 <= y <= full_btn_y2:
                        # Try playback with safety measures
                        self._unbind_video_warning()
                        self._load_video_with_extreme_safeguards(video_path)
                else:
                    # Check if click is on play button
                    play_btn_x1 = canvas_width // 2 - button_width // 2
                    play_btn_x2 = play_btn_x1 + button_width
                    play_btn_y1 = button_y
                    play_btn_y2 = button_y + button_height
                    
                    if play_btn_x1 <= x <= play_btn_x2 and play_btn_y1 <= y <= play_btn_y2:
                        # Normal playback
                        self._unbind_video_warning()
                        self._load_video_with_safeguards(video_path)
            
            # Bind the click event
            self.media_player.canvas.bind("<Button-1>", on_canvas_click)
            self._bound_warning = True
            
            # Hide media player controls as we're showing our custom UI
            self.media_player.hide_controls()
            
            return True
        except Exception as e:
            logger.error(f"Error displaying video preview: {e}")
            # Fall back to normal loading if preview fails
            return self._load_video_with_safeguards(video_path)

    def _create_canvas_button(self, canvas, x, y, width, height, text, bg_color="#333333", outline_color="#555555"):
        """Create a button on the canvas and return its ID"""
        # Create the button rectangle
        button = canvas.create_rectangle(
            x, y,
            x + width, y + height,
            fill=bg_color,
            outline=outline_color
        )
        
        # Create the button text
        text_id = canvas.create_text(
            x + width // 2,
            y + height // 2,
            text=text,
            fill="#FFFFFF",
            font=("Segoe UI", 11, "bold")
        )
        
        return (button, text_id)

    def _show_large_video_warning(self, temp_file_path, video_size, dimensions_text, is_very_large=False):
        """Show a warning for large videos"""
        self.media_player.canvas.delete("all")
        canvas_width = self.media_player.canvas.winfo_width() or 600
        canvas_height = self.media_player.canvas.winfo_height() or 400
        
        # Background style based on severity
        if is_very_large:
            # Strong warning style
            bg_color = "#331111"  # Dark red
            outline_color = "#FF5252"  # Brighter red
            title = "⚠️ Very Large Video Warning ⚠️"
            title_color = "#FF5252"
        else:
            # Standard warning style
            bg_color = "#232323"
            outline_color = "#FFC107"  # Warning amber
            title = "Large Video Warning"
            title_color = "#FFC107"
        
        # Background
        self.media_player.canvas.create_rectangle(
            50, 50,
            canvas_width - 50, canvas_height - 50,
            fill=bg_color,
            outline=outline_color
        )
        
        # Warning title
        self.media_player.canvas.create_text(
            canvas_width // 2,
            80,
            text=title,
            fill=title_color,
            font=("Segoe UI", 18, "bold")
        )
        
        # Warning message
        video_size_str = self._format_size(video_size)
        
        if is_very_large:
            warning_message = (
                f"This video is {video_size_str} ({dimensions_text}) and may crash the viewer.\n\n"
                f"Would you like to:\n"
                f"• Try anyway with safety measures\n"
                f"• View a single frame (safe)\n"
                f"• Cancel viewing"
            )
        else:
            warning_message = (
                f"This video is {video_size_str} ({dimensions_text}) which may cause instability.\n\n"
                f"Do you still want to play it?\n"
                f"Click anywhere in this box to play, or Cancel to skip."
            )
        
        self.media_player.canvas.create_text(
            canvas_width // 2,
            canvas_height // 2 - 30,
            text=warning_message,
            fill="#FFFFFF",
            font=("Segoe UI", 12),
            width=canvas_width - 150,  # Wrap text
            justify=tk.CENTER
        )
        
        # Create buttons based on severity
        if is_very_large:
            # Create buttons with better visual design
            button_width = 180
            button_height = 40
            button_spacing = 20
            button_y = canvas_height - 120
            
            # Try anyway button (yellow warning)
            try_button = self.media_player.canvas.create_rectangle(
                canvas_width // 2 - button_width - button_spacing,
                button_y,
                canvas_width // 2 - button_spacing,
                button_y + button_height,
                fill="#663c00",
                outline="#FFC107"
            )
            
            try_text = self.media_player.canvas.create_text(
                canvas_width // 2 - button_width//2 - button_spacing,
                button_y + button_height//2,
                text="Try With Safety Mode",
                fill="#FFFFFF",
                font=("Segoe UI", 11, "bold")
            )
            
            # Frame only button (green - safest)
            frame_button = self.media_player.canvas.create_rectangle(
                canvas_width // 2,
                button_y,
                canvas_width // 2 + button_width,
                button_y + button_height,
                fill="#1b5e20",
                outline="#4CAF50"
            )
            
            frame_text = self.media_player.canvas.create_text(
                canvas_width // 2 + button_width//2,
                button_y + button_height//2,
                text="View Frame Only",
                fill="#FFFFFF",
                font=("Segoe UI", 11, "bold")
            )
            
            # Cancel button (placed at bottom)
            cancel_button = self.media_player.canvas.create_rectangle(
                canvas_width // 2 - 75,
                button_y + button_height + 20,
                canvas_width // 2 + 75,
                button_y + button_height + 60,
                fill="#333333",
                outline="#BBBBBB"
            )
            
            cancel_text = self.media_player.canvas.create_text(
                canvas_width // 2,
                button_y + button_height + 40,
                text="Cancel",
                fill="#FFFFFF",
                font=("Segoe UI", 11, "bold")
            )
        else:
            # Standard cancel button
            cancel_button = self.media_player.canvas.create_rectangle(
                canvas_width // 2 - 75, canvas_height - 100,
                canvas_width // 2 + 75, canvas_height - 60,
                fill="#333333",
                outline="#FFC107"
            )
            
            cancel_text = self.media_player.canvas.create_text(
                canvas_width // 2,
                canvas_height - 80,
                text="Cancel",
                fill="#FFFFFF",
                font=("Segoe UI", 12, "bold")
            )
        
        # Bind click events
        def on_canvas_click(event):
            x, y = event.x, event.y
            
            if is_very_large:
                # Check if click is on try button
                if (canvas_width // 2 - button_width - button_spacing <= x <= canvas_width // 2 - button_spacing and
                    button_y <= y <= button_y + button_height):
                    # Try with safety mode
                    self._unbind_video_warning()
                    self._load_video_with_extreme_safeguards(temp_file_path)
                
                # Check if click is on frame button
                elif (canvas_width // 2 <= x <= canvas_width // 2 + button_width and
                      button_y <= y <= button_y + button_height):
                    # View single frame
                    self._unbind_video_warning()
                    self._display_video_first_frame(temp_file_path)
                
                # Check if click is on cancel button
                elif (canvas_width // 2 - 75 <= x <= canvas_width // 2 + 75 and
                      button_y + button_height + 20 <= y <= button_y + button_height + 60):
                    # Cancel
                    self._unbind_video_warning()
                    self._show_error("Video playback cancelled.")
            else:
                # Check if click is within the warning rectangle
                if 50 <= x <= canvas_width - 50 and 50 <= y <= canvas_height - 50:
                    # If click is on the cancel button
                    if canvas_width // 2 - 75 <= x <= canvas_width // 2 + 75 and canvas_height - 100 <= y <= canvas_height - 60:
                        # Cancel playback
                        self._unbind_video_warning()
                        self._show_error("Video playback cancelled.")
                    else:
                        # Proceed with playback
                        self._unbind_video_warning()
                        self._load_video_with_safeguards(temp_file_path)
        
        # Bind the click event
        self.media_player.canvas.bind("<Button-1>", on_canvas_click)
        self._bound_warning = True
    
    def _display_audio(self, audio_data, file_path):
        """Display an audio file with error handling"""
        try:
            # Create a temporary file for the audio
            temp_file_path = self._create_temp_file(audio_data, file_path)
            if not temp_file_path:
                return False
                
            # Try to load the audio
            success = self.media_player.load_audio(temp_file_path)
            return success
        except Exception as e:
            logger.error(f"Error playing audio: {e}")
            self._show_error(f"Error playing audio: {str(e)}")
            return False
    
    def _create_temp_file(self, file_data, file_path):
        """Create a temporary file from binary data"""
        try:
            # Make sure temp directory exists
            if not self.temp_dir or not os.path.exists(self.temp_dir):
                self.temp_dir = tempfile.mkdtemp(prefix="gmodel_")
                
            # Create temporary file
            temp_file_path = os.path.join(self.temp_dir, os.path.basename(file_path))
            with open(temp_file_path, 'wb') as f:
                f.write(file_data)
            
            return temp_file_path
        except Exception as e:
            logger.error(f"Error creating temporary file: {e}")
            self._show_error(f"Error creating temporary file: {str(e)}")
            return None
    
    def _cleanup_temp_file(self, file_path):
        """Clean up temporary file if it exists"""
        if not self.temp_dir or not file_path:
            return
            
        try:
            # Get base filename
            base_name = os.path.basename(file_path)
            temp_file_path = os.path.join(self.temp_dir, base_name)
            
            # Delete if exists
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                logger.debug(f"Cleaned up temp file: {temp_file_path}")
        except Exception as e:
            logger.error(f"Error cleaning up temp file: {e}")
            # Continue anyway
    
    def _display_text(self, file_data, file_path):
        """Display text content"""
        # Clear media player
        self.media_player.canvas.delete("all")
        
        try:
            # Try to decode text content
            try:
                # Try UTF-8 first
                text_content = file_data.decode('utf-8')
            except UnicodeDecodeError:
                # Fall back to Latin-1
                text_content = file_data.decode('latin-1')
                
            # Create text display
            text_width = self.media_player.canvas.winfo_width() - 40
            text_height = self.media_player.canvas.winfo_height() - 40
            
            # Create text widget for scrollable content
            text_frame = ttk.Frame(self.media_player.canvas, style='Main.TFrame')
            
            # Configure text widget with custom style for dark theme
            text_widget = tk.Text(
                text_frame,
                wrap=tk.WORD,
                bg='#121212',
                fg='#FFFFFF',
                insertbackground='#FFFFFF',
                selectbackground='#BB86FC',
                selectforeground='#FFFFFF',
                borderwidth=0,
                highlightthickness=0,
                width=80,
                height=30
            )
            
            # Create custom scrollbar with transparent style
            scrollbar = CustomScrollbar(
                text_frame,
                orient="vertical",
                command=text_widget.yview
            )
            text_widget.configure(yscrollcommand=scrollbar.set)
            
            # Pack widgets
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)
            
            # Insert text content
            text_widget.insert(tk.END, text_content)
            text_widget.config(state=tk.DISABLED)  # Make read-only
            
            # Create window in canvas to display text frame
            window_id = self.media_player.canvas.create_window(
                20, 20,
                anchor=tk.NW,
                window=text_frame,
                width=text_width,
                height=text_height
            )
            
            # Hide controls for text files
            self.media_player.hide_controls()
            
            return True
        except Exception as e:
            logger.error(f"Error displaying text: {e}")
            self._show_error(f"Error displaying text: {str(e)}")
            return False
    
    def _show_error(self, message):
        """Display an error message"""
        if not hasattr(self, 'media_player') or self.media_player is None:
            logger.error(f"Cannot show error UI: {message}")
            return
            
        # Update preview title
        self.preview_title.config(text="Error")
            
        self.media_player.canvas.delete("all")
        
        # Get canvas dimensions
        canvas_width = self.media_player.canvas.winfo_width() or 600
        canvas_height = self.media_player.canvas.winfo_height() or 400
        
        # Background
        self.media_player.canvas.create_rectangle(
            50, 50,
            canvas_width - 50, canvas_height - 50,
            fill="#271c24",  # Dark red background
            outline="#CF6679"  # Error color
        )
        
        # Error title
        self.media_player.canvas.create_text(
            canvas_width // 2,
            100,
            text="Error",
            fill="#CF6679",
            font=("Segoe UI", 18, "bold")
        )
        
        # Error message
        self.media_player.canvas.create_text(
            canvas_width // 2,
            canvas_height // 2,
            text=message,
            fill="#FFFFFF",
            font=("Segoe UI", 12),
            width=canvas_width - 150  # Wrap text
        )
    
    def close(self):
        """Close the viewer"""
        # Clean up resources
        self._cleanup_resources()
        
        # Destroy window if we own it
        if self.owns_root:
            self.root.destroy()
    
    def _cleanup_resources(self):
        """Clean up resources"""
        # Clean up any video state resources
        if hasattr(self, 'video_state') and self.video_state:
            try:
                # Stop any running video thread
                if self.video_state.get("stop_event"):
                    self.video_state["stop_event"].set()
                
                # If there's a thread, wait for it to end
                if self.video_state.get("thread") and self.video_state["thread"].is_alive():
                    self.video_state["thread"].join(timeout=0.5)
                    
                # Release any video capture resources
                if self.video_state.get("cap"):
                    self.video_state["cap"].release()
            except Exception as e:
                logger.error(f"Error cleaning up video resources: {e}")
        
        # Clean up media player
        if hasattr(self, 'media_player') and self.media_player is not None:
            try:
                self.media_player._reset_video()
                self.media_player._stop_audio()
                self.media_player.hide_controls()
            except Exception as e:
                logger.error(f"Error cleaning up media player: {e}")
        
        # Close zipfile if open
        if self.zipfile:
            try:
                self.zipfile.close()
            except Exception as e:
                logger.error(f"Error closing zipfile: {e}")
            self.zipfile = None
        
        # Clean up temp directory
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                logger.error(f"Error removing temp directory: {e}")
            self.temp_dir = None
        
        # Create a new temp directory
        self.temp_dir = tempfile.mkdtemp(prefix="gmodel_")
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        try:
            self._cleanup_resources()
        except:
            pass
    
    def _close_preview(self):
        """Close the current preview and show GMODEL information"""
        # Immediately remove any video UI
        self.media_player.canvas.delete("all")
        
        # Force removal of any embedded windows in the canvas
        for child in self.media_player.canvas.winfo_children():
            child.destroy()
        
        # Clear current file
        self.current_file = None
        
        # Thorough cleanup of video player and media resources
        self._cleanup_video_player()
            
        # Show splash screen with GMODEL info
        self._show_splashscreen()
        
        # Unselect any item in the file browser
        if hasattr(self, 'file_browser') and self.file_browser:
            try:
                self.file_browser.tree.selection_remove(self.file_browser.tree.selection())
            except:
                pass
    
    def _create_icon(self):
        """Create and set a window icon"""
        try:
            # Try to load @icon.png first
            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(script_dir))
            icon_path = os.path.join(project_root, "assets", "@icon.png")
            
            # If @icon.png doesn't exist, try icon.png
            if not os.path.exists(icon_path):
                icon_path = os.path.join(project_root, "assets", "icon.png")
            
            # If icon.ico exists, use it directly on Windows
            icon_ico_path = os.path.join(project_root, "assets", "icon.ico")
            
            if os.path.exists(icon_path) or os.path.exists(icon_ico_path):
                # For taskbar icon on Windows
                if os.name == 'nt':
                    if os.path.exists(icon_ico_path):
                        # Use existing .ico file directly
                        self.root.iconbitmap(default=icon_ico_path)
                        logger.debug(f"Using existing icon.ico for taskbar")
                    else:
                        try:
                            # Use PIL to load the icon
                            icon = Image.open(icon_path)
                            
                            # Create a temporary file for the .ico
                            with tempfile.NamedTemporaryFile(suffix='.ico', delete=False) as temp_file:
                                icon.save(temp_file.name)
                                # Set the window icon - specifically for taskbar
                                self.root.iconbitmap(default=temp_file.name)
                            
                            # We can now delete the temporary file
                            try:
                                os.unlink(temp_file.name)
                            except:
                                pass
                        except Exception as e:
                            logger.error(f"Error creating ICO for taskbar: {e}")
                            # Fallback: Try using the PNG directly
                            self.root.iconphoto(True, tk.PhotoImage(file=icon_path))
                else:
                    # For non-Windows platforms
                    self.root.iconphoto(True, tk.PhotoImage(file=icon_path))
            else:
                # If neither icon file exists, create a basic icon
                logger.warning(f"Icon not found at {icon_path}, creating default icon")
                self._create_default_icon()
        except Exception as e:
            logger.error(f"Error setting window icon: {e}")
            # Create a default icon as fallback
            self._create_default_icon()
            
    def _create_default_icon(self):
        """Create a default icon when the standard icon isn't available"""
        try:
            # Create a small colored square as the icon
            img = Image.new('RGBA', (64, 64), color=(70, 130, 180, 255))  # Steel blue color
            
            # Add some simple graphics to make it recognizable
            draw = ImageDraw.Draw(img)
            
            # Draw 'G' in the center
            try:
                # Try to use a built-in font
                font = ImageFont.truetype("arial.ttf", 36)
            except:
                # Fallback to default font
                font = ImageFont.load_default()
                
            # Draw text centered
            draw.text((32, 32), "G", fill="white", font=font, anchor="mm")
            
            # Convert to PhotoImage for Tkinter
            photo_image = ImageTk.PhotoImage(img)
            
            # Set as window icon
            self.root.iconphoto(True, photo_image)
            
            # Store reference to prevent garbage collection
            self._icon_image = photo_image
        except Exception as e:
            logger.error(f"Error creating default icon: {e}")
            # No further fallback - will use system default icon 

    def _unbind_video_warning(self):
        """Remove video warning click bindings"""
        if hasattr(self, '_bound_warning') and self._bound_warning:
            try:
                self.media_player.canvas.unbind("<Button-1>")
                self._bound_warning = False
            except:
                pass
    
    def _load_video_with_safeguards(self, video_path):
        """Load video with safeguards against crashes using pygame"""
        try:
            # Clear canvas before loading
            self.media_player.canvas.delete("all")
            
            # Create loading message
            canvas_width = self.media_player.canvas.winfo_width() or 600
            canvas_height = self.media_player.canvas.winfo_height() or 400
            
            loading_id = self.media_player.canvas.create_text(
                canvas_width // 2,
                canvas_height // 2,
                text="Loading video...",
                fill="#FFFFFF",
                font=("Segoe UI", 14)
            )
            self.media_player.canvas.update()  # Force update
            
            # Try to use custom pygame playback with reduced flickering
            try:
                # Create a full-screen embedded frame for the video player
                video_frame = tk.Frame(
                    self.media_player.canvas,
                    bg="#000000",
                    highlightthickness=0
                )
                
                # Calculate dimensions that maintain aspect ratio
                vid_width, vid_height = self._get_video_dimensions(video_path)
                
                # Place the video frame on the canvas
                window_id = self.media_player.canvas.create_window(
                    canvas_width // 2,  # Center horizontally
                    canvas_height // 2,  # Center vertically
                    window=video_frame,
                    width=canvas_width - 20,
                    height=canvas_height - 70,  # Leave space for controls
                    anchor=tk.CENTER
                )
                
                # Initialize our custom video player
                success = self._init_custom_video_player(video_frame, video_path)
                
                if success:
                    return True
                else:
                    # Fall back to OpenCV if custom player fails
                    self.media_player.canvas.delete(window_id)
                    return self._load_video_with_cv2(video_path)
            except Exception as e:
                logger.error(f"Error initializing custom video player: {e}")
                # Fall back to OpenCV
                return self._load_video_with_cv2(video_path)
                
        except Exception as e:
            logger.error(f"Error loading video: {e}")
            self._show_error(f"Error loading video: The video format may be unsupported or corrupted.")
            return False

    def _get_video_dimensions(self, video_path):
        """Get video dimensions using OpenCV"""
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                return width, height
            else:
                cap.release()
                return 640, 480  # Default dimensions
        except Exception as e:
            logger.error(f"Error getting video dimensions: {e}")
            return 640, 480  # Default dimensions
            
    def _init_custom_video_player(self, frame, video_path):
        """Initialize a high-performance OpenCV video player"""
        import cv2
        import threading
        
        # Video player state with default values
        self.video_state = {
            "playing": True,
            "cap": None,
            "canvas": None,
            "frame_container": None,
            "thread": None,
            "stop_event": threading.Event(),
            "current_frame": None,
            "frame_count": 0,
            "duration": 0,
            "fps": 0,
            "current_position": 0,
            "paused": False,
            "seek_position": None,  # Used for seeking
            "is_seeking": False,
            "was_playing": False
        }
        
        # Create a black canvas for the video
        self.video_state["frame_container"] = tk.Frame(frame, bg="black")
        self.video_state["frame_container"].pack(fill=tk.BOTH, expand=True)
        
        # Create a canvas for drawing directly
        canvas_width = frame.winfo_width() or 640
        canvas_height = frame.winfo_height() or 480
        
        self.video_state["canvas"] = tk.Canvas(
            self.video_state["frame_container"],
            bg="black",
            width=canvas_width,
            height=canvas_height,
            highlightthickness=0
        )
        self.video_state["canvas"].pack(fill=tk.BOTH, expand=True)
        
        # Create controls frame with darker background
        controls_frame = tk.Frame(frame, bg="#111111")
        controls_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        # Top row for seek bar
        seek_frame = tk.Frame(controls_frame, bg="#111111")
        seek_frame.pack(fill=tk.X, padx=5, pady=(5, 0))
        
        # Create seek bar using Scale widget
        self.seek_var = tk.DoubleVar(value=0)
        
        # Configure style for transparent seek bar
        style = ttk.Style()
        style.configure("Transparent.Horizontal.TScale",
                       background="#111111",  # Match controls background
                       troughcolor="#333333",  # Subtle dark gray for trough
                       slidercolor="#BB86FC",  # Purple accent color for slider
                       sliderthickness=15,     # Make slider more visible
                       sliderlength=15,        # Square slider shape
                       borderwidth=0)          # No border
        
        self.seek_bar = ttk.Scale(
            seek_frame,
            orient="horizontal",
            variable=self.seek_var,
            from_=0,
            to=100,  # Will be updated with actual frame count
            command=self._on_seek,
            style="Transparent.Horizontal.TScale"
        )
        self.seek_bar.pack(fill=tk.X, expand=True)
        
        # Bottom row for control buttons
        buttons_frame = tk.Frame(controls_frame, bg="#111111")
        buttons_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        # Play/Pause button
        self.play_pause_btn = tk.Button(
            buttons_frame, 
            text="⏸", 
            command=self._toggle_video_playback,
            bg="#222222", fg="white",
            font=("Segoe UI", 10),
            width=2,
            bd=0,
            highlightthickness=0
        )
        self.play_pause_btn.pack(side=tk.LEFT, padx=5, pady=2)
        
        # Reset button
        self.reset_btn = tk.Button(
            buttons_frame, 
            text="↺", 
            command=self._reset_video_position,
            bg="#222222", fg="white",
            font=("Segoe UI", 10),
            width=2,
            bd=0,
            highlightthickness=0
        )
        self.reset_btn.pack(side=tk.LEFT, padx=2, pady=2)
        
        # Position label
        self.position_label = tk.Label(
            buttons_frame,
            text="0:00 / 0:00",
            bg="#111111", fg="white",
            font=("Segoe UI", 9)
        )
        self.position_label.pack(side=tk.RIGHT, padx=5, pady=2)
        
        # Start video thread
        self.video_state["stop_event"].clear()
        self.video_state["thread"] = threading.Thread(
            target=self._optimized_video_thread,
            args=(video_path,),
            daemon=True
        )
        self.video_state["thread"].start()
        
        return True
    
    def _on_seek(self, value):
        """Handle seek bar value change"""
        if not hasattr(self, 'video_state') or not self.video_state.get("cap"):
            return
            
        try:
            # Convert value to frame position
            value = float(value)
            if self.video_state["frame_count"] > 0:
                frame_pos = int((value / 100.0) * self.video_state["frame_count"])
                
                # Remember playback state before seeking - only on first seek event
                if not self.video_state.get("is_seeking", False):
                    self.video_state["was_playing"] = not self.video_state.get("paused", False)
                    self.video_state["is_seeking"] = True
                
                # Pause the video while seeking
                self.video_state["paused"] = True
                
                # Update play/pause button to show play icon
                if hasattr(self, 'play_pause_btn') and self.play_pause_btn.winfo_exists():
                    self.play_pause_btn.config(text="▶")
                
                # Set a flag to indicate a seek operation
                self.video_state["seek_position"] = frame_pos
                
                # Schedule end of seeking for this event
                if hasattr(self, 'root') and self.root.winfo_exists():
                    # Cancel any previous end_seek callback
                    if hasattr(self, '_end_seek_id') and self._end_seek_id:
                        self.root.after_cancel(self._end_seek_id)
                    
                    # Set a new callback for after scrubbing
                    self._end_seek_id = self.root.after(500, self._end_seek)
                    
        except Exception as e:
            logger.error(f"Error seeking video: {e}")
    
    def _end_seek(self):
        """Called after scrubbing ends to restore previous playback state"""
        if not hasattr(self, 'video_state'):
            return
            
        try:
            if self.video_state.get("is_seeking", False):
                # Clear seeking flag
                self.video_state["is_seeking"] = False
                
                # Restore previous playback state if it was playing
                if self.video_state.get("was_playing", False):
                    self.video_state["paused"] = False
                    
                    # Update play/pause button to show pause icon
                    if hasattr(self, 'play_pause_btn') and self.play_pause_btn.winfo_exists():
                        self.play_pause_btn.config(text="⏸")
        except Exception as e:
            logger.error(f"Error ending seek: {e}")
    
    def _optimized_video_thread(self, video_path):
        """High-performance video playback thread using OpenCV"""
        import cv2
        import time
        import queue
        import threading
        from PIL import Image, ImageTk
        import numpy as np
        
        try:
            # Open video capture
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                self._show_error("Failed to open video file")
                return
                
            # Store the capture object
            self.video_state["cap"] = cap
            
            # Get video properties
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.video_state["fps"] = cap.get(cv2.CAP_PROP_FPS) or 30
            self.video_state["frame_count"] = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Update seek bar range with actual frame count
            if hasattr(self, 'seek_bar') and self.video_state["frame_count"] > 0:
                self.seek_bar.config(to=100)  # Keep as percentage for smoother UI
            
            # Calculate video duration
            if self.video_state["fps"] > 0:
                self.video_state["duration"] = self.video_state["frame_count"] / self.video_state["fps"]
            
            # Create a queue for frames (prebuffer a few frames)
            frame_queue = queue.Queue(maxsize=5)
            
            # Flag to signal prebuffer completion
            prebuffer_done = threading.Event()
            
            # Calculate target frame rate (cap at 30fps for smooth UI)
            target_fps = min(30, self.video_state["fps"])
            frame_delay = 1.0 / target_fps if target_fps > 0 else 0.033  # 33ms default
            
            # Save preview frame at start
            original_preview_frame = None
            ret, first_frame = cap.read()
            if ret:
                # Keep a copy of the first frame for the preview when video ends
                original_preview_frame = cv2.cvtColor(first_frame, cv2.COLOR_BGR2RGB).copy()
                # Reset to start
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            
            # Frame reading thread function
            def frame_reader():
                frame_count = 0
                last_seek_pos = None
                end_of_video = False
                
                while not self.video_state["stop_event"].is_set():
                    # Check for seek request
                    if self.video_state.get("seek_position") is not None:
                        seek_pos = self.video_state["seek_position"]
                        
                        # Only seek if position has changed
                        if seek_pos != last_seek_pos:
                            # Clear the queue when seeking
                            while not frame_queue.empty():
                                try:
                                    frame_queue.get_nowait()
                                except:
                                    pass
                                    
                            # Seek to the new position
                            if 0 <= seek_pos < self.video_state["frame_count"]:
                                cap.set(cv2.CAP_PROP_POS_FRAMES, seek_pos)
                                frame_count = seek_pos
                                self.video_state["current_position"] = seek_pos
                                last_seek_pos = seek_pos
                                end_of_video = False  # Reset end state after seeking
                                
                        # Clear the seek request
                        self.video_state["seek_position"] = None
                    
                    # If paused, sleep and continue
                    if self.video_state.get("paused", False):
                        time.sleep(0.1)
                        continue
                        
                    # If queue is full, wait
                    if frame_queue.full():
                        time.sleep(0.01)
                        continue
                    
                    # If we already reached the end, don't try to read more frames
                    if end_of_video:
                        time.sleep(0.1)
                        continue
                    
                    # Read frame
                    ret, frame = cap.read()
                    
                    # If end of video, set flag and show preview
                    if not ret:
                        end_of_video = True
                        # Pause playback
                        self.video_state["paused"] = True
                        # Update button in main thread
                        if hasattr(self, 'play_pause_btn') and self.play_pause_btn.winfo_exists():
                            self.root.after(0, lambda: self.play_pause_btn.config(text="▶"))
                        
                        # If we have the preview frame saved, show it
                        if original_preview_frame is not None:
                            try:
                                # Put the preview frame in the queue to display at end
                                frame_queue.put(original_preview_frame.copy(), block=False)
                            except queue.Full:
                                pass
                        
                        # Show end of video notification in main thread
                        self.root.after(0, self._show_video_ended_indicator)
                        continue
                        
                    # Update position
                    frame_count += 1
                    self.video_state["current_position"] = frame_count
                    
                    # Update seek bar position (only every few frames to avoid UI lag)
                    if frame_count % 5 == 0 and hasattr(self, 'seek_var'):
                        # Calculate position as percentage
                        if self.video_state["frame_count"] > 0:
                            position_percent = (frame_count / self.video_state["frame_count"]) * 100
                            # Update in main thread without triggering the seek command
                            self.root.after(0, lambda p=position_percent: self._update_seek_position(p))
                    
                    # Resize frame if too large (memory optimization)
                    if width > 1280 or height > 720:
                        scale = min(1280/width, 720/height)
                        new_w, new_h = int(width*scale), int(height*scale)
                        frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
                    
                    # Convert to RGB
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # Put frame in queue
                    try:
                        frame_queue.put(rgb_frame, block=False)
                        
                        # Signal prebuffer completion
                        if not prebuffer_done.is_set() and frame_queue.qsize() >= 3:
                            prebuffer_done.set()
                    except queue.Full:
                        pass  # Skip frame if queue is full
            
            # Start frame reader thread
            reader_thread = threading.Thread(target=frame_reader, daemon=True)
            reader_thread.start()
            
            # Wait for initial prebuffer
            prebuffer_done.wait(timeout=2.0)  # Wait up to 2 seconds for prebuffer
            
            # Get canvas dimensions for scaling
            canvas = self.video_state["canvas"]
            
            # Function to format time
            def format_time(seconds):
                minutes = int(seconds // 60)
                seconds = int(seconds % 60)
                return f"{minutes}:{seconds:02d}"
            
            # Main display loop
            last_frame_time = time.time()
            frame_count = 0
            
            # Last successful frame for when queue is empty
            last_good_frame = None
            
            while not self.video_state["stop_event"].is_set():
                start_time = time.time()
                
                # Update position display
                if self.video_state["fps"] > 0:
                    current_seconds = self.video_state["current_position"] / self.video_state["fps"]
                    total_seconds = self.video_state["duration"]
                    position_text = f"{format_time(current_seconds)} / {format_time(total_seconds)}"
                    
                    # Update in main thread
                    if hasattr(self, 'position_label') and self.position_label.winfo_exists():
                        self.position_label.config(text=position_text)
                
                # If paused, just sleep to reduce CPU
                if self.video_state.get("paused", False):
                    time.sleep(0.1)
                    continue
                
                # Try to get frame from queue with timeout
                try:
                    rgb_frame = frame_queue.get(timeout=0.01)
                    last_good_frame = rgb_frame  # Save this good frame
                except queue.Empty:
                    # If no new frame, use last good frame if available
                    if last_good_frame is not None:
                        rgb_frame = last_good_frame
                    else:
                        # No frames available yet, wait
                        time.sleep(0.01)
                        continue
                
                # Convert frame to PhotoImage for display
                try:
                    # Get current canvas size
                    canvas_width = canvas.winfo_width() or 640
                    canvas_height = canvas.winfo_height() or 480
                    
                    # Calculate scaling to maintain aspect ratio
                    img_h, img_w = rgb_frame.shape[:2]
                    scale_w = canvas_width / img_w
                    scale_h = canvas_height / img_h
                    scale = min(scale_w, scale_h)
                    
                    # Only resize if needed
                    if scale < 1 or scale > 1.1:  # Allow slight upscaling for small videos
                        new_w, new_h = int(img_w * scale), int(img_h * scale)
                        rgb_frame = cv2.resize(rgb_frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
                    
                    # Convert to PIL Image then to PhotoImage
                    pil_img = Image.fromarray(rgb_frame)
                    photo = ImageTk.PhotoImage(image=pil_img)
                    
                    # Clear canvas and create new image
                    canvas.delete("all")
                    
                    # Calculate position to center image
                    x = (canvas_width - pil_img.width) // 2
                    y = (canvas_height - pil_img.height) // 2
                    
                    # Create image on canvas
                    canvas.create_image(x, y, anchor=tk.NW, image=photo)
                    canvas.photo = photo  # Keep reference
                    
                    # Update the canvas
                    canvas.update_idletasks()
                    
                except Exception as e:
                    logger.error(f"Error displaying frame: {e}")
                    # If canvas is destroyed, exit thread
                    if not canvas.winfo_exists():
                        break
                
                # Calculate timing to maintain frame rate
                frame_time = time.time() - start_time
                sleep_time = max(0, frame_delay - frame_time)
                time.sleep(sleep_time)
                
                # Count frames for FPS calculation
                frame_count += 1
                
        except Exception as e:
            logger.error(f"Video thread error: {e}")
        finally:
            # Clean up resources
            if self.video_state["cap"] is not None:
                self.video_state["cap"].release()
                self.video_state["cap"] = None
                
    def _show_video_ended_indicator(self):
        """Show small indicator that video has ended and return to preview"""
        if not hasattr(self, 'video_state') or not self.video_state.get("canvas"):
            return
            
        try:
            canvas = self.video_state["canvas"]
            canvas_width = canvas.winfo_width()
            
            # Create semi-transparent overlay for "End of Video" message
            canvas.create_rectangle(
                canvas_width // 2 - 100, 20,
                canvas_width // 2 + 100, 60,
                fill="#000000",
                stipple="gray50",
                outline="#555555"
            )
            
            # Create text
            canvas.create_text(
                canvas_width // 2, 40,
                text="End of Video",
                fill="#FFFFFF",
                font=("Segoe UI", 10, "bold")
            )
            
            # Schedule return to preview screen after 2 seconds
            if hasattr(self, 'root') and self.root.winfo_exists():
                self.root.after(2000, self._close_video_player)
        except Exception as e:
            logger.error(f"Error showing video end indicator: {e}")
            
    def _close_video_player(self):
        """Close video player and return to preview screen"""
        try:
            # Make sure we have the file path
            if not self.current_file:
                return
                
            # Thoroughly clean up video resources
            self._cleanup_video_player()
            
            # If the file is still the current one, re-display preview
            if self.current_file and self.zipfile:
                try:
                    # Get file data for preview
                    file_info = self.zipfile.getinfo(self.current_file)
                    file_data = self.zipfile.read(self.current_file)
                    
                    # Get file extension
                    file_ext = os.path.splitext(self.current_file)[1].lower()
                    
                    # Create temp file for video again
                    temp_file_path = self._create_temp_file(file_data, self.current_file)
                    
                    if temp_file_path and file_ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
                        # Extract preview frame
                        success, preview_frame = self._extract_video_preview_frame(temp_file_path)
                        
                        if success and preview_frame is not None:
                            # Get video info
                            video_size = os.path.getsize(temp_file_path)
                            
                            # Get dimensions
                            vcap = cv2.VideoCapture(temp_file_path)
                            if vcap.isOpened():
                                width = int(vcap.get(cv2.CAP_PROP_FRAME_WIDTH))
                                height = int(vcap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                                frame_count = int(vcap.get(cv2.CAP_PROP_FRAME_COUNT))
                                fps = vcap.get(cv2.CAP_PROP_FPS)
                                duration = frame_count / fps if fps > 0 else 0
                                duration_formatted = self._format_time_long(duration)
                                dimensions_text = f"{width}x{height}, {frame_count} frames"
                                vcap.release()
                            else:
                                dimensions_text = "unknown dimensions"
                                duration_formatted = "unknown duration"
                                vcap.release()
                            
                            # Display video preview with options again
                            self._display_video_preview_with_options(
                                preview_frame, 
                                temp_file_path, 
                                video_size, 
                                dimensions_text, 
                                duration_formatted,
                                is_large=(video_size > 30 * 1024 * 1024)
                            )
                        else:
                            # Failed to get preview, show error
                            self._show_error("Could not create video preview")
                except Exception as e:
                    logger.error(f"Error returning to preview: {e}")
                    self._show_error(f"Error returning to preview: {str(e)}")
        except Exception as e:
            logger.error(f"Error closing video player: {e}")
            self._show_error(f"Error closing video player: {str(e)}")
    
    def _toggle_video_playback(self):
        """Toggle video playback between play and pause"""
        if hasattr(self, 'video_state'):
            paused = self.video_state.get("paused", False)
            self.video_state["paused"] = not paused
            
            # Update button text
            if hasattr(self, 'play_pause_btn') and self.play_pause_btn.winfo_exists():
                self.play_pause_btn.config(text="▶" if self.video_state["paused"] else "⏸")
    
    def _reset_video_position(self):
        """Reset video to beginning"""
        if hasattr(self, 'video_state') and self.video_state.get("cap") is not None:
            self.video_state["cap"].set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.video_state["current_position"] = 0
    
    def _load_video_with_cv2(self, video_path):
        """Load video with OpenCV as fallback"""
        try:
            # Use the media player's built-in video loading
            success = self.media_player.load_video(video_path, safe_mode=True)
            return success
        except Exception as e:
            logger.error(f"Error loading video with OpenCV: {e}")
            self._show_error(f"Error loading video: Unable to play this format.")
            return False
    
    def _load_video_with_extreme_safeguards(self, video_path):
        """Load video with extreme safety measures for very large videos"""
        try:
            # First clean up any other resources to maximize available memory
            import gc
            gc.collect()
            
            # Show loading feedback
            self.media_player.canvas.delete("all")
            canvas_width = self.media_player.canvas.winfo_width() or 600
            canvas_height = self.media_player.canvas.winfo_height() or 400
            
            loading_id = self.media_player.canvas.create_text(
                canvas_width // 2,
                canvas_height // 2,
                text="Loading large video with safety measures...",
                fill="#FFFFFF",
                font=("Segoe UI", 12)
            )
            self.media_player.canvas.update()  # Force UI update
            
            # Use our custom implementation with scaled-down resolution
            try:
                # Create a full-screen embedded frame for the video player
                video_frame = tk.Frame(
                    self.media_player.canvas,
                    bg="#000000",
                    highlightthickness=0
                )
                
                # Place the video frame on the canvas
                window_id = self.media_player.canvas.create_window(
                    canvas_width // 2,  # Center horizontally
                    canvas_height // 2,  # Center vertically
                    window=video_frame,
                    width=canvas_width - 20,
                    height=canvas_height - 70,  # Leave space for controls
                    anchor=tk.CENTER
                )
                
                # Initialize our custom video player with lower resolution
                self._init_custom_video_player(video_frame, video_path)
                return True
            except Exception as e:
                logger.error(f"Error in custom video player: {e}")
                # OpenCV with minimal settings as fallback
                try:
                    # Set special environment flag for CV2
                    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|analyzeduration;10000000|fflags;discardcorrupt"
                    
                    # Use lower quality settings in media player
                    success = self.media_player.load_video(video_path, safe_mode=True)
                    
                    # If loading failed, try to display at least one frame
                    if not success:
                        return self._display_video_first_frame(video_path)
                        
                    return success
                except Exception as e:
                    logger.error(f"Error with extreme CV2 video loading: {e}")
                    # Last resort - single frame
                    return self._display_video_first_frame(video_path)
        except Exception as e:
            logger.error(f"Error loading video with extreme safeguards: {e}")
            # Try to display just the first frame as fallback
            try:
                return self._display_video_first_frame(video_path)
            except:
                self._show_error(f"Error loading video: Unable to display video content.")
                return False
    
    def _cleanup_video_player(self):
        """Thoroughly clean up video player resources"""
        try:
            # Immediately signal thread to stop
            if hasattr(self, 'video_state') and self.video_state:
                # Signal thread to stop
                if self.video_state.get("stop_event"):
                    self.video_state["stop_event"].set()
                
                # Wait for thread to finish
                if self.video_state.get("thread") and self.video_state["thread"].is_alive():
                    self.video_state["thread"].join(timeout=0.5)
                
                # Release OpenCV resources
                if self.video_state.get("cap"):
                    self.video_state["cap"].release()
                    self.video_state["cap"] = None
                
                # Clean up any canvas
                if self.video_state.get("canvas") and self.video_state["canvas"].winfo_exists():
                    try:
                        self.video_state["canvas"].delete("all")
                    except Exception as e:
                        logger.error(f"Error clearing canvas: {e}")
                
                # Destroy frame container to remove all video UI elements
                if self.video_state.get("frame_container") and self.video_state["frame_container"].winfo_exists():
                    try:
                        self.video_state["frame_container"].destroy()
                    except Exception as e:
                        logger.error(f"Error destroying frame container: {e}")
            
            # Immediately clear the media player canvas
            if hasattr(self, 'media_player') and self.media_player:
                try:
                    self.media_player.canvas.delete("all")
                    
                    # Force removal of any embedded windows
                    for child in self.media_player.canvas.winfo_children():
                        try:
                            child.destroy()
                        except Exception as e:
                            logger.error(f"Error destroying canvas child: {e}")
                except Exception as e:
                    logger.error(f"Error clearing media player canvas: {e}")
                    
                # Clean up media player
                try:
                    # Reset video player
                    self.media_player._reset_video()
                    self.media_player._stop_audio()
                    self.media_player.hide_controls()
                    
                    # Unpack controls if existing
                    if hasattr(self.media_player, 'controls_frame'):
                        try:
                            self.media_player.controls_frame.pack_forget()
                        except Exception as e:
                            logger.error(f"Error unpacking controls frame: {e}")
                except Exception as e:
                    logger.error(f"Error cleaning up media player: {e}")
            
            # Clean up controls
            if hasattr(self, 'play_pause_btn') and self.play_pause_btn.winfo_exists():
                try:
                    self.play_pause_btn.destroy()
                except Exception as e:
                    logger.error(f"Error destroying play button: {e}")
                    
            if hasattr(self, 'reset_btn') and self.reset_btn.winfo_exists():
                try:
                    self.reset_btn.destroy()
                except Exception as e:
                    logger.error(f"Error destroying reset button: {e}")
                    
            if hasattr(self, 'position_label') and self.position_label.winfo_exists():
                try:
                    self.position_label.destroy()
                except Exception as e:
                    logger.error(f"Error destroying position label: {e}")
            
            # Run garbage collection to reclaim memory
            import gc
            gc.collect()
            
        except Exception as e:
            logger.error(f"Error in video player cleanup: {e}")
    
    def _update_seek_position(self, position_percent):
        """Update seek bar position without triggering seek callback"""
        if hasattr(self, 'seek_var'):
            # Temporarily disconnect seek callback
            self.seek_bar.config(command=lambda x: None)
            self.seek_var.set(position_percent)
            # Reconnect seek callback
            self.seek_bar.config(command=self._on_seek)