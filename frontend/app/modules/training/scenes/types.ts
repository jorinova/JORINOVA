/**
 * Scene contract for the training runner.
 *
 * Architecture rule (do not break):
 *   Python defines behaviour, the frontend executes it, the DOM is the contract.
 *
 * Every scene component:
 *   - Accepts ONLY the props in `SceneProps` (no scenario-specific extras)
 *   - Renders elements tagged with `data-train="<step-id>"` matching the
 *     selectors referenced by the Python scenarios catalogue
 *   - Performs no scenario logic — the runner alone interprets steps
 */

import type { ComponentType } from 'react'

/**
 * Live data fetched by the runner from the pilot DB (anonymised by the backend).
 * Scenes use it instead of hardcoded synthetic data. Always optional — a scene
 * must still render something reasonable when no live record is available.
 */
export type LiveData = {
  lab_request?: {
    id:           number
    lab_id:       string
    doctor_name?: string | null
    ward?:        string | null
    diagnosis?:   string | null
    priority?:    string | null
  }
  patient?: {
    family_name?: string | null    // already anonymised → initials only
    other_names?: string | null
    age_band?:    string | null    // e.g. "30s"
    gender?:      string | null
    pid?:         string | null    // '[redacted]'
    lid?:         string | null
  }
  results?: Array<{
    test_id:       number | null
    value:         string | null
    numeric_value: number | null
    unit:          string | null
    flag:          string | null   // H | L | HH | LL | POS | null
    status:        string | null
  }>
}

export type SceneProps = {
  /** Map from `data-train` selector → current typed text (driven by `type` action) */
  typedText: Record<string, string>
  /** Map from `data-train` selector → highlight CSS class (driven by `highlight` / `flash` / `click` actions) */
  highlight: Record<string, string>
  /** Anonymised real-pilot data fetched by the runner. May be undefined. */
  liveData?: LiveData
}

export type SceneComponent = ComponentType<SceneProps>

/** Helper to merge a runner-driven highlight class with a scene's base class. */
export function withHighlight(
  highlight: Record<string, string>,
  selector: string,
  baseClass: string,
): string {
  const h = highlight[selector]
  return h ? `${baseClass} ${h}` : baseClass
}
