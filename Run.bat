::[Bat To Exe Converter]
::
::fBE1pAF6MU+EWHreyHcjLQlHcAqNOWiyOpET6/326uSTsXEQXew2NYPaz7qNKOUBp0jte5MuxHtcjPchBRVRMz6qewE3oWtQ+0mMOcKfoQ7nXnSE70U5JGl1km3ThC4pX95r1NMasw==
::YAwzoRdxOk+EWAnk
::fBw5plQjdG8=
::YAwzuBVtJxjWCl3EqQJgSA==
::ZR4luwNxJguZRRnk
::Yhs/ulQjdF25
::cxAkpRVqdFKZSTk=
::cBs/ulQjdF+5
::ZR41oxFsdFKZSDk=
::eBoioBt6dFKZSDk=
::cRo6pxp7LAbNWATEpSI=
::egkzugNsPRvcWATEpCI=
::dAsiuh18IRvcCxnZtBJQ
::cRYluBh/LU+EWAnk
::YxY4rhs+aU+IeA==
::cxY6rQJ7JhzQF1fEqQJQ
::ZQ05rAF9IBncCkqN+0xwdVtCHErTcju4Zg==
::ZQ05rAF9IAHYFVzEqQIdIRVdDCiDKWW5DrAOqMXy4e+EsEwbQII=
::eg0/rx1wNQPfEVWB+kM9LVsJDGQ=
::fBEirQZwNQPfEVWB+kM9LVsJDAmLMmKFCrQJ5uvz6vi4r059
::cRolqwZ3JBvQF1fEqQIcKQ5aTwyHLiu5FLQf46jr/eORAYQYNA==
::dhA7uBVwLU+EWG6N+kY/Pwh3XgWEKDzsZg==
::YQ03rBFzNR3SWATElA==
::dhAmsQZ3MwfNWATElA==
::ZQ0/vhVqMQ3MEVWAtB9wSA==
::Zg8zqx1/OA3MEVWAtB9wSA==
::dhA7pRFwIByZRRnk
::Zh4grVQjdCyDJGyX8VAjFBVbSQeKAE+1BaAR7ebv/NaKq0MUGe4+bYHY0rGcbe0a5EDnZ5crwkZ2md4CDxNdbC29ax0noGFMikmMOc7Rnw70REuB41l9Nmx6gmDCjS0vLcU41JJNgyLw+VX6/w==
::YB416Ek+ZG8=
::
::
::978f952a14a936cc963da21a135fa983
@echo off
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Python n'est pas installe. Veuillez l'installer.
    echo --^> https://www.python.org/downloads/
    pause
) ELSE (
    echo Lancement du launcher...
    python mini_launcher_mc.py
    echo Launcher fermer
)
