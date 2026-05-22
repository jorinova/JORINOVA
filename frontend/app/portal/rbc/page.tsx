'use client'

/**
 * RBC portal — Rwanda Biomedical Centre surveillance client.
 *
 * Public-health surface for RBC officials to monitor pathogen signals,
 * outbreak risk, and antimicrobial resistance across reporting labs.
 * All data comes from the existing surveillance + dashboard endpoints:
 *
 *   GET /api/v1/surveillance/dashboard          rolled-up overview
 *   GET /api/v1/surveillance/signals            individual outbreak signals
 *   GET /api/v1/surveillance/disease-tracking   per-disease trends
 *   GET /api/v1/surveillance/amr-report         AMR susceptibility report
 *   GET /api/v1/dashboard/stats                 system-wide workload
 *
 * Defensive: if any endpoint 404s, that card shows an empty-state instead
 * of breaking the page. RBC's data envelope evolves quickly; we render
 * what's there and ignore what isn't.
 */

import { useEffect, useState } from 'react'
import Link from 'next/link'
import RequireAuth from '../../components/RequireAuth'
import AppShell    from '../../components/AppShell'
import { useAuth } from '../../contexts/AuthProvider'

const API        = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const NEXUS_BLUE = '#0066CC'
const RBC_RED    = '#B91C1C'        // accent for outbreak/critical
const MIL_GREEN  = '#4B5320'
const GOLD_DK    = '#A6800F'

function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return document.cookie.split('; ').find(r => r.startsWith('access_token='))?.split('=')[1]
    ?? localStorage.getItem('access_token')
}

// Loose shapes — the surveillance API is still iterating, so we accept
// any extra fields and only render what we recognise.
type SurvDashboard = {
  active_signals?:     number
  high_risk?:          number
  signals_7d?:         number
  reporting_labs?:     number
  diseases_tracked?:   number
  amr_alerts?:         number
} | null

type Signal = {
  id?:           number | string
  signal_id?:    string
  pathogen?:     string
  disease?:      string
  district?:     string
  cases_7d?:     number
  baseline?:     number
  severity?:     string                   // low | medium | high | critical
  status?:       string                   // active | resolved
  created_at?:   string
}

type AmrRow = {
  organism?: string
  antibiotic?: string
  resistance_pct?: number
  sample_count?: number
}

export default function RbcPortal() {
  return (
    <RequireAuth>
      <AppShell pageTag="RBC portal">
        <RbcInner />
      </AppShell>
    </RequireAuth>
  )
}

function RbcInner() {
  const { user } = useAuth()
  const [dash,    setDash]    = useState<SurvDashboard>(null)
  const [signals, setSignals] = useState<Signal[]>([])
  const [amr,     setAmr]     = useState<AmrRow[]>([])
  const [stats,   setStats]   = useState<{ lab_requests?: { today?: number; week?: number } } | null>(null)

  useEffect(() => {
    const tok = getToken()
    const headers: HeadersInit = tok ? { Authorization: `Bearer ${tok}` } : {}
    fetch(`${API}/api/v1/surveillance/dashboard`, { headers }).then(r => r.ok ? r.json() : null).then(setDash).catch(() => {})
    fetch(`${API}/api/v1/surveillance/signals?limit=15`, { headers }).then(r => r.ok ? r.json() : []).then(s => setSignals(Array.isArray(s) ? s : [])).catch(() => {})
    fetch(`${API}/api/v1/surveillance/amr-report`, { headers }).then(r => r.ok ? r.json() : []).then(a => setAmr(Array.isArray(a) ? a : (a?.items ?? []))).catch(() => {})
    fetch(`${API}/api/v1/dashboard/stats`, { headers }).then(r => r.ok ? r.json() : null).then(setStats).catch(() => {})
  }, [])

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 py-7 space-y-7">

      {/* Greeting + identity */}
      <header className="rounded-2xl border bg-white p-5" style={{ borderColor: `${RBC_RED}30` }}>
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="text-xs uppercase tracking-wider font-semibold" style={{ color: RBC_RED }}>
              RWANDA BIOMEDICAL CENTRE · PUBLIC HEALTH SURVEILLANCE
            </div>
            <h1 className="text-2xl font-extrabold tracking-wide mt-1" style={{ color: MIL_GREEN }}>
              {(user?.full_name || user?.username || '').toUpperCase()}
            </h1>
            <p className="text-sm italic font-semibold mt-1" style={{ color: GOLD_DK }}>
              Smart data. Safer health.
            </p>
          </div>
          <div className="flex gap-2">
            <Link href="/modules/audit" className="px-4 py-2 rounded-lg border border-zinc-300 text-zinc-700 text-sm font-medium hover:bg-zinc-50">
              Audit trail
            </Link>
            <Link href="/dashboard" className="px-4 py-2 rounded-lg text-white text-sm font-semibold" style={{ background: NEXUS_BLUE }}>
              Lab dashboard
            </Link>
          </div>
        </div>
      </header>

      {/* KPI row */}
      <section className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Kpi label="Active signals"   value={dash?.active_signals   ?? '—'} accent={RBC_RED}    hint={`${dash?.high_risk ?? 0} high-risk`} />
        <Kpi label="Signals — 7 days" value={dash?.signals_7d       ?? '—'} accent="#B45309"   hint="New signals" />
        <Kpi label="Reporting labs"   value={dash?.reporting_labs   ?? '—'} accent={NEXUS_BLUE} hint="Currently uploading" />
        <Kpi label="AMR alerts"       value={dash?.amr_alerts       ?? '—'} accent="#7C3AED"   hint="Resistance patterns" />
      </section>

      {/* National workload context */}
      <section className="rounded-2xl border bg-white p-5 shadow-sm" style={{ borderColor: `${NEXUS_BLUE}30` }}>
        <h2 className="text-sm font-bold tracking-wide mb-2" style={{ color: NEXUS_BLUE }}>NATIONAL LAB WORKLOAD</h2>
        <div className="flex items-baseline gap-6 flex-wrap">
          <div>
            <div className="text-3xl font-extrabold text-zinc-900">{stats?.lab_requests?.today ?? '—'}</div>
            <div className="text-[11px] uppercase tracking-wider text-zinc-500">requests today</div>
          </div>
          <div>
            <div className="text-3xl font-extrabold text-zinc-900">{stats?.lab_requests?.week ?? '—'}</div>
            <div className="text-[11px] uppercase tracking-wider text-zinc-500">this week</div>
          </div>
          <div>
            <div className="text-3xl font-extrabold text-zinc-900">{dash?.diseases_tracked ?? '—'}</div>
            <div className="text-[11px] uppercase tracking-wider text-zinc-500">diseases tracked</div>
          </div>
        </div>
      </section>

      {/* Two-column: outbreak signals + AMR */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Outbreak signals */}
        <section className="rounded-2xl border bg-white p-5 shadow-sm" style={{ borderColor: `${RBC_RED}30` }}>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-bold tracking-wide" style={{ color: RBC_RED }}>ACTIVE OUTBREAK SIGNALS</h2>
            <span className="text-[11px] text-zinc-500">latest 15</span>
          </div>
          {signals.length === 0 ? (
            <p className="text-sm text-zinc-500 py-6 text-center">No outbreak signals currently active.</p>
          ) : (
            <div className="divide-y divide-zinc-100">
              {signals.slice(0, 15).map((s, idx) => (
                <div key={s.id ?? idx} className="flex items-center justify-between py-2.5 text-sm">
                  <div className="min-w-0">
                    <div className="font-semibold text-zinc-900 truncate">
                      {s.pathogen ?? s.disease ?? 'Unspecified'}
                    </div>
                    <div className="text-[11px] text-zinc-500">
                      {s.district ?? 'National'}{typeof s.cases_7d === 'number' ? ` · ${s.cases_7d} cases / 7d` : ''}
                    </div>
                  </div>
                  <span className="text-[10px] uppercase tracking-wider px-2 py-1 rounded-full font-semibold"
                        style={severityStyle(s.severity)}>
                    {s.severity ?? s.status ?? 'monitoring'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* AMR */}
        <section className="rounded-2xl border bg-white p-5 shadow-sm" style={{ borderColor: '#7C3AED30' }}>
          <h2 className="text-sm font-bold tracking-wide mb-3" style={{ color: '#6D28D9' }}>ANTIMICROBIAL RESISTANCE</h2>
          {amr.length === 0 ? (
            <p className="text-sm text-zinc-500 py-6 text-center">No AMR data yet — reporting labs need at least 14 days of cultures.</p>
          ) : (
            <div className="divide-y divide-zinc-100">
              {amr.slice(0, 12).map((r, i) => (
                <div key={i} className="flex items-center justify-between py-2 text-sm">
                  <div className="min-w-0">
                    <div className="font-semibold text-zinc-900 truncate">
                      <span className="italic">{r.organism ?? '?'}</span>
                      {r.antibiotic ? ` vs ${r.antibiotic}` : ''}
                    </div>
                    <div className="text-[11px] text-zinc-500">{r.sample_count ?? 0} isolates</div>
                  </div>
                  {typeof r.resistance_pct === 'number' && (
                    <span className="text-sm font-bold"
                          style={{ color: r.resistance_pct >= 50 ? RBC_RED : r.resistance_pct >= 25 ? '#B45309' : '#0F766E' }}>
                      {Math.round(r.resistance_pct)}%
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

function severityStyle(sev?: string): React.CSSProperties {
  switch ((sev || '').toLowerCase()) {
    case 'critical': return { background: '#FEE2E2', color: '#7F1D1D' }
    case 'high':     return { background: '#FFEDD5', color: '#9A3412' }
    case 'medium':   return { background: '#FEF3C7', color: '#92400E' }
    case 'low':      return { background: '#D1FAE5', color: '#065F46' }
    default:         return { background: '#E0F2FE', color: '#075985' }
  }
}

function Kpi({ label, value, accent, hint }: { label: string; value: string | number; accent: string; hint?: string }) {
  return (
    <div className="rounded-xl bg-white p-4 shadow-sm border" style={{ borderColor: `${accent}40` }}>
      <div className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: accent }}>{label}</div>
      <div className="text-3xl font-extrabold text-zinc-900 mt-1">{value}</div>
      {hint && <div className="text-[11px] text-zinc-500 mt-0.5">{hint}</div>}
    </div>
  )
}
