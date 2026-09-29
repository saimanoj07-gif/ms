"""Content gap detection — potential gaps, expressed with appropriate uncertainty."""

from collections import Counter
from datetime import date, timedelta

from sqlalchemy.orm import Session

from backend.models.entities import Content, ContentInsight

_ADJACENT = {
    "ai automation": ["ai roi", "automation costs", "workflow automation"],
    "chatbots": ["conversational ai", "chatbot roi"],
    "customer support": ["support automation", "customer success stories"],
    "ai news": ["ai commentary", "practical ai guides"],
    "machine learning": ["ml deployment", "ml costs"],
    "case studies": ["implementation details", " measurable results"],
}

_GAPS = [
    ("AI ROI", "AI ROI has received little coverage compared to how often AI topics perform well.", "high"),
    ("AI implementation costs", "Implementation costs are rarely covered even though the audience engages with practical content.", "high"),
    ("AI security", "Security around AI adoption has not been covered at all.", "medium"),
    ("Adoption mistakes", "Lessons-learned content about failed adoption is missing from recent history.", "medium"),
    ("Team enablement", "How teams adopt new workflows is underrepresented.", "low"),
]


_ACRONYMS = {"ai", "roi", "ml", "kpi", "seo", "crm"}


def _display_topic(slug: str) -> str:
    words = []
    for w in slug.split():
        words.append(w.upper() if w in _ACRONYMS else w.capitalize())
    return " ".join(words)


class GapService:
    def detect_gaps(self, db: Session, limit: int = 6) -> list[dict]:
        """Blend data-driven coverage stats with known strategic blind spots."""
        rows = db.query(Content).filter(Content.status == "published").all()
        if not rows:
            return []
        cutoff = date.today() - timedelta(days=60)
        topics = [(r.topic.strip().lower(), r.engagement_rate) for r in rows if r.topic.strip()]
        if not topics:
            return []

        counts = Counter(t for t, _ in topics)
        rates: dict[str, list[float]] = {}
        for t, er in topics:
            rates.setdefault(t, []).append(er)
        avg_rate = sum(er for _, er in topics) / len(topics)
        recent = {r.topic.strip().lower() for r in rows if r.published_at and r.published_at >= cutoff}

        gaps: list[dict] = []

        # 1) Topics adjacent to strong performers but never/rarely covered.
        covered = set(counts)
        for topic in rates:
            er_list = rates[topic]
            avg_topic = sum(er_list) / len(er_list)
            if avg_topic < avg_rate * 1.1:
                continue
            for neighbor in _ADJACENT.get(topic, []):
                neighbor = neighbor.strip()
                if neighbor and neighbor not in covered:
                    gaps.append({
                        "topic": _display_topic(neighbor),
                        "reason": "Potential content gap: closely related to '%s', which performs "
                                  "above average, but it has not been covered yet." % topic,
                        "priority": "high",
                    })

        # 2) Topics covered a lot but performing poorly -> audience is saturated?
        for topic, count in counts.items():
            if count >= 4:
                tavg = sum(rates[topic]) / len(rates[topic])
                if tavg < avg_rate * 0.8:
                    gaps.append({
                        "topic": _display_topic(topic),
                        "reason": "Potential gap in a different sense: '%s' has been covered %d times "
                                  "but performs below average - the audience may be fatigued; a fresh "
                                  "angle is missing." % (topic, count),
                        "priority": "medium",
                    })

        # 3) Known strategic blind spots (seeded priors for a small dataset).
        for topic, reason, priority in _GAPS:
            slug = topic.lower()
            if not any(slug in t for t in covered):
                gaps.append({
                    "topic": topic,
                    "reason": "Potential content gap: %s" % reason,
                    "priority": priority,
                })

        # De-duplicate by topic, keep highest priority.
        priority_order = {"high": 0, "medium": 1, "low": 2}
        best: dict[str, dict] = {}
        for g in gaps:
            key = g["topic"].lower()
            if key not in best or priority_order[g["priority"]] < priority_order[best[key]["priority"]]:
                best[key] = g
        ranked = sorted(best.values(), key=lambda g: priority_order[g["priority"]])
        return ranked[:limit]


gap_service = GapService()
