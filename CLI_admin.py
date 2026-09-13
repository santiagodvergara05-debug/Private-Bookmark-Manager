import os
import sys
import time
import secrets
import sqlite3
from datetime import datetime
from dotenv import load_dotenv, set_key

ES_EXE = getattr(sys, "frozen", False)
if ES_EXE:
    DIRECTORIO_RAIZ = os.path.dirname(sys.executable)
else:
    DIRECTORIO_RAIZ = os.path.dirname(os.path.abspath(__file__))

ENV_PATH = os.path.join(DIRECTORIO_RAIZ, ".env")
DB_PATH = os.path.join(DIRECTORIO_RAIZ, "marcadores.db")
RUTA_ULTIMO_BACKUP = os.path.join(DIRECTORIO_RAIZ, "ultimo_backup.txt")
RUTA_SILENCIAR_BACKUP = os.path.join(DIRECTORIO_RAIZ, "silenciar_backup.txt")

def limpiar_pantalla():
    os.system("cls" if os.name == "nt" else "clear")

def verificar_entorno():
    """Bloquea el acceso al panel si no existe un archivo .env generado."""
    if not os.path.exists(ENV_PATH):
        limpiar_pantalla()
        print("=" * 65)
        print("    [!] ERROR: ARCHIVO DE CONFIGURACIÓN (.env) NO DETECTADO")
        print("=" * 65)
        print(" La consola administrativa no puede operar sin un entorno base.")
        print(" Inicie el servidor principal (app.py o el ejecutable) al menos")
        print(" una vez para aprovisionar las claves e inicializar el sistema.")
        print("=" * 65)
        input("\nPresione ENTER para salir...")
        sys.exit(1)

def obtener_resumen_db():
    if not os.path.exists(DB_PATH):
        return "0 carpetas / 0 marcadores"
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM carpetas")
        n_carp = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM marcadores")
        n_marc = cur.fetchone()[0]
        conn.close()
        return f"{n_carp} carpetas / {n_marc} marcadores"
    except Exception:
        return "DB inaccesible"

def obtener_info_backup():
    if os.path.exists(RUTA_ULTIMO_BACKUP):
        try:
            with open(RUTA_ULTIMO_BACKUP, "r") as f:
                ts = float(f.read().strip())
                return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        except Exception:
            return "Corrupto"
    return "Nunca realizado"

def submenu_inspeccion(titulo, etiqueta, valor):
    """Muestra la clave limpia con opciones de navegación rápida."""
    limpiar_pantalla()
    print("=" * 65)
    print(f"             INSPECCIÓN DE SEGURIDAD :: {titulo.upper()}")
    print("=" * 65)
    print(f"\n {etiqueta}:")
    print(f" \033[92m{valor}\033[0m" if sys.stdout.isatty() else f" {valor}")
    print("\n" + "-" * 65)
    print("  1. Volver al menú principal")
    print("  2. Salir del programa")
    print("=" * 65)

    while True:
        opc = input("Selecciona una opción [1-2]: ").strip()
        if opc == "1":
            return
        elif opc == "2":
            print("\nCerrando consola de administración...")
            sys.exit(0)
        else:
            print("Opción inválida. Ingrese 1 o 2.")

def pausar():
    input("\nPresione ENTER para continuar...")

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
        
        # CONTRASENA_MOSTRADA='false' significa que el cartel inicial se muestra
        cartel_login_activo = os.environ.get("CONTRASENA_MOSTRADA", "false").lower() == "false"
        estado_cartel = "Activo (Visible)" if cartel_login_activo else "Inactivo (Oculto)"

        tipo_red = "Global" if host == "0.0.0.0" else "Local"

        print("=" * 65)
        print("                   PANEL DE CONTROL ADMINISTRATIVO")
        print("=" * 65)
        print(f" Red: {host} ({tipo_red})    | Puerto HTTP: {port}")
        print(f" DB: {obtener_resumen_db()} | Debug: {debug} | Logs: {logs}")
        print(f" UI: [Oscuro: {oscuro}] [Favicons: {favicons}] [Pestaña: {tab}] [Auto-Nav: {auto_nav}]")
        print("-" * 65)
        print(f" Último Backup:    {obtener_info_backup()}")
        print(f" Cartel 1er Login: {estado_cartel}")
        print("-" * 65)
        print(" GESTIÓN DE SEGURIDAD")
        print("   P. Inspeccionar contraseña web (APP_PASSWORD)")
        print("   M. Inspeccionar MASTER_KEY (para copiar)")
        print("   C. Alternar Cartel de Credenciales en Login (Primer inicio)")
        print("   1. Cambiar contraseña web (APP_PASSWORD)")
        print("   2. Rotar MASTER_KEY (Criptografía 256 bits)")
        print("   3. Rotar SECRET_KEY (Invalida sesiones activas)")
        print("   4. Rotar ambas claves simultáneamente")
        print("")
        print(" PREFERENCIAS VISUALES Y SISTEMA")
        print("   5. Alternar Modo Oscuro (MODO_OSCURO)")
        print("   6. Alternar Iconos de Sitios (MOSTRAR_FAVICONS)")
        print("   7. Alternar Abrir Marcador en Nueva Pestaña (ABRIR_NUEVA_PESTANA)")
        print("   8. Alternar Depuración Flask (FLASK_DEBUG)")
        print("   9. Alternar Telemetría de Servidor (LOG_MODE)")
        print("  10. Cambiar Puerto HTTP de Escucha (PORT)")
        print("  11. Alternar Alcance de Red (Local 127.0.0.1 <-> Global 0.0.0.0)")
        print("  12. Alternar Auto-abrir Navegador al Iniciar (.exe)")
        print("")
        print(" MANTENIMIENTO")
        print("   R. Restaurar de fábrica (Eliminar DB, .env y backups)")
        print("   0. Salir")
        print("=" * 65)

        opcion = input("Selecciona una opción: ").strip().lower()

        # Inspección de credenciales con submenú (Volver / Salir)
        if opcion == "p":
            pass_actual = os.environ.get("APP_PASSWORD", "cambiame")
            submenu_inspeccion("Contraseña de Acceso Web", "APP_PASSWORD CONFIGURADA", pass_actual)

        elif opcion == "m":
            master_actual = os.environ.get("MASTER_KEY", "No configurada")
            submenu_inspeccion("Llave Maestra", "MASTER_KEY CONFIGURADA", master_actual)

        # Alternar cartel de credenciales en login
        elif opcion == "c":
            nuevo_estado = "true" if cartel_login_activo else "false"
            set_key(ENV_PATH, "CONTRASENA_MOSTRADA", nuevo_estado)
            os.environ["CONTRASENA_MOSTRADA"] = nuevo_estado
            msg = "Desactivado (Ya no se mostrará)" if nuevo_estado == "true" else "Activado (Se mostrará en /login)"
            print(f"\n[OK] Cartel de credenciales iniciales: {msg}")
            pausar()

        elif opcion == "1":
            nueva_pass = input("\nIngrese la nueva contraseña: ").strip()
            if nueva_pass:
                set_key(ENV_PATH, "APP_PASSWORD", nueva_pass)
                os.environ["APP_PASSWORD"] = nueva_pass
                print("[OK] Contraseña web actualizada.")
            else:
                print("[WARN] Operación cancelada: contraseña vacía.")
            pausar()

        elif opcion == "2":
            nueva_master = secrets.token_hex(32)
            set_key(ENV_PATH, "MASTER_KEY", nueva_master)
            os.environ["MASTER_KEY"] = nueva_master
            print(f"\n[OK] MASTER_KEY regenerada exitosamente.")
            pausar()

        elif opcion == "3":
            nueva_secret = secrets.token_hex(32)
            set_key(ENV_PATH, "SECRET_KEY", nueva_secret)
            os.environ["SECRET_KEY"] = nueva_secret
            print(f"\n[OK] SECRET_KEY regenerada. Todas las sesiones web fueron invalidadas.")
            pausar()

        elif opcion == "4":
            nueva_master = secrets.token_hex(32)
            nueva_secret = secrets.token_hex(32)
            set_key(ENV_PATH, "MASTER_KEY", nueva_master)
            set_key(ENV_PATH, "SECRET_KEY", nueva_secret)
            os.environ["MASTER_KEY"] = nueva_master
            os.environ["SECRET_KEY"] = nueva_secret
            print(f"\n[OK] Llaves regeneradas con éxito.")
            pausar()

        elif opcion == "5":
            val = "false" if oscuro == "Sí" else "true"
            set_key(ENV_PATH, "MODO_OSCURO", val)
            print(f"\n[OK] MODO_OSCURO configurado a: {val}")
            pausar()

        elif opcion == "6":
            val = "false" if favicons == "Sí" else "true"
            set_key(ENV_PATH, "MOSTRAR_FAVICONS", val)
            print(f"\n[OK] MOSTRAR_FAVICONS configurado a: {val}")
            pausar()

        elif opcion == "7":
            val = "false" if tab == "Sí" else "true"
            set_key(ENV_PATH, "ABRIR_NUEVA_PESTANA", val)
            print(f"\n[OK] ABRIR_NUEVA_PESTANA configurado a: {val}")
            pausar()

        elif opcion == "8":
            val = "false" if debug == "Sí" else "true"
            set_key(ENV_PATH, "FLASK_DEBUG", val)
            print(f"\n[OK] FLASK_DEBUG configurado a: {val}")
            pausar()

        elif opcion == "9":
            val = "false" if logs == "Sí" else "true"
            set_key(ENV_PATH, "LOG_MODE", val)
            print(f"\n[OK] LOG_MODE configurado a: {val}")
            pausar()

        elif opcion == "10":
            nuevo_puerto = input("\nIngrese el nuevo puerto (ej. 5050): ").strip()
            if nuevo_puerto.isdigit() and 1 <= int(nuevo_puerto) <= 65535:
                set_key(ENV_PATH, "PORT", nuevo_puerto)
                print(f"[OK] Puerto actualizado a: {nuevo_puerto}")
            else:
                print("[FAIL] Puerto inválido.")
            pausar()

        elif opcion == "11":
            nuevo_host = "127.0.0.1" if host == "0.0.0.0" else "0.0.0.0"
            set_key(ENV_PATH, "HOST", nuevo_host)
            print(f"\n[OK] Escucha de red cambiada a: {nuevo_host}")
            pausar()

        elif opcion == "12":
            val = "false" if auto_nav == "Sí" else "true"
            set_key(ENV_PATH, "AUTO_ABRIR_NAVEGADOR", val)
            os.environ["AUTO_ABRIR_NAVEGADOR"] = val
            print(f"\n[OK] AUTO_ABRIR_NAVEGADOR configurado a: {val}")
            pausar()

        elif opcion == "r":
            print("\n" + "!" * 65)
            print(" PELIGRO: ESTA ACCIÓN ELIMINARÁ BASE DE DATOS, .ENV Y BACKUPS")
            print("!" * 65)
            conf = input("Escriba 'CONFIRMAR' para proceder: ").strip()
            if conf == "CONFIRMAR":
                for f in [DB_PATH, ENV_PATH, RUTA_ULTIMO_BACKUP, RUTA_SILENCIAR_BACKUP]:
                    if os.path.exists(f):
                        try:
                            os.remove(f)
                        except Exception:
                            pass
                print("\n[OK] Sistema restaurado a estado inicial.")
                pausar()
                sys.exit(0)
            else:
                print("\n[INFO] Restauración cancelada.")
                pausar()

        elif opcion == "0":
            print("\nSaliendo del Panel Administrativo...")
            break

if __name__ == "__main__":
    verificar_entorno()
    main()