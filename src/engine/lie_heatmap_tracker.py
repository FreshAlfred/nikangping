# -*- coding: utf-8 -*-
"""
Gostart-inspired causal heatmap tracker for the lie-detector mini-game.

Contract (aligned with gostart lie-detector-observation.json):
  features  [1, 10, 96, 144] float32
  probability [1, 96, 144] float32 (sums ~1)

First-party model: hand-crafted ONNX over heuristic channels (not gostart weights).
Existing white/YOLO peaks can inject a soft measurement for bootstrap.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

WORK_H = 96
WORK_W = 144
FEATURE_CHANNELS = 10


@dataclass
class HeatmapEstimate:
    x: float  # frame coords
    y: float
    confidence: float
    secondary_ratio: float
    source: str  # heatmap | inject | predict
    work_xy: Tuple[float, float]


def export_lie_heatmap_onnx(path: str) -> str:
    """
    Export a tiny fixed-weight heatmap head.

    Channel roles (must match build_features):
      0 gray, 1 absdiff, 2 white, 3 residual, 4 V, 5 inv-S,
      6 edge, 7 soft-diff, 8 not-green, 9 prior
    """
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    # 1x1 conv: mix channels → single logit map
    w = np.zeros((1, FEATURE_CHANNELS, 1, 1), dtype=np.float32)
    w[0, 0, 0, 0] = 0.15  # gray
    w[0, 1, 0, 0] = 0.90  # motion
    w[0, 2, 0, 0] = 1.40  # white
    w[0, 3, 0, 0] = 0.55  # residual
    w[0, 4, 0, 0] = 0.25  # V
    w[0, 5, 0, 0] = 0.35  # inv-S
    w[0, 6, 0, 0] = 0.20  # edge
    w[0, 7, 0, 0] = 0.70  # soft diff
    w[0, 8, 0, 0] = 0.10  # not-green
    w[0, 9, 0, 0] = 0.80  # prior
    b = np.array([-0.35], dtype=np.float32)

    feats = helper.make_tensor_value_info(
        "features", TensorProto.FLOAT, [1, FEATURE_CHANNELS, WORK_H, WORK_W]
    )
    # Keep spatial size; softmax over HxW via Reshape trick done in Python.
    # ONNX graph only emits logits; runtime normalizes.
    logits = helper.make_tensor_value_info(
        "logits", TensorProto.FLOAT, [1, 1, WORK_H, WORK_W]
    )
    graph = helper.make_graph(
        nodes=[
            helper.make_node(
                "Conv",
                ["features", "W", "B"],
                ["logits"],
                kernel_shape=[1, 1],
                pads=[0, 0, 0, 0],
                strides=[1, 1],
            ),
        ],
        name="lie_heatmap",
        inputs=[feats],
        outputs=[logits],
        initializer=[
            numpy_helper.from_array(w, name="W"),
            numpy_helper.from_array(b, name="B"),
        ],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8
    onnx.save(model, path)
    return path


def _remove_green_cursor(bgr: np.ndarray) -> np.ndarray:
    """Neutralize bright green reticle / marker (gostart-style)."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    # Typical overlay greens
    m1 = cv2.inRange(hsv, (40, 80, 80), (95, 255, 255))
    m2 = cv2.inRange(bgr, (0, 180, 0), (120, 255, 120))
    mask = cv2.bitwise_or(m1, m2)
    if int(cv2.countNonZero(mask)) < 8:
        return bgr
    out = bgr.copy()
    out[mask > 0] = cv2.blur(bgr, (7, 7))[mask > 0]
    return out


def build_features(
    bgr: np.ndarray,
    prev_gray: Optional[np.ndarray],
    prior_work: Optional[np.ndarray],
):
    """
    Returns features [1,10,H,W], work BGR, (sx, sy, ox, oy), gray work.
    Full-frame resize: ox=oy=0, sx=WORK_W/fw, sy=WORK_H/fh.
    """
    clean = _remove_green_cursor(bgr)
    fh, fw = clean.shape[:2]
    work = cv2.resize(clean, (WORK_W, WORK_H), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    hsv = cv2.cvtColor(work, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    sf = s.astype(np.float32) / 255.0
    vf = v.astype(np.float32) / 255.0
    white = (
        (vf >= 0.72) & (sf <= 0.28)
    ).astype(np.float32)
    blur = cv2.GaussianBlur(gray, (0, 0), 2.0)
    residual = np.clip(gray - blur + 0.5, 0.0, 1.0)
    if prev_gray is None or prev_gray.shape != gray.shape:
        absdiff = np.zeros_like(gray)
        soft_diff = absdiff
    else:
        absdiff = np.abs(gray - prev_gray)
        soft_diff = cv2.GaussianBlur(absdiff, (0, 0), 1.2)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    edge = np.clip(np.sqrt(gx * gx + gy * gy) / 4.0, 0.0, 1.0)
    # not-green
    green = cv2.inRange(hsv, (40, 80, 80), (95, 255, 255)).astype(np.float32) / 255.0
    not_green = 1.0 - green
    if prior_work is None or prior_work.shape != (WORK_H, WORK_W):
        prior = np.zeros_like(gray)
    else:
        prior = prior_work.astype(np.float32)
        ssum = float(prior.sum())
        if ssum > 1e-6:
            prior = prior / ssum * (WORK_H * WORK_W * 0.01)
        prior = np.clip(prior, 0.0, 1.0)

    chans = [
        gray,
        np.clip(absdiff * 3.0, 0.0, 1.0),
        white,
        residual,
        vf,
        1.0 - sf,
        edge,
        np.clip(soft_diff * 3.0, 0.0, 1.0),
        not_green,
        prior,
    ]
    feat = np.stack(chans, axis=0)[None, ...].astype(np.float32)
    sx = float(WORK_W) / float(max(1, fw))
    sy = float(WORK_H) / float(max(1, fh))
    return feat, work, (sx, sy, 0.0, 0.0), gray


def _softmax_map(logits: np.ndarray) -> np.ndarray:
    x = logits.astype(np.float32).reshape(-1)
    x = x - float(x.max())
    e = np.exp(x)
    e = e / (float(e.sum()) + 1e-12)
    return e.reshape(WORK_H, WORK_W)


def _peak_stats(prob: np.ndarray) -> Tuple[float, float, float, float]:
    """Return work_x, work_y, confidence proxy, secondary_peak_ratio."""
    flat = prob.reshape(-1)
    i = int(np.argmax(flat))
    wy, wx = divmod(i, WORK_W)
    primary = float(flat[i])
    # concentration
    yy, xx = np.mgrid[0:WORK_H, 0:WORK_W]
    mass = float(prob.sum()) + 1e-12
    # secondary: max outside exclusion radius
    excl = 8
    mask = np.ones_like(prob, dtype=bool)
    y0, y1 = max(0, wy - excl), min(WORK_H, wy + excl + 1)
    x0, x1 = max(0, wx - excl), min(WORK_W, wx + excl + 1)
    mask[y0:y1, x0:x1] = False
    secondary = float(prob[mask].max()) if mask.any() else 0.0
    ratio = secondary / (primary + 1e-12)
    # concentration: inverse of spatial variance of mass
    cx = float((prob * xx).sum() / mass)
    cy = float((prob * yy).sum() / mass)
    var = float((prob * ((xx - cx) ** 2 + (yy - cy) ** 2)).sum() / mass)
    conc = 1.0 / (1.0 + var / 40.0)
    dominance = primary / (primary + secondary + 1e-12)
    conf = float(0.35 * conc + 0.65 * dominance)
    return float(wx) + 0.5, float(wy) + 0.5, conf, ratio


class LieHeatmapTracker:
    def __init__(self, cfg: Optional[dict] = None):
        la = (cfg or {}).get("lie_alert") or {}
        self.enable = bool(la.get("heatmap_enable", True))
        self.model_path = str(
            la.get("heatmap_model", "assets/lie_detector/lie_heatmap.onnx")
        ).strip()
        self.control_min_confidence = float(la.get("control_min_confidence", 0.42))
        self.ambiguity_cap = float(
            la.get("heatmap_ambiguity_secondary_ratio", 0.78)
        )
        self.opening_confirm_frames = max(1, int(la.get("opening_confirm_frames", 4)))
        self.opening_confirm_timeout_s = float(
            la.get("opening_confirm_timeout_s", 8.0)
        )
        self.predict_coast_s = float(la.get("predict_coast_s", 0.30))
        # Belief params (gostart numerical contract)
        self.learn_sigma = 5.0
        self.learn_power = 2.0
        self.learn_floor = 0.01
        self.learn_recovery = 0.1
        self.active_sigma = 3.0
        self.active_power = 2.5
        self.active_floor = 0.01
        self.active_recovery = 0.025
        self.velocity_gain = 1.0
        self.velocity_momentum = 0.5
        self.velocity_max_work_px = 10.0

        self._sess = None
        self._prev_gray = None
        self._belief = None  # WORK_H x WORK_W
        self._active = False
        self._vel = np.zeros(2, dtype=np.float32)
        self._last_work_xy = None
        self._opening_hits = 0
        self._opening_confirmed = False
        self._opening_start_t = 0.0
        self._last_est: Optional[HeatmapEstimate] = None

        if self.enable:
            self._ensure_session()

    def _ensure_session(self) -> bool:
        if self._sess is not None:
            return True
        path = self.model_path
        if not os.path.isfile(path):
            try:
                export_lie_heatmap_onnx(path)
            except Exception:
                return False
        try:
            import onnxruntime as ort

            self._sess = ort.InferenceSession(
                path, providers=["CPUExecutionProvider"]
            )
            return True
        except Exception:
            self._sess = None
            return False

    def reset(self, now: float = 0.0):
        self._prev_gray = None
        self._belief = None
        self._active = False
        self._vel[:] = 0
        self._last_work_xy = None
        self._opening_hits = 0
        self._opening_confirmed = False
        self._opening_start_t = float(now or 0.0)
        self._last_est = None

    @property
    def opening_confirmed(self) -> bool:
        return bool(self._opening_confirmed)

    def note_opening_white(self, hit: bool, now: float) -> bool:
        """Accumulate opening white confirms. Returns True once armed for mouse."""
        if self._opening_confirmed:
            return True
        if self._opening_start_t <= 0:
            self._opening_start_t = float(now)
        if hit:
            self._opening_hits += 1
        else:
            self._opening_hits = max(0, self._opening_hits - 1)
        if self._opening_hits >= self.opening_confirm_frames:
            self._opening_confirmed = True
            self._active = True
            return True
        return False

    def opening_timed_out(self, now: float) -> bool:
        if self._opening_confirmed:
            return False
        t0 = float(self._opening_start_t or now)
        return (float(now) - t0) >= self.opening_confirm_timeout_s

    def _update_belief(self, measurement: np.ndarray) -> np.ndarray:
        m = measurement.astype(np.float32)
        m = np.clip(m, 0.0, None)
        s = float(m.sum())
        if s > 1e-8:
            m = m / s
        else:
            m = np.full((WORK_H, WORK_W), 1.0 / (WORK_H * WORK_W), dtype=np.float32)

        sigma = self.active_sigma if self._active else self.learn_sigma
        power = self.active_power if self._active else self.learn_power
        floor = self.active_floor if self._active else self.learn_floor
        recovery = self.active_recovery if self._active else self.learn_recovery

        if self._belief is None:
            belief = m.copy()
        else:
            # Shift prior by velocity (work px)
            dx, dy = float(self._vel[0]), float(self._vel[1])
            prior = self._belief
            if abs(dx) > 0.05 or abs(dy) > 0.05:
                M = np.float32([[1, 0, dx], [0, 1, dy]])
                prior = cv2.warpAffine(
                    prior,
                    M,
                    (WORK_W, WORK_H),
                    flags=cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_CONSTANT,
                    borderValue=0,
                )
            # Blur = diffusion
            k = max(1, int(round(sigma)))
            if k % 2 == 0:
                k += 1
            prior = cv2.GaussianBlur(prior, (k, k), sigma)
            prior = prior + floor * (1.0 / (WORK_H * WORK_W))
            prior = prior / (float(prior.sum()) + 1e-12)
            meas = np.power(m + 1e-12, power)
            meas = meas / (float(meas.sum()) + 1e-12)
            belief = (1.0 - recovery) * prior * meas + recovery * meas
            belief = belief / (float(belief.sum()) + 1e-12)
        self._belief = belief
        return belief

    def push(
        self,
        frame_bgr: np.ndarray,
        now: float,
        inject_xy: Optional[Tuple[float, float]] = None,
        inject_weight: float = 0.35,
    ) -> Optional[HeatmapEstimate]:
        if not self.enable or not self._ensure_session():
            return None
        prior = self._belief
        feat, _work, scales, gray = build_features(
            frame_bgr, self._prev_gray, prior
        )
        self._prev_gray = gray
        sx, sy, ox, oy = scales

        try:
            out = self._sess.run(None, {"features": feat})[0]
        except Exception:
            return None
        logits = np.asarray(out)
        if logits.ndim == 4:
            logits = logits[0, 0]
        elif logits.ndim == 3:
            logits = logits[0]
        meas = _softmax_map(logits)

        if inject_xy is not None:
            fx, fy = float(inject_xy[0]), float(inject_xy[1])
            wx = (fx - ox) * sx
            wy = (fy - oy) * sy
            yy, xx = np.mgrid[0:WORK_H, 0:WORK_W]
            gauss = np.exp(-0.5 * (((xx - wx) / 3.0) ** 2 + ((yy - wy) / 3.0) ** 2))
            gauss = gauss / (float(gauss.sum()) + 1e-12)
            w = float(np.clip(inject_weight, 0.0, 0.9))
            meas = (1.0 - w) * meas + w * gauss
            meas = meas / (float(meas.sum()) + 1e-12)

        belief = self._update_belief(meas)
        wx, wy, conf, sec_ratio = _peak_stats(belief)

        # Velocity estimate in work space
        if self._last_work_xy is not None:
            raw = np.array(
                [wx - self._last_work_xy[0], wy - self._last_work_xy[1]],
                dtype=np.float32,
            )
            span = float(np.linalg.norm(raw))
            if span > self.velocity_max_work_px:
                raw *= self.velocity_max_work_px / (span + 1e-6)
            self._vel = (
                self.velocity_momentum * self._vel
                + (1.0 - self.velocity_momentum) * raw * self.velocity_gain
            )
        self._last_work_xy = (wx, wy)

        fx = wx / max(1e-6, sx) + ox
        fy = wy / max(1e-6, sy) + oy
        src = "heatmap"
        if inject_xy is not None and inject_weight >= 0.5:
            src = "inject"
        est = HeatmapEstimate(
            x=fx,
            y=fy,
            confidence=conf,
            secondary_ratio=sec_ratio,
            source=src,
            work_xy=(wx, wy),
        )
        self._last_est = est
        return est

    def predict_coast(self) -> Optional[HeatmapEstimate]:
        if self._last_est is None or self._last_work_xy is None:
            return None
        wx = self._last_work_xy[0] + float(self._vel[0]) * 0.5
        wy = self._last_work_xy[1] + float(self._vel[1]) * 0.5
        # Map back using last estimate scale approx via last frame coords ratio
        # Prefer last frame point + small step from last est
        fx = self._last_est.x + float(self._vel[0]) * 0.5 * (
            self._last_est.x / max(1.0, self._last_work_xy[0])
        )
        fy = self._last_est.y + float(self._vel[1]) * 0.5 * (
            self._last_est.y / max(1.0, self._last_work_xy[1])
        )
        # Safer: use last frame xy + scaled vel assuming ~frame/work from last est
        if self._last_work_xy[0] > 1 and self._last_est.x > 1:
            sx = self._last_work_xy[0] / max(1.0, self._last_est.x)
            sy = self._last_work_xy[1] / max(1.0, self._last_est.y)
            fx = self._last_est.x + float(self._vel[0]) / max(1e-6, sx) * 0.4
            fy = self._last_est.y + float(self._vel[1]) / max(1e-6, sy) * 0.4
        return HeatmapEstimate(
            x=fx,
            y=fy,
            confidence=max(0.0, float(self._last_est.confidence) * 0.7),
            secondary_ratio=1.0,
            source="predict",
            work_xy=(wx, wy),
        )

    def may_move(self, est: Optional[HeatmapEstimate]) -> bool:
        if est is None:
            return False
        if not self._opening_confirmed:
            return False
        if est.source == "predict":
            return est.confidence >= self.control_min_confidence * 0.85
        if est.secondary_ratio >= self.ambiguity_cap:
            return False
        return float(est.confidence) >= self.control_min_confidence
