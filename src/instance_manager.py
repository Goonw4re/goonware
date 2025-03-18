import os
import logging
import win32api
import win32con
import win32gui

logger = logging.getLogger(__name__)

class InstanceManager:
    def __init__(self, app_name="Goonware"):
        self.app_name = app_name
        self.lock_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'instance.lock')
        
        # Create assets directory if needed
        assets_dir = os.path.dirname(self.lock_file)
        if not os.path.exists(assets_dir):
            os.makedirs(assets_dir)
            logger.info(f"Created assets directory at: {assets_dir}")

    def check_instance(self):
        """Check if another instance is running"""
        try:
            logger.info("Checking for existing instance...")
            
            if os.path.exists(self.lock_file):
                logger.info("Found existing lock file")
                try:
                    with open(self.lock_file, 'r') as f:
                        pid = int(f.read().strip())
                    logger.info(f"Found PID in lock file: {pid}")
                    
                    # Check if process is running
                    handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, pid)
                    win32api.CloseHandle(handle)
                    logger.info(f"Found running instance with PID {pid}")
                    return True
                except Exception as e:
                    logger.info(f"Removing stale lock file: {e}")
                    os.remove(self.lock_file)
            
            # Create new lock file
            logger.info("Creating new lock file")
            with open(self.lock_file, 'w') as f:
                f.write(str(os.getpid()))
            logger.info("Created new lock file")
            return False
            
        except Exception as e:
            logger.error(f"Error checking instance: {e}")
            return False

    def show_existing_window(self):
        """Show the window of an existing instance"""
        try:
            hwnd = win32gui.FindWindow("TkTopLevel", self.app_name)
            if hwnd:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                win32gui.SetForegroundWindow(hwnd)
                logger.info(f"Found and showed window: {hwnd}")
                return True
            else:
                logger.warning(f"Could not find {self.app_name} window")
                return False
        except Exception as e:
            logger.error(f"Error showing existing window: {e}")
            return False

    def cleanup(self):
        """Clean up instance lock file"""
        try:
            logger.info(f"Cleaning up instance lock file: {self.lock_file}")
            
            # Check if the lock file exists
            if os.path.exists(self.lock_file):
                # Read the PID from the lock file
                try:
                    with open(self.lock_file, 'r') as f:
                        pid = int(f.read().strip())
                    
                    # Only remove if it's our PID
                    if pid == os.getpid():
                        os.remove(self.lock_file)
                        logger.info(f"Removed instance lock file for PID {pid}")
                    else:
                        logger.warning(f"Lock file contains different PID ({pid}), not removing")
                except ValueError:
                    # If the file doesn't contain a valid PID, remove it anyway
                    os.remove(self.lock_file)
                    logger.info("Removed invalid instance lock file")
                except Exception as e:
                    # If we can't read the file, try to remove it anyway
                    logger.error(f"Error reading lock file: {e}")
                    os.remove(self.lock_file)
                    logger.info("Removed instance lock file after read error")
            else:
                logger.info("Instance lock file does not exist, nothing to clean up")
                
            return True
        except Exception as e:
            logger.error(f"Error cleaning up instance lock file: {e}")
            return False
            
    def force_cleanup(self):
        """Force removal of the lock file regardless of PID"""
        try:
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
                logger.info("Forcibly removed instance lock file")
                return True
            return False
        except Exception as e:
            logger.error(f"Error during force cleanup: {e}")
            return False 