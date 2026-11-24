"""End-to-end test of the pipeline on small synthetic .docx files.

The files are generated in a temp folder, so the test covers edge cases that
may not exist in the real sample (identical editions, a corrupted file, a
single edition) and does not depend on data that can change.
"""
import json

import docx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.analyzer import RuleBasedAnalyzer
from app.db import Base
from app.models import Instruction
from app.pipeline import process_instruction


def make_docx(path, paragraphs):
    path.parent.mkdir(parents=True, exist_ok=True)
    d = docx.Document()
    d.add_heading("הנחיות לביצוע", level=1)
    for p in paragraphs:
        d.add_paragraph(p)
    d.save(path)


def entry(code, versions):
    return {"code": code, "name": f"הוראה {code}", "main_chapter": 11,
            "main_chapter_name": "רכב ממשלתי", "sub_chapter_name": "תפעול",
            "source_url": "https://example", "editions": [
                {"version": v, "file": f"raw/{code}/v{v}.docx", "valid_from": f"2026-0{v}-01"}
                for v in versions]}


def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_two_editions_produce_a_change_set(tmp_path):
    make_docx(tmp_path / "raw/1.1.1/v1.docx", ["החניה תהיה במגרש המשרד.", "אין לגרור נגרר."])
    make_docx(tmp_path / "raw/1.1.1/v2.docx", ["החניה תהיה במגרש המשרד בלבד.", "אין לגרור נגרר."])
    s = session()
    inst = process_instruction(s, entry("1.1.1", [1, 2]), tmp_path, RuleBasedAnalyzer())
    s.commit()
    [cs] = inst.change_sets
    assert (cs.from_version, cs.to_version) == (1, 2)
    assert [c.kind for c in cs.changes] == ["modified"]
    assert cs.changes[0].heading == "הנחיות לביצוע"
    assert len(inst.editions[1].blocks) == 3   # heading + 2 paragraphs, kept for in-browser viewing


def test_identical_editions_give_empty_change_set(tmp_path):
    for v in (1, 2):
        make_docx(tmp_path / f"raw/2.2.2/v{v}.docx", ["אותו טקסט בדיוק."])
    s = session()
    [cs] = process_instruction(s, entry("2.2.2", [1, 2]), tmp_path, RuleBasedAnalyzer()).change_sets
    assert cs.changes == [] and "לא נמצאו שינויים" in cs.summary


def test_single_edition_has_no_change_set(tmp_path):
    make_docx(tmp_path / "raw/3.3.3/v1.docx", ["טקסט."])
    s = session()
    inst = process_instruction(s, entry("3.3.3", [1]), tmp_path, RuleBasedAnalyzer())
    assert len(inst.editions) == 1 and inst.change_sets == []


def test_corrupted_file_is_skipped_not_fatal(tmp_path):
    make_docx(tmp_path / "raw/4.4.4/v1.docx", ["טקסט."])
    (tmp_path / "raw/4.4.4/v2.docx").write_bytes(b"this is not a docx")
    s = session()
    inst = process_instruction(s, entry("4.4.4", [1, 2]), tmp_path, RuleBasedAnalyzer())
    assert [e.version for e in inst.editions] == [1] and inst.change_sets == []


def test_rerun_replaces_instead_of_duplicating(tmp_path):
    make_docx(tmp_path / "raw/5.5.5/v1.docx", ["א."])
    make_docx(tmp_path / "raw/5.5.5/v2.docx", ["ב שונה לגמרי."])
    s = session()
    for _ in range(2):
        process_instruction(s, entry("5.5.5", [1, 2]), tmp_path, RuleBasedAnalyzer())
        s.commit()
    assert s.query(Instruction).filter_by(code="5.5.5").count() == 1


def test_missing_file_is_skipped(tmp_path):
    # The catalog lists v2, but the file was never downloaded.
    make_docx(tmp_path / "raw/5.5.5/v1.docx", ["טקסט."])
    s = session()
    inst = process_instruction(s, entry("5.5.5", [1, 2]), tmp_path, RuleBasedAnalyzer())
    assert [e.version for e in inst.editions] == [1] and inst.change_sets == []


def test_empty_edition_shows_everything_as_removed(tmp_path):
    make_docx(tmp_path / "raw/6.6.6/v1.docx", ["סעיף ראשון.", "סעיף שני."])
    path = tmp_path / "raw/6.6.6/v2.docx"
    docx.Document().save(path)   # a document with no paragraphs at all
    s = session()
    [cs] = process_instruction(s, entry("6.6.6", [1, 2]), tmp_path, RuleBasedAnalyzer()).change_sets
    assert sorted(c.kind for c in cs.changes) == ["removed", "removed", "removed"]


def test_heading_only_change(tmp_path):
    # Renaming a section heading is a change the reader should see.
    for v, title in ((1, "הנחיות לביצוע"), (2, "הנחיות לביצוע ולדיווח")):
        path = tmp_path / f"raw/8.8.8/v{v}.docx"
        path.parent.mkdir(parents=True, exist_ok=True)
        d = docx.Document()
        d.add_heading(title, level=1)
        d.add_paragraph("אותו תוכן.")
        d.save(path)
    s = session()
    [cs] = process_instruction(s, entry("8.8.8", [1, 2]), tmp_path, RuleBasedAnalyzer()).change_sets
    assert [c.kind for c in cs.changes] == ["modified"]
    assert any(seg["op"] == "insert" and "ולדיווח" in seg["text"] for seg in cs.changes[0].segments)
