import os
import sys
import time
import secrets
import logging
import socket
import sqlite3
from datetime import datetime
from dotenv import load_dotenv, dotenv_values, set_key
from flask import Flask
import database
from routes import marcadores_bp, RUTA_ULTIMO_BACKUP
import webbrowser
import threading

ES_EXE = getattr(sys, "frozen", False)
if ES_EXE:
    DIRECTORIO_RAIZ = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, "_MEIPASS", DIRECTORIO_RAIZ)
else:
    DIRECTORIO_RAIZ = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = DIRECTORIO_RAIZ

app = Flask(
    __name__,
    template_folder=os.path.join(BUNDLE_DIR, "templates"),
    static_folder=os.path.join(BUNDLE_DIR, "static")
)
app.register_blueprint(marcadores_bp)

def klog(estado, mensaje, delay=0.2):
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

def auditar_integridad_db(db_path):
    """
    Verifica si el archivo SQLite existe, no está dañado y contiene los esquemas base.
    Garantiza el cierre estricto de la conexión para evitar bloqueos en Windows.
    """
    if not os.path.exists(db_path):
        return "ausente", 0, 0
    
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Test de integridad interna de SQLite
        cur.execute("PRAGMA integrity_check;")
        res = cur.fetchone()
        if not res or res[0] != "ok":
            return "corrupta", 0, 0

        # Verificación de tablas mínimas
        cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name IN ('carpetas', 'marcadores');")
        if cur.fetchone()[0] < 2:
            return "incompleta", 0, 0

        cur.execute("SELECT COUNT(*) FROM carpetas")
        total_carpetas = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM marcadores")
        total_marcadores = cur.fetchone()[0]
        return "ok", total_carpetas, total_marcadores
    except Exception:
        return "corrupta", 0, 0
    finally:
        if conn:
            conn.close()

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

def reparar_env(ruta_env):
    """
    Verifica que existan todas las variables esperadas en el .env.
    Las que falten se crean con su valor predeterminado (SECRET_KEY/MASTER_KEY
    se generan al vuelo en vez de usar un literal). Devuelve la lista de
    claves que tuvo que restaurar.
    """
    valores_actuales = dotenv_values(ruta_env) if os.path.exists(ruta_env) else {}
    faltantes = []
    for clave, valor_default in VALORES_PREDETERMINADOS.items():
        if clave not in valores_actuales:
            valor = valor_default() if callable(valor_default) else valor_default
            set_key(ruta_env, clave, valor)
            faltantes.append(clave)
    return faltantes

if __name__ == "__main__":
    es_reloader = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    ENV_PATH = os.path.join(DIRECTORIO_RAIZ, ".env")
    DB_PATH = os.path.join(DIRECTORIO_RAIZ, "marcadores.db")

    if not es_reloader:
        print("\n" + "=" * 65)
        print("         BOOTLOADER :: SISTEMA DE MARCADORES PRIVADOS         ")
        print("=" * 65)
        time.sleep(0.4)

        # 1. Comprobación y creación de carpetas de interfaz
        klog("init", "Verificando directorios base del sistema...")
        for directorio in ["templates", "static"]:
            dir_path = os.path.join(DIRECTORIO_RAIZ, directorio)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                klog("ok", f"Directorio aprovisionado: /{directorio}")
            else:
                klog("ok", f"Directorio confirmado: /{directorio}")

        # 2. Detección de arranque previo mediante .env
        ya_inicializado = False
        if os.path.exists(ENV_PATH):
            load_dotenv(ENV_PATH)
            # Reconoce la variable de bandera de instalación
            ya_inicializado = os.environ.get("SISTEMA_INICIALIZADO", "true").lower() == "true"

        # 3. Auditoría y gestión de almacenamiento SQLite
        estado_db, n_carp, n_marc = auditar_integridad_db(DB_PATH)

        if estado_db == "ausente":
            if not ya_inicializado:
                # Primer inicio real de la aplicación
                klog("info", "Almacenamiento persistente SQLite ausente.")
                klog("init", "Creando base de datos SQLite y esquemas relacionales...")
                klog("info", "marcadores.db será generado en el directorio raíz de la aplicación.")
                database.inicializar_db()
                klog("ok", "Base de datos creada e indexada correctamente.")
            else:
                # El sistema ya corrió antes, pero la DB fue borrada externamente
                klog("fail", "Almacenamiento SQLite ausente o eliminado por accidente.")
                klog("warn", "Se detectó configuración previa (.env) pero la base de datos no existe.")
                klog("warn", "Creando una base de datos SQLite limpia para permitir el arranque...")
                klog("init", "Creando base de datos SQLite y esquemas relacionales...")
                klog("info", "marcadores.db será generado en el directorio raíz de la aplicación.")
                database.inicializar_db()
                klog("ok", "Base de datos SQLite limpia configurada.")
                klog("warn", "Base antigua no recuperable. Restaure desde /configuracion si posee backup.")

        elif estado_db == "corrupta":
            klog("fail", "Almacenamiento SQLite corrupto o ilegible (Fallo de integridad).")
            backup_corrupto = f"marcadores.db.corrupt_{int(time.time())}"
            liberado = False

            try:
                os.rename(DB_PATH, os.path.join(DIRECTORIO_RAIZ, backup_corrupto))
                klog("warn", f"Archivo dañado preservado como: {backup_corrupto}")
                liberado = True
            except Exception as e:
                klog("warn", f"No se pudo renombrar ({e}). Forzando eliminación del archivo dañado...")
                try:
                    os.remove(DB_PATH)
                    liberado = True
                except Exception as err_remove:
                    klog("fail", f"No se pudo eliminar el archivo corrupto: {err_remove}")

            if liberado:
                klog("warn", "Regenerando almacenamiento SQLite limpio para restablecer servicio...")
                klog("init", "Creando base de datos SQLite y esquemas relacionales...")
                klog("info", "marcadores.db será generado en el directorio raíz de la aplicación.")
                database.inicializar_db()
                klog("ok", "Base de datos SQLite recuperada en estado limpio.")
                klog("warn", "Importe su última copia de seguridad JSON desde /configuracion.")
            else:
                klog("fail", "Deteniendo arranque: cierre cualquier visor de SQLite o proceso externo.")
                sys.exit(1)

        elif estado_db in ["incompleta", "ok"]:
            database.inicializar_db()
            klog("ok", f"Base de datos verificada: {n_carp} carpetas y {n_marc} marcadores registrados.")

        # 4. Archivo de configuración (.env) — creación y reparación automática
        env_existia_antes = os.path.exists(ENV_PATH)

        if not env_existia_antes:
            klog("warn", "Configuración .env no encontrada. Iniciando aprovisionamiento...")
            open(ENV_PATH, "w", encoding="utf-8").close()
        else:
            klog("ok", "Archivo .env cargado desde almacenamiento local.")

        faltantes = reparar_env(ENV_PATH)
        for clave in faltantes:
            klog("init", f"Variable faltante detectada: generando {clave} con su valor predeterminado...")

        if not env_existia_antes:
            klog("ok", f"Archivo .env creado con {len(faltantes)} variable(s) iniciales.")
        elif faltantes:
            klog("ok", f"Archivo .env reparado ({len(faltantes)} variable(s) restaurada(s)).")
        else:
            klog("ok", "Archivo .env verificado: todas las variables presentes.")

        load_dotenv(ENV_PATH)
        app.secret_key = os.environ.get("SECRET_KEY")

        # Diagnóstico de preferencias activas
        oscuro = "Sí" if os.environ.get("MODO_OSCURO") == "true" else "No"
        favicons = "Sí" if os.environ.get("MOSTRAR_FAVICONS") == "true" else "No"
        tab = "Sí" if os.environ.get("ABRIR_NUEVA_PESTANA") == "true" else "No"
        klog("ok", f"Preferencias web activas: [Oscuro: {oscuro}] [Favicons: {favicons}] [Pestaña nueva: {tab}]")

        if os.environ.get("MASTER_KEY") and os.environ.get("SECRET_KEY"):
            klog("ok", "MASTER_KEY criptográfico verificada (256 bits).")

        # 5. Chequeo de backups
        ruta_backup = os.path.join(DIRECTORIO_RAIZ, RUTA_ULTIMO_BACKUP)
        if os.path.exists(ruta_backup):
            with open(ruta_backup) as f:
                try:
                    ts = float(f.read().strip())
                    fecha_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
                    klog("ok", f"Fecha de restauración verificada: {fecha_str}")
                except ValueError:
                    klog("warn", "Archivo de seguimiento de backup corrupto.")
        else:
            klog("info", "No se detecta snapshot de respaldo.")
            klog("info", "esta disponible la opción de exportar/importar marcadores desde la interfaz web.")

    load_dotenv(ENV_PATH)
    app.secret_key = os.environ.get("SECRET_KEY")

    if not es_reloader:
        contrasena_ya_mostrada = os.environ.get("CONTRASENA_MOSTRADA", "false").lower() == "true"
        if os.environ.get("APP_PASSWORD") == "cambiame" and not contrasena_ya_mostrada:
            print("\n" + "!" * 65)
            print(" [!] ALERTA CRÍTICA: Credencial de fábrica activa")
            print(" [i] SU CONTRASEÑA DE INICIO DE SESIÓN ES: cambiame")
            print(" [i] Se recomienda cambiarla inmediatamente para evitar accesos no autorizados.")
            print(" [i] puede usar uno de los siguientes métodos para cambiarla:")
            print("     1. desde la interfaz web")
            print("     2. desde una terminal ejecutando: python CLI_admin.py")
            print("     3. editando el archivo .env y reiniciando el servidor")
            print(" [i] Este aviso no volverá a mostrarse en próximos arranques.")
            print("!" * 65)

            set_key(ENV_PATH, "CONTRASENA_MOSTRADA", "true")
            os.environ["CONTRASENA_MOSTRADA"] = "false"

        print("\n" + "-" * 65)
        print(" [i] CONSOLA ADMINISTRATIVA DISPONIBLE:")
        print("     Ejecuta en una segunda terminal: python CLI_admin.py")
        print("     Permite modificar las configuraciones críticas del sistema sin editar archivos manualmente.")
        print("-" * 65)

        print("\n" + "-" * 65)
        print(" [i] CONSOLA DE PRUEBAS:")
        print("     Comando: python CLI_Chaos.py")
        print(" [!] ADVERTENCIA: Esta consola solo se ejecuta en modo debug y con el servidor cerrado.")
        print("-" * 65)

    log_mode_activo = os.environ.get("LOG_MODE", "false").lower() == "true"
    if not log_mode_activo:
        logging.getLogger("werkzeug").setLevel(logging.ERROR)

    debug_mode = False if ES_EXE else (os.environ.get("FLASK_DEBUG", "false").lower() == "true")
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
            klog("info", f"Modo Debug: {debug_mode}")
            klog("ok", f"Servidor HTTP listo (Local):   http://127.0.0.1:{port}")
            klog("ok", f"Servidor HTTP listo (Red LAN): http://{ip_lan}:{port}")
            klog("info", f"Asseso global habilitado ahora puede acceder desde cualquier dispositivo en la misma red LAN.")
            klog("info", f"Asegúrese de que el puerto {port} esté abierto en su firewall para acceso LAN.")
        else:
            klog("info", f"Modo Debug: {debug_mode}")
            klog("ok", f"Servidor HTTP enrutado en http://{host}:{port}")
            klog("fail", f"Servidor HTTP (Red LAN): no disponible ")
            

        print("-" * 65)
        print(">>> DISPOSITIVO LISTO PARA ATENDER SOLICITUDES HTTP <<<")
        print("-" * 65 + "\n")
        print(">>> EL SERVIDOR ESTA OPERATIVO <<<")
        print("-" * 65 + "\n")

    if ES_EXE and not es_reloader:
        auto_abrir = os.environ.get("AUTO_ABRIR_NAVEGADOR", "true").lower() == "true"
        if auto_abrir:
            threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()

    app.run(
        host=host,
        port=port,
        debug=debug_mode,
        use_reloader=False if ES_EXE else True,
        extra_files=[ENV_PATH] if not ES_EXE else []
    )