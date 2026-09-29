"""Hindsight by Vectorize - memory service.

Thin, defensive wrapper around the Hindsight HTTP API (retain / recall) plus a
graceful local fallback so the app never crashes when Hindsight is unreachable.

Docs: https://hindsight.vectorize.io
API base: {HINDSIGHT_API_URL}/v1/default/banks/{bank_id}
  POST /memories          retain { items: [{content, context, metadata, ...}] }
  POST /memories/recall   recall { query, budget, max_tokens }
"""

import logging
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from backend.core.config import get_settings

logger = logging.getLogger(__name__)


class HindsightService:
    """Memory layer: remember (retain) + recall via Hindsight by Vectorize."""

    def __init__(self) -> None:
        s = get_settings()
        self.bank_id = s.hindsight_bank_id
        self.base_url = (s.hindsight_api_url or "").rstrip("/")
        self.api_key = s.hindsight_api_key
        self.timeout = s.hindsight_timeout
        self._local: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._available: bool | None = None
        self._last_check = 0.0

    # ------------------------------------------------------------- status ----

    @property
    def available(self) -> bool:
        """True when a real Hindsight backend is configured and reachable."""
        if not self.base_url:
            return False
        now = time.monotonic()
        if self._available is None or (now - self._last_check) > 30:
            try:
                resp = httpx.get(f"{self.base_url}/health", timeout=2.0)
                self._available = resp.status_code == 200
            except Exception:
                self._available = False
            self._last_check = now
        return self._available

    @property
    def mode(self) -> str:
        return "hindsight" if self.available else "local"

    # ---------------------------------------------------------- internals ----

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = "Bearer " + self.api_key
        return h

    def _url(self, path: str) -> str:
        return self.base_url + "/v1/default/banks/" + self.bank_id + path

    @staticmethod
    def _extract_results(data: dict | None) -> list[dict]:
        results = (data or {}).get("results") or []
        out = []
        for r in results:
            if not isinstance(r, dict):
                continue
            out.append({
                "text": str(r.get("text") or "").strip(),
                "context": str(r.get("context") or ""),
                "fact_type": str(r.get("fact_type") or ""),
                "score": float(r.get("score") or 0.0),
                "metadata": r.get("metadata") or {},
            })
        return out

    # ------------------------------------------------------------ retain ----

    def retain(self, content: str, context: str = "", metadata: dict | None = None,
               document_id: str | None = None, timestamp: str | None = None) -> bool:
        """Retain one item. Returns True only if Hindsight accepted it."""
        if not content or not content.strip():
            return False
        if self.available:
            item: dict[str, Any] = {
                "content": content,
                "context": context or "content strategy",
            }
            if metadata:
                item["metadata"] = metadata
            if document_id:
                item["document_id"] = document_id
            if timestamp:
                item["timestamp"] = timestamp
            try:
                resp = httpx.post(
                    self._url("/memories"),
                    json={"items": [item]},
                    headers=self._headers(),
                    timeout=self.timeout,
                )
                if resp.status_code in (200, 201, 202):
                    return True
                logger.warning("Hindsight retain failed: %s %s", resp.status_code, resp.text[:200])
            except Exception:
                logger.exception("Hindsight retain error")
            return False
        with self._lock:
            self._local.append({
                "text": content,
                "context": context,
                "metadata": metadata or {},
                "at": datetime.now(timezone.utc).isoformat(),
            })
        return False

    def retain_batch(self, items: list[dict]) -> int:
        """Retain multiple items in one call; returns count accepted by Hindsight."""
        if not items:
            return 0
        if self.available:
            try:
                resp = httpx.post(
                    self._url("/memories"),
                    json={"items": items},
                    headers=self._headers(),
                    timeout=self.timeout,
                )
                if resp.status_code in (200, 201, 202):
                    return len(items)
                logger.warning("Hindsight batch retain failed: %s", resp.status_code)
            except Exception:
                logger.exception("Hindsight batch retain error")
            return 0
        with self._lock:
            for it in items:
                self._local.append({
                    "text": it.get("content", ""),
                    "context": it.get("context", ""),
                    "metadata": it.get("metadata") or {},
                    "at": datetime.now(timezone.utc).isoformat(),
                })
        return len(items)

    # ------------------------------------------------------------ recall ----

    def recall(self, query: str, budget: str = "mid", max_tokens: int = 4096) -> list[dict]:
        """Semantic recall: [{text, context, fact_type, score, metadata}]."""
        if not query.strip():
            return []
        if self.available:
            try:
                resp = httpx.post(
                    self._url("/memories/recall"),
                    json={"query": query, "budget": budget, "max_tokens": max_tokens},
                    headers=self._headers(),
                    timeout=self.timeout,
                )
                if resp.status_code == 200:
                    return self._extract_results(resp.json())
                logger.warning("Hindsight recall failed: %s", resp.status_code)
            except Exception:
                logger.exception("Hindsight recall error")
            return []
        terms = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 3]
        with self._lock:
            snapshot = list(self._local)
        scored = []
        for item in snapshot:
            text = str(item["text"]).lower()
            hits = sum(1 for t in terms if t in text)
            if hits:
                scored.append((hits / max(1, len(terms)), item))
        scored.sort(key=lambda pair: -pair[0])
        return [
            {
                "text": it["text"],
                "context": it["context"],
                "fact_type": "",
                "score": sc,
                "metadata": it.get("metadata") or {},
            }
            for sc, it in scored[:20]
        ]

    # ------------------------------------------------------- bank admin ----

    def list_memories(self, limit: int = 200) -> list[dict]:
        """List raw memory units (UI / debugging)."""
        if self.available:
            try:
                resp = httpx.get(
                    self._url("/memories/list?limit=%d" % limit),
                    headers=self._headers(),
                    timeout=self.timeout,
                )
                if resp.status_code == 200:
                    return resp.json().get("items", [])
            except Exception:
                logger.exception("Hindsight list error")
            return []
        with self._lock:
            snapshot = list(self._local)
        return [
            {"text": it["text"], "context": it["context"], "metadata": it.get("metadata") or {}}
            for it in snapshot[-limit:]
        ]

    def count(self) -> int:
        return len(self.list_memories(limit=1000))

    def clear(self) -> bool:
        """Clear the memory bank (demo reset)."""
        if self.available:
            try:
                resp = httpx.delete(self._url("/memories"), headers=self._headers(), timeout=self.timeout)
                if resp.status_code in (200, 202, 204):
                    return True
                logger.warning("Hindsight clear failed: %s", resp.status_code)
            except Exception:
                logger.exception("Hindsight clear error")
            return False
        with self._lock:
            self._local.clear()
        return True


hindsight_service = HindsightService()
