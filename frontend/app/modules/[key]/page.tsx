'use client'

import { useMemo } from 'react'
import { useParams, useRouter } from 'next/navigation'
import RequireAuth from '../../components/RequireAuth'
import { useAuth } from '../../contexts/AuthProvider'

const MODULES: Record<
  string,
  { label: string; icon: string; desc: string; roles?: string[] }
> = {
  dashboard: { label: 'Dashboard', icon: '🏠', desc: 'System overview & KPIs' },
  patients: { label: 'Patients', icon: '👤', desc: 'Patient registry & history' },
  laboratory: { label: 'Laboratory', icon: '🧪', desc: 'Results & worklists' },
  ai_nexus: { label: 'AI Nexus', icon: '🤖', desc: 'Hybrid AI assistant' },
  billing: { label: 'Billing', icon: '💳', desc: 'Invoices & insurance' },
  inventory: { label: 'Inventory', icon: '📦', desc: 'Stock & reorder' },
  notifications: { label: 'Notifications', icon: '🔔', desc: 'Alerts & SMS' },
  audit: { label: 'Audit', icon: '📋', desc: 'Compliance & logs' },
}

export default function ModulePage() {
  const params = useParams<{ key: string }>()
  const router = useRouter()
  const { user } = useAuth()

  const key = params.key
  const moduleInfo = MODULES[key] ?? null

  const title = moduleInfo?.label ?? 'Module'

  const roleBadge = useMemo(() => {
    if (!user) return null
    return user.role.replaceAll('_', ' ')
  }, [user])

  return (
    <RequireAuth>
      <div className="min-h-screen bg-zinc-50 dark:bg-black">
        <header className="sticky top-0 z-10 bg-white/80 dark:bg-zinc-900/80 backdrop-blur border-b border-zinc-200 dark:border-zinc-800 px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push('/dashboard')}
              className="text-sm text-zinc-700 dark:text-zinc-200 hover:underline"
              aria-label="Back to dashboard"
            >
              ←
            </button>
            <span className="text-xl font-bold text-black dark:text-white">
              JORINOVA NEXUS
            </span>
            {roleBadge && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-200">
                {roleBadge}
              </span>
            )}
          </div>
        </header>

        <main className="max-w-3xl mx-auto px-4 py-8">
          <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-4xl">{moduleInfo?.icon ?? '🧩'}</div>
                <h1 className="mt-2 text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
                  {title}
                </h1>
                <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
                  {moduleInfo?.desc ?? 'This section will be implemented next.'}
                </p>
              </div>
            </div>

            <div className="mt-6 space-y-3">
              <div className="rounded-lg bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 p-4">
                <div className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
                  Placeholder UI
                </div>
                <div className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">
                  Start wiring module-specific pages and API endpoints here.
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    </RequireAuth>
  )
}
