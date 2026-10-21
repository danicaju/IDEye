<div align="center">

# IDEye (Vistax L2C Engine)
**The Look-To-Code (L2C) Engine for Hands-Free, Silent Software Engineering**

[![English](https://img.shields.io/badge/Language-English-blue?style=flat-square)](README.md)
[![Español](https://img.shields.io/badge/Idioma-Español-red?style=flat-square)](README.es.md)

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-FaceMesh%20478-00A8E8?style=for-the-badge&logo=google&logoColor=white)](https://developers.google.com/mediapipe)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6%20No--Focus-41CD52?style=for-the-badge&logo=qt&logoColor=white)](https://www.riverbankcomputing.com/software/pyqt/)
[![Tests](https://img.shields.io/badge/Tests-411%20Passing-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)](#-testing--qa)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

*Write real production code using only a standard webcam, hybrid gaze tracking, and discrete facial gestures. No hands. No voice commands. No expensive infrared hardware.*

[Explore Architecture](#-system-architecture) • [Quick Start](#-quick-start) • [Core Innovations](#-core-innovations) • [Controls & Shortcuts](#-runtime-controls--shortcuts) • [Roadmap](#-roadmap)

---

<!-- TODO: Replace with a 15-second GIF recorded with OBS showing you coding in VS Code with the HUD overlay -->
![IDEye Demo Placeholder](https://via.placeholder.com/900x450/0d1117/58a6ff?text=Insert+GIF+Demo:+IDEye+3x3+HUD+Injecting+Code+into+VS+Code)

</div>

## The Problem & Why IDEye Exists

Developers experiencing severe RSI, carpal tunnel, motor disabilities, or temporary injuries face a major barrier when trying to write code:
1. **Voice-coding tools (Talon, Cursorless)** are amazing, but require constant vocalization—failing in shared offices, libraries, late-night sessions, or for users with speech impairments.
2. **On-screen keyboards (OptiKey)** force letter-by-letter typing (`f`-`o`-`r`-`space`...) and practically require $300–$1,000 specialized infrared eye-trackers (Tobii) because standard webcams suffer from a 100–150px dispersion jitter.
3. **Webcam mouse drivers (Project Gameface, eViacam)** only move the OS cursor; clicking tiny 15px IDE symbols or suffering from the *"Midas Touch" problem* (dwell-time clicking fatigue) makes programming agonizingly slow.

**IDEye (Vistax)** solves this by rethinking the programming interface from first principles: combining a **3x3 Macro-Zone AST HUD**, **hybrid head+iris webcam tracking**, **instant zero-dwell facial-gesture triggers**, **bidirectional VS Code WebSocket integration**, and **live AST/LLM context prediction**.

### State-of-the-Art Comparison

| Feature / Tool | Standard Webcam ($0) | 100% Silent (No Voice) | AST / Macro Code Injection | Live Local Variable Awareness | Bidirectional VS Code WebSocket + Auto-Context Modes + 60 Hz FreeLook & Gaming |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Talon Voice / Cursorless** | No | No | Yes | Yes | No |
| **OptiKey** | Partial *(IR Recommended)* | Yes | No *(Char-by-char)* | No | No |
| **Google Project Gameface** | Yes | Yes | No *(Mouse driver only)* | No | No |
| **IDEye (Vistax L2C)** | **Yes** | **Yes** | **Yes (3x3 Macro-HUD)** | **Yes (AST + AI)** | **Yes** |

---

## Core Innovations

### 1. Sub-Pixel Cranial Centroid & Multi-Mode Tracking
Standard webcam pupil tracking lacks dynamic range at normal monitor distances. IDEye fuses the normalized iris offset with the 3D nose-tip anchor vector:

$$\mathbf{P}_{raw} = \alpha_{head} \cdot \mathbf{V}_{nose} + (1 - \alpha_{head}) \cdot \mathbf{V}_{iris}$$

$$\mathbf{S}_t = \gamma \cdot \mathbf{P}_{raw} + (1 - \gamma) \cdot \mathbf{S}_{t-1}$$

Where $\alpha_{head} \approx 0.60$ provides macro stability across screen corners and $1 - \alpha_{head} \approx 0.40$ allows fast micro-adjustments with the eyes.

For sub-pixel stability, IDEye computes a cranial centroid from MediaPipe FaceMesh landmarks `[1,4,6,168,195,197]` with higher weights on the stable anchors `6`, `168`, and `197`. A hysteresis gate (`STATIC_LOCK_RADIUS=0.0035`, `STATIC_BREAKOUT_RADIUS=0.0085`, 3-frame confirmation, `0.0px` drift) suppresses micro-tremor during fixations without adding lag to saccades. Three tracking modes are provided:
* **`HEAD_PRIMARY`** — default smooth head-weighted tracking.
* **`PURE_IRIS`** — median-of-5 iris samples plus orbital multi-anchor roll compensation for pure eye control.
* **`HYBRID`** — fuses head and iris signals with an adaptive saccade coefficient ramping `0.08 -> 0.55` for fast, stable transitions.

### 2. Zero-Dwell Midas Elimination + Jaw-Lock Gestures
Navigation and activation are fully decoupled: looking only highlights, never clicks. A short mouth opening performs an instant click/inject, while a held open mouth at **55% MAR** enters **Jaw-Lock** drag mode. No dwell timers means no accidental Midas clicks while reading.

### 3. 6-Mode Strategy Engine + WebSocket Auto-Switch
The `ModeManager` hosts six specialized modes — `CODING_MODE`, `WRITING_MODE`, `TERMINAL_GIT_MODE`, `DATA_MATH_MODE`, `NAVIGATION_READ_MODE`, and `FREELOOK_GAMING_MODE` — and can switch automatically based on VS Code context received over the bidirectional WebSocket bridge. FreeLook delivers smooth 60 Hz camera/look control; Gaming mode maps gaze to an OS mouse plus keyboard holds (e.g., Roblox: `W` hold, left-wink jump, right-wink 360° camera).

### 4. Smart Prefix Deduplication
The writing pipeline deduplicates repeated prefix strokes: `h+hola` becomes `ola`, and `h+Hola` becomes a backspace followed by `Hola`. It tracks spaces, punctuation, arrow keys, and backspace state, and works identically over the VS Code WebSocket bridge.

### 5. Glass & Focus HUD + High-DPI Lucide + Procedural Audio
The HUD renders Glass and Focus panels with high-DPI Lucide/SVG icons. Sound feedback is generated procedurally in RAM as WAV data using `numpy`; no external `.wav` files are loaded, keeping the bundle small and offline.

### 6. Fault-Tolerant Live AST + Async AI Predictor
Half-written code rarely compiles. `ContextReader` combines Python's native `ast.walk()` with a line-ordered regex fallback engine to extract local variables, function arguments, and classes from your active file — even when a `SyntaxError` is present. It feeds them into an asynchronous worker (`Ollama` / OpenAI API / Local Heuristics) to populate one-click completions while preserving emergency Pause and Back buttons.

### 7. Non-Intrusive `WindowDoesNotAcceptFocus` HUD + Calibration
Built with `PyQt6`, the transparent overlay stays on top of VS Code, PyCharm, or any IDE using `Qt.WindowType.WindowDoesNotAcceptFocus` and native `WS_EX_TRANSPARENT`. Your editor never loses keyboard focus or cursor blinking, and physical mouse clicks pass seamlessly through the transparent grid to the code beneath. The 5-point visual calibration wizard stores the mapping in `calibration_profile.json`.

### 8. Bidirectional VS Code Bridge + Multilingual Menus
The `WebSocketBridge` exchanges editor state, diagnostics, and selection info with the VS Code extension in real time, enabling context-aware mode switching and snippet injection. Syntax trees are available in multiple languages, including a Spanish T9/common-word dictionary and localized menu labels.

---

## System Architecture

```text
+-------------------------------------------------------------------------+
| CAMERA TRACKER (QThread)                                                |
| OpenCV Capture -> MediaPipe FaceMesh (478 pts) -> Iris + Rigid Cranial Centroid |
+------------------------------------+------------------------------------+
 | pyqtSignal(x, y)                  | pyqtSignal("GESTURE")
 v                                   v
+-------------------------------------------------------------------------+
| PYQT6 NO-FOCUS OVERLAY (Main GUI)                                       |
| [0: FLOW] [1: FUNC/CLASS] [2: OPERATORS]                                |
| [3: CURSOR] [4: PAUSE] [5: LOCAL VARS / T9]                            |
| [6: EDIT/UNDO] [7: ENTER/TAB] [8: AI PREDICTOR]                         |
+------------------------------------+------------------------------------+
 |                                   |
 v                                   v
+-------------------------------+  +--------------------------------------+
| MODE MANAGER & VS CODE        |  | CONTEXT & AI ENGINE (QThread)        |
| WEBSOCKET BRIDGE              |  | - Live AST + Regex Symbol Parse      |
| - CODING / WRITING / TERMINAL |  | - Async Ollama / OpenAI Client       |
| - DATA / NAVIGATION / FREELOOK|  | - Zero-Latency Heuristic Backup      |
| - GAMING                      |  |                                      |
+-------------------------------+  +--------------------------------------+
 |                                   |
 v                                   v
+-------------------------------+  +--------------------------------------+
| CODE INJECTOR ENGINE          |  | PROCEDURAL SOUND ENGINE              |
| - Clipboard Atomic Swap       |  | - numpy RAM WAV synthesis            |
| - Auto Cursor Offset Reposition|  | - No external .wav files             |
| - Sticky vs. Auto-Return Nodes|  |                                      |
+-------------------------------+  +--------------------------------------+
 |                                   |
 v                                   v
+-------------------------------------------------------------------------+
| OS MOUSE & GAMING CONTROLLER                                            |
| - SetCursorPos gaze cursor    | - Jaw-Lock 55% MAR drag                 |
| - W hold / Space / right-click| - FreeLook 60 Hz / Gaming 360 camera    |
+-------------------------------+-----------------------------------------+
 |
 v
+---------------------------------+
| TARGET IDE (VS Code, etc.)      |
+---------------------------------+
```

---

## Quick Start

### Prerequisites
* **Python 3.10+** (Python 3.12 recommended)
* A standard webcam (720p/30fps or higher)
* *Optional:* [Ollama](https://ollama.com/) installed locally (`ollama run qwen2.5-coder:1.5b` or `codellama`) for offline neural line completions.

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/danicaju/IDEye.git
cd IDEye

# 2. Create and activate a virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch IDEye
python main.py
```

### Desktop Application Launchers

IDEye includes native Windows desktop launchers with custom high-DPI branding:

* **Desktop Shortcut (`IDEye.lnk`)**: Direct double-clickable icon on your Windows Desktop with the official `{ IDEye }` branding.
* **Silent Launcher (`IDEye.vbs`)**: Launches IDEye immediately with zero command-line console flash.
* **Batch Launcher (`IDEye.bat`)**: Quick launcher for standard execution.
* **Debug Launcher (`IDEye_debug.bat`)**: Launches with live terminal output for parameter tuning and tracking metrics.
* **Standalone Native Executable (`build_app.py`)**: Compiles IDEye into a self-contained `dist/IDEye/IDEye.exe` with bundled MediaPipe, PyQt6, and asset models.

### CLI Arguments

```bash
python main.py # Standard launch with camera & saved calibration
python main.py --recalibrate # Force the 5-point visual calibration wizard on startup
python main.py --camera synthetic # Run headlessly with synthetic face landmarks (for testing/demo)
```

### 5-Point Quick Calibration
On first launch (or with `--recalibrate`), IDEye launches the **5-Point Visual Calibration Screen**:
1. Look at the glowing target in the **Center** and slightly open your mouth.
2. Repeat for the **4 screen corners** (Top-Left, Top-Right, Bottom-Left, Bottom-Right).
3. The bilinear mapping matrix is calculated and saved to `calibration_profile.json`. Open VS Code, place your cursor in any `.py` file, and start coding!

---

## Runtime Controls & Shortcuts

| Key | Action | Description |
| :--- | :--- | :--- |
| **`Ctrl+Alt+Q` / `F12`** | **Emergency Killswitch** | **Global OS-wide hotkey**: cleanly shuts down IDEye from anywhere in the OS, even when VS Code has focus |
| **`Ctrl+Alt+R`** | **Emergency Reset** | Immediately clears calibration weights and reverts to safe neutral mapping |
| **`[A]`** | **Toggle Smart Menus** | Toggle real-time context-adaptive menus (auto-adapts 9 blocks to function signatures, try blocks, loops, etc.) |
| **`[V]` / `[MODE▾]`** | **Open Mode Selector** | Opens the 6-mode selector (Coding, Writing, Terminal/Git, Data/Math, Navigation, FreeLook/Gaming); does not blindly cycle. Use `Ctrl+Alt+V` anywhere |
| **`[K]`** | **Toggle Auto Mode Switching** | Enables/disables automatic mode changes based on editor context via WebSocket. Use `Ctrl+Alt+K` anywhere |
| **`[F]`** | **FreeLook Mode** | 60 Hz gaze-controlled camera/look mode. Use `Ctrl+Alt+F` anywhere |
| **`[G]`** | **Gaming Mode** | Gaming mouse + controller overlay (Roblox: `W` hold, left-wink jump, right-wink 360° camera). Use `Ctrl+Alt+G` anywhere |
| **`[S]`** | **Toggle Sound Feedback** | Enable/disable procedural audio cues. Use `Ctrl+Alt+S` anywhere |
| **`[H]`** | **Help & Gesture Guide** | Open/close the in-app gesture and shortcut cheat sheet modal |
| **Mouth Click** | **Inject / Click** | Short mouth opening (MAR) triggers a zero-dwell click or snippet injection |
| **Held Mouth** | **Drag / Jaw-Lock** | Holding the mouth open at 55% MAR enables drag/lock without hand buttons |
| **Right Wink** | **Pause / 360° Camera** | Pauses/hides HUD in normal modes; rotates camera 360° in Gaming mode |
| **Left Wink** | **Back / Undo / Jump** | Navigates back in menus or triggers Undo; makes the character jump in Gaming mode |
| **`[T]`** | **Cycle Tracking Mode** | Switch between **`HEAD_PRIMARY`**, **`PURE_IRIS`**, and **`HYBRID`** |
| **`[C]`** | **Center Recalibration** | Look at the screen center and press `C` to reset your neutral anchor |
| **`[+]` / `[-]`** | **Sensitivity Adjust** | Increase or decrease gaze tracking sensitivity on the fly |
| **`[P]` / `[Space]`** | **Pause / Reading Mode** | Dim HUD to 10% opacity so you can read code without accidental clicks |
| **`[M]`** | **Toggle Mini-Feed** | Show or hide the bottom camera preview and MAR meter |
| **`[Q]` / `[ESC]`** | **Safe Exit** | Release camera handles and gracefully stop all worker threads |
| **Eye Exit** | **[X EXIT] Hands-Free** | Gaze at the top-right header `[X EXIT]` and mouth-click; brings up a 100% eye-accessible confirmation dialogue |

---

## Project Structure

```text
IDEye/
├── main.py # Root launcher (`python main.py`)
├── config.py # Root configuration wrapper
├── requirements.txt # Project dependencies
├── pytest.ini # Pytest configuration & warning filters
├── calibration_profile.json # Generated at runtime after calibration
├── build_app.py # PyInstaller onedir desktop build
├── create_desktop_shortcut.py # Windows desktop shortcut helper
├── IDEye.bat / IDEye.vbs / IDEye_debug.bat # Windows launchers
├── tools/
│   └── ideye-mcp/ # MCP server for IDEye development tools
├── vscode-extension/ # VS Code extension for bidirectional WebSocket bridge
├── eyede/
│   ├── config.py # Tracking weights, MAR thresholds, HUD styles, LLM settings
│   ├── main.py # PyQt6 application lifecycle & signal dispatcher
│   ├── core/
│   │   ├── camera_tracker.py # QThread OpenCV + MediaPipe FaceMesh (478 pts) pipeline
│   │   ├── gaze_estimator.py # Hybrid gaze math, calibration & tracking-mode fusion
│   │   ├── gesture_detector.py # MAR calculation, wink detection & debounced state machine
│   │   ├── hotkey_manager.py # Global OS hotkeys (killswitch, reset, mode toggles)
│   │   ├── mouse_controller.py # OS mouse injection (SetCursorPos, gaming controls)
│   │   ├── sound_feedback.py # Procedural numpy RAM WAV audio feedback
│   │   └── websocket_bridge.py # Bidirectional VS Code WebSocket client/server
│   ├── modes/
│   │   ├── base_mode.py # Abstract mode interface
│   │   ├── mode_manager.py # 6-mode strategy engine & auto-context switching
│   │   ├── coding_mode.py # Coding menu trees and snippet injection
│   │   ├── writing_mode.py # T9/dictation text predictions
│   │   ├── terminal_git_mode.py # Terminal / Git command palette
│   │   ├── data_math_mode.py # Data/math symbol entry
│   │   ├── ide_nav_mode.py # IDE navigation & file explorer
│   │   └── sniper_mouse_mode.py # FreeLook direct OS mouse, Jaw-Lock & gaming
│   ├── ui/
│   │   ├── overlay_window.py # Transparent No-Focus PyQt6 HUD
│   │   ├── calibration_ui.py # Fullscreen calibration wizard
│   │   ├── debug_widget.py # Mini camera feed, tracking toggles & controls
│   │   └── icon_manager.py # High-DPI Lucide/SVG icon rendering & glass badges
│   ├── actions/
│   │   ├── menu_trees.py # 3x3 hierarchical syntax trees & sticky nodes
│   │   ├── context_reader.py # Fault-tolerant AST + Regex local symbol extractor
│   │   ├── ai_predictor.py # Async LLM worker + heuristic fallback
│   │   ├── code_injector.py # Atomic clipboard snippet injection & cursor offsets
│   │   ├── language_support.py # Multi-language syntax definitions
│   │   └── text_predictor.py # Local prefix/T9 prediction engine
│   └── assets/
│       ├── data/
│       │   └── es_common_words.txt # Spanish T9/common-word dictionary
│       └── icons/ # High-DPI neon SVG/Lucide icon suite
└── tests/ # 411 automated unit & integration tests (eyede/tests/ are legacy forwarders not collected)
    ├── test_phase1.py # Core computer vision & MAR state machine tests
    ├── test_phase2.py # PyQt6 QThread, non-focus window flags & calibration math
    ├── test_phase3.py # Syntax tree validation & code injection tests
    ├── test_phase4.py # ContextReader AST/Regex & AIPredictorWorker tests
    ├── test_phase5_multilang_and_websocket.py # Multi-language trees & VS Code WebSocket bridge
    ├── test_phase6_modes.py # 6-mode strategy engine & auto-context switching
    ├── test_phase6_6_lucide_ui.py # Lucide/SVG icon manager & high-DPI rendering
    ├── test_phase7_sniper_and_sound.py # FreeLook mouse, gaming gestures & procedural audio
    ├── test_phase7_6_gaze_stability.py # Sub-pixel stability, hysteresis & saccade fusion
    ├── test_glass_focus_ui.py # Glass/Focus HUD widget tests
    ├── test_help_ui_and_card_layout.py # Help card layout & gesture guide UI
    ├── test_writing_t9_predictions.py # Writing mode T9/prefix prediction tests
    ├── test_vision_math.py # GazeEstimator boundary clipping & zero-division audits
    ├── test_menu_integrity.py # Recursive 9-cell tree verification
    ├── test_code_injector.py # Modifier key recovery & clipboard safety tests
    ├── test_context_and_ai.py # Syntax-error tolerance & LLM JSON resilience tests
    ├── test_calibration_and_killswitch.py # Regularized mapping & emergency hotkeys
    └── test_tracking_modes_and_handsfree_exit.py # Pure Iris, VOR decoupling & hands-free exit
```

---

## Testing & QA

IDEye includes a comprehensive hardware-mocked test suite covering mathematical edge cases, recursive menu tree integrity, modifier-key safety, AST fault tolerance, WebSocket messaging, 6-mode strategy engine, and gaze stability:

```bash
pytest -q
```

```text
411 passed, 53 subtests, 12.18s
```

> [!NOTE]
> All 411 tests run headlessly without requiring a physical webcam, display server, or active internet connection. `testpaths=tests` is configured in `pytest.ini`; the legacy forwarders under `eyede/tests/` are not collected.

---

## Roadmap

- [x] **Phase 1:** Hybrid Iris + Head tracking with EMA smoothing & MAR mouth-click trigger.
- [x] **Phase 2:** PyQt6 `WindowDoesNotAcceptFocus` transparent HUD & 5-point JSON calibration.
- [x] **Phase 3:** 3x3 Hierarchical syntax trees & atomic clipboard code injection with cursor offsets.
- [x] **Phase 4:** Live AST/Regex symbol extraction & asynchronous AI/Heuristic code prediction.
- [x] **Phase Extra:** Forensic code audit, memory leak elimination, and hardware-mocked regression coverage.
- [x] **Phase 5:** Multi-language syntax trees (TypeScript/JS, Rust, C++, Go) & native VS Code WebSocket extension.
- [x] **Phase 6:** 6-mode strategy engine (Coding, Writing, Terminal/Git, Data/Math, Navigation, FreeLook/Gaming) & auto-context switching.
- [x] **Phase 6.5:** Glass & Focus HUD: taskbar-safe layout, high-contrast command bar, preview chips, and neutral/active card hierarchy.
- [x] **Phase 6.6:** High-DPI Lucide icon suite, tinted SVG rendering, wider AYUDA button, and help-card layout.
- [x] **Phase 7:** Procedural numpy RAM WAV sound engine and OS mouse foundation (click, drag, scroll).
- [x] **Phase 7.5:** Grid-free FreeLook at 60 Hz, Jaw-Lock, Gaming/Roblox profile, and Smart Prefix Deduplication (`h + hola` -> `ola`).
- [x] **Phase 7.6:** Sub-pixel cranial centroid stability, PURE_IRIS orbital multi-anchor + median, HYBRID saccade fusion, and bidirectional VS Code WebSocket auto-context.
- [x] **Phase 7.7:** Full-screen FreeLook mapping, comfortable edge overscan, and Windows taskbar magnetic rail.
- [x] **Phase 8.1:** Persistent `user_settings.json`, live debounced settings sync, 6th-step biometric MAR calibration, and live MAR slider.
- [ ] **Phase 8:** Multi-monitor gaze handover, custom macro builder, and Linux/macOS packaging.

---

## Contributing & License

Contributions, accessibility feedback, and PRs are welcome! Licensed under the **MIT License**.

<div align="center">
  <sub>Built by <b>Daniel Casado Juan</b></sub>
</div>
