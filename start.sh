#!/usr/bin/env bash

# Posicionarse en el directorio del script
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1

# ===================================================================
# PARÁMETROS DEL SERVICIO (Personalizable por repositorio)
# ===================================================================
APP_NAME="PBMrivateBookmarkManager"
APP_VER="v2.7.0"
APP_PORT="5050"
APP_FILE="app.py"
AUTO_OPEN=1

# Definición de estilos y colores ANSI
RESET="\033[0m"
BOLD="\033[1m"
TAG_OK="\033[92m[  OK  ]\033[0m"
TAG_INIT="\033[95m[ INIT ]\033[0m"
TAG_INFO="\033[94m[ INFO ]\033[0m"
TAG_WARN="\033[93m[ WARN ]\033[0m"
TAG_FAIL="\033[91m[ FAIL ]\033[0m"

echo "==================================================================="
echo "  BOOTLOADER :: ${APP_NAME} ${APP_VER} (OFFLINE & SECURE)"
echo "==================================================================="

# ===================================================================
# PASO 1: Comprobar entorno Python en el sistema
# ===================================================================
if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${TAG_FAIL} Python 3 no está instalado en el sistema."
    exit 1
fi

# ===================================================================
# PASO 2: Gestión inteligente de Entorno Virtual (.venv)
# ===================================================================
FIRST_RUN=0
if [ ! -f ".venv/bin/activate" ]; then
    echo -e "${TAG_INIT} Entorno virtual ausente. Creando estructura .venv..."
    rm -rf .venv >/dev/null 2>&1
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo -e "${TAG_FAIL} Error crítico al generar el entorno virtual."
        exit 1
    fi
    echo -e "${TAG_OK} Entorno virtual .venv generado con éxito."
    FIRST_RUN=1
else
    echo -e "${TAG_OK} Entorno virtual detectado e indexado."
fi

# shellcheck disable=SC1091
source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo -e "${TAG_FAIL} Falló al inicializar el contexto del entorno virtual."
    exit 1
fi

# ===================================================================
# PASO 3: Sincronización automática de Git (si existe repositorio)
# ===================================================================
if [ -d ".git" ] && command -v git >/dev/null 2>&1; then
    git fetch --quiet >/dev/null 2>&1
    LOCAL_REV=$(git rev-parse HEAD 2>/dev/null)
    REMOTE_REV=$(git rev-parse @{u} 2>/dev/null)

    if [ -n "$REMOTE_REV" ] && [ "$LOCAL_REV" != "$REMOTE_REV" ]; then
        echo -e "${TAG_INFO} Actualizaciones remotas detectadas. Descargando cambios..."
        if git pull --ff-only --quiet >/dev/null 2>&1; then
            echo -e "${TAG_OK} Código actualizado al último commit."
        else
            echo -e "${TAG_WARN} Conflicto en git pull. Se conserva versión local."
        fi
    else
        echo -e "${TAG_OK} Repositorio local sincronizado con GitHub."
    fi
fi

# ===================================================================
# PASO 4: Comprobación por Hash MD5 de dependencias (Fast-Boot)
# ===================================================================
if [ -f "requirements.txt" ]; then
    DO_INSTALL=0
    if [ "$FIRST_RUN" -eq 1 ]; then
        DO_INSTALL=1
    else
        if [ -f ".venv/.req_hash" ]; then
            CUR_HASH=$(md5sum requirements.txt 2>/dev/null | awk '{print $1}')
            OLD_HASH=$(cat .venv/.req_hash 2>/dev/null)
            if [ "$CUR_HASH" != "$OLD_HASH" ]; then
                DO_INSTALL=1
            fi
        else
            DO_INSTALL=1
        fi
    fi

    if [ "$DO_INSTALL" -eq 1 ]; then
        echo -e "${TAG_INIT} Novedades en requirements.txt. Actualizando librerías..."
        if python -m pip install -r requirements.txt --quiet >/dev/null 2>&1; then
            md5sum requirements.txt 2>/dev/null | awk '{print $1}' > .venv/.req_hash
            echo -e "${TAG_OK} Dependencias verificadas y listas para producción."
        else
            echo -e "${TAG_WARN} Fallo parcial en pip. Verifique dependencias manuales."
        fi
    else
        echo -e "${TAG_OK} Dependencias verificadas (sin cambios en requirements.txt)."
    fi
fi

# ===================================================================
# PASO 5: Apertura automática y Despliegue de Flask
# ===================================================================
if [ "$AUTO_OPEN" -eq 1 ]; then
    (sleep 2 && (xdg-open "http://127.0.0.1:${APP_PORT}" 2>/dev/null || open "http://127.0.0.1:${APP_PORT}" 2>/dev/null)) &
fi

echo "-------------------------------------------------------------------"
echo -e "${TAG_INFO} Servidor Local enrutado en http://127.0.0.1:${APP_PORT}"
echo -e "${TAG_INFO} Acceso LAN Red: Desactivado (modo exclusivo PC local)"
echo -e "${BOLD}>>> ${APP_NAME} OPERATIVO Y LISTO <<<${RESET}"
echo "-------------------------------------------------------------------"
echo ""

python "${APP_FILE}"
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo -e "${TAG_FAIL} La aplicación se cerró de forma inesperada (Código: ${EXIT_CODE})."
fi