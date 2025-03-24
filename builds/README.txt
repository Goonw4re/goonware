===================================
GOONWARE INSTALLER INSTRUCTIONS
===================================

This folder contains the following files:
- goonware_installer.iss: The Inno Setup script for building the installer
- build_installer.bat: A script to automatically compile the installer
- GoonwareSetup.exe: The compiled installer (after building)

Requirements:
------------
1. Inno Setup 6 or newer (download from https://jrsoftware.org/isinfo.php)
2. Python 3.8 or newer installed on the build system

Building the Installer:
---------------------
1. Install Inno Setup on your computer
2. Run the "build_installer.bat" script
3. Wait for the compilation to complete
4. The resulting installer will be "GoonwareSetup.exe" in this folder

Using the Installer:
------------------
The installer includes the following features:
- User can select installation location
- File associations for .gmodel files
- Option to add desktop shortcuts
- Option to install GoonConverter (for converting ZIP files to GMODEL format)
- Option to launch Goonware after installation
- Option to run on Windows startup

Installation Notes:
-----------------
- The installer requires administrator privileges to set up file associations
- Python 3.8 or newer is required on the target system
- The installer will check for Python before installing
- All files are installed to the user-selected directory
- Registry entries are created only for file associations

Distribution:
-----------
You can distribute the GoonwareSetup.exe file to users. It includes everything 
needed to install Goonware on a Windows system. 