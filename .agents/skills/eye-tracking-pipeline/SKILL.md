---
name: eye-tracking-pipeline
description: >-
  Use this skill when implementing, configuring, or debugging computer vision pipelines for eye tracking, pupil and iris landmark detection (MediaPipe Face Mesh, OpenCV), gaze calibration algorithms, and real-time jitter filtering.
---

# Pipeline de Visión por Computador y Seguimiento Ocular

Esta guía contiene la arquitectura técnica, fórmulas y procedimientos para implementar el motor de seguimiento ocular en tiempo real para `IDEye`.

---

## 1. Detección de Iris y Puntos Faciales (MediaPipe / OpenCV)

### Puntos Clave de MediaPipe Face Mesh (Refined Landmarks)
MediaPipe FaceMesh con refinamiento de iris (`refine_landmarks=True`) provee 478 puntos de referencia 3D:
* **Iris Izquierdo**: Puntos `468` (centro), `469` (derecha), `470` (arriba), `471` (izquierda), `472` (abajo).
* **Iris Derecho**: Puntos `473` (centro), `474` (derecha), `475` (arriba), `476` (izquierda), `477` (abajo).
* **Contorno Ojo Izquierdo**: `33`, `160`, `158`, `133`, `153`, `144`.
* **Contorno Ojo Derecho**: `362`, `385`, `387`, `263`, `373`, `380`.

### Estimación de la Posición Pupilar Relativa
El vector de mirada inicial se normaliza calculando la posición relativa del centro del iris respecto a las comisuras del ojo:
$$\text{Ratio}_X = \frac{x_{\text{iris}} - x_{\text{comisura\_interior}}}{x_{\text{comisura\_exterior}} - x_{\text{comisura\_interior}}}$$

---

## 2. Detección de Parpadeo y Guiños (Eye Aspect Ratio - EAR)

Para evitar falsos clics provocados por parpadeos involuntarios (100–150 ms) y permitir clics intencionales (250–500 ms):

$$\text{EAR} = \frac{||p_2 - p_6|| + ||p_3 - p_5||}{2 \cdot ||p_1 - p_4||}$$

Donde $p_1, \dots, p_6$ son los vértices del contorno ocular.

### Clasificación de Eventos Oculares:
* **Ojo Abierto**: $\text{EAR} > 0.22$
* **Microparpadeo Involuntario**: $\text{EAR} < 0.18$ durante $t < 180\text{ ms}$ (ignorar para acciones de clic).
* **Parpadeo Voluntario (Clic)**: $\text{EAR} < 0.18$ sostenido durante $250\text{ ms} \le t \le 600\text{ ms}$.
* **Guiño Unilateral**: $\text{EAR}_{\text{izq}} < 0.18$ y $\text{EAR}_{\text{der}} > 0.22$ (puede mapearse a clic derecho o alternar teclado).

---

## 3. Calibración Mirada-Pantalla (Gaze Calibration)

### Calibración de 9 Puntos
El usuario fija la mirada consecutivamente en 9 puntos distribuidos en pantalla:
$$P_i = (X_i, Y_i) \quad \text{con } i \in \{1, \dots, 9\}$$

### Modelo Polinomial Cuadrático de Mapeo
Para transformar las coordenadas relativas del iris $(u, v)$ en coordenadas de pantalla $(x, y)$:
$$x = a_0 + a_1 u + a_2 v + a_3 u^2 + a_4 v^2 + a_5 u v$$
$$y = b_0 + b_1 u + b_2 v + b_3 u^2 + b_4 v^2 + b_5 u v$$

Los coeficientes $A = [a_0, \dots, a_5]^T$ y $B = [b_0, \dots, b_5]^T$ se resuelven mediante mínimos cuadrados ordinarios (Ordinary Least Squares - OLS):
$$\mathbf{W} = (\mathbf{X}^T \mathbf{X})^{-1} \mathbf{X}^T \mathbf{Y}$$

---

## 4. Reducción de Temblor: One Euro Filter (1€ Filter)

El **1€ Filter** es el estándar de la industria para seguimiento en tiempo real porque adapta dinámicamente la frecuencia de corte: alta suavización en bajas velocidades (fijación estricta sin temblor) y baja suavización en altas velocidades (sácadas instantáneas sin retraso).

### Implementación del Filtro:
```python
import math

class OneEuroFilter:
    def __init__(self, t0, x0, min_cutoff=1.0, beta=0.007, d_cutoff=1.0):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self.x_prev = float(x0)
        self.dx_prev = 0.0
        self.t_prev = float(t0)

    def smoothing_factor(self, dt, cutoff):
        r = 2 * math.pi * cutoff * dt
        return r / (r + 1)

    def filter(self, t, x):
        dt = t - self.t_prev
        if dt <= 0.0:
            return self.x_prev

        # Estimar derivada (velocidad de movimiento ocular)
        dx = (x - self.x_prev) / dt
        edx = self.smoothing_factor(dt, self.d_cutoff)
        dx_hat = edx * dx + (1 - edx) * self.dx_prev

        # Frecuencia de corte adaptativa
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = self.smoothing_factor(dt, cutoff)
        x_hat = a * x + (1 - a) * self.x_prev

        # Guardar estado
        self.x_prev = x_hat
        self.dx_prev = dx_hat
        self.t_prev = t
        return x_hat
```

---

## 5. Detección de Fijación vs Sácada (Algoritmo I-VT)

* Calcular la velocidad angular o en píxeles: $V = \frac{\Delta \text{distancia}}{\Delta t}$.
* **Si $V < 30^\circ/\text{s}$ (o umbral calibrado en px/s)**:
  * El estado es **FIJACIÓN**. Se alimenta el temporizador de dwell.
* **Si $V \ge 30^\circ/\text{s}$**:
  * El estado es **SÁCADA**. El temporizador de dwell se cancela de inmediato y el cursor se desplaza fluidamente sin disparar clics.
