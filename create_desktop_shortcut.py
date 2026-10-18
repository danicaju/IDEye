"""
IDEye - Windows Desktop & Start Menu Shortcut Generator
Creates high-DPI desktop shortcuts with the official IDEye icon.
"""

import os
import sys
import subprocess

def create_shortcuts():
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    ico_path = os.path.join(repo_dir, "eyede.ico")
    main_py = os.path.join(repo_dir, "main.py")
    exe_path = os.path.join(repo_dir, "dist", "IDEye", "IDEye.exe")
    if os.path.exists(exe_path):
        target_path = exe_path
        target_args = ""
        work_dir = os.path.dirname(exe_path)
    else:
        pythonw_exe = sys.executable.replace("python.exe", "pythonw.exe")
        if not os.path.exists(pythonw_exe):
            pythonw_exe = sys.executable
        target_path = pythonw_exe
        target_args = f'"{main_py}"'
        work_dir = repo_dir

    desktop_dir = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
    old_lnk = os.path.join(desktop_dir, "EyeDE.lnk")
    if os.path.exists(old_lnk):
        try:
            os.remove(old_lnk)
            print(f"[CLEANUP] Removed legacy shortcut: {old_lnk}")
        except Exception as e:
            print(f"[WARN] Could not remove legacy shortcut: {e}")

    desktop_lnk = os.path.join(desktop_dir, "IDEye.lnk")

    ps_script = f'''
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("{desktop_lnk}")
    $Shortcut.TargetPath = "{target_path}"
    $Shortcut.Arguments = '{target_args}'
    $Shortcut.WorkingDirectory = "{work_dir}"
    $Shortcut.IconLocation = "{ico_path},0"
    $Shortcut.Description = "IDEye - Look-To-Code Assistive Eye Tracking IDE"
    $Shortcut.Save()
    '''

    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
    if res.returncode == 0 and os.path.exists(desktop_lnk):
        print(f"[SUCCESS] Desktop shortcut created at:\n  {desktop_lnk}")
        return True
    else:
        print(f"[ERROR] Failed to create shortcut: {res.stderr}")
        return False

if __name__ == "__main__":
    create_shortcuts()
