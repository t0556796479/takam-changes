import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { countsText, formatDate } from '../format.js'
import { DEFAULT_DAYS_BACK, saveSince, sessionSince, visitorId } from '../visitor.js'
import Status from '../components/Status.jsx'

// Main screen: latest updates, newest first. The chosen topics (main chapters)
// filter the list and are saved for the visitor; updates since the last visit are marked.
export default function Feed() {
  const [chapters, setChapters] = useState([])
  const [selected, setSelected] = useState(null)   // null until the visitor's choice loads
  const [visit, setVisit] = useState(null)
  const [onlyNew, setOnlyNew] = useState(false)
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    const id = visitorId()
    Promise.all([api.chapters(), api.visitor(id), sessionSince(api)])
      .then(([chs, visitor, v]) => {
        setChapters(chs)
        setSelected(visitor.chapters)
        setVisit(v)
      })
      .catch(setError)
  }, [])

  useEffect(() => {
    if (selected === null || !visit) return
    setItems(null)
    api.changes({ chapters: selected, since: visit.since }).then(setItems).catch(setError)
  }, [selected, visit])

  function toggleChapter(number) {
    const next = selected.includes(number)
      ? selected.filter((c) => c !== number)
      : [...selected, number].sort((a, b) => a - b)
    setSelected(next)
    api.setSubscriptions(visitorId(), next).catch(setError)
  }

  function changeSince(since) {
    const v = { ...visit, since }
    setVisit(v)
    saveSince(v)
  }

  if (error) return <Status error={error} />
  if (selected === null || !visit) return <Status />

  const shown = items && (onlyNew ? items.filter((i) => i.is_new) : items)
  const newCount = items ? items.filter((i) => i.is_new).length : 0

  return (
    <>
      <section className="panel">
        <div className="filter-row">
          <strong>הנושאים שלי:</strong>
          {chapters.map((c) => (
            <button key={c.number} type="button"
              className={`chip ${selected.includes(c.number) ? 'chip-on' : ''}`}
              aria-pressed={selected.includes(c.number)}
              onClick={() => toggleChapter(c.number)}>
              {c.number} · {c.name}
            </button>
          ))}
          {selected.length === 0 && <span className="muted">(לא נבחרו נושאים, מוצגים כולם)</span>}
        </div>
        <div className="filter-row">
          <label>
            {visit.firstVisit ? `ביקור ראשון: מוצגים כחדשים עדכונים מ-${DEFAULT_DAYS_BACK} הימים האחרונים, מ-` : 'חדש מאז הביקור הקודם שלך, '}
            <input type="date" value={visit.since} onChange={(e) => changeSince(e.target.value)} />
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={onlyNew} onChange={(e) => setOnlyNew(e.target.checked)} />
            רק חדשים ({newCount})
          </label>
        </div>
      </section>

      {!shown ? <Status /> : shown.length === 0 ? (
        <p className="empty">{onlyNew ? 'אין עדכונים חדשים מאז התאריך שנבחר.' : 'אין עדכונים בנושאים שנבחרו.'}</p>
      ) : (
        <ul className="feed">
          {shown.map((i) => (
            <li key={`${i.instruction_code}-${i.to_version}`} className={`card ${i.is_new ? 'card-new' : ''}`}>
              <Link to={`/instructions/${i.instruction_code}?v=${i.to_version}`} className="card-link">
                <div className="card-head">
                  {i.is_new && <span className="badge">חדש</span>}
                  <span className="code">{i.instruction_code}</span>
                  <span className="title">{i.instruction_name}</span>
                </div>
                <div className="meta">
                  {i.main_chapter_name} · מהדורה {i.from_version} ← {i.to_version} · בתוקף מ-{formatDate(i.published_at)}
                </div>
                <p className="summary">{i.summary}</p>
                <div className="counts">{countsText(i.counts)}</div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
