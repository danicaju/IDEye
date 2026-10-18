---
name: synthetic-gaze-testing
description: >-
  Use this skill when developing automated tests, creating synthetic eye-tracking datasets, testing dwell timers and UI interactions headlessly (Puppeteer, Playwright), or benchmarking gaze filters.
---

# Pruebas Automatizadas con Mirada Sintética y Benchmarking (Synthetic Gaze Testing)

Desarrollar software para seguimiento ocular probando manualmente cada botón frente a la cámara web es lento, impreciso y agotador. Esta habilidad proporciona las herramientas para **generar flujos de mirada sintética** y realizar pruebas automatizadas de regresión y rendimiento.

---

## 1. Generador de Mirada Sintética (Synthetic Gaze Stream)

Un emulador de mirada realista debe modelar los cuatro fenómenos psicofísicos de la visión humana:
1. **Fijaciones**: Puntos estables con micro-temblor fisiológico gaussiano ($\sigma \approx 2\text{ a } 5\text{ px}$).
2. **Sácadas**: Movimientos balísticos de alta velocidad (velocidades pico de $300^\circ/\text{s}$ a $700^\circ/\text{s}$) modelados mediante curvas sigmoideas o perfiles de aceleración senoidales.
3. **Deriva Fisiológica (Drift)**: Desviación lenta de baja frecuencia.
4. **Parpadeos**: Caída temporal del indicador de presencia de ojo ($\text{EAR} = 0.05$) durante 100–350 ms.

### Generador en Python:
```python
import numpy as np
import time

def generate_synthetic_gaze_path(start_xy, end_xy, duration_sec=0.4, fps=60, jitter_std=2.5):
    """Genera una trayectoria sacádica realista con temblor fisiológico."""
    num_frames = int(duration_sec * fps)
    t = np.linspace(0, 1, num_frames)
    
    # Perfil sigmoidal suave de sácada
    s_curve = 1 / (1 + np.exp(-10 * (t - 0.5)))
    
    x = start_xy[0] + (end_xy[0] - start_xy[0]) * s_curve + np.random.normal(0, jitter_std, num_frames)
    y = start_xy[1] + (end_xy[1] - start_xy[1]) * s_curve + np.random.normal(0, jitter_std, num_frames)
    
    timestamps = np.linspace(time.time(), time.time() + duration_sec, num_frames)
    return list(zip(timestamps, x, y))
```

---

## 2. Pruebas de Interfaz de Usuario con Puppeteer / Playwright

Para verificar que un botón de dwell se activa exactamente cuando el usuario mantiene la mirada:

```javascript
const puppeteer = require('puppeteer');

async function testDwellButtonActivation() {
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();
  await page.goto('http://localhost:3000/ideye-test');

  const targetSelector = '#btn-extract-function';
  const targetBox = await page.$eval(targetSelector, el => {
    const r = el.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  });

  // Emitir evento sintético de fijación de mirada por 450 ms
  await page.evaluate(({ x, y }) => {
    window.dispatchSyntheticGaze({ x, y, durationMs: 450, state: 'FIXATION' });
  }, targetBox);

  // Esperar a que el evento de clic o callback se haya registrado
  await page.waitForFunction(
    selector => document.querySelector(selector).classList.contains('dwell-activated'),
    { timeout: 1000 },
    targetSelector
  );

  console.log('Test exitoso: Botón activado por fijación de mirada.');
  await browser.close();
}
```

---

## 3. Benchmarking de Filtros (1€ Filter vs Kalman vs Raw)

Para evaluar si un cambio en el algoritmo introduce retraso excesivo o no suprime el temblor:
* **Métrica de Temblor (Jitter / Roughness)**:
  $$J = \frac{1}{N - 2} \sum_{i=2}^N ||(p_i - p_{i-1}) - (p_{i-1} - p_{i-2})||^2$$
* **Métrica de Retraso Temporal (Lag / Latency)**:
  Desfase temporal entre el inicio de una sácada real y la salida del filtro. Debe ser $\le 15\text{ ms}$.
* **Presupuesto de CPU**:
  El procesamiento por fotograma del filtro matemático no debe superar los $0.2\text{ ms}$ por muestra.
