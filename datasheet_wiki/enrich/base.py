"""The pluggable enrichment backend interface.

A backend turns a section's title + raw text into an :class:`Enrichment`
(summary, keywords, detected registers, code examples). The three concrete
backends are:

    none      -> heuristics only, no LLM (HeuristicBackend)
    ollama    -> a local LLM served by Ollama
    anthropic -> the Claude API

All backends inherit the heuristic results as a *baseline* and layer their own
output on top, so even the LLM tiers always have register/code detection.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import List, Optional


@dataclass
class RegisterField:
    bits: str = ""
    name: str = ""
    access: str = ""
    description: str = ""


@dataclass
class Register:
    name: str
    description: str = ""
    address: str = ""
    fields: List[RegisterField] = field(default_factory=list)


@dataclass
class CodeExample:
    title: str
    language: str
    code: str


@dataclass
class Enrichment:
    summary: str = ""
    keywords: List[str] = field(default_factory=list)
    registers: List[Register] = field(default_factory=list)
    code_examples: List[CodeExample] = field(default_factory=list)
    backend: str = "none"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Enrichment":
        return cls(
            summary=d.get("summary", ""),
            keywords=list(d.get("keywords", [])),
            registers=[
                Register(
                    name=r.get("name", ""),
                    description=r.get("description", ""),
                    address=r.get("address", ""),
                    fields=[RegisterField(**f) for f in r.get("fields", [])],
                )
                for r in d.get("registers", [])
            ],
            code_examples=[CodeExample(**c) for c in d.get("code_examples", [])],
            backend=d.get("backend", "none"),
        )


class Backend:
    """Base class. Subclasses override :meth:`enrich`."""

    name = "none"

    def available(self) -> bool:  # pragma: no cover - overridden
        return True

    def enrich(self, title: str, text: str) -> Enrichment:  # pragma: no cover
        raise NotImplementedError

    # Optional: backends that can embed text for semantic search override this.
    def supports_embeddings(self) -> bool:
        return False

    def embed(self, texts: List[str]) -> List[List[float]]:  # pragma: no cover
        raise NotImplementedError


def get_backend(name: str, model: Optional[str] = None, **kwargs) -> Backend:
    name = (name or "none").lower()
    if name == "none":
        from .heuristic import HeuristicBackend

        return HeuristicBackend()
    if name == "ollama":
        from .ollama_backend import OllamaBackend

        return OllamaBackend(model=model, host=kwargs.get("ollama_host"))
    if name in ("anthropic", "claude"):
        from .anthropic_backend import AnthropicBackend

        return AnthropicBackend(model=model)
    raise ValueError(f"Unknown enrichment backend: {name!r}")
