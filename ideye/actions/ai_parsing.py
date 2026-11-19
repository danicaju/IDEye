"""Parsers that turn raw LLM output into clean suggestion lists."""

import json
import re
from typing import List, Optional, Any

try:
    import ideye.config as config
except ImportError:
    import config


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

    def _remove_trailing_commas(s: str) -> str:
        return re.sub(r',\s*([\]\}])', r'\1', s)

    # 1. Try parsing JSON array or dict object directly
    for candidate_str in (cleaned, _remove_trailing_commas(cleaned)):
        try:
            data = json.loads(candidate_str)
            items = _extract_from_data(data)
            if items:
                return items[:6]
        except Exception:
            pass

    # 2. Try regex extraction of JSON object {.*} within surrounding text
    json_obj_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if json_obj_match:
        for raw_obj in (json_obj_match.group(0), _remove_trailing_commas(json_obj_match.group(0))):
            try:
                data = json.loads(raw_obj)
                items = _extract_from_data(data)
                if items:
                    return items[:6]
            except Exception:
                pass

    # 3. Try regex extraction of JSON array [...] within surrounding text
    json_arr_match = re.search(r'\[.*\]', cleaned, re.DOTALL)
    if json_arr_match:
        for raw_arr in (json_arr_match.group(0), _remove_trailing_commas(json_arr_match.group(0))):
            try:
                data = json.loads(raw_arr)
                items = _extract_from_data(data)
                if items:
                    return items[:6]
            except Exception:
                pass

    # 4. Balanced scanner: parse any valid JSON object or array blocks embedded in conversational text
    for open_ch, close_ch in (('[', ']'), ('{', '}')):
        depth = 0
        start = -1
        in_str = False
        esc = False
        for i, c in enumerate(cleaned):
            if c == '"' and not esc:
                in_str = not in_str
            elif not in_str:
                if c == open_ch:
                    if depth == 0:
                        start = i
                    depth += 1
                elif c == close_ch:
                    depth -= 1
                    if depth == 0 and start != -1:
                        chunk = cleaned[start : i + 1]
                        for c_text in (chunk, _remove_trailing_commas(chunk)):
                            try:
                                block_data = json.loads(c_text)
                                block_items = _extract_from_data(block_data)
                                if block_items and len(block_items) >= 2:
                                    return block_items[:6]
                            except Exception:
                                pass
                        start = -1
            esc = (c == '\\' and not esc) if in_str else False

    # 5. Fallback: Parse line by line (stripping bullet numbers: '1. ', '- ', etc.)
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

    # 6. If candidate looks like an unparsed JSON array or object string, rescue quoted elements
    if len(candidates) == 1 and (candidates[0].startswith("[") or candidates[0].startswith("{")):
        quoted = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', candidates[0])
        if quoted:
            rescued = [_clean_item(q) for q in quoted if _clean_item(q)]
            if rescued:
                return rescued[:6]

    return candidates
