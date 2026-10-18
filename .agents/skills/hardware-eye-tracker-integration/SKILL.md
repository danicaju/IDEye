---
name: hardware-eye-tracker-integration
description: >-
  Use this skill when integrating dedicated eye-tracking hardware (Tobii Core SDK, Tobii Stream Engine, Pupil Labs, EyeLink) or network protocols like OpenTrack UDP and generic webcam fallback.
---

# Integración de Dispositivos de Seguimiento Ocular (Hardware Trackers)

`IDEye` está diseñado con una arquitectura agnóstica de hardware para permitir el uso tanto de cámaras web estándar (accesibilidad de bajo costo) como de dispositivos infrarrojos de grado médico o comercial de alta precisión.

---

## 1. Dispositivos Soportados y Protocolos

1. **Cámara Web Estándar (Consumo)**:
   * 30–60 FPS mediante MediaPipe Iris y OpenCV (sin costo de hardware adicional).
2. **Tobii Eye Tracking (Tobii Eye Tracker 4C / 5 / Pro Spark)**:
   * Conexión directa mediante **Tobii Stream Engine API** (biblioteca en C con bindings para Node.js / Python).
   * 90–120 Hz de muestreo, iluminación por infrarrojo cercano (inmune a variaciones de luz ambiental en la habitación).
3. **Protocolo OpenTrack (UDP)**:
   * Permite recibir datos de seguimiento de cabeza y ojos a través de sockets UDP en formato binario estándar (puerto por defecto `4242`).
4. **Pupil Labs (Pupil Core / Neon / Invisible)**:
   * API en tiempo real basada en sockets ZeroMQ / WebSocket con transporte JSON/MessagePack.

---

## 2. Capa de Abstracción Unificada (`GazeProvider`)

Cualquier dispositivo o fuente de cámara implementa la misma interfaz estándar:

```typescript
export interface GazeSample {
  timestamp: number;       // Unix timestamp en milisegundos con alta resolución
  x: number;               // Coordenada X normalizada en pantalla (0.0 a 1.0)
  y: number;               // Coordenada Y normalizada en pantalla (0.0 a 1.0)
  confidence: number;      // Nivel de confianza del tracking (0.0 a 1.0)
  leftEyeOpenness: number;  // Apertura ocular (0 = cerrado, 1 = completamente abierto)
  rightEyeOpenness: number; // Apertura ocular derecha
  pupilDiameterMm?: number;// Diámetro pupilar (si el hardware lo reporta)
}

export interface IGazeProvider {
  name: string;
  isAvailable(): Promise<boolean>;
  start(onSample: (sample: GazeSample) => void): Promise<void>;
  stop(): Promise<void>;
  startCalibration(): Promise<void>;
}
```

---

## 3. Protocolo de Red OpenTrack UDP

Para usuarios que utilizan software externo como OpenTrack o TrackIR:
```python
import socket
import struct

def listen_opentrack_udp(ip="127.0.0.1", port=4242, callback=None):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((ip, port))
    print(f"Escuchando OpenTrack UDP en {ip}:{port}...")

    # Formato OpenTrack: 6 doubles (x, y, z en cm; yaw, pitch, roll en grados)
    struct_format = "dddddd"
    data_size = struct.calcsize(struct_format)

    while True:
        data, addr = sock.recvfrom(1024)
        if len(data) >= data_size:
            x, y, z, yaw, pitch, roll = struct.unpack(struct_format, data[:data_size])
            if callback:
                callback(x, y, z, yaw, pitch, roll)
```

---

## 4. Fallback Dinámico y Reconexión Automática

* Si un rastreador Tobii o hardware dedicado se desconecta durante una sesión de programación, el sistema conmuta suavemente al pipeline de cámara web con un aviso en pantalla, sin reiniciar el IDE ni perder el estado del código.
