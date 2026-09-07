@echo off
setlocal

:: Cambiar al directorio del script
cd /d "%~dp0"

:: 1. Crear entorno virtual si no existe
if not exist ".venv" (
    echo [*] Creando entorno virtual .venv...
    python -m venv .venv
)

:: 2. Activar entorno virtual
call .venv\Scripts\activate.bat

:: 3. Instalar dependencias si existe requirements.txt
if exist "requirements.txt" (
    echo [*] Comprobando dependencias...
    pip install -q -r requirements.txt
)

:: 4. Iniciar la aplicacion
echo [+] Iniciando servidor...
python app.py

pause
