"""Syntactic context constants and result container."""

from typing import Any, Dict, List, Optional, Tuple


CONTEXT_FUNCTION_SIGNATURE: str = "FUNCTION_SIGNATURE"
CONTEXT_TRY_BLOCK: str = "TRY_BLOCK"
CONTEXT_CLASS_BODY: str = "CLASS_BODY"
CONTEXT_IF_BLOCK: str = "IF_BLOCK"
CONTEXT_LOOP_BLOCK: str = "LOOP_BLOCK"
CONTEXT_WITH_BLOCK: str = "WITH_BLOCK"
CONTEXT_GENERAL: str = "GENERAL"


class SyntacticContext(dict):
    """
    Represents the active syntactic context detected in the source code.
    Subclasses dict for 100% dictionary compatibility while supporting attribute access.
    """
    def __init__(
        self,
        context: str,
        line: str = "",
        indent: int = 0,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        data = {
            "context": context,
            "line": line,
            "indent": indent,
            "details": details or {},
        }
        data.update(kwargs)
        super().__init__(data)

    @property
    def context(self) -> str:
        return self["context"]

    @property
    def line(self) -> str:
        return self["line"]

    @property
    def indent(self) -> int:
        return self["indent"]

    @property
    def details(self) -> Dict[str, Any]:
        return self["details"]

    def to_dict(self) -> Dict[str, Any]:
        return dict(self)
