<div align="center">

# IDEye (Motor Vistax L2C)
**El motor de programación Look-To-Code (L2C) para ingeniería de software manos libres y silenciosa**

[![English](https://img.shields.io/badge/Language-English-blue?style=flat-square)](README.md)
[![Español](https://img.shields.io/badge/Idioma-Español-red?style=flat-square)](README.es.md)

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Lanzamiento: v0.5.0](https://img.shields.io/badge/Lanzamiento-v0.5.0-blue.svg?style=for-the-badge&logo=github)](https://github.com/danicaju/IDEye/releases)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-FaceMesh%20468-00A8E8?style=for-the-badge&logo=google&logoColor=white)](https://developers.google.com/mediapipe)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6%20No--Focus-41CD52?style=for-the-badge&logo=qt&logoColor=white)](https://www.riverbankcomputing.com/software/pyqt/)
[![Pruebas](https://img.shields.io/badge/Pruebas-630%20Aprobadas-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)](#-testing-y-qa)
[![Licencia: MIT](https://img.shields.io/badge/Licencia-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

*Escribe código de producción real usando únicamente una webcam estándar, seguimiento ocular híbrido y gestos faciales discretos. Sin manos. Sin comandos de voz. Sin hardware infrarrojo caro.*

[Descargas Rápidas](#-descargas-y-versiones-precompiladas) • [Inicio Rápido](#-inicio-rápido) • [Cómo Funciona](#-cómo-funciona-en-3-pasos-flujo-de-interacción) • [Explorar Arquitectura](#-arquitectura-del-sistema) • [Innovaciones](#-innovaciones-principales) • [Controles en Vivo](#-controles-y-atajos-en-tiempo-real) • [Hoja de Ruta](#-hoja-de-ruta)

---

<!-- TODO: Reemplazar con un GIF de 15 segundos grabado con OBS mostrando cómo programas en VS Code con el HUD -->
![Demostración de IDEye](https://via.placeholder.com/900x450/0d1117/58a6ff?text=Insertar+GIF+Demostracion:+HUD+3x3+IDEye+en+VS+Code)

</div>
> [!TIP]
> **¿Solo quieres usar IDEye sin programar ni instalar Python?**
> Descarga la versión portátil precompilada y la extensión de VS Code directamente desde **[GitHub Releases](https://github.com/danicaju/IDEye/releases)**:
> * **`IDEye-Windows-v0.5.0.zip`** — Aplicación de escritorio para Windows (descomprimir y doble clic en `IDEye.exe`).
> * **`ideye-vscode-bridge-0.5.0.vsix`** — Extensión nativa para VS Code (arrastrar y soltar dentro de VS Code).


## El Problema y por qué existe IDEye

Los desarrolladores que sufren lesiones graves por esfuerzos repetitivos (RSI), túnel carpiano, parálisis o problemas del habla se enfrentan a una barrera crítica al intentar escribir código:
1. **Las herramientas de voz (Talon, Cursorless)** son fantásticas, pero requieren vocalización constante, lo que falla en espacios compartidos, bibliotecas o para usuarios con dificultades en el habla.
2. **Los teclados en pantalla (OptiKey)** obligan a escribir letra por letra (`f`-`o`-`r`-`espacio`...) y prácticamente exigen sensores infrarrojos caros de $300–$1,000 (Tobii) porque las webcams normales tienen un error de dispersión de 100–150px.
3. **Los drivers de ratón por webcam (Project Gameface, eViacam)** solo mueven el cursor del sistema; hacer clic en iconos diminutos de 15px en el IDE o sufrir el *"problema del toque de Midas"* (fatiga por tiempo de espera) hace que programar sea agotador.

**IDEye (Vistax)** resuelve esto replanteando la interfaz de desarrollo desde sus cimientos: combinando un **HUD de macro-zonas AST 3x3**, **seguimiento híbrido de cabeza e iris con supresión de parpadeo**, **desencadenantes instantáneos por gestos faciales**, **integración WebSocket bidireccional con VS Code** y **predicción de contexto en vivo mediante AST e IA**.

### Comparativa con el Estado del Arte

| Característica / Herramienta | Webcam estándar ($0) | 100% Silencioso (Sin voz) | Inyección de Bloques de Código (AST) | Conciencia de Variables Locales | Puente WebSocket bidireccional con VS Code + modos automáticos + FreeLook/Gaming a 60 Hz |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Talon Voice / Cursorless** | No | No | Sí | Sí | No |
| **OptiKey** | Parcial *(Se recomienda IR)* | Sí | No *(Carácter por carácter)* | No | No |
| **Google Project Gameface** | Sí | Sí | No *(Solo controlador de ratón)* | No | No |
| **IDEye (Vistax L2C)** | **Sí** | **Sí** | **Sí (Macro-HUD 3x3)** | **Sí (AST + IA)** | **Sí** |

---

### Cómo Funciona en 3 Pasos (Flujo de Interacción)

```mermaid
flowchart LR
    classDef step1 fill:#0d233a,stroke:#38bdf8,stroke-width:2px,color:#e0f2fe;
    classDef step2 fill:#062d22,stroke:#34d399,stroke-width:2px,color:#d1fae5;
    classDef step3 fill:#271238,stroke:#c084fc,stroke-width:2px,color:#f3e8ff;
    classDef actionNode fill:#1c2433,stroke:#64748b,stroke-width:1px,color:#f8fafc;

    subgraph S1 ["PASO 1: MIRA (Navegación)"]
        direction TB
        A1["Mirada / Cabeza (Webcam $0)"]:::actionNode --> A2["Ilumina Macro-Zona 3x3"]:::actionNode
        A2 --> A3["Sin Toque de Midas (Zero-Dwell)"]:::step1
    end

    subgraph S2 ["PASO 2: BOCA (Acción Instantánea)"]
        direction TB
        B1["Apertura breve de boca (MAR)"]:::actionNode --> B2["CLIC / Inyección de Código"]:::step2
        B1 -.->|"Mantener boca abierta"| B3["Arrastre Jaw-Lock"]:::actionNode
    end

    subgraph S3 ["PASO 3: GUIÑOS (Control Global)"]
        direction TB
        C1["Guiño Derecho"]:::actionNode --> C2["Pausar / Ocultar HUD"]:::step3
        C3["Guiño Izquierdo"]:::actionNode --> C4["Volver Atrás / Deshacer (Ctrl+Z)"]:::step3
    end

    S1 ==>|"1. Selecciona bloque"| S2
    S2 -.->|"2. Corrige o pausa"| S3

    class S1 step1;
    class S2 step2;
    class S3 step3;
```


---

## Innovaciones Principales

### 1. Centroide Craneal Subpíxel y Seguimiento Multi-Modo
El seguimiento ocular puro con webcam carece de rango dinámico a distancia normal de monitor. IDEye fusiona el desplazamiento normalizado del iris con el vector anclado 3D de la punta de la nariz:

$$\mathbf{P}_{raw} = \alpha_{head} \cdot \mathbf{V}_{nose} + (1 - \alpha_{head}) \cdot \mathbf{V}_{iris}$$

$$\mathbf{S}_t = \gamma \cdot \mathbf{P}_{raw} + (1 - \gamma) \cdot \mathbf{S}_{t-1}$$

Donde $\alpha_{head} \approx 0.60$ aporta estabilidad macro en las esquinas y $1 - \alpha_{head} \approx 0.40$ permite microajustes rápidos con los ojos.

Para estabilidad subpíxel, IDEye calcula un centroide craneal a partir de los landmarks `[1,4,6,168,195,197]` de MediaPipe FaceMesh, con pesos mayores en los anclajes estables `6`, `168` y `197`. Una puerta de histéresis (`STATIC_LOCK_RADIUS=0.0035`, `STATIC_BREAKOUT_RADIUS=0.0085`, confirmación de 3 frames, deriva de `0.0px`) suprime el micro-temblor durante las fijaciones sin añadir latencia a las sácadas. Se proporcionan tres modos de seguimiento:
* **`HEAD_PRIMARY`** — seguimiento suave basado en cabeza por defecto.
* **`PURE_IRIS`** — mediana de 5 muestras de iris más compensación de rol con anclajes orbitales múltiples para control exclusivo con los ojos.
* **`HYBRID`** — fusiona señales de cabeza e iris con un coeficiente de sácada adaptativo que rampa de `0.08` a `0.55` para transiciones rápidas y estables.

### 2. Eliminación del "Toque de Midas" sin Tiempos de Espera + Jaw-Lock
La navegación y la activación están totalmente desacopladas: mirar solo ilumina, nunca clica. Una breve apertura de boca realiza un clic/inyección instantáneo, mientras mantener la boca abierta por encima de tu umbral MAR de reposo activa el modo de arrastre **Jaw-Lock**. Sin temporizadores de fijación no hay clics Midas accidentales mientras se lee.

### 3. Motor de Estrategia de 6 Modos + Cambio Automático por WebSocket
El `ModeManager` alberga seis modos especializados - `CODING_MODE`, `WRITING_MODE`, `TERMINAL_GIT_MODE`, `DATA_MATH_MODE`, `NAVIGATION_READ_MODE` y `FREELOOK_GAMING_MODE` - y puede cambiar automáticamente según el contexto de VS Code recibido a través del puente WebSocket bidireccional. FreeLook ofrece control suave de cámara/mirada a 60 Hz; Gaming usa un **joystick de cabeza con zona muerta central** para moverte con WASD, y un guiño derecho alterna el cursor de menú para botones del juego. El modo Redacción combina un **teclado de letras** accesible por mirada con un **Motor Predictivo de Palabras y Frases** que sugiere palabras y frases completas mientras escribes.

Los snippets de delimitadores dejan el cursor tras el cierre, de modo que un nombre seguido de `()` queda como `func()` y el siguiente `:` cae en su sitio en Google Docs o cualquier editor externo. FreeLook adem?s libera un Jaw-Lock atascado tras dos segundos y recentra con seguridad al perder la cara.

La detecci?n de gui?os aprende una l?nea base EAR por ojo, descarta parpadeos bilaterales, caras lejanas, giros extremos y cierres demasiado breves, y expone duraci?n, enfriamiento, margen y distancia en user_settings.json.

### 4. Desduplicación Inteligente de Prefijos
La tubería de escritura desduplica pulsaciones de prefijo repetidas: `h+hola` se convierte en `ola`, y `h+Hola` en retroceso seguido de `Hola`. Rastrea espacios, puntuación, flechas y estado de retroceso, y funciona de forma idéntica a través del puente WebSocket de VS Code. Cuando un par de delimitadores sigue a un nombre, el cursor queda después del par (`func` + `()` -> `func()`); en una posición vacía el par conserva el cursor centrado.

### 5. HUD Glass & Focus + Lucide Alta DPI + Audio Procedural
El HUD renderiza paneles Glass y Focus con iconos Lucide/SVG de alta definición. La retroalimentación sonora se sintetiza proceduralmente con `numpy` y se cachea como archivos WAV pequeños en `tempfile.gettempdir()/ideye_audio_cache`; la reproducción usa el backend nativo asíncrono `winsound`, sin empaquetar audio externo y manteniendo la app totalmente offline.

### 6. Parser AST en Vivo Tolerante a Fallos y Predictor IA Asíncrono
El código a medio escribir rara vez compila. `ContextReader` combina el módulo nativo `ast.walk()` de Python con un motor de respaldo ordenado por líneas basado en expresiones regulares para extraer variables locales, argumentos y clases del archivo activo — incluso cuando hay un `SyntaxError` temporal. Alimenta un worker asíncrono (`Ollama` / API / Heurísticas locales) para rellenar completados con un solo clic, preservando siempre los botones de Pausa y Volver.

### 7. HUD No-Intrusivo `WindowDoesNotAcceptFocus` + Calibración
Construido con `PyQt6`, el overlay transparente se sitúa sobre VS Code, PyCharm o cualquier IDE usando `Qt.WindowType.WindowDoesNotAcceptFocus` y el estilo Win32 nativo `WS_EX_TRANSPARENT`. Tu editor nunca pierde el foco del teclado ni el parpadeo del cursor, y los clics de ratón físicos atraviesan la cuadrícula transparente hacia el código subyacente. El asistente de calibración visual de 5 puntos guarda el mapeo en `calibration_profile.json`.

### 8. Puente Bidireccional con VS Code + Menús Multilingües
El `WebSocketBridge` intercambia estado del editor, diagnósticos e información de selección con la extensión de VS Code en tiempo real, permitiendo el cambio automático de modo contextual y la inyección de snippets. Los árboles sintácticos están disponibles en varios idiomas, incluyendo un diccionario de palabras comunes en español y etiquetas de menú localizadas.

### 9. Máquina del Tiempo del Portapapeles e Inteligencia de Ventana Activa
`ClipboardHistory` conserva las seis copias más recientes del usuario en una cuadrícula 3x3 y excluye las escrituras atómicas internas de IDEye, evitando contaminar el historial. `WindowWatcher` sondea la ventana activa cada 500 ms, aplica debounce a cambios transitorios y enruta juegos, terminales, apps de redacción, navegadores e IDEs mediante listas configurables de procesos/títulos. `TelemetryManager` registra clics de boca, caracteres inyectados, pulsaciones ahorradas, ratio de eficiencia y mapas de calor por celda en `telemetry_stats.json`.

### 10. Handover Multi-Monitor y Calibración por Monitor
`ScreenManager` mueve el HUD y el panel de depuración entre pantallas, reancla los límites normalizados de mirada por monitor y permite handover manual con `Ctrl+Alt+N` o automático por cruce de bisel tras un gesto sostenido de yaw. Los perfiles de calibración guardan la relación de aspecto y una clave por monitor en `calibration_profiles/`, de modo que 1080p, 4K y ultrawide mantienen su propio mapeo.

### 11. Manual Interactivo Game Manual (Documentación Viva)

`docs/guia_interactiva.html` es una guía autocontenida y offline con estética "Nintendo Game Manual meets Cyber-Glass": cinco páginas con pestañas, tarjetas ilustradas con SVG inline, simulador 3x3 en vivo, chuleta de atajos y exportación A4 apaisada a PDF. Se abre desde el botón **Abrir Manual Interactivo** del panel de depuración o desde el modal de ayuda. Su fuente única de verdad es `ideye/core/guide_catalog.py` y se regenera con `generate_interactive_guide()`.

### 12. Diagnósticos en Vivo, Health Guard y Micro-Gestos

La extensión de VS Code envía errores y warnings de la línea activa por WebSocket. `DiagnosticsFixer` genera imports, dos puntos, cierres de paréntesis, sangrías y sugerencias de IA, y los expone en un menú 3x3 de Auto-Fix. `HealthGuard` avisa tras 28 s sin parpadear o si la distancia ocular supera el 138% de la base. Los micro-gestos opcionales permiten abrir Auto-Fix con las cejas e indentar/des-indentar inclinando la cabeza.

---

## Arquitectura del Sistema

```text
+-------------------------------------------------------------------------+
| TRACKER DE CÁMARA (QThread)                                             |
| Captura OpenCV -> MediaPipe FaceMesh (468 pts) -> Iris + Centroide Craneal Rígido |
+------------------------------------+------------------------------------+
 | pyqtSignal(x, y)                  | pyqtSignal("GESTURE")
 v                                   v
+-------------------------------------------------------------------------+
| HUD TRANSPARENTE PYQT6 NO-FOCUS (GUI Principal)                         |
| [0: FLUJO] [1: FUNC/CLASE] [2: OPERADORES]                             |
| [3: CURSOR] [4: PAUSA] [5: PALABRAS CLAVE]                          |
| [6: EDIT/UNDO] [7: ENTER/TAB] [8: PREDICTOR IA]                         |
+------------------------------------+------------------------------------+
 |                                   |
 v                                   v
+-------------------------------+  +--------------------------------------+
| MODE MANAGER & PUENTE         |  | MOTOR DE CONTEXTO E IA (QThread)     |
| WEBSOCKET CON VS CODE         |  | - AST en vivo + Parser de Símbolos   |
| - CÓDIGO / REDACCIÓN / TERMIN.|  | - Cliente Asíncrono Ollama/OpenAI    |
| - DATOS / NAVEGACIÓN / FREELOOK|  | - Respaldo Heurístico Cero-Lat.     |
| - GAMING                      |  |                                      |
+-------------------------------+  +--------------------------------------+
 |                                   |
 v                                   v
+-------------------------------+  +--------------------------------------+
| MOTOR DE INYECCIÓN DE CÓDIGO  |  | MOTOR DE SONIDO PROCEDURAL           |
| - Intercambio Atómico Portap. |  | - Síntesis numpy WAV                 |
| - Reposicionamiento de Cursor |  | - Caché temporal + winsound async    |
| - Nodos Pegajosos vs. Retorno |  |                                      |
+-------------------------------+  +--------------------------------------+
 |                                   |
 v                                   v
+-------------------------------------------------------------------------+
| RATÓN SO & CONTROLADOR GAMING                                           |
| - SetCursorPos del cursor de mirada | - Arrastre Jaw-Lock adaptativo       |
| - Joystick de cabeza WASD / salto | - FreeLook 60 Hz / cursor con guiño der. |
+-------------------------------+-----------------------------------------+
 |
 v
+---------------------------------+
| IDE DESTINO (VS Code, etc.)     |
+---------------------------------+
```

---

## Inicio Rápido

### Descargas y Versiones Precompiladas (Opción Recomendada para Usuarios)

No necesitas instalar Python, Git, ni usar la terminal:

1. **Descarga `IDEye-Windows-v0.5.0.zip`** desde **[GitHub Releases](https://github.com/danicaju/IDEye/releases)** y descomprímelo en cualquier carpeta de tu PC.
2. **Ejecuta `IDEye.exe`**: Incluye Python, OpenCV, MediaPipe y PyQt6 ya integrados sin dependencias externas.
3. **Instala la extensión en VS Code**: Arrastra `ideye-vscode-bridge-0.5.0.vsix` dentro de la ventana de VS Code, o desde la pestaña de Extensiones (`Ctrl+Shift+X` ➔ `...` ➔ *Instalar desde VSIX...*).
4. **Programa sin manos**: La cámara se calibrará automáticamente y se conectará con VS Code mediante WebSocket local (`ws://127.0.0.1:54321`).

---

### Instalación para Desarrolladores (Compilación desde Código Fuente)

### Prerrequisitos
* **Python 3.10+** (Python 3.12 recomendado)
* Una webcam estándar (720p/30fps o superior)
* *Opcional:* [Ollama](https://ollama.com/) instalado localmente (`ollama run qwen2.5-coder:1.5b` o `codellama`) para autocompletado local de líneas mediante IA.

### Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/danicaju/IDEye.git
cd IDEye

# 2. Crear y activar un entorno virtual
python -m venv venv
# En Windows:
venv\Scripts\activate
# En Linux/macOS:
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Iniciar IDEye
python main.py
```

### Lanzadores y Aplicación de Escritorio

IDEye incluye ejecutables y accesos directos nativos para Windows con el icono oficial de la app:

* **Acceso Directo en el Escritorio (`IDEye.lnk`)**: Icono en tu Escritorio de Windows con el logo `{ IDEye }` para abrir la app con doble clic.
* **Lanzador Silencioso (`IDEye.vbs`)**: Inicia IDEye instantáneamente sin parpadeo de ventana de consola CMD.
* **Lanzador por Lotes (`IDEye.bat`)**: Lanzador `.bat` estándar para iniciar con doble clic.
* **Lanzador de Depuración (`IDEye_debug.bat`)**: Inicia mostrando la consola para ver logs, métricas y diagnósticos.
* **Ejecutable Nativo Standalone (`build_app.py`)**: Empaqueta IDEye en un ejecutable independiente `dist/IDEye/IDEye.exe` con MediaPipe, OpenCV y PyQt6 integrados.

### Opciones de Línea de Comandos (CLI)

```bash
python main.py # Inicio estándar con cámara y calibración guardada
python main.py --recalibrate # Fuerza el asistente visual de calibración de 5 puntos
python main.py --camera synthetic # Modo sintético sin webcam física (para pruebas y demos)
```

### Calibración Rápida de 5 Puntos
En el primer inicio (o con `--recalibrate`), IDEye abrirá la **Pantalla de Calibración Visual de 5 Puntos**:
1. Mira al objetivo brillante en el **Centro** y abre ligeramente la boca.
2. Repite el proceso para las **4 esquinas** de la pantalla (Arriba-Izq, Arriba-Der, Abajo-Izq, Abajo-Der).
3. Tu matriz de interpolación se guardará automáticamente en `calibration_profile.json`. ¡Abre VS Code, sitúa el cursor en cualquier archivo `.py` y empieza a programar con la mirada!

> La calibración se guarda junto con la relación de aspecto de la pantalla. Al cambiar a un monitor con una relación muy distinta (por ejemplo 16:9 a 21:9) se aplica una corrección horizontal automática; si la precisión empeora, ejecuta `--recalibrate` en el monitor destino.

---

## Controles y Atajos en Tiempo Real

| Tecla | Acción | Descripción |
| :--- | :--- | :--- |
| **`Ctrl+Alt+Q`** | **Botón de Emergencia (Killswitch)** | **Atajo global en todo el SO**: apaga IDEye limpiamente de inmediato, incluso cuando VS Code tiene el foco |
| **`Ctrl+Alt+R`** | **Reset de Emergencia** | Restablece al instante la calibración a valores por defecto seguros y neutrales |
| **`Ctrl+Alt+A`** | **Alternar Menús Inteligentes** | Activa/desactiva menús contextuales en vivo (adapta los 9 bloques a funciones, try/except, bucles, etc.) |
| **`Ctrl+Alt+B`** | **Máquina del Tiempo del Portapapeles** | Abre las últimas 6 copias del usuario en una cuadrícula 3x3 para reinyectarlas; excluye las escrituras internas de CodeInjector |
| **`Ctrl+Alt+L`** | **Cambiar Lenguaje** | Cicla Python, TypeScript, Rust, C++ y Go desde cualquier sitio |
| **`Ctrl+Alt+V`** | **Abrir Selector de Modo** | Abre el selector de 6 modos; pulsa `Ctrl+Alt+V` desde cualquier sitio |
| **`Ctrl+Alt+K`** | **Alternar Cambio Automático de Modo** | Activa/desactiva el cambio automático de modo según el contexto del editor vía WebSocket. Usa `Ctrl+Alt+K` desde cualquier sitio |
| **`Ctrl+Alt+F`** | **Modo FreeLook** | Modo mirada/cámara a 60 Hz; un imán superior lleva el cursor a la barra de comandos y el clic de boca actúa como respaldo |
| **Scroll por borde** | **Scroll web en FreeLook** | Mira al borde superior o inferior durante ~0.3 s para desplazar la página; vuelve al centro para detenerte |
| **`Ctrl+Alt+G`** | **Modo Gaming** | Joystick de cabeza para WASD; guiño derecho alterna cursor de menú; guiño izquierdo salta. Usa `Ctrl+Alt+G` desde cualquier sitio |
| **`Ctrl+Alt+S`** | **Alternar Retroalimentación Sonora** | Pulsa `Ctrl+Alt+S` desde cualquier sitio |
| **`Ctrl+Alt+H`** | **Guía de Gestos y Ayuda** | Abre o cierra el modal de ayuda con la chuleta completa de gestos y atajos |
| **Clic de Boca** | **Inyectar / Clic** | Una breve apertura de boca (MAR) dispara un clic sin tiempo de espera o una inyección de snippet; en FreeLook también funciona como respaldo confirmado |
| **Boca Mantenida** | **Arrastrar / Jaw-Lock** | Mantener la boca abierta usa un umbral adaptado a tu MAR de reposo, no un 55% fijo |
| **Guiño Derecho** | **Pausar / Gaming: joystick → cursor** | Pausa/oculta el HUD en modos normales; en Gaming alterna joystick de cabeza y cursor de menú |
| **Guiño Izquierdo** | **Volver / Deshacer / Saltar** | Regresa al menú anterior o ejecuta Deshacer; hace saltar al personaje en modo Gaming |
| **`Ctrl+Alt+T`** | **Conmutar Modo de Seguimiento** | Alterna en vivo entre **`HEAD_PRIMARY`**, **`PURE_IRIS`** y **`HYBRID`** |
| **`Ctrl+Alt+C`** | **Recalibrar Centro** | Mira al centro de la pantalla y pulsa `Ctrl+Alt+C` para fijar tu ancla neutra |
| **`Ctrl+Alt+P`** | **Pausa / Modo Lectura** | Oculta el HUD por completo para leer código sin clics involuntarios; usa el mismo atajo o un guiño derecho para restaurarlo |
| **`Ctrl+Alt+M`** | **Alternar Mini-Feed** | Pulsa `Ctrl+Alt+M` desde cualquier sitio; alterna el panel de monitor |
| **`Ctrl+Alt+N`** | **Handover Multi-Monitor** | Mueve el HUD y el mapeo de mirada a la siguiente pantalla conectada |
| **`Ctrl+Alt+Z`** | **Lupa Sniper x3.5** | Activa la lupa de precisión y el slow-mo en FreeLook |
| **`Ctrl+Alt+I`** | **Agentic Prompt Launcher** | Abre seis órdenes de ingeniería para el chat de VS Code o la cola MCP local |
| **`Ctrl+Alt+W`** | **Scroll ocular inercial** | Rueda vertical/horizontal proporcional con zona muerta central y frenado suave |
| **Salida Ocular** | **[X SALIR] Manos Libres** | Mira a la esquina superior derecha `[X SALIR]` y abre la boca; despliega un diálogo de confirmación 100% asistivo |

---

## Estructura del Proyecto

```text
IDEye/
├── main.py # Lanzador raíz (`python main.py`)
├── config.py # Wrapper de configuración
├── requirements.txt # Dependencias
├── pytest.ini # Configuración de Pytest
├── build_app.py # Build PyInstaller onedir multiplataforma
├── create_desktop_shortcut.py # Acceso directo Windows
├── IDEye.bat / IDEye.vbs / IDEye_debug.bat # Lanzadores Windows
├── ideye.ico # Icono de la aplicación
├── .github/workflows/build.yml # Matriz CI Windows/macOS/Linux
├── docs/MULTI_MONITOR_VALIDATION.md # Guía de validación multi-monitor
?   ??? guia_interactiva.html # Manual visual interactivo Game Manual
├── tools/ideye-mcp/ # Servidor MCP de desarrollo
├── vscode-extension/ # Extensión VS Code del puente WebSocket
├── ideye/
│   ├── config.py # Ajustes de tracking, MAR, HUD, LLM, rutas y gaming
│   ├── main.py # Ciclo de vida PyQt6, managers y señales
│   ├── core/
│   │   ├── camera_tracker.py # QThread OpenCV + MediaPipe FaceMesh (468 pts)
│   │   ├── gaze_estimator.py # Mirada híbrida, calibración por monitor y fusión
│   │   ├── gaze_scroller.py # Scroll inercial proporcional por mirada
│   │   ├── eco_power_manager.py # Eco-Sleep 30/10/2 FPS
│   │   ├── gesture_detector.py # MAR, guiños y máquina de estados
│   │   ├── hotkey_manager.py # Atajos globales Ctrl+Alt+letra
│   │   ├── mouse_controller.py # Ratón SO y liberación de teclas gaming
│   │   ├── screen_manager.py # Handover multi-monitor y binding por monitor
│   │   ├── bezel_crossing.py # Detector yaw/hold/cooldown configurable
│   │   ├── window_watcher.py # Enrutado por ventana activa
│   │   ├── telemetry_manager.py # Métricas Look-To-Code e historial JSON
│   │   ├── settings_manager.py # user_settings.json atómico con debounce
│   │   ├── macro_manager.py # Persistencia de macros y overrides del HUD
│   │   ├── logging_config.py # Logging estructurado
│   │   ├── sound_feedback.py # Síntesis numpy WAV + caché temporal
?   ?   ??? lighting_compensator.py # Compensador CLAHE de baja luz
?   ?   ??? health_guard.py # Parpadeo, distancia y postura cervical
?   ?   ??? diagnostics_fixer.py # Auto-Fix de diagn?sticos en vivo
?   ?   ??? ast_code_jumper.py # Mapa 3x3 de símbolos AST
?   ?   ??? game_profiles.py # Perfiles de control por juego activo
?   ?   ??? guide_catalog.py # Fuente única de verdad del manual interactivo
?   ?   ??? guide_builder.py # Render HTML autocontenido y offline
│   │   └── websocket_bridge.py # Puente WebSocket bidireccional VS Code
│   ├── modes/
│   │   ├── base_mode.py # Interfaz abstracta de modo
│   │   ├── mode_manager.py # Motor de 6 modos y cambio automático
│   │   ├── coding_mode.py # Árboles de código e inyección de snippets
?   ?   ??? debug_mode.py # Inspector de variables locales de Fase 12
│   │   ├── writing_mode.py # Teclado de letras, predicción de palabras/frases y Markdown
│   │   ├── terminal_git_mode.py # Paleta Terminal / Git
│   │   ├── data_math_mode.py # Entrada de símbolos datos/mates
│   │   ├── ide_nav_mode.py # Navegación IDE y explorador
│   │   ├── sniper_mouse_mode.py # FreeLook, Jaw-Lock y joystick de cabeza
│   │   └── _helpers.py # Helpers de menús
│   ├── ui/
│   │   ├── overlay_window.py # HUD transparente PyQt6 No-Focus
│   │   ├── header_layout.py # Geometría de la barra de comandos
│   │   ├── calibration_ui.py # Asistente de calibración
│   │   ├── debug_widget.py # Mini-feed, telemetría y controles
│   │   ├── macro_editor_dialog.py # Editor de macros 3x3
│   │   ├── icon_manager.py # Iconos Lucide/SVG alta DPI
│   │   ├── system_tray.py # Bandeja nativa con estados de energ?a
│   │   └── sniper_lens.py # Lupa circular, micro-fijación y slow-mo
│   ├── actions/
│   │   ├── menu_trees.py # Árboles 3x3 y nodos pegajosos
│   │   ├── context_reader.py # Extractor AST + Regex tolerante
│   │   ├── ai_predictor.py # Worker LLM asíncrono + heurística
│   │   ├── code_injector.py # Inyección atómica y offsets
│   │   ├── clipboard_history.py # Máquina del tiempo MTF de 6 ranuras
│   │   ├── language_support.py # Sintaxis multi-lenguaje
?   ?   ??? semantic_taxonomy.py # ?rboles sem?nticos multiling?es de Fase 12
│   │   ├── agentic_launcher.py # Seis prompts de ingeniería + cola MCP
│   │   └── text_predictor.py # Predicción local de palabras
│   └── assets/
│   │   ├── data/es_common_words.txt # Diccionario español
│   │   ├── defaults/ # Plantillas user_settings.json y custom_macros.json
│   │   └── icons/ # Suite de iconos SVG/Lucide alta DPI
└── tests/ # 630 pruebas de unidad e integración
    ├── test_phase1.py # Visión y máquina MAR
    ├── test_phase2.py # QThread, no-focus y calibración
    ├── test_phase3.py # Árboles sintácticos e inyección
    ├── test_phase4.py # ContextReader y AIPredictorWorker
    ├── test_phase5_multilang_and_websocket.py # Multi-lenguaje y WebSocket
    ├── test_phase6_modes.py # Motor de 6 modos y auto-contexto
    ├── test_phase6_6_lucide_ui.py # Iconos Lucide/SVG
    ├── test_phase7_sniper_and_sound.py # FreeLook, gestos gaming y audio
    ├── test_phase7_6_gaze_stability.py # Estabilidad, histéresis y sácadas
    ├── test_phase8_settings_and_auto_mar.py # Ajustes y calibración MAR
    ├── test_phase8_2_custom_macros.py # Macros y editor 3x3
    ├── test_phase8_3_multimonitor.py # Handover, límites y build
    ├── test_phase8_4_refactor.py # Bisel, layout y logging
    ├── test_phase9_os_intelligence.py # Portapapeles, rutas y telemetría
    ├── test_phase9_5_biometrics_and_autofix.py # Auto-Fix, Health Guard y micro-gestos
    ├── test_phase10_1_lighting_and_sniper_lens.py # CLAHE y lupa Sniper
    ├── test_phase10_2_ast_code_jumper.py # Extracción AST y mapa de símbolos
    ├── test_phase10_3_game_profiles.py # Perfiles, twin-stick y edge-scroll
    ├── test_phase10_4_agentic_launcher.py # Prompt, menú 3x3 y cola MCP
        ├── test_phase11_scroll_eco_and_ghost_hud.py # Scroll, Eco-Sleep, Ghost-Peek y tray
    ??? test_phase12_semantic_coding_and_live_context.py # Taxonom?a sem?ntica y contexto vivo
    ├── test_hotfix_ui_and_gaming.py # Joystick, audio y ayuda
    ├── test_writing_words_and_letters.py # Teclado de letras, predicciones y frases
    ├── test_interactive_guide.py # Generación, catálogo y accesos al manual
    ├── test_interactive_guide_sync.py # Sincronización UTF-8 y tema Nintendo
    ├── test_freelook_edge_scroll.py # Scroll por borde en FreeLook
    ├── test_freelook_top_and_safe_clicks.py # Alcance superior, clic de boca y parpadeo de lupa
    ├── test_glass_focus_ui.py # Widgets Glass/Focus
    ├── test_help_ui_and_card_layout.py # Ayuda y guía de gestos
    ├── test_menu_integrity.py # Integridad de árboles 3x3
    ├── test_code_injector.py # Modificadores y portapapeles
    ├── test_context_and_ai.py # Tolerancia AST y JSON LLM
    ├── test_calibration_and_killswitch.py # Calibración y hotkeys
    ├── test_tracking_modes_and_handsfree_exit.py # Iris, VOR y salida manos libres
    ├── test_adaptive_ast_menus.py # Menús AST y atajo [A]
    ├── test_vision_math.py # Recorte de mirada y división
    └── test_wink_gestures_and_hud_hide.py # Guiños y visibilidad HUD
    ├── test_wink_robustness.py # EAR por ojo, filtros, tiempos y doble gui?o
```

---

## Testing y QA

IDEye incluye una suite completa de pruebas automatizadas mediante *mocks* que cubren casos límite matemáticos, integridad recursiva de los árboles de menús, seguridad de teclas modificadoras, tolerancia a fallos del AST, mensajería WebSocket, motor de 6 modos y estabilidad de la mirada:

```bash
pytest -q
```

```text
630 pruebas superadas, 85 subtests, 18.70s
```

> [!NOTE]
> Todos los 630 tests se ejecutan de forma *headless* sin requerir cámara web física, servidor gráfico ni conexión a Internet. `testpaths=tests` está configurado en `pytest.ini`.

---

## Hoja de Ruta

- [x] **Fase 1:** Seguimiento híbrido de Iris + Cabeza con suavizado EMA y disparador MAR por apertura de boca.
- [x] **Fase 2:** HUD transparente PyQt6 `WindowDoesNotAcceptFocus` y calibración de 5 puntos en JSON.
- [x] **Fase 3:** Árboles sintácticos jerárquicos 3x3 e inyección atómica de código con offsets de cursor.
- [x] **Fase 4:** Extracción de símbolos AST/Regex en vivo y predicción asíncrona de código con IA.
- [x] **Fase Extra:** Auditoría forense de código, eliminación de fugas de memoria y cobertura de regresión con hardware simulado.
- [x] **Fase 5:** Perfiles multi-lenguaje (TypeScript/JS, Rust, C++, Go) y extensión WebSocket nativa para VS Code.
- [x] **Fase 6:** Motor de 6 modos (Código, Redacción, Terminal/Git, Datos/Mates, Navegación, FreeLook/Gaming) y cambio automático por contexto.
- [x] **Fase 6.5:** HUD Glass & Focus: diseño seguro con barra de tareas, barra de comandos de alto contraste, preview chips y jerarquía neutral/activa.
- [x] **Fase 6.6:** Suite de iconos Lucide alta DPI, render SVG tintado, botón AYUDA más ancho y layout de tarjetas de ayuda.
- [x] **Fase 7:** Síntesis procedural numpy WAV con caché temporal y base de ratón OS (clic, arrastre, scroll).
- [x] **Fase 7.5:** FreeLook sin cuadrícula a 60 Hz, Jaw-Lock, perfil Gaming/Roblox y Desduplicación Inteligente de Prefijos (`h + hola` -> `ola`).
- [x] **Fase 7.6:** Estabilidad subpíxel con centroide craneal, multi-anclaje orbital + mediana en PURE_IRIS, fusión de sácadas HYBRID y WebSocket bidireccional con contexto automático.
- [x] **Fase 7.7:** Mapeo FreeLook a pantalla completa, overscan cómodo en bordes y carril magnético de la barra de tareas de Windows.
- [x] **Fase 7.9:** Imán superior de FreeLook, clic de boca fiable y captura de Lupa Sniper sin parpadeo.
- [x] **Fase 8.1:** `user_settings.json` persistente, sincronización live con debounce, calibración biométrica MAR de 6º paso y slider MAR en vivo.
- [x] **Fase 8.2:** Constructor de Macros: `custom_macros.json` persistente, editor de 9 celdas, snippets/comandos/atajos OS y parcheo del HUD en vivo.
- [x] **Fase 8.3:** Handover de mirada multi-monitor, cruce de bisel, límites de calibración por pantalla y empaquetado PyInstaller multiplataforma.
- [x] **Fase 8.4:** Perfiles de calibración por monitor, `BezelCrossingDetector`/`HeaderLayout` extraídos, logging estructurado, umbrales de handover configurables y matriz CI Windows/macOS/Linux.
- [x] **Fase 9:** Máquina del tiempo del portapapeles (6 ranuras 3x3), auto-cambio por ventana activa del SO y telemetría Look-To-Code con ahorro de esfuerzo persistido.
- [x] **Fase 9.5:** Hotfix de estabilidad: teclado de letras con predicción, modal de ayuda con wrap, audio en archivos cacheados y Gaming con joystick de cabeza y cambio a cursor.
- [x] **Fase 9.6:** Auto-Fix de diagn?sticos en vivo de VS Code, Health Guard biom?trico y micro-gestos opcionales de cejas/tilt.
- [x] **Fase 10.1:** Visión nocturna adaptativa CLAHE y Lupa Sniper x3.5 con slow-mo.
- [x] **Fase 10.2:** Salto semántico AST con mapa 3x3 y teleport de cursor en VS Code.
- [x] **Fase 10.3:** Perfiles de juego dinámicos desde game_profiles.json, twin-stick y edge-scrolling de estrategia.
- [x] **Fase 10.4:** Agentic Prompt Launcher para el chat de VS Code y la cola MCP de tareas oculares.
- [x] **Fase 11:** Scroll ocular inercial, Eco-Sleep din?mico, Ghost-Peek HUD y bandeja nativa.
- [x] **Fase 12:** Taxonom?a sem?ntica profunda, IA contextual en vivo para VS Code/Google Docs y modos Terminal, Navegaci?n y Debug conscientes del entorno.

> El enrutado por ventana no se limita a Roblox ni a unos pocos editores: reconoce listas amplias de juegos, terminales, apps de redacción/comunicación, navegadores e IDEs. También detecta juegos genéricos de Unreal `-Win64-Shipping.exe` y palabras clave configurables. Amplía `GAMING_PROCESSES`, `GAMING_TITLE_KEYWORDS`, `GAMING_PROCESS_SUFFIXES`, `TERMINAL_PROCESSES`, `WRITING_PROCESSES`, `BROWSER_PROCESSES` o `IDE_PROCESSES` en `ideye/config.py` para cualquier otra aplicación.

---

## Privacidad, Seguridad y Avisos Legales

### Procesamiento Biométrico 100% Local (Privacidad Primero)
Todos los fotogramas de la webcam y los 478 puntos faciales 3D de MediaPipe se procesan estrictamente en la memoria RAM volátil local. IDEye jamás graba, almacena ni transmite vídeo o datos biométricos por la red.

### Aviso Ergonómico y No Médico
IDEye es una herramienta de productividad y accesibilidad general, no un dispositivo médico certificado. No está diseñada para diagnosticar, tratar, curar ni prevenir afecciones médicas (como RSI o túnel carpiano). Se recomienda realizar pausas frecuentes y detener su uso si se experimenta fatiga mandibular (ATM), cervical u ocular.

### Aviso sobre Juegos Online y Sistemas Anti-Cheat
El Modo Gaming utiliza inyección de entrada sintética a nivel de sistema operativo (`Win32 API` / `pynput`) con fines de accesibilidad. Aunque es totalmente seguro en juegos para un jugador y sandboxes estándar, se recomienda verificar la compatibilidad antes de usarlo en juegos multijugador competitivos con sistemas anti-cheat de nivel kernel.

---

## Contribuciones y Licencia

¡Las contribuciones, sugerencias de accesibilidad y pull requests son bienvenidas! Bajo los términos de la **Licencia MIT**.

<div align="center">
  <sub>Desarrollado por <b>Daniel Casado Juan</b></sub>
</div>
