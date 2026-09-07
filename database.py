import sqlite3

DB_NAME = "marcadores.db"

def get_conexion():
    conexion = sqlite3.connect(DB_NAME)
    conexion.row_factory = sqlite3.Row
    return conexion

def inicializar_db():
    conexion = get_conexion()
    # Tabla de carpetas (necesaria para las relaciones)
    conexion.execute("""
        CREATE TABLE IF NOT EXISTS carpetas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            carpeta_padre_id INTEGER,
            FOREIGN KEY (carpeta_padre_id) REFERENCES carpetas(id)
        )
    """)
    # Tabla de marcadores con las nuevas columnas: nota y progreso
    conexion.execute("""
        CREATE TABLE IF NOT EXISTS marcadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            url TEXT NOT NULL,
            carpeta_id INTEGER,
            nota TEXT,
            progreso INTEGER DEFAULT 0,
            FOREIGN KEY (carpeta_id) REFERENCES carpetas(id)
        )
    """)
    conexion.commit()
    conexion.close()

# ---- Carpetas ----
def obtener_carpeta(carpeta_id):
    if carpeta_id is None:
        return None
    conexion = get_conexion()
    carpeta = conexion.execute("SELECT * FROM carpetas WHERE id = ?", (carpeta_id,)).fetchone()
    conexion.close()
    return carpeta

def obtener_subcarpetas(carpeta_padre_id):
    conexion = get_conexion()
    if carpeta_padre_id is None:
        datos = conexion.execute("SELECT * FROM carpetas WHERE carpeta_padre_id IS NULL ORDER BY nombre").fetchall()
    else:
        datos = conexion.execute("SELECT * FROM carpetas WHERE carpeta_padre_id = ? ORDER BY nombre", (carpeta_padre_id,)).fetchall()
    conexion.close()
    return datos

def crear_carpeta(nombre, carpeta_padre_id):
    conexion = get_conexion()
    conexion.execute("INSERT INTO carpetas (nombre, carpeta_padre_id) VALUES (?, ?)", (nombre, carpeta_padre_id))
    conexion.commit()
    conexion.close()

def eliminar_carpeta(carpeta_id):
    conexion = get_conexion()
    conexion.execute("UPDATE marcadores SET carpeta_id = NULL WHERE carpeta_id = ?", (carpeta_id,))
    conexion.execute("UPDATE carpetas SET carpeta_padre_id = NULL WHERE carpeta_padre_id = ?", (carpeta_id,))
    conexion.execute("DELETE FROM carpetas WHERE id = ?", (carpeta_id,))
    conexion.commit()
    conexion.close()

# ---- Marcadores ----
def obtener_marcadores(carpeta_id=None):
    conexion = get_conexion()
    if carpeta_id is None:
        datos = conexion.execute("SELECT * FROM marcadores WHERE carpeta_id IS NULL ORDER BY id DESC").fetchall()
    else:
        datos = conexion.execute("SELECT * FROM marcadores WHERE carpeta_id = ? ORDER BY id DESC", (carpeta_id,)).fetchall()
    conexion.close()
    return datos

def agregar_marcador(titulo, url, carpeta_id=None, nota=None):
    conexion = get_conexion()
    conexion.execute(
        "INSERT INTO marcadores (titulo, url, carpeta_id, nota) VALUES (?, ?, ?, ?)",
        (titulo, url, carpeta_id, nota)
    )
    conexion.commit()
    conexion.close()

def eliminar_marcador(id_marcador):
    conexion = get_conexion()
    conexion.execute("DELETE FROM marcadores WHERE id = ?", (id_marcador,))
    conexion.commit()
    conexion.close()

def buscar_marcadores(texto):
    conexion = get_conexion()
    datos = conexion.execute("""
        SELECT marcadores.*, carpetas.nombre AS carpeta_nombre
        FROM marcadores
        LEFT JOIN carpetas ON marcadores.carpeta_id = carpetas.id
        WHERE marcadores.titulo LIKE ?
        ORDER BY marcadores.id DESC
    """, (f"%{texto}%",)).fetchall()
    conexion.close()
    return datos

def obtener_todas_las_carpetas():
    conexion = get_conexion()
    datos = conexion.execute("SELECT * FROM carpetas ORDER BY nombre").fetchall()
    conexion.close()
    return datos

def mover_marcador(id_marcador, nueva_carpeta_id):
    conexion = get_conexion()
    conexion.execute("UPDATE marcadores SET carpeta_id = ? WHERE id = ?", (nueva_carpeta_id, id_marcador))
    conexion.commit()
    conexion.close()

def obtener_marcador(id_marcador):
    conexion = get_conexion()
    marcador = conexion.execute("SELECT * FROM marcadores WHERE id = ?", (id_marcador,)).fetchone()
    conexion.close()
    return marcador

def editar_marcador(id_marcador, titulo, url, carpeta_id=None, nota=None, progreso=0):
    conexion = get_conexion()
    conexion.execute(
        "UPDATE marcadores SET titulo = ?, url = ?, carpeta_id = ?, nota = ?, progreso = ? WHERE id = ?",
        (titulo, url, carpeta_id, nota, progreso, id_marcador)
    )
    conexion.commit()
    conexion.close()

def editar_carpeta(carpeta_id, nombre):
    conexion = get_conexion()
    conexion.execute("UPDATE carpetas SET nombre = ? WHERE id = ?", (nombre, carpeta_id))
    conexion.commit()
    conexion.close()

def obtener_todos_los_marcadores():
    conexion = get_conexion()
    datos = conexion.execute("""
        SELECT marcadores.*, carpetas.nombre AS carpeta_nombre
        FROM marcadores
        LEFT JOIN carpetas ON marcadores.carpeta_id = carpetas.id
        ORDER BY carpetas.nombre IS NULL, carpetas.nombre, marcadores.titulo
    """).fetchall()
    conexion.close()
    return datos

def importar_datos(carpetas_data, marcadores_data):
    conexion = get_conexion()
    mapa_ids = {}

    pendientes = list(carpetas_data)
    while pendientes:
        progreso = False
        restantes = []
        for c in pendientes:
            padre_viejo = c.get("carpeta_padre_id")
            if padre_viejo is None or padre_viejo in mapa_ids:
                nuevo_padre = mapa_ids.get(padre_viejo) if padre_viejo else None
                cursor = conexion.execute(
                    "INSERT INTO carpetas (nombre, carpeta_padre_id) VALUES (?, ?)",
                    (c["nombre"], nuevo_padre)
                )
                mapa_ids[c["id"]] = cursor.lastrowid
                progreso = True
            else:
                restantes.append(c)
        if not progreso:
            break
        pendientes = restantes

    for m in marcadores_data:
        carpeta_vieja = m.get("carpeta_id")
        nueva_carpeta = mapa_ids.get(carpeta_vieja) if carpeta_vieja else None
        conexion.execute(
            "INSERT INTO marcadores (titulo, url, carpeta_id, nota, progreso) VALUES (?, ?, ?, ?, ?)",
            (m["titulo"], m["url"], nueva_carpeta, m.get("nota"), m.get("progreso", 0))
        )

    conexion.commit()
    conexion.close()

def borrar_todo():
    conexion = get_conexion()
    conexion.execute("DROP TABLE IF EXISTS marcadores")
    conexion.execute("DROP TABLE IF EXISTS carpetas")
    conexion.commit()
    conexion.close()
    inicializar_db()

def actualizar_progreso(id_marcador, delta):
    conexion = get_conexion()
    conexion.execute(
        "UPDATE marcadores SET progreso = MAX(0, progreso + ?) WHERE id = ?",
        (delta, id_marcador)
    )
    conexion.commit()
    conexion.close()