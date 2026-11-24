import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api.js'
import { formatDate } from '../format.js'
import Status from '../components/Status.jsx'

// Reading an edition in the browser, without downloading the Word file.
export default function EditionPage() {
  const { code, version } = useParams()
  const [edition, setEdition] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setEdition(null)
    api.edition(code, version).then(setEdition).catch(setError)
  }, [code, version])

  if (error) return <Status error={error} />
  if (!edition) return <Status />

  return (
    <>
      <Link to={`/instructions/${code}`} className="back">→ חזרה להוראה {code}</Link>
      <h1>הוראה {code}, מהדורה {edition.version}</h1>
      {edition.valid_from && <div className="meta">בתוקף מ-{formatDate(edition.valid_from)}</div>}
      <p className="muted">טבלאות מהמסמך המקורי אינן מוצגות בגרסה זו.</p>
      <article className="document">
        {edition.blocks.map((b, i) =>
          b.is_heading ? <h3 key={i}>{b.text}</h3> : <p key={i}>{b.text}</p>)}
      </article>
    </>
  )
}
