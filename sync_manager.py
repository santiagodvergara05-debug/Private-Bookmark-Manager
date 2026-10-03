"""
==============================================================================
PBM PRIVATE BOOKMARK MANAGER - GESTOR DE SINCRONIZACIÓN BYOC (E2EE AES-256)
==============================================================================
Maneja el empaquetado seguro, verificación de integridad vía SHA-256,
lectura de metadatos (.meta) y resolución atómica entre nodos para marcadores.
"""

import os
import json
import time
import hashlib
import tempfile
import shutil
import pyzipper

VAULT_ZIP_NAME = "pbm_vault.zip"
VAULT_META_NAME = "pbm_vault.meta"
VAULT_PREV_NAME = "pbm_vault.prev.zip"
DB_FILE_NAME = "marcadores.db"


def calcular_sha256(ruta_archivo: str) -> str:
    """Calcula el hash SHA-256 de un archivo en bloques de 64 KB."""
    if not os.path.exists(ruta_archivo):
        return ""
    hasher = hashlib.sha256()
    try:
        with open(ruta_archivo, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return ""


def derivar_token_verificador(clave: str) -> str:
    """Genera un hash verificador para validar la clave sin exponerla en texto plano."""
    if not clave:
        return ""
    return hashlib.sha256(f"pbm_salt_e2ee_{clave}".encode("utf-8")).hexdigest()


def leer_metadatos_remotos(carpeta_sync: str) -> dict | None:
    """Lee el archivo .meta de la nube o carpeta externa."""
    if not carpeta_sync or not os.path.isdir(carpeta_sync):
        return None

    ruta_meta = os.path.join(carpeta_sync, VAULT_META_NAME)
    if not os.path.exists(ruta_meta):
        return None

    try:
        with open(ruta_meta, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def exportar_boveda_cifrada(
    carpeta_sync: str,
    ruta_db: str,
    carpeta_uploads: str = "",
    clave_sync: str = "",
    nombre_equipo: str = "Dispositivo PBM",
    revision_actual: int = 1
) -> tuple[bool, str]:
    """
    Empaqueta la base de datos (marcadores.db) y archivos adjuntos con AES-256.
    Escribe primero en un archivo temporal (.tmp) para garantizar escrituras atómicas
    y evitar lecturas parciales por clientes de sincronización como Google Drive o MEGA.
    """
    if not carpeta_sync or not os.path.isdir(carpeta_sync):
        return False, "La carpeta de sincronización no existe o no es accesible."

    if not os.path.exists(ruta_db):
        return False, "La base de datos local (marcadores.db) no existe."

    zip_final = os.path.join(carpeta_sync, VAULT_ZIP_NAME)
    zip_tmp = os.path.join(carpeta_sync, f"{VAULT_ZIP_NAME}.tmp")
    meta_final = os.path.join(carpeta_sync, VAULT_META_NAME)

    try:
        modo_cifrado = pyzipper.WZ_AES if clave_sync else None
        
        with pyzipper.AESZipFile(
            zip_tmp,
            "w",
            compression=pyzipper.ZIP_DEFLATED,
            encryption=modo_cifrado
        ) as zf:
            if clave_sync:
                zf.setpassword(clave_sync.encode("utf-8"))

            # 1. Base de datos SQLite de marcadores
            zf.write(ruta_db, arcname=DB_FILE_NAME)

            # 2. Archivos adjuntos o estáticos adicionales (si aplica)
            if carpeta_uploads and os.path.exists(carpeta_uploads):
                for raiz, _, archivos in os.walk(carpeta_uploads):
                    for archivo in archivos:
                        ruta_comp = os.path.join(raiz, archivo)
                        ruta_rel = os.path.relpath(ruta_comp, carpeta_uploads)
                        zf.write(ruta_comp, arcname=os.path.join("uploads", ruta_rel))

        # Respaldo rotativo previo de seguridad
        if os.path.exists(zip_final):
            prev_backup = os.path.join(carpeta_sync, VAULT_PREV_NAME)
            shutil.copy2(zip_final, prev_backup)

        # Reemplazo atómico
        os.replace(zip_tmp, zip_final)

        # Generación de metadatos y candado de integridad SHA-256
        hash_zip = calcular_sha256(zip_final)
        metadatos = {
            "revision": revision_actual,
            "ultimo_equipo": nombre_equipo,
            "timestamp": int(time.time()),
            "hash_zip": hash_zip,
            "tiene_clave": bool(clave_sync),
            "token_verificador": derivar_token_verificador(clave_sync)
        }

        with open(meta_final, "w", encoding="utf-8") as f:
            json.dump(metadatos, f, indent=4)

        return True, f"Bóveda PBM exportada exitosamente (Revisión #{revision_actual})"

    except Exception as e:
        if os.path.exists(zip_tmp):
            try:
                os.remove(zip_tmp)
            except OSError:
                pass
        return False, f"Fallo en la exportación: {str(e)}"


def importar_boveda_cifrada(
    carpeta_sync: str,
    ruta_db_destino: str,
    carpeta_uploads_destino: str = "",
    clave_sync: str = ""
) -> tuple[bool, str]:
    """
    Verifica integridad SHA-256 contra .meta, valida la clave de descifrado
    y restaura la base de datos de marcadores de forma atómica.
    """
    ruta_zip = os.path.join(carpeta_sync, VAULT_ZIP_NAME)
    meta = leer_metadatos_remotos(carpeta_sync)

    if not os.path.exists(ruta_zip) or not meta:
        return False, "No se encontraron archivos válidos de sincronización de PBM."

    # Candado de integridad: verificar si el archivo sigue en transferencia
    hash_disco = calcular_sha256(ruta_zip)
    if hash_disco != meta.get("hash_zip"):
        return False, "El paquete de la nube está incompleto o aún sincronizándose en disco."

    # Verificación de clave
    if meta.get("tiene_clave"):
        if not clave_sync:
            return False, "La bóveda remota requiere clave de descifrado."
        if derivar_token_verificador(clave_sync) != meta.get("token_verificador"):
            return False, "Clave de descifrado incorrecta."

    temp_dir = tempfile.mkdtemp(prefix="pbm_sync_import_")
    try:
        with pyzipper.AESZipFile(ruta_zip, "r") as zf:
            if clave_sync:
                zf.setpassword(clave_sync.encode("utf-8"))
            zf.extractall(temp_dir)

        # Respaldo de seguridad local antes de sobreescribir marcadores.db
        db_extraida = os.path.join(temp_dir, DB_FILE_NAME)
        if os.path.exists(db_extraida):
            if os.path.exists(ruta_db_destino):
                shutil.copy2(ruta_db_destino, f"{ruta_db_destino}.pre_sync")
            shutil.copy2(db_extraida, ruta_db_destino)

        # Restaurar adjuntos si existen en el paquete
        uploads_extraidos = os.path.join(temp_dir, "uploads")
        if os.path.exists(uploads_extraidos) and carpeta_uploads_destino:
            os.makedirs(carpeta_uploads_destino, exist_ok=True)
            for item in os.listdir(uploads_extraidos):
                origen = os.path.join(uploads_extraidos, item)
                destino = os.path.join(carpeta_uploads_destino, item)
                if os.path.isfile(origen):
                    shutil.copy2(origen, destino)

        rev = meta.get("revision", "?")
        equipo = meta.get("ultimo_equipo", "Desconocido")
        return True, f"Actualizado a la Revisión #{rev} desde {equipo}"

    except RuntimeError:
        return False, "Error criptográfico: clave de sincronización inválida o paquete dañado."
    except Exception as e:
        return False, f"Fallo al restaurar: {str(e)}"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)