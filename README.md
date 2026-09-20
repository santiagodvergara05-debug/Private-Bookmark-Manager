# Private Bookmark Manager (PBM) — v2.7.0

[![Versión](https://img.shields.io/badge/Versión-2.7.0-blue.svg)](version.py)
[![Python](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![Licencia](https://img.shields.io/badge/Licencia-GNU%20AGPLv3-orange.svg)](LICENSE)
[![Plataforma](https://img.shields.io/badge/Plataforma-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

Gestor de marcadores privado, autocontenido y de alta resiliencia diseñado para ejecutarse como servidor local o servicio centralizado en redes de área local (LAN). Incorpora un gestor de arranque defensivo (*Bootloader Gen 2*) con autorrecuperación de fallos, auditoría estructural para SQLite, dock de acciones por lote, importador universal inteligente y herramientas administrativas fuera de banda.

---

<div align="center">
  <table>
    <tr>
      <td align="center" valign="bottom">
        <b>Vista Escritorio</b><br><br>
        <img width="730" height="743" alt="image" src="https://github.com/user-attachments/assets/95f317f8-c2ab-4376-a014-2c840f4e2ede" />
" />
      </td>
      <td align="center" valign="bottom">
        <b>Diseño Móvil (LAN / Responsive)</b><br><br>
        <img width="540" height="1089" alt="Diseño Móvil" src="https://github.com/user-attachments/assets/86d19773-14a8-4f10-bac8-ca14a1557b20" />
      </td>
    </tr>
  </table>
</div>

---

## Novedades Principales de la Versión 2.7.0

* **Bootloader Defensivo Gen 2:** Detección de entorno binario congelado (`_MEIPASS`), fijación estricta de rutas de trabajo con `os.chdir()`, validación de puertos e interfaces de red, y cuarentena automática ante archivos `.env` o bases de datos dañadas.
* **Batch Actions Dock (Acciones por Lote):** Cápsula flotante inferior con selección múltiple desacoplada e independiente para carpetas y marcadores. Permite traslados atómicos de ramas completas y purgas masivas con un solo clic.
* **Organización Jerárquica sin Ciclos:** Soporte para subcarpetas profundamente anidadas con validación algorítmica recursiva (`es_subcarpeta_de`), impidiendo referencias circulares al reubicar directorios.
* **Modal Reactivo de Eliminación:** Consulta asíncrona (`fetch`) previa al borrado que muestra el conteo exacto de elementos y ofrece borrado condicional: preservar marcadores en la raíz o eliminar en cascada.
* **Importador Inteligente Netscape:** Aplanamiento automático de contenedores raíz del navegador (*"Barra de favoritos"*, *"Bookmarks Bar"*, etc.), ubicando su contenido directamente en el nivel principal.
* **Seguridad Perimetral Endurecida:** Interceptor de peticiones mutantes sin sesión (respuesta 401 estructurada), rotación en caliente de `SECRET_KEY` en memoria RAM para revocación global de sesiones y ventana de desbloqueo administrativo temporal de 120 segundos mediante `MASTER_KEY`.

---

## Funcionalidades del Sistema

### 1. Gestión Integral de Marcadores y Carpetas
* **Árbol Jerárquico Completo:** Creación, edición de nombre y reubicación de carpetas a cualquier nivel de la estructura o hacia la raíz.
* **Seguimiento de Progreso Numérico:** Contadores de avance rápido (`+` / `−`) integrados directamente en cada fila, ideales para mangas, cómics, series, libros técnicos o cursos en línea.
* **Notas y Metadatos Contextuales:** Adición de notas flotantes visibles sin abandonar la vista principal.
* **Captura Automática de Títulos:** Extracción remota del contenido de la etiqueta `<title>` mediante web scraping asistido.
* **Ordenamiento Alfabético Natural:** Consultas SQLite con intercalación `COLLATE NOCASE ASC` para una visualización ordenada e insensible a mayúsculas.

### 2. Acciones Masivas (Batch Dock)
* **Controles Desacoplados:** Botones independientes de *Seleccionar todos* para la sección de carpetas y la de marcadores.
* **Dock Flotante Ergonómico:** Barra fija inferior que muestra en tiempo real la cantidad de elementos seleccionados sin interrumpir la navegación.
* **Traslados Atómicos:** Movimiento masivo de múltiples enlaces y carpetas a un nuevo destino en una única transacción de base de datos.
* **Borrado Rápido Protegido:** Purga masiva de enlaces seleccionados bajo confirmación previa.

### 3. Seguridad y Control de Acceso
* **Sesiones Seguras:** Cookies endurecidas con directivas `HttpOnly` y directivas de aislamiento `SameSite=Lax`.
* **Cierre Global de Sesiones en Caliente:** Rotación inmediata de la llave criptográfica en memoria viva (RAM) y en disco, invalidando todas las cookies activas en la red sin reiniciar el proceso.
* **Protección Perimetral DoS:** Umbral máximo de carga fijado en 25 MiB con controlador global para desbordes HTTP 413.
* **Visibilidad de Contraseña (Toggle Eye):** Control interactivo en la pantalla de inicio de sesión para verificar la clave antes de enviarla.
* **Llave Maestra (Master Key):** Token criptográfico volátil en RAM (`INICIO_SERVIDOR`) para autorizar modificaciones de puertos, interfaces de red o vaciado de datos durante 2 minutos.

### 4. Portabilidad y Respaldos
* **Smart Dropzone:** Zona interactiva de carga que detecta automáticamente si el archivo suministrado es `.json` o `.html`, valida su peso en el cliente (tope 25 MB) y lo deriva al motor de importación adecuado.
* **JSON Nativo:** Respaldo íntegro de base de datos relacional (incluye relaciones jerárquicas, progreso, notas y metadatos).
* **HTML Estándar Netscape:** Compatibilidad total de importación y exportación con Chrome, Firefox, Brave, Opera y Edge.
* **Sistema de Alertas Preventivas:** Monitor de días transcurridos desde el último respaldo con opción de posponer la notificación por 24 horas.

---

## Arquitectura de Archivos

| Archivo / Módulo | Rol en el Sistema | Responsabilidad Principal |
| :--- | :--- | :--- |
| `app.py` | Núcleo / Servidor | Bootloader Gen 2, autocuración de entorno, auditoría de SQLite y arranque Flask. |
| `database.py` | Persistencia | Conexiones SQLite con cierre garantizado (`try...finally`), CRUD y prevención de ciclos. |
| `routes.py` | Controlador HTTP | Enrutamiento web, seguridad perimetral, telemetría y endpoints de operaciones en lote. |
| `bookmarks_html.py` | Motor HTML | Parser y generador estándar Netscape con aplanamiento inteligente de barra de favoritos. |
| `version.py` | Metadatos | Registro unificado de versión del software (`VERSION = "2.7.0"`). |
| `CLI_admin.py` | Operaciones CLI | Consola administrativa fuera de banda para credenciales, red y mantenimiento. |
| `CLI_Chaos.py` | Pruebas de Estrés | Inyector de fallos binarios para comprobar la tolerancia a corrupción del bootloader. |
| `static/style.css` | Capa Visual | Variables de diseño adaptativo (Modo Claro / Oscuro), Smart Dropzone y Dock flotante. |
| `templates/` | Plantillas Jinja2 | Vistas modulares: `index.html`, `login.html`, `editar_carpeta.html`, `configuracion.html`. |

---

## Puesta en Marcha

### Opción 1: Ejecutables Autónomos (Sin instalación previa de Python)

1. Descarga el paquete distribuible de la versión.
2. Ejecuta `PBMPrivateBookmarkManager.exe`.
3. El sistema verificará el entorno, provisionará `marcadores.db` y `.env` automáticamente, y abrirá tu navegador en `http://127.0.0.1:5050`.
4. Credencial predeterminada de fábrica: `cambiame`.
5. Para realizar tareas de mantenimiento, rotación de llaves o rescate, ejecuta `CLI_admin.exe` en la misma carpeta.

---

### Opción 2: Ejecución desde Código Fuente

**Requisitos:** Python 3.10 o superior instalado.

1. **Clonar el repositorio:**
   ```bash
   git clone [https://github.com/santiagodvergara05-debug/Private-Bookmark-Manager.git](https://github.com/santiagodvergara05-debug/Private-Bookmark-Manager.git)
   cd Private-Bookmark-Manager



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

El archivo `.env` se autogenera y cura automáticamente al iniciar el sistema. Puede editarse manualmente o mediante `CLI_admin`:

```ini
# Control de inicialización del núcleo
SISTEMA_INICIALIZADO='true'

# Seguridad y Criptografía
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

```

---

## Herramientas de Mantenimiento

### Consola Administrativa (`CLI_admin.py`)

Permite gestionar la instancia sin requerir el navegador o en caso de pérdida de credenciales:

* **Seguridad:** Rotación atómica de `MASTER_KEY` y `SECRET_KEY`, reseteo de `APP_PASSWORD`.
* **Red:** Cambio dinámico de puertos y alternancia entre enlace local (`127.0.0.1`) o red completa (`0.0.0.0`).
* **Mantenimiento:** Vaciado integral de colecciones y restauración a estado de fábrica bajo confirmación textual estricta.

### Generación de Ejecutables (`.exe`)

Para compilar la aplicación en un binario autónomo utilizando PyInstaller:

```bash
# Compilar Servidor Principal
python -m PyInstaller --noconfirm --onefile --console --name "PBMPrivateBookmarkManager" --add-data "templates;templates" --add-data "static;static" app.py

# Compilar Consola Administrativa
python -m PyInstaller --noconfirm --onefile --console --name "CLI_admin" CLI_admin.py

```

---

## Licencia

Este proyecto está licenciado bajo los términos de la **GNU Affero General Public License v3.0 (GNU AGPLv3)**. Consulta el archivo [LICENSE](https://www.google.com/search?q=LICENSE&utm_source=gemini) para más detalles.

```

```
