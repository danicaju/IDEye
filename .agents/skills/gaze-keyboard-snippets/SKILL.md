---
name: gaze-keyboard-snippets
description: >-
  Use this skill when designing, implementing, or optimizing gaze-controlled on-screen keyboards, syntax symbol layouts, predictive token suggestions, and code snippet expansion systems.
---

# Teclado Virtual para Mirada, Sugerencias Predictivas y Snippets

Escribir código con los ojos requiere una interfaz de entrada especializada donde los operadores y símbolos de programación no estén escondidos tras múltiples submenús.

---

## 1. Diseño del Teclado Virtual Especializado para Programación

### Distribución de Superficie y Zonas
El teclado virtual para mirada (`IDEye GazeBoard`) se divide en tres bloques ergonómicos accesibles:

1. **Bloque Alfanumérico Central**:
   * Letras con espaciado amplio y tolerancia a desviación (histeresis).
   * Teclas de borrado rápido (`Backspace` de carácter y `Delete Word`).
2. **Bloque de Sintaxis y Operadores Inmediatos (Lateral)**:
   * Acceso directo en primera capa a los símbolos más usados en programación sin requerir tecla Shift:
     * `{ }` y `( )` y `[ ]`
     * `;` y `:`
     * `=` y `==` y `!=`
     * `=>` y `->`
     * `"` y `'` y `` ` ``
     * `.` y `,`
     * `&&` y `||`
3. **Barra de Predicción Inteligente y Autocompletado (Superior)**:
   * 4 o 5 celdas de gran tamaño (mínimo 120 x 50 px) con las palabras o identificadores más probables calculados en tiempo real por el LSP o modelo de lenguaje.

---

## 2. Mecánica de Inserción y Auto-Cierre de Pares

* **Inserción de Delimitadores con Cursor Central**:
  * Al activar `{` por dwell, se inserta automáticamente `{}` y el cursor se posiciona internamente en el espacio central.
  * Al activar `(` se inserta `()`.
  * Al activar `"` se inserta `""`.
* **Inserción de Punto y Coma Rápido**:
  * Un botón de "Fin de Línea + `;`" que añade el punto y coma al final de la sentencia actual sin importar dónde esté el cursor y salta a la siguiente línea indentada.

---

## 3. Biblioteca de Plantillas y Expansión de Snippets Asistivos

La forma más rápida de generar código mediante la mirada es la expansión de plantillas semánticas:

### Ejemplos de Disparadores por Dwell Único:
* **Snippet `func` / `def`**:
  * Inserta la estructura completa de definición de función con marcadores de posición navegables (`TabStops`).
  * El usuario salta de un marcador al siguiente fijando la mirada en el botón de navegación "Siguiente Parámetro".
* **Snippet `for-loop` / `iter`**:
  * Inserta bucle estándar parametrizado según el lenguaje del archivo.
* **Snippet `try-catch` / `try-except`**:
  * Inserta bloque de captura de excepciones e indentación lista para editar.
* **Comandos de Control de Versiones y Terminal**:
  * Celdas dedicadas para: `git status`, `git add .`, `git commit -m "..."`, `npm test`, `python main.py`.

---

## 4. Chips Predictivos con Inteligencia Artificial (LLM Completion Chips)

Para evitar la fatiga motora:
1. Conforme el usuario escribe o navega por el código, el modelo contextual analiza el archivo y genera las **3 continuaciones de código más probables**.
2. Cada continuación se presenta como un "Chip Predictivo" de 150px de ancho en la parte superior del teclado.
3. El usuario simplemente mira el chip durante 350 ms:
   * La expresión o línea completa se inserta de golpe.
   * Aumenta la velocidad de codificación de ~8 WPM a más de 35-45 WPM efectivos.
