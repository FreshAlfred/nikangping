# -*- coding: utf-8 -*-
"""Compare src.engine.gostart_lie_features against NavigationGPS tracker.pyd."""
from __future__ import annotations

import argparse
import os
import sys
from collections import deque
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _load_local_features():
    import importlib.util

    path = ROOT / "src" / "engine" / "gostart_lie_features.py"
    spec = importlib.util.spec_from_file_location("gostart_lie_features", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.HISTORY_LAGS, mod.build_features, mod.encode_highpass, mod.registered_previous


def _load_tracker(nav_dir: Path, pkg_dir: Path):
    os.add_dll_directory(str(nav_dir))
    sys.path.insert(0, str(pkg_dir))
    import src.features.lie_detector.tracker as tracker  # type: ignore

    return tracker


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--nav",
        default=r"C:\Program Files\NavigationGPS\10.0.1-6664229309d07e9e00e763295d6b8dc3a48aca426501cea491aeae666d702587",
    )
    ap.add_argument("--pkg", default=r"C:\ghidra-work\gostart_pkg")
    args = ap.parse_args()

    tracker = _load_tracker(Path(args.nav), Path(args.pkg))
    HISTORY_LAGS, build_features, encode_highpass, local_registered_previous = _load_local_features()
    print("HISTORY_LAGS", tracker.HISTORY_LAGS, "local", HISTORY_LAGS)

    def prep(cx: int, seed: int) -> np.ndarray:
        rng = np.random.default_rng(seed + cx)
        img = np.zeros((501, 752, 3), np.uint8)
        img[:] = 45
        noise = rng.integers(0, 60, (501, 752), dtype=np.uint8)
        for c in range(3):
            img[:, :, c] = cv2.add(img[:, :, c], noise)
        cv2.circle(img, (cx, 255), 38, (220, 220, 220), -1)
        return tracker._prepare_gray(img)

    gs = [prep(280 + i * 7, i) for i in range(8)]

    print("--- channel formula with pyd _registered_previous ---")
    ok_channels = True
    for n in range(0, 8):
        hist = deque(gs[:n], maxlen=16)
        cur = gs[0] if n == 0 else gs[n]
        theirs = tracker._build_features(hist, cur)
        ours = build_features(hist, cur, registered_previous=tracker._registered_previous)
        eq = np.array_equal(theirs, ours)
        mae = float(np.mean(np.abs(theirs.astype(int) - ours.astype(int))))
        print(f"n_hist={n} eq={eq} mae={mae}")
        ok_channels &= eq

    print("--- full local replica (own registration) ---")
    ok_full = True
    for n in range(0, 8):
        hist = deque(gs[:n], maxlen=16)
        cur = gs[0] if n == 0 else gs[n]
        theirs = tracker._build_features(hist, cur)
        ours = build_features(hist, cur)
        eq = np.array_equal(theirs, ours)
        mae = float(np.mean(np.abs(theirs.astype(int) - ours.astype(int))))
        print(f"n_hist={n} eq={eq} mae={mae:.6f}")
        ok_full &= eq

    # highpass / ch9 spot checks
    cur = gs[-1]
    out = tracker._build_features(deque(gs[:-1], maxlen=16), cur)
    hp = encode_highpass(cur)
    print("ch8 highpass exact", np.array_equal(out[8], hp))
    print("ch9 current exact", np.array_equal(out[9], cur))

    g0, g1 = gs[0], gs[1]
    reg_t = tracker._registered_previous(g0, g1)
    reg_m = local_registered_previous(g0, g1)
    print(
        "registration mae",
        float(np.mean(np.abs(reg_t.astype(int) - reg_m.astype(int)))),
        "ndiff",
        int(np.count_nonzero(reg_t != reg_m)),
    )

    print("RESULT channels_bitexact", ok_channels, "full_replica_bitexact", ok_full)
    return 0 if ok_channels else 1


if __name__ == "__main__":
    raise SystemExit(main())
