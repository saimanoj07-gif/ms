"""SQLAlchemy ORM models: structured facts stored in the relational database.

Hindsight stores long-term *semantic* knowledge; this database stores the
structured records (content, metrics, plans, insights) the strategy engine
computes over.
"""

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Content(Base):
    __tablename__ = "content"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    platform: Mapped[str] = mapped_column(String(80), default="")
    content_type: Mapped[str] = mapped_column(String(80), default="")
    topic: Mapped[str] = mapped_column(String(120), default="")
    audience: Mapped[str] = mapped_column(String(160), default="")
    published_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(40), default="published")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    insights: Mapped[list["ContentInsight"]] = relationship(
        back_populates="content", cascade="all, delete-orphan"
    )


class ContentInsight(Base):
    __tablename__ = "content_insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("content.id"), nullable=False)
    insight_type: Mapped[str] = mapped_column(String(40), default="performance")
    insight: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    source: Mapped[str] = mapped_column(String(40), default="historical performance")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    content: Mapped[Content] = relationship(back_populates="insights")


class ContentPlan(Base):
    __tablename__ = "content_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300), default="Content Plan")
    date_range: Mapped[str] = mapped_column(String(120), default="")
    strategy_summary: Mapped[str] = mapped_column(Text, default="")
    memory_count: Mapped[int] = mapped_column(Integer, default=0)
    memories_used: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    items: Mapped[list["ContentPlanItem"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="ContentPlanItem.date"
    )


class ContentPlanItem(Base):
    __tablename__ = "content_plan_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("content_plans.id"), nullable=False)
    date: Mapped[date | None] = mapped_column(Date, nullable=True)
    platform: Mapped[str] = mapped_column(String(80), default="")
    topic: Mapped[str] = mapped_column(String(120), default="")
    format: Mapped[str] = mapped_column(String(80), default="")
    title: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    memory_used: Mapped[str] = mapped_column(Text, default="")  # JSON list of memory strings
    is_new: Mapped[bool] = mapped_column(Boolean, default=False)  # True if memory-driven novel topic

    plan: Mapped[ContentPlan] = relationship(back_populates="items")


class BrandProfile(Base):
    __tablename__ = "brand_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_name: Mapped[str] = mapped_column(String(200), default="")
    target_audience: Mapped[str] = mapped_column(String(300), default="")
    tone: Mapped[str] = mapped_column(String(200), default="")
    preferred_formats: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    preferred_platforms: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    description: Mapped[str] = mapped_column(Text, default="")
