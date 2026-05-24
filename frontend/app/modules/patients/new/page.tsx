'use client'

/**
 * Walk-in patient registration.
 *
 * When to use: only for patients who arrive WITHOUT going through the
 * normal reception workflow (the OCR + LIS auto-mapping route is the
 * standard path — it registers the patient as a side effect). This
 * screen is the manual fallback: walk-in, emergency, paper-only sites.
 *
 * Flow:
 *   1. Type minimum identifiers
 *   2. Click 'Check for duplicates' → POST /api/v1/patients/check-duplicate
 *   3. If duplicates: show them, let the user pick "use this one" or "continue anyway"
 *   4. Submit → POST /api/v1/patients/  → returns the new patient with PID + LID
 *   5. Land on the patient roster with the new patient highlighted.
 */

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import RequireAuth from '../../../components/RequireAuth'
import AppShell    from '../../../components/AppShell'

const API        = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const NEXUS_BLUE = '#0066CC'
const MIL_GREEN  = '#4B5320'

interface PatientOut {
  id: number; pid: string; unique_lab_id: string | null
  family_name: string; other_names: string | null
}
interface Duplicate { patient: PatientOut; match_field: string }

function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return document.cookie.split('; ').find(r => r.startsWith('access_token='))?.split('=')[1]
    ?? localStorage.getItem('access_token')
}

export default function NewPatientPage() {
  return (
    <RequireAuth>
      <AppShell pageTag="Register walk-in patient">
        <Inner />
      </AppShell>
    </RequireAuth>
  )
}

function Inner() {
  const router = useRouter()

  // Identifiers
  const [family,   setFamily]   = useState('')
  const [other,    setOther]    = useState('')
  const [gender,   setGender]   = useState<'M' | 'F' | ''>('')
  const [dob,      setDob]      = useState('')
  const [phone,    setPhone]    = useState('')
  const [email,    setEmail]    = useState('')
  const [nid,      setNid]      = useState('')
  const [bloodGrp, setBloodGrp] = useState('')
  const [address,  setAddress]  = useState('')

  // Flow state
  const [checking,   setChecking]   = useState(false)
  const [duplicates, setDuplicates] = useState<Duplicate[]>([])
  const [skipDup,    setSkipDup]    = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error,      setError]      = useState<string | null>(null)
  const [created,    setCreated]    = useState<PatientOut | null>(null)

  const canCheck = !!family.trim()

  async function checkDuplicates() {
    setError(null); setSkipDup(false); setDuplicates([])
    setChecking(true)
    try {
      const tok = getToken()
      const r = await fetch(`${API}/api/v1/patients/check-duplicate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(tok ? { Authorization: `Bearer ${tok}` } : {}),
        },
        body: JSON.stringify({
          family_name: family.trim(),
          other_names: other.trim() || null,
          date_of_birth: dob || null,
          gender: gender || null,
          national_id: nid.trim() || null,
          phone: phone.trim() || null,
        }),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const data = await r.json()
      setDuplicates(data.matches || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Duplicate check failed')
    } finally {
      setChecking(false)
    }
  }

  async function submit() {
    setError(null); setSubmitting(true)
    try {
      const tok = getToken()
      const r = await fetch(`${API}/api/v1/patients/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(tok ? { Authorization: `Bearer ${tok}` } : {}),
        },
        body: JSON.stringify({
          family_name:   family.trim(),
          other_names:   other.trim() || null,
          date_of_birth: dob || null,
          gender:        gender || null,
          blood_group:   bloodGrp || null,
          phone:         phone.trim() || null,
          email:         email.trim() || null,
          national_id:   nid.trim() || null,
          address:       address.trim() || null,
        }),
      })
      if (!r.ok) {
        const detail = await r.json().catch(() => ({}))
        throw new Error(detail.detail || `HTTP ${r.status}`)
      }
      const data: PatientOut = await r.json()
      setCreated(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Registration failed')
    } finally {
      setSubmitting(false)
    }
  }

  const needCheckFirst = duplicates.length === 0 && !skipDup
  const canSubmit = !!family.trim() && !!gender && (!needCheckFirst || skipDup) && !submitting

  return (
    <div className="mx-auto max-w-3xl px-4 sm:px-6 py-6 space-y-5">
      <header className="rounded-2xl border bg-white p-5" style={{ borderColor: `${NEXUS_BLUE}30` }}>
        <div className="text-xs uppercase tracking-wider font-semibold" style={{ color: NEXUS_BLUE }}>
          PATIENT REGISTRY · WALK-IN
        </div>
        <h1 className="text-xl sm:text-2xl font-extrabold tracking-wide mt-1" style={{ color: MIL_GREEN }}>
          REGISTER A WALK-IN PATIENT
        </h1>
        <p className="text-sm text-zinc-500 mt-1">
          Use this only when the standard OCR + LIS auto-mapping path is not available
          (paper-only site, after-hours arrival, emergency). The system auto-checks for
          duplicates by NID, phone, or name + date-of-birth before saving.
        </p>
      </header>

      {created ? (
        <section className="rounded-2xl bg-white border p-5" style={{ borderColor: '#16A34A50' }}>
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
            <div>
              <h2 className="text-base font-bold text-zinc-900">Patient registered</h2>
              <p className="text-sm text-zinc-600">
                {created.family_name} {created.other_names ?? ''} ·
                <span className="font-mono"> PID {created.pid}</span>
                {created.unique_lab_id ? <span className="font-mono"> · {created.unique_lab_id}</span> : null}
              </p>
            </div>
          </div>
          <div className="mt-5 flex gap-2">
            <Link href={`/modules/patients?pid=${created.pid}`}
                  className="px-4 py-2 rounded-lg text-white text-sm font-semibold"
                  style={{ background: NEXUS_BLUE }}>
              Open patient file
            </Link>
            <Link href="/modules/laboratory" className="px-4 py-2 rounded-lg border border-zinc-300 text-zinc-700 text-sm">
              Order a test
            </Link>
            <button onClick={() => { setCreated(null); setFamily(''); setOther(''); setDuplicates([]); setSkipDup(false); }}
                    className="px-4 py-2 rounded-lg border border-zinc-300 text-zinc-700 text-sm">
              Register another
            </button>
          </div>
        </section>
      ) : (
        <section className="rounded-2xl bg-white border p-5 shadow-sm" style={{ borderColor: `${NEXUS_BLUE}30` }}>
          {error && (
            <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-3 py-2.5 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <Input label="Family name *" value={family} onChange={setFamily} />
              <Input label="Other names"   value={other}  onChange={setOther} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Select label="Gender *" value={gender} onChange={v => setGender(v as 'M' | 'F' | '')}
                      options={[{v:'',  l:'—'}, {v:'M', l:'Male'}, {v:'F', l:'Female'}]} />
              <Input  label="Date of birth" type="date" value={dob} onChange={setDob} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Input label="Phone"        value={phone} onChange={setPhone} placeholder="+250788123456" />
              <Input label="Email"        value={email} onChange={setEmail} type="email" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Input label="National ID"  value={nid} onChange={setNid} />
              <Select label="Blood group" value={bloodGrp} onChange={setBloodGrp}
                      options={[{v:'',l:'—'},'O+','O-','A+','A-','B+','B-','AB+','AB-'].map(o => typeof o === 'string' ? {v:o,l:o} : o)} />
            </div>
            <Input label="Address (district / village)" value={address} onChange={setAddress} />
          </div>

          {/* Duplicate check */}
          <div className="mt-5">
            {duplicates.length > 0 && (
              <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 px-3 py-3 text-sm">
                <div className="font-semibold text-amber-800 mb-1">
                  Possible duplicate{duplicates.length > 1 ? 's' : ''} ({duplicates.length}):
                </div>
                <ul className="space-y-1">
                  {duplicates.map((d, i) => (
                    <li key={i} className="text-amber-900">
                      • <span className="font-semibold">{d.patient.family_name} {d.patient.other_names ?? ''}</span>
                      <span className="font-mono"> · PID {d.patient.pid}</span>
                      <span className="text-amber-700"> · matched on {d.match_field}</span>
                    </li>
                  ))}
                </ul>
                <div className="mt-3 flex gap-3 items-center">
                  <Link href={`/modules/patients?pid=${duplicates[0].patient.pid}`}
                        className="text-sm font-semibold underline text-blue-700">
                    Use existing patient
                  </Link>
                  <label className="text-xs flex items-center gap-1.5 text-amber-800">
                    <input type="checkbox" checked={skipDup} onChange={e => setSkipDup(e.target.checked)} />
                    No, this is a different person — register anyway
                  </label>
                </div>
              </div>
            )}

            <div className="flex items-center justify-between">
              <Link href="/modules/patients" className="text-sm text-zinc-600 hover:underline">
                ← Back to roster
              </Link>
              <div className="flex gap-2">
                <button onClick={checkDuplicates} disabled={!canCheck || checking}
                        className="px-4 py-2 rounded-lg border border-zinc-300 text-sm font-medium disabled:opacity-50">
                  {checking ? 'Checking…' : 'Check duplicates'}
                </button>
                <button onClick={submit} disabled={!canSubmit}
                        className="px-5 py-2 rounded-lg text-white font-semibold text-sm shadow-sm disabled:opacity-50"
                        style={{ background: NEXUS_BLUE }}>
                  {submitting ? 'Saving…' : 'Register'}
                </button>
              </div>
            </div>
            <p className="text-[11px] text-zinc-500 mt-2 text-right">
              {needCheckFirst ? 'Run "Check duplicates" first, or tick the override above.' : 'Ready to register.'}
            </p>
          </div>
        </section>
      )}
    </div>
  )
}


function Input({
  label, value, onChange, type = 'text', placeholder,
}: { label: string; value: string; onChange: (v: string) => void; type?: string; placeholder?: string }) {
  return (
    <label className="block">
      <span className="block text-xs font-medium text-zinc-700 mb-1">{label}</span>
      <input
        type={type} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
        className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:ring-2 focus:ring-blue-500"
      />
    </label>
  )
}

function Select({
  label, value, onChange, options,
}: { label: string; value: string; onChange: (v: string) => void; options: { v: string; l: string }[] }) {
  return (
    <label className="block">
      <span className="block text-xs font-medium text-zinc-700 mb-1">{label}</span>
      <select
        value={value} onChange={e => onChange(e.target.value)}
        className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:ring-2 focus:ring-blue-500"
      >
        {options.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
      </select>
    </label>
  )
}
