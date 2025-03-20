import os
import logging
import win32api
import win32con
import win32gui
import ctypes
import time
import threading
import win32process

logger = logging.getLogger(__name__)

# Define Windows message constants for custom window messages
WM_USER = 1024
WM_APP = 32768
WM_GOONWARE_MESSAGE = WM_APP + 100

class InstanceManager:
    def __init__(self, app_name="Goonware"):
        self.app_name = app_name
        self.lock_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'instance.lock')
        
        # Create assets directory if needed
        assets_dir = os.path.dirname(self.lock_file)
        if not os.path.exists(assets_dir):
            os.makedirs(assets_dir)
            logger.info(f"Created assets directory at: {assets_dir}")
        
        # For message passing between instances
        self.message_queue = []
        self.message_callback = None
        self.wnd_class = None
        self.hwnd = None
        self.is_listening = False
        
    def start_message_listener(self, callback=None):
        """Start listening for messages from other instances"""
        if self.is_listening:
            logger.warning("Message listener already running")
            return True
            
        try:
            self.message_callback = callback
            self.is_listening = True
            
            # Start listener in a separate thread to avoid blocking UI
            thread = threading.Thread(target=self._create_message_window, daemon=True)
            thread.start()
            
            # Give it a moment to initialize
            time.sleep(0.1)
            
            return True
        except Exception as e:
            logger.error(f"Error starting message listener: {e}")
            self.is_listening = False
            return False
    
    def _create_message_window(self):
        """Create a hidden window to receive messages"""
        try:
            # This needs to run in its own thread
            hinst = win32api.GetModuleHandle(None)
            
            # Register window class
            wnd_class = win32gui.WNDCLASS()
            wnd_class.hInstance = hinst
            wnd_class.lpszClassName = f"{self.app_name}MessageReceiver"
            wnd_class.lpfnWndProc = self._window_proc
            
            try:
                self.wnd_class = win32gui.RegisterClass(wnd_class)
                logger.info(f"Registered window class: {self.wnd_class}")
            except Exception as e:
                logger.error(f"Error registering window class: {e}")
                # Try unregistering first if it failed
                try:
                    win32gui.UnregisterClass(wnd_class.lpszClassName, hinst)
                    self.wnd_class = win32gui.RegisterClass(wnd_class)
                except:
                    # If it still fails, use a different class name
                    wnd_class.lpszClassName = f"{self.app_name}MessageReceiver_{int(time.time())}"
                    self.wnd_class = win32gui.RegisterClass(wnd_class)
            
            # Create window
            self.hwnd = win32gui.CreateWindow(
                wnd_class.lpszClassName,
                f"{self.app_name}MessageWindow",
                0, 0, 0, 0, 0,
                0, 0, hinst, None
            )
            
            logger.info(f"Created message window: {self.hwnd}")
            
            # Message loop
            msg = ctypes.wintypes.MSG()
            while self.is_listening:
                if win32gui.PeekMessage(ctypes.byref(msg), 0, 0, 0, win32con.PM_REMOVE):
                    win32gui.TranslateMessage(ctypes.byref(msg))
                    win32gui.DispatchMessage(ctypes.byref(msg))
                time.sleep(0.01)
                
            # Clean up
            if self.hwnd:
                win32gui.DestroyWindow(self.hwnd)
                self.hwnd = None
                
            if self.wnd_class:
                win32gui.UnregisterClass(wnd_class.lpszClassName, hinst)
                self.wnd_class = None
                
        except Exception as e:
            logger.error(f"Error in message window thread: {e}")
    
    def _window_proc(self, hwnd, msg, wparam, lparam):
        """Handle window messages"""
        try:
            if msg == WM_GOONWARE_MESSAGE:
                # Extract message from lparam (pointer to string)
                try:
                    # Get length of string from wparam
                    msg_len = wparam
                    if msg_len > 0:
                        # Create buffer to receive the string
                        buffer = ctypes.create_string_buffer(msg_len + 1)
                        ctypes.windll.kernel32.lstrcpyA(buffer, lparam)
                        message = buffer.value.decode('utf-8')
                        
                        logger.info(f"Received message: {message}")
                        
                        # Add to queue and process
                        self.message_queue.append(message)
                        self._process_message(message)
                except Exception as e:
                    logger.error(f"Error extracting message: {e}")
                
                return 0
                
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
        except Exception as e:
            logger.error(f"Error in window proc: {e}")
            return 0
    
    def _process_message(self, message):
        """Process received messages"""
        try:
            if message.startswith("open_model:"):
                model_path = message[len("open_model:"):]
                logger.info(f"Received request to open model: {model_path}")
                
                # Call the callback if registered
                if self.message_callback:
                    self.message_callback("open_model", model_path)
                
                # Show the window
                self.show_existing_window()
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def send_message(self, message):
        """Send a message to another running instance"""
        try:
            # Find the window of the other instance
            hwnd = win32gui.FindWindow(f"{self.app_name}MessageReceiver", f"{self.app_name}MessageWindow")
            if not hwnd:
                logger.warning("Could not find message window of other instance")
                return False
                
            # Allocate memory for the message
            message_bytes = message.encode('utf-8')
            msg_len = len(message_bytes)
            
            # Allocate memory in the target process
            pid = win32process.GetWindowThreadProcessId(hwnd)[1]
            h_process = win32api.OpenProcess(win32con.PROCESS_VM_OPERATION | win32con.PROCESS_VM_WRITE, False, pid)
            
            # Allocate memory in the target process
            remote_buffer = win32process.VirtualAllocEx(
                h_process, 0, msg_len + 1, win32con.MEM_COMMIT, win32con.PAGE_READWRITE
            )
            
            # Write the message to the allocated memory
            win32process.WriteProcessMemory(h_process, remote_buffer, message_bytes, msg_len)
            
            # Send the message
            win32gui.SendMessage(hwnd, WM_GOONWARE_MESSAGE, msg_len, remote_buffer)
            
            # Free the allocated memory
            win32process.VirtualFreeEx(h_process, remote_buffer, 0, win32con.MEM_RELEASE)
            win32api.CloseHandle(h_process)
            
            logger.info(f"Sent message to other instance: {message}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    def stop_message_listener(self):
        """Stop the message listener"""
        try:
            if self.is_listening:
                self.is_listening = False
                # Give it a moment to clean up
                time.sleep(0.2)
                return True
            return False
        except Exception as e:
            logger.error(f"Error stopping message listener: {e}")
            return False

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