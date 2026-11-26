# -*- coding: utf-8 -*-
"""
Disconnect / login-screen alert (对标 gostart「掉线提醒」).

Triggers on:
  1) sustained game-window capture loss (minimized / closed / unbound)
  2) optional template match under assets/disconnect/
  3) async OCR keywords (重新登录 / 选择角色 / …)

On hit: loud siren + pause AFK. No auto-login.
"""
from __future__ import annotations

import glob
import os
import threading
import time

import cv2
import numpy as np

from src.utils.logger import logger


class DisconnectAlert:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        da = cfg.get("disconnect_alert") or {}
        self.enable = bool(da.get("enable", True))
        self.sensitivity = float(da.get("sensitivity", 50.0))
        self.check_interval_frames = max(1, int(da.get("check_interval_frames", 8)))
        self.miss_frames = max(5, int(da.get("miss_frames", 45)))
        self.hold_seconds = float(da.get("hold_seconds", 20.0))
        self.freeze_seconds = float(da.get("freeze_seconds", 8.0))
        self.alert_cooldown_s = float(da.get("alert_cooldown_s", 8.0))
        self.match_threshold = float(da.get("match_threshold", 0.14))
        self.templates_dir = str(da.get("templates_dir", "assets/disconnect") or "")
        extras = da.get("templates") or []
        if isinstance(extras, str):
            extras = [extras]
        self.extra_templates = [str(p) for p in extras if str(p).strip()]
        self.ocr_enable = bool(da.get("ocr_enable", True))
        self.ocr_min_interval_s = float(da.get("ocr_min_interval_s", 6.0))
        kws = da.get("ocr_keywords") or [
            "重新登录",
            "请重新登录",
            "选择角色",
            "频道选择",
            "与服务器断开",
            "连接中断",
            "登录器",
        ]
        if isinstance(kws, str):
            kws = [kws]
        self.ocr_keywords = [str(k).strip() for k in kws if str(k).strip()]

        self.visible = False
        self._was_visible = False
        self._hold_until = 0.0
        self._last_alert_t = 0.0
        self._miss_streak = 0
        self._last_score = 1.0
        self._last_hit = ""
        self._tmpl_list = []  # (path, gray)
        self._ocr = None
        self._ocr_init_tried = False
        self._ocr_fail_logged = False
        self._ocr_lock = threading.Lock()
        self._ocr_busy = False
        self._pending_ocr_hit = ""
        self._ocr_submit_t = 0.0
        self._last_ocr_t = 0.0

        if self.enable:
            self._load_templates()
            try:
                from src.utils.alert_siren import warm_alert_wav

                warm_alert_wav()
            except Exception:
                pass

    def reload_cfg(self, cfg: dict):
        self.cfg = cfg
        da = cfg.get("disconnect_alert") or {}
        self.enable = bool(da.get("enable", self.enable))
        self.sensitivity = float(da.get("sensitivity", self.sensitivity))
        self.check_interval_frames = max(
            1, int(da.get("check_interval_frames", self.check_interval_frames))
        )
        self.miss_frames = max(5, int(da.get("miss_frames", self.miss_frames)))
        self.hold_seconds = float(da.get("hold_seconds", self.hold_seconds))
        self.freeze_seconds = float(da.get("freeze_seconds", self.freeze_seconds))
        self.alert_cooldown_s = float(da.get("alert_cooldown_s", self.alert_cooldown_s))
        self.match_threshold = float(da.get("match_threshold", self.match_threshold))
        self.templates_dir = str(
            da.get("templates_dir", self.templates_dir) or self.templates_dir
        )
        extras = da.get("templates")
        if extras is not None:
            if isinstance(extras, str):
                extras = [extras]
            self.extra_templates = [str(p) for p in extras if str(p).strip()]
        self.ocr_enable = bool(da.get("ocr_enable", self.ocr_enable))
        self.ocr_min_interval_s = float(
            da.get("ocr_min_interval_s", self.ocr_min_interval_s)
        )
        kws = da.get("ocr_keywords")
        if kws is not None:
            if isinstance(kws, str):
                kws = [kws]
            self.ocr_keywords = [str(k).strip() for k in kws if str(k).strip()]
        self._load_templates()

    def _sensitivity_scale(self) -> float:
        s = max(0.0, min(100.0, float(self.sensitivity or 50.0)))
        return 0.7 + (s / 100.0) * 0.7

    def _load_templates(self):
        self._tmpl_list = []
        paths = list(self.extra_templates)
        if self.templates_dir and os.path.isdir(self.templates_dir):
            for ext in ("*.png", "*.jpg", "*.jpeg", "*.bmp"):
                paths.extend(glob.glob(os.path.join(self.templates_dir, ext)))
        seen = set()
        loaded = 0
        for path in paths:
            path = os.path.normpath(str(path).strip())
            if not path or path in seen or not os.path.exists(path):
                continue
            seen.add(path)
            base = os.path.basename(path).lower()
            if base.startswith("readme") or base.startswith("ref_"):
                continue
            img = cv2.imread(path, cv2.IMREAD_COLOR)
            if img is None:
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            self._tmpl_list.append((path, gray))
            loaded += 1
            logger.info(
                f"[DisconnectAlert] Loaded template {gray.shape[1]}x{gray.shape[0]} "
                f"from {path}"
            )
        if loaded == 0:
            logger.info(
                "[DisconnectAlert] No UI templates yet — window-loss + OCR only. "
                "Drop crops into assets/disconnect/ to harden login/char-select detect."
            )

    def note_frame_miss(self, kb=None) -> bool:
        """Call when capture failed / window missing. Returns visible sticky."""
        if not self.enable:
            return False
        self._miss_streak += 1
        now = time.time()
        if self._miss_streak >= int(self.miss_frames):
            self._trigger(
                now,
                hit=f"window_lost x{self._miss_streak}",
                score=0.0,
                kb=kb,
            )
        elif self.visible and now < float(self._hold_until):
            if kb is not None:
                try:
                    kb.pause_for_lie_alert(self.freeze_seconds)
                except Exception:
                    pass
        return self.visible

    def note_frame_ok(self):
        self._miss_streak = 0

    def maybe_check(self, img_frame_bgr, frame_count: int, kb=None, capture=None) -> bool:
        """Detect login/char-select UI on a good frame. Returns sticky visible."""
        if not self.enable:
            self.visible = False
            self._was_visible = False
            self._hold_until = 0.0
            self._miss_streak = 0
            return False

        self.note_frame_ok()
        now = time.time()
        found = False
        hit = ""

        pending = self._consume_pending_ocr() if self.ocr_enable else ""
        do_detect = frame_count % self.check_interval_frames == 0
        if do_detect and img_frame_bgr is not None and getattr(img_frame_bgr, "size", 0) > 0:
            tmpl_hit = self._match_templates(img_frame_bgr)
            if tmpl_hit:
                found = True
                hit = tmpl_hit
            elif pending:
                found = True
                hit = f"ocr:{pending}"
            elif self.ocr_enable:
                # Rare async OCR — only when not already sticky
                if not self.visible or now >= float(self._hold_until):
                    self._submit_ocr_async(img_frame_bgr, reason="disconnect_scan")
        elif pending:
            found = True
            hit = f"ocr:{pending}"

        if found:
            self._trigger(now, hit=hit, score=float(self._last_score), kb=kb)
        elif self.visible and now >= float(self._hold_until):
            self.visible = False
            if self._was_visible:
                logger.info("[DisconnectAlert] cleared — AFK may resume")
                if kb is not None:
                    try:
                        kb.clear_lie_alert_freeze()
                    except Exception:
                        pass
            self._was_visible = False
        elif self.visible:
            if kb is not None:
                try:
                    kb.pause_for_lie_alert(self.freeze_seconds)
                except Exception:
                    pass

        self._was_visible = self.visible
        return self.visible

    def _trigger(self, now: float, hit: str, score: float, kb=None):
        rising = not self.visible or now >= float(self._hold_until)
        self.visible = True
        self._hold_until = now + max(1.0, self.hold_seconds)
        self._last_hit = hit
        self._last_score = float(score)
        if rising and (now - float(self._last_alert_t)) >= max(
            1.0, self.alert_cooldown_s
        ):
            self._last_alert_t = now
            logger.warning(
                f"[ALERT] 掉线提醒 via {hit} (score={score:.3f}, "
                f"sens={float(self.sensitivity):.0f}, "
                f"hold={max(0.0, self._hold_until - now):.1f}s) — pause AFK"
            )
            try:
                from src.utils.alert_siren import play_loud_alert

                play_loud_alert("掉线提醒")
            except Exception as e:
                logger.warning(f"[DisconnectAlert] siren failed: {e}")
        if kb is not None:
            try:
                kb.pause_for_lie_alert(self.freeze_seconds)
            except Exception as e:
                logger.debug(f"[DisconnectAlert] pause failed: {e}")

    def _match_templates(self, img_bgr) -> str:
        if not self._tmpl_list:
            return ""
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        fh, fw = gray.shape[:2]
        thr = max(0.05, min(0.28, float(self.match_threshold) * self._sensitivity_scale()))
        best = None
        for path, tmpl in self._tmpl_list:
            th, tw = tmpl.shape[:2]
            if tw >= fw or th >= fh:
                continue
            try:
                res = cv2.matchTemplate(gray, tmpl, cv2.TM_SQDIFF_NORMED)
                min_val = float(np.nanmin(res))
            except Exception:
                continue
            if not np.isfinite(min_val):
                continue
            if min_val <= thr and (best is None or min_val < best[0]):
                best = (min_val, path)
        if best is None:
            return ""
        self._last_score = float(best[0])
        return f"tmpl:{os.path.basename(best[1])}"

    def _ensure_ocr(self):
        if self._ocr is not None or self._ocr_init_tried:
            return
        self._ocr_init_tried = True
        try:
            from rapidocr_onnxruntime import RapidOCR

            self._ocr = RapidOCR()
            logger.info(
                f"[DisconnectAlert] OCR ready keywords={self.ocr_keywords}"
            )
        except Exception as e:
            self._ocr = None
            if not self._ocr_fail_logged:
                logger.warning(f"[DisconnectAlert] OCR unavailable ({e})")
                self._ocr_fail_logged = True

    def _submit_ocr_async(self, img_bgr, reason: str = ""):
        if not self.ocr_enable:
            return
        now = time.time()
        if (now - float(self._ocr_submit_t or 0.0)) < max(1.0, self.ocr_min_interval_s):
            return
        with self._ocr_lock:
            if self._ocr_busy:
                return
            self._ocr_busy = True
            self._ocr_submit_t = now
            self._last_ocr_t = now
        try:
            frame = img_bgr.copy()
        except Exception:
            with self._ocr_lock:
                self._ocr_busy = False
            return

        def _worker():
            hit = ""
            try:
                self._ensure_ocr()
                if self._ocr is not None:
                    hit = self._match_ocr(frame) or ""
            except Exception as e:
                logger.debug(f"[DisconnectAlert] async OCR error: {e}")
            finally:
                with self._ocr_lock:
                    if hit:
                        self._pending_ocr_hit = hit
                        logger.info(
                            f"[DisconnectAlert] async OCR hit={hit}"
                            + (f" ({reason})" if reason else "")
                        )
                    self._ocr_busy = False

        threading.Thread(target=_worker, daemon=True, name="DiscOCR").start()

    def _consume_pending_ocr(self) -> str:
        with self._ocr_lock:
            hit = str(getattr(self, "_pending_ocr_hit", "") or "")
            self._pending_ocr_hit = ""
            return hit

    @staticmethod
    def _normalize_ocr_text(s: str) -> str:
        return "".join(ch for ch in str(s).upper() if not ch.isspace())

    def _suppress_ocr_keywords(self):
        """OCR 关键词抑制表（商城等非游戏画面），返回已归一化的词。"""
        raw = (self.cfg.get("disconnect_alert") or {}).get("suppress_keywords") or []
        out = []
        for k in raw:
            nk = self._normalize_ocr_text(k)
            if nk:
                out.append(nk)
        return out

    def _match_ocr(self, img_bgr) -> str:
        if self._ocr is None or not self.ocr_keywords:
            return ""
        fh, fw = img_bgr.shape[:2]
        rois = [
            img_bgr[int(fh * 0.05) : int(fh * 0.55), int(fw * 0.15) : int(fw * 0.85)],
            img_bgr[int(fh * 0.20) : int(fh * 0.80), int(fw * 0.20) : int(fw * 0.80)],
        ]
        for roi in rois:
            if roi is None or getattr(roi, "size", 0) == 0:
                continue
            h, w = roi.shape[:2]
            if max(h, w) < 480:
                scale = 480.0 / max(h, w)
                roi = cv2.resize(
                    roi,
                    (int(w * scale), int(h * scale)),
                    interpolation=cv2.INTER_CUBIC,
                )
            try:
                result, _ = self._ocr(roi)
            except Exception:
                continue
            if not result:
                continue
            blob = " ".join(str(item[1]) for item in result if len(item) >= 2)
            blob_n = self._normalize_ocr_text(blob)
            # 商城/现金商城等画面里的「重新登录」按钮会误报掉线，先查抑制词。
            for sk in self._suppress_ocr_keywords():
                if sk in blob_n:
                    self._last_score = 1.0
                    return ""
            for kw in self.ocr_keywords:
                if not kw:
                    continue
                if self._normalize_ocr_text(kw) in blob_n or kw in blob:
                    self._last_score = 0.0
                    return kw
        return ""
