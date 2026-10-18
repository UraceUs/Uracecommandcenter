"""Cópia da waiver assinada por e-mail ao signatário (#114; lacuna E-1 do P-15).

ESIGN §7001(e) pede que o registro seja "capable of being retained and accurately reproduced… by all involved
parties". Baixar logo depois de assinar cumpre só em parte, e quem assina pelo convite perde o link em 72 h. O
e-mail dá uma cópia fora do nosso controle e a prova de entrega.

- **Para quem**: sempre o `signer_email` da linha da waiver, o e-mail que assinou (a conta confirmada por código,
  ou o do convite). Nunca o e-mail do card de agora, nunca outro endereço: a waiver é imutável (#109) e quem pede
  o reenvio (o cliente ou a equipe) não escolhe o destino.
- **De onde**: `noreply@` (dono, 06/10: código e cópia saem do noreply@), com Reply-To `support@`: a resposta cai
  numa caixa que alguém lê.
- **O anexo** é o PDF assinado, conferido com o `doc_sha256` antes de sair. Se o arquivo no disco não bate com o
  hash, não sai nada e fica o evento de falha.
- **O que fica**: o evento `copy_emailed` na trilha (#111), com o message-id do Gmail, a hora, o destino (mascarado)
  e o hash e o tamanho do anexo; ou `copy_email_failed`, com o motivo. A cópia completa do destino vai para a
  auditoria (`waiver.copy.*`). Nada disto toca a linha da waiver nem `waivers.audit`, que são imutáveis.
- **Depois de assinar, em segundo plano**: o e-mail que não sai não desfaz a assinatura.
- **Reenvio**: o cliente ("Email me a copy", na área do cliente) e a equipe ("Reenviar cópia", no card e em
  Site › Waiver), com intervalo e teto. A anulada não se reenvia: a cópia dela já saiu e o PDF continua para baixar.
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

from command_center.db import auditar, um, waiver_anulada

log = logging.getLogger("cc.waiver.copia")

RESPONDER_PARA = "support@urace.us"
INTERVALO_MIN = {"signer": 10, "staff": 1}      # entre duas cópias da mesma waiver
POR_DIA = {"signer": 3, "staff": 10}            # pedidos de reenvio por waiver nas últimas 24 h
EVENTOS = ("copy_emailed", "copy_email_failed")


class NaoEnvia(Exception):
    """Esta waiver não tem cópia para mandar (anulada, sem PDF ou com o PDF que não confere). A rota devolve 409."""


class Cedo(Exception):
    """Uma cópia acabou de sair, ou já saíram muitas hoje. A rota devolve 429."""


def _iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _mascarar(email):
    from command_center.providers import codigos
    return codigos.mascarar(email)


def _quando(iso):
    from command_center.providers import portal
    t = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(portal.FUSO)
    return t.strftime("%b %-d, %Y at %-I:%M %p")


def _dia(iso):
    from datetime import date
    return date.fromisoformat(iso[:10]).strftime("%b %-d, %Y")


def nome_do_arquivo(w):
    return f"URACE-waiver-{w['id']}.pdf"


def email(w, t):
    """(assunto, texto, html) da cópia. Inglês: é o que o cliente lê."""
    from command_center import enderecos
    from command_center.providers import email_marca
    piloto = t.get("driver_name") or w.get("minor_name") or "the driver"
    primeiro = (w.get("signer_name") or "").split()[0] if w.get("signer_name") else "there"
    assunto = f"Your signed URACE waiver for {piloto}"
    quando = _quando(w["completed_at"])
    ate = _dia(w["expires_at"])
    conta = bool(t.get("account_id"))
    intro = (f"Attached is your signed copy of the {t.get('template_name') or 'URACE waiver'} for {piloto}, "
             f"signed on {quando} (Orlando time). It is valid until {ate}.")
    guardar = "Keep this email: it is your copy of the signed document."
    onde = (f"You can also download it any time in your URACE account: {enderecos.cliente()}/ops/portal/waivers"
            if conta else "Questions about it? Just reply to this email.")
    prova = [("Signature ID", t.get("signature_id") or "—"), ("SHA-256 of the attached PDF", w["doc_sha256"])]
    texto = (f"Hi {primeiro},\n\n{intro}\n\n{guardar}\n{onde}\n\n" + "\n".join(f"{k}: {v}" for k, v in prova)
             + "\n\nIf you did not sign this waiver, reply to this email and tell us.\n\nURACE.US · Orlando, FL")
    html = email_marca.html(f"Hi {primeiro}!", [intro, guardar], prova,
                            ("Open my waivers", f"{enderecos.cliente()}/ops/portal/waivers") if conta else None,
                            ["If you did not sign this waiver, reply to this email and tell us."])
    return assunto, texto, html


def _ids(w, t):
    """Os campos de escopo da trilha para um evento depois de assinar."""
    return dict(waiver_id=w["id"], client_id=w["client_id"], pilot_id=w["pilot_id"], kind=w["template"],
                signature_id=t.get("signature_id"), account_id=t.get("account_id"), invite_id=t.get("invitation_id"))


def ultima(con, wid):
    """A última tentativa de cópia (evento), ou None."""
    e = um(con, f"SELECT * FROM waiver_events WHERE waiver_id=? AND event IN ({','.join('?' * len(EVENTOS))}) "
                "ORDER BY id DESC LIMIT 1", (wid, *EVENTOS))
    if not e:
        return None
    d = json.loads(e["detail"] or "{}")
    return {"status": "sent" if e["event"] == "copy_emailed" else "failed", "at": e["at"], "to": d.get("to"),
            "message_id": d.get("message_id"), "by": d.get("by")}


def _limite(con, wid, quem):
    agora_utc = datetime.now(timezone.utc)
    ult = um(con, f"SELECT at FROM waiver_events WHERE waiver_id=? AND event IN ({','.join('?' * len(EVENTOS))}) "
                  "ORDER BY id DESC LIMIT 1", (wid, *EVENTOS))
    if ult and ult["at"] > _iso(agora_utc - timedelta(minutes=INTERVALO_MIN[quem])):
        raise Cedo("We just emailed a copy. Check your inbox (and the spam folder) before asking again."
                   if quem == "signer" else "Uma cópia acabou de sair. Espere um minuto antes de reenviar.")
    n = um(con, f"""SELECT COUNT(*) AS n FROM waiver_events WHERE waiver_id=? AND event IN ({','.join('?' * len(EVENTOS))})
                    AND at >= ? AND json_extract(detail, '$.requested_by') = ?""",
           (wid, *EVENTOS, _iso(agora_utc - timedelta(hours=24)), quem))["n"]
    if n >= POR_DIA[quem]:
        raise Cedo("You already asked for this copy several times today. Try again tomorrow."
                   if quem == "signer" else "Já saíram muitas cópias desta waiver hoje. Tente amanhã.")


def mandar(con, wid, quem="auto", fluxo=None, por=None, user_id=None, ip=None, user_agent=None, enviar_email=None):
    """Manda a cópia da waiver `wid` ao signatário. `quem`: auto (logo depois de assinar), signer (o cliente pediu)
    ou staff (a equipe reenviou; `por` é o nome de quem). Devolve {ok, sent_to, message_id, at} ou {ok: False, error}.
    `LookupError`: não é waiver nativa assinada. `NaoEnvia`: anulada ou sem PDF. `Cedo`: intervalo ou teto."""
    from command_center.providers import email_envio, trilha_waiver as tw
    w = um(con, "SELECT * FROM waivers WHERE id=? AND source='urace' AND status='completed'", (wid,))
    if not w:
        raise LookupError("waiver")
    if um(con, f"SELECT 1 AS x FROM waivers WHERE id=? AND {waiver_anulada()}", (wid,)):
        raise NaoEnvia("This waiver was voided by URACE: its copy is not emailed again. You can still download it."
                       if quem == "signer" else "Waiver anulada: a cópia não se reenvia (o PDF continua para baixar).")
    if quem in INTERVALO_MIN:
        _limite(con, wid, quem)
    t = json.loads(w["audit"] or "{}")
    fluxo = fluxo or ("staff" if quem == "staff" else "invite" if t.get("invitation_id") else "account")
    ids = _ids(w, t)
    para = w["signer_email"]
    base = {"to": _mascarar(para), "requested_by": quem, **({"by": por, "user_id": user_id} if quem == "staff" else {})}

    def falhou(motivo, erro):
        tw.registrar(con, "copy_email_failed", fluxo, ip=ip, user_agent=user_agent, detail={**base, "reason": motivo, "error": erro},
                     **ids)
        auditar(con, "waiver.copy.failed", f"user:{user_id}" if user_id else f"waiver:{wid}", user_id=user_id, entity_type="waiver",
                entity_id=wid, detail={"to": para, "requested_by": quem, "reason": motivo, "error": erro}, ip=ip)
        log.warning(json.dumps({"log": "cc.waiver.copia", "waiver": wid, "ok": False, "reason": motivo}))
        return {"ok": False, "sent_to": base["to"], "error": erro}

    try:
        with open(w["pdf_path"] or "", "rb") as f:
            pdf = f.read()
    except OSError:
        return falhou("pdf_missing", "the signed PDF is not on the server")
    sha = hashlib.sha256(pdf).hexdigest()
    if sha != w["doc_sha256"]:                           # o arquivo mudou no disco: não manda um documento que não é o assinado
        return falhou("pdf_changed", "the signed PDF on the server does not match its SHA-256")
    assunto, texto, html = email(w, t)
    try:
        mid = (enviar_email or email_envio.enviar)(para, assunto, texto, html=html,
                                                    anexos=[(nome_do_arquivo(w), pdf, "application/pdf")],
                                                    responder_para=RESPONDER_PARA)
    except email_envio.ErroEnvio as e:
        return falhou("gmail", str(e)[:160])
    if not mid:
        return falhou("gmail", "Gmail did not return a message id")
    ev = tw.registrar(con, "copy_emailed", fluxo, ip=ip, user_agent=user_agent, detail={
        **base, "message_id": mid, "from": email_envio.CAIXAS[email_envio.remetente()], "reply_to": RESPONDER_PARA,
        "attachment": nome_do_arquivo(w), "attachment_sha256": sha, "attachment_bytes": len(pdf)}, **ids)
    auditar(con, "waiver.copy.emailed", f"user:{user_id}" if user_id else f"waiver:{wid}", user_id=user_id, entity_type="waiver",
            entity_id=wid, detail={"to": para, "requested_by": quem, "message_id": mid, "sha256": sha}, ip=ip)
    log.info(json.dumps({"log": "cc.waiver.copia", "waiver": wid, "ok": True}))
    return {"ok": True, "sent_to": base["to"], "message_id": mid, "at": ev["at"]}


def em_segundo_plano(wid):
    """Logo depois de assinar, fora da resposta (BackgroundTasks): conexão própria, e nada que dê errado aqui
    desfaz a assinatura (a falha vira o evento `copy_email_failed`)."""
    from command_center.db import conectar
    con = conectar()
    try:
        mandar(con, wid, "auto")
    except Exception:                                    # noqa: BLE001 — a assinatura já está gravada
        log.exception("cópia da waiver %s não saiu", wid)
    finally:
        con.close()
