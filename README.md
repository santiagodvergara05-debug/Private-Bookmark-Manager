# Private Bookmark Manager (PBM)

Gestor de marcadores privado, ligero y altamente resiliente diseñado para operar como servidor local o en red de área local (LAN). Incluye un gestor de arranque defensivo (*bootloader*) con autorrecuperación de fallos, auditoría de integridad estructural para SQLite y herramientas administrativas desacopladas por línea de comandos.

---

<div align="center">
  <table>
    <tr>
      <td align="center" valign="bottom">
        <b>Vista Escritorio</b><br><br>
        <img width="601" height="475" alt="image" src="https://github.com/user-attachments/assets/9f50cf15-be21-446f-9c7c-077235e62021" />
      </td>
      <td align="center" valign="bottom">
        <b>Diseño Móvil (LAN / Responsive)</b><br><br>
        <img width="540" height="1089" alt="image" src="https://github.com/user-attachments/assets/86d19773-14a8-4f10-bac8-ca14a1557b20" />
      </td>
    </tr>
  </table>
</div>

---
## Funcionalidades del Sistema

* **Gestión de Marcadores y Carpetas:** Organización estructurada de enlaces web agrupados por carpetas personalizadas.
* **Seguimiento de Progreso Numérico:** Contador manual integrado para registrar el avance de lectura o consumo en enlaces específicos (ideal para mangas, cómics, novelas ligeras, series o cursos).
* **Notas Contextuales:** Asignación de recordatorios y notas descriptivas junto al enlace para complementar la información sin necesidad de abrirlo.
* **Autenticación y Seguridad de Acceso:**
  * Servidor web protegido por inicio de sesión (credencial inicial de fábrica: informada en la consola durante el boot inicial).
  * **Métodos para cambiar la contraseña:**
    1. **Desde la consola administrativa:** Ejecutando `CLI_admin.exe` (o `python CLI_admin.py`).
    2. **Desde el archivo de configuración:** Editando `APP_PASSWORD` en `.env` y reiniciando el servidor.
    3. **Desde la interfaz web:** En la sección **Configuración**, desbloqueando los ajustes críticos mediante la `MASTER_KEY` (llave criptográfica de 256 bits consultable en `.env` y regenerable mediante el CLI).

---

## Características Principales

* **Interfaz Adaptable (Responsive):** Optimizada para uso cómodo en teléfonos, tablets o PC al acceder desde la red local (`HOST='0.0.0.0'`).
* **Organización Jerárquica:** Creación de carpetas anidadas, asignación de notas descriptivas y contadores de progreso manual (seguimiento de lecturas, cómics o cursos).
* **Personalización Visual:** Soporte nativo para modo oscuro/claro, alternancia de favicons automáticos y apertura configurable en nueva pestaña.
* **Bootloader Defensivo:**
  * Auto-aprovisionamiento del entorno (`.env`) y generación de llaves criptográficas de 256 bits (`MASTER_KEY`, `SECRET_KEY`).
  * Comprobación de integridad estructural en frío (`PRAGMA integrity_check`).
  * Aislamiento automático en cuarentena (`.corrupt_*`) ante corrupciones de base de datos y reconstrucción en limpio sin interrupción del servicio.
* **Consola Administrativa (`CLI_admin`):** Gestión fuera de banda de contraseñas, rotación criptográfica, alcance de red y restauración de fábrica.
* **Herramienta de Caos (`CLI_Chaos`):** Inyector de fallos binarios para simular caídas de disco y borrados accidentales (bloqueado por seguridad si el modo depuración está desactivado).
* **Portabilidad:** Diseñado para correr en servidores Linux/Raspberry Pi o compilarse como binario autónomo para Windows (`.exe`) sin requerir Python instalado.

---

## Arquitectura del Proyecto

| Archivo | Rol | Descripción |
| :--- | :--- | :--- |
| `app.py` | Núcleo / Servidor | Bootloader de arranque, verificación de entorno y servidor web Flask. |
| `database.py` | Almacenamiento | Controlador SQLite relacional para marcadores, carpetas y esquemas. |
| `routes.py` | Enrutamiento | Lógica de endpoints HTTP, autenticación de sesión y gestión de vistas. |
| `CLI_admin.py` | Operaciones | Panel de terminal para rotación de credenciales y ajustes del sistema. |
| `CLI_Chaos.py` | QA / Stress Test | Herramienta de inyección de corrupción binaria y validación de resiliencia. |
| `Marcadores_env.example` | Plantilla | Estructura base documentada para el archivo `.env`. |

---

## Puesta en Marcha

### Opción 1: Ejecutables Independientes (Sin Python)

1. Descarga el paquete distribuible o compila los ejecutables.
2. Ejecuta `MarcadoresPrivados.exe`. El sistema creará los archivos `marcadores.db` y `.env` automáticamente y abrirá el navegador en `[http://127.0.0.1:5050](http://127.0.0.1:5050)`.
3. Contraseña predeterminada de fábrica: `cambiame`.
4. Para tareas de mantenimiento o rotación de credenciales, ejecuta `CLI_admin.exe` en la misma carpeta.

### Opción 2: Ejecución desde Código Fuente

**Requisitos:** Python 3.10 o superior.

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/santiagodvergara05-debug/Private-Bookmark-Manager.git
   cd Private-Bookmark-Manager


Iniciar automáticamente con scripts:

--> En Windows: ejecuta start.bat

--> En Linux / Raspberry Pi: ejecuta chmod +x start.sh && ./start.sh

Inicio manual alternativo:
```
python -m venv .venv
# En Windows:
.venv\Scripts\activate
# En Linux:
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```
Configuración del Entorno (.env)
El archivo .env se autogenera en el primer arranque, pero puede ajustarse manualmente o mediante CLI_admin:

```# Bandera de control de inicio
SISTEMA_INICIALIZADO='true'

# Criptografía y acceso
SECRET_KEY='llave_sesion_flask_hex_256'
MASTER_KEY='llave_maestra_hex_256'
APP_PASSWORD='tu_contraseña_aqui'

# Parámetros de Interfaz
MOSTRAR_FAVICONS=
ABRIR_NUEVA_PESTANA=
MODO_OSCURO=

# Red y Servidor
PORT='5050'
HOST='127.0.0.1'       # Usar '0.0.0.0' para habilitar acceso en toda la LAN
FLASK_DEBUG='false'    # 'true' habilita herramientas de caos y desarrollo
LOG_MODE='false'       # 'true' activa telemetría de solicitudes en consola
```

Herramientas Administrativas
Panel de Administración (CLI_admin.py)
Permite operar el sistema en paralelo mientras el servidor está activo:

Seguridad: Rotación atómica de MASTER_KEY y SECRET_KEY, cambio de contraseña web.

Red: Cambio dinámico de puertos y alternancia entre interfaz Local (127.0.0.1) o Global (0.0.0.0).

Mantenimiento: Restauración completa de fábrica con confirmación explícita (BORRAR).

Suite de Caos (CLI_Chaos.py)
Utilidad reservada para validación y desarrollo:

Requiere estrictamente FLASK_DEBUG='true' en .env para ejecutarse.

Permite corromper cabeceras de SQLite, dañar bloques internos de datos o simular eliminaciones accidentales de disco para evaluar las rutinas de rescate del bootloader.

Compilación a Ejecutables (.exe)
Para empaquetar la solución sin dependencias externas mediante PyInstaller:

# Compilar servidor principal
```pyinstaller --noconfirm --onefile --console --name "PBMPrivateBookmarkManager" --add-data "templates;templates" --add-data "static;static" app.py```

# Compilar consola administrativa
```pyinstaller --noconfirm --onefile --console --name "CLI_admin" CLI_admin.py```

Licencia
Distribuido bajo la Licencia GNU GPLv3. Consulta el archivo LICENSE para más información.
