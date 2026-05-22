'use client'

import { useState } from 'react'
import { useAuth } from '../contexts/AuthProvider'
import { useRouter } from 'next/navigation'
import RequireAuth from '../components/RequireAuth'
import Avatar from '../components/Avatar'
import Logo from '../components/Logo'

interface RoutingDecision {
  multi_dept: boolean
  tests: Array<{ id: string; name: string; department: string }>
  departments: string[]
  message?: string
  sample_id: string
}

const MODULES = [
  { key: 'dashboard', label: 'Dashboard', icon: '🏠', desc: 'System overview & KPIs' },
  { key: 'patients', label: 'Patients', icon: '👤', desc: 'Patient registry & history' },
  { key: 'laboratory', label: 'Laboratory', icon: '🧪', desc: 'Results & worklists' },
  { key: 'ai_nexus', label: 'AI Nexus', icon: '🤖', desc: 'Hybrid AI assistant' },
  { key: 'billing', label: 'Billing', icon: '💳', desc: 'Invoices & insurance' },
  { key: 'inventory', label: 'Inventory', icon: '📦', desc: 'Stock & reorder' },
  { key: 'notifications', label: 'Notifications', icon: '🔔', desc: 'Alerts & SMS' },
  { key: 'audit', label: 'Audit', icon: '📋', desc: 'Compliance & logs' },
] as const

export default function DashboardPage() {
  const { user, logout } = useAuth()
  const router = useRouter()
  const [scanId, setScanId] = useState('')
  const [isScanning, setIsScanning] = useState(false)
  const [routingDecision, setRoutingDecision] = useState<RoutingDecision | null>(null)

  const handleScan = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!scanId) return

    setIsScanning(true)
    try {
      const res = await fetch(`/api/routing/scan/${scanId}`, { method: 'POST' })
      const data = await res.json()

      if (data.multi_dept) {
        setRoutingDecision({ ...data, sample_id: scanId })
      } else {
        alert(`Sample ${scanId} auto-routed successfully to ${data.departments[0]}`)
        setScanId('')
      }
    } catch (err) {
      console.error('Routing error:', err)
    } finally {
      setIsScanning(false)
    }
  }

  const confirmRouting = async (mode: 'all' | 'manual' | 'cancel') => {
    if (!routingDecision) return

    try {
      const res = await fetch(`/api/routing/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sample_id: routingDecision.sample_id, mode })
      })
      
      if (res.ok) {
        setRoutingDecision(null)
        setScanId('')
        // In production, trigger a toast notification here
      }
    } catch (err) {
      console.error('Confirmation error:', err)
    }
  }

  return (
    <RequireAuth>
      <div className="min-h-screen bg-zinc-50 dark:bg-black">
        {/* Header */}
        <header className="sticky top-0 z-10 bg-white/80 dark:bg-zinc-900/80 backdrop-blur border-b border-zinc-200 dark:border-zinc-800 px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Logo size={36} />
            <span className="text-xl font-bold text-black dark:text-white">JORINOVA NEXUS</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-200">
              {user!.role.replace('_', ' ')}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden sm:block text-right leading-tight">
              <div className="text-sm font-medium text-zinc-800 dark:text-zinc-100">{user!.full_name}</div>
              <div className="text-[11px] text-zinc-500">{user!.email}</div>
            </div>
            <Avatar src={user!.photo_url} name={user!.full_name || user!.username} size={38} />
            <button
              onClick={logout}
              className="text-xs text-red-600 hover:text-red-700 px-3 py-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-950 transition-colors"
            >
              Sign out
            </button>
          </div>
        </header>

        {/* Body */}
        <main className="max-w-6xl mx-auto px-4 py-8 space-y-6">
          <div>
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">
              Welcome back, {user!.first_name}
            </h2>
            <p className="text-sm text-zinc-500">{user!.department ?? 'General'}</p>
          </div>

          {/* Sample Scan Section */}
          <section className="bg-blue-50 dark:bg-blue-950/20 border border-blue-100 dark:border-blue-900 rounded-xl p-6">
            <h3 className="text-sm font-bold text-blue-900 dark:text-blue-100 mb-4 flex items-center gap-2">
              <span className="text-lg">🔍</span> SMART SAMPLE ROUTING
            </h3>
            <form onSubmit={handleScan} className="flex gap-2">
              <input
                type="text"
                value={scanId}
                onChange={(e) => setScanId(e.target.value)}
                placeholder="Scan Barcode / Enter Sample ID"
                className="flex-1 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-lg px-4 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
              />
              <button
                disabled={isScanning}
                className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              >
                {isScanning ? 'Processing...' : 'Scan'}
              </button>
            </form>
          </section>

          {/* Module grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {MODULES.map((m) => (
              <button
                key={m.key}
                onClick={() => router.push(`/modules/${m.key}`)}
                className="group text-left rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 hover:shadow-md hover:border-blue-400 dark:hover:border-blue-600 transition-all"
              >
                <div className="text-2xl mb-1">{m.icon}</div>
                <div className="font-medium text-sm text-zinc-900 dark:text-zinc-50">{m.label}</div>
                <div className="text-xs text-zinc-400 mt-0.5">{m.desc}</div>
              </button>
            ))}
          </div>

          {/* Admin-only tools */}
          {user!.is_superuser && (
            <div className="rounded-xl border border-purple-200 dark:border-purple-900 bg-purple-50 dark:bg-purple-950/30 p-4 space-y-2 mt-6">
              <div className="text-xs font-semibold text-purple-700 dark:text-purple-300 uppercase tracking-wider">
                Admin
              </div>
              <button
                onClick={() => router.push('/admin/')}
                className="text-sm text-purple-800 dark:text-purple-200 hover:underline"
              >
                Admin Dashboard
              </button>
              <span className="mx-2 text-purple-400">·</span>
              <button
                onClick={() => router.push('/security/voice-training/')}
                className="text-sm text-purple-800 dark:text-purple-200 hover:underline"
              >
                Voice Biometrics
              </button>
            </div>
          )}
        </main>

        {/* Routing Decision Modal */}
        {routingDecision && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
            <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl">
              <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-50">Multi-Department Routing Decision</h3>
              <p className="text-sm text-zinc-500 mt-1">Sample <b>{routingDecision.sample_id}</b> requires intervention.</p>
              
              <div className="mt-4 space-y-2 max-h-48 overflow-y-auto border-y border-zinc-100 dark:border-zinc-800 py-3">
                {routingDecision.tests.map(test => (
                  <div key={test.id} className="flex justify-between text-xs p-2 bg-zinc-50 dark:bg-zinc-950 rounded border border-zinc-100 dark:border-zinc-800">
                    <span className="font-medium">{test.name}</span>
                    <span className="text-blue-600 dark:text-blue-400 font-bold uppercase">{test.department}</span>
                  </div>
                ))}
              </div>

              <div className="mt-6 grid grid-cols-1 gap-2">
                <button onClick={() => confirmRouting('all')} className="w-full bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700">
                  Route to All Departments
                </button>
                <button onClick={() => confirmRouting('manual')} className="w-full bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 py-2 rounded-lg text-sm font-medium">
                  Select Manually
                </button>
                <button onClick={() => confirmRouting('cancel')} className="w-full text-zinc-500 py-2 text-sm font-medium hover:text-red-500">
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </RequireAuth>
  )
}
