"""Rotas do DocuSign (#436: saíram do rotas.py, sem mudar rota): modelos, waivers
(baixar, prova, lixeira, anular, reenviar, vincular), waiver por card e convite.
"""
import os
import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel, Field

from command_center.api import auth
from command_center.api.rotas import BASE
from command_center.api.rotas_ia import MAX_BYTES
from command_center.db import agora, auditar, get_db, um
from command_center.providers import NaoConectado, modulo

r = APIRouter(prefix=BASE)


@r.get("/docusign/templates")
def docusign_templates(u=Depends(auth.usuario_atual)):
    """Modelos da conta DocuSign, ao vivo. Sem credencial devolve connected=false, nunca 500."""
    from command_center.providers import NaoConectado, chamar
    try:
        return {"connected": True, "templates": chamar("docusign", "docusign_templates")}
    except NaoConectado as e:
        return {"connected": False, "reason": str(e), "templates": []}
    except Exception as e:
        return {"connected": False, "reason": f"{type(e).__name__}: {str(e)[:200]}", "templates": []}


from fastapi import File as _File, UploadFile as _UploadFile  # noqa: E402

RX_TEMPLATE = re.compile(r"^[0-9a-fA-F-]{36}$")
RX_DOCID = re.compile(r"^\d{1,6}$")
TEMPLATES_DIR = os.path.join(os.environ.get("URACE_DIR", os.path.expanduser("~/.urace")), "docusign-templates")


def _ids_do_modelo(tid, did=None):
    if not RX_TEMPLATE.match(tid or "") or (did is not None and not RX_DOCID.match(did or "")):
        raise HTTPException(400, "Identificador de modelo/documento inválido.")


@r.get("/docusign/templates/{tid}")
def docusign_template(tid: str, u=Depends(auth.usuario_atual)):
    """Um modelo por inteiro (dono, 16/09): documentos, papéis e campos. Só leitura."""
    _ids_do_modelo(tid)
    from command_center.providers import NaoConectado, modulo
    try:
        return {"connected": True, **modulo("docusign").modelo_humano(tid)}
    except NaoConectado as e:
        return {"connected": False, "reason": str(e)}
    except Exception as e:
        raise HTTPException(502, f"DocuSign: {str(e)[:300]}")


@r.get("/docusign/templates/{tid}/documents/{did}")
def docusign_template_pdf(tid: str, did: str, u=Depends(auth.usuario_atual)):
    """O PDF do modelo como está hoje, aberto no navegador."""
    _ids_do_modelo(tid, did)
    from fastapi.responses import Response
    from command_center.providers import NaoConectado, modulo
    try:
        pdf = modulo("docusign").baixar_documento_do_modelo_humano(tid, did)
    except NaoConectado as e:
        raise HTTPException(503, f"DocuSign não conectado: {e}")
    except Exception as e:
        raise HTTPException(502, str(e)[:300])
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="modelo-{tid[:8]}-{did}.pdf"', "Cache-Control": "no-store"})


class RenomearModeloIn(BaseModel):
    name: str


@r.patch("/docusign/templates/{tid}")
def docusign_template_rename(tid: str, dados: RenomearModeloIn, request: Request, u=Depends(auth.exige("MANAGER")),
                             con: sqlite3.Connection = Depends(get_db)):
    """Renomeia o modelo no DocuSign. MANAGER; auditado com o nome antigo."""
    _ids_do_modelo(tid)
    nome = (dados.name or "").strip()
    if not (2 <= len(nome) <= 120):
        raise HTTPException(400, "Nome do modelo: entre 2 e 120 caracteres.")
    from command_center.providers import NaoConectado, modulo
    try:
        g = modulo("docusign")
        antes = g.modelo_humano(tid).get("nome")
        g.renomear_modelo_humano(tid, nome)
    except NaoConectado as e:
        raise HTTPException(503, f"DocuSign não conectado: {e}")
    except Exception as e:
        raise HTTPException(502, str(e)[:300])
    auditar(con, "docusign.template.renamed", f"user:{u['id']}", user_id=u["id"], entity_type="docusign_template", entity_id=tid,
            detail={"antes": antes, "depois": nome}, ip=auth._ip(request))
    con.commit()
    return {"ok": True, "name": nome, "antes": antes}


@r.post("/docusign/templates/{tid}/documents/{did}")
async def docusign_template_replace(tid: str, did: str, request: Request, file: _UploadFile = _File(...),
                                    u=Depends(auth.exige("MANAGER")), con: sqlite3.Connection = Depends(get_db)):
    """Troca o PDF de um documento do modelo (dono, 16/09). Antes de trocar, guarda o PDF
    atual em ~/.urace/docusign-templates — troca de modelo de contrato não pode ser sem volta.
    O documentId é mantido, então os campos de assinatura continuam no documento."""
    _ids_do_modelo(tid, did)
    dados = await file.read()
    if not dados:
        raise HTTPException(400, "Arquivo vazio.")
    if len(dados) > MAX_BYTES:
        raise HTTPException(413, "Arquivo maior que 25 MB.")
    if not dados.startswith(b"%PDF") or os.path.splitext(file.filename or "")[1].lower() != ".pdf":
        raise HTTPException(400, "Só PDF.")
    from command_center.providers import NaoConectado, modulo
    try:
        g = modulo("docusign")
        existe = any(str(d.get("documentId")) == did for d in (g.modelo_humano(tid).get("documentos") or []))
        backup = None
        if existe:                                            # modelo vazio (sem PDF) não tem o que guardar
            antigo = g.baixar_documento_do_modelo_humano(tid, did)
            os.makedirs(TEMPLATES_DIR, mode=0o700, exist_ok=True)
            backup = os.path.join(TEMPLATES_DIR, f"{tid}-{did}-{agora()[:19].replace(':', '')}.pdf")
            with open(backup, "wb") as f:
                f.write(antigo)
            os.chmod(backup, 0o600)
        g.substituir_documento_do_modelo_humano(tid, did, file.filename, dados)
    except NaoConectado as e:
        raise HTTPException(503, f"DocuSign não conectado: {e}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, str(e)[:300])
    auditar(con, "docusign.template.document_replaced", f"user:{u['id']}", user_id=u["id"], entity_type="docusign_template", entity_id=tid,
            detail={"documentId": did, "arquivo": file.filename, "bytes": len(dados), "backup": backup, "novo": not existe}, ip=auth._ip(request))
    con.commit()
    return {"ok": True, "backup": os.path.basename(backup) if backup else None, "novo": not existe}


# ============================================================= DocuSign
def _envelope_id(con, wid):
    l = um(con, "SELECT external_id FROM entity_links WHERE entity_type='waiver' AND entity_id=? AND system='docusign'", (wid,))
    return l["external_id"] if l else None


@r.get("/waivers/{wid}/download")
def waiver_download(request: Request, wid: int = Path(..., ge=1, le=2**63 - 1), u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    """PDF assinado (documento + certificado). Baixa do DocuSign na primeira vez e guarda
    em ~/.urace/waivers: depois o card do cliente abre o arquivo guardado, e é o mesmo
    arquivo que vai anexado na tarefa do Asana."""
    from fastapi.responses import Response
    from command_center.api import motor
    w = um(con, "SELECT * FROM waivers WHERE id=?", (wid,))
    if not w:
        raise HTTPException(404, "Waiver not found.")
    nome = re.sub(r"[^A-Za-z0-9._-]+", "_", f"waiver-{w['signer_name'] or w['signer_email'] or wid}")[:80]
    if w["source"] == "urace":                      # #85: assinada aqui — o PDF já está guardado
        if not w["pdf_path"] or not os.path.isfile(w["pdf_path"]):
            raise HTTPException(410, "O PDF desta waiver não está mais no servidor.")
        with open(w["pdf_path"], "rb") as f:
            pdf = f.read()
        auditar(con, "waiver.download", f"user:{u['id']}", user_id=u["id"], entity_type="waiver", entity_id=wid,
                detail={"origem": "urace", "sha256": w["doc_sha256"]}, ip=auth._ip(request))
        from command_center.providers import trilha_waiver as tw          # #111: depois de assinar, na trilha
        tw.registrar(con, "downloaded", "staff", ip=auth._ip(request), user_agent=request.headers.get("user-agent"),
                     detail={"by": u.get("name"), "user_id": u["id"]}, waiver_id=wid, client_id=w["client_id"],
                     pilot_id=w["pilot_id"], kind=w["template"])
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{nome}.pdf"', "Cache-Control": "no-store"})
    env = _envelope_id(con, wid)
    if not env:
        raise HTTPException(409, "Envelope sem vínculo com o DocuSign.")
    try:
        try:
            with open(motor.pdf_da_waiver(con, w), "rb") as f:
                pdf = f.read()
        except OSError:                                  # sem lugar para guardar: pega ao vivo
            pdf = modulo("docusign").baixar_documento_humano(env)
    except NaoConectado as ex:
        raise HTTPException(503, f"DocuSign não conectado: {ex}")
    except Exception as ex:
        raise HTTPException(502, str(ex)[:300])
    auditar(con, "waiver.download", f"user:{u['id']}", user_id=u["id"], entity_type="waiver", entity_id=wid,
            detail={"envelope": env}, ip=auth._ip(request))
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{nome}.pdf"', "Cache-Control": "no-store"})


@r.get("/waivers/{wid}/evidence.zip")
def waiver_pacote_de_prova(request: Request, wid: int = Path(..., ge=1, le=2**63 - 1), u=Depends(auth.exige("MANAGER")),
                           con: sqlite3.Connection = Depends(get_db)):
    """#115: o pacote de prova (ZIP) da waiver assinada no próprio sistema, para o advogado e o tribunal — gerente ou
    acima. O PDF assinado, a trilha, os eventos com a cadeia de hashes, o audit_logs, o modelo, o carimbo, os
    certificados públicos, o certificado avulso, a descrição do sistema, a declaração (rascunho) e o SHA256SUMS. A
    exportação fica na trilha (`evidence_exported`) e na auditoria (`waiver.evidence_export`), com o hash do ZIP."""
    from fastapi.responses import Response as Resposta
    from command_center.providers import prova_waiver
    try:
        z, info = prova_waiver.exportar(con, wid, u, ip=auth._ip(request), user_agent=request.headers.get("user-agent"))
    except LookupError:
        raise HTTPException(404, "Waiver not found.")
    except (prova_waiver.NaoExporta, prova_waiver.SemArquivo) as e:
        raise HTTPException(409, str(e))
    return Resposta(content=z, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="URACE-waiver-{wid}-evidence.zip"',
                             "Cache-Control": "no-store", "X-Content-SHA256": info["sha256"],
                             "X-Evidence-Integrity": "ok" if info["integrity_ok"] else "problems"})


class LixeiraIn(BaseModel):
    reason: str | None = None


@r.post("/waivers/{wid}/trash")
def waiver_trash(wid: int, dados: LixeiraIn, request: Request, u=Depends(auth.exige("OPERATOR")),
                 con: sqlite3.Connection = Depends(get_db)):
    """Lixeira: some do painel (restaurável) e, se o envelope está em aberto, é ANULADO no DocuSign.
    Envelope assinado é registro legal: só some do painel."""
    w = um(con, "SELECT * FROM waivers WHERE id=?", (wid,))
    if not w:
        raise HTTPException(404, "Waiver not found.")
    # #118 (dono, 06/10: "nunca apagar"): a assinada aqui não tem cópia no DocuSign — este é o registro legal
    if w["source"] == "urace" and w["status"] == "completed":
        raise HTTPException(409, "Waiver assinada na área do cliente é registro legal e não vai para a lixeira.")
    env = _envelope_id(con, wid)
    anulado = None
    if env and w["status"] in ("sent", "delivered", "autoresponded"):
        try:
            anulado = modulo("docusign").anular_humano(env, dados.reason or f"Anulado no Command Center por {u['name']}")
        except NaoConectado as ex:
            raise HTTPException(503, f"DocuSign não conectado: {ex}")
        except Exception as ex:
            raise HTTPException(502, str(ex)[:300])
    con.execute("UPDATE waivers SET hidden=1, status=CASE WHEN ? THEN 'voided' ELSE status END, synced_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
                (1 if anulado and anulado.get("aplicado") else 0, wid))
    auditar(con, "waiver.trash", f"user:{u['id']}", user_id=u["id"], entity_type="waiver", entity_id=wid,
            detail={"envelope": env, "reason": dados.reason, "voided": bool(anulado and anulado.get("aplicado")), "status_antes": w["status"]}, ip=auth._ip(request))
    return {"ok": True, "hidden": True, "voided": bool(anulado and anulado.get("aplicado")),
            "note": "Assinada fica no DocuSign (registro legal); só saiu do painel." if w["status"] == "completed" else None}


@r.post("/waivers/{wid}/restore")
def waiver_restore(wid: int, request: Request, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    if not um(con, "SELECT id FROM waivers WHERE id=? AND hidden=1", (wid,)):
        raise HTTPException(404, "Nothing hidden with that id.")
    con.execute("UPDATE waivers SET hidden=0 WHERE id=?", (wid,))
    auditar(con, "waiver.restore", f"user:{u['id']}", user_id=u["id"], entity_type="waiver", entity_id=wid, ip=auth._ip(request))
    return {"ok": True}


class AnularIn(BaseModel):
    reason: str


@r.post("/waivers/{wid}/void")
def waiver_void(wid: int, dados: AnularIn, request: Request, u=Depends(auth.exige("MANAGER")),
                con: sqlite3.Connection = Depends(get_db)):
    """#109: anular com motivo a waiver assinada no próprio sistema — gerente ou acima. Ela não vai para a
    lixeira nem muda: a anulação fica em `waiver_voids` e na auditoria, e a waiver continua no card e no backup."""
    from command_center.providers import waiver_nativa as wn
    try:
        v = wn.anular(con, wid, u, dados.reason, ip=auth._ip(request))
    except LookupError:
        raise HTTPException(404, "Waiver not found.")
    except wn.ErroWaiver as e:
        raise HTTPException(400, str(e))
    except wn.NaoAnula as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "voided_at": v["at"], "voided_by": v["by_name"], "reason": v["reason"]}


@r.post("/waivers/{wid}/copy")
def waiver_copia(request: Request, wid: int = Path(..., ge=1, le=2**63 - 1), u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    """#114: reenviar a cópia da waiver assinada no próprio sistema. Vai sempre ao e-mail que assinou (`signer_email`);
    a tela mostra esse e-mail antes do clique. O message-id (ou a falha) fica na trilha da waiver."""
    from command_center.providers import copia_waiver
    try:
        res = copia_waiver.mandar(con, wid, "staff", por=u.get("name"), user_id=u["id"], ip=auth._ip(request),
                                  user_agent=request.headers.get("user-agent"))
    except LookupError:
        raise HTTPException(404, "Só a waiver assinada no próprio sistema tem cópia por e-mail aqui.")
    except copia_waiver.NaoEnvia as e:
        raise HTTPException(409, str(e))
    except copia_waiver.Cedo as e:
        raise HTTPException(429, str(e))
    if not res["ok"]:
        raise HTTPException(503, f"A cópia não saiu ({res['error']}). Ficou registrado na trilha; tente de novo.")
    return {"ok": True, "sent_to": res["sent_to"], "message_id": res["message_id"], "at": res["at"]}


class ReenviarIn(BaseModel):
    email: str | None = None
    name: str | None = None


@r.post("/waivers/{wid}/resend")
def waiver_resend(wid: int, dados: ReenviarIn, request: Request, u=Depends(auth.exige("OPERATOR")),
                  con: sqlite3.Connection = Depends(get_db)):
    """Reenvia a notificação; com e-mail novo, corrige o signatário antes (e-mail devolvido)."""
    w = um(con, "SELECT * FROM waivers WHERE id=?", (wid,))
    if not w:
        raise HTTPException(404, "Waiver not found.")
    if w["source"] == "urace":
        raise HTTPException(409, "Assinada na área do cliente: não há envelope para reenviar.")
    novo = (dados.email or "").strip().lower() or None
    if novo and ("@" not in novo or "." not in novo.split("@")[-1]):
        raise HTTPException(400, "E-mail inválido.")
    env = _envelope_id(con, wid)
    if not env:
        raise HTTPException(409, "Envelope sem vínculo com o DocuSign.")
    try:
        res = modulo("docusign").reenviar_humano(env, novo, dados.name)
    except NaoConectado as ex:
        raise HTTPException(503, f"DocuSign não conectado: {ex}")
    except Exception as ex:
        raise HTTPException(502, str(ex)[:300])
    if novo:
        con.execute("UPDATE waivers SET signer_email=?, status='sent', synced_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?", (novo, wid))
    auditar(con, "waiver.resend", f"user:{u['id']}", user_id=u["id"], entity_type="waiver", entity_id=wid,
            detail={"envelope": env, "new_email": novo}, ip=auth._ip(request))
    return {"ok": True, **res}


class VinculoIn(BaseModel):
    client_id: int | None = None   # null = desvincular


@r.post("/waivers/{wid}/link")
def waiver_link(wid: int, dados: VinculoIn, request: Request, u=Depends(auth.exige("OPERATOR")),
                con: sqlite3.Connection = Depends(get_db)):
    """Vínculo manual waiver ↔ cliente. A sincronia não sobrescreve vínculo humano."""
    if not um(con, "SELECT id FROM waivers WHERE id=?", (wid,)):
        raise HTTPException(404, "Waiver not found.")
    if dados.client_id is not None and not um(con, "SELECT id FROM clients WHERE id=?", (dados.client_id,)):
        raise HTTPException(404, "Client not found.")
    con.execute("UPDATE waivers SET client_id=?, link_by='human', link_reason=? WHERE id=?",
                (dados.client_id, f"vinculado à mão por {u['name']}" if dados.client_id else "desvinculado à mão", wid))
    auditar(con, "waiver.link", f"user:{u['id']}", user_id=u["id"], entity_type="waiver", entity_id=wid,
            detail={"client_id": dados.client_id}, ip=auth._ip(request))
    return {"ok": True}


# ------------------------------------------------------- waiver por card: DocuSign ou nativa (#348)
class FluxoWaiverIn(BaseModel):
    flow: str = Field(..., pattern="^(padrao|docusign|nativa)$")


@r.get("/clients/{cid}/waiver-flow")
def fluxo_waiver_do_card(cid: int, u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    from command_center.providers import waiver_nativa as wn
    if not um(con, "SELECT id FROM clients WHERE id=?", (cid,)):
        raise HTTPException(404, "Client not found.")
    return wn.fluxo_do_card(con, cid)


@r.put("/clients/{cid}/waiver-flow")
def fluxo_waiver_mudar(cid: int, dados: FluxoWaiverIn, request: Request, u=Depends(auth.exige("MANAGER")),
                       con: sqlite3.Connection = Depends(get_db)):
    """Dono, 19/10: o switch do card. Só decide a PRÓXIMA waiver: a já assinada (de qualquer fluxo) continua valendo."""
    from command_center.providers import waiver_nativa as wn
    if not um(con, "SELECT id FROM clients WHERE id=?", (cid,)):
        raise HTTPException(404, "Client not found.")
    antes = wn.fluxo_escolhido(con, cid)
    try:
        wn.escolher_fluxo(con, cid, dados.flow)
    except ValueError as e:
        raise HTTPException(409, str(e))
    if antes != dados.flow:
        auditar(con, "client.waiver_flow", f"user:{u['id']}", user_id=u["id"], entity_type="client", entity_id=cid,
                detail={"antes": antes, "depois": dados.flow, "por": u["name"]}, ip=auth._ip(request))
    con.commit()
    return wn.fluxo_do_card(con, cid)


# ------------------------------------------------------- convite da waiver por e-mail (#135)
class ConviteWaiverIn(BaseModel):
    email: str          # o e-mail que a pessoa viu na confirmação: se o card mudou no meio, não manda


@r.get("/clients/{cid}/waiver-invite")
def convite_waiver_do_card(cid: int, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    """Para quem o convite iria (nome, e-mail, adulto ou menor) ou por que não sai, e os convites já mandados."""
    from command_center.providers import convite_waiver as cw
    try:
        d = cw.destino(con, cid)
    except LookupError:
        raise HTTPException(404, "Client not found.")
    return {"destino": d, "convites": cw.listar(con, cid)}


@r.post("/clients/{cid}/waiver-invite", status_code=201)
def convite_waiver_enviar(cid: int, dados: ConviteWaiverIn, request: Request, u=Depends(auth.exige("OPERATOR")),
                          con: sqlite3.Connection = Depends(get_db)):
    """Manda (ou reenvia) o convite para o e-mail do card. O clique da pessoa, depois da confirmação, é a autorização."""
    from command_center.providers import convite_waiver as cw
    try:
        inv = cw.enviar(con, cid, f"user:{u['id']}", user_id=u["id"], email_confirmado=dados.email, ip=auth._ip(request))
    except LookupError:
        raise HTTPException(404, "Client not found.")
    except cw.Cedo as e:
        raise HTTPException(429, str(e))
    except cw.EnvioFalhou as e:
        raise HTTPException(503, str(e))
    except cw.ErroConvite as e:
        raise HTTPException(409, str(e))
    return {"convite": inv, "convites": cw.listar(con, cid)}
