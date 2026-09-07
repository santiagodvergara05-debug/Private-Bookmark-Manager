#!/usr/bin/env bash

# Salir si ocurre algún error crítico
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# 1. Crear el entorno virtual si no existe
if [ ! -d ".venv" ]; then
    echo "[*] Creando entorno virtual (.venv)..."
    python3 -m venv .venv
fi

# 2. Activar entorno virtual
source .venv/bin/activate

# 3. Instalar o actualizar dependencias si cambió requirements.txt
if [ -f "requirements.txt" ]; then
    echo "[*] Comprobando dependencias..."
    pip install -q -r requirements.txt
fi

# 4. Iniciar la aplicación
echo "[+] Iniciando servidor..."
python app.py