'use client'

/**
 * Main dashboard — the system's home screen.
 *
 * One coherent surface bringing together:
 *   - Welcome banner (military-green heading, golden tagline, PQC badge)
 *   - Live KPIs from /api/v1/dashboard/stats
 *   - Smart sample routing (barcode scan → multi-dept decision)
 *   - Quick-launch grid for the 7 voice-narrated demo scenes
 *   - Clinical module navigation (laboratory, patients, billing, etc.)
 *   - Recent activity feed from /api/v1/dashboard/activity-feed
 *
 * Header + footer come from AppShell so login -> dashboard -> any module
 * looks like one application, not stitched-together prototypes.
 */

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '../contexts/AuthProvider'
import RequireAuth from '../components/RequireAuth'
import AppShell from '../components/AppShell'

const API         = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const NEXUS_BLUE  = '#0066CC'
const MIL_GREEN   = '#4B5320'
const MIL_GREEN_DK= '#3A4019'
const GOLD        = '#D4A017'
const GOLD_DK     = '#A6800F'

// ── Module + demo definitions ───────────────────────────────────────────────

const CLINICAL_MODULES = [
  { key: 'laboratory',    label: 'Laboratory',     icon: '🧪', desc: 'Results, worklists, validation',     href: '/modules/laboratory' },
  { key: 'patients',      label: 'Patients',       icon: '👤', desc: 'Registry, demographics, history',    href: '/modules/patients' },
  { key: 'billing',       label: 'Billing & MoMo', icon: '💳', desc: 'Invoices, MoMo, insurance',          href: '/modules/billing' },
  { key: 'inventory',     label: 'Inventory',      icon: '📦', desc: 'Stock levels, reorder triggers',     href: '/modules/inventory' },
  { key: 'blood_bank',    label: 'Blood Bank',     icon: '🩸', desc: 'Chamber/slot, crossmatch',           href: '/modules/blood_bank' },
  { key: 'ai_nexus',      label: 'AI Nexus',       icon: '🤖', desc: 'Hybrid AI assistant',                href: '/modules/ai_nexus' },
  { key: 'notifications', label: 'Notifications',  icon: '🔔', desc: 'SMS, escalations',                   href: '/modules/notifications' },
  { key: 'audit',         label: 'Audit',          icon: '📋', desc: 'PQC signatures, compliance',         href: '/modules/audit' },
] as const

const TRAINING_SCENES = [
  { id: 'iot_analyzer_intake_demo',   title: 'IoT analyzer ingestion',  tag: 'Vendor-neutral',  icon: '⚡' },
  { id: 'lis_mapping_walkthrough',    title: 'OCR + LIS auto-mapping',  tag: 'OCR',             icon: '📄' },
  { id: 'specimen_intake_stat',       title: 'STAT specimen intake',    tag: 'Workflow',        icon: '🩺' },
  { id: 'critical_value_validation',  title: 'Critical CBC validation', tag: 'Auto-archive',    icon: '⚠️' },
  { id: 'medgenome_pcr_demo',         title: 'GeneXpert MTB / Rif',     tag: 'Genomic',         icon: '🧬' },
  { id: 'blood_bank_crossmatch_demo', title: 'Blood-bank crossmatch',   tag: 'Traceability',    icon: '🩸' },
  { id: 'momo_billing_demo',          title: 'MoMo payment + release',  tag: 'Billing',         icon: '💳' },
] as const

const REAL_FEATURE_LINKS = [
  { label: 'LIS Auto-Mapping (live)', href: '/modules/lis_mapping',     icon: '🔎', desc: 'Upload a real form → mapped LabRequest' },
  { label: 'Training scenarios',       href: '/modules/training',        icon: '🎓', desc: 'Run any voice-narrated demo scene' },
  { label: 'Zero-touch demo',          href: '/modules/zero_touch_demo', icon: '🔁', desc: 'End-to-end OCR pipeline showcase' },
] as const

// ── Types ───────────────────────────────────────────────────────────────────

interface Stats {
  lab_requests: { today: number; week: number; pending: number; stat_today: number; validated_today: number }
  results:      { entered_today: number; critical_today: number }
  patients:     { total_active: number; registered_today: number }
  system:       { status: string; current_date: string; user_role: string }
}

interface FeedItem {
  id: number; lab_id: string; pid: string | null
  status: string; emergency_level: string
  department: string; timestamp: string | null
}

interface RoutingDecision {
  multi_dept: boolean
  tests: Array<{ id: string; name: string; department: string }>
  departments: string[]
  message?: string
  sample_id: string
}

// ── Page ────────────────────────────────────────────────────────────────────

function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return document.cookie.split('; ').find(r => r.startsWith('access_token='))?.split('=')[1]
    ?? localStorage.getItem('access_token')
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <AppShell>
        <DashboardInner />
      </AppShell>
    </RequireAuth>
  )
}

function DashboardInner() {
  const { user } = useAuth()
  const router = useRouter()

  const [stats,           setStats]           = useState<Stats | null>(null)
  const [feed,            setFeed]            = useState<FeedItem[]>([])
  const [scanId,          setScanId]          = useState('')
  const [isScanning,      setIsScanning]      = useState(false)
  const [routingDecision, setRoutingDecision] = useState<RoutingDecision | null>(null)

  // Load KPIs + activity feed (auth required)
  useEffect(() => {
    const tok = getToken()
    const headers: HeadersInit = tok ? { Authorization: `Bearer ${tok}` } : {}
    fetch(`${API}/api/v1/dashboard/stats`, { headers })
      .then(r => r.ok ? r.json() : null)
      .then(setStats)
      .catch(() => setStats(null))
    fetch(`${API}/api/v1/dashboard/activity-feed?limit=10`, { headers })
      .then(r => r.ok ? r.json() : [])
      .then(setFeed)
      .catch(() => setFeed([]))
  }, [])

  const handleScan = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!scanId) return
    setIsScanning(true)
    try {
      const res  = await fetch(`/api/routing/scan/${scanId}`, { method: 'POST' })
      const data = await res.json()
      if (data.multi_dept) {
        setRoutingDecision({ ...data, sample_id: scanId })
      } else {
        alert(`Sample ${scanId} auto-routed successfully to ${data.departments?.[0] ?? 'lab'}`)
        setScanId('')
      }
    } catch {
      alert('Routing endpoint not reachable. Confirm the backend is up.')
    } finally {
      setIsScanning(false)
    }
  }

  const confirmRouting = async (mode: 'all' | 'manual' | 'cancel') => {
    if (!routingDecision) return
    try {
      const res = await fetch(`/api/routing/confirm`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ sample_id: routingDecision.sample_id, mode }),
      })
      if (res.ok) {
        setRoutingDecision(null)
        setScanId('')
      }
    } catch {/* noop */}
  }

  return (
    <>
      {/* ── WELCOME BANNER ──────────────────────────────────────────────── */}
      <section
        className="border-b"
        style={{ borderColor: `${NEXUS_BLUE}30`, background: 'rgba(255,255,255,0.55)' }}
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 py-7 text-center space-y-3">
          <h1
            className="text-2xl sm:text-3xl font-extrabold tracking-wide"
            style={{ color: MIL_GREEN, textShadow: '0 1px 0 rgba(0,0,0,0.05)' }}
          >
            WELCOME, {user?.first_name?.toUpperCase() || user?.username?.toUpperCase()}
          </h1>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-1">
            <p
              className="text-lg sm:text-xl font-extrabold italic"
              style={{ color: GOLD_DK, textShadow: `0 1px 0 ${GOLD}66, 0 0 16px ${GOLD}33` }}
            >
              Smart data. Safer health.
            </p>
            <span
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wider shadow-sm"
              style={{
                background: 'linear-gradient(135deg, rgba(75,83,32,0.10) 0%, rgba(75,83,32,0.18) 100%)',
                color: MIL_GREEN_DK,
                border: `1px solid ${MIL_GREEN}40`,
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <path d="M9 12l2 2 4-4" />
              </svg>
              Post-quantum cryptography
            </span>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-7xl px-4 sm:px-6 py-6 space-y-8">

        {/* ── KPI tiles ──────────────────────────────────────────────────── */}
        <section className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <KpiTile label="Requests today"   value={stats?.lab_requests.today ?? '—'}        accent={NEXUS_BLUE}  hint={`${stats?.lab_requests.week ?? 0} this week`} />
          <KpiTile label="Validated today"  value={stats?.lab_requests.validated_today ?? '—'} accent="#0F766E"      hint={`${stats?.results.entered_today ?? 0} results entered`} />
          <KpiTile label="Critical results" value={stats?.results.critical_today ?? '—'}    accent="#B91C1C"     hint="HH / LL flags today" />
          <KpiTile label="Pending"          value={stats?.lab_requests.pending ?? '—'}      accent="#B45309"     hint={`${stats?.lab_requests.stat_today ?? 0} STAT today`} />
        </section>

        {/* ── Smart sample routing ──────────────────────────────────────── */}
        <section className="rounded-xl border bg-white p-5 shadow-sm" style={{ borderColor: `${NEXUS_BLUE}30` }}>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-bold tracking-wide" style={{ color: NEXUS_BLUE }}>
              SMART SAMPLE ROUTING
            </h2>
            <span className="text-[11px] text-zinc-500">Barcode → auto-pick destination department(s)</span>
          </div>
          <form onSubmit={handleScan} className="flex gap-2">
            <input
              type="text"
              value={scanId}
              onChange={(e) => setScanId(e.target.value)}
              placeholder="Scan barcode or enter Sample ID (e.g. S-0042)"
              className="flex-1 bg-white border border-zinc-300 rounded-lg px-4 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
            />
            <button
              disabled={isScanning || !scanId}
              className="px-5 py-2.5 rounded-lg text-white text-sm font-semibold shadow-sm hover:shadow disabled:opacity-50"
              style={{ background: NEXUS_BLUE }}
            >
              {isScanning ? 'Routing…' : 'Scan'}
            </button>
          </form>
        </section>

        {/* ── Real-feature shortcuts ────────────────────────────────────── */}
        <section className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {REAL_FEATURE_LINKS.map(f => (
            <Link
              key={f.href}
              href={f.href}
              className="group rounded-xl bg-white border-2 p-4 hover:shadow-md transition-all"
              style={{ borderColor: `${NEXUS_BLUE}40` }}
            >
              <div className="flex items-start gap-3">
                <div className="text-2xl">{f.icon}</div>
                <div className="flex-1">
                  <div className="font-semibold text-sm text-zinc-900 group-hover:text-blue-700">{f.label}</div>
                  <div className="text-xs text-zinc-500 mt-0.5">{f.desc}</div>
                </div>
                <div className="text-zinc-400 group-hover:text-blue-600">→</div>
              </div>
            </Link>
          ))}
        </section>

        {/* ── Demo scene grid ───────────────────────────────────────────── */}
        <section>
          <div className="flex items-baseline justify-between mb-3">
            <h2 className="text-sm font-bold tracking-wide" style={{ color: NEXUS_BLUE }}>
              VOICE-NARRATED DEMOS
            </h2>
            <Link href="/modules/training" className="text-xs font-medium hover:underline" style={{ color: NEXUS_BLUE }}>
              All scenarios →
            </Link>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {TRAINING_SCENES.map(s => (
              <Link
                key={s.id}
                href={`/modules/training/${s.id}?demo=1`}
                className="group rounded-xl bg-white border border-zinc-200 p-3 hover:shadow-md hover:border-blue-400 transition-all"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="text-2xl">{s.icon}</div>
                  <span className="text-[10px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded-full"
                        style={{ background: `${MIL_GREEN}15`, color: MIL_GREEN_DK }}>
                    {s.tag}
                  </span>
                </div>
                <div className="text-sm font-semibold text-zinc-900 group-hover:text-blue-700">{s.title}</div>
                <div className="text-[11px] text-zinc-400 mt-1">Say "Jorinova start" to run</div>
              </Link>
            ))}
          </div>
        </section>

        {/* ── Clinical modules grid ─────────────────────────────────────── */}
        <section>
          <h2 className="text-sm font-bold tracking-wide mb-3" style={{ color: NEXUS_BLUE }}>
            CLINICAL MODULES
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {CLINICAL_MODULES.map(m => (
              <button
                key={m.key}
                onClick={() => router.push(m.href)}
                className="text-left rounded-xl bg-white border border-zinc-200 p-3 hover:shadow-md hover:border-blue-400 transition-all"
              >
                <div className="text-2xl mb-1">{m.icon}</div>
                <div className="font-semibold text-sm text-zinc-900">{m.label}</div>
                <div className="text-[11px] text-zinc-500 mt-0.5">{m.desc}</div>
              </button>
            ))}
          </div>
        </section>

        {/* ── Activity feed ─────────────────────────────────────────────── */}
        {feed.length > 0 && (
          <section className="rounded-xl border bg-white p-5 shadow-sm" style={{ borderColor: `${NEXUS_BLUE}30` }}>
            <h2 className="text-sm font-bold tracking-wide mb-3" style={{ color: NEXUS_BLUE }}>
              RECENT ACTIVITY
            </h2>
            <div className="space-y-1.5">
              {feed.map(f => (
                <div key={f.id} className="flex items-center justify-between text-sm py-1.5 border-b last:border-0 border-zinc-100">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className={`inline-block h-2 w-2 rounded-full ${
                      f.emergency_level === 'stat'   ? 'bg-rose-500 animate-pulse' :
                      f.emergency_level === 'urgent' ? 'bg-amber-500' : 'bg-zinc-300'
                    }`} />
                    <span className="font-mono text-xs text-zinc-700">{f.lab_id}</span>
                    <span className="text-xs text-zinc-500 truncate">PID {f.pid ?? '—'}</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[11px] uppercase tracking-wider text-zinc-500">{f.status.replace('_', ' ')}</span>
                    <span className="text-[10px] text-zinc-400">
                      {f.timestamp ? new Date(f.timestamp).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : ''}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ── Admin-only quick links ────────────────────────────────────── */}
        {user?.is_superuser && (
          <section className="rounded-xl border border-purple-200 bg-purple-50/60 p-4">
            <div className="text-xs font-bold uppercase tracking-wider text-purple-700 mb-2">Admin</div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
              <Link href="/admin"                       className="text-purple-800 hover:underline">Admin dashboard</Link>
              <Link href="/security/voice-training/"    className="text-purple-800 hover:underline">Voice biometrics</Link>
              <Link href="/forgot-password"             className="text-purple-800 hover:underline">Reset a password</Link>
            </div>
          </section>
        )}
      </div>

      {/* ── Routing decision modal ──────────────────────────────────────── */}
      {routingDecision && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-zinc-900">Multi-Department Routing Decision</h3>
            <p className="text-sm text-zinc-500 mt-1">
              Sample <b>{routingDecision.sample_id}</b> requires intervention.
            </p>
            <div className="mt-4 space-y-2 max-h-48 overflow-y-auto border-y border-zinc-100 py-3">
              {routingDecision.tests.map(test => (
                <div key={test.id} className="flex justify-between text-xs p-2 bg-zinc-50 rounded border border-zinc-100">
                  <span className="font-medium">{test.name}</span>
                  <span className="font-bold uppercase" style={{ color: NEXUS_BLUE }}>{test.department}</span>
                </div>
              ))}
            </div>
            <div className="mt-6 grid grid-cols-1 gap-2">
              <button onClick={() => confirmRouting('all')}
                      className="w-full text-white py-2 rounded-lg text-sm font-semibold"
                      style={{ background: NEXUS_BLUE }}>
                Route to all departments
              </button>
              <button onClick={() => confirmRouting('manual')}
                      className="w-full bg-white border border-zinc-300 py-2 rounded-lg text-sm font-medium">
                Select manually
              </button>
              <button onClick={() => confirmRouting('cancel')}
                      className="w-full text-zinc-500 py-2 text-sm font-medium hover:text-red-500">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}


// ── Bits ────────────────────────────────────────────────────────────────────

function KpiTile({
  label, value, accent, hint,
}: { label: string; value: string | number; accent: string; hint?: string }) {
  return (
    <div className="rounded-xl bg-white p-4 shadow-sm border" style={{ borderColor: `${accent}40` }}>
      <div className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: accent }}>
        {label}
      </div>
      <div className="text-3xl font-extrabold text-zinc-900 mt-1">{value}</div>
      {hint && <div className="text-[11px] text-zinc-500 mt-0.5">{hint}</div>}
    </div>
  )
}
