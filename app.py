"""
==============================================================================
PBM PRIVATE BOOKMARK MANAGER - NÚCLEO DEL SERVIDOR Y BOOTLOADER (APP.PY)
==============================================================================
Punto de entrada principal del sistema de marcadores privados (Gen 2).
Responsabilidades de arquitectura:
1. Detección de runtime (Desarrollo vs Binario congelado PyInstaller).
2. Estabilización de directorio de trabajo físico (CWD) para accesos directos.
3. Inicialización del framework Flask y endurecimiento de cookies de sesión.
4. Telemetría de arranque estilo init/kernel de Linux con formateo ANSI.
5. Motor de autorreparación, sanitización atómica y aislamiento de .env corrupto.
6. Auditoría de integridad física SQLite, detección de bloqueos y cuarentena.
7. Aprovisionamiento y verificación estructural del sistema de archivos local.
8. Resolución de interfaz de red (Local vs LAN) y apertura controlada del navegador.
==============================================================================
"""

# ==============================================================================
# SECCIÓN 1: IMPORTACIONES Y RESOLUCIÓN DE RUTAS DEL SISTEMA
# ==============================================================================
import os
import sys
import time
import secrets
import logging
import socket
import sqlite3
import webbrowser
import threading
from datetime import datetime

# Componentes del framework web y gestión de entorno
from flask import Flask, jsonify, request
from dotenv import load_dotenv, dotenv_values

# Módulos internos de la arquitectura PBM
import database
from routes import marcadores_bp, RUTA_ULTIMO_BACKUP
from version import VERSION

# ------------------------------------------------------------------------------
# RESOLUCIÓN DINÁMICA DE ENTORNO (EXE vs SCRIPT)
# sys.frozen es inyectado por PyInstaller al ejecutar como binario congelado.
# ------------------------------------------------------------------------------
ES_EXE = getattr(sys, "frozen", False)
if ES_EXE:
    # Ruta física donde reside el ejecutable empaquetado
    DIRECTORIO_RAIZ = os.path.dirname(sys.executable)
    # Carpeta temporal volátil donde PyInstaller extrae templates y static
    BUNDLE_DIR = getattr(sys, "_MEIPASS", DIRECTORIO_RAIZ)
else:
    # Modo desarrollo estándar de Python
    DIRECTORIO_RAIZ = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = DIRECTORIO_RAIZ

# Fijar el directorio de trabajo activo para evitar fallos por rutas relativas
os.chdir(DIRECTORIO_RAIZ)

# Rutas locales persistentes en disco
ENV_PATH = os.path.join(DIRECTORIO_RAIZ, ".env")
DB_PATH = os.path.join(DIRECTORIO_RAIZ, "marcadores.db")


# ==============================================================================
# SECCIÓN 2: INICIALIZACIÓN DE FLASK Y POLÍTICAS DE SEGURIDAD
# ==============================================================================
app = Flask(
    __name__,
    template_folder=os.path.join(BUNDLE_DIR, "templates"),
    static_folder=os.path.join(BUNDLE_DIR, "static")
)

# Registro del Blueprint central de marcadores
app.register_blueprint(marcadores_bp)

# Límite global contra DoS: 25 MiB (más que suficiente para miles de marcadores)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 26,214,400 bytes

# ------------------------------------------------------------------------------
# BLINDAJE DE IDENTIDAD: POLÍTICAS DE COOKIES DE SESIÓN
# HttpOnly  -> Mitiga la exfiltración de credenciales vía scripts maliciosos (XSS)
# SameSite  -> Mitiga ataques de falsificación de petición en sitios cruzados (CSRF)
# ------------------------------------------------------------------------------
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False

@app.errorhandler(413)
def error_archivo_demasiado_grande(e):
    """Intercepta cargas de archivos que superen los 25 MB."""
    ip_origen = request.remote_addr
    print(f"\n\033[91m[ALERTA DE SEGURIDAD :: OVERFLOW]\033[0m Carga masiva interceptada (> 25 MB) desde IP: {ip_origen}")
    return jsonify({
        "ok": False,
        "error": "El archivo excede el tamaño máximo permitido por el servidor (25 MB)."
    }), 413


# ==============================================================================
# SECCIÓN 3: MOTOR DE TELEMETRÍA Y LOGS ESTILO INIT / KERNEL
# ==============================================================================
def klog(estado, mensaje, delay=0.08):
    """
    Imprime mensajes formateados con insignias y colores ANSI simulando
    el arranque de un kernel Unix. Implementa fallback limpio si no hay soporte TTY.
    """
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


# ==============================================================================
# SECCIÓN 4: GESTIÓN, RESILIENCIA Y AUTORREPARACIÓN DE ENTORNO (.ENV)
# ==============================================================================
# Esquema de configuración comercial predeterminado de PBM
VALORES_PREDETERMINADOS = {
    "SISTEMA_INICIALIZADO": "true",
    "SECRET_KEY": lambda: secrets.token_hex(32),
    "MASTER_KEY": lambda: secrets.token_hex(32),
    "APP_PASSWORD": "cambiame",
    "CONTRASENA_MOSTRADA": "false",
    "MOSTRAR_FAVICONS": "true",
    "ABRIR_NUEVA_PESTANA": "true",
    "AUTO_ABRIR_NAVEGADOR": "true",
    "MODO_OSCURO": "false",
    "FLASK_DEBUG": "false",
    "LOG_MODE": "false",
    "PORT": "5050",
    "HOST": "127.0.0.1",
}

def serializar_valor_env(valor):
    """
    Normaliza y escapa valores para su serialización segura en el archivo .env,
    evitando inyecciones de saltos de línea o caracteres destructivos.
    """
    v_str = str(valor).replace("\r", "").replace("\n", "")
    v_str = v_str.replace("\\", "\\\\").replace("'", r"\'")
    return f"'{v_str}'"


def escribir_env_seguro(ruta_env, mapa_valores):
    """
    Escribe atómicamente el mapa de configuración completo en una sola pasada.
    Implementa reintentos exponenciales ante bloqueos temporales de disco en Windows.
    """
    for _ in range(4):
        try:
            with open(ruta_env, "w", encoding="utf-8") as f:
                for k, v in mapa_valores.items():
                    f.write(f"{k}={serializar_valor_env(v)}\n")
            return True
        except (PermissionError, OSError):
            time.sleep(0.15)
    return False


def sanitizar_y_reparar_env(ruta_env):
    """
    Motor de autocuración de configuración:
    1. Detecta archivos .env ilegibles o dañados por bytes binarios y los aísla.
    2. Aprovisiona claves faltantes invocando generadores criptográficos al vuelo.
    3. Normaliza rangos de puerto (1..65535) y direcciones IP de interfaz.
    4. Corrige inconsistencias de estado si la base de datos ya existe físicamente.
    """
    valores = {}
    archivo_danado = False
    env_existia = os.path.exists(ruta_env)

    # 1. Comprobación de lectura física
    if env_existia:
        try:
            with open(ruta_env, "r", encoding="utf-8") as f:
                f.read()
            valores = dict(dotenv_values(ruta_env))
        except Exception:
            archivo_danado = True

    # 2. Aislamiento preventivo ante corrupción
    if archivo_danado:
        ya_inicializado = True
        klog("fail", "Archivo .env corrupto o ilegible. Aislándolo preventivamente...")
        quarantine = f".env.corrupt_{int(time.time())}"
        try:
            os.rename(ruta_env, os.path.join(DIRECTORIO_RAIZ, quarantine))
            klog("warn", f"Configuración dañada enviada a cuarentena: {quarantine}")
        except Exception:
            try:
                os.remove(ruta_env)
            except Exception:
                pass
        valores = {}
    else:
        flag_env = str(valores.get("SISTEMA_INICIALIZADO", "")).strip("'\"").lower() == "true"
        ya_inicializado = flag_env or os.path.exists(DB_PATH)

    hubo_cambios = archivo_danado or (not env_existia)
    faltantes = []
    advertencias = []

    # 3. Conciliación de estado: Base activa con flag en false
    val_init = valores.get("SISTEMA_INICIALIZADO")
    if val_init is not None and str(val_init).strip("'\"").lower() == "false" and os.path.exists(DB_PATH):
        advertencias.append("Inconsistencia: marcadores.db activo pero SISTEMA_INICIALIZADO='false'. Corrigiendo a 'true'...")
        valores["SISTEMA_INICIALIZADO"] = "true"
        hubo_cambios = True

    # 4. Provisión de parámetros faltantes o vacíos
    for clave, valor_default in VALORES_PREDETERMINADOS.items():
        val = valores.get(clave)
        if val is None or not str(val).strip():
            nuevo_val = valor_default() if callable(valor_default) else valor_default
            valores[clave] = nuevo_val
            faltantes.append(clave)
            hubo_cambios = True

    # 5. Sanitización del puerto de red (1 a 65535)
    puerto_raw = valores.get("PORT", "5050")
    try:
        puerto_num = int(str(puerto_raw).strip("'\""))
        if not (1 <= puerto_num <= 65535):
            raise ValueError
        valores["PORT"] = str(puerto_num)
    except Exception:
        advertencias.append(f"Puerto inválido detectado ({puerto_raw}). Restableciendo a 5050...")
        valores["PORT"] = "5050"
        hubo_cambios = True

    # 6. Sanitización del host de enlace
    host_raw = str(valores.get("HOST", "127.0.0.1")).strip("'\"")
    if host_raw not in ["127.0.0.1", "0.0.0.0"]:
        advertencias.append(f"Host no estándar ({host_raw}). Normalizando enlace a 127.0.0.1...")
        valores["HOST"] = "127.0.0.1"
        hubo_cambios = True

    # 7. Persistencia final en disco
    if hubo_cambios:
        exito = escribir_env_seguro(ruta_env, valores)
        if not exito:
            klog("warn", "Bloqueo de E/S en disco. Empleando configuración en memoria volátil.")

    # Exportar al entorno del proceso
    for k, v in valores.items():
        os.environ[k] = str(v)

    return faltantes, ya_inicializado, env_existia, archivo_danado, advertencias


# ==============================================================================
# SECCIÓN 5: AUDITORÍA AVANZADA DE INTEGRIDAD SQLITE
# ==============================================================================
def auditar_integridad_db(db_path):
    """
    Inspecciona la integridad estructural de la base de datos de marcadores:
    - Ejecuta PRAGMA integrity_check para validar la salud física de las páginas B-Tree.
    - Confirma la presencia de los esquemas requeridos ('carpetas', 'marcadores').
    - Cuantifica registros para telemetría inicial.
    - Captura estados de bloqueo de concurrencia ('database is locked').
    """
    if not os.path.exists(db_path):
        return "ausente", 0, 0

    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=2.0)
        cur = conn.cursor()

        # Comprobación de integridad física de páginas
        cur.execute("PRAGMA integrity_check;")
        res = cur.fetchone()
        if not res or res[0] != "ok":
            return "corrupta", 0, 0

        # Verificación de esquemas relacionales obligatorios
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('carpetas', 'marcadores');")
        tablas = [r[0] for r in cur.fetchall()]
        if len(tablas) < 2:
            return "incompleta", 0, 0

        # Métricas de almacenamiento
        cur.execute("SELECT COUNT(*) FROM carpetas;")
        total_carpetas = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM marcadores;")
        total_marcadores = cur.fetchone()[0]

        return "ok", total_carpetas, total_marcadores

    except sqlite3.OperationalError as e:
        if "locked" in str(e).lower():
            return "bloqueada", 0, 0
        return "corrupta", 0, 0
    except Exception:
        return "corrupta", 0, 0
    finally:
        if conn:
            conn.close()


# ==============================================================================
# SECCIÓN 6: SANEAMIENTO DEL SISTEMA DE ARCHIVOS
# ==============================================================================
def sanear_directorios():
    """
    Aprovisiona y confirma la existencia de los directorios indispensables
    en la raíz de la aplicación para el correcto renderizado de recursos.
    """
    directorios = [
        ("templates", os.path.join(DIRECTORIO_RAIZ, "templates")),
        ("static", os.path.join(DIRECTORIO_RAIZ, "static"))
    ]

    for nombre, ruta in directorios:
        if not os.path.exists(ruta):
            os.makedirs(ruta, exist_ok=True)
            klog("init", f"Directorio aprovisionado: /{nombre}")
        else:
            klog("ok", f"Directorio confirmado: /{nombre}")


# ==============================================================================
# SECCIÓN 7: RUTINA DE ARRANQUE (BOOTLOADER), RED LAN Y SERVIDOR WSGI
# ==============================================================================
if __name__ == "__main__":
    es_reloader = os.environ.get("WERKZEUG_RUN_MAIN") == "true"

    if not es_reloader:
        print("\n" + "=" * 65)
        print(f"   BOOTLOADER :: PBM PrivateBookmarkManager v{VERSION} (OFFLINE)   ")
        print("=" * 65)
        time.sleep(0.15)

        # 1. Auditoría y autorreparación del entorno .env
        faltantes, ya_inicializado, env_existia, archivo_danado, advertencias = sanitizar_y_reparar_env(ENV_PATH)

        if not env_existia:
            klog("warn", "Configuración .env ausente. Iniciando aprovisionamiento inicial...")
            for clave in faltantes:
                klog("init", f"Generando parámetro predeterminado: {clave}")
            klog("ok", f"Archivo .env de fábrica configurado con {len(faltantes)} variables.")

        elif archivo_danado:
            for clave in faltantes:
                klog("init", f"Regenerando parámetro tras aislamiento: {clave}")
            klog("ok", f"Archivo .env recuperado con {len(faltantes)} variables.")

        else:
            klog("ok", "Archivo .env cargado desde almacenamiento local.")
            for adv in advertencias:
                klog("warn", adv)

            for clave in faltantes:
                klog("init", f"Restaurando parámetro faltante: {clave}")

            if faltantes or advertencias:
                klog("ok", "Archivo .env reparado con éxito.")
            else:
                klog("ok", "Archivo .env verificado: integridad completa.")

        # Cargar variables en el entorno del proceso
        try:
            load_dotenv(ENV_PATH, override=True)
        except Exception:
            pass

        app.secret_key = os.environ.get("SECRET_KEY")

        if os.environ.get("MASTER_KEY") and os.environ.get("SECRET_KEY"):
            klog("ok", "Llaves criptográficas maestras verificadas (256 bits).")

        # Telemetría de preferencias visuales de marcadores
        modo_oscuro = "Sí" if os.environ.get("MODO_OSCURO", "false").lower() == "true" else "No"
        favicons = "Sí" if os.environ.get("MOSTRAR_FAVICONS", "true").lower() == "true" else "No"
        nueva_pestana = "Sí" if os.environ.get("ABRIR_NUEVA_PESTANA", "true").lower() == "true" else "No"
        klog("ok", f"Preferencias web activas: [Oscuro: {modo_oscuro}] [Favicons: {favicons}] [Pestaña nueva: {nueva_pestana}]")

        # 2. Comprobación estructural de carpetas base
        klog("init", "Verificando estructura de interfaz...")
        sanear_directorios()

        # 3. Auditoría de integridad de marcadores.db
        estado_db, n_carpetas, n_marcadores = auditar_integridad_db(DB_PATH)

        # Manejo de candado de concurrencia activo
        if estado_db == "bloqueada":
            klog("fail", "La base de datos se encuentra bloqueada por otro proceso activo.")
            klog("warn", "Esperando 2 segundos para liberación de candado...")
            time.sleep(2)
            estado_db, n_carpetas, n_marcadores = auditar_integridad_db(DB_PATH)
            if estado_db == "bloqueada":
                klog("fail", "Imposible acceder a marcadores.db. Cierre el proceso que retiene el archivo.")
                sys.exit(1)

        # Base de datos ausente
        if estado_db == "ausente":
            if not ya_inicializado:
                klog("info", "Almacenamiento persistente ausente. Generando marcadores.db...")
            else:
                klog("fail", "Base de datos eliminada externamente. Regenerando estructura limpia...")
            database.inicializar_db()
            klog("ok", "Base de datos SQLite creada e indexada correctamente.")

        # Base de datos físicamente corrupta
        elif estado_db == "corrupta":
            klog("fail", "Fallo crítico de integridad en marcadores.db. Aislándolo en cuarentena...")
            cuarentena_db = f"marcadores.db.corrupt_{int(time.time())}"
            try:
                os.rename(DB_PATH, os.path.join(DIRECTORIO_RAIZ, cuarentena_db))
                klog("warn", f"Base de datos dañada aislada como: {cuarentena_db}")
            except Exception:
                try:
                    os.remove(DB_PATH)
                except Exception:
                    pass
            database.inicializar_db()
            klog("ok", "Nueva base de datos SQLite inicializada en estado limpio.")
            klog("warn", "Restaure sus marcadores desde /configuracion si cuenta con una copia de seguridad.")

        # Base de datos presente y funcional
        elif estado_db in ["incompleta", "ok"]:
            database.inicializar_db()
            klog("ok", f"Base de datos verificada: {n_carpetas} carpetas y {n_marcadores} marcadores registrados.")

        # 4. Verificación de última instantánea de respaldo
        ruta_backup = os.path.join(DIRECTORIO_RAIZ, RUTA_ULTIMO_BACKUP)
        if os.path.exists(ruta_backup):
            try:
                with open(ruta_backup, "r", encoding="utf-8") as f:
                    ts = float(f.read().strip())
                    fecha_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                    klog("ok", f"Último respaldo verificado: {fecha_str}")
            except Exception:
                klog("warn", "Archivo de seguimiento de respaldo ilegible (ignorado).")
        else:
            klog("info", "No se detecta snapshot de respaldo previo.")

        # 5. Detección y aviso de credencial por defecto
        contrasena_ya_mostrada = os.environ.get("CONTRASENA_MOSTRADA", "false").strip().lower() == "true"
        if os.environ.get("APP_PASSWORD") == "cambiame" and not contrasena_ya_mostrada:
            print("\n" + "!" * 65)
            print(" [!] PRIMER INICIO DETECTADO: Credencial temporal activa ('cambiame')")
            print(" [i] Visualice la Master Key e inicie sesión en la pantalla web.")
            print("!" * 65)

        # Información sobre consola administrativa
        print("\n" + "-" * 65)
        comando_cli = "CLI_admin.exe" if ES_EXE else "python CLI_admin.py"
        print(f" [i] CONSOLA DE ADMINISTRACIÓN DISPONIBLE: {comando_cli}")
        print("-" * 65)

    # Configuración de red y modo de logging de Werkzeug
    load_dotenv(ENV_PATH, override=True)
    app.secret_key = os.environ.get("SECRET_KEY")

    log_mode_activo = os.environ.get("LOG_MODE", "false").strip().lower() == "true"
    if not log_mode_activo:
        logging.getLogger("werkzeug").setLevel(logging.ERROR)

    debug_mode = False if ES_EXE else (os.environ.get("FLASK_DEBUG", "false").strip().lower() == "true")
    host = os.environ.get("HOST", "127.0.0.1").strip()
    try:
        port = int(os.environ.get("PORT", "5050").strip())
    except ValueError:
        port = 5050

    # Resolución de acceso local o LAN
    if not es_reloader:
        klog("info", f"Modo Debug: {debug_mode}")
        if host == "0.0.0.0":
            ip_lan = "127.0.0.1"
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip_lan = s.getsockname()[0]
                s.close()
            except Exception:
                try:
                    ip_lan = socket.gethostbyname(socket.gethostname())
                except Exception:
                    pass

            klog("ok", f"Servidor Local:   http://127.0.0.1:{port}")
            klog("ok", f"Acceso LAN Red:   http://{ip_lan}:{port}")
            klog("info", "Acceso multidispositivo habilitado en la red local.")
        else:
            klog("ok", f"Servidor Local enrutado en http://{host}:{port}")
            klog("info", "Acceso LAN Red: Desactivado (modo exclusivo PC local)")

        print("-" * 65)
        print(">>> PBM PrivateBookmarkManager OPERATIVO Y LISTO <<<")
        print("-" * 65 + "\n")

    # Apertura diferida del navegador
    auto_abrir = os.environ.get("AUTO_ABRIR_NAVEGADOR", "true").strip().lower() == "true"
    if auto_abrir and (ES_EXE or not es_reloader):
        url_destino = f"http://127.0.0.1:{port}"
        threading.Timer(1.2, lambda: webbrowser.open(url_destino)).start()

    # Ejecución del servidor HTTP
    app.run(
        host=host,
        port=port,
        debug=debug_mode,
        use_reloader=False if ES_EXE else True,
        extra_files=[ENV_PATH] if not ES_EXE else []
    )