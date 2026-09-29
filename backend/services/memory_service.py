"""Memory service — the REMEMBER / RECALL heart of ContentMind.

Orchestrates what gets stored in Hindsight (long-term semantic knowledge) and
how memories are retrieved and categorized. Route handlers never touch the
Hindsight API directly; they call this service.
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

from backend.models.entities import BrandProfile, Content, ContentInsight
from backend.schemas.api import MemoryOut
from backend.services.hindsight_service import HindsightService, hindsight_service
from backend.services.llm_service import LLMService, llm_service

logger = logging.getLogger(__name__)

CATEGORIES = ["Audience", "Topics", "Formats", "Platforms", "Brand Voice", "Content Gaps", "Strategy"]

_GAP_WORDS = ["gap", "undercovered", "under-covered", "underrepresented", "not been covered",
              "little coverage", "rarely covered", "missing"]


def _classify_category(text: str, declared: str = "") -> str:
    t = text.lower()
    if any(w in t for w in _GAP_WORDS):
        return "Content Gaps"
    if declared == "audience" or "audience" in t or "readers" in t or "followers" in t:
        return "Audience"
    if declared == "tone" or "brand voice" in t or "tone" in t:
        return "Brand Voice"
    if declared == "format" or "format" in t or "carousel" in t or "video" in t or "thread" in t:
        return "Formats"
    if declared == "topic" or "topic" in t:
        return "Topics"
    if "platform" in t or "linkedin" in t or "newsletter" in t or "twitter" in t or " x " in t:
        return "Platforms"
    return "Strategy"


class MemoryService:
    def __init__(self, memory: HindsightService | None = None, llm: LLMService | None = None) -> None:
        self.memory = memory or hindsight_service
        self.llm = llm or llm_service

    # ------------------------------------------------------------ REMEMBER ----

    def remember_content(
        self,
        db: Session,
        content: Content,
        insights: list[dict],
        avg_engagement: float,
    ) -> int:
        """Persist insights to the DB and retain knowledge in Hindsight.

        `insights` is a list of {insight_type, insight, confidence} dicts.
        Returns the number of memory items accepted by the memory backend.
        A memory-backend failure never raises: ingestion must survive it.
        """
        try:
            for ins in insights:
                db.add(ContentInsight(
                    content_id=content.id,
                    insight_type=ins.get("insight_type", "strategy"),
                    insight=ins["insight"],
                    confidence=float(ins.get("confidence", 0.6)),
                    source="historical performance" if ins.get("insight_type") == "performance" else "content history",
                ))
            db.commit()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to persist insights; continuing without memory")
            db.rollback()
            return 0

        rate_pct = round(content.engagement_rate * 100, 2)
        avg_pct = round(avg_engagement * 100, 2)
        fact = (
            "The company published a {ctype} on {platform} titled '{title}' about {topic} "
            "targeting {audience}. It received {imp} impressions, {likes} likes, {comments} comments, "
            "{shares} shares ({rate}% engagement vs {avg}% account average)."
        ).format(
            ctype=content.content_type or "post",
            platform=content.platform or "unknown platform",
            title=content.title,
            topic=content.topic or "general",
            audience=content.audience or "its audience",
            imp=content.impressions,
            likes=content.likes,
            comments=content.comments,
            shares=content.shares,
            rate=rate_pct,
            avg=avg_pct,
        )
        items: list[dict[str, Any]] = [{
            "content": fact,
            "context": "content performance record",
            "metadata": {
                "content_id": str(content.id),
                "topic": content.topic or "",
                "platform": content.platform or "",
                "category": "Performance",
                "source": "historical performance",
            },
        }]
        for ins in insights:
            items.append({
                "content": ins["insight"],
                "context": "strategic insight",
                "metadata": {
                    "content_id": str(content.id),
                    "category": _classify_category(ins["insight"], ins.get("insight_type", "")),
                    "source": "historical performance",
                },
            })
        try:
            return self.memory.retain_batch(items)
        except Exception:  # noqa: BLE001
            logger.exception("Memory backend retain failed; continuing without memory")
            return 0

    def remember_brand(self, db: Session) -> int:
        """Retain brand voice/audience knowledge so every recall can use it."""
        brand = db.query(BrandProfile).first()
        if not brand:
            return 0
        items = []
        if brand.tone:
            items.append({
                "content": "Brand voice: %s" % brand.tone,
                "context": "brand profile",
                "metadata": {"category": "Brand Voice", "source": "user preference"},
            })
        if brand.target_audience:
            items.append({
                "content": "Target audience: %s" % brand.target_audience,
                "context": "brand profile",
                "metadata": {"category": "Audience", "source": "user preference"},
            })
        if brand.description:
            items.append({
                "content": "About the brand: %s" % brand.description,
                "context": "brand profile",
                "metadata": {"category": "Brand Voice", "source": "user preference"},
            })
        try:
            return self.memory.retain_batch(items)
        except Exception:  # noqa: BLE001
            logger.exception("Memory backend retain failed; continuing without memory")
            return 0 if items else 0

    def remember_plan(self, db, plan, memory_texts: list[str]) -> int:
        """Retain that a plan was generated (planning history)."""
        topics = ", ".join(i.topic for i in plan.items)
        text = (
            "A %s content plan was generated covering: %s. It was based on %d recalled memories."
            % (plan.date_range, topics, len(memory_texts))
        )
        try:
            return 1 if self.memory.retain(
                text,
                context="planning history",
                metadata={"plan_id": str(plan.id), "category": "Strategy", "source": "content history"},
            ) else 0
        except Exception:  # noqa: BLE001
            logger.exception("Memory backend retain failed; continuing without memory")
            return 0

    # -------------------------------------------------------------- RECALL ----

    def recall(self, query: str, budget: str = "mid") -> list[dict]:
        """Raw semantic recall from Hindsight."""
        return self.memory.recall(query, budget=budget)

    def get_relevant_memories(self, db: Session, request_summary: str,
                              campaign_topic: str = "", limit: int = 18) -> list[dict]:
        """Multi-query recall: request + audience + brand + gaps, deduplicated."""
        queries = [request_summary]
        if campaign_topic:
            queries.append("insights about %s" % campaign_topic)
        queries += [
            "topics and content that perform well with the audience",
            "brand voice and tone",
            "content gaps and topics not covered enough",
        ]
        merged: dict[str, dict] = {}
        for q in queries:
            try:
                hits = self.recall(q, budget="low")
            except Exception:  # noqa: BLE001
                logger.exception("Memory recall failed; continuing without it")
                hits = []
            for m in hits:
                text = m.get("text") or ""
                if text and text.lower() not in merged:
                    merged[text.lower()] = m
        ranked = sorted(merged.values(), key=lambda m: -float(m.get("score") or 0.0))
        return ranked[:limit]

    # --------------------------------------------------------- VISIBILITY ----

    def get_learned(self, db: Session) -> dict:
        """Everything ContentMind has learned, grouped for the UI."""
        rows = db.query(ContentInsight).order_by(ContentInsight.created_at.desc()).limit(300).all()
        try:
            memories = self.memory.list_memories(limit=300)
        except Exception:  # noqa: BLE001
            logger.exception("Memory backend list failed; showing DB insights only")
            memories = []
        out: dict[str, list[MemoryOut]] = {c: [] for c in CATEGORIES}
        seen: set[str] = set()

        def add(text: str, category: str, source: str, confidence: float = 0.6) -> None:
            key = text.lower().strip()
            if not text or key in seen:
                return
            seen.add(key)
            out.setdefault(category, []).append(
                MemoryOut(category=category, text=text.strip(), source=source, confidence=confidence)
            )

        for ins in rows:
            add(ins.insight, _classify_category(ins.insight, ins.insight_type),
                ins.source or "content history", ins.confidence)
        for m in memories:
            meta = m.get("metadata") or {}
            add(str(m.get("text") or ""), str(meta.get("category") or ""),
                str(meta.get("source") or "Hindsight memory"))
        # Surface computed content gaps so the UI's Gaps category is always current.
        from backend.services.gap_service import gap_service
        for g in gap_service.detect_gaps(db, limit=5):
            add("%s - %s" % (g["topic"], g["reason"]), "Content Gaps", "content history", 0.5)
        return out

    def memory_count(self, db: Session) -> int:
        try:
            return self.memory.count()
        except Exception:  # noqa: BLE001
            return 0


memory_service = MemoryService()
