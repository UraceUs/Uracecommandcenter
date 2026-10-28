import { createContext, useContext, type ReactNode } from 'react'

// Contexto e hook da pergunta fora de Perguntar.tsx: arquivo de componente só exporta componente (#433).
export interface Pergunta {
  titulo: string
  texto?: ReactNode
  ok?: string
  cancelar?: string
  perigo?: boolean
  campo?: string
  valor?: string
  /** campo de senha: não aparece na tela, não é ditado e o navegador não guarda */
  segredo?: boolean
  /** a terceira escolha (devolve 'alt'). Com ela, Enter não confirma e o foco começa no Cancelar */
  alt?: string
}
export type Responder = (p: Pergunta) => Promise<boolean | string | null>

export const Ctx = createContext<Responder>(async () => false)

export const usePerguntar = () => useContext(Ctx)
