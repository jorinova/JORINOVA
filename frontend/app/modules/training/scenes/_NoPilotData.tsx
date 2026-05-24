'use client'

/**
 * Empty-state shown by every scene when no real pilot record is bound.
 *
 * Production rule: the demo runs on REAL pilot data only. When the data-source
 * endpoint returns nothing (i.e. the pilot site hasn't fed records yet), we
 * do NOT make up a fake patient — we show this placeholder so the operator
 * knows the pipeline is empty and the next step is to wire up an analyzer
 * (see the IoT adapter scenario).
 */
export default function NoPilotData({
  entity, hint,
}: { entity: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-dashed border-amber-500/30 bg-amber-500/5 p-6 text-center space-y-2">
      <div className="text-sm text-amber-200 font-medium">
        Waiting for pilot data
      </div>
      <div className="text-xs text-zinc-400 max-w-md mx-auto">
        This scene anchors on a real <span className="font-mono text-zinc-200">{entity}</span>{' '}
        record from the pilot database. None is available yet.
      </div>
      <div className="text-[11px] text-zinc-500 max-w-md mx-auto">
        {hint ?? 'Wire up an analyzer through the IoT adapter, or have a clinician submit one through the LIS workflow. Once a record exists, this scene will bind to it automatically.'}
      </div>
    </div>
  )
}
