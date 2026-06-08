@echo off
title Video Download Servisi
chcp 65001 > nul

echo Provera Python instalacije...
python --version >nul 2>&1
if %errorlevel% neq 0 goto :NO_PYTHON

if not exist ".venv" goto :CREATE_VENV

:RUN_APP
call .venv\Scripts\activate.bat
echo Pokretanje aplikacije i servera...
python run.py
if %errorlevel% neq 0 goto :RUN_ERROR
exit /b 0

:NO_PYTHON
echo.
echo ==============================================================================
echo [GRESKA] Python nije pronadjen na sistemu!
echo.
echo Molimo vas da preuzmete i instalirate Python (preporucuje se verzija 3.11 ili novija):
echo https://www.python.org/downloads/
echo.
echo VAZNO: Tokom instalacije obavezno stiklirajte opciju "Add Python to PATH".
echo ==============================================================================
echo.
pause
exit /b 1

:CREATE_VENV
echo Kreiranje virtuelnog okruzenja (.venv)...
python -m venv .venv
if %errorlevel% neq 0 goto :VENV_ERROR

echo Instalacija potrebnih Python biblioteka...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 goto :INSTALL_ERROR

echo.
echo Virtuelno okruzenje je uspesno kreirano i zavisnosti su instalirane!
echo.
goto :RUN_APP

:VENV_ERROR
echo [GRESKA] Neuspesno kreiranje virtuelnog okruzenja.
pause
exit /b 1

:INSTALL_ERROR
echo [GRESKA] Instalacija zavisnosti nije uspela. Proverite internet vezu.
pause
exit /b 1

:RUN_ERROR
echo.
echo Aplikacija je zatvorena sa greskom.
pause
exit /b 1
