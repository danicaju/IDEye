# Contributing to IDEye

IDEye is an assistive tool for programming with eye tracking alone. Changes are welcome when they keep that goal intact: nothing should require a physical keyboard, a mouse, or voice.

## Set up

```bash
git clone https://github.com/danicaju/IDEye.git
cd IDEye
python -m venv venv
venv\Scripts\activate      # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
python main.py
```

You do not need a camera to develop. The tests use synthetic gaze, and the MCP server in `tools/ideye-mcp` can simulate a gaze stream.

## Run the tests

```bash
pytest -v
```

Tests run headless. If Qt complains about a display, set `QT_QPA_PLATFORM=offscreen`. Every test must pass before you open a pull request.

## Rules that tests enforce

- **Looking never triggers an irreversible action.** Activation needs a dwell, a deliberate mouth opening, or a wink. Reflexive blinks shorter than 150 ms are ignored.
- **The 3x3 grid keeps its shape.** Each menu node has exactly 9 items. Cell 5 (index 4) is Pause, and cell 7 (index 6) is Back in every submenu. `validate_menu_tree` must pass.
- **No stuck keys.** Wrap key and modifier presses in `try ... finally` and call `release_all_modifiers()`. To hold modifiers, use the `hold_modifiers()` context manager in `ideye/actions/code_injector.py`.
- **No emoji in the UI or the guide.** Use inline SVG or `IconManager`.
- **Vision never runs on the UI thread.** Keep the capture-to-cursor path under 35 ms.

## Visual rules for the HUD

One cyan accent, two corner radii (8 px and 14 px), and glow only on the focused cell. Use the constants in `ideye/ui/design_tokens.py` instead of new hex values or radii. Animations must be interruptible and must respect the `reduced_motion` setting.

## Keep the interactive guide in sync

When you add, change, or remove a feature, mode, gesture, shortcut, or UI behavior:

1. Update `ideye/core/guide_catalog.py`.
2. Regenerate the guide:

   ```bash
   python -c "from ideye.core.guide_catalog import generate_interactive_guide; print(generate_interactive_guide())"
   ```

3. Update `README.md` and `README.es.md` if the change is visible to users.

The guide must stay self-contained: inline CSS, SVG, and JavaScript, and no external resources.

## Commits and pull requests

- Make small, atomic commits with a conventional prefix: `feat:`, `fix:`, `docs:`, `test:`, `chore:`.
- Do not mix unrelated changes in one commit.
- Do not commit anything listed in `.gitignore` (`dist/`, `build/`, `node_modules/`, logs, caches).
- If a change alters what users see, rebuild with `python build_app.py` and check `dist/IDEye/IDEye.exe`.

## License

By contributing you agree that your work is released under the GNU Affero General Public License v3.0 (AGPL-3.0-or-later), the same license as the project.
