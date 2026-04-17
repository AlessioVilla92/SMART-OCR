import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'

export default function Home() {
  const nav = useNavigate()
  const [health, setHealth] = useState<any>(null)

  useEffect(() => { api.health().then(setHealth).catch(() => {}) }, [])

  return (
    <div className="min-h-screen p-4 max-w-lg mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6 pt-2">
        <div>
          <h1 className="text-2xl font-extrabold gradient-text">Smart OCR</h1>
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>CBCL 6-18 v6.0</p>
        </div>
        <button onClick={() => { api.logout(); nav('/login') }}
          className="p-2.5 rounded-xl" style={{ color: 'var(--text-muted)' }}>
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
        </button>
      </div>

      {/* Status */}
      {health && (
        <div className="grid grid-cols-2 gap-3 mb-6">
          {[
            { label: 'SVM', ok: health.models?.svm },
            { label: 'YOLO', ok: health.models?.yolo_onnx },
          ].map(m => (
            <div key={m.label} className="glass p-4">
              <div className="flex items-center gap-2 mb-1">
                <div className={`w-2.5 h-2.5 rounded-full ${m.ok ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]' : 'bg-red-500'}`} />
                <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>{m.label}</span>
              </div>
              <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{m.ok ? 'Attivo' : 'N/D'}</p>
            </div>
          ))}
        </div>
      )}

      {/* Main CTA */}
      <button onClick={() => nav('/capture')}
        className="w-full rounded-2xl p-8 text-center transition-all duration-300 hover:-translate-y-1"
        style={{ background: 'var(--gradient-btn)', boxShadow: '0 8px 32px rgba(79, 70, 229, 0.3)' }}>
        <svg className="w-16 h-16 mx-auto mb-4 text-white/80" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
        <p className="text-xl font-bold text-white">Nuova Analisi</p>
        <p className="text-white/60 text-sm mt-1">Fotografa le 3 pagine del questionario</p>
      </button>

      {/* Instructions */}
      <div className="glass p-5 mt-6">
        <h3 className="font-semibold text-sm mb-3" style={{ color: 'var(--text-primary)' }}>Come funziona</h3>
        <div className="space-y-3">
          {['Fotografa o carica le 3 pagine CBCL', 'Analisi automatica delle risposte', 'Visualizza, correggi ed esporta'].map((t, i) => (
            <div key={i} className="flex gap-3 items-start">
              <span className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
                style={{ background: 'rgba(124,58,237,0.2)', color: 'var(--accent-light)' }}>{i + 1}</span>
              <span className="text-sm">{t}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
