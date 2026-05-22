'use client'

/**
 * AppShell — the single header + footer chrome shared by every
 * authenticated page in the system (dashboard, modules, training, etc.).
 *
 * Same visual language as the login / forgot-password pages so a user
 * never sees a regime change between sign-in and the app: clear-blue
 * gradient header on top, soft-blue tinted body, clear-blue footer.
 *
 * What lives in the header:
 *   - Logo (left, clickable -> dashboard)
 *   - Brand text + role chip
 *   - Live clock + locale-aware date
 *   - Internet status pill
 *   - User name + email + Avatar
 *   - Sign-out button
 *
 * Page content is rendered between header and footer via children.
 */

import { ReactNode, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '../contexts/AuthProvider'
import Logo from './Logo'
import Avatar from './Avatar'

const NEXUS_BLUE    = '#0066CC'
const NEXUS_BLUE_LT = '#E6F0FA'

export default function AppShell({
  children,
  /** Optional kicker shown next to the brand, e.g. "Laboratory" on a sub-page. */
  pageTag,
}: {
  children: ReactNode
  pageTag?: string
}) {
  const { user, logout } = useAuth()
  const router = useRouter()

  // SSR-safe live data (no hydration mismatch)
  const [now,    setNow]    = useState<Date | null>(null)
  const [online, setOnline] = useState<boolean>(true)
  useEffect(() => {
    setNow(new Date())
    const id = window.setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  useEffect(() => {
    setOnline(navigator.onLine)
    const up   = () => setOnline(true)
    const down = () => setOnline(false)
    window.addEventListener('online',  up)
    window.addEventListener('offline', down)
    return () => {
      window.removeEventListener('online',  up)
      window.removeEventListener('offline', down)
    }
  }, [])

  const lang = (user?.preferred_language ?? 'en') as 'en' | 'fr' | 'rw'
  const dateStr = now
    ? now.toLocaleDateString(lang === 'fr' ? 'fr-FR' : 'en-GB',
        { day: '2-digit', month: 'short', year: 'numeric' })
    : ''
  const timeStr = now
    ? now.toLocaleTimeString(lang === 'fr' ? 'fr-FR' : 'en-GB',
        { hour: '2-digit', minute: '2-digit' })
    : '--:--'

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ background: `linear-gradient(180deg, ${NEXUS_BLUE_LT} 0%, #FFFFFF 50%, ${NEXUS_BLUE_LT} 100%)` }}
    >
      {/* ── HEADER ─────────────────────────────────────────────────────────── */}
      <header
        className="text-white shadow-md"
        style={{ background: `linear-gradient(90deg, ${NEXUS_BLUE} 0%, #1E88E5 100%)` }}
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 py-2 flex items-center justify-between gap-3 flex-wrap">
          {/* Left: logo + brand */}
          <Link href="/dashboard" className="flex items-center gap-3 hover:opacity-90 transition-opacity">
            <Logo size={40} className="ring-1 ring-white/40" />
            <div className="leading-tight">
              <div className="font-bold tracking-wide text-sm sm:text-base">JORINOVA NEXUS</div>
              <div className="text-[10px] sm:text-xs text-blue-100 -mt-0.5">
                ALIS-X{pageTag ? ` · ${pageTag}` : ' · Laboratory Intelligence'}
              </div>
            </div>
          </Link>

          {/* Right: clock + online + user */}
          <div className="flex items-center gap-3 sm:gap-4 text-xs sm:text-sm">
            <div className="hidden md:flex flex-col items-end leading-tight">
              <span className="font-mono">{timeStr}</span>
              <span className="text-blue-100 text-[11px]">{dateStr}</span>
            </div>
            <span
              className={`hidden sm:inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium ${
                online
                  ? 'bg-emerald-500/20 text-emerald-50 border border-emerald-300/40'
                  : 'bg-rose-500/20 text-rose-50 border border-rose-300/40'
              }`}
            >
              <span className={`h-2 w-2 rounded-full ${online ? 'bg-emerald-300 animate-pulse' : 'bg-rose-300'}`} />
              {online ? 'Online' : 'Offline'}
            </span>

            {user && (
              <>
                <div className="hidden sm:block text-right leading-tight">
                  <div className="text-xs font-semibold">{user.full_name || user.username}</div>
                  <div className="text-[10px] text-blue-100">{user.role.replace('_', ' ')}</div>
                </div>
                <Avatar src={user.photo_url} name={user.full_name || user.username} size={36} />
                <button
                  onClick={() => { logout(); router.push('/login') }}
                  title="Sign out"
                  className="text-xs px-2.5 py-1.5 rounded-md bg-white/10 hover:bg-white/25 border border-white/30 transition-colors"
                >
                  ⎋
                </button>
              </>
            )}
          </div>
        </div>
      </header>

      {/* ── BODY ───────────────────────────────────────────────────────────── */}
      <main className="flex-1 w-full">
        {children}
      </main>

      {/* ── FOOTER ─────────────────────────────────────────────────────────── */}
      <footer
        className="text-white"
        style={{ background: `linear-gradient(90deg, ${NEXUS_BLUE} 0%, #1565C0 100%)` }}
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 py-3 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs sm:text-sm">
          <a href="mailto:jorinovanexus@gmail.com" className="hover:underline font-medium">
            jorinovanexus@gmail.com
          </a>
          <span className="text-blue-100">Powered by JORINOVA NEXUS ALIS-X</span>
        </div>
      </footer>
    </div>
  )
}
