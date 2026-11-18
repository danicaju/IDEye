<div align="center">

# IDEye (Motor Vistax L2C)
**Look-To-Code (L2C): programa con los ojos, la cabeza y la cara, sin manos ni voz**

<p align="right">
  <strong>Idioma:</strong>
  <a href="README.md">English</a> | <b>Español</b>
</p>

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Lanzamiento: v0.5.0](https://img.shields.io/badge/Lanzamiento-v0.5.0-blue.svg?style=for-the-badge&logo=github)](https://github.com/danicaju/IDEye/releases)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-FaceMesh%20478-00A8E8?style=for-the-badge&logo=google&logoColor=white)](https://developers.google.com/mediapipe)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6%20No--Focus-41CD52?style=for-the-badge&logo=qt&logoColor=white)](https://www.riverbankcomputing.com/software/pyqt/)
[![Pruebas](https://img.shields.io/badge/Pruebas-721%20Aprobadas-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)](#testing-y-qa)
[![Licencia: AGPL v3](https://img.shields.io/badge/Licencia-AGPL_v3-blue.svg?style=for-the-badge)](LICENSE)

*Escribe código con una webcam estándar, seguimiento ocular híbrido y unos pocos gestos faciales. Sin teclado, sin comandos de voz, sin hardware infrarrojo.*

[Descargas](#inicio-rápido) • [Cómo funciona](#cómo-funciona-en-3-pasos) • [Innovaciones](#innovaciones-principales) • [Inicio rápido](#inicio-rápido) • [Controles y atajos](#controles-y-atajos-en-tiempo-real) • [Arquitectura](#arquitectura-del-sistema) • [Hoja de ruta](#hoja-de-ruta)

---

</div>

> [!TIP]
> ¿Quieres usar IDEye sin instalar Python ni abrir una terminal? Descarga la versión portátil y la extensión de VS Code desde [GitHub Releases](https://github.com/danicaju/IDEye/releases):
> - `IDEye-Windows-v0.5.0.zip`: aplicación de Windows lista para usar. Descomprímela y ejecuta `IDEye.exe`.
> - `ideye-vscode-bridge-0.5.0.vsix`: extensión de VS Code. Arrástrala a la ventana del editor.

---

## El problema que resuelve IDEye

Quien tiene lesiones por esfuerzo repetitivo (RSI), síndrome del túnel carpiano, una discapacidad motora o una lesión temporal suele no poder teclear durante mucho tiempo. Las alternativas actuales se quedan cortas:
1. **Herramientas de voz (Talon, Cursorless):** necesitan hablar sin parar, así que no sirven en una oficina compartida, en una biblioteca o con dificultades del habla.
2. **Teclados en pantalla (OptiKey):** se escribe letra por letra y, por el temblor de las webcams, en la práctica hace falta hardware infrarrojo (Tobii) de 300 € a 1.000 €.
3. **Controladores de ratón por webcam (Project Gameface, eViacam):** solo mueven el cursor del sistema y sufren el Toque de Midas: cualquier cosa que mires puede activarse y esperar el temporizador de fijación cansa.

IDEye (Vistax) reúne un HUD 3x3 de macrozonas basado en el AST, seguimiento híbrido de cabeza e iris con una webcam estándar, gestos faciales que activan sin esperar, un puente WebSocket bidireccional con VS Code y predicción de contexto en vivo.

### Comparativa

| Característica / Capacidad | Webcam Estándar (0 €) | 100% Silencioso (Sin Voz) | Inyección de Código por AST / Macros | Detección de Variables Locales en Vivo | WebSocket Bidireccional con VS Code | FreeLook 60 Hz y Gaming |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Talon Voice / Cursorless** | No | No | Sí | Sí | No | No |
| **OptiKey** | Parcial *(Requiere IR)* | Sí | No *(Carácter a carácter)* | No | No | No |
| **Google Project Gameface** | Sí | Sí | No *(Solo ratón OS)* | No | No | Sí |
| **IDEye (Vistax L2C)** | **Sí** | **Sí** | **Sí (HUD 3x3 Macro)** | **Sí (AST + IA)** | **Sí** | **Sí** |

---

## Cómo funciona en 3 pasos

```mermaid
flowchart LR
    classDef step1 fill:#0d233a,stroke:#38bdf8,stroke-width:2px,color:#e0f2fe;
    classDef step2 fill:#062d22,stroke:#34d399,stroke-width:2px,color:#d1fae5;
    classDef step3 fill:#271238,stroke:#c084fc,stroke-width:2px,color:#f3e8ff;
    classDef actionNode fill:#1c2433,stroke:#64748b,stroke-width:1px,color:#f8fafc;

    subgraph S1 ["PASO 1: MIRAR (Navegación)"]
        direction TB
        A1["Seguimiento Mirada / Cabeza (Webcam)"]:::actionNode --> A2["Resalta Macrozona 3x3"]:::actionNode
        A2 --> A3["Navegación Desacoplada (Zero-Dwell)"]:::step1
    end

    subgraph S2 ["PASO 2: BOCA (Acción Inmediata)"]
        direction TB
        B1["Apertura bucal suave (MAR)"]:::actionNode --> B2["CLIC / Inyección de Código Instantánea"]:::step2
        B1 -.->|"Mantener boca abierta"| B3["Modo Arrastre Jaw-Lock"]:::actionNode
    end

    subgraph S3 ["PASO 3: GUIÑOS (Control Global)"]
        direction TB
        C1["Guiño Derecho"]:::actionNode --> C2["Pausar / Ocultar HUD"]:::step3
        C3["Guiño Izquierdo"]:::actionNode --> C4["Atrás / Deshacer (Ctrl+Z)"]:::step3
    end

    S1 ==>|"1. Enfocar bloque"| S2
    S2 -.->|"2. Pausar o deshacer"| S3

    class S1 step1;
    class S2 step2;
    class S3 step3;
```

---

## Innovaciones principales

IDEye tiene cuatro piezas principales.

### 1. Seguimiento Híbrido Sub-Píxel y Centroide Craneal
A la distancia habitual de un monitor, una webcam no distingue por sí sola el movimiento de la pupila con suficiente precisión. IDEye fusiona el desplazamiento del iris con el vector de anclaje de la nariz:
$$\mathbf{P}_{raw} = \alpha_{head} \cdot \mathbf{V}_{nose} + (1 - \alpha_{head}) \cdot \mathbf{V}_{iris}$$
Puntos de anclaje craneales ponderados en MediaPipe FaceMesh (`[1, 4, 6, 168, 195, 197]`) combinados con una puerta de histéresis (`STATIC_LOCK_RADIUS=0.0035`, deriva `0.0px`) suprimen el microtemblor en fijaciones sin añadir latencia a las sacadas. Incluye tolerancia a gorras y compensación ocular por CLAHE en baja iluminación.

### 2. Eliminación del Toque de Midas y Gestos Biométricos
Mirar y activar son cosas separadas: la mirada solo resalta una celda. Una apertura breve de la boca (Mouth Aspect Ratio, MAR) ejecuta un clic o inyección instantánea. Mantener la boca abierta activa el modo de arrastre **Jaw-Lock**. Un umbral dinámico de reposo (Anti-Midas) aprende cómo tienes la boca cuando estás relajado y evita clics accidentales. Los guiños independientes gestionan el retroceso/deshacer (guiño izquierdo) y la pausa del HUD (guiño derecho).

### 3. Puente WebSocket Bidireccional con VS Code y AST en Vivo
`WebSocketBridge` sincroniza diagnósticos del editor, selecciones y árboles sintácticos en tiempo real (`ws://127.0.0.1:54321`). `ContextReader` extrae variables locales, funciones y clases incluso en archivos con errores sintácticos (`ast.walk` + motor regex de respaldo). Tiene 6 modos de trabajo: `CODING`, `WRITING` (teclado de letras con predicción de palabras y frases), `TERMINAL_GIT`, `DATA_MATH`, `NAVIGATION` y `FREELOOK_GAMING` (joystick craneal a 60 Hz con zona muerta central).

### 4. HUD PyQt6 No Invasivo, Ergonomía y Multimonitor
La interfaz superpuesta funciona con PyQt6 mediante `WindowDoesNotAcceptFocus` y `WS_EX_TRANSPARENT`, permitiendo que los clics del ratón físico atraviesen el HUD sin robar el foco del teclado ni perder el cursor del editor. Admite columna Right Dock (30% de ancho), Ghost Mode (atenúa al 15% de opacidad mientras lees), traspaso de la mirada entre monitores y síntesis de sonido sin dependencias de audio externas. Un único acento cian marca la celda enfocada y el ajuste de movimiento reducido convierte todos los fundidos en cambios instantáneos.

---

## Inicio rápido

### Versión precompilada (recomendada)
1. Descarga `IDEye-Windows-v0.5.0.zip` desde [GitHub Releases](https://github.com/danicaju/IDEye/releases) y descomprímelo.
2. Ejecuta `IDEye.exe`. Incluye los entornos de Python, OpenCV, MediaPipe y PyQt6.
3. Instala la extensión arrastrando `ideye-vscode-bridge-0.5.0.vsix` a VS Code.
4. Empieza a programar. La cámara se calibra y se conecta con el editor por WebSocket local.

### Compilar desde el código fuente
```bash
# 1. Clonar el repositorio
git clone https://github.com/danicaju/IDEye.git
cd IDEye

# 2. Configurar entorno virtual
python -m venv venv
venv\Scripts\activate      # En Linux/macOS: source venv/bin/activate

# 3. Instalar dependencias e iniciar
pip install -r requirements.txt
python main.py
```

---

## Controles y atajos en tiempo real

### Atajos de uso diario

| Acción | Entrada / Atajo | Descripción |
| :--- | :--- | :--- |
| **Killswitch de Emergencia** | **`Ctrl+Alt+Q`** | Atajo global del sistema: cierra IDEye al instante desde cualquier aplicación |
| **Reset de Emergencia** | **`Ctrl+Alt+R`** | Restablece los pesos de calibración a los valores seguros por defecto |
| **Modo Pausa / Lectura** | **`Ctrl+Alt+P`** / **Guiño Der.** | Oculta el HUD por completo para leer código sin riesgo de clics accidentales |
| **Snap to Caret** | **`C`** | Micro-recalibración en 1 punto centrando la mirada sobre el cursor del editor |
| **Alternar Columna Derecha** | **`D`** | Cambia entre pantalla completa (100%) y columna lateral (30%, 460px de ancho) |
| **Inyectar / Clic** | **Clic Bucal** | Apertura breve de boca (MAR) para ejecutar clics inmediatos sin temporizador |
| **Arrastrar / Jaw-Lock** | **Boca Sostenida** | Mantener la boca abierta activa el modo arrastre continuo sin fatiga |
| **Deshacer Universal** | **`Z`** / **Guiño Izq.** | Retrocede en los menús o envía un Deshacer (Ctrl+Z) al editor activo |

<details>
<summary>Los 34 atajos, controles de modo y asignaciones de gaming</summary>

<br>

| Tecla | Acción | Descripción |
| :--- | :--- | :--- |
| **`Ctrl+Alt+A`** | **Menús Inteligentes** | Adapta dinámicamente las 9 celdas a firmas de función, bloques try y bucles |
| **`Ctrl+Alt+B`** | **Historial Portapapeles**| Abre las últimas 6 copias en una cuadrícula 3x3 para reinyección inmediata |
| **`Ctrl+Alt+L`** | **Cambiar Lenguaje** | Rota definiciones sintácticas: Python, TypeScript, Rust, C++, Go |
| **`Ctrl+Alt+V`** | **Selector de Modos** | Abre el conmutador de los 6 modos desde cualquier parte del sistema |
| **`Ctrl+Alt+K`** | **Auto-Conmutación** | Activa/desactiva el cambio de modo automático según el contexto de VS Code |
| **`Ctrl+Alt+F`** | **Modo FreeLook** | Control libre del cursor a 60 Hz con imán superior para la barra de comandos |
| **`Scroll Borde`** | **Desplazamiento Web** | Fijar la mirada en el borde superior/inferior durante ~0.3 s para hacer scroll |
| **`Ctrl+Alt+G`** | **Modo Gaming** | Joystick craneal para WASD; guiño izquierdo salta; guiño derecho activa cursor |
| **`Ctrl+Alt+S`** | **Sonido Procedural** | Activa o silencia el feedback auditivo sintetizado |
| **`Ctrl+Alt+H`** | **Ayuda y Gestos** | Abre la guía de atajos, calibración y referencia de gestos faciales |
| **`Ctrl+Alt+T`** | **Modo de Seguimiento** | Conmuta entre algoritmos `HEAD_PRIMARY`, `PURE_IRIS` y `HYBRID` |
| **`Ctrl+Alt+C`** | **Calibración Central** | Mirar al centro de la pantalla y pulsar para reajustar el ancla neutral |
| **`Ctrl+Alt+M`** | **Mini-Monitor** | Muestra/oculta el panel de métricas de seguimiento y cámara en tiempo real |
| **`Ctrl+Alt+N`** | **Traspaso Multimonitor**| Mueve el HUD y los límites de la mirada al siguiente monitor conectado |
| **`Ctrl+Alt+Z`** | **Lente Francotirador** | Activa zoom de precisión x3.5 y cámara lenta en modo FreeLook |
| **`Ctrl+Alt+J`** | **Salto Semántico AST** | Abre el mapa de símbolos 3x3 del archivo activo y teletransporta el cursor |
| **`Ctrl+Alt+I`** | **Lanzador Agéntico** | Abre 6 prompts de ingeniería para el chat de VS Code o la cola local MCP |
| **`Ctrl+Alt+W`** | **Scroll Inercial** | Rueda vertical/horizontal proporcional con zona muerta y frenado suave |
| **`P`** | **Spotlight Mirada** | Abre la paleta de comandos 3x3 accesible por mirada |
| **`O`** | **Cambiar Tema** | Alterna entre Cyber Glass, OLED Black (WCAG AAA) y Solarized Dark |
| **`F2`** | **Mini-Tutorial** | Guía interactiva de incorporación en 3 pasos dentro de la aplicación |
| **Salida Ocular**| **[X SALIR] Manos Libres** | Mirar a `[X SALIR]` arriba a la derecha y hacer clic bucal para diálogo accesible |

</details>

---

## Arquitectura del sistema

```text
+-------------------------------------------------------------------------+
| CAMERA TRACKER (QThread)                                                |
| Captura OpenCV -> MediaPipe FaceMesh (478 pts) -> Iris + Centroide Cráneo|
+------------------------------------+------------------------------------+
 | pyqtSignal(x, y)                  | pyqtSignal("GESTURE")
 v                                   v
+-------------------------------------------------------------------------+
| PYQT6 NO-FOCUS OVERLAY (GUI Principal)                                  |
| [0: FLUJO] [1: FUNC/CLASE] [2: OPERADORES]                              |
| [3: CURSOR] [4: PAUSA] [5: PALABRAS CLAVE]                              |
| [6: EDICIÓN/DESHACER] [7: ENTER/TAB] [8: PREDICTOR IA]                  |
+------------------------------------+------------------------------------+
 |                                   |
 v                                   v
+-------------------------------+  +--------------------------------------+
| GESTOR DE MODOS & VS CODE     |  | MOTOR DE CONTEXTO E IA (QThread)     |
| PUENTE WEBSOCKET              |  | - AST en vivo + Parser de Símbolos   |
| - CODING / WRITING / TERMINAL |  | - Cliente asíncrono Ollama / OpenAI  |
| - DATA / NAVIGATION / FREELOOK|  | - Respaldo heurístico de latencia 0  |
| - GAMING                      |  |                                      |
+-------------------------------+  +--------------------------------------+
 |                                   |
 v                                   v
+-------------------------------+  +--------------------------------------+
| INYECTOR DE CÓDIGO            |  | MOTOR DE SONIDO PROCEDURAL           |
| - Intercambio atómico en clip |  | - Síntesis WAV con numpy             |
| - Reposicionado de cursor     |  | - winsound asíncrono / caché local   |
+-------------------------------+  +--------------------------------------+
 |
 v
+---------------------------------+
| EDITOR OBJETIVO (VS Code, etc.) |
+---------------------------------+
```

---

## Estructura del proyecto

```text
IDEye/
├── main.py                          # Punto de entrada (`python main.py`)
├── config.py                        # Configuración central del sistema
├── requirements.txt                 # Dependencias (MediaPipe, PyQt6, OpenCV, numpy)
├── build_app.py                     # Compilador standalone PyInstaller
├── IDEye.bat / IDEye.vbs            # Lanzadores para Windows (consola / silencioso)
├── docs/guia_interactiva.html       # Manual interactivo autónomo offline
├── vscode-extension/                # Extensión oficial de VS Code por WebSocket
├── ideye/
│   ├── core/                        # Seguimiento, biometría, audio y puente WebSocket
│   ├── modes/                       # Motor de 6 modos (Coding, Writing, Gaming...)
│   ├── ui/                          # Overlay PyQt6 transparente, calibración e iconos
│   ├── actions/                     # Extractor AST, predictor de IA e inyector de código
│   └── assets/                      # Iconos vectoriales de alto DPI y datos de predicción
└── tests/                           # 49 módulos con 721 tests (hardware simulado)
```

---

## Testing y QA

La batería de pruebas simula el hardware y cubre casos límite numéricos, la integridad de los árboles de menús, la tolerancia a fallos del AST y la estabilidad de la mirada:

```bash
pytest -q
```
```text
721 passed, 89 subtests in 29.7s
```

> [!NOTE]
> Las 721 pruebas se ejecutan sin interfaz (*headless*). No necesitan cámara, servidor gráfico ni conexión a internet.

---

## Hoja de ruta

### Versión Actual (`v0.5.0`)
- [x] Lanzamiento completo en producción: paquete portátil para Windows + extensión de VS Code.
- [x] Motor de 6 modos con detección de contexto automática por WebSocket.
- [x] Umbral dinámico adaptativo Anti-Midas y navegación libre en juegos a 60 Hz.

### Próximos Hitos
- [ ] Backend nativo para Linux Wayland (soporte de `wlr-layer-shell`).
- [ ] Binario universal empaquetado para macOS Apple Silicon.
- [ ] Aceleración de modelos pupilares cuantizados en local con ONNX Runtime.

<details>
<summary>Fases completadas 1 a 12.1</summary>

<br>

- [x] **Fase 1:** Seguimiento híbrido iris + cabeza con suavizado EMA y disparo bucal MAR.
- [x] **Fase 2:** Overlay transparente PyQt6 con `WindowDoesNotAcceptFocus` y calibración JSON en 5 puntos.
- [x] **Fase 3:** Árboles sintácticos 3x3 e inyección atómica de código con offsets de cursor.
- [x] **Fase 4:** Extracción de símbolos AST/Regex y predicción asíncrona por IA y heurística.
- [x] **Fase 5:** Soporte multisintaxis (TypeScript, Rust, C++, Go) y extensión WebSocket nativa para VS Code.
- [x] **Fase 6:** Motor de 6 modos (Coding, Writing, Terminal, Data, Navigation, FreeLook/Gaming).
- [x] **Fase 6.5 - 6.6:** HUD Glass & Focus, iconos Lucide de alto DPI y maquetación de ayuda.
- [x] **Fase 7 - 7.9:** Audio procedural numpy, FreeLook 60 Hz, arrastre Jaw-Lock y centroide craneal sub-píxel.
- [x] **Fase 8.1 - 8.4:** Ajustes de usuario persistentes, creador de macros, traspaso multimonitor y matriz CI.
- [x] **Fase 9 - 9.6:** Historial de portapapeles, enrutamiento por ventana activa, auto-fix de errores y Health Guard.
- [x] **Fase 10 - 11:** CLAHE en baja iluminación, salto semántico AST, perfiles de juego y scroll inercial.
- [x] **Fase 12 - 12.1:** Taxonomía semántica profunda, tutorial interactivo de onboarding y motor adaptativo Anti-Midas.

</details>

---

## Privacidad, seguridad y avisos legales

- El procesamiento biométrico es local. Los fotogramas de la cámara y los puntos faciales 3D se quedan en memoria RAM volátil. IDEye nunca graba, almacena ni envía datos biométricos por la red.
- IDEye es una herramienta de productividad asistiva, no un dispositivo médico certificado. Haz descansos periódicos para evitar fatiga cervical o mandibular.
- El modo Gaming inyecta entrada sintética a nivel de sistema operativo (`Win32 API` / `pynput`) con fines de accesibilidad. Comprueba la compatibilidad antes de usarlo en juegos competitivos con antitrampas a nivel de kernel.

---

## Contribuciones y licencia

Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para preparar el entorno, ejecutar las pruebas y conocer las reglas del proyecto.

IDEye se distribuye bajo la GNU Affero General Public License v3.0 (AGPL-3.0-or-later). Cualquier modificación, redistribución o despliegue como servicio en red debe seguir siendo de código abierto bajo esta misma licencia.

<div align="center">
  <sub>Desarrollado por <b>Daniel Casado Juan</b> &middot; Universitat de les Illes Balears (UIB)</sub>
</div>
