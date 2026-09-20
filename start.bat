@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0"

:: ===================================================================
:: PARÁMETROS DEL SERVICIO (Personalizable por repositorio)
:: ===================================================================
set "APP_NAME=Private Bookmark Manager"
set "APP_VER=v2.7.0"
set "APP_PORT=5050"
set "APP_FILE=app.py"
set "AUTO_OPEN=0"

:: 1. Activar renderizado ANSI en Windows 10 nativo
reg add HKCU\Console /v VirtualTerminalLevel /t REG_DWORD /d 1 /f >nul 2>&1

:: 2. Capturar código ESC mediante PowerShell
for /f %%a in ('powershell -NoProfile -Command "[char]27"') do set "ESC=%%a"

:: 3. Definición de estilos y etiquetas idénticas a tu Bootloader
set "RESET=%ESC%[0m"
set "BOLD=%ESC%[1m"
set "TAG_OK=%ESC%[92m[  OK  ]%RESET%"
set "TAG_INIT=%ESC%[95m[ INIT ]%RESET%"
set "TAG_INFO=%ESC%[94m[ INFO ]%RESET%"
set "TAG_WARN=%ESC%[93m[ WARN ]%RESET%"
set "TAG_FAIL=%ESC%[91m[ FAIL ]%RESET%"

title %APP_NAME% %APP_VER% [Puerto %APP_PORT%]

echo ===================================================================
echo   BOOTLOADER :: %APP_NAME% %APP_VER% (OFFLINE ^& SECURE)
echo ===================================================================

:: ===================================================================
:: PASO 1: Comprobar entorno Python en el sistema
:: ===================================================================
python --version >nul 2>&1
if errorlevel 1 (
    echo %TAG_FAIL% Python no esta instalado o no se encuentra en el PATH.
    pause
    exit /b 1
)

:: ===================================================================
:: PASO 2: Gestión inteligente de Entorno Virtual (.venv)
:: ===================================================================
if not exist ".venv\Scripts\activate.bat" (
    echo %TAG_INIT% Entorno virtual ausente. Creando estructura .venv...
    if exist ".venv" rd /s /q ".venv" >nul 2>&1
    python -m venv .venv
    if errorlevel 1 (
        echo %TAG_FAIL% Error critico al generar el entorno virtual.
        pause
        exit /b 1
    )
    echo %TAG_OK% Entorno virtual .venv generado con exito.
    set "FIRST_RUN=1"
) else (
    echo %TAG_OK% Entorno virtual detectado e indexado.
    set "FIRST_RUN=0"
)

call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo %TAG_FAIL% Fallo al inicializar el contexto del entorno virtual.
    pause
    exit /b 1
)

:: ===================================================================
:: PASO 3: Sincronización automática de Git (si existe repositorio)
:: ===================================================================
if exist ".git" (
    git --version >nul 2>&1
    if not errorlevel 1 (
        git fetch >nul 2>&1
        for /f %%i in ('git rev-parse HEAD 2^>nul') do set "LOCAL_REV=%%i"
        for /f %%i in ('git rev-parse @{u} 2^>nul') do set "REMOTE_REV=%%i"
        if not "!LOCAL_REV!"=="!REMOTE_REV!" (
            if not "!REMOTE_REV!"=="" (
                echo %TAG_INFO% Actualizaciones remotas detectadas. Descargando cambios...
                git pull --ff-only --quiet >nul 2>&1
                if !errorlevel! equ 0 (
                    echo %TAG_OK% Codigo actualizado al ultimo commit.
                ) else (
                    echo %TAG_WARN% Conflicto en git pull. Se conserva version local.
                )
            )
        ) else (
            echo %TAG_OK% Repositorio local sincronizado con GitHub.
        )
    )
)

:: ===================================================================
:: PASO 4: Comprobación por Hash MD5 de dependencias (Fast-Boot)
:: ===================================================================
if exist "requirements.txt" (
    set "DO_INSTALL=0"
    if !FIRST_RUN!==1 (
        set "DO_INSTALL=1"
    ) else (
        if exist ".venv\.req_hash" (
            for /f "delims=" %%h in ('certutil -hashfile requirements.txt MD5 2^>nul ^| find /v "hash"') do set "CUR_HASH=%%h"
            set /p "OLD_HASH="<".venv\.req_hash"
            if not "!CUR_HASH!"=="!OLD_HASH!" set "DO_INSTALL=1"
        ) else (
            set "DO_INSTALL=1"
        )
    )

    if "!DO_INSTALL!"=="1" (
        echo %TAG_INIT% Novedades en requirements.txt. Actualizando librerias...
        python -m pip install -r requirements.txt --quiet >nul 2>&1
        if !errorlevel! equ 0 (
            for /f "delims=" %%h in ('certutil -hashfile requirements.txt MD5 2^>nul ^| find /v "hash"') do echo %%h>".venv\.req_hash"
            echo %TAG_OK% Dependencias verificadas y listas para produccion.
        ) else (
            echo %TAG_WARN% Fallo parcial en pip. Verifique dependencias manuales.
        )
    ) else (
        echo %TAG_OK% Dependencias verificadas (sin cambios en requirements.txt).
    )
)

:: ===================================================================
:: PASO 5: Apertura automática y Despliegue de Flask
:: ===================================================================
if "%AUTO_OPEN%"=="1" (
    start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:%APP_PORT%"
)

echo -------------------------------------------------------------------
echo %TAG_INFO% Servidor Local enrutado en http://127.0.0.1:%APP_PORT%
echo %TAG_INFO% Acceso LAN Red: Desactivado (modo exclusivo PC local)
echo %BOLD%>>> %APP_NAME% OPERATIVO Y LISTO <<<%RESET%
echo -------------------------------------------------------------------
echo.

python %APP_FILE%
if errorlevel 1 (
    echo.
    echo %TAG_FAIL% La aplicacion se cerro de forma inesperada.
)

pause