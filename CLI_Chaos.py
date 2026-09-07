import os
import sys
import glob
from dotenv import dotenv_values

DIRECTORIO_RAIZ = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DIRECTORIO_RAIZ, "marcadores.db")
ENV_PATH = os.path.join(DIRECTORIO_RAIZ, ".env")

def validar_seguridad_debug():
    """Bloquea el script si el modo debug no está habilitado en el .env."""
    if not os.path.exists(ENV_PATH):
        print("\n[-] Error crítico: Archivo .env ausente. No se puede verificar el entorno.")
        sys.exit(1)

    cfg = dotenv_values(ENV_PATH)
    # Limpia comillas simples o dobles en caso de que existan
    debug_val = cfg.get("FLASK_DEBUG", "false").strip("'\"").lower()

    if debug_val != "true":
        print("\n" + "!" * 70)
        print(" [!] ACCESO DENEGADO :: CONTROL DE SEGURIDAD DE ENTORNO")
        print("!" * 70)
        print(" MODO DEBUG DESACTIVADO")
        print(" POR SEGURIDAD NO PUEDE OPERAR ESTE CLI")
        print(" HABILITE EL MODO DEBUG PARA ACTIVAR LAS OPCIONES\n")
        print(" SI ACTIVA EL MODO DEBUG REALICE COPIA DE SEGURIDAD")
        print(" YA QUE TIENE OPCIONES IRREVERSIBLES")
        print("!" * 70 + "\n")
        sys.exit(1)

def corromper_cabecera():
    """Sobrescribe el Magic Header de SQLite haciendo que deje de ser una base válida."""
    if not os.path.exists(DB_PATH):
        print("[-] Error: 'marcadores.db' no existe. Inicia app.py primero.")
        return
    try:
        with open(DB_PATH, "r+b") as f:
            f.seek(0)
            f.write(b"CORRUPTED_HEADER")
        print("[+] Éxito: Cabecera destruida. SQLite reportará 'file is not a database'.")
    except Exception as e:
        print(f"[-] Fallo al escribir: {e}")

def corromper_arbol_paginas():
    """Sobrescribe datos reales al final del archivo para forzar el fallo de integridad."""
    if not os.path.exists(DB_PATH):
        print("[-] Error: 'marcadores.db' no existe.")
        return
    try:
        size = os.path.getsize(DB_PATH)
        if size < 500:
            print("[-] Archivo sin datos suficientes.")
            return
        with open(DB_PATH, "r+b") as f:
            # Apunta 128 bytes antes del final del archivo (donde residen los marcadores)
            f.seek(size - 128)
            f.write(os.urandom(64))
        print("[+] Éxito: Registro activo destruido. 'PRAGMA integrity_check' fallará.")
    except Exception as e:
        print(f"[-] Fallo al alterar datos: {e}")

def eliminar_solo_db():
    """Borra marcadores.db conservando el .env para simular borrado accidental."""
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print("[+] Éxito: 'marcadores.db' eliminado.")
            print("    El archivo '.env' se mantiene intacto con SISTEMA_INICIALIZADO='true'.")
        except Exception as e:
            print(f"[-] No se pudo eliminar: {e}")
    else:
        print("[i] 'marcadores.db' ya se encontraba ausente.")

def limpiar_archivos_cuarentena():
    """Elimina todos los archivos marcadores.db.corrupt_* generados en pruebas."""
    patron = os.path.join(DIRECTORIO_RAIZ, "marcadores.db.corrupt_*")
    archivos = glob.glob(patron)
    if not archivos:
        print("[i] No se encontraron archivos .corrupt_* para limpiar.")
        return
    for arc in archivos:
        try:
            os.remove(arc)
            print(f"[+] Eliminado: {os.path.basename(arc)}")
        except Exception as e:
            print(f"[-] Error borrando {arc}: {e}")

def estado_archivos():
    """Muestra el estado actual del disco."""
    print("\n--- ESTADO DEL ENTORNO LOCAL ---")
    print(f" .env:          {'PRESENTE' if os.path.exists(ENV_PATH) else 'AUSENTE'}")
    print(f" marcadores.db: {'PRESENTE (' + str(os.path.getsize(DB_PATH)) + ' bytes)' if os.path.exists(DB_PATH) else 'AUSENTE'}")
    corruptos = glob.glob(os.path.join(DIRECTORIO_RAIZ, "marcadores.db.corrupt_*"))
    print(f" Backups rotos: {len(corruptos)} archivo(s) en cuarentena")
    print("-" * 32)

def menu():
    while True:
        # Verifica nuevamente en cada iteración por si el usuario apagó el debug en caliente
        validar_seguridad_debug()
        
        estado_archivos()
        print("\nHERRAMIENTA DE CAOS :: SIMULADOR DE FALLOS (DEBUG MODE)")
        print("1. Corromper cabecera de DB (Simular archivo inválido)")
        print("2. Corromper árbol de datos (Simular fallo de integridad)")
        print("3. Borrar solo marcadores.db (Dejar .env intacto)")
        print("4. Limpiar archivos en cuarentena (.corrupt_*)")
        print("0. Salir")
        
        op = input("\nSelecciona una opción: ").strip()
        if op == "1":
            corromper_cabecera()
        elif op == "2":
            corromper_arbol_paginas()
        elif op == "3":
            eliminar_solo_db()
        elif op == "4":
            limpiar_archivos_cuarentena()
        elif op == "0":
            print("[*] Saliendo del simulador.")
            break
        else:
            print("[-] Opción inválida.")

if __name__ == "__main__":
    validar_seguridad_debug()
    menu()