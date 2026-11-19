"""Shadow buffer for document-mode (Docs, Notion, Overleaf) typing context."""

import ast
import os
import re
import time
import bisect
from typing import Optional, List, Set, Tuple, Dict, Any


class DocumentShadowBuffer:
    """Bounded in-memory mirror of text written into Google Docs or web editors."""

    DOCUMENT_KEYWORDS = (
        "google docs",
        "documentos de google",
        "notion",
        "overleaf",
        "word",
        "onedrive",
        "sharepoint",
    )

    def __init__(self, max_chars: int = 12000) -> None:
        self.max_chars = max(500, int(max_chars))
        self.title: str = ""
        self.process: str = ""
        self._text: str = ""

    @classmethod
    def is_document_window(cls, title: str, process: str = "") -> bool:
        haystack = f"{title or ''} {process or ''}".lower()
        return any(keyword in haystack for keyword in cls.DOCUMENT_KEYWORDS)

    def update_title(self, title: str, process: str = "") -> None:
        self.title = str(title or "")[:200]
        self.process = str(process or "")[:120]

    def append(self, text: str) -> None:
        value = str(text or "")
        if not value:
            return
        combined = (self._text + value)[-self.max_chars :]
        self._text = combined

    def recent(self, max_chars: int = 4000) -> str:
        limit = max(1, min(self.max_chars, int(max_chars)))
        return self._text[-limit:]

    def clear(self) -> None:
        self._text = ""

    def snapshot(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "process": self.process,
            "text": self.recent(),
            "has_text": bool(self._text),
        }
