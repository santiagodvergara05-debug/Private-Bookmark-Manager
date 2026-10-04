"""
==============================================================================
PBM PRIVATE BOOKMARK MANAGER - ENRUTADOR Y CONTROLADOR CENTRAL (ROUTES.PY)
==============================================================================
Controlador principal de peticiones HTTP para el sistema de marcadores (Gen 3).
Responsabilidades de arquitectura:
1. Control de accesos por sesión, interceptor perimetral y 401 JSON.
2. Desbloqueo administrativo temporal de 120s mediante MASTER_KEY criptográfica.
3. Rotación en caliente de SECRET_KEY en RAM para invalidación global de sesiones.
4. Telemetría de eventos en terminal formateada con paleta ANSI estilo Linux.
5. CRUD completo de carpetas y marcadores con metadatos y avance de lectura.
6. Reubicación masiva unificada (carpetas y marcadores) en una sola transacción.
7. Eliminación condicional/en cascada de carpetas con modal reactivo.
8. Extracción asíncrona de títulos remotos vía web scraping (BeautifulSoup).
9. Motor de importación y exportación dual (JSON nativo y HTML estándar Netscape).
10. Sincronización BYOC multidispositivo con cifrado E2EE (AES-256) y hashes SHA-256.
11. Diagnóstico de base de datos y métricas de almacenamiento.
==============================================================================
"""

import os
import sys
import io
import json
import time
import secrets
import shutil
import zipfile
import subprocess
import hashlib
from datetime import datetime
from functools import wraps

import requests
from bs4 import BeautifulSoup
from dotenv import set_key, dotenv_values
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    Response,
    jsonify,
    flash,
    current_app
)

# Módulos internos del sistema PBM
import database
import bookmarks_html
import sync_manager
from version import VERSION

# Instanciación del Blueprint central de marcadores
marcadores_bp = Blueprint("marcadores", __name__)


# ==============================================================================
# SECCIÓN 1: CONFIGURACIONES, CONSTANTES Y ESTADOS VOLÁTILES
# ==============================================================================
INICIO_SERVIDOR = secrets.token_hex(8)
DURACION_DESBLOQUEO = 120  # 2 minutos

RUTA_ENV = ".env"
RUTA_ULTIMO_BACKUP = "ultimo_backup.txt"
RUTA_ULTIMO_SYNC = "ultimo_sync.txt"

# Constantes del contenedor de sincronización BYOC
VAULT_ZIP_NAME = "pbm_vault.zip"
VAULT_META_NAME = "pbm_vault.meta"
VAULT_PREV_NAME = "pbm_vault.prev.zip"
VAULT_TMP_NAME = "pbm_vault.zip.tmp"


# ==============================================================================
# SECCIÓN 2: MOTOR DE AUDITORÍA, TELEMETRÍA Y LOGGING ANSI EN TERMINAL
# ==============================================================================
CLR_RESET    = "\033[0m"
CLR_GRIS     = "\033[90m"
CLR_AZUL     = "\033[94m"
CLR_CYAN     = "\033[96m"
CLR_VERDE    = "\033[92m"
CLR_AMARILLO = "\033[93m"
CLR_ROJO     = "\033[91m"
CLR_MAGENTA  = "\033[95m"
CLR_BOLD     = "\033[1m"

def registrar_log(accion, tipo=None):
    """
    Emite trazas de auditoría en la consola con marcas de tiempo e insignias
    coloreadas según la criticidad de la operación. Respeta el interruptor LOG_MODE.
    """
    if os.environ.get("LOG_MODE", "false").strip().lower() != "true":
        return

    hora = datetime.now().strftime("%H:%M:%S")
    accion_lower = accion.lower()

    if tipo == "ERROR" or (tipo is None and any(k in accion_lower for k in ["error", "fallid", "rechazad", "bloquead", "no autorizad", "peligro", "corrupto"])):
        badge = f"{CLR_BOLD}{CLR_ROJO}✖ [PBM :: ALERTA]{CLR_RESET}"
        texto_formateado = f"{CLR_ROJO}{accion}{CLR_RESET}"
    elif tipo == "WARN" or (tipo is None and any(k in accion_lower for k in ["advertencia", "aviso", "conflicto", "ignorado", "pendiente"])):
        badge = f"{CLR_BOLD}{CLR_AMARILLO}⚠ [PBM :: WARN]{CLR_RESET}"
        texto_formateado = f"{CLR_AMARILLO}{accion}{CLR_RESET}"
    elif tipo == "SUCCESS" or (tipo is None and any(k in accion_lower for k in ["éxito", "exitos", "cread", "guardad", "actualizad", "importad", "iniciad", "movido", "restaurad"])):
        badge = f"{CLR_BOLD}{CLR_VERDE}✔ [PBM :: ÉXITO]{CLR_RESET}"
        texto_formateado = f"{CLR_VERDE}{accion}{CLR_RESET}"
    elif tipo == "DELETE" or (tipo is None and any(k in accion_lower for k in ["elimin", "borrad", "vaciad", "purgad"])):
        badge = f"{CLR_BOLD}{CLR_MAGENTA}🗑 [PBM :: DELETE]{CLR_RESET}"
        texto_formateado = f"{CLR_MAGENTA}{accion}{CLR_RESET}"
    elif tipo == "SYS" or (tipo is None and any(k in accion_lower for k in ["desbloque", "bloque", "sesión", "rotad", "crític", "backup", "sync"])):
        badge = f"{CLR_BOLD}{CLR_AMARILLO}⚡ [PBM :: SYS]{CLR_RESET}"
        texto_formateado = f"{CLR_AMARILLO}{accion}{CLR_RESET}"
    else:
        badge = f"{CLR_BOLD}{CLR_CYAN}ℹ [PBM :: INFO]{CLR_RESET}"
        texto_formateado = f"{CLR_CYAN}{accion}{CLR_RESET}"

    print(f"{CLR_GRIS}[{hora}]{CLR_RESET} {badge} {texto_formateado}")


# ==============================================================================
# SECCIÓN 3: CONTROL DE ACCESO, SESIÓN Y SEGURIDAD PERIMETRAL
# ==============================================================================
def esta_desbloqueado():
    """Valida si la sesión actual cuenta con autorización administrativa vigente."""
    if not session.get("desbloqueo_critico"):
        return False
    if session.get("desbloqueo_servidor") != INICIO_SERVIDOR:
        session.pop("desbloqueo_critico", None)
        return False
    if time.time() > session.get("desbloqueo_expira", 0):
        session.pop("desbloqueo_critico", None)
        return False
    return True


@marcadores_bp.before_request
def requerir_login():
    """Interceptor de seguridad perimetral."""
    if request.endpoint in ["marcadores.login", "static"]:
        return

    if not session.get("autenticado"):
        if request.method in ["POST", "PUT", "DELETE"]:
            ip = request.remote_addr
            registrar_log(f"Intento de llamada {request.method} sin sesión a '{request.path}' desde IP: {ip}", "ERROR")
            if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"ok": False, "error": "Sesión no válida o expirada."}), 401

        return redirect(url_for("marcadores.login"))


# ==============================================================================
# SECCIÓN 4: INTEGRIDAD CRIPTOGRÁFICA Y UTILIDADES DEL SISTEMA OPERATIVO
# ==============================================================================
def formatear_tamano(bytes_cant):
    """Convierte bytes a formato legible (B, KB, MB)."""
    if bytes_cant < 1024:
        return f"{bytes_cant} B"
    elif bytes_cant < 1024 * 1024:
        return f"{bytes_cant / 1024:.1f} KB"
    else:
        return f"{bytes_cant / (1024 * 1024):.2f} MB"


def calcular_sha256_archivo(ruta):
    """Calcula el hash SHA-256 de un archivo en disco de forma segura."""
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


def verificar_integridad_zip_remoto(ruta_zip, meta_dict):
    """Valida la integridad estructural de un archivo ZIP y su coincidencia con la firma SHA-256."""
    if not os.path.exists(ruta_zip) or os.path.getsize(ruta_zip) == 0:
        return False

    if not zipfile.is_zipfile(ruta_zip):
        return False

    if meta_dict:
        hash_esperado = (
            meta_dict.get("hash_zip")
            or meta_dict.get("sha256")
            or meta_dict.get("hash_sha256")
            or meta_dict.get("hash")
            or meta_dict.get("checksum")
        )
        if hash_esperado:
            hash_calculado = calcular_sha256_archivo(ruta_zip)
            if hash_calculado != hash_esperado:
                return False

    return True


def seleccionar_carpeta_nativa():
    """Abre el explorador de directorios nativo del sistema operativo de forma resiliente."""
    if sys.platform == "win32":
        try:
            ps_script = (
                "[System.Reflection.Assembly]::LoadWithPartialName('System.windows.forms') | Out-Null; "
                "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
                "$f.Description = 'Selecciona la carpeta base de tu Nube (MEGA, Drive, OneDrive, Pendrive...)'; "
                "$f.ShowNewFolderButton = $true; "
                "if ($f.ShowDialog() -eq 'OK') { Write-Output $f.SelectedPath }"
            )
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
            salida = res.stdout.strip()
            if salida and os.path.isdir(salida):
                return os.path.normpath(salida)
        except Exception:
            pass

    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        ruta = filedialog.askdirectory(title="Selecciona la carpeta base de tu Nube")
        root.destroy()
        if ruta and os.path.isdir(ruta):
            return os.path.normpath(ruta)
    except Exception:
        pass

    if sys.platform.startswith("linux"):
        try:
            res = subprocess.run(["zenity", "--file-selection", "--directory", "--title=Selecciona la carpeta de tu Nube"], capture_output=True, text=True)
            salida = res.stdout.strip()
            if salida and os.path.isdir(salida):
                return os.path.normpath(salida)
        except Exception:
            pass

    return None


# ==============================================================================
# SECCIÓN 5: PROCESADOR DE CONTEXTO GLOBAL (DETECCIÓN INTELIGENTE DE SYNC)
# ==============================================================================
@marcadores_bp.app_context_processor
def inyectar_avisos():
    """
    Inyecta parámetros globales de estado, preferencias del .env y telemetría
    de sincronización en todas las vistas HTML sin carteles residuales.
    """
    desbloqueado = esta_desbloqueado()
    segundos_restantes = max(0, int(session.get("desbloqueo_expira", 0) - time.time())) if desbloqueado else 0

    sync_hab = os.environ.get("SYNC_HABILITADO", "false").strip().lower() == "true"
    sync_carp = os.environ.get("SYNC_CARPETA", "").strip()
    cambios_pendientes_sync = False
    motivo_sync = ""

    if sync_hab and sync_carp and os.path.isdir(sync_carp):
        ultimo_sync_ts = 0.0
        if os.path.exists(RUTA_ULTIMO_SYNC):
            try:
                with open(RUTA_ULTIMO_SYNC, "r", encoding="utf-8") as f:
                    ultimo_sync_ts = float(f.read().strip())
            except Exception:
                ultimo_sync_ts = 0.0

        # 1. ¿Modificaciones locales en marcadores.db posteriores al último sync?
        db_path = getattr(database, "DB_PATH", "marcadores.db")
        if os.path.exists(db_path):
            db_mtime = os.path.getmtime(db_path)
            if db_mtime > (ultimo_sync_ts + 1.5):
                cambios_pendientes_sync = True
                motivo_sync = "local_modificado"

        # 2. ¿Revisión remota en la nube superior a la local?
        try:
            meta_remoto = sync_manager.leer_metadatos_remotos(sync_carp)
            if meta_remoto:
                rev_remota = int(meta_remoto.get("revision", 0))
                rev_local = int(os.environ.get("SYNC_ULTIMA_REVISION", "0").strip())
                if rev_remota > rev_local:
                    cambios_pendientes_sync = True
                    motivo_sync = "nube_nueva"
        except Exception:
            pass

    return {
        "app_version": VERSION,
        "mostrar_favicons": os.environ.get("MOSTRAR_FAVICONS", "true").strip().lower() == "true",
        "desbloqueo_critico_activo": desbloqueado,
        "desbloqueo_segundos_restantes": segundos_restantes,
        "abrir_nueva_pestana": os.environ.get("ABRIR_NUEVA_PESTANA", "true").strip().lower() == "true",
        "modo_oscuro": os.environ.get("MODO_OSCURO", "false").strip().lower() == "true",
        "sync_hab": sync_hab,
        "sync_carpeta": sync_carp,
        "sync_pendiente": cambios_pendientes_sync,
        "sync_motivo": motivo_sync
    }


# ==============================================================================
# SECCIÓN 6: AUTENTICACIÓN Y SESIONES
# ==============================================================================
@marcadores_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("autenticado"):
        return redirect(url_for("marcadores.home"))

    mostrar_contrasena_inicial = os.environ.get("CONTRASENA_MOSTRADA", "false").strip().lower() != "true"
    app_pwd = os.environ.get("APP_PASSWORD", "cambiame").strip()
    master_key = os.environ.get("MASTER_KEY", "").strip()

    if request.method == "POST":
        pwd_ingresada = request.form.get("password", "").strip()

        if pwd_ingresada and (pwd_ingresada == app_pwd or (master_key and pwd_ingresada == master_key)):
            session["autenticado"] = True
            session.permanent = True
            session["intentos_fallidos"] = 0
            registrar_log(f"Inicio de sesión exitoso desde IP: {request.remote_addr}", "SUCCESS")

            if mostrar_contrasena_inicial:
                set_key(RUTA_ENV, "CONTRASENA_MOSTRADA", "true")
                os.environ["CONTRASENA_MOSTRADA"] = "true"
                registrar_log("Primer acceso: aviso de credenciales ocultado permanentemente", "SYS")

            return redirect(url_for("marcadores.home"))

        session["intentos_fallidos"] = session.get("intentos_fallidos", 0) + 1
        intentos = session["intentos_fallidos"]
        registrar_log(f"Credencial incorrecta desde {request.remote_addr} (intento #{intentos})", "ERROR")

        return render_template(
            "login.html",
            error="Contraseña incorrecta",
            mostrar_ayuda=intentos >= 3,
            mostrar_contrasena_inicial=mostrar_contrasena_inicial,
            app_password_actual=app_pwd,
            master_key_actual=master_key
        )

    return render_template(
        "login.html",
        error=None,
        mostrar_ayuda=False,
        mostrar_contrasena_inicial=mostrar_contrasena_inicial,
        app_password_actual=app_pwd,
        master_key_actual=master_key
    )


@marcadores_bp.route("/logout")
def logout():
    session.clear()
    registrar_log("Cierre de sesión manual ejecutado", "SYS")
    return redirect(url_for("marcadores.login"))


# ==============================================================================
# SECCIÓN 7: VISTAS Y NAVEGACIÓN DE DIRECTORIOS
# ==============================================================================
def ver_carpeta(carpeta_id):
    carpeta_actual = database.obtener_carpeta(carpeta_id)
    subcarpetas = database.obtener_subcarpetas(carpeta_id)
    marcadores = database.obtener_marcadores(carpeta_id)
    todas_las_carpetas = database.obtener_todas_las_carpetas()

    nombre_seccion = carpeta_actual["nombre"] if carpeta_actual else "Raíz (Mis Marcadores)"
    registrar_log(f"Catálogo explorado: {nombre_seccion} ({len(subcarpetas)} carpetas, {len(marcadores)} marcadores)", "INFO")

    return render_template(
        "index.html",
        carpeta_actual=carpeta_actual,
        subcarpetas=subcarpetas,
        marcadores=marcadores,
        todas_las_carpetas=todas_las_carpetas
    )


@marcadores_bp.route("/")
def home():
    return ver_carpeta(None)


@marcadores_bp.route("/carpeta/<int:carpeta_id>")
def ver_carpeta_ruta(carpeta_id):
    return ver_carpeta(carpeta_id)


# ==============================================================================
# SECCIÓN 8: GESTIÓN DE MARCADORES (CRUD & PROGRESO)
# ==============================================================================
def obtener_titulo_desde_url(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        respuesta = requests.get(url, timeout=5, headers=headers)
        if respuesta.status_code == 200:
            sopa = BeautifulSoup(respuesta.text, "html.parser")
            if sopa.title and sopa.title.string:
                return sopa.title.string.strip()
    except Exception as e:
        registrar_log(f"Fallo al autocompletar título para {url}: {e}", "WARN")
    return None


@marcadores_bp.route("/agregar", methods=["POST"])
def agregar():
    carpeta_id = request.form.get("carpeta_id") or None
    url = request.form.get("url", "").strip()
    titulo = request.form.get("titulo", "").strip()
    nota = request.form.get("nota", "").strip() or None

    try:
        progreso = max(0, int(request.form.get("progreso", 0)))
    except ValueError:
        progreso = 0

    if not titulo and request.form.get("autocompletar"):
        titulo = obtener_titulo_desde_url(url) or url
    if not titulo:
        titulo = url

    database.agregar_marcador(titulo, url, carpeta_id, nota, progreso)
    registrar_log(f"Marcador guardado: '{titulo}' ({url})", "SUCCESS")
    return redirect(request.referrer or url_for("marcadores.home"))


@marcadores_bp.route("/editar/<int:id_marcador>", methods=["GET", "POST"])
def editar(id_marcador):
    if request.method == "POST":
        nueva_carpeta_id = request.form.get("carpeta_id") or None
        nota = request.form.get("nota", "").strip() or None
        titulo = request.form.get("titulo", "").strip() or "Sin título"
        url = request.form.get("url", "").strip()

        try:
            progreso = max(0, int(request.form.get("progreso", 0)))
        except ValueError:
            progreso = 0

        database.editar_marcador(id_marcador, titulo, url, nueva_carpeta_id, nota, progreso)
        registrar_log(f"Marcador editado [ID: {id_marcador}]: '{titulo}'", "SUCCESS")

        if nueva_carpeta_id:
            return redirect(url_for("marcadores.ver_carpeta_ruta", carpeta_id=nueva_carpeta_id))
        return redirect(url_for("marcadores.home"))

    marcador = database.obtener_marcador(id_marcador)
    if not marcador:
        registrar_log(f"Intento de editar marcador inexistente [ID: {id_marcador}]", "ERROR")
        return redirect(url_for("marcadores.home"))

    todas_las_carpetas = database.obtener_todas_las_carpetas()
    return render_template("editar.html", marcador=marcador, todas_las_carpetas=todas_las_carpetas)


@marcadores_bp.route("/mover/<int:id_marcador>", methods=["POST"])
def mover(id_marcador):
    nueva_carpeta_id = request.form.get("nueva_carpeta_id") or None
    database.mover_marcador(id_marcador, nueva_carpeta_id)
    registrar_log(f"Marcador [ID: {id_marcador}] movido a carpeta {nueva_carpeta_id or 'Raíz'}", "SUCCESS")
    return redirect(request.referrer or url_for("marcadores.home"))


@marcadores_bp.route("/eliminar/<int:id_marcador>", methods=["GET", "POST", "DELETE"])
def eliminar(id_marcador):
    marcador = database.obtener_marcador(id_marcador)
    nombre = marcador["titulo"] if marcador else f"ID #{id_marcador}"
    database.eliminar_marcador(id_marcador)
    registrar_log(f"Marcador eliminado: '{nombre}' [ID: {id_marcador}]", "DELETE")
    return redirect(request.referrer or url_for("marcadores.home"))


@marcadores_bp.route("/progreso/<int:id_marcador>/<accion>", methods=["POST"])
def progreso(id_marcador, accion):
    if accion == "sumar":
        delta = 1
    elif accion == "restar":
        delta = -1
    else:
        return redirect(request.referrer or url_for("marcadores.home"))

    database.actualizar_progreso(id_marcador, delta)
    registrar_log(f"Progreso ajustado ({accion}) para marcador [ID: {id_marcador}]", "SUCCESS")
    return redirect(request.referrer or url_for("marcadores.home"))


# ==============================================================================
# SECCIÓN 9: GESTIÓN DE CARPETAS (CRUD & MODAL)
# ==============================================================================
@marcadores_bp.route("/crear_carpeta", methods=["POST"])
def crear_carpeta():
    carpeta_padre_id = request.form.get("carpeta_padre_id") or None
    nombre = request.form.get("nombre", "").strip() or "Nueva Carpeta"

    database.crear_carpeta(nombre, carpeta_padre_id)
    registrar_log(f"Carpeta creada con éxito: '{nombre}'", "SUCCESS")
    return redirect(request.referrer or url_for("marcadores.home"))


@marcadores_bp.route("/editar_carpeta/<int:carpeta_id>", methods=["GET", "POST"])
def editar_carpeta(carpeta_id):
    if request.method == "POST":
        nombre_nuevo = request.form.get("nombre", "").strip() or "Carpeta sin nombre"
        nueva_padre = request.form.get("carpeta_padre_id")

        if nueva_padre in ["", "null", "raiz", "0", None]:
            nueva_padre_id = None
        else:
            try:
                nueva_padre_id = int(nueva_padre)
            except ValueError:
                nueva_padre_id = None

        database.editar_carpeta(carpeta_id, nombre_nuevo, nueva_padre_id)
        registrar_log(f"Carpeta actualizada [ID: {carpeta_id}]: '{nombre_nuevo}'", "SUCCESS")

        carpeta = database.obtener_carpeta(carpeta_id)
        if carpeta and carpeta["carpeta_padre_id"]:
            return redirect(url_for("marcadores.ver_carpeta_ruta", carpeta_id=carpeta["carpeta_padre_id"]))
        return redirect(url_for("marcadores.home"))

    carpeta = database.obtener_carpeta(carpeta_id)
    if not carpeta:
        return redirect(url_for("marcadores.home"))

    todas_las_carpetas = database.obtener_todas_las_carpetas()
    return render_template("editar_carpeta.html", carpeta=carpeta, todas_las_carpetas=todas_las_carpetas)


@marcadores_bp.route("/carpeta/<int:carpeta_id>/conteo")
def conteo_carpeta(carpeta_id):
    total = database.contar_contenido_carpeta(carpeta_id)
    return jsonify({"ok": True, "carpeta_id": carpeta_id, "total": total})


@marcadores_bp.route("/eliminar_carpeta/<int:carpeta_id>", methods=["GET", "POST"])
def eliminar_carpeta(carpeta_id):
    borrar_contenido = False
    if request.method == "POST":
        borrar_contenido = request.form.get("borrar_contenido") in ["true", "1", "on"]

    carpeta = database.obtener_carpeta(carpeta_id)
    nombre_carpeta = carpeta["nombre"] if carpeta else f"ID #{carpeta_id}"

    database.eliminar_carpeta(carpeta_id, borrar_contenido=borrar_contenido)

    modo_desc = "y sus marcadores internos fueron eliminados" if borrar_contenido else "y sus marcadores fueron preservados en la raíz"
    registrar_log(f"Carpeta '{nombre_carpeta}' eliminada ({modo_desc})", "DELETE")

    return redirect(request.referrer or url_for("marcadores.home"))


# ==============================================================================
# SECCIÓN 10: ACCIONES EN LOTE (BATCH MOVE & DELETE)
# ==============================================================================
@marcadores_bp.route("/mover_masivo", methods=["POST"])
def mover_masivo():
    nueva_carpeta_id = request.form.get("nueva_carpeta_id")
    if nueva_carpeta_id in ["", "null", "raiz", "0"]:
        nueva_carpeta_id = None
    elif nueva_carpeta_id is not None:
        try:
            nueva_carpeta_id = int(nueva_carpeta_id)
        except ValueError:
            nueva_carpeta_id = None

    ids_marcadores = request.form.getlist("ids_marcadores")
    ids_carpetas = request.form.getlist("ids_carpetas")

    if not ids_marcadores and not ids_carpetas and request.is_json:
        payload = request.get_json() or {}
        ids_marcadores = payload.get("ids_marcadores", [])
        ids_carpetas = payload.get("ids_carpetas", [])
        if "nueva_carpeta_id" in payload:
            raw_id = payload.get("nueva_carpeta_id")
            nueva_carpeta_id = int(raw_id) if raw_id and str(raw_id).isdigit() else None

    if not ids_marcadores and not ids_carpetas:
        if request.is_json:
            return jsonify({"ok": False, "error": "No se seleccionaron elementos."}), 400
        return redirect(request.referrer or url_for("marcadores.home"))

    movidos_m = database.mover_marcadores_lote(ids_marcadores, nueva_carpeta_id)
    movidas_c = database.mover_carpetas_lote(ids_carpetas, nueva_carpeta_id)

    destino_nombre = "Raíz (Sin carpeta)"
    if nueva_carpeta_id:
        carpeta_dest = database.obtener_carpeta(nueva_carpeta_id)
        if carpeta_dest:
            destino_nombre = f"'{carpeta_dest['nombre']}'"

    registrar_log(f"Lote procesado: {movidos_m} marcadores y {movidas_c} carpetas trasladadas a {destino_nombre}", "SUCCESS")

    if request.is_json:
        return jsonify({
            "ok": True,
            "movidos_marcadores": movidos_m,
            "movidas_carpetas": movidas_c,
            "destino": destino_nombre
        })

    return redirect(request.referrer or url_for("marcadores.home"))


@marcadores_bp.route("/eliminar_masivo", methods=["POST"])
def eliminar_masivo():
    ids_marcadores = request.form.getlist("ids_marcadores")

    if not ids_marcadores:
        return redirect(request.referrer or url_for("marcadores.home"))

    total_eliminados = database.eliminar_marcadores_lote(ids_marcadores)
    registrar_log(f"Lote eliminado: {total_eliminados} marcadores borrados permanentemente", "DELETE")

    return redirect(request.referrer or url_for("marcadores.home"))


# ==============================================================================
# SECCIÓN 11: BÚSQUEDA Y VISTA GLOBAL
# ==============================================================================
@marcadores_bp.route("/buscar")
def buscar():
    texto = request.args.get("q", "").strip()
    resultados = database.buscar_marcadores(texto) if texto else []
    if texto:
        registrar_log(f"Búsqueda ejecutada: '{texto}' ({len(resultados)} coincidencias)", "INFO")
    return render_template("buscar.html", texto=texto, resultados=resultados)


@marcadores_bp.route("/todos")
def todos():
    marcadores = database.obtener_todos_los_marcadores()
    todas_las_carpetas = database.obtener_todas_las_carpetas()

    agrupados = {}
    for m in marcadores:
        nombre_grupo = m["carpeta_nombre"] if m["carpeta_nombre"] else "Sin carpeta"
        agrupados.setdefault(nombre_grupo, []).append(m)

    return render_template("todos.html", agrupados=agrupados, todas_las_carpetas=todas_las_carpetas)


# ==============================================================================
# SECCIÓN 12: EXPORTACIÓN E IMPORTACIÓN MANUAL
# ==============================================================================
@marcadores_bp.route("/exportar")
def exportar():
    carpetas = database.obtener_todas_las_carpetas()
    marcadores = database.obtener_todos_los_marcadores()

    datos = {
        "metadata": {
            "sistema": "PrivateBookmarkManager",
            "version": VERSION,
            "exportado_en": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        "carpetas": [dict(c) for c in carpetas],
        "marcadores": [dict(m) for m in marcadores]
    }

    with open(RUTA_ULTIMO_BACKUP, "w", encoding="utf-8") as f:
        f.write(str(time.time()))

    contenido = json.dumps(datos, indent=2, ensure_ascii=False)
    registrar_log(f"Exportación JSON completada ({len(carpetas)} carpetas, {len(marcadores)} marcadores)", "SUCCESS")
    return Response(
        contenido,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=backup_marcadores.json"}
    )


@marcadores_bp.route("/importar", methods=["POST"])
def importar():
    if "archivo" not in request.files:
        return redirect(url_for("marcadores.home"))

    archivo = request.files["archivo"]
    if not archivo or archivo.filename == "":
        return redirect(url_for("marcadores.home"))

    if not archivo.filename.lower().endswith(".json"):
        return redirect(url_for("marcadores.home"))

    try:
        datos = json.load(archivo)
        carpetas = datos.get("carpetas", [])
        marcadores = datos.get("marcadores", [])
        database.importar_datos(carpetas, marcadores)
        registrar_log(f"Importación JSON completada ({len(carpetas)} carpetas, {len(marcadores)} marcadores)", "SUCCESS")
    except Exception as e:
        registrar_log(f"Error procesando archivo JSON: {e}", "ERROR")

    return redirect(url_for("marcadores.home"))


@marcadores_bp.route("/exportar_html")
def exportar_html_ruta():
    carpetas = database.obtener_todas_las_carpetas()
    marcadores = database.obtener_todos_los_marcadores()
    contenido = bookmarks_html.exportar_html(
        [dict(c) for c in carpetas], [dict(m) for m in marcadores]
    )
    registrar_log(f"Exportación HTML Netscape completada ({len(marcadores)} enlaces)", "SUCCESS")
    return Response(
        contenido,
        mimetype="text/html",
        headers={"Content-Disposition": "attachment; filename=backup_marcadores.html"}
    )


@marcadores_bp.route("/importar_html", methods=["POST"])
def importar_html_ruta():
    if "archivo" not in request.files:
        return redirect(url_for("marcadores.home"))

    archivo = request.files["archivo"]
    if not archivo or archivo.filename == "":
        return redirect(url_for("marcadores.home"))

    if not (archivo.filename.lower().endswith(".html") or archivo.filename.lower().endswith(".htm")):
        return redirect(url_for("marcadores.home"))

    try:
        contenido = archivo.read().decode("utf-8", errors="ignore")
        carpetas_data, marcadores_data = bookmarks_html.importar_html(contenido)
        database.importar_datos(carpetas_data, marcadores_data)
        registrar_log(f"Importación HTML completada ({len(carpetas_data)} carpetas, {len(marcadores_data)} marcadores)", "SUCCESS")
    except Exception as e:
        registrar_log(f"Error procesando archivo HTML: {e}", "ERROR")

    return redirect(url_for("marcadores.home"))


# ==============================================================================
# SECCIÓN 13: CONFIGURACIÓN, DESBLOQUEO CRÍTICO Y ROTACIÓN DE CLAVE
# ==============================================================================
@marcadores_bp.route("/configuracion", methods=["GET", "POST"])
def configuracion():
    desbloqueado = esta_desbloqueado()
    segundos_restantes = max(0, int(session.get("desbloqueo_expira", 0) - time.time())) if desbloqueado else 0

    if request.method == "POST":
        hubo_cambios = False

        if desbloqueado:
            pass_anterior = os.environ.get("APP_PASSWORD", "cambiame").strip()
            nueva_password = request.form.get("password", "").strip() or request.form.get("app_password", "").strip()
            if nueva_password and nueva_password != pass_anterior:
                set_key(RUTA_ENV, "APP_PASSWORD", nueva_password)
                os.environ["APP_PASSWORD"] = nueva_password
                hubo_cambios = True
                registrar_log("Contraseña de acceso APP_PASSWORD actualizada", "SYS")

            host_anterior = os.environ.get("HOST", "127.0.0.1").strip()
            nuevo_host = request.form.get("host", "").strip()
            if nuevo_host in ["127.0.0.1", "0.0.0.0"] and nuevo_host != host_anterior:
                set_key(RUTA_ENV, "HOST", nuevo_host)
                os.environ["HOST"] = nuevo_host
                hubo_cambios = True

            port_anterior = os.environ.get("PORT", "5050").strip()
            nuevo_puerto = request.form.get("port", "").strip()
            if nuevo_puerto and nuevo_puerto != port_anterior:
                try:
                    p_num = int(nuevo_puerto)
                    if 1 <= p_num <= 65535:
                        set_key(RUTA_ENV, "PORT", str(p_num))
                        os.environ["PORT"] = str(p_num)
                        hubo_cambios = True
                except ValueError:
                    pass

            auto_abrir_ant = os.environ.get("AUTO_ABRIR_NAVEGADOR", "false").strip().lower()
            auto_abrir = "true" if "auto_abrir_navegador" in request.form else "false"
            if auto_abrir != auto_abrir_ant:
                set_key(RUTA_ENV, "AUTO_ABRIR_NAVEGADOR", auto_abrir)
                os.environ["AUTO_ABRIR_NAVEGADOR"] = auto_abrir
                hubo_cambios = True

            log_mode_ant = os.environ.get("LOG_MODE", "false").strip().lower()
            log_mode = "true" if "log_mode" in request.form else "false"
            if log_mode != log_mode_ant:
                set_key(RUTA_ENV, "LOG_MODE", log_mode)
                os.environ["LOG_MODE"] = log_mode
                hubo_cambios = True

            # Parámetros BYOC
            sync_hab_ant = os.environ.get("SYNC_HABILITADO", "false").strip().lower()
            sync_hab = "true" if "sync_habilitado" in request.form else "false"
            if sync_hab != sync_hab_ant:
                set_key(RUTA_ENV, "SYNC_HABILITADO", sync_hab)
                os.environ["SYNC_HABILITADO"] = sync_hab
                hubo_cambios = True

            sync_carp_ant = os.environ.get("SYNC_CARPETA", "").strip()
            sync_carp = request.form.get("sync_carpeta", "").strip()
            if sync_carp != sync_carp_ant:
                if sync_carp:
                    try:
                        os.makedirs(sync_carp, exist_ok=True)
                    except Exception:
                        pass
                set_key(RUTA_ENV, "SYNC_CARPETA", sync_carp)
                os.environ["SYNC_CARPETA"] = sync_carp
                hubo_cambios = True

            sync_modo_ant = os.environ.get("SYNC_MODO_CIFRADO", "auto").strip().lower()
            sync_modo = request.form.get("sync_modo_cifrado", "auto").strip().lower()
            if sync_modo in ["auto", "manual", "libre"] and sync_modo != sync_modo_ant:
                set_key(RUTA_ENV, "SYNC_MODO_CIFRADO", sync_modo)
                os.environ["SYNC_MODO_CIFRADO"] = sync_modo
                hubo_cambios = True

            sync_auto_ant = os.environ.get("SYNC_AUTO_APLICAR", "false").strip().lower()
            sync_auto = "true" if "sync_auto_aplicar" in request.form else "false"
            if sync_auto != sync_auto_ant:
                set_key(RUTA_ENV, "SYNC_AUTO_APLICAR", sync_auto)
                os.environ["SYNC_AUTO_APLICAR"] = sync_auto
                hubo_cambios = True

            sync_disp_ant = os.environ.get("SYNC_NOMBRE_DISPOSITIVO", "").strip()
            sync_disp = request.form.get("sync_nombre_dispositivo", "").strip()
            if sync_disp and sync_disp != sync_disp_ant:
                set_key(RUTA_ENV, "SYNC_NOMBRE_DISPOSITIVO", sync_disp)
                os.environ["SYNC_NOMBRE_DISPOSITIVO"] = sync_disp
                hubo_cambios = True

            clave_anterior = os.environ.get("SYNC_CLAVE", "").strip()
            nueva_clave = request.form.get("sync_clave", "").strip()
            clave_rotada = bool(nueva_clave and nueva_clave != clave_anterior)

            if clave_rotada:
                set_key(RUTA_ENV, "SYNC_CLAVE", nueva_clave)
                os.environ["SYNC_CLAVE"] = nueva_clave
                hubo_cambios = True

            rev_form = request.form.get("sync_ultima_revision", "").strip()
            rev_anterior = os.environ.get("SYNC_ULTIMA_REVISION", "0").strip()
            if rev_form.isdigit() and rev_form != rev_anterior:
                ruta_meta_f = os.path.join(sync_carp, VAULT_META_NAME) if sync_carp and os.path.isdir(sync_carp) else None
                existe_meta_fisico = bool(ruta_meta_f and os.path.exists(ruta_meta_f))
                meta_nube = sync_manager.leer_metadatos_remotos(sync_carp) if sync_carp and os.path.isdir(sync_carp) else None

                if not existe_meta_fisico and not meta_nube:
                    set_key(RUTA_ENV, "SYNC_ULTIMA_REVISION", rev_form)
                    os.environ["SYNC_ULTIMA_REVISION"] = rev_form
                    hubo_cambios = True

            # Si se rotó la clave en caliente desde el formulario principal
            if clave_rotada and sync_hab == "true" and sync_carp and os.path.isdir(sync_carp):
                for f_obs in [VAULT_ZIP_NAME, VAULT_META_NAME, VAULT_PREV_NAME, VAULT_TMP_NAME]:
                    r_obs = os.path.join(sync_carp, f_obs)
                    if os.path.exists(r_obs):
                        try:
                            os.remove(r_obs)
                        except Exception:
                            pass

                try:
                    rev_actual = int(os.environ.get("SYNC_ULTIMA_REVISION", "0").strip()) + 1
                except ValueError:
                    rev_actual = 1

                db_path = getattr(database, "DB_PATH", "marcadores.db")
                clave_empaque = "" if sync_modo == "libre" else nueva_clave

                exito, msg = sync_manager.exportar_boveda_cifrada(
                    carpeta_sync=sync_carp,
                    ruta_db=db_path,
                    clave_sync=clave_empaque,
                    nombre_equipo=sync_disp or "Dispositivo PBM",
                    revision_actual=rev_actual
                )
                if exito:
                    set_key(RUTA_ENV, "SYNC_ULTIMA_REVISION", str(rev_actual))
                    os.environ["SYNC_ULTIMA_REVISION"] = str(rev_actual)
                    flash(f"🔑 Clave guardada con éxito. Bóveda regenerada con el nuevo cifrado (Revisión #{rev_actual}).", "success")

        # Preferencias de usuario
        favicons_ant = os.environ.get("MOSTRAR_FAVICONS", "true").strip().lower()
        mostrar_favicons = "true" if "mostrar_favicons" in request.form else "false"
        if mostrar_favicons != favicons_ant:
            set_key(RUTA_ENV, "MOSTRAR_FAVICONS", mostrar_favicons)
            os.environ["MOSTRAR_FAVICONS"] = mostrar_favicons
            hubo_cambios = True

        pestana_ant = os.environ.get("ABRIR_NUEVA_PESTANA", "true").strip().lower()
        abrir_nueva_pestana = "true" if "abrir_nueva_pestana" in request.form else "false"
        if abrir_nueva_pestana != pestana_ant:
            set_key(RUTA_ENV, "ABRIR_NUEVA_PESTANA", abrir_nueva_pestana)
            os.environ["ABRIR_NUEVA_PESTANA"] = abrir_nueva_pestana
            hubo_cambios = True

        oscuro_ant = os.environ.get("MODO_OSCURO", "false").strip().lower()
        modo_oscuro = "true" if "modo_oscuro" in request.form else "false"
        if modo_oscuro != oscuro_ant:
            set_key(RUTA_ENV, "MODO_OSCURO", modo_oscuro)
            os.environ["MODO_OSCURO"] = modo_oscuro
            hubo_cambios = True

        if hubo_cambios:
            registrar_log("Ajustes del servidor y preferencias guardadas en .env", "SYS")

        return redirect(url_for("marcadores.configuracion", guardado=1))

    # Métricas y estado para la UI
    total_carpetas = 0
    total_marcadores = 0
    peso_db = "0 KB"

    db_path = getattr(database, "DB_PATH", "marcadores.db")
    if os.path.exists(db_path):
        try:
            peso_db = formatear_tamano(os.path.getsize(db_path))
            total_carpetas = len(database.obtener_todas_las_carpetas())
            total_marcadores = len(database.obtener_todos_los_marcadores())
        except Exception:
            pass

    sync_hab_val = os.environ.get("SYNC_HABILITADO", "false").strip().lower() == "true"
    sync_carp_val = os.environ.get("SYNC_CARPETA", "").strip()

    try:
        rev_local = int(os.environ.get("SYNC_ULTIMA_REVISION", "0").strip())
    except ValueError:
        rev_local = 0

    meta_remoto = None
    rev_remota = 0
    estado_sync = "desactivado"

    if sync_hab_val and sync_carp_val and os.path.isdir(sync_carp_val):
        ruta_meta_fisica = os.path.join(sync_carp_val, VAULT_META_NAME)
        ruta_zip_fisica = os.path.join(sync_carp_val, VAULT_ZIP_NAME)
        meta_remoto = sync_manager.leer_metadatos_remotos(sync_carp_val)

        if os.path.exists(ruta_meta_fisica) and not meta_remoto:
            estado_sync = "meta_corrupto"
        elif meta_remoto:
            rev_remota = int(meta_remoto.get("revision", 0))
            zip_valido = verificar_integridad_zip_remoto(ruta_zip_fisica, meta_remoto)

            if rev_remota > rev_local:
                estado_sync = "pendiente_descarga" if zip_valido else "zip_corrupto"
            elif rev_remota < rev_local:
                estado_sync = "adelantado_local"
            else:
                estado_sync = "al_dia" if zip_valido else "zip_corrupto"
        else:
            estado_sync = "sin_boveda_remota"
    elif sync_hab_val:
        estado_sync = "carpeta_invalida"

    valores_env = dict(dotenv_values(RUTA_ENV)) if os.path.exists(RUTA_ENV) else {}

    return render_template(
        "configuracion.html",
        valores=valores_env,
        guardado=request.args.get("guardado"),
        error_master=request.args.get("error_master"),
        desbloqueo_critico_activo=desbloqueado,
        desbloqueo_segundos_restantes=segundos_restantes,
        total_carpetas=total_carpetas,
        total_marcadores=total_marcadores,
        peso_db=peso_db,
        rev_local=rev_local,
        rev_remota=rev_remota,
        meta_remoto=meta_remoto,
        estado_sync=estado_sync
    )


@marcadores_bp.route("/configuracion/sync/rotar_clave", methods=["POST"])
def sync_rotar_clave():
    """Genera atómicamente una nueva clave de 256 bits y re-cifra la bóveda en la nube."""
    if not esta_desbloqueado():
        flash("La configuración crítica se encuentra bloqueada. Use la Master Key para desbloquearla.", "error")
        return redirect(url_for("marcadores.configuracion"))

    nueva_clave = secrets.token_hex(32)
    set_key(RUTA_ENV, "SYNC_CLAVE", nueva_clave)
    os.environ["SYNC_CLAVE"] = nueva_clave
    registrar_log("Rotación de SYNC_CLAVE generada (256 bits)", "SYS")

    sync_hab = os.environ.get("SYNC_HABILITADO", "false").strip().lower() == "true"
    sync_carp = os.environ.get("SYNC_CARPETA", "").strip()
    sync_modo = os.environ.get("SYNC_MODO_CIFRADO", "auto").strip().lower()
    sync_disp = os.environ.get("SYNC_NOMBRE_DISPOSITIVO", "Dispositivo PBM").strip()

    if sync_hab and sync_carp and os.path.isdir(sync_carp):
        registrar_log(f"Purgando bóvedas obsoletas en nube: {sync_carp}", "DELETE")
        for f_obs in [VAULT_ZIP_NAME, VAULT_META_NAME, VAULT_PREV_NAME, VAULT_TMP_NAME]:
            r_obs = os.path.join(sync_carp, f_obs)
            if os.path.exists(r_obs):
                try:
                    os.remove(r_obs)
                except Exception:
                    pass

        try:
            rev_actual = int(os.environ.get("SYNC_ULTIMA_REVISION", "0").strip()) + 1
        except ValueError:
            rev_actual = 1

        db_path = getattr(database, "DB_PATH", "marcadores.db")
        clave_empaque = "" if sync_modo == "libre" else nueva_clave

        exito, msg = sync_manager.exportar_boveda_cifrada(
            carpeta_sync=sync_carp,
            ruta_db=db_path,
            clave_sync=clave_empaque,
            nombre_equipo=sync_disp,
            revision_actual=rev_actual
        )

        if exito:
            with open(RUTA_ULTIMO_SYNC, "w", encoding="utf-8") as f:
                f.write(str(time.time()))
            set_key(RUTA_ENV, "SYNC_ULTIMA_REVISION", str(rev_actual))
            os.environ["SYNC_ULTIMA_REVISION"] = str(rev_actual)
            registrar_log(f"Bóveda re-cifrada y publicada con éxito (Revisión #{rev_actual})", "SUCCESS")
            flash(f"🔑 Clave rotada con éxito (256 bits). La bóveda remota anterior fue eliminada y regenerada con el nuevo cifrado (Revisión #{rev_actual}). Copia la nueva clave en tus otros equipos.", "success")
        else:
            registrar_log(f"Fallo al re-cifrar la bóveda con la nueva clave: {msg}", "ERROR")
            flash(f"⚠ La clave se rotó pero falló el empaquetado en la nube: {msg}", "error")
    else:
        flash("🔑 Nueva clave criptográfica generada con éxito (256 bits) en almacenamiento local.", "success")

    return redirect(url_for("marcadores.configuracion"))


@marcadores_bp.route("/configuracion/desbloquear", methods=["POST"])
def desbloquear_critico():
    clave_ingresada = request.form.get("master_key", "").strip()
    master_key_actual = os.environ.get("MASTER_KEY", "").strip()

    if clave_ingresada and clave_ingresada == master_key_actual:
        session["desbloqueo_critico"] = True
        session["desbloqueo_expira"] = time.time() + DURACION_DESBLOQUEO
        session["desbloqueo_servidor"] = INICIO_SERVIDOR
        registrar_log("Configuración crítica desbloqueada por 2 minutos con Master Key", "SYS")
        return redirect(url_for("marcadores.configuracion"))

    registrar_log(f"Intento fallido de desbloqueo crítico desde IP: {request.remote_addr}", "ERROR")
    return redirect(url_for("marcadores.configuracion", error_master=1))


@marcadores_bp.route("/configuracion/bloquear", methods=["POST"])
def bloquear_critico():
    session.pop("desbloqueo_critico", None)
    registrar_log("Configuración crítica bloqueada manualmente", "SYS")
    return redirect(url_for("marcadores.configuracion"))


@marcadores_bp.route("/configuracion/cerrar_sesiones", methods=["POST"])
def cerrar_sesiones_globales():
    nueva_key = secrets.token_hex(32)
    set_key(RUTA_ENV, "SECRET_KEY", nueva_key)
    os.environ["SECRET_KEY"] = nueva_key
    current_app.secret_key = nueva_key

    registrar_log("Cierre global: SECRET_KEY rotada en memoria y persistida en .env", "SYS")
    session.clear()
    return redirect(url_for("marcadores.login"))


@marcadores_bp.route("/configuracion/borrar_todo", methods=["POST"])
def borrar_todo_ruta():
    if not esta_desbloqueado():
        registrar_log("Intento no autorizado de vaciado de base de datos sin desbloqueo", "ERROR")
        return redirect(url_for("marcadores.configuracion"))

    database.borrar_todo()
    registrar_log("Vaciado integral de la base de datos de marcadores completado", "DELETE")
    return redirect(url_for("marcadores.configuracion", guardado=1))


# ==============================================================================
# SECCIÓN 14: SINCRONIZACIÓN BYOC (E2EE AES-256)
# ==============================================================================
@marcadores_bp.route("/configuracion/sync/subir", methods=["POST"])
def sync_subir_boveda():
    carpeta_sync = os.environ.get("SYNC_CARPETA", "").strip()
    if not carpeta_sync or not os.path.isdir(carpeta_sync):
        flash("La carpeta de sincronización no está configurada o no es accesible.", "error")
        return redirect(url_for("marcadores.configuracion"))

    ruta_meta_fisica = os.path.join(carpeta_sync, VAULT_META_NAME)
    meta_remoto = sync_manager.leer_metadatos_remotos(carpeta_sync)

    if os.path.exists(ruta_meta_fisica) and not meta_remoto:
        registrar_log(f"Subida bloqueada: '{VAULT_META_NAME}' corrupto en la nube", "ERROR")
        flash("⛔ Subida bloqueada: Se detectó un archivo de metadatos corrupto en la nube.", "error")
        return redirect(url_for("marcadores.configuracion"))

    try:
        rev_local = int(os.environ.get("SYNC_ULTIMA_REVISION", "0").strip())
    except ValueError:
        rev_local = 0

    if meta_remoto:
        rev_remota = int(meta_remoto.get("revision", 0))
        if rev_remota > rev_local:
            equipo_nube = meta_remoto.get("ultimo_equipo", "otro dispositivo")
            registrar_log(f"Subida rechazada: Conflicto (Local #{rev_local} < Nube #{rev_remota} de {equipo_nube})", "WARN")
            flash(
                f"⛔ Subida bloqueada por seguridad: La nube tiene una versión más reciente "
                f"(#{rev_remota} de '{equipo_nube}'). Aplica los cambios remotos antes de subir.",
                "error"
            )
            return redirect(url_for("marcadores.configuracion"))

    nueva_rev = rev_local + 1
    modo_cif = os.environ.get("SYNC_MODO_CIFRADO", "auto").strip().lower()
    clave = "" if modo_cif == "libre" else os.environ.get("SYNC_CLAVE", "").strip()
    nombre_disp = os.environ.get("SYNC_NOMBRE_DISPOSITIVO", "Dispositivo PBM").strip()
    db_path = getattr(database, "DB_PATH", "marcadores.db")

    registrar_log(f"Empaquetando marcadores.db con AES-256 (Revisión #{nueva_rev})...", "SYS")
    exito, msg = sync_manager.exportar_boveda_cifrada(
        carpeta_sync=carpeta_sync,
        ruta_db=db_path,
        clave_sync=clave,
        nombre_equipo=nombre_disp,
        revision_actual=nueva_rev
    )

    if exito:
        with open(RUTA_ULTIMO_SYNC, "w", encoding="utf-8") as f:
            f.write(str(time.time()))
        set_key(RUTA_ENV, "SYNC_ULTIMA_REVISION", str(nueva_rev))
        os.environ["SYNC_ULTIMA_REVISION"] = str(nueva_rev)
        registrar_log(f"Bóveda sincronizada a la nube con éxito (Revisión #{nueva_rev})", "SUCCESS")
        flash(f"Bóveda subida exitosamente a la carpeta compartida (Revisión #{nueva_rev}).", "success")
    else:
        registrar_log(f"Fallo al sincronizar bóveda a la nube: {msg}", "ERROR")
        flash(f"Error al exportar la bóveda: {msg}", "error")

    return redirect(url_for("marcadores.configuracion"))


@marcadores_bp.route("/configuracion/sync/descargar", methods=["POST"])
def sync_descargar_boveda():
    carpeta_sync = os.environ.get("SYNC_CARPETA", "").strip()
    if not carpeta_sync or not os.path.isdir(carpeta_sync):
        flash("La carpeta de sincronización no está configurada o no es accesible.", "error")
        return redirect(url_for("marcadores.configuracion"))

    ruta_meta_fisica = os.path.join(carpeta_sync, VAULT_META_NAME)
    meta_remoto = sync_manager.leer_metadatos_remotos(carpeta_sync)

    if os.path.exists(ruta_meta_fisica) and not meta_remoto:
        registrar_log("Descarga abortada: archivo de metadatos corrupto en la nube", "ERROR")
        flash("El archivo .meta en la nube está corrupto o ilegible. Operación abortada.", "error")
        return redirect(url_for("marcadores.configuracion"))

    if not meta_remoto:
        flash("No se encontró ningún archivo de metadatos (.meta) en la nube.", "error")
        return redirect(url_for("marcadores.configuracion"))

    modo_cif = os.environ.get("SYNC_MODO_CIFRADO", "auto").strip().lower()
    clave = "" if modo_cif == "libre" else os.environ.get("SYNC_CLAVE", "").strip()
    db_path = getattr(database, "DB_PATH", "marcadores.db")

    registrar_log(f"Validando integridad SHA-256 e importando bóveda desde: {carpeta_sync}", "SYS")

    exito, msg = sync_manager.importar_boveda_cifrada(
        carpeta_sync=carpeta_sync,
        ruta_db_destino=db_path,
        clave_sync=clave
    )

    if exito:
        with open(RUTA_ULTIMO_SYNC, "w", encoding="utf-8") as f:
            f.write(str(time.time()))
        rev_remota = str(meta_remoto.get("revision", 1))
        set_key(RUTA_ENV, "SYNC_ULTIMA_REVISION", rev_remota)
        os.environ["SYNC_ULTIMA_REVISION"] = rev_remota
        registrar_log(f"Bóveda importada desde la nube con éxito (Revisión #{rev_remota})", "SUCCESS")
        flash(f"Bóveda restaurada con éxito: {msg}", "success")
    else:
        registrar_log(f"Fallo al restaurar bóveda desde la nube: {msg}", "ERROR")
        flash(f"Error en la sincronización: {msg}", "error")

    return redirect(url_for("marcadores.configuracion"))


@marcadores_bp.route("/configuracion/sync/estado", methods=["GET"])
def sync_consultar_estado():
    carpeta_sync = os.environ.get("SYNC_CARPETA", "").strip()
    sync_habilitado = os.environ.get("SYNC_HABILITADO", "false").lower() == "true"

    if not sync_habilitado or not carpeta_sync or not os.path.isdir(carpeta_sync):
        return jsonify({
            "habilitado": sync_habilitado,
            "carpeta_valida": bool(carpeta_sync and os.path.isdir(carpeta_sync)),
            "hay_boveda": False,
            "estado": "desconectado"
        })

    ruta_meta_fisica = os.path.join(carpeta_sync, VAULT_META_NAME)
    ruta_zip_fisica = os.path.join(carpeta_sync, VAULT_ZIP_NAME)
    meta = sync_manager.leer_metadatos_remotos(carpeta_sync)

    try:
        rev_local = int(os.environ.get("SYNC_ULTIMA_REVISION", "0").strip())
    except ValueError:
        rev_local = 0

    if os.path.exists(ruta_meta_fisica) and not meta:
        registrar_log(f"Comprobación de nube: Archivo .meta corrupto en '{carpeta_sync}'", "ERROR")
        return jsonify({
            "habilitado": True,
            "carpeta_valida": True,
            "hay_boveda": False,
            "meta_corrupto": True,
            "rev_local": rev_local,
            "estado": "meta_corrupto"
        })

    if not meta:
        return jsonify({
            "habilitado": True,
            "carpeta_valida": True,
            "hay_boveda": False,
            "meta_corrupto": False,
            "rev_local": rev_local,
            "estado": "sin_boveda_remota"
        })

    rev_remota = int(meta.get("revision", 0))
    equipo_remoto = meta.get("ultimo_equipo", "Desconocido")
    zip_valido = verificar_integridad_zip_remoto(ruta_zip_fisica, meta)

    estado = "al_dia"
    if rev_remota > rev_local:
        estado = "pendiente_descarga" if zip_valido else "zip_corrupto"
    elif rev_local > rev_remota:
        estado = "adelantado_local"
    elif not zip_valido:
        estado = "zip_corrupto"

    return jsonify({
        "habilitado": True,
        "carpeta_valida": True,
        "hay_boveda": True,
        "meta_corrupto": False,
        "rev_local": rev_local,
        "rev_remota": rev_remota,
        "ultimo_equipo": equipo_remoto,
        "timestamp": meta.get("timestamp", 0),
        "estado": estado
    })


@marcadores_bp.route("/configuracion/sync/explorar_carpeta", methods=["POST"])
def sync_explorar_carpeta():
    if not esta_desbloqueado():
        return jsonify({"ok": False, "error": "Debes desbloquear la configuración crítica con tu Master Key primero."}), 403

    ruta_base = seleccionar_carpeta_nativa()
    if not ruta_base:
        return jsonify({"ok": False, "cancelado": True})

    nombre_carpeta = os.path.basename(ruta_base.rstrip("/\\"))
    if nombre_carpeta.lower() != "pbm_sync":
        ruta_final = os.path.join(ruta_base, "PBM_Sync")
    else:
        ruta_final = ruta_base

    try:
        os.makedirs(ruta_final, exist_ok=True)
        registrar_log(f"Carpeta de sincronización BYOC provisionada: {ruta_final}", "SYS")
        return jsonify({
            "ok": True,
            "ruta": ruta_final,
            "creada": True
        })
    except Exception as e:
        registrar_log(f"Fallo al provisionar carpeta BYOC en '{ruta_final}': {e}", "ERROR")
        return jsonify({"ok": False, "error": f"No se pudo crear la carpeta en la ruta seleccionada: {str(e)}"}), 500