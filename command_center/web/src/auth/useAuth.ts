import { createContext, useContext } from 'react'
import { ROLES, type Role, type User } from '../api/types'

// Contexto e hook fora de AuthContext.tsx: o arquivo do componente só exporta componente (#433).
export interface Ctx {
  user: User | null; ready: boolean
  login: (email: string, password: string, remember: boolean) => Promise<void>
  logout: () => Promise<void>
  can: (min: Role) => boolean
  /** conta de acesso livre: sem cargo, alcança tudo (decisão do dono, 17/09) */
  livre: boolean
  /** mecânico ou coach (#92): só as telas do box */
  box: boolean
  refresh: () => Promise<void>
}
export const AuthCtx = createContext<Ctx | null>(null)

export function can(role: Role | undefined, min: Role) {
  if (!role) return false
  return ROLES.indexOf(role) >= ROLES.indexOf(min)
}

export function useAuth() {
  const c = useContext(AuthCtx)
  if (!c) throw new Error('useAuth fora do AuthProvider')
  return c
}
