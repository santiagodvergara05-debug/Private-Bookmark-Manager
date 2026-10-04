"""
==============================================================================
PBM PRIVATE BOOKMARK MANAGER - CONSOLA DE ADMINISTRACIÓN FUERA DE BANDA
==============================================================================
Panel administrativo de consola (Gen 3).
Permite gestionar parámetros críticos del archivo .env, llaves criptográficas,
sincronización BYOC E2EE, preferencias de usuario y mantenimiento del sistema.
==============================================================================
"""

import os
import sys
import glob
import json
import secrets
import sqlite3
import shutil
from datetime import datetime
from dotenv import load_dotenv, dotenv_values, set_key

# Detección de entorno ejecutable PyInstaller vs Desarrollo
ES_EXE = getattr(sys, "frozen", False)
if ES_EXE:
    DIRECTORIO_RAIZ = os.path.dirname(sys.executable)
else:
    DIRECTORIO_RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(DIRECTORIO_RAIZ)

# Rutas principales del sistema
ENV_PATH = os.path.join(DIRECTORIO_RAIZ, ".env")
DB_PATH = os.path.join(DIRECTORIO_RAIZ, "marcadores.db")
RUTA_ULTIMO_BACKUP = os.path.join(DIRECTORIO_RAIZ, "ultimo_backup.txt")
RUTA_SILENCIAR_BACKUP = os.path.join(DIRECTORIO_RAIZ, "silenciar_backup.txt")
RUTA_ULTIMO_SYNC = os.path.join(DIRECTORIO_RAIZ, "ultimo_sync.txt")
CARPETA_BACKUPS = os.path.join(DIRECTORIO_RAIZ, "backups")

try:
    from version import VERSION
except ImportError:
    VERSION = "3.2.0"

VAULT_META_NAME = "pbm_vault.meta"


# ==============================================================================
# UTILIDADES VISUALES Y FORMATO
# ==============================================================================

def limpiar_pantalla():
    os.system("cls" if os.name == "nt" else "clear")


def colorear(texto, color):
    if not sys.stdout.isatty():
        return texto
    colores = {
        "verde": "\033[92m",
        "amarillo": "\033[93m",
        "rojo": "\033[91m",
        "azul": "\033[94m",
        "cyan": "\033[96m",
        "morado": "\033[95m",
        "bold": "\033[1m",
        "reset": "\033[0m"
    }
    return f"{colores.get(color, '')}{texto}{colores['reset']}"


def formatear_bytes(b):
    if b < 1024:
        return f"{b} B"
    elif b < 1024 * 1024:
        return f"{b / 1024:.1f} KB"
    return f"{b / (1024 * 1024):.2f} MB"


def pausar():
    input(f"\n{colorear('Presione ENTER para continuar...', 'bold')}")


def verificar_entorno():
    """Valida la presencia del archivo de configuración antes de operar."""
    if not os.path.exists(ENV_PATH):
        limpiar_pantalla()
        print("=" * 70)
        print(colorear(" [!] ERROR: ARCHIVO DE CONFIGURACIÓN (.env) NO DETECTADO", "rojo"))
        print("=" * 70)
        print(" La consola administrativa no puede operar sin un archivo .env base.")
        print(" Inicie el servidor principal (app.py) al menos una vez para")
        print(" aprovisionar las variables de fábrica y la base de datos.")
        print("=" * 70)
        input("\nPresione ENTER para salir...")
        sys.exit(1)


# ==============================================================================
# TELEMETRÍA Y CONSULTAS AL SISTEMA
# ==============================================================================

def obtener_resumen_db():
    if not os.path.exists(DB_PATH):
        return colorear("Ausente (No inicializada)", "amarillo")
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=2.0)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM carpetas")
        n_carp = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM marcadores")
        n_marc = cur.fetchone()[0]
        return f"{n_carp} carpetas | {n_marc} marcadores"
    except sqlite3.OperationalError as e:
        if "locked" in str(e).lower():
            return colorear("Bloqueada (En uso por el servidor)", "amarillo")
        return colorear("Estructura dañada", "rojo")
    except Exception:
        return colorear("Ilegible / Corrupta", "rojo")
    finally:
        if conn:
            conn.close()


def obtener_conteo_cuarentena():
    patrones = [
        os.path.join(DIRECTORIO_RAIZ, "*.corrupt_*"),
        os.path.join(DIRECTORIO_RAIZ, ".env.corrupt_*"),
        os.path.join(DIRECTORIO_RAIZ, "marcadores.db.corrupt_*"),
        os.path.join(DIRECTORIO_RAIZ, "*.pre_sync"),
        os.path.join(DIRECTORIO_RAIZ, "*.tmp")
    ]
    archivos = set()
    for p in patrones:
        archivos.update(glob.glob(p))
    return len(archivos)


def obtener_info_disco():
    peso_db = "0 KB"
    if os.path.exists(DB_PATH):
        peso_db = formatear_bytes(os.path.getsize(DB_PATH))

    peso_backups = 0
    cant_backups = 0
    if os.path.exists(CARPETA_BACKUPS):
        for arch in os.listdir(CARPETA_BACKUPS):
            ruta_f = os.path.join(CARPETA_BACKUPS, arch)
            if os.path.isfile(ruta_f):
                cant_backups += 1
                peso_backups += os.path.getsize(ruta_f)

    cuarentena_cant = obtener_conteo_cuarentena()
    return f"DB: {peso_db} | Backups: {cant_backups} ({formatear_bytes(peso_backups)}) | Cuarentena: {cuarentena_cant}"


def obtener_info_backup():
    if os.path.exists(RUTA_ULTIMO_BACKUP):
        try:
            with open(RUTA_ULTIMO_BACKUP, "r", encoding="utf-8") as f:
                ts = float(f.read().strip())
                return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        except Exception:
            return colorear("Corrupto", "rojo")
    return "Ninguno registrado"


def obtener_info_sync():
    """Diagnostica el estado de la sincronización BYOC en tiempo real."""
    cfg = dotenv_values(ENV_PATH)
    habilitado = cfg.get("SYNC_HABILITADO", "false").strip("'\"").lower() == "true"
    carpeta = cfg.get("SYNC_CARPETA", "").strip("'\"")
    rev_local = cfg.get("SYNC_ULTIMA_REVISION", "0").strip("'\"")

    if not habilitado:
        return colorear("Desactivada (Modo local independiente)", "amarillo")

    if not carpeta or not os.path.isdir(carpeta):
        return colorear(f"Carpeta inalcanzable ({carpeta or 'No configurada'})", "rojo")

    meta_path = os.path.join(carpeta, VAULT_META_NAME)
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            rev_nube = int(meta.get("revision", 0))
            equipo = meta.get("ultimo_equipo", "Desconocido")
            
            if int(rev_local) < rev_nube:
                return colorear(f"Pendiente de descarga (Nube #{rev_nube} de '{equipo}' > Local #{rev_local})", "amarillo")
            elif int(rev_local) > rev_nube:
                return colorear(f"Local adelantado (Local #{rev_local} > Nube #{rev_nube})", "cyan")
            else:
                return colorear(f"Al día (Revisión #{rev_local} vinculada con nube)", "verde")
        except Exception:
            return colorear("Metadatos de la nube (.meta) corruptos", "rojo")
    else:
        return colorear(f"Carpeta conectada (Sin bóveda previa | Local #{rev_local})", "cyan")


# ==============================================================================
# SUBMENÚS Y ACCIONES ADMINISTRATIVAS
# ==============================================================================

def submenu_inspeccion(titulo, etiqueta, valor):
    limpiar_pantalla()
    print("=" * 70)
    print(f"       INSPECCIÓN DE CREDENCIALES :: {titulo.upper()}")
    print("=" * 70)
    print(f"\n {etiqueta}:")
    print(f" {colorear(valor, 'verde')}")
    print("\n" + "-" * 70)
    print("  1. Volver al menú principal")
    print("  2. Salir de la consola")
    print("=" * 70)

    while True:
        opc = input("Selecciona una opción [1-2]: ").strip()
        if opc == "1":
            return
        elif opc == "2":
            sys.exit(0)


def limpiar_cuarentena_cli():
    limpiar_pantalla()
    print("=" * 70)
    print("     LIMPIEZA DE CUARENTENA, SABOTAJE Y TEMPORALES DE SYNC")
    print("=" * 70)

    patrones = [
        os.path.join(DIRECTORIO_RAIZ, "*.corrupt_*"),
        os.path.join(DIRECTORIO_RAIZ, ".env.corrupt_*"),
        os.path.join(DIRECTORIO_RAIZ, "marcadores.db.corrupt_*"),
        os.path.join(DIRECTORIO_RAIZ, "*.pre_sync"),
        os.path.join(DIRECTORIO_RAIZ, "*.zip.tmp"),
        os.path.join(DIRECTORIO_RAIZ, "*.db.tmp")
    ]
    archivos = set()
    for p in patrones:
        archivos.update(glob.glob(p))

    if not archivos:
        print("\n" + colorear("[✓] No se detectaron archivos de cuarentena o temporales residuales.", "verde"))
        pausar()
        return

    print(f"\nSe detectaron {len(archivos)} archivo(s) residuales:")
    for a in sorted(archivos):
        print(f"  - {os.path.basename(a)}")

    conf = input("\n¿Desea eliminarlos permanentemente? (s/N): ").strip().lower()
    if conf == "s":
        borrados = 0
        for a in archivos:
            try:
                os.remove(a)
                borrados += 1
            except Exception as e:
                print(f"[!] Error eliminando {os.path.basename(a)}: {e}")
        print("\n" + colorear(f"[✓] Limpieza exitosa: {borrados} archivo(s) eliminados.", "verde"))
    else:
        print("\n[INFO] Operación cancelada.")

    pausar()


# ==============================================================================
# BUCLE PRINCIPAL DE ADMINISTRACIÓN
# ==============================================================================

def main():
    while True:
        verificar_entorno()
        limpiar_pantalla()
        load_dotenv(ENV_PATH, override=True)

        host = os.environ.get("HOST", "127.0.0.1")
        port = os.environ.get("PORT", "5050")
        debug = "Sí" if os.environ.get("FLASK_DEBUG", "false").lower() == "true" else "No"
        logs = "Sí" if os.environ.get("LOG_MODE", "false").lower() == "true" else "No"
        oscuro = "Sí" if os.environ.get("MODO_OSCURO", "false").lower() == "true" else "No"
        favicons = "Sí" if os.environ.get("MOSTRAR_FAVICONS", "true").lower() == "true" else "No"
        tab = "Sí" if os.environ.get("ABRIR_NUEVA_PESTANA", "true").lower() == "true" else "No"
        auto_nav = "Sí" if os.environ.get("AUTO_ABRIR_NAVEGADOR", "true").lower() == "true" else "No"
        
        cartel_login_activo = os.environ.get("CONTRASENA_MOSTRADA", "false").lower() == "false"
        estado_cartel = "Visible" if cartel_login_activo else "Oculto"
        tipo_red = "Red LAN (0.0.0.0)" if host == "0.0.0.0" else "Local (127.0.0.1)"

        print("=" * 70)
        print(f"   PANEL ADMINISTRATIVO :: PBM PrivateBookmarkManager v{colorear(VERSION, 'cyan')}")
        print("=" * 70)
        print(f" Red & Acceso:   {tipo_red} | Puerto HTTP: {port}")
        print(f" Registros DB:   {obtener_resumen_db()}")
        print(f" Disco Físico:   {obtener_info_disco()}")
        print(f" Nube BYOC:      {obtener_info_sync()}")
        print(f" Preferencias:   Debug: {debug} | Logs: {logs} | Oscuro: {oscuro} | Favicons: {favicons}")
        print(f" Navegación:     Pestaña nueva: {tab} | Auto-Nav: {auto_nav} | Cartel 1er Login: {estado_cartel}")
        print(f" Último Backup:  {obtener_info_backup()}")
        print("-" * 70)
        print(colorear(" [ GESTIÓN DE SEGURIDAD CRÍTICA & LLAVES ]", "bold"))
        print("   P. Inspeccionar contraseña web (APP_PASSWORD)")
        print("   M. Inspeccionar MASTER_KEY (para desbloqueos web)")
        print("   K. Inspeccionar SYNC_CLAVE (Clave AES-256 para vincular equipos)")
        print("   C. Alternar Cartel de Credenciales en Login (Primer inicio)")
        print("   1. Cambiar contraseña web (APP_PASSWORD)")
        print("   2. Rotar MASTER_KEY (256 bits)")
        print("   3. Rotar SECRET_KEY (Invalida sesiones web activas)")
        print("   4. Rotar SYNC_CLAVE (Nueva llave aleatoria para la nube)")
        print("   5. Rotar TODAS las llaves simultáneamente (Master, Secret, Sync)")
        print("")
        print(colorear(" [ RED, SERVIDOR & PREFERENCIAS ]", "bold"))
        print("   6. Alternar Alcance de Red (127.0.0.1 <-> 0.0.0.0)")
        print("   7. Cambiar Puerto HTTP de Escucha (PORT)")
        print("   8. Alternar Modo Depuración (FLASK_DEBUG)")
        print("   9. Alternar Registro en Consola (LOG_MODE)")
        print("  10. Alternar Auto-abrir Navegador al Iniciar (.exe)")
        print("  11. Alternar Modo Oscuro (MODO_OSCURO)")
        print("  12. Alternar Iconos de Sitios (MOSTRAR_FAVICONS)")
        print("  13. Alternar Abrir Marcador en Nueva Pestaña (ABRIR_NUEVA_PESTANA)")
        print("")
        print(colorear(" [ SINCRONIZACIÓN BYOC & REVISIONES ]", "bold"))
        print("   S. Alternar Sincronización BYOC (Habilitar/Deshabilitar)")
        print("   D. Cambiar Nombre de este Dispositivo (SYNC_NOMBRE_DISPOSITIVO)")
        print("   X. Reiniciar Contador de Revisión Local a #0 (Solo si nube limpia)")
        print("")
        print(colorear(" [ MANTENIMIENTO & HIGIENE ]", "bold"))
        print("   H. Limpiar cuarentena, sabotaje y temporales (.corrupt_*, *.tmp)")
        print("   W. RESTAURAR DE FÁBRICA (Wipe total: DB, .env, backups, cuarentena)")
        print("   0. Salir")
        print("=" * 70)

        opcion = input("\nSelecciona una opción: ").strip().lower()

        # --- INSPECCIÓN DE CLAVES ---
        if opcion == "p":
            pass_actual = os.environ.get("APP_PASSWORD", "cambiame")
            submenu_inspeccion("Contraseña de Acceso Web", "APP_PASSWORD CONFIGURADA", pass_actual)

        elif opcion == "m":
            master_actual = os.environ.get("MASTER_KEY", "No configurada")
            submenu_inspeccion("Llave Maestra", "MASTER_KEY CONFIGURADA", master_actual)

        elif opcion == "k":
            sync_actual = os.environ.get("SYNC_CLAVE", "No generada")
            submenu_inspeccion("Llave de Cifrado BYOC AES-256", "SYNC_CLAVE (Copiar exactamente a otros equipos)", sync_actual)

        elif opcion == "c":
            nuevo_estado = "true" if cartel_login_activo else "false"
            set_key(ENV_PATH, "CONTRASENA_MOSTRADA", nuevo_estado)
            os.environ["CONTRASENA_MOSTRADA"] = nuevo_estado
            msg = "Desactivado (Ya no se mostrará)" if nuevo_estado == "true" else "Activado (Se mostrará en /login)"
            print(colorear(f"\n[✓] Cartel de credenciales iniciales: {msg}", "verde"))
            pausar()

        # --- ROTACIÓN DE CLAVES ---
        elif opcion == "1":
            nueva_pass = input("\nIngrese la nueva contraseña web: ").strip()
            if nueva_pass:
                set_key(ENV_PATH, "APP_PASSWORD", nueva_pass)
                os.environ["APP_PASSWORD"] = nueva_pass
                print(colorear("\n[✓] APP_PASSWORD actualizada con éxito.", "verde"))
            else:
                print(colorear("\n[WARN] Operación cancelada: contraseña vacía.", "amarillo"))
            pausar()

        elif opcion == "2":
            nueva_master = secrets.token_hex(32)
            set_key(ENV_PATH, "MASTER_KEY", nueva_master)
            os.environ["MASTER_KEY"] = nueva_master
            print(colorear("\n[✓] MASTER_KEY regenerada exitosamente con 256 bits.", "verde"))
            pausar()

        elif opcion == "3":
            nueva_secret = secrets.token_hex(32)
            set_key(ENV_PATH, "SECRET_KEY", nueva_secret)
            os.environ["SECRET_KEY"] = nueva_secret
            print(colorear("\n[✓] SECRET_KEY regenerada. Todas las sesiones web fueron invalidadas.", "verde"))
            pausar()

        elif opcion == "4":
            nueva_sync = secrets.token_hex(32)
            set_key(ENV_PATH, "SYNC_CLAVE", nueva_sync)
            os.environ["SYNC_CLAVE"] = nueva_sync
            print(colorear("\n[✓] SYNC_CLAVE rotada exitosamente.", "verde"))
            print(colorear("    Recuerde actualizar esta clave en sus demás dispositivos.", "amarillo"))
            pausar()

        elif opcion == "5":
            conf = input("\n¿Confirmar rotación simultánea de MASTER_KEY, SECRET_KEY y SYNC_CLAVE? (s/N): ").strip().lower()
            if conf == "s":
                nueva_m = secrets.token_hex(32)
                nueva_s = secrets.token_hex(32)
                nueva_k = secrets.token_hex(32)
                set_key(ENV_PATH, "MASTER_KEY", nueva_m)
                set_key(ENV_PATH, "SECRET_KEY", nueva_s)
                set_key(ENV_PATH, "SYNC_CLAVE", nueva_k)
                os.environ["MASTER_KEY"] = nueva_m
                os.environ["SECRET_KEY"] = nueva_s
                os.environ["SYNC_CLAVE"] = nueva_k
                print(colorear("\n[✓] Todas las claves criptográficas fueron renovadas exitosamente.", "verde"))
            else:
                print("\n[INFO] Operación cancelada.")
            pausar()

        # --- RED & PREFERENCIAS ---
        elif opcion == "6":
            nuevo_host = "127.0.0.1" if host == "0.0.0.0" else "0.0.0.0"
            set_key(ENV_PATH, "HOST", nuevo_host)
            os.environ["HOST"] = nuevo_host
            print(colorear(f"\n[✓] Escucha de red cambiada a: {nuevo_host}", "verde"))
            pausar()

        elif opcion == "7":
            nuevo_puerto = input("\nIngrese el nuevo puerto HTTP (ej. 5050): ").strip()
            if nuevo_puerto.isdigit() and 1 <= int(nuevo_puerto) <= 65535:
                set_key(ENV_PATH, "PORT", nuevo_puerto)
                os.environ["PORT"] = nuevo_puerto
                print(colorear(f"\n[✓] Puerto HTTP actualizado a: {nuevo_puerto}", "verde"))
            else:
                print(colorear("\n[FAIL] Puerto inválido.", "rojo"))
            pausar()

        elif opcion == "8":
            val = "false" if debug == "Sí" else "true"
            set_key(ENV_PATH, "FLASK_DEBUG", val)
            os.environ["FLASK_DEBUG"] = val
            print(colorear(f"\n[✓] FLASK_DEBUG alternado a: {val}", "verde"))
            pausar()

        elif opcion == "9":
            val = "false" if logs == "Sí" else "true"
            set_key(ENV_PATH, "LOG_MODE", val)
            os.environ["LOG_MODE"] = val
            print(colorear(f"\n[✓] LOG_MODE alternado a: {val}", "verde"))
            pausar()

        elif opcion == "10":
            val = "false" if auto_nav == "Sí" else "true"
            set_key(ENV_PATH, "AUTO_ABRIR_NAVEGADOR", val)
            os.environ["AUTO_ABRIR_NAVEGADOR"] = val
            print(colorear(f"\n[✓] AUTO_ABRIR_NAVEGADOR alternado a: {val}", "verde"))
            pausar()

        elif opcion == "11":
            val = "false" if oscuro == "Sí" else "true"
            set_key(ENV_PATH, "MODO_OSCURO", val)
            os.environ["MODO_OSCURO"] = val
            print(colorear(f"\n[✓] MODO_OSCURO alternado a: {val}", "verde"))
            pausar()

        elif opcion == "12":
            val = "false" if favicons == "Sí" else "true"
            set_key(ENV_PATH, "MOSTRAR_FAVICONS", val)
            os.environ["MOSTRAR_FAVICONS"] = val
            print(colorear(f"\n[✓] MOSTRAR_FAVICONS alternado a: {val}", "verde"))
            pausar()

        elif opcion == "13":
            val = "false" if tab == "Sí" else "true"
            set_key(ENV_PATH, "ABRIR_NUEVA_PESTANA", val)
            os.environ["ABRIR_NUEVA_PESTANA"] = val
            print(colorear(f"\n[✓] ABRIR_NUEVA_PESTANA alternado a: {val}", "verde"))
            pausar()

        # --- SINCRONIZACIÓN BYOC ---
        elif opcion == "s":
            sync_hab = os.environ.get("SYNC_HABILITADO", "false").lower() == "true"
            nuevo_val = "false" if sync_hab else "true"
            set_key(ENV_PATH, "SYNC_HABILITADO", nuevo_val)
            os.environ["SYNC_HABILITADO"] = nuevo_val
            print(colorear(f"\n[✓] Sincronización BYOC configurada a: {nuevo_val.upper()}", "verde"))
            pausar()

        elif opcion == "d":
            nombre_actual = os.environ.get("SYNC_NOMBRE_DISPOSITIVO", "")
            nuevo_nom = input(f"\nNombre de este dispositivo (Actual: '{nombre_actual}'): ").strip()
            if nuevo_nom:
                set_key(ENV_PATH, "SYNC_NOMBRE_DISPOSITIVO", nuevo_nom)
                os.environ["SYNC_NOMBRE_DISPOSITIVO"] = nuevo_nom
                print(colorear(f"\n[✓] Identificador fijado a: '{nuevo_nom}'", "verde"))
            pausar()

        elif opcion == "x":
            carp_nube = os.environ.get("SYNC_CARPETA", "").strip()
            tiene_boveda = False
            if carp_nube and os.path.isdir(carp_nube):
                tiene_boveda = os.path.exists(os.path.join(carp_nube, VAULT_META_NAME))

            if tiene_boveda:
                print(colorear("\n[!] DENEGADO POR SEGURIDAD:", "rojo"))
                print(" Existe una bóveda activa en la nube. Para reiniciar la revisión a #0,")
                print(" debe vaciar primero la carpeta de sincronización para evitar conflictos.")
            else:
                conf = input("\n¿Reiniciar contador local SYNC_ULTIMA_REVISION a 0? (s/N): ").strip().lower()
                if conf == "s":
                    set_key(ENV_PATH, "SYNC_ULTIMA_REVISION", "0")
                    os.environ["SYNC_ULTIMA_REVISION"] = "0"
                    print(colorear("\n[✓] Contador de revisión local reiniciado a #0.", "verde"))
                else:
                    print("\n[INFO] Operación cancelada.")
            pausar()

        # --- MANTENIMIENTO ---
        elif opcion == "h":
            limpiar_cuarentena_cli()

        elif opcion == "w":
            print("\n" + colorear("!" * 70, "rojo"))
            print(colorear(" PELIGRO EXTREMO: RESTAURACIÓN TOTAL DE FÁBRICA", "rojo"))
            print(" Esta acción eliminará permanentemente:")
            print("  - Base de datos relacional (marcadores.db)")
            print("  - Archivo de configuración (.env)")
            print("  - Copias de seguridad locales y archivos en cuarentena")
            print("  - Testigos de sincronización y respaldo")
            print(colorear("!" * 70, "rojo"))
            conf = input("Escriba 'CONFIRMAR' para ejecutar el borrado total: ").strip()
            if conf == "CONFIRMAR":
                elementos_a_borrar = [DB_PATH, ENV_PATH, RUTA_ULTIMO_BACKUP, RUTA_SILENCIAR_BACKUP, RUTA_ULTIMO_SYNC]
                for f in elementos_a_borrar:
                    if os.path.exists(f):
                        try:
                            os.remove(f)
                        except Exception:
                            pass

                if os.path.exists(CARPETA_BACKUPS):
                    try:
                        shutil.rmtree(CARPETA_BACKUPS)
                    except Exception:
                        pass

                patrones_cuarentena = [
                    os.path.join(DIRECTORIO_RAIZ, "*.corrupt_*"),
                    os.path.join(DIRECTORIO_RAIZ, ".env.corrupt_*"),
                    os.path.join(DIRECTORIO_RAIZ, "marcadores.db.corrupt_*"),
                    os.path.join(DIRECTORIO_RAIZ, "*.pre_sync"),
                    os.path.join(DIRECTORIO_RAIZ, "*.tmp")
                ]
                for pat in patrones_cuarentena:
                    for arch in glob.glob(pat):
                        try:
                            os.remove(arch)
                        except Exception:
                            pass

                print(colorear("\n[✓] Sistema restaurado a estado cero de fábrica exitosamente.", "verde"))
                pausar()
                sys.exit(0)
            else:
                print("\n[INFO] Wipe total cancelado.")
                pausar()

        elif opcion == "0":
            print("\nCerrando consola de administración...")
            break


if __name__ == "__main__":
    verificar_entorno()
    main()