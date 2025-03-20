import os
import logging
import tkinter as tk
from tkinter import ttk
import zipfile
from tkinter import messagebox
from PIL import Image, ImageTk
import io

# Configure logging
logger = logging.getLogger(__name__)

class FileBrowser(ttk.Frame):
    """File browser component for viewing and managing files in a ZIP/GMODEL archive"""
    
    def __init__(self, parent, on_file_selected, on_file_deleted=None, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.parent = parent
        self.on_file_selected = on_file_selected
        self.on_file_deleted = on_file_deleted
        self.archive_path = None
        self.current_files = []
        self.zipfile = None
        self.file_icons = {}  # Cache for file type icons
        self.path_to_id = {}  # Mapping from path to tree item ID
        
        # Configure style for dark theme
        style = ttk.Style()
        style.configure("FileBrowser.TFrame", 
                      background='#121212')
        self.configure(style="FileBrowser.TFrame")
        
        # Create title frame
        self.title_frame = ttk.Frame(self, style="FileBrowser.TFrame")
        
        # Create title label
        self.title_label = ttk.Label(
            self.title_frame,
            text="Archive Contents",
            style='Header.TLabel',
            anchor='center'
        )
        self.title_label.pack(fill=tk.X, expand=True, padx=5, pady=(5, 0))
        
        self.title_frame.pack(fill=tk.X)
        
        # Separator
        self.separator = ttk.Separator(self, orient='horizontal')
        self.separator.pack(fill=tk.X, padx=5, pady=5)
        
        # Create treeview frame
        self.tree_frame = ttk.Frame(self, style="FileBrowser.TFrame")
        
        # Create custom header frame
        self.header_frame = ttk.Frame(self.tree_frame, style="FileBrowser.TFrame")
        self.header_frame.pack(fill=tk.X, side=tk.TOP)
        
        # Create custom dark headers using Label widgets
        self.file_header = tk.Label(
            self.header_frame,
            text="Files",
            background="#121212",
            foreground="#FFFFFF",
            font=('Segoe UI', 9, 'bold'),
            anchor=tk.W,
            padx=5
        )
        self.file_header.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.size_header = tk.Label(
            self.header_frame,
            text="Size",
            background="#121212",
            foreground="#FFFFFF",
            font=('Segoe UI', 9, 'bold'),
            anchor=tk.E,
            width=10,
            padx=5
        )
        self.size_header.pack(side=tk.RIGHT)
        
        # Create a separator below the headers
        self.header_separator = ttk.Separator(self.tree_frame, orient='horizontal')
        self.header_separator.pack(fill=tk.X, side=tk.TOP)
        
        # Create treeview with single column for file name (better sizing control)
        self.tree = ttk.Treeview(
            self.tree_frame, 
            columns=("size",), 
            show="tree",  # Only show tree, not headings
            selectmode="browse",
            style="FileTree.Treeview"
        )
        self.tree.column("#0", width=250, stretch=tk.YES)
        self.tree.column("size", width=80, anchor=tk.E, stretch=tk.NO)
        
        # Create custom scrollbar - completely hidden
        self.scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview, style="Invisible.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=self._set_scrollbar)
        
        # Configure tree styling
        style.configure("FileTree.Treeview", 
                        background="#121212", 
                        foreground="#DCDCDC", 
                        fieldbackground="#121212",
                        borderwidth=0,
                        rowheight=26)
        
        # Hide expand/collapse indicators completely
        style.layout("FileTree.Treeview", [
            ('FileTree.Treeview.treearea', {'sticky': 'nswe'})
        ])
        
        # Configure the empty indicator layout
        style.configure("FileTree.Treeview",
                       indent=15,  # Control indentation level
                       background="#121212",
                       fieldbackground="#121212")
        
        # Further remove indicators by setting them to empty
        style.element_create("FileTree.Treeview.Indicator", "from", "default")
        style.layout("FileTree.Treeview.Row", [
            ('FileTree.Treeview.row', {'sticky': 'nswe', 'children': [
                ('FileTree.Treeview.cell', {'sticky': 'nswe', 'children': [
                    ('FileTree.Treeview.padding', {'sticky': 'nswe', 'children': [
                        ('FileTree.Treeview.image', {'side': 'left', 'sticky': ''}),
                        ('FileTree.Treeview.text', {'sticky': 'we'})
                    ]})
                ]})
            ]})
        ])
        
        # Set the Treeview selection colors
        style.map("FileTree.Treeview", 
                background=[('selected', '#6200EE')],
                foreground=[('selected', '#FFFFFF')])
        
        # Fix all tree colors for consistent appearance
        self.option_add('*TCombobox*Listbox.background', '#121212')
        self.option_add('*TCombobox*Listbox.foreground', '#FFFFFF')
        self.option_add('*Treeview.background', '#121212')
        self.option_add('*Treeview.foreground', '#FFFFFF')
        self.option_add('*Treeview.fieldBackground', '#121212')
        
        # Custom invisible scrollbar
        style.configure("Invisible.Vertical.TScrollbar",
                       background="#121212",
                       arrowcolor="#121212",
                       borderwidth=0,
                       troughcolor="#121212")
        style.map("Invisible.Vertical.TScrollbar",
                 background=[('active', '#121212'), ('disabled', '#121212')])
        
        # Create Header style for title
        style.configure('Header.TLabel',
                       font=('Segoe UI', 11, 'bold'),
                       background='#121212',
                       foreground='#BB86FC')
        
        # Pack treeview components
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Status bar
        self.status_frame = ttk.Frame(self, style="FileBrowser.TFrame")
        self.status_label = ttk.Label(
            self.status_frame,
            text="Ready",
            anchor='w',
            font=('Segoe UI', 8),
            foreground='#AAAAAA',
            background='#121212'
        )
        self.status_label.pack(side=tk.LEFT, fill=tk.X, padx=5, pady=2)
        
        # Pack main components
        self.tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Bind events
        self.tree.bind("<ButtonRelease-1>", self._on_file_click)  # Single click
        self.tree.bind("<Return>", self._on_file_click)
        self.tree.bind("<Button-3>", self._on_right_click)  # Right-click event
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        
        # Create context menu
        self.context_menu = tk.Menu(self, tearoff=0, bg='#1A1A1A', fg='#FFFFFF', activebackground='#6200EE', activeforeground='#FFFFFF')
        self.context_menu.add_command(label="Open", command=self._context_open)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Delete", command=self._context_delete)
        
        # Initialize file type icons
        self._create_file_icons()
    
    def _set_scrollbar(self, first, last):
        """Custom scrollbar setter that always hides the scrollbar"""
        self.scrollbar.set(first, last)
        # Always hide scrollbar
        if self.scrollbar.winfo_manager():
            self.scrollbar.pack_forget()
    
    def _create_file_icons(self):
        """Create icons for different file types"""
        try:
            # Create a tiny image for each file type
            icon_size = 16
            
            # Directory icon (folder closed)
            folder_img = Image.new('RGBA', (icon_size, icon_size), (0, 0, 0, 0))
            folder_draw = self._get_image_drawer(folder_img)
            folder_draw.rectangle([1, 4, 15, 14], fill="#FFC107", outline="#E69500")
            folder_draw.rectangle([1, 2, 8, 4], fill="#FFC107", outline="#E69500")
            self.file_icons["directory"] = ImageTk.PhotoImage(folder_img)
            
            # Directory icon (folder open)
            folder_open_img = Image.new('RGBA', (icon_size, icon_size), (0, 0, 0, 0))
            folder_open_draw = self._get_image_drawer(folder_open_img)
            folder_open_draw.rectangle([1, 4, 15, 14], fill="#FFD54F", outline="#E69500")
            folder_open_draw.rectangle([1, 2, 8, 4], fill="#FFD54F", outline="#E69500")
            folder_open_draw.rectangle([3, 10, 13, 14], fill="#E69500", outline="#E69500")
            self.file_icons["directory_open"] = ImageTk.PhotoImage(folder_open_img)
            
            # Image icon
            image_img = Image.new('RGBA', (icon_size, icon_size), (0, 0, 0, 0))
            image_draw = self._get_image_drawer(image_img)
            image_draw.rectangle([1, 1, 15, 15], fill="#2196F3", outline="#0D47A1")
            image_draw.rectangle([4, 4, 12, 8], fill="#FFFFFF", outline=None)
            image_draw.ellipse([6, 5, 9, 8], fill="#FF5722")
            self.file_icons["image"] = ImageTk.PhotoImage(image_img)
            
            # Video icon
            video_img = Image.new('RGBA', (icon_size, icon_size), (0, 0, 0, 0))
            video_draw = self._get_image_drawer(video_img)
            video_draw.rectangle([1, 1, 15, 15], fill="#F44336", outline="#B71C1C")
            video_draw.polygon([6, 5, 11, 8, 6, 11], fill="#FFFFFF")
            self.file_icons["video"] = ImageTk.PhotoImage(video_img)
            
            # Audio icon
            audio_img = Image.new('RGBA', (icon_size, icon_size), (0, 0, 0, 0))
            audio_draw = self._get_image_drawer(audio_img)
            audio_draw.rectangle([1, 1, 15, 15], fill="#4CAF50", outline="#1B5E20")
            audio_draw.rectangle([5, 4, 7, 12], fill="#FFFFFF")
            audio_draw.rectangle([9, 6, 11, 10], fill="#FFFFFF")
            self.file_icons["audio"] = ImageTk.PhotoImage(audio_img)
            
            # Text icon
            text_img = Image.new('RGBA', (icon_size, icon_size), (0, 0, 0, 0))
            text_draw = self._get_image_drawer(text_img)
            text_draw.rectangle([1, 1, 15, 15], fill="#9C27B0", outline="#4A148C")
            text_draw.line([4, 5, 12, 5], fill="#FFFFFF", width=1)
            text_draw.line([4, 8, 12, 8], fill="#FFFFFF", width=1)
            text_draw.line([4, 11, 10, 11], fill="#FFFFFF", width=1)
            self.file_icons["text"] = ImageTk.PhotoImage(text_img)
            
            # Generic file icon
            file_img = Image.new('RGBA', (icon_size, icon_size), (0, 0, 0, 0))
            file_draw = self._get_image_drawer(file_img)
            file_draw.rectangle([1, 1, 15, 15], fill="#607D8B", outline="#263238")
            file_draw.rectangle([4, 5, 12, 11], fill="#B0BEC5")
            self.file_icons["file"] = ImageTk.PhotoImage(file_img)
            
        except Exception as e:
            logger.error(f"Error creating file icons: {e}")
            # If icons fail, we'll fall back to text labels
    
    def _get_image_drawer(self, img):
        """Get an ImageDraw object for the given image"""
        try:
            from PIL import ImageDraw
            return ImageDraw.Draw(img)
        except ImportError:
            logger.error("PIL.ImageDraw not available for icons")
            return None
    
    def load_archive(self, archive_path):
        """Load files from ZIP/GMODEL archive"""
        try:
            self.archive_path = archive_path
            self.tree.delete(*self.tree.get_children())
            self.current_files = []
            
            # Close previous zipfile if open
            if self.zipfile:
                self.zipfile.close()
            
            # Open the archive
            self.zipfile = zipfile.ZipFile(archive_path, 'r')
            
            # Get file info
            file_infos = self.zipfile.infolist()
            
            # Update status
            self.status_label.config(text=f"Loading {len(file_infos)} files...")
            self.update()  # Force UI update
            
            # Sort by filename
            file_infos.sort(key=lambda x: x.filename)
            
            # Add directories first (for structure)
            directories = set()
            
            for file_info in file_infos:
                # Skip directories themselves
                if file_info.filename.endswith('/'):
                    continue
                
                # Add file's directory and all parent directories
                parts = file_info.filename.split('/')
                for i in range(1, len(parts)):
                    directories.add('/'.join(parts[:i]) + '/')
            
            # Create directory structure
            directories = sorted(list(directories))
            directory_nodes = {}  # Store node IDs for quick lookup
            
            for directory in directories:
                # Create directory nodes
                parts = directory.rstrip('/').split('/')
                parent = ""
                parent_id = ""  # Root
                
                for i, part in enumerate(parts):
                    current_path = '/'.join(parts[:i+1]) + '/'
                    
                    # If this node already exists, just update parent_id and continue
                    if current_path in directory_nodes:
                        parent_id = directory_nodes[current_path]
                        continue
                    
                    # Create new node
                    node_id = self.tree.insert(
                        parent_id, 
                        "end", 
                        text=part, 
                        values=("", current_path),  # Store path in values
                        tags=("directory",),
                        open=False
                    )
                    
                    # Store node ID for future reference
                    directory_nodes[current_path] = node_id
                    
                    # Set folder icon
                    if "directory" in self.file_icons:
                        self.tree.item(node_id, image=self.file_icons["directory"])
                    
                    # Update parent for next iteration
                    parent_id = node_id
            
            # Add files
            file_count = 0
            for file_info in file_infos:
                # Skip directories
                if file_info.filename.endswith('/'):
                    continue
                
                file_count += 1
                
                # Store file info
                self.current_files.append({
                    'path': file_info.filename,
                    'size': file_info.file_size,
                    'compress_size': file_info.compress_size,
                    'date_time': file_info.date_time
                })
                
                # Get path parts
                parts = file_info.filename.split('/')
                filename = parts[-1]
                directory = '/'.join(parts[:-1]) + '/' if len(parts) > 1 else ""
                
                # Find parent node
                parent_id = directory_nodes.get(directory, "")  # Root if directory not found
                
                # Format file size
                size_str = self._format_size(file_info.file_size)
                
                # Determine file type
                file_type = self._get_file_type(filename)
                
                # Insert file node
                node_id = self.tree.insert(
                    parent_id, 
                    "end", 
                    text=filename, 
                    values=(size_str, file_info.filename),  # Store full path in values
                    tags=(file_type,)
                )
                
                # Set file type icon
                if file_type in self.file_icons:
                    self.tree.item(node_id, image=self.file_icons[file_type])
            
            # Don't automatically expand root level folders
            # for item in self.tree.get_children():
            #     self.tree.item(item, open=True)
            
            # Update status with file count
            self.status_label.config(text=f"{file_count} files loaded")
                
            return True
        except Exception as e:
            logger.error(f"Error loading archive: {e}")
            error_message = f"Error loading archive: {str(e)}"
            self.status_label.config(text=error_message, foreground="#FF5252")
            messagebox.showerror("Error", f"Failed to load archive:\n{str(e)}")
            return False
    
    def _format_size(self, size_bytes):
        """Format file size in human-readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    
    def _get_file_type(self, filename):
        """Determine file type based on extension"""
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tif', '.tiff', '.webp']:
            return "image"
        elif ext in ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']:
            return "video"
        elif ext in ['.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a']:
            return "audio"
        elif ext in ['.txt', '.md', '.csv', '.json', '.xml', '.html', '.css', '.js']:
            return "text"
        else:
            return "file"
    
    def _on_file_click(self, event):
        """Handle single click on file"""
        # Get selected item
        item_id = self.tree.focus()
        if not item_id:
            return
        
        # Check if it's a directory
        if "directory" in self.tree.item(item_id, "tags"):
            # Toggle directory expansion
            if self.tree.item(item_id, "open"):
                self.tree.item(item_id, open=False)
                # Update icon to closed folder
                if "directory" in self.file_icons:
                    self.tree.item(item_id, image=self.file_icons["directory"])
            else:
                self.tree.item(item_id, open=True)
                # Update icon to open folder
                if "directory_open" in self.file_icons:
                    self.tree.item(item_id, image=self.file_icons["directory_open"])
                
            # Update status to show directory name
            dir_name = self.tree.item(item_id, "text")
            self.status_label.config(text=f"Directory: {dir_name}")
            return
        
        # Get file path
        file_path = self._get_full_path(item_id)
        if file_path:
            self.status_label.config(text=f"Opening: {os.path.basename(file_path)}")
            self.on_file_selected(file_path)
    
    def _on_tree_select(self, event):
        """Handle selection of an item in the tree"""
        item_id = self.tree.focus()
        if not item_id:
            return
            
        # Update status bar with selected item
        item_text = self.tree.item(item_id, "text")
        if "directory" in self.tree.item(item_id, "tags"):
            self.status_label.config(text=f"Directory: {item_text}")
        else:
            file_path = self._get_full_path(item_id)
            if file_path:
                self.status_label.config(text=f"Selected: {file_path}")
    
    def _on_right_click(self, event):
        """Handle right-click on file"""
        # Identify the item being clicked
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        
        # Select the item
        self.tree.selection_set(item_id)
        self.tree.focus(item_id)
        
        # Show context menu
        self.context_menu.post(event.x_root, event.y_root)
    
    def _context_open(self):
        """Open selected file from context menu"""
        item_id = self.tree.focus()
        if not item_id:
            return
        
        # Check if it's a directory
        if "directory" in self.tree.item(item_id, "tags"):
            return
        
        # Get file path
        file_path = self._get_full_path(item_id)
        if file_path:
            self.status_label.config(text=f"Opening: {os.path.basename(file_path)}")
            self.on_file_selected(file_path)
    
    def _context_delete(self):
        """Delete selected file from context menu"""
        if not self.on_file_deleted:
            return
            
        item_id = self.tree.focus()
        if not item_id:
            return
        
        # Check if it's a directory
        if "directory" in self.tree.item(item_id, "tags"):
            messagebox.showinfo("Info", "Directory deletion is not supported")
            return
        
        # Get file path
        file_path = self._get_full_path(item_id)
        if not file_path:
            return
            
        # Confirm deletion
        if messagebox.askyesno("Confirm", f"Delete file '{file_path}'?"):
            # Call the deletion callback
            self.status_label.config(text=f"Deleting: {os.path.basename(file_path)}")
            success = self.on_file_deleted(file_path)
            
            # If successful, remove from tree
            if success:
                self.tree.delete(item_id)
                self.status_label.config(text=f"Deleted: {os.path.basename(file_path)}")
                
                # Update files list
                self.current_files = [f for f in self.current_files if f['path'] != file_path]
    
    def _get_full_path(self, item_id):
        """Get full path from a tree item"""
        if not item_id:
            return None
        
        # Get the stored path directly from the values if available
        values = self.tree.item(item_id, "values")
        if len(values) > 1 and values[1]:
            return values[1]
            
        # Item text (filename)
        item_text = self.tree.item(item_id, "text")
        
        # Build path from parents
        parts = [item_text]
        parent = self.tree.parent(item_id)
        
        while parent:
            parts.insert(0, self.tree.item(parent, "text"))
            parent = self.tree.parent(parent)
        
        # Combine parts into path
        path = '/'.join(parts)
        
        # Find matching file in current_files
        for file_info in self.current_files:
            if file_info['path'] == path or file_info['path'].endswith('/' + path):
                return file_info['path']
        
        # If we couldn't find a direct match, try a case-insensitive match
        path_lower = path.lower()
        for file_info in self.current_files:
            if file_info['path'].lower() == path_lower or file_info['path'].lower().endswith('/' + path_lower):
                return file_info['path']
        
        return path  # Return the constructed path as a fallback
    
    def destroy(self):
        """Clean up resources when widget is destroyed"""
        # Close zipfile if open
        if self.zipfile:
            self.zipfile.close()
            self.zipfile = None
        
        # Call parent destroy
        super().destroy() 

    def _build_tree(self, parent_id, folder_data):
        """Recursively build the tree structure from the folder data"""
        for item in folder_data:
            is_folder = 'children' in item
            
            # Determine item icon based on type
            icon = self._get_icon_for_item(item)
            
            # Insert the item into the tree
            item_id = self.tree.insert(
                parent_id, 
                tk.END, 
                text=item['name'], 
                values=(item.get('path', ''), 'folder' if is_folder else 'file', item.get('size', '')),
                image=icon,
                open=False  # Make sure folders are closed by default
            )
            
            # Add to path -> id mapping for quick selection
            if 'path' in item:
                self.path_to_id[item['path']] = item_id
            
            # Process children recursively if it's a folder
            if is_folder and 'children' in item:
                self._build_tree(item_id, item['children']) 