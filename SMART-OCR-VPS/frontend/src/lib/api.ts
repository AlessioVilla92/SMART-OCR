const BASE = '/cbcl/api/v1'

function getToken(): string | null {
  return localStorage.getItem('token')
}

async function request(path: string, opts: RequestInit = {}) {
  const token = getToken()
  const headers: Record<string, string> = { ...(opts.headers as Record<string, string> || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (!(opts.body instanceof FormData)) headers['Content-Type'] = 'application/json'

  const res = await fetch(`${BASE}${path}`, { ...opts, headers })
  if (res.status === 401) {
    localStorage.removeItem('token')
    window.location.href = '/cbcl/login'
    throw new Error('Sessione scaduta')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `Errore ${res.status}`)
  }
  return res.json()
}

export const api = {
  health: () => request('/health'),

  login: async (username: string, password: string) => {
    const form = new URLSearchParams()
    form.append('username', username)
    form.append('password', password)
    const data = await fetch(`${BASE}/auth/login`, { method: 'POST', body: form })
      .then(r => { if (!r.ok) throw new Error('Credenziali non valide'); return r.json() })
    localStorage.setItem('token', data.access_token)
    return data
  },

  logout: () => { localStorage.removeItem('token') },
  isLoggedIn: () => !!getToken(),

  // Photos upload
  createJob: (form: FormData) => {
    const token = getToken()
    return fetch(`${BASE}/jobs`, {
      method: 'POST', body: form,
      headers: token ? { 'Authorization': `Bearer ${token}` } : {},
    }).then(r => { if (!r.ok) throw new Error('Upload fallito'); return r.json() })
  },

  // PDF extract pages (thumbnails)
  extractPdfPages: (file: File) => {
    const form = new FormData()
    form.append('pdf_file', file)
    const token = getToken()
    return fetch(`${BASE}/jobs/pdf-extract`, {
      method: 'POST', body: form,
      headers: token ? { 'Authorization': `Bearer ${token}` } : {},
    }).then(r => { if (!r.ok) throw new Error('Estrazione PDF fallita'); return r.json() })
  },

  // PDF direct analysis
  createPdfJob: (form: FormData) => {
    const token = getToken()
    return fetch(`${BASE}/jobs/pdf-analyze`, {
      method: 'POST', body: form,
      headers: token ? { 'Authorization': `Bearer ${token}` } : {},
    }).then(r => { if (!r.ok) throw new Error('Upload PDF fallito'); return r.json() })
  },

  jobStatus: (id: string) => request(`/jobs/${id}`),
  jobResults: (id: string) => request(`/jobs/${id}/results`),

  recompute: (items: Record<string, number>, age?: number, gender?: string, compilatore = 'MD') =>
    request('/score/recompute', {
      method: 'POST',
      body: JSON.stringify({ items, age, gender, compilatore }),
    }),
}
