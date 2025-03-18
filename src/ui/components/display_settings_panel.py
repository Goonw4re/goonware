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
        self.bounce_enabled = tk.BooleanVar(value=False)  # Add bounce control variable
        self.on_toggle = on_toggle
        self.on_panic = on_panic
        self.is_running = False
        
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
                       foreground='white')
        
        # Load saved settings
        root = self.frame.winfo_toplevel()
        if hasattr(root, 'media_manager'):
            settings = root.media_manager.get_display_settings()
            self.interval.set(settings.get('interval', 0.1))
            self.max_popups.set(settings.get('max_popups', 25))
            self.probability.set(settings.get('popup_probability', 5))
            
            # CRITICAL FIX: Properly load bounce_enabled as boolean from integer setting
            bounce_setting = settings.get('bounce_enabled', 0)
            bounce_enabled = bool(int(bounce_setting))
            self.bounce_enabled.set(bounce_enabled)
            print(f"DEBUG INIT: Loaded bounce_enabled={bounce_enabled} from settings value {bounce_setting}")
            
            # CRITICAL FIX: Immediately apply bounce setting to media_display
            if hasattr(root, 'media_display'):
                root.media_display.set_bounce_enabled(bounce_enabled)
                print(f"DEBUG INIT: Applied bounce_enabled={bounce_enabled} to media_display")
        
        self._create_interval_control()
        self._create_popup_control()
        self._create_probability_control()
        self._create_monitor_control()
        self._create_startup_control()
        self._create_buttons()
        
        # Update labels after all controls are created
        self._update_labels()
        
        # Bind update events to save settings
        self.interval_scale.bind("<ButtonRelease-1>", self._save_settings)
        self.popup_scale.bind("<ButtonRelease-1>", self._save_settings)
        self.probability_scale.bind("<ButtonRelease-1>", self._save_settings)
    
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
            to=300.0,  # Maximum 300 seconds
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
    
    def _create_monitor_control(self):
        """Create monitor selection controls and bounce control in the same line"""
        # Create monitor selection frame
        monitor_frame = ttk.Frame(self.frame, style='Modern.TFrame')
        monitor_frame.grid(row=3, column=0, columnspan=3, sticky='ew', pady=(5, 5))
        
        # Add label
        ttk.Label(
            monitor_frame,
            text="Monitors:",
            style='Modern.TLabel'
        ).grid(row=0, column=0, sticky='w', padx=(0, 10))
        
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
        
        # Add bounce checkbox in the same row
        self.bounce_checkbox = ttk.Checkbutton(
            monitor_frame,
            text="Bounce",
            variable=self.bounce_enabled,
            style='Modern.TCheckbutton',
            command=self._update_bounce_enabled
        )
        self.bounce_checkbox.grid(row=0, column=2, sticky='e', padx=(20, 0))
        
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

    def _create_startup_control(self):
        """Create startup control"""
        # Startup frame
        startup_frame = ttk.Frame(self.frame, style='Modern.TFrame')
        startup_frame.grid(row=4, column=0, columnspan=3, pady=(2, 5), sticky="nsew")  # Updated row number
        
        # Startup checkbox
        self.startup_var = tk.BooleanVar()
        self.startup_check = ttk.Checkbutton(
            startup_frame,
            text="Run on Windows Startup",
            style='Modern.TCheckbutton',
            variable=self.startup_var,
            command=self._toggle_startup
        )
        self.startup_check.pack(side=tk.LEFT, padx=5)
        
        # Set initial state from settings or registry
        root = self.frame.winfo_toplevel()
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
    
    def _toggle_startup(self):
        """Handle startup toggle"""
        root = self.frame.winfo_toplevel()
        if hasattr(root, 'manage_startup'):
            success = root.manage_startup(self.startup_var.get())
            if not success:
                # Revert checkbox if operation failed
                self.startup_var.set(not self.startup_var.get())
    
    def _create_buttons(self):
        # Button container
        button_frame = ttk.Frame(self.frame, style='Modern.TFrame')
        button_frame.grid(row=5, column=0, columnspan=3, pady=(5, 2), sticky="nsew")  # Updated row number
        
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
        self.frame.grid_rowconfigure(5, weight=0)  # Don't expand vertically
    
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
                bounce_enabled = self.bounce_enabled.get()
                settings['bounce_enabled'] = 1 if bounce_enabled else 0
                
                # Save startup setting
                startup_enabled = self.startup_var.get()
                settings['startup_enabled'] = 1 if startup_enabled else 0
                
                # Debug log the saved settings
                print(f"DEBUG SETTINGS: Saving bounce_enabled={settings['bounce_enabled']} (from {bounce_enabled})")
                print(f"DEBUG SETTINGS: Saving startup_enabled={settings['startup_enabled']} (from {startup_enabled})")
                
                root.media_manager.update_display_settings(settings)
                
                # Update media display if it exists
                if hasattr(root, 'media_display'):
                    root.media_display.set_bounce_enabled(bounce_enabled)
                    print(f"DEBUG SETTINGS: Updated media_display.bounce_enabled to {root.media_display.bounce_enabled}")
                
        except Exception as e:
            logger.error(f"Error saving settings: {e}")

    def get_bounce_enabled(self):
        """Get bounce enabled setting"""
        return self.bounce_enabled.get()

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

    def _update_bounce_enabled(self):
        """Update bounce enabled setting based on checkbox"""
        # Get the current bounce enabled state
        enabled = bool(self.bounce_enabled.get())
        print(f"DEBUG UI_BOUNCE: Setting bounce enabled to {enabled}")
        
        # Get the root window
        root = self.frame.winfo_toplevel()
        
        # Update the media display
        if hasattr(root, 'media_display'):
            # Set bounce enabled using the setter method
            root.media_display.set_bounce_enabled(enabled)
            
            # Verify the settings were applied
            print(f"DEBUG UI_BOUNCE: Updated media_display.bounce_enabled to {root.media_display.bounce_enabled}")
            print(f"DEBUG UI_BOUNCE: Updated media_display.bounce_chance to {root.media_display.bounce_chance}")
        
        # Save the setting to config
        if hasattr(root, 'media_manager'):
            settings = root.media_manager.get_display_settings()
            # CRITICAL FIX: Save as integer 1/0 instead of boolean
            settings['bounce_enabled'] = 1 if enabled else 0
            root.media_manager.update_display_settings(settings)
            print(f"DEBUG UI_BOUNCE: Saved bounce_enabled={settings['bounce_enabled']} to settings")
        
        # Log the change
        logger.info(f"Bounce enabled set to {enabled}")
