"""API tests: an in-memory database is filled with a small synthetic sample
through the real pipeline, and the endpoints are called with FastAPI's TestClient."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.analyzer import RuleBasedAnalyzer
from app.api.routes import get_session
from app.db import Base
from app.main import app
from app.pipeline import process_instruction
from tests.test_pipeline import entry, make_docx

VISITOR = "test-visitor-0001"


@pytest.fixture
def client(tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    make_docx(tmp_path / "raw/11.1.1/v1.docx", ["החניה תהיה במגרש המשרד.", "אין לגרור נגרר."])
    make_docx(tmp_path / "raw/11.1.1/v2.docx", ["החניה תהיה במגרש המשרד בלבד.", "אין לגרור נגרר."])
    make_docx(tmp_path / "raw/7.1.1/v1.docx", ["סעיף ישן."])
    make_docx(tmp_path / "raw/7.1.1/v2.docx", ["סעיף ישן.", "סעיף חדש שנוסף."])
    make_docx(tmp_path / "raw/13.1.1/v1.docx", ["מהדורה יחידה."])
    e7 = entry("7.1.1", [1, 2]) | {"main_chapter": 7, "main_chapter_name": "התקשרויות ורכישות"}
    e7["editions"][1]["valid_from"] = "2026-03-01"   # 11.1.1 gets 2026-02-01 from entry()
    e13 = entry("13.1.1", [1]) | {"main_chapter": 13, "main_chapter_name": "שכר"}
    with Session() as s:
        for e in (entry("11.1.1", [1, 2]), e7, e13):
            process_instruction(s, e, tmp_path, RuleBasedAnalyzer())
        s.commit()

    def override():
        with Session() as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "instructions": 3}


def test_chapters(client):
    assert [c["number"] for c in client.get("/api/chapters").json()] == [7, 11, 13]


def test_feed_is_newest_first(client):
    feed = client.get("/api/changes").json()
    assert [f["instruction_code"] for f in feed] == ["7.1.1", "11.1.1"]   # 13.1.1 has one edition
    assert feed[0]["counts"]["added"] == 1 and feed[1]["counts"]["modified"] == 1


def test_feed_filtered_by_chapters(client):
    feed = client.get("/api/changes", params={"chapters": [11, 13]}).json()
    assert [f["instruction_code"] for f in feed] == ["11.1.1"]


def test_since_marks_new_items(client):
    feed = client.get("/api/changes", params={"since": "2026-02-15T00:00:00"}).json()
    assert {f["instruction_code"]: f["is_new"] for f in feed} == {"7.1.1": True, "11.1.1": False}
    only = client.get("/api/changes", params={"since": "2026-02-15T00:00:00", "only_new": True}).json()
    assert [f["instruction_code"] for f in only] == ["7.1.1"]


def test_change_set_detail_has_word_segments(client):
    d = client.get("/api/instructions/11.1.1/changes/2").json()
    [change] = d["changes"]
    assert change["kind"] == "modified"
    assert {"op": "insert", "text": "בלבד."} in change["segments"] or \
        any(s["op"] == "insert" and "בלבד" in s["text"] for s in change["segments"])


def test_edition_text_for_in_browser_viewing(client):
    blocks = client.get("/api/instructions/13.1.1/editions/1").json()["blocks"]
    assert [b["text"] for b in blocks] == ["הנחיות לביצוע", "מהדורה יחידה."]


def test_single_edition_instruction_has_no_comparisons(client):
    inst = client.get("/api/instructions/13.1.1").json()
    assert inst["change_sets"] == [] and len(inst["editions"]) == 1


@pytest.mark.parametrize("url", ["/api/instructions/99.9.9",
                                 "/api/instructions/11.1.1/changes/7",
                                 "/api/instructions/11.1.1/editions/5"])
def test_not_found(client, url):
    assert client.get(url).status_code == 404


def test_visitor_subscriptions_and_visits(client):
    v = client.get(f"/api/visitors/{VISITOR}").json()
    assert v["chapters"] == [] and v["last_visit_at"] is None

    v = client.put(f"/api/visitors/{VISITOR}/subscriptions", json={"chapters": [11, 7, 11]}).json()
    assert v["chapters"] == [7, 11]   # duplicates removed
    v = client.put(f"/api/visitors/{VISITOR}/subscriptions", json={"chapters": [11, 13]}).json()
    assert v["chapters"] == [11, 13]   # keeps 11, adds 13, drops 7

    first = client.post(f"/api/visitors/{VISITOR}/visit").json()
    assert first["previous_visit_at"] is None
    second = client.post(f"/api/visitors/{VISITOR}/visit").json()
    assert second["previous_visit_at"] is not None


def test_invalid_visitor_id_is_rejected(client):
    assert client.get("/api/visitors/bad id!").status_code == 400
