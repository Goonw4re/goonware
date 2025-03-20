import os
import zipfile
import logging
import traceback
import tempfile

logger = logging.getLogger(__name__)

class MediaPathManager:
    def __init__(self):
        # Store the models directory path
        self.models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'models')
        if not os.path.exists(self.models_dir):
            os.makedirs(self.models_dir)
            logger.info(f"Created models directory at: {self.models_dir}")
            
        # Store the assets directory path
        self.assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets')
        if not os.path.exists(self.assets_dir):
            os.makedirs(self.assets_dir)
            logger.info(f"Created assets directory at: {self.assets_dir}")
            
        # Create resources directories in assets
        self.resources_dir = os.path.join(self.assets_dir, 'resources')
        self.img_dir = os.path.join(self.resources_dir, 'img')
        self.vid_dir = os.path.join(self.resources_dir, 'vid')
        os.makedirs(self.img_dir, exist_ok=True)
        os.makedirs(self.vid_dir, exist_ok=True)
    
    def get_media_paths(self, selected_zips=None):
        """Get all media paths from the models directory"""
        try:
            logger.info("Getting media paths...")
            logger.info(f"Selected zips: {selected_zips if selected_zips else 'All'}")
            
            # Initialize paths
            image_paths = []  # Will store tuples of (zip_path, image_name)
            gif_paths = []    # Will store tuples of (zip_path, gif_name) 
            video_paths = []  # Will store tuples of (zip_path, video_name)
            
            # Supported file extensions
            image_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
            gif_extensions = {'.gif'}
            video_extensions = {'.mp4', '.avi', '.mov', '.wmv', '.flv'}
            
            # Scan models directory for zip files and loose media files
            for item in os.listdir(self.models_dir):
                item_path = os.path.join(self.models_dir, item)
                logger.debug(f"Found item: {item_path}")
                
                # Handle zip and gmodel files (both use the zip format)
                if item.lower().endswith(('.zip', '.gmodel')):
                    # Skip if not in selected_zips (if provided)
                    if selected_zips is not None and item not in selected_zips and item_path not in selected_zips:
                        logger.debug(f"Skipping unselected archive: {item}")
                        continue
                        
                    logger.info(f"Processing archive file: {item_path}")
                    try:
                        with zipfile.ZipFile(item_path, 'r') as zf:
                            # List all files in zip
                            file_list = zf.namelist()
                            logger.info(f"Found {len(file_list)} files in {item}")
                            
                            for file_info in zf.filelist:
                                file_name = file_info.filename
                                ext = os.path.splitext(file_name)[1].lower()
                                
                                # Skip directories and hidden files
                                if file_info.is_dir() or file_name.startswith('__MACOSX') or file_name.startswith('.'):
                                    continue
                                
                                # Categorize files
                                if ext in image_extensions:
                                    image_paths.append((item_path, file_name))
                                elif ext in gif_extensions:
                                    gif_paths.append((item_path, file_name))
                                elif ext in video_extensions:
                                    video_paths.append((item_path, file_name))
                    except Exception as e:
                        logger.error(f"Error processing archive file {item_path}: {e}")
                        continue
                
                # Handle loose files
                else:
                    ext = os.path.splitext(item)[1].lower()
                    # Use tuples for loose files too to maintain consistent format
                    if ext in image_extensions:
                        image_paths.append((self.models_dir, item))
                        logger.debug(f"Found loose image: {item}")
                    elif ext in gif_extensions:
                        gif_paths.append((self.models_dir, item))
                        logger.debug(f"Found loose GIF: {item}")
                    elif ext in video_extensions:
                        video_paths.append((self.models_dir, item))
                        logger.debug(f"Found loose video: {item}")
            
            logger.info(f"Found {len(image_paths)} images, {len(gif_paths)} GIFs, and {len(video_paths)} videos")
            
            # Log some sample paths for debugging
            if image_paths:
                logger.info(f"Sample image paths: {image_paths[:3]}")
            if gif_paths:
                logger.info(f"Sample GIF paths: {gif_paths[:3]}")
            if video_paths:
                logger.info(f"Sample video paths: {video_paths[:3]}")
            
            # Return as dictionary
            return {
                'images': image_paths,
                'gifs': gif_paths,
                'videos': video_paths
            }
            
        except Exception as e:
            logger.error(f"Error getting media paths: {e}\n{traceback.format_exc()}")
            return {'images': [], 'gifs': [], 'videos': []}
    
    def extract_file_from_zip(self, zip_path, internal_path, target_dir=None):
        """Extract a file from a zip or gmodel archive to a temporary file"""
        try:
            if not target_dir:
                target_dir = tempfile.gettempdir()
            
            if not os.path.exists(zip_path):
                logger.error(f"ZIP/GMODEL file not found: {zip_path}")
                return None
            
            # Both .zip and .gmodel files use the same zipfile format
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                if internal_path not in zip_ref.namelist():
                    logger.error(f"File {internal_path} not found in archive {zip_path}")
                    return None
                    
                temp_file = os.path.join(target_dir, f"temp_{int(time.time())}_{os.path.basename(internal_path)}")
                
                with zip_ref.open(internal_path) as f_in, open(temp_file, 'wb') as f_out:
                    f_out.write(f_in.read())
            
            logger.info(f"Extracted file to temporary location: {temp_file}")
            return temp_file
            
        except Exception as e:
            logger.error(f"Error extracting temporary file: {e}\n{traceback.format_exc()}")
            return None
    
    def cleanup_temp_file(self, temp_file):
        """Clean up a temporary file"""
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
                logger.info(f"Removed temporary file: {temp_file}")
                return True
            except Exception as e:
                logger.error(f"Error removing temporary file: {e}")
                return False
        return False 