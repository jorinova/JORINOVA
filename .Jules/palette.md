## 2025-05-14 - [Password Visibility Toggle Container Padding]
**Learning:** When adding absolute-positioned UI controls (like a visibility toggle) inside an input field, it is crucial to add sufficient padding (e.g., `pr-10`) to the input itself. Without this, typed text will eventually overflow and render underneath the toggle icon, creating a poor visual experience.
**Action:** Always ensure horizontal padding is balanced when adding interactive elements inside form inputs.

## 2025-05-14 - [Avoid Committing Generated Lockfiles]
**Learning:** Micro-UX changes should remain focused. Running `pnpm install` or `pnpm build` may generate or update `pnpm-lock.yaml`. Committing this file alongside a small UI change violates "keep changes under 50 lines" and adds unnecessary noise to reviews.
**Action:** Explicitly check for and remove generated lockfiles before submitting micro-UX PRs unless dependency changes were intentional.
