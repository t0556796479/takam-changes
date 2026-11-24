"""Compare two editions of an instruction.

1. Paragraph level: align the two lists of paragraphs (difflib), using the
   normalized text so cosmetic differences do not break the alignment.
2. Paired paragraphs that differ become "modified"; unpaired ones become
   "added" / "removed".
3. Word level: inside a modified paragraph, mark exactly which words changed,
   so the UI can highlight them (like Track Changes).
"""
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import Enum

from app.core.extract import Block
from app.core.normalize import normalize

# Below this similarity two paragraphs are treated as remove + add, not an edit.
MODIFIED_SIMILARITY = 0.5
# A removed and an added paragraph this similar, anywhere in the document, are
# treated as one paragraph that moved (and maybe was slightly edited).
MOVED_SIMILARITY = 0.8


class ChangeKind(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    MOVED = "moved"            # same text, different place in the document


@dataclass(frozen=True)
class Segment:
    """A piece of a word-level diff: op is 'equal', 'insert' or 'delete'."""
    op: str
    text: str


@dataclass
class Change:
    kind: ChangeKind
    heading: str
    old_text: str | None
    new_text: str | None
    segments: list[Segment] = field(default_factory=list)
    moved_from: str | None = None   # old heading, when the paragraph changed place


@dataclass
class DiffResult:
    changes: list[Change]
    cosmetic_only_count: int   # paragraphs that differ only in punctuation etc.


def diff_blocks(old: list[Block], new: list[Block]) -> DiffResult:
    old_norm = [normalize(b.text) for b in old]
    new_norm = [normalize(b.text) for b in new]

    changes: list[Change] = []
    cosmetic = 0
    matcher = SequenceMatcher(a=old_norm, b=new_norm, autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            # Normalized text is identical; count raw-text differences as cosmetic.
            cosmetic += sum(old[i].text != new[j].text for i, j in zip(range(i1, i2), range(j1, j2)))
        elif op == "delete":
            changes += [_removed(b) for b in old[i1:i2]]
        elif op == "insert":
            changes += [_added(b) for b in new[j1:j2]]
        else:  # replace
            changes += _pair_replaced(old[i1:i2], new[j1:j2], old_norm[i1:i2], new_norm[j1:j2])
    return DiffResult(changes=_detect_moves(changes), cosmetic_only_count=cosmetic)


def _detect_moves(changes: list[Change]) -> list[Change]:
    """Pair a removed paragraph with an added one elsewhere that has the same
    (or almost the same) text: that is a move, not a delete + add.

    Typical case in Takam documents: appendices that were re-ordered.
    """
    removed = [c for c in changes if c.kind == ChangeKind.REMOVED]
    added = [c for c in changes if c.kind == ChangeKind.ADDED]
    if not removed or not added:
        return changes

    added_norm = {id(a): normalize(a.new_text or "") for a in added}
    replacement: dict[int, Change | None] = {}   # id(change) -> new change, or None to drop
    for r in removed:
        r_norm = normalize(r.old_text or "")
        best, best_score = None, 0.0
        for a in added:
            if id(a) in replacement:
                continue
            score = 1.0 if added_norm[id(a)] == r_norm else \
                SequenceMatcher(a=r_norm, b=added_norm[id(a)], autojunk=False).ratio()
            if score > best_score:
                best, best_score = a, score
            if score == 1.0:
                break
        if best is None or best_score < MOVED_SIMILARITY:
            continue
        if best_score == 1.0:
            merged = Change(ChangeKind.MOVED, best.heading, r.old_text, best.new_text,
                            moved_from=r.heading)
        else:
            merged = Change(ChangeKind.MODIFIED, best.heading, r.old_text, best.new_text,
                            word_diff(r.old_text or "", best.new_text or ""), moved_from=r.heading)
        replacement[id(r)] = None        # drop the "removed" entry
        replacement[id(best)] = merged   # the "added" entry becomes the move/edit
    return [replacement.get(id(c), c) for c in changes if replacement.get(id(c), c) is not None]


def _pair_replaced(old: list[Block], new: list[Block],
                   old_norm: list[str], new_norm: list[str]) -> list[Change]:
    """Greedily pair the most similar old/new paragraphs inside a replaced region."""
    result: list[Change] = []
    used_new: set[int] = set()
    for i, ob in enumerate(old):
        best_j, best_score = None, 0.0
        for j in range(len(new)):
            if j in used_new:
                continue
            score = SequenceMatcher(a=old_norm[i], b=new_norm[j], autojunk=False).ratio()
            if score > best_score:
                best_j, best_score = j, score
        if best_j is not None and best_score >= MODIFIED_SIMILARITY:
            used_new.add(best_j)
            nb = new[best_j]
            result.append(Change(ChangeKind.MODIFIED, nb.heading, ob.text, nb.text,
                                 word_diff(ob.text, nb.text)))
        else:
            result.append(_removed(ob))
    result += [_added(nb) for j, nb in enumerate(new) if j not in used_new]
    return result


def word_diff(old: str, new: str) -> list[Segment]:
    a, b = old.split(), new.split()
    segments: list[Segment] = []
    for op, i1, i2, j1, j2 in SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op == "equal":
            segments.append(Segment("equal", " ".join(a[i1:i2])))
        else:
            if i2 > i1:
                segments.append(Segment("delete", " ".join(a[i1:i2])))
            if j2 > j1:
                segments.append(Segment("insert", " ".join(b[j1:j2])))
    return segments


def _removed(b: Block) -> Change:
    return Change(ChangeKind.REMOVED, b.heading, b.text, None)


def _added(b: Block) -> Change:
    return Change(ChangeKind.ADDED, b.heading, None, b.text)
