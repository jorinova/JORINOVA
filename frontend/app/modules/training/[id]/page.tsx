'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { useParams, useSearchParams } from 'next/navigation'
import RequireAuth from '../../../components/RequireAuth'
import { resolveScene } from '../scenes'

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

export default function TrainingRunnerPage() {
  const sp = useSearchParams()
  const isPublic = sp?.get('demo') === '1'
  const body = <RunnerInner isPublic={isPublic} />
  return isPublic ? body : <RequireAuth>{body}</RequireAuth>
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

  // Voice + listening state
  const [muted,     setMuted]     = useState(false)
  const [voicesReady, setVoicesReady] = useState(false)
  const [subtitle,  setSubtitle]  = useState<string>('')
  const [listening, setListening] = useState(false)
  const [heardCmd,  setHeardCmd]  = useState<string>('')

  const runIdRef = useRef(0)
  const mutedRef = useRef(muted)
  useEffect(() => { mutedRef.current = muted }, [muted])

  // ── Preload TTS voices ──────────────────────────────────────────────────────
  // Web Speech API loads voices asynchronously. Without this, the first
  // utterance often falls back to whatever default the browser picked.
  useEffect(() => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return
    const synth = window.speechSynthesis
    const refresh = () => {
      const list = synth.getVoices?.() ?? []
      if (list.length > 0) setVoicesReady(true)
    }
    refresh()
    synth.addEventListener?.('voiceschanged', refresh)
    return () => synth.removeEventListener?.('voiceschanged', refresh)
  }, [])

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
  // Robust narrator. Three rules:
  //   1. Always update the subtitle (so the user sees the line even if audio is off)
  //   2. Never block the step loop — every speak() resolves within ~12s max
  //   3. Respect mute and language hint (en/fr/rw)
  const speak = useCallback(async (text: string, language?: string) => {
    setSubtitle(text)
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return
    if (mutedRef.current || !text) return

    const synth = window.speechSynthesis
    try { synth.cancel() } catch { /* noop */ }

    const utter = new SpeechSynthesisUtterance(text)
    const voices = synth.getVoices?.() ?? []
    const langTag = language === 'fr' ? 'fr' : language === 'rw' ? 'rw' : 'en'

    // Prefer a female English/French/Kinyarwanda voice if one is installed
    const langMatch = voices.filter(v => v.lang.toLowerCase().startsWith(langTag))
    const candidates = langMatch.length > 0 ? langMatch : voices
    const female = candidates.find(v =>
      /female|woman|zira|samantha|victoria|amelie|hortense|jenny|aria|fiona/i.test(v.name),
    )
    utter.voice = female ?? candidates[0] ?? null
    utter.rate  = 1.0
    utter.pitch = 1.05
    utter.volume = 1.0

    // Race speak vs a hard timeout so a stuck/silent utterance never deadlocks
    // the step loop. Estimate runtime: ~80ms per character with a 3s minimum
    // and 12s maximum.
    const estMs = Math.min(12000, Math.max(3000, text.length * 80))
    await new Promise<void>((resolve) => {
      let settled = false
      const finish = () => { if (!settled) { settled = true; resolve() } }
      utter.onend   = finish
      utter.onerror = finish
      try { synth.speak(utter) } catch { finish() }
      setTimeout(finish, estMs + 1500)
    })
  }, [])

  // ── Listening (SpeechRecognition / voice commands) ──────────────────────────
  // Wake-words   : jorinova, nexus, alis(-x), hey/hello/hi <wake>
  // Greetings    : hello / hi / good morning / mwaramutse / muraho
  // Help         : help, what can you do, ubufasha
  // Commands     : start, next, pause, resume, restart, stop (+ rw synonyms)
  // The mic auto-restarts on `onend` (Chrome stops it after silence).
  const cmdHandlerRef    = useRef<(cmd: string) => void>(() => {})
  const recognitionRef   = useRef<unknown>(null)
  const wantListeningRef = useRef(false)         // user intent — set true by Listen button

  // Intent matcher — returns { intent, reply? }.
  // `intent` is one of:
  //   start | next | pause | resume | restart | stop
  //   greet | wake | help | unknown
  const matchIntent = useCallback((text: string): { intent: string; reply?: string } => {
    const t = ' ' + text.toLowerCase().replace(/[^a-zà-ÿ0-9\s]/g, ' ').replace(/\s+/g, ' ').trim() + ' '

    // Wake / attention
    if (/(jorinova|nexus|alis( ?x)?)\b/.test(t)) {
      // Was it ALSO a greeting?
      if (/\b(hello|hi|hey|good (morning|afternoon|evening)|mwaramutse|muraho|murakoze)\b/.test(t)) {
        return { intent: 'greet', reply: timeGreeting(scenario?.language) }
      }
      return { intent: 'wake', reply: yes(scenario?.language) }
    }

    // Pure greeting (no wake-word)
    if (/^\s*(hello|hi|hey|good (morning|afternoon|evening)|mwaramutse|muraho)\b/.test(t)) {
      return { intent: 'greet', reply: timeGreeting(scenario?.language) }
    }

    // Help
    if (/\b(help|what can you do|how (do|to) i|what (are|do) (you|the) commands?|ubufasha)\b/.test(t)) {
      return {
        intent: 'help',
        reply: helpText(scenario?.language),
      }
    }

    // Thanks
    if (/\b(thank(s| you)?|murakoze)\b/.test(t)) {
      return { intent: 'thanks', reply: youreWelcome(scenario?.language) }
    }

    // Commands — looser regex, accepts natural phrasing
    if (/\b(start|begin|let'?s go|go ahead|tangira)\b/.test(t))           return { intent: 'start'  }
    if (/\b(next|next step|continue|move on|skip|forward|komeza)\b/.test(t))  return { intent: 'next'   }
    if (/\b(pause|wait|hold on|hold up|hagarara)\b/.test(t))              return { intent: 'pause'  }
    if (/\b(resume|continue now|go on|tangira nanone)\b/.test(t))         return { intent: 'resume' }
    if (/\b(restart|replay|again|from the start|subira|ongera)\b/.test(t))return { intent: 'restart'}
    if (/\b(stop|halt|cancel|reka|hagarika)\b/.test(t))                   return { intent: 'stop'   }

    return { intent: 'unknown' }
  }, [scenario?.language])

  const startListening = useCallback(() => {
    if (typeof window === 'undefined') return
    const SR = (window as unknown as {
      SpeechRecognition?:       new () => unknown
      webkitSpeechRecognition?: new () => unknown
    })
    const Ctor = SR.SpeechRecognition ?? SR.webkitSpeechRecognition
    if (!Ctor) { setHeardCmd('SpeechRecognition not supported in this browser'); return }

    wantListeningRef.current = true

    const spawn = () => {
      try {
        const rec = new Ctor() as unknown as {
          continuous: boolean
          interimResults: boolean
          lang: string
          onresult: (e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void
          onerror:  (e: { error?: string }) => void
          onend:    () => void
          start: () => void
          stop:  () => void
        }
        rec.continuous     = true
        rec.interimResults = false
        rec.lang = scenario?.language === 'fr' ? 'fr-FR'
                : scenario?.language === 'rw' ? 'rw-RW'
                : 'en-US'

        rec.onresult = async (e) => {
          const last = e.results[e.results.length - 1]
          const transcript = (last?.[0]?.transcript ?? '').trim()
          if (!transcript) return
          setHeardCmd(transcript)

          // Local-first matcher (instant). If unknown, fall back to the
          // backend cascade (regex → local LLM → cloud) for fuzzy phrasing.
          let { intent, reply } = matchIntent(transcript)
          if (intent === 'unknown') {
            try {
              const lang = scenario?.language === 'fr' ? 'fr'
                         : scenario?.language === 'rw' ? 'rw' : 'en'
              const res = await fetch(`${API}/api/v1/training/public/intent`, {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ text: transcript, language: lang, use_llm: true }),
              })
              if (res.ok) {
                const data = await res.json() as { intent: string; reply?: string; source?: string }
                if (data.intent && data.intent !== 'unknown') {
                  intent = data.intent
                  if (data.reply) reply = data.reply
                }
              }
            } catch { /* offline or backend down — stay unknown */ }
          }

          if (reply) speakImmediate(reply, scenario?.language)
          if (intent === 'unknown') {
            speakImmediate(unknownPhrase(scenario?.language, transcript), scenario?.language)
            return
          }
          // Greet / wake / help / thanks are pure conversational — no further action
          if (['greet', 'wake', 'help', 'thanks'].includes(intent)) return

          cmdHandlerRef.current(intent)
        }

        rec.onerror = (ev) => {
          // 'no-speech' fires on silence — fine, ignore. Other errors should not kill the loop.
          if (ev?.error && ev.error !== 'no-speech') {
            setHeardCmd(`(mic ${ev.error})`)
          }
        }
        rec.onend = () => {
          // Chrome stops after ~1 min of silence. If the user still wants to listen,
          // restart the recogniser after a tiny gap (browsers throttle tight loops).
          if (wantListeningRef.current) {
            setTimeout(() => { try { spawn() } catch { /* noop */ } }, 300)
          } else {
            setListening(false)
          }
        }
        rec.start()
        recognitionRef.current = rec
        setListening(true)
      } catch (e) {
        // 'InvalidStateError' fires when start() is called while one is already running
        setHeardCmd('mic error: ' + (e instanceof Error ? e.message : String(e)))
        wantListeningRef.current = false
        setListening(false)
      }
    }

    spawn()
  }, [scenario?.language, matchIntent])

  const stopListening = useCallback(() => {
    wantListeningRef.current = false
    const rec = recognitionRef.current as { stop?: () => void } | null
    try { rec?.stop?.() } catch { /* noop */ }
    setListening(false)
  }, [])

  // Helper that speaks one short line WITHOUT changing the step-loop subtitle.
  // We still update the subtitle so the operator sees what the assistant said.
  const speakImmediate = useCallback((text: string, language?: string) => {
    setSubtitle(text)
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return
    if (mutedRef.current || !text) return
    const synth = window.speechSynthesis
    try { synth.cancel() } catch { /* noop */ }
    const utter = new SpeechSynthesisUtterance(text)
    const voices = synth.getVoices?.() ?? []
    const langTag = language === 'fr' ? 'fr' : language === 'rw' ? 'rw' : 'en'
    const candidates = voices.filter(v => v.lang.toLowerCase().startsWith(langTag))
    const pool = candidates.length > 0 ? candidates : voices
    utter.voice = pool.find(v => /female|woman|zira|samantha|victoria|amelie|hortense|jenny|aria/i.test(v.name))
              ?? pool[0] ?? null
    utter.rate = 1.0; utter.pitch = 1.05
    try { synth.speak(utter) } catch { /* noop */ }
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
    const voicePromise = speak(step.voice, scenario?.language)
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
      setDone(true)
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
  function stopAll() {
    runIdRef.current += 1
    if (typeof window !== 'undefined') window.speechSynthesis?.cancel()
    setPaused(true)
    setSubtitle('')
  }

  // Voice command dispatcher — invoked by the SpeechRecognition handler above
  useEffect(() => {
    cmdHandlerRef.current = (cmd: string) => {
      if (cmd === 'start')   { start();   return }
      if (cmd === 'next')    { skip();    return }
      if (cmd === 'pause')   { pause();   return }
      if (cmd === 'resume')  { resume();  return }
      if (cmd === 'restart') { restart(); return }
      if (cmd === 'stop')    { stopAll(); return }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenario])

  const currentStep = scenario && stepIdx >= 0 && stepIdx < scenario.steps.length
    ? scenario.steps[stepIdx]
    : null
  const sceneName = scenario?.scenes?.[0] ?? ''
  const SceneComponent = resolveScene(sceneName)

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
            muted={muted}
            voicesReady={voicesReady}
            listening={listening}
            onStart={start} onPause={pause} onResume={resume} onRestart={restart} onSkip={skip}
            onToggleMute={() => setMuted(m => !m)}
            onToggleMic={() => listening ? stopListening() : startListening()}
          />
        </div>
      </div>

      {/* Subtitle bar — always shows current narration even when muted */}
      {(subtitle || heardCmd) && (
        <div className="sticky top-0 z-40 mx-auto max-w-5xl px-4 py-2">
          {subtitle && (
            <div className="rounded-xl border border-indigo-500/30 bg-indigo-500/10 px-4 py-2 text-sm text-indigo-100 shadow-lg">
              <span className="text-[10px] uppercase tracking-wide text-indigo-300 mr-2">narrator</span>
              {subtitle}
            </div>
          )}
          {heardCmd && (
            <div className="mt-1 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-[11px] text-amber-200">
              <span className="text-[10px] uppercase tracking-wide text-amber-300 mr-2">heard</span>
              &ldquo;{heardCmd}&rdquo;
            </div>
          )}
        </div>
      )}

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
        {SceneComponent
          ? <SceneComponent typedText={typedText} highlight={highlight} liveData={scenario?.live_data ?? undefined} />
          : sceneName && (
            <div className="text-xs text-rose-300">
              Unknown scene <code className="font-mono">{sceneName}</code> — register it in <code>scenes/index.ts</code>.
            </div>
          )
        }
      </div>
    </div>
  )
}

// ── Controls ──────────────────────────────────────────────────────────────────

function Controls({
  started, paused, done, stepIdx, total,
  muted, voicesReady, listening,
  onStart, onPause, onResume, onRestart, onSkip,
  onToggleMute, onToggleMic,
}: {
  started: boolean; paused: boolean; done: boolean; stepIdx: number; total: number
  muted: boolean; voicesReady: boolean; listening: boolean
  onStart: () => void; onPause: () => void; onResume: () => void; onRestart: () => void; onSkip: () => void
  onToggleMute: () => void; onToggleMic: () => void
}) {
  return (
    <div className="flex items-center gap-2 text-xs flex-wrap">
      {!started && (
        <button onClick={onStart}
          className="rounded-md bg-indigo-500/90 px-4 py-1.5 font-medium hover:bg-indigo-500 shadow-md">
          ▶ Start {voicesReady ? '' : '(loading voice…)'}
        </button>
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

      <span className="mx-1 w-px h-5 bg-zinc-700" aria-hidden />

      <button
        onClick={onToggleMute}
        title={muted ? 'Unmute narrator' : 'Mute narrator'}
        className={`rounded-md border px-2 py-1.5 ${muted
          ? 'border-rose-500/40 bg-rose-500/15 text-rose-200'
          : 'border-zinc-700 bg-zinc-800 hover:bg-zinc-700 text-zinc-200'}`}
      >
        {muted ? '🔇 Muted' : '🔊 Voice'}
      </button>
      <button
        onClick={onToggleMic}
        title='Toggle voice command listening'
        className={`rounded-md border px-2 py-1.5 ${listening
          ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-200 animate-pulse'
          : 'border-zinc-700 bg-zinc-800 hover:bg-zinc-700 text-zinc-200'}`}
      >
        {listening ? '🎙 Listening…' : '🎤 Listen'}
      </button>
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function wait(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

// Persona-aligned conversational replies (en / rw / fr). Kept short — the
// JORINOVA assistant persona is "simple words, short sentences, calm pace".

function timeGreeting(lang?: string): string {
  const hour = new Date().getHours()
  if (lang === 'rw') {
    if (hour < 12) return 'Mwaramutse. Murakoze guhamagara Jorinova.'
    if (hour < 18) return 'Mwiriwe. Murakoze guhamagara Jorinova.'
    return 'Muraho. Murakoze guhamagara Jorinova.'
  }
  if (lang === 'fr') {
    const slot = hour < 12 ? 'Bonjour' : hour < 18 ? 'Bon après-midi' : 'Bonsoir'
    return `${slot}. Merci de m'avoir appelée Jorinova.`
  }
  const slot = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
  return `${slot}. Thank you for calling Jorinova.`
}

function yes(lang?: string): string {
  if (lang === 'rw') return 'Ndi hano. Mwambwire icyo mushaka.'
  if (lang === 'fr') return 'Oui, je vous écoute.'
  return "Yes, I'm listening."
}

function helpText(lang?: string): string {
  if (lang === 'rw') {
    return 'Murashobora kuvuga: tangira, komeza, hagarara, subira, reka. Cyangwa muvugane Jorinova kugira ngo munsabe ubufasha.'
  }
  if (lang === 'fr') {
    return "Vous pouvez dire : démarrer, suivant, pause, reprendre, recommencer, ou arrêter. Dites Jorinova pour me parler."
  }
  return "You can say: start, next, pause, resume, restart, or stop. Say Jorinova to talk to me."
}

function youreWelcome(lang?: string): string {
  if (lang === 'rw') return 'Murakaza neza. Mugire umunsi mwiza.'
  if (lang === 'fr') return 'Je vous en prie. Bonne journée.'
  return "You're welcome. Have a nice day."
}

function unknownPhrase(lang: string | undefined, transcript: string): string {
  const heard = transcript.length > 40 ? transcript.slice(0, 40) + '…' : transcript
  if (lang === 'rw') return `Numvise: ${heard}. Sinabyumvise. Muvuge "ubufasha" kugira ngo mubone amategeko.`
  if (lang === 'fr') return `J'ai entendu : ${heard}. Je n'ai pas compris. Dites "aide" pour la liste des commandes.`
  return `I heard "${heard}". I did not understand. Say "help" to hear the commands.`
}

async function simulateTyping(_intoSel: string, text: string, onTick: (cur: string) => void) {
  for (let i = 1; i <= text.length; i++) {
    onTick(text.slice(0, i))
    await wait(60)
  }
}
