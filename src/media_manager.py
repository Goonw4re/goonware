import os
import zipfile
import json
import logging
from pathlib import Path
import traceback

logger = logging.getLogger(__name__)

class MediaManager:
    def __init__(self, models_dir, auto_load=False):
        self.models_dir = models_dir
        self.available_zips = {}  # Dictionary of available zip files
        self.loaded_zips = set()  # Set of currently loaded zip files
        self.config_file = os.path.join(os.path.dirname(models_dir), 'assets', 'config.json')
        
       # Create assets directory if it doesn't exist
        assets_dir = os.path.dirname(self.config_file)
        os.makedirs(assets_dir, exist_ok=True)
        
        # Set up media directories inside assets folder
        self.gif_dir = os.path.join(assets_dir, 'resources', 'img')
        self.video_dir = os.path.join(assets_dir, 'resources', 'vid')
        os.makedirs(self.gif_dir, exist_ok=True)
        os.makedirs(self.video_dir, exist_ok=True)
        
        # Default display settings
        self.display_settings = {
            'interval': 0.1,
            'max_popups': 25,
            'popup_probability': 5,
            'panic_key': "'",
            'active_monitors': None,  # Default to None means all monitors
            'bounce_enabled': False
        }
        
        # Load saved configuration (but not the models yet)
        self.load_config()
        
        # Scan for available zip files but don't load them yet
        if auto_load:
            self.refresh_media_files()
        else:
            # Just scan for available zips without loading them
            self._scan_available_zips()
            
        logger.info(f"MediaManager initialized with models directory: {models_dir}")
    
    def _scan_available_zips(self):
        """Scan for available zip and gmodel files without loading them"""
        try:
            # Clear existing zips
            self.available_zips.clear()
            
            # First, collect all files with their extensions
            all_model_files = {}
            
            if os.path.exists(self.models_dir):
                for filename in os.listdir(self.models_dir):
                    # Only process .zip and .gmodel files
                    if filename.lower().endswith(('.zip', '.gmodel')):
                        # Get the base name without extension
                        base_name = os.path.splitext(filename)[0]
                        
                        # Get file path
                        file_path = os.path.join(self.models_dir, filename)
                        
                        # Add or update the file info
                        if base_name not in all_model_files:
                            all_model_files[base_name] = {
                                'path': file_path,
                                'filename': filename,
                                'extension': os.path.splitext(filename)[1].lower()
                            }
                        else:
                            # If both .zip and .gmodel exist, prefer .gmodel
                            current_ext = all_model_files[base_name]['extension']
                            new_ext = os.path.splitext(filename)[1].lower()
                            
                            # .gmodel takes precedence over .zip
                            if new_ext == '.gmodel' and current_ext == '.zip':
                                all_model_files[base_name] = {
                                    'path': file_path,
                                    'filename': filename,
                                    'extension': new_ext
                                }
            
            # Now build available_zips using only the preferred file for each base name
            for file_info in all_model_files.values():
                filename = file_info['filename']
                file_path = file_info['path']
                self.available_zips[filename] = file_path
            
            logger.info(f"Found {len(self.available_zips)} model files")
            
        except Exception as e:
            logger.error(f"Error scanning available model files: {e}\n{traceback.format_exc()}")
    
    def load_config(self):
        """Load configuration from file"""
        try:
            # Check if config file exists
            if not os.path.exists(self.config_file):
                logger.info(f"Config file {self.config_file} not found, using defaults")
                self.config = {
                    'loaded_zips': [],
                    'display_settings': self._get_default_display_settings()
                }
                return True
                
            # Load config from file
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
                
            # Ensure required sections exist
            if 'loaded_zips' not in self.config:
                self.config['loaded_zips'] = []
                
            if 'display_settings' not in self.config:
                self.config['display_settings'] = self._get_default_display_settings()
                
            # Ensure active_monitors is present and valid in display settings
            if 'display_settings' in self.config:
                display_settings = self.config['display_settings']
                
                # Remove any 'enabled_monitors' key if it exists
                if 'enabled_monitors' in display_settings:
                    logger.warning(f"Found deprecated 'enabled_monitors' key in config, removing it")
                    del display_settings['enabled_monitors']
                
                # Ensure active_monitors is present and valid
                if 'active_monitors' not in display_settings or not display_settings['active_monitors']:
                    display_settings['active_monitors'] = [0]  # Default to primary monitor
                elif not isinstance(display_settings['active_monitors'], list):
                    display_settings['active_monitors'] = [int(display_settings['active_monitors'])]
                else:
                    # Convert each element to int
                    display_settings['active_monitors'] = [int(idx) for idx in display_settings['active_monitors']]
                    
                logger.info(f"Loaded config with active_monitors: {display_settings['active_monitors']}")
                print(f"DEBUG CONFIG: Loaded config with active_monitors: {display_settings['active_monitors']}")
            
            # Load zip files from config and store them
            saved_loaded_zips = self.config.get('loaded_zips', [])
            
            # Scan available zips first to ensure we have the latest list
            self._scan_available_zips()
            
            # Only load zips that actually exist in the available zips
            self.loaded_zips = set()
            for zip_name in saved_loaded_zips:
                if zip_name in self.available_zips:
                    self.loaded_zips.add(zip_name)
                else:
                    logger.warning(f"Saved zip {zip_name} not found in available zips, skipping")
            
            logger.info(f"Loaded configuration with {len(self.loaded_zips)} saved models and display settings")
            return True
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            # Use defaults
            self.config = {
                'loaded_zips': [],
                'display_settings': self._get_default_display_settings()
            }
            return False
    
    def save_config(self):
        """Save configuration to file"""
        try:
            # Ensure config directory exists
            config_dir = os.path.dirname(self.config_file)
            os.makedirs(config_dir, exist_ok=True)
            
            # Update loaded_zips in config
            self.config['loaded_zips'] = list(self.loaded_zips)
            
            # Log what we're saving
            logger.info(f"Saving config with {len(self.loaded_zips)} loaded zips: {', '.join(self.loaded_zips)}")
            
            if 'display_settings' in self.config:
                active_monitors = self.config['display_settings'].get('active_monitors', [0])
                logger.info(f"Saving config with active_monitors: {active_monitors}")
                print(f"DEBUG CONFIG: Saving config with active_monitors: {active_monitors}")
            
            # Save config to file
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
                
            logger.info(f"Saved configuration to {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False
    
    def get_display_settings(self):
        """Get display settings from config"""
        try:
            if not self.config:
                self.load_config()
                
            # Get display settings or create default
            settings = self.config.get('display_settings', {})
            if not settings:
                settings = self._get_default_display_settings()
                
            # Ensure active_monitors is a list of integers
            if 'active_monitors' in settings:
                # Convert to list if it's not already
                if not isinstance(settings['active_monitors'], list):
                    settings['active_monitors'] = [int(settings['active_monitors'])]
                else:
                    # Convert each element to int
                    settings['active_monitors'] = [int(idx) for idx in settings['active_monitors']]
                    
                logger.info(f"Retrieved display settings with active_monitors: {settings['active_monitors']}")
                print(f"DEBUG SETTINGS: Retrieved active_monitors: {settings['active_monitors']}")
            else:
                # Default to primary monitor
                settings['active_monitors'] = [0]
                logger.info("No active_monitors in settings, defaulting to primary monitor")
                print("DEBUG SETTINGS: No active_monitors in settings, defaulting to primary monitor")
                
            return settings
        except Exception as e:
            logger.error(f"Error getting display settings: {e}")
            return self._get_default_display_settings()
            
    def update_display_settings(self, settings):
        """Update display settings in config"""
        try:
            if not self.config:
                self.load_config()
                
            # Validate settings
            if not isinstance(settings, dict):
                logger.error(f"Invalid settings type: {type(settings)}")
                return False
                
            # Ensure active_monitors is a list of integers
            if 'active_monitors' in settings:
                # Convert to list if it's not already
                if not isinstance(settings['active_monitors'], list):
                    settings['active_monitors'] = [int(settings['active_monitors'])]
                else:
                    # Convert each element to int
                    settings['active_monitors'] = [int(idx) for idx in settings['active_monitors']]
                    
                logger.info(f"Set active_monitors to: {settings['active_monitors']}")
                print(f"DEBUG SETTINGS: Setting active_monitors to: {settings['active_monitors']}")
                
            # Update config
            self.config['display_settings'] = settings
            
            # Save config
            self.save_config()
            
            return True
        except Exception as e:
            logger.error(f"Error updating display settings: {e}")
            return False
    
    def refresh_media_files(self):
        """Refresh the list of available model files (.zip and .gmodel)"""
        try:
            # Store current loaded zips
            current_loaded = self.loaded_zips.copy()
            
            # Scan for available model files
            self._scan_available_zips()
            
            # Filter loaded zips to only those that are still available
            self.loaded_zips = {zip_name for zip_name in self.loaded_zips if zip_name in self.available_zips}
            
            # If no models are loaded after filtering, try to restore from config
            if not self.loaded_zips and 'loaded_zips' in self.config:
                for zip_name in self.config.get('loaded_zips', []):
                    if zip_name in self.available_zips:
                        self.loaded_zips.add(zip_name)
                logger.info(f"Restored {len(self.loaded_zips)} model files from config")
            
            # Save the configuration to ensure it's up to date
            self.config['loaded_zips'] = list(self.loaded_zips)
            self.save_config()
            
            logger.info(f"Refreshed media files: {len(self.available_zips)} available, {len(self.loaded_zips)} loaded")
            
        except Exception as e:
            logger.error(f"Error refreshing media files: {e}\n{traceback.format_exc()}")
    
    def get_media_paths(self):
        """Get all media paths from loaded model files"""
        media_paths = {
            'images': [],
            'gifs': [],
            'videos': []
        }
        
        try:
            # Check if we have any loaded models
            if not self.loaded_zips:
                logger.warning("No model files are currently loaded")
                return media_paths
                
            logger.info(f"Getting media paths from {len(self.loaded_zips)} loaded model files: {', '.join(self.loaded_zips)}")
            
            # Process each loaded model file
            for zip_name in self.loaded_zips:
                if zip_name in self.available_zips:
                    zip_path = self.available_zips[zip_name]
                    logger.info(f"Processing model file: {zip_path}")
                    
                    # Process zip file to extract media paths
                    try:
                        from media.path_utils import MediaPathManager
                        path_manager = MediaPathManager()
                        
                        # Pass only the currently processing zip to get_media_paths
                        paths = path_manager.get_media_paths({zip_name})
                        
                        # Add paths to the main list
                        media_paths['images'].extend(paths.get('images', []))
                        media_paths['gifs'].extend(paths.get('gifs', []))
                        media_paths['videos'].extend(paths.get('videos', []))
                        
                    except Exception as e:
                        logger.error(f"Error getting media paths from {zip_path}: {e}\n{traceback.format_exc()}")
                else:
                    logger.warning(f"Model file {zip_name} not found in available models")
            
            logger.info(f"Found {len(media_paths['images'])} images, {len(media_paths['gifs'])} GIFs, and {len(media_paths['videos'])} videos")
            
            # Log sample paths for debugging
            if media_paths['images']:
                sample_count = min(3, len(media_paths['images']))
                logger.info(f"Sample image paths: {media_paths['images'][:sample_count]}")
            if media_paths['gifs']:
                sample_count = min(3, len(media_paths['gifs']))
                logger.info(f"Sample GIF paths: {media_paths['gifs'][:sample_count]}")
            if media_paths['videos']:
                sample_count = min(3, len(media_paths['videos']))
                logger.info(f"Sample video paths: {media_paths['videos'][:sample_count]}")
                
            return media_paths
            
        except Exception as e:
            logger.error(f"Error getting media paths: {e}\n{traceback.format_exc()}")
            return media_paths
    
    def get_loaded_zips(self):
        """Get the currently loaded zip files"""
        return self.loaded_zips.copy()
    
    def get_available_zips(self):
        """Get list of available zip files"""
        return list(self.available_zips.keys())
    
    def load_zip(self, zip_name):
        """Load a zip file"""
        try:
            if zip_name in self.available_zips:
                # Check if the zip is already loaded
                if zip_name in self.loaded_zips:
                    logger.info(f"Zip file already loaded: {zip_name}")
                    return True
                
                # Add to loaded zips
                self.loaded_zips.add(zip_name)
                
                # Save configuration after loading
                self.save_config()
                
                # Notify any listeners that media files have changed
                if hasattr(self, 'on_media_changed') and self.on_media_changed:
                    self.on_media_changed()
                
                logger.info(f"Loaded zip file: {zip_name}")
                return True
            else:
                logger.warning(f"Attempted to load non-existent zip: {zip_name}")
                return False
        except Exception as e:
            logger.error(f"Error loading zip {zip_name}: {e}\n{traceback.format_exc()}")
            return False
    
    def unload_zip(self, zip_name):
        """Unload a zip file"""
        try:
            # Check if the zip is actually loaded
            if zip_name not in self.loaded_zips:
                logger.info(f"Zip file not loaded, nothing to unload: {zip_name}")
                return True
            
            # Remove from loaded zips
            self.loaded_zips.discard(zip_name)
            
            # Save configuration after unloading
            self.save_config()
            
            # Notify any listeners that media files have changed
            if hasattr(self, 'on_media_changed') and self.on_media_changed:
                self.on_media_changed()
            
            logger.info(f"Unloaded zip file: {zip_name}")
            return True
        except Exception as e:
            logger.error(f"Error unloading zip {zip_name}: {e}\n{traceback.format_exc()}")
            return False
    
    def set_on_media_changed_callback(self, callback):
        """Set a callback to be called when media files change"""
        self.on_media_changed = callback

    def _get_default_display_settings(self):
        """Get default display settings"""
        return {
            'interval': 0.1,
            'max_popups': 25,
            'popup_probability': 5,
            'panic_key': "'",
            'active_monitors': [0],
            'bounce_enabled': False
        }
