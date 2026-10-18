---
name: ast-structural-coding
description: >-
  Use this skill when implementing structural code navigation, AST-based selection (Tree-sitter, LSP), semantic token hopping, and block-level code manipulation designed for eye-controlled programming.
---

# Navegación y Edición Estructural de Código Basada en AST

El tecleo carácter por carácter mediante la mirada es un cuello de botella físico y cognitivo. Esta habilidad establece la arquitectura para **programar a nivel de árbol de sintaxis abstracta (AST)**, permitiendo manipular bloques completos de código con un número mínimo de fijaciones oculares.

---

## 1. Principio Fundamental: De Caracteres a Nodos Semánticos

En lugar de requerir que el usuario apunte con los ojos a una columna y línea específica:
1. La mirada se posa en cualquier lugar dentro de una línea o expresión.
2. El analizador AST (Tree-sitter o cliente LSP) detecta el **nodo sintáctico más cercano o envolvente**:
   * Identificador / Variable
   * Expresión binaria
   * Declaración de función o método
   * Sentencia de control (`if`, `for`, `while`, `match`)
   * Bloque léxico / Alcance (Scope)

---

## 2. Acciones Estructurales Directas por Dwell

Al fijar la mirada sobre un nodo sintáctico y seleccionar la paleta contextual de acciones semánticas:

### Acciones de Alcance (Scope Navigation):
* **Expandir Selección (`Grow Selection`)**: Sube un nivel en el AST (e.g., de la variable `x` a `x + y`, luego al `return x + y;`, luego a la función `calculate()`).
* **Contraer Selección (`Shrink Selection`)**: Baja al nodo hijo donde se originó la selección.
* **Saltar al Hermano Siguiente/Anterior (`Next/Prev Sibling`)**: Salta de parámetro en parámetro, o de sentencia en sentencia en una sola fijación.

### Transformaciones Estructurales Comunes:
* **Envolver (Wrap)**: Envolver el nodo seleccionado en `if (...)`, `try { ... } catch`, `while (...)`.
* **Extraer (Extract)**: Extraer expresión a variable local o función auxiliar.
* **Intercambiar (Swap)**: Invertir el orden de dos parámetros en una llamada de función o dos sentencias consecutivas.
* **Eliminar Bloque (Delete Node)**: Eliminar de forma limpia la función o declaración completa preservando la indentación sintáctica correcta.
* **Duplicar (Duplicate)**: Clona el nodo sintáctico actual debajo del actual.

---

## 3. Integración con Tree-sitter

Para soportar múltiples lenguajes de programación (Python, TypeScript, JavaScript, Rust, C++, Go) con análisis incremental de alta velocidad:

```javascript
// Ejemplo conceptual de resolución de nodo AST bajo la mirada
const Parser = require('tree-sitter');
const JavaScript = require('tree-sitter-javascript');

const parser = new Parser();
parser.setLanguage(JavaScript);

function getNodeAtGaze(sourceCode, cursorLine, cursorColumn) {
  const tree = parser.parse(sourceCode);
  const point = { row: cursorLine, column: cursorColumn };
  
  // Buscar el nodo más profundo en el punto de mirada
  let node = tree.rootNode.descendantForPosition(point);
  
  // Si es un token trivial o espacio en blanco, resolver el ancestro de interés
  while (node && ['(', ')', '{', '}', ';', ','].includes(node.type)) {
    node = node.parent;
  }
  
  return {
    type: node.type,
    text: node.text,
    range: {
      start: node.startPosition,
      end: node.endPosition
    },
    parentType: node.parent ? node.parent.type : null
  };
}
```

---

## 4. Integración con Language Server Protocol (LSP)

IDEye debe comunicarse con servidores LSP nativos (e.g., `pyright`, `typescript-language-server`, `rust-analyzer`):
* `textDocument/definition`: Salto directo a la definición fijando la mirada en un símbolo.
* `textDocument/references`: Visualización de referencias en un menú radial de objetivos grandes.
* `textDocument/completion`: Proveer los 3 o 4 autocompletados más probables en botones gaze-friendly de al menos 70px.
* `textDocument/codeAction`: Ejecutar correcciones rápidas (quick fixes) y refactorizaciones en un clic ocular.
