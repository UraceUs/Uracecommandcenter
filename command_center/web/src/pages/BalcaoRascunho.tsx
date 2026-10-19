/* Rascunho de invoice do balcão (#341).
 *
 * Dono, 19/10: "colocar peças e valores em um rascunho de bulk para o cliente e dali o command center cria a
 * invoice com os itens que eu falar; se não tiver item ele cria; coloque também todo o inventário do QuickBooks".
 * O rascunho mora no servidor (recarregar ou outro aparelho mostra o mesmo) e é do card aberto, nunca de outro.
 * Montar é de quem está no galpão; "Criar invoice" é do gerente (cria item no QuickBooks e usa o preço digitado). */
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api, ApiError, qs } from '../api/client'
import { Banner, Chip, Scrim, Section } from '../components/ui'
import { useToast } from '../components/Toast'
import { tr } from '../i18n'

export interface ItemQboLista { id: string; name: string; full_name: string | null; price: number | null; type: string | null }
interface LinhaRz { id: number; origem: 'estoque' | 'quickbooks' | 'livre'; nome: string; descricao: string | null; qty: number
  preco: number | null; preco_tabela: number | null; preco_digitado: boolean; total: number | null; sem_saldo: boolean }
interface Rz { id: number; status: string; linhas: LinhaRz[]; total: number; sem_preco: string[]; pronto: boolean; erro: string | null
  incerto: boolean; doc_number: string | null; invoice_status: string | null }
export interface EstadoRz { rascunho: Rz | null; faturados: Rz[]; gerente: boolean }

const usd = (n: number) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
const ORIGEM: Record<string, string> = { estoque: tr("estoque"), quickbooks: tr("QuickBooks"), livre: tr("linha livre") }
const num = (s: string) => { const n = Number(s.replace(',', '.')); return s.trim() !== '' && Number.isFinite(n) ? n : null }

/** Linha nova no rascunho do card (cria o rascunho na primeira). Peça do estoque, item do QuickBooks ou livre. */
export function adicionarLinha(clientId: number, corpo: Record<string, unknown>) {
  return api.post<EstadoRz>(`/balcao/cliente/${clientId}/rascunho/linhas`, corpo)
}

/** O inventário inteiro do QuickBooks, buscado e paginado no servidor (o espelho do catálogo). */
export function BuscaQbo({ onEscolher, rotulo }: { onEscolher: (i: ItemQboLista) => void; rotulo?: string }) {
  const toast = useToast()
  const [q, setQ] = useState('')
  const [d, setD] = useState<{ itens: ItemQboLista[]; total: number } | null>(null)
  const [limite, setLimite] = useState(30)
  const [atualizando, setAtualizando] = useState(false)
  const carregar = useCallback(() => {
    api.get<{ itens: ItemQboLista[]; total: number }>(`/balcao/quickbooks/itens${qs({ q: q.trim() || undefined, limit: limite })}`)
      .then(setD).catch(e => toast((e as ApiError).message, 'crit'))
  }, [q, limite, toast])
  useEffect(() => { const t = setTimeout(carregar, 250); return () => clearTimeout(t) }, [carregar])
  async function atualizar() {
    setAtualizando(true)
    try { await api.post('/balcao/quickbooks/itens/atualizar'); carregar() }
    catch (e) { toast((e as ApiError).message, 'warn') } finally { setAtualizando(false) }
  }
  return <div className="stack" style={{ gap: 8 }}>
    <label className="fld"><span>{rotulo || tr("Buscar no inventário do QuickBooks")}</span>
      <input value={q} onChange={e => { setQ(e.target.value); setLimite(30) }} placeholder={tr("bumper, chain, MG…")} autoComplete="off" /></label>
    {!d ? <span className="spin" /> : !d.itens.length ? <p className="small muted" style={{ margin: 0 }}>{tr("Nada no inventário com esse nome.")}</p>
      : <ul className="rz-busca">{d.itens.map(i => <li key={i.id}><button type="button" className="btn" onClick={() => onEscolher(i)}>
        <span>{i.full_name || i.name}</span><span className="mono">{i.price != null ? usd(i.price) : '—'}</span></button></li>)}</ul>}
    <div className="rz-acoes">
      {d && d.total > d.itens.length && <button type="button" className="btn ghost" onClick={() => setLimite(l => Math.min(100, l + 30))}>{tr("Carregar mais")}</button>}
      <button type="button" className="btn ghost" disabled={atualizando} onClick={atualizar}>{atualizando ? <span className="spin" /> : tr("Atualizar do QuickBooks")}</button>
    </div>
  </div>
}

type Escolha = { origem: 'estoque'; item_id: number; nome: string; preco: number | null }
  | { origem: 'quickbooks'; qbo_item_id: string; nome: string; preco: number | null } | { origem: 'livre' }

/** "Adicionar linha": a peça do estoque, um item do QuickBooks ou uma linha livre, com quantidade e preço. */
function NovaLinha({ clientId, inicial, onFeito, onFechar }: { clientId: number; inicial?: Escolha; onFeito: (r: EstadoRz) => void; onFechar: () => void }) {
  const toast = useToast()
  const [aba, setAba] = useState<'estoque' | 'quickbooks' | 'livre'>(inicial?.origem || 'estoque')
  const [esc, setEsc] = useState<Escolha | null>(inicial || null)
  const [itens, setItens] = useState<{ id: number; name: string; price: number | null }[]>([])
  const [busca, setBusca] = useState('')
  const [nome, setNome] = useState('')
  const [qty, setQty] = useState('1')
  const [preco, setPreco] = useState(inicial && 'preco' in inicial && inicial.preco != null ? String(inicial.preco) : '')
  const [desc, setDesc] = useState('')
  const [indo, setIndo] = useState(false)
  useEffect(() => { api.get<{ itens: { id: number; name: string; price: number | null }[] }>('/estoque').then(r => setItens(r.itens)).catch(() => undefined) }, [])
  const termo = busca.trim().toLowerCase()
  const lista = (termo ? itens.filter(i => i.name.toLowerCase().includes(termo)) : itens).slice(0, 40)
  function escolher(e: Escolha) { setEsc(e); if ('preco' in e) setPreco(e.preco != null ? String(e.preco) : '') }
  const escolhida = aba === 'livre' ? nome.trim() !== '' : !!esc && esc.origem === aba
  async function salvar(e: FormEvent) {
    e.preventDefault()
    if (!escolhida) return
    setIndo(true)
    try {
      const base = aba === 'livre' ? { origem: 'livre', nome: nome.trim() }
        : esc!.origem === 'estoque' ? { origem: 'estoque', item_id: esc!.item_id } : { origem: 'quickbooks', qbo_item_id: (esc as { qbo_item_id: string }).qbo_item_id }
      const r = await adicionarLinha(clientId, { ...base, qty: num(qty) ?? 1, preco: num(preco), descricao: desc.trim() || null })
      toast(tr("Linha no rascunho."), 'ok'); onFeito(r); onFechar()
    } catch (er) { toast((er as ApiError).message, 'crit') } finally { setIndo(false) }
  }
  return <Scrim onMouseDown={onFechar}><form className="modal stack" style={{ maxWidth: 560, gap: 12 }} onMouseDown={e => e.stopPropagation()} onSubmit={salvar}
    role="dialog" aria-modal="true" aria-labelledby="rz-nova-h">
    <h3 id="rz-nova-h" style={{ margin: 0 }}>{tr("Adicionar linha ao rascunho")}</h3>
    <div className="rz-acoes" role="radiogroup" aria-label={tr("De onde vem a linha")}>
      {(['estoque', 'quickbooks', 'livre'] as const).map(k => <button key={k} type="button" role="radio" aria-checked={aba === k}
        className={`btn${aba === k ? ' primary' : ''}`} onClick={() => setAba(k)}>{k === 'estoque' ? tr("Estoque") : k === 'quickbooks' ? tr("QuickBooks") : tr("Linha livre")}</button>)}
    </div>
    {aba === 'estoque' && (esc?.origem === 'estoque' ? <Banner tone="ok">{esc.nome} <button type="button" className="btn ghost" onClick={() => setEsc(null)}>{tr("Trocar")}</button></Banner> : <>
      <label className="fld"><span>{tr("Buscar peça no estoque")}</span><input value={busca} onChange={e => setBusca(e.target.value)} autoComplete="off" /></label>
      <ul className="rz-busca">{lista.map(i => <li key={i.id}><button type="button" className="btn" onClick={() => escolher({ origem: 'estoque', item_id: i.id, nome: i.name, preco: i.price })}>
        <span>{i.name}</span><span className="mono">{i.price != null ? usd(i.price) : tr("sem preço")}</span></button></li>)}</ul></>)}
    {aba === 'quickbooks' && (esc?.origem === 'quickbooks' ? <Banner tone="ok">{esc.nome} <button type="button" className="btn ghost" onClick={() => setEsc(null)}>{tr("Trocar")}</button></Banner>
      : <BuscaQbo onEscolher={i => escolher({ origem: 'quickbooks', qbo_item_id: i.id, nome: i.full_name || i.name, preco: i.price })} />)}
    {aba === 'livre' && <label className="fld"><span>{tr("Nome da linha")} <i>{tr("se não existir no QuickBooks, o item é criado lá")}</i></span>
      <input value={nome} maxLength={100} onChange={e => setNome(e.target.value)} placeholder={tr("Solda no chassi")} /></label>}
    <div className="rz-campos">
      <label className="fld"><span>{tr("Quantidade")}</span><input inputMode="decimal" value={qty} onChange={e => setQty(e.target.value)} /></label>
      <label className="fld"><span>{tr("Preço unitário (US$)")}</span><input inputMode="decimal" value={preco} onChange={e => setPreco(e.target.value)} /></label>
    </div>
    <label className="fld"><span>{tr("Descrição (opcional)")}</span><input value={desc} maxLength={300} onChange={e => setDesc(e.target.value)} /></label>
    <div className="rz-acoes" style={{ justifyContent: 'flex-end' }}>
      <button type="button" className="btn" onClick={onFechar}>{tr("Cancelar")}</button>
      <button className="btn primary" disabled={indo || !escolhida}>{indo ? <span className="spin" /> : tr("Pôr no rascunho")}</button></div>
  </form></Scrim>
}

function LinhaEditavel({ clientId, l, travada, onMudou }: { clientId: number; l: LinhaRz; travada: boolean; onMudou: (r: EstadoRz) => void }) {
  const toast = useToast()
  const [qty, setQty] = useState(String(l.qty))
  const [preco, setPreco] = useState(l.preco != null ? String(l.preco) : '')
  useEffect(() => { setQty(String(l.qty)); setPreco(l.preco != null ? String(l.preco) : '') }, [l.qty, l.preco])
  async function salvar(campo: 'qty' | 'preco', valor: string) {
    const n = num(valor)
    if (n === null || n === (campo === 'qty' ? l.qty : l.preco)) return
    try { onMudou(await api.patch<EstadoRz>(`/balcao/cliente/${clientId}/rascunho/linhas/${l.id}`, { [campo]: n })) }
    catch (e) { toast((e as ApiError).message, 'crit') }
  }
  async function remover() {
    try { onMudou(await api.del<EstadoRz>(`/balcao/cliente/${clientId}/rascunho/linhas/${l.id}`)); toast(tr("Linha removida."), 'ok') }
    catch (e) { toast((e as ApiError).message, 'crit') }
  }
  return <li className="rz-linha">
    <div className="rz-nome"><b>{l.nome}</b><Chip tone="neutral">{ORIGEM[l.origem]}</Chip>
      {l.preco == null && <Chip tone="crit">{tr("sem preço")}</Chip>}
      {l.preco_digitado && <Chip tone="warn" title={l.preco_tabela != null ? tr("Tabela: {0}", usd(l.preco_tabela)) : tr("Sem preço de tabela")}>{tr("preço digitado")}</Chip>}
      {l.sem_saldo && <Chip tone="warn">{tr("sem saldo no estoque")}</Chip>}</div>
    {l.descricao && <span className="small muted">{l.descricao}</span>}
    <div className="rz-campos">
      <label className="fld"><span>{tr("Qtd.")}</span><input inputMode="decimal" value={qty} disabled={travada} aria-label={tr("Quantidade de {0}", l.nome)}
        onChange={e => setQty(e.target.value)} onBlur={() => salvar('qty', qty)} /></label>
      <label className="fld"><span>{tr("Preço (US$)")}</span><input inputMode="decimal" value={preco} disabled={travada} aria-label={tr("Preço de {0}", l.nome)}
        onChange={e => setPreco(e.target.value)} onBlur={() => salvar('preco', preco)} /></label>
      <span className="rz-total mono">{l.total != null ? usd(l.total) : '—'}</span>
      {!travada && <button type="button" className="btn ghost" onClick={remover} aria-label={tr("Remover {0}", l.nome)}>{tr("Remover")}</button>}
    </div>
  </li>
}

/** O rascunho do card aberto. `versao` muda quando a tela de fora pôs uma linha (peça lida no leitor). */
export function RascunhoInvoice({ clientId, versao, onEstado, onFaturou }: { clientId: number; versao: number
  onEstado: (aberto: boolean) => void; onFaturou: () => void }) {
  const toast = useToast()
  const [d, setD] = useState<EstadoRz | null>(null)
  const [nova, setNova] = useState(false)
  const [indo, setIndo] = useState(false)
  const aplicar = useCallback((r: EstadoRz) => { setD(r); onEstado(!!r.rascunho) }, [onEstado])
  useEffect(() => { api.get<EstadoRz>(`/balcao/cliente/${clientId}/rascunho`).then(aplicar).catch(e => toast((e as ApiError).message, 'crit')) }, [clientId, versao, aplicar, toast])
  async function faturar() {
    setIndo(true)
    try {
      const r = await api.post<EstadoRz>(`/balcao/cliente/${clientId}/rascunho/faturar`)
      aplicar(r); toast(tr("Invoice criada no QuickBooks (não enviada)."), 'ok'); onFaturou()
    } catch (e) {
      toast((e as ApiError).message, 'crit')
      api.get<EstadoRz>(`/balcao/cliente/${clientId}/rascunho`).then(aplicar).catch(() => undefined)
    } finally { setIndo(false) }
  }
  async function descartar() {
    if (!window.confirm(tr("Descartar o rascunho inteiro?"))) return
    try { aplicar(await api.post<EstadoRz>(`/balcao/cliente/${clientId}/rascunho/descartar`)); toast(tr("Rascunho descartado."), 'ok') }
    catch (e) { toast((e as ApiError).message, 'crit') }
  }
  const rz = d?.rascunho
  const travada = rz?.status === 'criando'
  return <Section title={tr("Rascunho de invoice")} count={rz?.linhas.length}>
    {!d ? <span className="spin" /> : <div className="stack" style={{ gap: 10 }}>
      {!rz ? <p className="small muted" style={{ margin: 0 }}>{tr("Monte a invoice com várias peças e valores: do estoque, do inventário do QuickBooks ou numa linha livre. Com o rascunho aberto, cada peça lida no modo COBRAR entra nele.")}</p> : <>
        {rz.erro && <Banner tone={rz.incerto ? 'warn' : 'crit'}>{rz.erro}</Banner>}
        <ul className="rz-linhas">{rz.linhas.map(l => <LinhaEditavel key={l.id} clientId={clientId} l={l} travada={!!travada} onMudou={aplicar} />)}</ul>
        <div className="rz-total-geral"><span>{tr("Total")}</span><span className="mono">{usd(rz.total)}</span></div>
        {rz.sem_preco.length > 0 && <Banner tone="warn">{tr("Sem preço: {0}. Digite o preço para criar a invoice.", rz.sem_preco.join(', '))}</Banner>}
        {!d.gerente && <p className="small muted" style={{ margin: 0 }}>{tr("Criar a invoice é do gerente: ele confere os preços digitados.")}</p>}
      </>}
      <div className="rz-acoes">
        {!travada && <button type="button" className="btn" onClick={() => setNova(true)}>{tr("Adicionar linha")}</button>}
        {rz && d.gerente && <button type="button" className="btn primary" disabled={indo || !(rz.pronto || rz.incerto)} onClick={faturar}>
          {indo ? <span className="spin" /> : rz.incerto ? tr("Criar invoice de novo (não duplica)") : tr("Criar invoice")}</button>}
        {rz && !travada && <button type="button" className="btn ghost" onClick={descartar}>{tr("Descartar rascunho")}</button>}
      </div>
      {d.faturados.length > 0 && <div className="stack" style={{ gap: 4 }}>
        <h3 className="small" style={{ margin: 0 }}>{tr("Faturados")}</h3>
        {d.faturados.map(f => <div key={f.id} className="small">{tr("Invoice {0} · {1} · {2}", f.doc_number || '—', usd(f.total), f.invoice_status === 'enviada' ? tr("enviada") : tr("não enviada"))}</div>)}
      </div>}
    </div>}
    {nova && <NovaLinha clientId={clientId} onFeito={aplicar} onFechar={() => setNova(false)} />}
  </Section>
}

/** Peça sem preço final (ou sem item no QuickBooks) lida no COBRAR: em vez de travar, vai para o rascunho com o preço. */
export function PorNoRascunho({ clientId, item, motivo, onFeito, onFechar }: { clientId: number; item: { id: number; name: string; price: number | null }
  motivo: string; onFeito: () => void; onFechar: () => void }) {
  const toast = useToast()
  const [preco, setPreco] = useState(item.price != null ? String(item.price) : '')
  const [qty, setQty] = useState('1')
  const [indo, setIndo] = useState(false)
  async function salvar(e: FormEvent) {
    e.preventDefault(); setIndo(true)
    try { await adicionarLinha(clientId, { origem: 'estoque', item_id: item.id, qty: num(qty) ?? 1, preco: num(preco) }); toast(tr("{0}: no rascunho.", item.name), 'ok'); onFeito(); onFechar() }
    catch (er) { toast((er as ApiError).message, 'crit') } finally { setIndo(false) }
  }
  return <Scrim onMouseDown={onFechar}><form className="modal stack" style={{ maxWidth: 480, gap: 12 }} onMouseDown={e => e.stopPropagation()} onSubmit={salvar}
    role="dialog" aria-modal="true" aria-labelledby="rz-por-h">
    <h3 id="rz-por-h" style={{ margin: 0 }}>{tr("Pôr no rascunho")}</h3>
    <p style={{ margin: 0 }}><b>{item.name}</b></p>
    <Banner tone="warn">{motivo}</Banner>
    <p className="small muted" style={{ margin: 0 }}>{tr("Digite o preço desta venda: a peça entra no rascunho de invoice deste cliente e o gerente cria a invoice (o item do QuickBooks é criado se faltar).")}</p>
    <div className="rz-campos">
      <label className="fld"><span>{tr("Quantidade")}</span><input inputMode="decimal" value={qty} onChange={e => setQty(e.target.value)} /></label>
      <label className="fld"><span>{tr("Preço unitário (US$)")}</span><input inputMode="decimal" value={preco} onChange={e => setPreco(e.target.value)} autoFocus /></label>
    </div>
    <div className="rz-acoes" style={{ justifyContent: 'flex-end' }}>
      <button type="button" className="btn" onClick={onFechar}>{tr("Cancelar")}</button>
      <button className="btn primary" disabled={indo}>{indo ? <span className="spin" /> : tr("Pôr no rascunho")}</button></div>
  </form></Scrim>
}
