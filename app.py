import os
import time
import secrets
import logging
import sys
import socket
from dotenv import load_dotenv
from flask import Flask
import database
from routes import marcadores_bp, RUTA_ULTIMO_BACKUP
from datetime import datetime

app = Flask(__name__)
app.register_blueprint(marcadores_bp)

def klog(estado, mensaje, delay=0.3):
    """Imprime mensajes formateados al estilo init/kernel de Linux."""
    prefijos = {
        "ok":   "  [\033[92m  OK  \033[0m] ",
        "info": "  [\033[94m INFO \033[0m] ",
        "warn": "  [\033[93m WARN \033[0m] ",
        "fail": "  [\033[91m FAIL \033[0m] ",
        "init": "  [\033[95m INIT \033[0m] "
    }
    prefijo = prefijos.get(estado.lower(), "  [ .... ] ")
    if not sys.stdout.isatty():
        prefijo = f"  [{estado.upper():^6}] "
    print(f"{prefijo}{mensaje}")
    if delay > 0:
        time.sleep(delay)

if __name__ == "__main__":
    # Evita duplicar el banner detallado cuando Werkzeug recarga el proceso
    es_reloader = os.environ.get("WERKZEUG_RUN_MAIN") == "true"

    if not es_reloader:
        print("\n" + "=" * 65)
        print("         BOOTLOADER :: SISTEMA DE MARCADORES PRIVADOS         ")
        print("=" * 65)
        time.sleep(0.3)

        # 1. Comprobación y creación de carpetas del sistema
        klog("init", "Verificando directorios de infraestructura...")
        for directorio in ["templates", "static"]:
            if not os.path.exists(directorio):
                os.makedirs(directorio, exist_ok=True)
                klog("ok", f"Directorio creado: /{directorio}")
            else:
                klog("ok", f"Directorio presente: /{directorio}")

        # 2. Base de datos SQLite
        DB_PATH = "marcadores.db"
        if not os.path.exists(DB_PATH):
            klog("info", "Almacenamiento persistente marcadores.db ausente.")
            klog("init", "Creando esquema SQLite (tablas: carpetas, marcadores)...")
            database.inicializar_db()
            klog("ok", "Base de datos creada e inicializada correctamente.")
        else:
            klog("ok", "Revisando consistencia de esquema SQLite en marcadores.db...")
            database.inicializar_db()

        # 3. Archivo de configuración (.env)
        ENV_PATH = ".env"
        if os.path.exists(ENV_PATH):
            klog("ok", "Archivo de entorno .env montado y cargado en memoria.")
        else:
            klog("warn", "Archivo de entorno .env no encontrado. Iniciando configuración cero...")
            
            with open(ENV_PATH, "w", encoding="utf-8") as f:
                klog("init", "Generando token de entropía para SECRET_KEY (256 bits)...")
                f.write(f"SECRET_KEY={secrets.token_hex(32)}\n")
                
                klog("init", "Generando token de entropía para MASTER_KEY (256 bits)...")
                f.write(f"MASTER_KEY={secrets.token_hex(32)}\n")
                
                klog("init", "Escribiendo credencial web por defecto (APP_PASSWORD)...")
                f.write("APP_PASSWORD=cambiame\n")
                
                klog("init", "Configurando parámetros de interfaz (favicons, tabs)...")
                f.write("MOSTRAR_FAVICONS=false\n")
                f.write("ABRIR_NUEVA_PESTANA=true\n")
                
                klog("init", "Estableciendo banderas de runtime (debug, logs, networking)...")
                f.write("FLASK_DEBUG=false\n")
                f.write("LOG_MODE=false\n")
                f.write("PORT=5050\n")
                f.write("HOST=127.0.0.1\n")
            
            klog("ok", "Archivo .env aprovisionado con llaves maestras e iniciales.")

        # 4. Chequeo de backups
        if os.path.exists(RUTA_ULTIMO_BACKUP):
            with open(RUTA_ULTIMO_BACKUP) as f:
                try:
                    ts = float(f.read().strip())
                    fecha_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
                    klog("ok", f"Punto de restauración detectado: {fecha_str}")
                except ValueError:
                    klog("warn", "Archivo de seguimiento de backup corrupto.")
        else:
            klog("info", "No se registra backup previo (disponible en /configuracion).")

    load_dotenv()
    app.secret_key = os.environ.get("SECRET_KEY")

    if not es_reloader:
        if os.environ.get("APP_PASSWORD") == "cambiame":
            print("\n" + "!" * 65)
            print(" [!] ALERTA CRÍTICA: Credencial de fábrica activa (APP_PASSWORD='cambiame')")
            print("     Cambiala desde la interfaz o ejecutando: python CLI_admin.py")
            print("!" * 65)

        print("\n" + "-" * 65)
        print(" [i] CONSOLA ADMINISTRATIVA DISPONIBLE:")
        print("     Ejecuta en una terminal secundaria: python CLI_admin.py")
        print("-" * 65)

    log_mode_activo = os.environ.get("LOG_MODE", "false").lower() == "true"
    if not log_mode_activo:
        logging.getLogger("werkzeug").setLevel(logging.ERROR)

    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 5050))

    if not es_reloader:
        if host == "0.0.0.0":
            ip_lan = "desconocida"
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip_lan = s.getsockname()[0]
                s.close()
            except Exception:
                pass

            klog("ok", f"Daemon HTTP (Local):   http://127.0.0.1:{port} (Debug: {debug_mode})")
            klog("ok", f"Daemon HTTP (Red LAN): http://{ip_lan}:{port} (Debug: {debug_mode})")
        else:
            klog("ok", f"Daemon HTTP enrutado en http://{host}:{port} (Debug: {debug_mode})")

        print("-" * 65)
        print(">>> DISPOSITIVO LISTO PARA ATENDER SOLICITUDES HTTP <<<")
        print("-" * 65 + "\n")

    app.run(
        host=host,
        port=port,
        debug=debug_mode,
        use_reloader=True,
        extra_files=[".env"]
    )