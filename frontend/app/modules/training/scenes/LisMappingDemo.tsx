'use client'

import type { SceneProps } from './types'
import { withHighlight } from './types'
import NoPilotData from './_NoPilotData'

/**
 * Scene: lis_mapping_demo
 * Used by: `lis_mapping_walkthrough` scenario.
 * DOM contract:
 *   [data-train="dropzone"]
 *   [data-train="extract-btn"]
 *   [data-train="draft"]
 *   [data-train="confirm-btn"]
 *   [data-train="result"]
 */
// Catalog ids → short labels for the displayed chips. The ids match the
// pilot DB rows (see `test_catalog` table). If a test isn't in this map,
// the chip still renders as "T-<id>".
const TEST_CODE: Record<number, string> = {
  1: 'HGB', 2: 'RBC', 3: 'WBC', 4: 'PLT', 5: 'HCT',
  6: 'MCV', 7: 'MCH', 8: 'MCHC', 9: 'RDW',
  17: 'ESR', 34: 'CREAT',
}

export default function LisMappingDemo({ highlight, liveData }: SceneProps) {
  if (!liveData?.lab_request) {
    return <NoPilotData entity="LabRequest created by LIS auto-mapping"
      hint="Upload a real lab-request form through the LIS Mapping module. This scene will bind to the resulting LabRequest automatically." />
  }
  const lr      = liveData.lab_request
  const patient = liveData.patient
  const results = liveData.results ?? []

  const chips = results.map(r => r.test_id ? (TEST_CODE[r.test_id] ?? `T-${r.test_id}`) : '?')

  const formName = lr ? `request_form_${lr.lab_id}.pdf` : 'request_form_uwineza.pdf'
  const patientLine = patient
    ? `${patient.family_name ?? '—'}${patient.gender ? ` · ${patient.gender}` : ''}${patient.age_band ? ` · age ${patient.age_band}` : ''}`
    : 'Mary Uwineza · F · DOB 1990-06-03'
  const wardLine = lr
    ? `PID ${patient?.pid ?? '—'} · ${lr.ward ?? '—'} · ${lr.doctor_name ?? '—'}`
    : 'PID P-20260512-9999 · Maternity · Dr. Kayitesi'

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-zinc-200">LIS Auto-Mapping demo</h3>
        {liveData && (
          <span className="text-[10px] px-2 py-0.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-200">
            live · pilot data
          </span>
        )}
      </div>

      <div
        data-train="dropzone"
        className={withHighlight(highlight, '[data-train="dropzone"]',
          'rounded-xl border border-dashed border-zinc-700 bg-zinc-900/40 px-6 py-8 text-center transition-all duration-300')}
      >
        <div className="text-sm text-zinc-300">{formName}</div>
        <div className="text-xs text-zinc-500 mt-1">62 KB · application/pdf</div>
      </div>

      <div className="flex justify-end">
        <button
          data-train="extract-btn"
          className={withHighlight(highlight, '[data-train="extract-btn"]',
            'rounded-md bg-indigo-500/80 px-4 py-2 text-xs font-medium transition-all duration-300')}
        >
          Extract draft
        </button>
      </div>

      <div
        data-train="draft"
        className={withHighlight(highlight, '[data-train="draft"]',
          'rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 grid gap-4 md:grid-cols-2 transition-all duration-300')}
      >
        <div>
          <div className="text-xs uppercase tracking-wide text-zinc-500 mb-2">Patient</div>
          <div className="text-sm text-zinc-100">{patientLine}</div>
          <div className="text-xs text-zinc-400 mt-1">{wardLine}</div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wide text-zinc-500 mb-2">
            Tests ({chips.length || 14} matched)
          </div>
          <div className="grid grid-cols-3 gap-1 text-[11px] text-zinc-300">
            {(chips.length > 0
              ? chips
              : ['HGB','RBC','WBC','PLT','HCT','MCV','MCH','MCHC','RDW','ESR','RBG','CREAT','HIV','HBSAG']
            ).map((c, i) => (
              <div key={`${c}-${i}`} className="rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 font-mono text-emerald-200">
                {c}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="flex justify-between items-center">
        <div
          data-train="result"
          className={withHighlight(highlight, '[data-train="result"]',
            'text-xs text-zinc-400 transition-all duration-300')}
        >
          {lr ? `Bound to ${lr.lab_id} — awaiting confirmation` : 'Awaiting confirmation'}
        </div>
        <button
          data-train="confirm-btn"
          className={withHighlight(highlight, '[data-train="confirm-btn"]',
            'rounded-md bg-emerald-500/80 px-4 py-2 text-xs font-medium transition-all duration-300')}
        >
          Create LabRequest
        </button>
      </div>
    </section>
  )
}
