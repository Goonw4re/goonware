from tkinter import ttk

def configure_styles():
    """Configure modern styles for the application"""
    style = ttk.Style()
    
    # Base styles
    style.configure('Modern.TFrame',
                   background='#1e1e1e')
    
    # Label frame styles
    style.configure('Modern.TLabelframe',
                   background='#1e1e1e',
                   foreground='white',
                   bordercolor='#1e1e1e',
                   darkcolor='#1e1e1e',
                   lightcolor='#1e1e1e',
                   borderwidth=0,
                   relief='flat')
    style.configure('Modern.TLabelframe.Label',
                   background='#1e1e1e',
                   foreground='white',
                   font=('Segoe UI', 11, 'bold'))
    
    # Button styles
    style.configure('Modern.TButton',
                   foreground='black',
                   background='#2b2b2b',
                   font=('Segoe UI', 10))
    style.configure('Modern.Danger.TButton',
                   foreground='black',
                   background='#ff4444',
                   font=('Segoe UI', 10, 'bold'))
    
    # Label styles
    style.configure('Modern.TLabel',
                   foreground='white',
                   background='#1e1e1e',
                   font=('Segoe UI', 10))
    
    # Checkbox styles
    style.configure('Modern.TCheckbutton',
                   foreground='white',
                   background='#1e1e1e',
                   font=('Segoe UI', 10))
    
    # Scale styles
    style.configure('Modern.Horizontal.TScale',
                   background='#1e1e1e',
                   troughcolor='#3d3d3d',
                   slidercolor='#007acc')
