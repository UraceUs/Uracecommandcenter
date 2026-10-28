/* Voz no painel (dono, 17/09): "para a gente não ficar precisando digitar".
 *
 * Ditado: reconhecimento de fala do próprio navegador (Chrome, Edge, Safari 14.5+).
 * Não sai do aparelho para nenhum servidor nosso e não precisa de chave nova.
 * Fala: a resposta da IA pode ser lida em voz alta (o mesmo motor do navegador).
 *
 * Onde o navegador não tem o recurso, o botão não aparece — nada quebra.
 */
import { useEffect, useRef, useState } from 'react'
import { Icon } from './Icon'
import { tr } from '../i18n'
import { calar, falar, temFala, useDitado } from './fala'

/** Botão de microfone: cola o que for falado no fim do texto que já está no campo. */
export function Mic({ valor, onTexto, titulo, className }: { valor: string; onTexto: (t: string) => void; titulo?: string; className?: string }) {
  const base = useRef(valor)
  const d = useDitado(t => { base.current = (base.current ? base.current.replace(/\s*$/, ' ') : '') + t; onTexto(base.current) })
  useEffect(() => { if (!d.ligado) base.current = valor }, [valor, d.ligado])
  if (!d.disponivel) return null
  return <button type="button" className={`mic${d.ligado ? ' on' : ''}${className ? ' ' + className : ''}`} onClick={d.alternar}
    title={d.erro || titulo || (d.ligado ? tr("Parar de ditar") : tr("Ditar (falar em vez de digitar)"))}
    aria-label={d.ligado ? tr("Parar de ditar") : tr("Ditar")} aria-pressed={d.ligado}>
    <Icon name="mic" size={16} />{d.ligado && <i className="onda" aria-hidden="true"><i /><i /><i /></i>}
  </button>
}

/** Campo de texto com microfone embutido: é o que usamos em todo lugar que se digita muito. */
export function TextoComVoz({ valor, onChange, linhas = 3, placeholder, disabled, onEnter, autoFocus, id }: {
  valor: string; onChange: (t: string) => void; linhas?: number; placeholder?: string
  disabled?: boolean; onEnter?: () => void; autoFocus?: boolean; id?: string
}) {
  const d = useDitado(t => onChange((valor ? valor.replace(/\s*$/, ' ') : '') + t))
  return <div className={`vozwrap${d.ligado ? ' ditando' : ''}`}>
    <textarea id={id} className="input" rows={linhas} value={valor + (d.parcial ? (valor ? ' ' : '') + d.parcial : '')}
      placeholder={placeholder} disabled={disabled} autoFocus={autoFocus}
      onChange={e => onChange(e.target.value)}
      onKeyDown={e => { if (onEnter && e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); onEnter() } }} />
    {d.disponivel && <button type="button" className={`mic dentro${d.ligado ? ' on' : ''}`} onClick={d.alternar} disabled={disabled}
      title={d.erro || (d.ligado ? tr("Parar de ditar") : tr("Ditar"))} aria-label={tr("Ditar")} aria-pressed={d.ligado}>
      <Icon name="mic" size={16} />{d.ligado && <i className="onda" aria-hidden="true"><i /><i /><i /></i>}
    </button>}
    {d.erro && <div className="small" style={{ color: 'var(--warn)', marginTop: 4 }}>{d.erro}</div>}
  </div>
}

/** Botão "ouvir": lê um texto em voz alta e para quando clicado de novo. */
export function Ouvir({ texto, titulo }: { texto: string; titulo?: string }) {
  const [falando, setFalando] = useState(false)
  useEffect(() => {
    if (!temFala()) return
    const t = setInterval(() => setFalando(window.speechSynthesis.speaking), 500)
    return () => clearInterval(t)
  }, [])
  if (!temFala() || !texto.trim()) return null
  return <button type="button" className={`mic sm${falando ? ' on' : ''}`} title={titulo || tr("Ouvir em voz alta")} aria-label={tr("Ouvir")}
    onClick={() => { if (window.speechSynthesis.speaking) { calar(); setFalando(false) } else { falar(texto); setFalando(true) } }}>
    <Icon name={falando ? 'x' : 'som'} size={15} />
  </button>
}
