'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import RequireAuth from '../../components/RequireAuth'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type TestMatch = {
  query:         string
  test_id:       number | null
  code:          string | null
  name:          string | null
  short_name:    string | null
  department_id: number | null
  specimen_type: string | null
  price:         number
  confidence:    number
  status:        'matched' | 'ambiguous' | 'unmatched'
}

type PatientMatch = {
  pid:           string | null
  lid:           string | null
  national_id:   string | null
  family_name:   string | null
  other_names:   string | null
  date_of_birth: string | null
  gender:        string | null
  phone:         string | null
  matched_id:    number | null
  confidence:    number
  status:        'matched' | 'candidate' | 'unmatched' | 'new'
}

type Draft = {
  patient:            PatientMatch
  tests:              TestMatch[]
  priority:           'routine' | 'urgent' | 'stat'
  department:         string | null
  specimen_type:      string | null
  doctor_name:        string | null
  ward:               string | null
  diagnosis:          string | null
  duplicate_of:       number | null
  warnings:           string[]
  text_hash:          string
  raw_text:           string
  field_confidence:   Record<string, number>
  overall_confidence: number
  source?:            string
}

function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return document.cookie
    .split('; ')
    .find((r) => r.startsWith('access_token='))
    ?.split('=')[1] ?? localStorage.getItem('access_token')
}

function confidenceTone(c: number): string {
  if (c >= 0.9) return 'bg-emerald-500/15 border-emerald-500/30 text-emerald-200'
  if (c >= 0.7) return 'bg-amber-500/15 border-amber-500/30 text-amber-200'
  return 'bg-rose-500/15 border-rose-500/30 text-rose-200'
}

function statusTone(s: string): string {
  switch (s) {
    case 'matched':   return 'bg-emerald-500/15 border-emerald-500/30 text-emerald-200'
    case 'ambiguous': return 'bg-amber-500/15 border-amber-500/30 text-amber-200'
    case 'candidate': return 'bg-amber-500/15 border-amber-500/30 text-amber-200'
    case 'new':       return 'bg-sky-500/15 border-sky-500/30 text-sky-200'
    default:          return 'bg-rose-500/15 border-rose-500/30 text-rose-200'
  }
}

export default function LisMappingPage() {
  return (
    <RequireAuth>
      <LisMappingInner />
    </RequireAuth>
  )
}

function LisMappingInner() {
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [file, setFile]       = useState<File | null>(null)
  const [mode, setMode]       = useState<'assisted' | 'auto'>('assisted')
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState<string | null>(null)
  const [draft, setDraft]     = useState<Draft | null>(null)
  const [confirmed, setConfirmed] = useState<{ lab_request_id: number; lab_id: string; patient_id: number } | null>(null)

  const onPickFile = useCallback((f: File | null) => {
    setFile(f)
    setDraft(null)
    setConfirmed(null)
    setError(null)
  }, [])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const f = e.dataTransfer.files?.[0] ?? null
    onPickFile(f)
  }, [onPickFile])

  async function runExtract() {
    if (!file) return
    setLoading(true); setError(null); setDraft(null); setConfirmed(null)
    try {
      const tok = getToken()
      const fd = new FormData()
      fd.append('file', file)
      fd.append('lang', 'en')
      fd.append('cloud_ok', 'false')

      const endpoint = mode === 'auto' ? '/api/v1/lis-mapping/auto-create' : '/api/v1/lis-mapping/extract'
      const res = await fetch(`${API}${endpoint}`, {
        method: 'POST',
        headers: tok ? { Authorization: `Bearer ${tok}` } : undefined,
        body: fd,
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? `HTTP ${res.status}`)
      setDraft(data)
      if (data.auto_created) {
        setConfirmed({
          lab_request_id: data.lab_request_id,
          lab_id:         data.lab_id,
          patient_id:     data.patient_id,
        })
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Extraction failed')
    } finally {
      setLoading(false)
    }
  }

  async function runConfirm() {
    if (!draft) return
    setLoading(true); setError(null)
    try {
      const tok = getToken()
      const res = await fetch(`${API}/api/v1/lis-mapping/confirm`, {
        method:  'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(tok ? { Authorization: `Bearer ${tok}` } : {}),
        },
        body: JSON.stringify({
          draft,
          auto_create_patient: draft.patient.status === 'new',
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? `HTTP ${res.status}`)
      setConfirmed({
        lab_request_id: data.lab_request_id,
        lab_id:         data.lab_id,
        patient_id:     data.patient_id,
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Confirmation failed')
    } finally {
      setLoading(false)
    }
  }

  function updatePatient<K extends keyof PatientMatch>(k: K, v: PatientMatch[K]) {
    if (!draft) return
    setDraft({ ...draft, patient: { ...draft.patient, [k]: v } })
  }

  function dropTest(idx: number) {
    if (!draft) return
    const tests = draft.tests.filter((_, i) => i !== idx)
    setDraft({ ...draft, tests })
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#070a17] to-[#02061a] text-zinc-100 px-4 py-8">
      <div className="mx-auto max-w-5xl space-y-6">
        <header className="flex items-end justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-semibold">LIS Auto-Mapping</h1>
            <p className="text-sm text-zinc-400">
              Upload a lab request form. The system extracts patient, tests, priority, doctor — review before creating the worklist.
            </p>
          </div>
          <div className="inline-flex rounded-lg border border-zinc-700 bg-zinc-900 p-1 text-xs">
            <button
              type="button"
              onClick={() => setMode('assisted')}
              className={`px-3 py-1.5 rounded-md transition ${mode === 'assisted' ? 'bg-indigo-500/20 text-indigo-200' : 'text-zinc-400 hover:text-zinc-200'}`}
            >
              Review &amp; Edit
            </button>
            <button
              type="button"
              onClick={() => setMode('auto')}
              className={`px-3 py-1.5 rounded-md transition ${mode === 'auto' ? 'bg-indigo-500/20 text-indigo-200' : 'text-zinc-400 hover:text-zinc-200'}`}
            >
              Auto-create
            </button>
          </div>
        </header>

        {error && (
          <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
            {error}
          </div>
        )}

        <section
          onDragOver={(e) => e.preventDefault()}
          onDrop={onDrop}
          className="rounded-xl border border-dashed border-zinc-700 bg-zinc-900/40 px-6 py-8 text-center"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp,.txt,.docx,.csv,.xml"
            className="hidden"
            onChange={(e) => onPickFile(e.target.files?.[0] ?? null)}
          />
          <div className="text-sm text-zinc-300">
            {file ? (
              <>
                <div className="font-medium">{file.name}</div>
                <div className="text-xs text-zinc-500 mt-1">{(file.size / 1024).toFixed(1)} KB · {file.type || 'unknown'}</div>
              </>
            ) : (
              <>Drop a request form here, or click below to choose a file.</>
            )}
          </div>
          <div className="mt-4 flex justify-center gap-3">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="rounded-md border border-zinc-700 bg-zinc-800 px-4 py-2 text-xs hover:bg-zinc-700"
            >
              Choose file
            </button>
            <button
              type="button"
              onClick={runExtract}
              disabled={!file || loading}
              className="rounded-md bg-indigo-500/80 px-4 py-2 text-xs font-medium hover:bg-indigo-500 disabled:opacity-50"
            >
              {loading ? 'Processing…' : mode === 'auto' ? 'Run auto-create' : 'Extract draft'}
            </button>
          </div>
        </section>

        {draft && (
          <DraftPanel
            draft={draft}
            onUpdatePatient={updatePatient}
            onDropTest={dropTest}
            onConfirm={runConfirm}
            confirmed={confirmed}
            loading={loading}
            modeIsAuto={mode === 'auto'}
          />
        )}
      </div>
    </div>
  )
}

function DraftPanel({
  draft, onUpdatePatient, onDropTest, onConfirm, confirmed, loading, modeIsAuto,
}: {
  draft: Draft
  onUpdatePatient: <K extends keyof PatientMatch>(k: K, v: PatientMatch[K]) => void
  onDropTest: (idx: number) => void
  onConfirm: () => void
  confirmed: { lab_request_id: number; lab_id: string; patient_id: number } | null
  loading: boolean
  modeIsAuto: boolean
}) {
  const matchedCount = draft.tests.filter(t => t.status === 'matched').length
  const totalCost    = draft.tests.reduce((s, t) => s + (t.price || 0), 0)

  return (
    <section className="grid gap-4 md:grid-cols-2">
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 space-y-4">
        <header className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-zinc-200">Patient</h2>
          <span className={`text-[10px] px-2 py-0.5 rounded-full border ${statusTone(draft.patient.status)}`}>
            {draft.patient.status}
          </span>
        </header>
        <div className="grid grid-cols-2 gap-3 text-xs">
          <Field label="Family name"  value={draft.patient.family_name}  onChange={(v) => onUpdatePatient('family_name', v)} />
          <Field label="Other names"  value={draft.patient.other_names}  onChange={(v) => onUpdatePatient('other_names', v)} />
          <Field label="PID"          value={draft.patient.pid}          onChange={(v) => onUpdatePatient('pid', v)} />
          <Field label="LID"          value={draft.patient.lid}          onChange={(v) => onUpdatePatient('lid', v)} />
          <Field label="National ID"  value={draft.patient.national_id}  onChange={(v) => onUpdatePatient('national_id', v)} />
          <Field label="DOB"          value={draft.patient.date_of_birth} onChange={(v) => onUpdatePatient('date_of_birth', v)} />
          <Field label="Sex"          value={draft.patient.gender}       onChange={(v) => onUpdatePatient('gender', v)} />
          <Field label="Phone"        value={draft.patient.phone}        onChange={(v) => onUpdatePatient('phone', v)} />
        </div>
      </div>

      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 space-y-3">
        <header className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-zinc-200">Encounter</h2>
          <span className={`text-[10px] px-2 py-0.5 rounded-full border ${confidenceTone(draft.overall_confidence)}`}>
            conf {(draft.overall_confidence * 100).toFixed(0)}%
          </span>
        </header>
        <div className="grid grid-cols-2 gap-3 text-xs">
          <ReadField label="Priority"  value={draft.priority} accent={draft.priority === 'stat'} />
          <ReadField label="Department" value={draft.department || '—'} />
          <ReadField label="Specimen"  value={draft.specimen_type || '—'} />
          <ReadField label="Source"    value={draft.source || '—'} />
          <ReadField label="Doctor"    value={draft.doctor_name || '—'} wide />
          <ReadField label="Ward"      value={draft.ward || '—'} wide />
          <ReadField label="Diagnosis" value={draft.diagnosis || '—'} wide />
        </div>
      </div>

      <div className="md:col-span-2 rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
        <header className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium text-zinc-200">Ordered tests</h2>
          <div className="text-xs text-zinc-400">
            {matchedCount} matched of {draft.tests.length} · Total: {totalCost.toFixed(0)} RWF
          </div>
        </header>
        <div className="divide-y divide-zinc-800 text-xs">
          {draft.tests.length === 0 && (
            <div className="text-zinc-500 py-4">No tests extracted.</div>
          )}
          {draft.tests.map((t, idx) => (
            <div key={`${t.test_id ?? 't'}-${idx}-${t.query}`} className="flex items-center justify-between gap-3 py-2">
              <div className="flex items-center gap-2 min-w-0">
                <span className={`text-[10px] px-2 py-0.5 rounded-full border whitespace-nowrap ${statusTone(t.status)}`}>
                  {t.status}
                </span>
                <span className="font-mono text-zinc-300 w-16 shrink-0">{t.code ?? '—'}</span>
                <span className="text-zinc-200 truncate">{t.name ?? `&ldquo;${t.query}&rdquo;`}</span>
              </div>
              <div className="flex items-center gap-3 text-zinc-400 text-[11px] shrink-0">
                <span>q=&quot;{t.query}&quot;</span>
                <span>{(t.confidence * 100).toFixed(0)}%</span>
                {t.price > 0 && <span>{t.price.toFixed(0)} RWF</span>}
                <button
                  type="button"
                  onClick={() => onDropTest(idx)}
                  className="text-rose-300 hover:text-rose-200"
                  aria-label="Remove test"
                >×</button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {draft.warnings.length > 0 && (
        <div className="md:col-span-2 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-xs text-amber-200 space-y-1">
          {draft.warnings.map((w, i) => <div key={i}>⚠️ {w}</div>)}
        </div>
      )}

      <div className="md:col-span-2 flex items-center justify-between gap-3">
        <div className="text-[11px] text-zinc-500">
          text-hash {draft.text_hash}
        </div>
        {confirmed ? (
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-xs text-emerald-200">
            ✓ {modeIsAuto ? 'Auto-created' : 'Created'} LabRequest <span className="font-mono">{confirmed.lab_id}</span> (#{confirmed.lab_request_id}) · patient #{confirmed.patient_id}
          </div>
        ) : (
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading || draft.tests.filter(t => t.test_id).length === 0}
            className="rounded-md bg-emerald-500/80 px-4 py-2 text-xs font-medium hover:bg-emerald-500 disabled:opacity-50"
          >
            {loading ? 'Creating…' : 'Create LabRequest'}
          </button>
        )}
      </div>
    </section>
  )
}

function Field({
  label, value, onChange,
}: { label: string; value: string | null; onChange: (v: string | null) => void }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</span>
      <input
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value || null)}
        className="rounded-md border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-zinc-100 outline-none focus:border-indigo-400/60"
      />
    </label>
  )
}

function ReadField({
  label, value, accent, wide,
}: { label: string; value: string; accent?: boolean; wide?: boolean }) {
  return (
    <div className={`flex flex-col gap-1 ${wide ? 'col-span-2' : ''}`}>
      <span className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</span>
      <span className={`rounded-md border border-zinc-800 bg-zinc-950 px-2 py-1.5 ${accent ? 'text-amber-200 font-semibold' : 'text-zinc-200'}`}>
        {value}
      </span>
    </div>
  )
}
