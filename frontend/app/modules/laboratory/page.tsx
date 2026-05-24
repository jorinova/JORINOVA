'use client'

/**
 * Laboratory module — real worklist view.
 *
 * Lists every lab request from /api/v1/dashboard/activity-feed (which
 * the backend orders by request_date DESC). Operators can filter by
 * status (pending / in_progress / validated / released) and emergency
 * level (routine / urgent / stat) without a server round-trip.
 *
 * Each row links to the relevant detail page — for now /modules/patients
 * with the PID prefilled; the per-request detail view is the next module.
 */

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import RequireAuth from '../../components/RequireAuth'
import AppShell    from '../../components/AppShell'

const API        = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const NEXUS_BLUE = '#0066CC'
const MIL_GREEN  = '#4B5320'

interface Row {
  id: number; lab_id: string; pid: string | null
  status: string; emergency_level: string
  department: string; timestamp: string | null
}

const STATUSES = ['all', 'pending', 'received', 'in_progress', 'validated', 'released', 'cancelled'] as const
const LEVELS   = ['all', 'routine', 'urgent', 'stat'] as const

function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return document.cookie.split('; ').find(r => r.startsWith('access_token='))?.split('=')[1]
    ?? localStorage.getItem('access_token')
}

export default function LaboratoryPage() {
  return (
    <RequireAuth>
      <AppShell pageTag="Laboratory">
        <LabInner />
      </AppShell>
    </RequireAuth>
  )
}

function LabInner() {
  const [rows,     setRows]     = useState<Row[]>([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState<string | null>(null)
  const [status,   setStatus]   = useState<(typeof STATUSES)[number]>('all')
  const [level,    setLevel]    = useState<(typeof LEVELS)[number]>('all')
  const [query,    setQuery]    = useState('')

  useEffect(() => {
    const tok = getToken()
    const headers: HeadersInit = tok ? { Authorization: `Bearer ${tok}` } : {}
    fetch(`${API}/api/v1/dashboard/activity-feed?limit=200`, { headers })
      .then(async r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(setRows)
      .catch(e => setError(e instanceof Error ? e.message : 'Failed to load worklist'))
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => {
    return rows.filter(r => {
      if (status !== 'all' && r.status !== status) return false
      if (level  !== 'all' && r.emergency_level !== level) return false
      if (query) {
        const q = query.toLowerCase()
        if (!(r.lab_id?.toLowerCase().includes(q) || (r.pid ?? '').toLowerCase().includes(q))) return false
      }
      return true
    })
  }, [rows, status, level, query])

  // Counts for the status pills
  const counts = useMemo(() => {
    const c: Record<string, number> = { all: rows.length }
    for (const s of STATUSES) if (s !== 'all') c[s] = rows.filter(r => r.status === s).length
    return c
  }, [rows])

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 py-6 space-y-5">
      <header className="rounded-2xl border bg-white p-5" style={{ borderColor: `${NEXUS_BLUE}30` }}>
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="text-xs uppercase tracking-wider font-semibold" style={{ color: NEXUS_BLUE }}>LABORATORY</div>
            <h1 className="text-2xl font-extrabold tracking-wide mt-1" style={{ color: MIL_GREEN }}>
              WORKLIST
            </h1>
            <p className="text-sm text-zinc-500">{rows.length} lab requests · {filtered.length} match current filter</p>
          </div>
          <Link href="/modules/lis_mapping"
                className="px-4 py-2 rounded-lg text-white text-sm font-semibold shadow-sm"
                style={{ background: NEXUS_BLUE }}>
            + New from lab form
          </Link>
        </div>
      </header>

      {/* Filter row */}
      <div className="flex items-center gap-2 flex-wrap">
        {STATUSES.map(s => (
          <button
            key={s}
            onClick={() => setStatus(s)}
            className={`text-xs px-2.5 py-1.5 rounded-md border transition-colors ${
              status === s
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-white text-zinc-700 border-zinc-300 hover:bg-zinc-50'
            }`}
          >
            {s} <span className="opacity-70">({counts[s] ?? 0})</span>
          </button>
        ))}
        <span className="text-zinc-300 px-1">|</span>
        {LEVELS.map(l => (
          <button
            key={l}
            onClick={() => setLevel(l)}
            className={`text-xs px-2.5 py-1.5 rounded-md border transition-colors ${
              level === l
                ? (l === 'stat' ? 'bg-rose-600 border-rose-600 text-white'
                  : l === 'urgent' ? 'bg-amber-600 border-amber-600 text-white'
                  : 'bg-zinc-700 border-zinc-700 text-white')
                : 'bg-white text-zinc-700 border-zinc-300 hover:bg-zinc-50'
            }`}
          >
            {l}
          </button>
        ))}
        <input
          value={query} onChange={e => setQuery(e.target.value)}
          placeholder="Search LR-... or PID"
          className="ml-auto rounded-md border border-zinc-300 px-3 py-1.5 text-xs outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Worklist table */}
      <section className="rounded-2xl border bg-white shadow-sm overflow-hidden" style={{ borderColor: `${NEXUS_BLUE}30` }}>
        {loading && <div className="p-6 text-center text-zinc-500 text-sm">Loading worklist…</div>}
        {error && <div className="p-6 text-center text-rose-600 text-sm">Error: {error}</div>}
        {!loading && !error && filtered.length === 0 && (
          <div className="p-12 text-center text-zinc-500 text-sm">No lab requests match the current filter.</div>
        )}
        {filtered.length > 0 && (
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-[11px] uppercase tracking-wider text-zinc-500">
              <tr>
                <th className="text-left px-4 py-2.5">Lab ID</th>
                <th className="text-left px-4 py-2.5">Patient PID</th>
                <th className="text-left px-4 py-2.5">Status</th>
                <th className="text-left px-4 py-2.5">Priority</th>
                <th className="text-left px-4 py-2.5">When</th>
                <th className="text-right px-4 py-2.5"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(r => (
                <tr key={r.id} className="border-t border-zinc-100 hover:bg-zinc-50">
                  <td className="px-4 py-2.5 font-mono text-xs text-zinc-700">{r.lab_id}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-zinc-700">{r.pid ?? '—'}</td>
                  <td className="px-4 py-2.5">
                    <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full font-semibold ${
                      r.status === 'released'    ? 'bg-emerald-100 text-emerald-700' :
                      r.status === 'validated'   ? 'bg-blue-100 text-blue-700' :
                      r.status === 'in_progress' ? 'bg-amber-100 text-amber-700' :
                      r.status === 'cancelled'   ? 'bg-zinc-100 text-zinc-500' :
                                                    'bg-zinc-100 text-zinc-700'
                    }`}>
                      {r.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="inline-flex items-center gap-1.5 text-xs">
                      <span className={`inline-block h-2 w-2 rounded-full ${
                        r.emergency_level === 'stat'   ? 'bg-rose-500 animate-pulse' :
                        r.emergency_level === 'urgent' ? 'bg-amber-500' : 'bg-zinc-300'
                      }`} />
                      {r.emergency_level}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-zinc-500">
                    {r.timestamp ? new Date(r.timestamp).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {r.pid && (
                      <Link href={`/modules/patients?pid=${r.pid}`}
                            className="text-xs font-medium hover:underline" style={{ color: NEXUS_BLUE }}>
                        View →
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
