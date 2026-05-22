## 2025-05-22 - Decorative Icon Accessibility
**Learning:** Decorative SVG icons (like loading spinners) used alongside descriptive text should be hidden from screen readers to reduce redundancy and noise.
**Action:** Always add `aria-hidden="true"` to SVG elements that are purely visual or decorative when the same information is conveyed via text.
