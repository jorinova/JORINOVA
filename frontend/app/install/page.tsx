'use client'

/**
 * First-run installation wizard.
 *
 * Lands here automatically the first time anyone hits the system if no
 * hospital + admin exist yet (GET /api/v1/setup/status). Four screens:
 *
 *   1. Language        — pick en/fr/rw; locked as the system default
 *   2. Hospital        — name + district + contact
 *   3. Admin account   — first user (super_admin)
 *   4. Done            — single 'Sign in' button → /login
 *
 * Calls POST /api/v1/setup/init once; the backend refuses with 409 if
 * anyone else has already initialised, so this page cannot overwrite
 * a live install.
 */

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Logo from '../components/Logo'

const API           = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const NEXUS_BLUE    = '#0066CC'
const NEXUS_BLUE_LT = '#E6F0FA'
const MIL_GREEN     = '#4B5320'
const GOLD_DK       = '#A6800F'

type Lang = 'en' | 'fr' | 'rw'
type Step = 'language' | 'hospital' | 'admin' | 'done'

const LANG_OPTIONS: { code: Lang; label: string; native: string; flag: string }[] = [
  { code: 'en', label: 'English',     native: 'English',     flag: '🇬🇧' },
  { code: 'fr', label: 'French',      native: 'Français',    flag: '🇫🇷' },
  { code: 'rw', label: 'Kinyarwanda', native: 'Ikinyarwanda',flag: '🇷🇼' },
]

const COPY: Record<Lang, {
  pickLanguage: string; pickLangSub: string;
  hospital: string; hospitalSub: string;
  hospitalName: string; district: string; province: string; phone: string; email: string;
  admin: string; adminSub: string;
  username: string; firstName: string; lastName: string; adminEmail: string; password: string;
  done: string; doneSub: string; signIn: string;
  next: string; back: string; finish: string; saving: string;
}> = {
  en: {
    pickLanguage: 'Choose system language',
    pickLangSub:  'The language you pick becomes the default for everyone signing in. Each user can override their own.',
    hospital:     'Hospital details',
    hospitalSub:  'Identifies the facility on every report, label and signed result.',
    hospitalName: 'Hospital name', district: 'District', province: 'Province', phone: 'Phone', email: 'Email',
    admin:        'First administrator account',
    adminSub:     'This user can create everyone else and is the system super-admin.',
    username:     'Username', firstName: 'First name', lastName: 'Last name', adminEmail: 'Email', password: 'Password (8+ chars)',
    done:         'Setup complete',
    doneSub:      'JORINOVA NEXUS is ready. Sign in with the credentials you just created.',
    signIn:       'Sign in',
    next: 'Continue', back: 'Back', finish: 'Create system', saving: 'Saving…',
  },
  fr: {
    pickLanguage: 'Choisissez la langue du système',
    pickLangSub:  "Cette langue devient celle par défaut à la connexion. Chaque utilisateur peut la modifier.",
    hospital:     "Informations de l'hôpital",
    hospitalSub:  'Identifie l’établissement sur chaque rapport, étiquette et résultat signé.',
    hospitalName: "Nom de l'hôpital", district: 'District', province: 'Province', phone: 'Téléphone', email: 'E-mail',
    admin:        "Compte du premier administrateur",
    adminSub:     "Ce compte peut créer tous les autres utilisateurs ; il est super-admin.",
    username:     "Nom d'utilisateur", firstName: 'Prénom', lastName: 'Nom', adminEmail: 'E-mail', password: 'Mot de passe (8+)',
    done:         'Installation terminée',
    doneSub:      'JORINOVA NEXUS est prêt. Connectez-vous avec les identifiants créés.',
    signIn:       'Se connecter',
    next: 'Continuer', back: 'Retour', finish: 'Créer le système', saving: 'Enregistrement…',
  },
  rw: {
    pickLanguage: 'Hitamo ururimi rwa sisitemu',
    pickLangSub:  'Ururimi uhise ni rwo ruzakoreshwa na buri ukoresha sisitemu.',
    hospital:     'Amakuru y’ibitaro',
    hospitalSub:  'Ibyo bitazwi ku raporo, ibimenyetso, n’ibyemezo by’ibisubizo.',
    hospitalName: 'Izina ry’ibitaro', district: 'Akarere', province: 'Intara', phone: 'Telefoni', email: 'Imeyili',
    admin:        'Konti ya mbere y’umuyobozi',
    adminSub:     'Iyi konti ishobora kurema abandi bose; ni super-admin.',
    username:     'Izina rikoreshwa', firstName: 'Izina', lastName: 'Izina ry’umuryango', adminEmail: 'Imeyili', password: 'Ijambo ry’ibanga (8+)',
    done:         'Iyinjiza ryarangiye',
    doneSub:      'JORINOVA NEXUS yiteguye. Injira ukoresheje konti uhise urema.',
    signIn:       'Injira',
    next: 'Komeza', back: 'Subira', finish: 'Rema sisitemu', saving: 'Ribika…',
  },
}


export default function InstallPage() {
  const router = useRouter()
  const [step,    setStep]    = useState<Step>('language')
  const [lang,    setLang]    = useState<Lang>('en')
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // Hospital
  const [hName, setHName] = useState('')
  const [hDist, setHDist] = useState('')
  const [hProv, setHProv] = useState('')
  const [hPhone,setHPhone] = useState('')
  const [hEmail,setHEmail] = useState('')

  // Admin
  const [aUser,  setAUser]  = useState('admin')
  const [aFirst, setAFirst] = useState('')
  const [aLast,  setALast]  = useState('')
  const [aEmail, setAEmail] = useState('')
  const [aPwd,   setAPwd]   = useState('')

  // On mount: redirect away if setup already done
  useEffect(() => {
    fetch(`${API}/api/v1/setup/status`)
      .then(r => r.json())
      .then(d => {
        if (!d.needs_setup) router.replace('/login')
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [router])

  const t = COPY[lang]

  async function submit() {
    setError(null); setSubmitting(true)
    try {
      const r = await fetch(`${API}/api/v1/setup/init`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          language:         lang,
          hospital_name:    hName.trim(),
          hospital_district:hDist.trim() || null,
          hospital_province:hProv.trim() || null,
          hospital_phone:   hPhone.trim() || null,
          hospital_email:   hEmail.trim() || null,
          admin_username:   aUser.trim(),
          admin_first_name: aFirst.trim(),
          admin_last_name:  aLast.trim(),
          admin_email:      aEmail.trim(),
          admin_password:   aPwd,
        }),
      })
      if (!r.ok) {
        const detail = await r.json().catch(() => ({}))
        throw new Error(detail.detail || `HTTP ${r.status}`)
      }
      setStep('done')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Setup failed')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center text-zinc-500">Loading…</div>
  }

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ background: `linear-gradient(180deg, ${NEXUS_BLUE_LT} 0%, #FFFFFF 50%, ${NEXUS_BLUE_LT} 100%)` }}
    >
      {/* Branded header */}
      <header
        className="text-white shadow-md"
        style={{ background: `linear-gradient(90deg, ${NEXUS_BLUE} 0%, #1E88E5 100%)` }}
      >
        <div className="mx-auto max-w-5xl px-4 sm:px-6 py-3 flex items-center gap-3">
          <Logo size={48} className="ring-1 ring-white/40" />
          <div className="leading-tight">
            <div className="font-bold tracking-wide text-base">JORINOVA NEXUS</div>
            <div className="text-xs text-blue-100 -mt-0.5">ALIS-X · First-run installation</div>
          </div>
        </div>
      </header>

      {/* Hero strip */}
      <section className="border-b" style={{ borderColor: `${NEXUS_BLUE}30`, background: 'rgba(255,255,255,0.55)' }}>
        <div className="mx-auto max-w-3xl px-4 py-6 text-center space-y-1">
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-wide" style={{ color: MIL_GREEN }}>
            WELCOME — LET’S SET UP YOUR LAB
          </h1>
          <p className="text-sm italic font-bold" style={{ color: GOLD_DK }}>
            Smart data. Safer health.
          </p>
          <ProgressDots step={step} />
        </div>
      </section>

      {/* Card */}
      <main className="flex-1 flex items-center justify-center px-4 py-10">
        <div
          className="w-full max-w-lg bg-white rounded-2xl shadow-xl p-7"
          style={{ border: `2px solid ${NEXUS_BLUE}`, boxShadow: `0 12px 40px ${NEXUS_BLUE}33` }}
        >
          {error && (
            <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-3 py-2.5 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* ── Step 1: language ── */}
          {step === 'language' && (
            <>
              <h2 className="text-lg font-bold text-zinc-900">{t.pickLanguage}</h2>
              <p className="text-sm text-zinc-500 mt-1">{t.pickLangSub}</p>
              <div className="mt-5 grid grid-cols-3 gap-3">
                {LANG_OPTIONS.map(opt => {
                  const active = opt.code === lang
                  return (
                    <button
                      key={opt.code}
                      onClick={() => setLang(opt.code)}
                      className="rounded-xl p-4 border-2 transition-all flex flex-col items-center gap-1"
                      style={{
                        borderColor: active ? NEXUS_BLUE : '#E4E4E7',
                        background:  active ? '#EFF6FF' : 'white',
                        boxShadow:   active ? `0 0 0 4px ${NEXUS_BLUE}22` : 'none',
                      }}
                    >
                      <div className="text-3xl">{opt.flag}</div>
                      <div className="text-xs font-semibold text-zinc-700">{opt.label}</div>
                      <div className="text-[11px] text-zinc-500">{opt.native}</div>
                    </button>
                  )
                })}
              </div>
              <div className="mt-6 flex justify-end">
                <button onClick={() => setStep('hospital')}
                        className="px-5 py-2.5 rounded-lg text-white font-semibold shadow-sm"
                        style={{ background: NEXUS_BLUE }}>
                  {t.next} →
                </button>
              </div>
            </>
          )}

          {/* ── Step 2: hospital ── */}
          {step === 'hospital' && (
            <>
              <h2 className="text-lg font-bold text-zinc-900">{t.hospital}</h2>
              <p className="text-sm text-zinc-500 mt-1">{t.hospitalSub}</p>
              <div className="mt-5 space-y-3">
                <Field label={t.hospitalName} value={hName} onChange={setHName} required />
                <div className="grid grid-cols-2 gap-3">
                  <Field label={t.district} value={hDist} onChange={setHDist} />
                  <Field label={t.province} value={hProv} onChange={setHProv} />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <Field label={t.phone} value={hPhone} onChange={setHPhone} />
                  <Field label={t.email} value={hEmail} onChange={setHEmail} type="email" />
                </div>
              </div>
              <div className="mt-6 flex justify-between">
                <button onClick={() => setStep('language')}
                        className="px-4 py-2 rounded-lg border border-zinc-300 text-zinc-700">
                  ← {t.back}
                </button>
                <button onClick={() => setStep('admin')} disabled={!hName.trim()}
                        className="px-5 py-2.5 rounded-lg text-white font-semibold shadow-sm disabled:opacity-50"
                        style={{ background: NEXUS_BLUE }}>
                  {t.next} →
                </button>
              </div>
            </>
          )}

          {/* ── Step 3: admin ── */}
          {step === 'admin' && (
            <>
              <h2 className="text-lg font-bold text-zinc-900">{t.admin}</h2>
              <p className="text-sm text-zinc-500 mt-1">{t.adminSub}</p>
              <div className="mt-5 space-y-3">
                <Field label={t.username} value={aUser} onChange={setAUser} required />
                <div className="grid grid-cols-2 gap-3">
                  <Field label={t.firstName} value={aFirst} onChange={setAFirst} required />
                  <Field label={t.lastName}  value={aLast}  onChange={setALast}  required />
                </div>
                <Field label={t.adminEmail} value={aEmail} onChange={setAEmail} required type="email" />
                <Field label={t.password}   value={aPwd}   onChange={setAPwd}   required type="password" />
              </div>
              <div className="mt-6 flex justify-between">
                <button onClick={() => setStep('hospital')}
                        className="px-4 py-2 rounded-lg border border-zinc-300 text-zinc-700">
                  ← {t.back}
                </button>
                <button
                  onClick={submit}
                  disabled={submitting || !aUser.trim() || !aFirst.trim() || !aLast.trim() || !aEmail.trim() || aPwd.length < 8}
                  className="px-5 py-2.5 rounded-lg text-white font-semibold shadow-sm disabled:opacity-50"
                  style={{ background: NEXUS_BLUE }}
                >
                  {submitting ? t.saving : t.finish}
                </button>
              </div>
            </>
          )}

          {/* ── Step 4: done ── */}
          {step === 'done' && (
            <div className="text-center space-y-4">
              <div className="mx-auto h-14 w-14 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center">
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </div>
              <h2 className="text-lg font-bold text-zinc-900">{t.done}</h2>
              <p className="text-sm text-zinc-600">{t.doneSub}</p>
              <button onClick={() => router.replace('/login')}
                      className="w-full px-5 py-2.5 rounded-lg text-white font-semibold shadow-sm"
                      style={{ background: NEXUS_BLUE }}>
                {t.signIn}
              </button>
            </div>
          )}
        </div>
      </main>

      <footer className="text-white" style={{ background: `linear-gradient(90deg, ${NEXUS_BLUE} 0%, #1565C0 100%)` }}>
        <div className="mx-auto max-w-7xl px-4 sm:px-6 py-3 flex items-center justify-between text-xs">
          <a href="mailto:jorinovanexus@gmail.com" className="font-medium">jorinovanexus@gmail.com</a>
          <span className="text-blue-100">Powered by JORINOVA NEXUS ALIS-X</span>
        </div>
      </footer>
    </div>
  )
}


function Field({
  label, value, onChange, required, type = 'text',
}: {
  label: string; value: string; onChange: (v: string) => void
  required?: boolean; type?: string
}) {
  return (
    <label className="block">
      <span className="block text-xs font-medium text-zinc-700 mb-1">{label}{required && ' *'}</span>
      <input
        type={type} value={value} onChange={e => onChange(e.target.value)} required={required}
        className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:ring-2 focus:ring-blue-500"
      />
    </label>
  )
}

function ProgressDots({ step }: { step: Step }) {
  const idx = { language: 0, hospital: 1, admin: 2, done: 3 }[step]
  return (
    <div className="flex items-center justify-center gap-2 pt-2">
      {[0,1,2,3].map(i => (
        <div key={i} className="h-1.5 rounded-full transition-all"
             style={{ width: i === idx ? 28 : 12, background: i <= idx ? NEXUS_BLUE : '#CBD5E1' }} />
      ))}
    </div>
  )
}
