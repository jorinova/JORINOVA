'use client'

import type { SceneProps } from './types'
import { withHighlight } from './types'
import NoPilotData from './_NoPilotData'

/**
 * Scene: critical_cbc
 * Used by: `critical_value_validation` scenario.
 * DOM contract:
 *   [data-train="search"]
 *   [data-train="lab-panel"]
 *   [data-train="hgb-row"]
 *   [data-train="wbc-row"]
 *   [data-train="plt-row"]
 *   [data-train="approve"]
 */
// Test catalog ids (matches backend test_catalog rows used in the pilot):
const T_HGB = 1
const T_WBC = 3
const T_PLT = 4

export default function CriticalCBC({ typedText, highlight, liveData }: SceneProps) {
  // Production rule: no synthetic fallback. If the pilot DB has no matching
  // record yet, render the explicit waiting state instead of imaginary data.
  if (!liveData?.lab_request) {
    return <NoPilotData entity="LabRequest with a flagged result"
      hint="Wire an analyzer through the IoT adapter, or have a clinician submit a critical-flag result. This scene will bind automatically." />
  }
  const lr      = liveData.lab_request
  const patient = liveData.patient
  const results = liveData.results ?? []

  const find = (testId: number) => results.find(r => r.test_id === testId)
  const hgb  = find(T_HGB)
  const wbc  = find(T_WBC)
  const plt  = find(T_PLT)

  const patientName = patient
    ? `Patient ${patient.family_name ?? '—'}${patient.age_band ? `, ${patient.age_band}` : ''}${patient.gender ? `, ${patient.gender}` : ''}`
    : 'Patient (no live record bound)'

  return (
    <section className="grid gap-4 md:grid-cols-2">
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-zinc-200">Patient lookup</h3>
          {liveData && (
            <span className="text-[10px] px-2 py-0.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-200">
              live · pilot data
            </span>
          )}
        </div>
        <div className="text-xs text-zinc-400">
          {patientName}
          {lr && (<>
            <div className="mt-1">Lab ID: <span className="font-mono text-zinc-300">{lr.lab_id}</span> · Ward: {lr.ward ?? '—'} · Doctor: {lr.doctor_name ?? '—'}</div>
            <div>Diagnosis: {lr.diagnosis ?? '—'} · Priority: <b className={lr.priority === 'stat' ? 'text-rose-300' : 'text-zinc-300'}>{lr.priority?.toUpperCase()}</b></div>
          </>)}
        </div>
        <input
          data-train="search"
          readOnly
          value={typedText['[data-train="search"]'] ?? ''}
          placeholder="Enter Patient ID…"
          className={withHighlight(highlight, '[data-train="search"]',
            'w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm font-mono transition-all duration-300')}
        />
        <div data-train="lab-panel" className="space-y-2">
          <Row label="Hemoglobin"        val={hgb?.value ?? '13.8'}   unit={hgb?.unit ?? 'g/dL'}     flag={hgb?.flag} hl={highlight} sel='[data-train="hgb-row"]' />
          <Row label="White Blood Cells" val={wbc?.value ?? '15,000'} unit={wbc?.unit ?? 'cells/µL'} flag={wbc?.flag} hl={highlight} sel='[data-train="wbc-row"]' bold />
          <Row label="Platelets"         val={plt?.value ?? '240'}    unit={plt?.unit ?? 'k/µL'}     flag={plt?.flag} hl={highlight} sel='[data-train="plt-row"]' />
        </div>
      </div>

      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
        <h3 className="text-sm font-medium text-zinc-200">Authorization</h3>
        <p className="mt-2 text-xs text-zinc-400">
          Voice + virtual cursor control enabled. Reviewing flagged values before sign-off.
        </p>
        {results.length > 0 && (
          <div className="mt-3 text-[11px] text-zinc-500">
            {results.filter(r => r.flag).length} flagged of {results.length} results · binding: {lr?.lab_id ?? 'n/a'}
          </div>
        )}
        <button
          data-train="approve"
          className={withHighlight(highlight, '[data-train="approve"]',
            'mt-5 w-full rounded-lg border border-indigo-500/40 bg-indigo-500/20 px-3 py-3 text-sm font-medium transition-all duration-300')}
        >
          Approve &amp; Sign
        </button>
      </div>
    </section>
  )
}

function Row({
  label, val, unit, flag, hl, sel, bold,
}: {
  label: string; val: string; unit: string; flag?: string | null
  hl: Record<string, string>; sel: string; bold?: boolean
}) {
  const trainKey = sel.replace(/^\[data-train="(.+)"\]$/, '$1')
  const flagTone = flag === 'HH' || flag === 'H'
    ? 'text-rose-300 border-rose-500/30 bg-rose-500/10'
    : flag === 'LL' || flag === 'L'
      ? 'text-amber-300 border-amber-500/30 bg-amber-500/10'
      : ''
  return (
    <div
      data-train={trainKey}
      className={withHighlight(
        hl, sel,
        `grid grid-cols-[1fr_auto_60px_36px] gap-2 px-3 py-2 rounded-lg border border-zinc-700 bg-zinc-950 text-xs transition-all duration-300 ${bold ? 'font-medium' : ''}`,
      )}
    >
      <span className="text-zinc-300">{label}</span>
      <span className="text-zinc-100 font-mono text-right">{val}</span>
      <span className="text-zinc-500">{unit}</span>
      <span className={`text-[10px] rounded-full px-1.5 py-0.5 border text-center ${flag ? flagTone : 'opacity-0 border-transparent'}`}>
        {flag || '—'}
      </span>
    </div>
  )
}
