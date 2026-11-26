# -*- coding: utf-8 -*-
"""Offline probe: gostart ONNX heatmap on a local lie-detector clip."""
from __future__ import annotations

import argparse
import os
import sys
import time

import cv2
import numpy as np
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.engine.LieAlert import LieAlert  # noqa: E402
from src.engine.lie_heatmap_tracker import LieHeatmapTracker  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--video",
        default=os.path.join("_debug_out", "bilibili", "BV1Ueht6rEig_game.mp4"),
    )
    ap.add_argument(
        "--out",
        default=os.path.join("_debug_out", "gostart_heatmap_BV1Ueht6rEig.mp4"),
    )
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--every", type=int, default=1, help="run heatmap every N frames")
    args = ap.parse_args()
    if not os.path.isfile(args.video):
        print("missing video", args.video)
        return 1

    cfg = yaml.safe_load(
        open(os.path.join(ROOT, "config", "config_custom.yaml"), "r", encoding="utf-8")
    )
    la = LieAlert(cfg)
    hm = LieHeatmapTracker(cfg)
    if not hm._ensure_session():
        print("heatmap onnx unavailable", hm.model_path)
        return 1
    hm.note_opening_white(True, 0.0)  # force arm for offline probe

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print("cannot open", args.video)
        return 1
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    print(f"video {w}x{h} @ {fps:.1f}fps frames={n} model={hm.model_path}")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    writer = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    sample_dir = os.path.join("_debug_out", "gostart_heatmap_samples")
    os.makedirs(sample_dir, exist_ok=True)

    t0 = time.time()
    la.visible = True
    la._session_start_t = t0
    la._follow_ready_t = t0
    la._hold_until = t0 + 999
    la._reset_bg_model()
    hm.reset(t0)
    hm.note_opening_white(True, t0)

    i = 0
    hm_ok = 0
    hm_move = 0
    title_hits = 0
    sources: dict[str, int] = {}
    confs: list[float] = []
    wall0 = time.time()

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        i += 1
        if args.max_frames and i > args.max_frames:
            break
        now = t0 + i / max(fps, 1.0)

        if i <= 12:
            la._learn_background(frame, locked=False)

        # Refresh title TL (non-intro) for gostart crop
        found, hit, _ = la._match_templates(frame)
        title_tl = getattr(la, "_lie_title_tl", None)
        if title_tl is not None:
            title_hits += 1

        est = None
        if i % max(1, args.every) == 0:
            dialog = la._dialog_roi(w, h)
            est = hm.push(
                frame,
                now,
                dialog_xyxy=dialog,
                title_tl=title_tl,
            )
            if est is not None:
                hm_ok += 1
                sources[est.source] = sources.get(est.source, 0) + 1
                confs.append(float(est.confidence))
                if hm.may_move(est):
                    hm_move += 1

        pt = la._locate_shape(frame, now) if i > 12 else None

        vis = frame.copy()
        if title_tl is not None:
            cv2.circle(vis, (int(title_tl[0]), int(title_tl[1])), 6, (255, 128, 0), 2)
            cv2.putText(
                vis,
                "title",
                (int(title_tl[0]) + 8, int(title_tl[1]) - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 128, 0),
                1,
            )
        if est is not None:
            hx, hy = int(est.x), int(est.y)
            color = (0, 255, 255) if hm.may_move(est) else (0, 165, 255)
            cv2.drawMarker(vis, (hx, hy), color, cv2.MARKER_CROSS, 24, 2)
            cv2.circle(vis, (hx, hy), 10, color, 2)
            cv2.putText(
                vis,
                f"HM {est.source} c={est.confidence:.2f} s={est.secondary_ratio:.2f} "
                f"crop={hm._crop_mode}",
                (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
            )
        if pt is not None:
            cv2.circle(vis, (int(pt[0]), int(pt[1])), 8, (0, 0, 255), 2)
            name = getattr(la, "_last_shape_name", "") or "-"
            cv2.putText(
                vis,
                f"LOC {name}",
                (12, 54),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 0, 255),
                2,
            )
        cv2.putText(
            vis,
            f"f={i}/{n} title_tl={title_tl} hit={hit or '-'}",
            (12, h - 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
        )
        writer.write(vis)

        # samples around fade (~7s) and mid
        t_sec = i / max(fps, 1.0)
        if i in {30, 60, 90, 120, 150, 180, 210, 240, 300, 360} or (
            6.5 <= t_sec <= 12.0 and i % 15 == 0
        ):
            cv2.imwrite(os.path.join(sample_dir, f"f{i:05d}.jpg"), vis)

        if i % 60 == 0:
            print(
                f"f={i} title={title_tl} est="
                f"{None if est is None else (round(est.x,1), round(est.y,1), est.source, round(est.confidence,3))}"
            )

    cap.release()
    writer.release()
    elapsed = time.time() - wall0
    print("---")
    print(f"frames={i} wall={elapsed:.1f}s fps={i/max(elapsed,1e-6):.1f}")
    print(f"title_tl_frames={title_hits}/{i}")
    print(f"heatmap_ok={hm_ok} may_move={hm_move} sources={sources}")
    if confs:
        print(
            f"conf mean={float(np.mean(confs)):.3f} "
            f"p50={float(np.median(confs)):.3f} min={float(np.min(confs)):.3f}"
        )
    print("out", args.out)
    print("samples", sample_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
