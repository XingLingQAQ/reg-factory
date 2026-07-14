@echo off
cd /d "%~dp0"
if not exist node_modules call npm install
if errorlevel 1 exit /b 1
call npm run build
if errorlevel 1 exit /b 1
call npm start
