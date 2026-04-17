import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'

export default function Login({ onLogin }: { onLogin?: () => void }) {
  const nav = useNavigate()
  const [user, setUser] = useState('')
  const [pass, setPass] = useState('')
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)

  const handle = async (e: React.FormEvent) => {
    e.preventDefault(); setLoading(true); setErr('')
    try {
      await api.login(user, pass)
      onLogin?.()
      nav('/capture')
    } catch (e: any) { setErr(e.message || 'Errore') }
    finally { setLoading(false) }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <form onSubmit={handle} style={{ width: '100%', maxWidth: 380 }}>
        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <div style={{ width: 72, height: 72, margin: '0 auto 16px', borderRadius: 18, background: 'var(--grad-btn)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ fontSize: 36 }}>🧾</span>
          </div>
          <h1 className="gradient-text h1">Smart OCR</h1>
          <p style={{ color: 'var(--text-5)', fontSize: '0.85rem', marginTop: 4 }}>CBCL 6-18 Scanner</p>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <input type="text" placeholder="Username" value={user} onChange={e => setUser(e.target.value)} className="input" autoComplete="username" required />
          <input type="password" placeholder="Password" value={pass} onChange={e => setPass(e.target.value)} className="input" autoComplete="current-password" required />
        </div>
        {err && <p style={{ color: '#F87171', fontSize: '0.85rem', textAlign: 'center', marginTop: 12 }}>{err}</p>}
        <button type="submit" disabled={loading} className="btn btn-primary" style={{ marginTop: 24, padding: '14px 24px', fontSize: '1rem' }}>
          {loading ? '⏳ Accesso...' : 'Accedi'}
        </button>
      </form>
    </div>
  )
}
