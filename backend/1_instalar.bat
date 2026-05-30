@echo off
chcp 65001 >nul
title Bingo Imperial - Instalacion
echo ================================
echo  Instalando Bingo Imperial
echo ================================
echo.

REM Verificar Python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado o no esta en el PATH.
    echo Descargalo desde https://www.python.org/downloads/
    echo Asegurate de marcar "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

echo [OK] Python detectado:
python --version
echo.

REM Crear entorno virtual si no existe
if not exist venv (
    echo Creando entorno virtual...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)

echo Activando entorno virtual e instalando dependencias...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo ================================
echo  Instalacion completada
echo ================================
echo.
echo Ahora ejecuta:  2_iniciar.bat
echo.
pause
