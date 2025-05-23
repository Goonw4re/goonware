#!/usr/bin/env python
"""
Uninstall script for Goonware application.
Removes .gmodel file associations from Windows registry only.
"""

import os
import sys
import logging
import ctypes
import winreg
import traceback
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def is_admin():
    """Check if the script is running with admin privileges"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def remove_registry_entries():
    """Remove all registry entries related to .gmodel files"""
    try:
        success = True
        
        # Try multiple approaches to ensure thorough registry cleanup
        
        # 1. Classes root key for file extension
        try:
            # First remove any associations that might prevent deletion
            try:
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, ".gmodel", 0, winreg.KEY_ALL_ACCESS) as key:
                    winreg.DeleteValue(key, "")  # Delete default value first
            except Exception as e:
                logger.debug(f"No default value for .gmodel: {e}")
                
            # Now delete the key itself
            winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, ".gmodel")
            logger.info("Removed .gmodel file extension association")
        except FileNotFoundError:
            logger.info(".gmodel file extension not found in registry")
        except Exception as e:
            logger.error(f"Error removing .gmodel extension: {e}")
            success = False

        # 2. HKCU file association
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FileExts\\.gmodel")
            logger.info("Removed .gmodel HKCU file extension")
        except FileNotFoundError:
            logger.info(".gmodel HKCU file extension not found")
        except Exception as e:
            logger.error(f"Error removing HKCU .gmodel extension: {e}")
            # Not critical, continue

        # 3. Delete all GModelFile keys using a recursive approach
        try:
            # Define all possible paths to clean
            gmodel_paths = [
                "GModelFile\\shell\\open\\command",
                "GModelFile\\shell\\open",
                "GModelFile\\shell\\View Model Contents\\command",
                "GModelFile\\shell\\View Model Contents",
                "GModelFile\\shell",
                "GModelFile\\DefaultIcon",
                "GModelFile"
            ]
            
            # Delete each path, starting from the deepest
            for path in gmodel_paths:
                try:
                    winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, path)
                    logger.info(f"Removed registry key: {path}")
                except FileNotFoundError:
                    logger.info(f"Registry key not found: {path}")
                except Exception as e:
                    logger.error(f"Error deleting registry key {path}: {e}")
                    success = False
                    
            logger.info("Removed GModelFile registry keys")
        except Exception as e:
            logger.error(f"Error removing GModelFile keys: {e}")
            success = False
            
        # 4. Check for any leftover ProgID references
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\Classes\\.gmodel", 0, winreg.KEY_ALL_ACCESS) as key:
                winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\Classes\\.gmodel")
                logger.info("Removed HKLM Classes .gmodel key")
        except FileNotFoundError:
            logger.info("HKLM Classes .gmodel key not found")
        except Exception as e:
            logger.error(f"Error removing HKLM Classes .gmodel key: {e}")
            # Not critical, continue
            
        # 5. Clean up the Applications key if it exists
        try:
            app_paths = [
                "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FileExts\\.gmodel\\OpenWithProgids",
                "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FileExts\\.gmodel\\OpenWithList",
                "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FileExts\\.gmodel"
            ]
            
            for path in app_paths:
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
                    logger.info(f"Removed HKCU key: {path}")
                except FileNotFoundError:
                    logger.debug(f"HKCU key not found: {path}")
                except Exception as e:
                    logger.error(f"Error deleting HKCU key {path}: {e}")
                    # Not critical

        except Exception as e:
            logger.error(f"Error cleaning up file extensions: {e}")
            # Continue anyway

        # Refresh shell icons - use multiple methods to ensure it works
        try:
            # Method 1: SHChangeNotify
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
            logger.info("Refreshed shell icons using SHChangeNotify")
            
            # Method 2: IE4UINIT
            try:
                os.system("ie4uinit.exe -show")
                logger.info("Refreshed shell icons using ie4uinit")
            except:
                logger.warning("Could not refresh shell icons with ie4uinit")
                
            # Method 3: Explorer restart
            try:
                os.system("taskkill /im explorer.exe /f")
                os.system("start explorer.exe")
                logger.info("Restarted explorer to refresh icons")
            except:
                logger.warning("Could not restart explorer")
        except Exception as e:
            logger.error(f"Error refreshing shell icons: {e}")
            logger.warning("You may need to restart your computer to see icon changes")
            # Continue anyway

        return success
    except Exception as e:
        logger.error(f"Error removing registry entries: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def main():
    """Main uninstall function"""
    print("=" * 60)
    print("          GOONWARE UNINSTALL UTILITY")
    print("=" * 60)
    print("\nThis utility will:")
    print("  1. Remove .gmodel file associations from the registry")
    print("\nNo files will be deleted from your computer.")
    print("=" * 60)
    
    # Check for admin rights
    if not is_admin():
        logger.error("This script requires administrator privileges.")
        print("\nPlease run this script as administrator.")
        print("Right-click on the script and select 'Run as administrator'.")
        input("\nPress Enter to exit...")
        return
    
    choice = input("\nDo you want to proceed with removing registry entries? (y/n): ").lower().strip()
    if choice != 'y':
        print("Operation cancelled.")
        input("\nPress Enter to exit...")
        return
    
    # Step 1: Remove registry entries
    print("\nRemoving registry entries...")
    if remove_registry_entries():
        print("✓ Registry entries removed successfully")
        print("\n✓ Operation completed successfully!")
    else:
        print("✗ Failed to remove some registry entries")
        print("\n⚠ Operation completed with some errors.")
        print("  Please check the log output above for details.")
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main() 