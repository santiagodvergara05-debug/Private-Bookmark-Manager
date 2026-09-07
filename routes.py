import database
import os
from flask import Blueprint, render_template, request, redirect, url_for, session
import secrets
from dotenv import set_key, dotenv_values
import json
from flask import Response
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
from version import VERSION

INICIO_SERVIDOR = secrets.token_hex(8)  # se regenera en cada arranque real del proceso
DURACION_DESBLOQUEO = 120  # segundos (2 minutos)

RUTA_ULTIMO_BACKUP = "ultimo_backup.txt"
RUTA_SILENCIAR_BACKUP = "silenciar_backup.txt"

SEGUNDOS_AVISO_BACKUP = 10 * 24 * 60 * 60   # Avisa si pasaron 10 días desde el último backup
SEGUNDOS_SILENCIO_BACKUP = 1 * 24 * 60 * 60  # Pospone el cartel por 1 día (24 horas)

#Tiempo de testeo
#SEGUNDOS_AVISO_BACKUP = 60
#SEGUNDOS_SILENCIO_BACKUP = 60

RUTA_ENV = ".env"

def esta_desbloqueado():
    if not session.get("desbloqueo_critico"):
        return False
    if session.get("desbloqueo_servidor") != INICIO_SERVIDOR:
        session.pop("desbloqueo_critico", None)
        return False
    if time.time() > session.get("desbloqueo_expira", 0):
        session.pop("desbloqueo_critico", None)
        return False
    return True

marcadores_bp = Blueprint("marcadores", __name__)


def registrar_log(accion):
    if os.environ.get("LOG_MODE", "false").lower() == "true":
        hora = datetime.now().strftime("%H:%M:%S")
        print(f"[{hora} LOG] {accion}")

@marcadores_bp.app_context_processor
def inyectar_avisos():
    
    desbloqueado = esta_desbloqueado()
    segundos_restantes = max(0, int(session.get("desbloqueo_expira", 0) - time.time())) if desbloqueado else 0

    fecha_ultimo = None
    if os.path.exists(RUTA_ULTIMO_BACKUP):
        with open(RUTA_ULTIMO_BACKUP) as f:
            try:
                fecha_ultimo = float(f.read().strip())
            except ValueError:
                pass

    silenciado_hasta = 0
    if os.path.exists(RUTA_SILENCIAR_BACKUP):
        with open(RUTA_SILENCIAR_BACKUP) as f:
            try:
                silenciado_hasta = float(f.read().strip())
            except ValueError:
                pass

    recordar_backup = False
    dias_sin_backup = 0
    if fecha_ultimo:
        segundos_pasados = time.time() - fecha_ultimo
        dias_sin_backup = int(segundos_pasados // 86400)
        if segundos_pasados >= SEGUNDOS_AVISO_BACKUP and time.time() > silenciado_hasta:
            recordar_backup = True
    elif time.time() > silenciado_hasta:
        recordar_backup = True

    return {
        "app_version": VERSION,
        "contraseña_por_defecto": os.environ.get("APP_PASSWORD") == "cambiame",
        "mostrar_favicons": os.environ.get("MOSTRAR_FAVICONS", "true").lower() == "true",
        "desbloqueo_critico_activo": desbloqueado,
        "desbloqueo_segundos_restantes": segundos_restantes,
        "recordar_backup": recordar_backup,
        "dias_sin_backup": dias_sin_backup,
        "abrir_nueva_pestana": os.environ.get("ABRIR_NUEVA_PESTANA", "true").lower() == "true",
        "modo_oscuro": os.environ.get("MODO_OSCURO", "false").lower() == "true"
    }

@marcadores_bp.before_request
def requerir_login():
    if request.endpoint == "marcadores.login":
        return
    if not session.get("autenticado"):
        return redirect(url_for("marcadores.login"))

@marcadores_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == os.environ.get("APP_PASSWORD"):
            session["autenticado"] = True
            session["intentos_fallidos"] = 0
            registrar_log(f"Inicio de sesión exitoso desde {request.remote_addr}")
            return redirect(url_for("marcadores.home"))

        session["intentos_fallidos"] = session.get("intentos_fallidos", 0) + 1
        registrar_log(f"Intento fallido de inicio de sesión desde {request.remote_addr} (intento #{session['intentos_fallidos']})")
        
        if session["intentos_fallidos"] == 3:
            registrar_log(f"⚠️ Umbral alcanzado desde {request.remote_addr}: mostrada ayuda de recuperación en pantalla")

        return render_template(
            "login.html",
            error="Contraseña incorrecta",
            mostrar_ayuda=session["intentos_fallidos"] >= 3
        )
    return render_template("login.html", error=None, mostrar_ayuda=False)

@marcadores_bp.route("/logout")
def logout():
    session.pop("autenticado", None)
    registrar_log("Cierre de sesión")
    return redirect(url_for("marcadores.login"))

def ver_carpeta(carpeta_id):
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
    return ver_carpeta(None)

@marcadores_bp.route("/carpeta/<int:carpeta_id>")
def ver_carpeta_ruta(carpeta_id):
    return ver_carpeta(carpeta_id)

def obtener_titulo_desde_url(url):
    try:
        respuesta = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        sopa = BeautifulSoup(respuesta.text, "html.parser")
        if sopa.title and sopa.title.string:
            return sopa.title.string.strip()
    except Exception as e:
        registrar_log(f"No se pudo autocompletar título para {url}: {e}")
    return None

@marcadores_bp.route("/agregar", methods=["POST"])
def agregar():
    carpeta_id = request.form.get("carpeta_id") or None
    url = request.form["url"]
    titulo = request.form.get("titulo", "").strip()
    nota = request.form.get("nota", "").strip() or None

    if not titulo and request.form.get("autocompletar"):
        titulo = obtener_titulo_desde_url(url) or url

    if not titulo:
        titulo = url

    database.agregar_marcador(titulo, url, carpeta_id, nota)
    registrar_log(f"Marcador agregado: '{titulo}' ({url})")
    return redirect(request.referrer or url_for("marcadores.home"))

@marcadores_bp.route("/crear_carpeta", methods=["POST"])
def crear_carpeta():
    carpeta_padre_id = request.form.get("carpeta_padre_id") or None
    nombre = request.form["nombre"]
    database.crear_carpeta(nombre, carpeta_padre_id)
    registrar_log(f"Carpeta creada: '{nombre}'")
    return redirect(request.referrer or url_for("marcadores.home"))

@marcadores_bp.route("/eliminar/<int:id_marcador>")
def eliminar(id_marcador):
    database.eliminar_marcador(id_marcador)
    registrar_log(f"Marcador eliminado (ID: {id_marcador})")
    return redirect(request.referrer or url_for("marcadores.home"))

@marcadores_bp.route("/eliminar_carpeta/<int:carpeta_id>")
def eliminar_carpeta(carpeta_id):
    database.eliminar_carpeta(carpeta_id)
    registrar_log(f"Carpeta eliminada (ID: {carpeta_id})")
    return redirect(url_for("marcadores.home"))

@marcadores_bp.route("/buscar")
def buscar():
    texto = request.args.get("q", "")
    resultados = database.buscar_marcadores(texto) if texto else []
    if texto:
        registrar_log(f"Búsqueda: '{texto}' - {len(resultados)} resultado(s)")
    return render_template("buscar.html", texto=texto, resultados=resultados)

@marcadores_bp.route("/mover/<int:id_marcador>", methods=["POST"])
def mover(id_marcador):
    nueva_carpeta_id = request.form.get("nueva_carpeta_id") or None
    database.mover_marcador(id_marcador, nueva_carpeta_id)
    registrar_log(f"Marcador {id_marcador} movido a carpeta {nueva_carpeta_id or 'Raíz'}")
    return redirect(request.referrer or url_for("marcadores.home"))

@marcadores_bp.route("/editar/<int:id_marcador>", methods=["GET", "POST"])
def editar(id_marcador):
    if request.method == "POST":
        nueva_carpeta_id = request.form.get("carpeta_id") or None
        nota = request.form.get("nota", "").strip() or None
        try:
            progreso = max(0, int(request.form.get("progreso", 0)))
        except ValueError:
            progreso = 0
        database.editar_marcador(id_marcador, request.form["titulo"], request.form["url"], nueva_carpeta_id, nota, progreso)
        registrar_log(f"Marcador {id_marcador} editado: '{request.form['titulo']}'")
        if nueva_carpeta_id:
            return redirect(url_for("marcadores.ver_carpeta_ruta", carpeta_id=nueva_carpeta_id))
        return redirect(url_for("marcadores.home"))
    marcador = database.obtener_marcador(id_marcador)
    todas_las_carpetas = database.obtener_todas_las_carpetas()
    return render_template("editar.html", marcador=marcador, todas_las_carpetas=todas_las_carpetas)

@marcadores_bp.route("/editar_carpeta/<int:carpeta_id>", methods=["GET", "POST"])
def editar_carpeta(carpeta_id):
    if request.method == "POST":
        nombre_nuevo = request.form["nombre"]
        database.editar_carpeta(carpeta_id, nombre_nuevo)
        registrar_log(f"Carpeta {carpeta_id} editada. Nuevo nombre: '{nombre_nuevo}'")
        carpeta = database.obtener_carpeta(carpeta_id)
        if carpeta and carpeta["carpeta_padre_id"]:
            return redirect(url_for("marcadores.ver_carpeta_ruta", carpeta_id=carpeta["carpeta_padre_id"]))
        return redirect(url_for("marcadores.home"))
    carpeta = database.obtener_carpeta(carpeta_id)
    return render_template("editar_carpeta.html", carpeta=carpeta)

@marcadores_bp.route("/todos")
def todos():
    marcadores = database.obtener_todos_los_marcadores()
    todas_las_carpetas = database.obtener_todas_las_carpetas()

    agrupados = {}
    for m in marcadores:
        nombre_grupo = m["carpeta_nombre"] if m["carpeta_nombre"] else "Sin carpeta"
        agrupados.setdefault(nombre_grupo, []).append(m)

    return render_template("todos.html", agrupados=agrupados, todas_las_carpetas=todas_las_carpetas)

@marcadores_bp.route("/configuracion", methods=["GET", "POST"])
def configuracion():
    if request.method == "POST":
        if esta_desbloqueado():
            nueva_password = request.form.get("password")
            if nueva_password:
                set_key(RUTA_ENV, "APP_PASSWORD", nueva_password)
                os.environ["APP_PASSWORD"] = nueva_password
                nueva_key = secrets.token_hex(32)
                set_key(RUTA_ENV, "SECRET_KEY", nueva_key)
                os.environ["SECRET_KEY"] = nueva_key
                registrar_log("Contraseña y Secret Key actualizadas")

        mostrar_favicons = "true" if "mostrar_favicons" in request.form else "false"
        set_key(RUTA_ENV, "MOSTRAR_FAVICONS", mostrar_favicons)
        os.environ["MOSTRAR_FAVICONS"] = mostrar_favicons

        abrir_nueva_pestana = "true" if "abrir_nueva_pestana" in request.form else "false"
        set_key(RUTA_ENV, "ABRIR_NUEVA_PESTANA", abrir_nueva_pestana)
        os.environ["ABRIR_NUEVA_PESTANA"] = abrir_nueva_pestana

        modo_oscuro = "true" if "modo_oscuro" in request.form else "false"
        set_key(RUTA_ENV, "MODO_OSCURO", modo_oscuro)
        os.environ["MODO_OSCURO"] = modo_oscuro

        nuevo_puerto = request.form.get("port")
        if nuevo_puerto:
            set_key(RUTA_ENV, "PORT", nuevo_puerto)
            os.environ["PORT"] = nuevo_puerto

        if esta_desbloqueado():
            flask_debug = "true" if "flask_debug" in request.form else "false"
            set_key(RUTA_ENV, "FLASK_DEBUG", flask_debug)
            os.environ["FLASK_DEBUG"] = flask_debug

            log_mode = "true" if "log_mode" in request.form else "false"
            set_key(RUTA_ENV, "LOG_MODE", log_mode)
            os.environ["LOG_MODE"] = log_mode

            nuevo_host = request.form.get("host")
            if nuevo_host:
                set_key(RUTA_ENV, "HOST", nuevo_host)
                os.environ["HOST"] = nuevo_host

        registrar_log("Configuración guardada en .env")
        return redirect(url_for("marcadores.configuracion", guardado=1))

    valores = dotenv_values(RUTA_ENV)
    return render_template("configuracion.html", valores=valores, guardado=request.args.get("guardado"))




@marcadores_bp.route("/configuracion/desbloquear", methods=["POST"])
def desbloquear_critico():
    clave_ingresada = request.form.get("master_key", "")
    if clave_ingresada and clave_ingresada == os.environ.get("MASTER_KEY"):
        session["desbloqueo_critico"] = True
        session["desbloqueo_expira"] = time.time() + DURACION_DESBLOQUEO
        session["desbloqueo_servidor"] = INICIO_SERVIDOR
        registrar_log("Configuración crítica desbloqueada")
        return redirect(url_for("marcadores.configuracion"))

    registrar_log("Intento fallido de desbloqueo de configuración crítica")
    return redirect(url_for("marcadores.configuracion", error_master=1))

@marcadores_bp.route("/configuracion/bloquear", methods=["POST"])
def bloquear_critico():
    session.pop("desbloqueo_critico", None)
    registrar_log("Configuración crítica bloqueada nuevamente")
    return redirect(url_for("marcadores.configuracion"))




@marcadores_bp.route("/configuracion/cerrar_sesiones", methods=["POST"])
def cerrar_sesiones_globales():
    set_key(RUTA_ENV, "SECRET_KEY", secrets.token_hex(32))
    registrar_log("Cierre de sesión global ejecutado (Secret Key regenerada)")
    return redirect(url_for("marcadores.configuracion", guardado=1))

@marcadores_bp.route("/exportar")
def exportar():
    carpetas = database.obtener_todas_las_carpetas()
    marcadores = database.obtener_todos_los_marcadores()

    datos = {
        "carpetas": [dict(c) for c in carpetas],
        "marcadores": [dict(m) for m in marcadores]
    }

    with open(RUTA_ULTIMO_BACKUP, "w") as f:
        f.write(str(time.time()))
    if os.path.exists(RUTA_SILENCIAR_BACKUP):
        os.remove(RUTA_SILENCIAR_BACKUP)

    contenido = json.dumps(datos, indent=2, ensure_ascii=False)
    registrar_log("Exportación de base de datos realizada")
    return Response(
        contenido,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=backup_marcadores.json"}
    )

@marcadores_bp.route("/configuracion/posponer_backup", methods=["POST"])
def posponer_backup():
    silenciar_hasta = time.time() + SEGUNDOS_SILENCIO_BACKUP
    with open(RUTA_SILENCIAR_BACKUP, "w") as f:
        f.write(str(silenciar_hasta))
    registrar_log("Aviso de backup pospuesto")
    return redirect(request.referrer or url_for("marcadores.home"))

@marcadores_bp.route("/importar", methods=["POST"])
def importar():
    archivo = request.files.get("archivo")
    if archivo:
        datos = json.load(archivo)
        database.importar_datos(datos.get("carpetas", []), datos.get("marcadores", []))
        registrar_log(f"Importación completada: {len(datos.get('marcadores', []))} marcadores importados")
    return redirect(url_for("marcadores.home"))

@marcadores_bp.route("/configuracion/borrar_todo", methods=["POST"])
def borrar_todo_ruta():
    if not esta_desbloqueado():
        registrar_log("Intento de borrado total sin desbloqueo crítico - bloqueado")
        return redirect(url_for("marcadores.configuracion"))
    database.borrar_todo()
    registrar_log("⚠️ Base de datos borrada por completo")
    return redirect(url_for("marcadores.configuracion", guardado=1))

@marcadores_bp.route("/progreso/<int:id_marcador>/<accion>", methods=["POST"])
def progreso(id_marcador, accion):
    if accion == "sumar":
        delta = 1
    elif accion == "restar":
        delta = -1
    else:
        return redirect(request.referrer or url_for("marcadores.home"))

    database.actualizar_progreso(id_marcador, delta)
    registrar_log(f"Progreso de marcador {id_marcador} ajustado ({accion})")
    return redirect(request.referrer or url_for("marcadores.home"))
