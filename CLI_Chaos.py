"""
==============================================================================
PBM PRIVATE BOOKMARK MANAGER - SIMULADOR DE CAOS & ESTRÉS (CLI_CHAOS.PY)
==============================================================================
Herramienta de Ingeniería del Caos para pruebas de resiliencia y autorreparación:
1. Sabotaje de integridad de base de datos SQLite (Headers, B-Tree, Schema Drift).
2. Concurrencia y bloqueos exclusivos de archivos de base de datos.
3. Sabotaje binario y de red del archivo de configuración .env.
4. Inyección de caos en sincronización BYOC (Bóvedas truncadas, SHA-256, Meta).
5. Limpieza integral de cuarentena y residuos de prueba.
==============================================================================
"""

import os
import sys
import glob
import json
import sqlite3
import time
from dotenv import dotenv_values, set_key

DIRECTORIO_RAIZ = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DIRECTORIO_RAIZ, "marcadores.db")
ENV_PATH = os.path.join(DIRECTORIO_RAIZ, ".env")
BACKUPS_DIR = os.path.join(DIRECTORIO_RAIZ, "backups")
RUTA_ULTIMO_BACKUP = os.path.join(DIRECTORIO_RAIZ, "ultimo_backup.txt")
RUTA_SILENCIAR_BACKUP = os.path.join(DIRECTORIO_RAIZ, "silenciar_backup.txt")
RUTA_ULTIMO_SYNC = os.path.join(DIRECTORIO_RAIZ, "ultimo_sync.txt")

VAULT_ZIP_NAME = "pbm_vault.zip"
VAULT_META_NAME = "pbm_vault.meta"


def limpiar_pantalla():
    os.system("cls" if os.name == "nt" else "clear")


def validar_seguridad_debug():
    """Bloquea la ejecución si FLASK_DEBUG no es explícitamente 'true' en el .env."""
    if not os.path.exists(ENV_PATH):
        print("\n[-] Error crítico: Archivo .env ausente. Operación de caos cancelada.")
        sys.exit(1)

    cfg = dotenv_values(ENV_PATH)
    debug_val = cfg.get("FLASK_DEBUG", "false").strip("'\"").lower()

    if debug_val != "true":
        limpiar_pantalla()
        print("=" * 70)
        print(" [!] ACCESO RESTRINGIDO :: MODO DEBUG INACTIVO")
        print("=" * 70)
        print(" Por seguridad, el generador de caos exige FLASK_DEBUG=true en .env.")
        print(" Active el modo debug mediante CLI_admin.py o web antes de testear.")
        print(" Asegúrese de contar con respaldos de marcadores.db y .env.")
        print("=" * 70 + "\n")
        sys.exit(1)


def pausar():
    input("\nPresione ENTER para continuar...")


def obtener_carpeta_nube():
    """Obtiene la carpeta configurada en SYNC_CARPETA si existe."""
    if not os.path.exists(ENV_PATH):
        return None
    cfg = dotenv_values(ENV_PATH)
    carp = cfg.get("SYNC_CARPETA", "").strip("'\"")
    return carp if (carp and os.path.isdir(carp)) else None


# ==============================================================================
# SECCIÓN 1: VECTORES DE CAOS EN BASE DE DATOS SQLITE (MARCADORES.DB)
# ==============================================================================

def corromper_cabecera_sqlite():
    """Destruye el Magic Header de 16 bytes de SQLite ('SQLite format 3\\000')."""
    if not os.path.exists(DB_PATH):
        print("[-] 'marcadores.db' no existe.")
        pausar()
        return
    try:
        with open(DB_PATH, "r+b") as f:
            f.seek(0)
            f.write(b"CORRUPT_HEADER!!")
        print("[+] Éxito: Cabecera destruida. SQLite reportará 'file is not a database'.")
        print("    Prueba: Ejecuta 'python app.py' para verificar aislamiento y rescate.")
    except Exception as e:
        print(f"[-] Fallo al alterar cabecera: {e}")
    pausar()


def corromper_arbol_b():
    """Inyecta ruido binario en el cuerpo de datos para romper consistencia de páginas."""
    if not os.path.exists(DB_PATH):
        print("[-] 'marcadores.db' no existe.")
        pausar()
        return
    try:
        tam = os.path.getsize(DB_PATH)
        if tam < 500:
            print("[-] Base de datos demasiado pequeña para fragmentar páginas.")
            pausar()
            return
        with open(DB_PATH, "r+b") as f:
            f.seek(max(100, tam - 256))
            f.write(os.urandom(128))
        print("[+] Éxito: Ruido inyectado en B-Tree. 'PRAGMA integrity_check' fallará.")
    except Exception as e:
        print(f"[-] Fallo al inyectar ruido: {e}")
    pausar()


def romper_esquema_tablas():
    """Elimina la tabla 'carpetas' dejando la base viva (Schema Drift)."""
    if not os.path.exists(DB_PATH):
        print("[-] 'marcadores.db' no existe.")
        pausar()
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DROP TABLE IF EXISTS carpetas")
        conn.commit()
        conn.close()
        print("[+] Éxito: Tabla 'carpetas' eliminada.")
        print("    Prueba: Inicia 'python app.py' para probar la regeneración del esquema.")
    except Exception as e:
        print(f"[-] Error al eliminar tabla: {e}")
    pausar()


def bloquear_archivo_db():
    """Abre marcadores.db con bloqueo exclusivo para simular colgado de procesos."""
    if not os.path.exists(DB_PATH):
        print("[-] 'marcadores.db' no existe.")
        pausar()
        return
    print("\n[!] Bloqueando 'marcadores.db' en modo EXCLUSIVE...")
    try:
        conn = sqlite3.connect(DB_PATH, timeout=0.1)
        conn.isolation_level = "EXCLUSIVE"
        conn.execute("BEGIN EXCLUSIVE")
        print("[✓] Candado activo: Cualquier consulta de app.py lanzará 'database is locked'.")
        input("    Presione ENTER para liberar el candado y cerrar la conexión...")
        conn.rollback()
        conn.close()
        print("[+] Candado liberado exitosamente.")
    except Exception as e:
        print(f"[-] Error al bloquear base de datos: {e}")
    pausar()


def eliminar_solo_db():
    """Borra marcadores.db conservando el resto intacto."""
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print("[+] Éxito: 'marcadores.db' eliminado.")
            print("    Prueba: Si BYOC está activo, 'python app.py' ejecutará Rescate Automático.")
        except Exception as e:
            print(f"[-] Fallo al borrar: {e}")
    else:
        print("[i] 'marcadores.db' ya se encuentra ausente.")
    pausar()


# ==============================================================================
# SECCIÓN 2: VECTORES DE SABOTAJE DE CONFIGURACIÓN (.ENV)
# ==============================================================================

def sabotear_red_puerto():
    """Asigna valores fuera de rango a PORT y HOST."""
    if not os.path.exists(ENV_PATH):
        print("[-] .env ausente.")
        pausar()
        return
    set_key(ENV_PATH, "PORT", "99999")
    set_key(ENV_PATH, "HOST", "999.999.999.999")
    print("[+] Éxito: Configurado PORT=99999 y HOST=999.999.999.999 en .env.")
    print("    Prueba: 'python app.py' debe normalizar a 5050 y 127.0.0.1 con aviso [ WARN ].")
    pausar()


def vaciar_claves_seguridad():
    """Vacía SECRET_KEY y MASTER_KEY."""
    if not os.path.exists(ENV_PATH):
        print("[-] .env ausente.")
        pausar()
        return
    set_key(ENV_PATH, "SECRET_KEY", "")
    set_key(ENV_PATH, "MASTER_KEY", "")
    print("[+] Éxito: SECRET_KEY y MASTER_KEY vaciadas en .env.")
    print("    Prueba: 'python app.py' regenerará llaves criptográficas de 256 bits al arrancar.")
    pausar()


def corromper_archivo_env():
    """Sobrescribe el .env con bytes nulos no interpretables."""
    if not os.path.exists(ENV_PATH):
        print("[-] .env no existe.")
        pausar()
        return
    try:
        with open(ENV_PATH, "wb") as f:
            f.write(b"\x00\xFF\xFE\x00_CORRUPT_ENV_DATA_PBM_#@!")
        print("[+] Éxito: .env sobrescrito con datos binarios corruptos.")
        print("    Prueba: 'python app.py' aislará el archivo a .env.corrupt_* y creará uno nuevo.")
    except Exception as e:
        print(f"[-] Error: {e}")
    pausar()


# ==============================================================================
# SECCIÓN 3: VECTORES DE SINCRONIZACIÓN BYOC & INTEGRIDAD CRIPTOGRÁFICA
# ==============================================================================

def corromper_boveda_zip_nube():
    """Mutila pbm_vault.zip e incrementa revisión remota para probar candado SHA-256."""
    nube = obtener_carpeta_nube()
    if not nube:
        print("[-] SYNC_CARPETA no configurada o inaccesible.")
        pausar()
        return
    ruta_zip = os.path.join(nube, VAULT_ZIP_NAME)
    ruta_meta = os.path.join(nube, VAULT_META_NAME)
    if not os.path.exists(ruta_zip):
        print(f"[-] No se encontró '{VAULT_ZIP_NAME}' en: {nube}")
        pausar()
        return
    try:
        tam = os.path.getsize(ruta_zip)
        with open(ruta_zip, "r+b") as f:
            f.seek(max(0, tam // 2))
            f.write(b"CORRUPTED_ZIP_STREAM_CHAOS_BYTE_INJECTION")
            f.truncate(max(100, tam - 200))

        if os.path.exists(ruta_meta):
            try:
                with open(ruta_meta, "r", encoding="utf-8") as f:
                    datos = json.load(f)
                datos["revision"] = int(datos.get("revision", 0)) + 1
                with open(ruta_meta, "w", encoding="utf-8") as f:
                    json.dump(datos, f, indent=4)
                print(f"[+] '{VAULT_META_NAME}' actualizado a #{datos['revision']} para forzar el intento de descarga.")
            except Exception:
                pass

        print(f"[+] Éxito: '{VAULT_ZIP_NAME}' mutilado en la nube.")
        print("    Prueba: La verificación SHA-256 debe abortar la descarga y alertar 'zip_corrupto'.")
    except Exception as e:
        print(f"[-] Error: {e}")
    pausar()


def corromper_metadatos_nube():
    """Sobrescribe pbm_vault.meta con JSON roto o sintaxis inválida."""
    nube = obtener_carpeta_nube()
    if not nube:
        print("[-] SYNC_CARPETA no configurada o inaccesible.")
        pausar()
        return
    ruta_meta = os.path.join(nube, VAULT_META_NAME)
    try:
        with open(ruta_meta, "w", encoding="utf-8") as f:
            f.write("{'revision': 'BROKEN_JSON_SYNTAX_ERROR_PBM',,,,,")
        print(f"[+] Éxito: '{VAULT_META_NAME}' saboteado con JSON corrupto.")
        print("    Prueba: El sistema y la web deben mostrar 'meta_corrupto' y bloquear operaciones.")
    except Exception as e:
        print(f"[-] Error: {e}")
    pausar()


def sabotear_revision_nube():
    """Modifica la revisión del meta remoto fijándola a #99999."""
    nube = obtener_carpeta_nube()
    if not nube:
        print("[-] SYNC_CARPETA no configurada o inaccesible.")
        pausar()
        return
    ruta_meta = os.path.join(nube, VAULT_META_NAME)
    try:
        datos = {}
        if os.path.exists(ruta_meta):
            try:
                with open(ruta_meta, "r", encoding="utf-8") as f:
                    datos = json.load(f)
            except Exception:
                datos = {"algoritmo": "AES-256", "hash_zip": "fake_hash"}

        datos["revision"] = 99999
        datos["ultimo_equipo"] = "Chaos-Node-PBM"
        with open(ruta_meta, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=4)
        print("[+] Éxito: Revisión en la nube fijada a #99999.")
        print("    Prueba: El botón de subida web debe quedar estrictamente deshabilitado (Anti-Atraso).")
    except Exception as e:
        print(f"[-] Error: {e}")
    pausar()


def corromper_timestamp_sync():
    """Inyecta texto no numérico en ultimo_sync.txt."""
    try:
        with open(RUTA_ULTIMO_SYNC, "w", encoding="utf-8") as f:
            f.write("TIMESTAMP_SYNC_CORRUPTO_ERROR")
        print("[+] Éxito: 'ultimo_sync.txt' contiene texto corrupto no numérico.")
    except Exception as e:
        print(f"[-] Error: {e}")
    pausar()


def sembrar_temporales_sync():
    """Crea archivos .pre_sync y .zip.tmp para probar la purga del bootloader."""
    try:
        with open(os.path.join(DIRECTORIO_RAIZ, "marcadores.db.pre_sync"), "w") as f:
            f.write("RESIDUO_PRE_SYNC_ABORTADO")
        with open(os.path.join(DIRECTORIO_RAIZ, "pbm_vault.zip.tmp"), "w") as f:
            f.write("RESIDUO_TEMP_DESCARGA_INCOMPLETA")
        print("[+] Éxito: Creados 'marcadores.db.pre_sync' y 'pbm_vault.zip.tmp'.")
        print("    Prueba: 'python app.py' los purgará al iniciar mostrando advertencias [ WARN ].")
    except Exception as e:
        print(f"[-] Error: {e}")
    pausar()


# ==============================================================================
# SECCIÓN 4: MANTENIMIENTO, TIMESTAMPS Y CUARENTENA
# ==============================================================================

def corromper_timestamp_backup():
    """Inyecta texto no parseable en ultimo_backup.txt y silenciar_backup.txt."""
    try:
        with open(RUTA_ULTIMO_BACKUP, "w", encoding="utf-8") as f:
            f.write("TIMESTAMP_INVALIDO_TEXTO_BASURA")
        with open(RUTA_SILENCIAR_BACKUP, "w", encoding="utf-8") as f:
            f.write("SILENCIO_INVALIDO")
        print("[+] Éxito: 'ultimo_backup.txt' y 'silenciar_backup.txt' saboteados.")
    except Exception as e:
        print(f"[-] Error: {e}")
    pausar()


def limpiar_archivos_cuarentena():
    """Limpia todos los residuos generados durante pruebas de estrés."""
    patrones = [
        os.path.join(DIRECTORIO_RAIZ, "marcadores.db.corrupt_*"),
        os.path.join(DIRECTORIO_RAIZ, ".env.corrupt_*"),
        os.path.join(DIRECTORIO_RAIZ, "*.corrupt_*"),
        os.path.join(DIRECTORIO_RAIZ, "*.pre_sync"),
        os.path.join(DIRECTORIO_RAIZ, "*.zip.tmp"),
        os.path.join(DIRECTORIO_RAIZ, "*.db.tmp"),
    ]
    borrados = 0
    for pat in patrones:
        for arch in glob.glob(pat):
            try:
                os.remove(arch)
                borrados += 1
                print(f"[+] Eliminado de cuarentena/prueba: {os.path.basename(arch)}")
            except Exception as e:
                print(f"[-] No se pudo eliminar {os.path.basename(arch)}: {e}")

    print(f"\n[✓] Limpieza completada: {borrados} archivo(s) removidos.")
    pausar()


# ==============================================================================
# MONITOR DE ESTADO Y MENÚ INTERACTIVO
# ==============================================================================

def estado_archivos():
    """Muestra el estado en tiempo real del entorno, nube y cuarentena."""
    print("\n--- ESTADO DEL ENTORNO LOCAL & NUBE (PBM) ---")
    print(f" .env:          {'PRESENTE' if os.path.exists(ENV_PATH) else 'AUSENTE'}")
    tam_db = f"{os.path.getsize(DB_PATH)} bytes" if os.path.exists(DB_PATH) else "AUSENTE"
    print(f" marcadores.db: {tam_db}")

    nube = obtener_carpeta_nube()
    if nube:
        meta_p = os.path.join(nube, VAULT_META_NAME)
        if os.path.exists(meta_p):
            try:
                with open(meta_p, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                print(f" Nube BYOC:     CONECTADA (Revisión #{meta.get('revision')} - {meta.get('ultimo_equipo')})")
            except Exception:
                print(" Nube BYOC:     CONECTADA (Metadatos .meta CORRUPTOS)")
        else:
            print(" Nube BYOC:     CONECTADA (Sin bóveda activa)")
    else:
        print(" Nube BYOC:     DESCONECTADA / NO CONFIGURADA")

    corruptos_db = glob.glob(os.path.join(DIRECTORIO_RAIZ, "marcadores.db.corrupt_*"))
    corruptos_env = glob.glob(os.path.join(DIRECTORIO_RAIZ, ".env.corrupt_*"))
    print(f" Cuarentena:    {len(corruptos_db) + len(corruptos_env)} archivo(s)")
    print("-" * 45)


def menu():
    while True:
        validar_seguridad_debug()
        limpiar_pantalla()
        estado_archivos()

        print("\nSIMULADOR DE CAOS & ESTRÉS :: PrivateBookmarkManager (DEBUG MODE)")
        print(" [ BASE DE DATOS SQLITE ]")
        print("  1. Corromper cabecera de marcadores.db (Magic Header inválido)")
        print("  2. Corromper árbol B-Tree de páginas (Fallo de integridad)")
        print("  3. Borrar tabla 'carpetas' (Schema Drift / Inconsistencia)")
        print("  4. Bloquear marcadores.db con candado exclusivo (Database locked)")
        print("  5. Borrar archivo marcadores.db (Simular pérdida / Test Disaster Recovery)")
        print("")
        print(" [ ENTORNO & .ENV ]")
        print("  6. Inyectar puerto/host inválidos (PORT=99999)")
        print("  7. Vaciar SECRET_KEY y MASTER_KEY")
        print("  8. Corromper archivo .env con bytes basura")
        print("")
        print(" [ SINCRONIZACIÓN BYOC & INTEGRIDAD ]")
        print("  9. Mutilar / Truncar pbm_vault.zip en la nube (Test SHA-256)")
        print(" 10. Corromper metadatos pbm_vault.meta en la nube")
        print(" 11. Forzar conflicto de revisión remota superior (#99999)")
        print(" 12. Corromper testigo local ultimo_sync.txt")
        print(" 13. Sembrar archivos temporales atómicos (*.pre_sync, *.tmp)")
        print("")
        print(" [ MANTENIMIENTO & CUARENTENA ]")
        print(" 14. Corromper timestamps de copia de seguridad")
        print(" 15. Limpiar archivos de cuarentena y pruebas (.corrupt_*, *.tmp)")
        print("  0. Salir")

        op = input("\nSelecciona un vector de caos: ").strip()

        if op == "1":
            corromper_cabecera_sqlite()
        elif op == "2":
            corromper_arbol_b()
        elif op == "3":
            romper_esquema_tablas()
        elif op == "4":
            bloquear_archivo_db()
        elif op == "5":
            eliminar_solo_db()
        elif op == "6":
            sabotear_red_puerto()
        elif op == "7":
            vaciar_claves_seguridad()
        elif op == "8":
            corromper_archivo_env()
        elif op == "9":
            corromper_boveda_zip_nube()
        elif op == "10":
            corromper_metadatos_nube()
        elif op == "11":
            sabotear_revision_nube()
        elif op == "12":
            corromper_timestamp_sync()
        elif op == "13":
            sembrar_temporales_sync()
        elif op == "14":
            corromper_timestamp_backup()
        elif op == "15":
            limpiar_archivos_cuarentena()
        elif op == "0":
            print("[*] Saliendo del simulador de caos.")
            break
        else:
            print("[-] Opción no válida.")
            time.sleep(0.8)


if __name__ == "__main__":
    validar_seguridad_debug()
    menu()