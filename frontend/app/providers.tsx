'use client'

/**
 * App-wide client providers.
 *
 * Wraps children with TanStack Query's `QueryClientProvider` so any hook in
 * the tree (`useQuery`, `useMutation`, …) can talk to a shared client. The
 * client is created once on mount via `useState` so it survives Fast Refresh
 * but does not leak across users in SSR.
 *
 * To use, import in app/layout.tsx and wrap around `<AuthProvider>` or your
 * other context providers.
 */

import { ReactNode, useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            retry: 1,
          },
          mutations: {
            retry: 0,
          },
        },
      }),
  )

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}
