import os
import io
import logging
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageSequence
import cv2
import numpy as np
from threading import Thread
import time
import tempfile
import subprocess
import platform

# Try to import pygame for audio playback
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    logging.warning("pygame not available, audio playback disabled")

# Configure logging
logger = logging.getLogger(__name__)

class MediaPlayer(ttk.Frame):
    """Media player component that supports images, video frames, and audio playback"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.parent = parent
        
        # Initialize pygame mixer if available
        if PYGAME_AVAILABLE:
            pygame.mixer.init()
            self.current_audio = None
            self.is_playing = False
        
        # Create canvas for displaying media
        self.canvas = tk.Canvas(self, bg='#121212', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Store the current media
        self.current_image = None
        self.photo_image = None
        
        # Video playback variables
        self.video_capture = None
        self.current_frame = 0
        self.total_frames = 0
        self.playing = False
        self.playback_thread = None
        self.fps = 24  # Default FPS
        self.current_media_path = None
        self.current_media_type = None  # 'image', 'video', 'gif', or 'audio'
        self.is_seeking = False  # Flag to prevent playback during seeking
        self.seek_after_release = False  # Flag to resume playback after seeking
        self.cache_frames = {}  # Cache for frequently accessed frames
        self.max_cache_size = 24  # Maximum number of frames to cache
        
        # GIF animation variables
        self.gif_image = None       # Original GIF image object
        self.gif_frames = []        # List of all frames as PhotoImage objects
        self.current_gif_frame = 0  # Current frame index
        self.gif_after_id = None    # ID for after() call to track animation
        
        # Create styles
        style = ttk.Style()
        style.configure('Controls.TFrame', 
                        background='#121212',
                        borderwidth=0,
                        relief="flat")
        
        style.configure('Controls.TButton', 
                        background='#121212',
                        foreground='#FFFFFF',
                        borderwidth=0,
                        focusthickness=0,
                        font=('Segoe UI', 10, 'bold'))
        
        # Create a slider style for the scrub bar
        style.configure("Media.Horizontal.TScale",
                       background='#121212',
                       troughcolor='#444444',
                       sliderlength=12,
                       sliderrelief='flat')
        
        # Create controls frame with padding
        self.controls_frame = ttk.Frame(self, style='Controls.TFrame')
        self.controls_frame.configure(padding="10 5 10 5")
        
        # Create time display
        self.time_label = ttk.Label(
            self.controls_frame,
            text="00:00 / 00:00",
            background='#121212',
            foreground='#FFFFFF',
            font=('Segoe UI', 9)
        )
        
        # Create slider for scrubbing
        self.scrub_var = tk.DoubleVar(value=0)
        self.scrub_bar = ttk.Scale(
            self.controls_frame,
            orient='horizontal',
            variable=self.scrub_var,
            from_=0,
            to=100,
            style="Media.Horizontal.TScale",
            command=self._on_scrub
        )
        
        # Bind events for scrubbing to ensure we properly pause
        self.scrub_bar.bind("<ButtonPress-1>", self._on_scrub_start)
        self.scrub_bar.bind("<ButtonRelease-1>", self._on_scrub_end)
        
        # Create buttons frame
        self.buttons_frame = ttk.Frame(self.controls_frame, style='Controls.TFrame')
        
        # Create play/pause button with better styling
        self.play_button = tk.Button(
            self.buttons_frame, 
            text="⏸",
            font=('Segoe UI', 12, 'bold'),
            fg='#FFFFFF',
            bg='#121212',
            activebackground='#333333',
            activeforeground='#FFFFFF',
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=2,
            command=self.toggle_playback
        )
        
        # Pack controls with better spacing
        self.play_button.pack(side=tk.LEFT, padx=5)
        self.time_label.pack(side=tk.LEFT, padx=10)
        self.scrub_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        self.buttons_frame.pack(side=tk.LEFT, padx=5)
        
        # Only show controls for video content initially
        self.hide_controls()
        
        # Bind resize event to redraw
        self.canvas.bind("<Configure>", self._on_resize)
    
    def show_controls(self):
        """Show the playback controls"""
        self.controls_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=0, ipady=5)
    
    def hide_controls(self):
        """Hide the playback controls"""
        self.controls_frame.pack_forget()
    
    def load_image(self, image_data, media_path=None):
        """Load an image from bytes data"""
        try:
            # Reset video playback if active
            self._reset_video()
            
            # Reset audio playback if active
            self._stop_audio()
            
            # Reset GIF animation if active
            self._reset_gif()
            
            # Store media path for reference
            self.current_media_path = media_path
            self.current_media_type = 'image'
            
            # Convert image data to PIL Image
            self.current_image = Image.open(io.BytesIO(image_data))
            
            # Check if this is actually a GIF with animation
            if getattr(self.current_image, 'is_animated', False) and self.current_image.format == 'GIF':
                # Handle as GIF instead
                return self.load_gif(image_data, media_path)
            
            # Display the image initially
            self._display_current_image()
            
            # Hide controls for images
            self.hide_controls()
            
            return True
        except Exception as e:
            logger.error(f"Error loading image: {e}")
            self._display_error("Error loading image")
            return False
    
    def load_gif(self, gif_data, media_path=None):
        """Load a GIF image and prepare for animation"""
        try:
            # Reset video playback if active
            self._reset_video()
            
            # Reset audio playback if active
            self._stop_audio()
            
            # Reset existing GIF animation if active
            self._reset_gif()
            
            # Store media path for reference
            self.current_media_path = media_path
            self.current_media_type = 'gif'
            
            # Open the GIF image
            self.gif_image = Image.open(io.BytesIO(gif_data))
            
            # Verify it's a GIF with animation
            if not getattr(self.gif_image, 'is_animated', False) or self.gif_image.format != 'GIF':
                logger.warning("Attempted to load non-animated image as GIF")
                # Fall back to regular image display
                self.current_image = self.gif_image
                self.current_media_type = 'image'
                self._display_current_image()
                self.hide_controls()
                return True
                
            logger.info(f"Loading animated GIF with {self.gif_image.n_frames} frames")
            
            # Clear any existing frames
            self.gif_frames = []
            
            # Extract all frames with their individual durations
            self.gif_durations = []
            for frame in ImageSequence.Iterator(self.gif_image):
                # Make a copy of the frame and convert to RGBA for better display
                frame_copy = frame.copy().convert('RGBA')
                # Store the frame as a PhotoImage
                self.gif_frames.append(ImageTk.PhotoImage(frame_copy))
                # Store the frame duration (in milliseconds, default to 100ms if not specified)
                duration = frame.info.get('duration', 100)
                self.gif_durations.append(max(20, min(duration, 500)))  # Clamp between 20ms and 500ms
            
            # Initialize at the first frame
            self.current_gif_frame = 0
            
            # Show controls for GIF (for pause/play)
            self.show_controls()
            
            # Update time label with frame count instead of timestamp
            self.time_label.config(text=f"Frame 1/{len(self.gif_frames)}")
            
            # Update scrub bar range for frames
            self.scrub_bar.configure(from_=0, to=len(self.gif_frames)-1)
            self.scrub_var.set(0)
            
            # Start animation
            self.playing = True
            self.play_button.config(text="⏸")
            self._animate_gif()
            
            return True
        except Exception as e:
            logger.error(f"Error loading GIF: {e}")
            self._display_error("Error loading GIF animation")
            return False
    
    def load_video(self, video_path, safe_mode=False):
        """Load a video file for frame-by-frame viewing with safety measures
        
        Args:
            video_path: Path to the video file
            safe_mode: If True, use extra precautions for potentially problematic videos
        """
        try:
            # Reset any existing video
            self._reset_video()
            
            # Reset audio playback if active
            self._stop_audio()
            
            # Reset GIF animation if active
            self._reset_gif()
            
            # Store media path for reference
            self.current_media_path = video_path
            self.current_media_type = 'video'
            
            # Open the video file with timeout
            self.video_capture = None
            
            # Try to open video with timeout
            success = False
            try:
                import threading
                import time
                
                # Define a function to open the video in a thread
                def open_video():
                    nonlocal success
                    try:
                        # Use lower resolution by default for safer playback
                        cap = cv2.VideoCapture(video_path)
                        if cap.isOpened():
                            self.video_capture = cap
                            success = True
                    except Exception as e:
                        logger.error(f"Error opening video in thread: {e}")
                
                # Create and start the thread
                video_thread = threading.Thread(target=open_video)
                video_thread.daemon = True
                video_thread.start()
                
                # Wait for thread with timeout (5 seconds)
                video_thread.join(timeout=5.0)
                
                if not success:
                    raise TimeoutError("Timeout opening video file - format may be unsupported")
            except Exception as e:
                logger.error(f"Failed to open video with timeout: {e}")
                raise
            
            # Get video properties
            self.total_frames = int(self.video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(self.video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.fps = self.video_capture.get(cv2.CAP_PROP_FPS)
            self.video_duration = self.total_frames / self.fps if self.fps > 0 else 0
            
            # Check for valid video
            if self.total_frames <= 0:
                # Try to estimate total frames if not provided by the codec
                self.total_frames = int(self.video_duration * self.fps) if self.video_duration > 0 else 1000
                logger.warning(f"Video frame count not detected, estimating {self.total_frames} frames")
                
            if self.fps <= 0 or self.fps > 120:
                self.fps = 24  # Default to 24 FPS if not detected correctly or if too high
                logger.warning("Invalid FPS detected, using 24 FPS default")
            
            # Always use safety measures for all videos
            # Limit cache size for large videos 
            frame_size = width * height * 3  # RGB bytes per frame
            
            # Set default safety limits, more strict if safe_mode is enabled
            if safe_mode:
                # Very conservative limits for safe mode
                max_frame_cache = 3 if frame_size < 1280 * 720 * 3 else 0  # Minimal cache for HD, none for larger
                playback_fps = min(24, self.fps) 
                
                # For extremely large videos
                if width * height > 1920 * 1080:
                    # Ultra-conservative for very large videos
                    playback_fps = min(15, self.fps)
                    self._downscale_ratio = 0.5  # Reduce visual quality to prevent crashes
                else:
                    self._downscale_ratio = 0.75
            else:
                # Standard safe limits
                max_frame_cache = 12 if frame_size < 1280 * 720 * 3 else 5
                playback_fps = min(30, self.fps)
                
                # For large videos
                if width * height > 1920 * 1080:
                    max_frame_cache = 3
                    playback_fps = min(20, self.fps)
                    self._downscale_ratio = 0.75
                else:
                    self._downscale_ratio = 1.0
            
            # Apply safety settings
            self.max_cache_size = max_frame_cache
            self.playback_fps = playback_fps  # Store actual FPS to use for playback
            logger.info(f"Video safety settings: cache={max_frame_cache}, fps={playback_fps}, scale={self._downscale_ratio}")
            
            # Try to read first frame with fallback
            attempt = 0
            success = False
            
            while attempt < 3 and not success:
                try:
                    success = self._display_frame()
                    if not success:
                        # Try to reset position and try again
                        self.current_frame = attempt * 10  # Try different frames
                        attempt += 1
                except Exception as e:
                    logger.error(f"Error displaying first frame, attempt {attempt}: {e}")
                    attempt += 1
            
            if not success:
                raise ValueError("Could not read video frames - video may be corrupted or unsupported")
            
            # Update scrub bar range
            self.scrub_var.set(0)
            self.scrub_bar.configure(from_=0, to=self.total_frames-1)
            
            # Update time display
            self._update_time_display()
            
            # Show controls for video
            self.show_controls()
            
            # Auto-play the video
            self._start_playback()
            
            return True
        except Exception as e:
            logger.error(f"Error loading video: {e}")
            self._display_error(f"Error loading video: {str(e)[:100]}")
            self._reset_video()  # Clean up any partial resources
            return False
    
    def _animate_gif(self):
        """Display the next frame in the GIF animation"""
        if not self.playing or self.current_media_type != 'gif' or not self.gif_frames:
            return
            
        try:
            # Display current frame
            self.canvas.delete("all")
            self.photo_image = self.gif_frames[self.current_gif_frame]
            
            # Calculate canvas center position
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            # Display image centered
            self.canvas.create_image(canvas_width//2, canvas_height//2, 
                                   image=self.photo_image, anchor=tk.CENTER)
            
            # Update scrub position (without triggering callback)
            self.scrub_var.set(self.current_gif_frame)
            
            # Update time display
            self.time_label.config(text=f"Frame {self.current_gif_frame+1}/{len(self.gif_frames)}")
            
            # Move to next frame or loop back
            self.current_gif_frame = (self.current_gif_frame + 1) % len(self.gif_frames)
            
            # Schedule next frame update using the duration for the current frame
            frame_delay = self.gif_durations[self.current_gif_frame]
            self.gif_after_id = self.after(frame_delay, self._animate_gif)
            
        except Exception as e:
            logger.error(f"Error animating GIF: {e}")
            self._reset_gif()
    
    def _reset_gif(self):
        """Reset GIF animation state"""
        # Cancel any pending animation
        if self.gif_after_id:
            self.after_cancel(self.gif_after_id)
            self.gif_after_id = None
            
        # Clear frames to free memory
        self.gif_frames = []
        self.gif_durations = []
        self.current_gif_frame = 0
        
        # Clear the gif image
        self.gif_image = None
    
    def _on_scrub_start(self, event):
        """Handle start of scrubbing - always pause playback"""
        if not self.video_capture or self.current_media_type != 'video':
            return
            
        # Set seeking flag so we know we're in a scrub operation
        self.is_seeking = True
        
        # Remember if we were playing to resume after scrub
        self.seek_after_release = self.playing
        
        # Always pause playback during scrubbing
        if self.playing:
            self._stop_playback()
    
    def _on_scrub_end(self, event):
        """Handle end of scrubbing - resume if necessary"""
        if not self.video_capture or self.current_media_type != 'video':
            return
            
        # Reset seeking flag
        self.is_seeking = False
        
        # Resume playback if it was playing before
        if self.seek_after_release:
            self.after(100, self._start_playback)
    
    def _on_scrub(self, value):
        """Handle scrub bar movement"""
        if self.current_media_type == 'video' and self.video_capture:
            # Convert to int as the value is a string when called from the Scale widget
            try:
                frame_pos = int(float(value))
            except ValueError:
                return
            
            # Set current frame position
            self.current_frame = max(0, min(frame_pos, self.total_frames - 1))
            
            # Update display
            self._display_frame()
            self._update_time_display()
        elif self.current_media_type == 'gif' and self.gif_frames:
            # Handle GIF frame scrubbing
            try:
                frame_pos = int(float(value))
            except ValueError:
                return
                
            # Set current frame position
            self.current_gif_frame = max(0, min(frame_pos, len(self.gif_frames) - 1))
            
            # Update display 
            self.canvas.delete("all")
            self.photo_image = self.gif_frames[self.current_gif_frame]
            
            # Calculate canvas center position
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            # Display image centered
            self.canvas.create_image(canvas_width//2, canvas_height//2, 
                                   image=self.photo_image, anchor=tk.CENTER)
            
            # Update time display
            self.time_label.config(text=f"Frame {self.current_gif_frame+1}/{len(self.gif_frames)}")
    
    def _format_time(self, seconds):
        """Format time in MM:SS format"""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"
    
    def _update_time_display(self):
        """Update the time display"""
        if self.video_capture is not None and self.fps > 0:
            current_time = self.current_frame / self.fps
            total_time = self.total_frames / self.fps
            
            self.time_label.config(
                text=f"{self._format_time(current_time)} / {self._format_time(total_time)}"
            )
    
    def load_audio(self, audio_path):
        """Load an audio file for playback"""
        if not PYGAME_AVAILABLE:
            logger.error("Cannot play audio: pygame not available")
            self._display_error("Audio playback not available (pygame required)")
            return False
        
        try:
            # Reset video playback if active
            self._reset_video()
            
            # Stop any current audio
            self._stop_audio()
            
            # Store media path for reference
            self.current_media_path = audio_path
            self.current_media_type = 'audio'
            
            # Load the audio file
            pygame.mixer.music.load(audio_path)
            
            # Display audio placeholder image
            self._display_audio_placeholder()
            
            # Show controls for audio
            self.show_controls()
            
            # Update time label
            self.time_label.config(text="Audio Ready")
            
            return True
        except Exception as e:
            logger.error(f"Error loading audio: {e}")
            self._display_error("Error loading audio")
            return False
    
    def _stop_audio(self):
        """Stop any playing audio"""
        if PYGAME_AVAILABLE and pygame.mixer.get_init():
            try:
                pygame.mixer.music.stop()
                self.is_playing = False
                # Update play button text to show play symbol
                self.play_button.config(text="▶")
            except:
                pass
    
    def _display_audio_placeholder(self):
        """Display a placeholder image for audio files"""
        # Create a simple audio waveform placeholder
        width, height = 400, 300
        img = Image.new('RGB', (width, height), color='#121212')
        
        # Draw audio icon or waveform
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        
        # Draw a simple audio waveform
        center_y = height // 2
        wave_height = 100
        segments = 20
        segment_width = width // segments
        
        for i in range(segments):
            # Create a simple sine wave pattern
            amplitude = wave_height * (0.5 + 0.5 * np.sin(i / 2))
            x = i * segment_width
            draw.line(
                [(x, center_y - amplitude), (x, center_y + amplitude)],
                fill='#BB86FC', 
                width=segment_width // 2
            )
        
        self.current_image = img
        self._display_current_image()
    
    def toggle_playback(self):
        """Toggle video or audio playback"""
        if self.current_media_type == 'video':
            if self.playing:
                self._stop_playback()
            else:
                self._start_playback()
        elif self.current_media_type == 'gif':
            if self.playing:
                # Pause GIF animation
                self.playing = False
                self.play_button.config(text="▶")
                if self.gif_after_id:
                    self.after_cancel(self.gif_after_id)
                    self.gif_after_id = None
            else:
                # Resume GIF animation
                self.playing = True
                self.play_button.config(text="⏸")
                self._animate_gif()
        elif self.current_media_type == 'audio' and PYGAME_AVAILABLE:
            if self.is_playing:
                pygame.mixer.music.pause()
                self.is_playing = False
                self.play_button.config(text="▶")
            else:
                pygame.mixer.music.play()
                self.is_playing = True
                self.play_button.config(text="⏸")
    
    def _start_playback(self):
        """Start video playback"""
        if not self.playing and self.video_capture is not None:
            self.playing = True
            self.play_button.config(text="⏸")
            self.playback_thread = Thread(target=self._playback_loop, daemon=True)
            self.playback_thread.start()
    
    def _stop_playback(self):
        """Stop video playback"""
        self.playing = False
        self.play_button.config(text="▶")
        if self.playback_thread:
            self.playback_thread.join(timeout=0.5)
            self.playback_thread = None
    
    def _playback_loop(self):
        """Background thread for video playback"""
        # Use playback_fps instead of actual fps for more stable playback
        frame_time = 1.0 / self.playback_fps if hasattr(self, 'playback_fps') else 1.0 / self.fps
        last_update_time = 0
        skip_frame_threshold = frame_time * 0.8  # If we're behind, skip frames
        recovery_count = 0
        
        while self.playing and self.video_capture is not None:
            # Skip if we're actively seeking
            if self.is_seeking:
                time.sleep(0.05)
                continue
                
            start_time = time.time()
            
            # Check if we need to skip frames to catch up
            if last_update_time > 0 and start_time - last_update_time > skip_frame_threshold:
                # Calculate how many frames to skip to maintain speed
                frames_behind = int((start_time - last_update_time) / frame_time)
                if frames_behind > 1 and self.current_frame + frames_behind < self.total_frames:
                    # Skip more frames when we're falling behind
                    self.current_frame += frames_behind - 1
                    logger.debug(f"Skipping {frames_behind-1} frames to maintain playback speed")
            
            # Frame advance logic with error recovery
            if self.current_frame < self.total_frames - 1:
                self.current_frame += 1
                
                # Display frame with error recovery
                try:
                    # Only update UI every other frame for high FPS videos to reduce load
                    if self.current_frame % 2 == 0 or self.fps < 20:
                        success = self._display_frame()
                        
                        if not success:
                            # Try recovery before giving up
                            recovery_count += 1
                            if recovery_count < 5:
                                logger.warning(f"Frame display failed, attempting recovery ({recovery_count}/5)")
                                # Skip ahead a few frames
                                self.current_frame += 5
                                continue
                            else:
                                logger.error("Video playback failed after multiple recovery attempts")
                                self.playing = False
                                # Show error on main thread
                                self.after(0, lambda: self._display_error("Video playback error - format may be unsupported"))
                                break
                        else:
                            # Reset recovery counter on success
                            recovery_count = 0
                        
                        # Update UI indicators
                        last_update_time = time.time()
                        
                        # Update position indicators on UI thread
                        self.after(0, lambda: self._update_ui_indicators())
                    else:
                        # For frames we skip showing, still advance the position
                        pass
                except Exception as e:
                    logger.error(f"Error in playback loop: {e}")
                    recovery_count += 1
                    if recovery_count >= 5:
                        self.playing = False
                        # Show error on main thread
                        self.after(0, lambda: self._display_error("Video playback failed"))
                        break
            else:
                # Loop back to the start
                self.current_frame = 0
                try:
                    self._display_frame()
                    # Reset recovery counter on loop
                    recovery_count = 0
                    
                    # Update indicators
                    self.after(0, lambda: self._update_ui_indicators())
                except Exception as e:
                    logger.error(f"Error looping video: {e}")
                    self.playing = False
                    break
            
            # Calculate sleep time to maintain correct FPS
            # Add a small extra delay to prevent busy-waiting
            elapsed = time.time() - start_time
            sleep_time = max(0.001, frame_time - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def _update_ui_indicators(self):
        """Update UI indicators (called from main thread)"""
        if not self.playing:
            return
            
        # Update time display
        self._update_time_display()
        
        # Update scrub bar without triggering the callback
        self.scrub_var.set(self.current_frame)
    
    def _display_frame(self):
        """Display the current video frame - optimized version with safety checks"""
        if self.video_capture is None:
            return False
        
        # Check cache first (much faster than loading from disk)
        if self.current_frame in self.cache_frames:
            self.current_image = self.cache_frames[self.current_frame]
            self._display_current_image()
            return True
        
        try:
            # Set the video position to the current frame
            self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
            
            # Read the frame with error protection and timeout
            try:
                # Wrap frame read in a timeout
                import threading
                
                frame_read_success = [False]
                frame_data = [None]
                
                def read_frame():
                    try:
                        success, frame = self.video_capture.read()
                        frame_read_success[0] = success
                        frame_data[0] = frame
                    except Exception as e:
                        logger.error(f"Error in read_frame thread: {e}")
                
                # Create thread for reading
                frame_thread = threading.Thread(target=read_frame)
                frame_thread.daemon = True
                frame_thread.start()
                
                # Wait with timeout (prevent hanging on corrupt frames)
                frame_thread.join(timeout=0.5)
                
                if not frame_thread.is_alive():
                    # Thread completed
                    success = frame_read_success[0]
                    frame = frame_data[0]
                else:
                    # Timeout occurred
                    logger.error(f"Timeout reading frame {self.current_frame}")
                    return False
            except Exception as e:
                logger.error(f"Error reading frame {self.current_frame}: {e}")
                return False
            
            if not success or frame is None:
                logger.error(f"Failed to read frame {self.current_frame}")
                return False
            
            try:
                # Check frame dimensions - protect against corrupt frames
                if frame.shape[0] == 0 or frame.shape[1] == 0:
                    logger.error(f"Invalid frame dimensions at frame {self.current_frame}")
                    return False
                
                # Downscale frame if needed for performance
                if hasattr(self, '_downscale_ratio') and self._downscale_ratio < 1.0:
                    new_width = int(frame.shape[1] * self._downscale_ratio)
                    new_height = int(frame.shape[0] * self._downscale_ratio)
                    frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
                
                # Convert the frame from BGR to RGB more efficiently
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Convert to PIL Image with error handling
                try:
                    pil_image = Image.fromarray(frame_rgb)
                except Exception as e:
                    logger.error(f"Error converting frame to PIL Image: {e}")
                    return False
                
                # Update current image
                self.current_image = pil_image
                
                # Only cache if cache is enabled (max_cache_size > 0)
                if self.max_cache_size > 0:
                    # Store in cache for reuse (for seeking)
                    if len(self.cache_frames) >= self.max_cache_size:
                        # Remove oldest frame if cache is full
                        oldest_frame = min(self.cache_frames.keys())
                        del self.cache_frames[oldest_frame]
                        
                    # Cache keyframes or frames likely to be used in seeking
                    # Only cache every 30th frame to save memory
                    if self.current_frame % 30 == 0 or self.is_seeking:
                        self.cache_frames[self.current_frame] = pil_image
                
                # Display the image
                self._display_current_image()
                
                return True
            except Exception as e:
                logger.error(f"Error processing frame: {e}")
                return False
        except Exception as e:
            logger.error(f"Error in _display_frame: {e}")
            return False
    
    def _display_current_image(self):
        """Display the current PIL image on the canvas - optimized version"""
        if self.current_image is None:
            return
            
        try:
            # Get canvas dimensions
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            # Skip if canvas has no size yet
            if canvas_width <= 1 or canvas_height <= 1:
                self.canvas.after(100, self._display_current_image)
                return
            
            # Get image dimensions
            img_width, img_height = self.current_image.size
            
            # Calculate scaling factor
            scale_width = canvas_width / img_width
            scale_height = canvas_height / img_height
            scale = min(scale_width, scale_height)
            
            # Calculate new dimensions
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
            
            # Only resize if necessary - reduces CPU usage
            if new_width != img_width or new_height != img_height:
                # Use NEAREST for video frames during playback for better performance
                if self.playing and not self.is_seeking and self.current_media_type == 'video':
                    resample = Image.NEAREST
                else:
                    resample = Image.LANCZOS
                    
                resized_img = self.current_image.resize((new_width, new_height), resample)
            else:
                resized_img = self.current_image
            
            # Convert to PhotoImage
            self.photo_image = ImageTk.PhotoImage(resized_img)
            
            # Clear canvas
            self.canvas.delete("all")
            
            # Calculate canvas center position
            x = (canvas_width - new_width) // 2
            y = (canvas_height - new_height) // 2
            
            # Display image
            self.canvas.create_image(x, y, anchor=tk.NW, image=self.photo_image)
        except Exception as e:
            logger.error(f"Error displaying image: {e}")
    
    def _on_resize(self, event):
        """Handle canvas resize event"""
        if self.current_image is not None:
            self._display_current_image()
    
    def _display_error(self, message):
        """Display an error message on the canvas"""
        # Clear the canvas
        self.canvas.delete("all")
        
        # Display error text
        self.canvas.create_text(
            self.canvas.winfo_width() // 2,
            self.canvas.winfo_height() // 2,
            text=message,
            fill="#FF5252",
            font=("Segoe UI", 12, "bold")
        )
    
    def _reset_video(self):
        """Reset video playback state"""
        # Stop playback if running
        if self.playing:
            self._stop_playback()
        
        # Release video capture if exists
        if self.video_capture is not None:
            try:
                self.video_capture.release()
            except Exception as e:
                logger.error(f"Error releasing video capture: {e}")
            finally:
                self.video_capture = None
        
        # Reset frame counters
        self.current_frame = 0
        self.total_frames = 0
        
        # Clear cache to free memory
        self.cache_frames.clear()
        
        # Clear the canvas
        try:
            self.canvas.delete("all")
        except:
            pass
        
        # Force garbage collection to free memory
        try:
            import gc
            gc.collect()
        except:
            pass
    
    def destroy(self):
        """Clean up resources when widget is destroyed"""
        # Stop playback
        if self.playing:
            self._stop_playback()
        
        # Release video resources
        if self.video_capture is not None:
            self.video_capture.release()
            self.video_capture = None
        
        # Clear cache
        self.cache_frames.clear()
        
        # Stop audio
        self._stop_audio()
        
        # Reset GIF animation
        self._reset_gif()
        
        # Call parent destroy
        super().destroy() 