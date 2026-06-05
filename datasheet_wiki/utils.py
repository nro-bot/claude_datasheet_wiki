"""Small, dependency-free helpers shared across the package."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Iterator


# ---------------------------------------------------------------------------
# Filesystem
# ---------------------------------------------------------------------------
def ensure_dir(path: Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, data: Any) -> None:
    ensure_dir(Path(path).parent)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


# ---------------------------------------------------------------------------
# Hashing (used for resumable caching keyed by content)
# ---------------------------------------------------------------------------
def sha1_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def sha1_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Slugs / ids
# ---------------------------------------------------------------------------
_slug_re = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_len: int = 60) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = _slug_re.sub("-", text).strip("-")
    if len(text) > max_len:
        text = text[:max_len].rstrip("-")
    return text or "section"


def human_size(num: int) -> str:
    f = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if f < 1024 or unit == "GB":
            return f"{f:.1f}{unit}" if unit != "B" else f"{int(f)}{unit}"
        f /= 1024
    return f"{f:.1f}GB"


# ---------------------------------------------------------------------------
# Lightweight progress / logging (no extra dependency)
# ---------------------------------------------------------------------------
class Progress:
    """Minimal, tqdm-free progress reporter that is friendly to log files."""

    def __init__(self, total: int, label: str, enabled: bool = True, every: float = 0.5):
        self.total = max(total, 0)
        self.label = label
        self.enabled = enabled and total > 0
        self.every = every
        self.n = 0
        self._start = time.time()
        self._last = 0.0

    def update(self, step: int = 1) -> None:
        self.n += step
        now = time.time()
        if not self.enabled:
            return
        if now - self._last < self.every and self.n < self.total:
            return
        self._last = now
        frac = self.n / self.total if self.total else 1.0
        elapsed = now - self._start
        eta = (elapsed / frac - elapsed) if frac > 0 else 0.0
        bar_w = 24
        filled = int(bar_w * frac)
        bar = "#" * filled + "-" * (bar_w - filled)
        sys.stderr.write(
            f"\r  {self.label:<22} [{bar}] {self.n}/{self.total} "
            f"({frac*100:4.0f}%) eta {eta:5.0f}s"
        )
        sys.stderr.flush()

    def close(self) -> None:
        if self.enabled:
            sys.stderr.write("\n")
            sys.stderr.flush()


def log(msg: str) -> None:
    sys.stderr.write(f"[datasheet-wiki] {msg}\n")
    sys.stderr.flush()


def chunked(seq: list, size: int) -> Iterator[list]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def batched(it: Iterable, size: int) -> Iterator[list]:
    batch: list = []
    for item in it:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch
