/* #114: a cópia por e-mail da waiver assinada no próprio sistema, no card do cliente e em Site › Waiver.
 * Mostra a última tentativa (saiu, para quem e quando; ou não saiu) e o "Reenviar cópia", que vai sempre ao
 * e-mail que assinou: a janela mostra esse e-mail antes do clique. O message-id fica na trilha da waiver. */
import { fmtDateTime } from './fmt'
import type { CopiaW } from './reenviarCopia'
import { tr } from '../i18n'

export function SituacaoDaCopia({ c }: { c?: CopiaW | null }) {
  if (!c) return <div className="small muted">{tr("cópia por e-mail: ainda não saiu")}</div>
  return c.status === 'sent'
    ? <div className="small muted">{tr("cópia por e-mail para {0} em {1}", c.to || '—', fmtDateTime(c.at))}</div>
    : <div className="small" style={{ color: 'var(--crit)' }}>{tr("a cópia por e-mail não saiu em {0}", fmtDateTime(c.at))}</div>
}
