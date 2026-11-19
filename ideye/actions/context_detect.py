"""Cursor-position syntactic context detection."""

import ast
import os
import re
import time
import bisect
from typing import Optional, List, Set, Tuple, Dict, Any

try:
    import ideye.config as config
except ImportError:
    import config

try:
    from ideye.actions.language_support import (
        LANG_PYTHON,
        LANG_TYPESCRIPT,
        LANG_RUST,
        LANG_CPP,
        LANG_GO,
        SUPPORTED_LANGUAGES,
        LANGUAGE_EXTENSIONS,
        LANGUAGE_KEYWORDS,
        detect_language_from_path,
        detect_language_from_id,
        normalize_language,
        get_language_display_name,
        get_language_badge,
    )
except ImportError:
    from actions.language_support import (
        LANG_PYTHON,
        LANG_TYPESCRIPT,
        LANG_RUST,
        LANG_CPP,
        LANG_GO,
        SUPPORTED_LANGUAGES,
        LANGUAGE_EXTENSIONS,
        LANGUAGE_KEYWORDS,
        detect_language_from_path,
        detect_language_from_id,
        normalize_language,
        get_language_display_name,
        get_language_badge,
    )

# Python reserved keywords and internal names to filter out from user symbol lists
PYTHON_KEYWORDS: Set[str] = LANGUAGE_KEYWORDS.get(LANG_PYTHON, {
    "False", "None", "True", "and", "as", "assert", "async", "await", "break",
    "class", "continue", "def", "del", "elif", "else", "except", "finally",
    "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
    "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
    "self", "cls",
})

from ideye.actions.context_types import *  # noqa: F401,F403


def detect_syntactic_context(
    file_path: Optional[str] = None,
    source_code: Optional[str] = None,
    language: Optional[str] = None,
) -> SyntacticContext:
    """
    Detects the active syntactic construct from the file path or raw source code.
    Multi-language support for Python, TypeScript/JS, Rust, C++, and Go.
    Robust against SyntaxError and incomplete lines being typed.

    Contexts detected:
    - FUNCTION_SIGNATURE: writing function header
    - TRY_BLOCK: inside try / catch / match / error check
    - CLASS_BODY: inside class, struct, impl, or interface
    - IF_BLOCK: inside if / elif / else
    - LOOP_BLOCK: inside for / while / loop
    - WITH_BLOCK: inside with
    - GENERAL: default context when no specific construct is active
    """
    target_lang = normalize_language(language or (detect_language_from_path(file_path) if file_path else LANG_PYTHON))

    content = ""
    if source_code is not None:
        content = source_code
    elif file_path:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except (FileNotFoundError, PermissionError, OSError):
            return SyntacticContext(CONTEXT_GENERAL, line="", indent=0)
        except Exception:
            return SyntacticContext(CONTEXT_GENERAL, line="", indent=0)
    else:
        from ideye.actions.context_reader import ContextReader
        reader = ContextReader()
        content = reader.read_file_content()

    if not content or not content.strip():
        return SyntacticContext(CONTEXT_GENERAL, line="", indent=0)

    lines = content.splitlines()
    if not lines:
        return SyntacticContext(CONTEXT_GENERAL, line="", indent=0)

    comment_pattern = r'#.*$' if target_lang == LANG_PYTHON else r'//.*$'

    # Find the last non-empty line (ignoring trailing comments)
    last_non_empty_idx = -1
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip()
        if stripped:
            if target_lang == LANG_PYTHON and not stripped.startswith("#"):
                last_non_empty_idx = i
                break
            elif target_lang != LANG_PYTHON and not stripped.startswith("//") and not stripped.startswith("/*") and not stripped.startswith("*"):
                last_non_empty_idx = i
                break

    if last_non_empty_idx == -1:
        return SyntacticContext(CONTEXT_GENERAL, line="", indent=0)

    last_line = lines[last_non_empty_idx]
    stripped_last = last_line.strip()
    last_indent = len(last_line) - len(last_line.lstrip())

    clean_last = re.sub(comment_pattern, '', last_line).strip()
    if target_lang != LANG_PYTHON:
        clean_last = re.sub(r'/\*.*?\*/', '', clean_last).strip()
    clean_last_no_str = re.sub(r'(["\'])(?:(?=(\\?))\2.)*?\1', '', clean_last)

    # -------------------------------------------------------------------------
    # MULTI-LANGUAGE SYNTACTIC CHECKS FOR NON-PYTHON LANGUAGES
    # -------------------------------------------------------------------------
    if target_lang == LANG_TYPESCRIPT:
        if re.search(r'^\s*(?:export\s+)?(?:async\s+)?function\b', clean_last) or \
           re.search(r'^\s*(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?\([^)]*$', clean_last) or \
           re.search(r'^\s*constructor\s*\(', clean_last):
            return SyntacticContext(CONTEXT_FUNCTION_SIGNATURE, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*try\b', clean_last) or re.search(r'^\s*(?:catch|finally)\b', clean_last):
            return SyntacticContext(CONTEXT_TRY_BLOCK, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*(?:export\s+)?(?:abstract\s+)?(?:class|interface|type)\b', clean_last):
            return SyntacticContext(CONTEXT_CLASS_BODY, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*(?:if|else\s+if)\b', clean_last):
            return SyntacticContext(CONTEXT_IF_BLOCK, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*(?:for|while|do)\b', clean_last):
            return SyntacticContext(CONTEXT_LOOP_BLOCK, line=stripped_last, indent=last_indent)

        # Enclosing brace block scan
        for prev_idx in range(last_non_empty_idx - 1, max(-1, last_non_empty_idx - 25), -1):
            p_line = re.sub(comment_pattern, '', lines[prev_idx]).strip()
            if not p_line:
                continue
            net_braces = sum(lines[k].count('{') - lines[k].count('}') for k in range(prev_idx, last_non_empty_idx + 1))
            if net_braces > 0:
                if re.search(r'^\s*try\b', p_line) or re.search(r'^\s*(?:catch|finally)\b', p_line):
                    return SyntacticContext(CONTEXT_TRY_BLOCK, line=p_line, indent=last_indent)
                if re.search(r'^\s*(?:export\s+)?(?:abstract\s+)?(?:class|interface|type)\b', p_line):
                    return SyntacticContext(CONTEXT_CLASS_BODY, line=p_line, indent=last_indent)
                if re.search(r'^\s*(?:if|else\s+if)\b', p_line):
                    return SyntacticContext(CONTEXT_IF_BLOCK, line=p_line, indent=last_indent)
                if re.search(r'^\s*(?:for|while|do)\b', p_line):
                    return SyntacticContext(CONTEXT_LOOP_BLOCK, line=p_line, indent=last_indent)
                break
        return SyntacticContext(CONTEXT_GENERAL, line=stripped_last, indent=last_indent)

    elif target_lang == LANG_RUST:
        if re.search(r'^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\b', clean_last):
            return SyntacticContext(CONTEXT_FUNCTION_SIGNATURE, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*match\b', clean_last):
            return SyntacticContext(CONTEXT_TRY_BLOCK, line=stripped_last, indent=last_indent, details={"type": "match"})
        if re.search(r'^\s*(?:pub(?:\([^)]*\))?\s+)?(?:impl|struct|enum|trait)\b', clean_last):
            return SyntacticContext(CONTEXT_CLASS_BODY, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*(?:if|else\s+if)\b', clean_last):
            return SyntacticContext(CONTEXT_IF_BLOCK, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*(?:for|while|loop)\b', clean_last):
            return SyntacticContext(CONTEXT_LOOP_BLOCK, line=stripped_last, indent=last_indent)

        # Enclosing brace block scan
        for prev_idx in range(last_non_empty_idx - 1, max(-1, last_non_empty_idx - 25), -1):
            p_line = re.sub(comment_pattern, '', lines[prev_idx]).strip()
            if not p_line:
                continue
            net_braces = sum(lines[k].count('{') - lines[k].count('}') for k in range(prev_idx, last_non_empty_idx + 1))
            if net_braces > 0:
                if re.search(r'^\s*match\b', p_line):
                    return SyntacticContext(CONTEXT_TRY_BLOCK, line=p_line, indent=last_indent, details={"type": "match"})
                if re.search(r'^\s*(?:pub(?:\([^)]*\))?\s+)?(?:impl|struct|enum|trait)\b', p_line):
                    return SyntacticContext(CONTEXT_CLASS_BODY, line=p_line, indent=last_indent)
                if re.search(r'^\s*(?:if|else\s+if)\b', p_line):
                    return SyntacticContext(CONTEXT_IF_BLOCK, line=p_line, indent=last_indent)
                if re.search(r'^\s*(?:for|while|loop)\b', p_line):
                    return SyntacticContext(CONTEXT_LOOP_BLOCK, line=p_line, indent=last_indent)
                break
        return SyntacticContext(CONTEXT_GENERAL, line=stripped_last, indent=last_indent)

    elif target_lang == LANG_CPP:
        if re.search(r'^\s*(?:(?:void|int|bool|auto|double|float|size_t|char|std::string)\s+)?\w+(?:::w+)?\s*\([^)]*$', clean_last):
            return SyntacticContext(CONTEXT_FUNCTION_SIGNATURE, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*try\b', clean_last) or re.search(r'^\s*catch\b', clean_last):
            return SyntacticContext(CONTEXT_TRY_BLOCK, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*(?:class|struct|namespace)\b', clean_last):
            return SyntacticContext(CONTEXT_CLASS_BODY, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*(?:if|else\s+if)\b', clean_last):
            return SyntacticContext(CONTEXT_IF_BLOCK, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*(?:for|while|do)\b', clean_last):
            return SyntacticContext(CONTEXT_LOOP_BLOCK, line=stripped_last, indent=last_indent)

        # Enclosing brace block scan
        for prev_idx in range(last_non_empty_idx - 1, max(-1, last_non_empty_idx - 25), -1):
            p_line = re.sub(comment_pattern, '', lines[prev_idx]).strip()
            if not p_line:
                continue
            net_braces = sum(lines[k].count('{') - lines[k].count('}') for k in range(prev_idx, last_non_empty_idx + 1))
            if net_braces > 0:
                if re.search(r'^\s*try\b', p_line) or re.search(r'^\s*catch\b', p_line):
                    return SyntacticContext(CONTEXT_TRY_BLOCK, line=p_line, indent=last_indent)
                if re.search(r'^\s*(?:class|struct|namespace)\b', p_line):
                    return SyntacticContext(CONTEXT_CLASS_BODY, line=p_line, indent=last_indent)
                if re.search(r'^\s*(?:if|else\s+if)\b', p_line):
                    return SyntacticContext(CONTEXT_IF_BLOCK, line=p_line, indent=last_indent)
                if re.search(r'^\s*(?:for|while|do)\b', p_line):
                    return SyntacticContext(CONTEXT_LOOP_BLOCK, line=p_line, indent=last_indent)
                break
        return SyntacticContext(CONTEXT_GENERAL, line=stripped_last, indent=last_indent)

    elif target_lang == LANG_GO:
        if re.search(r'^\s*func\b', clean_last):
            return SyntacticContext(CONTEXT_FUNCTION_SIGNATURE, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*if\s+err\s*!=\s*nil\b', clean_last):
            return SyntacticContext(CONTEXT_TRY_BLOCK, line=stripped_last, indent=last_indent, details={"type": "err_check"})
        if re.search(r'^\s*type\s+\w+\s+(?:struct|interface)\b', clean_last):
            return SyntacticContext(CONTEXT_CLASS_BODY, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*(?:if|else\s+if)\b', clean_last):
            return SyntacticContext(CONTEXT_IF_BLOCK, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*for\b', clean_last):
            return SyntacticContext(CONTEXT_LOOP_BLOCK, line=stripped_last, indent=last_indent)

        # Enclosing brace block scan
        for prev_idx in range(last_non_empty_idx - 1, max(-1, last_non_empty_idx - 25), -1):
            p_line = re.sub(comment_pattern, '', lines[prev_idx]).strip()
            if not p_line:
                continue
            net_braces = sum(lines[k].count('{') - lines[k].count('}') for k in range(prev_idx, last_non_empty_idx + 1))
            if net_braces > 0:
                if re.search(r'^\s*if\s+err\s*!=\s*nil\b', p_line):
                    return SyntacticContext(CONTEXT_TRY_BLOCK, line=p_line, indent=last_indent, details={"type": "err_check"})
                if re.search(r'^\s*type\s+\w+\s+(?:struct|interface)\b', p_line):
                    return SyntacticContext(CONTEXT_CLASS_BODY, line=p_line, indent=last_indent)
                if re.search(r'^\s*(?:if|else\s+if)\b', p_line):
                    return SyntacticContext(CONTEXT_IF_BLOCK, line=p_line, indent=last_indent)
                if re.search(r'^\s*for\b', p_line):
                    return SyntacticContext(CONTEXT_LOOP_BLOCK, line=p_line, indent=last_indent)
                break
        return SyntacticContext(CONTEXT_GENERAL, line=stripped_last, indent=last_indent)

    # -------------------------------------------------------------------------
    # PYTHON SYNTACTIC CHECKS
    # -------------------------------------------------------------------------
    # 1. Direct active line checks (user is actively typing a construct starter)
    # Exclude standard entrypoint idioms (if __name__ == "__main__":)
    if re.search(r'^\s*if\s*\(?\s*__name__\s*==\s*["\']__main__["\']', last_line):
        return SyntacticContext(CONTEXT_GENERAL, line=stripped_last, indent=last_indent)

    # IF_BLOCK: writing if or elif condition
    if re.search(r'^\s*(?:if|elif)\b', clean_last):
        return SyntacticContext(
            CONTEXT_IF_BLOCK,
            line=stripped_last,
            indent=last_indent,
            details={"type": "if" if "if " in clean_last else "elif"},
        )

    # LOOP_BLOCK: writing for or while loop header
    if re.search(r'^\s*(?:for|while)\b', clean_last):
        return SyntacticContext(
            CONTEXT_LOOP_BLOCK,
            line=stripped_last,
            indent=last_indent,
            details={"type": "for" if "for " in clean_last else "while"},
        )

    # WITH_BLOCK: writing with statement
    if re.search(r'^\s*(?:async\s+)?with\b', clean_last):
        return SyntacticContext(
            CONTEXT_WITH_BLOCK,
            line=stripped_last,
            indent=last_indent,
            details={"type": "with"},
        )

    # TRY_BLOCK: try / try: or except or finally
    if re.search(r'^\s*try\b', clean_last) or re.search(r'^\s*(?:except\b|finally\b)', clean_last):
        return SyntacticContext(
            CONTEXT_TRY_BLOCK,
            line=stripped_last,
            indent=last_indent,
            details={"type": "try_header"},
        )

    # CLASS_BODY: class definition header
    if re.search(r'^\s*class\b', clean_last):
        return SyntacticContext(
            CONTEXT_CLASS_BODY,
            line=stripped_last,
            indent=last_indent,
            details={"type": "class_header"},
        )

    # FUNCTION_SIGNATURE (single-line header being actively typed):
    # e.g. def foo( or async def foo(a, or def foo
    def_match = re.search(r'^\s*(?:async\s+)?def\s+([a-zA-Z_]\w*)?\s*(?:\(.*)?$', clean_last_no_str)
    if def_match:
        # Check if signature was closed on this very line
        p_count = clean_last_no_str.count('(') - clean_last_no_str.count(')')
        has_colon = clean_last.rstrip().endswith(":")
        if p_count > 0 or not has_colon:
            return SyntacticContext(
                CONTEXT_FUNCTION_SIGNATURE,
                line=stripped_last,
                indent=last_indent,
                details={"signature": stripped_last},
            )

    # 2. Check for Multiline FUNCTION_SIGNATURE:
    # If the user is typing arguments across multiple lines:
    # def foo(
    #     arg1: int,
    #     arg2: str,
    # Look backwards for an unclosed def header without any intervening statements.
    statement_keywords = {
        "return", "pass", "yield", "raise", "import", "from", "break",
        "continue", "if", "elif", "else", "while", "for", "try", "except",
        "finally", "with", "class"
    }

    nearest_def_idx = -1
    multiline_def_line = ""
    multiline_def_indent = 0

    for idx in range(last_non_empty_idx - 1, max(-1, last_non_empty_idx - 30), -1):
        cur_l = lines[idx]
        c_l = re.sub(r'#.*$', '', cur_l).strip()
        if not c_l:
            continue

        first_token = c_l.split()[0] if c_l.split() else ""
        if first_token in statement_keywords:
            break

        if re.search(r'^\s*(?:async\s+)?def\b', c_l):
            nearest_def_idx = idx
            multiline_def_line = c_l
            multiline_def_indent = len(cur_l) - len(cur_l.lstrip())
            break

    if nearest_def_idx != -1:
        parens = 0
        sig_closed = False
        saw_statement = False

        for idx in range(nearest_def_idx, last_non_empty_idx + 1):
            cur_l = lines[idx]
            c_l = re.sub(r'#.*$', '', cur_l).strip()
            if not c_l:
                continue
            c_l_no_str = re.sub(r'(["\'])(?:(?=(\\?))\2.)*?\1', '', c_l)
            c_indent = len(cur_l) - len(cur_l.lstrip())

            if idx > nearest_def_idx and c_indent <= multiline_def_indent:
                saw_statement = True
                break

            first_w = c_l.split()[0] if c_l.split() else ""
            if idx > nearest_def_idx and first_w in statement_keywords:
                saw_statement = True
                break

            parens += c_l_no_str.count('(') - c_l_no_str.count(')')

            if parens <= 0 and c_l.rstrip().endswith(":"):
                sig_closed = True
                if idx < last_non_empty_idx:
                    break

        if not sig_closed and not saw_statement and (parens > 0 or not lines[last_non_empty_idx].rstrip().endswith(":")):
            return SyntacticContext(
                CONTEXT_FUNCTION_SIGNATURE,
                line=multiline_def_line,
                indent=last_indent,
                details={"signature": multiline_def_line},
            )

    # 3. Indentation Stack Analysis: determine the innermost enclosing block
    stack: List[Tuple[str, int, str]] = []  # (block_type, indent, line)

    for i in range(0, last_non_empty_idx + 1):
        line_str = lines[i]
        clean_line = re.sub(r'#.*$', '', line_str).rstrip()
        s_line = clean_line.strip()
        if not s_line:
            continue

        l_indent = len(clean_line) - len(clean_line.lstrip())

        # Pop any blocks that have closed (their indentation is >= current line's indentation)
        is_continuation = bool(re.search(r'^\s*(?:elif|else|except|finally)\b', clean_line))
        while stack and (stack[-1][1] > l_indent or (stack[-1][1] == l_indent and not is_continuation)):
            stack.pop()

        # Check for block starters
        if re.search(r'^\s*try\s*:\s*$', clean_line):
            stack.append((CONTEXT_TRY_BLOCK, l_indent, s_line))
        elif re.search(r'^\s*except\b', clean_line):
            if stack and stack[-1][0] == CONTEXT_TRY_BLOCK and stack[-1][1] == l_indent:
                stack.pop()
            stack.append((CONTEXT_TRY_BLOCK, l_indent, s_line))
        elif re.search(r'^\s*finally\s*:\s*$', clean_line):
            if stack and stack[-1][0] == CONTEXT_TRY_BLOCK and stack[-1][1] == l_indent:
                stack.pop()
            stack.append((CONTEXT_TRY_BLOCK, l_indent, s_line))
        elif re.search(r'^\s*class\b', clean_line):
            stack.append((CONTEXT_CLASS_BODY, l_indent, s_line))
        elif re.search(r'^\s*(?:async\s+)?def\b', clean_line):
            stack.append(("DEF_BODY", l_indent, s_line))
        elif re.search(r'^\s*(?:if|elif)\b', clean_line):
            if re.search(r'^\s*if\s*\(?\s*__name__\s*==\s*["\']__main__["\']', clean_line):
                stack.append(("MAIN_BLOCK", l_indent, s_line))
            else:
                if is_continuation and stack and stack[-1][0] == CONTEXT_IF_BLOCK and stack[-1][1] == l_indent:
                    stack.pop()
                stack.append((CONTEXT_IF_BLOCK, l_indent, s_line))
        elif re.search(r'^\s*else\s*:\s*$', clean_line):
            prev_type = stack[-1][0] if stack else CONTEXT_IF_BLOCK
            if stack and stack[-1][1] == l_indent:
                stack.pop()
            stack.append((prev_type, l_indent, s_line))
        elif re.search(r'^\s*(?:for|while)\b', clean_line):
            stack.append((CONTEXT_LOOP_BLOCK, l_indent, s_line))
        elif re.search(r'^\s*(?:async\s+)?with\b', clean_line):
            stack.append((CONTEXT_WITH_BLOCK, l_indent, s_line))

    # Evaluate stack for innermost enclosing block
    if stack:
        innermost_type, innermost_indent, innermost_line = stack[-1]
        if innermost_type not in ("DEF_BODY", "MAIN_BLOCK"):
            return SyntacticContext(
                innermost_type,
                line=innermost_line,
                indent=innermost_indent,
                details={"enclosing": innermost_type},
            )

    # 4. AST Validation fallback (if code happens to be valid Python)
    try:
        tree = ast.parse(content)
        target_lineno = last_non_empty_idx + 1
        candidate_nodes = []
        for node in ast.walk(tree):
            if isinstance(node, (
                ast.Try, ast.ExceptHandler, ast.For, ast.AsyncFor,
                ast.While, ast.If, ast.With, ast.AsyncWith, ast.ClassDef,
                ast.FunctionDef, ast.AsyncFunctionDef,
            )):
                if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                    if node.lineno <= target_lineno <= node.end_lineno:
                        span = node.end_lineno - node.lineno
                        candidate_nodes.append((span, node.lineno, node))

        if candidate_nodes:
            candidate_nodes.sort(key=lambda x: (x[0], -x[1]))
            innermost_ast = candidate_nodes[0][2]

            if isinstance(innermost_ast, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return SyntacticContext(CONTEXT_GENERAL, line=stripped_last, indent=last_indent)
            elif isinstance(innermost_ast, (ast.Try, ast.ExceptHandler)):
                return SyntacticContext(CONTEXT_TRY_BLOCK, line=stripped_last, indent=last_indent)
            elif isinstance(innermost_ast, (ast.For, ast.AsyncFor, ast.While)):
                return SyntacticContext(CONTEXT_LOOP_BLOCK, line=stripped_last, indent=last_indent)
            elif isinstance(innermost_ast, ast.If):
                is_main_check = False
                if isinstance(innermost_ast.test, ast.Compare):
                    left = innermost_ast.test.left
                    if isinstance(left, ast.Name) and left.id == "__name__":
                        is_main_check = True
                    for comp in innermost_ast.test.comparators:
                        if isinstance(comp, ast.Constant) and comp.value == "__main__":
                            is_main_check = True
                if not is_main_check:
                    return SyntacticContext(CONTEXT_IF_BLOCK, line=stripped_last, indent=last_indent)
            elif isinstance(innermost_ast, (ast.With, ast.AsyncWith)):
                return SyntacticContext(CONTEXT_WITH_BLOCK, line=stripped_last, indent=last_indent)
            elif isinstance(innermost_ast, ast.ClassDef):
                return SyntacticContext(CONTEXT_CLASS_BODY, line=stripped_last, indent=last_indent)
    except Exception:
        pass

    return SyntacticContext(CONTEXT_GENERAL, line=stripped_last, indent=last_indent)
