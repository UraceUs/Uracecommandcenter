/* O contador do plano mensal, para o cliente (#340). Dono, 19/10: "precisa mostrar tanto para nos quanto para
 * eles a quantidade de sessões que eles tem pagas ou em aberto". Muda a decisão de 01/10 (o contador era só da
 * equipe). Por piloto: as sessões do pacote usadas e livres do mês (zera no dia 1), a mensalidade do mês pelo
 * QuickBooks (paga, aberta com o link para pagar, ou ainda sem invoice), as extras do mês com a invoice delas e o
 * que está em aberto (sessões já feitas sem invoice paga). Tudo vem do servidor (`GET /plan` → `counter`). */
import { usd, type PlanoPiloto, type SituacaoInvoice } from './api'
import { linhaDoMes } from './linhaDoMes'

const curta = (iso: string) => new Date(iso + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
const mesLongo = (m: string) => new Date(m + '-15T12:00:00').toLocaleDateString('en-US', { month: 'long', year: 'numeric' })

/** "Paid", "Open", "Invoice on its way" — a mesma palavra em todas as linhas. */
export function SituacaoChip({ s }: { s: SituacaoInvoice }) {
  const [rot, tom] = s === 'paid' ? ['Paid', 'ok'] : s === 'open' ? ['Open', 'warn'] : ['Invoice on its way', 'neutral']
  return <span className={`chip ${tom}`}>{rot}</span>
}

/** O cartão de um piloto. `nivel`: o título do cartão (h2 quando é a seção da tela, h3 dentro de uma seção). */
export function ContadorDoPlano({ plano, nome, nivel = 3 }: { plano: PlanoPiloto; nome?: string; nivel?: 2 | 3 }) {
  const k = plano.counter
  if (!k) return null
  const H = nivel === 2 ? 'h2' : 'h3'
  const m = k.monthly_invoice
  return <article className="card card-b stack portal-contador" style={{ gap: 8 }} aria-label={`Monthly plan${nome ? ` of ${nome}` : ''}`}>
    <H className={nivel === 2 ? 'h2' : 'h3'} style={{ margin: 0 }}>{nome ? `${nome} · ` : ''}{plano.plan || 'Monthly plan'}</H>
    <p style={{ margin: 0 }}><b>{linhaDoMes(k)}</b></p>
    <div className="portal-contador-barra" role="img" aria-label={`${k.used} of ${k.sessions_per_month} sessions used`}>
      <span style={{ transform: `scaleX(${Math.min(1, k.sessions_per_month ? k.used / k.sessions_per_month : 0)})` }} /></div>
    <dl className="portal-contador-dl">
      <dt>Monthly invoice ({mesLongo(k.month)})</dt>
      <dd>{!m ? <span className="muted">—</span> : <span className="row wrap" style={{ gap: 6 }}>
        <SituacaoChip s={m.status} />{m.doc && <span className="small muted">Invoice {m.doc}</span>}
        {m.status === 'open' && (m.link ? <a className="btn sm" href={m.link} target="_blank" rel="noopener noreferrer">Pay now</a>
          : <span className="small muted">It is in your email from QuickBooks.</span>)}</span>}</dd>
      <dt>Extra sessions this month</dt>
      <dd>{!k.extras.length ? <span className="muted">None</span> : <ul className="portal-contador-extras">
        {k.extras.map(e => <li key={`${e.date}${e.period}`} className="row wrap" style={{ gap: 6 }}>
          <span>{curta(e.date)}{e.price != null ? ` · ${usd(e.price)}` : ''}</span><SituacaoChip s={e.status} />
          {e.status === 'open' && e.link && <a className="btn sm" href={e.link} target="_blank" rel="noopener noreferrer">Pay now</a>}</li>)}</ul>}</dd>
      <dt>Open</dt>
      <dd>{!k.open.count ? <span>Nothing open</span> : <span>
        {k.open.count} session{k.open.count === 1 ? '' : 's'} done and not paid yet
        {k.open.amount != null ? ` · ${usd(k.open.amount)}` : ''}
        {k.open.not_invoiced ? <span className="small muted"> · {k.open.not_invoiced} not invoiced yet</span> : null}</span>}</dd>
    </dl>
  </article>
}

/** O pro com a mensalidade ainda não configurada no card: aviso, sem preço e sem carrinho (#340). */
export function PlanoEmMontagem() {
  return <div className="banner info" role="status"><span className="bi" aria-hidden="true">●</span><div className="grow">
    Your monthly plan is being set up by our team. You can still request sessions: our team confirms them and bills them by
    QuickBooks invoice with your plan. Nothing is charged online.</div></div>
}
