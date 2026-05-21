'use client'

import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import RequireAuth from '../../components/RequireAuth'

type Step = {
  id: string
  target: 'patient_search' | 'lab_results' | 'approve_sign'
  voiceText: string
  action?: 'type' | 'highlight_row' | 'approve'
}

type WsCommand = {
  type: 'STEP'
  payload: {
    step: Step
  }
}

type WsAck = {
  type: 'DONE'
  payload: {
    stepId: string
  }
}

function clamp(n: number, a: number, b: number) {
  return Math.max(a, Math.min(b, n))
}

export default function ZeroTouchDemoPage() {
  const searchParams = useSearchParams()
  const skipAuth = searchParams?.get('demo') === '1'

  const [connected, setConnected] = useState(false)
  const [status, setStatus] = useState('Idle')
  const [currentStepId, setCurrentStepId] = useState<string | null>(null)

  const [cursor, setCursor] = useState({ x: 40, y: 40, visible: true })
  const [ripple, setRipple] = useState<{ id: string; x: number; y: number } | null>(null)

  const patientSearchRef = useRef<HTMLInputElement | null>(null)
  const labPanelRef = useRef<HTMLDivElement | null>(null)
  const approveBtnRef = useRef<HTMLButtonElement | null>(null)
  const wbcRowRef = useRef<HTMLDivElement | null>(null)

  const typingRef = useRef<number | null>(null)

  const steps = useMemo<Step[]>(
    () => [
      {
        id: 'step1_search',
        target: 'patient_search',
        voiceText: 'Accessing patient records for ID One-Zero-One.',
        action: 'type',
      },
      {
        id: 'step2_analysis',
        target: 'lab_results',
        voiceText:
          'Analyzing laboratory data. Hemoglobin is normal, but White Blood Cell count is elevated at 15,000 cells per microliter. Flagging mild leukocytosis.',
        action: 'highlight_row',
      },
      {
        id: 'step3_approve',
        target: 'approve_sign',
        voiceText:
          'No critical panic values detected. Results have been automatically validated, digitally signed under Jorinova Nexus protocols, and transmitted.',
        action: 'approve',
      },
    ],
    []
  )

  useEffect(() => {
    return () => {
      if (typingRef.current) window.clearInterval(typingRef.current)
    }
  }, [])

  function getTargetCenter(target: Step['target']) {
    const el =
      target === 'patient_search'
        ? patientSearchRef.current
        : target === 'lab_results'
          ? labPanelRef.current
          : approveBtnRef.current

    if (!el) return null
    const rect = el.getBoundingClientRect()
    return {
      x: rect.left + rect.width / 2,
      y: rect.top + rect.height / 2,
    }
  }

  async function speak(text: string) {
    try {
      if (!('speechSynthesis' in window)) return
      window.speechSynthesis.cancel()

      const utter = new SpeechSynthesisUtterance(text)

      // Best-effort female-ish voice selection
      const voices = window.speechSynthesis.getVoices?.() ?? []
      const female = voices.find((v) => /female|woman|zira|samantha|victoria/i.test(v.name))
      const english = voices.find((v) => /en/i.test(v.lang))
      utter.voice = female ?? english ?? voices[0] ?? null

      utter.rate = 1.0
      utter.pitch = 1.1
      utter.volume = 1.0

      await new Promise<void>((resolve) => {
        utter.onend = () => resolve()
        utter.onerror = () => resolve()
        window.speechSynthesis.speak(utter)
      })
    } catch {
      // no-op
    }
  }

  function clickRippleAt(x: number, y: number) {
    const id = `${Date.now()}_${Math.random().toString(16).slice(2)}`
    setRipple({ id, x, y })
    // ripple automatically fades via CSS animation
  }

  function animateCursorTo(step: Step) {
    const center = getTargetCenter(step.target)
    if (!center) return

    const x = clamp(center.x, 10, window.innerWidth - 10)
    const y = clamp(center.y, 10, window.innerHeight - 10)

    setCursor({ x, y, visible: true })
    return { x, y }
  }

  function doAction(step: Step) {
    if (!step.action) return Promise.resolve()

    if (step.action === 'type') {
      const el = patientSearchRef.current
      if (!el) return Promise.resolve()

      const text = 'One-Zero-One'
      el.value = ''
      setStatus('Typing patient ID…')

      const letters = text.split('')
      let i = 0

      return new Promise<void>((resolve) => {
        typingRef.current = window.setInterval(() => {
          i += 1
          el.value = letters.slice(0, i).join('')
          if (i >= letters.length) {
            if (typingRef.current) window.clearInterval(typingRef.current)
            typingRef.current = null
            setStatus('Patient ID entered')
            resolve()
          }
        }, 70)
      })
    }

    if (step.action === 'highlight_row') {
      setStatus('Analyzing CBC…')
      if (wbcRowRef.current) {
        wbcRowRef.current.classList.remove('demoWbcPulse')
        // force reflow
        // eslint-disable-next-line @typescript-eslint/no-unused-expressions
        wbcRowRef.current.offsetHeight
        wbcRowRef.current.classList.add('demoWbcPulse')
      }
      return new Promise<void>((resolve) => setTimeout(() => resolve(), 900))
    }

    if (step.action === 'approve') {
      setStatus('Auto-validating…')
      if (approveBtnRef.current) {
        approveBtnRef.current.classList.add('demoApproved')
        approveBtnRef.current.textContent = 'AUTHORIZED ✓'
      }
      return new Promise<void>((resolve) => setTimeout(() => resolve(), 800))
    }

    return Promise.resolve()
  }

  async function runStep(step: Step, sendDone: (ack: WsAck) => void) {
    setCurrentStepId(step.id)
    setStatus(`Running: ${step.id}`)

    const coords = animateCursorTo(step)
    if (coords) clickRippleAt(coords.x, coords.y)

    // Voice first, but allow overlap by small offset
    await speak(step.voiceText)

    await doAction(step)

    sendDone({ type: 'DONE', payload: { stepId: step.id } })
    setStatus('Waiting next…')
  }

  useEffect(() => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const wsUrl = apiBase.replace(/^http/, 'ws') + '/ws/zero-touch'

    let cancelled = false
    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      if (cancelled) return
      setConnected(true)
      setStatus('Connected. Awaiting steps…')
    }

    ws.onclose = () => {
      if (cancelled) return
      setConnected(false)
      setStatus('Disconnected')
    }

    ws.onerror = () => {
      if (cancelled) return
      setStatus('WebSocket error')
    }

    ws.onmessage = async (ev) => {
      if (cancelled) return
      try {
        const msg = JSON.parse(ev.data) as WsCommand
        if (msg.type !== 'STEP') return
        const step = msg.payload.step

        const sendDone = (ack: WsAck) => {
          if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(ack))
        }

        await runStep(step, sendDone)
      } catch {
        // ignore
      }
    }

    return () => {
      cancelled = true
      try { ws.close() } catch { /* ignore */ }
    }
  }, [])

  const body = (
    <div className="zeroTouchRoot">
        <style jsx global>{`
          .zeroTouchRoot {
            min-height: 100vh;
            background: radial-gradient(1100px 700px at 50% -10%, rgba(99,102,241,0.25), transparent),
              linear-gradient(180deg, #070a17, #02061a);
            color: #e5e7eb;
            font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
            position: relative;
            overflow: hidden;
          }
          .demoGrid {
            max-width: 980px;
            margin: 0 auto;
            padding: 28px 18px;
            display: grid;
            grid-template-columns: 1.2fr 1fr;
            gap: 16px;
          }
          @media (max-width: 900px) {
            .demoGrid {
              grid-template-columns: 1fr;
            }
          }
          .card {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.10);
            border-radius: 18px;
            padding: 16px;
            box-shadow: 0 16px 60px rgba(0,0,0,0.35);
          }
          .cardTitle {
            font-size: 14px;
            letter-spacing: 0.2px;
            color: rgba(226,232,240,0.85);
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 12px;
          }
          .chip {
            font-size: 12px;
            padding: 6px 10px;
            border-radius: 999px;
            background: rgba(99,102,241,0.20);
            border: 1px solid rgba(99,102,241,0.35);
            color: rgba(199,210,254,0.95);
          }
          .patientInput {
            width: 100%;
            padding: 12px 14px;
            border-radius: 12px;
            border: 1px solid rgba(148,163,184,0.25);
            background: rgba(2,6,23,0.35);
            color: #f8fafc;
            outline: none;
          }
          .patientInput:focus {
            border-color: rgba(129,140,248,0.9);
            box-shadow: 0 0 0 4px rgba(129,140,248,0.15);
          }

          .labPanel {
            display: grid;
            grid-template-columns: 1fr;
            gap: 10px;
          }

          .tableRow {
            display: grid;
            grid-template-columns: 1.2fr 0.8fr 0.9fr;
            gap: 10px;
            padding: 10px 12px;
            border-radius: 12px;
            border: 1px solid rgba(148,163,184,0.15);
            background: rgba(255,255,255,0.02);
          }
          .tableRow span:nth-child(1) { color: rgba(226,232,240,0.92); }
          .tableRow span {
            font-size: 13px;
          }

          .demoWbcPulse {
            border: 2px solid #ef4444 !important;
            background: rgba(239,68,68,0.10) !important;
            animation: blinkRed 0.85s ease-in-out infinite;
            box-shadow: 0 0 0 6px rgba(239,68,68,0.09);
          }
          @keyframes blinkRed {
            0%,100% { transform: translateY(0); opacity: 1; }
            50% { transform: translateY(-1px); opacity: 0.75; }
          }

          .approveWrap {
            display: flex;
            flex-direction: column;
            gap: 12px;
            margin-top: 8px;
          }
          .approveBtn {
            padding: 14px 14px;
            border-radius: 14px;
            border: 1px solid rgba(99,102,241,0.45);
            background: rgba(99,102,241,0.20);
            color: rgba(224,231,255,0.95);
            font-weight: 700;
            letter-spacing: 0.2px;
            cursor: not-allowed;
            transition: all 1.2s ease-in-out;
          }
          .approveBtn.demoApproved {
            border-color: rgba(34,197,94,0.7);
            background: rgba(34,197,94,0.25);
            color: rgba(187,247,208,1);
          }

          /* Virtual cursor */
          .virtualCursor {
            position: absolute;
            width: 44px;
            height: 44px;
            transform: translate(-50%, -50%);
            pointer-events: none;
            z-index: 9999;
            transition: all 1.2s ease-in-out;
          }
          .cursorSvg {
            width: 44px;
            height: 44px;
            filter: drop-shadow(0 10px 22px rgba(0,0,0,0.45));
          }

          .ripple {
            position: absolute;
            width: 18px;
            height: 18px;
            border-radius: 999px;
            border: 2px solid rgba(129,140,248,0.95);
            transform: translate(-50%, -50%);
            background: rgba(129,140,248,0.15);
            animation: ripple 650ms ease-out forwards;
            pointer-events: none;
          }
          @keyframes ripple {
            0% { opacity: 0.95; transform: translate(-50%, -50%) scale(0.7); }
            70% { opacity: 0.35; transform: translate(-50%, -50%) scale(2.0); }
            100% { opacity: 0; transform: translate(-50%, -50%) scale(2.6); }
          }
        `}</style>

        <div className="virtualCursor" style={{ left: cursor.x, top: cursor.y, opacity: cursor.visible ? 1 : 0 }}>
          <svg className="cursorSvg" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path
              d="M10 6 L56 32 L12 58 L18 34 Z"
              fill="rgba(129,140,248,0.95)"
              stroke="rgba(199,210,254,0.9)"
              strokeWidth="2"
            />
            <circle cx="32" cy="32" r="3.5" fill="rgba(226,232,240,0.95)" />
          </svg>
        </div>

        {ripple && <div className="ripple" style={{ left: ripple.x, top: ripple.y }} key={ripple.id} />}

        <div className="demoGrid">
          <div className="card">
            <div className="cardTitle">
              <span>Patient Search</span>
              <span className="chip">Zero-Touch Simulation</span>
            </div>

            <input
              ref={patientSearchRef}
              className="patientInput"
              placeholder="Enter Patient ID…"
              aria-label="Patient Search"
            />

            <div style={{ height: 12 }} />

            <div className="cardTitle" style={{ marginTop: 10 }}>
              <span>Lab Results Panel (CBC)</span>
              <span style={{ fontSize: 12, color: 'rgba(226,232,240,0.6)' }}>
                Cursor-driven UI
              </span>
            </div>

            <div ref={labPanelRef} className="labPanel">
              <div className="tableRow">
                <span>Hemoglobin</span>
                <span>13.8</span>
                <span>g/dL</span>
              </div>
              <div
                ref={wbcRowRef}
                className="tableRow"
                style={{ transition: 'all 0.3s ease' }}
              >
                <span>White Blood Cells (WBC)</span>
                <span>15,000</span>
                <span>cells/µL</span>
              </div>
              <div className="tableRow">
                <span>Platelets</span>
                <span>240</span>
                <span>k/µL</span>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="cardTitle">
              <span>Authorization</span>
              <span className="chip">Workflow Automations</span>
            </div>

            <div style={{ color: 'rgba(226,232,240,0.75)', fontSize: 13, lineHeight: 1.45 }}>
              <div>
                Voice + virtual cursor control enabled.
              </div>
              <div style={{ marginTop: 8 }}>
                Status: <b style={{ color: '#c7d2fe' }}>{status}</b>
              </div>
              <div style={{ marginTop: 8, fontSize: 12, color: 'rgba(226,232,240,0.55)' }}>
                WS: {connected ? 'Connected' : 'Disconnected'}
                {currentStepId ? ` • ${currentStepId}` : ''}
              </div>
            </div>

            <div className="approveWrap">
              <button ref={approveBtnRef} className="approveBtn" type="button">
                Approve & Sign
              </button>
            </div>

            <div style={{ marginTop: 14, fontSize: 12, color: 'rgba(226,232,240,0.55)' }}>
              Demo is intentionally zero-touch: no mouse/keyboard required.
            </div>
          </div>
        </div>
      </div>
  )

  return skipAuth ? body : <RequireAuth>{body}</RequireAuth>
}

