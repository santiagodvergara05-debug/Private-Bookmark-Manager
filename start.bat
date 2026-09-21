@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

:: ===================================================================
:: CONFIGURACIÓN DEL CARGADOR DE ENTORNO
:: ===================================================================
set "APP_NAME=Private Bookmark Manager"
set "APP_VER=v2.7.0"
set "APP_PORT=5050"
set "APP_FILE=app.py"

:: Rutas fijas protegidas contra espacios
set "VENV_DIR=%~dp0.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

:: 1. Activar renderizado ANSI nativo en Windows 10 / 11
reg add HKCU\Console /v VirtualTerminalLevel /t REG_DWORD /d 1 /f >nul 2>&1

:: 2. Capturar código ESC
for /f %%a in ('powershell -NoProfile -Command "[char]27"') do set "ESC=%%a"

:: 3. Definición de estilos idénticos al Bootloader de app.py
set "RESET=%ESC%[0m"
set "BOLD=%ESC%[1m"
set "TAG_OK=%ESC%[92m[  OK  ]%RESET%"
set "TAG_INIT=%ESC%[95m[ INIT ]%RESET%"
set "TAG_INFO=%ESC%[94m[ INFO ]%RESET%"
set "TAG_WARN=%ESC%[93m[ WARN ]%RESET%"
set "TAG_FAIL=%ESC%[91m[ FAIL ]%RESET%"

title %APP_NAME% %APP_VER% [Puerto %APP_PORT%]

echo ===================================================================
echo   STAGE 1 :: INICIALIZADOR DE ENTORNO Y DEPENDENCIAS
echo ===================================================================

:: ===================================================================
:: PASO 1: Validación de Python base en el sistema
:: ===================================================================
python --version >nul 2>&1
if errorlevel 1 (
    echo %TAG_FAIL% Python no esta instalado o no se encuentra en el PATH.
    pause
    exit /b 1
)

:: ===================================================================
:: PASO 2: Gestión e indexación del Entorno Virtual (.venv)
:: ===================================================================
set "FIRST_RUN=0"
if not exist "%VENV_PY%" (
    echo %TAG_INIT% Entorno virtual ausente. Creando estructura .venv...
    if exist "%VENV_DIR%" rd /s /q "%VENV_DIR%" >nul 2>&1
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo %TAG_FAIL% Error critico al generar el entorno virtual.
        pause
        exit /b 1
    )
    echo %TAG_OK% Entorno virtual .venv generado con exito.
    set "FIRST_RUN=1"
) else (
    echo %TAG_OK% Entorno virtual detectado e indexado.
)

:: ===================================================================
:: PASO 3: Sincronización Git automática
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
            echo %TAG_OK% Repositorio local activo - sin seguimiento remoto configurado
        ) else if "!LOCAL_REV!"=="!REMOTE_REV!" (
            echo %TAG_OK% Repositorio local sincronizado con GitHub.
        ) else (
            echo %TAG_INFO% Actualizaciones remotas detectadas. Descargando cambios...
            git pull --ff-only --quiet >nul 2>&1
            if !errorlevel! equ 0 (
                echo %TAG_OK% Codigo actualizado al ultimo commit.
            ) else (
                echo %TAG_WARN% Conflicto en git pull. Se conserva version local.
            )
        )
    )
)

:: ===================================================================
:: PASO 4: Comprobacion e Instalacion Detallada de Dependencias
:: ===================================================================
if exist "requirements.txt" (
    set "DO_INSTALL=0"
    if "!FIRST_RUN!"=="1" set "DO_INSTALL=1"

    if "!DO_INSTALL!"=="0" (
        "%VENV_PY%" -c "import hashlib, pathlib, sys; f=pathlib.Path(r'%VENV_DIR%\.req_hash'); sys.exit(0 if f.exists() and f.read_text().strip()==hashlib.md5(open('requirements.txt','rb').read()).hexdigest() else 1)" >nul 2>&1
        if errorlevel 1 set "DO_INSTALL=1"
    )

    :: Comprobacion preventiva: si falta Flask fisicamente, forzar instalacion
    "%VENV_PY%" -c "import flask" >nul 2>&1
    if errorlevel 1 set "DO_INSTALL=1"

    if "!DO_INSTALL!"=="1" (
        echo %TAG_INFO% Sincronizando librerias de requirements.txt...
        
        :: 1. Normalizar requirements.txt con soporte automatico UTF-16 / UTF-8
        "%VENV_PY%" -c "b=open('requirements.txt','rb').read(); t=b.decode('utf-16' if b[:2] in (b'\xff\xfe',b'\xfe\xff') or b'\x00' in b[:50] else 'utf-8-sig', errors='ignore'); lines=[l.strip() for l in t.splitlines() if l.strip() and not l.strip().startswith('#')]; open('requirements.txt','w',encoding='utf-8',newline='\n').write('\n'.join(lines)+'\n')" >nul 2>&1

        set "INSTALL_OK=1"
        set "COUNT=0"

        :: 2. Bucle con seguimiento detallado por dependencia
        for /f "usebackq eol=# tokens=1 delims= " %%L in ("requirements.txt") do (
            set /a COUNT+=1
            set "PAQUETE=%%L"
            echo %TAG_INIT% Instalando: !BOLD!!PAQUETE!!RESET!...
            
            "%VENV_PY%" -m pip install "!PAQUETE!" --quiet >nul 2>&1
            if !errorlevel! equ 0 (
                echo %TAG_OK% Instalado: !BOLD!!PAQUETE!!RESET!
            ) else (
                echo %TAG_FAIL% Error al instalar: !BOLD!!PAQUETE!!RESET!
                set "INSTALL_OK=0"
            )
        )

        :: Validacion de proteccion: Si no proceso ningun paquete, abortar exito
        if !COUNT! equ 0 (
            echo %TAG_FAIL% No se detectaron dependencias validas en requirements.txt.
            set "INSTALL_OK=0"
        )

        :: 3. Guardar huella solo si todos los paquetes finalizaron con exito
        if "!INSTALL_OK!"=="1" (
            "%VENV_PY%" -c "import hashlib, pathlib; pathlib.Path(r'%VENV_DIR%\.req_hash').write_text(hashlib.md5(open('requirements.txt','rb').read()).hexdigest())" >nul 2>&1
            echo %TAG_OK% Todas las dependencias quedaron preparadas.
        ) else (
            echo %TAG_WARN% Uno o mas paquetes fallaron. Se reintentara en el proximo inicio.
        )
    ) else (
        echo %TAG_OK% Dependencias verificadas - sin cambios en requirements.txt
    )
)

:: ===================================================================
:: PASO 5: Transferencia de Control al Bootloader de la Aplicacion
:: ===================================================================
echo -------------------------------------------------------------------
echo %TAG_OK% Entorno validado. Lanzando nucleo del servidor...
echo -------------------------------------------------------------------

"%VENV_PY%" "%APP_FILE%"
if errorlevel 1 (
    echo.
    echo %TAG_FAIL% La aplicacion finalizo con un codigo de error.
)

pause