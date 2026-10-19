"""
IDEye - Context Mode Strategy Package (Phase 6)
"""

from .base_mode import BaseMode, ModeTheme
from .mode_manager import (
    ModeManager,
    MODE_ORDER,
    MODE_CLASSES,
    MODE_ALIASES,
)
from .coding_mode import CodingMode, CodeMode, ProgrammingMode
from .writing_mode import WritingMode, DocMode, Writing
from .terminal_git_mode import TerminalGitMode, TerminalMode, GitMode, Terminal, TerminalGit
from .data_math_mode import DataMathMode, DataMode, MathMode, SqlMode, LatexMode, DataMath
from .ide_nav_mode import IdeNavMode, NavigationMode, NavMode, IdeNav, Navigation, ReadMode, IdeNavMode as NavigationReadMode

MODE_INSTANCES = [CodingMode(), WritingMode(), TerminalGitMode(), DataMathMode(), IdeNavMode()]

__all__ = [
    "BaseMode",
    "ModeTheme",
    "ModeManager",
    "CodingMode",
    "WritingMode",
    "TerminalGitMode",
    "DataMathMode",
    "IdeNavMode",
    "MODE_ORDER",
    "MODE_CLASSES",
]
