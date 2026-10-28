import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { tr } from '../i18n'
import { Ctx, type Tom } from './useToast'

interface T { id: number; text: string; tone?: Tom }

export function ToastProvider({ children }: { children: ReactNode }) {
  const [list, setList] = useState<T[]>([])
  const push = useCallback((text: string, tone?: Tom) => {
    const id = Date.now() + Math.random()
    setList(l => [...l, { id, text, tone }])
    setTimeout(() => setList(l => l.filter(t => t.id !== id)), 5000)
  }, [])
  const v = useMemo(() => push, [push])
  return <Ctx.Provider value={v}>{children}
    <div className="toast-wrap" aria-live="polite">{list.map(t => <div key={t.id} className={`toast ${t.tone || ''}`}><span className="ic" aria-hidden="true">{t.tone === 'ok' ? '✓' : t.tone === 'crit' ? '✕' : t.tone === 'warn' ? '▲' : '●'}</span><div className="grow"><div className="tt">{t.tone === 'ok' ? tr("Feito") : t.tone === 'crit' ? tr("Não deu") : t.tone === 'warn' ? tr("Quase") : tr("Aviso")}</div>{t.text}</div></div>)}</div>
  </Ctx.Provider>
}
