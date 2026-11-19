"""Modularity guard: no source file may exceed 500 lines.

Scans ``ideye/``, ``vscode-extension/src/``, ``tools/`` and ``tests/`` for
``.py``, ``.ts``, ``.js`` and ``.mjs`` files. Large modules must be split into
cohesive submodules with a facade that re-exports the public API.
"""

import os
import unittest
from pathlib import Path

MAX_LINES = 500
ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ("ideye", "vscode-extension/src", "tools", "tests")
EXTENSIONS = {".py", ".ts", ".js", ".mjs"}
EXCLUDED_DIRS = {
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "out",
    "build",
    ".git",
}


def iter_source_files():
    for rel in SCAN_DIRS:
        base = ROOT / rel
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
            for name in filenames:
                path = Path(dirpath) / name
                if path.suffix in EXTENSIONS:
                    yield path


def count_lines(path: Path) -> int:
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return len(handle.read().splitlines())


class TestModularityLineLimit(unittest.TestCase):
    def test_scan_finds_source_files(self):
        self.assertGreater(len(list(iter_source_files())), 50)

    def test_no_file_exceeds_line_limit(self):
        offenders = []
        for path in iter_source_files():
            total = count_lines(path)
            if total > MAX_LINES:
                offenders.append(f"{path.relative_to(ROOT).as_posix()}: {total} lines")
        self.assertEqual(
            offenders,
            [],
            f"Files above {MAX_LINES} lines (split them behind a facade):\n"
            + "\n".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
