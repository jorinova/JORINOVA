/**
 * Single source of truth for what a given role sees:
 *   - which page they land on after login
 *   - which sidebar items they can reach
 *
 * Keep this in sync with backend role names (see seed_database.py users).
 */

export type Role =
  | 'super_admin'
  | 'lab_manager'
  | 'scientist'
  | 'lab_technician'
  | 'pathologist'
  | 'receptionist'
  | 'doctor'
  | 'rbc_admin'
  | string

/** Where a freshly-signed-in user goes next. */
export function landingPathFor(role: string | null | undefined): string {
  switch (role) {
    case 'doctor':       return '/portal/doctor'
    case 'rbc_admin':    return '/portal/rbc'
    case 'receptionist': return '/modules/lis_mapping'
    case 'pathologist':  return '/modules/laboratory'
    // super_admin, lab_manager, scientist, lab_technician, anything else
    default:             return '/dashboard'
  }
}

/** True if `role` may access a nav item that lists `allowed`. */
export function roleCan(role: string | null | undefined, allowed: readonly string[]): boolean {
  if (!allowed || allowed.length === 0)       return true
  if (allowed.includes('*'))                   return true
  if (!role)                                   return false
  return allowed.includes(role)
}
