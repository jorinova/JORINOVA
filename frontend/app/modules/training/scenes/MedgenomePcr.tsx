'use client'

import type { SceneProps } from './types'
import { withHighlight } from './types'
import NoPilotData from './_NoPilotData'

/**
 * Scene: medgenome_pcr
 * Used by: `medgenome_pcr_demo` scenario.
 * DOM contract:
 *   [data-train="pcr-card"]
 *   [data-train="ct-value"]
 *   [data-train="resistance"]
 *   [data-train="interpret-btn"]
 *   [data-train="route-btn"]
 */
export default function MedgenomePcr({ highlight, liveData }: SceneProps) {
  if (!liveData?.pcr_result) {
    return <NoPilotData entity="PCRResult (TB GeneXpert)"
      hint="Run a TB GeneXpert MTB/RIF Ultra test through the Molecular module. This scene will bind to the next result." />
  }
  const pcr     = liveData.pcr_result
  const patient = liveData.patient

  const result   = pcr?.result ?? 'DETECTED'
  const ct       = pcr?.ct_value ?? 22.4
  const semi     = pcr?.semi_quant ?? 'MEDIUM'
  const rifR     = pcr?.rifampicin_resistance ?? 'NOT_DETECTED'
  const markers  = pcr?.resistance_markers as Record<string, string> | null | undefined

  const resTone = result === 'DETECTED'
    ? 'border-rose-500/40 bg-rose-500/15 text-rose-200'
    : result === 'NOT_DETECTED'
      ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-200'
      : 'border-amber-500/40 bg-amber-500/15 text-amber-200'

  const rifTone = rifR === 'DETECTED'
    ? 'border-rose-500/40 bg-rose-500/15 text-rose-200'
    : rifR === 'NOT_DETECTED'
      ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-200'
      : 'border-zinc-700 bg-zinc-950 text-zinc-400'

  return (
    <section className="grid gap-4 md:grid-cols-2">
      <div
        data-train="pcr-card"
        className={withHighlight(highlight, '[data-train="pcr-card"]',
          'rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 space-y-3 transition-all duration-300')}
      >
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-zinc-200">PCR run</h3>
          {liveData?.pcr_result && (
            <span className="text-[10px] px-2 py-0.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-200">
              live · pilot data
            </span>
          )}
        </div>
        <div className="text-sm text-zinc-100 font-mono">{pcr?.pcr_id ?? 'PCR-2026-0001'}</div>
        <div className="text-xs text-zinc-400">
          {pcr?.test_name ?? 'GeneXpert MTB/RIF Ultra'} · {pcr?.target_organism ?? 'Mycobacterium tuberculosis'}
        </div>
        <div className="grid grid-cols-2 gap-2 text-[11px]">
          <Kv label="Instrument" v={pcr?.instrument     ?? 'GeneXpert'} />
          <Kv label="Cartridge"  v={pcr?.cartridge_type ?? 'Ultra'} />
          <Kv label="Category"   v={pcr?.category       ?? 'TB'} />
          <Kv label="Patient"    v={patient ? `${patient.family_name ?? '—'} (${patient.age_band ?? '—'})` : 'unbound'} />
        </div>
        <div className={`inline-block text-xs px-3 py-1 rounded border font-medium ${resTone}`}>
          Result: {result}
        </div>
      </div>

      <div className="space-y-3">
        <div
          data-train="ct-value"
          className={withHighlight(highlight, '[data-train="ct-value"]',
            'rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 space-y-2 transition-all duration-300')}
        >
          <h3 className="text-sm font-medium text-zinc-200">Ct value &amp; semi-quant</h3>
          <div className="flex items-baseline gap-3">
            <span className="text-3xl font-mono text-zinc-100">{ct.toFixed(1)}</span>
            <span className="text-xs text-zinc-500">Ct</span>
            <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 text-indigo-200">
              {semi}
            </span>
          </div>
          <div className="text-[11px] text-zinc-500">
            Ct &lt; 16: very high · 16-22: high · 22-28: medium · &gt; 28: low. Lower Ct ⇒ higher bacillary load.
          </div>
        </div>

        <div
          data-train="resistance"
          className={withHighlight(highlight, '[data-train="resistance"]',
            'rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 space-y-2 transition-all duration-300')}
        >
          <h3 className="text-sm font-medium text-zinc-200">Resistance markers</h3>
          <div className={`inline-block text-[11px] px-3 py-1 rounded border ${rifTone}`}>
            Rifampicin: {rifR}
          </div>
          {markers && Object.keys(markers).length > 0 && (
            <div className="grid grid-cols-4 gap-1 text-[10px]">
              {Object.entries(markers).map(([drug, state]) => (
                <div key={drug} className={`text-center rounded border px-1.5 py-1 font-mono ${
                  state === 'R' ? 'border-rose-500/40 bg-rose-500/10 text-rose-200' :
                  state === 'S' ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200' :
                  'border-zinc-700 bg-zinc-950 text-zinc-400'
                }`}>
                  {drug}: {state}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="md:col-span-2 flex flex-wrap gap-3">
        <button
          data-train="interpret-btn"
          className={withHighlight(highlight, '[data-train="interpret-btn"]',
            'rounded-md bg-indigo-500/80 px-4 py-2 text-xs font-medium hover:bg-indigo-500 transition-all duration-300')}
        >
          Run AI interpretation
        </button>
        <button
          data-train="route-btn"
          className={withHighlight(highlight, '[data-train="route-btn"]',
            'rounded-md bg-emerald-500/80 px-4 py-2 text-xs font-medium hover:bg-emerald-500 transition-all duration-300')}
        >
          Route to molecular epidemiology
        </button>
        <div className="text-[11px] text-zinc-500 ml-auto self-center">
          AI interpretation will summarise Ct + resistance call and forward to the surveillance signal pipeline.
        </div>
      </div>
    </section>
  )
}

function Kv({ label, v }: { label: string; v: string }) {
  return (
    <div className="rounded border border-zinc-700 bg-zinc-950 px-2 py-1">
      <div className="text-[9px] uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="text-zinc-100 font-mono truncate">{v}</div>
    </div>
  )
}
