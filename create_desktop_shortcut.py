"""
IDEye - Windows Desktop & Start Menu Shortcut Generator
Creates high-DPI desktop shortcuts with the official IDEye icon.
"""

import os
import sys
import subprocess
import base64

def create_shortcuts():
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    ico_path = os.path.join(repo_dir, "ideye.ico")
    main_py = os.path.join(repo_dir, "main.py")
    exe_path = os.path.join(repo_dir, "dist", "IDEye", "IDEye.exe")
    if os.path.exists(exe_path):
        target_path = exe_path
        target_args = ""
        work_dir = os.path.dirname(exe_path)
        icon_location = f"{exe_path},0"
    else:
        pythonw_exe = sys.executable.replace("python.exe", "pythonw.exe")
        if not os.path.exists(pythonw_exe):
            pythonw_exe = sys.executable
        target_path = pythonw_exe
        target_args = f'"{main_py}"'
        work_dir = repo_dir
        icon_location = f"{ico_path},0"

    desktop_dir = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
    # Clean up existing shortcut so Windows Explorer detects creation event
    try:
        for entry in os.listdir(desktop_dir):
            if entry.casefold() == "ideye.lnk":
                old_lnk = os.path.join(desktop_dir, entry)
                os.remove(old_lnk)
                print(f"[CLEANUP] Removed existing shortcut: {old_lnk}")
    except Exception as e:
        print(f"[WARN] Could not remove existing shortcut: {e}")

    desktop_lnk = os.path.join(desktop_dir, "IDEye.lnk")

    ps_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{desktop_lnk}')
$Shortcut.TargetPath = '{target_path}'
$Shortcut.Arguments = '{target_args}'
$Shortcut.WorkingDirectory = '{work_dir}'
$Shortcut.IconLocation = '{icon_location}'
$Shortcut.Description = 'IDEye - Look-To-Code Assistive Eye Tracking IDE'
$Shortcut.Save()
"""

    encoded_cmd = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")

    subp_kwargs = {"capture_output": True, "text": True, "encoding": "cp1252", "errors": "replace"}
    if sys.platform == "win32":
        subp_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 1)
        si.wShowWindow = 0
        subp_kwargs["startupinfo"] = si
    res = subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", encoded_cmd], **subp_kwargs)
    if res.returncode == 0 and os.path.exists(desktop_lnk):
        print(f"[SUCCESS] Desktop shortcut created at:\n  {desktop_lnk}")
        try:
            import ctypes
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x1000, None, None)
        except Exception:
            pass
        return True
    else:
        print(f"[ERROR] Failed to create shortcut: {res.stderr}")
        return False

if __name__ == "__main__":
    create_shortcuts()
