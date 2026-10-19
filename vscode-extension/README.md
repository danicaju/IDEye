# IDEye VS Code Bridge Extension

Extensión oficial y nativa de **IDEye (Look-To-Code)** para Visual Studio Code.

## ¿Qué hace esta extensión?
Permite la comunicación bidireccional y de ultra-baja latencia (<5ms) entre el editor Visual Studio Code y el motor de seguimiento de mirada / cabeza **IDEye** a través de un WebSocket local seguro (`ws://127.0.0.1:54321`):

1. **Sincronización Contextual en Vivo**:
   - Envía a IDEye el archivo activo, el lenguaje de programación detectado (`TypeScript`, `Rust`, `C++`, `Go`, `Python`), la posición exacta del cursor y el contexto de las líneas circundantes.
   - Permite que los árboles sintácticos adaptativos (AST) de IDEye ofrezcan exactamente los bloques de código y variables requeridos para la función o bloque actual.

2. **Inyección Nativa de Snippets con TabStops ($1, $2, $0)**:
   - Emplea directamente la API `vscode.window.activeTextEditor.insertSnippet()`.
   - Soporta autocompletado y tabulaciones automáticas sin depender del portapapeles del sistema operativo ni de atajos de teclado virtuales (`Ctrl+V`).

3. **Ejecución de Comandos del Editor**:
   - Navegación precisa de cursor, formato de documento (`editor.action.formatDocument`), salto a definición (`revealDefinition`), deshacer/rehacer y guardado.

## Instalación en VS Code

### Opción Rápida (Directorio de extensiones):
Copia o crea un enlace simbólico de la carpeta `vscode-extension` dentro de tu directorio de extensiones de VS Code:
- **Windows**: `%USERPROFILE%\.vscode\extensions\ideye-vscode-bridge`
- **Linux / macOS**: `~/.vscode/extensions/ideye-vscode-bridge`

Reinicia VS Code o recarga la ventana (`Ctrl+Shift+P` -> `Developer: Reload Window`).

### Estado de la Conexión
En la barra de estado inferior derecha de VS Code verás el indicador de estado:
- `$(eye) IDEye: Conectado` cuando el software IDEye esté en ejecución.
- `$(eye-closed) IDEye: Desconectado` cuando IDEye esté cerrado.
