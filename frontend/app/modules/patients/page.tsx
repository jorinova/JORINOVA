'use client'

/**
 * Patients module — real registry view.
 *
 * Lists the active patient roster from GET /api/v1/patients/, with
 * client-side search by PID, family name, or other names. Clicking
 * a patient surfaces their detail panel (right column) including
 * demographics + most recent lab activity.
 */

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import RequireAuth from '../../components/RequireAuth'
import AppShell    from '../../components/AppShell'

const API        = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const NEXUS_BLUE = '#0066CC'
const MIL_GREEN  = '#4B5320'

interface Patient {
  id:             number
  pid:            string
  unique_lab_id?: string | null
  family_name:    string
  other_names?:   string | null
  date_of_birth?: string | null
  gender?:        string | null
  phone?:         string | null
  email?:         string | null
  national_id?:   string | null
  address?:       string | null
  is_active:      boolean
}

interface Activity {
  id: number; lab_id: string; pid: string | null
  status: string; emergency_level: string; timestamp: string | null
}

function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return document.cookie.split('; ').find(r => r.startsWith('access_token='))?.split('=')[1]
    ?? localStorage.getItem('access_token')
}

function ageOf(dob?: string | null): string {
  if (!dob) return '—'
  const d = new Date(dob); if (isNaN(d.getTime())) return '—'
  const now = new Date()
  let age = now.getFullYear() - d.getFullYear()
  if (now.getMonth() < d.getMonth() || (now.getMonth() === d.getMonth() && now.getDate() < d.getDate())) age--
  return `${age}y`
}

export default function PatientsPage() {
  return (
    <RequireAuth>
      <AppShell pageTag="Patients">
        <PatientsInner />
      </AppShell>
    </RequireAuth>
  )
}

function PatientsInner() {
  const [patients, setPatients] = useState<Patient[]>([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState<string | null>(null)
  const [query,    setQuery]    = useState('')
  const [picked,   setPicked]   = useState<Patient | null>(null)
  const [activity, setActivity] = useState<Activity[]>([])

  useEffect(() => {
    const tok = getToken()
    const headers: HeadersInit = tok ? { Authorization: `Bearer ${tok}` } : {}
    fetch(`${API}/api/v1/patients/?limit=200`, { headers })
      .then(async r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data: Patient[]) => {
        setPatients(data)
        if (data.length > 0) setPicked(data[0])
      })
      .catch(e => setError(e instanceof Error ? e.message : 'Failed to load patients'))
      .finally(() => setLoading(false))
  }, [])

  // Pull recent activity, then filter client-side by chosen patient's PID
  useEffect(() => {
    const tok = getToken()
    const headers: HeadersInit = tok ? { Authorization: `Bearer ${tok}` } : {}
    fetch(`${API}/api/v1/dashboard/activity-feed?limit=200`, { headers })
      .then(r => r.ok ? r.json() : [])
      .then(setActivity)
      .catch(() => setActivity([]))
  }, [])

  const filtered = useMemo(() => {
    if (!query) return patients
    const q = query.toLowerCase()
    return patients.filter(p =>
      (p.pid || '').toLowerCase().includes(q) ||
      (p.family_name || '').toLowerCase().includes(q) ||
      (p.other_names || '').toLowerCase().includes(q) ||
      (p.unique_lab_id || '').toLowerCase().includes(q) ||
      (p.national_id || '').toLowerCase().includes(q),
    )
  }, [patients, query])

  const patientActivity = useMemo(() => {
    if (!picked) return []
    return activity.filter(a => a.pid === picked.pid).slice(0, 15)
  }, [activity, picked])

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 py-6 space-y-5">
      <header className="rounded-2xl border bg-white p-5" style={{ borderColor: `${NEXUS_BLUE}30` }}>
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="text-xs uppercase tracking-wider font-semibold" style={{ color: NEXUS_BLUE }}>PATIENT REGISTRY</div>
            <h1 className="text-2xl font-extrabold tracking-wide mt-1" style={{ color: MIL_GREEN }}>
              PATIENTS
            </h1>
            <p className="text-sm text-zinc-500">{patients.length} active patients on file</p>
          </div>
          <Link href="/modules/lis_mapping"
                className="px-4 py-2 rounded-lg text-white text-sm font-semibold shadow-sm"
                style={{ background: NEXUS_BLUE }}>
            + Register from lab form
          </Link>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_400px] gap-5">

        {/* Patient list */}
        <section className="rounded-2xl border bg-white shadow-sm" style={{ borderColor: `${NEXUS_BLUE}30` }}>
          <div className="p-4 border-b border-zinc-100 flex items-center gap-3">
            <input
              value={query} onChange={e => setQuery(e.target.value)}
              placeholder="Search by PID, name, NID, or LID"
              className="flex-1 rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500"
            />
            <span className="text-xs text-zinc-500 shrink-0">{filtered.length} match</span>
          </div>
          <div className="max-h-[60vh] overflow-y-auto">
            {loading && <div className="p-6 text-center text-zinc-500 text-sm">Loading…</div>}
            {error && <div className="p-6 text-center text-rose-600 text-sm">Error: {error}</div>}
            {!loading && !error && filtered.length === 0 && (
              <div className="p-6 text-center text-zinc-500 text-sm">No patients match that search.</div>
            )}
            {filtered.map(p => (
              <button
                key={p.id}
                onClick={() => setPicked(p)}
                className={`w-full text-left px-4 py-3 border-b border-zinc-50 flex items-center justify-between hover:bg-zinc-50 transition-colors ${
                  picked?.id === p.id ? 'bg-blue-50' : ''
                }`}
              >
                <div>
                  <div className="text-sm font-semibold text-zinc-900">
                    {p.family_name} {p.other_names ?? ''}
                  </div>
                  <div className="text-[11px] text-zinc-500 font-mono">PID {p.pid} · {p.unique_lab_id ?? ''}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-[10px] uppercase tracking-wider text-zinc-500">{p.gender ?? '?'} · {ageOf(p.date_of_birth)}</div>
                  {p.phone && <div className="text-[10px] text-zinc-400 font-mono">{p.phone}</div>}
                </div>
              </button>
            ))}
          </div>
        </section>

        {/* Detail panel */}
        <section className="rounded-2xl border bg-white shadow-sm p-5" style={{ borderColor: `${NEXUS_BLUE}30` }}>
          {!picked ? (
            <div className="text-center py-12 text-zinc-500 text-sm">Pick a patient to see details.</div>
          ) : (
            <>
              <div className="text-xs uppercase tracking-wider font-semibold mb-1" style={{ color: NEXUS_BLUE }}>PATIENT FILE</div>
              <h2 className="text-xl font-bold text-zinc-900">{picked.family_name} {picked.other_names ?? ''}</h2>
              <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                <Field label="PID"          value={picked.pid} mono />
                <Field label="Lab ID"       value={picked.unique_lab_id ?? '—'} mono />
                <Field label="National ID"  value={picked.national_id ?? '—'} mono />
                <Field label="Gender / Age" value={`${picked.gender ?? '?'} · ${ageOf(picked.date_of_birth)}`} />
                <Field label="Phone"        value={picked.phone ?? '—'} mono />
                <Field label="District"     value={picked.address ?? '—'} />
              </div>

              <div className="mt-5">
                <h3 className="text-xs uppercase tracking-wider font-semibold text-zinc-500 mb-2">RECENT LAB ACTIVITY</h3>
                {patientActivity.length === 0 ? (
                  <p className="text-sm text-zinc-500">No lab requests yet.</p>
                ) : (
                  <div className="space-y-1">
                    {patientActivity.map(a => (
                      <Link key={a.id} href={`/modules/laboratory?lab_id=${a.lab_id}`}
                            className="block text-sm px-2 py-1.5 rounded hover:bg-zinc-50">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2 min-w-0">
                            <span className={`inline-block h-2 w-2 rounded-full ${
                              a.emergency_level === 'stat'   ? 'bg-rose-500' :
                              a.emergency_level === 'urgent' ? 'bg-amber-500' : 'bg-zinc-300'
                            }`} />
                            <span className="font-mono text-xs text-zinc-700">{a.lab_id}</span>
                          </div>
                          <span className="text-[10px] uppercase text-zinc-500">{a.status.replace('_', ' ')}</span>
                        </div>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  )
}

function Field({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-md bg-zinc-50 border border-zinc-100 px-2 py-1.5">
      <div className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</div>
      <div className={`text-zinc-900 ${mono ? 'font-mono text-[12px]' : 'text-sm'}`}>{value}</div>
    </div>
  )
}
