import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, ApiError, subscribeUnauthorized } from '../api/client'
import type { User } from '../api/types'
import { AuthCtx, can, type Ctx } from './useAuth'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(false)

  const refresh = useCallback(async () => {
    try { setUser(await api.get<User>('/auth/me', { silent401: true })) }
    catch (e) { if (e instanceof ApiError && e.status === 401) setUser(null); else throw e }
  }, [])

  // A sessão vem do servidor: o estado só muda na resposta, nunca no corpo do effect (#433).
  useEffect(() => { Promise.resolve().then(refresh).catch(() => {}).finally(() => setReady(true)) }, [refresh])
  useEffect(() => subscribeUnauthorized(() => setUser(null)), [])

  const value = useMemo<Ctx>(() => ({
    user, ready, refresh,
    login: async (email, password, remember) => { setUser(await api.post<User>('/auth/login', { email, password, remember })) },
    logout: async () => { try { await api.post('/auth/logout') } finally { setUser(null) } },
    can: (min) => (user?.free ? true : can(user?.role, min)),
    livre: !!user?.free,
    box: !!user?.cargo && !user?.free,
  }), [user, ready, refresh])
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>
}
