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

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "dl":
            self.pila_carpetas.append(self.carpeta_pendiente)
            self.carpeta_pendiente = None
        elif tag == "h3":
            self.modo = "h3"
            self.buffer = ""
        elif tag == "a":
            self.modo = "a"
            self.buffer = ""
            self.href_actual = attrs.get("href")

    def handle_endtag(self, tag):
        if tag == "dl":
            if len(self.pila_carpetas) > 1:
                self.pila_carpetas.pop()
        elif tag == "h3":
            nueva_id = self.contador_id
            self.contador_id += 1
            self.carpetas_data.append({
                "id": nueva_id,
                "nombre": self.buffer.strip(),
                "carpeta_padre_id": self.pila_carpetas[-1]
            })
            self.carpeta_pendiente = nueva_id
            self.modo = None
        elif tag == "a":
            if self.href_actual:
                self.marcadores_data.append({
                    "titulo": self.buffer.strip() or self.href_actual,
                    "url": self.href_actual,
                    "carpeta_id": self.pila_carpetas[-1],
                    "nota": None,
                    "progreso": 0
                })
            self.modo = None
            self.href_actual = None

    def handle_data(self, data):
        if self.modo in ("h3", "a"):
            self.buffer += data


def importar_html(contenido_html):
    parser = _ImportadorBookmarks()
    parser.feed(contenido_html)
    return parser.carpetas_data, parser.marcadores_data