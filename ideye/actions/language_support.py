"""
IDEye - Multi-Language Syntax Support Module (Phase 5)
Provides multi-language syntax trees, language auto-detection, snippet mappings,
and language-specific syntactic context detectors for:
- Python (PYTHON)
- TypeScript / JavaScript (TYPESCRIPT)
- Rust (RUST)
- C / C++ (CPP)
- Go (GO)

Adheres strictly to the Golden Rules of Gaze Ergonomics:
1. Every grid layout has EXACTLY 9 cells (indices 0 to 8).
2. The Center Cell (Index 4) is ALWAYS Pause/Reading Mode.
3. In any submenu (Level >= 2), Index 6 is ALWAYS Volver Atrás.
4. Zero emojis, clean typography, and high-DPI vector icons.
"""

import os
from typing import Optional, List, Dict, Set, Tuple, Any

# Language Constants
LANG_PYTHON = "PYTHON"
LANG_TYPESCRIPT = "TYPESCRIPT"
LANG_RUST = "RUST"
LANG_CPP = "CPP"
LANG_GO = "GO"

SUPPORTED_LANGUAGES: List[str] = [
    LANG_PYTHON,
    LANG_TYPESCRIPT,
    LANG_RUST,
    LANG_CPP,
    LANG_GO,
]

LANGUAGE_DISPLAY_NAMES: Dict[str, str] = {
    LANG_PYTHON: "Python",
    LANG_TYPESCRIPT: "TypeScript / JS",
    LANG_RUST: "Rust",
    LANG_CPP: "C / C++",
    LANG_GO: "Go",
}

LANGUAGE_BADGES: Dict[str, str] = {
    LANG_PYTHON: "PY",
    LANG_TYPESCRIPT: "TS/JS",
    LANG_RUST: "RS",
    LANG_CPP: "C++",
    LANG_GO: "GO",
}

LANGUAGE_EXTENSIONS: Dict[str, str] = {
    ".py": LANG_PYTHON,
    ".ts": LANG_TYPESCRIPT,
    ".tsx": LANG_TYPESCRIPT,
    ".js": LANG_TYPESCRIPT,
    ".jsx": LANG_TYPESCRIPT,
    ".mjs": LANG_TYPESCRIPT,
    ".cjs": LANG_TYPESCRIPT,
    ".rs": LANG_RUST,
    ".cpp": LANG_CPP,
    ".cc": LANG_CPP,
    ".cxx": LANG_CPP,
    ".hpp": LANG_CPP,
    ".h": LANG_CPP,
    ".c": LANG_CPP,
    ".go": LANG_GO,
}

LANGUAGE_ID_MAP: Dict[str, str] = {
    "python": LANG_PYTHON,
    "typescript": LANG_TYPESCRIPT,
    "javascript": LANG_TYPESCRIPT,
    "typescriptreact": LANG_TYPESCRIPT,
    "javascriptreact": LANG_TYPESCRIPT,
    "rust": LANG_RUST,
    "cpp": LANG_CPP,
    "c": LANG_CPP,
    "cuda-cpp": LANG_CPP,
    "go": LANG_GO,
}

# Reserved keywords per language (used for variable/symbol extraction filtering)
LANGUAGE_KEYWORDS: Dict[str, Set[str]] = {
    LANG_PYTHON: {
        "False", "None", "True", "and", "as", "assert", "async", "await", "break",
        "class", "continue", "def", "del", "elif", "else", "except", "finally",
        "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
        "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
        "self", "cls", "print", "len", "range", "str", "int", "float", "list", "dict",
    },
    LANG_TYPESCRIPT: {
        "break", "case", "catch", "class", "const", "continue", "debugger", "default",
        "delete", "do", "else", "enum", "export", "extends", "false", "finally",
        "for", "function", "if", "import", "in", "instanceof", "new", "null", "return",
        "super", "switch", "this", "throw", "true", "try", "typeof", "var", "void",
        "while", "with", "yield", "let", "static", "yield", "await", "async",
        "interface", "type", "namespace", "declare", "abstract", "as", "any", "boolean",
        "number", "string", "symbol", "never", "unknown", "console", "log", "error",
    },
    LANG_RUST: {
        "as", "break", "const", "continue", "crate", "else", "enum", "extern", "false",
        "fn", "for", "if", "impl", "in", "let", "loop", "match", "mod", "move", "mut",
        "pub", "ref", "return", "self", "Self", "static", "struct", "super", "trait",
        "true", "type", "unsafe", "use", "where", "while", "async", "await", "dyn",
        "Option", "Some", "None", "Result", "Ok", "Err", "println", "eprintln", "vec",
    },
    LANG_CPP: {
        "alignas", "alignof", "and", "and_eq", "asm", "auto", "bitand", "bitor",
        "bool", "break", "case", "catch", "char", "char8_t", "char16_t", "char32_t",
        "class", "compl", "concept", "const", "consteval", "constexpr", "const_cast",
        "continue", "decltype", "default", "delete", "do", "double", "dynamic_cast",
        "else", "enum", "explicit", "export", "extern", "false", "float", "for", "friend",
        "goto", "if", "inline", "int", "long", "mutable", "namespace", "new", "noexcept",
        "not", "not_eq", "nullptr", "operator", "or", "or_eq", "private", "protected",
        "public", "register", "reinterpret_cast", "requires", "return", "short", "signed",
        "sizeof", "static", "static_assert", "static_cast", "struct", "switch", "template",
        "this", "thread_local", "throw", "true", "try", "typedef", "typeid", "typename",
        "union", "unsigned", "using", "virtual", "void", "volatile", "wchar_t", "while",
        "xor", "xor_eq", "std", "cout", "cin", "endl", "vector", "string",
    },
    LANG_GO: {
        "break", "default", "func", "interface", "select", "case", "defer", "go",
        "map", "struct", "chan", "else", "goto", "package", "switch", "const",
        "fallthrough", "if", "range", "type", "continue", "for", "import", "return",
        "var", "true", "false", "iota", "nil", "append", "cap", "close", "complex",
        "copy", "delete", "imag", "len", "make", "new", "panic", "print", "println",
        "real", "recover", "string", "int", "bool", "byte", "error", "fmt",
    },
}


def normalize_language(lang: Optional[str]) -> str:
    """Normalizes any language string to one of the supported language identifiers."""
    if not lang:
        return LANG_PYTHON
    cleaned = lang.strip().upper()
    if cleaned in SUPPORTED_LANGUAGES:
        return cleaned

    # Common aliases & abbreviations
    if cleaned in ("PY", "PYTHON3") or cleaned.startswith("PYTHON"):
        return LANG_PYTHON
    if cleaned in ("TS", "TYPESCRIPT", "JS", "JAVASCRIPT"):
        return LANG_TYPESCRIPT
    if cleaned in ("RS", "RUST"):
        return LANG_RUST
    if cleaned in ("CPP", "C++", "C", "CXX", "CC", "H", "HPP"):
        return LANG_CPP
    if cleaned in ("GO", "GOLANG"):
        return LANG_GO

    # Check lowercase alias map
    low = lang.strip().lower()
    if low in LANGUAGE_ID_MAP:
        return LANGUAGE_ID_MAP[low]
    # Check extension match
    if lang.startswith("."):
        return LANGUAGE_EXTENSIONS.get(lang.lower(), LANG_PYTHON)
    return LANG_PYTHON


def detect_language_from_path(file_path: Optional[str]) -> str:
    """Detects programming language from a file path extension."""
    if not file_path:
        return LANG_PYTHON
    _, ext = os.path.splitext(file_path)
    return LANGUAGE_EXTENSIONS.get(ext.lower(), LANG_PYTHON)


def detect_language_from_id(lang_id: Optional[str]) -> str:
    """Detects programming language from a VS Code language identifier."""
    if not lang_id:
        return LANG_PYTHON
    return LANGUAGE_ID_MAP.get(lang_id.strip().lower(), LANG_PYTHON)


def get_language_display_name(lang: str) -> str:
    """Returns human-readable display name for the language."""
    norm = normalize_language(lang)
    return LANGUAGE_DISPLAY_NAMES.get(norm, "Python")


def get_language_badge(lang: str) -> str:
    """Returns a short 2-5 letter badge for the language."""
    norm = normalize_language(lang)
    return LANGUAGE_BADGES.get(norm, "PY")


def get_language_keywords(lang: str) -> Set[str]:
    """Returns the set of reserved keywords for the specified language."""
    norm = normalize_language(lang)
    return LANGUAGE_KEYWORDS.get(norm, LANGUAGE_KEYWORDS[LANG_PYTHON])


# Alias for clarity with VS Code integration
detect_language_from_vscode_id = detect_language_from_id
