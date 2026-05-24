## 2025-05-15 - [Next.js CSR Bailout with useSearchParams]
**Learning:** In this project's Next.js version (16.2.6), using `useSearchParams()` in a client component that is not wrapped in a `<Suspense>` boundary causes the build to fail with a "CSR bailout" error during static generation. This is prevalent in several existing modules.
**Action:** Always wrap components (or pages) that use `useSearchParams()` in a `<Suspense>` boundary to ensure successful production builds.

## 2025-05-15 - [Restricted 'module' Variable Name]
**Learning:** The ESLint configuration (`@next/next/no-assign-module-variable`) in this repository strictly prohibits assigning values to a variable named `module`, which is commonly used in this LIS for laboratory modules.
**Action:** Use `moduleData` or `mod` instead of `module` for variable names representing LIS modules to pass linting checks.
