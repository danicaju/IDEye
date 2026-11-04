"""Adaptive low-light and eye-region shadow preprocessing for MediaPipe iris landmarks."""

from __future__ import annotations

from typing import Any, Optional
import cv2
import numpy as np


class LightingCompensator:
    """
    CLAHE on LAB luminance with dual-mode detection:
    1. Global low-light compensation (night/dim rooms).
    2. Localized Eye ROI / Cap-Visor shadow compensation (illuminates dark eye sockets
       cast by caps, hats, or overhead lighting while preserving well-lit faces).
    """

    def __init__(
        self,
        enabled: bool = True,
        low_light_threshold: float = 85.0,
        eye_shadow_threshold: float = 75.0,
        shadow_delta_threshold: float = 20.0,
        auto_eye_roi: bool = True,
    ) -> None:
        self.enabled = bool(enabled)
        self.low_light_threshold = float(low_light_threshold)
        self.eye_shadow_threshold = float(eye_shadow_threshold)
        self.shadow_delta_threshold = float(shadow_delta_threshold)
        self.auto_eye_roi = bool(auto_eye_roi)
        self.cap_mode = False

        self.is_low_light_active = False
        self.is_eye_shadow_active = False
        self.current_luma = 0.0
        self.current_eye_luma = 0.0

        self._clahe_standard = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
        self._clahe_boost = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        self._gamma_table = np.array(
            [((i / 255.0) ** 0.85) * 255 for i in range(256)], dtype=np.uint8
        )

    @property
    def is_active(self) -> bool:
        """True if either global low light or ocular shadow compensation is active."""
        return self.is_low_light_active or self.is_eye_shadow_active

    def set_cap_mode(self, enabled: bool) -> None:
        """Enables aggressive eye-shadow compensation for caps and visors."""
        self.cap_mode = bool(enabled)

    def _extract_eye_roi_luma(self, gray: np.ndarray, landmarks: Optional[Any] = None) -> float:
        """Calculates luminance specifically in the ocular / upper-face region."""
        h, w = gray.shape[:2]
        if h <= 0 or w <= 0:
            return self.current_luma

        if landmarks is not None:
            try:
                lm = getattr(landmarks, "landmark", landmarks)
                # Left eye corners (33, 133) and right eye corners (362, 263)
                indices = (33, 133, 362, 263, 159, 386, 145, 374)
                xs = [float(lm[i].x) for i in indices]
                ys = [float(lm[i].y) for i in indices]
                min_x = max(0, int((min(xs) - 0.04) * w))
                max_x = min(w, int((max(xs) + 0.04) * w))
                min_y = max(0, int((min(ys) - 0.05) * h))
                max_y = min(h, int((max(ys) + 0.05) * h))
                if max_x > min_x and max_y > min_y:
                    roi = gray[min_y:max_y, min_x:max_x]
                    if roi.size > 0:
                        return float(np.mean(roi))
            except Exception:
                pass

        # Fallback to upper-central facial band in standard webcam frame
        y1, y2 = int(h * 0.20), int(h * 0.55)
        x1, x2 = int(w * 0.25), int(w * 0.75)
        if y2 > y1 and x2 > x1:
            band = gray[y1:y2, x1:x2]
            if band.size > 0:
                return float(np.mean(band))
        return self.current_luma

    def process(self, frame: np.ndarray, landmarks: Optional[Any] = None) -> np.ndarray:
        """
        Returns the original frame in good, uniform light, or a CLAHE+gamma enhanced
        frame if global low light or a localized cap visor shadow is detected.
        """
        if frame is None:
            self.is_low_light_active = False
            self.is_eye_shadow_active = False
            self.current_luma = 0.0
            self.current_eye_luma = 0.0
            return frame
        if not isinstance(frame, np.ndarray) or frame.size == 0:
            self.is_low_light_active = False
            self.is_eye_shadow_active = False
            self.current_luma = 0.0
            self.current_eye_luma = 0.0
            return frame

        try:
            gray_output = False
            if frame.ndim == 2:
                gray = frame
                working = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                gray_output = True
            elif frame.ndim == 3 and frame.shape[2] == 1:
                gray = frame[:, :, 0]
                working = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
                gray_output = True
            elif frame.ndim == 3 and frame.shape[2] == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                working = frame
            elif frame.ndim == 3 and frame.shape[2] == 4:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
                working = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            else:
                self.is_low_light_active = False
                self.is_eye_shadow_active = False
                self.current_luma = 0.0
                self.current_eye_luma = 0.0
                return frame

            mean_luma = float(np.mean(gray)) if gray.size else 0.0
            self.current_luma = mean_luma if np.isfinite(mean_luma) else 0.0

            eye_luma = self._extract_eye_roi_luma(gray, landmarks)
            self.current_eye_luma = eye_luma if np.isfinite(eye_luma) else self.current_luma

            low_light = self.current_luma < self.low_light_threshold
            shadow_thresh = 82.0 if self.cap_mode else self.eye_shadow_threshold
            delta_thresh = 15.0 if self.cap_mode else self.shadow_delta_threshold
            eye_shadow = self.auto_eye_roi and (
                self.current_eye_luma < shadow_thresh
                or (self.current_luma - self.current_eye_luma) >= delta_thresh
            )

            if not self.enabled or (not low_light and not eye_shadow):
                self.is_low_light_active = False
                self.is_eye_shadow_active = False
                return frame

            if working.dtype != np.uint8:
                self.is_low_light_active = False
                self.is_eye_shadow_active = False
                return frame

            # Choose CLAHE intensity based on whether visor shadow is being pierced
            clahe = self._clahe_boost if (self.cap_mode or eye_shadow) else self._clahe_standard

            lab = cv2.cvtColor(working, cv2.COLOR_BGR2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
            l_channel = clahe.apply(l_channel)
            l_channel = cv2.LUT(l_channel, self._gamma_table)
            enhanced = cv2.cvtColor(cv2.merge((l_channel, a_channel, b_channel)), cv2.COLOR_LAB2BGR)

            self.is_low_light_active = low_light
            self.is_eye_shadow_active = eye_shadow

            if gray_output:
                return cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
            return enhanced

        except Exception:
            self.is_low_light_active = False
            self.is_eye_shadow_active = False
            return frame
