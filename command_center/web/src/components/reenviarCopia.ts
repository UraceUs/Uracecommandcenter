/* #114: "Reenviar cópia" da waiver assinada no próprio sistema (card do cliente e Site › Waiver). Vai sempre ao
 * e-mail que assinou; a janela mostra esse e-mail antes do clique. */
import { api, ApiError } from '../api/client'
import { usePerguntar } from './usePerguntar'
import { useToast } from './useToast'
import { tr } from '../i18n'

export interface CopiaW { status: 'sent' | 'failed'; at: string; to: string | null; message_id?: string | null; by?: string | null }

/** O clique de "Reenviar cópia": confirma com o e-mail que assinou e manda. */
export function useReenviarCopia(depois: () => void) {
  const perguntar = usePerguntar()
  const toast = useToast()
  return async (w: { id: number; signer_email: string | null }) => {
    if (!await perguntar({ titulo: tr("Reenviar a cópia da waiver?"), ok: tr("Reenviar cópia"),
      texto: tr("Vai para {0}, o e-mail que assinou, com o PDF assinado anexado. Sai do noreply@; a resposta cai no support@.", w.signer_email || '—') })) return
    try {
      const r = await api.post<{ sent_to: string }>(`/waivers/${w.id}/copy`)
      toast(tr("Cópia enviada para {0}.", r.sent_to), 'ok')
    } catch (e) { toast((e as ApiError).message, 'crit') }
    depois()
  }
}
