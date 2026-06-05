"""Configuration objects and the compute-tier presets.

The three tiers map directly onto the project's "small / medium / large amount
of compute, including locally instead of an LLM API" requirement:

    small   -> no LLM at all. Pure heuristics + full-text search. Runs anywhere.
    medium  -> a *local* LLM via Ollama (+ optional local embeddings). No API,
               nothing leaves your machine.
    large   -> a cloud LLM API (Anthropic by default) for the best summaries,
               register extraction, code examples and a local embedding index.

`--backend`, `--dpi`, `--semantic` etc. can override any preset value.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

TIERS = ("small", "medium", "large")

# backend -> whether it is a network/API call (used for warnings & docs)
LOCAL_BACKENDS = {"none", "ollama"}
API_BACKENDS = {"anthropic", "openai"}


@dataclass
class TierPreset:
    backend: str
    dpi: int
    semantic: bool
    description: str


TIER_PRESETS = {
    "small": TierPreset(
        backend="none",
        dpi=120,
        semantic=False,
        description="No LLM. Heuristic cross-links, register/code detection, "
        "full-text search. Minutes, runs on any laptop.",
    ),
    "medium": TierPreset(
        backend="ollama",
        dpi=150,
        semantic=True,
        description="Local LLM via Ollama + local embeddings. Per-section "
        "summaries and a local embedding index. Nothing leaves your machine.",
    ),
    "large": TierPreset(
        backend="anthropic",
        dpi=200,
        semantic=True,
        description="Cloud LLM API. Best summaries, structured register "
        "extraction, generated code examples, embedding index.",
    ),
}


@dataclass
class Config:
    pdf_path: Path
    out_dir: Path
    cache_dir: Path

    compute: str = "small"
    backend: str = "none"
    model: Optional[str] = None  # backend-specific model id; None -> backend default

    # Rendering
    dpi: int = 120
    image_format: str = "png"  # png|webp|jpg
    render_images: bool = True

    # Search
    semantic: bool = False
    embed_model: str = "all-MiniLM-L6-v2"  # local sentence-transformers model
    chunk_chars: int = 1200  # target size of a search/embedding chunk

    # Authoritative register data (CMSIS-SVD); overrides PDF heuristics for the
    # register map + C-header export when supplied.
    svd_path: Optional[Path] = None

    # Scope / performance
    max_pages: int = 0  # 0 == all pages (useful for quick test runs)
    resume: bool = True

    # Site
    title: Optional[str] = None  # defaults to PDF title / filename

    # Ollama
    ollama_host: str = "http://localhost:11434"

    # internal
    progress: bool = True

    @classmethod
    def from_tier(cls, pdf_path: Path, out_dir: Path, compute: str, **overrides) -> "Config":
        if compute not in TIER_PRESETS:
            raise ValueError(f"Unknown compute tier {compute!r}; choose from {TIERS}")
        preset = TIER_PRESETS[compute]
        cache_dir = overrides.pop("cache_dir", None) or (Path(out_dir) / ".dsw-cache")
        cfg = cls(
            pdf_path=Path(pdf_path),
            out_dir=Path(out_dir),
            cache_dir=Path(cache_dir),
            compute=compute,
            backend=preset.backend,
            dpi=preset.dpi,
            semantic=preset.semantic,
        )
        for key, value in overrides.items():
            if value is None:
                continue
            if not hasattr(cfg, key):
                raise ValueError(f"Unknown config override: {key}")
            setattr(cfg, key, value)
        return cfg

    @property
    def is_api_backend(self) -> bool:
        return self.backend in API_BACKENDS
