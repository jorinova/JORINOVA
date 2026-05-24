'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '../contexts/AuthProvider'
import Logo from '../components/Logo'
import { landingPathFor } from '../lib/role-routes'

const NEXUS_BLUE   = '#0066CC'        // clear corporate blue (header / footer / accents)
const NEXUS_BLUE_LT= '#E6F0FA'        // tinted blue background for the body
const MIL_GREEN    = '#4B5320'        // military / olive drab (welcome heading)
const MIL_GREEN_DK = '#3A4019'
const GOLD         = '#D4A017'        // golden yellow (tagline)
const GOLD_DK      = '#A6800F'

type Lang = 'en' | 'fr' | 'rw'

const STRINGS: Record<Lang, {
  welcome: string; tagline: string; pqc: string;
  user: string; pwd: string; signIn: string; signingIn: string;
  forgot: string; helpFooter: string; powered: string;
  online: string; offline: string;
}> = {
  en: {
    welcome:    'WELCOME TO JORINOVA NEXUS ALIS-X',
    tagline:    'Smart data. Safer health.',
    pqc:        'Post-quantum cryptography',
    user:       'Username or Email',
    pwd:        'Password',
    signIn:     'Sign in',
    signingIn:  'Signing in…',
    forgot:     'Forgot password?',
    helpFooter: 'Support: jorinovanexus@gmail.com',
    powered:    'Powered by JORINOVA NEXUS ALIS-X',
    online:     'Online',
    offline:    'Offline',
  },
  fr: {
    welcome:    'BIENVENUE À JORINOVA NEXUS ALIS-X',
    tagline:    'Données intelligentes. Santé plus sûre.',
    pqc:        'Cryptographie post-quantique',
    user:       'Nom d’utilisateur ou e-mail',
    pwd:        'Mot de passe',
    signIn:     'Se connecter',
    signingIn:  'Connexion…',
    forgot:     'Mot de passe oublié ?',
    helpFooter: 'Support : jorinovanexus@gmail.com',
    powered:    'Propulsé par JORINOVA NEXUS ALIS-X',
    online:     'En ligne',
    offline:    'Hors ligne',
  },
  rw: {
    welcome:    'MURAKAZA NEZA KURI JORINOVA NEXUS ALIS-X',
    tagline:    'Amakuru y’ubwenge. Ubuzima burinzwe.',
    pqc:        'Ibanga ry’ibyuma bigezweho rya quantum',
    user:       'Izina cyangwa email',
    pwd:        'Ijambo ry’ibanga',
    signIn:     'Injira',
    signingIn:  'Kwinjira…',
    forgot:     'Wibagiwe ijambo ry’ibanga?',
    helpFooter: 'Ubufasha: jorinovanexus@gmail.com',
    powered:    'Yashyizweho na JORINOVA NEXUS ALIS-X',
    online:     'Kuri internet',
    offline:    'Nta nternet',
  },
}


export default function LoginPage() {
  // ── State ────────────────────────────────────────────────────────────────
  const [username,   setUsername]   = useState('')
  const [password,   setPassword]   = useState('')
  const [showPwd,    setShowPwd]    = useState(false)
  const [error,      setError]      = useState('')
  const [loading,    setLoading]    = useState(false)
  const [lang,       setLang]       = useState<Lang>('en')
  // SSR-safe initial values — the real values land on the client in useEffect.
  // (`new Date()` and `navigator.onLine` would otherwise cause a hydration
  // mismatch because the SSR HTML and the first client render disagree.)
  const [now,        setNow]        = useState<Date | null>(null)
  const [online,     setOnline]     = useState<boolean>(true)

  const { login } = useAuth()
  const router = useRouter()
  const sp = useSearchParams()
  const idleSignout = sp?.get('reason') === 'idle'
  const t = STRINGS[lang]

  // Persist language across reloads
  useEffect(() => {
    const saved = typeof window !== 'undefined' ? (localStorage.getItem('nexus.lang') as Lang | null) : null
    if (saved && saved in STRINGS) setLang(saved)
  }, [])
  useEffect(() => { if (typeof window !== 'undefined') localStorage.setItem('nexus.lang', lang) }, [lang])

  // Live clock — ticks once per second. Set first value on mount so SSR
  // and client agree on the initial render.
  useEffect(() => {
    setNow(new Date())
    const id = window.setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  // Internet status — pure browser signal. Initial value also deferred to
  // after-mount so SSR HTML matches the first client render.
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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const tokenOut = await login(username.trim(), password)
      // Role-based redirect — doctors land on their portal, RBC officials
      // on theirs, receptionists on the LIS intake, etc.
      router.replace(landingPathFor(tokenOut.role))
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  const dateStr = now
    ? now.toLocaleDateString(
        lang === 'fr' ? 'fr-FR' : lang === 'rw' ? 'rw-RW' : 'en-GB',
        { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' },
      )
    : ''
  const timeStr = now
    ? now.toLocaleTimeString(
        lang === 'fr' ? 'fr-FR' : 'en-GB',
        { hour: '2-digit', minute: '2-digit', second: '2-digit' },
      )
    : '--:--:--'

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div
      className="min-h-screen flex flex-col"
      style={{
        background: `linear-gradient(180deg, ${NEXUS_BLUE_LT} 0%, #FFFFFF 50%, ${NEXUS_BLUE_LT} 100%)`,
      }}
    >
      {/* ── HEADER ────────────────────────────────────────────────────────── */}
      <header
        className="text-white shadow-md"
        style={{ background: `linear-gradient(90deg, ${NEXUS_BLUE} 0%, #1E88E5 100%)` }}
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 py-2 flex items-center justify-between gap-3 flex-wrap">
          {/* Logo (left — sized to fill the header edge-to-edge) */}
          <div className="flex items-center gap-3">
            <Logo size={40} className="ring-1 ring-white/40" />
            <div className="leading-tight">
              <div className="font-bold tracking-wide text-sm sm:text-base">JORINOVA NEXUS</div>
              <div className="text-[10px] sm:text-xs text-blue-100 -mt-0.5">ALIS-X · Laboratory Intelligence</div>
            </div>
          </div>

          {/* Date / time / language / status (right) */}
          <div className="flex items-center gap-3 sm:gap-4 text-xs sm:text-sm">
            <div className="hidden md:flex flex-col items-end leading-tight">
              <span className="font-mono">{timeStr}</span>
              <span className="text-blue-100">{dateStr}</span>
            </div>

            {/* Language dropdown */}
            <label className="sr-only" htmlFor="lang-select">Language</label>
            <select
              id="lang-select"
              value={lang}
              onChange={(e) => setLang(e.target.value as Lang)}
              className="rounded-md bg-white/15 hover:bg-white/25 px-2 py-1 text-sm font-medium border border-white/20 focus:outline-none focus:ring-2 focus:ring-white/60 cursor-pointer"
            >
              <option value="en" className="text-zinc-900">EN · English</option>
              <option value="fr" className="text-zinc-900">FR · Français</option>
              <option value="rw" className="text-zinc-900">RW · Kinyarwanda</option>
            </select>

            {/* Internet status */}
            <span
              className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium ${
                online
                  ? 'bg-emerald-500/20 text-emerald-50 border border-emerald-300/40'
                  : 'bg-rose-500/20 text-rose-50 border border-rose-300/40'
              }`}
              aria-live="polite"
            >
              <span className={`h-2 w-2 rounded-full ${online ? 'bg-emerald-300' : 'bg-rose-300'} ${online ? 'animate-pulse' : ''}`} />
              {online ? t.online : t.offline}
            </span>
          </div>
        </div>
      </header>

      {/* ── WELCOME BANNER ─────────────────────────────────────────────────── */}
      <section
        className="border-b"
        style={{ borderColor: `${NEXUS_BLUE}30`, background: 'rgba(255,255,255,0.55)' }}
      >
        <div className="mx-auto max-w-3xl px-4 py-8 sm:py-10 text-center space-y-3">
          <h1
            className="text-2xl sm:text-4xl font-extrabold tracking-wide"
            style={{ color: MIL_GREEN, textShadow: '0 1px 0 rgba(0,0,0,0.05)' }}
          >
            {t.welcome}
          </h1>

          {/* Tagline + PQC highlight */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <p
              className="text-xl sm:text-2xl font-extrabold italic"
              style={{
                color: GOLD_DK,
                textShadow: `0 1px 0 ${GOLD}66, 0 0 16px ${GOLD}33`,
                letterSpacing: '0.02em',
              }}
            >
              {t.tagline}
            </p>
            <span
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wider shadow-sm"
              style={{
                background:
                  'linear-gradient(135deg, rgba(75,83,32,0.10) 0%, rgba(75,83,32,0.18) 100%)',
                color: MIL_GREEN_DK,
                border: `1px solid ${MIL_GREEN}40`,
              }}
              title="Cryptographic signatures and authentication are quantum-resistant"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <path d="M9 12l2 2 4-4" />
              </svg>
              {t.pqc}
            </span>
          </div>
        </div>
      </section>

      {/* ── LOGIN FORM (main) ──────────────────────────────────────────────── */}
      <main className="flex-1 flex items-center justify-center px-4 py-10">
        <div
          className="w-full max-w-sm bg-white rounded-2xl shadow-xl p-7"
          style={{ border: `2px solid ${NEXUS_BLUE}`, boxShadow: `0 12px 40px ${NEXUS_BLUE}33` }}
        >
          <form onSubmit={handleSubmit} className="space-y-5" noValidate>
            {idleSignout && !error && (
              <div className="rounded-lg bg-amber-50 border border-amber-300 px-3 py-2.5 text-sm text-amber-800">
                Session ended after 5 minutes of inactivity. Sign in again to continue.
              </div>
            )}
            {error && (
              <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2.5 text-sm text-red-700">
                {error}
              </div>
            )}

            <div>
              <label htmlFor="username" className="block text-sm font-medium text-zinc-700 mb-1">
                {t.user}
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
                autoComplete="username"
                className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2.5 text-sm text-zinc-900 outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-zinc-700 mb-1">
                {t.pwd}
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPwd ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  className="w-full rounded-lg border border-zinc-300 bg-white pl-3 pr-10 py-2.5 text-sm text-zinc-900 outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  type="button"
                  onClick={() => setShowPwd(s => !s)}
                  aria-label={showPwd ? 'Hide password' : 'Show password'}
                  className="absolute inset-y-0 right-2 px-1.5 text-xs text-zinc-500 hover:text-zinc-800"
                >
                  {showPwd ? '🙈' : '👁'}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !username || !password}
              className="w-full rounded-lg text-white font-semibold text-sm py-2.5 transition-colors shadow-sm hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ background: loading ? '#6B7280' : NEXUS_BLUE }}
              onMouseEnter={(e) => { if (!loading) e.currentTarget.style.background = '#0052A6' }}
              onMouseLeave={(e) => { if (!loading) e.currentTarget.style.background = NEXUS_BLUE }}
            >
              {loading ? t.signingIn : t.signIn}
            </button>

            <div className="flex justify-center">
              <Link
                href="/forgot-password"
                className="text-sm font-medium hover:underline"
                style={{ color: NEXUS_BLUE }}
              >
                {t.forgot}
              </Link>
            </div>
          </form>
        </div>
      </main>

      {/* ── FOOTER ─────────────────────────────────────────────────────────── */}
      <footer
        className="text-white"
        style={{ background: `linear-gradient(90deg, ${NEXUS_BLUE} 0%, #1565C0 100%)` }}
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 py-3 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs sm:text-sm">
          <a
            href="mailto:jorinovanexus@gmail.com"
            className="hover:underline font-medium"
          >
            jorinovanexus@gmail.com
          </a>
          <span className="text-blue-100">{t.powered}</span>
        </div>
      </footer>
    </div>
  )
}
