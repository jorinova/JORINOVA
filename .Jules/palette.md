## 2026-05-30 - [Password Visibility Toggle Patterns]
**Learning:** When implementing a password visibility toggle inside an input field, using `pl-3 pr-10` on the input and absolute positioning on the button ensures typed text doesn't overlap the control. Additionally, setting `type="button"` is mandatory to prevent accidental form submission in React/Next.js.
**Action:** Always wrap input in a `relative` container and use specific right-padding when adding inline UI controls.
