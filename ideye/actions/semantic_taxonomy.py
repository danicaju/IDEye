"""Phase 12: deep semantic coding taxonomy and environment-aware mode trees.

The builders are pure and deterministic: they take the active language and
local symbols and return complete 3x3 ``MenuNode`` trees. The UI can rebuild a
tree at any time without restarting IDEye.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    from ideye.actions.menu_trees import (
        MenuAction,
        MenuNode,
        create_back_action,
        create_pause_action,
    )
except ImportError:  # pragma: no cover
    from actions.menu_trees import (  # type: ignore
        MenuAction,
        MenuNode,
        create_back_action,
        create_pause_action,
    )


CURSOR = "[[CURSOR]]"
SLOTS = (0, 1, 2, 3, 5, 7)
KEY_LABELS = ("1", "2", "3", "4", "6", "8")
ROOT_KEY_LABELS = {0: "1", 1: "2", 2: "3", 3: "4", 5: "6", 6: "7", 7: "8", 8: "9"}


def _slot_key(slot: int) -> str:
    return ROOT_KEY_LABELS.get(int(slot), str(int(slot) + 1))

CATEGORY_SPECS: Sequence[tuple[str, str, str, str]] = (
    ("SEM_COND", "CONDICIONALES Y RAMAS", "flow", "if"),
    ("SEM_LOOP", "BUCLES E ITERADORES", "loop", "for"),
    ("SEM_FUNC", "FUNCIONES Y CLASES", "function", "def"),
    ("SEM_VAR", "VARIABLES Y ESTRUCTURAS", "variables", "x"),
    ("SEM_ERR", "ERRORES, LOGS Y TESTS", "shield", "try"),
    ("SEM_IMPORT", "IMPORTS, E/S Y ASYNC", "terminal", "import"),
    ("SEM_OP", "OPERADORES Y EDICIÓN", "operators", "=="),
    ("SEM_AI", "SUGERENCIAS IA EN VIVO", "ai_spark", "ai"),
)


def normalize_taxonomy_language(language: Optional[str]) -> str:
    value = str(language or "python").strip().lower()
    aliases = {
        "py": "python",
        "python3": "python",
        "js": "javascript",
        "node": "javascript",
        "ts": "typescript",
        "c++": "cpp",
        "cplusplus": "cpp",
        "cs": "csharp",
        "c#": "csharp",
        "gd": "gdscript",
        "godot": "gdscript",
        "gml": "gdscript",
    }
    return aliases.get(value, value)


def _clean_symbols(symbols: Optional[Sequence[Any]]) -> List[str]:
    result: List[str] = []
    for item in symbols or ():
        value = item.get("name") if isinstance(item, dict) else item
        text = str(value or "").strip()
        if text and text.isidentifier() and text not in result:
            result.append(text)
    return result


def _singular(word: str) -> str:
    value = str(word or "item")
    if value.endswith("ies") and len(value) > 3:
        return value[:-3] + "y"
    if value.endswith("ses") and len(value) > 3:
        return value[:-2]
    if value.endswith("s") and len(value) > 1:
        return value[:-1]
    return "item"


def _pick_list(symbols: Sequence[str]) -> str:
    for name in symbols:
        lower = name.lower()
        if any(token in lower for token in ("list", "items", "users", "usuarios", "data", "rows", "records", "collection", "values")):
            return name
    for name in symbols:
        if name.endswith("s") and len(name) > 2:
            return name
    return "items"


def _pick_scalar(symbols: Sequence[str], fallback: str = "value") -> str:
    for name in symbols:
        if not name.endswith("s") and name not in {"self", "cls"}:
            return name
    return symbols[0] if symbols else fallback


def _action(action_id: str, label: str, text: str, icon: str = "function", hint: str = "") -> MenuAction:
    clean = str(text)
    offset = 0
    marker = clean.find(CURSOR)
    if marker >= 0:
        clean = clean.replace(CURSOR, "", 1)
        offset = max(0, len(clean) - marker)
    return MenuAction(
        id=action_id,
        label=label,
        hint=hint or label,
        action_type="SNIPPET",
        snippet=clean,
        cursor_offset_left=offset,
        icon=icon,
    )


def _lang_templates(lang: str, symbols: Sequence[str]) -> Dict[str, List[tuple[str, str, str]]]:
    items = _pick_list(symbols)
    item = _singular(items)
    var = _pick_scalar(symbols, "value")
    func = next((s for s in symbols if s.isidentifier()), "process")
    Type = "Item"
    if lang == "python":
        return {
            "SEM_COND": [
                ("if simple", f"if {var}:{CURSOR}", "flow"),
                ("if / else", f"if {var}:\n    pass\nelse:\n    pass{CURSOR}", "flow"),
                ("elif", f"elif {var}:{CURSOR}", "flow"),
                ("match / case", f"match {var}:\n    case _:\n        pass{CURSOR}", "flow"),
                ("ternario", f"{var} if {item} else None{CURSOR}", "operators"),
                ("guard clause", f"if not {var}:\n    return{CURSOR}", "flow"),
            ],
            "SEM_LOOP": [
                ("for rango", f"for i in range({items}):{CURSOR}", "loop"),
                ("for each", f"for {item} in {items}:{CURSOR}", "loop"),
                ("while", f"while {var}:{CURSOR}", "loop"),
                ("break / continue", f"break{CURSOR}", "loop"),
                ("comprensión", f"[{item} for {item} in {items}]{CURSOR}", "loop"),
                ("enumerate / zip", f"for i, {item} in enumerate({items}):{CURSOR}", "loop"),
            ],
            "SEM_FUNC": [
                ("def función", f"def {func}():{CURSOR}", "function"),
                ("async def", f"async def {func}():{CURSOR}", "function"),
                ("clase + init", f"class {Type}:\n    def __init__(self):{CURSOR}", "function"),
                ("property", f"@property\ndef {func}(self):{CURSOR}", "function"),
                ("return", f"return {var}{CURSOR}", "flow"),
                ("decorador / tipo", f"@staticmethod\ndef {func}() -> None:{CURSOR}", "function"),
            ],
            "SEM_VAR": [
                ("asignación", f"{var} = {item}{CURSOR}", "variables"),
                ("dict / mapa", f"{var} = {{{item!r}: {item!r}}}{CURSOR}", "variables"),
                ("lista / array", f"{var} = []{CURSOR}", "variables"),
                ("f-string", f'f"{{{var}}}"{CURSOR}', "variables"),
                ("desempaquetado", f"a, b = {items}{CURSOR}", "variables"),
                ("constante", f"CONSTANT = {var!r}{CURSOR}", "variables"),
            ],
            "SEM_ERR": [
                ("try / except", f"try:\n    pass\nexcept Exception as exc:{CURSOR}", "shield"),
                ("finally", f"finally:\n    pass{CURSOR}", "shield"),
                ("raise", f"raise ValueError({var!r}){CURSOR}", "shield"),
                ("assert", f"assert {var} is not None{CURSOR}", "shield"),
                ("log", f"print(f'{var}={{ {var} }}'){CURSOR}", "terminal"),
                ("test", f"def test_{func}():\n    assert {func}() is not None{CURSOR}", "test"),
            ],
            "SEM_IMPORT": [
                ("import", f"import {func}{CURSOR}", "terminal"),
                ("from import", f"from {func} import {var}{CURSOR}", "terminal"),
                ("archivo seguro", f"with open({var!r}, 'r', encoding='utf-8') as fh:\n    data = fh.read(){CURSOR}", "terminal"),
                ("async / await", f"async def {func}():\n    await {var}(){CURSOR}", "function"),
                ("JSON", f"import json\npayload = json.loads({var}){CURSOR}", "terminal"),
                ("petición", f"response = requests.get({var!r}, timeout=10){CURSOR}", "terminal"),
            ],
            "SEM_OP": [
                ("comparación", f"{var} == {item}{CURSOR}", "operators"),
                ("lógica", f"{var} and {item}{CURSOR}", "operators"),
                ("comentar", f"# {var}{CURSOR}", "operators"),
                ("indentar", f"    {var}{CURSOR}", "operators"),
                ("envolver paréntesis", f"({var}){CURSOR}", "operators"),
                ("lambda / flecha", f"lambda {item}: {item}{CURSOR}", "operators"),
            ],
        }
    if lang == "sql":
        return {
            "SEM_COND": [
                ("WHERE", f"WHERE {var} = {item}{CURSOR}", "flow"),
                ("AND / OR", f"WHERE {var} = {item} AND {item} IS NOT NULL{CURSOR}", "flow"),
                ("CASE", f"CASE WHEN {var} IS NULL THEN 0 ELSE 1 END{CURSOR}", "flow"),
                ("IF / ELSE", f"IF {var} IS NULL\nBEGIN\n    SELECT 1;\nEND{CURSOR}", "flow"),
                ("NULL check", f"WHERE {var} IS NULL{CURSOR}", "flow"),
                ("guard", f"WHERE {var} IS NOT NULL{CURSOR}", "flow"),
            ],
            "SEM_LOOP": [
                ("SELECT", f"SELECT * FROM {items}{CURSOR}", "loop"),
                ("JOIN", f"SELECT * FROM {items} JOIN {item} ON {item}.id = {items}.id{CURSOR}", "loop"),
                ("GROUP BY", f"SELECT {var}, COUNT(*) FROM {items} GROUP BY {var}{CURSOR}", "loop"),
                ("ORDER BY", f"ORDER BY {var} DESC{CURSOR}", "loop"),
                ("LIMIT", f"LIMIT 100{CURSOR}", "loop"),
                ("WITH", f"WITH {item} AS (SELECT * FROM {items}) SELECT * FROM {item}{CURSOR}", "loop"),
            ],
            "SEM_FUNC": [
                ("CREATE FUNCTION", f"CREATE FUNCTION {func}() RETURNS void AS $$ BEGIN END; $$ LANGUAGE plpgsql;{CURSOR}", "function"),
                ("PROCEDURE", f"CREATE PROCEDURE {func}() AS $$ BEGIN END; $$ LANGUAGE plpgsql;{CURSOR}", "function"),
                ("CREATE TABLE", f"CREATE TABLE {Type} (id INTEGER PRIMARY KEY);{CURSOR}", "function"),
                ("VIEW", f"CREATE VIEW {func}_view AS SELECT * FROM {items};{CURSOR}", "function"),
                ("RETURN", f"RETURN {var};{CURSOR}", "flow"),
                ("TYPE", f"CREATE TYPE {Type} AS ({var} TEXT);{CURSOR}", "function"),
            ],
            "SEM_VAR": [
                ("SELECT INTO", f"SELECT {var} INTO {item} FROM {items};{CURSOR}", "variables"),
                ("DECLARE", f"DECLARE {var} TEXT;{CURSOR}", "variables"),
                ("INSERT", f"INSERT INTO {items} ({var}) VALUES ({item});{CURSOR}", "variables"),
                ("UPDATE", f"UPDATE {items} SET {var} = {item} WHERE id = 1;{CURSOR}", "variables"),
                ("DELETE", f"DELETE FROM {items} WHERE id = 1;{CURSOR}", "variables"),
                ("CAST", f"CAST({var} AS TEXT){CURSOR}", "variables"),
            ],
            "SEM_ERR": [
                ("TRY / CATCH", f"BEGIN TRY\n    SELECT 1;\nEND TRY\nBEGIN CATCH\n    SELECT ERROR_MESSAGE();\nEND CATCH{CURSOR}", "shield"),
                ("TRANSACTION", f"BEGIN TRANSACTION;{CURSOR}", "shield"),
                ("ROLLBACK", f"ROLLBACK;{CURSOR}", "shield"),
                ("ASSERT", f"ASSERT {var} IS NOT NULL;{CURSOR}", "shield"),
                ("RAISERROR", f"RAISERROR('{var}', 16, 1);{CURSOR}", "shield"),
                ("TEST QUERY", f"SELECT COUNT(*) FROM {items};{CURSOR}", "test"),
            ],
            "SEM_IMPORT": [
                ("EXTENSION", f"CREATE EXTENSION IF NOT EXISTS {func};{CURSOR}", "terminal"),
                ("SCHEMA", f"CREATE SCHEMA IF NOT EXISTS {func};{CURSOR}", "terminal"),
                ("COPY", f"COPY {items} FROM '{var}.csv' CSV HEADER;{CURSOR}", "terminal"),
                ("ASYNC", f"SELECT pg_notify('{func}', '{var}');{CURSOR}", "function"),
                ("JSON", f"SELECT jsonb_build_object('{var}', {var});{CURSOR}", "terminal"),
                ("HTTP", f"SELECT http_get('{var}');{CURSOR}", "terminal"),
            ],
            "SEM_OP": [
                ("comparación", f"{var} >= {item}{CURSOR}", "operators"),
                ("lógica", f"{var} AND {item}{CURSOR}", "operators"),
                ("comentar", f"-- {var}{CURSOR}", "operators"),
                ("indentar", f"    {var}{CURSOR}", "operators"),
                ("paréntesis", f"({var}){CURSOR}", "operators"),
                ("alias", f"{var} AS {item}{CURSOR}", "operators"),
            ],
        }
    # C-like family: c, cpp, java, javascript, typescript, csharp, gdscript, lua, rust, go
    if lang == "gdscript":
        return {
            "SEM_COND": [("if", f"if {var}:{CURSOR}", "flow"), ("if / else", f"if {var}:\n    pass\nelse:\n    pass{CURSOR}", "flow"), ("elif", f"elif {var}:{CURSOR}", "flow"), ("match", f"match {var}:\n    _:\n        pass{CURSOR}", "flow"), ("ternario", f"{var} if {item} else null{CURSOR}", "operators"), ("guard", f"if not {var}:\n    return{CURSOR}", "flow")],
            "SEM_LOOP": [("for range", f"for i in range({items}.size()):{CURSOR}", "loop"), ("for each", f"for {item} in {items}:{CURSOR}", "loop"), ("while", f"while {var}:{CURSOR}", "loop"), ("break / continue", f"continue{CURSOR}", "loop"), ("map", f"var result = {items}.map(func(x): return x){CURSOR}", "loop"), ("enumerate", f"for i in range({items}.size()):\n    var item = {items}[i]{CURSOR}", "loop")],
            "SEM_FUNC": [("func", f"func {func}():{CURSOR}", "function"), ("async", f"func {func}() -> void:{CURSOR}", "function"), ("class", f"class_name {Type}\n\nfunc _init():{CURSOR}", "function"), ("property", f"var {var}:\n    get:\n        return {var}{CURSOR}", "function"), ("return", f"return {var}{CURSOR}", "flow"), ("typed", f"func {func}({item}: int) -> int:{CURSOR}", "function")],
            "SEM_VAR": [("asignación", f"var {var} = {item}{CURSOR}", "variables"), ("dict", f"var {var} = {{{item!r}: {item!r}}}{CURSOR}", "variables"), ("array", f"var {var} = []{CURSOR}", "variables"), ("format", f'"{var} %s" % {var}{CURSOR}', "variables"), ("unpack", f"var a = {items}[0]{CURSOR}", "variables"), ("const", f"const {var.upper()} = {item!r}{CURSOR}", "variables")],
            "SEM_ERR": [("try", f"try:\n    pass\nexcept:\n    pass{CURSOR}", "shield"), ("finally", f"finally:\n    pass{CURSOR}", "shield"), ("push_error", f"push_error({var!r}){CURSOR}", "shield"), ("assert", f"assert({var} != null){CURSOR}", "shield"), ("print", f"print({var}){CURSOR}", "terminal"), ("test", f"func test_{func}():\n    assert({func}() != null){CURSOR}", "test")],
            "SEM_IMPORT": [("preload", f"const {func} = preload('res://{func}.gd'){CURSOR}", "terminal"), ("load", f"var {var} = load('res://{var}.tscn'){CURSOR}", "terminal"), ("file", f"var file = FileAccess.open({var!r}, FileAccess.READ){CURSOR}", "terminal"), ("await", f"await {func}(){CURSOR}", "function"), ("JSON", f"var data = JSON.parse_string({var}){CURSOR}", "terminal"), ("request", f"HTTPRequest.new(){CURSOR}", "terminal")],
            "SEM_OP": [("comparación", f"{var} == {item}{CURSOR}", "operators"), ("lógica", f"{var} and {item}{CURSOR}", "operators"), ("comentar", f"# {var}{CURSOR}", "operators"), ("indentar", f"    {var}{CURSOR}", "operators"), ("paréntesis", f"({var}){CURSOR}", "operators"), ("lambda", f"func(x): return x{CURSOR}", "operators")],
        }
    if lang == "lua":
        return {
            "SEM_COND": [("if", f"if {var} then{CURSOR}", "flow"), ("if / else", f"if {var} then\nelse\nend{CURSOR}", "flow"), ("elseif", f"elseif {var} then{CURSOR}", "flow"), ("switch", f"if {var} == {item} then{CURSOR}", "flow"), ("ternario", f"{var} and {item} or nil{CURSOR}", "operators"), ("guard", f"if not {var} then return end{CURSOR}", "flow")],
            "SEM_LOOP": [("for numeric", f"for i = 1, #{items} do{CURSOR}", "loop"), ("for each", f"for _, {item} in ipairs({items}) do{CURSOR}", "loop"), ("while", f"while {var} do{CURSOR}", "loop"), ("break", f"break{CURSOR}", "loop"), ("map", f"for _, {item} in ipairs({items}) do table.insert({var}, {item}) end{CURSOR}", "loop"), ("pairs", f"for key, {item} in pairs({items}) do{CURSOR}", "loop")],
            "SEM_FUNC": [("function", f"function {func}(){CURSOR}", "function"), ("async", f"function {func}(){CURSOR}", "function"), ("class", f"{Type} = {{}}\nfunction {Type}:new(){CURSOR}", "function"), ("property", f"function {func}:get_{var}(){CURSOR}", "function"), ("return", f"return {var}{CURSOR}", "flow"), ("typed", f"---@param {item} any\nfunction {func}({item}){CURSOR}", "function")],
            "SEM_VAR": [("asignación", f"local {var} = {item}{CURSOR}", "variables"), ("table", f"local {var} = {{{item} = {item}}}{CURSOR}", "variables"), ("array", f"local {var} = {{}}{CURSOR}", "variables"), ("format", f"string.format('%s', {var}){CURSOR}", "variables"), ("unpack", f"local a, b = {items}[1], {items}[2]{CURSOR}", "variables"), ("const", f"local {var.upper()} = {item!r}{CURSOR}", "variables")],
            "SEM_ERR": [("pcall", f"local ok, err = pcall(function()\n    {CURSOR}\nend)", "shield"), ("finally", f"-- cleanup after pcall{CURSOR}", "shield"), ("error", f"error({var!r}){CURSOR}", "shield"), ("assert", f"assert({var} ~= nil, {var!r}){CURSOR}", "shield"), ("print", f"print({var}){CURSOR}", "terminal"), ("test", f"function test_{func}()\n    assert({func}() ~= nil)\nend{CURSOR}", "test")],
            "SEM_IMPORT": [("require", f"local {func} = require({func!r}){CURSOR}", "terminal"), ("module", f"local {var} = require({var!r}){CURSOR}", "terminal"), ("file", f"local file = io.open({var!r}, 'r'){CURSOR}", "terminal"), ("async", f"coroutine.wrap({func})(){CURSOR}", "function"), ("JSON", f"local data = json.decode({var}){CURSOR}", "terminal"), ("request", f"http.request({var!r}){CURSOR}", "terminal")],
            "SEM_OP": [("comparación", f"{var} == {item}{CURSOR}", "operators"), ("lógica", f"{var} and {item}{CURSOR}", "operators"), ("comentar", f"-- {var}{CURSOR}", "operators"), ("indentar", f"    {var}{CURSOR}", "operators"), ("paréntesis", f"({var}){CURSOR}", "operators"), ("arrow", f"function({item}) return {item} end{CURSOR}", "operators")],
        }
    # C / C++ / Java / JS / TS / C# / Rust / Go
    if lang in {"javascript", "typescript"}:
        cond = [("if", f"if ({var}) {{{CURSOR}}}", "flow"), ("if / else", f"if ({var}) {{\n}} else {{\n{CURSOR}}}", "flow"), ("else if", f"else if ({var}) {{{CURSOR}}}", "flow"), ("switch / case", f"switch ({var}) {{\n  case {item}:\n    break;\n{CURSOR}}}", "flow"), ("ternario", f"{var} ? {item} : null{CURSOR}", "operators"), ("guard", f"if (!{var}) return;{CURSOR}", "flow")]
        loop = [("for index", f"for (let i = 0; i < {items}.length; i++) {{{CURSOR}}}", "loop"), ("for of", f"for (const {item} of {items}) {{{CURSOR}}}", "loop"), ("while", f"while ({var}) {{{CURSOR}}}", "loop"), ("break / continue", f"continue;{CURSOR}", "loop"), ("map", f"{items}.map(({item}) => {item}){CURSOR}", "loop"), ("filter", f"{items}.filter(({item}) => {item}){CURSOR}", "loop")]
        func = [("function", f"function {func}() {{{CURSOR}}}", "function"), ("async function", f"async function {func}() {{{CURSOR}}}", "function"), ("class", f"class {Type} {{\n  constructor() {{{CURSOR}}}\n}}", "function"), ("getter", f"get {var}() {{{CURSOR}}}", "function"), ("return", f"return {var};{CURSOR}", "flow"), ("typed", f"function {func}({item}: {Type}): void {{{CURSOR}}}", "function")]
        var = [("asignación", f"const {var} = {item};{CURSOR}", "variables"), ("objeto", f"const {var} = {{ {item}: {item} }};{CURSOR}", "variables"), ("array", f"const {var} = [];{CURSOR}", "variables"), ("template", f"`${{{var}}}`{CURSOR}", "variables"), ("unpack", f"const [{item}, ...rest] = {items};{CURSOR}", "variables"), ("constante", f"const {var.upper()} = {item};{CURSOR}", "variables")]
        err = [("try / catch", f"try {{\n}} catch (error) {{{CURSOR}}}", "shield"), ("finally", f"finally {{{CURSOR}}}", "shield"), ("throw", f"throw new Error({var!r});{CURSOR}", "shield"), ("assert", f"console.assert({var});{CURSOR}", "shield"), ("log", f"console.log({var});{CURSOR}", "terminal"), ("test", f"test('{func}', () => {{\n  expect({func}()).toBeDefined();{CURSOR}\n}});", "test")]
        imp = [("import", f"import {func} from '{func}';{CURSOR}", "terminal"), ("named import", f"import {{ {var} }} from '{func}';{CURSOR}", "terminal"), ("file", f"const fs = require('fs');\nconst data = fs.readFileSync({var!r}, 'utf8');{CURSOR}", "terminal"), ("async / await", f"async function {func}() {{\n  await {var}();{CURSOR}\n}}", "function"), ("JSON", f"const data = JSON.parse({var});{CURSOR}", "terminal"), ("fetch", f"const response = await fetch({var!r});{CURSOR}", "terminal")]
        op = [("comparación", f"{var} === {item}{CURSOR}", "operators"), ("lógica", f"{var} && {item}{CURSOR}", "operators"), ("comentar", f"// {var}{CURSOR}", "operators"), ("indentar", f"  {var}{CURSOR}", "operators"), ("paréntesis", f"({var}){CURSOR}", "operators"), ("flecha", f"({item}) => {item}{CURSOR}", "operators")]
    elif lang == "java":
        cond = [("if", f"if ({var}) {{{CURSOR}}}", "flow"), ("if / else", f"if ({var}) {{\n}} else {{\n{CURSOR}}}", "flow"), ("else if", f"else if ({var}) {{{CURSOR}}}", "flow"), ("switch / case", f"switch ({var}) {{\n  case {item}:\n    break;\n{CURSOR}}}", "flow"), ("ternario", f"{var} ? {item} : null{CURSOR}", "operators"), ("guard", f"if ({var} == null) return;{CURSOR}", "flow")]
        loop = [("for index", f"for (int i = 0; i < {items}.size(); i++) {{{CURSOR}}}", "loop"), ("for each", f"for (var {item} : {items}) {{{CURSOR}}}", "loop"), ("while", f"while ({var}) {{{CURSOR}}}", "loop"), ("break / continue", f"continue;{CURSOR}", "loop"), ("stream map", f"{items}.stream().map({item} -> {item}){CURSOR}", "loop"), ("iterator", f"for (var it = {items}.iterator(); it.hasNext();) {{{CURSOR}}}", "loop")]
        func = [("method", f"public void {func}() {{{CURSOR}}}", "function"), ("async", f"public CompletableFuture<Void> {func}() {{{CURSOR}}}", "function"), ("class", f"public class {Type} {{\n  public {Type}() {{{CURSOR}}}\n}}", "function"), ("getter", f"public {Type} get{Type}() {{{CURSOR}}}", "function"), ("return", f"return {var};{CURSOR}", "flow"), ("typed", f"public {Type} {func}({Type} {item}) {{{CURSOR}}}", "function")]
        var = [("asignación", f"var {var} = {item};{CURSOR}", "variables"), ("map", f"Map<String, Object> {var} = new HashMap<>();{CURSOR}", "variables"), ("list", f"List<{Type}> {var} = new ArrayList<>();{CURSOR}", "variables"), ("format", f"String.format(\"%s\", {var}){CURSOR}", "variables"), ("unpack", f"var {item} = {items}.get(0);{CURSOR}", "variables"), ("constante", f"static final {Type} {var.upper()} = {item};{CURSOR}", "variables")]
        err = [("try / catch", f"try {{\n}} catch (Exception error) {{{CURSOR}}}", "shield"), ("finally", f"finally {{{CURSOR}}}", "shield"), ("throw", f"throw new IllegalStateException({var!r});{CURSOR}", "shield"), ("assert", f"assert {var} != null;{CURSOR}", "shield"), ("log", f"System.out.println({var});{CURSOR}", "terminal"), ("test", f"@Test\nvoid test{Type}() {{\n  assertNotNull({func}());{CURSOR}\n}}", "test")]
        imp = [("import", f"import {func};{CURSOR}", "terminal"), ("static import", f"import static {func}.{var};{CURSOR}", "terminal"), ("file", f"Files.readString(Path.of({var!r}));{CURSOR}", "terminal"), ("async", f"CompletableFuture.runAsync(() -> {func}());{CURSOR}", "function"), ("JSON", f"new ObjectMapper().readTree({var});{CURSOR}", "terminal"), ("request", f"HttpClient.newHttpClient().send(request, BodyHandlers.ofString());{CURSOR}", "terminal")]
        op = [("comparación", f"{var} == {item}{CURSOR}", "operators"), ("lógica", f"{var} && {item}{CURSOR}", "operators"), ("comentar", f"// {var}{CURSOR}", "operators"), ("indentar", f"    {var}{CURSOR}", "operators"), ("paréntesis", f"({var}){CURSOR}", "operators"), ("flecha", f"({item}) -> {item}{CURSOR}", "operators")]
    else:  # c / cpp / csharp / rust / go
        cond = [("if", f"if ({var}) {{{CURSOR}}}", "flow"), ("if / else", f"if ({var}) {{\n}} else {{\n{CURSOR}}}", "flow"), ("else if", f"else if ({var}) {{{CURSOR}}}", "flow"), ("switch / match", f"switch ({var}) {{\n  case {item}: break;\n{CURSOR}}}", "flow"), ("ternario", f"{var} ? {item} : 0{CURSOR}", "operators"), ("guard", f"if ({var} == NULL) return;{CURSOR}", "flow")]
        loop = [("for index", f"for (int i = 0; i < {items}_len; i++) {{{CURSOR}}}", "loop"), ("for each", f"for (int i = 0; i < {items}_len; i++) {{\n  {item} = {items}[i];{CURSOR}\n}}", "loop"), ("while", f"while ({var}) {{{CURSOR}}}", "loop"), ("break / continue", f"continue;{CURSOR}", "loop"), ("map", f"for (int i = 0; i < {items}_len; i++) {{ {item} = {items}[i]; }}{CURSOR}", "loop"), ("iterator", f"for (auto& {item} : {items}) {{{CURSOR}}}", "loop")]
        func = [("function", f"void {func}() {{{CURSOR}}}", "function"), ("async", f"std::future<void> {func}() {{{CURSOR}}}", "function"), ("class", f"class {Type} {{\npublic:\n  {Type}() {{{CURSOR}}}\n}};", "function"), ("getter", f"int get_{var}() const {{{CURSOR}}}", "function"), ("return", f"return {var};{CURSOR}", "flow"), ("typed", f"int {func}(int {item}) {{{CURSOR}}}", "function")]
        var = [("asignación", f"auto {var} = {item};{CURSOR}", "variables"), ("map", f"std::map<std::string, int> {var};{CURSOR}", "variables"), ("array", f"std::vector<int> {var};{CURSOR}", "variables"), ("format", f"std::format(\"{{}}\", {var}){CURSOR}", "variables"), ("unpack", f"auto [{item}] = {items};{CURSOR}", "variables"), ("constante", f"constexpr int {var.upper()} = {item};{CURSOR}", "variables")]
        err = [("try / catch", f"try {{\n}} catch (const std::exception& error) {{{CURSOR}}}", "shield"), ("finally", f"// cleanup guard{CURSOR}", "shield"), ("throw", f"throw std::runtime_error({var!r});{CURSOR}", "shield"), ("assert", f"assert({var} != nullptr);{CURSOR}", "shield"), ("log", f"std::cerr << {var} << std::endl;{CURSOR}", "terminal"), ("test", f"TEST({Type}, {func}) {{\n  EXPECT_TRUE({func}());{CURSOR}\n}}", "test")]
        imp = [("include", f"#include <{func}>{CURSOR}", "terminal"), ("using", f"using {func} = {Type};{CURSOR}", "terminal"), ("file", f"std::ifstream file({var!r});{CURSOR}", "terminal"), ("async", f"std::async(std::launch::async, {func});{CURSOR}", "function"), ("JSON", f"auto data = nlohmann::json::parse({var});{CURSOR}", "terminal"), ("request", f"auto response = client.Get({var!r});{CURSOR}", "terminal")]
        op = [("comparación", f"{var} == {item}{CURSOR}", "operators"), ("lógica", f"{var} && {item}{CURSOR}", "operators"), ("comentar", f"// {var}{CURSOR}", "operators"), ("indentar", f"    {var}{CURSOR}", "operators"), ("paréntesis", f"({var}){CURSOR}", "operators"), ("flecha", f"[]({item}) {{ return {item}; }}{CURSOR}", "operators")]
    return {"SEM_COND": cond, "SEM_LOOP": loop, "SEM_FUNC": func, "SEM_VAR": var, "SEM_ERR": err, "SEM_IMPORT": imp, "SEM_OP": op}


def _category_node(category_id: str, title: str, actions: List[MenuAction], parent_id: str = "ROOT") -> MenuNode:
    items: List[MenuAction] = [None] * 9  # type: ignore[list-item]
    for index, action in zip(SLOTS, actions[:6]):
        items[index] = action
    items[4] = create_pause_action("5")
    items[6] = create_back_action(parent_id, "7")
    items[8] = MenuAction(
        id=f"{category_id}_REFRESH",
        label="9: ACTUALIZAR",
        hint="Releer símbolos y contexto en vivo",
        action_type="SEMANTIC_REFRESH",
        icon="refresh",
    )
    return MenuNode(
        id=category_id,
        title=title,
        breadcrumb_label=title,
        items=items,
        parent_id=parent_id,
        sticky=False,
    )


def _ai_actions(suggestions: Optional[Sequence[str]], document_context: bool) -> List[MenuAction]:
    defaults = (
        ["Continuar la frase actual", "Desarrollar el párrafo con argumentos", "Sintetizar en puntos clave", "Redactar conclusión o transición", "Insertar conector formal", "Resumir la selección"]
        if document_context
        else ["Cerrar la lógica pendiente", "Completar la condición con variables locales", "Implementar el cuerpo de la función", "Corregir el error activo", "Añadir validación defensiva", "Extraer una función auxiliar"]
    )
    values = [str(s).strip() for s in (suggestions or []) if str(s).strip()]
    for fallback in defaults:
        if len(values) >= 6:
            break
        if fallback not in values:
            values.append(fallback)
    actions: List[MenuAction] = []
    for index, value in enumerate(values[:6]):
        actions.append(_action(f"SEM_AI_{index + 1}", f"{KEY_LABELS[index]}: {value[:30]}", value, "ai_spark", value))
    return actions


def build_semantic_coding_tree(
    language: str = "PYTHON",
    symbols: Optional[Sequence[Any]] = None,
    ai_suggestions: Optional[Sequence[str]] = None,
    document_context: bool = False,
) -> Dict[str, MenuNode]:
    """Builds the deep Phase 12 coding taxonomy for the active language."""
    lang = normalize_taxonomy_language(language)
    syms = _clean_symbols(symbols)
    templates = _lang_templates(lang, syms)
    tree: Dict[str, MenuNode] = {}
    root_items: List[MenuAction] = [None] * 9  # type: ignore[list-item]
    for slot, spec in zip((0, 1, 2, 3, 5, 6, 7, 8), CATEGORY_SPECS):
        category_id, title, icon, _ = spec
        actions = [
            _action(f"{category_id}_{index + 1}", f"{KEY_LABELS[index]}: {label}", text, action_icon)
            for index, (label, text, action_icon) in enumerate(templates.get(category_id, [])[:6])
        ]
        if category_id == "SEM_AI":
            actions = _ai_actions(ai_suggestions, document_context)
        tree[category_id] = _category_node(category_id, title, actions)
        root_items[slot] = MenuAction(
            id=category_id,
            label=f"{_slot_key(slot)}: {title}",
            hint=f"Abrir {title.lower()}",
            action_type="SUBMENU",
            submenu_id=category_id,
            icon=icon,
        )
    root_items[4] = create_pause_action("5")
    tree["ROOT"] = MenuNode(
        id="ROOT",
        title="CÓDIGO / TAXONOMÍA",
        breadcrumb_label="CÓDIGO",
        items=root_items,
        parent_id=None,
        sticky=False,
    )
    return tree


_PROJECT_CONTEXT_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL_SEC: float = 5.0


def clear_project_context_cache() -> None:
    """Clears the cached git project context (useful for testing or manual refresh)."""
    _PROJECT_CONTEXT_CACHE.clear()


def detect_project_context(
    workspace_dir: Optional[str] = None, force_refresh: bool = False
) -> Dict[str, Any]:
    """Safe, bounded inspection of the current repository for Terminal mode.

    Caches results per workspace root to avoid repeated git execution.
    On Windows, uses CREATE_NO_WINDOW and hidden STARTUPINFO to prevent
    console window popups.
    """
    root = os.path.abspath(workspace_dir or os.getcwd())
    now = time.time()
    if not force_refresh and root in _PROJECT_CONTEXT_CACHE:
        cached_time, cached_val = _PROJECT_CONTEXT_CACHE[root]
        if now - cached_time < _CACHE_TTL_SEC:
            return dict(cached_val)

    result: Dict[str, Any] = {
        "root": root,
        "branch": "",
        "status": [],
        "project_type": "generic",
        "files": [],
    }
    for marker, kind in (
        ("pyproject.toml", "python"),
        ("package.json", "node"),
        ("Cargo.toml", "rust"),
        ("Makefile", "make"),
        ("pom.xml", "java"),
        ("build.gradle", "java"),
    ):
        if os.path.isfile(os.path.join(root, marker)):
            result["project_type"] = kind
            result["files"].append(marker)

    subp_kwargs: Dict[str, Any] = {
        "cwd": root,
        "capture_output": True,
        "text": True,
        "timeout": 2,
        "check": False,
    }
    if sys.platform == "win32":
        subp_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 1)
        si.wShowWindow = 0  # SW_HIDE
        subp_kwargs["startupinfo"] = si

    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            **subp_kwargs,
        )
        result["branch"] = (branch.stdout or "").strip()
        status = subprocess.run(
            ["git", "status", "--short"],
            **subp_kwargs,
        )
        result["status"] = [
            line for line in (status.stdout or "").splitlines() if line.strip()
        ][:12]
    except (OSError, subprocess.SubprocessError):
        pass

    _PROJECT_CONTEXT_CACHE[root] = (now, dict(result))
    return result


def build_terminal_semantic_tree(project_context: Optional[Dict[str, Any]] = None) -> Dict[str, MenuNode]:
    ctx = project_context or detect_project_context()
    branch = str(ctx.get("branch") or "sin rama")
    modified = len(ctx.get("status") or [])
    tree: Dict[str, MenuNode] = {}
    specs = [
        ("TERM_SMART_GIT", "GIT INTELIGENTE", [("Estado", "git status --short", "flow"), ("Añadir todo", "git add .", "flow"), ("Commit", 'git commit -m "[[CURSOR]]"', "format"), ("Push", "git push", "format"), ("Pull", "git pull", "format"), ("Rama actual", f"git branch --show-current", "navigation")]),
        ("TERM_BUILD", "EJECUTAR Y COMPILAR", [("Ejecutar", "python main.py", "terminal"), ("Compilar", "python -m compileall .", "terminal"), ("Instalar", "pip install -r requirements.txt", "terminal"), ("Build", "python build_app.py", "terminal"), ("Test rápido", "pytest -q", "test"), ("Limpiar", "python -m compileall -q .", "terminal")]),
        ("TERM_TEST", "PYTEST Y COBERTURA", [("Pytest", "pytest -v", "test"), ("Cobertura", "pytest --cov=. --cov-report=term-missing", "test"), ("Un test", "pytest -q -k [[CURSOR]]", "test"), ("Fallos", "pytest -x --tb=short", "test"), ("Watch", "pytest -f", "test"), ("Reporte", "coverage html", "test")]),
        ("TERM_ENV", "ENTORNOS Y PAQUETES", [("Activar venv", "venv\\Scripts\\activate", "terminal"), ("Pip list", "pip list", "terminal"), ("Instalar", "pip install [[CURSOR]]", "terminal"), ("Procesos", "tasklist", "terminal"), ("Python", "python --version", "terminal"), ("Entorno", "set", "terminal")]),
        ("TERM_PATHS", "RUTAS Y ARCHIVOS", [("Listar", "dir", "navigation"), ("Subir", "cd ..", "navigation"), ("Crear", "mkdir [[CURSOR]]", "navigation"), ("Ruta", "cd [[CURSOR]]", "navigation"), ("Actual", "cd", "navigation"), ("Árbol", "tree /F", "navigation")]),
        ("TERM_CLEAN", "LIMPIEZA Y SEÑALES", [("Limpiar", "cls", "edit"), ("Cancelar", "CTRL_C", "edit"), ("Salir", "exit", "edit"), ("Borrar", "del [[CURSOR]]", "edit"), ("Historial", "doskey /history", "navigation"), ("Reset", "git restore .", "edit")]),
        ("TERM_PIPE", "TUBERÍAS Y FLAGS", [("Pipe", " | ", "operators"), ("Y lógico", " && ", "operators"), ("Redirigir", " > ", "operators"), ("Append", " >> ", "operators"), ("Ayuda", " --help", "operators"), ("Fondo", " &", "operators")]),
        ("TERM_AI", "SUGERENCIAS IA", [("Estado", "git status", "ai_spark"), ("Commit", 'git commit -m "feat: [[CURSOR]]"', "ai_spark"), ("Test", "pytest -q", "ai_spark"), ("Build", "python build_app.py", "ai_spark"), ("Rama", f"git checkout -b feature/{branch}", "ai_spark"), ("Diff", "git diff --stat", "ai_spark")]),
    ]
    root_items: List[MenuAction] = [None] * 9  # type: ignore[list-item]
    for slot, (node_id, title, actions) in zip((0, 1, 2, 3, 5, 6, 7, 8), specs):
        menu_actions = [_action(f"{node_id}_{i+1}", f"{KEY_LABELS[i]}: {label}", text, icon) for i, (label, text, icon) in enumerate(actions)]
        tree[node_id] = _category_node(node_id, title, menu_actions)
        root_items[slot] = MenuAction(
            id=node_id,
            label=f"{_slot_key(slot)}: {title}",
            hint=f"{branch} · {modified} cambios",
            action_type="SUBMENU",
            submenu_id=node_id,
            icon="terminal",
        )
    root_items[4] = create_pause_action("5")
    tree["ROOT"] = MenuNode(id="ROOT", title="TERMINAL INTELIGENTE", breadcrumb_label="TERMINAL", items=root_items, parent_id=None, sticky=False)
    return tree


def build_navigation_dual_tree(document_mode: bool = False) -> Dict[str, MenuNode]:
    tree: Dict[str, MenuNode] = {}
    if document_mode:
        specs = [
            ("NAV_DOC_HEAD", "ENCABEZADOS", [("H1", "CTRL_ALT_1", "navigation"), ("H2", "CTRL_ALT_2", "navigation"), ("H3", "CTRL_ALT_3", "navigation"), ("Título", "CTRL_ALT_0", "navigation"), ("Párrafo", "CTRL_ALT_0", "navigation"), ("Limpiar formato", "CTRL_BACKSLASH", "edit")]),
            ("NAV_DOC_LIST", "LISTAS", [("Viñetas", "CTRL_SHIFT_8", "navigation"), ("Numerada", "CTRL_SHIFT_7", "navigation"), ("Sangría", "TAB", "navigation"), ("Quitar sangría", "SHIFT_TAB", "navigation"), ("Checklist", "CTRL_SHIFT_9", "navigation"), ("Cita", "CTRL_SHIFT_9", "navigation")]),
            ("NAV_DOC_FIND", "BUSCAR", [("Buscar", "CTRL_F", "navigation"), ("Siguiente", "F3", "navigation"), ("Anterior", "SHIFT_F3", "navigation"), ("Reemplazar", "CTRL_H", "navigation"), ("Ir a", "CTRL_G", "navigation"), ("Cerrar", "ESC", "navigation")]),
            ("NAV_DOC_TABS", "PESTAÑAS", [("Siguiente", "CTRL_TAB", "navigation"), ("Anterior", "CTRL_SHIFT_TAB", "navigation"), ("Nueva", "CTRL_T", "navigation"), ("Cerrar", "CTRL_W", "navigation"), ("Reabrir", "CTRL_SHIFT_T", "navigation"), ("Ventana", "CTRL_N", "navigation")]),
            ("NAV_DOC_ZOOM", "ZOOM Y LECTURA", [("Acercar", "CTRL_PLUS", "navigation"), ("Alejar", "CTRL_MINUS", "navigation"), ("100%", "CTRL_0", "navigation"), ("Pantalla", "F11", "navigation"), ("Scroll arriba", "PAGE_UP", "navigation"), ("Scroll abajo", "PAGE_DOWN", "navigation")]),
            ("NAV_DOC_EDIT", "EDICIÓN", [("Deshacer", "CTRL_Z", "edit"), ("Rehacer", "CTRL_Y", "edit"), ("Copiar", "CTRL_C", "edit"), ("Pegar", "CTRL_V", "edit"), ("Seleccionar todo", "CTRL_A", "edit"), ("Comentar", "CTRL_ALT_M", "edit")]),
            ("NAV_DOC_SCROLL", "SCROLL SUAVE", [("Arriba", "PAGE_UP", "navigation"), ("Abajo", "PAGE_DOWN", "navigation"), ("Inicio", "CTRL_HOME", "navigation"), ("Fin", "CTRL_END", "navigation"), ("Scroll ocular", "GAZE_SCROLL", "navigation"), ("Centrar", "CTRL_HOME", "navigation")]),
            ("NAV_DOC_AI", "IA DE DOCUMENTO", [("Continuar", "continuar la frase", "ai_spark"), ("Desarrollar", "desarrollar el párrafo", "ai_spark"), ("Resumir", "resumir la selección", "ai_spark"), ("Conclusión", "redactar conclusión", "ai_spark"), ("Conector", "insertar conector formal", "ai_spark"), ("Formato", "formatear selección", "ai_spark")]),
        ]
    else:
        specs = [
            ("NAV_GOTO", "SALTAR", [("Definición", "F12", "navigation"), ("Referencias", "SHIFT_F12", "navigation"), ("Símbolo", "CTRL_SHIFT_O", "navigation"), ("Archivo", "CTRL_P", "navigation"), ("Línea", "CTRL_G", "navigation"), ("Atrás", "ALT_LEFT", "navigation")]),
            ("NAV_FOLD", "PLEGAR / DIVIDIR", [("Plegar", "CTRL_SHIFT_LBRACKET", "navigation"), ("Desplegar", "CTRL_SHIFT_RBRACKET", "navigation"), ("Plegar todo", "CTRL_K_CTRL_0", "navigation"), ("Desplegar todo", "CTRL_K_CTRL_J", "navigation"), ("Dividir editor", "CTRL_BACKSLASH", "navigation"), ("Cerrar grupo", "CTRL_W", "navigation")]),
            ("NAV_RECENT", "ARCHIVOS RECIENTES", [("Reciente 1", "CTRL_TAB", "navigation"), ("Reciente 2", "CTRL_SHIFT_TAB", "navigation"), ("Reabrir", "CTRL_SHIFT_T", "navigation"), ("Explorador", "CTRL_SHIFT_E", "navigation"), ("Guardar", "CTRL_S", "navigation"), ("Guardar todo", "CTRL_K_S", "navigation")]),
            ("NAV_SCROLL", "SCROLL OCULAR", [("Arriba", "PAGE_UP", "navigation"), ("Abajo", "PAGE_DOWN", "navigation"), ("Inicio", "CTRL_HOME", "navigation"), ("Fin", "CTRL_END", "navigation"), ("Scroll continuo", "GAZE_SCROLL", "navigation"), ("Centrar", "CTRL_HOME", "navigation")]),
            ("NAV_SEARCH", "BUSCAR", [("Buscar", "CTRL_F", "navigation"), ("Archivos", "CTRL_SHIFT_F", "navigation"), ("Reemplazar", "CTRL_H", "navigation"), ("Global", "CTRL_SHIFT_H", "navigation"), ("Siguiente", "F3", "navigation"), ("Anterior", "SHIFT_F3", "navigation")]),
            ("NAV_TABS", "PESTAÑAS", [("Siguiente", "CTRL_TAB", "navigation"), ("Anterior", "CTRL_SHIFT_TAB", "navigation"), ("Cerrar", "CTRL_W", "navigation"), ("Reabrir", "CTRL_SHIFT_T", "navigation"), ("Nueva", "CTRL_T", "navigation"), ("Foco lateral", "CTRL_1", "navigation")]),
            ("NAV_EDIT", "EDICIÓN", [("Deshacer", "CTRL_Z", "edit"), ("Rehacer", "CTRL_Y", "edit"), ("Formatear", "SHIFT_ALT_F", "edit"), ("Renombrar", "F2", "edit"), ("Quick fix", "CTRL_DOT", "edit"), ("Comandos", "CTRL_SHIFT_P", "edit")]),
            ("NAV_AI", "IA DE CÓDIGO", [("Explicar", "explicar el código", "ai_spark"), ("Referencias", "buscar referencias", "ai_spark"), ("Tests", "generar tests", "ai_spark"), ("Docs", "generar documentación", "ai_spark"), ("Refactor", "refactorizar", "ai_spark"), ("Optimizar", "optimizar", "ai_spark")]),
        ]
    root_items: List[MenuAction] = [None] * 9  # type: ignore[list-item]
    for slot, (node_id, title, actions) in zip((0, 1, 2, 3, 5, 6, 7, 8), specs):
        menu_actions = []
        for i, (label, value, icon) in enumerate(actions):
            if value in {"GAZE_SCROLL"}:
                action = MenuAction(f"{node_id}_{i+1}", f"{KEY_LABELS[i]}: {label}", label, "GAZE_SCROLL", icon=icon)
            elif value.isupper() or "_" in value:
                action = MenuAction(f"{node_id}_{i+1}", f"{KEY_LABELS[i]}: {label}", label, "KEY", key_name=value, icon=icon)
            else:
                action = _action(f"{node_id}_{i+1}", f"{KEY_LABELS[i]}: {label}", value, icon)
            menu_actions.append(action)
        tree[node_id] = _category_node(node_id, title, menu_actions)
        root_items[slot] = MenuAction(node_id, f"{_slot_key(slot)}: {title}", f"Abrir {title.lower()}", "SUBMENU", submenu_id=node_id, icon="navigation")
    root_items[4] = create_pause_action("5")
    title = "LECTURA / DOCUMENTO" if document_mode else "NAVEGACIÓN / IDE"
    tree["ROOT"] = MenuNode(id="ROOT", title=title, breadcrumb_label=title, items=root_items, parent_id=None, sticky=False)
    return tree


def build_debug_semantic_tree(symbols: Optional[Sequence[Any]] = None) -> Dict[str, MenuNode]:
    syms = _clean_symbols(symbols) or ["value", "result", "item"]
    inspect_actions = [("Inspeccionar", f"print({name})", "terminal") for name in syms[:6]]
    specs = [
        ("DBG_LOCALS", "INSPECCIONAR VARIABLES", inspect_actions),
        ("DBG_BREAK", "BREAKPOINTS CONDICIONALES", [("Breakpoint", "F9", "shield"), ("Condicional", "SHIFT_F9", "shield"), ("Logpoint", "CTRL_SHIFT_F9", "shield"), ("Eliminar", "CTRL_SHIFT_F9", "shield"), ("Desactivar", "CTRL_F9", "shield"), ("Listar", "CTRL_SHIFT_F8", "shield")]),
        ("DBG_STEP", "PASO A PASO", [("Step over", "F10", "navigation"), ("Step into", "F11", "navigation"), ("Step out", "SHIFT_F11", "navigation"), ("Continuar", "F5", "navigation"), ("Pausar", "F6", "navigation"), ("Reiniciar", "CTRL_SHIFT_F5", "navigation")]),
        ("DBG_STACK", "PILA DE LLAMADAS", [("Subir", "UP", "navigation"), ("Bajar", "DOWN", "navigation"), ("Marco actual", "ENTER", "navigation"), ("Copiar pila", "CTRL_C", "navigation"), ("Reiniciar", "CTRL_SHIFT_F5", "navigation"), ("Cerrar", "SHIFT_F5", "navigation")]),
        ("DBG_WATCH", "WATCH", [("Añadir", "watch", "variables"), ("Editar", "edit watch", "variables"), ("Eliminar", "remove watch", "variables"), ("Evaluar", "evaluate", "variables"), ("Copiar", "copy value", "variables"), ("Limpiar", "clear watches", "variables")]),
        ("DBG_CONSOLE", "CONSOLA", [("Abrir", "CTRL_SHIFT_Y", "terminal"), ("Limpiar", "clear", "terminal"), ("Ejecutar", "ENTER", "terminal"), ("Historial", "UP", "terminal"), ("Copiar", "CTRL_C", "terminal"), ("Cerrar", "ESC", "terminal")]),
        ("DBG_SESSION", "SESIONES Y CONFIG", [("Iniciar", "F5", "shield"), ("Detener", "SHIFT_F5", "shield"), ("Reiniciar", "CTRL_SHIFT_F5", "shield"), ("Configurar", "edit configuration", "shield"), ("Guardar log", "save log", "shield"), ("Abrir panel", "CTRL_SHIFT_D", "shield")]),
        ("DBG_AI", "IA DE DEBUG", [("Explicar fallo", "explicar el fallo", "ai_spark"), ("Causa raíz", "analizar causa raíz", "ai_spark"), ("Fix", "proponer fix", "ai_spark"), ("Test", "generar test de regresión", "ai_spark"), ("Logs", "añadir logs", "ai_spark"), ("Resumen", "resumir la pila", "ai_spark")]),
    ]
    tree: Dict[str, MenuNode] = {}
    root_items: List[MenuAction] = [None] * 9  # type: ignore[list-item]
    for slot, (node_id, title, actions) in zip((0, 1, 2, 3, 5, 6, 7, 8), specs):
        menu_actions = []
        for i, (label, value, icon) in enumerate(actions):
            if value.isupper() or "_" in value:
                menu_actions.append(MenuAction(f"{node_id}_{i+1}", f"{KEY_LABELS[i]}: {label}", label, "KEY", key_name=value, icon=icon))
            else:
                menu_actions.append(_action(f"{node_id}_{i+1}", f"{KEY_LABELS[i]}: {label}", value, icon))
        tree[node_id] = _category_node(node_id, title, menu_actions)
        root_items[slot] = MenuAction(node_id, f"{_slot_key(slot)}: {title}", f"Abrir {title.lower()}", "SUBMENU", submenu_id=node_id, icon="shield")
    root_items[4] = create_pause_action("5")
    tree["ROOT"] = MenuNode(id="ROOT", title="DEBUG / INSPECCIÓN", breadcrumb_label="DEBUG", items=root_items, parent_id=None, sticky=False)
    return tree
