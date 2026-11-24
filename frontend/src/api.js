// Thin wrapper over the backend API. All paths are relative, so the Vite proxy
// (development) or a reverse proxy (production) decides where the API lives.
async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = new Error(res.status === 404 ? 'לא נמצא' : `שגיאת שרת (${res.status})`)
    err.status = res.status
    throw err
  }
  return res.json()
}

export const api = {
  chapters: () => request('/chapters'),
  changes: ({ chapters = [], since } = {}) => {
    const params = new URLSearchParams()
    chapters.forEach((c) => params.append('chapters', c))
    if (since) params.set('since', since)
    return request(`/changes?${params}`)
  },
  instruction: (code) => request(`/instructions/${encodeURIComponent(code)}`),
  changeSet: (code, toVersion) => request(`/instructions/${encodeURIComponent(code)}/changes/${toVersion}`),
  edition: (code, version) => request(`/instructions/${encodeURIComponent(code)}/editions/${version}`),
  visitor: (id) => request(`/visitors/${id}`),
  setSubscriptions: (id, chapters) =>
    request(`/visitors/${id}/subscriptions`, { method: 'PUT', body: JSON.stringify({ chapters }) }),
  recordVisit: (id) => request(`/visitors/${id}/visit`, { method: 'POST' }),
}
