import { useState, useEffect } from 'react'
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { api } from './lib/api'
import Login from './pages/Login'
import Capture from './pages/Capture'
import Analysis from './pages/Analysis'
import Results from './pages/Results'
import CbclForm from './pages/CbclForm'
import './App.css'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  if (!api.isLoggedIn()) return <Navigate to="/login" replace />
  return <>{children}</>
}

/** Sidebar — identical to Smart OCR desktop */
function Sidebar({ health, mode, setMode, debug, setDebug, onClose, isOpen }: any) {
  const nav = useNavigate()
  const loc = useLocation()

  return (
    <div className={`sidebar ${isOpen ? 'open' : ''}`}>
      {/* Logo */}
      <div style={{ textAlign: 'center', padding: '8px 0' }}>
        <span style={{ fontSize: '2rem' }}>🧾</span>
        <h2 className="gradient-text" style={{ fontSize: '1.1rem', fontWeight: 700, margin: '4px 0 0' }}>Smart OCR</h2>
      </div>
      <hr className="sep" />

      {/* Navigation — identical to Smart OCR desktop sidebar */}
      <button className={`nav-item ${loc.pathname === '/capture' || loc.pathname === '/' ? 'active' : ''}`}
        onClick={() => { nav('/capture'); onClose?.() }}>📤 Analisi</button>
      <button className={`nav-item ${loc.pathname.startsWith('/form') ? 'active' : ''}`}
        onClick={() => { nav('/form'); onClose?.() }}
        style={!_analysisData ? { opacity: 0.4 } : {}}>
        📝 Questionario
      </button>
      <button className={`nav-item ${loc.pathname.startsWith('/results') ? 'active' : ''}`}
        onClick={() => { if (_lastJobId) { nav(`/results/${_lastJobId}`); onClose?.() } }}
        style={!_lastJobId ? { opacity: 0.4 } : {}}>
        📊 Risultati
      </button>

      <hr className="sep" />

      {/* Settings */}
      <div className="label" style={{ padding: '0 14px', marginBottom: 8 }}>Impostazioni</div>
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 14px', fontSize: '0.85rem', color: 'var(--text-4)', cursor: 'pointer' }}>
        <input type="checkbox" checked={debug} onChange={e => setDebug(e.target.checked)}
          style={{ accentColor: 'var(--accent)' }} />
        Modalita debug
      </label>

      <hr className="sep" />

      {/* Mode selector */}
      <div className="label" style={{ padding: '0 14px', marginBottom: 8 }}>Modalita Riconoscimento</div>
      {[
        { v: 'ensemble', l: 'C — Ensemble (SVM+YOLO+TTA)' },
        { v: 'svm', l: 'A — Classico (HOG + SVM)' },
        { v: 'yolo', l: 'B — AI (YOLOv8n ONNX)' },
      ].map(m => (
        <label key={m.v} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 14px', fontSize: '0.8rem', color: mode === m.v ? 'var(--text-1)' : 'var(--text-4)', cursor: 'pointer' }}>
          <input type="radio" name="mode" value={m.v} checked={mode === m.v}
            onChange={() => setMode(m.v)} style={{ accentColor: 'var(--accent)' }} />
          {m.l}
        </label>
      ))}

      <hr className="sep" />

      {/* System status */}
      <div className="label" style={{ padding: '0 14px', marginBottom: 8 }}>Stato sistema</div>
      <div style={{ padding: '0 14px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {health ? (
          <>
            <span className={`pill ${health.models?.svm ? 'pill-ok' : 'pill-warn'}`}>
              🧠 SVM {health.models?.svm ? 'disponibile' : 'non trovato'}
            </span>
            <span className={`pill ${health.models?.yolo_onnx ? 'pill-ok' : 'pill-info'}`}>
              🤖 YOLO {health.models?.yolo_onnx ? 'disponibile' : 'non trovato'}
            </span>
            <span className={`pill ${health.templates?.grid ? 'pill-ok' : 'pill-warn'}`}>
              📐 Griglia {health.templates?.grid ? 'calibrata' : 'non calibrata'}
            </span>
          </>
        ) : <span className="pill pill-warn">Connessione...</span>}
      </div>

      {/* Spacer + footer */}
      <div style={{ flex: 1 }} />
      <hr className="sep" />
      <div style={{ textAlign: 'center', padding: '8px 0' }}>
        <button className="nav-item" style={{ justifyContent: 'center', color: '#EF4444' }}
          onClick={() => { api.logout(); nav('/login'); onClose?.() }}>
          ↪ Esci
        </button>
      </div>
      <p style={{ textAlign: 'center', fontSize: '0.65rem', color: 'var(--text-5)' }}>
        Smart OCR v6.0<br />CBCL 6-18 Scanner
      </p>
    </div>
  )
}

// Global analysis state — shared between pages, persisted in sessionStorage
function loadAnalysis() {
  try { const s = sessionStorage.getItem('smartocr_analysis'); return s ? JSON.parse(s) : null } catch { return null }
}
function saveAnalysis(d: any) {
  try { sessionStorage.setItem('smartocr_analysis', JSON.stringify(d)) } catch {}
}

let _analysisData: any = loadAnalysis()
let _lastJobId: string | null = sessionStorage.getItem('smartocr_last_job') || null
export function setAnalysisData(d: any) { _analysisData = d; saveAnalysis(d) }
export function getAnalysisData() { return _analysisData }
export function setLastJobId(id: string) { _lastJobId = id; sessionStorage.setItem('smartocr_last_job', id) }
export function getLastJobId() { return _lastJobId }

function BottomTabs({ sidebarOpen, setSidebarOpen }: { sidebarOpen: boolean; setSidebarOpen: (v: boolean) => void }) {
  const nav = useNavigate()
  const loc = useLocation()
  const tabs = [
    { path: '/capture', icon: '📤', label: 'Analisi' },
    { path: '/form', icon: '📝', label: 'Form' },
    { path: _lastJobId ? `/results/${_lastJobId}` : '', icon: '📊', label: 'Risultati', disabled: !_lastJobId },
  ]
  return (
    <div className="bottom-tabs">
      <div className="bottom-tabs-inner">
        {tabs.map(t => (
          <button key={t.label}
            className={`bottom-tab ${loc.pathname.includes(t.path.split('/')[1]) ? 'active' : ''}`}
            style={t.disabled ? { opacity: 0.35 } : {}}
            onClick={() => { if (!t.disabled && t.path) nav(t.path) }}>
            <span className="tab-icon">{t.icon}</span>
            {t.label}
          </button>
        ))}
        <button className={`bottom-tab ${sidebarOpen ? 'active' : ''}`}
          onClick={() => setSidebarOpen(!sidebarOpen)}>
          <span className="tab-icon">⚙️</span>
          Menu
        </button>
      </div>
    </div>
  )
}

export default function App() {
  const [health, setHealth] = useState<any>(null)
  const [mode, setMode] = useState('ensemble')
  const [debug, setDebug] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [, forceUpdate] = useState(0)

  useEffect(() => {
    if (api.isLoggedIn()) api.health().then(setHealth).catch(() => {})
  }, [])

  return (
    <Routes>
      <Route path="/login" element={<Login onLogin={() => api.health().then(setHealth)} />} />
      <Route path="/*" element={
        <ProtectedRoute>
          <div className="app-layout">
            {/* Mobile header */}
            <div className="mobile-header" style={{ position: 'fixed', top: 0, left: 0, right: 0, zIndex: 30, padding: '12px 16px', background: 'rgba(7,11,20,0.95)', backdropFilter: 'blur(12px)', borderBottom: '1px solid var(--border)', display: 'none', alignItems: 'center', justifyContent: 'space-between' }}>
              <button onClick={() => setSidebarOpen(!sidebarOpen)} style={{ background: 'none', border: 'none', color: 'var(--text-3)', fontSize: '1.2rem', cursor: 'pointer' }}>☰</button>
              <span className="gradient-text" style={{ fontWeight: 700 }}>Smart OCR</span>
              <span style={{ width: 28 }} />
            </div>
            {/* Sidebar overlay (mobile) */}
            {sidebarOpen && <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />}
            {/* Sidebar — always rendered, visibility controlled by CSS + open class */}
            <Sidebar health={health} mode={mode} setMode={setMode} debug={debug} setDebug={setDebug} onClose={() => setSidebarOpen(false)} isOpen={sidebarOpen} />
            {/* Bottom Tab Bar (mobile only) */}
            <BottomTabs sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />

            {/* Main */}
            <div className="main-content">
              <div className="md:hidden" style={{ height: 48 }} /> {/* spacer for mobile header */}
              <Routes>
                <Route path="/" element={<Navigate to="/capture" replace />} />
                <Route path="/capture" element={<Capture mode={mode} debug={debug} health={health} />} />
                <Route path="/analysis/:jobId" element={<Analysis />} />
                <Route path="/form" element={
                  <CbclForm data={_analysisData} onUpdate={(updatedItems) => {
                    if (_analysisData) {
                      _analysisData = { ..._analysisData, items: updatedItems }
                      forceUpdate(n => n + 1)
                      // Recompute scores
                      const vals: Record<string, number> = {}
                      for (const [k, v] of Object.entries(updatedItems) as any) {
                        if (v.value != null) vals[k] = v.value
                      }
                      api.recompute(vals).then(r => {
                        _analysisData = { ..._analysisData, ...r }
                        forceUpdate(n => n + 1)
                      }).catch(() => {})
                    }
                  }} />
                } />
                <Route path="/results/:jobId" element={<Results />} />
              </Routes>
            </div>
          </div>
        </ProtectedRoute>
      } />
    </Routes>
  )
}
