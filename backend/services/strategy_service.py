"""Strategy service — RECALL -> REASON -> RECOMMEND.

Builds a strategy context from (1) recalled Hindsight memories, (2) structured
analytics, and (3) content gaps, then asks the LLM for a personalized plan.
Every recommendation carries a reason and the memories that drove it.
"""

import json
import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from backend.models.entities import Content, ContentPlan, ContentPlanItem, BrandProfile
from backend.schemas.api import ChatResponse, GeneratedPlan, PlanRequest
from backend.services.analytics_service import analytics_service
from backend.services.gap_service import gap_service
from backend.services.llm_service import LLMError, llm_service
from backend.services.memory_service import memory_service

logger = logging.getLogger(__name__)

_PLAN_SYSTEM = """You are ContentMind, a memory-driven content strategist.
You will receive: (1) recalled long-term memories about what has worked for
this company, (2) structured performance analytics, (3) content gaps, and (4)
recent topics to avoid repeating.
Produce a concrete content plan where every item is clearly justified BY the
memory or data provided - never invent patterns that are not in the context.
Each item's "reason" must cite the specific memory, statistic, or gap behind
the choice, and "memory_used" must quote the exact memory lines used.
Respect the brand voice. Avoid topics from "recent topics" unless given a new
angle. Vary formats and platforms. If the context says historical data is
limited, say so honestly in the strategy_summary and keep recommendations
generic best-practice."""

_CHAT_SYSTEM = """You are ContentMind, a content strategy assistant with long-term
memory (Hindsight). Answer using the recalled memories and analytics provided.
When you use a memory, weave in its substance. If memories are empty, say you
do not have historical knowledge yet and answer from general best practice.
Be concise (max ~180 words) and practical."""


class StrategyService:
    # ------------------------------------------------------------ context ----

    def build_context(self, db: Session, request_summary: str, campaign_topic: str = "") -> dict:
        """RECALL: memories + structured data -> a single strategy context."""
        memories = memory_service.get_relevant_memories(db, request_summary, campaign_topic)
        stats = analytics_service.summarize(db)
        gaps = gap_service.detect_gaps(db)
        recent = analytics_service.recent(db, limit=12)
        brand = db.query(BrandProfile).first()
        return {
            "memories": memories,
            "stats": stats,
            "gaps": gaps,
            "recent_topics": [r.topic for r in recent if r.topic],
            "recent_titles": [r.title for r in recent],
            "brand": brand,
        }

    @staticmethod
    def _context_text(ctx: dict) -> str:
        parts: list[str] = []
        if ctx["memories"]:
            parts.append("RECALLED MEMORIES (long-term knowledge):\n" + "\n".join(
                "- %s" % m["text"] for m in ctx["memories"]))
        else:
            parts.append("RECALLED MEMORIES: none yet - historical knowledge is limited.")
        s = ctx["stats"]
        if s["total_content"]:
            parts.append(
                "HISTORICAL PERFORMANCE: %d published items; avg engagement %.2f%%; "
                "top topic '%s'; top platform '%s'. By topic: %s. By platform: %s. By type: %s."
                % (
                    s["total_content"], s["avg_engagement_rate"] * 100,
                    s["top_topic"] or "n/a", s["top_platform"] or "n/a",
                    json.dumps([{ "name": b["name"], "posts": b["posts"], "avg_rate": round(b["avg_rate"] * 100, 2)}
                                for b in s["by_topic"][:6]]),
                    json.dumps([{ "name": b["name"], "posts": b["posts"], "avg_rate": round(b["avg_rate"] * 100, 2)}
                                for b in s["by_platform"][:6]]),
                    json.dumps([{ "name": b["name"], "posts": b["posts"], "avg_rate": round(b["avg_rate"] * 100, 2)}
                                for b in s["by_content_type"][:6]]),
                ))
        else:
            parts.append("HISTORICAL PERFORMANCE: no published content recorded yet.")
        if ctx["gaps"]:
            parts.append("CONTENT GAPS:\n" + "\n".join(
                "- %s: %s" % (g["topic"], g["reason"]) for g in ctx["gaps"]))
        if ctx["recent_topics"]:
            parts.append("RECENT TOPICS (avoid repeating): " + ", ".join(ctx["recent_topics"]))
        b = ctx["brand"]
        if b:
            parts.append("BRAND: %s. Voice: %s. Audience: %s." % (
                b.brand_name or "Unnamed brand", b.tone or "not specified",
                b.target_audience or "not specified"))
        return "\n\n".join(parts)

    # -------------------------------------------------------------- plan ----

    def generate_plan(self, db: Session, req: PlanRequest) -> dict:
        """Full planner: recall -> reason -> recommend -> persist -> remember."""
        start = date.today()
        end = start + timedelta(days=req.date_range_days - 1)
        request_summary = req.campaign_topic or "a %d-day content plan" % req.date_range_days

        ctx = self.build_context(db, request_summary, req.campaign_topic)
        memory_texts = [m["text"] for m in ctx["memories"]]

        if not req.use_memory:
            # Demo mode: deliberately ignore memory and history.
            ctx = {"memories": [], "stats": {"total_content": 0, "avg_engagement_rate": 0.0,
                                             "top_topic": None, "top_platform": None, "by_topic": [],
                                             "by_platform": [], "by_content_type": []},
                   "gaps": [], "recent_topics": [], "recent_titles": [], "brand": ctx["brand"]}
            memory_texts = []

        user = (
            "REQUEST: Create a %d-day content plan with %d posts%s on platforms: %s.\n\n%s"
            % (
                req.date_range_days, req.num_posts,
                " about '%s'" % req.campaign_topic if req.campaign_topic else "",
                ", ".join(req.platforms) or "best-performing platforms",
                self._context_text(ctx),
            )
        )

        plan: GeneratedPlan | None = None
        llm_used = False
        if llm_service.available:
            try:
                plan = llm_service.chat_json(_PLAN_SYSTEM, user, GeneratedPlan)
                llm_used = True
            except LLMError as exc:
                logger.warning("Plan generation via LLM failed, using fallback: %s", exc)
        if plan is None:
            plan = self._fallback_plan(req, ctx)

        record = ContentPlan(
            title=plan.title,
            date_range="%s to %s" % (start.isoformat(), end.isoformat()),
            strategy_summary=plan.strategy_summary,
            memory_count=len(memory_texts),
            memories_used=json.dumps(memory_texts[:20]),
        )
        db.add(record)
        db.flush()
        for i, item in enumerate(plan.items[: req.num_posts]):
            db.add(ContentPlanItem(
                plan_id=record.id,
                date=start + timedelta(days=i % max(1, req.date_range_days)),
                platform=item.platform, topic=item.topic, format=item.format,
                title=item.title, description=item.description, reason=item.reason,
                memory_used=json.dumps(item.memory_used),
                is_new=bool(item.memory_used),
            ))
        db.commit()
        db.refresh(record)
        memory_service.remember_plan(db, record, memory_texts)

        return {
            "plan": record,
            "items": record.items,
            "memory_count": len(memory_texts),
            "memories_used": memory_texts,
            "llm_used": llm_used,
            "hindsight_available": memory_service.memory.available,
        }

    @staticmethod
    def _fallback_plan(req: PlanRequest, ctx: dict) -> GeneratedPlan:
        """Heuristic plan when the LLM is unavailable - still memory/data driven."""
        stats = ctx["stats"]
        gaps = ctx["gaps"]
        memories = ctx["memories"]
        has_data = bool(stats.get("total_content"))
        top_topic = stats.get("top_topic") or "your core topic"
        top_platform = (req.platforms or [stats.get("top_platform") or "LinkedIn"])
        items = []
        for i in range(req.num_posts):
            if i < len(gaps):
                topic = gaps[i]["topic"]
                reason = gaps[i]["reason"] + (" Memory: '%s'." % memories[0]["text"] if memories else "")
                used = [m["text"] for m in memories[:2]]
                fmt = "How-to guide"
            elif has_data and i == len(gaps):
                topic = "%s mistakes to avoid" % top_topic
                reason = ("Double-down: '%s' is your strongest topic historically." % top_topic) \
                    + (" Memory: '%s'." % memories[0]["text"] if memories else "")
                used = [m["text"] for m in memories[:2]]
                fmt = "Educational post"
            elif has_data:
                topic = top_topic
                reason = ("Recurring high-performing topic (avg engagement leader across %d items)."
                          % stats.get("total_content", 0))
                used = []
                fmt = ["Educational post", "Case study", "Thread", "Poll"][i % 4]
            else:
                # No history and no memory: be honest that this is generic advice.
                topic = ["Industry trends", "Practical how-to", "Audience Q&A"][i % 3]
                reason = "Generic best practice - no historical knowledge or memories available yet."
                used = []
                fmt = ["Educational post", "Case study", "Thread"][i % 3]
            platform = top_platform[i % len(top_platform)] if top_platform else "LinkedIn"
            items.append({
                "date": None, "platform": platform, "topic": topic, "format": fmt,
                "title": "%s: %s" % (topic, ["A practical guide", "What the data shows",
                                             "Mistakes to avoid", "A deep dive"][i % 4]),
                "description": "", "reason": reason, "memory_used": used,
            })
        summary = (
            "Data-driven plan built from %d content items and %d recalled memories. "
            "Leads with under-covered gap topics, then reinforces the strongest topic ('%s')."
            % (stats.get("total_content", 0), len(memories), top_topic)
        ) if has_data else (
            "Generic best-practice plan - no historical content or memories available yet. "
            "Add your content history to unlock personalized recommendations."
        )
        return GeneratedPlan(title="%d-Day Content Plan" % req.date_range_days,
                             strategy_summary=summary, items=items)

    # -------------------------------------------------------------- chat ----

    def chat(self, db: Session, message: str) -> ChatResponse:
        memories = memory_service.get_relevant_memories(db, message, limit=12)
        stats = analytics_service.summarize(db)
        context_parts = []
        if memories:
            context_parts.append("RECALLED MEMORIES:\n" + "\n".join("- %s" % m["text"] for m in memories))
        else:
            context_parts.append("RECALLED MEMORIES: none yet.")
        if stats["total_content"]:
            context_parts.append(
                "QUICK STATS: %d items, avg engagement %.2f%%, top topic '%s', top platform '%s'."
                % (stats["total_content"], stats["avg_engagement_rate"] * 100,
                   stats["top_topic"] or "n/a", stats["top_platform"] or "n/a"))
        reply = ""
        llm_used = False
        if llm_service.available:
            try:
                reply = llm_service.chat_text(
                    _CHAT_SYSTEM,
                    "USER QUESTION: %s\n\n%s" % (message, "\n\n".join(context_parts)),
                    temperature=0.4,
                )
                llm_used = True
            except LLMError as exc:
                logger.warning("Chat LLM failed, using fallback: %s", exc)
        if not llm_used:
            reply = self._fallback_chat(message, memories, stats)
        return ChatResponse(
            reply=reply,
            memories_used=[{"text": m["text"], "category": (m.get("metadata") or {}).get("category", "")}
                           for m in memories[:6]],
            memory_count=len(memories),
            hindsight_available=memory_service.memory.available,
            llm_used=llm_used,
        )

    @staticmethod
    def _fallback_chat(message: str, memories: list[dict], stats: dict) -> str:
        m = message.lower()
        lines: list[str] = []
        if memories:
            lines.append("Based on %d recalled memories:" % len(memories))
            lines += ["- %s" % mem["text"] for mem in memories[:5]]
        else:
            lines.append("I don't have historical knowledge yet - add or seed content so I can learn.")
        if "gap" in m and stats.get("total_content"):
            lines.append("Ask the planner to target these gaps in your next plan.")
        if "top" in m and stats.get("top_topic"):
            lines.append("Historically, '%s' is your strongest topic (avg engagement %.2f%%)."
                         % (stats["top_topic"], stats["avg_engagement_rate"] * 100))
        return "\n".join(lines)

    # ---------------------------------------------------------- dashboard ----

    def dashboard(self, db: Session) -> dict:
        stats = analytics_service.summarize(db)
        gaps = gap_service.detect_gaps(db, limit=3)
        top = analytics_service.top_performers(db, limit=3)
        recent_insights = []
        from backend.models.entities import ContentInsight
        rows = db.query(ContentInsight).order_by(ContentInsight.created_at.desc()).limit(4).all()
        recent_insights = [r.insight for r in rows]
        # Memory count: prefer the memory backend, but fall back to persisted
        # insights so the UI stays truthful after a process restart.
        try:
            backend_count = memory_service.memory_count(db)
        except Exception:
            backend_count = 0
        insight_count = db.query(ContentInsight).count()
        memories_count = max(backend_count, insight_count)
        next_action = (
            "Create a post about '%s' - it is a potential gap and relates to your "
            "historically strong topics." % gaps[0]["topic"] if gaps else
            ("Double down on '%s', your strongest topic." % stats["top_topic"] if stats["top_topic"]
             else "Add historical content so ContentMind can start learning.")
        )
        learning = recent_insights[0] if recent_insights else (
            "No learning yet - ingest content to build memory.")
        return {
            "stats": stats,
            "gaps": gaps,
            "top_performers": [
                {"id": t.id, "title": t.title, "topic": t.topic, "platform": t.platform,
                 "engagement_rate": round(t.engagement_rate * 100, 2)}
                for t in top
            ],
            "recent_learning": recent_insights,
            "memories_learned": memories_count,
            "recommended_next_action": next_action,
            "hindsight_available": memory_service.memory.available,
            "memory_backend": memory_service.memory.mode,
        }


strategy_service = StrategyService()
