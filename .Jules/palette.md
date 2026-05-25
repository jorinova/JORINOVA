## 2025-05-15 - [Login UX: Password Visibility Toggle]
**Learning:** Adding a password visibility toggle is a high-impact, low-line-count micro-UX improvement that significantly aids user verification and accessibility.
**Action:** Use a relative container for the password input and an absolute positioned button for the toggle. Always include `aria-label` for screen readers and ensure the input type dynamically switches between 'password' and 'text'.

## 2025-05-15 - [Next.js Build: Null Auth User during Prerendering]
**Learning:** In Next.js (App Router), pages that rely on auth context (even if wrapped in auth-guarding components) can encounter null user objects during the static prerendering phase of the build.
**Action:** Use optional chaining (e.g., `user?.role`) or explicit null checks in components that access the user object to prevent build-time TypeErrors.

## 2025-05-15 - [Next.js Lint: Avoid 'module' Variable Name]
**Learning:** Next.js has a specific lint rule (`@next/next/no-assign-module-variable`) that prevents assigning to the variable name `module`.
**Action:** Use more descriptive names like `activeModule` or `currentModule` to avoid name collisions with the global `module` object.
