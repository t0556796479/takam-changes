import json
from types import SimpleNamespace

from app.ai.analyzer import (Classification, ClaudeAnalyzer, RuleBasedAnalyzer,
                             build_analyzer, NO_CHANGES_SUMMARY)
from app.core.diff import Change, ChangeKind, DiffResult


def diff_with(n=2):
    changes = [Change(ChangeKind.MODIFIED, "פרק > חניה", "ישן", "חדש") for _ in range(n)]
    return DiffResult(changes=changes, cosmetic_only_count=0)


class FakeClient:
    """Stands in for anthropic.Anthropic so tests never call the network."""

    def __init__(self, payload=None, error=None, stop_reason="end_turn"):
        self.payload, self.error, self.stop_reason = payload, error, stop_reason
        self.messages = self
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        block = SimpleNamespace(type="text", text=json.dumps(self.payload, ensure_ascii=False))
        return SimpleNamespace(stop_reason=self.stop_reason, content=[block])


def test_rule_based_summary_and_labels():
    a = RuleBasedAnalyzer().analyze("הוראה", diff_with(2))
    assert "2 סעיפים שונו" in a.summary and "חניה" in a.summary
    assert a.classifications == [Classification.UNCLASSIFIED] * 2


def test_rule_based_no_changes():
    a = RuleBasedAnalyzer().analyze("הוראה", DiffResult([], cosmetic_only_count=3))
    assert a.summary.startswith(NO_CHANGES_SUMMARY) and a.classifications == []


def test_claude_result_is_mapped_by_index():
    payload = {"summary": "שונה מונח.", "changes": [
        {"index": 2, "classification": "wording", "explanation": "ניסוח"},
        {"index": 1, "classification": "substantive", "explanation": "מונח חדש"}]}
    a = ClaudeAnalyzer("k", "m", client=FakeClient(payload)).analyze("הוראה", diff_with(2))
    assert a.classifications == [Classification.SUBSTANTIVE, Classification.WORDING]
    assert a.summary == "שונה מונח." and a.analyzer == "ai:m"


def test_missing_item_defaults_to_substantive():
    payload = {"summary": "x", "changes": [{"index": 1, "classification": "wording", "explanation": ""}]}
    a = ClaudeAnalyzer("k", "m", client=FakeClient(payload)).analyze("הוראה", diff_with(2))
    assert a.classifications[1] == Classification.SUBSTANTIVE


def test_api_error_falls_back_to_rules():
    a = ClaudeAnalyzer("k", "m", client=FakeClient(error=ConnectionError("down"))).analyze("הוראה", diff_with(1))
    assert a.analyzer == "rules (AI fallback)"
    assert a.classifications == [Classification.UNCLASSIFIED]


def test_refusal_falls_back_to_rules():
    client = FakeClient({"summary": "", "changes": []}, stop_reason="refusal")
    assert ClaudeAnalyzer("k", "m", client=client).analyze("ה", diff_with(1)).analyzer == "rules (AI fallback)"


def test_no_changes_does_not_call_the_model():
    client = FakeClient({"summary": "", "changes": []})
    ClaudeAnalyzer("k", "m", client=client).analyze("ה", DiffResult([], 0))
    assert client.calls == 0


def test_build_analyzer_without_key_uses_rules():
    assert isinstance(build_analyzer("anthropic", "", "m"), RuleBasedAnalyzer)
    assert isinstance(build_analyzer("none", "key", "m"), RuleBasedAnalyzer)
