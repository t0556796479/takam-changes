// Anonymous visitor: a random id kept in the browser, no login and no personal details.
const ID_KEY = 'takam.visitorId'
const SINCE_KEY = 'takam.since'   // per browser tab, so a refresh keeps the "new" marks

export function visitorId() {
  let id = localStorage.getItem(ID_KEY)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(ID_KEY, id)
  }
  return id
}

export const DEFAULT_DAYS_BACK = 30

export function daysAgo(days) {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString().slice(0, 10)
}

// On the first load in this tab: record the visit and remember the previous one.
// Returns { since: 'YYYY-MM-DD', firstVisit } - updates published after `since` count as new.
export async function sessionSince(api) {
  const saved = sessionStorage.getItem(SINCE_KEY)
  if (saved) return JSON.parse(saved)
  const { previous_visit_at } = await api.recordVisit(visitorId())
  const value = previous_visit_at
    ? { since: previous_visit_at.slice(0, 10), firstVisit: false }
    : { since: daysAgo(DEFAULT_DAYS_BACK), firstVisit: true }
  sessionStorage.setItem(SINCE_KEY, JSON.stringify(value))
  return value
}

export function saveSince(value) {
  sessionStorage.setItem(SINCE_KEY, JSON.stringify(value))
}
