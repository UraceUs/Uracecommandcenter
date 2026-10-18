/* Editor do site como o Canva (#315, etapa 5): a ajuda dos atalhos. Abre com "?" (na prévia ou no painel, fora de um
 * texto em edição) ou no botão "?" de cima. É um diálogo: título h3, o foco entra nele e fica preso (Tab e
 * Shift+Tab dão a volta), Esc ou Fechar fecham e o foco volta para onde estava. A lista é a das teclas que o editor
 * atende de verdade (`teclar` em Editor.tsx e `aoTeclar` em ponte.ts): mudou uma tecla lá, muda aqui. */
import { Fragment, useEffect, useRef, type KeyboardEvent as KE } from 'react'
import { Scrim } from '../../components/ui'
import { tr } from '../../i18n'

type Linha = [string[][], string]
const mac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent)
const CTRL = mac ? '⌘' : 'Ctrl'

const GRUPOS: [string, Linha[]][] = [
  [tr("Com uma peça escolhida"), [
    [[['↑'], ['↓']], tr("a peça anterior e a próxima")],
    [[['Enter']], tr("escrever no lugar (na seção: vai para a primeira peça dela)")],
    [[['Esc']], tr("subir um nível: da peça para a seção, depois tirar a seleção")],
    [[['Alt', '↑'], ['Alt', '↓']], tr("mover para cima e para baixo")],
    [[['Alt', '←'], ['Alt', '→']], tr("mudar de coluna")],
    [[[CTRL, 'D']], tr("duplicar")],
    [[['Delete'], ['Backspace']], tr("apagar (a faixa original esconde)")],
  ]],
  [tr("Escrevendo no lugar"), [
    [[['Esc']], tr("sair do texto")],
    [[['Enter']], tr("sair do texto (no texto longo, parágrafo novo; na lista, o próximo item)")],
    [[[CTRL, 'B'], [CTRL, 'I']], tr("negrito e itálico (no texto longo)")],
    [[[CTRL, 'K']], tr("link no texto marcado")],
  ]],
  [tr("Sempre"), [
    [[[CTRL, 'Z']], tr("desfazer (até 100 passos)")],
    [[[CTRL, 'Shift', 'Z'], [CTRL, 'Y']], tr("refazer")],
    [[[CTRL, 'S']], tr("salvar já")],
    [[['Esc']], tr("fechar a folha do celular e cancelar o \"toque onde quer pôr\"")],
    [[['?']], tr("esta ajuda")],
  ]],
  [tr("Mouse e toque"), [
    [[[tr("clique")]], tr("seleciona; clique de novo (ou duplo clique) escreve no lugar")],
    [[[tr("arrastar")]], tr("move a peça ou a seção (a linha azul mostra onde cai); da aba Inserir, põe uma peça nova")],
    [[[tr("tocar e segurar")]], tr("no celular, arrasta a peça")],
  ]],
]

function Teclas({ combos }: { combos: string[][] }) {
  return <>{combos.map((c, i) => <Fragment key={i}>{i > 0 && <span className="muted"> {tr("ou")} </span>}
    {c.map((k, j) => <Fragment key={k}>{j > 0 && '+'}<kbd>{k}</kbd></Fragment>)}</Fragment>)}</>
}

export function Atalhos({ fechar }: { fechar: () => void }) {
  const caixa = useRef<HTMLDivElement>(null)
  const primeiro = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    const antes = document.activeElement as HTMLElement | null
    primeiro.current?.focus()
    // o foco volta para onde estava (o botão "?", a linha das Camadas, a prévia)
    return () => { if (antes?.isConnected) antes.focus({ preventScroll: true }) }
  }, [])
  function teclar(e: KE<HTMLDivElement>) {
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); fechar(); return }
    if (e.key !== 'Tab') return
    const fs = Array.from(caixa.current?.querySelectorAll<HTMLElement>('button, a[href]') || []).filter(x => !(x as HTMLButtonElement).disabled)
    if (!fs.length) return
    const i = fs.indexOf(document.activeElement as HTMLElement)
    if (e.shiftKey && i <= 0) { e.preventDefault(); fs[fs.length - 1].focus() }
    else if (!e.shiftKey && (i === fs.length - 1 || i < 0)) { e.preventDefault(); fs[0].focus() }
  }
  return <Scrim className="modal-scrim ed-ajuda-fundo" onMouseDown={fechar}>
    <div ref={caixa} className="modal ed-ajuda" role="dialog" aria-modal="true" aria-labelledby="ed-ajuda-h" onMouseDown={e => e.stopPropagation()} onKeyDown={teclar}>
      <button ref={primeiro} type="button" className="btn ghost sm close" aria-label={tr("Fechar")} onClick={fechar}>✕</button>
      <h3 id="ed-ajuda-h">{tr("Atalhos do teclado")}</h3>
      {GRUPOS.map(([g, linhas]) => <section key={g} className="ed-ajuda-grupo" aria-label={g}>
        <h4>{g}</h4>
        <dl>{linhas.map(([combos, o], i) => <div key={i} className="ed-ajuda-linha"><dt><Teclas combos={combos} /></dt><dd>{o}</dd></div>)}</dl>
      </section>)}
      <div className="modal-foot"><button type="button" className="btn primary" onClick={fechar}>{tr("Entendi")}</button></div>
    </div>
  </Scrim>
}
