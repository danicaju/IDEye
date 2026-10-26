"""Adaptive low-light preprocessing for MediaPipe iris landmarks."""

from __future__ import annotations

import cv2
import numpy as np


class LightingCompensator:
    """CLAHE on LAB luminance with a cheap daylight bypass."""

    def __init__(self, enabled: bool = True, low_light_threshold: float = 85.0) -> None:
        self.enabled = bool(enabled)
        self.low_light_threshold = float(low_light_threshold)
        self.is_low_light_active = False
        self.current_luma = 0.0
        self._clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
        self._gamma_table = np.array(
            [((i / 255.0) ** 0.85) * 255 for i in range(256)], dtype=np.uint8
        )

    def process(self, frame):
        """Returns the original frame in good light, or a CLAHE+gamma frame in low light."""
        if frame is None:
            self.is_low_light_active = False
            self.current_luma = 0.0
            return frame
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            self.current_luma = float(np.mean(gray))
            if not self.enabled or self.current_luma >= self.low_light_threshold:
                self.is_low_light_active = False
                return frame
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
            l_channel = self._clahe.apply(l_channel)
            l_channel = cv2.LUT(l_channel, self._gamma_table)
            enhanced = cv2.cvtColor(cv2.merge((l_channel, a_channel, b_channel)), cv2.COLOR_LAB2BGR)
            self.is_low_light_active = True
            return enhanced
        except Exception:
            self.is_low_light_active = False
            return frame
