"""Seed data - realistic synthetic content history with intentional patterns.

HIGH performers: practical AI automation tutorials, how-to implementation
guides, customer case studies (mostly LinkedIn).
LOW performers: generic company announcements, AI news roundups, promo posts.
Everything else sits near the account average with realistic noise.
"""

import random
from datetime import date, timedelta

from sqlalchemy.orm import Session

from backend.models.entities import BrandProfile
from backend.schemas.api import ContentCreate
from backend.services.content_service import ContentService
from backend.services.memory_service import MemoryService

_HIGH_TEMPLATES = [
    ("Practical AI Automation: {n} Workflows You Can Ship This Week", "AI automation", "LinkedIn", "How-to guide"),
    ("How We Automated {n} Reporting Tasks with AI", "AI automation", "LinkedIn", "Case study"),
    ("Step-by-Step: Building Your First AI Workflow", "AI automation", "Newsletter", "How-to guide"),
    ("Customer Story: {name} Cut Response Time 40% with AI", "Customer stories", "LinkedIn", "Case study"),
    ("Customer Story: {name} Automated Onboarding with AI", "Customer stories", "Blog", "Case study"),
    ("AI Implementation Playbook: From Pilot to Production", "AI implementation", "Blog", "How-to guide"),
    ("The 5-Step Framework for Practical AI Adoption", "AI implementation", "LinkedIn", "Educational post"),
    ("Tutorial: Automate Lead Scoring with AI in an Afternoon", "AI automation", "Newsletter", "How-to guide"),
    ("From Zero to Automated: AI Workflows for Small Teams", "AI automation", "LinkedIn", "How-to guide"),
    ("What 12 Months of AI Automation Taught Us", "AI automation", "Newsletter", "Thought leadership"),
]

_LOW_TEMPLATES = [
    ("We Are Excited to Announce {n}!", "Company news", "LinkedIn", "Product announcement"),
    ("Company Update: Another Milestone Reached", "Company news", "LinkedIn", "Product announcement"),
    ("AI Weekly Roundup #{n}", "AI news", "X / Twitter", "News commentary"),
    ("This Week in AI: Headlines You Missed", "AI news", "X / Twitter", "News commentary"),
    ("Limited Offer: {n}% Off This Week Only", "Promotions", "LinkedIn", "Product announcement"),
    ("Our CEO Featured in {name} Interview", "Company news", "X / Twitter", "Product announcement"),
    ("Quick Update on Our Latest Release", "Company news", "LinkedIn", "Product announcement"),
]

_MID_TEMPLATES = [
    ("Chatbots in Customer Support: Where They Actually Help", "Chatbots", "Blog", "Educational post"),
    ("Chatbot vs Human Support: A Balanced Look", "Chatbots", "LinkedIn", "Thought leadership"),
    ("How {name} Uses Chatbots for First-Line Support", "Chatbots", "Blog", "Case study"),
    ("5 Questions to Ask Before Buying AI Tooling", "AI tools", "Newsletter", "Educational post"),
    ("Poll: What Should We Cover Next Month?", "Community", "LinkedIn", "Poll"),
    ("Trends in AI-Assisted Support", "AI trends", "LinkedIn", "Thought leadership"),
    ("Measuring Content ROI: A Simple Framework", "Content strategy", "Blog", "How-to guide"),
    ("Why Most AI Pilots Stall (and How to Avoid It)", "AI implementation", "LinkedIn", "Thought leadership"),
    ("A Practical Intro to Machine Learning for Marketers", "Machine learning", "Newsletter", "Educational post"),
    ("Customer Q&A: {name} on Scaling Content Ops", "Customer stories", "Newsletter", "Case study"),
]

_NAMES = ["Acme Corp", "Globex", "Initech", "Umbrella", "Stark Industries", "Wayne Enterprises",
          "Wonka Industries", "Gekko & Co", "Tyrell Corp", "Soylent"]


class SeedService:
    def __init__(self) -> None:
        self.content_service = ContentService()
        self.memory_service = MemoryService()

    def reset(self, db: Session) -> None:
        """Drop all rows (content, insights, plans, brand) - NOT Hindsight."""
        from backend.core.database import Base, engine
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
        engine.dispose()

    def seed_history(self, db: Session, count: int = 64, learn: bool = True) -> dict:
        """Generate `count` content items spread over the past 5 months."""
        rng = random.Random(42)  # deterministic seed data
        created = 0
        memories_retained = 0
        end = date.today()
        for i in range(count):
            # Pattern: ~30% high, ~25% low, ~45% mid - with noise.
            roll = rng.random()
            pool = _HIGH_TEMPLATES if roll < 0.30 else _LOW_TEMPLATES if roll < 0.55 else _MID_TEMPLATES
            title, topic, platform, ctype = pool[i % len(pool)]
            title = title.format(n=rng.randint(3, 12), name=rng.choice(_NAMES))

            impressions = rng.randint(4000, 30000)
            if pool is _HIGH_TEMPLATES:
                er = rng.uniform(0.07, 0.13)      # 7-13% engagement: strong
                clicks = int(impressions * rng.uniform(0.02, 0.045))
            elif pool is _LOW_TEMPLATES:
                er = rng.uniform(0.005, 0.02)     # 0.5-2%: weak
                clicks = int(impressions * rng.uniform(0.002, 0.008))
            else:
                er = rng.uniform(0.025, 0.055)    # near average
                clicks = int(impressions * rng.uniform(0.008, 0.02))

            likes = int(impressions * er * rng.uniform(0.65, 0.8))
            comments = int(impressions * er * rng.uniform(0.1, 0.2))
            shares = int(impressions * er * rng.uniform(0.1, 0.25))

            published = end - timedelta(days=rng.randint(1, 150))
            payload = ContentCreate(
                title=title,
                body="Synthetic seeded content body for demo purposes.",
                platform=platform,
                content_type=ctype,
                topic=topic,
                audience=rng.choice(["Marketing managers", "Engineering leaders",
                                     "Founders / executives", "Content strategists"]),
                published_at=published,
                impressions=impressions,
                likes=likes, comments=comments, shares=shares, clicks=clicks,
            )
            _, _, stored, _ = self.content_service.create_content(db, payload)
            created += 1
            if learn and stored:
                memories_retained += 1
        self.memory_service.remember_brand(db)
        return {"content_created": created, "memories_retained": memories_retained}

    def seed_brand(self, db: Session) -> None:
        db.add(BrandProfile(
            brand_name="Acme AI",
            target_audience="Marketing managers and content strategists at mid-size B2B "
                            "software companies evaluating practical AI adoption",
            tone="Educational, concise, practical; implementation-first, no fluff",
            preferred_formats='["How-to guides", "Case studies", "Educational posts"]',
            preferred_platforms='["LinkedIn", "Newsletter", "Blog"]',
            description="Acme AI builds AI automation tooling for marketing and support teams.",
        ))
        db.commit()


seed_service = SeedService()
