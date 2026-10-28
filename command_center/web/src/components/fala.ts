// Motor de ditado e fala do navegador fora de Voz.tsx: arquivo de componente só exporta componente (#433).
import { useCallback, useEffect, useRef, useState } from 'react'
import { tr, LOCALE } from '../i18n'

type Rec = {
  lang: string; continuous: boolean; interimResults: boolean
  start: () => void; stop: () => void; abort: () => void
  onresult: ((e: { resultIndex: number; results: { length: number;[i: number]: { isFinal: boolean;[j: number]: { transcript: string } } } }) => void) | null
  onerror: ((e: { error?: string }) => void) | null
  onend: (() => void) | null
}
type ComRec = { SpeechRecognition?: new () => Rec; webkitSpeechRecognition?: new () => Rec }

function Motor(): (new () => Rec) | null {
  const w = window as unknown as ComRec
  return w.SpeechRecognition || w.webkitSpeechRecognition || null
}
export const temDitado = () => !!Motor()
export const temFala = () => typeof window !== 'undefined' && 'speechSynthesis' in window

/** Lê um texto em voz alta (pt-BR quando houver voz instalada). Chamar de novo troca a fala. */
export function falar(texto: string) {
  if (!temFala() || !texto.trim()) return
  const s = window.speechSynthesis
  s.cancel()
  const f = new SpeechSynthesisUtterance(texto.replace(/\s+/g, ' ').slice(0, 4000))
  const vozes = s.getVoices()
  const pt = vozes.find(v => /pt.?BR/i.test(v.lang)) || vozes.find(v => /^pt/i.test(v.lang))
  if (pt) f.voice = pt
  f.lang = pt?.lang || LOCALE()
  f.rate = 1.03
  s.speak(f)
}
export const calar = () => { if (temFala()) window.speechSynthesis.cancel() }

/** Ditado: devolve o que já foi reconhecido (parcial e final) enquanto o microfone está ligado. */
export function useDitado(aoFinal?: (texto: string) => void) {
  const [ligado, setLigado] = useState(false)
  const [parcial, setParcial] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const rec = useRef<Rec | null>(null)
  const cb = useRef(aoFinal)
  useEffect(() => { cb.current = aoFinal }, [aoFinal])

  const parar = useCallback(() => { try { rec.current?.stop() } catch { /* já parado */ } setLigado(false) }, [])

  const ligar = useCallback(() => {
    const M = Motor()
    if (!M) { setErro(tr("Este navegador não tem ditado. No celular use o microfone do teclado; no computador, o Chrome.")); return }
    setErro(null)
    const r = new M()
    r.lang = LOCALE()
    r.continuous = true
    r.interimResults = true
    r.onresult = e => {
      let fim = '', meio = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript
        if (e.results[i].isFinal) fim += t
        else meio += t
      }
      if (meio) setParcial(meio)
      if (fim.trim()) { setParcial(''); cb.current?.(fim.trim()) }
    }
    r.onerror = e => {
      const k = e?.error || ''
      setErro(k === 'not-allowed' || k === 'service-not-allowed'
        ? tr("O navegador bloqueou o microfone. Libere o microfone para este site e tente de novo.")
        : k === 'no-speech' ? null : tr("Ditado parou ({0}).", k || 'erro'))
      setLigado(false)
    }
    r.onend = () => { setLigado(false); setParcial('') }
    rec.current = r
    try { r.start(); setLigado(true) } catch { setLigado(false) }
  }, [])

  useEffect(() => () => { try { rec.current?.abort() } catch { /* nada */ } }, [])
  return { ligado, parcial, erro, ligar, parar, alternar: () => (ligado ? parar() : ligar()), disponivel: temDitado() }
}
