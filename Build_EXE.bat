@echo off
setlocal
cd /d %~dp0
echo Installing PyInstaller...
pip install pyinstaller
echo.
echo Building SCUM Recipe Editor...
echo --------------------------------------
pyinstaller --noconsole --onefile --icon=icon.ico --name="SCUM Recipe Editor" main.py
echo.
echo --------------------------------------
echo Done! The executable is in the 'dist' folder.
echo You will need to copy UAssetGUI.exe into the output folder for conversion to work.
pause
