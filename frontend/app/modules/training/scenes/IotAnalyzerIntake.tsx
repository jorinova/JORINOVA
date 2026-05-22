'use client'

import { useEffect, useState } from 'react'
import type { SceneProps } from './types'
import { withHighlight } from './types'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type Adapter = {
  id:           string
  vendor:       string
  model:        string
  wire_format:  string
  description:  string
}

/**
 * Scene: iot_analyzer_intake
 *
 * Demonstrates the vendor-neutral analyzer ingestion layer. The scene fetches
 * the live list of registered IoT adapters from the backend so the demo
 * always reflects which analyzers are wired up right now — not a hardcoded
 * Sysmex/Cobas list.
 *
 * DOM contract:
 *   [data-train="adapter-list"]
 *   [data-train="selected-adapter"]
 *   [data-train="payload-preview"]
 *   [data-train="ingest-btn"]
 *   [data-train="result-feed"]
 */
export default function IotAnalyzerIntake({ highlight }: SceneProps) {
  const [adapters, setAdapters] = useState<Adapter[]>([])
  const [selected, setSelected] = useState<string>('hl7_generic')

  useEffect(() => {
    let cancelled = false
    fetch(`${API}/api/v1/iot/public/adapters`)
      .then(r => r.json())
      .then(d => { if (!cancelled) setAdapters(d.adapters ?? []) })
      .catch(() => {/* show empty */})
    return () => { cancelled = true }
  }, [])

  const current = adapters.find(a => a.id === selected) ?? adapters[0]

  return (
    <section className="grid gap-4 md:grid-cols-2">
      <div
        data-train="adapter-list"
        className={withHighlight(highlight, '[data-train="adapter-list"]',
          'rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 space-y-3 transition-all duration-300')}
      >
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-zinc-200">Registered analyzer adapters</h3>
          <span className="text-[10px] px-2 py-0.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-200">
            live · {adapters.length} adapter{adapters.length === 1 ? '' : 's'}
          </span>
        </div>
        <p className="text-[11px] text-zinc-500">
          Any analyzer in the lab plugs into one of these adapters — vendor-neutral.
        </p>
        <ul className="space-y-1.5">
          {adapters.length === 0 && (
            <li className="text-xs text-zinc-500 py-2">Loading adapters…</li>
          )}
          {adapters.map(a => (
            <li key={a.id}>
              <button
                onClick={() => setSelected(a.id)}
                className={`w-full text-left rounded-md border px-3 py-2 text-xs transition ${
                  selected === a.id
                    ? 'border-indigo-400/60 bg-indigo-500/15 text-indigo-100'
                    : 'border-zinc-700 bg-zinc-950 text-zinc-300 hover:bg-zinc-800'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{a.vendor} · {a.model}</span>
                  <span className="text-[10px] uppercase tracking-wide text-zinc-500">{a.wire_format}</span>
                </div>
                <div className="text-[11px] text-zinc-500 mt-0.5 font-mono">{a.id}</div>
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="space-y-3">
        <div
          data-train="selected-adapter"
          className={withHighlight(highlight, '[data-train="selected-adapter"]',
            'rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 space-y-2 transition-all duration-300')}
        >
          <h3 className="text-sm font-medium text-zinc-200">Selected adapter</h3>
          {current ? (
            <>
              <div className="text-sm">
                <span className="font-medium text-zinc-100">{current.vendor}</span>
                <span className="text-zinc-400"> · {current.model}</span>
              </div>
              <div className="text-[11px] text-zinc-500">{current.description}</div>
              <div className="flex gap-2 text-[10px] flex-wrap">
                <span className="rounded-full border border-zinc-700 bg-zinc-950 px-2 py-0.5 text-zinc-400">
                  wire: {current.wire_format}
                </span>
                <span className="rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2 py-0.5 text-indigo-200 font-mono">
                  id: {current.id}
                </span>
              </div>
            </>
          ) : (
            <div className="text-xs text-zinc-500">No adapter selected.</div>
          )}
        </div>

        <div
          data-train="payload-preview"
          className={withHighlight(highlight, '[data-train="payload-preview"]',
            'rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 space-y-2 transition-all duration-300')}
        >
          <h3 className="text-sm font-medium text-zinc-200">Incoming payload</h3>
          <pre className="text-[10px] font-mono text-zinc-300 bg-zinc-950 rounded border border-zinc-800 p-3 overflow-auto max-h-32">
{samplePayload(current?.wire_format ?? 'HL7v2')}
          </pre>
        </div>

        <button
          data-train="ingest-btn"
          className={withHighlight(highlight, '[data-train="ingest-btn"]',
            'w-full rounded-lg border border-indigo-500/40 bg-indigo-500/15 px-3 py-2 text-sm hover:bg-indigo-500/25 transition-all duration-300')}
        >
          Ingest into LIS
        </button>
      </div>

      <div
        data-train="result-feed"
        className={withHighlight(highlight, '[data-train="result-feed"]',
          'md:col-span-2 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 text-xs text-zinc-300 space-y-1 transition-all duration-300')}
      >
        <div className="font-medium text-zinc-200 mb-1">Normalised result feed</div>
        <div className="text-zinc-500">
          After ingest, every analyzer produces the same ParsedResult shape — sample_id, test_code, value, unit, flag —
          so downstream rules (validation, critical-value escalation, AI interpretation) never see vendor differences.
        </div>
      </div>
    </section>
  )
}

function samplePayload(format: string): string {
  if (format === 'ASTM') {
    return [
      'H|\\^&|||COBAS-PRO|||||||P|1',
      'P|1|||PID-000123|||19900603|F',
      'O|1|SID-99001||^^^CBC^Complete Blood Count|R||20260521||||||||1',
      'R|1|^^^WBC^White Blood Cells|15.0|10^9/L|4.0 to 10.0|H||F',
      'L|1|N',
    ].join('\n')
  }
  if (format === 'JSON') {
    return JSON.stringify({
      results: [
        { sample_id: 'SID-99001', pid: 'PID-000123', test_code: 'WBC',
          value: 15.0, unit: '10^9/L', flag: 'H', reference_high: 10.0 },
      ],
    }, null, 2)
  }
  if (format === 'CSV') {
    return 'sample_id,pid,test_code,value,unit,flag\nSID-99001,PID-000123,WBC,15.0,10^9/L,H\n'
  }
  // default: HL7
  return [
    'MSH|^~\\&|SYSMEX-XN|LAB|ALIS-X|HOSP|20260521||ORU^R01|MSG00001|P|2.5',
    'PID|1||PID-000123||UWINEZA^MARY||19900603|F',
    'OBR|1|||CBC^Complete Blood Count',
    'OBX|1|NM|WBC^White Blood Cells||15.0|10^9/L|4.0-10.0|H',
    'OBX|2|NM|HGB^Hemoglobin||13.8|g/dL|12.0-15.5|N',
  ].join('\n')
}
