"""IDEye - Cross-platform PyInstaller builder (Phase 8.3).

Builds a self-contained onedir distribution on Windows, macOS and Linux.
"""

import os
import sys
import subprocess
import shutil

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(ROOT_DIR, "eyede", "assets")
ICON_ICO = os.path.join(ROOT_DIR, "eyede.ico")
ICON_ICNS = os.path.join(ROOT_DIR, "eyede.icns")
MAIN_PY = os.path.join(ROOT_DIR, "main.py")

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
DATA_SEP = ";" if IS_WINDOWS else ":"

USER_FILES = ("calibration_profile.json", "user_settings.json", "custom_macros.json")


def _data_arg(source: str, destination: str) -> str:
    return f"--add-data={source}{DATA_SEP}{destination}"


def _icon_arg() -> str:
    if IS_WINDOWS and os.path.exists(ICON_ICO):
        return f"--icon={ICON_ICO}"
    if IS_MACOS and os.path.exists(ICON_ICNS):
        return f"--icon={ICON_ICNS}"
    if IS_MACOS and os.path.exists(ICON_ICO):
        return f"--icon={ICON_ICO}"
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


def build_command() -> list:
    """Returns the complete PyInstaller command for the current platform."""
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name=IDEye",
        "--windowed",
        _data_arg(ASSETS_DIR, "eyede/assets"),
        "--collect-data=mediapipe",
        "--collect-binaries=mediapipe",
        "--copy-metadata=mediapipe",
        "--hidden-import=eyede",
        "--hidden-import=eyede.main",
        "--hidden-import=eyede.config",
        "--hidden-import=eyede.core.camera_tracker",
        "--hidden-import=eyede.core.gaze_estimator",
        "--hidden-import=eyede.core.gesture_detector",
        "--hidden-import=eyede.core.hotkey_manager",
        "--hidden-import=eyede.core.sound_feedback",
        "--hidden-import=eyede.core.mouse_controller",
        "--hidden-import=eyede.core.settings_manager",
        "--hidden-import=eyede.core.macro_manager",
        "--hidden-import=eyede.core.screen_manager",
        "--hidden-import=eyede.ui.macro_editor_dialog",
        "--hidden-import=eyede.modes.sniper_mouse_mode",
        "--hidden-import=eyede.ui.overlay_window",
        "--hidden-import=eyede.ui.debug_widget",
        "--hidden-import=eyede.ui.calibration_ui",
        "--hidden-import=eyede.ui.icon_manager",
        "--hidden-import=eyede.actions.code_injector",
        "--hidden-import=eyede.actions.menu_trees",
        "--hidden-import=eyede.actions.context_reader",
        "--hidden-import=eyede.actions.ai_predictor",
        "--hidden-import=eyede.actions.language_support",
        "--hidden-import=eyede.actions.text_predictor",
        "--hidden-import=eyede.core.websocket_bridge",
        "--hidden-import=websockets",
        "--hidden-import=websockets.asyncio",
        "--hidden-import=websockets.asyncio.server",
        "--hidden-import=PyQt6.QtSvg",
        "--hidden-import=PyQt6.QtNetwork",
    ]
    icon = _icon_arg()
    if icon:
        cmd.append(icon)
    for filename in USER_FILES:
        path = os.path.join(ROOT_DIR, filename)
        if os.path.isfile(path):
            cmd.append(_data_arg(path, "."))
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
    for filename in USER_FILES:
        src = os.path.join(ROOT_DIR, filename)
        if os.path.isfile(src):
            try:
                shutil.copy2(src, os.path.join(dist_dir, filename))
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
