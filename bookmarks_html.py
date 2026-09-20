"""
==============================================================================
PBM PRIVATE BOOKMARK MANAGER - MOTOR DE IMPORTACIÓN/EXPORTACIÓN HTML
==============================================================================
Parser y generador de archivos HTML en formato estándar Netscape Bookmark File 1.
Capacidades:
1. Importación jerárquica de carpetas y enlaces respetando anidamientos.
2. Detección inteligente de contenedores de navegadores comerciales (Chrome,
   Edge, Brave, Firefox): aplana 'Barra de favoritos' colocándola en la raíz.
3. Exportación universal compatible con importadores de todos los navegadores.
==============================================================================
"""

from html.parser import HTMLParser


class _ImportadorBookmarks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.carpetas_data = []
        self.marcadores_data = []
        self.contador_id = 1
        self.pila_carpetas = [None]
        self.carpeta_pendiente = None
        self.modo = None
        self.buffer = ""
        self.href_actual = None
        self.attrs_h3_actual = {}

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        tag_lower = tag.lower()

        if tag_lower == "dl":
            # Apila la carpeta recién detectada como padre activo
            self.pila_carpetas.append(self.carpeta_pendiente)
            self.carpeta_pendiente = None
        elif tag_lower == "h3":
            self.modo = "h3"
            self.buffer = ""
            self.attrs_h3_actual = {k.lower(): str(v).lower() for k, v in attrs}
        elif tag_lower == "a":
            self.modo = "a"
            self.buffer = ""
            self.href_actual = attrs_dict.get("href", "").strip()

    def handle_data(self, data):
        if self.modo in ("h3", "a"):
            self.buffer += data

    def handle_endtag(self, tag):
        tag_lower = tag.lower()

        if tag_lower == "dl":
            if len(self.pila_carpetas) > 1:
                self.pila_carpetas.pop()

        elif tag_lower == "h3":
            nombre = self.buffer.strip() or "Carpeta sin nombre"
            padre_id = self.pila_carpetas[-1]

            # Detección de contenedores de barra del navegador
            es_toolbar_attr = (
                self.attrs_h3_actual.get("personal_toolbar_folder") == "true" or
                self.attrs_h3_actual.get("toolbar_folder") == "true"
            )
            es_nombre_barra = nombre.lower() in [
                "barra de favoritos",
                "bookmarks bar",
                "bookmarks toolbar",
                "barra de marcadores",
                "bookmarks menu",
                "menú de marcadores"
            ]

            # Si es la barra del navegador en la raíz (padre_id is None), la aplanamos
            if padre_id is None and (es_toolbar_attr or es_nombre_barra):
                # No creamos la carpeta: sus hijos se ubicarán directamente en la raíz (None)
                self.carpeta_pendiente = None
            else:
                nueva_id = self.contador_id
                self.contador_id += 1
                self.carpetas_data.append({
                    "id": nueva_id,
                    "nombre": nombre,
                    "carpeta_padre_id": padre_id
                })
                self.carpeta_pendiente = nueva_id

            self.modo = None
            self.buffer = ""
            self.attrs_h3_actual = {}

        elif tag_lower == "a":
            titulo = self.buffer.strip() or self.href_actual or "Sin título"
            if self.href_actual:
                self.marcadores_data.append({
                    "titulo": titulo,
                    "url": self.href_actual,
                    "carpeta_id": self.pila_carpetas[-1],
                    "nota": None,
                    "progreso": 0
                })
            self.modo = None
            self.buffer = ""
            self.href_actual = None


def importar_html(contenido_html):
    """Parsea el HTML de marcadores devolviendo listas de carpetas y marcadores."""
    parser = _ImportadorBookmarks()
    parser.feed(contenido_html)
    return parser.carpetas_data, parser.marcadores_data


def exportar_html(carpetas, marcadores):
    """Genera archivo HTML estándar Netscape con jerarquía completa."""
    lineas = [
        "<!DOCTYPE NETSCAPE-Bookmark-file-1>",
        "<!-- This is an automatically generated file. -->",
        '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
        "<TITLE>Bookmarks</TITLE>",
        "<H1>Bookmarks</H1>",
        "<DL><p>"
    ]

    marcadores_por_carpeta = {}
    for m in marcadores:
        c_id = m.get("carpeta_id")
        marcadores_por_carpeta.setdefault(c_id, []).append(m)

    carpetas_por_padre = {}
    for c in carpetas:
        p_id = c.get("carpeta_padre_id")
        carpetas_por_padre.setdefault(p_id, []).append(c)

    def escribir_nivel(padre_id, indent="    "):
        # 1. Marcadores en este nivel
        for m in marcadores_por_carpeta.get(padre_id, []):
            url = m.get("url", "")
            titulo = m.get("titulo", url)
            lineas.append(f'{indent}<DT><A HREF="{url}">{titulo}</A>')

        # 2. Subcarpetas en este nivel
        for c in carpetas_por_padre.get(padre_id, []):
            c_id = c["id"]
            nombre = c["nombre"]
            lineas.append(f'{indent}<DT><H3>{nombre}</H3>')
            lineas.append(f'{indent}<DL><p>')
            escribir_nivel(c_id, indent + "    ")
            lineas.append(f'{indent}</DL><p>')

    escribir_nivel(None)
    lineas.append("</DL><p>")
    return "\n".join(lineas)