// Fora de BalcaoRascunho.tsx: arquivo de componente só exporta componente (#433).
import { api } from '../api/client'
import type { EstadoRz } from './BalcaoRascunho'

/** Linha nova no rascunho do card (cria o rascunho na primeira). Peça do estoque, item do QuickBooks ou livre. */
export function adicionarLinha(clientId: number, corpo: Record<string, unknown>) {
  return api.post<EstadoRz>(`/balcao/cliente/${clientId}/rascunho/linhas`, corpo)
}
