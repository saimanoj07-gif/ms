"""Pydantic schemas: API request/response contracts and LLM output validation."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------- content ----

PLATFORMS = ["LinkedIn", "X / Twitter", "Blog", "Newsletter", "YouTube", "Instagram"]
CONTENT_TYPES = [
    "Educational post", "Case study", "Product announcement", "News commentary",
    "How-to guide", "Thought leadership", "Video", "Poll", "Thread", "Webinar recap",
]
AUDIENCES = [
    "Marketing managers", "Engineering leaders", "Founders / executives",
    "Content strategists", "Sales teams", "General / mixed",
]

InsightType = Literal["performance", "topic", "audience", "format", "tone", "strategy"]

# Alias: a field literally named `date` cannot reference the class `date` in its
# own annotation (CPython binds the default before evaluating the annotation).
OptionalDate = date | None


def compute_engagement_rate(likes: int, comments: int, shares: int, impressions: int) -> float:
    """(likes + comments + shares) / impressions, guarded against zero."""
    if impressions <= 0:
        return 0.0
    return round((likes + comments + shares) / impressions, 6)


class ContentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    body: str = ""
    platform: str = ""
    content_type: str = ""
    topic: str = ""
    audience: str = ""
    published_at: date | None = None
    impressions: int = Field(default=0, ge=0)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    clicks: int = Field(default=0, ge=0)
    status: str = "published"

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title cannot be blank")
        return v.strip()


class ContentOut(BaseModel):
    id: int
    title: str
    body: str
    platform: str
    content_type: str
    topic: str
    audience: str
    published_at: date | None
    impressions: int
    likes: int
    comments: int
    shares: int
    clicks: int
    engagement_rate: float
    status: str
    created_at: datetime


class ContentAnalysisOut(BaseModel):
    """Response for POST /api/content: record + extracted insights + memory status."""

    content: ContentOut
    insights: list[str]
    memory_stored: bool
    memory_backend: str


# ---------------------------------------------------------------- insights ----

class ExtractedInsight(BaseModel):
    """A single strategic insight the LLM extracts from a content item."""

    insight_type: InsightType
    insight: str = Field(min_length=1, description="One-sentence, self-contained takeaway")
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class ExtractedInsights(BaseModel):
    """LLM output schema for content ingestion analysis."""

    insights: list[ExtractedInsight]


# ----------------------------------------------------------------- plans ----

class PlanItemOut(BaseModel):
    date: OptionalDate = None
    platform: str
    topic: str
    format: str
    title: str
    description: str = ""
    reason: str
    memory_used: list[str] = Field(default_factory=list)


class GeneratedPlan(BaseModel):
    """LLM output schema for the content planner."""

    title: str
    strategy_summary: str
    items: list[PlanItemOut]


class PlanRequest(BaseModel):
    date_range_days: int = Field(default=7, ge=1, le=30)
    platforms: list[str] = Field(default_factory=list)
    num_posts: int = Field(default=5, ge=1, le=14)
    campaign_topic: str = ""
    use_memory: bool = True


class PlanOut(BaseModel):
    id: int
    title: str
    date_range: str
    strategy_summary: str
    memory_count: int
    memories_used: list[str]
    created_at: datetime
    items: list[PlanItemOut]


# -------------------------------------------------------------- analytics ----

class AnalyticsOut(BaseModel):
    total_content: int
    total_engagement: int
    avg_engagement_rate: float
    median_engagement_rate: float
    top_topic: str | None
    top_platform: str | None
    by_platform: list[dict]
    by_topic: list[dict]
    by_content_type: list[dict]
    over_time: list[dict]
    insights: list[str]


class GapOut(BaseModel):
    topic: str
    reason: str
    priority: str


# --------------------------------------------------------------- learning ----

class MemoryOut(BaseModel):
    """One entry in the 'What I've Learned' view."""

    category: str  # Audience / Topics / Formats / Platforms / Brand Voice / Gaps / Strategy
    text: str
    source: str  # historical performance | user preference | content history | Hindsight memory
    confidence: float = 0.5


class LearnedOut(BaseModel):
    categories: dict[str, list[MemoryOut]]
    total: int
    hindsight_available: bool


class LearningEvent(BaseModel):
    summary: str
    detail: str = ""
    at: datetime | None = None


# ------------------------------------------------------------------ chat ----

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ChatCitation(BaseModel):
    text: str
    category: str = ""


class ChatResponse(BaseModel):
    reply: str
    memories_used: list[ChatCitation] = Field(default_factory=list)
    memory_count: int = 0
    hindsight_available: bool = True
    llm_used: bool = False


# ------------------------------------------------------------------ demo ----

class DemoStateOut(BaseModel):
    content_count: int
    memory_count: int
    plans_count: int
    hindsight_available: bool


class ChatStateMessage(BaseModel):
    role: str
    content: str
    memory_count: int = 0
