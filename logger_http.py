"""
==============================================================================
PBM PRIVATE BOOKMARK MANAGER - TRADUCTOR Y FORMATEADOR DE PETICIONES HTTP
==============================================================================
Módulo encargado de silenciar los registros crudos de Werkzeug e imprimir 
cada petición con descripciones claras en palabras, íconos y colores ANSI.
==============================================================================
"""

import os
import logging
from datetime import datetime
from flask import request

# Paleta ANSI de alta visibilidad para terminales oscuras
CLR_RESET    = "\033[0m"
CLR_GRIS     = "\033[90m"
CLR_AZUL     = "\033[94m"
CLR_CYAN     = "\033[96m"
CLR_VERDE    = "\033[92m"
CLR_AMARILLO = "\033[93m"
CLR_ROJO     = "\033[91m"
CLR_MAGENTA  = "\033[95m"
CLR_BOLD     = "\033[1m"

# Diccionario traductor de códigos de estado HTTP a descripciones en lenguaje claro
ESTADOS_TRADUCIDOS = {
    200: "Éxito (Recurso entregado)",
    201: "Creado exitosamente",
    204: "Sin contenido (Acción completada)",
    301: "Redirección permanente",
    302: "Redirección temporal",
    304: "Caché del navegador (Sin cambios)",
    400: "Petición incorrecta o inválida",
    401: "No autorizado (Requiere sesión)",
    403: "Acceso prohibido",
    404: "Recurso no encontrado",
    405: "Método HTTP no permitido",
    413: "Archivo demasiado pesado (Límite excedido)",
    500: "Error interno del servidor",
    502: "Puerta de enlace incorrecta",
    503: "Servicio no disponible"
}

def color_por_codigo(codigo):
    """Asigna un color ANSI representativo según el rango de código HTTP."""
    if 200 <= codigo < 300:
        return CLR_VERDE
    elif 300 <= codigo < 400:
        return CLR_CYAN
    elif 400 <= codigo < 500:
        return CLR_AMARILLO
    else:
        return CLR_ROJO

def configurar_logger_http(app):
    """
    Silencia los registros por defecto de Werkzeug y registra el interceptor amigable.
    """
    # Silenciar las trazas crudas de Werkzeug
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    @app.after_request
    def interceptar_y_formatear(response):
        # Solo emitir registros si LOG_MODE está activo en el entorno
        if os.environ.get("LOG_MODE", "false").strip().lower() != "true":
            return response

        codigo = response.status_code
        color_cod = color_por_codigo(codigo)
        mensaje_estado = ESTADOS_TRADUCIDOS.get(codigo, f"Código {codigo}")
        hora = datetime.now().strftime("%H:%M:%S")

        # Clasificación visual del recurso solicitado adaptada a la estructura de PBM
        ruta = request.path
        if ruta.endswith(".css") or "/css/" in ruta:
            etiqueta = f"{CLR_MAGENTA}🎨 [CSS]{CLR_RESET}"
        elif ruta.endswith(".js") or "/js/" in ruta:
            etiqueta = f"{CLR_AMARILLO}⚡ [JS]{CLR_RESET}"
        elif ruta.endswith((".svg", ".ico", ".png", ".jpg", ".jpeg", ".webp")):
            etiqueta = f"{CLR_CYAN}🖼️  [ICON]{CLR_RESET}"
        elif ruta.startswith("/static/"):
            etiqueta = f"{CLR_GRIS}📁 [ASSET]{CLR_RESET}"
        elif request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            etiqueta = f"{CLR_CYAN}🔄 [API/AJAX]{CLR_RESET}"
        else:
            etiqueta = f"{CLR_AZUL}🌐 [PÁGINA]{CLR_RESET}"

        # Salida formateada con espacio limpio tras la flecha
        print(
            f"{CLR_GRIS}[{hora}]{CLR_RESET} {etiqueta} "
            f"{CLR_BOLD}{request.method:<6}{CLR_RESET} {ruta:<32} ➜ "
            f" {color_cod}{mensaje_estado} ({codigo}){CLR_RESET}"
        )

        return response