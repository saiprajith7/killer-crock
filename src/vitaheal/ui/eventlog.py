"""In-memory + on-disk logs for troubles, heals, and system updates."""

from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Deque, Iterable, Literal

Kind = Literal["trouble", "heal", "update"]


@dataclass
class LogEntry:
    kind: Kind
    title: str
    detail: str
    severity: str = "info"
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()

    @property
    def clock(self) -> str:
        return time.strftime("%H:%M:%S", time.localtime(self.timestamp))

    def as_dict(self) -> dict:
        return asdict(self)


class EventLog:
    """Streams: trouble, heal, and system update activity."""

    def __init__(self, maxlen: int = 200) -> None:
        self._trouble: Deque[LogEntry] = deque(maxlen=maxlen)
        self._heal: Deque[LogEntry] = deque(maxlen=maxlen)
        self._update: Deque[LogEntry] = deque(maxlen=maxlen)
        self._seen_troubles: set[str] = set()
        self._path = Path.home() / ".cache" / "boss-sentinel" / "events.jsonl"

    @property
    def trouble(self) -> list[LogEntry]:
        return list(reversed(self._trouble))

    @property
    def heal(self) -> list[LogEntry]:
        return list(reversed(self._heal))

    @property
    def update(self) -> list[LogEntry]:
        return list(reversed(self._update))

    def note_trouble(self, key: str, title: str, detail: str, severity: str = "warn") -> None:
        if key in self._seen_troubles:
            return
        self._seen_troubles.add(key)
        entry = LogEntry("trouble", title, detail, severity=severity)
        self._trouble.append(entry)
        self._persist(entry)

    def clear_trouble_key(self, key: str) -> None:
        self._seen_troubles.discard(key)

    def sync_active_troubles(self, active_keys: Iterable[str]) -> None:
        active = set(active_keys)
        self._seen_troubles &= active

    def note_heal(self, title: str, detail: str, ok: bool = True) -> None:
        entry = LogEntry(
            "heal",
            title,
            detail,
            severity="ok" if ok else "fail",
        )
        self._heal.append(entry)
        self._persist(entry)

    def note_declined(self, title: str) -> None:
        self.note_heal(f"Declined — {title}", "User chose No", ok=False)

    def note_update(self, title: str, detail: str, ok: bool = True) -> None:
        entry = LogEntry(
            "update",
            title,
            detail,
            severity="ok" if ok else "fail",
        )
        self._update.append(entry)
        self._persist(entry)

    def _persist(self, entry: LogEntry) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry.as_dict()) + "\n")
        except OSError:
            pass
