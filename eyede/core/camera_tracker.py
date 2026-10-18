"""
Camera Tracker Module for EyeDE (Phase 1)
Handles OpenCV webcam capture and MediaPipe FaceMesh processing
with 478 refined 3D landmarks for iris and facial tracking.

Implements threaded background capture & inference to ensure the main UI thread
remains silky smooth (<35ms budget) per AGENTS.md requirements.
"""

from typing import Optional, Tuple, Any, List, Union
import threading
import time
import math
import cv2
import numpy as np
import mediapipe as mp


class CameraTracker:
    """
    Manages OpenCV video capture and MediaPipe FaceMesh inference.
    
    Features:
    - Dedicated background worker thread for camera I/O & CV inference (optional, enabled by default).
    - Idempotent resource cleanup (safe multiple calls to release()).
    - Synthetic test camera mode for headless testing environments.
    - Mirror flip support and landmark overlay visualization.
    """

    def __init__(
        self,
        camera_index: Union[int, str] = 0,
        frame_width: int = 1280,
        frame_height: int = 720,
        fps: int = 30,
        mirror: bool = True,
        max_num_faces: int = 1,
        refine_landmarks: bool = True,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        threaded: bool = True,
    ):
        self.camera_index = camera_index
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.fps = fps
        self.mirror = mirror
        self.threaded = threaded

        # MediaPipe FaceMesh initialization
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh: Optional[Any] = self.mp_face_mesh.FaceMesh(
            max_num_faces=max_num_faces,
            refine_landmarks=refine_landmarks,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

        self.cap: Optional[cv2.VideoCapture] = None
        self._is_opened = False
        self.is_synthetic = (str(camera_index).lower() == "synthetic")

        # Threading infrastructure
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_landmarks: Optional[Any] = None
        self._has_new_frame: bool = False
        self._synthetic_tick: float = 0.0

    def start(self) -> bool:
        """
        Initializes and opens the camera capture device and starts the worker thread if threaded=True.
        Returns True if successful, False otherwise.
        """
        if self._is_opened:
            return True

        if self.is_synthetic:
            self._is_opened = True
            if self.threaded:
                self._stop_event.clear()
                self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="CameraTrackerWorker")
                self._worker_thread.start()
            return True

        # Open real camera device
        cam_idx = int(self.camera_index) if isinstance(self.camera_index, (int, str)) and str(self.camera_index).isdigit() else 0
        self.cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW if cv2.os.name == "nt" else cv2.CAP_ANY)
        if not self.cap.isOpened():
            # Fallback to default backend if DirectShow fails
            self.cap = cv2.VideoCapture(cam_idx)

        if not self.cap.isOpened():
            self._is_opened = False
            return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        self._is_opened = True

        if self.threaded:
            self._stop_event.clear()
            self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="CameraTrackerWorker")
            self._worker_thread.start()

        return True

    def _generate_synthetic_frame(self) -> Tuple[np.ndarray, Optional[Any]]:
        """Generates a synthetic frame for testing without a physical camera."""
        frame = np.full((self.frame_height, self.frame_width, 3), (25, 27, 32), dtype=np.uint8)
        self._synthetic_tick += 0.05
        # Draw a synthetic circular 'face'
        center_x = int(self.frame_width * (0.5 + 0.1 * math.sin(self._synthetic_tick)))
        center_y = int(self.frame_height * (0.5 + 0.05 * math.cos(self._synthetic_tick)))
        cv2.circle(frame, (center_x, center_y), 100, (120, 140, 160), -1)
        cv2.circle(frame, (center_x - 35, center_y - 20), 15, (240, 240, 240), -1)
        cv2.circle(frame, (center_x + 35, center_y - 20), 15, (240, 240, 240), -1)
        cv2.circle(frame, (center_x - 35, center_y - 20), 6, (40, 180, 220), -1)
        cv2.circle(frame, (center_x + 35, center_y - 20), 6, (40, 180, 220), -1)

        # Process through MediaPipe if possible
        landmarks = None
        if self.face_mesh is not None:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = self.face_mesh.process(rgb)
            if res.multi_face_landmarks and len(res.multi_face_landmarks) > 0:
                landmarks = res.multi_face_landmarks[0]
        return frame, landmarks

    def _worker_loop(self) -> None:
        """Background thread worker loop for non-blocking camera capture & inference."""
        target_delay = 1.0 / max(1, self.fps)

        while not self._stop_event.is_set():
            t_start = time.perf_counter()

            if self.is_synthetic:
                frame, landmarks = self._generate_synthetic_frame()
                with self._lock:
                    self._latest_frame = frame
                    self._latest_landmarks = landmarks
                    self._has_new_frame = True
            else:
                if self.cap is None or not self.cap.isOpened():
                    time.sleep(0.05)
                    continue

                ret, frame = self.cap.read()
                if not ret or frame is None:
                    time.sleep(0.02)
                    continue

                if self.mirror:
                    frame = cv2.flip(frame, 1)

                landmarks = None
                if self.face_mesh is not None:
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    rgb_frame.flags.writeable = False
                    try:
                        results = self.face_mesh.process(rgb_frame)
                        if results.multi_face_landmarks and len(results.multi_face_landmarks) > 0:
                            landmarks = results.multi_face_landmarks[0]
                    except Exception:
                        landmarks = None

                with self._lock:
                    self._latest_frame = frame
                    self._latest_landmarks = landmarks
                    self._has_new_frame = True

            elapsed = time.perf_counter() - t_start
            sleep_time = max(0.001, target_delay - elapsed)
            time.sleep(sleep_time)

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray], Optional[Any]]:
        """
        Reads one frame and processes FaceMesh landmarks.
        In threaded mode: instantly returns the latest processed frame from the worker.
        In synchronous mode: captures from device directly.

        Returns:
            Tuple of:
                - success (bool): True if frame was read and processed.
                - frame (np.ndarray): BGR image frame (flipped horizontally if mirror=True).
                - face_landmarks: MediaPipe NormalizedLandmarkList or None if no face detected.
        """
        if not self._is_opened:
            if not self.start():
                return False, None, None

        if self.threaded:
            with self._lock:
                if self._latest_frame is None:
                    # Waiting for first frame
                    return False, None, None
                return True, self._latest_frame.copy(), self._latest_landmarks

        # Synchronous fallback mode (e.g. for deterministic unit testing)
        if self.is_synthetic:
            frame, landmarks = self._generate_synthetic_frame()
            return True, frame, landmarks

        if self.cap is None or not self.cap.isOpened():
            return False, None, None

        ret, frame = self.cap.read()
        if not ret or frame is None:
            return False, None, None

        if self.mirror:
            frame = cv2.flip(frame, 1)

        landmarks = None
        if self.face_mesh is not None:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb_frame.flags.writeable = False
            try:
                results = self.face_mesh.process(rgb_frame)
                if results.multi_face_landmarks and len(results.multi_face_landmarks) > 0:
                    landmarks = results.multi_face_landmarks[0]
            except Exception:
                landmarks = None

        return True, frame, landmarks

    def draw_debug_landmarks(
        self,
        frame: np.ndarray,
        face_landmarks: Any,
        draw_iris: bool = True,
        draw_mouth: bool = True,
        draw_nose: bool = True,
    ) -> np.ndarray:
        """
        Renders key landmark points (iris, lips, nose) onto the camera feed.
        """
        if face_landmarks is None or frame is None:
            return frame

        landmarks = getattr(face_landmarks, "landmark", face_landmarks)
        h, w = frame.shape[:2]

        def get_pt(idx: int) -> Tuple[int, int]:
            p = landmarks[idx]
            return int(p.x * w), int(p.y * h)

        try:
            # Nose tip
            if draw_nose:
                nose_pt = get_pt(1)
                cv2.circle(frame, nose_pt, 4, (0, 255, 255), -1)

            # Irises
            if draw_iris:
                # Left iris center (468) and right iris center (473)
                l_iris = get_pt(468)
                r_iris = get_pt(473)
                cv2.circle(frame, l_iris, 3, (0, 220, 255), -1)
                cv2.circle(frame, r_iris, 3, (0, 220, 255), -1)

                # Eye corners
                for c_idx in (33, 133, 263, 362):
                    cv2.circle(frame, get_pt(c_idx), 2, (180, 180, 180), -1)

            # Mouth
            if draw_mouth:
                m_top = get_pt(13)
                m_bot = get_pt(14)
                m_l = get_pt(78)
                m_r = get_pt(308)
                cv2.circle(frame, m_top, 3, (0, 255, 0), -1)
                cv2.circle(frame, m_bot, 3, (0, 255, 0), -1)
                cv2.circle(frame, m_l, 3, (0, 165, 255), -1)
                cv2.circle(frame, m_r, 3, (0, 165, 255), -1)
                # Draw vertical opening indicator line
                cv2.line(frame, m_top, m_bot, (0, 255, 120), 1)

        except (IndexError, AttributeError):
            pass

        return frame

    def release(self) -> None:
        """
        Releases the camera, terminates worker thread, and closes FaceMesh cleanly.
        Guaranteed to be idempotent (safe to call multiple times without error).
        """
        self._stop_event.set()

        if self._worker_thread is not None and self._worker_thread.is_alive():
            try:
                self._worker_thread.join(timeout=1.0)
            except Exception:
                pass
            self._worker_thread = None

        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        if self.face_mesh is not None:
            try:
                self.face_mesh.close()
            except Exception:
                pass
            self.face_mesh = None

        self._is_opened = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
