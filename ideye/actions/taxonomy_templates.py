"""Language templates and symbol helpers for the semantic taxonomy."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Any


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
