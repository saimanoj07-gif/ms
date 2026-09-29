"""Content service — ingestion pipeline.

create -> compute metrics -> extract insights (LLM) -> persist -> REMEMBER.
"""

import logging

from sqlalchemy.orm import Session

from backend.models.entities import Content
from backend.schemas.api import ContentCreate, ExtractedInsights, compute_engagement_rate
from backend.services.analytics_service import analytics_service
from backend.services.llm_service import LLMService, LLMError, llm_service
from backend.services.memory_service import MemoryService, memory_service

logger = logging.getLogger(__name__)

_INSIGHT_SYSTEM = """You are ContentMind, a content strategy analyst.
Given one piece of published content and its performance metrics, extract 1-4
short, self-contained strategic insights that a marketing team should REMEMBER
long-term. Focus on what this result teaches: topic resonance, audience
interest, format effectiveness, platform effectiveness, tone, or strategy.
Only include insights that are genuinely useful for future planning. Be
specific (name the topic/platform/format), never generic. Each insight must be
one sentence written as a durable statement, e.g. "Practical AI automation
tutorials perform above the account average engagement"."""


class ContentService:
    def __init__(self, llm: LLMService | None = None, memory: MemoryService | None = None) -> None:
        self.llm = llm or llm_service
        self.memory = memory or memory_service

    # ------------------------------------------------------------- metrics ----

    @staticmethod
    def apply_metrics(content: Content) -> Content:
        content.engagement_rate = compute_engagement_rate(
            content.likes, content.comments, content.shares, content.impressions
        )
        return content

    # ---------------------------------------------------------- extraction ----

    def extract_insights(self, content: Content, avg_engagement: float) -> list[dict]:
        """LLM extraction with deterministic fallback (never blocks ingestion)."""
        if not self.llm.available:
            return self._fallback_insights(content, avg_engagement)
        user = (
            "Content record:\n"
            "Title: %s\nPlatform: %s\nType: %s\nTopic: %s\nAudience: %s\n"
            "Published: %s\nImpressions: %d\nLikes: %d\nComments: %d\nShares: %d\nClicks: %d\n"
            "Engagement rate: %.2f%% (account average: %.2f%%)\n\nBody (truncated):\n%s"
            % (
                content.title, content.platform, content.content_type, content.topic,
                content.audience, content.published_at or "unknown",
                content.impressions, content.likes, content.comments, content.shares,
                content.clicks, content.engagement_rate * 100, avg_engagement * 100,
                (content.body or "")[:1500],
            )
        )
        try:
            parsed = self.llm.chat_json(_INSIGHT_SYSTEM, user, ExtractedInsights)
            return [i.model_dump() for i in parsed.insights][:4]
        except LLMError as exc:
            logger.warning("Insight extraction failed, using fallback: %s", exc)
            return self._fallback_insights(content, avg_engagement)

    @staticmethod
    def _fallback_insights(content: Content, avg_engagement: float) -> list[dict]:
        """Rule-based insights used when the LLM is unavailable."""
        insights: list[dict] = []
        if content.impressions > 0 and content.engagement_rate > avg_engagement * 1.2:
            insights.append({
                "insight_type": "performance",
                "insight": "%s content about %s performs above the account average engagement"
                           % (content.content_type or "This", content.topic or "this subject"),
                "confidence": 0.6,
            })
        elif content.impressions > 0 and content.engagement_rate < avg_engagement * 0.6:
            insights.append({
                "insight_type": "performance",
                "insight": "%s content about %s performs below the account average engagement"
                           % (content.content_type or "This", content.topic or "this subject"),
                "confidence": 0.6,
            })
        insights.append({
            "insight_type": "topic",
            "insight": "The company has published %s content about %s on %s"
                       % (content.content_type or "content", content.topic or "general",
                          content.platform or "an unspecified platform"),
            "confidence": 0.9,
        })
        return insights

    # ------------------------------------------------------------ pipeline ----

    def create_content(self, db: Session, payload: ContentCreate) -> tuple[Content, list[dict], bool, str]:
        """Full ingestion pipeline. Returns (content, insight texts, memory_stored, backend)."""
        content = Content(
            title=payload.title,
            body=payload.body,
            platform=payload.platform.strip(),
            content_type=payload.content_type.strip(),
            topic=payload.topic.strip(),
            audience=payload.audience.strip(),
            published_at=payload.published_at,
            impressions=payload.impressions,
            likes=payload.likes,
            comments=payload.comments,
            shares=payload.shares,
            clicks=payload.clicks,
            status=payload.status,
        )
        self.apply_metrics(content)
        db.add(content)
        db.commit()
        db.refresh(content)

        avg = analytics_service.average_engagement_rate(db)
        raw = self.extract_insights(content, avg)
        retained = self.memory.remember_content(db, content, raw, avg)
        backend = self.memory.memory.mode
        insight_texts = [i["insight"] for i in raw]
        return content, insight_texts, retained > 0, backend


content_service = ContentService()
