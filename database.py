"""
==============================================================================
PBM PRIVATE BOOKMARK MANAGER - CAPA DE PERSISTENCIA Y MODELO (DATABASE.PY)
==============================================================================
Controlador de persistencia relacional en SQLite para marcadores y carpetas.
Responsabilidades:
1. Creación e inicialización del esquema de datos relacional.
2. Gestión transaccional segura con liberación garantizada (try...finally).
3. CRUD de carpetas (anidadas, edición, conteo, borrado condicional y traslados).
4. Algoritmo de detección y prevención de ciclos en el árbol de carpetas.
5. CRUD de marcadores (inclusión de notas, progreso y movimiento/borrado en lote).
6. Motor de importación jerárquica con reconstrucción de IDs foráneos.
==============================================================================
"""

import sqlite3

DB_NAME = "marcadores.db"


def get_conexion():
    """
    Establece la conexión con la base de datos local activando
    la fábrica de filas (Row) para acceso por clave de columna.
    """
    conexion = sqlite3.connect(DB_NAME, timeout=5.0)
    conexion.row_factory = sqlite3.Row
    return conexion

# Alias de compatibilidad para evitar discrepancias entre módulos
obtener_conexion = get_conexion


def inicializar_db():
    """
    Crea las tablas relacionales indispensables si no existen en el archivo SQLite.
    Garantiza índices y esquemas base para arranque en frío.
    """
    conexion = get_conexion()
    try:
        # Tabla de carpetas con soporte para jerarquías anidadas
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS carpetas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                carpeta_padre_id INTEGER,
                FOREIGN KEY (carpeta_padre_id) REFERENCES carpetas(id)
            )
        """)

        # Tabla de marcadores con campos de texto enriquecido y avance de lectura
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
    finally:
        conexion.close()


# ==============================================================================
# SECCIÓN 1: OPERACIONES DE CARPETAS (CRUD & MOVIMIENTOS SEGUROS)
# ==============================================================================

def obtener_carpeta(carpeta_id):
    """Obtiene los datos de una carpeta específica mediante su identificador."""
    if carpeta_id is None:
        return None
    conexion = get_conexion()
    try:
        return conexion.execute("SELECT * FROM carpetas WHERE id = ?", (carpeta_id,)).fetchone()
    finally:
        conexion.close()


def obtener_subcarpetas(carpeta_padre_id):
    """Retorna las subcarpetas inmediatas contenidas dentro de una carpeta padre o la raíz."""
    conexion = get_conexion()
    try:
        if carpeta_padre_id is None:
            return conexion.execute("SELECT * FROM carpetas WHERE carpeta_padre_id IS NULL ORDER BY nombre COLLATE NOCASE ASC").fetchall()
        else:
            return conexion.execute("SELECT * FROM carpetas WHERE carpeta_padre_id = ? ORDER BY nombre COLLATE NOCASE ASC", (carpeta_padre_id,)).fetchall()
    finally:
        conexion.close()


def crear_carpeta(nombre, carpeta_padre_id):
    """Registra una nueva carpeta en la raíz o como subdirectorio."""
    conexion = get_conexion()
    try:
        conexion.execute("INSERT INTO carpetas (nombre, carpeta_padre_id) VALUES (?, ?)", (nombre, carpeta_padre_id))
        conexion.commit()
    finally:
        conexion.close()


def es_subcarpeta_de(posible_hijo_id, padre_id):
    """
    Algoritmo de prevención de ciclos: comprueba si 'posible_hijo_id' desciende de 'padre_id'.
    Evita que una carpeta sea movida dentro de sí misma o dentro de sus carpetas descendientes.
    """
    if posible_hijo_id is None or padre_id is None:
        return False
    if posible_hijo_id == padre_id:
        return True

    actual = posible_hijo_id
    conexion = get_conexion()
    try:
        visitados = set()
        while actual is not None:
            if actual == padre_id:
                return True
            if actual in visitados:
                break
            visitados.add(actual)
            row = conexion.execute("SELECT carpeta_padre_id FROM carpetas WHERE id = ?", (actual,)).fetchone()
            actual = row["carpeta_padre_id"] if row else None
        return False
    finally:
        conexion.close()


def mover_carpeta(carpeta_id, nueva_carpeta_padre_id):
    """
    Reubica una carpeta validando que no genere bucles infinitos en la jerarquía.
    Devuelve True si el movimiento fue exitoso, o False si fue bloqueado por seguridad.
    """
    if nueva_carpeta_padre_id is not None:
        nueva_carpeta_padre_id = int(nueva_carpeta_padre_id)
        if nueva_carpeta_padre_id == carpeta_id:
            return False
        if es_subcarpeta_de(nueva_carpeta_padre_id, carpeta_id):
            return False

    conexion = get_conexion()
    try:
        conexion.execute(
            "UPDATE carpetas SET carpeta_padre_id = ? WHERE id = ?",
            (nueva_carpeta_padre_id, carpeta_id)
        )
        conexion.commit()
        return True
    finally:
        conexion.close()


def mover_carpetas_lote(ids_carpetas, nueva_carpeta_padre_id):
    """
    Traslada múltiples carpetas al destino indicado filtrando automáticamente
    aquellas que generarían ciclos circulares. Retorna la cantidad de carpetas movidas.
    """
    if not ids_carpetas:
        return 0

    ids_validos = [int(i) for i in ids_carpetas if str(i).isdigit()]
    if not ids_validos:
        return 0

    movidas = 0
    for c_id in ids_validos:
        if mover_carpeta(c_id, nueva_carpeta_padre_id):
            movidas += 1
    return movidas


def editar_carpeta(carpeta_id, nombre, nueva_carpeta_padre_id="NO_MODIFICAR"):
    """
    Actualiza el nombre de una carpeta y, opcionalmente, traslada su posición
    en el árbol respetando las restricciones de integridad jerárquica.
    """
    conexion = get_conexion()
    try:
        conexion.execute("UPDATE carpetas SET nombre = ? WHERE id = ?", (nombre, carpeta_id))
        conexion.commit()
    finally:
        conexion.close()

    if nueva_carpeta_padre_id != "NO_MODIFICAR":
        mover_carpeta(carpeta_id, nueva_carpeta_padre_id)


def eliminar_carpeta(carpeta_id, borrar_contenido=False):
    """
    Elimina una carpeta de la base de datos:
    - Si borrar_contenido es True: elimina físicamente todos los marcadores dentro de ella.
    - Si borrar_contenido es False: preserva los marcadores moviéndolos a la raíz (carpeta_id = NULL).
    - Las subcarpetas dependientes se desvinculan a la raíz para evitar estructuras huérfanas.
    """
    conexion = get_conexion()
    try:
        if borrar_contenido:
            conexion.execute("DELETE FROM marcadores WHERE carpeta_id = ?", (carpeta_id,))
        else:
            conexion.execute("UPDATE marcadores SET carpeta_id = NULL WHERE carpeta_id = ?", (carpeta_id,))

        conexion.execute("UPDATE carpetas SET carpeta_padre_id = NULL WHERE carpeta_padre_id = ?", (carpeta_id,))
        conexion.execute("DELETE FROM carpetas WHERE id = ?", (carpeta_id,))
        conexion.commit()
    finally:
        conexion.close()


def contar_contenido_carpeta(carpeta_id):
    """Devuelve la cantidad de marcadores alojados dentro de una carpeta."""
    conexion = get_conexion()
    try:
        res = conexion.execute("SELECT COUNT(*) FROM marcadores WHERE carpeta_id = ?", (carpeta_id,)).fetchone()
        return res[0] if res else 0
    finally:
        conexion.close()


def obtener_todas_las_carpetas():
    """Devuelve el catálogo completo de carpetas ordenadas alfabéticamente."""
    conexion = get_conexion()
    try:
        return conexion.execute("SELECT * FROM carpetas ORDER BY nombre COLLATE NOCASE ASC").fetchall()
    finally:
        conexion.close()


# ==============================================================================
# SECCIÓN 2: OPERACIONES DE MARCADORES
# ==============================================================================

def obtener_marcadores(carpeta_id=None):
    """Obtiene los marcadores que pertenecen a una carpeta puntual o a la raíz."""
    conexion = get_conexion()
    try:
        if carpeta_id is None:
            return conexion.execute("SELECT * FROM marcadores WHERE carpeta_id IS NULL ORDER BY id DESC").fetchall()
        else:
            return conexion.execute("SELECT * FROM marcadores WHERE carpeta_id = ? ORDER BY id DESC", (carpeta_id,)).fetchall()
    finally:
        conexion.close()


def obtener_marcador(id_marcador):
    """Recupera un marcador individual por su ID primario."""
    conexion = get_conexion()
    try:
        return conexion.execute("SELECT * FROM marcadores WHERE id = ?", (id_marcador,)).fetchone()
    finally:
        conexion.close()


def obtener_todos_los_marcadores():
    """Recupera todos los marcadores del sistema asociando el nombre de su carpeta contenedora."""
    conexion = get_conexion()
    try:
        return conexion.execute("""
            SELECT marcadores.*, carpetas.nombre AS carpeta_nombre
            FROM marcadores
            LEFT JOIN carpetas ON marcadores.carpeta_id = carpetas.id
            ORDER BY carpetas.nombre IS NULL, carpetas.nombre COLLATE NOCASE ASC, marcadores.titulo COLLATE NOCASE ASC
        """).fetchall()
    finally:
        conexion.close()


def agregar_marcador(titulo, url, carpeta_id=None, nota=None, progreso=0):
    """Registra un nuevo marcador con soporte completo de metadatos."""
    conexion = get_conexion()
    try:
        conexion.execute(
            "INSERT INTO marcadores (titulo, url, carpeta_id, nota, progreso) VALUES (?, ?, ?, ?, ?)",
            (titulo, url, carpeta_id, nota, progreso)
        )
        conexion.commit()
    finally:
        conexion.close()


def editar_marcador(id_marcador, titulo, url, carpeta_id=None, nota=None, progreso=0):
    """Actualiza la información de un marcador existente."""
    conexion = get_conexion()
    try:
        conexion.execute(
            "UPDATE marcadores SET titulo = ?, url = ?, carpeta_id = ?, nota = ?, progreso = ? WHERE id = ?",
            (titulo, url, carpeta_id, nota, progreso, id_marcador)
        )
        conexion.commit()
    finally:
        conexion.close()


def mover_marcador(id_marcador, nueva_carpeta_id):
    """Traslada un marcador individual a una carpeta de destino o a la raíz."""
    conexion = get_conexion()
    try:
        conexion.execute("UPDATE marcadores SET carpeta_id = ? WHERE id = ?", (nueva_carpeta_id, id_marcador))
        conexion.commit()
    finally:
        conexion.close()


def mover_marcadores_lote(ids_marcadores, nueva_carpeta_id):
    """
    Mueve una lista de marcadores a la carpeta indicada en una sola transacción atómica.
    Retorna el total de registros actualizados.
    """
    if not ids_marcadores:
        return 0

    ids_validos = [int(i) for i in ids_marcadores if str(i).isdigit()]
    if not ids_validos:
        return 0

    conexion = get_conexion()
    try:
        placeholders = ",".join("?" for _ in ids_validos)
        params = [nueva_carpeta_id] + ids_validos
        cursor = conexion.execute(
            f"UPDATE marcadores SET carpeta_id = ? WHERE id IN ({placeholders})",
            params
        )
        conexion.commit()
        return cursor.rowcount
    finally:
        conexion.close()


def eliminar_marcador(id_marcador):
    """Elimina físicamente un marcador de la base de datos."""
    conexion = get_conexion()
    try:
        conexion.execute("DELETE FROM marcadores WHERE id = ?", (id_marcador,))
        conexion.commit()
    finally:
        conexion.close()


def eliminar_marcadores_lote(ids_marcadores):
    """Elimina físicamente una lista de marcadores en una sola transacción."""
    if not ids_marcadores:
        return 0

    ids_validos = [int(i) for i in ids_marcadores if str(i).isdigit()]
    if not ids_validos:
        return 0

    conexion = get_conexion()
    try:
        placeholders = ",".join("?" for _ in ids_validos)
        cursor = conexion.execute(
            f"DELETE FROM marcadores WHERE id IN ({placeholders})",
            ids_validos
        )
        conexion.commit()
        return cursor.rowcount
    finally:
        conexion.close()


def actualizar_progreso(id_marcador, delta):
    """Incrementa o decrementa el contador numérico de un marcador asegurando que no sea menor a 0."""
    conexion = get_conexion()
    try:
        conexion.execute(
            "UPDATE marcadores SET progreso = MAX(0, progreso + ?) WHERE id = ?",
            (delta, id_marcador)
        )
        conexion.commit()
    finally:
        conexion.close()


def buscar_marcadores(texto):
    """Busca coincidencias parciales por título o URL en todos los marcadores."""
    conexion = get_conexion()
    try:
        return conexion.execute("""
            SELECT marcadores.*, carpetas.nombre AS carpeta_nombre
            FROM marcadores
            LEFT JOIN carpetas ON marcadores.carpeta_id = carpetas.id
            WHERE marcadores.titulo LIKE ? OR marcadores.url LIKE ?
            ORDER BY marcadores.id DESC
        """, (f"%{texto}%", f"%{texto}%")).fetchall()
    finally:
        conexion.close()


# ==============================================================================
# SECCIÓN 3: GESTIÓN DE MIGRACIÓN Y LIMPIEZA
# ==============================================================================

def importar_datos(carpetas_data, marcadores_data):
    """
    Restaura colecciones de carpetas y marcadores resolviendo
    y asignando las relaciones padre-hijo generadas dinámicamente.
    """
    conexion = get_conexion()
    try:
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
    finally:
        conexion.close()


def borrar_todo():
    """Reinicia la base de datos eliminando tablas y regenerándolas limpias."""
    conexion = get_conexion()
    try:
        conexion.execute("DROP TABLE IF EXISTS marcadores")
        conexion.execute("DROP TABLE IF EXISTS carpetas")
        conexion.commit()
    finally:
        conexion.close()
    inicializar_db()