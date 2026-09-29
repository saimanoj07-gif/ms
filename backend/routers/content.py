"""Content routes - thin handlers over the content service."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models.entities import Content
from backend.schemas.api import ContentAnalysisOut, ContentCreate, ContentOut
from backend.services.analytics_service import analytics_service
from backend.services.content_service import content_service
from backend.services.memory_service import memory_service
from backend.services.hindsight_service import hindsight_service

router = APIRouter(prefix="/api/content", tags=["content"])


def _to_out(c: Content) -> ContentOut:
    return ContentOut(
        id=c.id, title=c.title, body=c.body, platform=c.platform,
        content_type=c.content_type, topic=c.topic, audience=c.audience,
        published_at=c.published_at, impressions=c.impressions, likes=c.likes,
        comments=c.comments, shares=c.shares, clicks=c.clicks,
        engagement_rate=round(c.engagement_rate * 100, 2), status=c.status,
        created_at=c.created_at,
    )


@router.post("", response_model=ContentAnalysisOut)
def create_content(payload: ContentCreate, db: Session = Depends(get_db)):
    """Ingest one content item: save -> analyze -> remember."""
    try:
        content, insights, stored, backend = content_service.create_content(db, payload)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Failed to ingest content: %s" % exc)
    return ContentAnalysisOut(
        content=_to_out(content),
        insights=insights,
        memory_stored=stored,
        memory_backend=backend,
    )


@router.get("", response_model=list[ContentOut])
def list_content(
    topic: str | None = None,
    platform: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(Content)
    if topic:
        q = q.filter(Content.topic.ilike("%" + topic + "%"))
    if platform:
        q = q.filter(Content.platform.ilike("%" + platform + "%"))
    rows = q.order_by(Content.published_at.desc().nullslast(), Content.id.desc()).offset(offset).limit(limit).all()
    return [_to_out(c) for c in rows]


@router.get("/{content_id}", response_model=ContentOut)
def get_content(content_id: int, db: Session = Depends(get_db)):
    c = db.get(Content, content_id)
    if not c:
        raise HTTPException(status_code=404, detail="Content not found")
    return _to_out(c)


@router.post("/analyze")
def analyze_content(payload: dict, db: Session = Depends(get_db)):
    """Re-run insight extraction + memory retention for an existing item."""
    content_id = payload.get("content_id")
    c = db.get(Content, int(content_id)) if content_id else None
    if not c:
        raise HTTPException(status_code=404, detail="Content not found")
    avg = analytics_service.average_engagement_rate(db)
    insights = content_service.extract_insights(c, avg)
    retained = memory_service.remember_content(db, c, insights, avg)
    return {"content_id": c.id, "insights": [i["insight"] for i in insights],
            "memory_stored": retained > 0, "memory_backend": hindsight_service.mode}
