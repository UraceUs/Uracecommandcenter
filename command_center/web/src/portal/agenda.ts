// Rótulos e regras da agenda do portal fora de Agendar.tsx: arquivo de componente só exporta componente (#433).
import type { AgendaCfg, Driver } from './api'

export const PERIODO: Record<string, string> = { manha: 'Morning', tarde: 'Afternoon', dia: 'Full day' }
export const STATUS: Record<string, [string, string]> = { pendente: ['Waiting for confirmation', 'warn'], confirmada: ['Confirmed', 'ok'],
  recusada: ['Not available', 'crit'], cancelada: ['Cancelled', 'neutral'] }

function horaUS(h: string) {
  const [hh, mm] = h.split(':').map(Number)
  return `${((hh + 11) % 12) + 1}${mm ? `:${String(mm).padStart(2, '0')}` : ''} ${hh < 12 ? 'AM' : 'PM'}`
}
export const faixa = (cfg: AgendaCfg, p: string) => p === 'manha' ? `${horaUS(cfg.morning_start)} – ${horaUS(cfg.morning_end)}`
  : p === 'tarde' ? `${horaUS(cfg.afternoon_start)} – ${horaUS(cfg.afternoon_end)}` : `${horaUS(cfg.morning_start)} – ${horaUS(cfg.afternoon_end)}`
export const dataLonga = (iso: string) => new Date(iso + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })
export const PERIODOS = PERIODO
export const STATUS_SESSAO = STATUS

/** #148: o site novo manda o cliente para cá com o que ele já escolheu lá
 * (`?date=2026-10-16&period=manha&kart=4-stroke`). Só vale o que tem formato certo. */
export function escolhaDoSite(q: URLSearchParams) {
  const data = q.get('date') || ''
  const periodo = q.get('period') || ''
  const kart = (q.get('kart') || '').slice(0, 40)
  return {
    dia: /^\d{4}-\d{2}-\d{2}$/.test(data) ? data : null,
    periodo: (['manha', 'tarde', 'dia'].includes(periodo) ? periodo : null) as 'manha' | 'tarde' | 'dia' | null,
    kart: kart || null,
  }
}

/** Por que este piloto não pode marcar agora (ou null). */
export function bloqueioDoPiloto(p: Driver): string | null {
  if (p.measures_status === 'faltando') return 'complete the profile first'
  if (p.measures_status === 'vencida') return 'update the measurements first'
  return null
}
