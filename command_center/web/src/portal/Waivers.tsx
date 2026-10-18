/* Todas as waivers da conta (#114; lacuna E-2 do P-15). Carregada só nesta rota.
 *
 * ESIGN §7001(e): o registro tem de poder ser guardado e reproduzido por quem assinou. Aqui ficam todas as waivers
 * assinadas no próprio sistema pelos pilotos da conta, vigentes, vencidas e anuladas, das mais novas para as mais
 * velhas, cada uma com o PDF assinado e a última cópia por e-mail. "Email me a copy" manda de novo, sempre para o
 * e-mail que assinou. Só o que existe: sem waiver, a lista diz que não há. */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { papi, PortalError, type WaiverDaConta } from './api'
import { dataUS } from './datas'

const POR_PAGINA = 10
const SITUACAO: Record<WaiverDaConta['status'], [string, string]> = { valid: ['Valid', 'ok'], expired: ['Expired', 'neutral'], voided: ['Voided by URACE', 'crit'] }

function Copia({ c }: { c: WaiverDaConta['copy'] }) {
  if (!c) return null
  return c.status === 'sent'
    ? <div className="small muted">Copy emailed to {c.to} on {dataUS(c.at)}</div>
    : <div className="small">The emailed copy could not be sent ({dataUS(c.at)}). Download it here, or ask for it again.</div>
}

export function MinhasWaivers() {
  const [offset, setOffset] = useState(0)
  const [d, setD] = useState<{ items: WaiverDaConta[]; total: number } | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const [indo, setIndo] = useState<number | null>(null)
  const carregar = (o: number) => papi<{ items: WaiverDaConta[]; total: number }>('GET', `/waivers/history?limit=${POR_PAGINA}&offset=${o}`)
    .then(setD).catch(e => setErro((e as PortalError).message))
  useEffect(() => { carregar(offset) }, [offset])
  async function mandar(w: WaiverDaConta) {
    setErro(null); setAviso(null); setIndo(w.id)
    try {
      const r = await papi<{ sent_to: string }>('POST', `/waivers/${w.id}/email`)
      setAviso(`We emailed a copy of the waiver for ${w.driver} to ${r.sent_to}.`)
      await carregar(offset)
    } catch (e) { setErro((e as PortalError).message) } finally { setIndo(null) }
  }
  return <div className="stack" style={{ gap: 18 }}>
    <div><h1 className="h1">Waivers</h1>
      <p className="muted" style={{ margin: '4px 0 0' }}>Every waiver signed for your drivers, valid or not. Download any of them, or have a copy emailed
        to the address that signed it.</p></div>
    {erro && <div className="banner crit" role="alert"><span className="bi" aria-hidden="true">✕</span><div className="grow">{erro}</div></div>}
    {aviso && <div className="banner ok" role="status"><span className="bi" aria-hidden="true">✓</span><div className="grow">{aviso}</div></div>}
    {!d ? (!erro && <div className="state"><span className="spin" /></div>)
      : !d.items.length ? <p className="muted small" style={{ margin: 0 }}>No waivers signed here yet. <Link to="/portal/drivers">Go to Drivers</Link> to sign one.</p>
      : <ul className="stack portal-waivers" style={{ gap: 10 }}>{d.items.map(w => {
        const [rot, tom] = SITUACAO[w.status]
        return <li key={w.id} className="card card-b stack portal-waiver-item" style={{ gap: 6 }}>
          <div className="row wrap" style={{ gap: 8 }}><h2 className="h3 grow" style={{ margin: 0 }}>{w.driver}</h2><span className={`chip ${tom}`}>{rot}</span></div>
          <div className="small">{w.document}</div>
          <div className="small muted">Signed {dataUS(w.signed_at)} by {w.signer_name} · {w.status === 'voided' && w.voided_at
            ? <>voided {dataUS(w.voided_at)}</> : <>{w.status === 'expired' ? 'expired' : 'valid until'} {dataUS(w.valid_until)}</>}</div>
          <Copia c={w.copy} />
          <div className="row wrap" style={{ gap: 8, marginTop: 4 }}>
            <a className="btn sm" href={w.pdf}>Download PDF</a>
            {w.status !== 'voided' && <button type="button" className="btn sm ghost" disabled={indo !== null} onClick={() => mandar(w)}>
              {indo === w.id ? 'Sending…' : 'Email me a copy'}</button>}
          </div>
        </li>
      })}</ul>}
    {d && d.total > POR_PAGINA && <div className="row" style={{ gap: 8 }}>
      <button type="button" className="btn sm ghost" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - POR_PAGINA))}>Newer</button>
      <span className="small muted grow" style={{ textAlign: 'center' }}>{offset + 1}–{Math.min(offset + POR_PAGINA, d.total)} of {d.total}</span>
      <button type="button" className="btn sm ghost" disabled={offset + POR_PAGINA >= d.total} onClick={() => setOffset(offset + POR_PAGINA)}>Older</button></div>}
  </div>
}
