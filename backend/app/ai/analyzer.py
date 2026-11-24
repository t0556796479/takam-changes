"""Turn a raw diff into something a person can read: a short summary, and a
label per change saying whether it is substantive or only a wording change.

Two implementations behind one interface:
- RuleBasedAnalyzer: no AI, no key, deterministic. Always available.
- ClaudeAnalyzer: asks Claude to classify and summarize. If the API is not
  configured, fails or declines, it falls back to RuleBasedAnalyzer, so the
  product keeps working (and the fallback is recorded on the result).
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from app.core.diff import Change, ChangeKind, DiffResult

log = logging.getLogger(__name__)


class Classification(str, Enum):
    SUBSTANTIVE = "substantive"   # changes a rule, amount, duty, authority...
    WORDING = "wording"           # same meaning, different phrasing
    UNCLASSIFIED = "unclassified" # rule-based mode cannot tell
    MOVED = "moved"               # same text, only its place changed


@dataclass
class Analysis:
    summary: str
    classifications: list[Classification]   # one per change, same order
    explanations: list[str] = field(default_factory=list)
    analyzer: str = "rules"


class ChangeAnalyzer(Protocol):
    def analyze(self, instruction_name: str, diff: DiffResult) -> Analysis: ...


NO_CHANGES_SUMMARY = "לא נמצאו שינויים בתוכן בין המהדורות."


class RuleBasedAnalyzer:
    """Deterministic summary built from the diff itself."""

    def analyze(self, instruction_name: str, diff: DiffResult) -> Analysis:
        changes = diff.changes
        if not changes:
            summary = NO_CHANGES_SUMMARY
            if diff.cosmetic_only_count:
                summary += f" ({diff.cosmetic_only_count} שינויי פיסוק/עיצוב בלבד)"
            return Analysis(summary, [], [], "rules")

        counts = Counter(c.kind for c in changes)
        if counts[ChangeKind.MOVED] == len(changes):
            return Analysis(f"לא נמצאו שינויים בתוכן. {len(changes)} פסקאות הועברו למקום אחר במסמך.",
                            [Classification.MOVED] * len(changes), [""] * len(changes), "rules")
        parts = []
        if counts[ChangeKind.MODIFIED]:
            parts.append(f"{counts[ChangeKind.MODIFIED]} סעיפים שונו")
        if counts[ChangeKind.ADDED]:
            parts.append(f"{counts[ChangeKind.ADDED]} נוספו")
        if counts[ChangeKind.REMOVED]:
            parts.append(f"{counts[ChangeKind.REMOVED]} הוסרו")
        sections = _unique_sections([c for c in changes if c.kind != ChangeKind.MOVED])
        summary = ", ".join(parts) + "."
        if sections:
            summary += " בפרקים: " + ", ".join(sections[:3]) + ("..." if len(sections) > 3 else "")
        if counts[ChangeKind.MOVED]:
            summary += f" בנוסף {counts[ChangeKind.MOVED]} פסקאות הועברו ללא שינוי."
        labels = [Classification.MOVED if c.kind == ChangeKind.MOVED else Classification.UNCLASSIFIED
                  for c in changes]
        return Analysis(summary, labels, [""] * len(changes), "rules")


def _unique_sections(changes: list[Change]) -> list[str]:
    seen: list[str] = []
    for c in changes:
        name = c.heading.split(" > ")[-1] if c.heading else ""
        if name and name not in seen:
            seen.append(name)
    return seen


SYSTEM_PROMPT = """You review changes between two editions of an Israeli government \
financial regulation ("הוראת תכ"ם"). Readers are ministry accountants and procurement staff \
who need to know quickly whether anything they must do differently has changed.

For each numbered change decide:
- "substantive": changes a rule, amount, threshold, deadline, duty, permission, \
responsible role, procedure or referenced system/term in a way that affects how people act.
- "wording": same meaning, only phrasing, grammar or style changed.
When unsure, choose "substantive".

Write in Hebrew. "summary" is 1-2 short sentences describing only the substantive changes \
in plain language (or saying there are only wording changes). "explanation" is one short \
Hebrew sentence per change."""


class ClaudeAnalyzer:
    def __init__(self, api_key: str, model: str, fallback: ChangeAnalyzer | None = None,
                 client=None):
        self.model = model
        self.fallback = fallback or RuleBasedAnalyzer()
        if client is not None:
            self.client = client
        else:
            import anthropic  # imported lazily so the no-AI mode needs no SDK setup
            self.client = anthropic.Anthropic(api_key=api_key)

    def analyze(self, instruction_name: str, diff: DiffResult) -> Analysis:
        content = [c for c in diff.changes if c.kind != ChangeKind.MOVED]
        if not content:  # nothing to ask the model about (no changes, or only moves)
            return self.fallback.analyze(instruction_name, diff)
        try:
            return self._call_model(instruction_name, diff)
        except Exception as e:  # network, auth, rate limit, refusal, bad output...
            log.warning("AI analysis failed for %s, using rule-based fallback: %s",
                        instruction_name, e)
            result = self.fallback.analyze(instruction_name, diff)
            result.analyzer = "rules (AI fallback)"
            return result

    def _call_model(self, instruction_name: str, diff: DiffResult) -> Analysis:
        # Moved-but-unchanged paragraphs are not sent: there is nothing to interpret.
        content = [c for c in diff.changes if c.kind != ChangeKind.MOVED]
        n = len(content)
        schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "changes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer"},
                            "classification": {"type": "string", "enum": ["substantive", "wording"]},
                            "explanation": {"type": "string"},
                        },
                        "required": ["index", "classification", "explanation"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["summary", "changes"],
            "additionalProperties": False,
        }
        response = self.client.messages.create(
            model=self.model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _render_changes(instruction_name, content)}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("model declined the request")
        text = next(b.text for b in response.content if b.type == "text")
        data = json.loads(text)

        by_index = {item["index"]: item for item in data["changes"]}
        classifications, explanations = [], []
        i = 0
        for change in diff.changes:   # map answers back, keeping the original order
            if change.kind == ChangeKind.MOVED:
                classifications.append(Classification.MOVED)
                explanations.append("")
                continue
            i += 1
            item = by_index.get(i)
            if item is None:  # model skipped one: be conservative
                classifications.append(Classification.SUBSTANTIVE)
                explanations.append("")
            else:
                classifications.append(Classification(item["classification"]))
                explanations.append(item["explanation"])
        return Analysis(data["summary"], classifications, explanations, f"ai:{self.model}")


def _render_changes(instruction_name: str, changes: list[Change]) -> str:
    lines = [f"הוראה: {instruction_name}", ""]
    for i, c in enumerate(changes, 1):
        lines.append(f"[{i}] סוג: {c.kind.value} | מיקום: {c.heading or '-'}")
        if c.old_text:
            lines.append(f"לפני: {c.old_text}")
        if c.new_text:
            lines.append(f"אחרי: {c.new_text}")
        lines.append("")
    return "\n".join(lines)


def build_analyzer(provider: str, api_key: str, model: str) -> ChangeAnalyzer:
    if provider == "anthropic":
        if not api_key:
            log.warning("AI_PROVIDER=anthropic but ANTHROPIC_API_KEY is empty; using rule-based mode")
            return RuleBasedAnalyzer()
        return ClaudeAnalyzer(api_key=api_key, model=model)
    return RuleBasedAnalyzer()
