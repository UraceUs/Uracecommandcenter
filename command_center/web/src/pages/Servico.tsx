/* #460 — o card do serviço dentro do Command Center (dono, 29/10: "ir para o card do serviço do cliente dentro do
 * Command Center ... ver mais pelo Command Center do que pelo Asana. E as informações que estiverem no Asana serão as
 * mesmas que estarão no Command Center, sempre"). Lê o espelho do Asana (#455); comentar e concluir subtarefa
 * escrevem no Asana e o espelho relê na hora. */
import { Fragment, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { useGet } from '../api/hooks'
import type { ServicoCard, TaskDetail } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { Banner, Dots, Empty, ErrorState, Loading, Section, Status } from '../components/ui'
import { WAIVER_LABEL } from '../components/uiConst'
import { fmtDate, fmtDateTime, money } from '../components/fmt'
import { idade } from '../components/medidas'
import { TextoComVoz } from '../components/Voz'
import { useToast } from '../components/useToast'
import { useDescricao } from '../titulo'
import { tr } from '../i18n'

const TAM: Record<string, string> = { suit_size: tr("Macacão"), helmet_size: tr("Capacete"), glove_size: tr("Luva"), shoe_size: tr("Sapato") }

export function Servico() {
  const { id } = useParams()
  const tid = Number(id)
  const nav = useNavigate()
  const { can } = useAuth()
  const toast = useToast()
  useDescricao(tr("O serviço do cliente como está no Asana: descrição, subtarefas, comentários, anexos, peças e checklist."))
  const { data, error, loading, reload } = useGet<ServicoCard>(tid ? `/tasks/${tid}/servico` : null)
  const [det, setDet] = useState<TaskDetail | null>(null)          // a resposta da escrita/releitura é a que vale
  const [ocupado, setOcupado] = useState<string | null>(null)
  const [texto, setTexto] = useState('')
  if (error && !data) return <ErrorState error={error} retry={reload} />
  if (loading && !data) return <Loading rows={8} />
  if (!data) return null
  const t = data.tarefa
  const d = det ?? data.servico
  const subs = d.task?.subtarefas_lista || []
  const cl = data.cliente
  const anos = idade(cl?.nascimento)

  async function agir(chave: string, fazer: () => Promise<TaskDetail>, ok: string) {
    setOcupado(chave)
    try { setDet(await fazer()); toast(ok, 'ok') }
    catch (e) { toast((e as ApiError).message, 'crit') } finally { setOcupado(null) }
  }
  const atualizar = () => agir('asana', () => api.get<TaskDetail>(`/tasks/${tid}/detail?atualizar=1`), tr("Relido do Asana."))
  const comentar = () => agir('comentar', async () => { const r = await api.post<TaskDetail>(`/tasks/${tid}/comentar`, { texto: texto.trim() }); setTexto(''); return r },
    tr("Comentário gravado no Asana."))
  const concluir = (gid: string) => agir(gid, () => api.post<TaskDetail>(`/tasks/${tid}/subtarefas/${gid}/concluir`), tr("Subtarefa concluída no Asana."))

  return <>
    <div className="c360-h">
      <div className="who">
        <div className="small"><a href="#" onClick={e => { e.preventDefault(); nav(-1) }}>{tr("← Voltar")}</a>
          {cl && <> · <Link to={`/clients/${cl.id}`}>{tr("card de {0}", cl.piloto || cl.nome)}</Link></>}</div>
        <div className="row wrap" style={{ gap: 10 }}><h1 className="h1" style={{ fontSize: 28 }}>{t.titulo}</h1><Status s={t.excluida ? 'deleted' : t.status} /></div>
        <div className="meta">
          <span><span className="k">{tr("data")}</span> <b className="mono">{fmtDate(t.data) || '—'}</b></span>
          <span><span className="k">{tr("coluna")}</span> {t.secao || '—'}</span>
          <span><span className="k">{tr("responsável")}</span> {t.responsavel || '—'}</span>
          <span><span className="k">{tr("subtarefas")}</span> <Dots done={subs.filter(s => s.concluida).length} total={subs.length} /></span>
        </div>
      </div>
      <div className="c360-acts">
        {d.connected && <button className="btn" disabled={!!ocupado} onClick={atualizar}>{ocupado === 'asana' ? <span className="spin" /> : tr("↻ Atualizar do Asana")}</button>}
        {d.task?.link && <a className="btn ghost" href={d.task.link} target="_blank" rel="noopener noreferrer">{tr("Asana ↗")}</a>}
      </div>
    </div>
    {!d.connected && <Banner tone="warn">{tr("Sem espelho do Asana:")} {String(d.reason || '').replace(/[.\s]+$/, '')}.</Banner>}
    {d.espelho?.aviso && <Banner tone="warn">{d.espelho.aviso}</Banner>}
    {d.espelho?.em && <p className="small muted">{tr("Espelho do Asana · atualizado {0}", fmtDateTime(d.espelho.em))}</p>}
    <div className="svc-g">
      <div className="svc-main">
        <Section title={tr("Descrição")}>{d.task?.notas ? <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'var(--font)', margin: 0, fontSize: 13.5 }}>{d.task.notas}</pre> : <span className="muted small">{tr("sem descrição")}</span>}</Section>
        <Section title={tr("Subtarefas")} count={subs.length} tight>{subs.length === 0 ? <Empty>{tr("Nenhuma.")}</Empty> : <div>{subs.map(s => <div key={s.gid} className="att">
          <div className={`lv ${s.concluida ? 'LOW' : 'MEDIUM'}`} />
          <div className="grow" style={{ textDecoration: s.concluida ? 'line-through' : undefined, color: s.concluida ? 'var(--muted)' : undefined }}>{s.concluida ? '✓ ' : '○ '}{s.nome}{s.vence_em && <span className="small muted mono"> · {fmtDate(s.vence_em)}</span>}</div>
          {!s.concluida && can('OPERATOR') && !t.excluida && <button className="btn ghost sm" style={{ minHeight: 40 }} disabled={!!ocupado} onClick={() => concluir(s.gid)}>{ocupado === s.gid ? <span className="spin" /> : tr("Concluir")}</button>}
        </div>)}</div>}</Section>
        <Section title={tr("Comentários")} count={d.comments?.length} tight>
          {!d.comments?.length ? <Empty>{tr("Nenhum comentário.")}</Empty> : <div>{d.comments.map((c, i) => <div key={i} className="att"><div className="lv LOW" /><div className="grow"><div className="small muted"><b>{c.quem || '?'}</b> · {fmtDateTime(c.quando)}</div><div style={{ whiteSpace: 'pre-wrap' }}>{c.texto}</div></div></div>)}</div>}
          {can('OPERATOR') && d.connected && !t.excluida && <div className="card-b">
            <label className="small muted" htmlFor="svc-com">{tr("Anotar neste serviço (vai como comentário no Asana, com o seu nome)")}</label>
            <TextoComVoz id="svc-com" valor={texto} onChange={setTexto} linhas={3} placeholder={tr("Dá para ditar")} />
            <div className="row" style={{ justifyContent: 'flex-end', marginTop: 8 }}><button className="btn primary" disabled={!texto.trim() || !!ocupado} onClick={comentar}>{ocupado === 'comentar' ? <span className="spin" /> : tr("Anotar")}</button></div>
          </div>}
        </Section>
        <Section title={tr("Anexos")} count={d.attachments?.length} tight>{!d.attachments?.length ? <Empty>{tr("Nenhum.")}</Empty> : <div>{d.attachments.map(a => <div key={a.gid} className="att"><div className="lv LOW" /><div className="grow">{a.download ? <a href={a.download} target="_blank" rel="noopener noreferrer">{a.nome} ↗</a> : a.nome}<div className="small muted">{a.origem} · {fmtDateTime(a.quando)}</div></div></div>)}</div>}</Section>
      </div>
      <div className="svc-side">
        <Section title={tr("Cliente")}>{!cl ? <span className="muted small">{tr("Serviço sem cliente vinculado.")}</span> : <dl className="dl">
          <dt>{tr("Piloto")}</dt><dd><Link to={`/clients/${cl.id}`}>{cl.piloto || cl.nome}</Link></dd>
          {cl.piloto && cl.piloto !== cl.nome && <><dt>{tr("Responsável")}</dt><dd>{cl.nome}</dd></>}
          <dt>{tr("Idade")}</dt><dd>{anos ?? '—'}</dd>
          <dt>{tr("Classe")}</dt><dd>{cl.classe || '—'}</dd>
          <dt>{tr("Waiver")}</dt><dd>{cl.vip ? tr("dispensada (VIP)") : cl.waiver ? <>{WAIVER_LABEL[cl.waiver.status] || cl.waiver.status}{cl.waiver.expires_at && <span className="small muted"> · {tr("vale até {0}", fmtDate(cl.waiver.expires_at))}</span>}</> : tr("nenhuma")}</dd>
          {Object.entries(cl.tamanhos).map(([k, v]) => <Fragment key={k}><dt>{TAM[k] || k}</dt><dd>{v}</dd></Fragment>)}
        </dl>}</Section>
        <Section title={tr("Peças do dia")} count={data.pecas_do_dia.length} tight>{!data.pecas_do_dia.length ? <Empty>{tr("Nenhuma peça no balcão neste dia.")}</Empty> : <div>{data.pecas_do_dia.map(p => <div key={p.id} className="att"><div className="lv LOW" /><div className="grow">
          {p.itens.map(i => `${i.nome} ×${i.qtd}`).join(' · ') || '—'}<div className="small muted">{p.doc ? `#${p.doc} · ` : ''}{p.status}{p.total !== null && <> · {money(p.total)}</>}</div></div></div>)}</div>}</Section>
        <Section title={tr("Checklist do box")} count={data.checklists.length} tight>{!data.checklists.length ? <Empty>{tr("Nenhum checklist neste serviço.")}</Empty> : <div>{data.checklists.map(k => <div key={k.id} className="att"><div className={`lv ${k.status === 'completo' ? 'LOW' : 'MEDIUM'}`} /><div className="grow">
          <Link to={`/checklists/${k.id}`}>{k.title}</Link><div className="small muted">{tr("{0} de {1} itens", k.feitos, k.total)}</div></div></div>)}</div>}</Section>
        {!!d.task?.campos && Object.keys(d.task.campos).length > 0 && <Section title={tr("Campos do Asana")}><dl className="dl">{Object.entries(d.task.campos).map(([k, v]) => <Fragment key={k}><dt>{k}</dt><dd>{v}</dd></Fragment>)}</dl></Section>}
      </div>
    </div>
  </>
}
