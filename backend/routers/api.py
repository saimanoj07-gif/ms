"""Analytics + gaps + plans + memory + chat + demo routes (thin handlers)."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models.entities import ContentPlan
from backend.schemas.api import (
    AnalyticsOut,
    ChatRequest,
    ChatResponse,
    GapOut,
    LearnedOut,
    PlanOut,
    PlanRequest,
)
from backend.services.analytics_service import analytics_service
from backend.services.gap_service import gap_service
from backend.services.hindsight_service import hindsight_service
from backend.services.memory_service import memory_service
from backend.services.seed_service import seed_service
from backend.services.strategy_service import strategy_service

router = APIRouter(prefix="/api")


def _plan_out(plan: ContentPlan) -> PlanOut:
    items = []
    for it in plan.items:
        try:
            used = json.loads(it.memory_used or "[]")
        except ValueError:
            used = []
        items.append({
            "date": it.date, "platform": it.platform, "topic": it.topic,
            "format": it.format, "title": it.title, "description": it.description,
            "reason": it.reason, "memory_used": used,
        })
    try:
        used_all = json.loads(plan.memories_used or "[]")
    except ValueError:
        used_all = []
    return PlanOut(
        id=plan.id, title=plan.title, date_range=plan.date_range,
        strategy_summary=plan.strategy_summary, memory_count=plan.memory_count,
        memories_used=used_all, created_at=plan.created_at, items=items,
    )


# --------------------------------------------------------------- analytics ----

@router.get("/analytics", response_model=AnalyticsOut)
def get_analytics(db: Session = Depends(get_db)):
    return analytics_service.summarize(db) | {"insights": []}


@router.get("/gaps", response_model=list[GapOut])
def get_gaps(db: Session = Depends(get_db)):
    return gap_service.detect_gaps(db)


# ------------------------------------------------------------------ plans ----

@router.post("/plans/generate", response_model=PlanOut)
def generate_plan(req: PlanRequest, db: Session = Depends(get_db)):
    try:
        result = strategy_service.generate_plan(db, req)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Plan generation failed: %s" % exc)
    return _plan_out(result["plan"])


@router.get("/plans", response_model=list[PlanOut])
def list_plans(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)):
    plans = db.query(ContentPlan).order_by(ContentPlan.created_at.desc()).limit(limit).all()
    return [_plan_out(p) for p in plans]


# ----------------------------------------------------------------- memory ----

@router.get("/memory", response_model=LearnedOut)
def get_memory(db: Session = Depends(get_db)):
    categories = memory_service.get_learned(db)
    total = sum(len(v) for v in categories.values())
    return LearnedOut(categories=categories, total=total,
                      hindsight_available=hindsight_service.available)


@router.post("/memory/learn")
def memory_learn(payload: dict, db: Session = Depends(get_db)):
    """Manually retain a strategic statement (user preference) into memory."""
    text = str(payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="'text' is required")
    ok = hindsight_service.retain(
        text, context="user preference",
        metadata={"category": "Strategy", "source": "user preference"},
    )
    return {"memory_stored": ok or hindsight_service.mode == "local", "backend": hindsight_service.mode}


@router.get("/memory/raw")
def memory_raw(limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)):
    items = hindsight_service.list_memories(limit=limit)
    return {"backend": hindsight_service.mode, "available": hindsight_service.available,
            "count": len(items), "items": items}


# ------------------------------------------------------------------- chat ----

@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    try:
        return strategy_service.chat(db, req.message)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Chat failed: %s" % exc)


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    return strategy_service.dashboard(db)


# ------------------------------------------------------------------- demo ----

@router.post("/demo/reset")
def demo_reset(db: Session = Depends(get_db)):
    seed_service.reset(db)
    hindsight_service.clear()
    return {"ok": True, "message": "Database and memory cleared."}


@router.post("/demo/seed")
def demo_seed(payload: dict | None = None, db: Session = Depends(get_db)):
    n = int((payload or {}).get("count") or 64)
    seed_service.seed_brand(db)
    stats = seed_service.seed_history(db, count=n, learn=True)
    return {"ok": True, "message": "Seeded %d content items." % stats["content_created"], **stats,
            "hindsight_available": hindsight_service.available,
            "memory_backend": hindsight_service.mode}
