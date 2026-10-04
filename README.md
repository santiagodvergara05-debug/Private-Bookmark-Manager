# Private Bookmark Manager (PBM) — v3.0.x

[![Versión](https://img.shields.io/badge/Versión-3.0.x-blue.svg)](version.py)
[![Python](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![Licencia](https://img.shields.io/badge/Licencia-GNU%20AGPLv3-orange.svg)](LICENSE)
[![Cifrado](https://img.shields.io/badge/Cifrado-E2EE%20AES--256-blueviolet.svg)]()
[![Plataforma](https://img.shields.io/badge/Plataforma-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

Gestor de marcadores privado, autocontenido y de alta resiliencia diseñado para ejecutarse como servidor local o servicio centralizado en redes de área local (LAN). Incorpora un gestor de arranque defensivo (*Bootloader Gen 3*) con protocolo de recuperación ante desastres en caliente (*Disaster Recovery*), motor de sincronización multinube **BYOC** (*Bring Your Own Cloud*) con cifrado Zero-Knowledge **AES-256**, auditoría estructural para SQLite, dock de acciones por lote, importador inteligente universal y consola administrativa fuera de banda.

---

<div align="center">
  <table>
    <tr>
      <td align="center" valign="top">
        <b>Vista Escritorio</b><br><br>
        <img width="500" alt="Vista Escritorio" src="https://github.com/user-attachments/assets/95f317f8-c2ab-4376-a014-2c840f4e2ede" />
      </td>
      <td align="center" valign="top">
        <b>Diseño Móvil (LAN / Responsive)</b><br><br>
        <img width="260" alt="Diseño Móvil" src="https://github.com/user-attachments/assets/0eb24d93-f8b8-450d-8d78-55aeaf3811bc" />
      </td>
    </tr>
  </table>
</div>

---

## Novedades Principales de la Versión 3.0.x

* **Sincronización BYOC Zero-Knowledge (E2EE AES-256):** Mecanismo de sincronización descentralizada compatible con cualquier proveedor en la nube (Microsoft OneDrive, Google Drive, MEGAsync, Dropbox, pendrive USB o recurso compartido LAN) sin servidores intermediarios. La base de datos se cifra y comprime localmente mediante `pyzipper` con verificación estricta de integridad SHA-256.
* **Bootloader Defensivo Gen 3 con Disaster Recovery:** Inspección binaria preventiva del archivo `.env` inmune a corrupción de bytes nulos (`\x00`), aislamiento automático en cuarentena (`.env.corrupt_*` / `marcadores.db.corrupt_*`) y **rescate automático en caliente**: si la base local se borra o corrompe, el bootloader reconstruye el sistema restaurando automáticamente la última copia íntegra disponible en la nube.
* **Pastilla Reactiva de Sincronización en Header:** Indicador visual inteligente en tiempo real (`[ ☁ Sincronizar ● ]` / `[ ☁ Al día ● ]`). Detecta tanto modificaciones locales recientes en `marcadores.db` pendientes de subir como versiones superiores creadas desde otros dispositivos conectadas a la carpeta compartida.
* **Selector Nativo de Carpetas en un Clic:** Integración nativa con el explorador de archivos del sistema operativo (PowerShell / Tkinter / Zenity). Con un solo clic en *«Examinar»*, PBM aprovisiona automáticamente el directorio `PBM_Sync` en la nube seleccionada.
* **Consola Administrativa Fuera de Banda (`CLI_admin.py`):** Panel interactivo por terminal con telemetría viva ANSI (conteo de registros, diagnóstico de enlace BYOC, espacio en disco, estado de cuarentena y rotación atómica de llaves de 256 bits).
* **Simulador de Caos y Estrés (`CLI_Chaos.py`):** Suite de ingeniería del caos para verificar la resiliencia del software mediante sabotaje de cabeceras SQLite, fragmentación de B-Tree, bloqueos concurrentes de archivo, inyección de metadatos rotos y pruebas de rechazo criptográfico SHA-256.
* **Batch Actions Dock (Acciones por Lote):** Cápsula flotante inferior con selección múltiple desacoplada e independiente para carpetas y marcadores. Permite traslados atómicos de ramas completas y purgas masivas con confirmación protegida.
* **Smart Dropzone & Interfaz Dual:** Soporte integrado de temas Claro y Oscuro con contraste adaptativo, carga de respaldos universales (.JSON nativo y .HTML Netscape) con validación estricta de tamaño en el cliente (tope 25 MB).

---

## Funcionalidades del Sistema

### 1. Sincronización Multinube BYOC (E2EE)
* **Arquitectura Zero-Knowledge:** Tu información viaja cifrada con AES-256 de extremo a extremo. El proveedor de almacenamiento en la nube solo ve paquetes binarios cifrados (`pbm_vault.zip`) y firmas criptográficas (`pbm_vault.meta`).
* **Protección Anti-Atraso:** Si en la nube existe una revisión más reciente (`#Remota > #Local`), las subidas quedan estrictamente bloqueadas para evitar sobreescritura o pérdida de datos.
* **Extracción Atómica y Verificación SHA-256:** Antes de reemplazar la base de datos local, el sistema valida la firma hash del archivo descargado. Si el paquete se encuentra incompleto o dañado, la operación se cancela sin alterar la base activa.
* **Rotación Criptográfica en un Clic:** Regeneración asistida de `SYNC_CLAVE` con re-cifrado inmediato de la bóveda remota, eliminación de paquetes anteriores e incremento de revisión.

### 2. Gestión Integral de Marcadores y Carpetas
* **Árbol Jerárquico Completo:** Creación, edición de nombre y reubicación de carpetas a cualquier nivel de la estructura o hacia la raíz.
* **Prevención de Ciclos:** Validación algorítmica recursiva (`es_subcarpeta_de`) que impide crear referencias circulares al reubicar carpetas.
* **Seguimiento de Progreso Numérico:** Contadores de avance rápido (`+` / `−`) integrados directamente en cada fila, ideales para mangas, series, cómics, libros técnicos o cursos en línea.
* **Notas y Metadatos Contextuales:** Adición de notas flotantes con despliegue interactivo sin abandonar la vista principal.
* **Captura Automática de Títulos:** Extracción remota asistida del contenido de la etiqueta `<title>` mediante web scraping asíncrono.
* **Modal Reactivo de Eliminación:** Consulta asíncrona (`fetch`) previa al borrado que muestra el conteo exacto de elementos y ofrece borrado condicional: preservar marcadores en la raíz o eliminar en cascada.

### 3. Acciones Masivas (Batch Dock)
* **Controles Desacoplados:** Botones independientes de *Seleccionar todos* para la sección de carpetas y la de marcadores.
* **Dock Flotante Ergonómico:** Barra fija inferior que muestra en tiempo real la cantidad de elementos seleccionados sin interrumpir la navegación.
* **Traslados Atómicos:** Movimiento masivo de múltiples enlaces y carpetas a un nuevo destino en una única transacción SQLite.
* **Borrado Rápido Protegido:** Purga masiva de enlaces seleccionados bajo confirmación previa.

### 4. Seguridad, Control de Acceso y Resiliencia
* **Sesiones Seguras:** Cookies endurecidas con directivas `HttpOnly` y aislamiento perimetral `SameSite=Lax`.
* **Cierre Global de Sesiones en Caliente:** Rotación inmediata de `SECRET_KEY` en memoria viva (RAM) y persistida en disco, cerrando todas las sesiones web de la red sin reiniciar el servidor.
* **Protección Perimetral DoS:** Umbral de carga fijado en 100 MB con controlador global para desbordes HTTP 413.
* **Llave Maestra (Master Key):** Token criptográfico volátil en RAM (`INICIO_SERVIDOR`) para autorizar modificaciones de puertos, interfaces de red o vaciado de datos durante 2 minutos.

### 5. Portabilidad y Respaldos
* **Smart Dropzone:** Zona interactiva de carga que detecta automáticamente si el archivo suministrado es `.json` o `.html`, valida su peso en el cliente (tope 25 MB) y lo deriva al motor de importación adecuado.
* **JSON Nativo:** Respaldo íntegro de base de datos relacional (incluye relaciones jerárquicas, progreso, notas y metadatos).
* **HTML Estándar Netscape:** Compatibilidad total de importación y exportación con Chrome, Firefox, Brave, Opera y Edge con aplanamiento automático de carpetas raíz redundantes (*"Barra de favoritos"*).

---

## Arquitectura de Archivos

| Archivo / Módulo | Rol en el Sistema | Responsabilidad Principal |
| :--- | :--- | :--- |
| `app.py` | Núcleo / Servidor | Bootloader Gen 3, Disaster Recovery BYOC, sanitización binaria de `.env` y arranque Flask. |
| `database.py` | Persistencia | Conexiones SQLite con cierre garantizado (`try...finally`), CRUD y prevención de ciclos. |
| `sync_manager.py` | Motor Criptográfico | Empaquetado AES-256 (`pyzipper`), auditoría de metadatos `.meta` y cálculo SHA-256. |
| `routes.py` | Controlador HTTP | Enrutamiento web, seguridad perimetral, telemetría y endpoints de operaciones en lote y sync. |
| `logger_http.py` | Telemetría HTTP | Traductor de peticiones de red a lenguaje natural con etiquetas ANSI y códigos traducidos. |
| `bookmarks_html.py` | Motor HTML | Parser y generador estándar Netscape con aplanamiento inteligente de barra de favoritos. |
| `version.py` | Metadatos | Registro unificado de versión del software (`VERSION = "3.2.0"`). |
| `CLI_admin.py` | Operaciones CLI | Consola administrativa fuera de banda para credenciales, red, mantenimiento y BYOC. |
| `CLI_Chaos.py` | Pruebas de Estrés | Inyector de caos y fallos para verificar tolerancia a corrupción y autorreparación. |
| `static/style.css` | Capa Visual | Variables de diseño adaptativo (Modo Claro / Oscuro), Smart Dropzone y Dock flotante. |
| `templates/` | Plantillas Jinja2 | Vistas modulares: `index.html`, `login.html`, `editar_carpeta.html`, `configuracion.html`. |

---

## Puesta en Marcha

### Opción 1: Ejecutables Autónomos (Sin instalación previa de Python)

1. Descarga el paquete distribuible de la versión desde la sección de Releases.
2. Ejecuta `PBMPrivateBookmarkManager.exe`.
3. El sistema verificará el entorno, provisionará `marcadores.db` y `.env` automáticamente, y abrirá tu navegador en `http://127.0.0.1:5050`.
4. Credencial predeterminada de fábrica: `cambiame`.
5. Para realizar tareas de mantenimiento, rotación de llaves o rescate, ejecuta `CLI_admin.exe` en la misma carpeta.

---

### Opción 2: Ejecución desde Código Fuente

**Requisitos:** Python 3.10 o superior instalado.

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/santiagodvergara05-debug/Private-Bookmark-Manager.git
   cd Private-Bookmark-Manager
   ```

2. **Inicio automatizado por scripts:**
   * **En Windows:** Ejecuta con doble clic `start.bat`.
   * **En Linux / macOS / Raspberry Pi:**
     ```bash
     chmod +x start.sh
     ./start.sh
     ```

3. **Inicio manual alternativo:**
   ```bash
   # Crear y activar entorno virtual
   python -m venv .venv

   # Windows
   .venv\Scripts\activate
   # Linux / macOS
   source .venv/bin/activate

   # Instalar dependencias
   pip install -r requirements.txt

   # Arrancar el servidor
   python app.py
   ```

---

## Variables de Configuración (`.env`)

El archivo `.env` se autogenera y cura automáticamente al iniciar el sistema. Puede editarse manualmente o mediante `CLI_admin.py`:

```ini
# Control de inicialización del núcleo
SISTEMA_INICIALIZADO='true'

# Seguridad y Criptografía Web
SECRET_KEY='llave_hexadecimal_sesion_flask_256'
MASTER_KEY='llave_hexadecimal_maestra_256'
APP_PASSWORD='tu_contrasena_segura'
CONTRASENA_MOSTRADA='false'   # Cambia a 'true' automáticamente tras el primer acceso exitoso

# Preferencias de Interfaz
MOSTRAR_FAVICONS='true'
ABRIR_NUEVA_PESTANA='true'
MODO_OSCURO='false'

# Comportamiento del Servidor
AUTO_ABRIR_NAVEGADOR='true'   # Activo por defecto en entornos de escritorio

# Red y Enlace (Requiere MASTER_KEY para modificarse desde la web)
PORT='5050'
HOST='127.0.0.1'              # Cambiar a '0.0.0.0' para acceso multidispositivo en toda la LAN
FLASK_DEBUG='false'           # Solo modificable vía CLI o archivo; activa herramientas de caos
LOG_MODE='false'              # 'true' activa telemetría unificada en terminal con etiquetas ANSI

# Módulo de Sincronización BYOC (E2EE AES-256)
SYNC_HABILITADO='false'       # 'true' activa el motor de sincronización multidispositivo
SYNC_CARPETA=''               # Ruta absoluta a tu carpeta en la nube (ej: C:\Users\TuUsuario\OneDrive\PBM_Sync)
SYNC_MODO_CIFRADO='auto'      # 'auto' (AES-256 recomendado) o 'libre' (ZIP abierto para uso en pendrive)
SYNC_CLAVE='llave_hexadecimal_aes256_compartida'
SYNC_AUTO_APLICAR='true'      # Auto-aplica revisiones remotas superiores al iniciar el servidor
SYNC_NOMBRE_DISPOSITIVO='PC-Escritorio'
SYNC_ULTIMA_REVISION='0'      # Número de revisión incremental
```

---

## Herramientas de Administración y Caos

### 1. Consola Administrativa (`CLI_admin.py`)

Herramienta fuera de banda para gestionar la instancia sin requerir el navegador o en caso de pérdida de credenciales:
```bash
python CLI_admin.py
```
* **Inspección y Rotación:** Consulta y regeneración de `APP_PASSWORD`, `MASTER_KEY` y `SYNC_CLAVE` (256 bits).
* **Parámetros de Red:** Alternancia entre enlace local (`127.0.0.1`) o red completa (`0.0.0.0`) y modificación de puertos HTTP.
* **Control BYOC:** Activación/desactivación del servicio de sincronización, ajuste del nombre del dispositivo y reseteo seguro de revisiones.
* **Higiene:** Purga de cuarentena, archivos temporales residuales (`.pre_sync`, `*.tmp`) y restauración de fábrica bajo confirmación estricta (`CONFIRMAR`).

### 2. Simulador de Caos y Estrés (`CLI_Chaos.py`)

Herramienta de pruebas de resiliencia (requiere `FLASK_DEBUG=true` en `.env`):
```bash
python CLI_Chaos.py
```
* **Pruebas SQLite:** Corrupción deliberada del *Magic Header*, inyección de ruido binario en el árbol B-Tree, eliminación de tablas relacionales (*Schema Drift*) y bloqueos transaccionales exclusivos (`BEGIN EXCLUSIVE`).
* **Pruebas de Red y Configuración:** Inyección de puertos e interfaces fuera de rango (`PORT=99999`) y sabotaje binario con bytes nulos (`\x00\xFF`).
* **Pruebas BYOC:** Mutilación de archivos `pbm_vault.zip` para validar el rechazo por firma SHA-256, inyección de JSON inválido en `pbm_vault.meta` y simulación de conflicto de revisión superior (`#99999`).

---

## Generación de Ejecutables (`.exe`)

Para compilar la aplicación en binarios autónomos utilizando PyInstaller:

```bash
# Compilar Servidor Principal
python -m PyInstaller --noconfirm --onefile --console --name "PBMPrivateBookmarkManager" --add-data "templates;templates" --add-data "static;static" app.py

# Compilar Consola Administrativa
python -m PyInstaller --noconfirm --onefile --console --name "CLI_admin" CLI_admin.py

# Compilar Simulador de Caos
python -m PyInstaller --noconfirm --onefile --console --name "CLI_Chaos" CLI_Chaos.py
```

---

## Licencia

Este proyecto está licenciado bajo los términos de la **GNU Affero General Public License v3.0 (GNU AGPLv3)**. Consulta el archivo [LICENSE](LICENSE) para más detalles.