# IDEye — Guía para Claude Code

IDEye es un sistema asistivo de código abierto para programar **usando exclusivamente el seguimiento ocular** (sin teclado ni ratón físicos ni voz obligatoria).

## Arquitectura

- **Stack**: Python, PyQt6 (overlay/HUD), MediaPipe + OpenCV (visión), pynput (entrada virtual), websockets.
- **Paquete principal `ideye/`**: `core/` (tracking, gestos, hotkeys, WebSocket, guía), `actions/` (inyección de código, menús, AST, predicción), `modes/`, `ui/` (overlay, `icon_manager.py`), `assets/`.
- **Puente VS Code**: `core/websocket_bridge.py` (WebSocket) + extensión en `vscode-extension/`.
- **Servidor MCP `ideye-dev-tools`**: `tools/ideye-mcp/index.mjs`. Herramientas: `simulate_gaze_stream`, `benchmark_one_euro_filter`, `calculate_gaze_calibration`, `detect_camera_devices`, `resolve_ast_target`, `get_pending_gaze_task`. Úsalas para diagnóstico y pruebas sin hardware.
- **Empaquetado**: `python build_app.py` (PyInstaller, salida `dist/IDEye/IDEye.exe`). Recompila si el cambio altera el comportamiento visible.

## Principios de diseño

1. **Toque de Midas**: mirar nunca dispara una acción irreversible. Activación por dwell-time adaptativo (300–600 ms, indicador radial), parpadeo voluntario (EAR > 250 ms; los reflejos < 150 ms se ignoran) y zonas de reposo para leer sin activar nada.
2. **Edición estructural (AST)** sobre edición por carácter: saltos semánticos, expansión/contracción de selección, snippets de un solo dwell.
3. **Rendimiento**: < 35 ms de la captura al cursor; CPU objetivo < 10 %; la visión corre siempre en hilo/proceso secundario, jamás en el hilo de UI. Filtrado con One Euro Filter (o Kalman adaptativo) e I-VT / I-DT para fijaciones y sácadas.
4. **Ergonomía**: objetivos de al menos 45x45 px (ideal 60–80), lupa/zoom jerárquico para elementos pequeños, tema oscuro de alto contraste (WCAG AAA).

## Regla obligatoria: INTERACTIVE GUIDE SYNC

Al añadir, modificar o eliminar una funcionalidad, modo, gesto facial, atajo o comportamiento de UI:

- Actualiza `ideye/core/guide_catalog.py` y **regenera** `docs/guia_interactiva.html`.
- Documenta cada función con el estilo "Game Manual": título en cinta, badge, icono SVG y explicación de 3–4 líneas orientada al usuario final.
- Ninguna tarea o fase está completa si `docs/guia_interactiva.html`, `README.md` y `README.es.md` no reflejan el cambio.
- La guía debe seguir siendo 100 % autocontenida (CSS, SVG y JS inline; sin CDN ni recursos externos) y abrirse offline.

```powershell
python -c "from ideye.core.guide_catalog import generate_interactive_guide; print(generate_interactive_guide())"
pytest -q tests/test_interactive_guide.py
```

## ZERO EMOJI POLICY

Prohibido el uso de emojis Unicode en `docs/guia_interactiva.html`, `ideye/core/guide_catalog.py` y en cualquier componente visual de la UI. Todo icono, insignia o indicador se implementa con SVG vectorial inline o mediante `IconManager` (Lucide SVG). Lo verifican `tests/test_interactive_guide_sync.py`, `tests/test_help_ui_and_card_layout.py` y `tests/test_adaptive_ast_menus.py`.

## Invariantes del grid 3x3

Verificadas en `tests/test_menu_integrity.py` (no las rompas al tocar `ideye/actions/menu_trees.py` ni menús adaptativos):

- Todo nodo del menú tiene **exactamente 9 ítems** (índices 0–8).
- **Casilla 4 (índice 4) = Pausa / Modo Lectura** (`action_type == "PAUSE"`, etiqueta con "PAUSA") en todos los nodos.
- **Casilla 6 (índice 6) = Volver** (`action_type == "BACK"`, etiqueta con "VOLVER") en todos los submenús (`node_id != "ROOT"`).
- `validate_menu_tree` debe pasar sin errores.

## Liberación de teclas

Ninguna tecla modificadora puede quedar atascada. Toda pulsación de teclas/modificadores va en bloques `try ... finally` que llamen a `release_all_modifiers()` (ver `ideye/actions/code_injector.py`). Para mantener modificadores usa el context manager `hold_modifiers()`, que los libera en orden inverso aunque haya excepción o cancelación.

## Modularidad: límite duro de 500 líneas

- **Ningún archivo `.py`, `.ts`, `.js` o `.mjs` dentro de `ideye/`, `vscode-extension/src/`, `tools/` o `tests/` puede superar las 500 líneas** (docstrings, comentarios y líneas en blanco incluidos). Lo verifica `tests/test_modularity_line_limit.py`.
- **Responsabilidad única y patrón fachada**: cuando un módulo supere o roce las 500 líneas, divídelo en submódulos cohesivos por responsabilidad (cada archivo nuevo idealmente entre 150 y 380 líneas) y re-exporta sus clases y funciones públicas en el archivo original para mantener la retrocompatibilidad de imports.
- Las clases grandes se reparten en mixins (`class X(MixinA, MixinB)`) dentro de un subpaquete; los datos y el CSS se dividen por dominio.

## Tests

- Ejecuta `pytest -v` (config en `pytest.ini`, `testpaths = tests`) y mantén el **100 % de los tests en verde** antes de dar una tarea por terminada.
- Los tests corren sin cámara (mirada sintética) y con `QT_QPA_PLATFORM=offscreen` para PyQt6.

## Flujo de trabajo

- Commits atómicos con prefijo convencional (`feat:`, `fix:`, `docs:`, `test:`, `chore:`); no mezcles cambios no relacionados.
- Respeta `.gitignore` (`dist/`, `build/`, `node_modules/`, logs, cachés). No subas artefactos ignorados.
- Si un push falla, informa del error y deja el commit local hecho.
