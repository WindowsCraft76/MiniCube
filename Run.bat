@echo off
title Mini Minecraft Launcher
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
	echo Python n'est pas installe. Veuillez l'installer.
	echo --^> https://www.python.org/downloads/
    pause
) ELSE (
	echo Lancement du launcher...
	python mini_launcher.py
	echo Launcher fermer.
)


