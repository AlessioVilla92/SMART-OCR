import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'

const PAGES = [
  { key: 'page_4', label: 'page_4 — Item 1-54' },
  { key: 'page_5', label: 'page_5 — Item 55-85' },
  { key: 'page_6', label: 'page_6 — Item 86-113' },
]

export default function Capture({ mode }: { mode: string; debug?: boolean; health?: any }) {
  const nav = useNavigate()
  const [tab, setTab] = useState<'photo' | 'pdf'>('photo')
  const [selectedPage, setSelectedPage] = useState('page_4')
  const [files, setFiles] = useState<Record<string, File | null>>({ page_4: null, page_5: null, page_6: null })
  const [previews, setPreviews] = useState<Record<string, string | null>>({ page_4: null, page_5: null, page_6: null })
  const [compilatore, setCompilatore] = useState('MD')
  const [sex, setSex] = useState('M')
  const [age, setAge] = useState(10)
  const [uploading, setUploading] = useState(false)
  const [statusMsg, setStatusMsg] = useState('')
  const [pdfFile, setPdfFile] = useState<File | null>(null)
  const [pdfPages, setPdfPages] = useState<any[]>([])
  const [pdfLoading, setPdfLoading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const pdfRef = useRef<HTMLInputElement>(null)

  const handleFileSelect = (file: File) => {
    setFiles(f => ({ ...f, [selectedPage]: file }))
    setPreviews(p => ({ ...p, [selectedPage]: URL.createObjectURL(file) }))
  }

  const allReady = files.page_4 && files.page_5 && files.page_6

  const handleAnalyze = async () => {
    if (!allReady) return
    setUploading(true); setStatusMsg('Caricamento foto...')
    try {
      const form = new FormData()
      form.append('page_4', files.page_4!)
      form.append('page_5', files.page_5!)
      form.append('page_6', files.page_6!)
      form.append('mode', mode)
      form.append('compilatore', compilatore)
      form.append('sex', sex)
      form.append('age', String(age))
      const res = await api.createJob(form)
      nav(`/analysis/${res.job_id}`)
    } catch (e: any) { setStatusMsg(`❌ Errore: ${e.message}`) }
    finally { setUploading(false) }
  }

  const handlePdfSelect = async (file: File) => {
    setPdfFile(file); setPdfLoading(true)
    try {
      const d = await api.extractPdfPages(file)
      setPdfPages(d.pages || [])
    } catch (e: any) { alert(e.message) }
    finally { setPdfLoading(false) }
  }

  const handlePdfAnalyze = async () => {
    if (!pdfFile) return
    setUploading(true); setStatusMsg('Caricamento PDF...')
    try {
      const form = new FormData()
      form.append('pdf_file', pdfFile)
      form.append('mode', mode)
      form.append('compilatore', compilatore)
      form.append('sex', sex)
      form.append('age', String(age))
      const res = await api.createPdfJob(form)
      nav(`/analysis/${res.job_id}`)
    } catch (e: any) { setStatusMsg(`❌ Errore: ${e.message}`) }
    finally { setUploading(false) }
  }

  const methodLabel = mode === 'svm' ? 'HOG + SVM — Mode A' : mode === 'yolo' ? 'YOLOv8n ONNX — Mode B' : 'Ensemble SVM + YOLO + TTA — Mode C'

  return (
    <div>
      {/* Header */}
      <h1 className="gradient-text h1">Smart OCR</h1>
      <p style={{ color: 'var(--text-4)', marginBottom: 20 }}>Lettura automatica questionari CBCL 6-18 da foto smartphone</p>

      {/* Tabs: Analisi */}
      <div className="tab-bar" style={{ marginBottom: 20 }}>
        <button className={`tab ${tab === 'photo' ? 'active' : ''}`} onClick={() => setTab('photo')}>📤 Analisi Foto</button>
        <button className={`tab ${tab === 'pdf' ? 'active' : ''}`} onClick={() => setTab('pdf')}>📄 Analisi PDF</button>
      </div>

      {/* Demographics bar */}
      <div className="glass" style={{ padding: 16, marginBottom: 16, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12 }}>
        <div>
          <div className="label" style={{ marginBottom: 4 }}>Compilatore</div>
          <div style={{ display: 'flex', gap: 4 }}>
            {['MD', 'PD'].map(c => (
              <button key={c} className={`btn ${compilatore === c ? 'btn-primary' : 'btn-ghost'}`}
                style={{ padding: '6px 12px', fontSize: '0.8rem', flex: 1 }}
                onClick={() => setCompilatore(c)}>
                {c === 'MD' ? '👩 Madre' : '👨 Padre'}
              </button>
            ))}
          </div>
        </div>
        <div>
          <div className="label" style={{ marginBottom: 4 }}>Sesso</div>
          <div style={{ display: 'flex', gap: 4 }}>
            {['M', 'F'].map(s => (
              <button key={s} className={`btn ${sex === s ? 'btn-primary' : 'btn-ghost'}`}
                style={{ padding: '6px 12px', fontSize: '0.8rem', flex: 1 }}
                onClick={() => setSex(s)}>
                {s === 'M' ? 'Maschio' : 'Femmina'}
              </button>
            ))}
          </div>
        </div>
        <div>
          <div className="label" style={{ marginBottom: 4 }}>Eta (6-18)</div>
          <input type="number" min={6} max={18} value={age} onChange={e => setAge(+e.target.value)} className="input" style={{ textAlign: 'center' }} />
        </div>
      </div>

      {/* === PHOTO TAB === */}
      {tab === 'photo' && (
        <>
          <h2 className="h2">Carica foto questionario</h2>

          {/* Two-column layout (desktop) / stacked (mobile) */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 20 }}>
            {/* LEFT: Upload */}
            <div>
              <div className="label" style={{ marginBottom: 6 }}>Pagina del questionario</div>
              <select className="input" value={selectedPage} onChange={e => setSelectedPage(e.target.value)} style={{ marginBottom: 12 }}>
                {PAGES.map(p => <option key={p.key} value={p.key}>{p.label}</option>)}
              </select>

              {previews[selectedPage] ? (
                <div style={{ position: 'relative', borderRadius: 14, overflow: 'hidden', border: '1px solid var(--border)' }}>
                  <img src={previews[selectedPage]!} alt="" style={{ width: '100%', maxHeight: 400, objectFit: 'contain', background: 'rgba(0,0,0,0.3)' }} />
                  <button onClick={() => { setFiles(f => ({ ...f, [selectedPage]: null })); setPreviews(p => ({ ...p, [selectedPage]: null })) }}
                    style={{ position: 'absolute', top: 8, right: 8, width: 32, height: 32, borderRadius: '50%', background: 'rgba(0,0,0,0.6)', border: 'none', color: 'white', cursor: 'pointer', fontSize: 16 }}>✕</button>
                </div>
              ) : (
                <div className="upload-zone" onClick={() => inputRef.current?.click()}>
                  <span style={{ fontSize: 40, display: 'block', marginBottom: 8 }}>📷</span>
                  <p style={{ color: 'var(--text-1)', fontWeight: 600 }}>Foto del questionario CBCL compilato</p>
                  <p style={{ color: 'var(--text-5)', fontSize: '0.8rem', marginTop: 4 }}>Tocca per fotografare o selezionare</p>
                </div>
              )}
              <input ref={inputRef} type="file" accept="image/*" capture="environment" style={{ display: 'none' }}
                onChange={e => { if (e.target.files?.[0]) handleFileSelect(e.target.files[0]); e.target.value = '' }} />

              {/* Page status pills */}
              <div style={{ display: 'flex', gap: 6, marginTop: 12 }}>
                {PAGES.map(p => (
                  <span key={p.key} className={`pill ${files[p.key] ? 'pill-ok' : 'pill-warn'}`} style={{ cursor: 'pointer', flex: 1, textAlign: 'center' }}
                    onClick={() => setSelectedPage(p.key)}>
                    {files[p.key] ? '✅' : '⬜'} {p.key.replace('page_', 'P')}
                  </span>
                ))}
              </div>
            </div>

            {/* RIGHT: Controls */}
            <div>
              <div className="alert alert-info" style={{ marginBottom: 12 }}>
                Metodo: <strong>{methodLabel}</strong>
              </div>

              {!allReady && (
                <div className="alert alert-warning">
                  Carica tutte e 3 le pagine per avviare l'analisi
                </div>
              )}

              {allReady && !uploading && (
                <button className="btn btn-primary" style={{ padding: '14px 24px', fontSize: '1rem' }} onClick={handleAnalyze}>
                  🔍 Analizza Questionario
                </button>
              )}

              {uploading && (
                <div className="glass" style={{ padding: 16, textAlign: 'center' }}>
                  <div className="progress-bar" style={{ marginBottom: 8 }}>
                    <div className="progress-fill" style={{ width: '100%', animation: 'pulse 1.5s infinite' }} />
                  </div>
                  <p style={{ color: 'var(--text-4)', fontSize: '0.85rem' }}>{statusMsg}</p>
                </div>
              )}

              {statusMsg.includes('❌') && (
                <div className="alert alert-error">{statusMsg}</div>
              )}
            </div>
          </div>
        </>
      )}

      {/* === PDF TAB === */}
      {tab === 'pdf' && (
        <>
          <h2 className="h2">Carica PDF questionario</h2>
          <div className="upload-zone" onClick={() => pdfRef.current?.click()} style={{ marginBottom: 16 }}>
            <span style={{ fontSize: 40, display: 'block', marginBottom: 8 }}>📄</span>
            <p style={{ color: 'var(--text-1)', fontWeight: 600 }}>
              {pdfFile ? `📄 ${pdfFile.name}` : 'Seleziona PDF CBCL (3 pagine)'}
            </p>
            <p style={{ color: 'var(--text-5)', fontSize: '0.8rem', marginTop: 4 }}>Le pagine verranno assegnate automaticamente</p>
          </div>
          <input ref={pdfRef} type="file" accept=".pdf" style={{ display: 'none' }}
            onChange={e => { if (e.target.files?.[0]) handlePdfSelect(e.target.files[0]); e.target.value = '' }} />

          {pdfLoading && (
            <div style={{ textAlign: 'center', padding: 24 }}>
              <div style={{ width: 32, height: 32, margin: '0 auto', border: '2px solid var(--accent)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
              <p style={{ color: 'var(--text-5)', marginTop: 12, fontSize: '0.85rem' }}>Estrazione pagine...</p>
            </div>
          )}

          {pdfPages.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <p style={{ color: 'var(--text-1)', fontWeight: 600, marginBottom: 8, fontSize: '0.9rem' }}>
                {pdfPages.length} pagine trovate
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))', gap: 8 }}>
                {pdfPages.slice(0, 6).map((p: any) => (
                  <div key={p.index} className="glass" style={{ padding: 4 }}>
                    <img src={p.thumbnail} alt="" style={{ width: '100%', borderRadius: 8 }} />
                    <p style={{ textAlign: 'center', fontSize: '0.65rem', color: 'var(--text-5)', marginTop: 2 }}>Pag {p.index + 1}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {pdfFile && !pdfLoading && (
            <button className="btn btn-primary" style={{ padding: '14px 24px', fontSize: '1rem' }} disabled={uploading} onClick={handlePdfAnalyze}>
              {uploading ? '⏳ Analisi in corso...' : '🔍 Analizza PDF'}
            </button>
          )}
        </>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } } @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }`}</style>
    </div>
  )
}
