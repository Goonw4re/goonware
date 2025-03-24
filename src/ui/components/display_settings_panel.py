import tkinter as tk
from tkinter import ttk
import keyboard
import logging

logger = logging.getLogger(__name__)

class DisplaySettingsPanel:
    def __init__(self, parent, interval_var, max_popups_var, probability_var, on_toggle, on_panic):
        self.frame = ttk.LabelFrame(
            parent,
            text="Display Settings",
            padding="5",
            style='Modern.TLabelframe'
        )
        
        self.interval = interval_var
        self.max_popups = max_popups_var
        self.probability = probability_var
        self.bounce_chance = tk.DoubleVar(value=0.0)  # Default to disabled (0%)
        self.on_toggle = on_toggle
        self.on_panic = on_panic
        self.is_running = False
        
        # Media type probability variables
        self.image_prob = tk.IntVar(value=60)  # Default: 60%
        self.gif_prob = tk.IntVar(value=20)    # Default: 20%
        self.video_prob = tk.IntVar(value=20)  # Default: 20%
        self.currently_adjusting = None  # Track which slider is being adjusted
        
        # Configure styles for this panel
        style = ttk.Style()
        style.configure('Modern.TLabelframe.Label',
                       background='#1e1e1e',
                       foreground='white',
                       font=('Segoe UI', 11, 'bold'))
        style.configure('Modern.TLabelframe',
                       background='#1e1e1e',
                       foreground='white',
                       bordercolor='#1e1e1e',
                       darkcolor='#1e1e1e',
                       lightcolor='#1e1e1e',
                       borderwidth=0,
                       relief='flat')
        style.configure('Modern.Accent.TButton',
                       background='#0078d4',
                       foreground='black')
        style.map('Modern.TButton',
                  background=[('active', '#606060'), ('!disabled', '#444444')],
                  foreground=[('active', 'black'), ('!disabled', 'black')])
        
        # Configure transparent scale style for bounce chance slider
        style.configure('Transparent.Horizontal.TScale',
                      background='#1e1e1e',
                      troughcolor='#1e1e1e',
                      lightcolor='#1e1e1e',
                      darkcolor='#1e1e1e',
                      slidercolor='darkorchid3')
        
        # Load saved settings
        root = self.frame.winfo_toplevel()
        if hasattr(root, 'media_manager'):
            settings = root.media_manager.get_display_settings()
            self.interval.set(settings.get('interval', 0.1))
            self.max_popups.set(settings.get('max_popups', 25))
            self.probability.set(settings.get('popup_probability', 5))
            
            # Load bounce chance setting - if bounce_enabled is false, use 0
            bounce_enabled = bool(int(settings.get('bounce_enabled', 0)))
            bounce_chance = settings.get('bounce_chance', 0.0)
            # If bounce is disabled, set chance to 0
            if not bounce_enabled:
                bounce_chance = 0.0
            self.bounce_chance.set(float(bounce_chance))
            print(f"DEBUG INIT: Loaded bounce_chance={bounce_chance}% (enabled={bounce_enabled})")
            
            # Load media type probabilities
            self.image_prob.set(int(settings.get('image_prob', 60)))
            self.gif_prob.set(int(settings.get('gif_prob', 20)))
            self.video_prob.set(int(settings.get('video_prob', 20)))
            
            # Apply bounce settings to media_display
            if hasattr(root, 'media_display'):
                root.media_display.set_bounce_enabled(bounce_enabled)
                root.media_display.bounce_chance = float(bounce_chance) / 100.0
                print(f"DEBUG INIT: Applied to media_display: bounce_enabled={bounce_enabled}, chance={bounce_chance}%")
                
                # Apply media type probabilities
                root.media_display.set_media_weights(
                    self.image_prob.get(),
                    self.gif_prob.get(),
                    self.video_prob.get()
                )
        
        self._create_interval_control()
        self._create_popup_control()
        self._create_probability_control()
        self._create_bounce_control()
        self._create_media_prob_control()
        self._create_monitor_control()
        self._create_buttons()
        
        # Update labels after all controls are created
        self._update_labels()
        
        # Bind update events to save settings
        self.interval_scale.bind("<ButtonRelease-1>", self._save_settings)
        self.popup_scale.bind("<ButtonRelease-1>", self._save_settings)
        self.probability_scale.bind("<ButtonRelease-1>", self._save_settings)
        
        # Also update bounce settings during slider movement
        self.bounce_chance_scale.bind("<Motion>", self._update_bounce_settings)
    
    def _create_interval_control(self):
        # Interval label
        ttk.Label(
            self.frame,
            text="Display Interval:",
            style='Modern.TLabel'
        ).grid(row=0, column=0, sticky=tk.W)
        
        # Interval scale
        self.interval_scale = ttk.Scale(
            self.frame,
            from_=0.1,
            to=30.0,  # Maximum 30 seconds
            variable=self.interval,
            orient="horizontal",
            style='Modern.Horizontal.TScale'
        )
        self.interval_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        # Interval value label
        self.interval_label = ttk.Label(
            self.frame,
            style='Modern.TLabel'
        )
        self.interval_label.grid(row=0, column=2, padx=5)
    
    def _create_popup_control(self):
        # Max popups label
        ttk.Label(
            self.frame,
            text="Max Windows:",
            style='Modern.TLabel'
        ).grid(row=1, column=0, sticky=tk.W)
        
        # Max popups scale
        self.popup_scale = ttk.Scale(
            self.frame,
            from_=1,
            to=250,  # Maximum 150 images
            variable=self.max_popups,
            orient="horizontal",
            style='Modern.Horizontal.TScale'
        )
        self.popup_scale.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5)
        
        # Max popups value label
        self.popup_label = ttk.Label(
            self.frame,
            style='Modern.TLabel'
        )
        self.popup_label.grid(row=1, column=2, padx=5)
        
        # Bind update events
        self.interval_scale.bind("<Motion>", self._update_labels)
        self.popup_scale.bind("<Motion>", self._update_labels)
    
    def _create_probability_control(self):
        # Probability label
        ttk.Label(
            self.frame,
            text="Popup Chance:",
            style='Modern.TLabel'
        ).grid(row=2, column=0, sticky=tk.W)
        
        # Probability scale
        self.probability_scale = ttk.Scale(
            self.frame,
            from_=0,
            to=100,  # Percentage from 0-100
            variable=self.probability,
            orient="horizontal",
            style='Modern.Horizontal.TScale'
        )
        self.probability_scale.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=5)
        
        # Probability value label
        self.probability_label = ttk.Label(
            self.frame,
            style='Modern.TLabel'
        )
        self.probability_label.grid(row=2, column=2, padx=5)
        
        # Bind update event
        self.probability_scale.bind("<Motion>", self._update_labels)
    
    def _create_bounce_control(self):
        """Create bounce control settings"""
        # Bounce label
        ttk.Label(
            self.frame,
            text="Bounce Chance:",
            style='Modern.TLabel',
            width=13  # Fixed width for alignment
        ).grid(row=4, column=0, sticky=tk.W)  # Updated row number to 4
        
        # Bounce slider frame
        bounce_frame = ttk.Frame(self.frame, style='Modern.TFrame')
        bounce_frame.grid(row=4, column=1, sticky=(tk.W, tk.E), padx=5)  # Updated row number to 4
        
        # Bounce chance slider - now starting from 0 to disable bounce
        self.bounce_chance_scale = ttk.Scale(
            bounce_frame,
            from_=0,  # Start from 0 to allow disabling
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.bounce_chance,
            command=self._update_bounce_settings,
            style='Transparent.Horizontal.TScale'
        )
        self.bounce_chance_scale.grid(row=0, column=0, sticky='ew')
        
        # Configure column weights
        bounce_frame.columnconfigure(0, weight=1)  # Slider expands
        
        # Bounce chance value label - increased width to ensure % sign is visible
        self.bounce_chance_label = ttk.Label(
            self.frame,
            text=f"{int(self.bounce_chance.get())}%",
            style='Modern.TLabel',
            width=5  # Increased width to ensure % sign is fully visible
        )
        self.bounce_chance_label.grid(row=4, column=2, padx=5)
        
        # Bind update events
        self.bounce_chance_scale.bind("<Motion>", self._update_bounce_settings)
    
    def _create_media_prob_control(self):
        """Create the media type probability sliders"""
        # Create a frame to contain the media probability controls
        media_prob_frame = ttk.LabelFrame(
            self.frame,
            text="Media Mix",
            padding="2",
            style='Modern.TLabelframe'
        )
        media_prob_frame.grid(row=6, column=0, columnspan=3, padx=3, pady=3, sticky=(tk.W, tk.E))  # Updated from row 7 to row 6
        
        # Helper function to create slider row with compact labels
        def create_slider_row(row, label_text, variable, color):
            # Label with shorter text - right aligned
            ttk.Label(
                media_prob_frame,
                text=label_text,
                style='Modern.TLabel',
                width=5,  # Reduced width
                anchor='e'  # Right align text
            ).grid(row=row, column=0, sticky=tk.E, padx=0)
            
            # Scale - much more compact
            scale = ttk.Scale(
                media_prob_frame,
                from_=0,
                to=100,
                variable=variable,
                orient="horizontal",
                style='Modern.Horizontal.TScale',
                length=100  # Made shorter for skinnier layout
            )
            scale.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=1)
            
            # Value label with colored background
            value_label = ttk.Label(
                media_prob_frame,
                foreground='white',
                background=color,
                width=4,  # Width for percentage
                anchor='center'
            )
            value_label.grid(row=row, column=2, padx=1)
            
            # Return the scale and label for event binding
            return scale, value_label
        
        # Create sliders with shorter labels
        self.image_scale, self.image_label = create_slider_row(0, "Img:", self.image_prob, "#3a86ff")
        self.gif_scale, self.gif_label = create_slider_row(1, "GIF:", self.gif_prob, "#ff006e")
        self.video_scale, self.video_label = create_slider_row(2, "Vid:", self.video_prob, "#8338ec")
        
        # Configure the grid to expand
        media_prob_frame.columnconfigure(1, weight=1)
        
        # Update the values initially
        self._update_media_prob_labels()
        
        # Bind events for interactive adjustment
        self.image_scale.bind("<B1-Motion>", lambda e: self._adjust_media_probs("image"))
        self.gif_scale.bind("<B1-Motion>", lambda e: self._adjust_media_probs("gif"))
        self.video_scale.bind("<B1-Motion>", lambda e: self._adjust_media_probs("video"))
        
        # Bind release events to save settings
        self.image_scale.bind("<ButtonRelease-1>", self._save_media_probs)
        self.gif_scale.bind("<ButtonRelease-1>", self._save_media_probs)
        self.video_scale.bind("<ButtonRelease-1>", self._save_media_probs)
    
    def _create_monitor_control(self):
        """Create monitor selection controls"""
        # Create monitor selection frame
        monitor_frame = ttk.Frame(self.frame, style='Modern.TFrame')
        monitor_frame.grid(row=5, column=0, columnspan=3, sticky='ew', pady=(2, 2))  # Updated row number to 5, reduced padding
        
        # Add label - more compact
        ttk.Label(
            monitor_frame,
            text="Monitors:",
            style='Modern.TLabel',
            width=7  # Fixed width to match other labels
        ).grid(row=0, column=0, sticky='w', padx=(0, 5))  # Reduced padding
        
        # Get available monitors first
        root = self.frame.winfo_toplevel()
        monitors = []
        if hasattr(root, 'media_display'):
            monitors = root.media_display.get_monitor_info()
            print(f"DEBUG MONITOR_INIT: Available monitors: {monitors}")
            logger.info(f"Available monitors: {monitors}")
        
        if not monitors:
            monitors = [(0, "Primary Monitor")]
        
        # Get active monitors from settings
        active_monitors = []
        if hasattr(root, 'media_manager'):
            settings = root.media_manager.get_display_settings()
            active_monitors = settings.get('active_monitors', [0])  # Default to primary monitor
            print(f"DEBUG MONITOR_INIT: Loaded active monitors from settings: {active_monitors}")
            logger.info(f"Loaded active monitors from settings: {active_monitors}")
            
            # Validate active_monitors against available monitors
            valid_active_monitors = []
            for idx in active_monitors:
                if any(m_idx == idx for m_idx, _ in monitors):
                    valid_active_monitors.append(idx)
                else:
                    logger.warning(f"Monitor index {idx} from settings not found in available monitors")
            
            # If no valid monitors, default to primary
            if not valid_active_monitors and monitors:
                valid_active_monitors = [monitors[0][0]]
                logger.info(f"No valid monitors from settings, defaulting to {valid_active_monitors}")
                
            active_monitors = valid_active_monitors
            
        # Create monitor selection area
        monitor_buttons_frame = ttk.Frame(monitor_frame, style='Modern.TFrame')
        monitor_buttons_frame.grid(row=0, column=1, sticky='w')
        
        # Create checkbuttons for monitors
        self.monitor_vars = []
        for i, (idx, name) in enumerate(monitors):
            # Set initial state based on saved settings or default to primary monitor
            is_active = idx in active_monitors
            var = tk.BooleanVar(value=is_active)
            self.monitor_vars.append((idx, var))
            
            # Create more compact monitor names
            display_name = f"#{idx+1}"  # Just show monitor number
            
            # Create the checkbutton
            monitor_cb = ttk.Checkbutton(
                monitor_buttons_frame,
                text=display_name,
                variable=var,
                style='Modern.TCheckbutton',
                command=self._update_monitors
            )
            monitor_cb.grid(row=0, column=i, sticky='w', padx=(0, 5))
            
            # Log the monitor checkbutton creation
            print(f"DEBUG MONITOR_INIT: Created monitor checkbutton for monitor {idx} (active: {is_active})")
            logger.info(f"Created monitor checkbutton for monitor {idx} (active: {is_active})")
        
        # Add startup checkbox on same line
        self.startup_var = tk.BooleanVar()
        
        # Create a separator frame
        sep_label = ttk.Label(monitor_frame, text="|", style='Modern.TLabel')
        sep_label.grid(row=0, column=2, padx=(10, 10))
        
        # Startup checkbox, more compact
        self.startup_check = ttk.Checkbutton(
            monitor_frame,
            text="Run on Startup",
            style='Modern.TCheckbutton',
            variable=self.startup_var,
            command=self._toggle_startup
        )
        self.startup_check.grid(row=0, column=3, sticky='w', padx=(0, 5))
        
        # Set initial state from settings or registry
        startup_enabled = False
        
        # First try to load from settings
        if hasattr(root, 'media_manager'):
            settings = root.media_manager.get_display_settings()
            startup_enabled = bool(int(settings.get('startup_enabled', 0)))
            print(f"DEBUG STARTUP: Loaded startup_enabled={startup_enabled} from settings")
        
        # Then check actual registry state
        if hasattr(root, 'is_in_startup'):
            registry_state = root.is_in_startup()
            print(f"DEBUG STARTUP: Registry startup state is {registry_state}")
            
            # If there's a mismatch, use the registry state as source of truth
            if registry_state != startup_enabled:
                startup_enabled = registry_state
                print(f"DEBUG STARTUP: Using registry state {startup_enabled} as source of truth")
                
                # Update settings to match registry
                if hasattr(root, 'media_manager'):
                    settings = root.media_manager.get_display_settings()
                    settings['startup_enabled'] = 1 if startup_enabled else 0
                    root.media_manager.update_display_settings(settings)
        
        # Set the checkbox state
        self.startup_var.set(startup_enabled)
        
        # Initial update of monitor settings - force update to ensure correct monitors are set
        print("DEBUG MONITOR_INIT: Forcing initial update of monitor settings")
        self._update_monitors()

    def _update_monitors(self):
        """Update active monitors in MediaDisplay"""
        root = self.frame.winfo_toplevel()
        
        # Get selected monitors
        active_monitors = [idx for idx, var in self.monitor_vars if var.get()]
        
        # Ensure at least one monitor is selected
        if not active_monitors:
            # If none selected, select the first one
            if self.monitor_vars:
                idx, var = self.monitor_vars[0]
                var.set(True)
                active_monitors = [idx]
                print("DEBUG UI: No monitors selected, defaulting to first monitor")
                
        # Convert to integers
        active_monitors = [int(idx) for idx in active_monitors]
        
        print(f"DEBUG UI: Updating active monitors to {active_monitors}")
            
        # CRITICAL FIX: Save the monitor settings first
        if hasattr(root, 'media_manager'):
            settings = root.media_manager.get_display_settings()
            settings['active_monitors'] = active_monitors
            root.media_manager.update_display_settings(settings)
            print(f"DEBUG UI: Saved monitor settings: {active_monitors}")
            
        # Update media display
        if hasattr(root, 'media_display'):
            # Set active monitors using the setter method
            root.media_display.set_active_monitors(active_monitors)
            
            # Verify the monitors were set correctly
            print(f"DEBUG UI: Media display active monitors now: {root.media_display.active_monitors}")
        
        # Refresh UI
        self._save_settings()

    def _create_buttons(self):
        # Button container
        button_frame = ttk.Frame(self.frame, style='Modern.TFrame')
        button_frame.grid(row=7, column=0, columnspan=3, pady=(5, 2), sticky="nsew")  # Updated to row 7
        
        # Start/Stop button
        self.toggle_button = ttk.Button(
            button_frame,
            text="▶ Start",
            command=self.on_toggle,
            style='Modern.TButton',
            width=15
        )
        self.toggle_button.pack(pady=5)
        
        # Configure frame grid weights
        self.frame.grid_columnconfigure(1, weight=1)  # Make the scale expand
        self.frame.grid_rowconfigure(7, weight=0)  # Don't expand vertically - updated to row 7
    
    def _update_labels(self, event=None):
        """Update the value labels for interval and max popups"""
        interval = self.interval.get()
        if interval >= 60:
            minutes = int(interval // 60)
            seconds = int(interval % 60)
            text = f"{minutes}m {seconds}s"
        else:
            text = f"{interval:.1f}s"
        self.interval_label.configure(text=text)
        self.popup_label.configure(text=str(int(self.max_popups.get())))
        self.probability_label.configure(text=f"{int(self.probability.get())}%")
    
    def set_running(self, is_running):
        """Update the UI state based on running status"""
        self.is_running = is_running
        self.toggle_button.configure(
            text="⏹ Stop" if is_running else "▶ Start"
        )
        
        # Also update the button style to reflect running state
        if is_running:
            logger.info("Display is running, updating button to Stop state")
            # Ensure UI correctly shows the running state
            self.toggle_button.configure(text="⏹ Stop")
    
    def grid(self, **kwargs):
        """Grid the frame"""
        self.frame.grid(**kwargs)

    def _save_settings(self, event=None):
        """Save current settings to config"""
        try:
            root = self.frame.winfo_toplevel()
            if hasattr(root, 'media_manager'):
                settings = root.media_manager.get_display_settings()
                settings['interval'] = self.interval.get()
                settings['max_popups'] = int(self.max_popups.get())
                settings['popup_probability'] = int(self.probability.get())
                
                # CRITICAL FIX: Save bounce_enabled as integer 1/0 instead of boolean
                bounce_enabled = self.bounce_chance.get() > 0
                settings['bounce_enabled'] = 1 if bounce_enabled else 0
                
                # Save bounce chance setting
                bounce_chance = self.bounce_chance.get()
                settings['bounce_chance'] = bounce_chance
                
                # Save startup setting
                startup_enabled = self.startup_var.get()
                settings['startup_enabled'] = 1 if startup_enabled else 0
                
                # Save media probabilities
                settings['image_prob'] = self.image_prob.get()
                settings['gif_prob'] = self.gif_prob.get()
                settings['video_prob'] = self.video_prob.get()
                
                # Debug log the saved settings
                print(f"DEBUG SETTINGS: Saving bounce_enabled={settings['bounce_enabled']} (from {bounce_enabled})")
                print(f"DEBUG SETTINGS: Saving bounce_chance={settings['bounce_chance']}% (from {bounce_chance})")
                print(f"DEBUG SETTINGS: Saving startup_enabled={settings['startup_enabled']} (from {startup_enabled})")
                print(f"DEBUG SETTINGS: Saving media probabilities - Image: {settings['image_prob']}%, GIF: {settings['gif_prob']}%, Video: {settings['video_prob']}%")
                
                root.media_manager.update_display_settings(settings)
                
                # Update media display if it exists
                if hasattr(root, 'media_display'):
                    root.media_display.set_bounce_enabled(bounce_enabled)
                    root.media_display.bounce_chance = float(bounce_chance) / 100.0
                    print(f"DEBUG SETTINGS: Updated media_display.bounce_enabled to {root.media_display.bounce_enabled}")
                    
                    # Update media weights
                    root.media_display.set_media_weights(
                        settings['image_prob'],
                        settings['gif_prob'],
                        settings['video_prob']
                    )
                
        except Exception as e:
            logger.error(f"Error saving settings: {e}")

    def get_bounce_enabled(self):
        """Get bounce enabled setting"""
        return self.bounce_chance.get() > 0

    def get_active_monitors(self):
        """Get list of active monitor indices"""
        # Get the currently selected monitors
        active_monitors = [int(idx) for idx, var in self.monitor_vars if var.get()]
        
        # Ensure at least one monitor is selected
        if not active_monitors and self.monitor_vars:
            # Default to first monitor
            active_monitors = [int(self.monitor_vars[0][0])]
            print(f"DEBUG UI: No monitors selected, defaulting to first monitor {active_monitors}")
            
        print(f"DEBUG UI: Returning active monitors: {active_monitors}")
        
        # CRITICAL FIX: Save the monitor settings
        root = self.frame.winfo_toplevel()
        if hasattr(root, 'media_manager'):
            settings = root.media_manager.get_display_settings()
            settings['active_monitors'] = active_monitors
            root.media_manager.update_display_settings(settings)
            print(f"DEBUG UI: Saved monitor settings: {active_monitors}")
        
        # Force update the media_display
        if hasattr(root, 'media_display'):
            # Set active monitors using the setter method
            root.media_display.set_active_monitors(active_monitors)
            
            # Verify the monitors were set correctly
            print(f"DEBUG UI: Media display active monitors now: {root.media_display.active_monitors}")
            
        return active_monitors

    def _update_bounce_settings(self, *args):
        """Update bounce settings based on slider"""
        # Get the current bounce chance
        chance = float(self.bounce_chance.get())
        
        # Determine if bounce is enabled based on chance value
        enabled = chance > 0
        
        # Update the label
        self.bounce_chance_label.configure(text=f"{int(chance)}%")
        
        print(f"DEBUG UI_BOUNCE: Setting bounce enabled={enabled}, chance={chance}%")
        
        # Get the root window
        root = self.frame.winfo_toplevel()
        
        # Update the media display
        if hasattr(root, 'media_display'):
            # Set bounce enabled based on chance value
            root.media_display.set_bounce_enabled(enabled)
            # Convert from percentage to decimal for internal use (0-100% -> 0.0-1.0)
            decimal_chance = chance / 100.0
            root.media_display.bounce_chance = decimal_chance
            
            # Verify the settings were applied
            print(f"DEBUG UI_BOUNCE: Updated media_display.bounce_enabled to {root.media_display.bounce_enabled}")
            print(f"DEBUG UI_BOUNCE: Updated media_display.bounce_chance to {root.media_display.bounce_chance} ({root.media_display.bounce_chance*100}%)")
        
        # Save the settings to config
        if hasattr(root, 'media_manager'):
            settings = root.media_manager.get_display_settings()
            # Save bounce enabled as integer based on chance value
            settings['bounce_enabled'] = 1 if enabled else 0
            # Save chance as percentage value (0-100)
            settings['bounce_chance'] = chance
            root.media_manager.update_display_settings(settings)
            print(f"DEBUG UI_BOUNCE: Saved bounce_enabled={settings['bounce_enabled']} to settings")
            print(f"DEBUG UI_BOUNCE: Saved bounce_chance={settings['bounce_chance']}% to settings")
        
        # Log the change
        logger.info(f"Bounce settings updated: enabled={enabled}, chance={chance}%")

    def _update_media_prob_labels(self):
        """Update the media probability labels"""
        self.image_label.configure(text=f"{self.image_prob.get():3d}%")  # Fixed width format
        self.gif_label.configure(text=f"{self.gif_prob.get():3d}%")    # Fixed width format
        self.video_label.configure(text=f"{self.video_prob.get():3d}%")  # Fixed width format

    def _adjust_media_probs(self, current):
        """Adjust media probabilities to maintain 100% total"""
        # Determine which slider is being adjusted
        self.currently_adjusting = current
        
        # Get current values
        image_val = self.image_prob.get()
        gif_val = self.gif_prob.get()
        video_val = self.video_prob.get()
        
        # Calculate total
        total = image_val + gif_val + video_val
        
        # If total is 100%, no need to adjust
        if total == 100:
            self._update_media_prob_labels()
            return
        
        # Calculate how much we need to adjust
        diff = 100 - total
        
        # Adjust other sliders based on which one is currently being moved
        if current == "image":
            # Distribute the difference proportionally between gif and video
            if gif_val + video_val > 0:
                gif_ratio = gif_val / (gif_val + video_val)
                video_ratio = video_val / (gif_val + video_val)
                
                gif_adjustment = int(diff * gif_ratio)
                video_adjustment = diff - gif_adjustment
                
                new_gif = max(0, gif_val + gif_adjustment)
                new_video = max(0, video_val + video_adjustment)
                
                # Set new values
                self.gif_prob.set(new_gif)
                self.video_prob.set(new_video)
            else:
                # If both are zero, set one of them to the difference
                self.gif_prob.set(max(0, diff))
                self.video_prob.set(0)
        elif current == "gif":
            # Distribute the difference proportionally between image and video
            if image_val + video_val > 0:
                image_ratio = image_val / (image_val + video_val)
                video_ratio = video_val / (image_val + video_val)
                
                image_adjustment = int(diff * image_ratio)
                video_adjustment = diff - image_adjustment
                
                new_image = max(0, image_val + image_adjustment)
                new_video = max(0, video_val + video_adjustment)
                
                # Set new values
                self.image_prob.set(new_image)
                self.video_prob.set(new_video)
            else:
                # If both are zero, set one of them to the difference
                self.image_prob.set(max(0, diff))
                self.video_prob.set(0)
        elif current == "video":
            # Distribute the difference proportionally between image and gif
            if image_val + gif_val > 0:
                image_ratio = image_val / (image_val + gif_val)
                gif_ratio = gif_val / (image_val + gif_val)
                
                image_adjustment = int(diff * image_ratio)
                gif_adjustment = diff - image_adjustment
                
                new_image = max(0, image_val + image_adjustment)
                new_gif = max(0, gif_val + gif_adjustment)
                
                # Set new values
                self.image_prob.set(new_image)
                self.gif_prob.set(new_gif)
            else:
                # If both are zero, set one of them to the difference
                self.image_prob.set(max(0, diff))
                self.gif_prob.set(0)
        
        # Update the labels
        self._update_media_prob_labels()

    def _save_media_probs(self, event=None):
        """Save media probabilities to settings and apply to media display"""
        # Ensure total is exactly 100% (might be off by 1 due to rounding)
        self._ensure_total_100()
        
        # Update the UI
        self._update_media_prob_labels()
        
        # Save to settings
        try:
            root = self.frame.winfo_toplevel()
            if hasattr(root, 'media_manager'):
                settings = root.media_manager.get_display_settings()
                
                # Save media probabilities
                settings['image_prob'] = self.image_prob.get()
                settings['gif_prob'] = self.gif_prob.get()
                settings['video_prob'] = self.video_prob.get()
                
                root.media_manager.update_display_settings(settings)
                
                # Apply to media display
                if hasattr(root, 'media_display'):
                    root.media_display.set_media_weights(
                        self.image_prob.get(),
                        self.gif_prob.get(),
                        self.video_prob.get()
                    )
                    print(f"DEBUG: Applied media weights - Image: {self.image_prob.get()}%, GIF: {self.gif_prob.get()}%, Video: {self.video_prob.get()}%")
        except Exception as e:
            logger.error(f"Error saving media probabilities: {e}")

    def _ensure_total_100(self):
        """Ensure the total of all media probabilities is exactly 100%"""
        image_val = self.image_prob.get()
        gif_val = self.gif_prob.get()
        video_val = self.video_prob.get()
        
        total = image_val + gif_val + video_val
        
        if total != 100:
            # Adjust the value that's not currently being adjusted
            diff = 100 - total
            
            if self.currently_adjusting == "image":
                if gif_val > 0:
                    self.gif_prob.set(gif_val + diff)
                elif video_val > 0:
                    self.video_prob.set(video_val + diff)
            elif self.currently_adjusting == "gif":
                if image_val > 0:
                    self.image_prob.set(image_val + diff)
                elif video_val > 0:
                    self.video_prob.set(video_val + diff)
            elif self.currently_adjusting == "video":
                if image_val > 0:
                    self.image_prob.set(image_val + diff)
                elif gif_val > 0:
                    self.gif_prob.set(gif_val + diff)
            else:
                # If no slider is being adjusted, adjust the largest one
                largest = max(image_val, gif_val, video_val)
                if largest == image_val:
                    self.image_prob.set(image_val + diff)
                elif largest == gif_val:
                    self.gif_prob.set(gif_val + diff)
                else:
                    self.video_prob.set(video_val + diff)

    def _toggle_startup(self):
        """Handle startup toggle"""
        root = self.frame.winfo_toplevel()
        if hasattr(root, 'manage_startup'):
            success = root.manage_startup(self.startup_var.get())
            if not success:
                # Revert checkbox if operation failed
                self.startup_var.set(not self.startup_var.get())