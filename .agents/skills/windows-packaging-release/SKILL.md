---
name: windows-packaging-release
description: >-
  Use this skill when building, packaging, or releasing IDEye on Windows. Covers PyInstaller onedir builds, asset bundling, desktop shortcuts, VSIX packaging, verification steps, and common Windows failures.
---

# Windows Packaging and Release for IDEye

IDEye ships in two parts: a PyInstaller desktop app and a VS Code extension. Build both after user-visible changes.

## 1. Desktop executable

Build from the repository root:

```powershell
python build_app.py
```

What the script does:

- Runs PyInstaller in `--onedir --windowed` mode with `main.py` as entrypoint.
- Bundles `ideye/assets` into `ideye/assets` inside the distribution.
- Collects MediaPipe data/binaries and metadata.
- Adds hidden imports for `ideye`, core engines, WebSocket bridge, `websockets.asyncio`, and Windows `pynput` backends.
- Copies `calibration_profile.json` into `dist/IDEye/` when present.

The wrapper prints `[SUCCESS]` and may still exit with code 1. Verify the artifact instead of trusting the wrapper code:

```powershell
Test-Path dist\IDEye\IDEye.exe
Test-Path dist\IDEye\_internal\ideye\assets\icons\mode.svg
Get-Item dist\IDEye\IDEye.exe | Select-Object FullName,Length,LastWriteTime
```

If an icon or SVG is missing, confirm it is under `ideye/assets/` before rebuilding. Do not add individual `--add-data` entries for every asset; the whole assets directory is bundled.

### Common failures

- `PermissionError` / access denied: the running `IDEye.exe` or antivirus is locking `dist/`. Close the app and rebuild.
- Missing module at runtime: add a hidden import in `build_app.py`, not just an import in code.
- Camera/MediaPipe crash only in the exe: check that `--collect-data` and `--collect-binaries` for MediaPipe are still present.
- Old assets in the exe: use `--clean` (already in the script) and confirm the timestamp on `dist/IDEye/IDEye.exe`.

## 2. Desktop shortcut

Update the shortcut after moving or rebuilding the executable:

```powershell
python create_desktop_shortcut.py
```

Verify the target in the shortcut properties. It should point to:

```text
C:\Users\danic\Desktop\IDEye\dist\IDEye\IDEye.exe
```

Working directory: `dist\IDEye`. Icon: `ideye.ico`.

## 3. VS Code extension (VSIX)

From `vscode-extension/`:

```powershell
npm install
npm run compile
npm run package
```

`npm run package` runs `vsce package --allow-missing-repository`. The artifact is:

```text
vscode-extension/ideye-vscode-bridge-<version>.vsix
```

Install it with:

```powershell
code --install-extension vscode-extension\ideye-vscode-bridge-0.5.0.vsix --force
```

Then reload the VS Code window. `dist/extension.js` is generated and gitignored; the `.vsix` is a release artifact and may be committed when the project tracks it.

## 4. Release verification

Before publishing:

```powershell
python -m pytest -q --tb=short 2>&1 | Select-Object -Last 15
git status --short
```

Checklist:

- Tests pass.
- `dist/` and `build/` are not staged (they are gitignored).
- Visible changes are present in the rebuilt exe.
- The desktop shortcut still targets the rebuilt exe.
- Version numbers match between `vscode-extension/package.json` and the VSIX filename.
- Commit and push to `origin/main` without waiting for an explicit request.

## 5. What not to do

- Do not commit `build/`, `dist/`, `*.spec`, `node_modules/`, or logs.
- Do not run PyInstaller from inside `dist/`; always run it from the repository root.
- Do not assume a successful print means a successful build; assert that the exe exists and is fresh.
- Do not add `websockets.legacy` hidden imports; the bridge uses `websockets.asyncio.server` with a compatibility fallback only.
