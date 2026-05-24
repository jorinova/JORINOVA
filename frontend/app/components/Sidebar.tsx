'use client'

/**
 * Sidebar — role-filtered persistent navigation.
 *
 * Sits to the left of every authenticated page. The whole roster lives in
 * NAV_ITEMS below; the visible subset is derived from the user's role via
 * roleCan(). Two modes:
 *
 *   - desktop (md+):  240 px column, always visible
 *   - mobile:         hidden by default; toggled by a hamburger button
 *                     in AppShell's header (passed via the `open` prop)
 *
 * The active route is highlighted by matching the URL prefix so deep
 * pages like /modules/training/medgenome_pcr_demo still light up
 * "Training" in the sidebar.
 */

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { roleCan } from '../lib/role-routes'

type NavItem = {
  href:    string
  icon:    string
  label:   string
  roles:   readonly string[]      // ['*'] = everyone
  group?:  string                  // optional section header
}

const NAV: readonly NavItem[] = [
  // ── Main ────────────────────────────────────────────────────────────────
  { href: '/dashboard',             icon: '🏠', label: 'Dashboard',     roles: ['*'], group: 'Main' },
  { href: '/modules/patients',      icon: '👤', label: 'Patients',      roles: ['*'], group: 'Main' },
  { href: '/modules/laboratory',    icon: '🧪', label: 'Laboratory',    roles: ['lab_manager', 'scientist', 'lab_technician', 'pathologist', 'super_admin'], group: 'Main' },

  // ── Clinical ────────────────────────────────────────────────────────────
  { href: '/modules/lis_mapping',   icon: '📄', label: 'OCR + LIS',     roles: ['*'], group: 'Clinical' },
  { href: '/modules/blood_bank',    icon: '🩸', label: 'Blood Bank',    roles: ['lab_manager', 'scientist', 'super_admin'], group: 'Clinical' },
  { href: '/modules/billing',       icon: '💳', label: 'Billing & MoMo',roles: ['receptionist', 'lab_manager', 'super_admin'], group: 'Clinical' },
  { href: '/modules/inventory',     icon: '📦', label: 'Inventory',     roles: ['lab_manager', 'super_admin'], group: 'Clinical' },

  // ── Portals ─────────────────────────────────────────────────────────────
  { href: '/portal/doctor',         icon: '🩺', label: 'Doctor portal', roles: ['doctor', 'lab_manager', 'super_admin'], group: 'Portals' },
  { href: '/portal/rbc',            icon: '🏛️', label: 'RBC surveillance', roles: ['rbc_admin', 'super_admin'], group: 'Portals' },

  // ── Support ─────────────────────────────────────────────────────────────
  { href: '/modules/help-support',  icon: '🎓', label: 'Help & Support',roles: ['*'], group: 'Support' },
  { href: '/modules/notifications', icon: '🔔', label: 'Notifications', roles: ['*'], group: 'Support' },

  // ── Admin ───────────────────────────────────────────────────────────────
  { href: '/modules/audit',         icon: '📋', label: 'Audit',         roles: ['lab_manager', 'super_admin'], group: 'Admin' },
  { href: '/modules/ai_nexus',      icon: '🤖', label: 'AI Nexus',      roles: ['lab_manager', 'super_admin'], group: 'Admin' },
] as const

const NEXUS_BLUE = '#0066CC'

export default function Sidebar({
  role,
  open,
  onItemClick,
  theme = 'light',
}: {
  role:          string | null | undefined
  open:          boolean
  onItemClick?:  () => void
  theme?:        'light' | 'dark'
}) {
  const pathname = usePathname()

  const visible = NAV.filter(item => roleCan(role, item.roles))
  const groups: string[] = Array.from(new Set(visible.map(i => i.group ?? 'Other')))

  const dark = theme === 'dark'

  return (
    <aside
      className={`
        ${open ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
        fixed md:static inset-y-0 left-0 z-30
        w-60 shrink-0 transition-transform
        flex flex-col
        border-r
      `}
      style={{
        background: dark ? '#020817ee' : '#FFFFFFE6',
        borderColor: dark ? 'rgba(56,189,248,0.18)' : `${NEXUS_BLUE}25`,
        backdropFilter: 'blur(8px)',
      }}
      aria-label="Primary navigation"
    >
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
        {groups.map(g => {
          const items = visible.filter(i => (i.group ?? 'Other') === g)
          return (
            <div key={g}>
              <div className={`px-2 mb-1.5 text-[10px] uppercase tracking-widest font-semibold ${dark ? 'text-slate-400' : 'text-zinc-500'}`}>
                {g}
              </div>
              <ul className="space-y-0.5">
                {items.map(item => {
                  const active = pathname === item.href || pathname?.startsWith(item.href + '/')
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        onClick={onItemClick}
                        className={`
                          flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm
                          transition-colors
                          ${active
                            ? (dark
                                ? 'bg-sky-500/15 text-sky-200 border border-sky-400/30'
                                : 'bg-blue-50 text-blue-700 border border-blue-200')
                            : (dark
                                ? 'text-slate-300 hover:bg-slate-800/60 border border-transparent'
                                : 'text-zinc-700 hover:bg-zinc-100 border border-transparent')
                          }
                        `}
                      >
                        <span className="text-base leading-none">{item.icon}</span>
                        <span className="truncate">{item.label}</span>
                      </Link>
                    </li>
                  )
                })}
              </ul>
            </div>
          )
        })}
      </nav>

      <div className={`px-3 py-3 text-[10px] border-t ${dark ? 'text-slate-500 border-slate-800' : 'text-zinc-400 border-zinc-200'}`}>
        Role: <span className={`font-mono ${dark ? 'text-slate-300' : 'text-zinc-700'}`}>{role ?? 'guest'}</span>
      </div>
    </aside>
  )
}
