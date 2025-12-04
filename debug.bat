@echo off
python --version >nul 2>&1

IF %ERRORLEVEL% NEQ 0 (
    powershell -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Python n''est pas installe. Veuillez l''installer: https://www.python.org/downloads/','Erreur Python',[System.Windows.MessageBoxButton]::OK,[System.Windows.MessageBoxImage]::Error)"
) ELSE (
    python mini_launcher_mc.py
)
pause