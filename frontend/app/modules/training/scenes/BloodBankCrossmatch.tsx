'use client'

import type { SceneProps } from './types'
import { withHighlight } from './types'
import NoPilotData from './_NoPilotData'

/**
 * Scene: blood_bank_crossmatch
 * Used by: `blood_bank_crossmatch_demo` scenario.
 * DOM contract:
 *   [data-train="bag-card"]
 *   [data-train="slot-grid"]
 *   [data-train="crossmatch-btn"]
 *   [data-train="issue-btn"]
 *   [data-train="status"]
 */
export default function BloodBankCrossmatch({ highlight, liveData }: SceneProps) {
  if (!liveData?.blood_bag) {
    return <NoPilotData entity="BloodBag"
      hint="Register a blood unit in the Blood Bank module (donor, group, slot). This scene will bind automatically." />
  }
  const bag       = liveData.blood_bag
  const xm        = liveData.crossmatch ?? null
  const recipient = liveData.recipient

  // Synthesize a chamber/slot grid keyed off the bag id so the demo looks
  // consistent on repeat runs.
  const slotKey = (bag?.id ?? 42) % 12
  const grid = Array.from({ length: 12 }, (_, i) => ({
    label: `S-${(i + 1).toString().padStart(2, '0')}`,
    occupied: i === slotKey ? 'this' : (i % 3 === 0 ? 'other' : 'empty'),
  }))

  const expiryTone = bag?.expiry_status === 'critical'
    ? 'border-rose-500/40 bg-rose-500/15 text-rose-200'
    : bag?.expiry_status === 'warning'
      ? 'border-amber-500/40 bg-amber-500/15 text-amber-200'
      : 'border-emerald-500/40 bg-emerald-500/15 text-emerald-200'

  const xmTone = xm?.result === 'compatible'
    ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-200'
    : xm?.result === 'incompatible'
      ? 'border-rose-500/40 bg-rose-500/15 text-rose-200'
      : 'border-zinc-700 bg-zinc-800 text-zinc-300'

  return (
    <section className="grid gap-4 md:grid-cols-2">
      <div
        data-train="bag-card"
        className={withHighlight(highlight, '[data-train="bag-card"]',
          'rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 space-y-3 transition-all duration-300')}
      >
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-zinc-200">Blood bag</h3>
          {liveData?.blood_bag && (
            <span className="text-[10px] px-2 py-0.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-200">
              live · pilot data
            </span>
          )}
        </div>
        <div className="text-sm font-mono text-zinc-100">
          {bag?.bag_number ?? 'BB-2026-001'}
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <Kv label="Group"     v={bag?.blood_group ?? 'O+'} />
          <Kv label="Component" v={bag?.component   ?? 'PRBC'} />
          <Kv label="Volume"    v={`${bag?.volume_ml ?? 450} mL`} />
          <Kv label="Status"    v={bag?.status ?? 'available'} />
          <Kv label="Irradiated"   v={bag?.is_irradiated   ? 'yes' : 'no'} />
          <Kv label="Leukoreduced" v={bag?.is_leukoreduced ? 'yes' : 'no'} />
        </div>
        {bag?.expiry_date && (
          <div className={`inline-block text-[10px] px-2 py-0.5 rounded-full border ${expiryTone}`}>
            Expires {bag.expiry_date} · {bag.days_to_expiry ?? 0} d ({bag.expiry_status})
          </div>
        )}
        <button
          data-train="crossmatch-btn"
          className={withHighlight(highlight, '[data-train="crossmatch-btn"]',
            'w-full rounded-lg border border-indigo-500/40 bg-indigo-500/15 px-3 py-2 text-sm hover:bg-indigo-500/25 transition-all duration-300')}
        >
          Run crossmatch (IAT)
        </button>
        {xm && (
          <div className={`text-[11px] px-2 py-1 rounded border ${xmTone}`}>
            Crossmatch {xm.result ?? 'pending'} {xm.method ? `· ${xm.method}` : ''}
          </div>
        )}
      </div>

      <div
        data-train="slot-grid"
        className={withHighlight(highlight, '[data-train="slot-grid"]',
          'rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 space-y-3 transition-all duration-300')}
      >
        <h3 className="text-sm font-medium text-zinc-200">
          Fridge F-2 · Chamber C-1 · Slot grid
        </h3>
        <div className="grid grid-cols-6 gap-1.5">
          {grid.map((s) => (
            <div
              key={s.label}
              className={`text-[10px] font-mono text-center rounded border px-1 py-2 ${
                s.occupied === 'this'
                  ? 'border-indigo-400 bg-indigo-500/25 text-indigo-100'
                  : s.occupied === 'other'
                    ? 'border-zinc-700 bg-zinc-800/60 text-zinc-400'
                    : 'border-dashed border-zinc-800 bg-zinc-950 text-zinc-600'
              }`}
            >
              {s.label}
            </div>
          ))}
        </div>
        <div className="text-[11px] text-zinc-500">
          FIFO/FEFO selected · this bag at <b className="text-zinc-300">S-{String(slotKey + 1).padStart(2, '0')}</b>
        </div>
        {recipient && (
          <div className="text-[11px] text-zinc-400 border-t border-zinc-800 pt-2">
            Crossmatch recipient: {recipient.family_name ?? '—'} ({recipient.gender ?? '—'}, {recipient.age_band ?? '—'})
          </div>
        )}
        <button
          data-train="issue-btn"
          className={withHighlight(highlight, '[data-train="issue-btn"]',
            'w-full rounded-lg border border-emerald-500/40 bg-emerald-500/15 px-3 py-2 text-sm hover:bg-emerald-500/25 transition-all duration-300')}
        >
          Issue unit (transfusion start)
        </button>
      </div>

      <div
        data-train="status"
        className={withHighlight(highlight, '[data-train="status"]',
          'md:col-span-2 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 text-xs text-zinc-300 transition-all duration-300')}
      >
        Workflow: <span className="text-zinc-100 font-medium">
          {xm?.result === 'compatible'
            ? 'Compatible — ready to issue. Haemovigilance watch armed.'
            : xm?.result === 'incompatible'
              ? 'INCOMPATIBLE — quarantine bag, escalate to senior.'
              : 'Crossmatch pending — bag held in current slot.'}
        </span>
      </div>
    </section>
  )
}

function Kv({ label, v }: { label: string; v: string }) {
  return (
    <div className="rounded border border-zinc-700 bg-zinc-950 px-2 py-1">
      <div className="text-[9px] uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="text-zinc-100 font-mono">{v}</div>
    </div>
  )
}
