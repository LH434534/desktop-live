@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo  Qwen 2.5 7B Instruct - controle do Windows
echo  100%% local / sem nuvem / sem chave de API
echo ============================================
echo.
python agente.py %*
if errorlevel 1 (
  echo.
  echo Se deu erro de conexao, rode primeiro: instalar.bat
)
echo.
pause
