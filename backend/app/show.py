"""Print the processed changes of an instruction, for a quick check in the terminal.

Usage (from backend/):
    python -m app.show            # list all instructions and their summaries
    python -m app.show 7.3.3      # full details of one instruction

In the details, deleted words appear as [-...-] and inserted words as {+...+}.
"""
import sys

from app.db import SessionLocal
from app.models import Instruction

LABELS = {"substantive": "מהותי", "wording": "ניסוחי", "unclassified": "לא סווג", "moved": "הועבר"}


def _render(segments: list[dict]) -> str:
    out = []
    for s in segments:
        if s["op"] == "delete":
            out.append(f"[-{s['text']}-]")
        elif s["op"] == "insert":
            out.append(f"{{+{s['text']}+}}")
        else:
            out.append(s["text"])
    return " ".join(out)


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # Hebrew output on Windows terminals
    with SessionLocal() as session:
        query = session.query(Instruction).order_by(Instruction.main_chapter, Instruction.code)
        if not argv:
            for inst in query:
                print(f"{inst.code:8} {inst.name}")
                for cs in inst.change_sets:
                    print(f"         v{cs.from_version}->v{cs.to_version}: {cs.summary}")
                if not inst.change_sets:
                    print("         (מהדורה אחת בלבד, אין השוואה)")
            return 0

        inst = query.filter(Instruction.code == argv[0]).one_or_none()
        if inst is None:
            print(f"הוראה {argv[0]} לא נמצאה. הריצו קודם: python -m app.pipeline")
            return 1
        print(f"{inst.code} {inst.name}\n")
        for cs in inst.change_sets:
            print(f"=== מהדורה {cs.from_version} -> {cs.to_version} ({cs.analyzer}) ===")
            print(f"תמצית: {cs.summary}")
            if cs.cosmetic_only_count:
                print(f"(בנוסף {cs.cosmetic_only_count} שינויי פיסוק/עיצוב שסוננו)")
            moved = [c for c in cs.changes if c.kind == "moved"]
            for c in (c for c in cs.changes if c.kind != "moved"):
                print(f"\n- [{LABELS.get(c.classification, c.classification)}] {c.kind} | {c.heading}")
                if c.kind == "modified":
                    print("  " + _render(c.segments))
                else:
                    print("  " + (c.new_text or c.old_text or ""))
                if c.moved_from and c.moved_from != c.heading:
                    print(f"  (הועבר מ: {c.moved_from})")
                if c.explanation:
                    print(f"  הסבר: {c.explanation}")
            if moved:
                print(f"\n- {len(moved)} פסקאות הועברו ללא שינוי בתוכן:")
                for c in moved:
                    print(f"  {c.moved_from} -> {c.heading}: {(c.new_text or '')[:60]}...")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
