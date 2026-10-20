"""
IDEye - Sound Feedback Manager (Phase 7)
Generates short, non-blocking PCM tones in memory for gaze interactions.
"""

from __future__ import annotations

import struct
import sys
import threading
from typing import Dict

import numpy as np

if sys.platform == "win32":
    import winsound

SAMPLE_RATE: int = 44100


class SoundFeedbackManager:
    """Lightweight, UI-thread-safe sound generator with in-memory WAV buffers."""

    def __init__(self, enabled: bool = True, volume: float = 0.5) -> None:
        self._enabled: bool = bool(enabled)
        self._volume: float = float(np.clip(volume, 0.0, 1.0))
        self._buffers: Dict[str, bytes] = {
            "click": self._build_wav(0.040, 520.0, 780.0),
            "back": self._build_wav(0.035, 480.0, 320.0),
            "mode": self._build_wav(0.055, 600.0, second_freq=900.0),
            "pause": self._build_wav(0.045, 300.0),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def play(self, name: str) -> None:
        """Play a pre-generated sound asynchronously; never blocks the UI."""
        if not self._enabled or name not in self._buffers:
            return
        buffer = self._buffers[name]
        try:
            if sys.platform == "win32":
                winsound.PlaySound(buffer, winsound.SND_MEMORY | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except Exception:
            # Backend failure must never propagate to the caller / UI thread.
            threading.Thread(target=lambda: None, daemon=True).start()

    def toggle_mute(self) -> bool:
        """Toggle audible state. Returns True if now audible."""
        self._enabled = not self._enabled
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)

    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def volume(self) -> float:
        return self._volume

    @volume.setter
    def volume(self, value: float) -> None:
        self._volume = float(np.clip(value, 0.0, 1.0))

    # ------------------------------------------------------------------
    # Tone generation
    # ------------------------------------------------------------------
    def _build_wav(
        self,
        duration_sec: float,
        freq_start: float,
        freq_end: float | None = None,
        second_freq: float | None = None,
    ) -> bytes:
        samples = int(round(SAMPLE_RATE * duration_sec))
        t = np.linspace(0.0, duration_sec, samples, endpoint=False)

        # Primary tone with optional linear sweep.
        if freq_end is None or freq_end == freq_start:
            phase = 2.0 * np.pi * freq_start * t
        else:
            freq = np.linspace(freq_start, freq_end, samples)
            phase = 2.0 * np.pi * np.cumsum(freq) / SAMPLE_RATE

        signal = np.sin(phase)

        # Optional harmonic/dual tone mixed at equal amplitude.
        if second_freq is not None:
            phase2 = 2.0 * np.pi * second_freq * t
            signal = (signal + np.sin(phase2)) * 0.5

        # Soft fade-in to avoid zero-crossing clicks, exponential fade-out.
        fade_in_samples = max(1, int(round(0.003 * SAMPLE_RATE)))  # 3 ms
        envelope_in = np.ones(samples)
        envelope_in[:fade_in_samples] = np.linspace(0.0, 1.0, fade_in_samples)
        # Exponential decay: tail ~ e^{-8} at the end of the buffer.
        envelope_out = np.exp(-8.0 * t / duration_sec)

        signal = signal * envelope_in * envelope_out

        pcm = np.int16(np.clip(signal * 32767.0 * self._volume, -32768, 32767))
        return self._pack_wav(pcm.tobytes())

    def _pack_wav(self, pcm_bytes: bytes) -> bytes:
        data_size = len(pcm_bytes)
        fmt_chunk = struct.pack(
            "<HHIIHH",
            1,          # wFormatTag = PCM
            1,          # nChannels = mono
            SAMPLE_RATE,
            SAMPLE_RATE * 1 * 2,  # nAvgBytesPerSec
            1 * 2,      # nBlockAlign
            16,         # wBitsPerSample
        )
        data_chunk = b"data" + struct.pack("<I", data_size) + pcm_bytes
        fmt_chunk_full = b"fmt " + struct.pack("<I", len(fmt_chunk)) + fmt_chunk
        riff_body = b"WAVE" + fmt_chunk_full + data_chunk
        return b"RIFF" + struct.pack("<I", len(riff_body)) + riff_body


# Convenience alias used by the rest of the application.
SoundFeedback = SoundFeedbackManager
