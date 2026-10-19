"""
IDEye - Desktop Application Builder (PyInstaller)
Compiles IDEye into a native Windows desktop executable with custom icon and bundled assets.
"""

import os
import sys
import subprocess
import shutil

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(ROOT_DIR, "eyede", "assets")
ICON_PATH = os.path.join(ROOT_DIR, "eyede.ico")
MAIN_PY = os.path.join(ROOT_DIR, "main.py")

def build():
    print("=" * 60)
    print("  IDEye - Building Native Windows Desktop Executable")
    print("=" * 60)

    if not os.path.exists(ICON_PATH):
        print(f"[ERROR] Icon not found at {ICON_PATH}")
        return False

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name=IDEye",
        "--windowed",  # No console window popup
        f"--icon={ICON_PATH}",
        f"--add-data={ASSETS_DIR};eyede/assets",
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
        "--hidden-import=eyede.ui.overlay_window",
        "--hidden-import=eyede.ui.debug_widget",
        "--hidden-import=eyede.ui.calibration_ui",
        "--hidden-import=eyede.ui.icon_manager",
        "--hidden-import=eyede.actions.code_injector",
        "--hidden-import=eyede.actions.menu_trees",
        "--hidden-import=eyede.actions.context_reader",
        "--hidden-import=eyede.actions.ai_predictor",
        "--hidden-import=eyede.actions.language_support",
        "--hidden-import=eyede.core.websocket_bridge",
        "--hidden-import=websockets",
        "--hidden-import=websockets.asyncio",
        "--hidden-import=websockets.asyncio.server",
        "--hidden-import=pynput.keyboard._win32",
        "--hidden-import=pynput.mouse._win32",
        "--onedir",
        MAIN_PY,
    ]

    print("[INFO] Running PyInstaller command:")
    print(" ".join(cmd))
    print("-" * 60)

    result = subprocess.run(cmd, cwd=ROOT_DIR)
    if result.returncode != 0:
        print(f"[ERROR] PyInstaller failed with exit code {result.returncode}")
        return False

    dist_dir = os.path.join(ROOT_DIR, "dist", "IDEye")
    exe_path = os.path.join(dist_dir, "IDEye.exe")
    print("-" * 60)
    if os.path.exists(exe_path):
        print(f"[SUCCESS] Native desktop executable generated at:\n  {exe_path}")

        # Also copy calibration profile if exists
        profile_src = os.path.join(ROOT_DIR, "calibration_profile.json")
        if os.path.exists(profile_src):
            shutil.copy2(profile_src, dist_dir)
            print(f"[INFO] Copied calibration_profile.json to {dist_dir}")

        return True
    else:
        print(f"[ERROR] Expected executable not found at {exe_path}")
        return False

if __name__ == "__main__":
    success = build()
    sys.exit(0 if success else 1)
