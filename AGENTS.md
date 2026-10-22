# IDEye — Software Open-Source de Programación Controlada por Ojos

## Visión del Proyecto
IDEye es un entorno de desarrollo integrado (IDE) y sistema asistivo de código abierto diseñado para permitir a desarrolladores programar rápida, ergonómica y eficazmente **utilizando exclusivamente el seguimiento ocular (eye-tracking / gaze control)**, sin requerir teclado ni ratón físicos, ni comandos de voz obligatorios.

---

## Principios Arquitectónicos Fundamentales

### 1. El Problema del Toque de Midas (The Midas Touch Problem)
* Los ojos son órganos sensoriales de entrada, no efectores mecánicos de salida. Mirar un elemento no debe desencadenar automáticamente una acción irreversible.
* **Mecanismos de activación obligatorios**:
  * **Dwell-Time adaptativo**: Fijación de la mirada con indicador visual circular/radial progresivo (típicamente 300ms a 600ms, configurable por el usuario).
  * **Gestos oculares / Parpadeo voluntario**: Detección de parpadeos conscientes mediante Eye Aspect Ratio (EAR > 250ms), diferenciados de parpadeos reflejos involuntarios (<150ms).
  * **Zonas de reposo (Resting Zones)**: Áreas neutras perimetrales donde la mirada puede posarse para leer código o pensar sin activar ningún control.

### 2. Paradigma de Edición Estructural sobre Edición por Carácter
* El tecleo carácter por carácter con teclado en pantalla mediante la mirada es lento (10-20 palabras por minuto) y produce fatiga ocular.
* **Solución Mandataria**: Navegación y manipulación de código basada en **AST (Abstract Syntax Tree)** mediante Tree-sitter / LSP:
  * Saltos semánticos entre nodos (funciones, bloques, clases, expresiones).
  * Expansión y contracción de alcance de selección.
  * Plantillas de código y fragmentos (snippets) parametrizados con inserción en un solo dwell.
  * Inferencia predictiva de tokens y autocompletado mediante modelos de lenguaje (LLMs / Copilot).

### 3. Presupuesto de Rendimiento y Latencia (Real-time Pipeline)
* **Presupuesto de Latencia Extremo a Extremo**: < 35 ms desde la captura del fotograma de cámara hasta la actualización visual del cursor ocular.
* **Procesamiento de Visión por Computador (CV)**:
  * Siempre en hilo/proceso secundario (Worker Thread o Subproceso dedicado) para jamás bloquear el hilo principal de la UI.
  * Consumo de CPU objetivo: < 10% en equipos estándar.
* **Filtrado de Temblor (Jitter) y Sácadas**:
  * Implementación obligatoria de **One Euro Filter (1€ Filter)** o filtro de Kalman adaptativo para estabilizar fijaciones sin introducir retraso perceptible durante las sácadas.
  * Algoritmo I-VT (Velocity-Threshold Identification) o I-DT (Dispersion-Threshold) para clasificar fijaciones y sácadas en tiempo real.

### 4. Ergonomía Visual y Accesibilidad
* **Tamaño mínimo de objetivos visuales**: Al menos 45x45 píxeles (preferiblemente 60-80px) para acomodar la precisión angular típica del seguimiento ocular (0.5° - 1.5° de ángulo visual).
* **Lente de Aumento / Zoom Jerárquico**: Para seleccionar elementos densos o pequeños (puntos, comas, paréntesis), usar una lupa / cuadrícula de zoom en dos pasos.
* **Tema Visual**: Modo oscuro de alto contraste (WCAG AAA) para minimizar la fatiga retiniana y evitar fluctuaciones en el tamaño de la pupila debidas a cambios de luminosidad en pantalla.

---

## Estructura Modular Recomendada

```text
IDEye/
├── core/
│   ├── tracker/        # Captura de cámara, MediaPipe / Tobii, detección de pupila e iris
│   ├── calibration/    # Algoritmos de calibración (polinomial, homografía, 9 puntos)
│   ├── filters/        # One Euro Filter, Kalman, supresión de temblor, detector sácadas
│   └── virtual_input/  # Inyección de eventos en SO (SendInput / pynput / uiohook)
├── ui/
│   ├── dwell/          # Indicadores visuales de tiempo de fijación (radial progress)
│   ├── keyboard/       # Teclado virtual especializado en programación y operadores
│   ├── zoom_grid/      # Lupa y cuadrícula de precisión para selección fina
│   └── rest_zones/     # Zonas neutras seguras de lectura
├── editor/
│   ├── ast/            # Tree-sitter parser, navegación estructural por bloques
│   ├── lsp_client/     # Conexión Language Server Protocol (diagnósticos, autocompletado)
│   └── snippets/       # Generador y expansor de plantillas de código asistivas
└── tests/
    └── synthetic_gaze/ # Generador sintético de eventos oculares para pruebas sin cámara
```

---

## Flujo de Trabajo y Publicación

* **Publicar siempre**: al terminar una tarea, haz `commit` y `push` a `origin/main` sin esperar a que el usuario lo pida, siempre que las pruebas relevantes pasen.
* **Verificar antes de publicar**: ejecuta la suite afectada (o la suite completa si el cambio toca varios módulos) y revisa `git status` para no dejar cambios importantes fuera del commit.
* **Commits atómicos**: usa mensajes claros con prefijo convencional (`feat:`, `fix:`, `docs:`, `test:`, `chore:`). No mezcles cambios no relacionados cuando sea evitable.
* **Nunca subir artefactos ignorados**: respeta `.gitignore` (`dist/`, `build/`, `node_modules/`, logs y cachés).
* **Recompilar si afecta a la app**: si el cambio modifica comportamiento visible, regenera `dist/IDEye/IDEye.exe` con `python build_app.py` antes de terminar.
* **Si el push falla**: no lo ocultes; informa del error, deja el commit local hecho y explica qué falta para resolverlo.

---

## Herramientas de Desarrollo

* **MCP `ideye-dev-tools`**: definido en `.opencode/opencode.jsonc` y servido por `tools/ideye-mcp/index.mjs`. Expone simulación de mirada, benchmark del One Euro Filter, calibración polinomial, detección de cámaras y resolución de objetivos AST. Úsalo para diagnóstico y pruebas sin hardware.
* **Skills locales**: `.agents/skills/` incluye skills de pipeline ocular, UX de mirada, teclado predictivo, edición AST, entrada virtual, hardware, pruebas sintéticas, testing PyQt6 offscreen, empaquetado Windows y puente WebSocket de VS Code.
* **Context7**: disponible para consultar documentación actualizada de librerías (PyQt6, MediaPipe, websockets, VS Code API).
* **GitHub MCP**: configurado pero requiere autenticación OAuth; para operaciones de repositorio usa `git` mientras no esté conectado.
* **Uso obligatorio bajo petición**: cuando el usuario pida usar una skill, MCP o plugin concreto, cárgalo o invócalo antes de responder. Si la tarea coincide claramente con una skill local o con una herramienta de `ideye-dev-tools`, úsala en lugar de resolverlo con herramientas genéricas.

---

## Enrutado de Modelos en IDEye

Antes de editar, declara la clase y el agente elegido. La tabla completa está en el `AGENTS.md` global; para este repo:

| Tarea típica | Clase | Agente / modelo |
| :--- | :--- | :--- |
| Fix de una línea, ajuste de test, typo | S | `build` con `deepseek-v4.1-flash` |
| Feature de 2–5 archivos (T9, modo nuevo, puente WebSocket) | M | `@refactor` (`kimi-k2.7-code`) |
| Rediseño de HUD/overlay, refactor multiarchivo, cambio de arquitectura | L | `@architect` (`qwen3.7-plus`) + `@refactor` |
| Bug difícil tras 2 intentos, matemáticas de mirada/filtros | H | `@scalpel` (`deepseek-v4-pro`), solo el fix |
| README, guías, changelog, commit | Docs | `@documenter` (`longcat-2.5-preview-free`) |
| Revisión de UI, seguridad o regresiones | Review | `@reviewer` / `@security` (`qwen3.7-plus`) |

Reglas específicas:

- **Un rediseño visual del overlay es L**, aunque parezca “solo pintar”: toca geometría, hit-testing, estilos, main y tests.
- **T9/redacción y el hub de modos son M**: no se implementan con `build`/flash.
- **F12/killswitch**: investigación y fix pequeño pueden ser S, pero si el root cause no aparece en 2 intentos, escala a `@scalpel`.
- No mezclar modelos dentro del mismo commit: primero se implementa con el agente correcto, luego se revisa con `@reviewer` si aplica.

---

## 📖 REGLA OBLIGATORIA DE DOCUMENTACIÓN VIVA (INTERACTIVE GUIDE SYNC)

1. Cada vez que añadas, modifiques o elimines una funcionalidad, modo, gesto facial, atajo de teclado o comportamiento de UI en IDEye:
   - DEBES actualizar obligatoriamente `eyede/core/guide_catalog.py` y regenerar `docs/guia_interactiva.html` ejecutando el generador de la guía.
   - Toda nueva función debe documentarse siguiendo el estilo visual "Game Manual" (título llamativo en cinta, badge visual, icono SVG y explicación clara de 3-4 líneas orientada al usuario final).
   - Ninguna tarea o Fase se considerará completada si `docs/guia_interactiva.html`, `README.md` y `README.es.md` no reflejan los cambios realizados.

### Generación y verificación

```bash
python -c "from eyede.core.guide_catalog import generate_interactive_guide; print(generate_interactive_guide())"
pytest -q tests/test_interactive_guide.py
```

La guía debe seguir siendo 100% autocontenida (CSS, SVG y JavaScript inline, sin CDN ni recursos externos) y abrirse offline.
