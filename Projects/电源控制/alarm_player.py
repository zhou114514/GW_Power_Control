# -*- coding: utf-8 -*-
"""
声音警报模块。

这个文件用于把参考项目里的“声音警报”能力，复现成当前 Python 项目里可复用的小模块。

设计目标很简单：
1. 对外只暴露一个很薄的类 `AlarmPlayer`
2. 发生告警时调用 `play_warning()`
3. 优先播放项目内的 `报警声.wav`
4. 如果找不到 wav 文件，就退回到系统蜂鸣
"""

from __future__ import annotations

from pathlib import Path
import threading
import time

try:
    import winsound
except ImportError:  # pragma: no cover
    winsound = None


ROOT_PATH = Path(__file__).resolve().parents[2]
DEFAULT_ALARM_WAV = ROOT_PATH / "报警声.wav"


class AlarmPlayer:
    """
    简单的声音警报播放器。

    这里做了一个很轻的节流，避免采集线程短时间连续触发过流时，
    多段报警声重叠播放，导致体验很差。
    """

    def __init__(self, wav_path: str | None = None, cooldown_seconds: float = 1.5):
        self.wav_path = Path(wav_path).resolve() if wav_path else DEFAULT_ALARM_WAV
        self.cooldown_seconds = max(float(cooldown_seconds), 0.0)
        self._last_play_time = 0.0
        self._lock = threading.Lock()

    def play_warning(self) -> None:
        with self._lock:
            now = time.monotonic()
            if now - self._last_play_time < self.cooldown_seconds:
                return
            self._last_play_time = now

        self._play_once()

    def _play_once(self) -> None:
        if winsound is None:
            return

        if self.wav_path.exists():
            winsound.PlaySound(
                str(self.wav_path),
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )
            return

        winsound.MessageBeep(winsound.MB_ICONHAND)
