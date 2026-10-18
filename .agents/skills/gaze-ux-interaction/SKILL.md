---
name: gaze-ux-interaction
description: >-
  Use this skill when designing, building, or styling user interfaces and interaction models specifically for eye tracking, dwell-time triggers, Midas Touch prevention, zoom grids, and resting zones.
---

# Diseño de Interacción y Experiencia de Usuario Controlada por Ojos (Gaze UX)

Esta guía define las reglas de diseño ergonómico e interactivo para la interfaz de usuario de `IDEye`.

---

## 1. Prevención del Problema del Toque de Midas (Midas Touch)

Los ojos son receptores de información continua. Sin un protocolo estricto, cualquier exploración visual dispararía acciones no deseadas.

### Reglas de Diseño Obligatorias:
1. **Activación por Dwell Progresivo**:
   * Ningún botón responde a un simple `hover`.
   * El usuario debe mantener la mirada dentro de los límites del elemento durante un tiempo umbral $T_{\text{dwell}}$ (por defecto 400 ms, ajustable entre 250 ms y 800 ms).
   * **Feedback Visual Inmediato**: Un anillo de progreso circular SVG (`stroke-dasharray` / `stroke-dashoffset`) se llena progresivamente sobre el objetivo mientras la mirada permanece fija.
   * Si la mirada sale del objetivo antes de completar el $100\%$, el progreso se reinicia instantáneamente a cero sin penalización.

2. **Zonas de Reposo (Resting Zones / Dead Zones)**:
   * Todo entorno de desarrollo para ojos debe incluir márgenes neutros amplios (mínimo 60px) en los bordes de pantalla o barras separadoras donde la mirada pueda descansar mientras el desarrollador lee código o reflexiona, sin riesgo de activación.

3. **Modo Pausa / Reposo Global**:
   * Un botón de fijación prolongada (o gesto de guiño) en una esquina superior fija que pone a `IDEye` en "Modo Lectura / Suspensión", desactivando todos los disparadores de dwell hasta reactivarlo explícitamente.

---

## 2. Dimensionamiento de Objetivos y Ley de Fitts para Gaze

Debido a que la fóvea humana abarca aproximadamente $1^\circ$ a $2^\circ$ de ángulo visual, y la precisión típica de seguimiento ocular con cámara web estándar ronda entre $0.8^\circ$ y $1.5^\circ$:

| Parámetro | Valor Recomendado | Justificación |
| :--- | :--- | :--- |
| **Tamaño Mínimo de Botón** | 50 x 50 px | Previene falsos positivos y fatiga de micro-puntería |
| **Tamaño Óptimo para Teclado** | 70 x 70 px | Permite tecleo ágil y seguro |
| **Separación (Gutter / Padding)** | 10 a 16 px | Previene que el temblor active el botón adyacente |
| **Tolerancia de Borde (Hysteresis)** | 15 px extras al salir | Si la mirada oscila en el borde del botón, no se cancela el dwell bruscamente |

---

## 3. Lupa Jerárquica y Cuadrícula de Zoom (Fish-Eye / Zoom Grid)

El código fuente contiene caracteres diminutos (puntos, paréntesis, comas, dos puntos) que miden menos de 15 píxeles de ancho, imposibles de seleccionar directamente con la mirada con 100% de confianza.

### Flujo de Selección en Dos Pasos (Two-Step Zoom Selection):
1. **Paso 1 (Zona Macro)**:
   * El usuario mira la región del editor donde desea posicionar el cursor.
   * Al cumplirse un dwell breve (300 ms), esa región se expande en una ventana flotante o lupa con zoom óptico $3\times$ o $4\times$.
2. **Paso 2 (Punto Micro)**:
   * Los caracteres ahora aparecen con un tamaño de 40 a 60 px cada uno.
   * El usuario fija la mirada en el carácter o token exacto (300 ms).
   * El cursor se ubica con precisión milimétrica y la lupa se cierra automáticamente.

---

## 4. Ergonomía Visual y Prevención de Fatiga

1. **Tema Oscuro con Luminancia Controlada**:
   * Fondo: `#121212` o `#18181b`.
   * Texto: `#e4e4e7` (evitar blanco puro `#ffffff` sobre negro absoluto `#000000` para reducir el efecto halo y contracción pupilar).
2. **Estabilidad de Brillo**:
   * Evitar transiciones de pantalla con destellos blancos. Los cambios bruscos de luminosidad cambian el diámetro pupilar, lo que introduce un error de deriva (drift) en el calibrador de la cámara.
3. **Pausas y Notificaciones de Descanso**:
   * Seguimiento del tiempo de uso continuo con alertas sutiles cada 20 minutos (regla 20-20-20 para descanso ocular).
