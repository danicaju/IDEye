"""IDEye - Sound feedback with cached WAV files.

Windows' multimedia API is reliable with `SND_FILENAME | SND_ASYNC`; in-memory
buffers combined with `SND_MEMORY | SND_ASYNC` can be rejected or collected
before playback. The manager therefore writes four small cached WAV files to
the user's temp directory and plays those files.
"""

from __future__ import annotations

import struct
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional

import numpy as np

if sys.platform == "win32":
    import winsound

SAMPLE_RATE: int = 44100
AMPLITUDE: int = 24000  # ~75% of int16 full scale
CACHE_DIR_NAME: str = "ideye_audio_cache"


class SoundFeedbackManager:
    """UI-thread-safe sound generator backed by cached WAV files."""

    def __init__(
        self,
        enabled: bool = True,
        volume: float = 0.5,
        cache_dir: Optional[Path] = None,
    ) -> None:
        self._enabled: bool = bool(enabled)
        self._volume: float = float(np.clip(volume, 0.0, 1.0))
        self.cache_dir = Path(cache_dir) if cache_dir else Path(tempfile.gettempdir()) / CACHE_DIR_NAME
        self._buffers: Dict[str, bytes] = {}
        self._wav_paths: Dict[str, Path] = {}
        self._build_cache()

    _ALIASES: Dict[str, str] = {
        "nav": "mode",
        "navigation": "mode",
        "hover": "mode",
        "confirm": "click",
        "confirmation": "click",
        "retroceso": "back",
        "undo": "back",
        "error": "pause",
        "alert": "pause",
        "fail": "pause",
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def play(self, name: str) -> None:
        """Play a cached WAV asynchronously; never blocks the UI."""
        if not self._enabled:
            return
        canonical = self._ALIASES.get(name, name)
        path = self._wav_paths.get(canonical)
        if path is None:
            return
        try:
            if sys.platform == "win32":
                winsound.PlaySound(
                    str(path),
                    winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
                )
            elif sys.platform == "darwin":
                # Lightweight fallback; missing afplay is harmless.
                import subprocess

                subprocess.Popen(
                    ["afplay", str(path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except Exception:
            # Audio must never break the gaze loop or the Qt event thread.
            pass

    def test_play(self) -> None:
        """Convenience method for the UI sound-test button."""
        self.play("click")

    def toggle_mute(self) -> bool:
        """Toggle audible state. Returns True if now audible."""
        self._enabled = not self._enabled
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)

    def is_enabled(self) -> bool:
        return self._enabled

    def wav_path(self, name: str) -> Optional[Path]:
        return self._wav_paths.get(name)

    @property
    def volume(self) -> float:
        return self._volume

    @volume.setter
    def volume(self, value: float) -> None:
        self._volume = float(np.clip(value, 0.0, 1.0))

    # ------------------------------------------------------------------
    # WAV cache
    # ------------------------------------------------------------------
    def _build_cache(self) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            # If the directory cannot be created, keep in-memory buffers and
            # playback becomes a safe no-op.
            self.cache_dir = Path(tempfile.gettempdir())

        specs = {
            "click": (0.055, 650.0, 920.0),
            "back": (0.045, 520.0, 320.0),
            "mode": (0.060, 700.0, 1000.0),
            "pause": (0.050, 380.0, 300.0),
        }
        for name, (duration, start_freq, end_freq) in specs.items():
            data = self._build_wav(duration, start_freq, end_freq)
            self._buffers[name] = data
            path = self.cache_dir / f"{name}.wav"
            try:
                path.write_bytes(data)
                self._wav_paths[name] = path
            except Exception:
                pass

    def _build_wav(self, duration_sec: float, freq_start: float, freq_end: float) -> bytes:
        samples = max(1, int(round(SAMPLE_RATE * duration_sec)))
        t = np.linspace(0.0, duration_sec, samples, endpoint=False)
        frequencies = np.linspace(freq_start, freq_end, samples)
        phase = 2.0 * np.pi * np.cumsum(frequencies) / SAMPLE_RATE
        signal = np.sin(phase)

        fade_in_samples = max(1, int(round(0.003 * SAMPLE_RATE)))
        envelope_in = np.ones(samples)
        envelope_in[:fade_in_samples] = np.linspace(0.0, 1.0, fade_in_samples)
        envelope_out = np.exp(-7.0 * t / duration_sec)
        signal = signal * envelope_in * envelope_out
        peak = float(np.max(np.abs(signal))) if samples else 0.0
        if peak > 1e-9:
            signal = signal * (float(AMPLITUDE) / peak)

        pcm = np.int16(np.clip(signal, -32768, 32767))
        return self._pack_wav(pcm.tobytes())

    @staticmethod
    def _pack_wav(pcm_bytes: bytes) -> bytes:
        data_size = len(pcm_bytes)
        fmt_chunk = struct.pack(
            "<HHIIHH",
            1,  # PCM
            1,  # mono
            SAMPLE_RATE,
            SAMPLE_RATE * 2,
            2,
            16,
        )
        data_chunk = b"data" + struct.pack("<I", data_size) + pcm_bytes
        fmt_chunk_full = b"fmt " + struct.pack("<I", len(fmt_chunk)) + fmt_chunk
        riff_body = b"WAVE" + fmt_chunk_full + data_chunk
        return b"RIFF" + struct.pack("<I", len(riff_body)) + riff_body


# Convenience alias used by the rest of the application.
SoundFeedback = SoundFeedbackManager
