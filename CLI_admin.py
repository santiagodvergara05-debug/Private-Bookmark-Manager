import os
import secrets
from datetime import datetime
import time
from dotenv import set_key, dotenv_values

ENV_PATH = ".env"
RUTA_ULTIMO_BACKUP = "ultimo_backup.txt"
RUTA_SILENCIAR_BACKUP = "silenciar_backup.txt"

def obtener_config():
    if not os.path.exists(ENV_PATH):
        print("[-] Error: No se encontró el archivo .env.")
        return None
    return dotenv_values(ENV_PATH)

def cambiar_valor(clave, nuevo_valor, mensaje_exito):
    set_key(ENV_PATH, clave, nuevo_valor)
    print(f"\n[+] {mensaje_exito}: {nuevo_valor}")

def obtener_estado_backups():
    # Lectura del último backup realizado
    ultimo_texto = "Nunca realizado (o archivo no disponible)"
    if os.path.exists(RUTA_ULTIMO_BACKUP):
        try:
            with open(RUTA_ULTIMO_BACKUP, "r") as f:
                ts = float(f.read().strip())
                ultimo_texto = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, OSError):
            ultimo_texto = "Dato corrupto"

    # Lectura del estado de silenciado
    silencio_texto = "Inactivo"
    if os.path.exists(RUTA_SILENCIAR_BACKUP):
        try:
            with open(RUTA_SILENCIAR_BACKUP, "r") as f:
                ts = float(f.read().strip())
                if time.time() < ts:
                    silencio_texto = f"Hasta {datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')}"
                else:
                    silencio_texto = "Expirado"
        except (ValueError, OSError):
            silencio_texto = "Dato corrupto"

    return ultimo_texto, silencio_texto

def menu_principal():
    while True:
        cfg = obtener_config()
        if cfg is None:
            break

        host_desc = "Solo esta PC (127.0.0.1)" if cfg.get("HOST") == "127.0.0.1" else "Toda la red (0.0.0.0)"
        debug_desc = "Activo" if cfg.get("FLASK_DEBUG", "").lower() == "true" else "Inactivo"
        log_desc = "Activo" if cfg.get("LOG_MODE", "").lower() == "true" else "Inactivo"
        fav_desc = "Activo" if cfg.get("MOSTRAR_FAVICONS", "").lower() == "true" else "Inactivo"
        
        ultimo_bkp, silencio_bkp = obtener_estado_backups()

        print("\n" + "=" * 60)
        print("                PANEL DE ADMINISTRACIÓN CLI")
        print("=" * 60)
        print(f" Puerto actual: {cfg.get('PORT', '5050')} | Red: {host_desc}")
        print(f" Debug: {debug_desc} | Logs: {log_desc} | Favicons: {fav_desc}")
        print("-" * 60)
        print(f" Último Backup: {ultimo_bkp}")
        print(f" Silencio Backup: {silencio_bkp}")
        print("-" * 60)
        print("--- GESTIÓN DE CREDENCIALES ---")
        print("M. Ver MASTER_KEY actual (para copiar)")
        print("1. Cambiar contraseña web (APP_PASSWORD)")
        print("2. Rotar MASTER_KEY (256 bits)")
        print("3. Rotar SECRET_KEY (Cierra todas las sesiones)")
        print("4. Rotar AMBAS llaves maestras")
        print("\n--- CONFIGURACIÓN DEL SISTEMA ---")
        print("5. Alternar Debug Mode (true/false)")
        print("6. Alternar Log Mode (true/false)")
        print("7. Alternar Favicons (true/false)")
        print("8. Cambiar Puerto (PORT)")
        print("9. Alternar alcance de red (127.0.0.1 <-> 0.0.0.0)")
        print("\n0. Salir")
        print("=" * 60)

        opcion = input("Selecciona una opción (0-9 o M): ").strip()

        if opcion.upper() == "M":
            master_actual = cfg.get("MASTER_KEY")
            if master_actual:
                print("\n" + "-" * 60)
                print("🔑 MASTER_KEY ACTUAL:")
                print(master_actual)
                print("-" * 60)
            else:
                print("\n[-] No se encontró MASTER_KEY definida en el .env.")

        elif opcion == "1":
            nueva_pass = input("Ingresa la nueva contraseña: ").strip()
            if nueva_pass:
                cambiar_valor("APP_PASSWORD", nueva_pass, "Contraseña actualizada")
            else:
                print("[-] Contraseña no válida.")

        elif opcion == "2":
            nueva_master = secrets.token_hex(32)
            cambiar_valor("MASTER_KEY", nueva_master, "Nueva MASTER_KEY generada")

        elif opcion == "3":
            nueva_secret = secrets.token_hex(32)
            cambiar_valor("SECRET_KEY", nueva_secret, "Nueva SECRET_KEY generada (Sesiones cerradas)")

        elif opcion == "4":
            nueva_secret = secrets.token_hex(32)
            nueva_master = secrets.token_hex(32)
            set_key(ENV_PATH, "SECRET_KEY", nueva_secret)
            set_key(ENV_PATH, "MASTER_KEY", nueva_master)
            print("\n[+] Ambas llaves actualizadas con éxito:")
            print(f"    SECRET_KEY: {nueva_secret}")
            print(f"    MASTER_KEY: {nueva_master}")

        elif opcion == "5":
            nuevo = "false" if cfg.get("FLASK_DEBUG", "").lower() == "true" else "true"
            cambiar_valor("FLASK_DEBUG", nuevo, "Debug Mode cambiado")

        elif opcion == "6":
            nuevo = "false" if cfg.get("LOG_MODE", "").lower() == "true" else "true"
            cambiar_valor("LOG_MODE", nuevo, "Log Mode cambiado")

        elif opcion == "7":
            nuevo = "false" if cfg.get("MOSTRAR_FAVICONS", "").lower() == "true" else "true"
            cambiar_valor("MOSTRAR_FAVICONS", nuevo, "Mostrar favicons cambiado")

        elif opcion == "8":
            nuevo_puerto = input("Ingresa el nuevo puerto (ej. 5050): ").strip()
            if nuevo_puerto.isdigit():
                cambiar_valor("PORT", nuevo_puerto, "Puerto actualizado")
            else:
                print("[-] El puerto debe ser un número entero.")

        elif opcion == "9":
            nuevo_host = "0.0.0.0" if cfg.get("HOST") == "127.0.0.1" else "127.0.0.1"
            cambiar_valor("HOST", nuevo_host, "Alcance de red actualizado")

        elif opcion == "0":
            print("\n[*] Saliendo del panel...")
            break
        else:
            print("\n[-] Opción no reconocida. Intenta de nuevo.")

if __name__ == "__main__":
    menu_principal()