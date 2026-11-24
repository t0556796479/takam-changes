"""Processing pipeline: data/ files -> database.

Usage (from backend/):  python -m app.pipeline

For every instruction in data/instructions.json:
  1. extract the text of each edition,
  2. compare each pair of consecutive editions,
  3. analyze the changes (AI or rule-based, per settings),
  4. store everything in the database.

Instructions are rebuilt from scratch on every run, so the pipeline is safe to
re-run. Visitor data is not touched. One broken file does not stop the run.
"""
import json
import logging
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.ai.analyzer import ChangeAnalyzer, build_analyzer
from app.config import get_settings
from app.core.diff import diff_blocks
from app.core.extract import Block, ExtractionError, extract_blocks
from app.db import Base, SessionLocal, engine
from app.models import Change, ChangeSet, Edition, Instruction

log = logging.getLogger("pipeline")


def load_catalog(data_dir: Path) -> list[dict]:
    return json.loads((data_dir / "instructions.json").read_text(encoding="utf-8"))


def process_instruction(session: Session, entry: dict, data_dir: Path,
                        analyzer: ChangeAnalyzer) -> Instruction:
    existing = session.query(Instruction).filter_by(code=entry["code"]).one_or_none()
    if existing:
        session.delete(existing)
        session.flush()

    instruction = Instruction(
        code=entry["code"], name=entry["name"], main_chapter=entry["main_chapter"],
        main_chapter_name=entry["main_chapter_name"], sub_chapter_name=entry["sub_chapter_name"],
        source_url=entry["source_url"])
    session.add(instruction)

    extracted: list[tuple[Edition, list[Block]]] = []
    for ed in sorted(entry["editions"], key=lambda e: e["version"]):
        path = data_dir / ed["file"]
        try:
            blocks = extract_blocks(path)
        except (ExtractionError, FileNotFoundError) as e:
            log.warning("  %s v%s skipped: %s", entry["code"], ed["version"], e)
            continue
        edition = Edition(version=ed["version"], file_path=ed["file"],
                          valid_from=_parse_date(ed.get("valid_from")),
                          blocks=[asdict(b) for b in blocks])
        instruction.editions.append(edition)
        extracted.append((edition, blocks))

    for (old_ed, old_blocks), (new_ed, new_blocks) in zip(extracted, extracted[1:]):
        diff = diff_blocks(old_blocks, new_blocks)
        analysis = analyzer.analyze(instruction.name, diff)
        cs = ChangeSet(from_version=old_ed.version, to_version=new_ed.version,
                       published_at=new_ed.valid_from, summary=analysis.summary,
                       analyzer=analysis.analyzer, cosmetic_only_count=diff.cosmetic_only_count)
        for pos, (change, cls, expl) in enumerate(
                zip(diff.changes, analysis.classifications, analysis.explanations)):
            cs.changes.append(Change(
                position=pos, kind=change.kind.value, heading=change.heading,
                moved_from=change.moved_from,
                old_text=change.old_text, new_text=change.new_text,
                segments=[asdict(s) for s in change.segments],
                classification=cls.value, explanation=expl))
        instruction.change_sets.append(cs)
        log.info("  %s v%s->v%s: %d changes (%s)", entry["code"], old_ed.version,
                 new_ed.version, len(diff.changes), analysis.analyzer)
    return instruction


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def run() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = get_settings()
    Base.metadata.create_all(engine)
    analyzer = build_analyzer(settings.ai_provider, settings.anthropic_api_key, settings.ai_model)

    failed = 0
    with SessionLocal() as session:
        for entry in load_catalog(settings.data_dir):
            log.info("Processing %s %s", entry["code"], entry["name"])
            try:
                process_instruction(session, entry, settings.data_dir, analyzer)
                session.commit()
            except Exception:
                session.rollback()
                failed += 1
                log.exception("  failed")
    log.info("Done. %d failed.", failed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
