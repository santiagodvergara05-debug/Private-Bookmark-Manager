"""
==============================================================================
PBM PRIVATE BOOKMARK MANAGER - NÚCLEO DEL SERVIDOR Y BOOTLOADER GEN 3 (APP.PY)
==============================================================================
Punto de entrada principal del sistema de marcadores privados blindado.
Responsabilidades de arquitectura:
1. Detección de runtime (Desarrollo vs Binario congelado PyInstaller).
2. Sanitización binaria temprana y aislamiento preventivo de .env corrupto.
3. Inicialización del framework Flask y endurecimiento de cookies de sesión.
4. Telemetría de arranque estilo init/kernel de Linux con formateo ANSI.
5. Saneamiento del sistema de archivos local, purga de huérfanos y aislamiento WAL.
6. Auditoría exhaustiva de integridad SQLite (Magic Header, Tablas 'carpetas'/'marcadores').
7. Protocolo de Disaster Recovery y Rescate Automático desde Bóvedas BYOC (E2EE AES-256).
8. Auditoría cruzada de sincronización condicionada al modo operativo.
9. Resolución dinámica de interfaz local/LAN y puesta en marcha del servidor WSGI.
==============================================================================
"""

# ==============================================================================
# SECCIÓN 1: IMPORTACIONES Y CONSTANTES DE DIRECTORIO
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
import hashlib
from datetime import datetime

from flask import Flask, jsonify, request
from dotenv import load_dotenv, dotenv_values, set_key

# Detección de empaquetado PyInstaller
ES_EXE = getattr(sys, "frozen", False)
if ES_EXE:
    DIRECTORIO_RAIZ = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, "_MEIPASS", DIRECTORIO_RAIZ)
else:
    DIRECTORIO_RAIZ = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = DIRECTORIO_RAIZ

os.chdir(DIRECTORIO_RAIZ)

ENV_PATH = os.path.join(DIRECTORIO_RAIZ, ".env")
DB_PATH = os.path.join(DIRECTORIO_RAIZ, "marcadores.db")
BACKUPS_DIR = os.path.join(DIRECTORIO_RAIZ, "backups")


# ==============================================================================
# SECCIÓN 2: GESTOR DE RESILIENCIA Y AUTORREPARACIÓN BINARIA (.ENV)
# ==============================================================================
VALORES_PREDETERMINADOS = {
    "SISTEMA_INICIALIZADO": "false",
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
    # Módulo de Sincronización BYOC (E2EE AES-256)
    "SYNC_HABILITADO": "false",
    "SYNC_CARPETA": "",
    "SYNC_MODO_CIFRADO": "auto",
    "SYNC_CLAVE": lambda: secrets.token_hex(32),
    "SYNC_AUTO_APLICAR": "true",
    "SYNC_NOMBRE_DISPOSITIVO": lambda: socket.gethostname(),
    "SYNC_ULTIMA_REVISION": "0",
}


def serializar_valor_env(valor):
    """Sanitiza y serializa un valor para su almacenamiento seguro dentro de .env."""
    v_str = str(valor).replace("\r", "").replace("\n", "")
    v_str = v_str.replace("\\", "\\\\").replace("'", r"\'")
    return f"'{v_str}'"


def escribir_env_seguro(ruta_env, mapa_valores):
    """Escribe los ajustes en disco con reintentos para mitigar bloqueos transitorios."""
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
    Inspección binaria tolerante y autorreparación del archivo .env:
    - Lee en bytes ('rb') para que caracteres inválidos o bytes nulos (\x00, \xff) no crasheen Python.
    - Aísla configuraciones dañadas a .env.corrupt_<timestamp>.
    - Preserva y calcula 'ya_inicializado' respetando la existencia de marcadores.db.
    """
    valores = {}
    archivo_danado = False
    env_existia = os.path.exists(ruta_env)
    db_activa = os.path.exists(DB_PATH) and os.path.getsize(DB_PATH) > 0

    if env_existia:
        try:
            with open(ruta_env, "rb") as f:
                contenido_bytes = f.read()

            if b"\x00" in contenido_bytes:
                archivo_danado = True
            else:
                try:
                    contenido_bytes.decode("utf-8")
                    valores = dict(dotenv_values(ruta_env))
                except Exception:
                    archivo_danado = True
        except Exception:
            archivo_danado = True

    quarantine_nombre = None
    if archivo_danado:
        quarantine_nombre = f".env.corrupt_{int(time.time())}"
        try:
            os.rename(ruta_env, os.path.join(DIRECTORIO_RAIZ, quarantine_nombre))
        except Exception:
            try:
                os.remove(ruta_env)
            except Exception:
                pass
        valores = {}

    flag_env = str(valores.get("SISTEMA_INICIALIZADO", "")).strip("'\"").lower() == "true"
    ya_inicializado = flag_env or db_activa

    hubo_cambios = archivo_danado or (not env_existia)
    faltantes = []
    advertencias = []

    # Conciliación de consistencia
    val_init = valores.get("SISTEMA_INICIALIZADO")
    if val_init is not None and str(val_init).strip("'\"").lower() == "false" and db_activa:
        advertencias.append("Inconsistencia: marcadores.db activo pero SISTEMA_INICIALIZADO='false'. Corrigiendo a 'true'...")
        valores["SISTEMA_INICIALIZADO"] = "true"
        hubo_cambios = True

    for clave, valor_default in VALORES_PREDETERMINADOS.items():
        val = valores.get(clave)

        if clave == "SISTEMA_INICIALIZADO":
            if val is None or not str(val).strip():
                valores[clave] = "true" if ya_inicializado else "false"
                faltantes.append(clave)
                hubo_cambios = True
            continue

        if clave == "SYNC_CARPETA":
            if val is None:
                valores[clave] = ""
                faltantes.append(clave)
                hubo_cambios = True
            continue

        if val is None or not str(val).strip():
            nuevo_val = valor_default() if callable(valor_default) else valor_default
            valores[clave] = nuevo_val
            faltantes.append(clave)
            hubo_cambios = True

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

    host_raw = str(valores.get("HOST", "127.0.0.1")).strip("'\"")
    if host_raw not in ["127.0.0.1", "0.0.0.0"]:
        advertencias.append(f"Host no estándar ({host_raw}). Normalizando enlace a 127.0.0.1...")
        valores["HOST"] = "127.0.0.1"
        hubo_cambios = True

    if hubo_cambios:
        escribir_env_seguro(ruta_env, valores)

    for k, v in valores.items():
        os.environ[k] = str(v)

    return faltantes, ya_inicializado, env_existia, archivo_danado, advertencias, quarantine_nombre


# ==============================================================================
# SECCIÓN 3: PRE-BOOT Y CARGA DE FLASK (INMUNE A FALLAS BINARIAS)
# ==============================================================================
# 1. Sanitizar .env ANTES de que cualquier módulo intente leerlo
faltantes_env, ya_inicializado_sistema, env_existia_prev, env_danado_prev, advertencias_env, quarantine_generado = sanitizar_y_reparar_env(ENV_PATH)
load_dotenv(ENV_PATH)

# Módulos dependientes de configuración
import database
import sync_manager
from routes import marcadores_bp, RUTA_ULTIMO_BACKUP
from version import VERSION

try:
    from routes import RUTA_ULTIMO_SYNC
except ImportError:
    RUTA_ULTIMO_SYNC = "ultimo_sync.txt"

try:
    from logger_http import configurar_logger_http
    TIENE_LOGGER_HTTP = True
except ImportError:
    TIENE_LOGGER_HTTP = False

app = Flask(
    __name__,
    template_folder=os.path.join(BUNDLE_DIR, "templates"),
    static_folder=os.path.join(BUNDLE_DIR, "static")
)

app.secret_key = os.environ.get("SECRET_KEY")
app.register_blueprint(marcadores_bp)

if TIENE_LOGGER_HTTP:
    configurar_logger_http(app)

app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False


@app.errorhandler(413)
def error_archivo_demasiado_grande(e):
    ip_origen = request.remote_addr
    print(f"\n\033[91m[PBM :: ALERTA DE SEGURIDAD]\033[0m Carga masiva interceptada (> 100 MB) desde IP: {ip_origen}")
    return jsonify({
        "ok": False,
        "error": "El archivo excede el tamaño máximo permitido por el servidor (100 MB)."
    }), 413


# ==============================================================================
# SECCIÓN 4: MOTOR DE TELEMETRÍA (KLOG) Y UTILIDADES DE INTEGRIDAD
# ==============================================================================
def klog(estado, mensaje, delay=0.07):
    """Emite líneas de telemetría de arranque estilo kernel con formateo ANSI."""
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


def calcular_sha256_local(ruta):
    """Calcula el hash SHA-256 en bloques de 64 KB de forma segura mediante streaming."""
    if not os.path.exists(ruta):
        return None
    try:
        h = hashlib.sha256()
        with open(ruta, "rb") as f:
            for bloque in iter(lambda: f.read(65536), b""):
                h.update(bloque)
        return h.hexdigest()
    except Exception:
        return None


def resolver_ip_lan():
    """Resuelve la dirección IP en la red local de forma tolerante a entornos 100% offline."""
    ip_detectada = "127.0.0.1"
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("10.255.255.255", 1))
        ip_detectada = sock.getsockname()[0]
    except Exception:
        try:
            ip_detectada = socket.gethostbyname(socket.gethostname())
        except Exception:
            pass
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass
    return ip_detectada


# ==============================================================================
# SECCIÓN 5: AUDITORÍA DE INTEGRIDAD SQLITE
# ==============================================================================
def auditar_integridad_db(db_path):
    """
    Audita exhaustivamente la base de datos de marcadores:
    - Retorna 'ausente' si no existe o mide 0 bytes.
    - Retorna 'bloqueada' si otro proceso retiene un bloqueo exclusivo en disco.
    - Retorna 'corrupta' ante fallo estructural de páginas B-Tree o cabecera inválida.
    - Retorna 'incompleta' si falta alguna de las tablas maestras ('carpetas', 'marcadores').
    - Retorna 'ok' junto con el conteo de registros si la estructura es sólida.
    """
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        return "ausente", 0, 0

    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=3.0)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("PRAGMA integrity_check;")
        res = cur.fetchone()
        if not res or res[0] != "ok":
            return "corrupta", 0, 0

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('carpetas', 'marcadores');")
        tablas = [r["name"] for r in cur.fetchall()]
        if "carpetas" not in tablas or "marcadores" not in tablas:
            return "incompleta", 0, 0

        def contar_seguro(query):
            try:
                cur.execute(query)
                r = cur.fetchone()
                return r[0] if r else 0
            except Exception:
                return 0

        total_carpetas = contar_seguro("SELECT COUNT(*) FROM carpetas;")
        total_marcadores = contar_seguro("SELECT COUNT(*) FROM marcadores;")

        return "ok", total_carpetas, total_marcadores

    except sqlite3.OperationalError as e:
        err_msg = str(e).lower()
        if "locked" in err_msg or "busy" in err_msg:
            return "bloqueada", 0, 0
        return "corrupta", 0, 0

    except (sqlite3.DatabaseError, sqlite3.Error):
        return "corrupta", 0, 0

    except Exception:
        return "corrupta", 0, 0

    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def sanear_directorios_y_archivos():
    """Verifica directorios requeridos y purga archivos temporales residuales."""
    directorios = [
        ("templates", os.path.join(DIRECTORIO_RAIZ, "templates")),
        ("static", os.path.join(DIRECTORIO_RAIZ, "static")),
        ("backups", BACKUPS_DIR)
    ]

    for nombre, ruta in directorios:
        if not os.path.exists(ruta):
            os.makedirs(ruta, exist_ok=True)
            klog("init", f"Directorio aprovisionado: /{nombre}")
        else:
            klog("ok", f"Directorio confirmado: /{nombre}")

    purgados_sync = 0
    for elemento in os.listdir(DIRECTORIO_RAIZ):
        if elemento.endswith((".pre_sync", ".zip.tmp", ".db.tmp")):
            try:
                os.remove(os.path.join(DIRECTORIO_RAIZ, elemento))
                purgados_sync += 1
            except Exception:
                pass
    if purgados_sync > 0:
        klog("warn", f"Saneamiento: {purgados_sync} archivo(s) temporales residuales de sync eliminados.")


# ==============================================================================
# SECCIÓN 6: RUTINA DE ARRANQUE (BOOTLOADER), RED LAN Y SERVIDOR WSGI
# ==============================================================================
if __name__ == "__main__":
    es_reloader = os.environ.get("WERKZEUG_RUN_MAIN") == "true"

    if not es_reloader:
        print("\n" + "=" * 65)
        print(f"   BOOTLOADER :: PBM PrivateBookmarkManager v{VERSION} (OFFLINE & SECURE)   ")
        print("=" * 65)
        time.sleep(0.10)

        # 1. Informe de telemetría del entorno .env
        if not env_existia_prev:
            klog("warn", "Configuración .env no encontrada. Iniciando aprovisionamiento inicial...")
            for clave in faltantes_env:
                klog("init", f"Generando parámetro predeterminado: {clave}")
            klog("ok", f"Archivo .env de fábrica creado con {len(faltantes_env)} variables.")

        elif env_danado_prev:
            klog("fail", "Archivo .env ilegible o corrupto (sabotaje de datos binarios detectado).")
            klog("warn", f"Configuración dañada aislada como: {quarantine_generado}")
            for clave in faltantes_env:
                klog("init", f"Regenerando parámetro tras aislamiento: {clave}")
            klog("ok", f"Archivo .env recuperado con {len(faltantes_env)} variables.")

        else:
            klog("ok", "Archivo .env cargado desde almacenamiento local.")
            for adv in advertencias_env:
                klog("warn", adv)

            for clave in faltantes_env:
                klog("init", f"Restaurando parámetro faltante: {clave}")

            if faltantes_env or advertencias_env:
                klog("ok", "Archivo .env reparado con éxito.")
            else:
                klog("ok", "Archivo .env verificado: integridad completa.")

        # 2. Verificación de Entropía Criptográfica en Llaves Maestras
        master_val = os.environ.get("MASTER_KEY", "").strip("'\"")
        sync_clave_val = os.environ.get("SYNC_CLAVE", "").strip("'\"")

        es_hex_64 = lambda s: len(s) == 64 and all(c in "0123456789abcdefABCDEF" for c in s)

        master_es_256 = es_hex_64(master_val)
        sync_es_256 = es_hex_64(sync_clave_val)

        if master_es_256:
            klog("ok", "Llaves criptográficas maestras activas (256 bits).")
        else:
            bits_master = len(master_val.encode("utf-8")) * 8
            klog("info", f"Llave maestra manual activa: {bits_master} bits ({len(master_val)} car. / personalizada).")

        sync_activa_check = os.environ.get("SYNC_HABILITADO", "false").strip().lower() == "true"
        if sync_activa_check and not sync_es_256 and os.environ.get("SYNC_MODO_CIFRADO", "auto") != "libre":
            bits_sync = len(sync_clave_val.encode("utf-8")) * 8
            klog("info", f"SYNC_CLAVE opera con clave manual: {bits_sync} bits ({len(sync_clave_val)} car.).")

        # Telemetría de preferencias visuales
        modo_oscuro = "Sí" if os.environ.get("MODO_OSCURO", "false").lower() == "true" else "No"
        favicons = "Sí" if os.environ.get("MOSTRAR_FAVICONS", "true").lower() == "true" else "No"
        nueva_pestana = "Sí" if os.environ.get("ABRIR_NUEVA_PESTANA", "true").lower() == "true" else "No"
        klog("ok", f"Preferencias web activas: [Oscuro: {modo_oscuro}] [Favicons: {favicons}] [Pestaña nueva: {nueva_pestana}]")

        # 3. Comprobación y saneamiento de almacenamiento físico
        klog("init", "Verificando estructura de almacenamiento...")
        sanear_directorios_y_archivos()

        # 4. Auditoría estructural de base de datos SQLite
        estado_db, n_carpetas, n_marcadores = auditar_integridad_db(DB_PATH)

        if estado_db == "bloqueada":
            klog("fail", "La base de datos se encuentra bloqueada por otro proceso.")
            klog("warn", "Esperando 2 segundos para liberación de candado...")
            time.sleep(2)
            estado_db, n_carpetas, n_marcadores = auditar_integridad_db(DB_PATH)
            if estado_db == "bloqueada":
                klog("fail", "Imposible acceder a marcadores.db. Cierre el proceso que mantiene el bloqueo.")
                sys.exit(1)

        if estado_db == "corrupta":
            klog("fail", "Base de datos dañada o ilegible (sabotaje / corrupción estructural).")
            cuarentena_db = f"marcadores.db.corrupt_{int(time.time())}"
            try:
                os.rename(DB_PATH, os.path.join(DIRECTORIO_RAIZ, cuarentena_db))
                klog("warn", f"Base de datos corrupta aislada en cuarentena: {cuarentena_db}")
            except Exception:
                try:
                    os.remove(DB_PATH)
                except Exception:
                    pass

            for ext_wal in ["-wal", "-shm", "-journal"]:
                f_wal = DB_PATH + ext_wal
                if os.path.exists(f_wal):
                    try:
                        os.remove(f_wal)
                    except Exception:
                        pass
            estado_db = "ausente"

        # 5. Protocolo de Sincronización BYOC y Disaster Recovery
        sync_activa = os.environ.get("SYNC_HABILITADO", "false").strip().lower() == "true"
        carpeta_nube = os.environ.get("SYNC_CARPETA", "").strip()
        auto_aplicar = os.environ.get("SYNC_AUTO_APLICAR", "false").strip().lower() == "true"
        recuperada_de_nube = False
        boveda_bloqueada_corrupta = False
        rev_local = 0
        rev_remota = 0

        try:
            rev_local = int(os.environ.get("SYNC_ULTIMA_REVISION", "0").strip())
        except ValueError:
            rev_local = 0

        if sync_activa and carpeta_nube:
            klog("init", f"Verificando enlace BYOC: {carpeta_nube}")
            if not os.path.isdir(carpeta_nube):
                klog("warn", "Carpeta de sincronización inalcanzable. Operando en modo local.")
            else:
                ruta_meta_fisica = os.path.join(carpeta_nube, "pbm_vault.meta")
                ruta_zip_fisica = os.path.join(carpeta_nube, "pbm_vault.zip")
                
                meta = sync_manager.leer_metadatos_remotos(carpeta_nube)
                
                if os.path.exists(ruta_meta_fisica) and not meta:
                    boveda_bloqueada_corrupta = True
                    klog("fail", "Archivo 'pbm_vault.meta' corrupto o ilegible en la nube.")
                    klog("warn", "Ignorando bóveda remota dañada por seguridad (modo local forzado).")

                elif meta:
                    rev_remota = int(meta.get("revision", 0))
                    origen = meta.get("ultimo_equipo", "Nodo Externo")
                    modo_cif = os.environ.get("SYNC_MODO_CIFRADO", "auto").strip().lower()
                    clave = "" if modo_cif == "libre" else os.environ.get("SYNC_CLAVE", "").strip()

                    zip_presente = os.path.exists(ruta_zip_fisica) and os.path.getsize(ruta_zip_fisica) > 0

                    if not zip_presente:
                        boveda_bloqueada_corrupta = True
                        klog("fail", f"Inconsistencia en la nube: Existe .meta (#{rev_remota}) pero falta 'pbm_vault.zip'.")

                    elif estado_db == "ausente":
                        klog("warn", f"Base local no disponible. Ejecutando Rescate Automático (#{rev_remota} desde '{origen}')...")
                        exito, msg = sync_manager.importar_boveda_cifrada(carpeta_nube, DB_PATH, clave_sync=clave)
                        if exito:
                            klog("ok", f"Rescate completado con éxito: {msg}")
                            rev_local = rev_remota
                            recuperada_de_nube = True
                            try:
                                with open(os.path.join(DIRECTORIO_RAIZ, RUTA_ULTIMO_SYNC), "w", encoding="utf-8") as f:
                                    f.write(str(time.time()))
                                set_key(ENV_PATH, "SYNC_ULTIMA_REVISION", str(rev_remota))
                                set_key(ENV_PATH, "SISTEMA_INICIALIZADO", "true")
                                os.environ["SYNC_ULTIMA_REVISION"] = str(rev_remota)
                                os.environ["SISTEMA_INICIALIZADO"] = "true"
                            except Exception:
                                pass
                            estado_db, n_carpetas, n_marcadores = auditar_integridad_db(DB_PATH)
                        else:
                            boveda_bloqueada_corrupta = True
                            klog("fail", f"Fallo al rescatar desde la nube (Firma SHA-256 o clave errónea): {msg}")

                    elif rev_remota > rev_local:
                        klog("info", f"Revisión remota #{rev_remota} disponible desde '{origen}' (Local: #{rev_local}).")
                        if auto_aplicar:
                            klog("init", "Auto-aplicando actualización de bóveda desde la nube...")
                            exito, msg = sync_manager.importar_boveda_cifrada(carpeta_nube, DB_PATH, clave_sync=clave)
                            if exito:
                                klog("ok", f"Bóveda aplicada con éxito: {msg}")
                                rev_local = rev_remota
                                try:
                                    with open(os.path.join(DIRECTORIO_RAIZ, RUTA_ULTIMO_SYNC), "w", encoding="utf-8") as f:
                                        f.write(str(time.time()))
                                    set_key(ENV_PATH, "SYNC_ULTIMA_REVISION", str(rev_remota))
                                    os.environ["SYNC_ULTIMA_REVISION"] = str(rev_remota)
                                except Exception:
                                    pass
                            else:
                                boveda_bloqueada_corrupta = True
                                klog("fail", f"Sincronización rechazada (Integridad SHA-256 comprometida): {msg}")
                        else:
                            klog("warn", f"Actualización pendiente (#{rev_remota} > #{rev_local}). Subida bloqueada por seguridad anti-atraso.")

                    elif rev_remota == rev_local:
                        if not os.path.exists(ruta_zip_fisica) or os.path.getsize(ruta_zip_fisica) == 0:
                            boveda_bloqueada_corrupta = True
                            klog("fail", f"Alerta en la nube: Existe .meta (#{rev_local}) pero 'pbm_vault.zip' está ausente o vacío.")
                        else:
                            hash_esperado = meta.get("hash_zip") or meta.get("hash_sha256") or meta.get("sha256")
                            if hash_esperado:
                                hash_real = calcular_sha256_local(ruta_zip_fisica)
                                if hash_real != hash_esperado:
                                    boveda_bloqueada_corrupta = True
                                    klog("fail", "Bóveda remota dañada: 'pbm_vault.zip' no coincide con su firma SHA-256.")
                                    klog("warn", "La copia remota está corrupta. Se sugiere re-subir la bóveda local.")
                                else:
                                    klog("ok", f"Bóveda sincronizada al día con la nube (Revisión #{rev_local} verificada).")
                            else:
                                klog("ok", f"Bóveda sincronizada al día con la nube (Revisión #{rev_local}).")

        # 6. Inicialización, Rescate y Autocuración de Esquema de Base de Datos
        if estado_db == "ausente" and not recuperada_de_nube:
            if ya_inicializado_sistema:
                klog("fail", "Base de datos eliminada externamente (pérdida de datos detectada).")
                klog("warn", "Regenerando estructura limpia de emergencia...")
                database.inicializar_db()
                klog("ok", "Nueva base de datos SQLite inicializada en estado limpio.")
                klog("warn", "Restaura tus marcadores desde /configuracion si cuentas con una copia de seguridad.")
            else:
                klog("info", "Primer inicio detectado: Generando marcadores.db limpia e indexada...")
                database.inicializar_db()
                klog("ok", "Base de datos SQLite creada e indexada correctamente.")
                set_key(ENV_PATH, "SISTEMA_INICIALIZADO", "true")
                os.environ["SISTEMA_INICIALIZADO"] = "true"

            try:
                with open(os.path.join(DIRECTORIO_RAIZ, RUTA_ULTIMO_SYNC), "w", encoding="utf-8") as f:
                    f.write(str(time.time() + 2.0))
            except Exception:
                pass
            estado_db, n_carpetas, n_marcadores = auditar_integridad_db(DB_PATH)

        elif estado_db in ["incompleta", "ok"]:
            database.inicializar_db()
            klog("ok", f"Base de datos verificada: {n_carpetas} carpetas y {n_marcadores} marcadores registrados.")

        # 7. Auditoría cruzada de sincronización y modificaciones locales
        if sync_activa and carpeta_nube:
            ruta_sync = os.path.join(DIRECTORIO_RAIZ, RUTA_ULTIMO_SYNC)
            ultimo_sync_ts = 0.0
            hay_nube_pendiente = bool(rev_remota > rev_local)

            if os.path.exists(ruta_sync):
                try:
                    with open(ruta_sync, "r", encoding="utf-8") as f:
                        ultimo_sync_ts = float(f.read().strip())
                        fecha_sync_str = datetime.fromtimestamp(ultimo_sync_ts).strftime("%Y-%m-%d %H:%M:%S")

                        if os.path.exists(DB_PATH):
                            db_mtime = os.path.getmtime(DB_PATH)
                            total_registros = n_carpetas + n_marcadores

                            if total_registros > 0 and db_mtime > (ultimo_sync_ts + 1.5):
                                klog("warn", f"Cambios locales en marcadores.db posteriores al último sync ({fecha_sync_str}).")
                            elif boveda_bloqueada_corrupta:
                                klog("fail", f"Sincronización suspendida: Bóveda remota #{rev_remota} bloqueada por integridad.")
                            elif hay_nube_pendiente:
                                klog("warn", f"Último sync local: {fecha_sync_str} (Pendiente descargar #{rev_remota} de la nube).")
                            else:
                                klog("ok", f"Última sincronización confirmada: {fecha_sync_str} (Datos locales al día).")
                        else:
                            klog("ok", f"Última sincronización registrada: {fecha_sync_str}")
                except Exception:
                    klog("warn", "Archivo de seguimiento de sincronización corrupto (ignorado).")
            else:
                klog("info", "Sin registro de sincronización previa en este nodo (archivo testigo ausente).")
        else:
            klog("info", "Sincronización BYOC desactivada (Operando en modo local independiente).")

        # 8. Verificación de última instantánea de respaldo
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

        # 9. Detección y aviso de credencial por defecto
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

    if not TIENE_LOGGER_HTTP:
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
            ip_lan = resolver_ip_lan()
            klog("ok", f"Servidor Local:   http://127.0.0.1:{port}")
            klog("ok", f"Acceso LAN Red:   http://{ip_lan}:{port}")
            klog("info", "Acceso multidispositivo habilitado en la red local.")
        else:
            klog("ok", f"Servidor Local enrutado en http://{host}:{port}")
            klog("fail", "Acceso LAN Red: no disponible")
            klog("info", "Acceso LAN Red: Desactivado (modo exclusivo PC local)")

        print("-" * 65)
        print(">>> PBM PrivateBookmarkManager OPERATIVO Y LISTO <<<")
        print("-" * 65 + "\n")

    auto_abrir = os.environ.get("AUTO_ABRIR_NAVEGADOR", "true").strip().lower() == "true"
    if auto_abrir and (ES_EXE or not es_reloader):
        url_destino = f"http://127.0.0.1:{port}"
        threading.Timer(1.2, lambda: webbrowser.open(url_destino)).start()

    app.run(
        host=host,
        port=port,
        debug=debug_mode,
        use_reloader=False if ES_EXE else True,
        extra_files=[ENV_PATH] if not ES_EXE else []
    )