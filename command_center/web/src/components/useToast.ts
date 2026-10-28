import { createContext, useContext } from 'react'

// Contexto e hook do aviso fora de Toast.tsx: arquivo de componente só exporta componente (#433).
/* `warn` entrou em 23/09 com o cadastro de peça: "a peça foi cadastrada, mas a foto
   não" não é sucesso nem falha, e usar 'crit' ali assustaria por causa de uma imagem. */
export type Tom = 'ok' | 'crit' | 'warn'
export const Ctx = createContext<(text: string, tone?: Tom) => void>(() => {})
export const useToast = () => useContext(Ctx)
