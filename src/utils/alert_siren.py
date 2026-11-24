# -*- coding: utf-8 -*-
"""Shared loud alert siren (测谎 / 掉线). Non-blocking."""
from __future__ import annotations

import os
import threading
import time

from src.utils.logger import logger

_sound_lock = threading.Lock()
_sound_thread = None


def alert_wav_path() -> str:
    """Cached loud siren WAV under temp (regenerated if missing)."""
    import math
    import struct
    import tempfile
    import wave

    path = os.path.join(tempfile.gettempdir(), "lie_alert_siren_v2.wav")
    if os.path.isfile(path) and os.path.getsize(path) > 1000:
        return path
    rate = 22050
    secs = 1.6
    n = int(rate * secs)
    buf = bytearray()
    for i in range(n):
        t = i / rate
        f = 1760.0 if (int(t * 5) % 2 == 0) else 880.0
        env = 0.55 + 0.45 * abs(math.sin(2 * math.pi * 2.5 * t))
        v = int(32000 * env * math.sin(2 * math.pi * f * t))
        v = max(-32767, min(32767, v))
        buf.extend(struct.pack("<h", v))
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(buf))
    return path


def _sound_worker(label: str = "ALERT"):
    ok = False
    try:
        print(f"\a\a\a *** {label} ***", flush=True)
    except Exception:
        pass
    try:
        import winsound
    except ImportError:
        logger.warning("[AlertSiren] winsound missing — no alert sound")
        return
    try:
        wav = alert_wav_path()
        for _ in range(2):
            winsound.PlaySound(wav, winsound.SND_FILENAME | winsound.SND_NODEFAULT)
            ok = True
    except Exception as e:
        logger.warning(f"[AlertSiren] alert WAV failed: {e}")
    try:
        for _ in range(3):
            try:
                winsound.MessageBeep(winsound.MB_ICONHAND)
            except Exception:
                pass
            try:
                winsound.Beep(2000, 250)
                winsound.Beep(1100, 200)
                winsound.Beep(2000, 300)
                ok = True
            except Exception:
                try:
                    winsound.PlaySound(
                        "SystemHand",
                        winsound.SND_ALIAS | winsound.SND_NODEFAULT,
                    )
                    ok = True
                except Exception:
                    pass
            time.sleep(0.05)
    except Exception as e:
        logger.warning(f"[AlertSiren] alert beep failed: {e}")
    if ok:
        logger.info(f"[AlertSiren] alert sound played ({label})")
    else:
        logger.warning(
            "[AlertSiren] alert sound FAILED — check Windows volume mixer "
            "for python.exe / system sounds"
        )


def play_loud_alert(label: str = "ALERT") -> None:
    """Fire siren on a daemon thread (no-op if already playing)."""
    global _sound_thread
    with _sound_lock:
        if _sound_thread is not None and _sound_thread.is_alive():
            return
        _sound_thread = threading.Thread(
            target=_sound_worker,
            kwargs={"label": str(label or "ALERT")},
            daemon=True,
            name="AlertSiren",
        )
        _sound_thread.start()


def warm_alert_wav() -> None:
    try:
        alert_wav_path()
    except Exception:
        pass
