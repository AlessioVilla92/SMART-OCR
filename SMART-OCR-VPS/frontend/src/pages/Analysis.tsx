import { useEffect, useState, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../lib/api'
import { setLastJobId } from '../App'

export default function Analysis() {
  const { jobId } = useParams<{ jobId: string }>()
  const nav = useNavigate()
  const [status, setStatus] = useState('queued')
  const [progress, setProgress] = useState(0)
  const [step, setStep] = useState('In attesa...')
  const [error, setError] = useState('')
  const timer = useRef<ReturnType<typeof setInterval>>(undefined)

  useEffect(() => {
    const poll = async () => {
      try {
        const data = await api.jobStatus(jobId!)
        setStatus(data.status)
        setProgress(data.progress || 0)
        setStep(data.current_step || 'Elaborazione...')

        if (data.status === 'completed') {
          clearInterval(timer.current)
          setLastJobId(jobId!)
          setTimeout(() => nav(`/results/${jobId}`), 500)
        } else if (data.status === 'failed') {
          clearInterval(timer.current)
          setError(data.error_message || 'Errore sconosciuto')
        }
      } catch (e: any) {
        setError('Connessione persa')
      }
    }

    poll()
    timer.current = setInterval(poll, 2000)
    return () => clearInterval(timer.current)
  }, [jobId, nav])

  const pct = Math.round(progress * 100)
  const circumference = 2 * Math.PI * 54
  const offset = circumference - (progress * circumference)

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="text-center max-w-sm w-full">
        {/* Progress ring */}
        <div className="relative w-36 h-36 mx-auto mb-8">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 120 120">
            <circle cx="60" cy="60" r="54" fill="none" stroke="rgba(124,58,237,0.15)" strokeWidth="8" />
            <circle cx="60" cy="60" r="54" fill="none" stroke="url(#grad)" strokeWidth="8"
              strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={offset}
              className="progress-ring" />
            <defs>
              <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#818CF8" />
                <stop offset="100%" stopColor="#C084FC" />
              </linearGradient>
            </defs>
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-3xl font-bold" style={{ color: 'var(--text-primary)' }}>{pct}%</span>
          </div>
        </div>

        <p className="text-lg font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>
          {status === 'failed' ? 'Analisi fallita' : 'Analisi in corso'}
        </p>
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{step}</p>

        {error && (
          <div className="glass p-4 mt-6 text-left">
            <p className="text-red-400 text-sm">{error}</p>
            <button onClick={() => nav('/')} className="btn-primary mt-4">Torna alla home</button>
          </div>
        )}
      </div>
    </div>
  )
}
