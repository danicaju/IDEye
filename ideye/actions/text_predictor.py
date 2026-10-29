"""
Local word prediction for IDEye's Writing mode.

The predictor is deliberately offline and dependency-free: it loads a compact
Spanish frequency list bundled with the app and filters it by the prefix typed
through the writing letter keyboard. No network or LLM is required for basic writing.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import unicodedata
from typing import Iterable, List, Sequence

DEFAULT_PREDICTIONS: Sequence[str] = (
    "que",
    "para",
    "con",
    "una",
    "como",
    "más",
)

# Documentation/technical vocabulary ranked before the general frequency list.
DOCUMENTATION_WORDS: Sequence[str] = (
    "documentación",
    "implementación",
    "configuración",
    "aplicación",
    "función",
    "método",
    "repositorio",
    "usuario",
    "usuarios",
    "código",
    "proyecto",
    "archivo",
    "interfaz",
    "comando",
    "servidor",
    "cliente",
    "prueba",
    "pruebas",
    "error",
    "errores",
    "datos",
    "sistema",
    "proceso",
    "resultado",
    "ejemplo",
    "explicación",
    "descripción",
    "referencia",
    "versión",
    "cambio",
    "cambios",
    "solución",
    "problema",
    "requisito",
    "objetivo",
    "seguridad",
    "rendimiento",
    "acceso",
    "permiso",
    "permisos",
    "entorno",
    "herramienta",
    "herramientas",
    "mensaje",
    "ventana",
    "botón",
    "pantalla",
    "calibración",
    "seguimiento",
    "mirada",
    "modelo",
    "modelos",
    "texto",
    "párrafo",
    "oración",
    "palabra",
    "palabras",
    "idioma",
    "traducción",
    "correo",
    "reunión",
    "nota",
    "notas",
    "informe",
    "guía",
    "manual",
    "instalación",
    "actualización",
    "desarrollo",
    "programación",
    "aplicaciones",
    "componente",
    "componentes",
    "módulo",
    "módulos",
    "librería",
    "librerías",
    "paquete",
    "paquetes",
    "clase",
    "clases",
    "objeto",
    "objetos",
    "variable",
    "variables",
    "valor",
    "valores",
    "entrada",
    "salida",
    "memoria",
    "proceso",
    "hilo",
    "hilos",
    "evento",
    "eventos",
    "tiempo",
    "latencia",
    "precisión",
    "velocidad",
    "usabilidad",
    "accesibilidad",
)

_FALLBACK_WORDS: Sequence[str] = (
    "de",
    "que",
    "no",
    "la",
    "el",
    "es",
    "en",
    "un",
    "por",
    "con",
    "para",
    "una",
    "como",
    "pero",
    "más",
    "sus",
    "le",
    "ya",
    "todo",
    "esta",
    "hacer",
    "puede",
    "tiene",
    "donde",
    "cuando",
    "porque",
    "sobre",
    "entre",
    "desde",
    "hasta",
    "también",
    "siempre",
    "nunca",
    "trabajo",
    "tiempo",
    "mundo",
    "persona",
    "palabra",
    "texto",
    "documento",
)


def _word_file() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "data" / "es_common_words.txt"


@lru_cache(maxsize=1)
def load_common_words() -> tuple[str, ...]:
    """Loads the bundled word list once, falling back to a small core list."""
    path = _word_file()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return tuple(_FALLBACK_WORDS)

    words: List[str] = []
    seen = set()
    for line in lines:
        word = line.strip().lower()
        if not word or word.startswith("#"):
            continue
        if not (2 <= len(word) <= 18):
            continue
        if not all(ch.isalpha() or ch in "áéíóúüñ" for ch in word):
            continue
        if word in seen:
            continue
        seen.add(word)
        words.append(word)
    return tuple(words) or tuple(_FALLBACK_WORDS)


def normalize_word(word: str) -> str:
    """Lowercases and strips accents so 'cancion' also matches 'canción'."""
    decomposed = unicodedata.normalize("NFD", word.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def extract_words(text: str) -> List[str]:
    """Extracts likely words from editor text for context-aware ranking."""
    current: List[str] = []
    words: List[str] = []
    for ch in text:
        if ch.isalpha() or ch in "áéíóúüñ":
            current.append(ch.lower())
        elif current:
            word = "".join(current)
            if len(word) >= 2:
                words.append(word)
            current = []
    if current:
        word = "".join(current)
        if len(word) >= 2:
            words.append(word)
    return words


def predict_words(
    prefix: str = "",
    limit: int = 6,
    context_words: Iterable[str] = (),
    extra_words: Iterable[str] = (),
) -> List[str]:
    """
    Returns up to `limit` words that start with `prefix`.

    Context words (from the active document) and user words are ranked before
    the general frequency list. Accents are ignored for matching but preserved
    in the returned spelling.
    """
    if limit <= 0:
        return []

    normalized_prefix = normalize_word(prefix.strip())
    if not normalized_prefix:
        return list(DEFAULT_PREDICTIONS[:limit])

    context = [w for w in context_words if w]
    extras = [w for w in extra_words if w]
    candidates: List[str] = []
    seen = set()

    def add(word: str) -> None:
        word = word.strip()
        if not word or word.lower() in seen:
            return
        if not normalize_word(word).startswith(normalized_prefix):
            return
        seen.add(word.lower())
        candidates.append(word)

    for word in context:
        add(word)
    for word in extras:
        add(word)

    # Short prefixes are usually everyday words; longer prefixes benefit from
    # documentation vocabulary (e.g. "doc" -> documentación, not doctor).
    if len(normalized_prefix) >= 3:
        sources = (DOCUMENTATION_WORDS, load_common_words())
    else:
        sources = (load_common_words(), DOCUMENTATION_WORDS)

    for source in sources:
        for word in source:
            add(word)
            if len(candidates) >= limit * 4:
                break
        if len(candidates) >= limit * 4:
            break

    # An exact prefix hit ("con") should always be the first suggestion.
    candidates.sort(key=lambda word: normalize_word(word) != normalized_prefix)
    return candidates[:limit]
