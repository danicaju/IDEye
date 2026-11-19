"""
IDEye - Asynchronous AI Code Predictor & Heuristic Engine (Phase 4)
QThread worker that queries Ollama or OpenAI-compatible LLM endpoints with
fail-safe heuristic fallback engine guaranteeing exactly 6 code suggestions.
"""

import json
import re
from typing import List, Optional, Any
import requests
from PyQt6.QtCore import QThread, pyqtSignal

try:
    import ideye.config as config
except ImportError:
    import config


from ideye.actions.ai_heuristics import (  # noqa: F401
    generate_document_predictions,
    generate_heuristic_predictions,
)
from ideye.actions.ai_parsing import clean_markdown_blocks, parse_llm_suggestions  # noqa: F401


class AIPredictorWorker(QThread):
    """
    Asynchronous QThread worker that requests code completions from Ollama or OpenAI-compatible
    APIs and falls back instantaneously to the Heuristic Engine upon timeout or network failure.
    Guarantees emitting exactly 6 suggestions via predictions_ready.
    Supports graceful termination via boolean flag self._running without terminate().
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
        document_context: bool = False,
        document_title: str = "",
        parent: Optional[QThread] = None,
    ):
        super().__init__(parent)
        self.context_text: str = context_text or ""
        self.local_symbols: List[str] = local_symbols or []
        self.context_reader: Optional[Any] = context_reader
        self.document_context: bool = bool(document_context)
        self.document_title: str = str(document_title or "")
        self.provider: str = (provider or getattr(config, "LLM_PROVIDER", "ollama")).lower()
        self.endpoint: str = endpoint or getattr(config, "LLM_ENDPOINT", "http://localhost:11434/api/generate")
        self.model: str = model or getattr(config, "LLM_MODEL", "codellama")
        self.timeout: float = float(timeout if timeout is not None else getattr(config, "LLM_TIMEOUT_SEC", 2.5))
        self.api_key: str = api_key or getattr(config, "LLM_API_KEY", "")
        self.temperature: float = float(temperature if temperature is not None else getattr(config, "LLM_TEMPERATURE", 0.2))
        self._running: bool = True

    def stop(self) -> None:
        """Gracefully halts worker thread without calling terminate()."""
        self._running = False

    def wait(self, timeout_ms: int = 2000) -> bool:
        """Waits for worker thread to terminate cleanly."""
        if not self.isRunning():
            return True
        return super().wait(timeout_ms)

    def run(self) -> None:
        """Executes LLM request or falls back cleanly to Heuristic Engine."""
        if not self._running:
            return

        # Read context on worker thread if not explicitly passed
        if self.context_reader is not None:
            if getattr(self.context_reader, "document_context_active", False):
                self.document_context = True
                doc = self.context_reader.get_document_context()
                self.document_title = self.document_title or doc.get("title", "")
                if not self.context_text:
                    self.context_text = doc.get("text", "")
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

        if not self._running:
            return

        self.status_changed.emit(f"Consultando {self.provider.upper()} ({self.model})...")

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

        if not self._running:
            return

        # If LLM didn't return 6 valid suggestions, switch to Heuristic Engine
        if len(suggestions) < 6:
            if error_msg:
                self.prediction_failed.emit(error_msg)
            self.status_changed.emit("Motor Heurístico Activo")
            if self.document_context:
                heuristic_suggestions = generate_document_predictions(self.context_text, self.document_title)
            else:
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

        if not self._running:
            return

        self.predictions_ready.emit(suggestions[:6])

    def _query_llm(self) -> List[str]:
        """Queries the configured LLM endpoint."""
        if self.document_context:
            prompt = (
                "You are a writing assistant for a disabled author using eye-tracking in a web document.\n"
                f"Document title: {self.document_title or 'untitled'}\n"
                f"Recent text:\n{self.context_text}\n"
                "Produce EXACTLY 6 suggestions: continue the sentence, develop the paragraph, "
                "summarize as bullets, write a conclusion/transition, add a formal connector, "
                "or reformat the selection. Return ONLY a JSON array of 6 strings.\n"
            )
        else:
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
