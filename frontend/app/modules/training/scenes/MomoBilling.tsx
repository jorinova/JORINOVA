'use client'

import type { SceneProps } from './types'
import { withHighlight } from './types'
import NoPilotData from './_NoPilotData'

/**
 * Scene: momo_billing
 * Used by: `momo_billing_demo` scenario.
 * DOM contract:
 *   [data-train="invoice"]
 *   [data-train="momo-input"]
 *   [data-train="confirm-btn"]
 *   [data-train="receipt"]
 *   [data-train="status"]
 */
export default function MomoBilling({ typedText, highlight, liveData }: SceneProps) {
  if (!liveData?.billing_record) {
    return <NoPilotData entity="BillingRecord"
      hint="Confirm a lab bill in the Billing module (any payment method). This scene will bind to the next paid record." />
  }
  const br      = liveData.billing_record
  const items   = liveData.items ?? []
  const patient = liveData.patient

  const displayItems = items
  const total    = br.total
  const currency = br.currency
  const status   = br.status
  const paid     = br.paid
  const fullyPaid = paid >= total && total > 0
  const method = br.payment_method ?? 'MOMO'

  const typedRef = typedText['[data-train="momo-input"]'] ?? ''

  return (
    <section className="grid gap-4 md:grid-cols-2">
      <div
        data-train="invoice"
        className={withHighlight(highlight, '[data-train="invoice"]',
          'rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 space-y-3 transition-all duration-300')}
      >
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-zinc-200">Invoice</h3>
          {liveData?.billing_record && (
            <span className="text-[10px] px-2 py-0.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-200">
              live · pilot data
            </span>
          )}
        </div>
        <div className="text-xs text-zinc-400">
          {patient
            ? `Patient ${patient.family_name ?? '—'} · ${patient.gender ?? '—'} · ${patient.age_band ?? '—'}`
            : 'Patient (no live record bound)'}
        </div>
        <div className="space-y-1 text-[11px]">
          {displayItems.map((i, idx) => (
            <div key={`${i.code}-${idx}`} className="flex justify-between gap-3 border-b border-zinc-800 py-1">
              <span className="font-mono text-zinc-300 truncate">{i.code || '—'}</span>
              <span className="text-zinc-200 flex-1 truncate">{i.name}</span>
              <span className="text-zinc-100 font-mono">{i.total.toFixed(0)} {currency}</span>
            </div>
          ))}
        </div>
        <div className="flex justify-between items-center text-sm pt-2 border-t border-zinc-700">
          <span className="text-zinc-400">Total</span>
          <span className="text-zinc-100 font-mono font-medium">{total.toFixed(0)} {currency}</span>
        </div>
      </div>

      <div className="space-y-3">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 space-y-3">
          <h3 className="text-sm font-medium text-zinc-200">Mobile Money payment</h3>
          <div className="grid grid-cols-3 gap-2 text-[11px]">
            {['MTN', 'Airtel', 'Tigo'].map(p => (
              <div key={p} className={`text-center rounded border px-2 py-1.5 ${p === 'MTN' ? 'border-amber-500/40 bg-amber-500/15 text-amber-200' : 'border-zinc-700 bg-zinc-950 text-zinc-400'}`}>
                {p}
              </div>
            ))}
          </div>
          <input
            data-train="momo-input"
            readOnly
            value={typedRef}
            placeholder="MoMo reference…"
            className={withHighlight(highlight, '[data-train="momo-input"]',
              'w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm font-mono transition-all duration-300')}
          />
          <button
            data-train="confirm-btn"
            className={withHighlight(highlight, '[data-train="confirm-btn"]',
              'w-full rounded-lg border border-indigo-500/40 bg-indigo-500/15 px-3 py-2 text-sm hover:bg-indigo-500/25 transition-all duration-300')}
          >
            Confirm payment
          </button>
        </div>

        <div
          data-train="receipt"
          className={withHighlight(highlight, '[data-train="receipt"]',
            `rounded-xl border ${fullyPaid ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200' : 'border-zinc-800 bg-zinc-900/40 text-zinc-300'} p-4 text-xs space-y-1 transition-all duration-300`)}
        >
          <div className="font-medium">Receipt</div>
          <div>Method: {method}</div>
          <div>MoMo ref: <span className="font-mono">{(br?.momo_ref ?? typedRef) || '—'}</span></div>
          <div>Paid: {paid.toFixed(0)} / {total.toFixed(0)} {currency}</div>
        </div>
      </div>

      <div
        data-train="status"
        className={withHighlight(highlight, '[data-train="status"]',
          'md:col-span-2 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 text-xs text-zinc-300 transition-all duration-300')}
      >
        Worklist gate: <span className="text-zinc-100 font-medium">
          {status === 'PAID' || fullyPaid
            ? 'Bill settled. Worklist released downstream.'
            : status === 'CANCELLED'
              ? 'Bill cancelled. Worklist held.'
              : 'Bill confirmed. Awaiting MoMo payment to release worklist.'}
        </span>
      </div>
    </section>
  )
}
