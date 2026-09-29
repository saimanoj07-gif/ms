"""ContentMind backend tests.

Covers: content creation, metric calculation, analysis, memory storage/recall,
gap detection, plan generation, empty database, Hindsight failure, invalid LLM
output, and API validation - plus the full workflow:
add content -> analyze -> remember -> recall -> generate plan.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text


@pytest.fixture(scope="module")
def client():
    """Test client over an isolated temp DB with no Hindsight and no LLM."""
    import os, tempfile
    import backend.core.config as cfg
    from backend.core.database import Base, engine, SessionLocal

    tmpdir = tempfile.mkdtemp()
    os.environ["DATABASE_URL"] = "sqlite:///" + tmpdir.replace("\\", "/") + "/test.db"
    cfg.get_settings.cache_clear()

    from backend.core.database import create_engine  # not exported; rebuild below

    # Rebuild engine/SessionLocal against the temp DB by patching settings.
    import backend.core.database as dbmod
    url = os.environ["DATABASE_URL"]
    from sqlalchemy import create_engine as _ce
    from sqlalchemy.orm import sessionmaker as _sm
    test_engine = _ce(url, connect_args={"check_same_thread": False}, future=True)
    dbmod.engine = test_engine
    dbmod.SessionLocal = _sm(bind=test_engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=test_engine)

    # Ensure no external services interfere.
    import backend.services.hindsight_service as hs
    hs.hindsight_service.base_url = ""
    hs.hindsight_service._available = False

    from backend.app.main import app
    with TestClient(app) as c:
        # Point the app's DB dependency at the test engine.
        from backend.core import database as core_db
        app.dependency_overrides[core_db.get_db] = _override(test_engine)
        yield c
    app.dependency_overrides.clear()


def _override(engine):
    from sqlalchemy.orm import Session

    def _get_db():
        s = Session(engine, autoflush=False, autocommit=False, future=True)
        try:
            yield s
        finally:
            s.close()
    return _get_db


# ------------------------------------------------------------------ content ----

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_metric_calculation(client):
    from backend.schemas.api import compute_engagement_rate
    assert compute_engagement_rate(1200, 180, 220, 20000) == pytest.approx(0.08)
    assert compute_engagement_rate(100, 0, 0, 0) == 0.0


def test_create_content_and_insights(client):
    payload = {
        "title": "5 AI Automation Mistakes",
        "platform": "LinkedIn", "content_type": "Educational post", "topic": "AI automation",
        "audience": "Marketing managers", "published_at": "2026-09-01",
        "impressions": 20000, "likes": 1200, "comments": 150, "shares": 180, "clicks": 600,
    }
    r = client.post("/api/content", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["content"]["title"] == "5 AI Automation Mistakes"
    assert body["memory_stored"] is True          # local fallback retains
    assert body["memory_backend"] == "local"
    assert isinstance(body["insights"], list) and body["insights"]
    assert body["content"]["engagement_rate"] == pytest.approx(7.65, abs=0.01)


def test_create_content_validation(client):
    r = client.post("/api/content", json={"title": "   "})
    assert r.status_code == 422
    r = client.post("/api/content", json={"title": "x", "impressions": -5})
    assert r.status_code == 422


def test_list_and_get_content(client):
    r = client.get("/api/content")
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 1
    cid = items[0]["id"]
    assert client.get("/api/content/%d" % cid).status_code == 200
    assert client.get("/api/content/99999").status_code == 404


# ------------------------------------------------------------------- memory ----

def test_memory_stored_and_learned(client):
    r = client.get("/api/memory")
    assert r.status_code == 200
    d = r.json()
    assert d["total"] > 0
    assert "Topics" in d["categories"]
    joined = " ".join(m["text"] for m in d["categories"]["Topics"])
    assert "AI automation" in joined or "automation" in joined.lower()


def test_memory_learn_endpoint(client):
    r = client.post("/api/memory/learn", json={"text": "Our audience dislikes overly promotional posts."})
    assert r.status_code == 200
    assert r.json()["memory_stored"] is True
    r = client.post("/api/memory/learn", json={})
    assert r.status_code == 400


def test_recall_finds_relevant_memory(client):
    from backend.services.hindsight_service import hindsight_service as hs
    results = hs.recall("AI automation performance")
    assert results, "recall should return local fallback results"
    texts = " ".join(m["text"].lower() for m in results)
    assert "automation" in texts


def test_memory_raw_endpoint(client):
    r = client.get("/api/memory/raw")
    assert r.status_code == 200
    assert r.json()["count"] > 0


# --------------------------------------------------------------------- gaps ----

def test_gap_detection(client):
    r = client.get("/api/gaps")
    assert r.status_code == 200
    gaps = r.json()
    assert gaps, "expected gaps for seeded-like data"
    topics = [g["topic"] for g in gaps]
    assert "AI ROI" in topics
    assert all("Potential" in g["reason"] or "gap" in g["reason"].lower() for g in gaps)


def test_gap_detection_empty_db(client):
    from backend.services.gap_service import gap_service
    from backend.core.database import engine
    from sqlalchemy.orm import Session
    with Session(engine, future=True) as s:
        s.execute(text("DELETE FROM content_plan_items"))
        s.execute(text("DELETE FROM content_plans"))
        s.execute(text("DELETE FROM content_insights"))
        s.execute(text("DELETE FROM content"))
        s.commit()
        assert gap_service.detect_gaps(s) == []
        # restore state for later tests
        from backend.services.seed_service import seed_service
        seed_service.seed_brand(s)
        seed_service.seed_history(s, count=10, learn=False)
        s.commit()


# -------------------------------------------------------------------- plans ----

def test_plan_generation_with_memory(client):
    r = client.post("/api/plans/generate", json={
        "date_range_days": 7, "num_posts": 4, "platforms": ["LinkedIn"], "use_memory": True})
    assert r.status_code == 200
    d = r.json()
    assert d["memory_count"] > 0
    assert len(d["items"]) == 4
    assert all(it["reason"].strip() for it in d["items"]), "every item needs a reason"
    assert any(it["memory_used"] for it in d["items"]), "recommendations must cite memory"
    assert client.get("/api/plans").status_code == 200


def test_plan_without_memory_is_generic(client):
    r = client.post("/api/plans/generate", json={"date_range_days": 7, "num_posts": 3, "use_memory": False})
    assert r.status_code == 200
    d = r.json()
    assert d["memory_count"] == 0
    assert d["memories_used"] == []


def test_plan_generation_empty_db(client):
    from backend.services.strategy_service import strategy_service
    from backend.schemas.api import PlanRequest
    from backend.services.hindsight_service import hindsight_service as hs
    from backend.core.database import engine
    from sqlalchemy.orm import Session
    with Session(engine, future=True) as s:
        s.execute(text("DELETE FROM content_plan_items"))
        s.execute(text("DELETE FROM content_plans"))
        s.execute(text("DELETE FROM content_insights"))
        s.execute(text("DELETE FROM content"))
        s.commit()
        hs._local.clear()
        result = strategy_service.generate_plan(s, PlanRequest(num_posts=3))
        assert result["memory_count"] == 0
        assert len(result["items"]) == 3
        from backend.services.seed_service import seed_service
        seed_service.seed_brand(s)
        seed_service.seed_history(s, count=10, learn=True)
        s.commit()


# --------------------------------------------------------------------- chat ----

def test_chat_with_memory(client):
    r = client.post("/api/chat", json={"message": "What topics have worked best?"})
    assert r.status_code == 200
    d = r.json()
    assert d["memory_count"] > 0
    assert d["hindsight_available"] is False
    assert "memory" in d["reply"].lower() or "-" in d["reply"]


def test_chat_empty_db(client):
    from backend.services.strategy_service import strategy_service
    from backend.services.hindsight_service import hindsight_service as hs
    from backend.core.database import engine
    from sqlalchemy.orm import Session
    with Session(engine, future=True) as s:
        s.execute(text("DELETE FROM content_plan_items"))
        s.execute(text("DELETE FROM content_plans"))
        s.execute(text("DELETE FROM content_insights"))
        s.execute(text("DELETE FROM content"))
        s.commit()
        hs._local.clear()
        resp = strategy_service.chat(s, "What should I post next week?")
        assert "don't have historical knowledge" in resp.reply
        # restore state for later tests
        from backend.services.seed_service import seed_service
        seed_service.seed_brand(s)
        seed_service.seed_history(s, count=10, learn=True)
        s.commit()


# ---------------------------------------------------------------- analytics ----

def test_analytics(client):
    r = client.get("/api/analytics")
    assert r.status_code == 200
    d = r.json()
    assert d["total_content"] >= 1
    assert d["avg_engagement_rate"] > 0
    assert d["top_topic"]


def test_dashboard(client):
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    d = r.json()
    assert "memories_learned" in d
    assert "recommended_next_action" in d


# ---------------------------------------------------------------------- demo ----

def test_demo_reset_and_seed(client):
    r = client.post("/api/demo/reset")
    assert r.status_code == 200
    r = client.post("/api/demo/seed", json={"count": 12})
    assert r.status_code == 200
    assert r.json()["content_created"] == 12
    assert client.get("/api/content").json()
    assert client.get("/api/analytics").json()["total_content"] == 12


def test_full_memory_loop(client):
    """add content -> analyze -> remember -> recall -> generate plan."""
    client.post("/api/demo/reset")
    for i in range(4):
        client.post("/api/content", json={
            "title": "Automation tutorial %d" % i, "topic": "AI automation",
            "platform": "LinkedIn", "content_type": "How-to guide",
            "impressions": 10000, "likes": 900, "comments": 100, "shares": 100,
        })
    r = client.post("/api/content/analyze", json={"content_id": 1})
    r = client.post("/api/content/analyze", json={"content_id": 1})
    assert r.status_code == 200
    assert r.json()["memory_stored"] is True
    assert hindsight_recall_nonempty()


def hindsight_recall_nonempty() -> bool:
    from backend.services.hindsight_service import hindsight_service as hs
    return len(hs.recall("AI automation")) > 0


# ----------------------------------------------------------------- failure ----

def test_hindsight_unavailable_graceful(client, monkeypatch):
    from backend.services import strategy_service as ssmod

    class Boom:
        available = False
        mode = "unavailable"

        def recall(self, *a, **k):
            raise ConnectionError("hindsight down")

        def retain(self, *a, **k):
            raise ConnectionError("hindsight down")

        def retain_batch(self, *a, **k):
            raise ConnectionError("hindsight down")

        def list_memories(self, *a, **k):
            raise ConnectionError("hindsight down")

        def count(self, *a, **k):
            raise ConnectionError("hindsight down")

    monkeypatch.setattr(ssmod.memory_service, "memory", Boom())
    r = client.post("/api/plans/generate", json={"num_posts": 2, "use_memory": True})
    assert r.status_code == 200, "plan must not crash when memory backend is down"
    r2 = client.post("/api/memory/learn", json={"text": "still works when memory is down"})
    assert r2.status_code == 200


def test_invalid_llm_output_falls_back(client, monkeypatch):
    from backend.services import content_service as csmod
    from backend.services.llm_service import LLMService

    class BadLLM(LLMService):
        @property
        def available(self):
            return True
        def chat_json(self, *a, **k):
            from backend.services.llm_service import LLMError
            raise LLMError("malformed output")

    monkeypatch.setattr(type(csmod.llm_service), "available",
                        property(lambda self: True), raising=False)
    monkeypatch.setattr(type(csmod.llm_service), "chat_json",
                        lambda self, *a, **k: (_ for _ in ()).throw(__import__('backend.services.llm_service', fromlist=['LLMError']).LLMError("malformed output")),
                        raising=False)
    payload = {
        "title": "LLM fallback check", "topic": "AI tools", "platform": "Blog",
        "impressions": 5000, "likes": 100, "comments": 10, "shares": 5,
    }
    r = client.post("/api/content", json=payload)
    assert r.status_code == 200, "ingestion must survive invalid LLM output"
    assert r.json()["insights"]
