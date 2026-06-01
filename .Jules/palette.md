## 2025-05-15 - [Password Visibility & Next.js Build Integrity]
**Learning:** In Next.js (App Router), `useSearchParams()` triggers a CSR bailout during static generation if not wrapped in a `<Suspense>` boundary. Additionally, auth-dependent pages like the dashboard can encounter `null` user objects during prerendering even if protected by auth-wrappers, necessitating defensive checks (e.g., `if (!user) return <Loading />`) to avoid build failures.
**Action:** Always wrap `useSearchParams()` in `<Suspense>` and use defensive null-checks for session-based data to ensure build stability.

**Learning:** Interactive UI controls within forms (like password toggles) MUST explicitly set `type="button"` to prevent them from defaulting to `type="submit"` and triggering unintended form submissions.
**Action:** Default all non-submit buttons in forms to `type="button"`.
