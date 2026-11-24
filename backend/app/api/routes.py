"""HTTP endpoints. Read-only access to the processed data, plus the anonymous
visitor's topic choices and last visit ("what changed since my last visit")."""
import re
from collections import Counter
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api import schemas
from app.db import SessionLocal
from app.models import ChangeSet, Edition, Instruction, Subscription, Visitor

router = APIRouter(prefix="/api")

# The visitor id is created in the browser (crypto.randomUUID); accept only safe values.
VISITOR_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def get_session():
    with SessionLocal() as session:
        yield session


def _summary(cs: ChangeSet, since: datetime | None = None) -> schemas.ChangeSetSummary:
    counts = Counter(c.kind for c in cs.changes)
    inst = cs.instruction
    is_new = bool(since and cs.published_at and cs.published_at > since.date())
    return schemas.ChangeSetSummary(
        instruction_code=inst.code, instruction_name=inst.name,
        main_chapter=inst.main_chapter, main_chapter_name=inst.main_chapter_name,
        from_version=cs.from_version, to_version=cs.to_version, published_at=cs.published_at,
        summary=cs.summary, analyzer=cs.analyzer, counts=schemas.ChangeCounts(**counts),
        is_new=is_new)


def _get_instruction(session: Session, code: str) -> Instruction:
    inst = session.scalar(select(Instruction).where(Instruction.code == code))
    if inst is None:
        raise HTTPException(404, f"Instruction {code} not found")
    return inst


def _get_visitor(session: Session, visitor_id: str, create: bool = True) -> Visitor:
    if not VISITOR_ID.match(visitor_id):
        raise HTTPException(400, "Invalid visitor id")
    visitor = session.get(Visitor, visitor_id)
    if visitor is None and create:
        visitor = Visitor(id=visitor_id)
        session.add(visitor)
        session.commit()
    return visitor


@router.get("/health")
def health(session: Session = Depends(get_session)):
    """Used by deployment checks: the app is up and the database is reachable and loaded."""
    count = session.scalar(select(func.count()).select_from(Instruction))
    return {"status": "ok", "instructions": count}


@router.get("/chapters", response_model=list[schemas.Chapter])
def chapters(session: Session = Depends(get_session)):
    rows = session.execute(
        select(Instruction.main_chapter, Instruction.main_chapter_name, func.count())
        .group_by(Instruction.main_chapter, Instruction.main_chapter_name)
        .order_by(Instruction.main_chapter)).all()
    return [schemas.Chapter(number=n, name=name, instruction_count=c) for n, name, c in rows]


@router.get("/changes", response_model=list[schemas.ChangeSetSummary])
def changes(chapters: list[int] = Query(default=[]),
            since: datetime | None = None,
            only_new: bool = False,
            session: Session = Depends(get_session)):
    """Change feed, newest first. Optional filters: chapters (repeatable) and
    since (marks newer items is_new; with only_new=true, returns only those)."""
    query = (select(ChangeSet).join(ChangeSet.instruction)
             .options(selectinload(ChangeSet.changes), selectinload(ChangeSet.instruction))
             .order_by(ChangeSet.published_at.desc().nulls_last(), Instruction.code))
    if chapters:
        query = query.where(Instruction.main_chapter.in_(chapters))
    items = [_summary(cs, since) for cs in session.scalars(query)]
    return [i for i in items if i.is_new] if only_new and since else items


@router.get("/instructions/{code}", response_model=schemas.InstructionOut)
def instruction(code: str, session: Session = Depends(get_session)):
    inst = _get_instruction(session, code)
    return schemas.InstructionOut(
        code=inst.code, name=inst.name, main_chapter=inst.main_chapter,
        main_chapter_name=inst.main_chapter_name, sub_chapter_name=inst.sub_chapter_name,
        source_url=inst.source_url,
        editions=[schemas.EditionInfo(version=e.version, valid_from=e.valid_from) for e in inst.editions],
        change_sets=[_summary(cs) for cs in reversed(inst.change_sets)])


@router.get("/instructions/{code}/changes/{to_version}", response_model=schemas.ChangeSetDetail)
def change_set(code: str, to_version: int, session: Session = Depends(get_session)):
    inst = _get_instruction(session, code)
    cs = next((c for c in inst.change_sets if c.to_version == to_version), None)
    if cs is None:
        raise HTTPException(404, f"No comparison for {code} edition {to_version}")
    return schemas.ChangeSetDetail(
        **_summary(cs).model_dump(), cosmetic_only_count=cs.cosmetic_only_count,
        changes=[schemas.ChangeOut(kind=c.kind, heading=c.heading, moved_from=c.moved_from,
                                   old_text=c.old_text, new_text=c.new_text, segments=c.segments,
                                   classification=c.classification, explanation=c.explanation)
                 for c in cs.changes])


@router.get("/instructions/{code}/editions/{version}", response_model=schemas.EditionContent)
def edition(code: str, version: int, session: Session = Depends(get_session)):
    """Full text of one edition, so it can be read in the browser without downloading."""
    inst = _get_instruction(session, code)
    ed = session.scalar(select(Edition).where(Edition.instruction_id == inst.id,
                                              Edition.version == version))
    if ed is None:
        raise HTTPException(404, f"Edition {version} of {code} not found")
    return schemas.EditionContent(instruction_code=code, version=ed.version,
                                  valid_from=ed.valid_from, blocks=ed.blocks)


@router.get("/visitors/{visitor_id}", response_model=schemas.VisitorOut)
def get_visitor(visitor_id: str, session: Session = Depends(get_session)):
    v = _get_visitor(session, visitor_id)
    return schemas.VisitorOut(id=v.id, chapters=sorted(s.main_chapter for s in v.subscriptions),
                              last_visit_at=v.last_visit_at)


@router.put("/visitors/{visitor_id}/subscriptions", response_model=schemas.VisitorOut)
def set_subscriptions(visitor_id: str, body: schemas.SubscriptionsIn,
                      session: Session = Depends(get_session)):
    v = _get_visitor(session, visitor_id)
    # Update in place: replacing the whole list would insert rows that already
    # exist (e.g. keeping chapter 11 while adding 13) and break the unique constraint.
    wanted = set(body.chapters)
    v.subscriptions = [s for s in v.subscriptions if s.main_chapter in wanted]
    existing = {s.main_chapter for s in v.subscriptions}
    v.subscriptions.extend(Subscription(main_chapter=c) for c in sorted(wanted - existing))
    session.commit()
    return get_visitor(visitor_id, session)


@router.post("/visitors/{visitor_id}/visit", response_model=schemas.VisitOut)
def record_visit(visitor_id: str, session: Session = Depends(get_session)):
    """Mark 'I have seen everything up to now'. Returns the previous visit time."""
    v = _get_visitor(session, visitor_id)
    previous = v.last_visit_at
    v.last_visit_at = datetime.now(timezone.utc)
    session.commit()
    return schemas.VisitOut(previous_visit_at=previous, last_visit_at=v.last_visit_at)
