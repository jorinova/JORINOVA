'use client'

import type { SceneProps } from './types'
import { withHighlight } from './types'

/**
 * Scene: specimen_intake
 * Used by: `specimen_intake_stat` scenario.
 * DOM contract — these `data-train` selectors are the ones the scenario steps target:
 *   [data-train="scanner"]
 *   [data-train="patient-card"]
 *   [data-train="priority-chip"]
 *   [data-train="print-btn"]
 *   [data-train="status"]
 */
export default function SpecimenIntake({ typedText, highlight, liveData }: SceneProps) {
  const lr      = liveData?.lab_request
  const patient = liveData?.patient
  const results = liveData?.results ?? []

  // Up to 3 short labels for the test chips (real test_ids from the request)
  const testChips = results.slice(0, 6).map(r => r.test_id ? `T-${r.test_id}` : '—')

  const priorityRaw  = lr?.priority?.toLowerCase() ?? 'stat'
  const priorityText = priorityRaw.toUpperCase()
  const priorityTone = priorityRaw === 'stat'
    ? 'border-rose-500/40 bg-rose-500/15 text-rose-200'
    : priorityRaw === 'urgent'
      ? 'border-amber-500/40 bg-amber-500/15 text-amber-200'
      : 'border-zinc-600 bg-zinc-700/40 text-zinc-300'

  const patientLine = patient
    ? `${patient.family_name ?? '—'}${patient.age_band ? ` · ${patient.age_band}` : ''}${patient.gender ? ` · ${patient.gender}` : ''}`
    : 'Mary Uwineza · Female · 28y'   // fallback when no live record

  return (
    <section className="grid gap-4 md:grid-cols-2">
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-zinc-200">Reception · Barcode scanner</h3>
          {liveData && (
            <span className="text-[10px] px-2 py-0.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-200">
              live · pilot data
            </span>
          )}
        </div>
        <input
          data-train="scanner"
          readOnly
          value={typedText['[data-train="scanner"]'] ?? ''}
          placeholder="Scan tube barcode…"
          className={withHighlight(highlight, '[data-train="scanner"]',
            'w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm font-mono transition-all duration-300')}
        />
        <button
          data-train="print-btn"
          className={withHighlight(highlight, '[data-train="print-btn"]',
            'w-full rounded-lg border border-indigo-500/40 bg-indigo-500/15 px-3 py-2 text-sm hover:bg-indigo-500/25 transition-all duration-300')}
        >
          Print aliquot labels
        </button>
        {lr && (
          <div className="text-[11px] text-zinc-500">
            Lab ID <span className="font-mono text-zinc-300">{lr.lab_id}</span> · binding via specimen_intake_stat
          </div>
        )}
      </div>

      <div
        data-train="patient-card"
        className={withHighlight(highlight, '[data-train="patient-card"]',
          'rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 transition-all duration-300')}
      >
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-zinc-200">Patient</h3>
          <span
            data-train="priority-chip"
            className={withHighlight(highlight, '[data-train="priority-chip"]',
              `text-[10px] px-2 py-0.5 rounded-full border transition-all duration-300 ${priorityTone}`)}
          >
            {priorityText}
          </span>
        </div>
        <div className="mt-3 text-sm">
          <div className="text-zinc-100 font-medium">{patientLine}</div>
          <div className="text-zinc-400 text-xs">PID {patient?.pid ?? '—'} · LID {patient?.lid ?? '—'}</div>
          <div className="text-zinc-400 text-xs mt-1">
            Ward: {lr?.ward ?? 'Emergency'} · Doctor: {lr?.doctor_name ?? 'Dr. Kayitesi'}
          </div>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-2 text-[11px] text-zinc-400">
          {(testChips.length > 0 ? testChips : ['CBC', 'CRP', 'Glucose']).slice(0, 6).map((c, i) => (
            <div key={`${c}-${i}`} className="rounded border border-zinc-700 bg-zinc-950 p-2 font-mono text-center">{c}</div>
          ))}
        </div>
      </div>

      <div
        data-train="status"
        className={withHighlight(highlight, '[data-train="status"]',
          'md:col-span-2 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 text-xs text-zinc-300 transition-all duration-300')}
      >
        Workflow status: <span className="text-zinc-100 font-medium">
          {results.length > 0
            ? `${results.length} ordered tests · awaiting label print`
            : 'Specimen registered, awaiting label print'}
        </span>
      </div>
    </section>
  )
}
