::[Bat To Exe Converter]
::
::YAwzoRdxOk+EWAnk
::fBw5plQjdG8=
::YAwzuBVtJxjWCl3EqQJgSA==
::ZR4luwNxJguZRRnk
::Yhs/ulQjdF+5
::cxAkpRVqdFKZSTk=
::cBs/ulQjdF+5
::ZR41oxFsdFKZSDk=
::eBoioBt6dFKZSDk=
::cRo6pxp7LAbNWATEpCI=
::egkzugNsPRvcWATEpCI=
::dAsiuh18IRvcCxnZtBJQ
::cRYluBh/LU+EWAnk
::YxY4rhs+aU+IeA==
::cxY6rQJ7JhzQF1fEqQJQ
::ZQ05rAF9IBncCkqN+0xwdVs0
::ZQ05rAF9IAHYFVzEqQIdIRVdDCiDKWW5DrAOqMXy4e+EsEwbQII=
::eg0/rx1wNQPfEVWB+kM9LVsJDGQ=
::fBEirQZwNQPfEVWB+kM9LVsJDGQ=
::cRolqwZ3JBvQF1fEqQIcPRpaTwyHLiu5FLQf46jr/eORAYR9
::dhA7uBVwLU+EWG6N+kY/Pwh3XgWEKDzsZg==
::YQ03rBFzNR3SWATElA==
::dhAmsQZ3MwfNWATElA==
::ZQ0/vhVqMQ3MEVWAtB9wSA==
::Zg8zqx1/OA3MEVWAtB9wSA==
::dhA7pRFwIByZRRnk
::Zh4grVQjdCyDJGyX8VAjFBVbSQeKAE+1BaAR7ebv/NaKq0MUGe4+bYHY0rGcbe0a5EDnZ5crwkZ3kcUFTDdZaxGlZgom6UNLuGGGJcaap0HkUk3p
::YB416Ek+ZG8=
::
::
::978f952a14a936cc963da21a135fa983
@echo off
python --version >nul 2>&1

IF %ERRORLEVEL% NEQ 0 (
    powershell -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Python n''est pas installe. Veuillez l''installer: https://www.python.org/downloads/','Erreur Python',[System.Windows.MessageBoxButton]::OK,[System.Windows.MessageBoxImage]::Error)"
) ELSE (
    python mini_launcher_mc.py
)

