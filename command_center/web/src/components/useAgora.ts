import { useEffect, useState } from 'react'

/** "Agora" em milissegundos que se atualiza a cada `cada` ms: a tela compara com o relógio sem
 *  chamar Date.now() no render, que dá resultado diferente a cada render (#433). */
export function useAgora(cada = 30000) {
  const [agora, setAgora] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setAgora(Date.now()), cada)
    return () => clearInterval(id)
  }, [cada])
  return agora
}
