# JORINOVA NEXUS — Brand Logo

Drop the official brand mark here as **`jorinova-nexus.png`**.

The Logo component at `frontend/app/components/Logo.tsx` reads from
`/logo/jorinova-nexus.png` (this folder, served by Next.js as static
assets). If the file is missing it falls back to a `JN` text badge so
nothing crashes — but the real logo should always be present in
production.

## Recommended file

- **Name**: `jorinova-nexus.png`
- **Size**: at least 256 × 256 px (component renders at 32–56 px usually)
- **Format**: PNG with transparency *or* the official dark-navy circle
  background
- **Color background**: the Logo component sets `background: #0a1b2e`
  behind the image to match the mark's navy ring even if the PNG has
  transparency

## To add it

Save your brand asset as:

```
D:\JORINOVA NEXUS\frontend\public\logo\jorinova-nexus.png
```

then hard-refresh the browser (Ctrl + Shift + R). Every page that uses
`<Logo />` will pick it up automatically — login, forgot-password,
dashboard headers, footers, training runner, etc.

## Optional variants

If you later want light- and dark-theme variants, drop them as
`jorinova-nexus-light.png` and `jorinova-nexus-dark.png` and extend the
`<Logo>` component to swap based on the active theme.
