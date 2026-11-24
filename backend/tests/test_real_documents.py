"""Regression test on a real instruction from the sample (data/raw/11.4.4).

Edition 5 of "נסיעה וחניה ברכב איגום" hides a substantive change inside an
existing paragraph: drivers may use a government car without the 7-day limit.
The test makes sure the comparison finds it at word level. It is skipped when
the sample files are not present (e.g. a checkout without data/raw)."""
import pytest

from app.config import get_settings
from app.core.diff import ChangeKind, diff_blocks
from app.core.extract import extract_blocks

RAW = get_settings().data_dir / "raw" / "11.4.4"
pytestmark = pytest.mark.skipif(not (RAW / "v5.docx").exists(), reason="sample data not present")


@pytest.fixture(scope="module")
def result():
    return diff_blocks(extract_blocks(RAW / "v4.docx"), extract_blocks(RAW / "v5.docx"))


def test_finds_the_hidden_substantive_addition(result):
    [change] = [c for c in result.changes if "כנהג" in (c.new_text or "")]
    assert change.kind == ChangeKind.MODIFIED
    assert change.heading.endswith("שימוש ברכב")
    inserted = " ".join(s.text for s in change.segments if s.op == "insert")
    assert "עובד המוגדר בתפקידו כנהג" in inserted and "ללא הגבלה" in inserted


def test_small_number_of_changes_in_a_long_document(result):
    # 49 paragraphs in each edition, only a handful really changed:
    # the reader is pointed at 4 paragraphs instead of re-reading everything.
    assert len(result.changes) <= 6
    assert all(c.kind == ChangeKind.MODIFIED for c in result.changes)
