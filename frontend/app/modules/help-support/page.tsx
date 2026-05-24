'use client'

/**
 * Help & Support — single home for every training video plus FAQ.
 *
 * All voice-narrated demos that used to live on the dashboard are also
 * surfaced here so every user can find them in one obvious place.
 * Pulls the list of scenarios from /api/v1/training/public/scenarios so
 * any new scene added on the backend automatically appears.
 */

import { useEffect, useState } from 'react'
import Link from 'next/link'
import RequireAuth from '../../components/RequireAuth'
import AppShell    from '../../components/AppShell'

const API        = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const NEXUS_BLUE = '#0066CC'
const MIL_GREEN  = '#4B5320'
const GOLD_DK    = '#A6800F'

interface Scenario {
  id: string; title: string; description: string
  duration_minutes: number; modules?: string[]; step_count?: number
}

export default function HelpSupportPage() {
  return (
    <RequireAuth>
      <AppShell pageTag="Help & Support">
        <HelpInner />
      </AppShell>
    </RequireAuth>
  )
}

function HelpInner() {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [loading,   setLoading]   = useState(true)
  const [filter,    setFilter]    = useState('')

  useEffect(() => {
    fetch(`${API}/api/v1/training/public/scenarios`)
      .then(r => r.ok ? r.json() : { scenarios: [] })
      .then(d => setScenarios(d.scenarios || []))
      .catch(() => setScenarios([]))
      .finally(() => setLoading(false))
  }, [])

  const filtered = scenarios.filter(s => {
    const q = filter.toLowerCase()
    return !q || s.title.toLowerCase().includes(q) || s.description.toLowerCase().includes(q)
  })

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 py-7 space-y-7">

      {/* Header strip */}
      <header className="rounded-2xl border bg-white p-5" style={{ borderColor: `${NEXUS_BLUE}30` }}>
        <div className="text-xs uppercase tracking-wider font-semibold" style={{ color: NEXUS_BLUE }}>
          HELP &amp; SUPPORT
        </div>
        <h1 className="text-2xl font-extrabold tracking-wide mt-1" style={{ color: MIL_GREEN }}>
          TRAINING VIDEOS &amp; GUIDED WALKTHROUGHS
        </h1>
        <p className="text-sm italic font-semibold mt-1" style={{ color: GOLD_DK }}>
          Smart data. Safer health.
        </p>
        <p className="text-sm text-zinc-600 mt-3">
          Every voice-narrated walkthrough lives here. Click any tile to launch the in-app
          assistant — say <span className="font-mono px-1 py-0.5 bg-zinc-100 rounded">Jorinova start</span> to play,
          <span className="font-mono px-1 py-0.5 bg-zinc-100 rounded ml-1">Jorinova next</span> to advance.
        </p>
      </header>

      {/* Filter */}
      <div className="flex items-center justify-between gap-3">
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Search scenarios (e.g. blood bank, OCR, malaria)"
          className="flex-1 max-w-md bg-white border border-zinc-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500"
        />
        <span className="text-xs text-zinc-500">{filtered.length} of {scenarios.length}</span>
      </div>

      {/* Scenario grid */}
      {loading ? (
        <div className="text-center py-12 text-zinc-500">Loading scenarios…</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 text-zinc-500">
          No scenarios match &ldquo;{filter}&rdquo;.
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map(s => (
            <Link
              key={s.id}
              href={`/modules/training/${s.id}?demo=1`}
              className="group rounded-2xl bg-white border border-zinc-200 p-5 hover:shadow-md hover:border-blue-400 transition-all"
            >
              <div className="flex items-start justify-between mb-2">
                <span className="text-[10px] uppercase tracking-wider font-semibold px-2 py-1 rounded-full"
                      style={{ background: `${MIL_GREEN}15`, color: '#3A4019', border: `1px solid ${MIL_GREEN}40` }}>
                  ▶ {s.duration_minutes} min · {s.step_count ?? '?'} steps
                </span>
              </div>
              <h3 className="text-base font-bold text-zinc-900 group-hover:text-blue-700 mb-1">
                {s.title}
              </h3>
              <p className="text-sm text-zinc-600 leading-snug">{s.description}</p>
              {s.modules && s.modules.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1">
                  {s.modules.map(m => (
                    <span key={m} className="text-[10px] uppercase px-1.5 py-0.5 rounded bg-zinc-100 text-zinc-600">
                      {m}
                    </span>
                  ))}
                </div>
              )}
            </Link>
          ))}
        </div>
      )}

      {/* FAQ */}
      <section className="rounded-2xl border bg-white p-5 shadow-sm" style={{ borderColor: `${NEXUS_BLUE}30` }}>
        <h2 className="text-sm font-bold tracking-wide mb-3" style={{ color: NEXUS_BLUE }}>FREQUENTLY ASKED</h2>
        <div className="space-y-3">
          <Faq q="The voice assistant doesn't speak — what should I check?"
               a="Click 🔊 Voice in the runner header (the mute toggle). On first load, browsers wait for a user interaction before allowing audio. Volume must be up." />
          <Faq q="The mic doesn't hear me when I say 'Jorinova start'"
               a="Click 🎤 Listen, then accept the browser permission prompt. The 'heard' bar shows what the mic actually picked up. SpeechRecognition needs Chrome or Edge on HTTPS or localhost." />
          <Faq q="My session keeps signing out"
               a="The system auto-logs-out after 5 minutes of inactivity for security. Any mouse / key / scroll resets the timer. Sign in again to continue." />
          <Faq q="Where do I report a bug or request a feature?"
               a="Email jorinovanexus@gmail.com with a screen recording and the time it happened — we cross-reference with the audit log." />
        </div>
      </section>
    </div>
  )
}

function Faq({ q, a }: { q: string; a: string }) {
  return (
    <details className="rounded-lg border border-zinc-200 px-3 py-2 open:bg-zinc-50">
      <summary className="cursor-pointer text-sm font-semibold text-zinc-800">{q}</summary>
      <p className="mt-2 text-sm text-zinc-600">{a}</p>
    </details>
  )
}
