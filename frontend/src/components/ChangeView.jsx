// One change between editions. Word-level segments show exactly what was
// deleted (red, struck through) and inserted (green) inside a modified paragraph.
const LABELS = { modified: 'שונה', added: 'נוסף', removed: 'הוסר', moved: 'הועבר' }

function Segments({ segments }) {
  return segments.map((s, i) => {
    if (s.op === 'delete') return <del key={i}>{s.text}</del>
    if (s.op === 'insert') return <ins key={i}>{s.text}</ins>
    return <span key={i}>{s.text}</span>
  }).reduce((acc, el, i) => (i ? [...acc, ' ', el] : [el]), [])
}

export default function ChangeView({ change }) {
  const { kind } = change
  return (
    <div className={`change change-${kind}`}>
      <span className={`tag tag-${kind}`}>{LABELS[kind] || kind}</span>
      {change.moved_from && <span className="moved-from">הועבר מ: {change.moved_from}</span>}
      <p className="change-text">
        {kind === 'modified' && <Segments segments={change.segments} />}
        {kind === 'added' && <ins>{change.new_text}</ins>}
        {kind === 'removed' && <del>{change.old_text}</del>}
        {kind === 'moved' && change.new_text}
      </p>
    </div>
  )
}
