#!/usr/bin/env bash

# Posicionarse de forma segura en el directorio del script
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1

# ===================================================================
# CONFIGURACION DEL CARGADOR DE ENTORNO
# ===================================================================
APP_NAME="Private Bookmark Manager"
APP_VER="v2.7.0"
APP_PORT="5050"
APP_FILE="app.py"

# Rutas internas del entorno virtual
VENV_DIR="$(pwd)/.venv"
VENV_PY="${VENV_DIR}/bin/python"

# Definicion de estilos ANSI identicos al bootloader de app.py
RESET="\033[0m"
BOLD="\033[1m"
TAG_OK="\033[92m[  OK  ]\033[0m"
TAG_INIT="\033[95m[ INIT ]\033[0m"
TAG_INFO="\033[94m[ INFO ]\033[0m"
TAG_WARN="\033[93m[ WARN ]\033[0m"
TAG_FAIL="\033[91m[ FAIL ]\033[0m"

echo "==================================================================="
echo "  STAGE 1 :: INICIALIZADOR DE ENTORNO Y DEPENDENCIAS"
echo "==================================================================="

# ===================================================================
# PASO 1: Validacion de Python base en el sistema
# ===================================================================
if command -v python3 >/dev/null 2>&1; then
    BASE_PY="python3"
elif command -v python >/dev/null 2>&1; then
    BASE_PY="python"
else
    echo -e "${TAG_FAIL} Python 3 no esta instalado en el sistema o no esta en el PATH."
    exit 1
fi

# ===================================================================
# PASO 2: Gestion e indexacion del Entorno Virtual (.venv)
# ===================================================================
FIRST_RUN=0
if [ ! -f "${VENV_PY}" ]; then
    echo -e "${TAG_INIT} Entorno virtual ausente. Creando estructura .venv..."
    rm -rf "${VENV_DIR}" >/dev/null 2>&1
    "${BASE_PY}" -m venv "${VENV_DIR}"
    if [ $? -ne 0 ]; then
        echo -e "${TAG_FAIL} Error critico al generar el entorno virtual."
        exit 1
    fi
    echo -e "${TAG_OK} Entorno virtual .venv generado con exito."
    FIRST_RUN=1
else
    echo -e "${TAG_OK} Entorno virtual detectado e indexado."
fi

# ===================================================================
# PASO 3: Sincronizacion Git automatica
# ===================================================================
if [ -d ".git" ] && command -v git >/dev/null 2>&1; then
    git fetch --quiet >/dev/null 2>&1
    LOCAL_REV=$(git rev-parse HEAD 2>/dev/null)
    REMOTE_REV=$(git rev-parse @{u} 2>/dev/null)

    if [ -z "$REMOTE_REV" ]; then
        echo -e "${TAG_OK} Rama local activa - sin seguimiento remoto configurado"
    elif [ "$LOCAL_REV" = "$REMOTE_REV" ]; then
        echo -e "${TAG_OK} Repositorio local sincronizado con GitHub."
    else
        echo -e "${TAG_INFO} Actualizaciones remotas detectadas. Descargando cambios..."
        if git pull --ff-only --quiet >/dev/null 2>&1; then
            echo -e "${TAG_OK} Codigo actualizado al ultimo commit."
        else
            echo -e "${TAG_WARN} Conflicto en git pull. Se conserva version local."
        fi
    fi
fi

# ===================================================================
# PASO 4: Comprobacion e Instalacion Detallada de Dependencias
# ===================================================================
if [ -f "requirements.txt" ]; then
    DO_INSTALL=0
    if [ "$FIRST_RUN" -eq 1 ]; then
        DO_INSTALL=1
    fi

    # Comprobacion por hash MD5 nativo con Python
    if [ "$DO_INSTALL" -eq 0 ]; then
        "${VENV_PY}" -c "import hashlib, pathlib, sys; f=pathlib.Path(r'${VENV_DIR}/.req_hash'); sys.exit(0 if f.exists() and f.read_text().strip()==hashlib.md5(open('requirements.txt','rb').read()).hexdigest() else 1)" >/dev/null 2>&1
        if [ $? -ne 0 ]; then
            DO_INSTALL=1
        fi
    fi

    # Comprobacion preventiva: si falta Flask fisicamente, forzar instalacion
    "${VENV_PY}" -c "import flask" >/dev/null 2>&1
    if [ $? -ne 0 ]; then
        DO_INSTALL=1
    fi

    if [ "$DO_INSTALL" -eq 1 ]; then
        echo -e "${TAG_INFO} Sincronizando librerias de requirements.txt..."

        # Normalizar requirements.txt eliminando retornos de carro (\r) y comentarios
        "${VENV_PY}" -c "import pathlib; p=pathlib.Path('requirements.txt'); lines=[l.strip() for l in p.read_text(encoding='utf-8', errors='ignore').splitlines() if l.strip() and not l.startswith('#')]; p.write_text('\n'.join(lines) + '\n', encoding='utf-8')" >/dev/null 2>&1

        INSTALL_OK=1

        # Bucle con seguimiento individual
        while IFS= read -r PAQUETE || [ -n "$PAQUETE" ]; do
            [ -z "$PAQUETE" ] && continue
            echo -e "${TAG_INIT} Instalando: ${BOLD}${PAQUETE}${RESET}..."

            "${VENV_PY}" -m pip install "${PAQUETE}" --quiet >/dev/null 2>&1
            if [ $? -eq 0 ]; then
                echo -e "${TAG_OK} Instalado: ${BOLD}${PAQUETE}${RESET}"
            else
                echo -e "${TAG_FAIL} Error al instalar: ${BOLD}${PAQUETE}${RESET}"
                INSTALL_OK=0
            fi
        done < "requirements.txt"

        # Guardar huella digital solo si todos los paquetes se instalaron sin fallas
        if [ "$INSTALL_OK" -eq 1 ]; then
            "${VENV_PY}" -c "import hashlib, pathlib; pathlib.Path(r'${VENV_DIR}/.req_hash').write_text(hashlib.md5(open('requirements.txt','rb').read()).hexdigest())" >/dev/null 2>&1
            echo -e "${TAG_OK} Todas las dependencias quedaron preparadas."
        else
            echo -e "${TAG_WARN} Uno o mas paquetes fallaron. Se reintentara en el proximo inicio."
        fi
    else
        echo -e "${TAG_OK} Dependencias verificadas - sin cambios en requirements.txt"
    fi
fi

# ===================================================================
# PASO 5: Transferencia de Control al Bootloader de la Aplicacion
# ===================================================================
echo "-------------------------------------------------------------------"
echo -e "${TAG_OK} Entorno validado. Lanzando nucleo del servidor..."
echo "-------------------------------------------------------------------"

"${VENV_PY}" "${APP_FILE}"
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo -e "${TAG_FAIL} La aplicacion finalizo con un codigo de error (Codigo: ${EXIT_CODE})."
    exit $EXIT_CODE
fi