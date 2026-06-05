"""Local LLM enrichment via Ollama (the 'medium' tier).

Talks to a locally running Ollama server (https://ollama.com) over HTTP using
only the standard library, so no extra Python dependency is required. Nothing
leaves the user's machine.

    ollama pull llama3.1        # or qwen2.5, mistral, phi3, ...
    ollama serve                # usually already running
    datasheet-wiki build ds.pdf --compute medium --model llama3.1

Local embeddings for semantic search are handled separately (sentence-
transformers); see datasheet_wiki/search/embeddings.py.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Optional

from ..utils import log
from .base import Backend, Enrichment
from .heuristic import baseline
from .prompts import SYSTEM, build_user_prompt
from .parse import merge_llm_json

DEFAULT_MODEL = "llama3.1"


class OllamaBackend(Backend):
    name = "ollama"

    def __init__(self, model: Optional[str] = None, host: Optional[str] = None, timeout: int = 600):
        self.model = model or DEFAULT_MODEL
        self.host = (host or "http://localhost:11434").rstrip("/")
        self.timeout = timeout
        self._warned = False

    def available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.host}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _generate(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "system": SYSTEM,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.host}/api/generate", data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body.get("response", "")

    def enrich(self, title: str, text: str) -> Enrichment:
        base = baseline(title, text, backend=self.name)
        if not text.strip():
            return base
        try:
            raw = self._generate(build_user_prompt(title, text))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if not self._warned:
                log(f"Ollama unreachable ({exc}); falling back to heuristics.")
                self._warned = True
            return base
        return merge_llm_json(raw, base, backend=self.name)
