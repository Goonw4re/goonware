import os
import shutil
import logging
import traceback
import zipfile
import tempfile
import subprocess
import winreg
from pathlib import Path
import sys

# Try to import PIL for icon conversion
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logging.warning("PIL not available, icon conversion functionality limited")

logger = logging.getLogger(__name__)

class GoonConverter:
    """
    Converts zip files to gmodel files, which are functionally identical but with a different extension.
    This allows for better organization and custom icon association.
    """
    
    def __init__(self, models_dir=None):
        """Initialize the converter with the models directory path"""
        if models_dir is None:
            self.models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'models')
        else:
            self.models_dir = models_dir
            
        # Ensure models directory exists
        if not os.path.exists(self.models_dir):
            os.makedirs(self.models_dir)
            logger.info(f"Created models directory at: {self.models_dir}")
            
        # Get path to the icon file
        self.icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'assets', 'icon.png')
        if not os.path.exists(self.icon_path):
            logger.warning(f"Icon file not found at: {self.icon_path}")
            self.icon_path = None
        else:
            logger.info(f"Using icon file: {self.icon_path}")
            
        # Get path to the ico file
        self.ico_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'assets', 'icon.ico')
        if not os.path.exists(self.ico_path) and self.icon_path and HAS_PIL:
            # Try to convert png to ico
            self.convert_png_to_ico(self.icon_path, self.ico_path)
        elif not os.path.exists(self.ico_path):
            logger.warning(f"Icon ICO file not found at: {self.ico_path}")
            self.ico_path = None
    
    def convert_to_gmodel(self, zip_path, delete_original=False, compress=True):
        """
        Convert a zip file to a gmodel file with optional compression
        
        Args:
            zip_path: Path to the zip file
            delete_original: Whether to delete the original zip file after conversion
            compress: Whether to recompress the contents (default: True)
            
        Returns:
            Path to the new gmodel file, or None if conversion failed
        """
        try:
            # Validate input file
            if not os.path.exists(zip_path):
                logger.error(f"File not found: {zip_path}")
                return None
                
            # Check if it's a zip file
            if not zip_path.lower().endswith('.zip'):
                logger.error(f"File is not a zip file: {zip_path}")
                return None
            
            # Create the output path
            filename = os.path.basename(zip_path)
            basename = os.path.splitext(filename)[0]
            gmodel_filename = f"{basename}.gmodel"
            gmodel_path = os.path.join(self.models_dir, gmodel_filename)
            
            # Check if the gmodel file already exists
            if os.path.exists(gmodel_path):
                logger.warning(f"Gmodel file already exists: {gmodel_path}")
                return None
            
            if compress:
                # Create a new compressed gmodel file
                logger.info(f"Creating compressed GMODEL file: {gmodel_path}")
                with zipfile.ZipFile(zip_path, 'r') as source_zip:
                    with zipfile.ZipFile(gmodel_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as target_zip:
                        # Copy all files with maximum compression
                        for item in source_zip.infolist():
                            # Read the data
                            file_data = source_zip.read(item.filename)
                            
                            # Create a new ZipInfo object to preserve metadata
                            info = zipfile.ZipInfo(item.filename)
                            info.date_time = item.date_time
                            info.compress_type = zipfile.ZIP_DEFLATED
                            info.external_attr = item.external_attr
                            
                            # Write the file with preserved metadata
                            target_zip.writestr(info, file_data)
                            
                            # Log progress for large files
                            if item.file_size > 10 * 1024 * 1024:  # 10MB
                                logger.info(f"Compressed: {item.filename} ({item.file_size / 1024 / 1024:.2f}MB)")
            else:
                # Simple copy with extension change (no compression)
                shutil.copy2(zip_path, gmodel_path)
                logger.info(f"Converted {zip_path} to {gmodel_path} (without compression)")
            
            # Apply custom icon to the .gmodel file
            if self.icon_path and os.path.exists(self.icon_path):
                self.set_custom_icon_for_file(gmodel_path)
            
            # Delete original if requested
            if delete_original:
                os.remove(zip_path)
                logger.info(f"Deleted original file: {zip_path}")
            
            return gmodel_path
            
        except Exception as e:
            logger.error(f"Error converting to gmodel: {e}\n{traceback.format_exc()}")
            return None
    
    def batch_convert(self, delete_originals=False, compress=True):
        """
        Convert all zip files in the models directory to gmodel files
        
        Args:
            delete_originals: Whether to delete the original zip files after conversion
            compress: Whether to recompress the contents (default: True)
            
        Returns:
            Dictionary with statistics about the conversion
        """
        try:
            stats = {
                'total': 0,
                'success': 0,
                'failures': 0,
                'skipped': 0
            }
            
            # Get all zip files in the models directory
            for filename in os.listdir(self.models_dir):
                if filename.lower().endswith('.zip'):
                    stats['total'] += 1
                    zip_path = os.path.join(self.models_dir, filename)
                    
                    # Check if corresponding gmodel file already exists
                    basename = os.path.splitext(filename)[0]
                    gmodel_filename = f"{basename}.gmodel"
                    gmodel_path = os.path.join(self.models_dir, gmodel_filename)
                    
                    if os.path.exists(gmodel_path):
                        logger.info(f"Skipping {filename} as {gmodel_filename} already exists")
                        stats['skipped'] += 1
                        continue
                    
                    # Convert file
                    result = self.convert_to_gmodel(zip_path, delete_originals, compress)
                    
                    if result:
                        stats['success'] += 1
                    else:
                        stats['failures'] += 1
            
            # Ensure the .gmodel extension is associated with the icon
            if stats['success'] > 0:
                self.register_file_association()
            
            logger.info(f"Batch conversion completed: {stats['success']} converted, {stats['failures']} failed, {stats['skipped']} skipped")
            return stats
            
        except Exception as e:
            logger.error(f"Error in batch conversion: {e}\n{traceback.format_exc()}")
            return {'total': 0, 'success': 0, 'failures': 0, 'skipped': 0}
    
    def set_custom_icon_for_file(self, file_path):
        """
        Set a custom icon for a specific .gmodel file using Windows APIs
        
        Args:
            file_path: Path to the .gmodel file
        """
        try:
            if not self.icon_path or not os.path.exists(self.icon_path):
                logger.warning("Icon file not found, skipping icon association")
                return False
                
            logger.info(f"Setting custom icon for file: {file_path}")
            
            # First, ensure the extension is associated with the icon
            self.register_file_association()
                
            return True
            
        except Exception as e:
            logger.error(f"Error setting custom icon for file: {e}\n{traceback.format_exc()}")
            return False
    
    def convert_png_to_ico(self, png_path, ico_path):
        """
        Convert a PNG image to ICO format for Windows icon association
        
        Args:
            png_path: Path to the PNG file
            ico_path: Path to save the ICO file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not HAS_PIL:
                logger.warning("PIL not available, cannot convert PNG to ICO")
                return False
                
            logger.info(f"Converting PNG to ICO: {png_path} -> {ico_path}")
            
            # Open the PNG file
            img = Image.open(png_path)
            
            # ICO format supports multiple sizes, so let's create different sizes
            sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
            icon_sizes = []
            
            for size in sizes:
                # Create a resized copy
                resized_img = img.resize(size, Image.Resampling.LANCZOS)
                
                # Convert to RGBA if not already
                if resized_img.mode != 'RGBA':
                    resized_img = resized_img.convert('RGBA')
                    
                icon_sizes.append(resized_img)
            
            # Save as ICO with multiple sizes
            icon_sizes[0].save(ico_path, format='ICO', sizes=[(img.size[0], img.size[1]) for img in icon_sizes])
            
            logger.info(f"Successfully converted PNG to ICO: {ico_path}")
            self.ico_path = ico_path
            return True
            
        except Exception as e:
            logger.error(f"Error converting PNG to ICO: {e}\n{traceback.format_exc()}")
            return False
            
    def register_file_association(self):
        """
        Register the .gmodel extension with the system and associate it with the custom icon
        """
        try:
            # Try with .ico file first
            if self.ico_path and os.path.exists(self.ico_path):
                icon_path = os.path.abspath(self.ico_path)
            # Fall back to .png file if .ico not available
            elif self.icon_path and os.path.exists(self.icon_path):
                icon_path = os.path.abspath(self.icon_path)
            else:
                logger.warning("No icon file found, skipping file association registration")
                return False
                
            logger.info("Registering .gmodel file association with custom icon")
            
            # Find the path to the main application
            app_path = os.path.abspath(sys.executable)
            
            # Find the path to file_viewer.py in the main src folder
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            file_viewer_path = os.path.join(project_root, "src", "file_viewer.py")
            
            # If the file_viewer.py doesn't exist in the src folder, look for it in the current directory
            if not os.path.exists(file_viewer_path):
                current_dir = os.path.dirname(os.path.abspath(__file__))
                file_viewer_path = os.path.join(current_dir, "file_viewer.py")
            
            # Final fallback: check if there's a file_viewer.py anywhere in the project
            if not os.path.exists(file_viewer_path):
                for root, dirs, files in os.walk(project_root):
                    if "file_viewer.py" in files:
                        file_viewer_path = os.path.join(root, "file_viewer.py")
                        break
            
            if not os.path.exists(file_viewer_path):
                logger.warning(f"Could not find file_viewer.py, using main.py instead")
                # Use the main.py with --open-model parameter as a fallback
                main_path = os.path.join(project_root, "src", "main.py")
                if os.path.exists(main_path):
                    open_command = f'"{app_path}" "{main_path}" --open-model "%1"'
                else:
                    logger.error("Could not find main.py either, file association will not work properly")
                    return False
            else:
                # Create the command to run the viewer
                open_command = f'"{app_path}" "{file_viewer_path}" "%1"'
            
            logger.info(f"Using viewer command: {open_command}")
            
            # 1. Create file type association
            try:
                # Create .gmodel key
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.gmodel") as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "GModelFile")
                
                # Create GModelFile key
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\GModelFile") as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "GMODEL Model File")
                
                # Set default icon
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\GModelFile\DefaultIcon") as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"{icon_path},0")
                
                # Set open command
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\GModelFile\shell\open\command") as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, open_command)
                
                # Add "View Contents" command to right-click menu
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\GModelFile\shell\viewcontents") as view_key:
                    winreg.SetValueEx(view_key, "", 0, winreg.REG_SZ, "View Model Contents")
                    
                    # Add icon for the command
                    winreg.SetValueEx(view_key, "Icon", 0, winreg.REG_SZ, icon_path)
                    
                    # Set the command
                    with winreg.CreateKey(view_key, "command") as view_cmd_key:
                        winreg.SetValueEx(view_cmd_key, "", 0, winreg.REG_SZ, open_command)
                
                # Register in Explorer FileExts
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.gmodel") as key:
                    with winreg.CreateKey(key, "UserChoice") as choice_key:
                        winreg.SetValueEx(choice_key, "ProgId", 0, winreg.REG_SZ, "GModelFile")
                
                logger.info(f"Registered .gmodel extension with icon: {icon_path}")
                logger.info(f"Registered open command: {open_command}")
                
                # Notify the system of the change
                try:
                    subprocess.run(["assoc", ".gmodel=GModelFile"], shell=True, check=True)
                    subprocess.run(["ftype", f"GModelFile={open_command}"], shell=True, check=True)
                    
                    # Force Windows to refresh shell icons
                    try:
                        import ctypes
                        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
                    except:
                        subprocess.run(["ie4uinit.exe", "-show"], shell=True, check=False)
                    
                    logger.info("File association commands executed successfully")
                except subprocess.SubprocessError as e:
                    logger.error(f"Error executing file association commands: {e}")
            
            except Exception as e:
                logger.error(f"Error setting registry keys for file association: {e}\n{traceback.format_exc()}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error registering file association: {e}\n{traceback.format_exc()}")
            return False 