'use client'

import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import type { TokenOut, User } from '@/types'
import { login as apiLogin, me as apiMe, logout as apiLogout } from '../lib/api'

interface AuthContextType {
  user: User | null
  loading: boolean
  login: (username: string, password: string) => Promise<TokenOut>
  logout: () => void
  refreshProfile: () => Promise<void>
}

const AuthContext = createContext<AuthContextType>({} as AuthContextType)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  const refreshProfile = useCallback(async () => {
    try {
      const data = await apiMe()
      setUser(data)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  // Refresh the session on every page load (incl. hard refresh / direct URL).
  // Without this, `loading` stays `true` forever in any tab the user didn't
  // sign in from, so RequireAuth shows 'Loading…' indefinitely.
  useEffect(() => {
    // If there is no token at all, skip the network round-trip — apiMe would
    // 401 and we'd just sit on Loading… while waiting.
    const hasToken =
      typeof document !== 'undefined' &&
      (document.cookie.split('; ').some(r => r.startsWith('access_token=')) ||
       !!localStorage.getItem('access_token'))
    if (!hasToken) {
      setLoading(false)
      return
    }
    void refreshProfile()
  }, [refreshProfile])

  const login = useCallback(async (username: string, password: string) => {
    const tokenOut = await apiLogin(username, password)
    await refreshProfile()
    return tokenOut
  }, [refreshProfile])

  const logout = useCallback(async () => {
    try {
      await apiLogout()
    } finally {
      setUser(null)
      router.replace('/login')
    }
  }, [router])

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshProfile }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>')
  return ctx
}
