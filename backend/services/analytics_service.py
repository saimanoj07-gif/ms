"""Analytics service — structured performance facts that ground the strategy engine."""

from datetime import date
from statistics import median
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.entities import Content
from backend.schemas.api import compute_engagement_rate


class AnalyticsService:
    def summarize(self, db: Session) -> dict:
        rows = db.query(Content).filter(Content.status == "published").all()
        total = len(rows)
        if not rows:
            return {
                "total_content": 0, "total_engagement": 0, "avg_engagement_rate": 0.0,
                "median_engagement_rate": 0.0, "top_topic": None, "top_platform": None,
                "by_platform": [], "by_topic": [], "by_content_type": [], "over_time": [],
                "insights": [],
            }

        rates = [r.engagement_rate for r in rows]
        total_engagement = sum(r.likes + r.comments + r.shares for r in rows)
        by_platform = self._breakdown(rows, key=lambda r: r.platform or "unknown")
        by_topic = self._breakdown(rows, key=lambda r: r.topic or "general")
        by_type = self._breakdown(rows, key=lambda r: r.content_type or "unknown")

        over_time: dict[str, dict] = {}
        for r in rows:
            if r.published_at:
                k = r.published_at.isoformat()[:7]  # month bucket
                b = over_time.setdefault(k, {"period": k, "posts": 0, "engagement_rate": 0.0})
                b["posts"] += 1
                b["engagement_rate"] += r.engagement_rate
        time_list = [
            {"period": v["period"], "posts": v["posts"],
             "engagement_rate": round(v["engagement_rate"] / v["posts"], 4)}
            for v in sorted(over_time.values(), key=lambda x: x["period"])
        ]

        return {
            "total_content": total,
            "total_engagement": total_engagement,
            "avg_engagement_rate": round(sum(rates) / total, 6),
            "median_engagement_rate": round(float(median(rates)), 6),
            "top_topic": by_topic[0]["name"] if by_topic else None,
            "top_platform": by_platform[0]["name"] if by_platform else None,
            "by_platform": by_platform[:8],
            "by_topic": by_topic[:8],
            "by_content_type": by_type[:8],
            "over_time": time_list,
        }

    def _breakdown(self, rows: list[Content], key) -> list[dict]:
        groups: dict[str, dict] = {}
        for r in rows:
            k = key(r)
            g = groups.setdefault(k, {"name": k, "posts": 0, "impressions": 0, "engagement": 0})
            g["posts"] += 1
            g["impressions"] += r.impressions
            g["engagement"] += r.likes + r.comments + r.shares
        for g in groups.values():
            g["avg_rate"] = round(g["engagement"] / g["impressions"], 6) if g["impressions"] else 0.0
        return sorted(groups.values(), key=lambda g: -g["avg_rate"])

    def top_performers(self, db: Session, limit: int = 5) -> list[Content]:
        return (
            db.query(Content)
            .filter(Content.status == "published", Content.impressions > 0)
            .order_by(Content.engagement_rate.desc())
            .limit(limit)
        ).all()

    def recent(self, db: Session, limit: int = 8) -> list[Content]:
        return (
            db.query(Content)
            .order_by(Content.published_at.desc().nullslast(), Content.created_at.desc())
            .limit(limit)
        ).all()

    def average_engagement_rate(self, db: Session) -> float:
        rates = [r.engagement_rate for r in db.query(Content).all()]
        return round(sum(rates) / len(rates), 6) if rates else 0.0


analytics_service = AnalyticsService()
