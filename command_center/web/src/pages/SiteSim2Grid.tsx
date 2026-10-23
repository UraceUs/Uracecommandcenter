/* #392 · Site › Sim2Grid (dono, 22/10): "sera um serviço um diferente das aulas de kart podendo agendar ate 5 pessoas
 * para a mesma hora, o valor do serviço é cobrado por hora. monte assim como montou o arrive and drive com todas as
 * configurações ajustaveis".
 *
 * Três partes, como o Arrive and Drive: as regras (vender online, quantos simuladores por hora, horas mínimas e máximas,
 * horizonte, antecedência, abertura, datas fechadas, idade, waiver, aviso e sorteio), as faixas de preço de cada formato
 * por dia e horário (preço vazio = "ligue para nós") e as reservas que vêm do site. O nome, o texto, o depósito e o item
 * do QuickBooks de cada formato ficam em Serviços e preços; os programas mensais, em Cartões das páginas.
 *
 * #396 (dono, 23/10): "alguns dias frequentados por pilotos · outros dias por pessoas que vao levar como
 * entretenimento". A etiqueta do dia (ex.: 🏁 Pilot day, 🎮 Fun night) por dia da semana ou por data, o dia inteiro
 * ou uma faixa de horas: o selo no calendário do site e no topo do dia. Nasce vazia; o gerente define, o operador vê. */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { useGet } from '../api/hooks'
import { useAuth } from '../auth/AuthContext'
import { Banner, Chip, Empty, ErrorState, Loading, Section } from '../components/ui'
import { useToast } from '../components/Toast'
import { tr } from '../i18n'

interface Config { online: number; capacity: number; min_hours: number; max_hours: number; horizon_days: number; min_notice_hours: number
  open_from: string | null; closed_dates: string | null; min_age: number | null; waiver_required: number; notice: string | null; raffle_text: string | null }
interface Formato { id: number; name: string; titulo: string; linha: string; texto: string; deposit: number; active: boolean; qbo_item_id: string | null }
interface Faixa { id: number; service_id: number; service_name: string; days: string; start_hour: number; end_hour: number; price: number | null; active: number; sort: number }
interface Etiqueta { id: number; label: string; icon: string | null; note: string | null; days: string | null; date: string | null
  start_hour: number | null; end_hour: number | null; active: number; sort: number }
type EtiquetaForm = { label: string; icon: string; note: string; modo: 'semana' | 'data'; days: string; date: string; start_hour: string; end_hour: string }
interface Reserva { id: number; date: string; start_hour: number; hours: number; price: number; status: 'paga' | 'segurada'; service_name: string | null
  pilot_name: string | null; account_name: string | null; account_email: string | null; client_id: number | null; client_name: string | null
  order_id: number | null; raffle: number; waiver_ref: number | null; waiver_error: string | null }
interface Painel { config: Config; formatos: Formato[]; faixas: Faixa[]; etiquetas: Etiqueta[]; pagina: string; desde: number | null
  reservas: { itens: Reserva[]; total: number; limit: number; offset: number } }

const DIAS = [tr("Seg"), tr("Ter"), tr("Qua"), tr("Qui"), tr("Sex"), tr("Sáb"), tr("Dom")]
const POR_PAGINA = 30
const usd = (n: number) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
const hora = (h: number) => `${String(h % 24).padStart(2, '0')}:00`
const dbr = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`
type Regras = Partial<Record<keyof Config, string | number | boolean | null>>

const CAMPOS: [keyof Config, string, string, number, number][] = [
  ['capacity', tr("Simuladores (pessoas por hora)"), tr("vagas de cada hora"), 1, 50],
  ['min_hours', tr("Horas mínimas seguidas"), '', 1, 12],
  ['max_hours', tr("Horas máximas seguidas"), '', 1, 12],
  ['horizon_days', tr("Mostra até (dias)"), '', 1, 365],
  ['min_notice_hours', tr("Antecedência (horas)"), '', 0, 720],
  ['min_age', tr("Idade mínima"), tr("vazio = o site não diz"), 1, 99],
]

const ETIQUETA_VAZIA: EtiquetaForm = { label: '', icon: '', note: '', modo: 'semana', days: '', date: '', start_hour: '', end_hour: '' }
const alterna = (dias: string, i: number) => (dias.includes(String(i)) ? dias.replace(String(i), '') : dias + i).split('').sort().join('')
const doBanco = (t: Etiqueta): EtiquetaForm => ({ label: t.label, icon: t.icon || '', note: t.note || '', modo: t.date ? 'data' : 'semana',
  days: t.days || '', date: t.date || '', start_hour: t.start_hour == null ? '' : String(t.start_hour), end_hour: t.end_hour == null ? '' : String(t.end_hour) })
const paraApi = (f: EtiquetaForm) => ({ label: f.label, icon: f.icon, note: f.note, days: f.modo === 'semana' ? f.days : null,
  date: f.modo === 'data' ? f.date : null, start_hour: f.start_hour === '' ? null : Number(f.start_hour), end_hour: f.end_hour === '' ? null : Number(f.end_hour) })

/** A etiqueta do dia (#396): a mesma caixa para criar e para editar. */
function CamposEtiqueta({ f, muda, gerente, rotulo }: { f: EtiquetaForm; muda: (x: Partial<EtiquetaForm>) => void; gerente: boolean; rotulo: string }) {
  return <>
    <label className="fld" style={{ margin: 0, width: 72 }}><span>{tr("Ícone")}</span>
      <input disabled={!gerente} maxLength={8} value={f.icon} placeholder="🏁" onChange={e => muda({ icon: e.target.value })} /></label>
    <label className="fld" style={{ margin: 0, minWidth: 150 }}><span>{tr("Rótulo")} <i>{tr("curto, em inglês")}</i></span>
      <input disabled={!gerente} maxLength={24} value={f.label} placeholder="Pilot day" onChange={e => muda({ label: e.target.value })} /></label>
    <label className="fld" style={{ margin: 0 }}><span>{tr("Quando")}</span>
      <select disabled={!gerente} value={f.modo} onChange={e => muda({ modo: e.target.value as EtiquetaForm['modo'] })}>
        <option value="semana">{tr("Dias da semana")}</option><option value="data">{tr("Uma data")}</option></select></label>
    {f.modo === 'semana'
      ? <div className="seg" role="group" aria-label={rotulo}>{DIAS.map((n, i) =>
        <button key={n} type="button" aria-pressed={f.days.includes(String(i))} disabled={!gerente} className={`btn sm${f.days.includes(String(i)) ? '' : ' ghost'}`}
          onClick={() => muda({ days: alterna(f.days, i) })}>{n}</button>)}</div>
      : <label className="fld" style={{ margin: 0 }}><span>{tr("Data")}</span>
        <input type="date" disabled={!gerente} value={f.date} onChange={e => muda({ date: e.target.value })} /></label>}
    <label className="fld" style={{ margin: 0 }}><span>{tr("De")}</span><select disabled={!gerente} value={f.start_hour} onChange={e => muda({ start_hour: e.target.value })}>
      <option value="">{tr("o dia todo")}</option>{Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{hora(h)}</option>)}</select></label>
    <label className="fld" style={{ margin: 0 }}><span>{tr("Até")}</span><select disabled={!gerente} value={f.end_hour} onChange={e => muda({ end_hour: e.target.value })}>
      <option value="">{tr("o dia todo")}</option>{Array.from({ length: 24 }, (_, h) => <option key={h + 1} value={h + 1}>{h + 1 === 24 ? tr("meia-noite") : hora(h + 1)}</option>)}</select></label>
    <label className="fld" style={{ margin: 0, flex: '1 1 220px' }}><span>{tr("Texto curto do dia")} <i>{tr("opcional, em inglês")}</i></span>
      <input disabled={!gerente} maxLength={120} value={f.note} placeholder="Coaches on site · race setups" onChange={e => muda({ note: e.target.value })} /></label>
  </>
}

export function SiteSim2Grid() {
  const { can } = useAuth()
  const gerente = can('MANAGER')
  const toast = useToast()
  const [pagina, setPagina] = useState(0)
  const p = useGet<Painel>(`/site/sim2grid?limit=${POR_PAGINA}&offset=${pagina * POR_PAGINA}`)
  const [cfg, setCfg] = useState<Regras>({})
  const [edit, setEdit] = useState<Record<number, Partial<Faixa> & { price_txt?: string }>>({})
  const [nova, setNova] = useState({ service_id: 0, days: '01234', start_hour: '7', end_hour: '17', price: '' })
  const [etq, setEtq] = useState<Record<number, EtiquetaForm>>({})
  const [novaEtq, setNovaEtq] = useState<EtiquetaForm>(ETIQUETA_VAZIA)
  if (p.error && !p.data) return <ErrorState error={p.error} retry={p.reload} />
  if (!p.data) return <Loading />
  const d = p.data
  const c = { ...d.config, ...cfg } as Config
  const valor = (k: keyof Config) => (cfg[k] !== undefined ? cfg[k] : d.config[k]) ?? ''

  async function salvarRegras() {
    try { await api.patch('/site/sim2grid/config', cfg); toast(tr("Regras salvas: o site já mostra."), 'ok'); setCfg({}); p.reload() }
    catch (e) { toast((e as ApiError).message, 'crit') }
  }
  async function salvarFaixa(f: Faixa, extra?: Partial<Faixa>) {
    const e = edit[f.id] || {}
    const corpo: Record<string, unknown> = { ...extra }
    if (e.days !== undefined) corpo.days = e.days
    if (e.start_hour !== undefined) corpo.start_hour = e.start_hour
    if (e.end_hour !== undefined) corpo.end_hour = e.end_hour
    if (e.price_txt !== undefined) corpo.price = e.price_txt.trim() || null
    try { await api.patch(`/site/sim2grid/faixas/${f.id}`, corpo); toast(tr("Faixa salva: vale para as próximas reservas."), 'ok')
      setEdit(x => { const y = { ...x }; delete y[f.id]; return y }); p.reload() }
    catch (er) { toast((er as ApiError).message, 'crit') }
  }
  async function criarFaixa() {
    const sid = nova.service_id || d.formatos[0]?.id
    try { await api.post('/site/sim2grid/faixas', { ...nova, service_id: sid, price: nova.price.trim() || null })
      toast(tr("Faixa criada: o site já mostra."), 'ok'); setNova({ ...nova, price: '' }); p.reload() }
    catch (er) { toast((er as ApiError).message, 'crit') }
  }
  async function salvarEtiqueta(t: Etiqueta, extra?: Record<string, unknown>) {
    const corpo = extra || paraApi(etq[t.id] || doBanco(t))
    try { await api.patch(`/site/sim2grid/etiquetas/${t.id}`, corpo); toast(tr("Etiqueta salva: o calendário do site já mostra."), 'ok')
      setEtq(x => { const y = { ...x }; delete y[t.id]; return y }); p.reload() }
    catch (er) { toast((er as ApiError).message, 'crit') }
  }
  async function criarEtiqueta() {
    try { await api.post('/site/sim2grid/etiquetas', paraApi(novaEtq)); toast(tr("Etiqueta criada: o calendário do site já mostra."), 'ok')
      setNovaEtq(ETIQUETA_VAZIA); p.reload() }
    catch (er) { toast((er as ApiError).message, 'crit') }
  }
  const mudaFaixa = (id: number, x: Partial<Faixa> & { price_txt?: string }) => setEdit(e => ({ ...e, [id]: { ...e[id], ...x } }))
  const alternaDia = (dias: string, i: number) => (dias.includes(String(i)) ? dias.replace(String(i), '') : dias + i).split('').sort().join('')
  const total = d.reservas.total, paginas = Math.max(1, Math.ceil(total / POR_PAGINA))

  return <div className="stack" style={{ gap: 18 }}>
    {!c.online && <Banner tone="warn">{tr("A venda online do SIM2GRID está desligada: a página mostra os preços e o telefone, sem o botão de reservar.")}</Banner>}
    {!d.formatos.some(f => f.active) && <Banner tone="warn">{tr("Nenhum formato de simulador ativo em Serviços e preços: o site não vende a hora.")}</Banner>}

    <Section title={tr("Regras da reserva")} right={<a className="btn sm ghost" href={d.pagina} target="_blank" rel="noreferrer">{tr("Ver no site ↗")}</a>}>
      <div className="site-horarios">
        {CAMPOS.map(([k, rot, dica, mi, ma]) => <label key={k} className="fld" style={{ margin: 0 }}><span>{rot} {dica && <i>{dica}</i>}</span>
          <input type="number" min={mi} max={ma} disabled={!gerente} value={String(valor(k))} onChange={e => setCfg({ ...cfg, [k]: e.target.value })} /></label>)}
        <label className="fld" style={{ margin: 0 }}><span>{tr("Abre a partir de")}</span>
          <input type="date" disabled={!gerente} value={String(valor('open_from'))} onChange={e => setCfg({ ...cfg, open_from: e.target.value })} /></label>
      </div>
      <div className="site-servico" style={{ marginTop: 10 }}>
        <label className="fld"><span>{tr("Datas fechadas")} <i>{tr("AAAA-MM-DD, separadas por vírgula")}</i></span>
          <input disabled={!gerente} value={String(valor('closed_dates'))} placeholder="2026-12-25, 2026-12-31" onChange={e => setCfg({ ...cfg, closed_dates: e.target.value })} /></label>
        <label className="fld"><span>{tr("Aviso perto do botão")} <i>{tr("opcional, em inglês")}</i></span>
          <textarea rows={2} disabled={!gerente} value={String(valor('notice'))} onChange={e => setCfg({ ...cfg, notice: e.target.value })} /></label>
        <label className="fld"><span>{tr("Texto do sorteio do mês")} <i>{tr("vazio = sem a caixa")}</i></span>
          <input disabled={!gerente} value={String(valor('raffle_text'))} onChange={e => setCfg({ ...cfg, raffle_text: e.target.value })} /></label>
      </div>
      <label className="check" style={{ marginTop: 10, minHeight: 40 }}><input type="checkbox" disabled={!gerente} checked={!!c.online} onChange={e => setCfg({ ...cfg, online: e.target.checked })} />
        {' '}{tr("Vender online")} <span className="small muted">{tr("(o mesmo carrinho e Stripe do Arrive and Drive; desligado, a página pede para ligar)")}</span></label>
      <label className="check" style={{ minHeight: 40 }}><input type="checkbox" disabled={!gerente} checked={!!c.waiver_required} onChange={e => setCfg({ ...cfg, waiver_required: e.target.checked })} />
        {' '}{tr("Waiver obrigatória")} <span className="small muted">{tr("(cada piloto assina a waiver, como no kart)")}</span></label>
      {gerente && Object.keys(cfg).length > 0 && <div style={{ marginTop: 10 }}><button className="btn primary" onClick={salvarRegras}>{tr("Salvar regras")}</button></div>}
      <p className="small muted" style={{ margin: '10px 0 0' }}>{tr("Cada pessoa é um simulador: a hora fica cheia quando as reservas pagas e as que estão no pagamento somam os simuladores. O nome, o texto, o depósito e o item do QuickBooks de cada formato ficam em")} <Link to="/site/servicos">{tr("Serviços e preços")}</Link>{tr("; os programas mensais, em")} <Link to="/site/cartoes">{tr("Cartões das páginas")}</Link>.</p>
    </Section>

    <Section title={tr("Faixas de preço por hora")} count={d.faixas.filter(f => f.active).length}>
      {d.desde != null && <p className="small muted" style={{ marginTop: 0 }}>{tr("A partir de {0} por hora no site (a menor faixa com preço).", usd(d.desde))}</p>}
      <div className="tbl">{d.faixas.map(f => { const e = edit[f.id] || {}; const dias = e.days ?? f.days
        return <div className="tr" key={f.id} data-faixa={f.id} style={{ flexWrap: 'wrap', gap: 8, opacity: f.active ? 1 : .6 }}>
          <b style={{ minWidth: 180 }}>{f.service_name}</b>
          <div className="seg" role="group" aria-label={tr("Dias da faixa")}>{DIAS.map((n, i) =>
            <button key={n} type="button" aria-pressed={dias.includes(String(i))} disabled={!gerente} className={`btn sm${dias.includes(String(i)) ? '' : ' ghost'}`}
              onClick={() => mudaFaixa(f.id, { days: alternaDia(dias, i) })}>{n}</button>)}</div>
          <label className="fld" style={{ margin: 0 }}><span>{tr("De")}</span><select disabled={!gerente} value={e.start_hour ?? f.start_hour} onChange={x => mudaFaixa(f.id, { start_hour: Number(x.target.value) })}>
            {Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{hora(h)}</option>)}</select></label>
          <label className="fld" style={{ margin: 0 }}><span>{tr("Até")}</span><select disabled={!gerente} value={e.end_hour ?? f.end_hour} onChange={x => mudaFaixa(f.id, { end_hour: Number(x.target.value) })}>
            {Array.from({ length: 24 }, (_, h) => <option key={h + 1} value={h + 1}>{h + 1 === 24 ? tr("meia-noite") : hora(h + 1)}</option>)}</select></label>
          <label className="fld" style={{ margin: 0 }}><span>{tr("US$ por hora")} <i>{tr("vazio = ligar")}</i></span>
            <input inputMode="decimal" disabled={!gerente} value={e.price_txt ?? (f.price != null ? String(f.price) : '')} placeholder={tr("ligar")} onChange={x => mudaFaixa(f.id, { price_txt: x.target.value })} /></label>
          {f.price == null && <Chip tone="warn">{tr("ligue para nós")}</Chip>}
          {!f.active && <Chip tone="neutral">{tr("desativada")}</Chip>}
          {gerente && <><button className="btn sm primary" disabled={!edit[f.id]} onClick={() => salvarFaixa(f)}>{tr("Salvar")}</button>
            <button className="btn sm" onClick={() => salvarFaixa(f, { active: f.active ? 0 : 1 })}>{f.active ? tr("Desativar") : tr("Reativar")}</button></>}
        </div> })}</div>
      {gerente && d.formatos.length > 0 && <div className="row gap wrap" style={{ alignItems: 'flex-end', marginTop: 12 }}>
        <label className="fld" style={{ margin: 0 }}><span>{tr("Formato")}</span><select value={nova.service_id || d.formatos[0].id} onChange={x => setNova({ ...nova, service_id: Number(x.target.value) })}>
          {d.formatos.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}</select></label>
        <div className="seg" role="group" aria-label={tr("Dias da faixa nova")}>{DIAS.map((n, i) =>
          <button key={n} type="button" aria-pressed={nova.days.includes(String(i))} className={`btn sm${nova.days.includes(String(i)) ? '' : ' ghost'}`}
            onClick={() => setNova({ ...nova, days: alternaDia(nova.days, i) })}>{n}</button>)}</div>
        <label className="fld" style={{ margin: 0 }}><span>{tr("De")}</span><select value={nova.start_hour} onChange={x => setNova({ ...nova, start_hour: x.target.value })}>
          {Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{hora(h)}</option>)}</select></label>
        <label className="fld" style={{ margin: 0 }}><span>{tr("Até")}</span><select value={nova.end_hour} onChange={x => setNova({ ...nova, end_hour: x.target.value })}>
          {Array.from({ length: 24 }, (_, h) => <option key={h + 1} value={h + 1}>{h + 1 === 24 ? tr("meia-noite") : hora(h + 1)}</option>)}</select></label>
        <label className="fld" style={{ margin: 0 }}><span>{tr("US$ por hora")} <i>{tr("vazio = ligar")}</i></span>
          <input inputMode="decimal" value={nova.price} placeholder={tr("ligar")} onChange={x => setNova({ ...nova, price: x.target.value })} /></label>
        <button className="btn primary" disabled={!nova.days} onClick={criarFaixa}>{tr("Adicionar faixa")}</button>
      </div>}
      <p className="small muted" style={{ margin: '10px 0 0' }}>{tr("A hora abre para um formato quando uma faixa ativa cobre aquele dia e horário; a primeira da lista vale. Preço vazio mostra \"Call us\" no site e não vende online. Mudar o preço vale para as próximas reservas: quem já pagou fica com o valor do dia.")}</p>
    </Section>

    <Section title={tr("Etiqueta do dia: piloto ou diversão")} count={d.etiquetas.filter(t => t.active).length}>
      <p className="small muted" style={{ marginTop: 0 }}>{tr("O selo que aparece no dia do calendário do site e no topo do dia escolhido (ex.: 🏁 Pilot day, 🎮 Fun night). Por dia da semana ou por data; sem horário, vale o dia inteiro. A data vem antes do dia da semana.")}</p>
      {!d.etiquetas.length ? <Empty title={tr("Nenhuma etiqueta: o calendário sai sem selo")} /> : <div className="tbl">{d.etiquetas.map(t => {
        const f = etq[t.id] || doBanco(t)
        return <div className="tr" key={t.id} data-etiqueta={t.id} style={{ flexWrap: 'wrap', gap: 8, alignItems: 'flex-end', opacity: t.active ? 1 : .6 }}>
          <CamposEtiqueta f={f} gerente={gerente} rotulo={tr("Dias da etiqueta")} muda={x => setEtq(e => ({ ...e, [t.id]: { ...f, ...x } }))} />
          {!t.active && <Chip tone="neutral">{tr("desativada")}</Chip>}
          {gerente && <><button className="btn sm primary" disabled={!etq[t.id]} onClick={() => salvarEtiqueta(t)}>{tr("Salvar")}</button>
            <button className="btn sm" onClick={() => salvarEtiqueta(t, { active: !t.active })}>{t.active ? tr("Desativar") : tr("Reativar")}</button></>}
        </div> })}</div>}
      {gerente && <div className="row gap wrap" data-etiqueta-nova style={{ alignItems: 'flex-end', marginTop: 12 }}>
        <CamposEtiqueta f={novaEtq} gerente={gerente} rotulo={tr("Dias da etiqueta nova")} muda={x => setNovaEtq({ ...novaEtq, ...x })} />
        <button className="btn primary" disabled={!novaEtq.label.trim() || (novaEtq.modo === 'semana' ? !novaEtq.days : !novaEtq.date)} onClick={criarEtiqueta}>{tr("Adicionar etiqueta")}</button>
      </div>}
    </Section>

    <Section title={tr("Reservas do simulador")} count={total}>
      {!d.reservas.itens.length ? <Empty title={tr("Nenhuma reserva daqui para a frente")} /> : <div className="tbl">{d.reservas.itens.map(r =>
        <div className="tr" key={r.id} style={{ flexWrap: 'wrap', gap: 8 }}>
          <b>{dbr(r.date)} · {hora(r.start_hour)}–{hora(r.start_hour + r.hours)}</b>
          <span className="grow">{r.service_name} · {r.pilot_name || r.account_name || '—'}{r.account_email ? <span className="small muted"> · {r.account_email}</span> : null}</span>
          <span>{usd(r.price)}</span>
          <Chip tone={r.status === 'paga' ? 'ok' : 'warn'}>{r.status === 'paga' ? tr("paga") : tr("no pagamento")}</Chip>
          {r.raffle ? <Chip tone="info">{tr("sorteio")}</Chip> : null}
          {r.waiver_error ? <Chip tone="crit" title={r.waiver_error}>{tr("waiver com erro")}</Chip> : r.waiver_ref ? <Chip tone="ok">{tr("waiver enviada")}</Chip> : null}
          {r.client_id ? <Link className="btn sm ghost" to={`/clients/${r.client_id}`}>{tr("Card {0}", r.client_name || r.client_id)}</Link> : <Chip tone="warn">{tr("sem card")}</Chip>}
        </div>)}</div>}
      {paginas > 1 && <div className="row gap" style={{ marginTop: 10 }}>
        <button className="btn sm" disabled={pagina === 0} onClick={() => setPagina(pagina - 1)}>{tr("Anterior")}</button>
        <span className="small muted">{tr("Página {0} de {1}", pagina + 1, paginas)}</span>
        <button className="btn sm" disabled={pagina + 1 >= paginas} onClick={() => setPagina(pagina + 1)}>{tr("Próxima")}</button></div>}
    </Section>
  </div>
}
