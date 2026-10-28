import type { Level, Policy } from '../api/types'
import { tr } from '../i18n'

// Constantes e funções de rótulo das telas, fora de ui.tsx: arquivo de componente só exporta componente (#433).

export type Tone = 'ok' | 'warn' | 'crit' | 'info' | 'neutral' | 'accent' | 'outline'

/** Linguagem de estado do Pit Wall: cor + glifo + texto, nunca só a cor.
 *  ✓ feito/ok · ◐ em andamento · ○ esperando · ▲ atenção · ✕ falhou/crítico · — desligado */
export type StatusKind = 'ok' | 'run' | 'wait' | 'warn' | 'crit' | 'off'
export const STATUS_GLYPH: Record<StatusKind, string> = { ok: '✓', run: '◐', wait: '○', warn: '▲', crit: '✕', off: '—' }
export function statusKind(s?: string | null): StatusKind {
  switch ((s || '').toUpperCase()) {
    case 'CONNECTED': case 'COMPLETED': case 'DONE': case 'APPROVED': case 'ACTIVE': case 'SAFE': case 'PAID': case 'OK': case 'CONFIRMED': return 'ok'
    case 'SYNCING': case 'RUNNING': case 'QUEUED': return 'run'
    case 'PROPOSED': case 'DELIVERED': case 'SENT': case 'PENDING': case 'NEW': case 'OPEN': case 'INVITED': case 'REQUIRES_APPROVAL': case 'REQUIRES_CONFIRMATION': case 'DRAFT': return 'wait'
    case 'DEGRADED': case 'AT_RISK': case 'OVERDUE': return 'warn'
    case 'ERROR': case 'FAILED': case 'REJECTED': case 'AUTORESPONDED': case 'DECLINED': case 'VOIDED': case 'BLOCKED': return 'crit'
    case 'DISCONNECTED': case 'INACTIVE': case 'CANCELLED': case 'SKIPPED': return 'off'
    default: return 'wait'
  }
}
/** Nome em português de cada estado cru que a API devolve. O que não estiver aqui aparece como veio. */
export const STATUS_PT: Record<string, string> = {
  CONNECTED: 'ok', DEGRADED: tr("degradado"), ERROR: tr("erro"), DISCONNECTED: tr("desligado"), SYNCING: tr("sincronizando"),
  ACTIVE: tr("ativo"), INACTIVE: tr("inativo"), NEW: tr("novo"), PENDING: tr("pendente"), AT_RISK: tr("em risco"), COMPLETED: tr("concluído"),
  open: tr("aberto"), completed: tr("concluído"), paid: tr("paga"), overdue: tr("vencida"), sent: tr("enviada"), draft: tr("rascunho"),
  PROPOSED: tr("esperando você"), APPROVED: tr("aprovada"), RUNNING: tr("executando"), QUEUED: tr("na fila"), DONE: tr("feita"), FAILED: tr("falhou"), REJECTED: tr("rejeitada"), BLOCKED: tr("bloqueada"), SKIPPED: tr("pulado"),
}
export const LEVEL_GLYPH: Record<Level, string> = { CRITICAL: '✕', HIGH: '▲', MEDIUM: '●', LOW: '○' }

export function levelTone(l: Level): Tone {
  return l === 'CRITICAL' ? 'crit' : l === 'HIGH' ? 'warn' : l === 'MEDIUM' ? 'info' : 'neutral'
}
export function statusTone(s?: string | null): Tone {
  switch ((s || '').toUpperCase()) {
    case 'CONNECTED': case 'COMPLETED': case 'DONE': case 'APPROVED': case 'ACTIVE': case 'SAFE': return 'ok'
    case 'DEGRADED': case 'SYNCING': case 'RUNNING': case 'QUEUED': case 'PROPOSED': case 'DELIVERED': case 'SENT':
    case 'PENDING': case 'AT_RISK': case 'REQUIRES_APPROVAL': case 'REQUIRES_CONFIRMATION': case 'NEW': return 'warn'
    case 'ERROR': case 'FAILED': case 'REJECTED': case 'AUTORESPONDED': case 'DECLINED': case 'VOIDED': case 'BLOCKED': case 'OVERDUE': return 'crit'
    case 'DISCONNECTED': case 'INACTIVE': case 'CANCELLED': return 'neutral'
    default: return 'neutral'
  }
}
export const POLICY_LABEL: Record<Policy, string> = {
  SAFE: tr("Automática"), REQUIRES_CONFIRMATION: tr("Confirmar"), REQUIRES_APPROVAL: tr("Aprovação"), BLOCKED: tr("Bloqueada"),
}
export const WAIVER_LABEL: Record<string, string> = {
  completed: tr("assinada"), delivered: tr("aberta, não assinada"), sent: tr("enviada, não aberta"),
  autoresponded: tr("e-mail devolveu"), declined: tr("recusada"), voided: tr("anulada"),
}

/** Nome legível de cada sistema, para o link ficar ao lado do SEU item — nunca solto no topo. */
export const SYS_NAME: Record<string, string> = { site: tr("Página do pedido"), asana: tr("Asana"), docusign: tr("DocuSign"), gmail: tr("Gmail"), quickbooks: tr("QuickBooks"), qbo: tr("QuickBooks"), brain: tr("Cérebro"), kommo: tr("Kommo"), backup: tr("Backup do banco") }
