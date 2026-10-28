"""Rotas de dados da Fase 1, o geral: integrações e sincronia, dashboard, atenção, busca,
listas e políticas. Toda rota exige sessão; escrita exige papel.

#436: o resto foi dividido por assunto, cada um com o seu `r` no mesmo prefixo:
rotas_clientes.py, rotas_gmail.py, rotas_docusign.py, rotas_qbo.py e rotas_ia.py.
Daqui eles importam o comum (`BASE`, `_links`, a trava da sincronia).
"""
import sqlite3
import threading
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from command_center.api import atencao, auth, equipe, vendas
from command_center.api.cache_api import paginar
from command_center.db import agora, auditar, conectar, get_db, todos, um
from command_center.providers import identidade, sync as sy

BASE = "/ops/api"
r = APIRouter(prefix=BASE)


def _links(con, tipo, id_):
    return todos(con, "SELECT system, external_id, deep_link FROM entity_links WHERE entity_type=? AND entity_id=?", (tipo, id_))


# ------------------------------------------------------- integrações
@r.get("/integrations")
def integrations(u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    return todos(con, "SELECT * FROM integrations ORDER BY system")


@r.post("/integrations/check")
def integrations_check(request: Request, u=Depends(auth.exige("OPERATOR")),
                       con: sqlite3.Connection = Depends(get_db)):
    """Sonda cada sistema com UMA chamada real e grava o estado. A rotina
    automática só roda de manhã e à noite (agenda.py, decisão do dono 09/09)."""
    from command_center.api import agenda
    saida = agenda.sondar(con, por=f"user:{u['id']}")
    auditar(con, "integrations.check", f"user:{u['id']}", user_id=u["id"], ip=auth._ip(request))
    return saida


_SYNC = {"running": False, "started_at": None, "finished_at": None, "result": None, "by": None, "stage": None, "stage_started_at": None}
_SYNC_LOCK = threading.Lock()


def _sync_thread(user_id, ip):
    from command_center.api import motor
    con = conectar()
    try:
        res = {}
        # uma etapa por sistema, com o nome visível em GET /sync (a tela mostra "sincronizando: asana")
        for nome, fn in (("cerebro", sy.sync_cerebro), ("asana", sy.sync_asana), ("docusign", sy.sync_docusign),
                         ("gmail", sy.sync_gmail), ("gmail_compras", sy.sync_compras_email), ("quickbooks", sy.sync_qbo)):
            _SYNC["stage"] = nome; _SYNC["stage_started_at"] = agora()
            try:
                res[nome] = fn(con)
            except Exception as e:                    # um sistema com erro não derruba os outros
                res[nome] = {"ok": False, "motivo": f"{type(e).__name__}: {str(e)[:300]}"}
            if isinstance(res[nome], dict) and res[nome].get("ok") is False and nome != "cerebro":
                try:                                  # caiu no meio do uso: aí sim re-sonda (só ele)
                    from command_center.api import agenda
                    agenda.sondar_apos_falha(con, nome, str(res[nome].get("motivo") or ""))
                except Exception:
                    pass
        _SYNC["stage"] = "eventos"
        auditar(con, "sync.run", f"user:{user_id}", user_id=user_id, detail=res, ip=ip)
        res["eventos_disparados"] = motor.processar_eventos(con, user_id)
        _SYNC["result"] = res
    except Exception as e:                        # nunca deixa a flag presa em "running"
        _SYNC["result"] = {"ok": False, "motivo": f"{type(e).__name__}: {str(e)[:300]}"}
    finally:
        _SYNC["running"] = False
        _SYNC["finished_at"] = agora()
        _SYNC["stage"] = None
        con.close()


@r.post("/sync", status_code=202)
def sync(request: Request, wait: bool = False, u=Depends(auth.exige("OPERATOR")),
         con: sqlite3.Connection = Depends(get_db)):
    """Atualiza os espelhos a partir das fontes reais. Só leitura nos sistemas.

    Roda em segundo plano (o histórico do Asana pode levar minutos); o
    estado sai em GET /sync. wait=1 espera terminar (testes e scripts).
    """
    if wait:
        from command_center.api import motor
        res = sy.sync_tudo(con)
        auditar(con, "sync.run", f"user:{u['id']}", user_id=u["id"], detail=res, ip=auth._ip(request))
        res["eventos_disparados"] = motor.processar_eventos(con, u["id"])
        return res
    with _SYNC_LOCK:
        if _SYNC["running"]:
            return {"started": False, "running": True, "started_at": _SYNC["started_at"]}
        _SYNC.update(running=True, started_at=agora(), finished_at=None, result=None, by=u["id"])
    threading.Thread(target=_sync_thread, args=(u["id"], auth._ip(request)), daemon=True).start()
    return {"started": True, "running": True, "started_at": _SYNC["started_at"]}


@r.get("/sync")
def sync_status(u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    return {**_SYNC, "logs": todos(con, "SELECT * FROM sync_logs ORDER BY id DESC LIMIT 12")}


# --------------------------------------------------------- dashboard
@r.get("/dashboard")
def dashboard(u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    hoje = date.today().isoformat()
    n = lambda sql, p=(): (um(con, sql, p) or {}).get("n", 0)
    # fim do dia da Florida em UTC: é assim que next_at está gravado
    fim_do_dia = vendas.fim_do_dia_local()
    fin = auth.pode(u["role"], "MANAGER")   # financeiro: MANAGER+
    inv_abertas = todos(con, "SELECT amount, balance, due_on FROM invoices WHERE status IN ('sent','overdue')") if fin else []
    atencao_itens = atencao.coletar(con)
    return {
        "active_clients": n("SELECT COUNT(*) AS n FROM clients WHERE status='ACTIVE'"),
        "tasks_due_today": n("SELECT COUNT(*) AS n FROM tasks WHERE status='open' AND deleted_at IS NULL AND due_on=?", (hoje,)),
        "overdue_tasks": n("SELECT COUNT(*) AS n FROM tasks WHERE status='open' AND deleted_at IS NULL AND due_on<?", (hoje,)),
        "upcoming_7d": n("SELECT COUNT(*) AS n FROM tasks WHERE status='open' AND deleted_at IS NULL AND due_on BETWEEN ? AND ?",
                         (hoje, (date.today() + timedelta(days=7)).isoformat())),
        "waivers_open": n("SELECT COUNT(*) AS n FROM waivers WHERE status IN ('sent','delivered') AND COALESCE(internal,0)=0"),
        "waivers_bounced": n("SELECT COUNT(*) AS n FROM waivers WHERE status='autoresponded' AND COALESCE(internal,0)=0"),
        "emails_attention": n("SELECT COUNT(*) AS n FROM emails WHERE handled=0 AND client_id IS NOT NULL"),
        "crm_pending": n("SELECT COUNT(*) AS n FROM crm_leads WHERE needs_reply=1"),
        "sdr_relatos_abertos": n("SELECT COUNT(*) AS n FROM sdr_relatos WHERE status='aberto'"),   # Robô SDR (12/10)
        # chat da equipe: o que ESTA pessoa ainda não leu (o menu mostra o número dela,
        # não o da casa — contador que não é meu eu aprendo a ignorar em dois dias), já
        # sem o que ela silenciou
        "equipe_nao_lidas": equipe.total_nao_lidas(con, u["id"]),
        # vendas (17/09): retornos vencidos ou de hoje, de todo mundo
        "sales_due": n("""SELECT COUNT(*) AS n FROM opportunities
                          WHERE stage NOT IN ('GANHO','PERDIDO') AND next_at IS NOT NULL
                            AND next_at <= ?""", (fim_do_dia,)),
        "ai_actions_today": n("SELECT COUNT(*) AS n FROM ai_actions WHERE created_at >= ?", (hoje,)),
        "ai_pending_approval": n("SELECT COUNT(*) AS n FROM ai_actions WHERE status='PROPOSED' AND policy='REQUIRES_APPROVAL'"),
        "open_invoices": (None if not fin else {
            "count": len(inv_abertas), "total": round(sum(i["balance"] or 0 for i in inv_abertas), 2),
            "overdue": sum(1 for i in inv_abertas if (i["due_on"] or "9999") < hoje),
            "connected": (um(con, "SELECT status FROM integrations WHERE system='quickbooks'") or {}).get("status") == "CONNECTED"}),
        "integrations": todos(con, "SELECT system, status, last_success_at FROM integrations ORDER BY system"),
        "needs_attention": atencao_itens[:12],
        "needs_attention_total": len(atencao_itens),
        "last_sync": todos(con, "SELECT system, MAX(finished_at) AS at, ok, message FROM sync_logs GROUP BY system"),
    }


@r.get("/needs-attention")
def needs_attention(hidden: bool = False, u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    return atencao.coletar(con, incluir_ocultos=hidden)


class OcultarIn(BaseModel):
    key: str
    reason: str | None = None
    level: str | None = None
    title: str | None = None


@r.post("/needs-attention/dismiss")
def attention_dismiss(dados: OcultarIn, request: Request, u=Depends(auth.exige("OPERATOR")),
                      con: sqlite3.Connection = Depends(get_db)):
    """Esconde um aviso. Não toca na tarefa, no envelope nem no e-mail de origem."""
    if not dados.key or ":" not in dados.key or len(dados.key) > 200:
        raise HTTPException(400, "Invalid key.")
    con.execute("""INSERT INTO attention_dismissals (key, level, title, reason, dismissed_by)
                   VALUES (?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET reason=excluded.reason,
                   dismissed_by=excluded.dismissed_by, dismissed_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')""",
                (dados.key, dados.level, (dados.title or "")[:200], (dados.reason or "")[:500] or None, u["id"]))
    auditar(con, "attention.dismiss", f"user:{u['id']}", user_id=u["id"], entity_type="attention", entity_id=dados.key,
            detail={"title": dados.title, "reason": dados.reason}, ip=auth._ip(request))
    return {"ok": True}


class RestaurarIn(BaseModel):
    key: str


@r.post("/needs-attention/restore")
def attention_restore(dados: RestaurarIn, request: Request, u=Depends(auth.exige("OPERATOR")),
                      con: sqlite3.Connection = Depends(get_db)):
    n = con.execute("DELETE FROM attention_dismissals WHERE key=?", (dados.key,)).rowcount
    if not n:
        raise HTTPException(404, "Nothing hidden with that key.")
    auditar(con, "attention.restore", f"user:{u['id']}", user_id=u["id"], entity_type="attention", entity_id=dados.key,
            ip=auth._ip(request))
    return {"ok": True}


# -------------------------------------------------------------- busca
@r.get("/search")
def search(q: str, u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    q = (q or "").strip()
    if len(q) < 2 and not identidade.RX_CLIENT_ID.match(q):      # #430: o Client ID busca com 1 dígito
        return {"clients": [], "tasks": [], "waivers": [], "emails": [], "commands": []}
    like = f"%{q}%"
    f, pf, ordem, po = identidade.filtro_busca(q, "")
    out = {
        "clients": todos(con, f"SELECT id, name, pilot_name, email, status, vip FROM clients WHERE {f} ORDER BY {ordem}id LIMIT 8", (*pf, *po)),
        "tasks": todos(con, "SELECT id, title, due_on, section, status, client_id FROM tasks WHERE title LIKE ? LIMIT 8", (like,)),
        "waivers": todos(con, "SELECT id, signer_name, signer_email, status, expires_at, client_id FROM waivers WHERE signer_name LIKE ? OR signer_email LIKE ? LIMIT 8", (like, like)),
        "emails": todos(con, "SELECT id, subject, sender, mailbox, last_at, client_id FROM emails WHERE subject LIKE ? OR sender LIKE ? LIMIT 8", (like, like)),
        "commands": todos(con, "SELECT id, text, status, created_at FROM ai_commands WHERE text LIKE ? AND user_id=? ORDER BY id DESC LIMIT 5", (like, u["id"])),
    }
    return out


# ------------------------------------------------------------- listas
@r.get("/tasks")
def tasks(status: str = "open", project: str | None = None, u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    """status=open|completed|all. Espelho do quadro inteiro (menos Matt tasks)."""
    where, p = ["COALESCE(t.deleted_reason,'')!=?"], ["excluída no Asana"]   # #227: espelho do que existe lá
    if status != "all":
        where.append("t.status=?"); p.append(status)
    if project:
        where.append("t.project=?"); p.append(project)
    sql = "SELECT t.*, c.name AS client_name FROM tasks t LEFT JOIN clients c ON c.id=t.client_id"
    if where:
        sql += " WHERE " + " AND ".join(where)
    rows = todos(con, sql + " ORDER BY t.due_on IS NULL, t.due_on, t.title", p)
    for t in rows:
        t["links"] = _links(con, "task", t["id"])
    return rows


@r.get("/waivers")
def waivers(hidden: bool = False, u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    rows = todos(con, "SELECT w.*, c.name AS client_name, c.pilot_name AS client_pilot, v.at AS voided_at, v.by_name AS voided_by, v.reason AS void_reason "
                      "FROM waivers w LEFT JOIN clients c ON c.id=w.client_id LEFT JOIN waiver_voids v ON v.waiver_id=w.id WHERE w.hidden=? ORDER BY CASE w.status WHEN 'autoresponded' THEN 0 WHEN 'delivered' THEN 1 WHEN 'sent' THEN 2 ELSE 3 END, w.sent_at DESC", (1 if hidden else 0,))
    # `internal` e `subject` vêm no w.*: a tela separa os documentos da empresa numa aba (dono, 16/09)
    for w in rows:
        w["links"] = _links(con, "waiver", w["id"])
    return rows


@r.get("/emails")
def emails(response: Response, mailbox: str | None = None, limit: int | None = None, offset: int = 0,
           u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    sql = "SELECT e.*, c.name AS client_name FROM emails e LEFT JOIN clients c ON c.id=e.client_id"
    p = []
    if mailbox:
        sql += " WHERE e.mailbox=?"; p.append(mailbox)
    # inbox primeiro: o e-mail que o dono ainda não arquivou não pode cair fora do
    # LIMIT por ser antigo (regra dele, 14/09). O já arquivado é que pode.
    rows = paginar(con, sql + " ORDER BY e.is_inbox DESC, e.last_at DESC, e.id DESC", p, response,
                   limit=limit, offset=offset, padrao=300)
    for e in rows:
        e["links"] = _links(con, "email", e["id"])
    return rows


class EmailIn(BaseModel):
    handled: bool


@r.patch("/emails/{eid}")
def email_patch(eid: int, dados: EmailIn, request: Request, u=Depends(auth.exige("OPERATOR")),
                con: sqlite3.Connection = Depends(get_db)):
    """Marca tratado/não tratado no espelho. Não mexe no Gmail."""
    if not um(con, "SELECT id FROM emails WHERE id=?", (eid,)):
        raise HTTPException(404, "Email not found.")
    con.execute("UPDATE emails SET handled=?, handled_by=?, handled_reason=NULL WHERE id=?", (1 if dados.handled else 0, f"user:{u['id']}" if dados.handled else None, eid))
    auditar(con, "email.handled", f"user:{u['id']}", user_id=u["id"], entity_type="email", entity_id=eid,
            detail={"handled": dados.handled}, ip=auth._ip(request))
    return {"ok": True}


# ---------------------------------------------------------- políticas
@r.get("/policies")
def policies(u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    return todos(con, "SELECT * FROM action_policies ORDER BY policy, action")


class PoliticaIn(BaseModel):
    policy: str
    note: str | None = None


@r.put("/policies/{action}")
def policy_put(action: str, dados: PoliticaIn, request: Request, u=Depends(auth.exige("ADMIN")),
               con: sqlite3.Connection = Depends(get_db)):
    if dados.policy not in ("SAFE", "REQUIRES_CONFIRMATION", "REQUIRES_APPROVAL", "BLOCKED"):
        raise HTTPException(400, "Invalid policy.")
    atual = um(con, "SELECT * FROM action_policies WHERE action=?", (action,))
    if not atual:
        raise HTTPException(404, "Unknown action.")
    if atual["policy"] == "BLOCKED" and action.startswith("apagar"):
        raise HTTPException(403, "Deleting is blocked by design and cannot be enabled here.")
    con.execute("UPDATE action_policies SET policy=?, note=COALESCE(?, note), updated_by=?, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE action=?",
                (dados.policy, dados.note, u["id"], action))
    auditar(con, "policy.update", f"user:{u['id']}", user_id=u["id"], entity_type="policy", entity_id=action,
            detail={"from": atual["policy"], "to": dados.policy}, ip=auth._ip(request))
    return {"ok": True}
