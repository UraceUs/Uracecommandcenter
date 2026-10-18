/* Título da aba por tela (issue #18): "Compras · URACE Command Center".
 * Um mecanismo só para todas as telas: o título é o h1 da tela (cada tela tem exatamente
 * um — o teste end-to-end garante). Tela com nome dinâmico (o card do cliente) ganha o
 * nome do piloto na aba sem código a mais.
 *
 * #315: a subtela que abre uma coisa dentro da tela (a página no Editor do site) marca o nome dela com
 * `data-aba-titulo`; ele entra antes do h1: "Summer Camp · Editor do site · URACE Command Center". E a
 * `meta description` da tela (`useDescricao`) vale enquanto ela está aberta; ao sair, volta a do painel. */
import { useEffect } from 'react'

const SUFIXO = 'URACE Command Center'

function textoDoH1(h: Element) {
  const c = h.cloneNode(true) as Element
  c.querySelectorAll('button, [aria-hidden="true"]').forEach(b => b.remove())
  return (c.textContent || '').replace(/\s+/g, ' ').trim()
}

export function iniciarTituloAutomatico() {
  let pendente = 0
  const atualizar = () => {
    pendente = 0
    const h = document.querySelector('h1')
    const t = h ? textoDoH1(h) : ''
    const sub = document.querySelector('[data-aba-titulo]')
    const s = sub ? textoDoH1(sub).slice(0, 50) : ''
    const sufixo = location.pathname.startsWith('/ops/portal') ? 'URACE' : SUFIXO   // área do cliente: a marca, não o painel
    const novo = [s, t.slice(0, 60), sufixo].filter(Boolean).join(' · ')
    if (document.title !== novo) document.title = novo
  }
  new MutationObserver(() => { if (!pendente) pendente = window.setTimeout(atualizar, 50) })
    .observe(document.getElementById('root') || document.body, { childList: true, subtree: true, characterData: true })
  atualizar()
}

let descricaoDoPainel: string | null = null
/** A `meta description` desta tela enquanto ela está aberta; ao sair, volta a do painel (a do index.html). Na troca de
 *  tela, a que entra pode escrever a dela antes de a que sai limpar: quem sai só devolve a do painel se a descrição
 *  ainda for a sua. */
export function useDescricao(texto: string) {
  useEffect(() => {
    const m = document.querySelector('meta[name="description"]')
    if (!m || !texto) return
    if (descricaoDoPainel === null) descricaoDoPainel = m.getAttribute('content') || ''
    m.setAttribute('content', texto)
    return () => { if (m.getAttribute('content') === texto) m.setAttribute('content', descricaoDoPainel || '') }
  }, [texto])
}
