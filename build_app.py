"""IDEye - Cross-platform PyInstaller builder (Phase 8.3).

Builds a self-contained onedir distribution on Windows, macOS and Linux.
"""

import os
import sys
import subprocess
import shutil

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(ROOT_DIR, "ideye", "assets")
DEFAULTS_DIR = os.path.join(ASSETS_DIR, "defaults")
ICON_ICO = os.path.join(ROOT_DIR, "ideye.ico")
ICON_ICNS = os.path.join(ROOT_DIR, "ideye.icns")
MAIN_PY = os.path.join(ROOT_DIR, "main.py")

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
DATA_SEP = ";" if IS_WINDOWS else ":"

# Runtime JSON files. Defaults live in ideye/assets/defaults; live root files
# are only bundled when IDEYE_BUNDLE_USER_DATA=1 is explicitly set.
PROFILE_FILES = ("user_settings.json", "custom_macros.json", "calibration_profile.json")
LIVE_DATA_ENV = "IDEYE_BUNDLE_USER_DATA"


def _data_arg(source: str, destination: str) -> str:
    return f"--add-data={source}{DATA_SEP}{destination}"


def _icon_arg() -> str:
    if IS_WINDOWS and os.path.exists(ICON_ICO):
        return f"--icon={ICON_ICO}"
    if IS_MACOS and os.path.exists(ICON_ICNS):
        return f"--icon={ICON_ICNS}"
    return ""


def _pynput_backends() -> list:
    if IS_WINDOWS:
        return [
            "--hidden-import=pynput.keyboard._win32",
            "--hidden-import=pynput.mouse._win32",
        ]
    if IS_MACOS:
        return [
            "--hidden-import=pynput.keyboard._darwin",
            "--hidden-import=pynput.mouse._darwin",
        ]
    return [
        "--hidden-import=pynput.keyboard._xorg",
        "--hidden-import=pynput.mouse._xorg",
    ]


def _profile_sources() -> list:
    """Returns (filename, source_path) for sanitized defaults or opt-in live data."""
    include_live = os.environ.get(LIVE_DATA_ENV, "").strip() == "1"
    sources = []
    for filename in PROFILE_FILES:
        default_path = os.path.join(DEFAULTS_DIR, filename)
        live_path = os.path.join(ROOT_DIR, filename)
        if include_live and os.path.isfile(live_path):
            sources.append((filename, live_path))
        elif os.path.isfile(default_path):
            sources.append((filename, default_path))
    return sources


def build_command() -> list:
    """Returns the complete PyInstaller command for the current platform."""
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name=IDEye",
        _data_arg(ASSETS_DIR, "ideye/assets"),
        "--collect-data=mediapipe",
        "--collect-binaries=mediapipe",
        "--copy-metadata=mediapipe",
        "--hidden-import=ideye",
        "--hidden-import=ideye.main",
        "--hidden-import=ideye.config",
        "--hidden-import=ideye.core.camera_tracker",
        "--hidden-import=ideye.core.gaze_estimator",
        "--hidden-import=ideye.core.gesture_detector",
        "--hidden-import=ideye.core.hotkey_manager",
        "--hidden-import=ideye.core.sound_feedback",
        "--hidden-import=ideye.core.mouse_controller",
        "--hidden-import=ideye.core.settings_manager",
        "--hidden-import=ideye.core.macro_manager",
        "--hidden-import=ideye.core.screen_manager",
        "--hidden-import=ideye.core.guide_catalog",
        "--hidden-import=ideye.core.guide_builder",
        "--hidden-import=ideye.core.bezel_crossing",
        "--hidden-import=ideye.core.logging_config",
        "--hidden-import=ideye.core.window_watcher",
        "--hidden-import=ideye.core.telemetry_manager",
        "--hidden-import=ideye.actions.clipboard_history",
        "--hidden-import=ideye.ui.header_layout",
        "--hidden-import=ideye.ui.macro_editor_dialog",
        "--hidden-import=ideye.modes.sniper_mouse_mode",
        "--hidden-import=ideye.ui.overlay_window",
        "--hidden-import=ideye.ui.debug_widget",
        "--hidden-import=ideye.ui.calibration_ui",
        "--hidden-import=ideye.ui.icon_manager",
        "--hidden-import=ideye.actions.code_injector",
        "--hidden-import=ideye.actions.menu_trees",
        "--hidden-import=ideye.actions.semantic_taxonomy",
        "--hidden-import=ideye.modes.debug_mode",
        "--hidden-import=ideye.actions.context_reader",
        "--hidden-import=ideye.actions.ai_predictor",
        "--hidden-import=ideye.actions.language_support",
        "--hidden-import=ideye.actions.text_predictor",
        "--hidden-import=ideye.core.websocket_bridge",
        "--hidden-import=ideye.core.gaze_scroller",
        "--hidden-import=ideye.core.eco_power_manager",
        "--hidden-import=ideye.core.game_profiles",
        "--hidden-import=ideye.core.lighting_compensator",
        "--hidden-import=ideye.core.health_guard",
        "--hidden-import=ideye.actions.diagnostics_fixer",
        "--hidden-import=ideye.actions.ast_code_jumper",
        "--hidden-import=ideye.actions.agentic_launcher",
        "--hidden-import=ideye.ui.system_tray",
        "--hidden-import=ideye.ui.sniper_lens",
        "--hidden-import=ideye.modes.mode_manager",
        "--hidden-import=ideye.modes.coding_mode",
        "--hidden-import=ideye.modes.writing_mode",
        "--hidden-import=ideye.modes.terminal_git_mode",
        "--hidden-import=ideye.modes.data_math_mode",
        "--hidden-import=ideye.modes.ide_nav_mode",
        "--hidden-import=websockets",
        "--hidden-import=websockets.asyncio",
        "--hidden-import=websockets.asyncio.server",
        "--hidden-import=PyQt6.QtSvg",
        "--hidden-import=PyQt6.QtNetwork",
    ]
    if IS_WINDOWS or IS_MACOS:
        cmd.append("--windowed")
    icon = _icon_arg()
    if icon:
        cmd.append(icon)
    for filename, source in _profile_sources():
        cmd.append(_data_arg(source, "."))
    cmd.extend(_pynput_backends())
    if IS_MACOS:
        cmd.append("--osx-bundle-identifier=com.vistax.ideye")
    cmd.extend(["--onedir", MAIN_PY])
    return cmd


def _dist_candidates() -> list:
    return [
        os.path.join(ROOT_DIR, "dist", "IDEye", "IDEye.exe"),
        os.path.join(ROOT_DIR, "dist", "IDEye.app"),
        os.path.join(ROOT_DIR, "dist", "IDEye", "IDEye"),
    ]


def _copy_user_files(dist_dir: str) -> None:
    for filename, source in _profile_sources():
        target = os.path.join(dist_dir, filename)
        if os.path.exists(target):
            print(f"[INFO] Keeping existing {filename} in {dist_dir}")
            continue
        try:
            shutil.copy2(source, target)
            print(f"[INFO] Copied {filename} to {dist_dir}")
        except Exception as exc:
            print(f"[WARN] Could not copy {filename}: {exc}")


def build():
    print("=" * 60)
    print(f"  IDEye - Building Native Desktop Application ({sys.platform})")
    print("=" * 60)

    if not os.path.isdir(ASSETS_DIR):
        print(f"[ERROR] Assets directory not found at {ASSETS_DIR}")
        return False
    if not os.path.isfile(MAIN_PY):
        print(f"[ERROR] Entrypoint not found at {MAIN_PY}")
        return False

    cmd = build_command()
    print("[INFO] Running PyInstaller command:")
    print(" ".join(cmd))
    print("-" * 60)

    result = subprocess.run(cmd, cwd=ROOT_DIR)
    if result.returncode != 0:
        print(f"[ERROR] PyInstaller failed with exit code {result.returncode}")
        return False

    artifact = next((path for path in _dist_candidates() if os.path.exists(path)), None)
    if artifact is None:
        print("[ERROR] Expected build artifact was not found in dist/.")
        return False

    print("-" * 60)
    print(f"[SUCCESS] Native application generated at:\n  {artifact}")
    if IS_MACOS and artifact.endswith(".app"):
        _copy_user_files(os.path.join(artifact, "Contents", "MacOS"))
    elif os.path.isdir(artifact):
        _copy_user_files(artifact)
    return True


if __name__ == "__main__":
    success = build()
    sys.exit(0 if success else 1)
