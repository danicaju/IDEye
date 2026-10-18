<div align="center">

# 👁️ EyeDE (Motor Vistax L2C)
**El motor de programación Look-To-Code (L2C) para ingeniería de software manos libres y silenciosa**

[![English](https://img.shields.io/badge/Language-English-blue?style=flat-square)](README.md)
[![Español](https://img.shields.io/badge/Idioma-Español-red?style=flat-square)](README.es.md)

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-FaceMesh%20478-00A8E8?style=for-the-badge&logo=google&logoColor=white)](https://developers.google.com/mediapipe)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6%20No--Focus-41CD52?style=for-the-badge&logo=qt&logoColor=white)](https://www.riverbankcomputing.com/software/pyqt/)
[![Pruebas](https://img.shields.io/badge/Pruebas-232%20Aprobadas-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)](#-testing-y-qa)
[![Licencia: MIT](https://img.shields.io/badge/Licencia-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

*Escribe código de producción real usando únicamente una webcam estándar, seguimiento ocular híbrido y gestos faciales discretos. Sin manos. Sin comandos de voz. Sin hardware infrarrojo caro.*

[Explorar Arquitectura](#-arquitectura-del-sistema) • [Inicio Rápido](#-inicio-rápido) • [Cómo Funciona](#-innovaciones-principales) • [Controles en Vivo](#-controles-y-atajos-en-tiempo-real) • [Hoja de Ruta](#-hoja-de-ruta)

---

<!-- TODO: Reemplazar con un GIF de 15 segundos grabado con OBS mostrando cómo programas en VS Code con el HUD -->
![Demostración de EyeDE](https://via.placeholder.com/900x450/0d1117/58a6ff?text=Insertar+GIF+Demostracion:+HUD+3x3+Eyede+en+VS+Code)

</div>

## ⚡ El Problema y por qué existe EyeDE

Los desarrolladores que sufren lesiones graves por esfuerzos repetitivos (RSI), túnel carpiano, parálisis o problemas del habla se enfrentan a una barrera crítica al intentar escribir código:
1. **Las herramientas de voz (Talon, Cursorless)** son fantásticas, pero requieren vocalización constante, lo que falla en espacios compartidos, bibliotecas o para usuarios con dificultades en el habla.
2. **Los teclados en pantalla (OptiKey)** obligan a escribir letra por letra (`f`-`o`-`r`-`espacio`...) y prácticamente exigen sensores infrarrojos caros de $300–$1,000 (Tobii) porque las webcams normales tienen un error de dispersión de 100–150px.
3. **Los drivers de ratón por webcam (Project Gameface, eViacam)** solo mueven el cursor del sistema; hacer clic en iconos diminutos de 15px en el IDE o sufrir el *"problema del toque de Midas"* (fatiga por tiempo de espera) hace que programar sea agotador.

**EyeDE (Vistax)** resuelve esto replanteando la interfaz de desarrollo desde sus cimientos: combinando un **HUD de macro-zonas AST 3x3**, **seguimiento híbrido de cabeza e iris con supresión de parpadeo**, **desencadenantes instantáneos por gestos faciales** y **predicción de contexto en vivo mediante AST e IA**.

### 📊 Comparativa con el Estado del Arte

| Característica / Herramienta | Webcam estándar ($0) | 100% Silencioso (Sin voz) | Inyección de Bloques de Código (AST) | Conciencia de Variables Locales |
| :--- | :---: | :---: | :---: | :---: |
| **Talon Voice / Cursorless** | ❌ | ❌ | ✅ | ✅ |
| **OptiKey** | ⚠️ *(Se recomienda IR)* | ✅ | ❌ *(Carácter por carácter)* | ❌ |
| **Google Project Gameface** | ✅ | ✅ | ❌ *(Solo controlador de ratón)* | ❌ |
| **👁️ EyeDE (Vistax L2C)** | **✅ Sí** | **✅ Sí** | **✅ Sí (Macro-HUD 3x3)** | **✅ Sí (AST + IA)** |

---

## 🧠 Innovaciones Principales

### 1. Vector Híbrido de Mirada + Cabeza con Filtro EMA y Supresión de Parpadeo
El seguimiento ocular puro con webcam carece de rango dinámico a distancia normal de monitor. EyeDE fusiona el desplazamiento normalizado del iris con el vector anclado 3D de la punta de la nariz, congela la posición del iris durante el parpadeo natural para evitar saltos del cursor y suaviza la salida mediante una **Media Móvil Exponencial (EMA)**:

$$\mathbf{P}_{raw} = \alpha_{head} \cdot \mathbf{V}_{nose} + (1 - \alpha_{head}) \cdot \mathbf{V}_{iris}$$

$$\mathbf{S}_t = \gamma \cdot \mathbf{P}_{raw} + (1 - \gamma) \cdot \mathbf{S}_{t-1}$$

Donde $\alpha_{head} \approx 0.60$ aporta estabilidad macro en las esquinas y $1 - \alpha_{head} \approx 0.40$ permite microajustes rápidos con los ojos.

### 2. Eliminación del "Toque de Midas" sin Tiempos de Espera (Dwell Time)
En lugar de mirar fijamente un botón durante 1.5 segundos para hacer clic (lo que fatiga la vista y genera clics accidentales al leer), EyeDE desacopla la navegación de la selección:
* **Mira** para iluminar cualquiera de las 9 Macro-Zonas.
* **Abre ligeramente la boca** (controlada mediante **MAR — Mouth Aspect Ratio** en tiempo real con una máquina de estados de 150 ms de *debounce*) para disparar un `CLICK` instantáneo y sin latencia.

### 3. HUD No-Intrusivo `WindowDoesNotAcceptFocus`
Construido con `PyQt6`, el overlay transparente 3x3 se sitúa sobre VS Code, PyCharm o cualquier IDE usando `Qt.WindowType.WindowDoesNotAcceptFocus` y el estilo Win32 nativo `WS_EX_TRANSPARENT`. Tu editor **nunca pierde el foco del teclado ni el parpadeo del cursor**, y los clics de ratón físicos atraviesan la cuadrícula transparente hacia el código subyacente.

### 4. Parser AST en Vivo Tolerante a Fallos y Predictor IA Asíncrono
El código a medio escribir rara vez compila. `ContextReader` combina el módulo nativo `ast.walk()` de Python con un motor de respaldo ordenado por líneas basado en expresiones regulares para extraer variables locales, argumentos y clases del archivo activo —incluso cuando hay un `SyntaxError` temporal— alimentando un worker asíncrono (`Ollama` / API / Heurísticas locales) para rellenar 6 completados de código con un solo clic, preservando siempre los botones de Pausa y Volver.

---

## 🏗️ Arquitectura del Sistema

```text
+-------------------------------------------------------------------------+
|                  TRACKER DE CÁMARA (QThread)                            |
|  Captura OpenCV -> MediaPipe FaceMesh (478 pts) -> Vectores Iris y Nariz|
+-------------------+---------------------------------+-------------------+
                    | pyqtSignal(x, y)                | pyqtSignal("MOUTH_CLICK")
                    v                                 v
+-------------------------------------------------------------------------+
|                 HUD TRANSPARENTE PYQT6 NO-FOCUS (GUI Principal)         |
|   [0: FLUJO]     [1: FUNC/CLASE]  [2: OPERADORES]                       |
|   [3: CURSOR]    [4: 👁️ PAUSA]     [5: VARS LOCALES / T9]                |
|   [6: EDIT/UNDO] [7: ENTER/TAB]   [8: ⚡ PREDICTOR IA]                  |
+-------------------+---------------------------------+-------------------+
                    |                                 |
                    v                                 v
+-----------------------------------+   +---------------------------------+
|      MOTOR DE INYECCIÓN DE CÓDIGO |   |  MOTOR DE CONTEXTO E IA (QThread)|
| - Intercambio Atómico de Portapap.|   | - AST en vivo + Parser de Símbol.|
| - Reposicionamiento de Cursor     |   | - Cliente Asíncrono Ollama/OpenAI|
| - Nodos Pegajosos vs. Retorno     |   | - Respaldo Heurístico Cero-Lat. |
+-----------------------------------+   +---------------------------------+
                    |                                 |
                    +----------------+----------------+
                                     |
                                     v
                    +---------------------------------+
                    |    IDE DESTINO (VS Code, etc.)  |
                    +---------------------------------+
```

---

## 🚀 Inicio Rápido

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

# 4. Iniciar EyeDE
python main.py
```

### Opciones de Línea de Comandos (CLI)

```bash
python main.py                    # Inicio estándar con cámara y calibración guardada
python main.py --recalibrate      # Fuerza el asistente visual de calibración de 5 puntos
python main.py --camera synthetic # Modo sintético sin webcam física (para pruebas y demos)
```

### Calibración Rápida de 5 Puntos
En el primer inicio (o con `--recalibrate`), EyeDE abrirá la **Pantalla de Calibración Visual de 5 Puntos**:
1. Mira al objetivo brillante en el **Centro** y abre ligeramente la boca.
2. Repite el proceso para las **4 esquinas** de la pantalla (Arriba-Izq, Arriba-Der, Abajo-Izq, Abajo-Der).
3. Tu matriz de interpolación se guardará automáticamente en `calibration_profile.json`. ¡Abre VS Code, sitúa el cursor en cualquier archivo `.py` y empieza a programar con la mirada!

---

## 🎮 Controles y Atajos en Tiempo Real

| Tecla | Acción | Descripción |
| :--- | :--- | :--- |
| **`Ctrl+Alt+Q` / `F12`** | **🚨 Botón de Emergencia (Killswitch)** | **Atajo global en todo el SO**: apaga EyeDE limpiamente de inmediato, incluso cuando VS Code tiene el foco |
| **`Ctrl+Alt+R`** | **🔄 Reset de Emergencia** | Restablece al instante la calibración a valores por defecto seguros y neutrales |
| **`[C]`** | **Recalibrar Centro** | Mira al centro de la pantalla y pulsa `C` para fijar tu ancla neutra |
| **`[+]` / `[-]`** | **Ajustar Sensibilidad** | Aumenta o disminuye la sensibilidad de seguimiento sobre la marcha |
| **`[P]` / `[Espacio]`** | **Pausa / Modo Lectura** | Atenúa el HUD al 10% de opacidad para leer código sin clics involuntarios |
| **`[M]`** | **Alternar Mini-Feed** | Muestra u oculta la miniatura de la cámara y la barra de nivel MAR |
| **`[Q]` / `[ESC]`** | **Salida Segura** | Libera la cámara y cierra de forma limpia todos los hilos secundarios |

---

## 📂 Estructura del Proyecto

```text
IDEye/
├── main.py                      # Lanzador raíz (`python main.py`)
├── config.py                    # Wrapper de configuración en la raíz
├── requirements.txt             # Dependencias del proyecto
├── pytest.ini                   # Configuración y filtros de advertencias para Pytest
├── calibration_profile.json      # Perfil bilineal guardado de calibración de 5 puntos
├── eyede/
│   ├── config.py                # Pesos de tracking, umbrales MAR, estilos y ajustes de IA
│   ├── main.py                  # Ciclo de vida de PyQt6 y enrutador de señales
│   ├── core/
│   │   ├── camera_tracker.py    # Pipeline QThread OpenCV + MediaPipe FaceMesh (478 pts)
│   │   ├── gaze_estimator.py    # Matemáticas híbridas, supresión de parpadeo y filtro EMA
│   │   └── gesture_detector.py  # Cálculo MAR y máquina de estados con debounce
│   ├── ui/
│   │   ├── overlay_window.py    # HUD de macro-zonas 3x3 transparente en PyQt6 (No-Focus)
│   │   ├── calibration_ui.py    # Asistente de calibración a pantalla completa de 5 puntos
│   │   └── debug_widget.py      # Mini-feed de cámara, nivel MAR y selector de archivos .py
│   └── actions/
│       ├── code_injector.py     # Inyección atómica no bloqueante con offsets de cursor
│       ├── menu_trees.py        # Árboles de sintaxis jerárquica 3x3 y nodos pegajosos
│       ├── context_reader.py    # Extractor de símbolos AST + Regex tolerante a errores
│       └── ai_predictor.py      # Worker QThread asíncrono para IA con respaldo heurístico
└── tests/                       # Suite de 198 pruebas automatizadas de unidad e integración
    ├── test_phase1.py           # Tests de visión artificial y máquina de estados MAR
    ├── test_phase2.py           # Tests de QThread, banderas de ventana no-focus y calibración
    ├── test_phase3.py           # Validación de árboles sintácticos e inyección de código
    ├── test_phase4.py           # Tests de ContextReader AST/Regex y AIPredictorWorker
    ├── test_vision_math.py      # Acotación matemática de mirada y auditorías de división por cero
    ├── test_menu_integrity.py   # Verificación recursiva de las 9 casillas en todo el árbol
    ├── test_code_injector.py    # Seguridad de teclas modificadoras y portapapeles
    └── test_context_and_ai.py   # Resiliencia ante errores de sintaxis y JSON de LLMs
```

---

## 🧪 Testing y QA

EyeDE incluye una suite completa de pruebas automatizadas mediante *mocks* que cubren casos límite matemáticos, integridad recursiva de los árboles de menús, seguridad de teclas modificadoras y tolerancia a fallos del AST:

```bash
pytest -v
```

```text
============================= 198 passed in 9.24s =============================
```

> [!NOTE]
> Todos los 198 tests se ejecutan de forma *headless* sin requerir cámara web física, servidor gráfico ni conexión a Internet.

---

## 🗺️ Hoja de Ruta

- [x] **Fase 1:** Seguimiento híbrido de Iris + Cabeza con suavizado EMA y disparador MAR por apertura de boca.
- [x] **Fase 2:** HUD transparente PyQt6 `WindowDoesNotAcceptFocus` y calibración de 5 puntos en JSON.
- [x] **Fase 3:** Árboles sintácticos jerárquicos 3x3 e inyección atómica de código con offsets de cursor.
- [x] **Fase 4:** Extracción de símbolos AST/Regex en vivo y predicción asíncrona de código con IA.
- [x] **Fase Extra:** Auditoría forense de código, eliminación de fugas de memoria y 198 tests automatizados.
- [ ] **Fase 5:** Perfiles multi-lenguaje (TypeScript/JS, Rust, C++, Go) y extensión WebSocket nativa para VS Code.

---

## 🤝 Contribuciones y Licencia

¡Las contribuciones, sugerencias de accesibilidad y pull requests son bienvenidas! Bajo los términos de la **Licencia MIT**.

<div align="center">
  <sub>Desarrollado con ❤️ por <b>Daniel Casado Juan</b></sub>
</div>
