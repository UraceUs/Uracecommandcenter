/* Suits · Alpha Line (#153): pedidos de macacão do contato à entrega.
 *
 * Dono, 08/10: "na aba de suítes ... registrar novo pedido ... Sempre dê a oportunidade ali de
 * eu adicionar uma nota, às vezes um screenshot para IA poder entender, já avançar com aquilo ali
 * no status que estiver" e "O envio ao Usman ... tem um padrão de envio. Salva esse padrão como
 * template". O que vivia no projeto SUITS do Asana (pedidos, leads e fornecedores) vem para cá.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, Navigate, NavLink, useNavigate, useParams } from 'react-router-dom'
import { api, ApiError, qs } from '../api/client'
import { useGet, usePaginado } from '../api/hooks'
import type { Client } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { Chip, Empty, ErrorState, Loading, PageHeader, Scrim, Section } from '../components/ui'
import { Icon } from '../components/Icon'
import { Md } from '../components/Md'
import { useToast } from '../components/useToast'
import { Picker } from '../components/Unir'
import { Cartao, CdItem, CdLista, type TomD } from '../components/Cartao'
import { tr, LOCALE } from '../i18n'

interface Etapa { codigo: string; nome: string; descricao: string }
interface Medida { chave: string; numero: string; nome: string; tipo: 'comp' | 'peso' | 'texto' }
interface Campo { chave: string; nome: string }
interface Meta { etapas: Etapa[]; medidas: Medida[]; design: Campo[]; transicoes?: Record<string, string[]>; so_da_equipe?: string[] }
interface Linha { id: number; title: string; product: string; quantity: number; customer_name: string | null; driver_name: string | null
  status: string; closed: number; order_date: string | null; due_on: string | null; source: string; fornecedor: string | null
  notas: number; ultima_nota: string | null; updated_at: string | null; created_at: string
  discarded_at?: string | null; discard_reason?: string | null; ia_ligada?: number; is_test?: number; wa_rascunhos?: number }
interface Nota { id: number; status: string | null; kind: string; text: string | null; tem_imagem: number; arquivo?: string | null; command_id: number | null
  created_at: string; autor: string | null; ia?: { status: string; output: string | null; error: string | null } | null }
type Valor = { v: number; u: string } | { t: string }
interface PedidoApi extends Omit<Linha, 'notas'> { customer_email: string | null; customer_phone: string | null; ship_address: string | null
  language: string | null; supplier_id: number | null; fornecedor_email: string | null; fornecedor: string | null
  designer_id: number | null; designer: { id: number | null; nome: string | null; email: string | null } | null; paid_at: string | null; tracking: string | null
  asana_gid: string | null; asana_notes: string | null; asana_status: string | null; measurements: Record<string, Valor>
  site_order: string | null; gmail_thread_cliente: string | null; gmail_thread_designer: string | null; gmail_thread_fornecedor: string | null
  medidas_texto: Record<string, string>; faltam_medidas: string[]; design: Record<string, string>; criado_por: string | null; notas: Nota[]
  client_id: number | null; cliente_nome: string | null; cliente_piloto: string | null
  estado_medidas: Record<string, EstadoMedida>; arte_final: string[]; aprovacao: EstadoAprovacao | null; proxima_acao: string
  saude_ponte: SaudePedido; preparados: Preparado[]; checked_at: string | null; welcome_sent_at: string | null }
/** #382: a aprovação final do cliente, amarrada à arte final e às medidas (o hash de cada uma). */
interface Aprovacao { id: number; message_id: string | null; excerpt: string; approved_at: string; source: 'ia' | 'manual'; status: string
  stale_reason: string | null; files: string[]; created_at: string }
interface EstadoAprovacao { estado: 'valida' | 'desatualizada' | 'nenhuma'; aprovacao: Aprovacao | null; bloqueios: string[]; arte_final: string[]
  versao: string; pedido_final: { versao: string; em: string; simulado: boolean; atual: boolean } | null }
interface EstadoMedida { estado: 'preenchida' | 'conferida' | 'suspeita'; motivo: string | null }
interface SaudePedido { ultima_tentativa: string | null; ultimo_sucesso: string | null; ultimo_erro: string | null; ultimo_erro_em: string | null; modo: string | null }
interface Preparado { id: number; subject: string; body: string; attachments: string[]; status: 'preparado' | 'enviado' | 'descartado'; created_at: string; decided_at: string | null }
interface SaudePonte { ultima_rodada: { at: string; eventos: number; erros: number; simulacao: boolean; pulada?: string | null; ambiguos?: number } | null
  simulacao: boolean; ligada: boolean; manual: boolean; preparados: number; com_erro: number }
interface Endereco { para: string | null; assunto: string; corpo: string; whatsapp: string; faltam: string[] }
/** O que o cadastro já sabe do cliente (#158: inserção manual sempre com "vincular ao cliente"). */
interface DadosCliente { client_id: number; customer_name: string | null; customer_email: string | null; customer_phone: string | null
  driver_name: string | null; ship_address: string | null; medidas: { valores: Record<string, number>; unidade: string; unidade_peso: string } | null
  de_onde: { card: boolean; conta_do_site: boolean; piloto: string | null } }
const puxarCliente = (id: number) => api.get<DadosCliente>(`/suits/cliente/${id}`)
function oQuePuxou(d: DadosCliente) {
  const itens = ['nome', d.customer_email && 'e-mail', d.customer_phone && 'telefone', d.driver_name && 'piloto',
    d.ship_address && tr("endereço da conta do site"), d.medidas && `${Object.keys(d.medidas.valores).length} medida(s) do piloto ${d.de_onde.piloto || ''}`.trim()]
  return 'Puxado do cadastro: ' + itens.filter(Boolean).join(', ') + '.'
}
const cartao = (id: number, nome: string | null, piloto: string | null) => ({ id, name: nome || '', pilot_name: piloto, email: null, phone: null } as unknown as Client)
interface Resumo { por_etapa: Record<string, number>; abertos: number; fechados: number; descartados?: number; testes?: number; leads: number; fornecedores: number }
interface Lead { id: number; name: string; email: string | null; phone: string | null; notes: string | null; status: string; order_id: number | null; created_at: string; client_id: number | null }
interface Designer { id: number; name: string; email: string | null; notes: string | null; is_current: number; pedidos?: number }
interface Fornecedor { id: number; name: string; contact: string | null; email: string | null; phone: string | null; has_fia: number | null
  status: string | null; price: string | null; shipping: string | null; payment: string | null; lead_time: string | null; comments: string | null
  is_current: number; pedidos: number; asana_gid: string | null }
interface Email { para: string | null; assunto: string; corpo: string; faltam: string[]; anexos?: string[]; fornecedor: Fornecedor | null }
interface PonteCfg { ponte_ligada: string; envio_automatico: string; designer_nome: string; designer_email: string; assinatura: string; boas_vindas: string; politica: string }
interface Ponte { config: PonteCfg; manual: boolean; motor: string; ultima_rodada: { at: string; detail: string } | null }
interface Anexo { nome: string; bytes: number }

const TOM: Record<string, 'neutral' | 'warn' | 'info' | 'accent' | 'ok' | 'crit'> = {
  standby: 'neutral', awaiting_measurements: 'warn', design_pending: 'info', design_review: 'warn', approved: 'accent',
  sent_to_supplier: 'info', supplier_accepted: 'info', in_production: 'info', photos_received: 'warn', checked: 'accent',
  address_sent: 'info', in_transit: 'accent', delivered: 'ok', canceled: 'neutral' }
const IDIOMAS: [string, string][] = [['en', tr("Inglês")], ['pt', tr("Português")], ['es', tr("Espanhol")], ['it', tr("Italiano")], ['fr', tr("Francês")], ['de', tr("Alemão")]]
// #447: imagem vira foto na linha do tempo; o resto vai para os arquivos do pedido
const IMAGENS = ['image/png', 'image/jpeg', 'image/webp']
const ARQUIVO_MAX = 25 * 1024 * 1024
const KIND: Record<string, string> = { nota: tr("nota"), etapa: tr("etapa"), ia: 'IA', email: tr("e-mail"), whatsapp: 'WhatsApp' }
const ESTADO_MED: Record<string, string> = { preenchida: tr("preenchida"), conferida: tr("conferida"), suspeita: tr("suspeita") }
const horaFL = (iso: string) => { const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z'); return isNaN(d.getTime()) ? iso
  : d.toLocaleString(LOCALE(), { timeZone: 'America/New_York', day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }).replace(',', '') }
const dia = (iso: string | null) => iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(2, 4)}` : '—'

function useMeta() { return useGet<Meta>('/suits/etapas') }
function nomeEtapa(meta: Meta | null, c: string) { return meta?.etapas.find(e => e.codigo === c)?.nome || c }
/** #313: o tom da pílula do cartão D (o accent dos chips vira o azul da informação) */
const tomD = (t: string): TomD => t === 'accent' ? 'info' : (t as TomD)
function EtapaChip({ meta, s }: { meta: Meta | null; s: string }) { return <Chip tone={TOM[s] || 'neutral'}>{nomeEtapa(meta, s)}</Chip> }

/* ============================================================ a aba */
const ABAS: [string, string][] = [['', tr("Pedidos")], ['leads', tr("Leads")], ['contatos', tr("Contatos")], ['ponte', tr("Ponte de e-mail")], ['whatsapp', 'WhatsApp'], ['modelo', tr("E-mail ao fornecedor")]]

export function Suits() {
  const { aba = '' } = useParams()
  const { can } = useAuth()
  const toast = useToast()
  const nav = useNavigate()
  const meta = useMeta()
  const resumo = useGet<Resumo>('/suits/resumo')
  const [novo, setNovo] = useState(false)
  const [importando, setImportando] = useState(false)

  async function importar() {
    setImportando(true)
    try {
      const r = await api.post<{ pedidos: number; leads: number; fornecedores: number; ja_tinha: number }>('/suits/importar')
      toast(tr("Do Asana: {0} pedido(s), {1} lead(s) e {2} fornecedor(es) novos; {3} já estavam aqui.", r.pedidos, r.leads, r.fornecedores, r.ja_tinha), 'ok')
      resumo.reload(); nav('/suits')
    } catch (e) { toast((e as ApiError).message, 'crit') } finally { setImportando(false) }
  }

  return <>
    <PageHeader title={tr("Suits · Alpha Line")} eyebrow={tr("Macacões sob medida")}
      help={<>{tr("Cada pedido de macacão, do contato à entrega direta ao cliente. Em qualquer etapa dá para escrever uma nota, anexar um print e pedir à IA para seguir dali. Produção só com a aprovação final escrita do cliente; o endereço vai ao fornecedor só depois do OK nas fotos do WhatsApp.")}</>}>
      {can('MANAGER') && <button className="btn ghost" disabled={importando} onClick={importar}>{importando ? tr("Importando…") : tr("Importar do Asana")}</button>}
      {can('OPERATOR') && <button className="btn primary" onClick={() => setNovo(true)}><Icon name="plus" size={16} /> {tr("Registrar novo pedido")}</button>}
    </PageHeader>
    <SaudeTopo />
    <nav className="tabs" aria-label={tr("Suits")}>{ABAS.map(([path, rot]) => <NavLink key={path} to={path ? `/suits/${path}` : '/suits'} end
      className={() => (aba === path ? 'on' : '')}>{rot}{path === 'leads' && resumo.data ? <span className="count">{resumo.data.leads}</span> : null}</NavLink>)}</nav>
    {meta.error ? <div className="card"><ErrorState error={meta.error} retry={meta.reload} /></div>
      : aba === 'leads' ? <Leads />
      : aba === 'contatos' ? <Contatos />
      : aba === 'fornecedores' ? <Navigate to="/suits/contatos" replace />
      : aba === 'modelo' ? <Modelo />
      : aba === 'ponte' ? <Ponte />
      : aba === 'whatsapp' ? <WhatsApp />
      : <Pedidos meta={meta.data} resumo={resumo.data} />}
    {novo && <NovoPedido meta={meta.data} onClose={() => setNovo(false)} onDone={id => nav(`/suits/${id}`)} />}
  </>
}

function Pedidos({ meta, resumo }: { meta: Meta | null; resumo: Resumo | null }) {
  const [estado, setEstado] = useState<'abertos' | 'fechados' | 'descartados'>('abertos')
  const [etapa, setEtapa] = useState('')
  const [busca, setBusca] = useState('')
  const base = `/suits${qs({ estado, status: etapa || undefined, q: busca.trim() || undefined })}`
  const { itens, total, erro, carregando, mais, temMais, recarregar } = usePaginado<Linha>(base, 50)
  const titulo = estado === 'abertos' ? tr("Em andamento") : estado === 'fechados' ? tr("Histórico") : tr("Descartados")
  return <Section title={titulo} count={total}
    right={<div className="tabs"><button className={estado === 'abertos' ? 'on' : ''} onClick={() => { setEstado('abertos'); setEtapa('') }}>{tr("Em andamento")}</button>
      <button className={estado === 'fechados' ? 'on' : ''} onClick={() => { setEstado('fechados'); setEtapa('') }}>{tr("Histórico")}</button>
      {(resumo?.descartados || estado === 'descartados') ? <button className={estado === 'descartados' ? 'on' : ''} onClick={() => { setEstado('descartados'); setEtapa('') }}
        title={tr("O que chegou por e-mail e não era pedido de macacão. Nada foi apagado.")}>{tr("Descartados")}</button> : null}</div>}>
    {estado === 'descartados' && <p className="small muted">{tr("Não eram pedidos de macacão: saíram das listas e a ponte de e-mail não lê mais essas conversas. Abra um para restaurar.")}</p>}
    {estado === 'abertos' && meta && <div className="suit-filtro" role="group" aria-label={tr("Filtrar por etapa")}>
      <button className={`btn sm${etapa ? ' ghost' : ' on'}`} onClick={() => setEtapa('')}>{tr("Todas ·")} {resumo?.abertos ?? '…'}</button>
      {meta.etapas.filter(e => !['delivered', 'canceled'].includes(e.codigo)).map(e =>
        <button key={e.codigo} className={`btn sm${etapa === e.codigo ? ' on' : ' ghost'}`} onClick={() => setEtapa(e.codigo)} title={e.descricao}>
          {e.nome} · {resumo?.por_etapa[e.codigo] || 0}</button>)}
    </div>}
    <label className="fld"><span className="sr-only">{tr("Buscar")}</span><input value={busca} onChange={e => setBusca(e.target.value)} placeholder={tr("Buscar por cliente, piloto ou e-mail")} /></label>
    {erro ? <ErrorState error={erro} retry={recarregar} /> : carregando && !itens.length ? <Loading />
      : !itens.length ? <Empty title={estado === 'abertos' ? tr("Nenhum pedido em andamento") : estado === 'fechados' ? tr("Nada no histórico") : tr("Nada descartado")}>{tr("Registre um pedido novo ou importe o que está no Asana.")}</Empty>
      : <div className="cd-grade">{itens.map(p => <Cartao key={p.id} id={`suit-${p.id}`} abrir={`/suits/${p.id}`}
          estado={p.discarded_at ? tr("descartado") : nomeEtapa(meta, p.status)} tom={p.discarded_at ? 'neutral' : tomD(TOM[p.status] || 'neutral')}
          avatar={p.driver_name || p.customer_name || p.title} nome={p.title}
          sub={[[p.product !== 'Suit' ? p.product : null, p.quantity > 1 ? `${p.quantity} un.` : null, p.fornecedor].filter(Boolean).join(' · '),
            p.source === 'asana' ? 'do Asana' : p.source === 'ia' ? 'pela IA' : null]}
          grande={p.order_date ? dia(p.order_date) : null} detalhe={p.order_date ? tr("pedido") : null}>
          {((!p.discarded_at && p.ia_ligada === 0) || p.notas > 0 || p.is_test || !!p.wa_rascunhos) && <CdLista>
            {p.is_test ? <CdItem tom="info">{tr("teste")}</CdItem> : null}
            {!p.discarded_at && p.ia_ligada === 0 && <CdItem tom="warn">{tr("IA desligada")}</CdItem>}
            {!!p.wa_rascunhos && <CdItem tom="warn" valor={p.wa_rascunhos}>{tr("WhatsApp para aprovar")}</CdItem>}
            {p.notas > 0 && <CdItem tom="info" glifo="✎" valor={p.notas}>{tr("notas")}</CdItem>}
          </CdLista>}
        </Cartao>)}</div>}
    {temMais && <button className="btn ghost" disabled={carregando} onClick={mais}>{tr("Carregar mais")}</button>}
  </Section>
}

/* ============================================================ registrar */
function NovoPedido({ meta, onClose, onDone }: { meta: Meta | null; onClose: () => void; onDone: (id: number) => void }) {
  const toast = useToast()
  const forn = useGet<Fornecedor[]>('/suits/fornecedores')
  const [f, setF] = useState<Record<string, string>>({ language: 'en', product: 'Suit', quantity: '1' })
  const [semIa, setSemIa] = useState(false)
  const [teste, setTeste] = useState(false)
  const [design, setDesign] = useState<Record<string, string>>({})
  const [indo, setIndo] = useState(false)
  const [cli, setCli] = useState<Client | null>(null)
  const [puxado, setPuxado] = useState<DadosCliente | null>(null)
  const set = (k: string) => (e: { target: { value: string } }) => setF(x => ({ ...x, [k]: e.target.value }))
  async function escolher(c: Client | null) {
    setCli(c); setPuxado(null)
    if (!c) return
    try {
      const d = await puxarCliente(c.id)
      setPuxado(d)
      setF(x => ({ ...x, customer_name: d.customer_name || x.customer_name || '', customer_email: d.customer_email || x.customer_email || '',
        customer_phone: d.customer_phone || x.customer_phone || '', driver_name: d.driver_name || x.driver_name || '',
        ship_address: d.ship_address || x.ship_address || '' }))
    } catch (e) { toast((e as ApiError).message, 'crit') }
  }
  async function salvar() {
    if (!(f.customer_name || '').trim()) { toast(tr("Diga o nome do cliente."), 'warn'); return }
    setIndo(true)
    try {
      const p = await api.post<{ id: number }>('/suits', { ...f, quantity: Number(f.quantity) || 1,
        supplier_id: f.supplier_id ? Number(f.supplier_id) : (forn.data || []).find(x => x.is_current)?.id ?? null,
        client_id: cli?.id ?? null, medidas: puxado?.medidas ?? undefined,
        design, nota: f.nota || null, ia_ligada: !semIa, is_test: teste })
      toast(tr("Pedido registrado."), 'ok'); onDone(p.id); onClose()
    } catch (e) { toast((e as ApiError).message, 'crit') } finally { setIndo(false) }
  }
  return <Scrim onMouseDown={onClose}><div className="modal" style={{ maxWidth: 640 }} onMouseDown={e => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={tr("Registrar novo pedido")}>
    <h3>{tr("Registrar novo pedido")}</h3>
    <Picker label={tr("Vincular ao cliente (puxa os dados do cadastro)")} value={cli} onPick={escolher} />
    {puxado && <p className="small muted" style={{ marginTop: 0 }}>{oQuePuxou(puxado)}</p>}
    <div className="suit-form">
      <label className="fld"><span>{tr("Cliente")}</span><input value={f.customer_name || ''} onChange={set('customer_name')} /></label>
      <label className="fld"><span>{tr("Piloto (se não for o cliente)")}</span><input value={f.driver_name || ''} onChange={set('driver_name')} /></label>
      <label className="fld"><span>{tr("E-mail")}</span><input type="email" value={f.customer_email || ''} onChange={set('customer_email')} /></label>
      <label className="fld"><span>{tr("Telefone")}</span><input type="tel" value={f.customer_phone || ''} onChange={set('customer_phone')} /></label>
      <label className="fld"><span>{tr("Idioma do cliente")}</span><select value={f.language} onChange={set('language')}>{IDIOMAS.map(([k, n]) => <option key={k} value={k}>{n}</option>)}</select></label>
      <label className="fld"><span>{tr("Fornecedor")}</span><select value={f.supplier_id || ''} onChange={set('supplier_id')}>
        <option value="">{tr("o atual")}{(forn.data || []).find(x => x.is_current) ? ` (${(forn.data || []).find(x => x.is_current)!.name})` : ''}</option>
        {(forn.data || []).map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
      <label className="fld"><span>{tr("Produto")}</span><select value={f.product} onChange={set('product')}>{['Suit', 'T-shirt', 'Gloves', 'Outro'].map(x => <option key={x}>{x}</option>)}</select></label>
      <label className="fld"><span>{tr("Quantidade")}</span><input type="number" min={1} max={50} inputMode="numeric" value={f.quantity} onChange={set('quantity')} /></label>
    </div>
    <label className="fld"><span>{tr("Endereço de entrega (o fornecedor manda direto)")}</span><textarea rows={2} value={f.ship_address || ''} onChange={set('ship_address')} /></label>
    {meta && <details className="suit-mais"><summary>{tr("Design (opcional agora)")}</summary><div className="suit-form">
      {meta.design.map(d => <label key={d.chave} className="fld"><span>{d.nome}</span><input value={design[d.chave] || ''} onChange={e => setDesign(x => ({ ...x, [d.chave]: e.target.value }))} /></label>)}
    </div></details>}
    <div className="suit-checks">
      <label className="check suit-ia"><input type="checkbox" checked={semIa} onChange={e => setSemIa(e.target.checked)} /> {tr("Nascer com a IA desligada (a ponte não age)")}</label>
      <label className="check suit-ia"><input type="checkbox" checked={teste} onChange={e => setTeste(e.target.checked)} /> {tr("Pedido de teste (nunca manda e-mail real; não conta nem avisa)")}</label>
    </div>
    <label className="fld"><span>{tr("Nota (o que já se sabe)")}</span><textarea rows={3} value={f.nota || ''} onChange={set('nota')} placeholder={tr("pagou?, prazo, de onde veio o pedido, link da conversa")} /></label>
    <div className="modal-foot"><button className="btn ghost" onClick={onClose}>{tr("Cancelar")}</button>
      <button className="btn primary" disabled={indo} onClick={salvar}>{indo ? tr("Registrando…") : tr("Registrar")}</button></div>
  </div></Scrim>
}

/* ============================================================ o pedido */
export function SuitPedido() {
  const { aba: id } = useParams()           // /suits/:aba — o número do pedido chega no mesmo segmento das abas
  const meta = useMeta()
  const p = useGet<PedidoApi>(`/suits/${id}`, 15000)
  if (p.error) return <><PageHeader title={tr("Pedido de macacão")} /><div className="card"><ErrorState error={p.error} retry={p.reload} /></div></>
  if (!p.data || !meta.data) return <><PageHeader title={tr("Pedido de macacão")} /><div className="card"><Loading /></div></>
  const d = p.data
  return <>
    <PageHeader title={d.title} eyebrow={<><Link to="/suits">{tr("Suits · Alpha Line")}</Link> {tr("· pedido #")}{d.id}{d.product !== 'Suit' ? ` · ${d.product}` : ''}</>}>
      {d.discarded_at ? <Chip tone="neutral">{tr("descartado")}</Chip> : <EtapaChip meta={meta.data} s={d.status} />}
    </PageHeader>
    <Descarte pedido={d} onDone={p.reload} />
    {d.is_test ? <p className="small" role="status" style={{ color: 'var(--info, var(--accent))' }}><b>{tr("Pedido de teste:")}</b> {tr("nenhum e-mail real sai dele, e ele não entra nas contagens nem na Atenção.")}</p> : null}
    {/* #464: o desenho aprovado — as 4 fases, o "Agora" e duas colunas (o que fazer à esquerda, o pedido à direita) */}
    <Etapas meta={meta.data} atual={d.status} />
    {d.client_id ? <p className="small"><Link to={`/clients/${d.client_id}`}>{tr("Card do cliente #{0} ↗", d.client_id)}</Link></p> : null}
    <div className="suit-g">
      <div className="suit-col">
        <section className="card suit-agora" aria-labelledby="agora-t"><div className="card-b">
          <h2 className="h2" id="agora-t">{tr("Agora")} <span className="k">· {nomeEtapa(meta.data, d.status)}</span></h2>
          <p className="suit-proxima">{d.proxima_acao}</p>
        </div></section>
        <NovaNota meta={meta.data} pedido={d} onDone={p.reload} />
        <AprovacaoFinal pedido={d} onDone={p.reload} />
        <Preparados pedido={d} onDone={p.reload} />
        <Linha_do_tempo meta={meta.data} notas={d.notas} pid={d.id} />
      </div>
      <div className="suit-col">
        <Cliente pedido={d} onDone={p.reload} />
        <PonteDoPedido pedido={d} onDone={p.reload} />
        <Medidas meta={meta.data} pedido={d} onDone={p.reload} />
        <Design meta={meta.data} pedido={d} onDone={p.reload} />
        <WhatsAppDoPedido pedido={d} onDone={p.reload} />
        <EmailFornecedor pedido={d} onDone={p.reload} />
        <EnderecoFornecedor pedido={d} onDone={p.reload} />
        {d.asana_notes || d.asana_gid ? <Section title={tr("Como estava no Asana")}>
      {d.asana_status && <p className="small muted">{tr("Status no Asana:")} {d.asana_status}</p>}
      {d.asana_notes && <pre className="suit-pre">{d.asana_notes}</pre>}
      {d.asana_gid && <a href={`https://app.asana.com/0/0/${d.asana_gid}`} target="_blank" rel="noreferrer">{tr("Abrir a tarefa no Asana ↗")}</a>}
    </Section> : null}
      </div>
    </div>
  </>
}

/** #195 (dono, 13/10): "nenhum desse aí foi e-mail de suit … limpa esses daí". Descartar não apaga: tira das listas e da ponte. */
function Descarte({ pedido, onDone }: { pedido: PedidoApi; onDone: () => void }) {
  const toast = useToast()
  const [aberto, setAberto] = useState(false)
  const [motivo, setMotivo] = useState('')
  const [indo, setIndo] = useState(false)
  async function descartar() {
    setIndo(true)
    try { await api.post(`/suits/${pedido.id}/descartar`, { motivo: motivo.trim() || null }); toast(tr("Descartado: saiu das listas e a ponte não lê mais este pedido."), 'ok'); setAberto(false); onDone() }
    catch (e) { toast((e as ApiError).message, 'crit') } finally { setIndo(false) }
  }
  async function restaurar() {
    setIndo(true)
    try { await api.post(`/suits/${pedido.id}/restaurar`); toast(tr("Restaurado: o pedido voltou para a lista."), 'ok'); onDone() }
    catch (e) { toast((e as ApiError).message, 'crit') } finally { setIndo(false) }
  }
  if (pedido.discarded_at) return <div className="card" role="status">
    <p><b>{tr("Descartado em {0}.", new Date(pedido.discarded_at).toLocaleString(LOCALE(), { timeZone: 'America/New_York', dateStyle: 'short', timeStyle: 'short' }))}</b> {pedido.discard_reason || ''}</p>
    <p className="small muted">{tr("Não aparece nas listas e a ponte de e-mail não lê, não responde nem anota nada aqui.")}</p>
    <button className="btn" disabled={indo} onClick={restaurar}>{tr("Restaurar o pedido")}</button>
  </div>
  const ligada = pedido.ia_ligada !== 0
  async function chave() {
    setIndo(true)
    try { await api.post(`/suits/${pedido.id}/ia`, { ligada: !ligada }); toast(ligada ? tr("IA desligada neste pedido: o que chegar por e-mail fica para a equipe.") : tr("IA ligada neste pedido."), 'ok'); onDone() }
    catch (e) { toast((e as ApiError).message, 'crit') } finally { setIndo(false) }
  }
  return <>
    <div className="suit-acoes">
      {/* #198 (dono, 13/10): "um switch para poder ligar e desligar IA naquele pedido" */}
      <button type="button" role="switch" aria-checked={ligada} className="suit-chave" disabled={indo} onClick={chave}
        title={ligada ? tr("A IA lê os e-mails deste pedido, responde e avança as etapas.") : tr("A IA não age neste pedido: o que chegar fica para a equipe.")}>
        <span className={`sw${ligada ? '' : ' off'}`} aria-hidden="true" />
        <span>{tr("IA neste pedido")}: <b>{ligada ? tr("ligada") : tr("desligada")}</b></span>
      </button>
      <button className="btn ghost sm" onClick={() => setAberto(true)}>{tr("Não é pedido de suit")}</button>
    </div>
    {!ligada && <p className="small muted" style={{ margin: '4px 0 0' }}>{tr("Com a IA desligada, ela não responde, não manda e-mail e não altera nada neste pedido. E-mail novo aparece na linha do tempo para a equipe.")}</p>}
    {aberto && <Scrim onMouseDown={() => setAberto(false)}><div className="modal" style={{ maxWidth: 480 }} onMouseDown={e => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="descarte-t">
      <h3 id="descarte-t">{tr("Descartar o pedido #{0}?", pedido.id)}</h3>
      <p className="small muted">{tr("Ele sai de Em andamento e do Histórico, e a ponte para de ler as conversas dele. Nada é apagado: dá para restaurar em Descartados.")}</p>
      <label className="fld"><span>{tr("Por quê (opcional)")}</span>
        <input value={motivo} onChange={e => setMotivo(e.target.value)} placeholder={tr("ex.: fatura da OpenAI, não é macacão")} maxLength={300} /></label>
      <div className="row gap"><button className="btn ghost" onClick={() => setAberto(false)}>{tr("Cancelar")}</button>
        <button className="btn primary" disabled={indo} onClick={descartar}>{indo ? tr("Descartando…") : tr("Descartar")}</button></div>
    </div></Scrim>}
  </>
}

/** #464: as 13 etapas em 4 fases; a fase atual diz em que etapa está e quantas faltam dentro dela */
const FASES: [string, string[]][] = [
  [tr("Medidas e design"), ['standby', 'awaiting_measurements', 'design_pending', 'design_review']],
  [tr("Aprovação"), ['approved']],
  [tr("Produção"), ['sent_to_supplier', 'supplier_accepted', 'in_production', 'photos_received', 'checked']],
  [tr("Entrega"), ['address_sent', 'in_transit', 'delivered']],
]
function Etapas({ meta, atual }: { meta: Meta; atual: string }) {
  const fa = FASES.findIndex(([, cs]) => cs.includes(atual))
  return <ol className="suit-etapas suit-fases" aria-label={tr("Etapas do pedido")}>{FASES.map(([nome, cs], k) => {
    const feita = fa >= 0 && (k < fa || (atual === 'delivered' && k === fa))
    const agora = k === fa && !feita
    return <li key={nome} className={agora ? 'atual' : feita ? 'feita' : ''} aria-current={agora ? 'step' : undefined}
      title={cs.map(c => nomeEtapa(meta, c)).join(' · ')}>
      <span className="n" aria-hidden="true">{feita ? '✓' : k + 1}</span>
      <span className="f"><b>{nome}</b><span className="small">{agora ? (cs.length > 1 ? tr("{0} · {1} de {2}", nomeEtapa(meta, atual), cs.indexOf(atual) + 1, cs.length) : nomeEtapa(meta, atual))
        : cs.map(c => nomeEtapa(meta, c)).join(' · ')}</span></span></li>
  })}</ol>
}

function NovaNota({ meta, pedido, onDone }: { meta: Meta; pedido: PedidoApi; onDone: () => void }) {
  const toast = useToast()
  const [texto, setTexto] = useState('')
  const [etapa, setEtapa] = useState(pedido.status)
  // a etapa do pedido mudou fora daqui (a IA, outra pessoa, outra seção da tela): a escolha volta para a etapa de agora,
  // no render (#433). Antes, a próxima nota salva devolvia o pedido para a etapa de quando a tela abriu (debug 29/10)
  const [statusVisto, setStatusVisto] = useState(pedido.status)
  if (statusVisto !== pedido.status) { setStatusVisto(pedido.status); setEtapa(pedido.status) }
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [ia, setIa] = useState(true)
  const [indo, setIndo] = useState(false)
  const { can } = useAuth()
  // #448/#482: o administrador leva o pedido a qualquer etapa à mão (aconteceu fora do Command Center), com o motivo na
  // nota; vale quando a ordem das etapas ou uma trava (aprovação escrita, foto, endereço, rastreio) impediria
  const admin = can('ADMIN')
  const permitida = (c: string) => c === pedido.status || !meta.transicoes || (meta.transicoes[pedido.status] || []).includes(c)
  const travada = (c: string) => (['approved', 'sent_to_supplier'].includes(c) && pedido.aprovacao?.estado !== 'valida')
    || ['checked', 'address_sent', 'in_transit'].includes(c)
  const liberar = admin && etapa !== pedido.status && (!permitida(etapa) || travada(etapa))
  const nomeEtapa_ = meta.etapas.find(e => e.codigo === etapa)?.nome || etapa
  const ehImagem = !!arquivo && IMAGENS.includes(arquivo.type)
  const previa = useMemo(() => arquivo && ehImagem ? URL.createObjectURL(arquivo) : null, [arquivo, ehImagem])
  async function salvar() {
    if (!texto.trim() && !arquivo && etapa === pedido.status) { toast(tr("Escreva a nota, anexe um arquivo ou mude a etapa."), 'warn'); return }
    if (liberar) return liberarAprovado()
    const fd = new FormData()
    fd.set('texto', texto.trim()); fd.set('status', etapa === pedido.status ? '' : etapa); fd.set('pedir_ia', String(ia && pedido.ia_ligada !== 0 && !!(texto.trim() || arquivo)))
    if (arquivo) {
      if (arquivo.size > ARQUIVO_MAX) { toast(tr("Arquivo grande demais (máximo 25 MB)."), 'warn'); return }
      fd.set('arquivo', arquivo)
    }
    setIndo(true)
    try {
      const r = await api.postForm<{ id: number | null; command_id: number | null }>(`/suits/${pedido.id}/notas`, fd)
      toast(r.command_id ? tr("Nota salva. A IA está lendo e segue daqui; a resposta aparece na linha do tempo.") : tr("Nota salva."), 'ok')
      setTexto(''); setArquivo(null); onDone()
    } catch (e) { toast((e as ApiError).message, 'crit') } finally { setIndo(false) }
  }
  async function liberarAprovado() {
    if (texto.trim().length < 5) { toast(tr("Escreva na nota o motivo de mover à mão (ex.: aprovou pessoalmente, já foi para a produção)."), 'warn'); return }
    setIndo(true)
    try {
      await api.post(`/suits/${pedido.id}/etapa-admin`, { etapa, motivo: texto.trim() })
      if (arquivo) { const fd = new FormData(); fd.set('arquivo', arquivo); await api.postForm(`/suits/${pedido.id}/notas`, fd) }
      toast(tr("Pedido movido para {0}.", nomeEtapa_), 'ok')
      setTexto(''); setArquivo(null); onDone()
    } catch (e) { toast((e as ApiError).message, 'crit') } finally { setIndo(false) }
  }
  return <Section title={tr("Nota")}>
    <label className="fld"><span className="sr-only">{tr("Nota")}</span><textarea rows={3} value={texto} onChange={e => setTexto(e.target.value)}
      placeholder={tr("O que aconteceu? Ex.: cliente aprovou o design, mandou as medidas no print, pediu outra cor…")} /></label>
    <div className="suit-nota-op">
      <label className="btn ghost suit-arquivo"><Icon name="plus" size={16} /> {arquivo ? tr("Trocar arquivo") : tr("Anexar arquivo")}
        <input type="file" onChange={e => setArquivo(e.target.files?.[0] || null)} /></label>
      <label className="fld suit-etapa"><span>{tr("Etapa")}</span><select aria-label={tr("Etapa")} value={etapa} onChange={e => setEtapa(e.target.value)}>
        {meta.etapas.filter(e => admin || permitida(e.codigo)).map(e =>
          <option key={e.codigo} value={e.codigo}>{e.codigo === pedido.status ? tr("{0} (atual)", e.nome) : permitida(e.codigo) ? tr("mover para {0}", e.nome) : tr("mover à mão para {0}", e.nome)}</option>)}</select></label>
      {pedido.ia_ligada !== 0 && <label className="check suit-ia"><input type="checkbox" checked={ia} onChange={e => setIa(e.target.checked)} /> {tr("Pedir à IA para seguir daqui")}</label>}
      <button className="btn primary" disabled={indo} onClick={salvar}>{indo ? tr("Salvando…") : liberar ? tr("Mover à mão para {0}", nomeEtapa_) : tr("Salvar nota")}</button>
    </div>
    {liberar && <p className="small suit-liberar" role="note">{tr("Pelo caminho normal o pedido não vai para {0} agora (a ordem das etapas ou uma trava impede). Como administrador, você move à mão quando aconteceu fora do Command Center: escreva o motivo na nota (fica na linha do tempo e na auditoria, com o seu nome).", nomeEtapa_)}</p>}
    {(etapa === 'photos_received' || pedido.status === 'in_production') && <p className="small muted">{tr("Fotos do fornecedor (WhatsApp): anexe cada foto aqui com a etapa Photos received. O Checked (OK da equipe) exige pelo menos uma.")}</p>}
    {previa && <img src={previa} alt={tr("Print anexado")} className="suit-previa" />}
    {arquivo && !ehImagem && <p className="small muted suit-arquivo-nome">{tr("Anexado:")} <b>{arquivo.name}</b> · {tr("vai para os arquivos do pedido")}</p>}
  </Section>
}

function Cliente({ pedido, onDone }: { pedido: PedidoApi; onDone: () => void }) {
  const toast = useToast()
  const [editando, setEditando] = useState(false)
  const [f, setF] = useState<Record<string, string>>({})
  const campos: [string, string, string?][] = [['customer_name', tr("Cliente")], ['driver_name', tr("Piloto")], ['customer_email', tr("E-mail"), 'email'],
    ['customer_phone', tr("Telefone"), 'tel'], ['ship_address', tr("Endereço de entrega")], ['order_date', tr("Data do pedido"), 'date'],
    ['paid_at', tr("Pago em"), 'date'], ['due_on', tr("Prazo"), 'date'], ['tracking', tr("Rastreio")]]
  const [cli, setCli] = useState<Client | null>(null)
  const abrir = () => {
    setF(Object.fromEntries([...campos.map(([k]) => [k, String((pedido as unknown as Record<string, unknown>)[k] ?? '')]), ['language', pedido.language || 'en']]))
    setCli(pedido.client_id ? cartao(pedido.client_id, pedido.cliente_nome, pedido.cliente_piloto) : null)
    setEditando(true)
  }
  async function escolher(c: Client | null) {
    setCli(c)
    if (!c) return
    try {     // vincular puxa do cadastro o que ainda está vazio aqui; o que a equipe escreveu fica
      const d = await puxarCliente(c.id)
      setF(x => ({ ...x, customer_name: x.customer_name || d.customer_name || '', customer_email: x.customer_email || d.customer_email || '',
        customer_phone: x.customer_phone || d.customer_phone || '', driver_name: x.driver_name || d.driver_name || '',
        ship_address: x.ship_address || d.ship_address || '' }))
    } catch (e) { toast((e as ApiError).message, 'crit') }
  }
  async function salvar() {
    try { await api.patch(`/suits/${pedido.id}`, { ...f, client_id: cli ? cli.id : 0 }); toast(tr("Salvo."), 'ok'); setEditando(false); onDone() }
    catch (e) { toast((e as ApiError).message, 'crit') }
  }
  return <Section title={tr("Cliente")} right={!editando && <button className="btn sm ghost" onClick={abrir}><Icon name="pencil" size={14} /> {tr("Editar")}</button>}>
    {editando ? <>
      <Picker label={tr("Vincular ao cliente (puxa os dados do cadastro)")} value={cli} onPick={escolher} />
      <div className="suit-form">{campos.map(([k, rot, tipo]) => <label key={k} className="fld"><span>{rot}</span>
        {k === 'ship_address' ? <textarea rows={2} value={f[k]} onChange={e => setF(x => ({ ...x, [k]: e.target.value }))} />
          : <input type={tipo || 'text'} value={f[k]} onChange={e => setF(x => ({ ...x, [k]: e.target.value }))} />}</label>)}
        <label className="fld"><span>{tr("Idioma")}</span><select value={f.language} onChange={e => setF(x => ({ ...x, language: e.target.value }))}>{IDIOMAS.map(([k, n]) => <option key={k} value={k}>{n}</option>)}</select></label>
      </div>
      <div className="row gap"><button className="btn ghost" onClick={() => setEditando(false)}>{tr("Cancelar")}</button><button className="btn primary" onClick={salvar}>{tr("Salvar")}</button></div>
    </> : <dl className="suit-dl">
      <div><dt>{tr("Card do cliente")}</dt><dd>{pedido.client_id ? <Link to={`/clients/${pedido.client_id}`}>{pedido.cliente_piloto || pedido.cliente_nome || `#${pedido.client_id}`} ↗</Link>
        : <span className="muted">{tr("não vinculado — Editar para vincular")}</span>}</dd></div>
      {campos.map(([k, rot]) => { const v = (pedido as unknown as Record<string, unknown>)[k] as string | null
        return <div key={k}><dt>{rot}</dt><dd>{v ? (k.endsWith('_at') || k.endsWith('_on') || k === 'order_date' ? dia(v) : v) : <span className="muted">—</span>}</dd></div> })}
      <div><dt>{tr("Idioma")}</dt><dd>{IDIOMAS.find(([k]) => k === pedido.language)?.[1] || pedido.language || <span className="muted">—</span>}</dd></div>
      <div><dt>{tr("Fornecedor")}</dt><dd>{pedido.fornecedor || <span className="muted">{tr("o atual")}</span>}</dd></div>
    </dl>}
  </Section>
}

function Medidas({ meta, pedido, onDone }: { meta: Meta; pedido: PedidoApi; onDone: () => void }) {
  const toast = useToast()
  const [editando, setEditando] = useState(false)
  const [unidade, setUnidade] = useState<'cm' | 'in'>('cm')
  const [peso, setPeso] = useState<'kg' | 'lb'>('kg')
  const [v, setV] = useState<Record<string, string>>({})
  const abrir = () => {
    const ini: Record<string, string> = {}
    for (const [k, m] of Object.entries(pedido.measurements)) ini[k] = 't' in m ? m.t : String(m.v)
    const u = Object.values(pedido.measurements).find(m => 'u' in m && (m.u === 'cm' || m.u === 'in')) as { u: 'cm' | 'in' } | undefined
    const pu = Object.values(pedido.measurements).find(m => 'u' in m && (m.u === 'kg' || m.u === 'lb')) as { u: 'kg' | 'lb' } | undefined
    if (u) setUnidade(u.u)
    if (pu) setPeso(pu.u)
    setV(ini); setEditando(true)
  }
  async function salvar() {
    try { await api.patch(`/suits/${pedido.id}`, { medidas: { valores: v, unidade, unidade_peso: peso } }); toast(tr("Medidas salvas."), 'ok'); setEditando(false); onDone() }
    catch (e) { toast((e as ApiError).message, 'crit') }
  }
  const falta = pedido.faltam_medidas.length
  const est = pedido.estado_medidas || {}
  const naoConf = Object.values(est).filter(e => e.estado === 'preenchida').length
  const susp = Object.values(est).filter(e => e.estado === 'suspeita').length
  const [suspeita, setSuspeita] = useState<string | null>(null)
  const [motivo, setMotivo] = useState('')
  async function marcar(chaves: string[], estado: string, mot?: string) {
    try { await api.post(`/suits/${pedido.id}/medidas/estado`, { chaves, estado, motivo: mot || null }); onDone() }
    catch (e) { toast((e as ApiError).message, 'crit') }
  }
  function escolherEstado(chave: string, estado: string) {
    if (estado === 'suspeita') { setMotivo(''); setSuspeita(chave) } else marcar([chave], estado)
  }
  return <Section title={tr("Medidas")} count={meta.medidas.length - 1 - falta}
    right={<>{falta > 0 && <Chip tone="warn">{tr("faltam")} {falta}</Chip>}{susp > 0 && <Chip tone="crit">{tr("suspeitas")} {susp}</Chip>}
      {naoConf > 0 && <Chip tone="warn">{tr("a conferir")} {naoConf}</Chip>}
      {!editando && <button className="btn sm ghost" onClick={abrir}><Icon name="pencil" size={14} /> {tr("Preencher")}</button>}</>}>
    {!editando && naoConf > 0 && <div className="suit-botoes"><button className="btn" onClick={() => marcar(Object.keys(est).filter(k => est[k].estado === 'preenchida'), 'conferida')}>
      {tr("Marcar as {0} preenchidas como conferidas", naoConf)}</button></div>}
    {!editando && <p className="small muted">{tr("Medida suspeita ou não conferida trava a aprovação final. Mudou o valor, volta para preenchida.")}</p>}
    {editando && <div className="row gap wrap" style={{ marginBottom: 10 }}>
      <div className="tabs" role="group" aria-label={tr("Unidade de comprimento")}><button className={unidade === 'cm' ? 'on' : ''} onClick={() => setUnidade('cm')}>{tr("cm")}</button><button className={unidade === 'in' ? 'on' : ''} onClick={() => setUnidade('in')}>{tr("polegadas")}</button></div>
      <div className="tabs" role="group" aria-label={tr("Unidade de peso")}><button className={peso === 'kg' ? 'on' : ''} onClick={() => setPeso('kg')}>{tr("kg")}</button><button className={peso === 'lb' ? 'on' : ''} onClick={() => setPeso('lb')}>{tr("lb")}</button></div>
    </div>}
    <div className="suit-medidas">{meta.medidas.map(m => editando
      ? <label key={m.chave} className="fld"><span>{m.numero} – {m.nome}{m.chave === 'bust' ? tr(" (só mulheres)") : ''}</span>
          <input inputMode={m.tipo === 'texto' ? 'text' : 'decimal'} value={v[m.chave] || ''} placeholder={m.tipo === 'texto' ? tr("42 EUR / 9 US") : m.tipo === 'peso' ? peso : unidade}
            onChange={e => setV(x => ({ ...x, [m.chave]: e.target.value }))} /></label>
      : (m.chave === 'bust' && !pedido.medidas_texto.bust) ? null
      : <div key={m.chave} className={`suit-med${pedido.medidas_texto[m.chave] ? '' : ' falta'}${est[m.chave]?.estado === 'suspeita' ? ' suspeita' : ''}`}>
          <span className="small muted">{m.numero} – {m.nome}</span><b>{pedido.medidas_texto[m.chave] || '—'}</b>
          {est[m.chave] && <label className="suit-med-estado"><span className="sr-only">{tr("Estado de {0}", m.nome)}</span>
            <select value={est[m.chave].estado} onChange={e => escolherEstado(m.chave, e.target.value)}>
              {Object.entries(ESTADO_MED).map(([k, n]) => <option key={k} value={k}>{n}</option>)}</select></label>}
          {est[m.chave]?.motivo && <span className="small" style={{ color: 'var(--crit)' }}>{est[m.chave].motivo}</span>}
        </div>)}</div>
    {suspeita && <Scrim onMouseDown={() => setSuspeita(null)}><div className="modal" style={{ maxWidth: 440 }} onMouseDown={e => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="suspeita-t">
      <h3 id="suspeita-t">{tr("Por que a medida parece errada?")}</h3>
      <label className="fld"><span>{tr("Motivo")}</span><input value={motivo} onChange={e => setMotivo(e.target.value)} maxLength={300} placeholder={tr("ex.: cintura maior que o peito")} /></label>
      <div className="row gap"><button className="btn ghost" onClick={() => setSuspeita(null)}>{tr("Cancelar")}</button>
        <button className="btn primary" disabled={!motivo.trim()} onClick={() => { marcar([suspeita], 'suspeita', motivo.trim()); setSuspeita(null) }}>{tr("Marcar suspeita")}</button></div>
    </div></Scrim>}
    {editando && <div className="row gap" style={{ marginTop: 10 }}><button className="btn ghost" onClick={() => setEditando(false)}>{tr("Cancelar")}</button><button className="btn primary" onClick={salvar}>{tr("Salvar medidas")}</button></div>}
  </Section>
}

function Design({ meta, pedido, onDone }: { meta: Meta; pedido: PedidoApi; onDone: () => void }) {
  const toast = useToast()
  const [editando, setEditando] = useState(false)
  const [v, setV] = useState<Record<string, string>>({})
  async function salvar() {
    try { await api.patch(`/suits/${pedido.id}`, { design: v }); toast(tr("Design salvo."), 'ok'); setEditando(false); onDone() }
    catch (e) { toast((e as ApiError).message, 'crit') }
  }
  return <Section title={tr("Design")} right={!editando && <button className="btn sm ghost" onClick={() => { setV({ ...pedido.design }); setEditando(true) }}><Icon name="pencil" size={14} /> {tr("Editar")}</button>}>
    <p className="small muted">{tr("É só isto que vai para o designer: nunca pagamento nem contato do cliente.")}</p>
    {editando ? <><div className="suit-form">{meta.design.map(d => <label key={d.chave} className="fld"><span>{d.nome}</span>
        <input value={v[d.chave] || ''} onChange={e => setV(x => ({ ...x, [d.chave]: e.target.value }))} /></label>)}</div>
      <div className="row gap"><button className="btn ghost" onClick={() => setEditando(false)}>{tr("Cancelar")}</button><button className="btn primary" onClick={salvar}>{tr("Salvar")}</button></div></>
      : <dl className="suit-dl">{meta.design.map(d => <div key={d.chave}><dt>{d.nome}</dt><dd>{pedido.design[d.chave] || <span className="muted">—</span>}</dd></div>)}</dl>}
  </Section>
}

const gmailLink = (t: string) => `https://mail.google.com/mail/?authuser=urace@urace.us#all/${t}`
const tamanho = (b: number) => b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1e3))} KB`

function PonteDoPedido({ pedido, onDone }: { pedido: PedidoApi; onDone: () => void }) {
  const toast = useToast()
  const designers = useGet<Designer[]>('/suits/designers')
  const fornecedores = useGet<Fornecedor[]>('/suits/fornecedores')
  const [puxando, setPuxando] = useState(false)
  const tentou = useRef(false)
  // #481 (dono, 29/10: "eu preciso que já venha a conversa com o cliente ... ele puxa de lá"): procura no Gmail as
  // conversas que faltam — sozinho na primeira vez que o pedido abre sem a conversa do cliente, e no botão
  async function puxar(silencioso = false) {
    setPuxando(true)
    try {
      const r = await api.post<{ puxadas: { ligadas: Record<string, string>; faltam: string[]; aviso?: string } }>(`/suits/${pedido.id}/ponte/puxar`)
      const n = Object.keys(r.puxadas.ligadas).length
      if (r.puxadas.aviso) { if (!silencioso) toast(r.puxadas.aviso, 'warn') }
      else if (n) { toast(tr("Conversas ligadas pelo Gmail: {0}.", Object.keys(r.puxadas.ligadas).join(', ')), 'ok'); onDone() }
      else if (!silencioso) toast(r.puxadas.faltam.length ? tr("Não achei no Gmail: {0}.", r.puxadas.faltam.join(', ')) : tr("As conversas já estão ligadas."), 'warn')
    } catch (e) { if (!silencioso) toast((e as ApiError).message, 'crit') } finally { setPuxando(false) }
  }
  useEffect(() => {
    if (tentou.current || pedido.gmail_thread_cliente || !pedido.customer_email || pedido.discarded_at) return
    tentou.current = true
    void puxar(true)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pedido.id])
  async function escolher(campo: 'designer_id' | 'supplier_id', valor: string) {
    try { await api.patch(`/suits/${pedido.id}`, { [campo]: valor ? Number(valor) : 0 }); toast(tr("Salvo."), 'ok'); onDone() }
    catch (e) { toast((e as ApiError).message, 'crit') }
  }
  const fAtual = (fornecedores.data || []).find(f => f.id === pedido.supplier_id) || (fornecedores.data || []).find(f => f.is_current)
  const anexos = useGet<Anexo[]>(`/suits/${pedido.id}/anexos?v=${pedido.notas.length}`)
  const [ed, setEd] = useState<Record<string, string> | null>(null)
  const [indo, setIndo] = useState(false)
  const sp = pedido.saude_ponte || { ultima_tentativa: null, ultimo_sucesso: null, ultimo_erro: null, ultimo_erro_em: null, modo: null }
  const papeis: [string, string][] = [['gmail_thread_cliente', tr("Conversa com o cliente")], ['gmail_thread_designer', tr("Conversa com o designer")],
    ['gmail_thread_fornecedor', tr("Conversa com o fornecedor")]]
  async function salvar() {
    try { await api.patch(`/suits/${pedido.id}`, ed); toast(tr("Conversas ligadas ao pedido."), 'ok'); setEd(null); onDone() }
    catch (e) { toast((e as ApiError).message, 'crit') }
  }
  async function arte(nome: string, final: boolean) {
    try { await api.post(`/suits/${pedido.id}/arte-final`, { nome, final }); toast(final ? tr("Marcado como arte final.") : tr("Saiu da arte final."), 'ok'); onDone() }
    catch (e) { toast((e as ApiError).message, 'crit') }
  }
  async function simular() {
    setIndo(true)
    try { await api.post(`/suits/${pedido.id}/ponte/simular`); toast(tr("Simulando: a IA faz o próximo passo e o e-mail que ela mandaria aparece na linha do tempo. Nada sai."), 'ok'); setTimeout(onDone, 4000) }
    catch (e) { toast((e as ApiError).message, 'crit') } finally { setIndo(false) }
  }
  return <Section title={tr("Ponte de e-mail")} right={!ed && <button className="btn sm ghost" onClick={() => setEd(Object.fromEntries(papeis.map(([k]) => [k, String((pedido as unknown as Record<string, unknown>)[k] ?? '')])))}><Icon name="pencil" size={14} /> {tr("Ligar conversas")}</button>}>
    <p className="small muted">{tr("A IA lê e responde nestas conversas do Gmail: com o cliente, com o designer (sem os dados do cliente) e com o fornecedor.")}{pedido.site_order ? tr(" Pedido do site #{0}.", pedido.site_order) : ''}</p>
    <div className="suit-form">
      <label className="fld"><span>{tr("E-mail do cliente")}</span><input aria-label={tr("E-mail do cliente")} value={pedido.customer_email || ''} readOnly placeholder={tr("preencha em Cliente › Editar")} /></label>
      <label className="fld"><span>{tr("Designer")}</span><select aria-label={tr("Designer")} value={pedido.designer_id || ''} onChange={e => escolher('designer_id', e.target.value)}>
        <option value="">{tr("o atual")}{pedido.designer && !pedido.designer_id && pedido.designer.nome ? ` (${pedido.designer.nome})` : ''}</option>
        {(designers.data || []).map(d => <option key={d.id} value={d.id}>{d.name}{d.email ? ` · ${d.email}` : ''}</option>)}</select>
        {pedido.designer?.email && <span className="small muted">{tr("vai para {0}", pedido.designer.email)}</span>}</label>
      <label className="fld"><span>{tr("Fornecedor")}</span><select aria-label={tr("Fornecedor")} value={pedido.supplier_id || ''} onChange={e => escolher('supplier_id', e.target.value)}>
        <option value="">{tr("o atual")}{!pedido.supplier_id && fAtual ? ` (${fAtual.name})` : ''}</option>
        {(fornecedores.data || []).map(f => <option key={f.id} value={f.id}>{f.name}{f.email ? ` · ${f.email}` : ''}</option>)}</select>
        {fAtual?.email && <span className="small muted">{tr("vai para {0}", fAtual.email)}</span>}</label>
    </div>
    <div className="row gap wrap" style={{ margin: '8px 0' }}><button className="btn" disabled={puxando} onClick={() => puxar()}>{puxando ? <span className="spin" /> : <Icon name="mail" size={14} />} {tr("Puxar conversas do Gmail")}</button></div>
    {ed ? <><div className="suit-form">{papeis.map(([k, rot]) => <label key={k} className="fld"><span>{rot} {tr("(link ou id do Gmail)")}</span>
        <input value={ed[k]} onChange={e => setEd(x => ({ ...x!, [k]: e.target.value }))} placeholder={tr("cole o link da conversa")} /></label>)}</div>
      <div className="row gap"><button className="btn ghost" onClick={() => setEd(null)}>{tr("Cancelar")}</button><button className="btn primary" onClick={salvar}>{tr("Salvar")}</button></div></>
      : <dl className="suit-dl">{papeis.map(([k, rot]) => { const v = (pedido as unknown as Record<string, string | null>)[k]
        return <div key={k}><dt>{rot}</dt><dd>{v ? <a href={gmailLink(v)} target="_blank" rel="noreferrer">{tr("abrir no Gmail ↗")}</a> : <span className="muted">—</span>}</dd></div> })}</dl>}
    <h3 className="h3" style={{ marginTop: 12 }}>{tr("Arquivos do pedido")}</h3>
    {anexos.data && anexos.data.length ? <ul className="suit-lista">{anexos.data.map(a => { const final = pedido.arte_final.includes(a.nome)
      return <li key={a.nome} className="suit-arq">
        <a className="suit-linha grow" href={`/ops/api/suits/${pedido.id}/anexos/${encodeURIComponent(a.nome)}`} target="_blank" rel="noreferrer">
          <span className="grow truncate">{a.nome}</span>{final && <Chip tone="ok">{tr("arte final")}</Chip>}<span className="small muted">{tamanho(a.bytes)}</span></a>
        <button className={`btn${final ? ' ghost' : ''}`} aria-pressed={final} onClick={() => arte(a.nome, !final)}>{final ? tr("Tirar da arte final") : tr("Marcar arte final")}</button></li> })}</ul>
      : <p className="small muted">{tr("Nada ainda. O que chegar por e-mail (medidas, inspiração, logos, arte) fica aqui.")}</p>}
    <div className="row gap wrap" style={{ marginTop: 10 }}><button className="btn" disabled={indo} onClick={simular}>{indo ? tr("Simulando…") : tr("Simular o próximo passo")}</button></div>
    <h3 className="h3" style={{ marginTop: 12 }}>{tr("Saúde da ponte neste pedido")}</h3>
    <dl className="suit-dl">
      <div><dt>{tr("Última tentativa")}</dt><dd>{sp.ultima_tentativa ? horaFL(sp.ultima_tentativa) : <span className="muted">—</span>}
        {sp.modo ? ` · ${sp.modo === 'real' ? tr("envio real") : tr("simulação")}` : ''}</dd></div>
      <div><dt>{tr("Último sucesso")}</dt><dd>{sp.ultimo_sucesso ? horaFL(sp.ultimo_sucesso) : <span className="muted">—</span>}</dd></div>
      <div><dt>{tr("Último erro")}</dt><dd>{sp.ultimo_erro ? <span style={{ color: 'var(--crit)' }}>{sp.ultimo_erro}{sp.ultimo_erro_em ? ` (${horaFL(sp.ultimo_erro_em)})` : ''}</span> : <span className="muted">—</span>}</dd></div>
      <div><dt>{tr("Próxima ação esperada")}</dt><dd>{pedido.proxima_acao}</dd></div>
    </dl>
  </Section>
}

function Ponte() {
  const { can } = useAuth()
  const toast = useToast()
  const p = useGet<Ponte>('/suits/ponte')
  const [ed, setEd] = useState<PonteCfg | null>(null)
  const [indo, setIndo] = useState('')
  if (p.error) return <div className="card"><ErrorState error={p.error} retry={p.reload} /></div>
  if (!p.data) return <div className="card"><Loading /></div>
  const cfg = ed || p.data.config
  const gerente = can('MANAGER')
  const set = (k: keyof PonteCfg, v: string) => setEd({ ...cfg, [k]: v })
  async function salvar() {
    setIndo('salvar')
    try { await api.put('/suits/ponte', { ...cfg, ponte_ligada: cfg.ponte_ligada === '1', envio_automatico: cfg.envio_automatico === '1' }); setEd(null); p.reload(); toast(tr("Ponte salva."), 'ok') }
    catch (e) { toast((e as ApiError).message, 'crit') } finally { setIndo('') }
  }
  async function manualGmail() {
    setIndo('gmail')
    try { const r = await api.post<{ nome: string }>('/suits/ponte/manual/gmail'); p.reload(); toast(tr("Manual carregado do Gmail: {0}.", r.nome), 'ok') }
    catch (e) { toast((e as ApiError).message, 'crit') } finally { setIndo('') }
  }
  async function subirManual(f: File | undefined) {
    if (!f) return
    const fd = new FormData(); fd.set('arquivo', f)
    try { await api.postForm('/suits/ponte/manual', fd); p.reload(); toast(tr("Manual carregado."), 'ok') } catch (e) { toast((e as ApiError).message, 'crit') }
  }
  async function rodar() {
    setIndo('rodar')
    try { const r = await api.post<{ iniciada: boolean; nota: string | null }>('/suits/ponte/rodar'); toast(r.iniciada ? tr("Rodando: em instantes os pedidos mostram o que a IA fez.") : (r.nota || ''), r.iniciada ? 'ok' : 'warn') }
    catch (e) { toast((e as ApiError).message, 'crit') } finally { setIndo('') }
  }
  let ultima: Record<string, unknown> | null = null
  try { ultima = p.data.ultima_rodada ? JSON.parse(p.data.ultima_rodada.detail) : null } catch { ultima = null }
  const auto = cfg.envio_automatico === '1'
  return <>
    <Section title={tr("Ponte de e-mail")} right={gerente && <button className="btn sm" disabled={indo === 'rodar'} onClick={rodar}>{indo === 'rodar' ? tr("Rodando…") : tr("Rodar agora")}</button>}>
      <p className="small muted">{tr("Venda de macacão no site → a IA agradece, manda o manual de medidas e pede o design. O cliente responde → a IA grava as medidas e o design e passa ao designer só o design. O designer pergunta ou entrega a arte → a IA leva ao cliente sem os dados do designer. Roda a cada 15 minutos.")}</p>
      {p.data.motor !== 'sdk' && <p className="small" style={{ color: 'var(--warn)' }}>{tr("A ponte precisa da IA no motor novo: falta a chave da Anthropic no serviço.")}</p>}
      {!auto && <p className="small" style={{ color: 'var(--warn)' }}><b>{tr("Em simulação:")}</b> {tr("nada sai. O e-mail que a IA mandaria aparece na linha do tempo do pedido, para conferir.")}</p>}
      {auto && <p className="small" style={{ color: 'var(--ok)' }}><b>{tr("Envio automático ligado:")}</b> {tr("a IA manda sem esperar aprovação.")}</p>}
      <div className="suit-form">
        <label className="check suit-ia"><input type="checkbox" disabled={!gerente} checked={cfg.ponte_ligada === '1'} onChange={e => set('ponte_ligada', e.target.checked ? '1' : '0')} /> {tr("Ponte ligada")}</label>
        <label className="check suit-ia"><input type="checkbox" disabled={!gerente} checked={auto} onChange={e => set('envio_automatico', e.target.checked ? '1' : '0')} /> {tr("Envio automático (sem aprovação)")}</label>
      </div>
      <label className="fld"><span>{tr("Boas-vindas (referência; a IA adapta ao idioma e ao pedido)")}</span><textarea disabled={!gerente} rows={9} value={cfg.boas_vindas} onChange={e => set('boas_vindas', e.target.value)} /></label>
      <label className="fld"><span>{tr("Política dos macacões (a IA segue e explica ao cliente; conflito vem para a equipe)")}</span><textarea disabled={!gerente} rows={6} value={cfg.politica} onChange={e => set('politica', e.target.value)} /></label>
      <label className="fld"><span>{tr("Assinatura")}</span><textarea disabled={!gerente} rows={5} value={cfg.assinatura} onChange={e => set('assinatura', e.target.value)} /></label>
      <p className="small">{tr("Designers e fornecedores, com o e-mail fixo e o contexto para a IA, ficam na aba")} <Link to="/suits/contatos">{tr("Contatos")}</Link>.</p>
      {gerente && ed && <div className="row gap"><button className="btn ghost" onClick={() => setEd(null)}>{tr("Cancelar")}</button><button className="btn primary" disabled={indo === 'salvar'} onClick={salvar}>{tr("Salvar")}</button></div>}
    </Section>
    <Section title={tr("Manual de medidas (PDF)")}>
      <p className="small">{p.data.manual ? <>{tr("Carregado.")} <a href="/ops/api/suits/ponte/manual" target="_blank" rel="noreferrer">{tr("Ver o PDF ↗")}</a></> : <span style={{ color: 'var(--warn)' }}>{tr("Ainda não carregado: as boas-vindas não saem sem ele.")}</span>}</p>
      {gerente && <div className="row gap wrap"><button className="btn" disabled={indo === 'gmail'} onClick={manualGmail}>{indo === 'gmail' ? tr("Buscando…") : tr("Buscar no Gmail")}</button>
        <label className="btn ghost suit-arquivo"><Icon name="plus" size={16} /> {tr("Subir o PDF")}<input type="file" accept="application/pdf" onChange={e => subirManual(e.target.files?.[0])} /></label></div>}
    </Section>
    {ultima && <Section title={tr("Última rodada")}><p className="small muted">{horaFL(p.data.ultima_rodada!.at)}</p><pre className="suit-pre">{JSON.stringify(ultima, null, 1)}</pre></Section>}
  </>
}

function EmailFornecedor({ pedido, onDone }: { pedido: PedidoApi; onDone: () => void }) {
  const toast = useToast()
  const e = useGet<Email>(`/suits/${pedido.id}/email-fornecedor?v=${pedido.updated_at || ''}`)
  const [indo, setIndo] = useState(false)
  async function rascunho() {
    setIndo(true)
    try { const r = await api.post<{ para: string; anexos: string[] }>(`/suits/${pedido.id}/email-fornecedor/rascunho`); toast(tr("Rascunho criado no Gmail para {0}, com a arte final aprovada anexada ({1}). Confira e envie.", r.para, r.anexos.join(', ')), 'ok'); onDone() }
    catch (x) { toast((x as ApiError).message, 'crit') } finally { setIndo(false) }
  }
  return <Section title={tr("Pedido ao fornecedor")}>
    {e.error ? <ErrorState error={e.error} retry={e.reload} /> : !e.data ? <Loading rows={2} /> : <>
      {e.data.faltam.length > 0 && <p className="small" style={{ color: 'var(--warn)' }}>{tr("Falta")} {e.data.faltam.join(' e ')} {tr("para mandar ao fornecedor.")}</p>}
      <div className="small muted">{tr("Para:")} {e.data.para || '—'} {tr("· Assunto:")} <b>{e.data.assunto}</b>{e.data.anexos?.length ? <> {tr("· Anexos:")} {e.data.anexos.join(', ')}</> : null}</div>
      <p className="small muted">{tr("Sai do pacote aprovado (a arte final e as medidas da aprovação), sem o endereço: ele vai depois do OK nas fotos.")}</p>
      <pre className="suit-pre">{e.data.corpo}</pre>
      <div className="row gap wrap"><button className="btn primary" disabled={indo || e.data.faltam.length > 0} onClick={rascunho}>{indo ? tr("Criando…") : tr("Criar rascunho no Gmail")}</button>
        <Link className="btn ghost" to="/suits/modelo">{tr("Editar o modelo")}</Link></div>
    </>}
  </Section>
}

/* ============================================================ #382: aprovação final, designer, endereço, saúde */
function AprovacaoFinal({ pedido, onDone }: { pedido: PedidoApi; onDone: () => void }) {
  const toast = useToast()
  const [aberto, setAberto] = useState(false)
  const [f, setF] = useState({ trecho: '', message_id: '', data: '' })
  const [indo, setIndo] = useState(false)
  const a = pedido.aprovacao
  if (!a) return null
  async function registrar() {
    setIndo(true)
    try { await api.post(`/suits/${pedido.id}/aprovacao`, { trecho: f.trecho, message_id: f.message_id || null, data: f.data || null }); toast(tr("Aprovação final registrada."), 'ok'); setAberto(false); onDone() }
    catch (e) { toast((e as ApiError).message, 'crit') } finally { setIndo(false) }
  }
  const tom = a.estado === 'valida' ? 'ok' : a.estado === 'desatualizada' ? 'crit' : 'warn'
  const rot = a.estado === 'valida' ? tr("válida") : a.estado === 'desatualizada' ? tr("desatualizada") : tr("ainda não")
  return <Section title={tr("Aprovação final")} right={<Chip tone={tom}>{rot}</Chip>}>
    <p className="small muted">{tr("A produção só sai com a aprovação final escrita do cliente (vale por e-mail), amarrada à arte final e às medidas de agora: mudou qualquer uma, ela cai. Versão atual:")} <b>{a.versao}</b></p>
    {a.bloqueios.length > 0 && <ul className="small suit-bloqueios">{a.bloqueios.map(b => <li key={b}>{b}</li>)}</ul>}
    {a.pedido_final && <p className="small">{tr("E-mail de aprovação final da versão {0} {1} em {2}.", a.pedido_final.versao, a.pedido_final.simulado ? tr("(simulação, não saiu)") : tr("enviado"), horaFL(a.pedido_final.em))}{!a.pedido_final.atual && <span style={{ color: 'var(--warn)' }}> {tr("A versão mudou depois.")}</span>}</p>}
    {a.aprovacao && <dl className="suit-dl">
      <div><dt>{tr("Trecho")}</dt><dd>«{a.aprovacao.excerpt}»</dd></div>
      <div><dt>{tr("Data do e-mail")}</dt><dd>{a.aprovacao.approved_at}</dd></div>
      <div><dt>{tr("E-mail")}</dt><dd>{a.aprovacao.message_id || <span className="muted">—</span>} · {a.aprovacao.source === 'ia' ? tr("registrada pela IA") : tr("registrada pela equipe")}</dd></div>
      <div><dt>{tr("Arte aprovada")}</dt><dd>{a.aprovacao.files.join(', ')}{a.aprovacao.stale_reason ? <span style={{ color: 'var(--crit)' }}> · {tr("caiu:")} {a.aprovacao.stale_reason}</span> : null}</dd></div>
    </dl>}
    <div className="suit-botoes"><button className="btn" disabled={a.bloqueios.length > 0} onClick={() => setAberto(true)}>{tr("Registrar aprovação à mão")}</button></div>
    {aberto && <Scrim onMouseDown={() => setAberto(false)}><div className="modal" style={{ maxWidth: 520 }} onMouseDown={e => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="aprov-t">
      <h3 id="aprov-t">{tr("Registrar a aprovação final da versão {0}", a.versao)}</h3>
      <p className="small muted">{tr("Copie do e-mail do cliente o trecho em que ele aprova esta versão final. \"Gostei\" de uma versão anterior não vale.")}</p>
      <label className="fld"><span>{tr("Trecho com o \"aprovo\"")}</span><textarea rows={3} value={f.trecho} onChange={e => setF(x => ({ ...x, trecho: e.target.value }))} /></label>
      <div className="suit-form">
        <label className="fld"><span>{tr("Id ou link do e-mail (opcional)")}</span><input value={f.message_id} onChange={e => setF(x => ({ ...x, message_id: e.target.value }))} /></label>
        <label className="fld"><span>{tr("Data do e-mail")}</span><input type="date" value={f.data} onChange={e => setF(x => ({ ...x, data: e.target.value }))} /></label>
      </div>
      <div className="row gap"><button className="btn ghost" onClick={() => setAberto(false)}>{tr("Cancelar")}</button>
        <button className="btn primary" disabled={indo || f.trecho.trim().length < 3} onClick={registrar}>{indo ? tr("Registrando…") : tr("Registrar")}</button></div>
    </div></Scrim>}
  </Section>
}

function Preparados({ pedido, onDone }: { pedido: PedidoApi; onDone: () => void }) {
  const { can } = useAuth()
  const toast = useToast()
  const [indo, setIndo] = useState(0)
  const lista = (pedido.preparados || []).filter(x => x.status === 'preparado')
  if (!lista.length) return null
  async function agir(id: number, acao: 'enviar' | 'descartar') {
    setIndo(id)
    try { await api.post(`/suits/${pedido.id}/preparados/${id}/${acao}`); toast(acao === 'enviar' ? tr("Enviado ao designer.") : tr("Descartado."), 'ok'); onDone() }
    catch (e) { toast((e as ApiError).message, 'crit') } finally { setIndo(0) }
  }
  return <Section title={tr("Para o designer")} count={lista.length}>
    <p className="small muted">{tr("A IA preparou; nada saiu ainda. Confira o texto e os anexos (já limpos, sem dado do cliente) e envie.")}</p>
    {lista.map(x => <div key={x.id} className="suit-prep">
      <h3 className="h3">{x.subject}</h3>
      <pre className="suit-pre">{x.body}</pre>
      {x.attachments.length > 0 && <p className="small muted">{tr("Anexos:")} {x.attachments.join(', ')}</p>}
      {can('OPERATOR') && <div className="suit-botoes"><button className="btn primary" disabled={indo === x.id} onClick={() => agir(x.id, 'enviar')}>{indo === x.id ? tr("Enviando…") : tr("Enviar ao designer")}</button>
        <button className="btn ghost" disabled={indo === x.id} onClick={() => agir(x.id, 'descartar')}>{tr("Descartar")}</button></div>}
    </div>)}
  </Section>
}

function EnderecoFornecedor({ pedido, onDone }: { pedido: PedidoApi; onDone: () => void }) {
  const toast = useToast()
  const mostrar = ['checked', 'address_sent', 'in_transit'].includes(pedido.status)
  const e = useGet<Endereco>(mostrar ? `/suits/${pedido.id}/endereco-fornecedor?v=${pedido.updated_at || ''}` : null)
  const [indo, setIndo] = useState(false)
  if (!mostrar) return null
  async function rascunho() {
    setIndo(true)
    try { const r = await api.post<{ para: string }>(`/suits/${pedido.id}/endereco-fornecedor/rascunho`); toast(tr("Rascunho com o endereço criado no Gmail para {0}.", r.para), 'ok'); onDone() }
    catch (x) { toast((x as ApiError).message, 'crit') } finally { setIndo(false) }
  }
  async function copiar() {
    try { await navigator.clipboard.writeText(e.data?.whatsapp || ''); toast(tr("Mensagem copiada para o WhatsApp."), 'ok') } catch { toast(tr("Não deu para copiar."), 'warn') }
  }
  return <Section title={tr("Endereço ao fornecedor")}>
    <p className="small muted">{tr("Só depois do OK nas fotos. O fornecedor manda direto ao cliente; o endereço nunca vai ao designer.")}</p>
    {e.error ? <ErrorState error={e.error} retry={e.reload} /> : !e.data ? <Loading rows={2} /> : <>
      {e.data.faltam.length > 0 && <p className="small" style={{ color: 'var(--warn)' }}>{tr("Falta")} {e.data.faltam.join(' e ')}.</p>}
      <pre className="suit-pre">{e.data.corpo}</pre>
      <div className="suit-botoes"><button className="btn primary" disabled={indo || e.data.faltam.length > 0} onClick={rascunho}>{indo ? tr("Criando…") : tr("Criar rascunho no Gmail")}</button>
        <button className="btn" onClick={copiar}>{tr("Copiar para o WhatsApp")}</button></div>
    </>}
  </Section>
}

/** #382 (F): no topo da aba, a última rodada da ponte. */
function SaudeTopo() {
  const s = useGet<SaudePonte>('/suits/ponte/saude', 60000)
  if (!s.data) return null
  const u = s.data.ultima_rodada
  return <p className="small suit-saude" role="status">
    <b>{tr("Ponte:")}</b> {!s.data.ligada ? tr("desligada") : u ? tr("última rodada {0} · {1} evento(s) · {2} erro(s)", horaFL(u.at), u.eventos, u.erros) : tr("ainda não rodou")}
    {' · '}{s.data.simulacao ? <span style={{ color: 'var(--warn)' }}>{tr("em simulação")}</span> : <span style={{ color: 'var(--ok)' }}>{tr("envio real")}</span>}
    {s.data.preparados > 0 && <> · {tr("{0} e-mail(s) ao designer esperando envio", s.data.preparados)}</>}
    {s.data.com_erro > 0 && <> · <span style={{ color: 'var(--crit)' }}>{tr("{0} pedido(s) com erro na ponte", s.data.com_erro)}</span></>}
    {!s.data.manual && <> · <span style={{ color: 'var(--warn)' }}>{tr("manual de medidas não carregado")}</span></>}
  </p>
}

const FILTROS: [string, string, string[]][] = [['tudo', tr("Tudo"), []], ['nota', tr("Notas"), ['nota']], ['email', tr("E-mails"), ['email']],
  ['whatsapp', 'WhatsApp', ['whatsapp']], ['etapa', tr("Etapas"), ['etapa']], ['ia', 'IA', ['ia']]]
const diaFL = (iso: string) => { const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z'); return isNaN(d.getTime()) ? iso.slice(0, 10)
  : d.toLocaleDateString(LOCALE(), { timeZone: 'America/New_York', weekday: 'short', day: '2-digit', month: '2-digit', year: '2-digit' }) }

function Linha_do_tempo({ meta, notas, pid }: { meta: Meta; notas: Nota[]; pid: number }) {
  const [filtro, setFiltro] = useState('tudo')
  const kinds = FILTROS.find(f => f[0] === filtro)?.[2] || []
  const lista = [...notas].reverse().filter(n => !kinds.length || kinds.includes(n.kind))
  return <Section title={tr("Linha do tempo")} count={notas.length}>
    <div className="suit-filtros" role="group" aria-label={tr("Filtrar a linha do tempo")}>{FILTROS.map(([k, rot, ks]) => {
      const n = ks.length ? notas.filter(x => ks.includes(x.kind)).length : notas.length
      return <button key={k} type="button" className={`btn sm${filtro === k ? ' primary' : ' ghost'}`} aria-pressed={filtro === k} disabled={!n && k !== 'tudo'} onClick={() => setFiltro(k)}>{rot} <span className="muted">{n}</span></button>
    })}</div>
    {!lista.length ? <Empty title={tr("Nada ainda")} /> : <ol className="suit-tempo">{lista.map((n, i) => {
      const d = diaFL(n.created_at); const novoDia = i === 0 || diaFL(lista[i - 1].created_at) !== d
      return <li key={n.id} className={`k-${n.kind}`}>
      {novoDia && <div className="suit-dia">{d}</div>}
      <div className="small muted">{horaFL(n.created_at)} · {n.autor || (n.kind === 'ia' ? tr("IA") : tr("sistema"))} · {KIND[n.kind] || n.kind}{n.status ? ` · ${nomeEtapa(meta, n.status)}` : ''}</div>
      {n.text && <div className="suit-texto">{n.text}</div>}
      {n.tem_imagem ? <a href={`/ops/api/suits/notas/${n.id}/imagem`} target="_blank" rel="noreferrer"><img className="suit-img" loading="lazy" src={`/ops/api/suits/notas/${n.id}/imagem`} alt={tr("Print da nota")} /></a> : null}
      {n.arquivo ? <a className="suit-anexo" href={`/ops/api/suits/${pid}/anexos/${encodeURIComponent(n.arquivo)}`} download><Icon name="doc" size={14} /> {n.arquivo}</a> : null}
      {n.ia && <div className="suit-ia-res">{n.ia.status === 'DONE' ? <Md text={n.ia.output || ''} /> : n.ia.status === 'FAILED'
        ? <span style={{ color: 'var(--crit)' }}>{tr("A IA não conseguiu:")} {n.ia.error}</span> : <span className="muted">{tr("A IA está trabalhando nesta nota…")}</span>}
        {n.command_id && <Link className="small" to={`/ai/${n.command_id}`}>{tr("abrir no AI Command")}</Link>}</div>}
    </li>})}</ol>}
  </Section>
}

/* ============================================================ leads */
function Leads() {
  const toast = useToast()
  const nav = useNavigate()
  const [estado, setEstado] = useState('aberto')
  const [busca, setBusca] = useState('')
  const { itens, total, erro, carregando, mais, temMais, recarregar } = usePaginado<Lead>(`/suits/leads${qs({ estado, q: busca.trim() || undefined })}`, 100)
  const [novo, setNovo] = useState<Record<string, string> | null>(null)
  const [cli, setCli] = useState<Client | null>(null)
  function escolher(c: Client | null) {
    setCli(c)
    if (c) setNovo(x => ({ ...x, name: c.pilot_name && c.pilot_name !== c.name ? `${c.pilot_name} (resp. ${c.name})` : c.name,
      email: c.email || x?.email || '', phone: c.phone || x?.phone || '' }))
  }
  async function criar() {
    try { await api.post('/suits/leads', { ...novo, client_id: cli?.id ?? null }); setNovo(null); setCli(null); recarregar(); toast(tr("Lead guardado."), 'ok') }
    catch (e) { toast((e as ApiError).message, 'crit') }
  }
  async function virar(l: Lead) {
    try { const p = await api.post<{ id: number }>(`/suits/leads/${l.id}/pedido`); nav(`/suits/${p.id}`) } catch (e) { toast((e as ApiError).message, 'crit') }
  }
  async function perdido(l: Lead) {
    try { await api.patch(`/suits/leads/${l.id}`, { status: 'perdido' }); recarregar() } catch (e) { toast((e as ApiError).message, 'crit') }
  }
  return <Section title={tr("Leads de macacão")} count={total} right={<button className="btn sm" onClick={() => setNovo({})}><Icon name="plus" size={14} /> {tr("Novo lead")}</button>}>
    <p className="small muted">{tr("Quem já demonstrou interesse: guardado para vender de novo.")}</p>
    <div className="row gap wrap"><div className="tabs">{[['aberto', tr("Abertos")], ['convertido', tr("Viraram pedido")], ['perdido', tr("Perdidos")]].map(([k, n]) =>
      <button key={k} className={estado === k ? 'on' : ''} onClick={() => setEstado(k)}>{n}</button>)}</div>
      <label className="fld grow" style={{ margin: 0 }}><span className="sr-only">{tr("Buscar")}</span><input value={busca} onChange={e => setBusca(e.target.value)} placeholder={tr("Buscar")} /></label></div>
    {novo && <div className="card-in"><Picker label={tr("Vincular ao cliente (puxa os dados do cadastro)")} value={cli} onPick={escolher} /></div>}
    {novo && <div className="suit-form card-in">
      <label className="fld"><span>{tr("Nome")}</span><input value={novo.name || ''} onChange={e => setNovo(x => ({ ...x, name: e.target.value }))} autoFocus /></label>
      <label className="fld"><span>{tr("E-mail")}</span><input value={novo.email || ''} onChange={e => setNovo(x => ({ ...x, email: e.target.value }))} /></label>
      <label className="fld"><span>{tr("Telefone")}</span><input value={novo.phone || ''} onChange={e => setNovo(x => ({ ...x, phone: e.target.value }))} /></label>
      <label className="fld"><span>{tr("Nota")}</span><input value={novo.notes || ''} onChange={e => setNovo(x => ({ ...x, notes: e.target.value }))} /></label>
      <div className="row gap"><button className="btn ghost" onClick={() => setNovo(null)}>{tr("Cancelar")}</button><button className="btn primary" onClick={criar}>{tr("Guardar")}</button></div>
    </div>}
    {erro ? <ErrorState error={erro} retry={recarregar} /> : carregando && !itens.length ? <Loading /> : !itens.length ? <Empty title={tr("Nenhum lead aqui")}>{tr("Quem perguntar de macacão e ainda não fechar entra nesta lista. Use “Novo lead” para registrar.")}</Empty>
      : <div className="cd-grade">{itens.map(l => <Cartao key={l.id} id={`lead-${l.id}`} estado={l.status === 'aberto' ? tr("aberto") : l.status === 'convertido' ? tr("virou pedido") : l.status === 'perdido' ? tr("perdido") : l.status}
          tom={l.status === 'aberto' ? 'warn' : l.status === 'convertido' ? 'ok' : 'neutral'} avatar={l.name} avatarTom="azul" nome={l.name}
          sub={[[l.email, l.phone].filter(Boolean).join(' · ') || '—']}
          acoes={l.status === 'aberto' || l.client_id || l.order_id ? <>
            {l.status === 'aberto' && <button className="btn primary" onClick={() => virar(l)}>{tr("Virar pedido")}</button>}
            {l.status === 'aberto' && <button className="btn" onClick={() => perdido(l)}>{tr("Perdido")}</button>}
            {l.client_id && <Link className="btn" to={`/clients/${l.client_id}`}>{tr("Card do cliente")}</Link>}
            {l.order_id && <Link className="btn" to={`/suits/${l.order_id}`}>{tr("Ver pedido")}</Link>}</> : null}>
          {l.notes && <p className="cd-aviso suit-texto">{l.notes}</p>}
        </Cartao>)}</div>}
    {temMais && <button className="btn ghost" disabled={carregando} onClick={mais}>{tr("Carregar mais")}</button>}
  </Section>
}

/* ============================================================ fornecedores */
const CAMPOS_FORN: [keyof Fornecedor, string][] = [['contact', tr("Contato")], ['email', tr("E-mail")], ['phone', tr("Telefone")], ['status', tr("Situação")],
  ['price', tr("Valor por macacão")], ['shipping', tr("Frete")], ['payment', tr("Pagamento")], ['lead_time', tr("Prazo")], ['comments', tr("Contexto para a IA")]]

function Fornecedores() {
  const { can } = useAuth()
  const toast = useToast()
  const lista = useGet<Fornecedor[]>('/suits/fornecedores')
  const [ed, setEd] = useState<Partial<Fornecedor> | null>(null)
  async function salvar() {
    if (!ed) return
    try {
      const corpo = { ...ed, is_current: !!ed.is_current }
      if (ed.id) await api.patch(`/suits/fornecedores/${ed.id}`, corpo); else await api.post('/suits/fornecedores', corpo)
      setEd(null); lista.reload(); toast(tr("Fornecedor salvo."), 'ok')
    } catch (e) { toast((e as ApiError).message, 'crit') }
  }
  return <Section title={tr("Fornecedores")} count={lista.data?.length} right={can('MANAGER') && <button className="btn sm" onClick={() => setEd({})}><Icon name="plus" size={14} /> {tr("Novo")}</button>}>
    <p className="small muted">{tr("Na Ponte de e-mail de cada pedido você escolhe o fornecedor; o e-mail e o contexto vêm daqui. O atual vale para o pedido sem escolha.")}</p>
    {lista.error ? <ErrorState error={lista.error} retry={lista.reload} /> : !lista.data ? <Loading /> : !lista.data.length ? <Empty title={tr("Nenhum fornecedor")}>{tr("Importe do Asana ou cadastre.")}</Empty>
      : <div className="cd-grade">{lista.data.map(f => <Cartao key={f.id} id={`forn-${f.id}`} estado={f.is_current ? tr("atual") : (f.status || tr("fornecedor"))} tom={f.is_current ? 'ok' : 'neutral'}
          avatar={f.name} avatarTom="azul" nome={f.name} sub={[f.has_fia === 1 ? tr("FIA") : f.has_fia === 0 ? tr("sem FIA") : null]}
          grande={f.pedidos} detalhe={tr("Pedidos")}
          acoes={can('MANAGER') ? <button className="btn" onClick={() => setEd({ ...f })}><Icon name="pencil" size={14} /> {tr("Editar")}</button> : null}>
          <CdLista>{CAMPOS_FORN.filter(([k]) => f[k]).map(([k, rot]) => <CdItem key={k} tom="neutral" valor={String(f[k])}>{rot}</CdItem>)}</CdLista>
        </Cartao>)}</div>}
    {ed && <Scrim onMouseDown={() => setEd(null)}><div className="modal" style={{ maxWidth: 560 }} onMouseDown={e => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={tr("Fornecedor")}>
      <h3>{ed.id ? tr("Editar {0}", ed.name) : tr("Novo fornecedor")}</h3>
      <div className="suit-form"><label className="fld"><span>{tr("Nome")}</span><input value={ed.name || ''} onChange={e => setEd(x => ({ ...x, name: e.target.value }))} /></label>
        {CAMPOS_FORN.map(([k, rot]) => <label key={k} className="fld"><span>{rot}</span><input value={String(ed[k] ?? '')} onChange={e => setEd(x => ({ ...x, [k]: e.target.value }))} /></label>)}
        <label className="fld"><span>{tr("Tem FIA")}</span><select value={ed.has_fia == null ? '' : String(ed.has_fia)} onChange={e => setEd(x => ({ ...x, has_fia: e.target.value === '' ? null : Number(e.target.value) }))}>
          <option value="">{tr("não sabemos")}</option><option value="1">{tr("sim")}</option><option value="0">{tr("não")}</option></select></label></div>
      <label className="check"><input type="checkbox" checked={!!ed.is_current} onChange={e => setEd(x => ({ ...x, is_current: e.target.checked ? 1 : 0 }))} /> {tr("É o fornecedor atual (recebe os pedidos)")}</label>
      <div className="modal-foot"><button className="btn ghost" onClick={() => setEd(null)}>{tr("Cancelar")}</button><button className="btn primary" onClick={salvar}>{tr("Salvar")}</button></div>
    </div></Scrim>}
  </Section>
}

/** #495 (dono, 29/10: "cria uma aba com contatos dentro da Alpha Line onde tenha os fornecedores e designer"): os dois
 *  cadastros que a Ponte de e-mail do pedido usa, com o e-mail fixo e o contexto para a IA. */
function Contatos() {
  return <><Fornecedores /><Designers /></>
}

/** #481 (dono, 29/10: "designer 1, designer 2, designer 3, com os endereços de e-mail fixos"): a lista que a Ponte de
 *  e-mail do pedido usa. O atual vale para o pedido que não escolheu outro. */
function Designers() {
  const { can } = useAuth()
  const toast = useToast()
  const lista = useGet<Designer[]>('/suits/designers')
  const [ed, setEd] = useState<Partial<Designer> | null>(null)
  async function salvar() {
    if (!ed) return
    try {
      const corpo = { name: ed.name, email: ed.email, notes: ed.notes, is_current: !!ed.is_current }
      if (ed.id) await api.patch(`/suits/designers/${ed.id}`, corpo); else await api.post('/suits/designers', corpo)
      setEd(null); lista.reload(); toast(tr("Designer salvo."), 'ok')
    } catch (e) { toast((e as ApiError).message, 'crit') }
  }
  return <Section title={tr("Designers")} count={lista.data?.length} right={can('MANAGER') && <button className="btn sm" onClick={() => setEd({})}><Icon name="plus" size={14} /> {tr("Novo")}</button>}>
    <p className="small muted">{tr("Na Ponte de e-mail de cada pedido você escolhe o designer; o e-mail e o contexto vêm daqui. O atual vale para o pedido sem escolha. O cliente nunca vê nome nem e-mail de designer.")}</p>
    {lista.error ? <ErrorState error={lista.error} retry={lista.reload} /> : !lista.data ? <Loading /> : !lista.data.length ? <Empty title={tr("Nenhum designer")}>{tr("Cadastre o primeiro.")}</Empty>
      : <div className="cd-grade">{lista.data.map(d => <Cartao key={d.id} id={`designer-${d.id}`} estado={d.is_current ? tr("atual") : tr("designer")} tom={d.is_current ? 'ok' : 'neutral'}
          avatar={d.name} avatarTom="azul" nome={d.name} sub={[d.email]} grande={d.pedidos} detalhe={tr("Pedidos")}
          acoes={can('MANAGER') ? <button className="btn" onClick={() => setEd({ ...d })}><Icon name="pencil" size={14} /> {tr("Editar")}</button> : null}>
          {d.notes ? <CdLista><CdItem tom="neutral" valor={d.notes}>{tr("Contexto para a IA")}</CdItem></CdLista> : null}
        </Cartao>)}</div>}
    {ed && <Scrim onMouseDown={() => setEd(null)}><div className="modal" style={{ maxWidth: 520 }} onMouseDown={e => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={tr("Designer")}>
      <h3>{ed.id ? tr("Editar {0}", ed.name) : tr("Novo designer")}</h3>
      <div className="suit-form">
        <label className="fld"><span>{tr("Nome")}</span><input value={ed.name || ''} onChange={e => setEd(x => ({ ...x, name: e.target.value }))} /></label>
        <label className="fld"><span>{tr("E-mail")}</span><input type="email" inputMode="email" value={ed.email || ''} onChange={e => setEd(x => ({ ...x, email: e.target.value }))} /></label>
        <label className="fld"><span>{tr("Contexto para a IA (o que ele faz, como falar com ele, idioma)")}</span><textarea rows={4} value={ed.notes || ''} onChange={e => setEd(x => ({ ...x, notes: e.target.value }))} /></label></div>
      <label className="check"><input type="checkbox" checked={!!ed.is_current} onChange={e => setEd(x => ({ ...x, is_current: e.target.checked ? 1 : 0 }))} /> {tr("É o designer atual (vale para o pedido sem escolha)")}</label>
      <div className="modal-foot"><button className="btn ghost" onClick={() => setEd(null)}>{tr("Cancelar")}</button><button className="btn primary" onClick={salvar}>{tr("Salvar")}</button></div>
    </div></Scrim>}
  </Section>
}

/* ============================================================ o modelo do e-mail */
function Modelo() {
  const { can } = useAuth()
  const toast = useToast()
  const m = useGet<{ subject: string; body: string; updated_at: string | null; campos: string[]; padrao: { subject: string; body: string } }>('/suits/modelo')
  const [ed, setEd] = useState<{ subject: string; body: string } | null>(null)
  async function salvar() {
    if (!ed) return
    try { await api.put('/suits/modelo', ed); setEd(null); m.reload(); toast(tr("Modelo salvo: os próximos pedidos saem assim."), 'ok') } catch (e) { toast((e as ApiError).message, 'crit') }
  }
  if (m.error) return <div className="card"><ErrorState error={m.error} retry={m.reload} /></div>
  if (!m.data) return <div className="card"><Loading /></div>
  const v = ed || m.data
  return <Section title={tr("E-mail ao fornecedor")} right={can('MANAGER') && !ed && <button className="btn sm ghost" onClick={() => setEd({ subject: m.data!.subject, body: m.data!.body })}><Icon name="pencil" size={14} /> {tr("Editar")}</button>}>
    <p className="small muted">{tr("O padrão dos últimos pedidos enviados ao Usman: assunto \"SUIT - piloto\", \"Hi Usman, We have a new order:\", as 29 medidas numeradas em cm e pés/polegadas, cor e mockup, e a assinatura da URACE. Os campos")} {m.data.campos.join(' ')} {tr("são trocados pelos dados do pedido.")}{m.data.updated_at ? tr(" Editado em {0}.", horaFL(m.data.updated_at)) : ''}</p>
    {ed ? <>
      <label className="fld"><span>{tr("Assunto")}</span><input value={ed.subject} onChange={e => setEd({ ...ed, subject: e.target.value })} /></label>
      <label className="fld"><span>{tr("Corpo")}</span><textarea rows={14} value={ed.body} onChange={e => setEd({ ...ed, body: e.target.value })} /></label>
      <div className="row gap wrap"><button className="btn ghost" onClick={() => setEd(null)}>{tr("Cancelar")}</button>
        <button className="btn ghost" onClick={() => setEd({ ...m.data!.padrao })}>{tr("Voltar ao padrão")}</button><button className="btn primary" onClick={salvar}>{tr("Salvar modelo")}</button></div>
    </> : <><div className="small muted">{tr("Assunto:")} <b>{v.subject}</b></div><pre className="suit-pre">{v.body}</pre></>}
  </Section>
}

/* ============================================================ WhatsApp do ateliê (#383) */
interface WaGrupo { papel: string; nome: string; configurado: boolean; idioma: string }
interface WaCfg { existe: boolean; aplicar: boolean; tem_segredo: boolean; numero: string | null; grupos: WaGrupo[] }
interface WaEstado { config: WaCfg; envio_automatico: boolean; rascunhos: number; sem_pedido: number }
interface WaAnexo { nome: string; tipo?: string | null; bytes?: number; nao_guardado?: boolean }
interface WaMsg { id: number; papel: string; direcao: string; remetente_nome: string | null; texto: string | null; resposta_texto?: string | null
  anexos: string | null; vinculo?: string | null; estado?: string; candidatos?: string | null; at: string | null }
interface WaSaida { id: number; order_id?: number; title?: string; papel: string; motivo: string; texto: string; anexos: string | null
  estado: string; erro?: string | null; created_at: string }
interface WaPedido { mensagens: WaMsg[]; saidas: WaSaida[]; pedido: { id: number; status: string; tracking: string | null; checked_at: string | null
  address_sent_at: string | null }; config: WaCfg }
const GRUPO: Record<string, string> = { design: tr("Grupo de design"), fornecedor: tr("Grupo do fornecedor") }
const MOTIVO: Record<string, string> = { mensagem: tr("mensagem"), cobranca: tr("cobrança do dia"), endereco: tr("endereço de envio") }
const anexosDe = (j: string | null): WaAnexo[] => { try { return j ? JSON.parse(j) : [] } catch { return [] } }

/** Um rascunho para o grupo: o texto pode ser corrigido antes do aprovar. */
function RascunhoWa({ s, onDone }: { s: WaSaida; onDone: () => void }) {
  const toast = useToast()
  const [texto, setTexto] = useState(s.texto)
  const [indo, setIndo] = useState(false)
  async function acao(qual: 'aprovar' | 'descartar') {
    setIndo(true)
    try {
      await api.post(`/atelie/saidas/${s.id}/${qual}`, qual === 'aprovar' ? { texto } : {})
      toast(qual === 'aprovar' ? tr("Enviado ao grupo.") : tr("Rascunho descartado."), 'ok'); onDone()
    } catch (e) { toast((e as ApiError).message, 'crit') } finally { setIndo(false) }
  }
  return <li className="wa-rascunho">
    <div className="small muted">{GRUPO[s.papel] || s.papel} · {MOTIVO[s.motivo] || s.motivo} · {horaFL(s.created_at)}
      {s.order_id ? <> · <Link to={`/suits/${s.order_id}`}>{s.title || `#${s.order_id}`}</Link></> : null}</div>
    {s.erro && <p className="small" style={{ color: 'var(--crit)', margin: '4px 0' }}>{tr("Não saiu:")} {s.erro}</p>}
    <label className="fld"><span className="sr-only">{tr("Texto da mensagem")}</span>
      <textarea rows={Math.min(8, Math.max(2, texto.split('\n').length))} value={texto} onChange={e => setTexto(e.target.value)} /></label>
    {anexosDe(s.anexos).length > 0 && <p className="small muted">{tr("Anexos:")} {anexosDe(s.anexos).map(a => typeof a === 'string' ? a : a.nome).join(', ')}</p>}
    <div className="row gap wrap"><button className="btn primary" disabled={indo} onClick={() => acao('aprovar')}>{tr("Aprovar e enviar")}</button>
      <button className="btn ghost" disabled={indo} onClick={() => acao('descartar')}>{tr("Descartar")}</button></div>
  </li>
}

const IMAGEM = /\.(png|jpe?g|webp)$/i

function MensagemWa({ m, pedido, foto }: { m: WaMsg; pedido?: number; foto?: (m: WaMsg, nome: string) => void }) {
  const anexos = anexosDe(m.anexos)
  return <li className={`wa-msg ${m.direcao === 'saida' ? 'nossa' : ''}`}>
    <div className="small muted">{GRUPO[m.papel] || m.papel} · {m.direcao === 'saida' ? tr("URACE") : (m.remetente_nome || tr("participante"))}{m.at ? ` · ${horaFL(m.at)}` : ''}</div>
    {m.resposta_texto && <div className="small muted wa-citada">↪ {m.resposta_texto.slice(0, 160)}</div>}
    {m.texto && <div className="suit-texto">{m.texto}</div>}
    {anexos.length > 0 && <ul className="suit-lista">{anexos.map(a => <li key={a.nome}>
      {a.nao_guardado ? <span className="small muted">{a.nome} {tr("(grande demais, não guardado)")}</span>
        : <a className="suit-linha" target="_blank" rel="noreferrer"
            href={pedido ? `/ops/api/suits/${pedido}/anexos/${encodeURIComponent(a.nome)}` : `/ops/api/atelie/mensagens/${m.id}/anexos/${encodeURIComponent(a.nome)}`}>
            <span className="grow truncate">{a.nome}</span>{a.bytes ? <span className="small muted">{tamanho(a.bytes)}</span> : null}</a>}
      {foto && pedido && m.papel === 'fornecedor' && m.direcao === 'entrada' && !a.nao_guardado && IMAGEM.test(a.nome) &&
        <button className="btn ghost sm" onClick={() => foto(m, a.nome)}>{tr("Usar como foto do suit")}</button>}</li>)}</ul>}
  </li>
}

function WhatsAppDoPedido({ pedido, onDone }: { pedido: PedidoApi; onDone: () => void }) {
  const toast = useToast()
  const w = useGet<WaPedido>(`/atelie/pedidos/${pedido.id}?v=${pedido.notas.length}`, 30000)
  const [papel, setPapel] = useState('design')
  const [texto, setTexto] = useState('')
  const [codigo, setCodigo] = useState('')
  const [transp, setTransp] = useState('')
  const [indo, setIndo] = useState('')
  if (w.error) return <Section title={tr("WhatsApp do ateliê")}><ErrorState error={w.error} retry={w.reload} /></Section>
  if (!w.data) return null
  const d = w.data
  const grupos = d.config.grupos.filter(g => g.configurado && GRUPO[g.papel])
  const pendentes = d.saidas.filter(s => s.estado === 'rascunho' || s.estado === 'falhou')
  const recarregar = () => { w.reload(); onDone() }
  async function fazer(qual: string, rota: string, corpo: object, ok: string) {
    setIndo(qual)
    try { await api.post(rota, corpo); toast(ok, 'ok'); recarregar(); return true }
    catch (e) { toast((e as ApiError).message, 'crit'); return false } finally { setIndo('') }
  }
  return <Section title={tr("WhatsApp do ateliê")} count={d.mensagens.length}>
    {!grupos.length ? <p className="small muted">{tr("Os grupos do WhatsApp ainda não estão ligados na VPS (Suits › WhatsApp).")}</p> : <>
      <p className="small muted">{tr("O designer e o fornecedor no WhatsApp. O que vai ao grupo segue a chave de envio automático da ponte: desligada, fica aqui para aprovar.")}</p>
      {pendentes.length > 0 && <><h3 className="h3">{tr("Para aprovar")}</h3>
        <ul className="suit-lista">{pendentes.map(s => <RascunhoWa key={s.id} s={s} onDone={recarregar} />)}</ul></>}
      <h3 className="h3" style={{ marginTop: 12 }}>{tr("Escrever no grupo")}</h3>
      <div className="suit-form">
        <label className="fld"><span>{tr("Grupo")}</span><select value={papel} onChange={e => setPapel(e.target.value)}>
          {grupos.map(g => <option key={g.papel} value={g.papel}>{GRUPO[g.papel]}{g.nome ? ` (${g.nome})` : ''}</option>)}</select></label>
      </div>
      <label className="fld"><span>{tr("Mensagem (sai na hora, com o número do pedido)")}</span>
        <textarea rows={3} value={texto} onChange={e => setTexto(e.target.value)} placeholder={tr("Ao designer, só o design: nada de contato ou pagamento do cliente.")} /></label>
      <div className="row gap wrap"><button className="btn" disabled={!!indo || !texto.trim()} onClick={async () => {
        if (await fazer('escrever', `/atelie/pedidos/${pedido.id}/escrever`, { papel, texto }, tr("Enviado ao grupo."))) setTexto('') }}>{tr("Enviar ao grupo")}</button></div>
      <h3 className="h3" style={{ marginTop: 12 }}>{tr("Suit pronto e envio")}</h3>
      {d.pedido.address_sent_at
        ? <p className="small">{tr("Endereço enviado ao fornecedor.")}</p>
        : d.pedido.status === 'checked'
        ? <><p className="small muted">{tr("A equipe conferiu as fotos (Checked): o endereço de entrega pode ir ao grupo do fornecedor.")}</p>
          <button className="btn" disabled={!!indo} onClick={() => fazer('endereco', `/atelie/pedidos/${pedido.id}/endereco`, {}, tr("Endereço enviado ao grupo do fornecedor."))}>{tr("Mandar o endereço ao fornecedor")}</button></>
        : <p className="small muted">{tr("As fotos do fornecedor que chegarem no grupo viram a foto do suit (Photos received) com um clique. O endereço só vai depois do OK da equipe (Checked).")}</p>}
      <div className="suit-form" style={{ marginTop: 10 }}>
        <label className="fld"><span>{tr("Código de rastreio")}</span><input value={codigo} onChange={e => setCodigo(e.target.value)} placeholder={pedido.tracking || ''} /></label>
        <label className="fld"><span>{tr("Transportadora (opcional)")}</span><input value={transp} onChange={e => setTransp(e.target.value)} /></label>
      </div>
      <button className="btn ghost" disabled={!!indo || !codigo.trim()} onClick={async () => {
        if (await fazer('rastreio', `/atelie/pedidos/${pedido.id}/rastreio`, { codigo, transportadora: transp || null }, tr("Rastreio gravado no pedido."))) { setCodigo(''); setTransp('') } }}>{tr("Gravar rastreio")}</button>
    </>}
    {d.mensagens.length > 0 && <><h3 className="h3" style={{ marginTop: 12 }}>{tr("Mensagens dos grupos")}</h3>
      <ol className="suit-lista">{d.mensagens.map(m => <MensagemWa key={m.id} m={m} pedido={pedido.id}
        foto={(x, nome) => fazer('foto', `/atelie/mensagens/${x.id}/foto-do-suit`, { nome }, tr("Foto do suit salva no pedido (Photos received)."))} />)}</ol></>}
  </Section>
}

function WhatsApp() {
  const toast = useToast()
  const e = useGet<WaEstado>('/atelie/whatsapp', 30000)
  const rasc = usePaginado<WaSaida>('/atelie/whatsapp/rascunhos', 50)
  const soltas = usePaginado<WaMsg>('/atelie/whatsapp/sem-pedido', 50)
  const [alvo, setAlvo] = useState<Record<number, string>>({})
  if (e.error) return <div className="card"><ErrorState error={e.error} retry={e.reload} /></div>
  if (!e.data) return <div className="card"><Loading /></div>
  const c = e.data.config
  async function ligar(m: WaMsg) {
    const n = Number((alvo[m.id] || '').replace('#', ''))
    if (!n) { toast(tr("Diga o número do pedido."), 'warn'); return }
    try { await api.post(`/atelie/mensagens/${m.id}/vincular`, { order_id: n }); toast(tr("Mensagem ligada ao pedido #{0}.", n), 'ok'); soltas.recarregar(); e.reload() }
    catch (x) { toast((x as ApiError).message, 'crit') }
  }
  return <>
    <Section title={tr("WhatsApp do ateliê")}>
      <p className="small muted">{tr("O OpenClaw na VPS lê só os grupos da lista (DM desligada) e o agente de Suits opera neles: manda o pedido de design, recebe a arte, cobra o que está em aberto uma vez por dia, manda o endereço ao fornecedor depois do OK da equipe nas fotos e grava o rastreio.")}</p>
      {!c.existe ? <p className="small" style={{ color: 'var(--warn)' }}>{tr("Ainda não configurado na VPS (~/.urace/whatsapp-grupos.env).")}</p> : <>
        {!c.aplicar && <p className="small" style={{ color: 'var(--warn)' }}><b>{tr("Em simulação:")}</b> {tr("nada sai para os grupos (WA_GRUPOS_APLICAR=0). As mensagens ficam como rascunho nos pedidos.")}</p>}
        {c.aplicar && !e.data.envio_automatico && <p className="small"><b>{tr("Com aprovação:")}</b> {tr("cada mensagem ao grupo espera o aprovar de um clique (envio automático da ponte desligado).")}</p>}
        {c.aplicar && e.data.envio_automatico && <p className="small" style={{ color: 'var(--ok)' }}><b>{tr("Envio automático ligado:")}</b> {tr("a IA manda sem esperar aprovação.")}</p>}
        <dl className="suit-dl">
          <div><dt>{tr("Número logado")}</dt><dd>{c.numero || <span className="muted">—</span>}</dd></div>
          {c.grupos.map(g => <div key={g.papel}><dt>{GRUPO[g.papel] || g.papel}</dt><dd>{g.nome || '—'} · {g.configurado ? tr("ligado") : <span style={{ color: 'var(--warn)' }}>{tr("sem o JID ainda")}</span>}</dd></div>)}
        </dl>
      </>}
    </Section>
    <Section title={tr("Para aprovar")} count={rasc.total}>
      {rasc.erro ? <ErrorState error={rasc.erro} retry={rasc.recarregar} /> : !rasc.itens.length ? <p className="small muted">{tr("Nada esperando aprovação.")}</p>
        : <ul className="suit-lista">{rasc.itens.map(s => <RascunhoWa key={s.id} s={s} onDone={() => { rasc.recarregar(); e.reload() }} />)}</ul>}
      {rasc.temMais && <button className="btn ghost" onClick={rasc.mais}>{tr("Carregar mais")}</button>}
    </Section>
    <Section title={tr("Sem pedido")} count={soltas.total}>
      <p className="small muted">{tr("Mensagens dos grupos que não dizem de qual pedido são, ou que podem ser de mais de um. Ninguém adivinha: ligue ao pedido certo.")}</p>
      {soltas.erro ? <ErrorState error={soltas.erro} retry={soltas.recarregar} /> : !soltas.itens.length ? <p className="small muted">{tr("Nenhuma.")}</p>
        : <ul className="suit-lista">{soltas.itens.map(m => <li key={m.id}><ul className="suit-lista"><MensagemWa m={m} /></ul>
            {m.estado === 'ambigua' && m.candidatos && <p className="small" style={{ color: 'var(--warn)' }}>{tr("Pode ser de:")} {(JSON.parse(m.candidatos) as number[]).map(n => `#${n}`).join(', ')}</p>}
            <div className="row gap wrap"><label className="fld"><span>{tr("Número do pedido")}</span>
              <input inputMode="numeric" value={alvo[m.id] || ''} onChange={ev => setAlvo(x => ({ ...x, [m.id]: ev.target.value }))} placeholder="#" /></label>
              <button className="btn" onClick={() => ligar(m)}>{tr("Ligar ao pedido")}</button></div></li>)}</ul>}
      {soltas.temMais && <button className="btn ghost" onClick={soltas.mais}>{tr("Carregar mais")}</button>}
    </Section>
  </>
}
