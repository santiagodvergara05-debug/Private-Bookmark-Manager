"""
==============================================================================
PBM PRIVATE BOOKMARK MANAGER - ENRUTADOR Y CONTROLADOR CENTRAL (ROUTES.PY)
==============================================================================
Controlador principal de peticiones HTTP para el sistema de marcadores (Gen 2).
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
10. Mantenimiento del ciclo de vida y alertas de respaldo preventivo.
==============================================================================
"""

import os
import json
import time
import secrets
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
    current_app
)

# Módulos internos del sistema PBM
import database
import bookmarks_html
from version import VERSION

# Instanciación del Blueprint central de marcadores
marcadores_bp = Blueprint("marcadores", __name__)


# ==============================================================================
# CONFIGURACIONES, CONSTANTES Y ESTADOS VOLÁTILES
# ==============================================================================
# Token volátil único generado en RAM al iniciar el servidor (invalida unlocks previos)
INICIO_SERVIDOR = secrets.token_hex(8)

# Ventana de gracia para ajustes críticos (puertos, IP, reseteo de datos): 2 minutos
DURACION_DESBLOQUEO = 120

# Rutas persistentes de configuración y telemetría de disco
RUTA_ENV = ".env"
RUTA_ULTIMO_BACKUP = "ultimo_backup.txt"
RUTA_SILENCIAR_BACKUP = "silenciar_backup.txt"

# Políticas de advertencia de respaldo (10 días para aviso, 24 horas para posponer)
SEGUNDOS_AVISO_BACKUP = 10 * 24 * 60 * 60
SEGUNDOS_SILENCIO_BACKUP = 1 * 24 * 60 * 60


# ==============================================================================
# SECCIÓN 1: MOTOR DE TELEMETRÍA Y LOGS EN TERMINAL (ESTILO LINUX / ANSI)
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

    # 1. Alertas de seguridad, intrusiones y fallas
    if tipo == "ERROR" or any(k in accion_lower for k in ["error", "fallid", "rechazad", "bloquead", "no autorizad", "peligro"]):
        badge = f"{CLR_BOLD}{CLR_ROJO}✖ [PBM :: ALERTA]{CLR_RESET}"
        texto_formateado = f"{CLR_ROJO}{accion}{CLR_RESET}"

    # 2. Creación, guardado, actualización y éxitos
    elif tipo == "SUCCESS" or any(k in accion_lower for k in ["éxito", "exitos", "cread", "guardad", "actualizad", "importad", "iniciad", "movido"]):
        badge = f"{CLR_BOLD}{CLR_VERDE}✔ [PBM :: ÉXITO]{CLR_RESET}"
        texto_formateado = f"{CLR_VERDE}{accion}{CLR_RESET}"

    # 3. Borrado físico y vaciado de registros
    elif tipo == "DELETE" or any(k in accion_lower for k in ["elimin", "borrad", "vaciad"]):
        badge = f"{CLR_BOLD}{CLR_MAGENTA}🗑 [PBM :: DELETE]{CLR_RESET}"
        texto_formateado = f"{CLR_MAGENTA}{accion}{CLR_RESET}"

    # 4. Operaciones críticas de sistema, llaves y sesiones
    elif tipo == "SYS" or any(k in accion_lower for k in ["desbloque", "bloque", "sesión", "rotad", "crític", "backup", "pospuest"]):
        badge = f"{CLR_BOLD}{CLR_AMARILLO}⚡ [PBM :: SYS]{CLR_RESET}"
        texto_formateado = f"{CLR_AMARILLO}{accion}{CLR_RESET}"

    # 5. Información general de navegación o consultas
    else:
        badge = f"{CLR_BOLD}{CLR_CYAN}ℹ [PBM :: INFO]{CLR_RESET}"
        texto_formateado = f"{CLR_CYAN}{accion}{CLR_RESET}"

    print(f"{CLR_GRIS}[{hora}]{CLR_RESET} {badge} {texto_formateado}")


# ==============================================================================
# SECCIÓN 2: SEGURIDAD, CONTROL DE ACCESOS Y CONTEXTO GLOBAL
# ==============================================================================
def esta_desbloqueado():
    """
    Valida si la sesión actual cuenta con autorización administrativa vigente.
    Verifica firma volátil de arranque de RAM y tiempo de vida útil (120s).
    """
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
    """
    Interceptor de seguridad perimetral:
    - Permite libre acceso únicamente a la pantalla de login y recursos estáticos.
    - Intercepta llamadas mutantes (POST/PUT/DELETE) no autorizadas emitiendo alertas con IP.
    - Devuelve JSON 401 en peticiones asíncronas (AJAX/Fetch) para evitar redirecciones corruptas.
    """
    if request.endpoint in ["marcadores.login", "static"]:
        return

    if not session.get("autenticado"):
        if request.method in ["POST", "PUT", "DELETE"]:
            ip = request.remote_addr
            print(f"\n\033[91m[SEGURIDAD :: PETICIÓN NO AUTORIZADA]\033[0m Intento de llamada {request.method} sin sesión a '{request.path}' desde IP: {ip}")
            if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"ok": False, "error": "Sesión no válida o expirada."}), 401

        return redirect(url_for("marcadores.login"))


@marcadores_bp.app_context_processor
def inyectar_avisos():
    """
    Inyecta parámetros globales de estado, preferencias del .env y telemetría
    de respaldos en todas las vistas HTML renderizadas por Flask.
    """
    desbloqueado = esta_desbloqueado()
    segundos_restantes = max(0, int(session.get("desbloqueo_expira", 0) - time.time())) if desbloqueado else 0

    fecha_ultimo = None
    if os.path.exists(RUTA_ULTIMO_BACKUP):
        try:
            with open(RUTA_ULTIMO_BACKUP, "r", encoding="utf-8") as f:
                fecha_ultimo = float(f.read().strip())
        except (ValueError, OSError):
            pass

    silenciado_hasta = 0
    if os.path.exists(RUTA_SILENCIAR_BACKUP):
        try:
            with open(RUTA_SILENCIAR_BACKUP, "r", encoding="utf-8") as f:
                silenciado_hasta = float(f.read().strip())
        except (ValueError, OSError):
            pass

    recordar_backup = False
    dias_sin_backup = 0
    ahora = time.time()

    if fecha_ultimo:
        segundos_pasados = ahora - fecha_ultimo
        dias_sin_backup = int(segundos_pasados // 86400)
        if segundos_pasados >= SEGUNDOS_AVISO_BACKUP and ahora > silenciado_hasta:
            recordar_backup = True
    elif ahora > silenciado_hasta:
        recordar_backup = True

    return {
        "app_version": VERSION,
        "contraseña_por_defecto": os.environ.get("APP_PASSWORD") == "cambiame",
        "contrasena_por_defecto": os.environ.get("APP_PASSWORD") == "cambiame",
        "mostrar_favicons": os.environ.get("MOSTRAR_FAVICONS", "true").strip().lower() == "true",
        "desbloqueo_critico_activo": desbloqueado,
        "desbloqueo_segundos_restantes": segundos_restantes,
        "recordar_backup": recordar_backup,
        "dias_sin_backup": dias_sin_backup,
        "abrir_nueva_pestana": os.environ.get("ABRIR_NUEVA_PESTANA", "true").strip().lower() == "true",
        "modo_oscuro": os.environ.get("MODO_OSCURO", "false").strip().lower() == "true"
    }


# ==============================================================================
# SECCIÓN 3: AUTENTICACIÓN Y SESIONES DE USUARIO
# ==============================================================================
@marcadores_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    Gestiona el acceso web admitiendo tanto APP_PASSWORD como MASTER_KEY de rescate.
    Monitorea intentos fallidos para proveer guías de recuperación tras 3 desatinos.
    """
    if session.get("autenticado"):
        return redirect(url_for("marcadores.home"))

    mostrar_contrasena_inicial = os.environ.get("CONTRASENA_MOSTRADA", "false").strip().lower() != "true"
    app_pwd = os.environ.get("APP_PASSWORD", "cambiame").strip()
    master_key = os.environ.get("MASTER_KEY", "").strip()

    if request.method == "POST":
        pwd_ingresada = request.form.get("password", "").strip()

        # Validación cruzada de identidad (Contraseña habitual o Llave Maestra)
        if pwd_ingresada and (pwd_ingresada == app_pwd or (master_key and pwd_ingresada == master_key)):
            session["autenticado"] = True
            session.permanent = True
            session["intentos_fallidos"] = 0
            registrar_log(f"Inicio de sesión exitoso desde {request.remote_addr}", "SUCCESS")

            # Desactiva la tarjeta informativa si era el primer arranque
            if mostrar_contrasena_inicial:
                set_key(RUTA_ENV, "CONTRASENA_MOSTRADA", "true")
                os.environ["CONTRASENA_MOSTRADA"] = "true"
                registrar_log("Primer acceso: aviso de credenciales ocultado permanentemente", "SYS")

            return redirect(url_for("marcadores.home"))

        session["intentos_fallidos"] = session.get("intentos_fallidos", 0) + 1
        intentos = session["intentos_fallidos"]
        registrar_log(f"Credencial incorrecta desde {request.remote_addr} (intento #{intentos})", "ERROR")

        if intentos == 3:
            registrar_log(f"Umbral de seguridad alcanzado desde {request.remote_addr}: ayuda en pantalla mostrada", "SYS")

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
    """Limpia el almacén de sesión y revoca el acceso del navegador actual."""
    session.clear()
    registrar_log("Cierre de sesión manual ejecutado", "SYS")
    return redirect(url_for("marcadores.login"))


# ==============================================================================
# SECCIÓN 4: VISTAS Y NAVEGACIÓN DE DIRECTORIOS
# ==============================================================================
def ver_carpeta(carpeta_id):
    """
    Controlador interno: obtiene las carpetas anidadas, la posición actual del árbol
    y la lista de marcadores contenidos para renderizar la interfaz principal.
    """
    carpeta_actual = database.obtener_carpeta(carpeta_id)
    subcarpetas = database.obtener_subcarpetas(carpeta_id)
    marcadores = database.obtener_marcadores(carpeta_id)
    todas_las_carpetas = database.obtener_todas_las_carpetas()

    return render_template(
        "index.html",
        carpeta_actual=carpeta_actual,
        subcarpetas=subcarpetas,
        marcadores=marcadores,
        todas_las_carpetas=todas_las_carpetas
    )


@marcadores_bp.route("/")
def home():
    """Punto de entrada principal: muestra la raíz del catálogo de marcadores."""
    return ver_carpeta(None)


@marcadores_bp.route("/carpeta/<int:carpeta_id>")
def ver_carpeta_ruta(carpeta_id):
    """Navega a un directorio específico de la jerarquía de marcadores."""
    return ver_carpeta(carpeta_id)


# ==============================================================================
# SECCIÓN 5: GESTIÓN DE MARCADORES Y CARPETAS (CRUD & OPERACIONES MASIVAS)
# ==============================================================================
def obtener_titulo_desde_url(url):
    """
    Realiza una solicitud HTTP ligera a la URL indicada con User-Agent de navegador
    para extraer y retornar el texto de la etiqueta <title>.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        respuesta = requests.get(url, timeout=5, headers=headers)
        if respuesta.status_code == 200:
            sopa = BeautifulSoup(respuesta.text, "html.parser")
            if sopa.title and sopa.title.string:
                return sopa.title.string.strip()
    except Exception as e:
        registrar_log(f"Fallo al autocompletar título para {url}: {e}", "INFO")
    return None


@marcadores_bp.route("/agregar", methods=["POST"])
def agregar():
    """Registra un nuevo marcador con soporte de autocompletado y progreso inicial."""
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


@marcadores_bp.route("/crear_carpeta", methods=["POST"])
def crear_carpeta():
    """Crea una nueva carpeta en la raíz o como subdirectorio de otra existente."""
    carpeta_padre_id = request.form.get("carpeta_padre_id") or None
    nombre = request.form.get("nombre", "").strip() or "Nueva Carpeta"

    database.crear_carpeta(nombre, carpeta_padre_id)
    registrar_log(f"Carpeta creada con éxito: '{nombre}'", "SUCCESS")
    return redirect(request.referrer or url_for("marcadores.home"))


@marcadores_bp.route("/editar/<int:id_marcador>", methods=["GET", "POST"])
def editar(id_marcador):
    """Actualiza la información, carpeta contenedora, notas y progreso de un marcador."""
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
    todas_las_carpetas = database.obtener_todas_las_carpetas()
    return render_template("editar.html", marcador=marcador, todas_las_carpetas=todas_las_carpetas)


@marcadores_bp.route("/editar_carpeta/<int:carpeta_id>", methods=["GET", "POST"])
def editar_carpeta(carpeta_id):
    """Renombra una carpeta y permite trasladar su ubicación jerárquica en el árbol."""
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
    todas_las_carpetas = database.obtener_todas_las_carpetas()
    return render_template("editar_carpeta.html", carpeta=carpeta, todas_las_carpetas=todas_las_carpetas)


@marcadores_bp.route("/mover/<int:id_marcador>", methods=["POST"])
def mover(id_marcador):
    """Reubica rápidamente un marcador en otra carpeta o en el directorio raíz."""
    nueva_carpeta_id = request.form.get("nueva_carpeta_id") or None
    database.mover_marcador(id_marcador, nueva_carpeta_id)
    registrar_log(f"Marcador [ID: {id_marcador}] movido a carpeta {nueva_carpeta_id or 'Raíz'}", "SUCCESS")
    return redirect(request.referrer or url_for("marcadores.home"))


@marcadores_bp.route("/mover_masivo", methods=["POST"])
def mover_masivo():
    """
    Reubica marcadores y/o carpetas seleccionadas hacia una carpeta destino o a la raíz.
    Soporta peticiones de formularios multipart/form-data y llamadas asíncronas JSON.
    """
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

    # Fallback para peticiones Fetch/JSON
    if not ids_marcadores and not ids_carpetas and request.is_json:
        payload = request.get_json() or {}
        ids_marcadores = payload.get("ids_marcadores", [])
        ids_carpetas = payload.get("ids_carpetas", [])
        if "nueva_carpeta_id" in payload:
            raw_id = payload.get("nueva_carpeta_id")
            nueva_carpeta_id = int(raw_id) if raw_id and str(raw_id).isdigit() else None

    if not ids_marcadores and not ids_carpetas:
        registrar_log("Intento de movimiento masivo sin elementos seleccionados", "INFO")
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
    """Elimina en lote los marcadores seleccionados permanentemente."""
    ids_marcadores = request.form.getlist("ids_marcadores")

    if not ids_marcadores:
        registrar_log("Intento de borrado masivo sin marcadores seleccionados", "INFO")
        return redirect(request.referrer or url_for("marcadores.home"))

    total_eliminados = database.eliminar_marcadores_lote(ids_marcadores)
    registrar_log(f"Lote eliminado: {total_eliminados} marcadores borrados permanentemente", "DELETE")

    return redirect(request.referrer or url_for("marcadores.home"))


@marcadores_bp.route("/carpeta/<int:carpeta_id>/conteo")
def conteo_carpeta(carpeta_id):
    """Retorna la cantidad de marcadores que alberga una carpeta para alimentar el modal interactivo."""
    total = database.contar_contenido_carpeta(carpeta_id)
    return jsonify({"ok": True, "carpeta_id": carpeta_id, "total": total})


@marcadores_bp.route("/eliminar/<int:id_marcador>")
def eliminar(id_marcador):
    """Elimina permanentemente un marcador específico de la base de datos."""
    database.eliminar_marcador(id_marcador)
    registrar_log(f"Marcador eliminado [ID: {id_marcador}]", "DELETE")
    return redirect(request.referrer or url_for("marcadores.home"))


@marcadores_bp.route("/eliminar_carpeta/<int:carpeta_id>", methods=["GET", "POST"])
def eliminar_carpeta(carpeta_id):
    """
    Elimina una carpeta específica:
    - Admite POST desde la ventana modal con la opción 'borrar_contenido'.
    - Si 'borrar_contenido' está activo ('on', 'true', '1'), elimina los marcadores internos.
    - Si no está activo, preserva los marcadores reubicándolos en la raíz (carpeta_id = NULL).
    - Mantiene compatibilidad con llamadas GET de versiones anteriores.
    """
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
# SECCIÓN 6: BÚSQUEDA, ÍNDICE MAESTRO Y PROGRESO DE LECTURA
# ==============================================================================
@marcadores_bp.route("/buscar")
def buscar():
    """Filtra y devuelve marcadores coincidentes por texto en títulos, URLs o notas."""
    texto = request.args.get("q", "").strip()
    resultados = database.buscar_marcadores(texto) if texto else []
    if texto:
        registrar_log(f"Búsqueda ejecutada: '{texto}' ({len(resultados)} coincidencias)", "INFO")
    return render_template("buscar.html", texto=texto, resultados=resultados)


@marcadores_bp.route("/todos")
def todos():
    """Genera la vista consolidada de todos los marcadores agrupados por carpeta."""
    marcadores = database.obtener_todos_los_marcadores()
    todas_las_carpetas = database.obtener_todas_las_carpetas()

    agrupados = {}
    for m in marcadores:
        nombre_grupo = m["carpeta_nombre"] if m["carpeta_nombre"] else "Sin carpeta"
        agrupados.setdefault(nombre_grupo, []).append(m)

    return render_template("todos.html", agrupados=agrupados, todas_las_carpetas=todas_las_carpetas)


@marcadores_bp.route("/progreso/<int:id_marcador>/<accion>", methods=["POST"])
def progreso(id_marcador, accion):
    """Ajusta en tiempo real el contador de progreso numérico (capítulo, lección, avance)."""
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
# SECCIÓN 7: AJUSTES DE SISTEMA, LLAVE MAESTRA Y SESIONES GLOBALES
# ==============================================================================
@marcadores_bp.route("/configuracion", methods=["GET", "POST"])
def configuracion():
    """Panel administrativo para preferencias visuales, puertos de red y credenciales."""
    desbloqueado = esta_desbloqueado()

    if request.method == "POST":
        # 1. Parámetros de seguridad protegidos por MASTER_KEY
        if desbloqueado:
            nueva_password = request.form.get("password", "").strip()
            if nueva_password:
                set_key(RUTA_ENV, "APP_PASSWORD", nueva_password)
                os.environ["APP_PASSWORD"] = nueva_password
                registrar_log("Contraseña de acceso APP_PASSWORD actualizada", "SYS")

            nuevo_host = request.form.get("host", "").strip()
            if nuevo_host in ["127.0.0.1", "0.0.0.0"]:
                set_key(RUTA_ENV, "HOST", nuevo_host)
                os.environ["HOST"] = nuevo_host

            nuevo_puerto = request.form.get("port", "").strip()
            if nuevo_puerto:
                try:
                    p_num = int(nuevo_puerto)
                    if 1 <= p_num <= 65535:
                        set_key(RUTA_ENV, "PORT", str(p_num))
                        os.environ["PORT"] = str(p_num)
                except ValueError:
                    pass

            auto_abrir = "true" if "auto_abrir_navegador" in request.form else "false"
            set_key(RUTA_ENV, "AUTO_ABRIR_NAVEGADOR", auto_abrir)
            os.environ["AUTO_ABRIR_NAVEGADOR"] = auto_abrir

            log_mode = "true" if "log_mode" in request.form else "false"
            set_key(RUTA_ENV, "LOG_MODE", log_mode)
            os.environ["LOG_MODE"] = log_mode

        # 2. Preferencias generales de usuario (libres de bloqueo)
        mostrar_favicons = "true" if "mostrar_favicons" in request.form else "false"
        set_key(RUTA_ENV, "MOSTRAR_FAVICONS", mostrar_favicons)
        os.environ["MOSTRAR_FAVICONS"] = mostrar_favicons

        abrir_nueva_pestana = "true" if "abrir_nueva_pestana" in request.form else "false"
        set_key(RUTA_ENV, "ABRIR_NUEVA_PESTANA", abrir_nueva_pestana)
        os.environ["ABRIR_NUEVA_PESTANA"] = abrir_nueva_pestana

        modo_oscuro = "true" if "modo_oscuro" in request.form else "false"
        set_key(RUTA_ENV, "MODO_OSCURO", modo_oscuro)
        os.environ["MODO_OSCURO"] = modo_oscuro

        registrar_log("Ajustes del servidor y preferencias actualizadas en .env", "SYS")
        return redirect(url_for("marcadores.configuracion", guardado=1))

    valores = dotenv_values(RUTA_ENV)
    return render_template("configuracion.html", valores=valores, guardado=request.args.get("guardado"))


@marcadores_bp.route("/configuracion/desbloquear", methods=["POST"])
def desbloquear_critico():
    """Valida la MASTER_KEY habilitando cambios sensibles por 120 segundos."""
    clave_ingresada = request.form.get("master_key", "").strip()
    master_key_actual = os.environ.get("MASTER_KEY", "").strip()

    if clave_ingresada and clave_ingresada == master_key_actual:
        session["desbloqueo_critico"] = True
        session["desbloqueo_expira"] = time.time() + DURACION_DESBLOQUEO
        session["desbloqueo_servidor"] = INICIO_SERVIDOR
        registrar_log("Configuración crítica desbloqueada por 2 minutos", "SYS")
        return redirect(url_for("marcadores.configuracion"))

    registrar_log("Intento denegado de desbloqueo crítico (MASTER_KEY inválida)", "ERROR")
    return redirect(url_for("marcadores.configuracion", error_master=1))


@marcadores_bp.route("/configuracion/bloquear", methods=["POST"])
def bloquear_critico():
    """Revoca el permiso administrativo de forma manual anticipando la expiración."""
    session.pop("desbloqueo_critico", None)
    registrar_log("Configuración crítica bloqueada manualmente", "SYS")
    return redirect(url_for("marcadores.configuracion"))


@marcadores_bp.route("/configuracion/cerrar_sesiones", methods=["POST"])
def cerrar_sesiones_globales():
    """
    Invalida instantáneamente todas las cookies activas en la red rotando la
    SECRET_KEY en caliente tanto en memoria viva (RAM) como en el archivo .env.
    """
    nueva_key = secrets.token_hex(32)

    # 1. Persistencia física en disco
    set_key(RUTA_ENV, "SECRET_KEY", nueva_key)
    os.environ["SECRET_KEY"] = nueva_key

    # 2. Rotación en memoria viva (invalida tokens de Flask en caliente sin reiniciar)
    current_app.secret_key = nueva_key

    registrar_log("Cierre global: SECRET_KEY rotada en memoria y persistida en .env", "SYS")
    session.clear()
    return redirect(url_for("marcadores.login"))


@marcadores_bp.route("/configuracion/posponer_backup", methods=["POST"])
def posponer_backup():
    """Pospone la notificación de respaldo en pantalla por 24 horas."""
    silenciado_hasta = time.time() + SEGUNDOS_SILENCIO_BACKUP
    with open(RUTA_SILENCIAR_BACKUP, "w", encoding="utf-8") as f:
        f.write(str(silenciado_hasta))
    registrar_log("Aviso preventivo de copia de seguridad pospuesto por 24 horas", "SYS")
    return redirect(request.referrer or url_for("marcadores.home"))


@marcadores_bp.route("/configuracion/borrar_todo", methods=["POST"])
def borrar_todo_ruta():
    """Vacia por completo todas las carpetas y marcadores bajo confirmación de Master Key."""
    if not esta_desbloqueado():
        registrar_log("Intento no autorizado de vaciado de base de datos sin desbloqueo", "ERROR")
        return redirect(url_for("marcadores.configuracion"))

    database.borrar_todo()
    registrar_log("Vaciado integral de la base de datos completado", "DELETE")
    return redirect(url_for("marcadores.configuracion", guardado=1))


# ==============================================================================
# SECCIÓN 8: MOTOR DE RESPALDOS Y MIGRACIÓN (JSON & HTML NETSCAPE)
# ==============================================================================
@marcadores_bp.route("/exportar")
def exportar():
    """Exporta toda la base de datos relacional en formato estructurado JSON nativo."""
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

    # Asienta la fecha del respaldo y limpia silenciamientos
    with open(RUTA_ULTIMO_BACKUP, "w", encoding="utf-8") as f:
        f.write(str(time.time()))
    if os.path.exists(RUTA_SILENCIAR_BACKUP):
        try:
            os.remove(RUTA_SILENCIAR_BACKUP)
        except OSError:
            pass

    contenido = json.dumps(datos, indent=2, ensure_ascii=False)
    registrar_log("Exportación JSON completada con éxito", "SUCCESS")
    return Response(
        contenido,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=backup_marcadores.json"}
    )


@marcadores_bp.route("/importar", methods=["POST"])
def importar():
    """Restaura o fusiona carpetas y enlaces desde un archivo JSON nativo."""
    if "archivo" not in request.files:
        registrar_log("Intento de importación sin campo de archivo", "ERROR")
        return redirect(url_for("marcadores.home"))

    archivo = request.files["archivo"]
    if not archivo or archivo.filename == "":
        registrar_log("Intento de importación con archivo vacío", "ERROR")
        return redirect(url_for("marcadores.home"))

    if not archivo.filename.lower().endswith(".json"):
        registrar_log(f"Extensión rechazada en importación JSON: '{archivo.filename}'", "ERROR")
        return redirect(url_for("marcadores.home"))

    try:
        datos = json.load(archivo)
        carpetas = datos.get("carpetas", [])
        marcadores = datos.get("marcadores", [])
        database.importar_datos(carpetas, marcadores)
        registrar_log(f"Importación JSON completada ({len(marcadores)} marcadores incorporados)", "SUCCESS")
    except Exception as e:
        registrar_log(f"Error procesando archivo JSON de respaldo: {e}", "ERROR")

    return redirect(url_for("marcadores.home"))


@marcadores_bp.route("/exportar_html")
def exportar_html_ruta():
    """Genera archivo HTML estándar (formato Netscape) compatible con Chrome, Firefox y Brave."""
    carpetas = database.obtener_todas_las_carpetas()
    marcadores = database.obtener_todos_los_marcadores()
    contenido = bookmarks_html.exportar_html(
        [dict(c) for c in carpetas], [dict(m) for m in marcadores]
    )
    registrar_log("Exportación HTML (formato estándar de navegador) completada", "SUCCESS")
    return Response(
        contenido,
        mimetype="text/html",
        headers={"Content-Disposition": "attachment; filename=backup_marcadores.html"}
    )


@marcadores_bp.route("/importar_html", methods=["POST"])
def importar_html_ruta():
    """Parsea e importa marcadores desde archivos HTML exportados por navegadores comerciales."""
    if "archivo" not in request.files:
        registrar_log("Intento de importación HTML sin campo de archivo", "ERROR")
        return redirect(url_for("marcadores.home"))

    archivo = request.files["archivo"]
    if not archivo or archivo.filename == "":
        registrar_log("Intento de importación HTML con archivo vacío", "ERROR")
        return redirect(url_for("marcadores.home"))

    # Validación de extensiones web
    if not (archivo.filename.lower().endswith(".html") or archivo.filename.lower().endswith(".htm")):
        registrar_log(f"Extensión rechazada en importación HTML: '{archivo.filename}'", "ERROR")
        return redirect(url_for("marcadores.home"))

    try:
        contenido = archivo.read().decode("utf-8", errors="ignore")
        carpetas_data, marcadores_data = bookmarks_html.importar_html(contenido)
        database.importar_datos(carpetas_data, marcadores_data)
        registrar_log(f"Importación HTML completada ({len(marcadores_data)} marcadores incorporados)", "SUCCESS")
    except Exception as e:
        registrar_log(f"Error procesando archivo HTML de navegadores: {e}", "ERROR")

    return redirect(url_for("marcadores.home"))