/**
 * Scene registry — the dispatcher for the training runner.
 *
 * To add a new interaction type:
 *   1. Create `./MyScene.tsx` exporting a `SceneComponent`
 *   2. Add an entry below: `my_scene: MyScene`
 *   3. Reference `'my_scene'` from a scenario's `scenes` list in
 *      `backend/ai_services/training_scenarios.py`
 *
 * Reusing an existing scene requires NO frontend changes — only edit the
 * Python scenarios catalogue.
 */
import type { SceneComponent } from './types'

import SpecimenIntake  from './SpecimenIntake'
import CriticalCBC     from './CriticalCBC'
import LisMappingDemo  from './LisMappingDemo'

export const sceneMap: Record<string, SceneComponent> = {
  specimen_intake:    SpecimenIntake,
  critical_cbc:       CriticalCBC,
  lis_mapping_demo:   LisMappingDemo,
}

export type SceneId = keyof typeof sceneMap

export function resolveScene(id: string | undefined | null): SceneComponent | null {
  if (!id) return null
  return sceneMap[id] ?? null
}
