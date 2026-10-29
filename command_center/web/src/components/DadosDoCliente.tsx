/* #460 (dono, 29/10): "antes de linha do tempo, coloca dados do cliente ... as medidas, nome responsável, idade,
 * waiver, um linkzinho só para abrir a outra seção de waiver, e-mail, número, parentesco, classe ... data de
 * nascimento, um dashboardzinho". Os dados pessoais num quadro só, antes da linha do tempo. */
import { Link } from 'react-router-dom'
import type { Client, PecasDoDia, TimelineEvent, Waiver } from '../api/types'
import { WAIVER_LABEL } from './uiConst'
import { fmtDate, money } from './fmt'
import { tr } from '../i18n'
import { CORPO, TAMANHOS, idade } from './medidas'

/** "59 in · 150 cm" e "88 lb · 40 kg": a medida como foi dada (polegadas/libras) e o métrico ao lado. */
function medida(v: number | string | undefined, un: string) {
  if (v === undefined || v === '') return '—'
  const n = Number(v)
  if (!isFinite(n)) return String(v)
  return un === 'lb' ? `${n} lb · ${Math.round(n * 0.4536)} kg` : `${n} in · ${Math.round(n * 2.54)} cm`
}

export function DadosDoCliente({ c, irmaos, waiver, waiverAberta, onWaivers, onEditar, onConvite }: {
  c: Client; irmaos?: { id: number; name: string; pilot_name: string | null }[]
  waiver: Waiver | undefined; waiverAberta: Waiver | undefined; onWaivers: () => void; onEditar?: () => void; onConvite?: () => void
}) {
  const d = c.dados
  const anos = idade(c.pilot_dob)
  const m = d?.medidas || {}
  const temMedida = CORPO.some(([k]) => m[k] !== undefined) || TAMANHOS.some(([k]) => m[k] !== undefined)
  const fonte = (d?.medidas_fonte || []).map(f => f.de === 'site' ? tr("preenchido pelo cliente no site em {0}", fmtDate(f.em)) : tr("conferido pela equipe em {0}", fmtDate(f.em))).join(' · ')
  const w = waiver || waiverAberta
  return <section className="card cd-dados" aria-labelledby="dados-t">
    <div className="card-h"><h2 className="h2" id="dados-t">{tr("Dados do cliente")}</h2><span className="grow" />{onEditar && <button className="btn sm" onClick={onEditar}>{tr("Editar dados")}</button>}</div>
    <div className="card-b">
      <div className="cd-tiles">
        <div className="cd-tile"><span className="k">{tr("Piloto")}</span><b>{c.pilot_name || c.name}</b>
          {!!irmaos?.length && <span className="small">{tr("irmão(s):")} {irmaos.map((i, n) => <span key={i.id}>{n ? ', ' : ''}<Link to={`/clients/${i.id}`}>{i.pilot_name || i.name}</Link></span>)}</span>}</div>
        <div className="cd-tile"><span className="k">{tr("Nascimento")}</span><b className="mono">{fmtDate(c.pilot_dob) || '—'}</b>
          {anos !== null && <span className={`small${anos < 18 ? ' warn' : ''}`}>{anos < 18 ? tr("{0} anos · menor", anos) : tr("{0} anos", anos)}</span>}</div>
        <div className="cd-tile"><span className="k">{tr("Classe")}</span><b>{d?.classe || '—'}</b>
          {d?.classe_de === 'chassi' && <span className="small muted">{tr("pelo chassi")}</span>}</div>
        <div className="cd-tile"><span className="k">{tr("Waiver")}</span>
          <b className={c.vip || (waiver && !waiver.voided_at) ? 'ok' : w ? 'warn' : 'crit'}>{c.vip ? tr("dispensada (VIP)") : waiver ? tr("assinada") : w ? WAIVER_LABEL[w.status || ''] || w.status : tr("nenhuma")}</b>
          <span className="small">{waiver?.expires_at ? <>{tr("vale até {0}", fmtDate(waiver.expires_at))} · </> : null}<button type="button" className="linkish" onClick={onWaivers}>{tr("ver waivers")}</button></span>
          {!waiver && !c.vip && onConvite && <button className="btn ghost sm" onClick={onConvite} title={tr("Mandar ao e-mail do card o convite para assinar a waiver")}>{tr("✉ Convite por e-mail")}</button>}</div>
        <div className="cd-tile"><span className="k">{tr("Responsável")}</span><b>{c.name}</b>
          <span className="small muted">{d?.parentesco ? tr("parentesco: {0}", d.parentesco) : tr("parentesco: —")}{d?.parentesco_de === 'waiver' ? ` ${tr("(da waiver)")}` : ''}</span></div>
        <div className="cd-tile"><span className="k">{tr("E-mail")}</span>{c.email ? <a href={`mailto:${c.email}`} className="quebra">{c.email}</a> : <span className="muted">—</span>}
          {c.email_alt && <a href={`mailto:${c.email_alt}`} className="small quebra">{c.email_alt}</a>}</div>
        <div className="cd-tile"><span className="k">{tr("Telefone")}</span>{c.phone ? <a href={`tel:${c.phone}`}>{c.phone}</a> : <span className="muted">—</span>}</div>
        <div className="cd-tile"><span className="k">{tr("Client ID")}</span><b className="mono">{c.id}</b><span className="small muted">{tr("desde {0}", fmtDate(c.created_at))}</span></div>
      </div>
      <div className="cd-medidas">
        <div><h3 className="h3">{tr("Tamanhos")}</h3>
          <div className="cd-tam">{TAMANHOS.map(([k, rot]) => <div key={k} className="cd-tile"><span className="k">{rot}</span><b>{m[k] ?? '—'}</b></div>)}</div></div>
        <div><h3 className="h3">{tr("Medidas")}</h3>
          <dl className="cd-dl">{CORPO.map(([k, rot, un]) => <div key={k}><dt>{rot}</dt><dd>{medida(m[k], un)}</dd></div>)}</dl>
          <p className="small muted" style={{ margin: '6px 0 0' }}>{temMedida ? fonte : tr("Sem medidas ainda: o cliente preenche na área do cliente, ou a equipe em Editar dados.")}</p></div>
      </div>
    </div>
  </section>
}


/** #460: na linha do tempo, a visita (o serviço do dia): o que o espelho do Asana sabe dele, o último comentário,
 * as peças do balcão daquele dia e os atalhos para o card do serviço no Command Center. */
export function VisitaServico({ tid, s, pecas, fin, abrir, onAnotar }: {
  tid: number; s?: TimelineEvent['servico']; pecas?: PecasDoDia[]; fin: boolean; abrir: boolean; onAnotar?: (tid: number) => void
}) {
  const uc = s?.ultimo_comentario
  return <div className="vis">
    {s && <div className="small muted">{tr("{0} de {1} subtarefas", s.subtarefas[0], s.subtarefas[1])}
      {s.checklists && <> · {tr("checklist do box {0} de {1}", s.checklists[0], s.checklists[1])}</>}
      {s.comentarios > 0 && <> · {s.comentarios === 1 ? tr("1 comentário") : tr("{0} comentários", s.comentarios)}</>}</div>}
    {uc && <div className="bloco"><div className="k">{fmtDate(uc.quando)} · {uc.quem || tr("Asana")}</div><div className="small" style={{ whiteSpace: 'pre-wrap' }}>{uc.texto}</div></div>}
    {!!pecas?.length && <div className="bloco"><div className="k">{tr("Peças do dia")}</div>
      {pecas.map(p => <div key={p.id} className="small">{p.itens.map(i => `${i.nome} ×${i.qtd}`).join(' · ') || '—'}
        {fin && p.total !== null && <span className="muted"> · {money(p.total)}</span>} <span className="muted">· {p.status}</span></div>)}</div>}
    <div className="acoes">
      {abrir && <Link className="btn sm" to={`/servicos/${tid}`}>{tr("Abrir o serviço")}</Link>}
      {onAnotar && <button type="button" className="btn ghost sm" onClick={() => onAnotar(tid)}>{tr("Anotar neste serviço")}</button>}
    </div>
  </div>
}
