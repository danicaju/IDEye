<div align="center">

# IDEye (Vistax L2C Engine)
**The Look-To-Code (L2C) Engine for Hands-Free, Silent Software Engineering**

[![English](https://img.shields.io/badge/Language-English-blue?style=flat-square)](README.md)
[![Español](https://img.shields.io/badge/Idioma-Español-red?style=flat-square)](README.es.md)

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-FaceMesh%20478-00A8E8?style=for-the-badge&logo=google&logoColor=white)](https://developers.google.com/mediapipe)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6%20No--Focus-41CD52?style=for-the-badge&logo=qt&logoColor=white)](https://www.riverbankcomputing.com/software/pyqt/)
[![Tests](https://img.shields.io/badge/Tests-252%20Passing-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)](#-testing--qa)
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

**IDEye (Vistax)** solves this by rethinking the programming interface from first principles: combining a **3x3 Macro-Zone AST HUD**, **hybrid head+iris webcam tracking**, **instant zero-dwell facial-gesture triggers**, and **live AST/LLM context prediction**.

### State-of-the-Art Comparison

| Feature / Tool | Standard Webcam ($0) | 100% Silent (No Voice) | AST / Macro Code Injection | Live Local Variable Awareness |
| :--- | :---: | :---: | :---: | :---: |
| **Talon Voice / Cursorless** | No | No | Si | Si |
| **OptiKey** | Parcial *(IR Recommended)* | Si | No *(Char-by-char)* | No |
| **Google Project Gameface** | Si | Si | No *(Mouse driver only)* | No |
| ** IDEye (Vistax L2C)** | **Si Yes** | **Si Yes** | **Si Yes (3x3 Macro-HUD)** | **Si Yes (AST + AI)** |

---

## Core Innovations

### 1. Hybrid Gaze + Head Vector with EMA & Blink Suppression
Standard webcam pupil tracking lacks dynamic range at normal monitor distances. IDEye fuses the normalized iris offset with the 3D nose-tip anchor vector, suppresses vertical jumps during natural eyelid blinks, and smooths the output via an **Exponential Moving Average (EMA)**:

$$\mathbf{P}_{raw} = \alpha_{head} \cdot \mathbf{V}_{nose} + (1 - \alpha_{head}) \cdot \mathbf{V}_{iris}$$

$$\mathbf{S}_t = \gamma \cdot \mathbf{P}_{raw} + (1 - \gamma) \cdot \mathbf{S}_{t-1}$$

Where $\alpha_{head} \approx 0.60$ provides macro stability across screen corners and $1 - \alpha_{head} \approx 0.40$ allows fast micro-adjustments with the eyes.

### 2. Zero-Dwell "Midas Touch" Elimination
Instead of staring at a button for 1.5 seconds to click (which causes severe eye strain and accidental clicks while reading), IDEye decouples navigation from selection:
* **Look** to highlight any of the 9 Macro-Zones.
* **Slightly open your mouth** (monitored via real-time **MAR — Mouth Aspect Ratio** with a 150ms debounce state machine) to trigger an instant, zero-latency `CLICK`.

### 3. Non-Intrusive `WindowDoesNotAcceptFocus` HUD
Built with `PyQt6`, the transparent 3x3 overlay stays on top of VS Code, PyCharm, or any IDE using `Qt.WindowType.WindowDoesNotAcceptFocus` and native `WS_EX_TRANSPARENT`. Your editor **never loses keyboard focus or cursor blinking**, and physical mouse clicks pass seamlessly through the transparent grid to the code beneath.

### 4. Fault-Tolerant Live AST + Async AI Predictor
Half-written code rarely compiles. `ContextReader` combines Python's native `ast.walk()` with a line-ordered regex fallback engine to extract local variables, function arguments, and classes from your active file—even when a `SyntaxError` is present. It feeds them into an asynchronous worker (`Ollama` / OpenAI API / Local Heuristics) to populate 6 one-click completions while preserving emergency Pause and Back buttons.

---

## System Architecture

```text
+-------------------------------------------------------------------------+
| CAMERA TRACKER (QThread) |
| OpenCV Capture -> MediaPipe FaceMesh (478 pts) -> Iris + Nose Vectors |
+-------------------+---------------------------------+-------------------+
 | pyqtSignal(x, y) | pyqtSignal("MOUTH_CLICK")
 v v
+-------------------------------------------------------------------------+
| PYQT6 NO-FOCUS OVERLAY (Main GUI) |
| [0: FLOW] [1: FUNC/CLASS] [2: OPERATORS] |
| [3: CURSOR] [4: PAUSE] [5: LOCAL VARS / T9] |
| [6: EDIT/UNDO] [7: ENTER/TAB] [8: AI PREDICTOR] |
+-------------------+---------------------------------+-------------------+
 | |
 v v
+-----------------------------------+ +---------------------------------+
| CODE INJECTOR ENGINE | | CONTEXT & AI ENGINE (QThread) |
| - Clipboard Atomic Swap (Ctrl+V) | | - Live AST + Regex Symbol Parse |
| - Auto Cursor Offset Reposition | | - Async Ollama / OpenAI Client |
| - Sticky vs. Auto-Return Nodes | | - Zero-Latency Heuristic Backup |
+-----------------------------------+ +---------------------------------+
 | |
 +----------------+----------------+
 |
 v
 +---------------------------------+
 | TARGET IDE (VS Code, etc.) |
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
| **`Ctrl+Alt+R`** | **Emergency Reset** | Immediately clears 5-point calibration weights and reverts to safe neutral mapping |
| **`[A]`** | **Toggle Smart Menus** | Toggle real-time context-adaptive menus (auto-adapts 9 blocks to function signatures, try blocks, loops, etc.) |
| **`[H]`** | **Help & Gesture Guide** | Open/close the in-app gesture and shortcut cheat sheet modal |
| **Right Wink** | **Pause / Total Hide** | Completely hides HUD from screen so 0% of IDE is obstructed; wink right again to restore |
| **Left Wink** | **Back / Undo** | Navigates back to previous menu node; triggers Undo if at root |
| **`[T]`** | **Cycle Tracking Mode** | Switch between **`HEAD_PRIMARY`** (Default - smooth head tracking), **`PURE_IRIS`**, and **`HYBRID`** |
| **`[C]`** | **Center Recalibration** | Look at the screen center and press `C` to reset your neutral anchor |
| **`[+]` / `[-]`** | **Sensitivity Adjust** | Increase or decrease gaze tracking sensitivity on the fly |
| **`[P]` / `[Space]`** | **Pause / Reading Mode** | Dim HUD to 10% opacity so you can read code without accidental clicks |
| **`[M]`** | **Toggle Mini-Feed** | Show or hide the bottom camera preview and MAR meter |
| **`[Q]` / `[ESC]`** | **Safe Exit** | Release camera handles and gracefully stop all worker threads |
| **Eye Exit** | **[X SALIR] Hands-Free** | Gaze at the top-right header `[X SALIR]` and mouth-click; brings up a 100% eye-accessible confirmation dialogue |

---

## Project Structure

```text
IDEye/
├── main.py # Root launcher (`python main.py`)
├── config.py # Root configuration wrapper
├── requirements.txt # Project dependencies
├── pytest.ini # Pytest configuration & warning filters
├── calibration_profile.json # Saved 5-point bilinear calibration profile
├── eyede/
│ ├── config.py # Tracking weights, MAR thresholds, HUD styles, LLM settings
│ ├── main.py # PyQt6 application lifecycle & signal dispatcher
│ ├── core/
│ │ ├── camera_tracker.py # QThread OpenCV + MediaPipe FaceMesh (478 pts) pipeline
│ │ ├── gaze_estimator.py # Hybrid gaze math, blink suppression, 5-pt calibration & EMA
│ │ └── gesture_detector.py # MAR calculation & debounced state machine
│ ├── ui/
│ │ ├── overlay_window.py # Transparent No-Focus PyQt6 3x3 Macro-Grid HUD
│ │ ├── calibration_ui.py # Fullscreen 5-point visual calibration wizard
│ │ ├── debug_widget.py # Mini camera feed, live tracking mode toggles & controls
│ │ └── icon_manager.py # Vector SVG pre-rendering, caching & glassmorphic badges
│ ├── assets/
│ │ └── icons/ # High-DPI neon SVG icon suite (logo, flow, AI, exit, etc.)
│ └── actions/
│ ├── code_injector.py # Non-blocking atomic clipboard snippet injection & cursor offsets
│ ├── menu_trees.py # 3x3 hierarchical syntax trees & sticky node definitions
│ ├── context_reader.py # Fault-tolerant AST + Regex local symbol extractor
│ └── ai_predictor.py # Async LLM QThread worker + syntactic heuristic fallback
└── tests/ # 444 automated unit & integration tests
 ├── test_phase1.py # Core computer vision & MAR state machine tests
 ├── test_phase2.py # PyQt6 QThread, non-focus window flags & calibration math
 ├── test_phase3.py # Syntax tree validation & code injection tests
 ├── test_phase4.py # ContextReader AST/Regex & AIPredictorWorker tests
 ├── test_vision_math.py # GazeEstimator boundary clipping & zero-division audits
 ├── test_menu_integrity.py # Recursive 9-cell tree verification
 ├── test_code_injector.py # Modifier key recovery & clipboard safety tests
 ├── test_context_and_ai.py # Syntax-error tolerance & LLM JSON resilience tests
 ├── test_calibration_and_killswitch.py # Tikhonov regularized mapping & emergency hotkeys
 └── test_tracking_modes_and_handsfree_exit.py # Pure Iris, VOR decoupling & hands-free exit
```

---

## Testing & QA

IDEye includes a comprehensive hardware-mocked test suite covering mathematical edge cases, recursive menu tree integrity, modifier-key safety, and AST fault tolerance:

```bash
pytest -v
```

```text
============================ 444 passed in 10.93s =============================
```

> [!NOTE]
> All 444 tests run headlessly without requiring a physical webcam, display server, or active internet connection.

---

## Roadmap

- [x] **Phase 1:** Hybrid Iris + Head tracking with EMA smoothing & MAR mouth-click trigger.
- [x] **Phase 2:** PyQt6 `WindowDoesNotAcceptFocus` transparent HUD & 5-point JSON calibration.
- [x] **Phase 3:** 3x3 Hierarchical syntax trees & atomic clipboard code injection with cursor offsets.
- [x] **Phase 4:** Live AST/Regex symbol extraction & asynchronous AI/Heuristic code prediction.
- [x] **Phase Extra:** Forensic code audit, memory leak elimination, and 198 automated tests.
- [ ] **Phase 5:** Multi-language syntax trees (TypeScript/JS, Rust, C++, Go) & native VS Code WebSocket extension.

---

## Contributing & License

Contributions, accessibility feedback, and PRs are welcome! Licensed under the **MIT License**.

<div align="center">
 <sub>Built by <b>Daniel Casado Juan</b></sub>
</div>
