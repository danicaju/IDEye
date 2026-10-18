"""
EyeDE - Asynchronous AI Code Predictor & Heuristic Engine (Phase 4)
QThread worker that queries Ollama or OpenAI-compatible LLM endpoints with
fail-safe heuristic fallback engine guaranteeing exactly 6 code suggestions.
"""

import json
import re
from typing import List, Optional, Any
import requests
from PyQt6.QtCore import QThread, pyqtSignal

try:
    import eyede.config as config
except ImportError:
    import config


def generate_heuristic_predictions(
    context_text: str,
    local_symbols: Optional[List[str]] = None,
) -> List[str]:
    """
    Local heuristic fallback engine.
    Analyzes the last line and structure of recent code context and injects
    smart, context-relevant suggestions using actual local symbols.
    Guarantees returning EXACTLY 6 distinct, ready-to-use code suggestions.
    """
    distinct_syms: List[str] = []
    pool = [s for s in (local_symbols or []) if s and isinstance(s, str) and s.isidentifier()] + [
        "data", "result", "item", "i", "val", "x", "count", "res", "obj"
    ]
    for s in pool:
        if s not in distinct_syms:
            distinct_syms.append(s)
    v1, v2, v3, v4 = distinct_syms[0], distinct_syms[1], distinct_syms[2], distinct_syms[3]

    # Find the last non-empty line
    lines = [line.rstrip() for line in (context_text or "").splitlines() if line.strip()]
    last_line = lines[-1].strip() if lines else ""

    suggestions: List[str] = []

    # Heuristic 1: Function / Method definition
    if last_line.startswith("def "):
        suggestions = [
            f'"""Docstring explicativo."""',
            f"{v2} = None",
            f"if {v1}:",
            f"for {v3} in {v1}:",
            f"return {v2}",
            "pass",
        ]

    # Heuristic 2: Class definition
    elif last_line.startswith("class "):
        suggestions = [
            f"def __init__(self, {v1}):\n    self.{v1} = {v1}",
            f"def process(self):\n    return self.{v1}",
            f"def get_{v1}(self):\n    return self.{v1}",
            f"def __repr__(self):\n    return f'{v1}={{self.{v1}}}'",
            "pass",
            '"""Clase principal."""',
        ]

    # Heuristic 3: If / Elif statement
    elif last_line.startswith("if ") or last_line.startswith("elif "):
        suggestions = [
            f"{v2} = {v1}",
            f"print(f'{v1}: {{{v1}}}')",
            f"return {v1}",
            f"raise ValueError('Error con {v1}')",
            "return True",
            "pass",
        ]

    # Heuristic 4: For loop header
    elif last_line.startswith("for "):
        suggestions = [
            f"print({v3})",
            f"if {v3}:",
            f"{v2}.append({v3})",
            f"total += {v3}",
            f"{v2} = process({v3})",
            "continue",
        ]

    # Heuristic 5: While loop header
    elif last_line.startswith("while "):
        suggestions = [
            f"if not {v1}: break",
            f"{v4} += 1",
            f"print({v1})",
            f"{v2} = process({v1})",
            "break",
            "time.sleep(0.1)",
        ]

    # Heuristic 6: Try block
    elif last_line.startswith("try:"):
        suggestions = [
            f"{v2} = process({v1})",
            f"{v1}.load()",
            f"{v2} = {v1}.read()",
            f"connect_service({v1})",
            "pass",
            f"validate({v1})",
        ]

    # Heuristic 7: Except block
    elif last_line.startswith("except"):
        suggestions = [
            "print(f'Error: {e}')",
            "logger.error(str(e))",
            "return None",
            f"{v2} = None",
            "raise",
            "pass",
        ]

    # Heuristic 8: With context manager
    elif last_line.startswith("with "):
        suggestions = [
            "content = f.read()",
            "data = json.load(f)",
            f"f.write({v1})",
            "for line in f:",
            f"{v2} = f.readlines()",
            "pass",
        ]

    # Heuristic 9: Incomplete assignment (e.g. `x = ` or `total += `)
    elif re.search(r'[\+\-\*/]?=\s*$', last_line):
        suggestions = [
            f"{v1}",
            f"len({v1})",
            f"[{v3} for {v3} in {v1}]",
            f"{v1}.copy()",
            "[]",
            "{}",
        ]

    # Heuristic 10: Dot access (e.g. `data.` or `self.`)
    elif last_line.endswith("."):
        suggestions = [
            "append()",
            "get()",
            "items()",
            "split()",
            "strip()",
            "copy()",
        ]

    # Heuristic 11: Return statement
    elif last_line.startswith("return"):
        suggestions = [
            f"{v2}",
            f"{v1}",
            "True",
            "False",
            "None",
            "0",
        ]

    # General Fallback: Smart statements using actual local symbols
    if len(suggestions) < 6:
        defaults = [
            f"print({v1})",
            f"if {v1}:",
            f"for {v3} in {v1}:",
            f"{v2} = {v1}",
            f"return {v1}",
            f"self.{v1} = {v1}",
        ]
        for d in defaults:
            if d not in suggestions:
                suggestions.append(d)
            if len(suggestions) == 6:
                break

    # Guaranteed length 6
    while len(suggestions) < 6:
        suggestions.append("pass")

    return suggestions[:6]


def clean_markdown_blocks(raw_text: str) -> str:
    """Strips markdown code fences (```python, ```json, etc.) and surrounding text."""
    text = raw_text.strip()
    # 1. Enclosed entirely in outer code fences
    outer_match = re.search(r'^\s*```(?:python|json)?\s*([\s\S]*?)\s*```\s*$', text, re.IGNORECASE)
    if outer_match:
        return outer_match.group(1).strip()

    # 2. If raw text already starts with a JSON array bracket '[', do not strip internal elements
    if text.startswith("["):
        text = re.sub(r'^```[a-zA-Z]*\n?', '', text)
        text = re.sub(r'```$', '', text).strip()
        return text

    # 3. Commentary preceding code fence with code block
    fence_match = re.search(r'```(?:python|json)?\s*([\s\S]*?)\s*```', text, re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()

    # 4. Strip stray single fences
    text = re.sub(r'^```[a-zA-Z]*\n?', '', text)
    text = re.sub(r'```$', '', text).strip()
    return text


def parse_llm_suggestions(raw_text: str) -> List[str]:
    """
    Parses LLM response into a list of suggestions.
    Supports JSON arrays, object wrappers with list keys, bulleted lists, numbered lists, and line-delimited code.
    """
    cleaned = clean_markdown_blocks(raw_text)

    def _clean_item(val: Any) -> str:
        if isinstance(val, dict):
            for k in ("code", "suggestion", "text", "content", "snippet"):
                if k in val and isinstance(val[k], (str, int, float)):
                    val = val[k]
                    break
            else:
                val = next(iter(val.values()), "") if val else ""
        s = str(val).strip()
        s = s.rstrip(",;").strip()
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            s = s[1:-1].strip()
        s = re.sub(r'^`+|`+$', '', s).strip()
        s = s.rstrip(",;").strip()
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            s = s[1:-1].strip()
        return s

    def _extract_from_data(data: Any) -> Optional[List[str]]:
        if isinstance(data, list):
            items = [_clean_item(x) for x in data if _clean_item(x)]
            if items:
                return items
        elif isinstance(data, dict):
            for key in ("suggestions", "predictions", "completions", "choices", "items", "code"):
                if key in data and isinstance(data[key], list):
                    items = [_clean_item(x) for x in data[key] if _clean_item(x)]
                    if items:
                        return items
            for v in data.values():
                if isinstance(v, list):
                    items = [_clean_item(x) for x in v if _clean_item(x)]
                    if items:
                        return items
        return None

    # 1. Try parsing JSON array or dict object
    try:
        data = json.loads(cleaned)
        items = _extract_from_data(data)
        if items:
            return items[:6]
    except Exception:
        pass

    # 2. Try regex extraction of JSON array within text: [...]
    json_match = re.search(r'\[\s*(?:\{|"(?:\'|))[\s\S]*?(?:\}|"(?:\'|))\s*\]', cleaned)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            items = _extract_from_data(data)
            if items:
                return items[:6]
        except Exception:
            pass

    # 3. Fallback: Parse line by line (stripping bullet numbers: '1. ', '- ', etc.)
    lines = cleaned.splitlines()
    candidates = []
    has_numbered_or_bullet = any(re.match(r'^(?:\d+[\.\)]|[-*])\s*', l.strip()) for l in lines)
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if has_numbered_or_bullet:
            if not re.match(r'^(?:\d+[\.\)]|[-*])\s*', stripped):
                continue
        unprefixed = re.sub(r'^(?:\d+[\.\)]\s*|[-*]\s*)', '', stripped)
        unprefixed = _clean_item(unprefixed)
        if unprefixed:
            candidates.append(unprefixed)

    return candidates


class AIPredictorWorker(QThread):
    """
    Asynchronous QThread worker that requests code completions from Ollama or OpenAI-compatible
    APIs and falls back instantaneously to the Heuristic Engine upon timeout or network failure.
    Guarantees emitting exactly 6 suggestions via predictions_ready.
    """

    predictions_ready = pyqtSignal(list)  # List[str] of 6 items
    status_changed = pyqtSignal(str)
    prediction_failed = pyqtSignal(str)

    def __init__(
        self,
        context_text: str = "",
        local_symbols: Optional[List[str]] = None,
        provider: Optional[str] = None,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        api_key: Optional[str] = None,
        temperature: Optional[float] = None,
        context_reader: Optional[Any] = None,
        parent: Optional[QThread] = None,
    ):
        super().__init__(parent)
        self.context_text: str = context_text or ""
        self.local_symbols: List[str] = local_symbols or []
        self.context_reader: Optional[Any] = context_reader
        self.provider: str = (provider or getattr(config, "LLM_PROVIDER", "ollama")).lower()
        self.endpoint: str = endpoint or getattr(config, "LLM_ENDPOINT", "http://localhost:11434/api/generate")
        self.model: str = model or getattr(config, "LLM_MODEL", "codellama")
        self.timeout: float = float(timeout if timeout is not None else getattr(config, "LLM_TIMEOUT_SEC", 2.5))
        self.api_key: str = api_key or getattr(config, "LLM_API_KEY", "")
        self.temperature: float = float(temperature if temperature is not None else getattr(config, "LLM_TEMPERATURE", 0.2))

    def run(self) -> None:
        """Executes LLM request or falls back cleanly to Heuristic Engine."""
        # Read context on worker thread if not explicitly passed
        if self.context_reader is not None:
            if not self.context_text:
                try:
                    self.context_text = self.context_reader.get_recent_context(
                        getattr(config, "PREDICTOR_MAX_CONTEXT_LINES", 30)
                    )
                except Exception:
                    pass
            if not self.local_symbols:
                try:
                    self.local_symbols = self.context_reader.extract_local_symbols(
                        getattr(config, "MAX_LOCAL_SYMBOLS", 12)
                    )
                except Exception:
                    pass

        self.status_changed.emit(f"⏳ Consultando {self.provider.upper()} ({self.model})...")

        suggestions: List[str] = []
        error_msg: str = ""

        try:
            suggestions = self._query_llm()
        except requests.exceptions.Timeout:
            error_msg = f"Timeout ({self.timeout}s) agotado"
        except requests.exceptions.RequestException as e:
            error_msg = f"Fallo de red/API: {type(e).__name__}"
        except json.JSONDecodeError as e:
            error_msg = f"JSON corrupto: {str(e)}"
        except Exception as e:
            error_msg = f"Error: {str(e)}"

        # If LLM didn't return 6 valid suggestions, switch to Heuristic Engine
        if len(suggestions) < 6:
            if error_msg:
                self.prediction_failed.emit(error_msg)
            self.status_changed.emit("⚡ Motor Heurístico Activo")
            heuristic_suggestions = generate_heuristic_predictions(self.context_text, self.local_symbols)
            combined = []
            for s in suggestions:
                if s and s not in combined:
                    combined.append(s)
            for h in heuristic_suggestions:
                if h and h not in combined:
                    combined.append(h)
                if len(combined) == 6:
                    break
            suggestions = combined[:6]

        while len(suggestions) < 6:
            suggestions.append("pass")

        self.predictions_ready.emit(suggestions[:6])

    def _query_llm(self) -> List[str]:
        """Queries the configured LLM endpoint."""
        prompt = (
            "You are a Python code completion assistant for a disabled programmer using eye-tracking.\n"
            f"Variables/functions in scope: {', '.join(self.local_symbols) if self.local_symbols else 'none'}\n"
            f"Recent code context:\n```python\n{self.context_text}\n```\n"
            "Predict the EXACTLY 6 most useful next Python statements or code completions.\n"
            "Return ONLY a JSON array containing exactly 6 strings. No markdown fences, no explanations.\n"
            'Example: ["result = []", "for x in items:", "print(data)", "return total", "if not valid: break", "self.value = 0"]'
        )

        if self.provider == "ollama":
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                },
            }
            conn_timeout = min(1.0, self.timeout)
            resp = requests.post(self.endpoint, json=payload, timeout=(conn_timeout, self.timeout))
            resp.raise_for_status()
            data = resp.json()
            raw_response = data.get("response", "") if isinstance(data, dict) else str(data)
            return parse_llm_suggestions(raw_response)

        else:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a code completion engine. Return ONLY a JSON array of 6 Python code strings."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": self.temperature,
            }
            conn_timeout = min(1.0, self.timeout)
            resp = requests.post(self.endpoint, json=payload, headers=headers, timeout=(conn_timeout, self.timeout))
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict):
                choices = data.get("choices", [])
                if choices and isinstance(choices, list) and isinstance(choices[0], dict) and "message" in choices[0]:
                    content = choices[0]["message"].get("content", "")
                    return parse_llm_suggestions(content)
            return []
