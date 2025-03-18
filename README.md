# GOONWARE

A powerful media display application that shows random images, GIFs, and videos from selected zip files with advanced customization options, multi-monitor support, and interactive animations.

> [!WARNING]
>This application is designed for displaying EXPLICIT ADULT CONTENT. Users must:
>- Be 18+ or of legal age in their jurisdiction
>- Be in a completely private setting ( or not :wink:)
>- Accept full responsibility for viewing content
>- Understand that viewed content cannot be unseen

## 🔑 Key Features

### Advanced Media Display
- Shows images, animated GIFs, and videos across multiple monitors simultaneously
- Intelligently distributes content across all your screens
- Maintains proper aspect ratios and scaling for all media types
- Supports transparent PNGs and high-quality animated GIFs
- Plays videos with audio and proper duration handling

### Multi-Monitor Support
- Full support for multiple monitor setups
- Select which monitors to use for display
- Configure each monitor independently
- Keeps windows on their assigned monitor during animations
- Respects monitor boundaries for proper display

### Interactive Animations
- Dynamic bounce animation that keeps windows within monitor boundaries
- Configurable bounce probability (set percentage of windows that bounce)
- Physics-based movement with realistic collision detection
- Smooth animations optimized for performance
- Windows maintain proper visibility during animations

### Customizable Display Controls
- Precise display interval control (0.1s to 300s)
- Adjustable maximum number of simultaneous popups (1-250)
- Fine-grained popup probability control (1-100%)
- Individual close buttons on each popup
- Automatic cleanup of resources

### Safety Features
- Emergency panic button (customizable, default: ')
- Instantly closes all windows when panic key is pressed
- System tray icon for quick access and control
- Warning dialog on startup
- Private viewing mode (no taskbar entries)

### Modern User Interface
- Sleek, dark-themed interface
- Intuitive control panel with real-time feedback
- Easy-to-use model selection and management
- Drag-and-drop model file management
- Always-on-top window option

## 🚀 Getting Started

1. Run `start.bat` to initialize the application
2. If needed re-run `start.bat` till the Config UI pops up
3. Add model ZIP files to the `models` folder
4. Select desired models in the control panel
5. Choose which monitors to use for display
6. Adjust display settings as needed
7. Enable bounce animation if desired
8. Click "Start" to begin display

## ⚙️ Configuration

### Display Settings
- **Interval**: Time between popup displays (lower = more frequent popups)
- **Max Popups**: Maximum number of simultaneous windows
- **Probability**: Chance of showing a popup each interval
- **Panic Key**: Customize your emergency stop key
- **Bounce**: Enable/disable popup bounce animation
- **Monitors**: Select which monitors to use for display

### Media Types
The application supports:
- **Images**: JPG, PNG, BMP (prioritized for display)
- **GIFs**: Animated GIFs with proper frame timing
- **Videos**: MP4, AVI, MOV, WMV, FLV (with audio)

All media files must be contained within ZIP archives in the models folder.

## 📁 File Management
### Find Some online
1. This application is compatible with all [Edgeware](https://github.com/PetitTournesol/Edgeware) and [Edgeware++](https://github.com/araten10/EdgewarePlusPlus) packs

### Adding Content
1. Create a ZIP file containing your media
2. Organize content in folders (optional but recommended):
   - `img/` for images
   - `vid/` for videos
3. Place the ZIP file in the `models` folder
4. Select it in the application

### Recommended ZIP Structure
```
your-model-pack.zip
├── img/
│   ├── image1.jpg
│   ├── image2.png
│   └── animation.gif
└── vid/
    ├── video1.mp4
    └── video2.mp4
```

## ⌨️ Keyboard Shortcuts

- **Panic Key** (default: '): Emergency stop all displays and shows/hides the config
- **ESC**: Hide control panel
- **System Tray**: Click to toggle UI visibility

## 🛠️ Technical Requirements

- Windows 10/11
- Python 3.8+ (installed automatically)
- 4GB RAM recommended
- Graphics card with basic video acceleration
- Multiple monitors for full experience (optional)

## 🔒 Privacy & Security

- No data collection or transmission
- All content stays local on your computer
- No network access required
- Private window mode
- Secure cleanup on exit

## 🚫 Troubleshooting

### Application Won't Start
1. Re-run start.bat
2. Run start.bat as administrator
3. Check logs in the assets/logs folder
4. Ensure Python is installed correctly

### Display Issues
1. Reduce maximum popup count
2. Increase display interval
3. Disable bounce animation
4. Check if your ZIP files contain valid media
5. Verify monitor configuration

### Media Not Showing
1. Verify ZIP file format is correct
2. Check that media files are in supported formats
3. Try extracting and re-zipping your content
4. Look for errors in the application logs

## 📝 Tips for Best Experience

- Keep model ZIP files under 500MB for better performance
- Use MP4 format for videos (most compatible)
- Resize large images before adding to ZIP files
- Close other resource-intensive applications
- Use the panic key if you need to quickly hide content
- For multi-monitor setups, ensure all monitors are detected in Windows display settings
