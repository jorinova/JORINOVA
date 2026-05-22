'use client'

/**
 * Avatar — renders user.photo_url with initials fallback.
 *
 * The photo source is whatever the backend stored in users.profile_photo
 * for that user. If the value is a relative path it is served by Next.js
 * from /public; if it is a full URL it is loaded as-is. Errors (404, CORS,
 * dead host) fall through to a coloured initials bubble so the layout
 * never breaks.
 *
 * Use:
 *   import Avatar from '@/app/components/Avatar'
 *   <Avatar src={user.photo_url} name={user.full_name} size={36} />
 */

import { useEffect, useState } from 'react'

const NEXUS_BLUE = '#0066CC'

type Props = {
  /** URL or absolute path of the photo. Pass `null` to skip the <img>. */
  src?:       string | null
  /** Used both for the initials fallback and the alt text. */
  name:       string
  /** Pixels. Square. */
  size?:      number
  className?: string
  /** Hide the green online dot in the corner. Default true. */
  showStatus?: boolean
}

function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

// Deterministic colour from a string — same name always gets the same hue.
function hueFor(name: string): number {
  let h = 0
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 360
  return h
}

export default function Avatar({
  src, name, size = 36, className = '', showStatus = true,
}: Props) {
  const [errored, setErrored] = useState(false)

  // Reset error state if src changes (e.g. after a new photo upload)
  useEffect(() => { setErrored(false) }, [src])

  const renderFallback = !src || errored
  const initials = initialsOf(name)
  const hue = hueFor(name)

  return (
    <div className={`relative inline-block ${className}`} style={{ height: size, width: size }}>
      {!renderFallback ? (
        /* eslint-disable @next/next/no-img-element */
        <img
          src={src!}
          alt={name}
          width={size}
          height={size}
          onError={() => setErrored(true)}
          className="rounded-full object-cover ring-2 ring-white shadow"
          style={{ height: size, width: size, background: '#0a1b2e' }}
        />
      ) : (
        <div
          className="rounded-full flex items-center justify-center font-semibold text-white ring-2 ring-white shadow"
          style={{
            height: size, width: size,
            background: `linear-gradient(135deg, hsl(${hue}, 65%, 45%) 0%, hsl(${(hue + 25) % 360}, 70%, 55%) 100%)`,
            fontSize: size * 0.4,
          }}
          aria-label={name}
        >
          {initials}
        </div>
      )}
      {showStatus && (
        <span
          className="absolute bottom-0 right-0 rounded-full ring-2 ring-white"
          style={{
            height: size * 0.27,
            width:  size * 0.27,
            background: '#10B981',  // emerald-500 = online
          }}
          title="Online"
        />
      )}
    </div>
  )
}
