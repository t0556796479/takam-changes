"""Response/request shapes of the HTTP API (validated by FastAPI)."""
from datetime import date, datetime

from pydantic import BaseModel


class Chapter(BaseModel):
    number: int
    name: str
    instruction_count: int


class ChangeCounts(BaseModel):
    modified: int = 0
    added: int = 0
    removed: int = 0
    moved: int = 0


class ChangeSetSummary(BaseModel):
    instruction_code: str
    instruction_name: str
    main_chapter: int
    main_chapter_name: str
    from_version: int
    to_version: int
    published_at: date | None
    summary: str
    analyzer: str
    counts: ChangeCounts
    is_new: bool = False   # published after the visitor's previous visit


class Segment(BaseModel):
    op: str
    text: str


class ChangeOut(BaseModel):
    kind: str
    heading: str
    moved_from: str | None
    old_text: str | None
    new_text: str | None
    segments: list[Segment]
    classification: str
    explanation: str


class ChangeSetDetail(ChangeSetSummary):
    cosmetic_only_count: int
    changes: list[ChangeOut]


class EditionInfo(BaseModel):
    version: int
    valid_from: date | None


class InstructionOut(BaseModel):
    code: str
    name: str
    main_chapter: int
    main_chapter_name: str
    sub_chapter_name: str
    source_url: str
    editions: list[EditionInfo]
    change_sets: list[ChangeSetSummary]


class Block(BaseModel):
    text: str
    heading: str
    is_heading: bool


class EditionContent(BaseModel):
    instruction_code: str
    version: int
    valid_from: date | None
    blocks: list[Block]


class VisitorOut(BaseModel):
    id: str
    chapters: list[int]
    last_visit_at: datetime | None


class SubscriptionsIn(BaseModel):
    chapters: list[int]


class VisitOut(BaseModel):
    previous_visit_at: datetime | None
    last_visit_at: datetime
