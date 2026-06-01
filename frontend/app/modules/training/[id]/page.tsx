'use client'

import { useCallback, useEffect, useMemo, useRef, useState, Suspense } from 'react'
import Link from 'next/link'
import { useParams, useSearchParams } from 'next/navigation'
import RequireAuth from '../../../components/RequireAuth'
import { resolveScene, sceneMap } from '../scenes'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type Step = {
  id:       string
  scene:    string
  target:   string | null
  voice:    string
  action:   string | null
  payload:  Record<string, unknown> | null
  dwell_ms: number
}

type LiveData = {
  lab_request?: { id: number; lab_id: string; doctor_name?: string | null; ward?: string | null; diagnosis?: string | null; priority?: string | null }
  patient?:     { family_name?: string | null; other_names?: string | null; age_band?: string | null; gender?: string | null; pid?: string | null; lid?: string | null }
  results?:     Array<{ test_id: number | null; value: string | null; numeric_value: number | null; unit: string | null; flag: string | null; status: string | null }>
}

type Scenario = {
  id:                string
  title:             string
  description:       string
  duration_minutes:  number
  roles:             string[]
  modules:           string[]
  scenes:            string[]
  steps:             Step[]
  data_source?:      Record<string, unknown> | null
  live_data?:        LiveData | null
  language?:         string
  generated?:        boolean
  source?:           string
}

function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return document.cookie.split('; ').find(r => r.startsWith('access_token='))?.split('=')[1]
    ?? localStorage.getItem('access_token')
}

function RunnerContent() {
  const sp = useSearchParams()
  const isPublic = sp?.get('demo') === '1'
  const body = <RunnerInner isPublic={isPublic} />
  return isPublic ? body : <RequireAuth>{body}</RequireAuth>
}

export default function TrainingRunnerPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#02061a] flex items-center justify-center text-zinc-400">Loading runner...</div>}>
      <RunnerContent />
    </Suspense>
  )
}

function RunnerInner({ isPublic }: { isPublic: boolean }) {
  const params = useParams<{ id: string }>()
  const id = params?.id ?? ''

  const [scenario, setScenario]   = useState<Scenario | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [stepIdx, setStepIdx]     = useState(-1)
  const [paused, setPaused]       = useState(false)
  const [done, setDone]           = useState(false)
  const [cursor, setCursor]       = useState({ x: 80, y: 80 })
  const [ripple, setRipple]       = useState<{ k: number; x: number; y: number } | null>(null)
  const [typedText, setTypedText] = useState<Record<string, string>>({})
  const [highlight, setHighlight] = useState<Record<string, string>>({})

  const runIdRef = useRef(0)

  // Load scenario. Generated scenarios (gen_*) come from the cache under the
  // public scenarios endpoint; static ones from the catalog endpoint.
  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const url = `${API}/api/v1/training/${isPublic ? 'public/' : ''}scenarios/${id}`
        const headers: Record<string, string> = {}
        if (!isPublic) {
          const tok = getToken()
          if (tok) headers.Authorization = `Bearer ${tok}`
        }
        const res = await fetch(url, { headers })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data: Scenario = await res.json()
        if (!cancelled) setScenario(data)

        // If a static scenario declares data_source but has no live_data, pull
        // one (anonymised) record so the scene can still render real values.
        if (!data.live_data && data.data_source && typeof data.data_source === 'object') {
          const ds = data.data_source as { feature_id?: string }
          const featureId = ds.feature_id ?? data.modules?.[0] ?? data.id
          try {
            const dsRes = await fetch(`${API}/api/v1/training/data-source/lab-request?feature_id=${encodeURIComponent(featureId)}`, { headers })
            if (dsRes.ok) {
              const live = await dsRes.json() as LiveData
              if (!cancelled) setScenario(prev => prev ? { ...prev, live_data: live } : prev)
            }
          } catch { /* live data is optional */ }
        }
      } catch (e) {
        if (!cancelled) setLoadError(e instanceof Error ? e.message : 'Failed to load scenario')
      }
    }
    load()
    return () => { cancelled = true }
  }, [id, isPublic])

  // ── Voice ───────────────────────────────────────────────────────────────────
  const speak = useCallback(async (text: string) => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return
    window.speechSynthesis.cancel()
    const utter = new SpeechSynthesisUtterance(text)
    const voices = window.speechSynthesis.getVoices?.() ?? []
    const female  = voices.find(v => /female|woman|zira|samantha|victoria/i.test(v.name))
    const english = voices.find(v => /en/i.test(v.lang))
    utter.voice = female ?? english ?? voices[0] ?? null
    utter.rate = 1.0; utter.pitch = 1.1
    await new Promise<void>(resolve => {
      utter.onend = () => resolve()
      utter.onerror = () => resolve()
      window.speechSynthesis.speak(utter)
    })
  }, [])

  // ── Step execution ──────────────────────────────────────────────────────────
  const runStep = useCallback(async (step: Step, runId: number) => {
    // helper that bails if the run was superseded (restart/leave)
    const stillCurrent = () => runId === runIdRef.current

    // 1. Move cursor
    if (step.target) {
      const el = document.querySelector(step.target) as HTMLElement | null
      if (el) {
        const r = el.getBoundingClientRect()
        setCursor({ x: r.left + r.width / 2, y: r.top + r.height / 2 })
        setRipple({ k: Date.now(), x: r.left + r.width / 2, y: r.top + r.height / 2 })
      }
      await wait(900)
      if (!stillCurrent()) return
    }

    // 2. Voice + action in parallel
    const voicePromise = speak(step.voice)
    if (step.action === 'type' && step.payload) {
      const intoSel = (step.payload.into as string) ?? step.target ?? ''
      const text    = (step.payload.text as string) ?? ''
      await simulateTyping(intoSel, text, (cur) => setTypedText(t => ({ ...t, [intoSel]: cur })))
    } else if ((step.action === 'highlight' || step.action === 'flash') && step.payload) {
      const cls    = (step.payload.cls as string) ?? 'trainPulseBlue'
      const sel    = (step.payload.target as string) ?? step.target ?? ''
      if (sel) {
        setHighlight(h => ({ ...h, [sel]: cls }))
      }
    } else if (step.action === 'click' && step.payload) {
      const cls = (step.payload.cls as string) ?? ''
      const sel = step.target ?? ''
      if (sel && cls) setHighlight(h => ({ ...h, [sel]: cls }))
    }
    await voicePromise
    if (!stillCurrent()) return

    // 3. Dwell
    if (step.dwell_ms) await wait(step.dwell_ms)
  }, [speak])

  // Drive the loop
  useEffect(() => {
    if (!scenario || stepIdx < 0 || paused) return
    if (stepIdx >= scenario.steps.length) {
      setTimeout(() => setDone(true), 0)
      return
    }
    const runId = runIdRef.current
    let cancelled = false
    ;(async () => {
      await runStep(scenario.steps[stepIdx], runId)
      if (cancelled || runId !== runIdRef.current) return
      setStepIdx(i => i + 1)
    })()
    return () => { cancelled = true }
  }, [scenario, stepIdx, paused, runStep])

  function start() {
    runIdRef.current += 1
    setDone(false)
    setTypedText({})
    setHighlight({})
    setStepIdx(0)
  }
  function pause() { setPaused(true); if (typeof window !== 'undefined') window.speechSynthesis?.cancel() }
  function resume() { setPaused(false) }
  function restart() {
    runIdRef.current += 1
    if (typeof window !== 'undefined') window.speechSynthesis?.cancel()
    setDone(false)
    setTypedText({})
    setHighlight({})
    setStepIdx(0)
  }
  function skip() {
    if (!scenario) return
    runIdRef.current += 1
    if (typeof window !== 'undefined') window.speechSynthesis?.cancel()
    setStepIdx(i => Math.min(i + 1, scenario.steps.length))
  }

  const currentStep = scenario && stepIdx >= 0 && stepIdx < scenario.steps.length
    ? scenario.steps[stepIdx]
    : null
  const sceneName = scenario?.scenes?.[0] ?? ''

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#070a17] to-[#02061a] text-zinc-100 relative overflow-hidden">
      <style jsx global>{`
        .trainPulseRed   { animation: trainRedPulse 0.85s ease-in-out infinite; border-color:#ef4444 !important; background: rgba(239,68,68,0.10) !important; box-shadow: 0 0 0 6px rgba(239,68,68,0.10); }
        .trainPulseBlue  { animation: trainBluePulse 0.85s ease-in-out infinite; box-shadow: 0 0 0 6px rgba(129,140,248,0.15); border-color:#818cf8 !important; }
        .trainPulseGreen { animation: trainGreenPulse 0.85s ease-in-out infinite; border-color:#22c55e !important; background: rgba(34,197,94,0.15) !important; box-shadow: 0 0 0 6px rgba(34,197,94,0.10); }
        .trainApproved   { background: rgba(34,197,94,0.25) !important; border-color:#22c55e !important; color:#bbf7d0 !important; }
        .trainPrinted    { background: rgba(99,102,241,0.20) !important; border-color:#6366f1 !important; }
        .trainRevealCard { animation: trainReveal 700ms ease-out; }
        @keyframes trainRedPulse  { 50% { opacity: 0.7; transform: translateY(-1px); } }
        @keyframes trainBluePulse { 50% { opacity: 0.85; } }
        @keyframes trainGreenPulse{ 50% { opacity: 0.85; } }
        @keyframes trainReveal    { from { opacity: 0.4; transform: scale(0.97); } to { opacity: 1; transform: scale(1); } }
        .trainCursor {
          position: fixed;
          width: 44px; height: 44px;
          transform: translate(-50%, -50%);
          pointer-events: none;
          z-index: 9999;
          transition: all 1.0s ease-in-out;
        }
        .trainRipple {
          position: fixed;
          width: 18px; height: 18px;
          border-radius: 999px;
          border: 2px solid rgba(129,140,248,0.95);
          background: rgba(129,140,248,0.15);
          transform: translate(-50%, -50%);
          animation: trainRippleAnim 700ms ease-out forwards;
          pointer-events: none;
          z-index: 9999;
        }
        @keyframes trainRippleAnim {
          0%   { opacity: 0.95; transform: translate(-50%, -50%) scale(0.7); }
          70%  { opacity: 0.35; transform: translate(-50%, -50%) scale(2.0); }
          100% { opacity: 0; transform: translate(-50%, -50%) scale(2.6); }
        }
      `}</style>

      {/* Virtual cursor + ripple */}
      <div className="trainCursor" style={{ left: cursor.x, top: cursor.y }} aria-hidden="true">
        <svg viewBox="0 0 64 64" width={44} height={44}>
          <path d="M10 6 L56 32 L12 58 L18 34 Z" fill="rgba(129,140,248,0.95)" stroke="rgba(199,210,254,0.9)" strokeWidth={2}/>
          <circle cx={32} cy={32} r={3.5} fill="rgba(226,232,240,0.95)"/>
        </svg>
      </div>
      {ripple && <div className="trainRipple" key={ripple.k} style={{ left: ripple.x, top: ripple.y }} />}

      {/* Header */}
      <div className="px-4 py-5 border-b border-zinc-800/60 bg-zinc-950/40 backdrop-blur">
        <div className="mx-auto max-w-5xl flex items-center justify-between gap-3">
          <div className="min-w-0">
            <Link href={isPublic ? '/modules/training?demo=1' : '/modules/training'} className="text-xs text-zinc-400 hover:text-zinc-200">← Back to scenarios</Link>
            <div className="mt-1 text-base font-medium truncate">{scenario?.title ?? 'Loading…'}</div>
          </div>
          <Controls
            started={stepIdx >= 0}
            paused={paused}
            done={done}
            stepIdx={stepIdx}
            total={scenario?.steps?.length ?? 0}
            onStart={start} onPause={pause} onResume={resume} onRestart={restart} onSkip={skip}
          />
        </div>
      </div>

      {/* Status line */}
      <div className="mx-auto max-w-5xl px-4 py-3 text-xs text-zinc-500 border-b border-zinc-800/30">
        {loadError && <span className="text-rose-300">Error: {loadError}</span>}
        {!loadError && scenario && (
          <>
            Step {Math.max(0, Math.min(stepIdx + 1, scenario.steps.length))} of {scenario.steps.length}
            {currentStep && <span className="text-zinc-300"> · {currentStep.voice.slice(0, 110)}{currentStep.voice.length > 110 ? '…' : ''}</span>}
            {done && <span className="text-emerald-300"> · Demo complete</span>}
          </>
        )}
      </div>

      {/* Scene mount — resolved by the dispatcher (scenes/index.ts) */}
      <div className="mx-auto max-w-5xl px-4 py-8">
        <SceneDispatcher
          sceneName={sceneName}
          typedText={typedText}
          highlight={highlight}
          liveData={scenario?.live_data ?? undefined}
        />
      </div>
    </div>
  )
}

// ── Controls ──────────────────────────────────────────────────────────────────

function Controls({
  started, paused, done, stepIdx, total, onStart, onPause, onResume, onRestart, onSkip,
}: {
  started: boolean; paused: boolean; done: boolean; stepIdx: number; total: number
  onStart: () => void; onPause: () => void; onResume: () => void; onRestart: () => void; onSkip: () => void
}) {
  return (
    <div className="flex items-center gap-2 text-xs">
      {!started && (
        <button onClick={onStart} className="rounded-md bg-indigo-500/80 px-3 py-1.5 font-medium hover:bg-indigo-500">▶ Start</button>
      )}
      {started && !done && !paused && (
        <button onClick={onPause} className="rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 hover:bg-zinc-700">⏸ Pause</button>
      )}
      {started && !done && paused && (
        <button onClick={onResume} className="rounded-md bg-indigo-500/80 px-3 py-1.5 font-medium hover:bg-indigo-500">▶ Resume</button>
      )}
      {started && !done && (
        <button onClick={onSkip} disabled={stepIdx >= total - 1} className="rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 hover:bg-zinc-700 disabled:opacity-40">⏭ Skip</button>
      )}
      <button onClick={onRestart} className="rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 hover:bg-zinc-700">⟲ Restart</button>
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function wait(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function simulateTyping(_intoSel: string, text: string, onTick: (cur: string) => void) {
  for (let i = 1; i <= text.length; i++) {
    onTick(text.slice(0, i))
    await wait(60)
  }
}

function SceneDispatcher({
  sceneName,
  typedText,
  highlight,
  liveData,
}: {
  sceneName: string
  typedText: Record<string, string>
  highlight: Record<string, string>
  liveData?: LiveData
}) {
  if (sceneName === 'specimen_intake') {
    return <sceneMap.specimen_intake typedText={typedText} highlight={highlight} liveData={liveData} />
  }
  if (sceneName === 'critical_cbc') {
    return <sceneMap.critical_cbc typedText={typedText} highlight={highlight} liveData={liveData} />
  }
  if (sceneName === 'lis_mapping_demo') {
    return <sceneMap.lis_mapping_demo typedText={typedText} highlight={highlight} liveData={liveData} />
  }

  if (!sceneName) return null
  return (
    <div className="text-xs text-rose-300">
      Unknown scene <code className="font-mono">{sceneName}</code> — register it in <code>scenes/index.ts</code>.
    </div>
  )
}
