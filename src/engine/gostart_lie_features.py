# -*- coding: utf-8 -*-
"""
Bit-exact channel layout of gostart tracker.pyd `_build_features`.

Verified against NavigationGPS `tracker.cp312-win_amd64.pyd` (uint8 path):

  out shape/dtype: (10, 96, 144) uint8
  HISTORY_LAGS = (1, 2, 4)

  ch0..2  signed lag diffs:   clip(delta / 2 + 128, 0, 255)
  ch3..5  abs lag diffs:      abs(delta).astype(uint8)
  ch6     mean_abs:           mean(abs_stack, axis=0).astype(uint8)   # trunc
  ch7     max_abs:            max(abs_stack, axis=0).astype(uint8)
  ch8     highpass:           clip((gray - GaussianBlur(gray, σ=2)) / 2 + 128)
  ch9     current gray

  delta = current.astype(int16) - registered_previous(hist[-min(lag, n)], current)

  Empty history → signed channels = 128, abs channels = 0.
  Short history clamps lag to available frames (reuse oldest).

Registration (phaseCorrelate + warpAffine) matches gostart within ~0.08 MAE
(±1 on a few percent of pixels under OpenCV 5.0). For bit-exact features when
gostart's pyd is importable, pass `registered_previous=tracker._registered_previous`.

`_prepare_gray`: remove green cursor → BGR2GRAY → INTER_AREA resize to (144, 96).
"""
from __future__ import annotations

from collections import deque
from typing import Callable, Deque, Optional, Sequence, Union

import cv2
import numpy as np

WORK_H = 96
WORK_W = 144
FEATURE_CHANNELS = 10
HISTORY_LAGS = (1, 2, 4)

History = Union[Sequence[np.ndarray], Deque[np.ndarray]]
RegisterFn = Callable[[np.ndarray, np.ndarray], np.ndarray]


def hanning_window() -> np.ndarray:
    return cv2.createHanningWindow((WORK_W, WORK_H), cv2.CV_32F)


def registered_previous(previous: np.ndarray, current: np.ndarray) -> np.ndarray:
    """
    Align `previous` onto `current` via phase correlation.

    phaseCorrelate mean-subtracts in place — warp a clean float copy.
    """
    earlier = np.ascontiguousarray(previous, dtype=np.float32)
    present = np.ascontiguousarray(current, dtype=np.float32)
    src = earlier.copy()
    shift, _response = cv2.phaseCorrelate(earlier, present, hanning_window())
    dx, dy = shift
    matrix = np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)
    warped = cv2.warpAffine(
        src,
        matrix,
        (WORK_W, WORK_H),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT_101,
    )
    if previous.dtype == np.uint8:
        return np.clip(np.rint(warped), 0, 255).astype(np.uint8)
    return warped


def encode_signed(delta: np.ndarray) -> np.ndarray:
    return np.clip(delta / 2.0 + 128.0, 0, 255).astype(np.uint8)


def encode_highpass(gray: np.ndarray) -> np.ndarray:
    blur = cv2.GaussianBlur(gray, (0, 0), sigmaX=2.0)
    delta = gray.astype(np.int16) - blur.astype(np.int16)
    return np.clip(delta / 2.0 + 128.0, 0, 255).astype(np.uint8)


def prepare_gray(crop_bgr: np.ndarray, remove_green: Optional[Callable[[np.ndarray], np.ndarray]] = None) -> np.ndarray:
    """Match gostart `_prepare_gray`: optional green wipe → gray → INTER_AREA (144×96)."""
    img = remove_green(crop_bgr) if remove_green is not None else crop_bgr
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, (WORK_W, WORK_H), interpolation=cv2.INTER_AREA)


def build_features(
    history: History,
    current: np.ndarray,
    *,
    registered_previous: RegisterFn = registered_previous,
) -> np.ndarray:
    """
    Replica of gostart `_build_features(history, current) -> (10, 96, 144) uint8`.

    `history` holds prior work-sized gray frames (oldest → newest), not including
    `current`. `registered_previous` can be swapped for tracker.pyd's helper.
    """
    if current.dtype != np.uint8 or current.shape != (WORK_H, WORK_W):
        raise ValueError(f"current must be uint8 ({WORK_H}, {WORK_W}), got {current.dtype} {current.shape}")

    frames = list(history)
    signed: list[np.ndarray] = []
    absolute: list[np.ndarray] = []
    for lag in HISTORY_LAGS:
        if not frames:
            signed.append(np.full((WORK_H, WORK_W), 128, dtype=np.uint8))
            absolute.append(np.zeros((WORK_H, WORK_W), dtype=np.uint8))
            continue
        previous = frames[-min(lag, len(frames))]
        reg = registered_previous(previous, current)
        delta = current.astype(np.int16) - reg.astype(np.int16)
        signed.append(encode_signed(delta))
        absolute.append(np.abs(delta).astype(np.uint8))

    abs_stack = np.stack(absolute, axis=0).astype(np.float32)
    mean_abs = abs_stack.mean(axis=0).astype(np.uint8)
    max_abs = abs_stack.max(axis=0).astype(np.uint8)
    highpass = encode_highpass(current)
    return np.stack(signed + absolute + [mean_abs, max_abs, highpass, current], axis=0)


def features_to_float01(features_u8: np.ndarray) -> np.ndarray:
    """ONNX-style [1,10,96,144] float32 in 0..1 from uint8 channels."""
    x = features_u8.astype(np.float32) / 255.0
    return x[None, ...]
