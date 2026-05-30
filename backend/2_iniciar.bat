@echo off
chcp 65001 >nul
title Bingo Imperial - Servidor
echo ================================
echo  Iniciando Bingo Imperial
echo ================================
echo.

if not exist venv (
    echo [ERROR] No se encontro el entorno virtual.
    echo Ejecuta primero 1_instalar.bat
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
echo Servidor corriendo en http://localhost:5000
echo Abre esa direccion en tu navegador.
echo.
echo Para detener: presiona Ctrl+C en esta ventana.
echo.

REM Abrir el navegador automaticamente
start "" http://localhost:5000

python run.py
pause
