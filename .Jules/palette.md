## 2025-05-28 - [Password Visibility Toggle]
**Learning:** Adding a password visibility toggle is a high-impact, low-effort micro-UX improvement that improves accessibility and reduces login friction. It requires wrapping the input in a relative container and ensuring the toggle button has 'type="button"' to avoid form submission.
**Action:** Use 'pr-10' (or similar) on the input to prevent text overlap with the absolute-positioned toggle button.
