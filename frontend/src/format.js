export function formatDate(iso) {
  if (!iso) return 'תאריך לא ידוע'
  const [y, m, d] = iso.slice(0, 10).split('-')
  return `${d}/${m}/${y}`
}

export function countsText(counts) {
  const parts = []
  if (counts.modified) parts.push(`${counts.modified} שונו`)
  if (counts.added) parts.push(`${counts.added} נוספו`)
  if (counts.removed) parts.push(`${counts.removed} הוסרו`)
  if (counts.moved) parts.push(`${counts.moved} הועברו`)
  return parts.length ? parts.join(' · ') : 'ללא שינויי תוכן'
}
