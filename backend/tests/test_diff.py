from app.core.diff import ChangeKind, diff_blocks, word_diff
from app.core.extract import Block


def b(text, heading="פרק"):
    return Block(text, heading, False)


def test_identical_editions_have_no_changes():
    blocks = [b("סעיף ראשון."), b("סעיף שני.")]
    result = diff_blocks(blocks, list(blocks))
    assert result.changes == [] and result.cosmetic_only_count == 0


def test_cosmetic_only_difference_is_counted_not_reported():
    result = diff_blocks([b("העובד ישיב את המפתחות - מיד.")], [b("העובד ישיב את המפתחות, מיד")])
    assert result.changes == []
    assert result.cosmetic_only_count == 1


def test_modified_paragraph_with_word_level_segments():
    old = [b("קבלת קוד ערבות עבור כל מציע.", "נספח ב")]
    new = [b("קבלת מספר דרישת הערבות עבור כל מציע.", "נספח ב")]
    [change] = diff_blocks(old, new).changes
    assert change.kind == ChangeKind.MODIFIED
    assert change.heading == "נספח ב"
    ops = [(s.op, s.text) for s in change.segments]
    assert ("delete", "קוד ערבות") in ops
    assert ("insert", "מספר דרישת הערבות") in ops


def test_added_and_removed_paragraphs():
    old = [b("א."), b("סעיף שיימחק לגמרי מההוראה."), b("ג.")]
    new = [b("א."), b("ג."), b("סעיף חדש לגמרי בסוף ההוראה.")]
    kinds = sorted(c.kind.value for c in diff_blocks(old, new).changes)
    assert kinds == ["added", "removed"]


def test_unrelated_replacement_is_remove_plus_add_not_modify():
    result = diff_blocks([b("חניית הרכב תהיה במגרש המשרד.")], [b("יש לדווח על כל תאונה תוך 24 שעות.")])
    assert sorted(c.kind.value for c in result.changes) == ["added", "removed"]


def test_empty_editions():
    assert diff_blocks([], []).changes == []
    assert [c.kind for c in diff_blocks([], [b("חדש.")]).changes] == [ChangeKind.ADDED]


def test_word_diff_of_equal_text_is_single_equal_segment():
    assert [(s.op, s.text) for s in word_diff("אותו טקסט", "אותו טקסט")] == [("equal", "אותו טקסט")]
