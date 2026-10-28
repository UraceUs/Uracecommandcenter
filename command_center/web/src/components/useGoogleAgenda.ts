// Tipos e hooks do Google Calendar fora de GoogleAgenda.tsx: arquivo de componente só exporta componente (#433).
import { useEffect, useRef } from 'react'
import { useGet } from '../api/hooks'
import { useToast } from './useToast'
import { tr } from '../i18n'

export interface StatusGoogle {
  configurado: boolean; motivo: string | null; conectado: boolean; expirado: boolean
  email: string | null; conectado_em: string | null; sincronizado_em: string | null; erro: string | null
}
export interface EventoGoogle { id: string; titulo: string | null; inicio: string; fim: string; dia_todo: boolean; ocupado: boolean }

const MOTIVO: Record<string, string> = {
  estado: tr("A volta do Google não foi aceita (link vencido, já usado ou aberto em outro navegador). Tente de novo."),
  negado: tr("Você cancelou no Google: nada foi conectado."),
  escopo: tr("O Google não deu a permissão de agenda. Conecte de novo e marque o acesso ao Google Calendar."),
  google: tr("O Google não completou a conexão. Tente de novo em instantes."),
}

/** Lê o `?google=` que a volta do Google deixa no endereço, avisa e limpa o endereço. */
export function useVoltaDoGoogle(onVolta: () => void) {
  const toast = useToast()
  const feito = useRef(false)
  useEffect(() => {
    if (feito.current) return
    const q = new URLSearchParams(window.location.search)
    const r = q.get('google')
    if (!r) return
    feito.current = true
    if (r === 'ok') toast(tr("Google Calendar conectado."), 'ok')
    else toast(MOTIVO[q.get('motivo') || 'google'] || MOTIVO.google, 'crit')
    window.history.replaceState(null, '', window.location.pathname)
    onVolta()
  }, [toast, onVolta])
}

/** O estado da conexão, com a volta do Google tratada. */
export function useStatusGoogle() {
  const s = useGet<StatusGoogle>('/google/status')
  useVoltaDoGoogle(s.reload)
  return s
}
