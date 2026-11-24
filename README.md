# takam-changes

> טיוטה. ה-README המלא ייכתב בסוף הפרויקט.

## הרצה מקומית (שרת)

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy ..\.env.example ..\.env

python -m app.pipeline    # מעבד את data/ ושומר למסד הנתונים
python -m app.show        # מציג תמצית לכל ההוראות
python -m app.show 7.3.3  # פירוט השינויים בהוראה אחת
pytest                    # בדיקות
```

ברירת המחדל היא מצב "בלי AI" (`AI_PROVIDER=none`). כדי להפעיל את Claude, מגדירים ב-`.env` את `AI_PROVIDER=anthropic` ואת `ANTHROPIC_API_KEY`.

## מבנה

- `data/`: מדגם ההוראות (ראו `data/SAMPLE.md`) וקובץ הפרטים `instructions.json`.
- `backend/app/core/`: חילוץ טקסט מ-Word, נרמול והשוואה בין מהדורות.
- `backend/app/ai/`: סיווג שינויים (מהותי או ניסוחי) ותמצית, עם Claude או בלי AI.
- `backend/app/pipeline.py`: מריץ את כל התהליך ושומר במסד הנתונים.
