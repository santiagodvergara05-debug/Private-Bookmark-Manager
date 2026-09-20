@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0"

:: ===================================================================
:: PARÁMETROS DEL SERVICIO (Configurar por proyecto)
:: ===================================================================
set "APP_NAME=Private Bookmark Manager"
set "APP_VER=v2.7.0"
set "APP_PORT=5050"
set "APP_FILE=app.py"
set "AUTO_OPEN=0"

:: 1. Activar renderizado ANSI en Windows 10/11
reg add HKCU\Console /v VirtualTerminalLevel /t REG_DWORD /d 1 /f >nul 2>&1

:: 2. Capturar código ESC
for /f %%a in ('powershell -NoProfile -Command "[char]27"') do set "ESC=%%a"

:: 3. Definición de estilos ANSI coherentes con el Bootloader
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
:: PASO 1: Validación del entorno Python
:: ===================================================================
python --version >nul 2>&1
if errorlevel 1 (
    echo %TAG_FAIL% Python no está instalado o no se encuentra en el PATH.
    pause
    exit /b 1
)

:: ===================================================================
:: PASO 2: Gestión del Entorno Virtual (.venv)
:: ===================================================================
set "FIRST_RUN=0"
if not exist ".venv\Scripts\activate.bat" (
    echo %TAG_INIT% Entorno virtual ausente. Creando estructura .venv...
    if exist ".venv" rd /s /q ".venv" >nul 2>&1
    python -m venv .venv
    if errorlevel 1 (
        echo %TAG_FAIL% Error crítico al generar el entorno virtual.
        pause
        exit /b 1
    )
    echo %TAG_OK% Entorno virtual .venv generado con éxito.
    set "FIRST_RUN=1"
) else (
    echo %TAG_OK% Entorno virtual detectado e indexado.
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo %TAG_FAIL% Falló al inicializar el contexto del entorno virtual.
    pause
    exit /b 1
)

:: ===================================================================
:: PASO 3: Sincronización Git modular
:: ===================================================================
call :sincronizar_git

:: ===================================================================
:: PASO 4: Comprobación de Hash MD5 de dependencias
:: ===================================================================
call :gestionar_dependencias

:: ===================================================================
:: PASO 5: Despliegue de la aplicación Flask
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

python "%APP_FILE%"
if errorlevel 1 (
    echo.
    echo %TAG_FAIL% La aplicación se cerró de forma inesperada.
)

pause
exit /b 0

:: ===================================================================
:: SUBRUTINAS AISLADAS (Sin colisiones de sintaxis en CMD)
:: ===================================================================

:sincronizar_git
if not exist ".git" goto :eof
where git >nul 2>&1
if errorlevel 1 goto :eof

git fetch --quiet >nul 2>&1
set "LOCAL_REV="
set "REMOTE_REV="
for /f "delims=" %%i in ('git rev-parse HEAD 2^>nul') do set "LOCAL_REV=%%i"
for /f "delims=" %%i in ('git rev-parse @{u} 2^>nul') do set "REMOTE_REV=%%i"

if not defined REMOTE_REV (
    echo %TAG_OK% Repositorio local activo (sin rama remota vinculada).
    goto :eof
)

if "!LOCAL_REV!"=="!REMOTE_REV!" (
    echo %TAG_OK% Repositorio local sincronizado con GitHub.
) else (
    echo %TAG_INFO% Actualizaciones remotas detectadas. Descargando cambios...
    git pull --ff-only --quiet >nul 2>&1
    if !errorlevel! equ 0 (
        echo %TAG_OK% Código actualizado al último commit.
    ) else (
        echo %TAG_WARN% Conflicto en git pull. Se conserva versión local.
    )
)
goto :eof

:gestionar_dependencias
if not exist "requirements.txt" goto :eof

set "DO_INSTALL=0"
if "%FIRST_RUN%"=="1" (
    set "DO_INSTALL=1"
) else (
    if not exist ".venv\.req_hash" (
        set "DO_INSTALL=1"
    ) else (
        call :calcular_md5_requirements CUR_HASH
        set /p OLD_HASH=<".venv\.req_hash"
        if not "!CUR_HASH!"=="!OLD_HASH!" set "DO_INSTALL=1"
    )
)

if "%DO_INSTALL%"=="1" (
    echo %TAG_INIT% Novedades en requirements.txt. Actualizando librerías...
    python -m pip install -r requirements.txt --quiet >nul 2>&1
    if !errorlevel! equ 0 (
        call :calcular_md5_requirements HASH_A_GUARDAR
        echo !HASH_A_GUARDAR!>".venv\.req_hash"
        echo %TAG_OK% Dependencias verificadas y listas para producción.
    ) else (
        echo %TAG_WARN% Fallo parcial en pip. Verifique dependencias manuales.
    )
) else (
    echo %TAG_OK% Dependencias verificadas (sin cambios en requirements.txt).
)
goto :eof

:calcular_md5_requirements
set "%~1="
for /f "skip=1 delims=" %%h in ('certutil -hashfile requirements.txt MD5 2^>nul') do (
    set "%~1=%%h"
    goto :eof
)
goto :eof