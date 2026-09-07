import os
import sys
import secrets
from datetime import datetime
import time
import sqlite3
from dotenv import set_key, dotenv_values

# Detección de ruta base (compatible con script y .exe)
ES_EXE = getattr(sys, "frozen", False)
if ES_EXE:
    DIRECTORIO_RAIZ = os.path.dirname(sys.executable)
else:
    DIRECTORIO_RAIZ = os.path.dirname(os.path.abspath(__file__))

ENV_PATH = os.path.join(DIRECTORIO_RAIZ, ".env")
DB_PATH = os.path.join(DIRECTORIO_RAIZ, "marcadores.db")
RUTA_ULTIMO_BACKUP = os.path.join(DIRECTORIO_RAIZ, "ultimo_backup.txt")
RUTA_SILENCIAR_BACKUP = os.path.join(DIRECTORIO_RAIZ, "silenciar_backup.txt")

def obtener_config():
    if not os.path.exists(ENV_PATH):
        print("\n[-] Error: No se encontró el archivo .env.")
        print("    Inicia 'app.py' primero para aprovisionar el sistema.")
        return None
    return dotenv_values(ENV_PATH)

def cambiar_valor(clave, nuevo_valor, mensaje_exito):
    set_key(ENV_PATH, clave, nuevo_valor)
    print(f"\n[+] {mensaje_exito}: {nuevo_valor}")

def obtener_conteo_db():
    if not os.path.exists(DB_PATH):
        return "No creada", "No creada"
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM carpetas")
        total_carpetas = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM marcadores")
        total_marcadores = cur.fetchone()[0]
        conn.close()
        return str(total_carpetas), str(total_marcadores)
    except Exception:
        return "Error", "Error"

def obtener_estado_backups():
    ultimo_texto = "Nunca realizado"
    if os.path.exists(RUTA_ULTIMO_BACKUP):
        try:
            with open(RUTA_ULTIMO_BACKUP, "r", encoding="utf-8") as f:
                ts = float(f.read().strip())
                ultimo_texto = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, OSError):
            ultimo_texto = "Dato corrupto"

    silencio_texto = "Inactivo"
    if os.path.exists(RUTA_SILENCIAR_BACKUP):
        try:
            with open(RUTA_SILENCIAR_BACKUP, "r", encoding="utf-8") as f:
                ts = float(f.read().strip())
                if time.time() < ts:
                    silencio_texto = f"Hasta {datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')}"
                else:
                    silencio_texto = "Expirado"
        except (ValueError, OSError):
            silencio_texto = "Dato corrupto"

    return ultimo_texto, silencio_texto

def ejecutar_restauracion_fabrica():
    print("\n" + "!" * 65)
    print("                 ZONA DE PELIGRO :: RESTAURACIÓN DE FÁBRICA")
    print("!" * 65)
    print(" Esta acción eliminará de forma irreversible:")
    print("   • Base de datos (marcadores.db) con todas las carpetas y enlaces")
    print("   • Archivo de configuración (.env) y llaves maestras")
    print("   • Registros de copias de seguridad (ultimo_backup.txt)")
    print("   • Recordatorios de silenciado (silenciar_backup.txt)")
    print("-" * 65)
    confirmacion = input(" Escribe 'BORRAR' para confirmar el restablecimiento completo: ").strip()

    if confirmacion == "BORRAR":
        archivos_a_borrar = [DB_PATH, ENV_PATH, RUTA_ULTIMO_BACKUP, RUTA_SILENCIAR_BACKUP]
        print("\n[*] Eliminando archivos de entorno...")
        for ruta in archivos_a_borrar:
            nombre = os.path.basename(ruta)
            if os.path.exists(ruta):
                try:
                    os.remove(ruta)
                    print(f"  [+] Eliminado: {nombre}")
                except Exception as e:
                    print(f"  [-] Error al eliminar {nombre}: {e}")
            else:
                print(f"  [i] No presente: {nombre} (omitido)")
        
        print("\n[OK] Restauración completada.")
        print("     Al volver a arrancar app.py, se ejecutará el bootloader desde cero.")
        return True
    else:
        print("\n[!] Operación cancelada. No se aplicaron modificaciones.")
        return False

def menu_principal():
    while True:
        cfg = obtener_config()
        if cfg is None:
            break

        host_desc = "127.0.0.1 (Local)" if cfg.get("HOST") == "127.0.0.1" else "0.0.0.0 (Red LAN)"
        debug_desc = "Sí" if cfg.get("FLASK_DEBUG", "").lower() == "true" else "No"
        log_desc = "Sí" if cfg.get("LOG_MODE", "").lower() == "true" else "No"
        fav_desc = "Sí" if cfg.get("MOSTRAR_FAVICONS", "").lower() == "true" else "No"
        dark_desc = "Sí" if cfg.get("MODO_OSCURO", "").lower() == "true" else "No"
        tab_desc = "Sí" if cfg.get("ABRIR_NUEVA_PESTANA", "").lower() == "true" else "No"
        
        carpetas_db, marcadores_db = obtener_conteo_db()
        ultimo_bkp, silencio_bkp = obtener_estado_backups()

        print("\n" + "=" * 65)
        print("                   PANEL DE CONTROL ADMINISTRATIVO")
        print("=" * 65)
        print(f" Red: {host_desc:<20} | Puerto HTTP: {cfg.get('PORT', '5050')}")
        print(f" DB: {carpetas_db} carpetas / {marcadores_db} marcadores | Debug: {debug_desc} | Logs: {log_desc}")
        print(f" UI: [Oscuro: {dark_desc}] [Favicons: {fav_desc}] [Nueva pestaña: {tab_desc}]")
        print("-" * 65)
        print(f" Último Backup:    {ultimo_bkp}")
        print(f" Silencio Backup:  {silencio_bkp}")
        print("-" * 65)
        print(" GESTIÓN DE SEGURIDAD")
        print("   M. Inspeccionar MASTER_KEY (para copiar)")
        print("   1. Cambiar contraseña web (APP_PASSWORD)")
        print("   2. Rotar MASTER_KEY (Criptografía 256 bits)")
        print("   3. Rotar SECRET_KEY (Invalida sesiones activas)")
        print("   4. Rotar ambas claves simultáneamente")
        print("\n PREFERENCIAS VISUALES Y SISTEMA")
        print("   5. Alternar Modo Oscuro (MODO_OSCURO)")
        print("   6. Alternar Iconos de Sitios (MOSTRAR_FAVICONS)")
        print("   7. Alternar Abrir Marcador en Nueva Pestaña (ABRIR_NUEVA_PESTANA)")
        print("   8. Alternar Depuración Flask (FLASK_DEBUG)")
        print("   9. Alternar Telemetría de Servidor (LOG_MODE)")
        print("  10. Cambiar Puerto HTTP de Escucha (PORT)")
        print("  11. Alternar Alcance de Red (Local 127.0.0.1 <-> Global 0.0.0.0)")
        print("\n MANTENIMIENTO")
        print("   R. Restaurar de fábrica (Eliminar DB, .env y backups)")
        print("   0. Salir")
        print("=" * 65)

        opcion = input("Selecciona una opción: ").strip().upper()

        if opcion == "M":
            master_actual = cfg.get("MASTER_KEY")
            if master_actual:
                print("\n" + "-" * 65)
                print(" MASTER_KEY CONFIGURADA:")
                print(f" {master_actual}")
                print("-" * 65)
            else:
                print("\n[-] No se localizó la variable MASTER_KEY en el .env.")

        elif opcion == "1":
            nueva_pass = input("Ingresa la nueva contraseña web: ").strip()
            if nueva_pass:
                cambiar_valor("APP_PASSWORD", nueva_pass, "Contraseña web actualizada")
            else:
                print("[-] Contraseña no válida.")

        elif opcion == "2":
            nueva_master = secrets.token_hex(32)
            cambiar_valor("MASTER_KEY", nueva_master, "Nueva MASTER_KEY generada")

        elif opcion == "3":
            nueva_secret = secrets.token_hex(32)
            cambiar_valor("SECRET_KEY", nueva_secret, "Nueva SECRET_KEY generada")

        elif opcion == "4":
            nueva_secret = secrets.token_hex(32)
            nueva_master = secrets.token_hex(32)
            set_key(ENV_PATH, "SECRET_KEY", nueva_secret)
            set_key(ENV_PATH, "MASTER_KEY", nueva_master)
            print("\n[+] Claves criptográficas rotadas correctamente:")
            print(f"    SECRET_KEY: {nueva_secret}")
            print(f"    MASTER_KEY: {nueva_master}")

        elif opcion == "5":
            nuevo = "false" if cfg.get("MODO_OSCURO", "").lower() == "true" else "true"
            cambiar_valor("MODO_OSCURO", nuevo, "Preferencia Modo Oscuro modificada")

        elif opcion == "6":
            nuevo = "false" if cfg.get("MOSTRAR_FAVICONS", "").lower() == "true" else "true"
            cambiar_valor("MOSTRAR_FAVICONS", nuevo, "Carga de favicons modificada")

        elif opcion == "7":
            nuevo = "false" if cfg.get("ABRIR_NUEVA_PESTANA", "").lower() == "true" else "true"
            cambiar_valor("ABRIR_NUEVA_PESTANA", nuevo, "Apertura en nueva pestaña modificada")

        elif opcion == "8":
            nuevo = "false" if cfg.get("FLASK_DEBUG", "").lower() == "true" else "true"
            cambiar_valor("FLASK_DEBUG", nuevo, "Modo Debug Flask modificado")

        elif opcion == "9":
            nuevo = "false" if cfg.get("LOG_MODE", "").lower() == "true" else "true"
            cambiar_valor("LOG_MODE", nuevo, "Modo de logs modificado")

        elif opcion == "10":
            nuevo_puerto = input("Ingresa el nuevo puerto HTTP (ej. 5050): ").strip()
            if nuevo_puerto.isdigit() and 1 <= int(nuevo_puerto) <= 65535:
                cambiar_valor("PORT", nuevo_puerto, "Puerto HTTP actualizado")
            else:
                print("[-] Valor no válido. Debe ser un número de puerto entre 1 y 65535.")

        elif opcion == "11":
            nuevo_host = "0.0.0.0" if cfg.get("HOST") == "127.0.0.1" else "127.0.0.1"
            cambiar_valor("HOST", nuevo_host, "Alcance de red modificado")

        elif opcion == "R":
            if ejecutar_restauracion_fabrica():
                break

        elif opcion == "0":
            print("\n[*] Saliendo del panel administrativo...")
            break
        else:
            print("\n[-] Opción no válida. Ingresa una de las opciones del listado.")

if __name__ == "__main__":
    menu_principal()