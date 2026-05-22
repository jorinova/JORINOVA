'use client'

/**
 * Logo component.
 *
 * Renders `public/logo/jorinova-nexus.png` (the official brand mark). If
 * the file is missing or fails to load — e.g. on a fresh checkout where
 * nobody has dropped the asset yet — falls back to a "JN" text badge so
 * the layout never breaks.
 *
 * Use everywhere a logo is needed:
 *   import Logo from '@/app/components/Logo'
 *   <Logo size={40} />
 *   <Logo size={56} className="ring-2 ring-white/30" />
 */

import { useState } from 'react'

const NEXUS_BLUE = '#0066CC'

type Props = {
  /** Width and height in pixels. The mark is square. */
  size?:      number
  /** Extra CSS classes — useful for ring/border/shadow tweaks. */
  className?: string
  /** Visible label for screen readers. Defaults to the brand name. */
  alt?:       string
}

export default function Logo({ size = 40, className = '', alt = 'JORINOVA NEXUS' }: Props) {
  const [errored, setErrored] = useState(false)

  if (errored) {
    return (
      <div
        className={`rounded-lg bg-white flex items-center justify-center font-bold shadow-sm ${className}`}
        style={{ height: size, width: size, color: NEXUS_BLUE, fontSize: size * 0.4 }}
        aria-label={alt}
        role="img"
      >
        JN
      </div>
    )
  }

  /* eslint-disable @next/next/no-img-element */
  return (
    <img
      src="/logo/jorinova-nexus.png"
      alt={alt}
      width={size}
      height={size}
      className={`rounded-lg shadow-sm object-contain ${className}`}
      style={{ background: '#0a1b2e' }}     // matches the dark navy of the mark
      onError={() => setErrored(true)}
    />
  )
}
