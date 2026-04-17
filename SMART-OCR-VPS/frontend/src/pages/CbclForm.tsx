import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { getAnalysisData } from '../App'

// 6 states (identical to desktop app)
type ItemState = 'pending' | 'confident' | 'multiple' | 'blank' | 'error' | 'manual'
const STATE_COLORS: Record<ItemState, { color: string; badge: string }> = {
  pending:    { color: '#7B8794', badge: '' },
  confident:  { color: '#34D399', badge: 'OK' },
  multiple:   { color: '#FBBF24', badge: "PIU' SEGNI" },
  blank:      { color: '#38BDF8', badge: 'NON COMPILATA' },
  error:      { color: '#F87171', badge: 'ERRORE' },
  manual:     { color: '#60A5FA', badge: 'MODIFICATA' },
}

type Filter = 'all' | 'review' | 'verified' | 'green' | 'yellow' | 'blue' | 'red'
const FILTERS: { key: Filter; label: string; color: string; states: ItemState[] }[] = [
  { key: 'all',      label: 'Tutti',         color: '#94A3B8', states: [] },
  { key: 'review',   label: 'Da verificare', color: '#FBBF24', states: ['multiple', 'blank', 'error'] },
  { key: 'verified', label: 'Verificati',    color: '#60A5FA', states: ['manual'] },
  { key: 'green',    label: 'Verdi',         color: '#34D399', states: ['confident'] },
  { key: 'yellow',   label: 'Gialli',        color: '#FBBF24', states: ['multiple'] },
  { key: 'blue',     label: 'Azzurri',       color: '#38BDF8', states: ['blank'] },
  { key: 'red',      label: 'Rossi',         color: '#F87171', states: ['error'] },
]

const HIDDEN_ITEMS = new Set(['113b', '113c'])  // completely hidden, not shown
const DISPLAY_ID: Record<string, string> = { '113a': '113' }

interface ItemData { value: number | null; confidence: number; state: ItemState }

export default function CbclForm({ data: propData, onUpdate }: { data: any; onUpdate: (items: Record<string, any>) => void }) {
  const nav = useNavigate()
  const [items, setItems] = useState<Record<string, ItemData>>({})
  const [questions, setQuestions] = useState<Record<string, string>>({})
  const [filter, setFilter] = useState<Filter>('all')
  const [editItem, setEditItem] = useState<string | null>(null)

  const data = propData || getAnalysisData()
  const hasData = !!(data?.items && Object.keys(data.items).length > 0)

  // Load questions
  useEffect(() => {
    fetch('/cbcl/api/v1/questions')
      .then(r => r.json())
      .then(d => setQuestions(d.questions || {}))
      .catch(() => {})
  }, [])

  // Build items from analysis data
  useEffect(() => {
    if (!data?.items) return
    const result: Record<string, ItemData> = {}
    for (const [id, it] of Object.entries(data.items) as [string, any][]) {
      if (HIDDEN_ITEMS.has(id)) continue  // skip 113b/113c entirely
      let state: ItemState = 'pending'
      if (it.flag === 'missing') { state = 'blank' }
      else if (it.flag === 'multiple_marks') { state = 'multiple' }
      else if (it.value == null) { state = 'error' }
      else { state = 'confident' }
      result[id] = { value: it.value, confidence: it.confidence || 0, state }
    }
    setItems(result)
  }, [data])

  const sortedIds = useMemo(() => {
    return Object.keys(items).sort((a, b) => {
      const toN = (s: string) => parseFloat(s.replace(/([a-h])$/, (_, c: string) => '.' + (c.charCodeAt(0) - 96)))
      return toN(a) - toN(b)
    })
  }, [items])

  const visibleIds = useMemo(() => {
    if (filter === 'all') return sortedIds
    const f = FILTERS.find(x => x.key === filter)!
    return sortedIds.filter(id => f.states.includes(items[id]?.state))
  }, [sortedIds, items, filter])

  const stats = useMemo(() => {
    const vals = Object.values(items)
    const score = vals.reduce((s, it) => s + (it.value ?? 0), 0)
    const completed = vals.filter(it => it.value != null).length
    const total = vals.length
    const byState = (s: ItemState) => vals.filter(it => it.state === s).length
    return {
      score, completed, total,
      pct: total > 0 ? Math.round(completed / total * 100) : 0,
      green: byState('confident'), yellow: byState('multiple'),
      blue: byState('blank'), red: byState('error'), manual: byState('manual'),
      toReview: byState('multiple') + byState('blank') + byState('error'),
    }
  }, [items])

  const handleChange = (itemId: string, newVal: number) => {
    const updated = { ...items, [itemId]: { ...items[itemId], value: newVal, confidence: 1.0, state: 'manual' as ItemState } }
    setItems(updated)
    setEditItem(null)
    const apiItems: Record<string, any> = {}
    for (const [k, v] of Object.entries(updated)) {
      apiItems[k] = { value: v.value, confidence: v.confidence, flag: v.state === 'blank' ? 'missing' : null }
    }
    onUpdate(apiItems)
  }

  // No data — show prompt
  if (!hasData) {
    return (
      <div>
        <h1 className="gradient-text h1">Questionario CBCL</h1>
        <div className="alert alert-info" style={{ marginTop: 20 }}>
          Carica e analizza un questionario nella tab "📤 Analisi" per visualizzare i 122 item qui.
        </div>
        <button className="btn btn-primary" style={{ marginTop: 16, maxWidth: 300 }} onClick={() => nav('/capture')}>
          📤 Vai ad Analisi
        </button>
      </div>
    )
  }

  return (
    <div>
      <h1 className="gradient-text h1">Questionario CBCL</h1>

      {/* Sticky header with stats */}
      <div style={{ position: 'sticky', top: 0, zIndex: 20, background: 'rgba(7,11,20,0.95)', backdropFilter: 'blur(12px)', padding: '10px 0', marginBottom: 10, borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', gap: 4, overflowX: 'auto', paddingBottom: 8 }}>
          {[
            { l: 'SCORE', v: stats.score, c: 'var(--text-1)' },
            { l: 'COMPILATI', v: `${stats.completed}/${stats.total}`, c: 'var(--text-1)' },
            { l: '%', v: `${stats.pct}%`, c: '#9B7FFF' },
            { l: 'VERDI', v: stats.green, c: '#34D399' },
            { l: 'GIALLI', v: stats.yellow, c: '#FBBF24' },
            { l: 'AZZURRI', v: stats.blue, c: '#38BDF8' },
            { l: 'ROSSI', v: stats.red, c: '#F87171' },
            { l: 'DA VERIF.', v: stats.toReview, c: '#FBBF24' },
            { l: 'VERIFICATI', v: stats.manual, c: '#60A5FA' },
          ].map(s => (
            <div key={s.l} style={{ background: '#1A1F2E', border: '1px solid var(--border)', borderRadius: 10, padding: '4px 8px', textAlign: 'center', minWidth: 52, flexShrink: 0 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: s.c }}>{s.v}</div>
              <div style={{ fontSize: 7, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.3px', color: 'var(--text-5)', marginTop: 1 }}>{s.l}</div>
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 3, overflowX: 'auto' }}>
          {FILTERS.map(f => {
            const active = filter === f.key
            const count = f.key === 'all' ? sortedIds.length : sortedIds.filter(id => f.states.includes(items[id]?.state)).length
            return (
              <button key={f.key} onClick={() => setFilter(f.key)}
                style={{
                  padding: '4px 8px', borderRadius: 8, fontSize: '0.68rem', fontWeight: 600,
                  border: `1px solid ${active ? f.color : 'var(--border)'}`,
                  background: active ? `${f.color}30` : 'transparent',
                  color: active ? f.color : 'var(--text-5)',
                  cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
                }}>
                {f.label} ({count})
              </button>
            )
          })}
        </div>
      </div>

      {/* Items */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3, paddingBottom: editItem ? 140 : 20 }}>
        {visibleIds.map(id => {
          const it = items[id]
          if (!it) return null
          const sc = STATE_COLORS[it.state]
          const displayId = DISPLAY_ID[id] || id

          return (
            <div key={id}
              onClick={() => setEditItem(id)}
              style={{
                display: 'flex', background: 'var(--surface)', border: '1px solid var(--border)',
                borderRadius: 10, overflow: 'hidden', cursor: 'pointer',
              }}>
              <div style={{ width: 4, background: sc.color, flexShrink: 0 }} />
              <div style={{ flex: 1, padding: '6px 10px', minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ background: `${sc.color}1A`, border: `1.5px solid ${sc.color}`, color: sc.color, borderRadius: 8, padding: '1px 6px', fontSize: 12, fontWeight: 700, minWidth: 32, textAlign: 'center', flexShrink: 0 }}>
                    {displayId}
                  </span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-2)', flex: 1, lineHeight: 1.25, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {questions[id] || `Item ${displayId}`}
                  </span>
                  {sc.badge && (
                    <span style={{ background: `${sc.color}26`, color: sc.color, borderRadius: 10, padding: '1px 8px', fontSize: '0.6rem', fontWeight: 700, whiteSpace: 'nowrap', flexShrink: 0 }}>
                      {it.state === 'confident' && it.confidence > 0 ? `OK ${Math.round(it.confidence * 100)}%` : sc.badge}
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 12, marginLeft: 38, marginTop: 3 }}>
                  {[0, 1, 2].map(v => (
                    <span key={v} style={{ fontSize: '0.68rem', fontWeight: it.value === v ? 700 : 400, color: it.value === v ? 'var(--text-1)' : 'var(--text-5)' }}>
                      {it.value === v ? '◉' : '○'} {v === 0 ? 'Non vero' : v === 1 ? 'A volte' : 'Molto vero'}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )
        })}
        {visibleIds.length === 0 && (
          <div className="alert alert-info">Nessun item corrisponde al filtro selezionato.</div>
        )}
      </div>

      {/* Edit bottom sheet */}
      {editItem && (
        <div className="bottom-sheet">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
            <div style={{ flex: 1 }}>
              <span style={{ color: 'var(--text-1)', fontWeight: 700 }}>Item {DISPLAY_ID[editItem] || editItem}</span>
              <p style={{ color: 'var(--text-5)', fontSize: '0.72rem', marginTop: 2, lineHeight: 1.3 }}>{questions[editItem] || ''}</p>
            </div>
            <button onClick={() => setEditItem(null)} style={{ background: 'none', border: 'none', color: '#F87171', cursor: 'pointer', fontSize: 20, padding: 4 }}>✕</button>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            {[
              { v: 0, l: '0 — Non vero' },
              { v: 1, l: '1 — A volte' },
              { v: 2, l: '2 — Molto vero' },
            ].map(o => (
              <button key={o.v} onClick={() => handleChange(editItem, o.v)}
                className={`btn ${items[editItem]?.value === o.v ? 'btn-primary' : 'btn-ghost'}`}
                style={{ flex: 1, padding: '12px 0', fontSize: '0.8rem' }}>
                {o.l}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
