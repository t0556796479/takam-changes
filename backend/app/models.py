"""Database tables."""
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Instruction(Base):
    __tablename__ = "instructions"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(300))
    main_chapter: Mapped[int] = mapped_column(Integer, index=True)
    main_chapter_name: Mapped[str] = mapped_column(String(200))
    sub_chapter_name: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str] = mapped_column(String(300))

    editions: Mapped[list["Edition"]] = relationship(back_populates="instruction",
                                                     order_by="Edition.version",
                                                     cascade="all, delete-orphan")
    change_sets: Mapped[list["ChangeSet"]] = relationship(back_populates="instruction",
                                                          order_by="ChangeSet.to_version",
                                                          cascade="all, delete-orphan")


class Edition(Base):
    __tablename__ = "editions"
    __table_args__ = (UniqueConstraint("instruction_id", "version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    instruction_id: Mapped[int] = mapped_column(ForeignKey("instructions.id"))
    version: Mapped[int] = mapped_column(Integer)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    file_path: Mapped[str] = mapped_column(String(300))
    # Extracted paragraphs, so the instruction can be read in the browser without downloading.
    blocks: Mapped[list] = mapped_column(JSON, default=list)

    instruction: Mapped[Instruction] = relationship(back_populates="editions")


class ChangeSet(Base):
    """The comparison between two consecutive editions of one instruction."""
    __tablename__ = "change_sets"
    id: Mapped[int] = mapped_column(primary_key=True)
    instruction_id: Mapped[int] = mapped_column(ForeignKey("instructions.id"))
    from_version: Mapped[int] = mapped_column(Integer)
    to_version: Mapped[int] = mapped_column(Integer)
    published_at: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    summary: Mapped[str] = mapped_column(Text)
    analyzer: Mapped[str] = mapped_column(String(100))
    cosmetic_only_count: Mapped[int] = mapped_column(Integer, default=0)

    instruction: Mapped[Instruction] = relationship(back_populates="change_sets")
    changes: Mapped[list["Change"]] = relationship(back_populates="change_set",
                                                   order_by="Change.position",
                                                   cascade="all, delete-orphan")


class Change(Base):
    __tablename__ = "changes"
    id: Mapped[int] = mapped_column(primary_key=True)
    change_set_id: Mapped[int] = mapped_column(ForeignKey("change_sets.id"))
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))
    heading: Mapped[str] = mapped_column(String(500), default="")
    moved_from: Mapped[str | None] = mapped_column(String(500), nullable=True)
    old_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    segments: Mapped[list] = mapped_column(JSON, default=list)   # word-level diff
    classification: Mapped[str] = mapped_column(String(20))
    explanation: Mapped[str] = mapped_column(Text, default="")

    change_set: Mapped[ChangeSet] = relationship(back_populates="changes")


class Visitor(Base):
    """Anonymous visitor (id generated in the browser). Used for 'what changed since my last visit'."""
    __tablename__ = "visitors"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_visit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    subscriptions: Mapped[list["Subscription"]] = relationship(cascade="all, delete-orphan")


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("visitor_id", "main_chapter"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    visitor_id: Mapped[str] = mapped_column(ForeignKey("visitors.id"))
    main_chapter: Mapped[int] = mapped_column(Integer)
