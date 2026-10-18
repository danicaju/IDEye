---
name: assistive-os-virtual-input
description: >-
  Use this skill when implementing OS-level virtual mouse and keyboard emulation, Windows SendInput API, transparent overlay windows (Electron/Tauri/PyQt), and click-through assistive layers.
---

# Entrada Virtual del Sistema Operativo y Capas Transparentes (OS Input Emulation)

Para que un software de programación por mirada controle tanto su propio editor interno como herramientas externas (terminales, navegadores para depuración, herramientas de Git), requiere emulación de bajo nivel a nivel de sistema operativo.

---

## 1. Emulación de Ratón y Teclado en Windows (`SendInput`)

La API recomendada en Windows para inyectar eventos sin ser bloqueada por controles de interfaz o directivas de seguridad es `SendInput`.

### Inyección de Clics por Mirada (Dwell Click):
```python
import ctypes
from ctypes import wintypes
import time

# Constantes de la API de Windows
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
    ]

class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]
    _anonymous_ = ("_input",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("_input", _INPUT)
    ]

def send_gaze_click(screen_x, screen_y, screen_w=1920, screen_h=1080, button='left'):
    # Normalizar a coordenadas normalizadas de Windows (0 a 65535)
    norm_x = int(screen_x * 65535 / screen_w)
    norm_y = int(screen_y * 65535 / screen_h)

    down_flag = MOUSEEVENTF_LEFTDOWN if button == 'left' else MOUSEEVENTF_RIGHTDOWN
    up_flag = MOUSEEVENTF_LEFTUP if button == 'left' else MOUSEEVENTF_RIGHTUP

    # 1. Mover cursor
    inp_move = INPUT(type=INPUT_MOUSE)
    inp_move.mi = MOUSEINPUT(dx=norm_x, dy=norm_y, mouseData=0,
                             dwFlags=MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
                             time=0, dwExtraInfo=None)

    # 2. Pulsar botón
    inp_down = INPUT(type=INPUT_MOUSE)
    inp_down.mi = MOUSEINPUT(dx=norm_x, dy=norm_y, mouseData=0,
                             dwFlags=down_flag | MOUSEEVENTF_ABSOLUTE,
                             time=0, dwExtraInfo=None)

    # 3. Soltar botón
    inp_up = INPUT(type=INPUT_MOUSE)
    inp_up.mi = MOUSEINPUT(dx=norm_x, dy=norm_y, mouseData=0,
                           dwFlags=up_flag | MOUSEEVENTF_ABSOLUTE,
                           time=0, dwExtraInfo=None)

    ctypes.windll.user32.SendInput(1, ctypes.byref(inp_move), ctypes.sizeof(INPUT))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(INPUT))
    time.sleep(0.02)
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(INPUT))
```

---

## 2. Ventana de Superposición Transparente (Transparent Overlay)

El cursor ocular y los anillos de dwell deben visualizarse sobre la pantalla sin robar el foco activo del editor de código ni interferir con las aplicaciones de fondo.

### Configuración de Ventana en Electron / Chromium:
```javascript
const { BrowserWindow } = require('electron');

const overlayWindow = new BrowserWindow({
  width: 1920,
  height: 1080,
  transparent: true,
  frame: false,
  alwaysOnTop: true,
  focusable: false,      // No roba el foco de la ventana activa donde se escribe
  hasShadow: false,
  webPreferences: {
    nodeIntegration: true,
    contextIsolation: false
  }
});

// Permitir que los clics físicos atraviesen la superposición si se desea
// overlayWindow.setIgnoreMouseEvents(true, { forward: true });
```

### Estilos Win32 Nativos:
* `WS_EX_LAYERED` (`0x00080000`): Permite transparencia por canal alfa.
* `WS_EX_TRANSPARENT` (`0x00000020`): Permite que los eventos de ratón pasen a las ventanas inferiores (click-through).
* `WS_EX_NOACTIVATE` (`0x08000000`): Evita que la ventana pase a primer plano al recibir interacción, manteniendo enfocado el editor.

---

## 3. Modos de Operación Asistida del Cursor Ocular

1. **Modo Edición Continua**:
   * El cursor ocular se posiciona sobre el código y permite selección de bloques, saltos de línea y apertura de paleta.
2. **Modo Arrastrar y Soltar (Drag & Drop Ocular)**:
   * Primer dwell sostenido (500 ms) en un bloque de código activa el estado "Enganchado".
   * El usuario mira la nueva ubicación de destino.
   * Segundo dwell sostenido (500 ms) suelta el bloque de código en la nueva posición.
3. **Modo Desplazamiento Suave (Eye Scroll)**:
   * Fijar la mirada en el $10\%$ superior o inferior del viewport de código produce un scroll proporcional y suave sin requerir barra de desplazamiento física.
