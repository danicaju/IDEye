"""Item builders for the flow, structure and operator submenus."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Set, Union, Any

try:
    from ideye.actions.language_support import (
        LANG_PYTHON,
        LANG_TYPESCRIPT,
        LANG_RUST,
        LANG_CPP,
        LANG_GO,
        SUPPORTED_LANGUAGES,
        LANGUAGE_DISPLAY_NAMES,
        LANGUAGE_BADGES,
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
        LANGUAGE_DISPLAY_NAMES,
        LANGUAGE_BADGES,
        normalize_language,
        get_language_display_name,
        get_language_badge,
    )

from ideye.actions.trees_model import *  # noqa: F401,F403
from ideye.actions.trees_populators import *  # noqa: F401,F403

def _build_flow_items(lang: str) -> List[MenuAction]:
    """Builds the 9 items for the FLOW submenu for the specified language."""
    if lang == LANG_TYPESCRIPT:
        return [
            MenuAction("FLOW_IF", "1: if () {", "Condicional if", "SNIPPET", snippet="if () {\n    \n}", cursor_offset_up=2, cursor_offset_left=3, icon="flow"),
            MenuAction("FLOW_ELIF", "2: else if () {", "Condicional else if", "SNIPPET", snippet="else if () {\n    \n}", cursor_offset_up=2, cursor_offset_left=3, icon="flow"),
            MenuAction("FLOW_ELSE", "3: else {", "Rama else", "SNIPPET", snippet="else {\n    \n}", cursor_offset_up=1, icon="flow"),
            MenuAction("FLOW_FOR_RANGE", "4: for (let i = 0...)", "Bucle indexado", "SNIPPET", snippet="for (let i = 0; i < ; i++) {\n    \n}", cursor_offset_up=1, cursor_offset_left=11, icon="flow"),
            create_pause_action("5"),
            MenuAction("FLOW_FOR_LIST", "6: for (const x of )", "Iterador de colección", "SNIPPET", snippet="for (const item of ) {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            create_back_action("ROOT", "7"),
            MenuAction("FLOW_WHILE", "8: while () {", "Bucle while", "SNIPPET", snippet="while () {\n    \n}", cursor_offset_up=2, cursor_offset_left=3, icon="flow"),
            MenuAction("FLOW_TRY_RET_SUB", "9: TRY / CATCH / RET", "try-catch, return, throw", "SUBMENU", submenu_id="FLOW_TRY_RET", icon="flow"),
        ]
    elif lang == LANG_RUST:
        return [
            MenuAction("FLOW_IF", "1: if {", "Condicional if", "SNIPPET", snippet="if  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            MenuAction("FLOW_ELIF", "2: else if {", "Condicional else if", "SNIPPET", snippet="else if  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            MenuAction("FLOW_ELSE", "3: else {", "Rama else", "SNIPPET", snippet="else {\n    \n}", cursor_offset_up=1, icon="flow"),
            MenuAction("FLOW_FOR_RANGE", "4: for i in 0.. {", "Bucle de rango", "SNIPPET", snippet="for i in 0.. {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            create_pause_action("5"),
            MenuAction("FLOW_FOR_LIST", "6: for x in .iter() {", "Iterador de colección", "SNIPPET", snippet="for x in .iter() {\n    \n}", cursor_offset_up=1, cursor_offset_left=11, icon="flow"),
            create_back_action("ROOT", "7"),
            MenuAction("FLOW_WHILE", "8: while {", "Bucle while", "SNIPPET", snippet="while  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            MenuAction("FLOW_TRY_RET_SUB", "9: MATCH / RESULT / RET", "match, Result, return", "SUBMENU", submenu_id="FLOW_TRY_RET", icon="flow"),
        ]
    elif lang == LANG_CPP:
        return [
            MenuAction("FLOW_IF", "1: if () {", "Condicional if", "SNIPPET", snippet="if () {\n    \n}", cursor_offset_up=2, cursor_offset_left=3, icon="flow"),
            MenuAction("FLOW_ELIF", "2: else if () {", "Condicional else if", "SNIPPET", snippet="else if () {\n    \n}", cursor_offset_up=2, cursor_offset_left=3, icon="flow"),
            MenuAction("FLOW_ELSE", "3: else {", "Rama else", "SNIPPET", snippet="else {\n    \n}", cursor_offset_up=1, icon="flow"),
            MenuAction("FLOW_FOR_RANGE", "4: for (int i = 0...)", "Bucle numérico", "SNIPPET", snippet="for (int i = 0; i < ; ++i) {\n    \n}", cursor_offset_up=1, cursor_offset_left=12, icon="flow"),
            create_pause_action("5"),
            MenuAction("FLOW_FOR_LIST", "6: for (auto& x : )", "Range-based for", "SNIPPET", snippet="for (const auto& item : ) {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            create_back_action("ROOT", "7"),
            MenuAction("FLOW_WHILE", "8: while () {", "Bucle while", "SNIPPET", snippet="while () {\n    \n}", cursor_offset_up=2, cursor_offset_left=3, icon="flow"),
            MenuAction("FLOW_TRY_RET_SUB", "9: TRY / CATCH / RET", "try-catch, return, throw", "SUBMENU", submenu_id="FLOW_TRY_RET", icon="flow"),
        ]
    elif lang == LANG_GO:
        return [
            MenuAction("FLOW_IF", "1: if {", "Condicional if", "SNIPPET", snippet="if  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            MenuAction("FLOW_ELIF", "2: else if {", "Condicional else if", "SNIPPET", snippet="else if  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            MenuAction("FLOW_ELSE", "3: else {", "Rama else", "SNIPPET", snippet="else {\n    \n}", cursor_offset_up=1, icon="flow"),
            MenuAction("FLOW_FOR_RANGE", "4: for i := 0; ...", "Bucle indexado", "SNIPPET", snippet="for i := 0; i < ; i++ {\n    \n}", cursor_offset_up=1, cursor_offset_left=10, icon="flow"),
            create_pause_action("5"),
            MenuAction("FLOW_FOR_LIST", "6: for _, x := range", "Iterador range", "SNIPPET", snippet="for _, item := range  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            create_back_action("ROOT", "7"),
            MenuAction("FLOW_WHILE", "8: for {", "Bucle infinito", "SNIPPET", snippet="for {\n    \n}", cursor_offset_up=1, icon="flow"),
            MenuAction("FLOW_TRY_RET_SUB", "9: ERR / RET / DEFER", "err != nil, return, defer", "SUBMENU", submenu_id="FLOW_TRY_RET", icon="flow"),
        ]
    else:  # PYTHON
        return [
            MenuAction(id="FLOW_IF", label="1: if ...:", hint="Condicional if", action_type="SNIPPET", snippet="if :", cursor_offset_left=1, icon="flow"),
            MenuAction(id="FLOW_ELIF", label="2: elif ...:", hint="Condicional elif", action_type="SNIPPET", snippet="elif :", cursor_offset_left=1, icon="flow"),
            MenuAction(id="FLOW_ELSE", label="3: else:", hint="Rama else con salto", action_type="SNIPPET", snippet="else:\n    ", icon="flow"),
            MenuAction(id="FLOW_FOR_RANGE", label="4: for i in range():", hint="Bucle indexado", action_type="SNIPPET", snippet="for i in range():", cursor_offset_left=2, icon="flow"),
            create_pause_action("5"),
            MenuAction(id="FLOW_FOR_LIST", label="6: for x in lista:", hint="Iterador de colección", action_type="SNIPPET", snippet="for x in :", cursor_offset_left=1, icon="flow"),
            create_back_action("ROOT", "7"),
            MenuAction(id="FLOW_WHILE", label="8: while ...:", hint="Bucle while", action_type="SNIPPET", snippet="while :", cursor_offset_left=1, icon="flow"),
            MenuAction(id="FLOW_TRY_RET_SUB", label="9: TRY / EXCEPT / RET", hint="try-except, return, raise", action_type="SUBMENU", submenu_id="FLOW_TRY_RET", icon="flow"),
        ]


def _build_flow_try_items(lang: str) -> List[MenuAction]:
    """Builds the 9 items for the FLOW_TRY_RET submenu for the specified language."""
    if lang == LANG_TYPESCRIPT:
        return [
            MenuAction("TRY_CATCH", "1: try / catch", "Bloque try-catch", "SNIPPET", snippet="try {\n    \n} catch (error) {\n    console.error(error);\n}", cursor_offset_up=3, icon="flow"),
            MenuAction("RET_VAL", "2: return", "Sentencia return", "SNIPPET", snippet="return ", icon="flow"),
            MenuAction("RET_NULL", "3: return null;", "Retorno null", "SNIPPET", snippet="return null;", icon="flow"),
            MenuAction("RET_TRUE", "4: return true;", "Retorno booleano true", "SNIPPET", snippet="return true;", icon="flow"),
            create_pause_action("5"),
            MenuAction("RET_FALSE", "6: return false;", "Retorno booleano false", "SNIPPET", snippet="return false;", icon="flow"),
            create_back_action("FLOW", "7"),
            MenuAction("THROW_ERR", "8: throw Error", "Lanzar error nuevo", "SNIPPET", snippet='throw new Error("");', cursor_offset_left=3, icon="flow"),
            MenuAction("RET_UNDEF", "9: return undefined;", "Retorno undefined", "SNIPPET", snippet="return undefined;", icon="flow"),
        ]
    elif lang == LANG_RUST:
        return [
            MenuAction("TRY_MATCH", "1: match res {", "Bloque match de Result", "SNIPPET", snippet="match res {\n    Ok(val) => val,\n    Err(e) => return Err(e),\n}", icon="flow"),
            MenuAction("RET_VAL", "2: return", "Sentencia return", "SNIPPET", snippet="return ", icon="flow"),
            MenuAction("RET_OK", "3: Ok(())", "Resultado Ok unit", "SNIPPET", snippet="Ok(())", icon="flow"),
            MenuAction("RET_TRUE", "4: return true;", "Retorno bool true", "SNIPPET", snippet="return true;", icon="flow"),
            create_pause_action("5"),
            MenuAction("RET_FALSE", "6: return false;", "Retorno bool false", "SNIPPET", snippet="return false;", icon="flow"),
            create_back_action("FLOW", "7"),
            MenuAction("RAISE_PANIC", "8: panic!()", "Pánico crítico", "SNIPPET", snippet='panic!("");', cursor_offset_left=3, icon="flow"),
            MenuAction("PROPAGATE_Q", "9: ?", "Operador propagate ?", "SNIPPET", snippet="?", icon="operators"),
        ]
    elif lang == LANG_CPP:
        return [
            MenuAction("TRY_CATCH", "1: try / catch", "Bloque try-catch", "SNIPPET", snippet="try {\n    \n} catch (const std::exception& e) {\n    std::cerr << e.what() << std::endl;\n}", cursor_offset_up=3, icon="flow"),
            MenuAction("RET_VAL", "2: return", "Sentencia return", "SNIPPET", snippet="return ", icon="flow"),
            MenuAction("RET_NULLPTR", "3: return nullptr;", "Retorno puntero nulo", "SNIPPET", snippet="return nullptr;", icon="flow"),
            MenuAction("RET_TRUE", "4: return true;", "Retorno bool true", "SNIPPET", snippet="return true;", icon="flow"),
            create_pause_action("5"),
            MenuAction("RET_FALSE", "6: return false;", "Retorno bool false", "SNIPPET", snippet="return false;", icon="flow"),
            create_back_action("FLOW", "7"),
            MenuAction("THROW_ERR", "8: throw runtime_error", "Lanzar std::runtime_error", "SNIPPET", snippet='throw std::runtime_error("");', cursor_offset_left=3, icon="flow"),
            MenuAction("BREAK_STMT", "9: break;", "Sentencia break", "SNIPPET", snippet="break;", icon="flow"),
        ]
    elif lang == LANG_GO:
        return [
            MenuAction("IF_ERR", "1: if err != nil", "Comprobar error", "SNIPPET", snippet="if err != nil {\n    return err\n}", icon="flow"),
            MenuAction("RET_VAL", "2: return", "Sentencia return", "SNIPPET", snippet="return ", icon="flow"),
            MenuAction("RET_NIL", "3: return nil", "Retorno nil", "SNIPPET", snippet="return nil", icon="flow"),
            MenuAction("RET_TRUE", "4: return true", "Retorno bool true", "SNIPPET", snippet="return true", icon="flow"),
            create_pause_action("5"),
            MenuAction("RET_FALSE", "6: return false", "Retorno bool false", "SNIPPET", snippet="return false", icon="flow"),
            create_back_action("FLOW", "7"),
            MenuAction("RAISE_PANIC", "8: panic()", "Llamada panic", "SNIPPET", snippet='panic("")', cursor_offset_left=2, icon="flow"),
            MenuAction("DEFER_STMT", "9: defer", "Sentencia defer", "SNIPPET", snippet="defer ", icon="flow"),
        ]
    else:  # PYTHON
        return [
            MenuAction(id="TRY_EXCEPT", label="1: try / except", hint="Bloque try-except", action_type="SNIPPET", snippet="try:\n    \nexcept Exception as e:\n    ", cursor_offset_up=2, icon="flow"),
            MenuAction(id="RET_VAL", label="2: return", hint="Retorno con espacio", action_type="SNIPPET", snippet="return ", icon="flow"),
            MenuAction(id="RET_NONE", label="3: return None", hint="Retorno nulo", action_type="SNIPPET", snippet="return None", icon="flow"),
            MenuAction(id="RET_TRUE", label="4: return True", hint="Retorno booleano True", action_type="SNIPPET", snippet="return True", icon="flow"),
            create_pause_action("5"),
            MenuAction(id="RET_FALSE", label="6: return False", hint="Retorno booleano False", action_type="SNIPPET", snippet="return False", icon="flow"),
            create_back_action("FLOW", "7"),
            MenuAction(id="RAISE_EXC", label="8: raise Exception", hint="Lanzar excepción", action_type="SNIPPET", snippet='raise Exception("")', cursor_offset_left=2, icon="flow"),
            MenuAction(id="PASS_STMT", label="9: pass", hint="Sentencia pass", action_type="SNIPPET", snippet="pass", icon="flow"),
        ]


def _build_struct_items(lang: str) -> List[MenuAction]:
    """Builds the 9 items for the STRUCT submenu for the specified language."""
    if lang == LANG_TYPESCRIPT:
        return [
            MenuAction("STRUCT_DEF", "1: function () {", "Declaración de función", "SNIPPET", snippet="function () {\n    \n}", cursor_offset_up=1, cursor_offset_left=5, icon="function"),
            MenuAction("STRUCT_CLASS", "2: class Name {", "Definición de clase", "SNIPPET", snippet="class  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="function"),
            MenuAction("STRUCT_IMPORT_SUB", "3: IMPORTAR", "import, export", "SUBMENU", submenu_id="STRUCT_IMPORT", icon="function"),
            MenuAction("STRUCT_ARROW", "4: const fn = () =>", "Función flecha", "SNIPPET", snippet="const  = () => {\n    \n};", cursor_offset_up=1, cursor_offset_left=12, icon="function"),
            create_pause_action("5"),
            MenuAction("STRUCT_PRINT", "6: console.log()", "Imprimir por consola", "SNIPPET", snippet="console.log();", cursor_offset_left=2, icon="function"),
            create_back_action("ROOT", "7"),
            MenuAction("STRUCT_LEN", "8: .length", "Propiedad de longitud", "SNIPPET", snippet=".length", icon="function"),
            MenuAction("STRUCT_IFACE", "9: interface Name {", "Definición de interfaz", "SNIPPET", snippet="interface  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="function"),
        ]
    elif lang == LANG_RUST:
        return [
            MenuAction("STRUCT_DEF", "1: fn name() -> {", "Definición de función", "SNIPPET", snippet="fn () {\n    \n}", cursor_offset_up=1, cursor_offset_left=5, icon="function"),
            MenuAction("STRUCT_CLASS", "2: struct Name {", "Definición de struct", "SNIPPET", snippet="struct  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="function"),
            MenuAction("STRUCT_IMPORT_SUB", "3: IMPORTAR", "use, pub use, mod", "SUBMENU", submenu_id="STRUCT_IMPORT", icon="function"),
            MenuAction("STRUCT_IMPL", "4: impl Name {", "Bloque de implementación", "SNIPPET", snippet="impl  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="function"),
            create_pause_action("5"),
            MenuAction("STRUCT_PRINT", "6: println!()", "Macro de impresión", "SNIPPET", snippet='println!("{}", );', cursor_offset_left=3, icon="function"),
            create_back_action("ROOT", "7"),
            MenuAction("STRUCT_LEN", "8: .len()", "Longitud de colección", "SNIPPET", snippet=".len()", icon="function"),
            MenuAction("STRUCT_PUB_FN", "9: pub fn", "Función pública", "SNIPPET", snippet="pub fn () {\n    \n}", cursor_offset_up=1, cursor_offset_left=5, icon="function"),
        ]
    elif lang == LANG_CPP:
        return [
            MenuAction("STRUCT_DEF", "1: void func() {", "Definición de función", "SNIPPET", snippet="void () {\n    \n}", cursor_offset_up=1, cursor_offset_left=5, icon="function"),
            MenuAction("STRUCT_CLASS", "2: class Name {", "Definición de clase", "SNIPPET", snippet="class  {\npublic:\n    \n};", cursor_offset_up=1, cursor_offset_left=12, icon="function"),
            MenuAction("STRUCT_IMPORT_SUB", "3: IMPORTAR", "#include, using", "SUBMENU", submenu_id="STRUCT_IMPORT", icon="function"),
            MenuAction("STRUCT_STRUCT", "4: struct Name {", "Definición de estructura", "SNIPPET", snippet="struct  {\n    \n};", cursor_offset_up=1, cursor_offset_left=5, icon="function"),
            create_pause_action("5"),
            MenuAction("STRUCT_PRINT", "6: std::cout <<", "Impresión en stream", "SNIPPET", snippet="std::cout <<  << std::endl;", cursor_offset_left=14, icon="function"),
            create_back_action("ROOT", "7"),
            MenuAction("STRUCT_LEN", "8: .size()", "Tamaño de contenedor", "SNIPPET", snippet=".size()", icon="function"),
            MenuAction("STRUCT_TEMPLATE", "9: template<typename T>", "Plantilla genérica", "SNIPPET", snippet="template<typename T>\n", icon="function"),
        ]
    elif lang == LANG_GO:
        return [
            MenuAction("STRUCT_DEF", "1: func name() {", "Definición de función", "SNIPPET", snippet="func () {\n    \n}", cursor_offset_up=1, cursor_offset_left=5, icon="function"),
            MenuAction("STRUCT_CLASS", "2: type S struct {", "Definición de struct", "SNIPPET", snippet="type  struct {\n    \n}", cursor_offset_up=1, cursor_offset_left=11, icon="function"),
            MenuAction("STRUCT_IMPORT_SUB", "3: IMPORTAR", "import packages", "SUBMENU", submenu_id="STRUCT_IMPORT", icon="function"),
            MenuAction("STRUCT_METHOD", "4: func (s *T) m()", "Método con receptor", "SNIPPET", snippet="func (s *) () {\n    \n}", cursor_offset_up=1, cursor_offset_left=11, icon="function"),
            create_pause_action("5"),
            MenuAction("STRUCT_PRINT", "6: fmt.Println()", "Impresión en consola", "SNIPPET", snippet="fmt.Println()", cursor_offset_left=1, icon="function"),
            create_back_action("ROOT", "7"),
            MenuAction("STRUCT_LEN", "8: len()", "Función built-in len", "SNIPPET", snippet="len()", cursor_offset_left=1, icon="function"),
            MenuAction("STRUCT_IFACE", "9: type I interface", "Definición de interfaz", "SNIPPET", snippet="type  interface {\n    \n}", cursor_offset_up=1, cursor_offset_left=14, icon="function"),
        ]
    else:  # PYTHON
        return [
            MenuAction(id="STRUCT_DEF", label="1: def func():", hint="Definición de función", action_type="SNIPPET", snippet="def ():", cursor_offset_left=3, icon="function"),
            MenuAction(id="STRUCT_CLASS", label="2: class Nombre:", hint="Definición de clase", action_type="SNIPPET", snippet="class :", cursor_offset_left=1, icon="function"),
            MenuAction(id="STRUCT_IMPORT_SUB", label="3: IMPORTAR", hint="import, from ... import", action_type="SUBMENU", submenu_id="STRUCT_IMPORT", icon="function"),
            MenuAction(id="STRUCT_LAMBDA", label="4: lambda", hint="Función anónima", action_type="SNIPPET", snippet="lambda : ", cursor_offset_left=2, icon="function"),
            create_pause_action("5"),
            MenuAction(id="STRUCT_PRINT", label="6: print()", hint="Impresión por consola", action_type="SNIPPET", snippet="print()", cursor_offset_left=1, icon="function"),
            create_back_action("ROOT", "7"),
            MenuAction(id="STRUCT_LEN", label="8: len()", hint="Longitud de contenedor", action_type="SNIPPET", snippet="len()", cursor_offset_left=1, icon="function"),
            MenuAction(id="STRUCT_SUPER", label="9: super().__init__()", hint="Constructor clase padre", action_type="SNIPPET", snippet="super().__init__()", icon="function"),
        ]


def _build_struct_import_items(lang: str) -> List[MenuAction]:
    """Builds the 9 items for the STRUCT_IMPORT submenu for the specified language."""
    if lang == LANG_TYPESCRIPT:
        return [
            MenuAction("IMP_NAMED", "1: import { } from", "Import nombrado", "SNIPPET", snippet='import {  } from "";', cursor_offset_left=11, icon="function"),
            MenuAction("IMP_ALL_AS", "2: import * as", "Import de namespace", "SNIPPET", snippet='import * as  from "";', cursor_offset_left=10, icon="function"),
            MenuAction("IMP_DEF", "3: import default", "Import por defecto", "SNIPPET", snippet='import  from "";', cursor_offset_left=10, icon="function"),
            MenuAction("EXP_CONST", "4: export const", "Exportación de constante", "SNIPPET", snippet="export const ", icon="function"),
            create_pause_action("5"),
            MenuAction("EXP_DEF", "6: export default", "Exportación por defecto", "SNIPPET", snippet="export default ", icon="function"),
            create_back_action("STRUCT", "7"),
            MenuAction("IMP_TYPE", "8: import type { }", "Import solo de tipos", "SNIPPET", snippet='import type {  } from "";', cursor_offset_left=11, icon="function"),
            MenuAction("EXP_NAMED", "9: export { }", "Exportación nombrada", "SNIPPET", snippet="export {  };", cursor_offset_left=3, icon="function"),
        ]
    elif lang == LANG_RUST:
        return [
            MenuAction("IMP_USE_STD", "1: use std::", "Import estándar", "SNIPPET", snippet="use std::;", cursor_offset_left=1, icon="function"),
            MenuAction("IMP_USE_CRATE", "2: use crate::", "Import local de crate", "SNIPPET", snippet="use crate::;", cursor_offset_left=1, icon="function"),
            MenuAction("IMP_PUB_USE", "3: pub use", "Re-exportación pública", "SNIPPET", snippet="pub use ;", cursor_offset_left=1, icon="function"),
            MenuAction("IMP_MOD", "4: mod name;", "Declaración de módulo", "SNIPPET", snippet="mod ;", cursor_offset_left=1, icon="function"),
            create_pause_action("5"),
            MenuAction("IMP_COLLECTIONS", "6: use collections::", "Estructuras de datos", "SNIPPET", snippet="use std::collections::;", cursor_offset_left=1, icon="function"),
            create_back_action("STRUCT", "7"),
            MenuAction("IMP_SYNC", "8: use sync::{Arc, Mutex}", "Primitivas de concurrencia", "SNIPPET", snippet="use std::sync::{Arc, Mutex};\n", icon="function"),
            MenuAction("IMP_EXTERN", "9: extern crate", "Crate externa", "SNIPPET", snippet="extern crate ;", cursor_offset_left=1, icon="function"),
        ]
    elif lang == LANG_CPP:
        return [
            MenuAction("INC_IOSTREAM", "1: #include <iostream>", "Stream de E/S estándar", "SNIPPET", snippet="#include <iostream>\n", icon="function"),
            MenuAction("INC_VECTOR", "2: #include <vector>", "Contenedor vector", "SNIPPET", snippet="#include <vector>\n", icon="function"),
            MenuAction("INC_STRING", "3: #include <string>", "Clase std::string", "SNIPPET", snippet="#include <string>\n", icon="function"),
            MenuAction("INC_MEMORY", "4: #include <memory>", "Punteros inteligentes", "SNIPPET", snippet="#include <memory>\n", icon="function"),
            create_pause_action("5"),
            MenuAction("INC_USING_STD", "6: using namespace std;", "Namespace estándar", "SNIPPET", snippet="using namespace std;\n", icon="function"),
            create_back_action("STRUCT", "7"),
            MenuAction("INC_LOCAL", '8: #include ""', "Header local", "SNIPPET", snippet='#include ""\n', cursor_offset_left=2, icon="function"),
            MenuAction("INC_PRAGMA", "9: #pragma once", "Guarda de inclusión única", "SNIPPET", snippet="#pragma once\n", icon="function"),
        ]
    elif lang == LANG_GO:
        return [
            MenuAction("IMP_FMT", '1: import "fmt"', "Paquete de formateo", "SNIPPET", snippet='import "fmt"\n', icon="function"),
            MenuAction("IMP_OS", '2: import "os"', "Paquete de sistema operativo", "SNIPPET", snippet='import "os"\n', icon="function"),
            MenuAction("IMP_SYNC", '3: import "sync"', "Paquete de sincronización", "SNIPPET", snippet='import "sync"\n', icon="function"),
            MenuAction("IMP_TIME", '4: import "time"', "Paquete de tiempo y reloj", "SNIPPET", snippet='import "time"\n', icon="function"),
            create_pause_action("5"),
            MenuAction("IMP_HTTP", '6: import "net/http"', "Cliente y servidor HTTP", "SNIPPET", snippet='import "net/http"\n', icon="function"),
            create_back_action("STRUCT", "7"),
            MenuAction("IMP_JSON", '8: import "encoding/json"', "Serialización JSON", "SNIPPET", snippet='import "encoding/json"\n', icon="function"),
            MenuAction("IMP_MULTI", "9: import ( ... )", "Bloque múltiple de imports", "SNIPPET", snippet='import (\n    ""\n)', cursor_offset_up=1, cursor_offset_left=2, icon="function"),
        ]
    else:  # PYTHON
        return [
            MenuAction(id="IMP_DIRECT", label="1: import", hint="Sentencia import", action_type="SNIPPET", snippet="import ", icon="function"),
            MenuAction(id="IMP_FROM", label="2: from ... import", hint="Importación selectiva", action_type="SNIPPET", snippet="from  import ", cursor_offset_left=8, icon="function"),
            MenuAction(id="IMP_SYS_OS", label="3: import sys, os", hint="Imports del sistema", action_type="SNIPPET", snippet="import sys, os\n", icon="function"),
            MenuAction(id="IMP_NUMPY", label="4: import numpy as np", hint="Import numpy", action_type="SNIPPET", snippet="import numpy as np\n", icon="function"),
            create_pause_action("5"),
            MenuAction(id="IMP_AS", label="6:  as", hint="Alias de módulo", action_type="SNIPPET", snippet=" as ", icon="function"),
            create_back_action("STRUCT", "7"),
            MenuAction(id="IMP_TYPING", label="8: from typing import", hint="Tipado estático", action_type="SNIPPET", snippet="from typing import ", icon="function"),
            MenuAction(id="IMP_ALL", label="9: __all__ = []", hint="Exports públicos", action_type="SNIPPET", snippet="__all__ = []", cursor_offset_left=1, icon="function"),
        ]


def _build_op_items(lang: str) -> List[MenuAction]:
    """Builds the 9 items for the OPERATORS submenu for the specified language."""
    if lang == LANG_GO:
        slot_0 = MenuAction("OP_ASSIGN_SHORT", "1: :=", "Asignación corta", "SNIPPET", snippet=" := ", icon="operators")
    else:
        slot_0 = MenuAction("OP_ASSIGN", "1: =", "Asignación", "SNIPPET", snippet=" = ", icon="operators")

    if lang == LANG_TYPESCRIPT:
        slot_1 = MenuAction("OP_EQ_STRICT", "2: ===", "Igualdad estricta", "SNIPPET", snippet=" === ", icon="operators")
        slot_2 = MenuAction("OP_NEQ_STRICT", "3: !==", "Desigualdad estricta", "SNIPPET", snippet=" !== ", icon="operators")
        slot_5 = MenuAction("OP_LOGICAL_SUB", "6: && / ||", "Operadores lógicos", "SUBMENU", submenu_id="OP_LOGICAL", icon="operators")
    else:
        slot_1 = MenuAction("OP_EQ", "2: ==", "Comparación igualdad", "SNIPPET", snippet=" == ", icon="operators")
        slot_2 = MenuAction("OP_NEQ", "3: !=", "Comparación desigualdad", "SNIPPET", snippet=" != ", icon="operators")
        if lang == LANG_PYTHON:
            slot_5 = MenuAction("OP_LOGICAL_SUB", "6: and / or", "Operadores lógicos", "SUBMENU", submenu_id="OP_LOGICAL", icon="operators")
        else:
            slot_5 = MenuAction("OP_LOGICAL_SUB", "6: && / ||", "Operadores lógicos", "SUBMENU", submenu_id="OP_LOGICAL", icon="operators")

    slot_3 = MenuAction("OP_PLUSEQ", "4: +=", "Suma acumulativa", "SNIPPET", snippet=" += ", icon="operators")
    pause_slot = create_pause_action("5")
    back_slot = create_back_action("ROOT", "7")
    slot_7 = MenuAction("OP_DELIMITERS_SUB", '8: () [] {} / ""', "Delimitadores y cadenas", "SUBMENU", submenu_id="OP_DELIMITERS", icon="operators")
    slot_8 = MenuAction("OP_PUNCT_SUB", "9: : / , / . / ;", "Puntuación y acceso", "SUBMENU", submenu_id="OP_PUNCT", icon="operators")

    return [slot_0, slot_1, slot_2, slot_3, pause_slot, slot_5, back_slot, slot_7, slot_8]


def _build_op_logical_items(lang: str) -> List[MenuAction]:
    """Builds the 9 items for the OP_LOGICAL submenu for the specified language."""
    pause_slot = create_pause_action("5")
    back_slot = create_back_action("OPERATORS", "7")

    if lang == LANG_PYTHON:
        return [
            MenuAction("OP_AND", "1: and", "Lógico AND", "SNIPPET", snippet=" and ", icon="operators"),
            MenuAction("OP_OR", "2: or", "Lógico OR", "SNIPPET", snippet=" or ", icon="operators"),
            MenuAction("OP_NOT", "3: not", "Lógico NOT", "SNIPPET", snippet="not ", icon="operators"),
            MenuAction("OP_IN", "4: in", "Pertenencia in", "SNIPPET", snippet=" in ", icon="operators"),
            pause_slot,
            MenuAction("OP_IS", "6: is", "Identidad is", "SNIPPET", snippet=" is ", icon="operators"),
            back_slot,
            MenuAction("OP_IS_NOT", "8: is not", "Identidad no es", "SNIPPET", snippet=" is not ", icon="operators"),
            MenuAction("OP_NOT_IN", "9: not in", "No pertenencia", "SNIPPET", snippet=" not in ", icon="operators"),
        ]
    elif lang == LANG_TYPESCRIPT:
        return [
            MenuAction("OP_AND", "1: &&", "Lógico Y", "SNIPPET", snippet=" && ", icon="operators"),
            MenuAction("OP_OR", "2: ||", "Lógico O", "SNIPPET", snippet=" || ", icon="operators"),
            MenuAction("OP_NOT", "3: !", "Negación lógica", "SNIPPET", snippet="!", icon="operators"),
            MenuAction("OP_TYPEOF", "4: typeof", "Comprobación de tipo", "SNIPPET", snippet="typeof ", icon="operators"),
            pause_slot,
            MenuAction("OP_INSTANCEOF", "6: instanceof", "Instancia de clase", "SNIPPET", snippet=" instanceof ", icon="operators"),
            back_slot,
            MenuAction("OP_NULLISH", "8: ??", "Coalescencia nula", "SNIPPET", snippet=" ?? ", icon="operators"),
            MenuAction("OP_TERNARY", "9: ? :", "Operador ternario", "SNIPPET", snippet=" ?  : ", cursor_offset_left=3, icon="operators"),
        ]
    else:  # RUST, CPP, GO
        return [
            MenuAction("OP_AND", "1: &&", "Lógico Y", "SNIPPET", snippet=" && ", icon="operators"),
            MenuAction("OP_OR", "2: ||", "Lógico O", "SNIPPET", snippet=" || ", icon="operators"),
            MenuAction("OP_NOT", "3: !", "Negación lógica", "SNIPPET", snippet="!", icon="operators"),
            MenuAction("OP_LT", "4: <", "Menor que", "SNIPPET", snippet=" < ", icon="operators"),
            pause_slot,
            MenuAction("OP_GT", "6: >", "Mayor que", "SNIPPET", snippet=" > ", icon="operators"),
            back_slot,
            MenuAction("OP_LTE", "8: <=", "Menor o igual", "SNIPPET", snippet=" <= ", icon="operators"),
            MenuAction("OP_GTE", "9: >=", "Mayor o igual", "SNIPPET", snippet=" >= ", icon="operators"),
        ]


def _build_op_delim_items(lang: str) -> List[MenuAction]:
    """Builds the 9 items for the OP_DELIMITERS submenu for the specified language."""
    pause_slot = create_pause_action("5")
    back_slot = create_back_action("OPERATORS", "7")

    p0 = MenuAction("DELIM_PAREN", "1: ()", "Paréntesis con cursor tras el cierre", "SNIPPET", snippet="()", cursor_offset_left=0, icon="operators")
    p1 = MenuAction("DELIM_BRACKET", "2: []", "Corchetes con cursor centrado", "SNIPPET", snippet="[]", cursor_offset_left=1, icon="operators")
    p2 = MenuAction("DELIM_BRACE", "3: {}", "Llaves con cursor centrado", "SNIPPET", snippet="{}", cursor_offset_left=1, icon="operators")
    p3 = MenuAction("DELIM_DQUOTE", '4: ""', "Comillas dobles centradas", "SNIPPET", snippet='""', cursor_offset_left=1, icon="operators")
    p5 = MenuAction("DELIM_SQUOTE", "6: ''", "Comillas simples centradas", "SNIPPET", snippet="''", cursor_offset_left=1, icon="operators")

    if lang == LANG_PYTHON:
        p7 = MenuAction("DELIM_FSTR", '8: f""', "F-string con cursor centrado", "SNIPPET", snippet='f""', cursor_offset_left=1, icon="operators")
        p8 = MenuAction("DELIM_DOCSTR", '9: """..."""', "Docstring triple centrado", "SNIPPET", snippet='""""""', cursor_offset_left=3, icon="operators")
    elif lang == LANG_TYPESCRIPT:
        p7 = MenuAction("DELIM_BQUOTE", "8: ``", "Template literal centrado", "SNIPPET", snippet="``", cursor_offset_left=1, icon="operators")
        p8 = MenuAction("DELIM_INTERP", "9: ${}", "Interpolación de template", "SNIPPET", snippet="${}", cursor_offset_left=1, icon="operators")
    elif lang == LANG_RUST:
        p7 = MenuAction("DELIM_REF", "8: &", "Préstamo / referencia", "SNIPPET", snippet="&", icon="operators")
        p8 = MenuAction("DELIM_RAWSTR", '9: r#""#', "String cruda", "SNIPPET", snippet='r#""#', cursor_offset_left=2, icon="operators")
    elif lang == LANG_CPP:
        p7 = MenuAction("DELIM_DEREF", "8: *", "Puntero / desreferencia", "SNIPPET", snippet="*", icon="operators")
        p8 = MenuAction("DELIM_ARROW", "9: ->", "Acceso a miembro por puntero", "SNIPPET", snippet="->", icon="operators")
    elif lang == LANG_GO:
        p7 = MenuAction("DELIM_RAWSTR", "8: ``", "String multilínea cruda", "SNIPPET", snippet="``", cursor_offset_left=1, icon="operators")
        p8 = MenuAction("DELIM_CHAN", "9: <-", "Envío / recepción de canal", "SNIPPET", snippet="<-", icon="operators")
    else:
        p7 = MenuAction("DELIM_FSTR", '8: f""', "F-string", "SNIPPET", snippet='f""', cursor_offset_left=1, icon="operators")
        p8 = MenuAction("DELIM_DOCSTR", '9: """..."""', "Docstring", "SNIPPET", snippet='""""""', cursor_offset_left=3, icon="operators")

    return [p0, p1, p2, p3, pause_slot, p5, back_slot, p7, p8]


def _build_op_punct_items(lang: str) -> List[MenuAction]:
    """Builds the 9 items for the OP_PUNCT submenu for the specified language."""
    pause_slot = create_pause_action("5")
    back_slot = create_back_action("OPERATORS", "7")

    p0 = MenuAction("PUNCT_COLON", "1: :", "Dos puntos con espacio", "SNIPPET", snippet=": ", icon="operators")
    p1 = MenuAction("PUNCT_COMMA", "2: ,", "Coma con espacio", "SNIPPET", snippet=", ", icon="operators")
    p2 = MenuAction("PUNCT_DOT", "3: .", "Punto de acceso", "SNIPPET", snippet=".", icon="operators")
    p3 = MenuAction("PUNCT_ARROW", "4: ->", "Retorno o puntero flecha", "SNIPPET", snippet=" -> ", icon="operators")
    p5 = MenuAction("PUNCT_UNDERSCORE", "6: _", "Guion bajo / variable muda", "SNIPPET", snippet="_", icon="operators")
    p7 = MenuAction("PUNCT_SEMICOLON", "8: ;", "Punto y coma", "SNIPPET", snippet=";", icon="operators")

    if lang in (LANG_RUST, LANG_CPP):
        p8 = MenuAction("PUNCT_SCOPE", "9: ::", "Resolución de ámbito", "SNIPPET", snippet="::", icon="operators")
    elif lang == LANG_GO:
        p8 = MenuAction("PUNCT_CHAN_ARROW", "9: <-", "Operador de canal", "SNIPPET", snippet=" <- ", icon="operators")
    else:
        p8 = MenuAction("PUNCT_SCOPE", "9: ::", "Resolución de ámbito", "SNIPPET", snippet="::", icon="operators")

    return [p0, p1, p2, p3, pause_slot, p5, back_slot, p7, p8]
