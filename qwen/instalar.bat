@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Instalando Ollama + Qwen 2.5 7B Instruct (4.7 GB)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1"
echo.
pause
