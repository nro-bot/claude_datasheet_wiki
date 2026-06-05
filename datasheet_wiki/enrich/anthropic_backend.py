"""Cloud LLM enrichment via the Claude API (the 'large' tier).

Uses the official `anthropic` SDK. Requires `uv sync --extra api`
and an ANTHROPIC_API_KEY in the environment.

Cost notes for big datasheets:
  * The stable system prompt is cached with prompt caching, so re-runs and the
    many per-section calls only pay full price for it once per 5-minute window.
  * Default model is claude-opus-4-8 (highest quality). For a 600-page datasheet
    with thousands of sections you may prefer a cheaper model — pass
    `--model claude-haiku-4-5` to cut cost dramatically.
  * Results are cached to disk per section (see pipeline), so an interrupted run
    resumes without re-paying for completed sections.
"""
from __future__ import annotations

import os
from typing import Optional

from ..utils import log
from .base import Backend, Enrichment
from .heuristic import baseline
from .parse import merge_llm_json
from .prompts import SYSTEM, build_user_prompt

DEFAULT_MODEL = "claude-opus-4-8"

# JSON schema for structured outputs (kept within the documented constraints:
# every object sets additionalProperties:false; no min/max/length keywords).
_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "registers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "address": {"type": "string"},
                    "description": {"type": "string"},
                    "fields": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "bits": {"type": "string"},
                                "name": {"type": "string"},
                                "access": {"type": "string"},
                                "description": {"type": "string"},
                            },
                            "required": ["bits", "name", "access", "description"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["name", "address", "description", "fields"],
                "additionalProperties": False,
            },
        },
        "code_examples": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "language": {"type": "string"},
                    "code": {"type": "string"},
                },
                "required": ["title", "language", "code"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "keywords", "registers", "code_examples"],
    "additionalProperties": False,
}


class AnthropicBackend(Backend):
    name = "anthropic"

    def __init__(self, model: Optional[str] = None, max_tokens: int = 4096):
        self.model = model or DEFAULT_MODEL
        self.max_tokens = max_tokens
        self._client = None
        self._warned = False

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "The 'anthropic' package is required for the large tier. "
                    "Install it with: uv sync --extra api"
                ) from exc
            # Anthropic() resolves ANTHROPIC_API_KEY from the environment.
            self._client = anthropic.Anthropic()
        return self._client

    def available(self) -> bool:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def enrich(self, title: str, text: str) -> Enrichment:
        base = baseline(title, text, backend=self.name)
        if not text.strip():
            return base
        try:
            client = self._get_client()
            resp = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                # Disable thinking: this is structured extraction, and we want
                # cheap, JSON-only output across many sections.
                thinking={"type": "disabled"},
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
                messages=[{"role": "user", "content": build_user_prompt(title, text)}],
            )
            raw = next((b.text for b in resp.content if b.type == "text"), "")
        except Exception as exc:  # pragma: no cover - network/credentials
            if not self._warned:
                log(f"Anthropic API error ({exc}); falling back to heuristics.")
                self._warned = True
            return base
        return merge_llm_json(raw, base, backend=self.name)
