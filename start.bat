@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

:: ===================================================================
:: PARÁMETROS DEL SERVICIO (Configurar por proyecto)
:: ===================================================================
set "APP_NAME=Private Bookmark Manager"
set "APP_VER=v2.7.0"
set "APP_PORT=5050"
set "APP_FILE=app.py"
set "AUTO_OPEN=0"

:: 1. Habilitar colores ANSI nativos en Windows 10 / 11
reg add HKCU\Console /v VirtualTerminalLevel /t REG_DWORD /d 1 /f >nul 2>&1

:: 2. Capturar carácter ESC de forma segura
for /f %%a in ('powershell -NoProfile -Command "[char]27"') do set "ESC=%%a"

:: 3. Definición de estilos idénticos al Bootloader
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
    echo %TAG_FAIL% Python no está instalado o no se encuentra en el PATH.
    pause
    exit /b 1
)

:: ===================================================================
:: PASO 2: Gestión e indexación del Entorno Virtual (.venv)
:: ===================================================================
set "FIRST_RUN=0"
if not exist ".venv\Scripts\python.exe" (
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

:: Aislar el entorno añadiendo su carpeta Scripts al PATH sin usar activate.bat
set "PATH=%~dp0.venv\Scripts;%PATH%"
set "VIRTUAL_ENV=%~dp0.venv"

:: ===================================================================
:: PASO 3: Sincronización automática de Git
:: ===================================================================
if exist ".git" (
    where git >nul 2>&1
    if not errorlevel 1 (
        git fetch --quiet >nul 2>&1
        set "LOCAL_REV="
        set "REMOTE_REV="
        for /f %%i in ('git rev-parse HEAD 2^>nul') do set "LOCAL_REV=%%i"
        for /f %%i in ('git rev-parse @{u} 2^>nul') do set "REMOTE_REV=%%i"

        if not defined REMOTE_REV (
            echo %TAG_OK% Rama local activa (sin seguimiento remoto configurado).
        ) else if "!LOCAL_REV!"=="!REMOTE_REV!" (
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
    )
)

:: ===================================================================
:: PASO 4: Comprobación por Hash MD5 de dependencias (Fast-Boot)
:: ===================================================================
if exist "requirements.txt" (
    set "DO_INSTALL=0"
    if "!FIRST_RUN!"=="1" (
        set "DO_INSTALL=1"
    ) else (
        python -c "import hashlib, pathlib, sys; f=pathlib.Path(r'.venv\.req_hash'); sys.exit(0 if f.exists() and f.read_text().strip()==hashlib.md5(open('requirements.txt','rb').read()).hexdigest() else 1)" >nul 2>&1
        if errorlevel 1 set "DO_INSTALL=1"
    )

    if "!DO_INSTALL!"=="1" (
        echo %TAG_INIT% Novedades en requirements.txt. Actualizando librerías...
        python -m pip install -r requirements.txt --quiet >nul 2>&1
        if !errorlevel! equ 0 (
            python -c "import hashlib, pathlib; pathlib.Path(r'.venv\.req_hash').write_text(hashlib.md5(open('requirements.txt','rb').read()).hexdigest())" >nul 2>&1
            echo %TAG_OK% Dependencias verificadas y listas para producción.
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

python "%APP_FILE%"
if errorlevel 1 (
    echo.
    echo %TAG_FAIL% La aplicación se cerró de forma inesperada.
)

pause