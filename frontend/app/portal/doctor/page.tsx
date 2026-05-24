'use client'

/**
 * Doctor portal — clinical-facing client.
 *
 * Surface for a clinician requesting tests and reviewing results.
 * Pulls real data from existing backend endpoints (no mocks):
 *   - GET /api/v1/dashboard/activity-feed (recent lab requests, scoped
 *     server-side; for now shows the global feed and the doctor can
 *     filter to their own once we wire requested_by_id)
 *   - GET /api/v1/patients              (their patient roster)
 *   - GET /api/v1/dashboard/stats        (today's workload)
 *
 * Same AppShell + Avatar so the doctor recognises this as part of the
 * same system they signed in to — no portal feels orphaned.
 */

import { useEffect, useState } from 'react'
import Link from 'next/link'
import RequireAuth from '../../components/RequireAuth'
import AppShell    from '../../components/AppShell'
import { useAuth } from '../../contexts/AuthProvider'

const API        = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const NEXUS_BLUE = '#0066CC'
const MIL_GREEN  = '#4B5320'
const GOLD_DK    = '#A6800F'

interface Patient { id: number; pid: string; family_name: string; other_names?: string; gender?: string }
interface FeedItem {
  id: number; lab_id: string; pid: string | null
  status: string; emergency_level: string; timestamp: string | null
}
interface Stats {
  lab_requests: { today: number; week: number; pending: number; stat_today: number; validated_today: number }
  results:      { entered_today: number; critical_today: number }
}

function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return document.cookie.split('; ').find(r => r.startsWith('access_token='))?.split('=')[1]
    ?? localStorage.getItem('access_token')
}

export default function DoctorPortal() {
  return (
    <RequireAuth>
      <AppShell pageTag="Doctor portal">
        <DoctorInner />
      </AppShell>
    </RequireAuth>
  )
}

function DoctorInner() {
  const { user } = useAuth()
  const [patients, setPatients] = useState<Patient[]>([])
  const [feed,     setFeed]     = useState<FeedItem[]>([])
  const [stats,    setStats]    = useState<Stats | null>(null)
  const [query,    setQuery]    = useState('')

  useEffect(() => {
    const tok = getToken()
    const headers: HeadersInit = tok ? { Authorization: `Bearer ${tok}` } : {}
    fetch(`${API}/api/v1/patients/?limit=50`, { headers }).then(r => r.ok ? r.json() : []).then(setPatients).catch(() => setPatients([]))
    fetch(`${API}/api/v1/dashboard/activity-feed?limit=15`, { headers }).then(r => r.ok ? r.json() : []).then(setFeed).catch(() => setFeed([]))
    fetch(`${API}/api/v1/dashboard/stats`, { headers }).then(r => r.ok ? r.json() : null).then(setStats).catch(() => setStats(null))
  }, [])

  const filteredPatients = patients.filter(p => {
    if (!query) return true
    const q = query.toLowerCase()
    return (p.pid || '').toLowerCase().includes(q)
        || (p.family_name || '').toLowerCase().includes(q)
        || (p.other_names || '').toLowerCase().includes(q)
  }).slice(0, 25)

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 py-7 space-y-7">

      {/* Greeting bar */}
      <header className="rounded-2xl border bg-white p-5" style={{ borderColor: `${NEXUS_BLUE}30` }}>
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="text-xs uppercase tracking-wider font-semibold" style={{ color: NEXUS_BLUE }}>
              CLINICIAN PORTAL
            </div>
            <h1 className="text-2xl font-extrabold tracking-wide mt-1" style={{ color: MIL_GREEN }}>
              GOOD MORNING, DR. {(user?.last_name || user?.username || '').toUpperCase()}
            </h1>
            <p className="text-sm italic font-semibold mt-1" style={{ color: GOLD_DK }}>
              Smart data. Safer health.
            </p>
          </div>
          <div className="flex gap-2">
            <Link href="/modules/laboratory" className="px-4 py-2 rounded-lg text-white text-sm font-semibold shadow-sm" style={{ background: NEXUS_BLUE }}>
              + New test request
            </Link>
            <Link href="/dashboard" className="px-4 py-2 rounded-lg border border-zinc-300 text-zinc-700 text-sm font-medium hover:bg-zinc-50">
              Lab dashboard
            </Link>
          </div>
        </div>
      </header>

      {/* Today snapshot */}
      <section className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Kpi label="Pending results"      value={stats?.lab_requests.pending ?? '—'}      accent={NEXUS_BLUE} hint={`${stats?.lab_requests.stat_today ?? 0} STAT today`} />
        <Kpi label="Validated today"      value={stats?.lab_requests.validated_today ?? '—'} accent="#0F766E"  hint="Ready to act on" />
        <Kpi label="Critical alerts"      value={stats?.results.critical_today ?? '—'}    accent="#B91C1C"   hint="Phone the lab" />
        <Kpi label="Requests this week"   value={stats?.lab_requests.week ?? '—'}         accent="#7C3AED"   hint="Across your patients" />
      </section>

      {/* Two-column: patients + recent activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Patient roster */}
        <section className="rounded-2xl border bg-white p-5 shadow-sm" style={{ borderColor: `${NEXUS_BLUE}30` }}>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-bold tracking-wide" style={{ color: NEXUS_BLUE }}>MY PATIENTS</h2>
            <input
              type="text" value={query} onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by PID or name"
              className="text-xs px-3 py-1.5 rounded-md border border-zinc-300 outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          {filteredPatients.length === 0 ? (
            <p className="text-sm text-zinc-500 py-4 text-center">
              {query ? 'No patient matches that search.' : 'No patients yet — register one or wait for assignment.'}
            </p>
          ) : (
            <div className="divide-y divide-zinc-100">
              {filteredPatients.map(p => (
                <Link key={p.id} href={`/modules/patients?pid=${p.pid}`}
                      className="flex items-center justify-between py-2.5 px-1 hover:bg-zinc-50 -mx-1 rounded">
                  <div>
                    <div className="text-sm font-semibold text-zinc-900">
                      {p.family_name} {p.other_names ?? ''}
                    </div>
                    <div className="text-[11px] text-zinc-500 font-mono">PID {p.pid}</div>
                  </div>
                  <span className="text-[10px] uppercase tracking-wider px-2 py-1 rounded-full bg-blue-50 text-blue-700">
                    {p.gender ?? '?'}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </section>

        {/* Recent results / requests */}
        <section className="rounded-2xl border bg-white p-5 shadow-sm" style={{ borderColor: `${NEXUS_BLUE}30` }}>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-bold tracking-wide" style={{ color: NEXUS_BLUE }}>RECENT LAB ACTIVITY</h2>
            <span className="text-[11px] text-zinc-500">latest 15</span>
          </div>
          {feed.length === 0 ? (
            <p className="text-sm text-zinc-500 py-4 text-center">No recent activity.</p>
          ) : (
            <div className="divide-y divide-zinc-100">
              {feed.map(f => (
                <div key={f.id} className="flex items-center justify-between py-2 text-sm">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className={`inline-block h-2 w-2 rounded-full ${
                      f.emergency_level === 'stat'   ? 'bg-rose-500 animate-pulse' :
                      f.emergency_level === 'urgent' ? 'bg-amber-500' : 'bg-zinc-300'
                    }`} />
                    <span className="font-mono text-xs text-zinc-700">{f.lab_id}</span>
                    <span className="text-xs text-zinc-500 truncate">PID {f.pid ?? '—'}</span>
                  </div>
                  <span className="text-[11px] uppercase text-zinc-500">{f.status.replace('_', ' ')}</span>
                </div>
              ))}
            </div>
          )}
        </section>

      </div>
    </div>
  )
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
