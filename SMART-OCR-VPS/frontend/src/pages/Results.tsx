import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../lib/api'
import { setAnalysisData, setLastJobId, saveProject } from '../App'

const FLAG_EMOJI: Record<string, string> = { '': '✅', ok: '✅', missing: '❌', ambiguous: '⚠️', multiple_marks: '🔴', not_processed: '⬜', low_confidence: '⚠️' }
const FLAG_CLASS: Record<string, string> = { missing: 'flag-missing', ambiguous: 'flag-ambiguous', multiple_marks: 'flag-multiple' }
const HIDDEN_ITEMS = new Set(['113b', '113c'])
const DISPLAY_ID: Record<string, string> = { '113a': '113' }

type Tab = 'results' | 'export'

export default function Results() {
  const { jobId } = useParams<{ jobId: string }>()
  useNavigate() // keep router context
  const [data, setData] = useState<any>(null)
  const [tab, setTab] = useState<Tab>('results')
  const [loading, setLoading] = useState(true)
  const [editItem, setEditItem] = useState<string | null>(null)
  const [pdfLoading, setPdfLoading] = useState(false)

  useEffect(() => {
    setLastJobId(jobId!)
    // Check if we have locally edited data (from CbclForm edits) for THIS job
    const saved = sessionStorage.getItem('smartocr_analysis')
    const localData = saved ? JSON.parse(saved) : null
    const localMatchesJob = localData && localData._editedByForm && localData.job_id === jobId
    if (localMatchesJob) {
      // Use locally edited data — user has made manual corrections to this job
      setData(localData)
      setLoading(false)
    } else {
      // No local edits — fetch fresh from API
      api.jobResults(jobId!).then(d => {
        const fresh = { ...d, job_id: jobId }
        setData(fresh)
        setAnalysisData(fresh) // share with form page
      }).catch(e => {
        if (localData) {
          setData(localData)
        } else {
          alert(e.message)
        }
      }).finally(() => setLoading(false))
    }
  }, [jobId])

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 100 }}><div style={{ width: 32, height: 32, border: '2px solid var(--accent)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} /></div>
  if (!data) return <div className="alert alert-error">Nessun risultato disponibile</div>

  const items = data.items || {}
  const scales = data.subscale_scores || {}
  const reportFinale = data.report_finale || {}
  const stats = data.statistics || {}
  const totalScore = data.total_score || 0

  // Sort items, exclude 113b/113c
  const sortedItems = Object.entries(items)
    .filter(([id]) => !HIDDEN_ITEMS.has(id))
    .sort(([a], [b]) => {
      const toNum = (s: string) => parseFloat(s.replace(/([a-h])$/, (_, c: string) => '.' + (c.charCodeAt(0) - 96)))
      return toNum(a) - toNum(b)
    })

  const handleEdit = async (itemId: string, newVal: number) => {
    const updated = { ...items, [itemId]: { ...items[itemId], value: newVal, confidence: 1.0, flag: null } }
    const newData = { ...data, items: updated, _editedByForm: true }
    setData(newData)
    setAnalysisData(newData) // persist to sessionStorage + sync with form page
    setEditItem(null)
    const vals: Record<string, number> = {}
    for (const [k, v] of Object.entries(updated) as any) { if (v.value != null) vals[k] = v.value }
    try {
      const r = await api.recompute(vals, data.child_age, data.child_sex, data.compilatore || 'MD')
      const recomputed = { ...data, ...r, items: updated, _editedByForm: true }
      setData(recomputed)
      setAnalysisData(recomputed) // persist recomputed scores
    } catch {}
  }

  const handleExportPdf = async () => {
    setPdfLoading(true)
    try {
      const token = localStorage.getItem('token')
      const res = await fetch('/cbcl/api/v1/export/pdf', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(Object.fromEntries(Object.entries(data).filter(([k]) => !k.startsWith('_')))),
      })
      if (!res.ok) throw new Error('Errore generazione PDF')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url; a.download = `CBCL_${data.compilatore || 'MD'}_${jobId}.pdf`; a.click()
    } catch (e: any) { alert(e.message) }
    finally { setPdfLoading(false) }
  }

  const handleExportJSON = () => {
    const clean = Object.fromEntries(Object.entries(data).filter(([k]) => !k.startsWith('_')))
    const blob = new Blob([JSON.stringify(clean, null, 2)], { type: 'application/json' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `CBCL_${jobId}.json`; a.click()
  }

  const handleExportCSV = () => {
    let csv = 'TOTALE\nScala;Formula;Raw\n'
    csv += `Internal;I + II + III;${scales.internalizing?.score ?? 0}\n`
    csv += `External;VII + VIII;${scales.externalizing?.score ?? 0}\n`
    csv += `Total;Tutte;${totalScore}\n\n`
    csv += 'RISPOSTE\nItem;Valore;Confidence;Flag\n'
    for (const [id, it] of sortedItems as any) {
      csv += `${id};${it.value ?? ''};${Math.round((it.confidence || 0) * 100)}%;${it.flag || 'ok'}\n`
    }
    const blob = new Blob([csv], { type: 'text/csv' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `CBCL_${jobId}.csv`; a.click()
  }

  return (
    <div style={{ paddingBottom: editItem ? 120 : 20 }}>
      <h1 className="gradient-text h1">Risultati Analisi</h1>
      <p style={{ color: 'var(--text-4)', marginBottom: 16 }}>
        Compilatore: <span className="pill pill-info">{data.compilatore === 'PD' ? '👨 Padre' : '👩 Madre'}</span>
        {data.method && <> &nbsp; Metodo: <span className="pill pill-info">{data.method}</span></>}
      </p>

      {/* Metrics row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 16 }}>
        {[
          { emoji: '📝', label: 'SCORE TOTALE', value: totalScore, color: '#C8B5FF' },
          { emoji: '✅', label: 'COMPLETATI', value: stats.items_scored ?? 0, color: '#34D399' },
          { emoji: '❌', label: 'MANCANTI', value: stats.items_missing ?? 0, color: '#F87171' },
          { emoji: '⚠️', label: 'AMBIGUI', value: stats.items_ambiguous ?? 0, color: '#FBBF24' },
        ].map(m => (
          <div key={m.label} className="glass metric" style={{ padding: 14 }}>
            <div className="value" style={{ color: m.color }}>{m.value}</div>
            <div className="label">{m.emoji} {m.label}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="tab-bar" style={{ marginBottom: 20 }}>
        <button className={`tab ${tab === 'results' ? 'active' : ''}`} onClick={() => setTab('results')}>📊 Risultati</button>
        <button className={`tab ${tab === 'export' ? 'active' : ''}`} onClick={() => setTab('export')}>💾 Export</button>
      </div>

      {/* === RESULTS TAB === */}
      {tab === 'results' && (
        <>
          {/* Subscale scores table */}
          <h2 className="h2">Score per Subscala</h2>
          <div className="glass" style={{ overflow: 'auto', marginBottom: 20 }}>
            <table className="data-table">
              <thead><tr><th>Subscala</th><th>Score</th><th>Max</th><th>%</th><th>Missing</th></tr></thead>
              <tbody>
                {Object.entries(scales).map(([key, sc]: any) => (
                  <tr key={key}>
                    <td style={{ fontWeight: 500, color: 'var(--text-1)' }}>{sc.label_it || key.replace(/_/g, ' ')}</td>
                    <td style={{ fontWeight: 700, color: 'var(--text-1)' }}>{sc.score}</td>
                    <td>{sc.max_score}</td>
                    <td>{sc.pct != null ? `${sc.pct}%` : '-'}</td>
                    <td style={{ color: sc.items_missing > 0 ? '#F59E0B' : 'var(--text-5)' }}>{sc.items_missing}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Item detail table */}
          <h2 className="h2">Dettaglio Item</h2>
          <div className="glass" style={{ overflow: 'auto', maxHeight: 500 }}>
            <table className="data-table">
              <thead><tr><th>Item</th><th>Valore</th><th>Confidence</th><th>Status</th></tr></thead>
              <tbody>
                {sortedItems.map(([id, it]: any) => {
                  const flag = it.flag || ''
                  const cls = FLAG_CLASS[flag] || ''
                  return (
                    <tr key={id} className={cls} style={{ cursor: 'pointer' }} onClick={() => setEditItem(id)}>
                      <td style={{ fontWeight: 500, color: 'var(--text-1)' }}>{DISPLAY_ID[id] || id}</td>
                      <td style={{ fontWeight: 700, color: 'var(--text-1)' }}>{it.value != null ? it.value : '-'}</td>
                      <td>{it.confidence > 0 ? `${Math.round(it.confidence * 100)}%` : '-'}</td>
                      <td>{FLAG_EMOJI[flag] || '❓'} {flag || 'ok'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Warnings */}
          {Object.values(items).some((it: any) => it.flag && !['ok', 'not_processed', 'missing'].includes(it.flag)) && (
            <>
              <h2 className="h2">⚠️ Item che richiedono revisione manuale</h2>
              {sortedItems.filter(([, it]: any) => it.flag && !['ok', 'not_processed', 'missing', null].includes(it.flag)).map(([id, it]: any) => (
                <div key={id} className="alert alert-warning">Item {id}: {it.flag}</div>
              ))}
            </>
          )}

          {/* Report Finale */}
          {reportFinale.critical_areas?.length > 0 && (
            <>
              <h2 className="h2">Report Finale — Aree Critiche (risposte = 2)</h2>
              <p style={{ color: 'var(--text-4)', marginBottom: 12, fontSize: '0.85rem' }}>
                Totale risposte critiche: <strong style={{ color: '#F472B6' }}>{reportFinale.total_critical}</strong>
              </p>
              {reportFinale.critical_areas.map((area: any) => (
                <div key={area.scale_key} className="glass" style={{ marginBottom: 10, overflow: 'hidden' }}>
                  <div style={{ padding: '10px 16px', background: area.color_dark, color: 'white', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.9rem' }}>{area.code} — {area.label}</span>
                    <span style={{ fontSize: '0.8rem', opacity: 0.9 }}>{area.n_critical}/{area.n_total}</span>
                  </div>
                  <div style={{ padding: '10px 16px' }}>
                    {area.items?.map((it: any) => (
                      <p key={it.id} style={{ fontSize: '0.8rem', margin: '3px 0', color: 'var(--text-3)' }}>
                        <span style={{ color: area.color_dark, fontWeight: 600 }}>•</span> <strong>Item {it.id}</strong>{it.text ? `: ${it.text}` : ''}
                      </p>
                    ))}
                  </div>
                </div>
              ))}
              {reportFinale.areas_without_critical?.length > 0 && (
                <div className="glass" style={{ padding: 16, marginTop: 12 }}>
                  <div className="label" style={{ marginBottom: 8 }}>Aree senza criticita</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {reportFinale.areas_without_critical.map((a: any) => (
                      <span key={a.code} className="pill" style={{ background: `${a.color_dark}15`, color: a.color_dark, border: `1px solid ${a.color_dark}33` }}>
                        {a.code} {a.label}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}

      {/* === EXPORT TAB === */}
      {tab === 'export' && (
        <>
          <h2 className="h2">Export Risultati</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
            {/* Save Project */}
            <div className="glass" style={{ padding: 20, textAlign: 'center', border: '1px solid var(--accent)' }}>
              <span style={{ fontSize: 40 }}>💾</span>
              <h3 className="h3" style={{ marginTop: 8 }}>Salva Progetto</h3>
              <p style={{ color: 'var(--text-5)', fontSize: '0.8rem', marginBottom: 12 }}>Salva il lavoro con tutte le modifiche manuali. Potrai riaprirlo dopo.</p>
              <button className="btn btn-primary" onClick={() => saveProject()}>💾 Salva Progetto</button>
            </div>
            {/* PDF */}
            <div className="glass" style={{ padding: 20, textAlign: 'center' }}>
              <span style={{ fontSize: 40 }}>📑</span>
              <h3 className="h3" style={{ marginTop: 8 }}>Export PDF</h3>
              <p style={{ color: 'var(--text-5)', fontSize: '0.8rem', marginBottom: 12 }}>Report professionale con scale colorate e aree critiche</p>
              <button className="btn btn-download" onClick={handleExportPdf} disabled={pdfLoading}>
                {pdfLoading ? '⏳ Generazione...' : '⬇️ Scarica PDF'}
              </button>
            </div>
            {/* JSON */}
            <div className="glass" style={{ padding: 20, textAlign: 'center' }}>
              <span style={{ fontSize: 40 }}>📄</span>
              <h3 className="h3" style={{ marginTop: 8 }}>Export JSON</h3>
              <p style={{ color: 'var(--text-5)', fontSize: '0.8rem', marginBottom: 12 }}>Report completo in formato JSON</p>
              <button className="btn btn-download" onClick={handleExportJSON}>⬇️ Scarica JSON</button>
            </div>
            {/* CSV */}
            <div className="glass" style={{ padding: 20, textAlign: 'center' }}>
              <span style={{ fontSize: 40 }}>📊</span>
              <h3 className="h3" style={{ marginTop: 8 }}>Export CSV</h3>
              <p style={{ color: 'var(--text-5)', fontSize: '0.8rem', marginBottom: 12 }}>Tabella per Excel (separatore ;)</p>
              <button className="btn btn-download" onClick={handleExportCSV}>⬇️ Scarica CSV</button>
            </div>
          </div>
        </>
      )}

      {/* Edit bottom sheet */}
      {editItem && (
        <div className="bottom-sheet">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <p style={{ color: 'var(--text-1)', fontWeight: 600 }}>Item {editItem}</p>
            <button onClick={() => setEditItem(null)} style={{ background: 'none', border: 'none', color: '#F87171', cursor: 'pointer', fontSize: 18 }}>✕</button>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {[0, 1, 2].map(v => (
              <button key={v} onClick={() => handleEdit(editItem, v)}
                className={`btn ${items[editItem]?.value === v ? 'btn-primary' : 'btn-ghost'}`}
                style={{ flex: 1, padding: '14px 0', fontSize: '1.2rem' }}>
                {v}
              </button>
            ))}
          </div>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
