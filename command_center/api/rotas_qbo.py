"""Rotas do QuickBooks e do detalhe do Asana (#436: saíram do rotas.py, sem mudar rota):
invoices, lembretes de cobrança, resumo do QBO; detalhe da tarefa, do espelho do Asana (#455).
"""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from command_center.api import auth
from command_center.api.cache_api import paginar
from command_center.api.rotas import BASE, _links
from command_center.db import auditar, get_db, todos, um
from command_center.providers import NaoConectado, chamar, espelho_asana

r = APIRouter(prefix=BASE)


# ================================================================ Asana: o espelho da tarefa (#455)
@r.get("/tasks/{tid}/detail")
def task_detail(tid: int, atualizar: bool = False, u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    """Descrição, campos, subtarefas, anexos e comentários da tarefa — do espelho do Asana (#455), que a sincronia
    mantém igual ao Asana. `atualizar=1` ("Atualizar do Asana") relê na hora; a tarefa nunca espelhada também.
    Com o Asana fora, o espelho continua aparecendo, com o aviso."""
    t = um(con, "SELECT id, mirrored_at FROM tasks WHERE id=?", (tid,))
    if not t:
        raise HTTPException(404, "Task not found.")
    gid = espelho_asana.gid_da_tarefa(con, tid)
    if not gid:
        return {"connected": False, "reason": "tarefa sem vínculo com o Asana"}
    aviso = None
    if atualizar or not t["mirrored_at"]:
        try:
            espelho_asana.espelhar(con, tid, gid)
            con.commit()
        except NaoConectado as e:
            if not t["mirrored_at"]:
                return {"connected": False, "reason": str(e)}
            aviso = f"Asana fora agora ({str(e)[:120]}): mostrando o espelho"
        except Exception as e:
            if not t["mirrored_at"]:
                raise HTTPException(502, f"Asana: {str(e)[:300]}")
            aviso = f"Asana não respondeu ({str(e)[:120]}): mostrando o espelho"
    saida = espelho_asana.detalhe(con, tid, BASE)
    saida["espelho"]["aviso"] = aviso
    return saida


@r.get("/tasks/{tid}/anexos/{agid}")
def task_anexo(tid: int, agid: str, u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    """#455: abre o anexo do espelho. O link de download do Asana expira, então ele é pedido na hora."""
    if not um(con, "SELECT 1 AS x FROM task_attachments WHERE task_id=? AND gid=?", (tid, agid)):
        raise HTTPException(404, "Anexo não encontrado nesta tarefa.")
    try:
        link = chamar("asana", "anexo_link", gid=agid).get("download")
    except NaoConectado as e:
        raise HTTPException(503, f"Asana não conectado: {e}")
    except Exception as e:
        raise HTTPException(502, f"Asana: {str(e)[:300]}")
    if not link or not str(link).startswith("https://"):
        raise HTTPException(404, "O Asana não deu link para este anexo.")
    return RedirectResponse(link, status_code=302, headers={"Cache-Control": "no-store"})


# ============================================================ QuickBooks (financeiro: MANAGER+)
@r.get("/invoices")
def invoices(response: Response, status: str = None, limit: int | None = None, offset: int = 0,
             u=Depends(auth.exige("MANAGER")), con: sqlite3.Connection = Depends(get_db)):
    from command_center.api import lembretes
    sql = f"SELECT i.*, c.name AS client_name, c.pilot_name, {lembretes.CAMPOS_NA_INVOICE} FROM invoices i LEFT JOIN clients c ON c.id=i.client_id"
    p = []
    if status:
        sql += " WHERE i.status=?"; p.append(status)
    rows = paginar(con, sql + " ORDER BY CASE i.status WHEN 'overdue' THEN 0 WHEN 'open' THEN 1 WHEN 'sent' THEN 1 ELSE 2 END, i.due_on DESC, i.id DESC",
                   p, response, limit=limit, offset=offset, padrao=500)
    for i in rows:
        i["links"] = _links(con, "invoice", i["id"])
    return rows


class LembreteIn(BaseModel):
    invoice_ids: list[int]
    cadence: str = "weekly"
    every_days: int | None = None
    enabled: bool = True


class LembretePatch(BaseModel):
    enabled: bool | None = None
    cadence: str | None = None
    every_days: int | None = None


@r.get("/invoice-reminders")
def reminders_list(client_id: int | None = None, u=Depends(auth.exige("MANAGER")), con: sqlite3.Connection = Depends(get_db)):
    from command_center.api import lembretes
    return lembretes.listar(con, client_id)


@r.put("/invoice-reminders")
def reminders_set(dados: LembreteIn, request: Request, u=Depends(auth.exige("MANAGER")), con: sqlite3.Connection = Depends(get_db)):
    """Liga (ou reconfigura) o lembrete das invoices escolhidas. Quem liga é a aprovação humana (dono, 16/09)."""
    from command_center.api import lembretes
    if not dados.invoice_ids:
        raise HTTPException(400, "Escolha ao menos uma invoice.")
    try:
        saida = lembretes.configurar(con, u["id"], dados.invoice_ids[:100], dados.cadence, dados.every_days, dados.enabled)
    except ValueError as e:
        raise HTTPException(400, str(e))
    con.commit()
    return {"ok": True, "reminders": saida}


@r.patch("/invoice-reminders/{rid}")
def reminder_patch(rid: int, dados: LembretePatch, u=Depends(auth.exige("MANAGER")), con: sqlite3.Connection = Depends(get_db)):
    from command_center.api import lembretes
    try:
        r_ = lembretes.alternar(con, u["id"], rid, dados.enabled, dados.cadence, dados.every_days)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not r_:
        raise HTTPException(404, "Lembrete não encontrado.")
    con.commit()
    return r_


@r.post("/invoice-reminders/send-now")
def reminders_send_now(dados: LembreteIn, request: Request, u=Depends(auth.exige("MANAGER")), con: sqlite3.Connection = Depends(get_db)):
    """Manda o lembrete agora para as invoices escolhidas (sem esperar as 09:00). Auditado por invoice."""
    from command_center.api import lembretes
    if not dados.invoice_ids:
        raise HTTPException(400, "Escolha ao menos uma invoice.")
    saida = []
    for iid in dados.invoice_ids[:50]:
        r_ = um(con, "SELECT * FROM invoice_reminders WHERE invoice_id=?", (iid,))
        if not r_:                                        # sem lembrete configurado: manda uma vez, sem criar recorrência
            inv = um(con, "SELECT id FROM invoices WHERE id=?", (iid,))
            if not inv:
                continue
            r_ = {"id": None, "invoice_id": iid, "every_days": 0}
        res = lembretes.enviar(con, r_, por=u["id"]) if r_["id"] else _enviar_uma_vez(con, u["id"], iid)
        saida.append({"invoice_id": iid, **res})
    con.commit()
    return {"ok": True, "enviados": sum(1 for s in saida if s.get("ok")), "detalhe": saida}


def _enviar_uma_vez(con, user_id, iid):
    from command_center.api import lembretes
    from command_center.providers import NaoConectado, chamar
    inv = um(con, "SELECT * FROM invoices WHERE id=?", (iid,))
    ext = lembretes._qbo_id(con, iid)
    if not ext:
        return {"ok": False, "motivo": "invoice sem vínculo com o QuickBooks"}
    if inv["status"] not in lembretes.ABERTAS or not (inv["balance"] or 0) > 0:
        return {"ok": False, "motivo": "invoice já paga"}
    try:
        res = chamar("quickbooks", "qbo_enviar_invoice", id=ext)
    except NaoConectado as e:
        return {"ok": False, "motivo": f"QuickBooks não conectado: {e}"}
    except Exception as e:
        return {"ok": False, "motivo": f"{type(e).__name__}: {str(e)[:200]}"}
    aplicado = bool(res.get("aplicado"))
    auditar(con, "invoice.reminder.sent" if aplicado else "invoice.reminder.simulated", f"user:{user_id}", user_id=user_id, entity_type="invoice", entity_id=iid,
            detail={"doc_number": inv["doc_number"], "balance": inv["balance"], "para": res.get("enviado_para") or inv["customer_email"], "unico": True})
    if aplicado:                       # dono, 21/09: a tarefa do cliente fica sabendo, com a hora
        from command_center.api import rastro
        rastro.invoice_enviada(con, inv, para=res.get("enviado_para") or inv["customer_email"], lembrete=True)
    return {"ok": True, "aplicado": aplicado, "para": res.get("enviado_para"), "doc_number": inv["doc_number"]}


@r.get("/qbo/summary")
def qbo_summary(u=Depends(auth.exige("MANAGER")), con: sqlite3.Connection = Depends(get_db)):
    from datetime import date as _d
    hoje = _d.today().isoformat()
    n = lambda sql, p=(): (um(con, sql, p) or {})
    aberto = n("SELECT COUNT(*) AS c, COALESCE(SUM(balance),0) AS t FROM invoices WHERE status IN ('open','sent','overdue')")
    vencido = n("SELECT COUNT(*) AS c, COALESCE(SUM(balance),0) AS t FROM invoices WHERE status='overdue'")
    pagas30 = n("SELECT COUNT(*) AS c, COALESCE(SUM(amount),0) AS t FROM invoices WHERE status='paid' AND issued_on >= date(?, '-30 days')", (hoje,))
    integ = um(con, "SELECT status, detail, last_success_at FROM integrations WHERE system='quickbooks'")
    return {"connected": bool(integ and integ["status"] == "CONNECTED"), "integration": integ,
            "open": {"count": aberto["c"], "total": round(aberto["t"], 2)}, "overdue": {"count": vencido["c"], "total": round(vencido["t"], 2)},
            "paid_30d": {"count": pagas30["c"], "total": round(pagas30["t"], 2)},
            "top_debtors": todos(con, """SELECT c.id, c.name, c.pilot_name, SUM(i.balance) AS balance, COUNT(*) AS n FROM invoices i JOIN clients c ON c.id=i.client_id
                                         WHERE i.status IN ('open','sent','overdue') GROUP BY c.id ORDER BY balance DESC LIMIT 8""")}
