## 2026-05-31 - [Password Visibility Toggle]
**Learning:** Adding a password visibility toggle is a high-impact, low-complexity UX improvement that significantly helps users during the sign-in process, especially when complex passwords are required. Accessibility must be handled carefully with dynamic ARIA labels and ensuring the toggle button doesn't trigger form submission.
**Action:** Use a relative container for password inputs and absolute positioning for the toggle, while ensuring `pr-10` or similar padding to prevent text overlap. Always include `aria-label` and `type="button"`.
