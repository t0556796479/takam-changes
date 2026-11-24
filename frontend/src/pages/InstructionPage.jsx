import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api.js'
import { countsText, formatDate } from '../format.js'
import ChangeView from '../components/ChangeView.jsx'
import Status from '../components/Status.jsx'

// Changes are shown in document order and grouped under their heading;
// paragraphs that only moved are collected at the end, collapsed.
function groupByHeading(changes) {
  const groups = []
  for (const c of changes) {
    const last = groups[groups.length - 1]
    if (last && last.heading === c.heading) last.changes.push(c)
    else groups.push({ heading: c.heading, changes: [c] })
  }
  return groups
}

export default function InstructionPage() {
  const { code } = useParams()
  const [params, setParams] = useSearchParams()
  const [inst, setInst] = useState(null)
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setInst(null)
    api.instruction(code).then(setInst).catch(setError)
  }, [code])

  const latest = inst?.change_sets[0]?.to_version
  const toVersion = Number(params.get('v')) || latest

  useEffect(() => {
    if (!inst || !toVersion) return
    setDetail(null)
    api.changeSet(code, toVersion).then(setDetail).catch(setError)
  }, [inst, code, toVersion])

  if (error) return <Status error={error} />
  if (!inst) return <Status />

  const lastEdition = inst.editions[inst.editions.length - 1]
  const content = detail ? detail.changes.filter((c) => c.kind !== 'moved') : []
  const moved = detail ? detail.changes.filter((c) => c.kind === 'moved') : []

  return (
    <>
      <Link to="/" className="back">→ חזרה לעדכונים</Link>
      <h1><span className="code">{inst.code}</span> {inst.name}</h1>
      <div className="meta">
        {inst.main_chapter_name} · {inst.sub_chapter_name} ·{' '}
        <a href={inst.source_url} target="_blank" rel="noreferrer">ההוראה באתר הוראות תכ"ם</a>
      </div>

      <section className="panel filter-row">
        <strong>קריאת ההוראה בדפדפן:</strong>
        {inst.editions.map((e) => (
          <Link key={e.version} className="chip" to={`/instructions/${inst.code}/editions/${e.version}`}>
            מהדורה {e.version}{e.version === lastEdition.version ? ' (עדכנית)' : ''}
          </Link>
        ))}
      </section>

      {inst.change_sets.length === 0 ? (
        <p className="empty">להוראה זו יש מהדורה אחת בלבד, אין מול מה להשוות.</p>
      ) : (
        <>
          {inst.change_sets.length > 1 && (
            <label className="panel filter-row">
              השוואה:
              <select value={toVersion} onChange={(e) => setParams({ v: e.target.value })}>
                {inst.change_sets.map((cs) => (
                  <option key={cs.to_version} value={cs.to_version}>
                    מהדורה {cs.from_version} ← {cs.to_version}
                  </option>
                ))}
              </select>
            </label>
          )}
          {!detail ? <Status /> : (
            <>
              <section className="panel">
                <h2>מהדורה {detail.from_version} ← {detail.to_version}, בתוקף מ-{formatDate(detail.published_at)}</h2>
                <p className="summary">{detail.summary}</p>
                <div className="counts">{countsText(detail.counts)}</div>
                {detail.cosmetic_only_count > 0 && (
                  <div className="muted">
                    עוד {detail.cosmetic_only_count} פסקאות השתנו רק בפיסוק או ברווחים ולא מוצגות.
                  </div>
                )}
                <div className="legend">מקרא: <del>טקסט שנמחק</del> <ins>טקסט שנוסף</ins></div>
              </section>

              {content.length === 0 && <p className="empty">לא נמצאו שינויים בתוכן בין המהדורות.</p>}
              {groupByHeading(content).map((g, i) => (
                <section key={i} className="group">
                  <h3>{g.heading || 'ללא כותרת'}</h3>
                  {g.changes.map((c, j) => <ChangeView key={j} change={c} />)}
                </section>
              ))}

              {moved.length > 0 && (
                <details className="group moved-group">
                  <summary>{moved.length} פסקאות הועברו למקום אחר ללא שינוי בתוכן</summary>
                  {moved.map((c, j) => <ChangeView key={j} change={c} />)}
                </details>
              )}
            </>
          )}
        </>
      )}
    </>
  )
}
