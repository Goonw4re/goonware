import os
import sys
import tkinter as tk
from tkinter import ttk
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path to allow importing from the project
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import converter GUI
from GoonConverter.src.gui import ConverterPanel, CustomTitleBar

def exit_application(root):
    """Close the application properly"""
    root.quit()
    root.destroy()

def main():
    """Main entry point for the standalone converter application"""
    # Create the main window with no title bar
    root = tk.Tk()
    root.title("GOONWARE CONVERTER")
    root.geometry("450x360")  # Reduced height from 400 to 360
    root.resizable(False, False)
    root.configure(bg='#252525')  # Match the dark theme
    root.overrideredirect(True)  # Remove the system title bar
    
    # Bind Alt+F4 to quit
    root.bind("<Alt-F4>", lambda e: exit_application(root))
    
    # Set window icon if available
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(script_dir))  # Go up to project root
        icon_path = os.path.join(project_root, "assets", "icon.png")
        
        if os.path.exists(icon_path):
            # Create a PhotoImage and set as icon
            icon = tk.PhotoImage(file=icon_path)
            root.iconphoto(True, icon)
    except Exception as e:
        logger.error(f"Error setting window icon: {e}")
    
    # Get models directory path
    models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'models')
    models_dir = os.path.abspath(models_dir)
    
    # Create main frame to hold everything
    main_frame = ttk.Frame(root, style='Modern.TFrame')
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Add custom title bar with exit callback
    title_bar = CustomTitleBar(main_frame, "GOONWARE CONVERTER", on_close=lambda: exit_application(root))
    
    # Create converter panel in the window
    converter_panel = ConverterPanel(main_frame, models_dir)
    converter_panel.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
    
    # Center the window on screen
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')
    
    # Start the main loop
    root.mainloop()

if __name__ == "__main__":
    main() 