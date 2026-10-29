"""Rotas dos clientes (#436: saíram do rotas.py, sem mudar rota): lista, card 360 e edição;
duplicados, união e varredura; criação manual pelo painel; Pro Racing Drivers,
mensalidade, contrato, equipamento e corridas.
"""
import json
import os
import re
import sqlite3
import threading
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel

from command_center.api import auth
from command_center.api.cache_api import paginar
from command_center.api.rotas import BASE, _SYNC, _SYNC_LOCK, _links
from command_center.api.rotas_ia import MAX_BYTES, _slug
from command_center.db import agora, auditar, conectar, get_db, inserir, status_da_waiver, todos, um
from command_center.providers import NaoConectado, chamar, contrato, modulo, sync as sy

r = APIRouter(prefix=BASE)


# ----------------------------------------------------------- clientes
@r.get("/clients")
def clients(response: Response, status: str | None = None, q: str | None = None, vip: bool | None = None,
            pro: bool | None = None, limit: int | None = None, offset: int = 0,
            u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    where, p = ["1=1"], []
    # 22/09: corrida/tarefa que virou card fica 'separado' — fora da lista, mas consultável
    if (status or "").upper() == "SEPARADO":
        where.append("c.kind=?"); p.append(identidade.SEPARADO)
    else:
        where.append("c.kind<>?"); p.append(identidade.SEPARADO)
        if status:
            where.append("c.status=?"); p.append(status.upper())
    if vip is not None:
        where.append("c.vip=?"); p.append(1 if vip else 0)
    if pro is not None:
        where.append("c.pro_driver=?"); p.append(1 if pro else 0)
    ordem, po = "", []
    if q:
        f, pf, ordem, po = identidade.filtro_busca(q)      # #430: também pelo Client ID
        where.append(f); p += pf
    return paginar(con, f"""
        SELECT c.*, s.label AS stage,
          (SELECT COUNT(*) FROM tasks t WHERE t.client_id=c.id AND t.deleted_at IS NULL AND t.status='open') AS open_tasks,
          (SELECT COUNT(*) FROM tasks t WHERE t.client_id=c.id AND t.deleted_at IS NULL AND t.status='completed') AS done_tasks,
          (SELECT MAX(due_on) FROM tasks t WHERE t.client_id=c.id AND t.deleted_at IS NULL AND t.status='completed') AS last_service,
          (SELECT MIN(due_on) FROM tasks t WHERE t.client_id=c.id AND t.deleted_at IS NULL AND t.status='open' AND due_on>=date('now')) AS next_service,
          (SELECT {status_da_waiver('w')} FROM waivers w WHERE w.client_id=c.id ORDER BY sent_at DESC LIMIT 1) AS waiver_status,
          (SELECT COUNT(*) FROM emails e WHERE e.client_id=c.id AND e.handled=0) AS emails_open,
          (SELECT MAX(synced_at) FROM tasks t WHERE t.client_id=c.id) AS last_activity
        FROM clients c LEFT JOIN client_stages s ON s.code=c.stage_code
        WHERE {' AND '.join(where)} ORDER BY {ordem}MAX(COALESCE(next_service, ''), COALESCE(last_service, '')) DESC,
              COALESCE(c.pilot_name, c.name), c.id""", p + po, response, limit=limit, offset=offset)


@r.get("/clients/{cid}")
def client_360(cid: int, u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    c = um(con, "SELECT * FROM clients WHERE id=?", (cid,))
    if not c:
        raise HTTPException(404, "Client not found.")
    fin = auth.pode(u["role"], "MANAGER")
    # #219: o excluído continua no histórico do card, marcado, com quem excluiu
    tarefas = todos(con, """SELECT t.*, ud.name AS deleted_by_name FROM tasks t LEFT JOIN users ud ON ud.id=t.deleted_by
                            WHERE t.client_id=? ORDER BY t.due_on DESC""", (cid,))
    for t in tarefas:
        t.pop("notes", None)                 # #457: a descrição do espelho do Asana vai só no detalhe da tarefa
        t["links"] = _links(con, "task", t["id"])
    # #109: a anulada continua no card, com quem anulou, quando e por quê (a linha dela não muda)
    waivers = todos(con, """SELECT w.*, v.at AS voided_at, v.by_name AS voided_by, v.reason AS void_reason
                            FROM waivers w LEFT JOIN waiver_voids v ON v.waiver_id = w.id
                            WHERE w.client_id=? ORDER BY w.sent_at DESC""", (cid,))
    from command_center.providers import copia_waiver
    for w in waivers:
        w["links"] = _links(con, "waiver", w["id"])
        w["copy"] = copia_waiver.ultima(con, w["id"]) if w["source"] == "urace" else None     # #114: a última cópia por e-mail
    box = bool(u.get("cargo"))               # mecânico/coach (#92): o card sem e-mail, IA e valores
    emails = [] if box else todos(con, "SELECT * FROM emails WHERE client_id=? ORDER BY last_at DESC LIMIT 50", (cid,))
    for e in emails:
        e["links"] = _links(con, "email", e["id"])
    from command_center.api import lembretes
    invoices = todos(con, f"SELECT i.*, {lembretes.CAMPOS_NA_INVOICE} FROM invoices i WHERE i.client_id=? ORDER BY i.issued_on DESC", (cid,)) if fin else None
    acoes = [] if box else todos(con, "SELECT a.* FROM ai_actions a JOIN ai_workflows w ON w.id=a.workflow_id WHERE w.client_id=? ORDER BY a.created_at DESC LIMIT 50", (cid,))
    # timeline: tudo junto, em ordem
    # cada item da linha do tempo leva o SEU link (Asana da tarefa, DocuSign do envelope, Gmail da thread, QBO da invoice)
    def _usd(v):
        return "?" if v is None else f"${v:,.2f}"

    def _dbr(d):
        return f"{d[8:10]}/{d[5:7]}/{d[:4]}" if d and len(d) >= 10 else (d or "")
    tl = []
    for t in tarefas:
        # #460: a visita mostra o último comentário do espelho do Asana, quantos há e o checklist do box
        ult = um(con, """SELECT author, text, created_at, (SELECT COUNT(*) FROM task_comments x WHERE x.task_id=c.task_id AND x.gone_at IS NULL) AS n
                         FROM task_comments c WHERE task_id=? AND gone_at IS NULL ORDER BY created_at DESC, id DESC LIMIT 1""", (t["id"],))
        ck = um(con, """SELECT COUNT(*) AS n, SUM(CASE WHEN r.status='completo' THEN 1 ELSE 0 END) AS feitos FROM checklist_runs r
                        WHERE r.task_id=?""", (t["id"],))
        tl.append({"at": t["due_on"], "kind": "SERVICE", "title": t["title"], "status": "deleted" if t["deleted_at"] else t["status"], "entity": {"type": "task", "id": t["id"]},
                   "detail": f"{t['section'] or ''}" + (f" · subtarefas {t['subtasks_done'] or 0}/{t['subtasks_total']}" if t.get("subtasks_total") else ""), "links": t["links"],
                   "servico": {"subtarefas": [t["subtasks_done"] or 0, t["subtasks_total"] or 0], "comentarios": ult["n"] if ult else 0,
                               "ultimo_comentario": {"quem": ult["author"], "texto": (ult["text"] or "")[:280], "quando": ult["created_at"]} if ult else None,
                               "checklists": [ck["feitos"] or 0, ck["n"]] if ck and ck["n"] else None}})
    for w in waivers:
        tl.append({"at": (w["sent_at"] or "")[:10], "kind": "WAIVER_SENT", "title": f"Waiver {w['template']} → {w['signer_name']}", "status": w["status"], "entity": {"type": "waiver", "id": w["id"]},
                   "detail": w.get("signer_email"), "links": w["links"]})
        if w["completed_at"]:
            tl.append({"at": w["completed_at"][:10], "kind": "WAIVER_SIGNED", "title": f"Waiver assinada por {w['signer_name']}", "status": "completed", "entity": {"type": "waiver", "id": w["id"]},
                       "detail": f"vale até {_dbr(w['expires_at'])}" if w.get("expires_at") else None, "links": w["links"]})
        if w["voided_at"]:
            tl.append({"at": w["voided_at"][:10], "kind": "WAIVER_VOIDED", "title": f"Waiver de {w['signer_name']} anulada por {w['voided_by']}",
                       "status": "voided", "entity": {"type": "waiver", "id": w["id"]}, "detail": w["void_reason"], "links": w["links"]})
    for e in emails:
        tl.append({"at": (e["last_at"] or "")[:10], "kind": "EMAIL", "title": e["subject"], "status": "handled" if e["handled"] else "open", "entity": {"type": "email", "id": e["id"]},
                   "detail": f"{e['mailbox']}@ · {e.get('sender') or ''}", "links": e["links"]})
    for a in acoes:
        tl.append({"at": a["created_at"][:10], "kind": "AI_ACTION", "title": a["action"], "status": a["status"], "entity": {"type": "ai_action", "id": a["id"]},
                   "detail": (a.get("reason") or "")[:120], "links": []})
    for i in (invoices or []):
        tl.append({"at": i["issued_on"] or (i["due_on"] or ""), "kind": "INVOICE", "title": f"Invoice {i['doc_number'] or ''} · {_usd(i['amount'])}", "status": i["status"] or "?",
                   "entity": {"type": "invoice", "id": i["id"]}, "detail": (f"saldo {_usd(i['balance'])}" if i.get("balance") else "paga") + (f" · vence {_dbr(i['due_on'])}" if i.get("due_on") else "") + (f" · {i['memo']}" if i.get("memo") else ""), "links": _links(con, "invoice", i["id"])})
    # #248: o resultado de cada pagamento do site (pago, processando, não passou, expirou), com o link do pedido.
    # Mecânico e coach (box) não veem valores.
    for ev in ([] if box else todos(con, "SELECT * FROM client_events WHERE client_id=? ORDER BY at DESC LIMIT 100", (cid,))):
        tl.append({"at": (ev["at"] or "")[:10], "kind": ev["kind"], "title": ev["title"], "status": ev["status"],
                   "entity": {"type": "store_order", "id": ev["order_id"]}, "detail": ev["detail"],
                   "links": [{"system": "site", "external_id": str(ev["order_id"]), "deep_link": ev["link"]}] if ev["link"] else []})
    tl.sort(key=lambda x: x["at"] or "", reverse=True)
    ultimo = next((t for t in tarefas if t["status"] == "completed" and t["due_on"]), None)
    # #460: as peças do balcão de cada dia, para a visita (o valor só para quem vê o financeiro)
    pecas = {}
    for pi in todos(con, "SELECT id, service_date, status, doc_number, total FROM parts_invoices WHERE client_id=? AND status!='anulada'", (cid,)):
        itens = todos(con, """SELECT COALESCE(i.name, 'peça') AS nome, SUM(sc.qty) AS qtd FROM stock_charges sc LEFT JOIN stock_items i ON i.id=sc.item_id
                              WHERE sc.parts_invoice_id=? GROUP BY nome ORDER BY nome""", (pi["id"],))
        pecas.setdefault(pi["service_date"], []).append({"id": pi["id"], "status": pi["status"], "doc": pi["doc_number"],
                                                         "total": pi["total"] if fin else None, "itens": itens})
    c = dict(c, dados=dados_do_cliente(con, c))
    return {"client": c, "pecas_por_dia": pecas, "irmaos": identidade.irmaos(con, cid), "links": _links(con, "client", cid), "tasks": tarefas, "waivers": waivers,
            "emails": emails, "invoices": invoices, "ai_actions": acoes, "timeline": tl, "last_service": ultimo,
            "open_balance": (sum((i["balance"] or 0) for i in invoices) if invoices else None),
            "stages": todos(con, "SELECT code, label FROM client_stages ORDER BY ord")}


class ClienteIn(BaseModel):
    status: str | None = None
    stage_code: str | None = None
    notes: str | None = None
    vip: bool | None = None
    monthly_plan: str | None = None
    monthly_note: str | None = None
    # #410 (dono, 28/10): "quando eu clico em editar no card do cliente, eu não consigo editar o nome, e-mail".
    # None = não mexe; "" = apaga (menos o responsável, que não fica vazio).
    name: str | None = None
    pilot_name: str | None = None
    pilot_dob: str | None = None
    email: str | None = None
    email_alt: str | None = None
    phone: str | None = None
    company: str | None = None
    # #460: "Dados do cliente" — parentesco, classe e as medidas conferidas pela equipe. "" apaga.
    relationship: str | None = None
    racing_class: str | None = None
    measures: dict | None = None


CONTATO = ("name", "pilot_name", "pilot_dob", "email", "email_alt", "phone", "company")
CLASSES = ("Mini", "Micro", "Cadet", "Junior", "Senior", "Shifter", "Masters")


def _dados_limpos(campos, u):
    """#460: parentesco (texto curto), classe (da lista) e medidas (as mesmas chaves e faixas da área do cliente)."""
    if "relationship" in campos:
        campos["relationship"] = " ".join(campos["relationship"].split())[:40] or None
    if "racing_class" in campos:
        cl = campos["racing_class"].strip()
        if cl and cl not in CLASSES:
            raise HTTPException(400, f"Classe inválida: use {', '.join(CLASSES)}.")
        campos["racing_class"] = cl or None
    if "measures" in campos:
        from command_center.providers import portal
        try:
            m = portal.medidas(campos["measures"])
        except portal.ErroPortal as e:
            raise HTTPException(400, str(e))
        campos.update(measures=json.dumps(m) if m else None, measures_at=agora(), measures_by=u["id"])


def dados_do_cliente(con, c):
    """#460: o "Dados do cliente" do card. Medidas: as da área do cliente, com o que a equipe conferiu por cima;
    parentesco: o do card, senão o da última waiver assinada pela área do cliente; classe: a do card, senão a do chassi."""
    site = um(con, """SELECT measures, measures_updated_at FROM portal_pilots WHERE client_id=? AND measures IS NOT NULL
                      ORDER BY measures_updated_at DESC LIMIT 1""", (c["id"],))
    medidas = dict(json.loads(site["measures"]) if site and site["measures"] else {})
    equipe = json.loads(c["measures"]) if c.get("measures") else {}
    medidas.update(equipe)
    fonte = []
    if site and site["measures"]:
        fonte.append({"de": "site", "em": site["measures_updated_at"]})
    if equipe:
        fonte.append({"de": "equipe", "em": c.get("measures_at")})
    parentesco, de = c.get("relationship"), "card"
    if not parentesco:
        w = um(con, """SELECT signer_relationship FROM waiver_reviews WHERE client_id=? AND signer_relationship IS NOT NULL
                       AND used_at IS NOT NULL ORDER BY used_at DESC LIMIT 1""", (c["id"],))
        parentesco, de = (w["signer_relationship"], "waiver") if w else (None, None)
    classe, classe_de = c.get("racing_class"), "card"
    if not classe and c.get("chassis_id"):
        ch = um(con, "SELECT size FROM catalog_chassis WHERE id=?", (c["chassis_id"],))
        classe, classe_de = (ch["size"], "chassi") if ch and ch["size"] else (None, None)
    return {"medidas": medidas, "medidas_fonte": fonte, "parentesco": parentesco, "parentesco_de": de if parentesco else None,
            "classe": classe, "classe_de": classe_de if classe else None, "classes": list(CLASSES)}


def _contato_limpo(con, cid, campos, antes):
    """Valida e normaliza os dados de contato editados à mão (#410), no mesmo formato da sincronia.
    E-mail que já é de outro card (fora da família de irmãos) é recusado: o caminho é Unir, nunca
    pôr um cliente no card de outro."""
    for k in CONTATO:
        if k in campos:
            campos[k] = (campos[k] or "").strip() or None
    if "name" in campos and len(campos["name"] or "") < 2:
        raise HTTPException(400, "O nome do responsável não pode ficar vazio.")
    for k in ("email", "email_alt"):
        if campos.get(k):
            principal, _ = identidade.normaliza_email(campos[k])
            if not principal:
                raise HTTPException(400, f"E-mail inválido: {campos[k]}")
            campos[k] = principal
    if campos.get("phone"):
        tel = identidade.normaliza_telefone(campos["phone"])
        if not tel:
            raise HTTPException(400, f"Telefone inválido: {campos['phone']}")
        campos["phone"] = tel
    if campos.get("pilot_dob"):
        try:
            nasc = date.fromisoformat(campos["pilot_dob"][:10])
        except ValueError:
            raise HTTPException(400, "Nascimento no formato AAAA-MM-DD.")
        if nasc > date.today():
            raise HTTPException(400, "Nascimento no futuro.")
        campos["pilot_dob"] = nasc.isoformat()
    for k in CONTATO:                                  # o que não mudou não entra na conta nem na auditoria
        if k in campos and campos[k] == antes[k]:
            campos.pop(k)
    familia = identidade.familia(con, cid)
    for k in ("email", "email_alt"):
        e = campos.get(k)
        if not e:
            continue
        outros = [o for o in todos(con, "SELECT id, name, pilot_name FROM clients WHERE LOWER(email)=? OR LOWER(COALESCE(email_alt,''))=?", (e, e))
                  if o["id"] not in familia]
        if outros:
            o = outros[0]
            raise HTTPException(409, f"O e-mail {e} já está no card {o['id']} ({o['pilot_name'] or o['name']}). "
                                     "Se é a mesma pessoa, use Unir com outro card.")
    return campos


@r.patch("/clients/{cid}")
def client_patch(cid: int, dados: ClienteIn, request: Request, u=Depends(auth.exige("OPERATOR")),
                 con: sqlite3.Connection = Depends(get_db)):
    if not um(con, "SELECT id FROM clients WHERE id=?", (cid,)):
        raise HTTPException(404, "Client not found.")
    campos = {k: v for k, v in dados.model_dump().items() if v is not None}
    for k in ("relationship", "racing_class"):         # a tela manda null para esvaziar (a chave ausente continua "não mexe")
        if k in dados.model_fields_set and getattr(dados, k) is None:
            campos[k] = ""
    antes = um(con, f"SELECT {', '.join(CONTATO)} FROM clients WHERE id=?", (cid,))
    _contato_limpo(con, cid, campos, antes)
    _dados_limpos(campos, u)
    if "vip" in campos:
        if not auth.pode(u["role"], "MANAGER"):
            raise HTTPException(403, "Only managers can change VIP.")
        campos["vip"] = 1 if campos["vip"] else 0
    if "status" in campos:
        campos["status_locked"] = 1                      # mudança à mão não é desfeita pela sincronia
    if not campos:
        return {"ok": True}
    sets = ", ".join(f"{k}=?" for k in campos)
    con.execute(f"UPDATE clients SET {sets}, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?", (*campos.values(), cid))
    detalhe = dict(campos)
    if mudou := {k: antes[k] for k in CONTATO if k in campos}:
        detalhe["antes"] = mudou                       # #410: o contato trocado à mão fica com o antes e o depois
    auditar(con, "client.update", f"user:{u['id']}", user_id=u["id"], entity_type="client", entity_id=cid,
            detail=detalhe, ip=auth._ip(request))
    return {"ok": True}


# ============================================================ Clientes: duplicados, união, varredura
from command_center.providers import identidade  # noqa: E402


_FULL = {"running": False, "started_at": None, "finished_at": None, "stage": None, "done": 0, "total": None, "result": None, "by": None}


def _full_thread(user_id):
    con = conectar()
    try:
        def prog(d):
            _FULL.update(d)
        res = sy.sync_asana_completo(con, prog)
        con.commit()
        _FULL["result"] = res
        auditar(con, "sync.full", f"user:{user_id}", user_id=user_id, detail=res)
    except Exception as e:
        _FULL["result"] = {"ok": False, "motivo": f"{type(e).__name__}: {str(e)[:300]}"}
    finally:
        _FULL["running"] = False; _FULL["finished_at"] = agora()
        with _SYNC_LOCK:
            _SYNC["running"] = False
        con.close()


@r.post("/sync/full", status_code=202)
def sync_full(u=Depends(auth.exige("MANAGER"))):
    """Puxa o histórico COMPLETO do quadro U-RACE (todas as colunas, concluídas incluídas,
    sem teto) e liga cada serviço à pessoa certa. Segura a sincronia normal enquanto roda."""
    with _SYNC_LOCK:
        if _FULL["running"] or _SYNC["running"]:
            return {"started": False, **_FULL, "sync_running": _SYNC["running"]}
        _SYNC.update(running=True, started_at=agora(), finished_at=None, result=None, by=u["id"], stage="histórico completo do Asana")
    _FULL.update(running=True, started_at=agora(), finished_at=None, stage="listando", done=0, total=None, result=None, by=u["id"])
    threading.Thread(target=_full_thread, args=(u["id"],), daemon=True).start()
    return {"started": True, **_FULL}


@r.get("/sync/full")
def sync_full_status(u=Depends(auth.usuario_atual)):
    return _FULL


from command_center.providers import atribuicao  # noqa: E402


@r.get("/service-attribution")
def service_attribution(u=Depends(auth.exige("MANAGER")), con: sqlite3.Connection = Depends(get_db)):
    """VARREDURA: de quem é cada serviço, segundo o título do Asana. Não escreve nada.

    Nasceu de 22/09: o dono abriu o card do David Pedalo para marcar uma sessão e achou
    113 serviços, 112 de outras pessoas."""
    rel = atribuicao.redistribuir(con, aplicar=False)
    return {**rel, "resumo": atribuicao.resumo(rel)}


@r.post("/service-attribution")
def service_attribution_apply(request: Request, u=Depends(auth.exige("ADMIN")), con: sqlite3.Connection = Depends(get_db)):
    """APLICA: move cada serviço para o card de quem é.

    Move só o que é certo. Nome ambíguo ("Alexander" com um Sprage e um Jetsby no
    quadro) e nome de uma palavra só sem card voltam na lista para decisão humana —
    unir no escuro é o que cria o problema do outro lado."""
    rel = atribuicao.redistribuir(con, aplicar=True)
    identidade.recalcular_status(con)
    con.commit()
    auditar(con, "clients.service_attribution", f"user:{u['id']}", user_id=u["id"],
            detail={"resumo": atribuicao.resumo(rel), "movidos": len(rel["movidos"]),
                    "criados": rel["criados"], "unir": rel["unir"],
                    "amostra": rel["movidos"][:40]},
            ip=auth._ip(request))
    return {**rel, "resumo": atribuicao.resumo(rel),
            "pares_para_decidir": identidade.candidatos_duplicados(con)}


@r.get("/clients/{cid}/duplicates")
def client_duplicates_of(cid: int, u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    """Quem parece ser a mesma pessoa que este cliente (para o botão 'Unir com…')."""
    if not um(con, "SELECT id FROM clients WHERE id=?", (cid,)):
        raise HTTPException(404, "Client not found.")
    pares = identidade.candidatos_duplicados(con, para=cid)
    return [dict(**(p["b"] if p["a"]["id"] == cid else p["a"]), why=p["why"]) for p in pares]


@r.get("/client-duplicates")
def clients_duplicates(u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    """Pares que parecem a mesma pessoa. Decisão humana; a IA pode opinar."""
    return {"pairs": identidade.candidatos_duplicados(con),
            "merged": todos(con, "SELECT * FROM client_merges ORDER BY id DESC LIMIT 50")}


class UnirIn(BaseModel):
    keep_id: int
    drop_id: int
    reason: str | None = None


@r.post("/client-merge")
def clients_merge(dados: UnirIn, request: Request, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    if dados.keep_id == dados.drop_id:
        raise HTTPException(400, "Same client.")
    if not um(con, "SELECT id FROM clients WHERE id=?", (dados.keep_id,)) or not um(con, "SELECT id FROM clients WHERE id=?", (dados.drop_id,)):
        raise HTTPException(404, "Client not found.")
    if (porque := identidade.nao_unir(con, dados.keep_id, dados.drop_id)):
        raise HTTPException(409, f"Esses dois cards não se unem: {porque}.")
    antes = {t: um(con, f"SELECT COUNT(*) AS n FROM {t} WHERE client_id=?", (dados.drop_id,))["n"] for t in ("tasks", "waivers", "emails", "invoices")}
    try:
        identidade.unir(con, dados.keep_id, dados.drop_id, f"user:{u['id']}", dados.reason or "unido à mão")
    except identidade.ErroUniao as e:
        raise HTTPException(409, f"Esses dois cards não se unem: {e}.")
    identidade.recalcular_status(con)
    auditar(con, "client.merge", f"user:{u['id']}", user_id=u["id"], entity_type="client", entity_id=dados.keep_id,
            detail={"drop_id": dados.drop_id, "reason": dados.reason, "moved": antes}, ip=auth._ip(request))
    return {"ok": True, "moved": antes}


_DUP_IA = {"running": False, "result": None, "finished_at": None}


def _duplicados_ia_thread(user_id):
    from command_center.api import ia
    con = conectar()
    try:
        pares = identidade.candidatos_duplicados(con)
        if not pares:
            _DUP_IA["result"] = {"pareceres": {}}; return
        linhas = [f"- par {i}: A=#{p['a']['id']} '{p['a']['pilot_name'] or p['a']['name']}' (resp. {p['a']['name']}, {p['a']['email'] or 'sem e-mail'}, {p['a']['phone'] or 'sem tel'}) × "
                  f"B=#{p['b']['id']} '{p['b']['pilot_name'] or p['b']['name']}' (resp. {p['b']['name']}, {p['b']['email'] or 'sem e-mail'}, {p['b']['phone'] or 'sem tel'})" for i, p in enumerate(pares)]
        prompt = ("TAREFA: para cada par abaixo, diga se é a MESMA pessoa/cliente da URACE. Consulte o Asana (asana_buscar / asana_tarefa) "
                  "para comparar descrição, e-mail, telefone e histórico das tarefas de cada nome antes de responder. Não altere nada em sistema nenhum. "
                  "RESPONDA APENAS JSON: {\"pares\":[{\"par\":<int>,\"mesma_pessoa\":true|false|null,\"confianca\":\"alta|media|baixa\",\"motivo\":\"<até 20 palavras>\"}]}\n" + "\n".join(linhas))
        ok, texto, erro = ia.RUNNER(prompt, f"agent:{ia.AGENTE}:duplicados")
        if not ok:
            _DUP_IA["result"] = {"erro": erro}; return
        m = re.search(r"\{.*\}", texto or "", re.S)
        dados = json.loads(m.group(0)) if m else {}
        pareceres = {}
        for it in dados.get("pares", []):
            try:
                i = int(it.get("par"))
            except (TypeError, ValueError):
                continue
            if 0 <= i < len(pares):
                pareceres[f"{pares[i]['a']['id']}-{pares[i]['b']['id']}"] = {"mesma_pessoa": it.get("mesma_pessoa"), "confianca": it.get("confianca"), "motivo": (it.get("motivo") or "")[:200]}
        auditar(con, "client.duplicates_ai", f"user:{user_id}", user_id=user_id, detail={"pares": len(pares), "pareceres": len(pareceres)})
        _DUP_IA["result"] = {"pareceres": pareceres}
    except Exception as e:
        _DUP_IA["result"] = {"erro": f"{type(e).__name__}: {str(e)[:300]}"}
    finally:
        _DUP_IA["running"] = False; _DUP_IA["finished_at"] = agora(); con.close()


@r.post("/client-duplicates/ai", status_code=202)
def clients_duplicates_ai(u=Depends(auth.exige("OPERATOR"))):
    if _DUP_IA["running"]:
        return {"started": False, "running": True}
    _DUP_IA.update(running=True, result=None, finished_at=None)
    threading.Thread(target=_duplicados_ia_thread, args=(u["id"],), daemon=True).start()
    return {"started": True, "running": True}


@r.get("/client-duplicates/ai")
def clients_duplicates_ai_status(u=Depends(auth.usuario_atual)):
    return _DUP_IA


def _varrer_cliente(con, c):
    """Gmail (as duas caixas, fora da inbox também) e DocuSign para UM cliente. Só leitura + espelho."""
    saida = {"gmail": 0, "docusign": 0, "avisos": []}
    email = (c["email"] or "").lower()
    nomes = [n for n in (c["pilot_name"], c["name"]) if n]
    for conta in ("urace", "support"):
        consultas = []
        if email:
            consultas.append(f"from:{email} OR to:{email}")
        if conta == "support" and nomes:                        # acessos do DocuSign chegam no support@
            consultas.append(" OR ".join(f'"{n}"' for n in nomes[:2]))
        for q in consultas:
            try:
                r = chamar("gmail", "gmail_buscar", conta=conta, consulta=q, so_inbox=False, maximo=50)
            except NaoConectado as e:
                saida["avisos"].append(f"gmail: {e}"); break
            except Exception as e:
                if "não configurada" in str(e):
                    break
                saida["avisos"].append(f"gmail {conta}: {str(e)[:120]}"); break
            for t in r.get("threads", []):
                eid = um(con, "SELECT entity_id FROM entity_links WHERE system='gmail' AND external_id=? AND entity_type='email'", (t["thread_id"],))
                marcadores = t.get("marcadores") or []
                na_inbox = "INBOX" in marcadores
                campos = dict(client_id=c["id"], mailbox=conta, subject=t.get("assunto"), sender=(t.get("de") or "")[:200],
                              last_at=sy._data_rfc(t.get("data")), snippet=(t.get("snippet") or "")[:300], messages=t.get("mensagens"),
                              is_inbox=1 if na_inbox else 0, labels=json.dumps(marcadores, ensure_ascii=False), synced_at=agora(),
                              # histórico fora da inbox é contexto do cliente, não trabalho pendente
                              handled=0 if na_inbox else 1, handled_by=None if na_inbox else "auto",
                              handled_reason=None if na_inbox else "histórico trazido pela varredura (fora da inbox)")
                if eid:
                    con.execute("UPDATE emails SET client_id=COALESCE(client_id, ?), synced_at=? WHERE id=?", (c["id"], agora(), eid["entity_id"]))
                else:
                    from command_center.db import inserir
                    nid = inserir(con, "emails", **campos)
                    con.execute("INSERT OR IGNORE INTO entity_links (entity_type, entity_id, system, external_id, deep_link) VALUES ('email',?,?,?,?)",
                                (nid, "gmail", t["thread_id"], f"https://mail.google.com/mail/u/{0 if conta == 'urace' else 1}/#all/{t['thread_id']}"))
                saida["gmail"] += 1
    if email:
        try:
            r = chamar("docusign", "docusign_waivers_de", email=email)
            for grupo in ("waiver_valida", "em_aberto", "historico"):
                for e in r.get(grupo) or []:
                    w = um(con, "SELECT w.id, w.client_id, w.link_by FROM waivers w JOIN entity_links l ON l.entity_type='waiver' AND l.entity_id=w.id WHERE l.system='docusign' AND l.external_id=?", (e["envelopeId"],))
                    if w and not w["client_id"]:
                        con.execute("UPDATE waivers SET client_id=?, link_by='sync', link_reason=? WHERE id=?", (c["id"], f"varredura: e-mail {email}", w["id"]))
                        saida["docusign"] += 1
        except NaoConectado as e:
            saida["avisos"].append(f"docusign: {e}")
        except Exception as e:
            saida["avisos"].append(f"docusign: {str(e)[:120]}")
    saida["contratos"] = _contratos_do_docusign(con, c)
    con.execute("UPDATE clients SET scanned_at=? WHERE id=?", (agora(), c["id"]))
    return saida


@r.post("/clients/{cid}/scan")
def client_scan(cid: int, request: Request, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    """Varre Gmail e DocuSign atrás deste cliente e liga o que achar ao card."""
    c = um(con, "SELECT * FROM clients WHERE id=?", (cid,))
    if not c:
        raise HTTPException(404, "Client not found.")
    res = _varrer_cliente(con, c)
    auditar(con, "client.scan", f"user:{u['id']}", user_id=u["id"], entity_type="client", entity_id=cid, detail=res, ip=auth._ip(request))
    return res


_SCAN = {"running": False, "done": 0, "total": 0, "result": None, "finished_at": None}


def _scan_all_thread(user_id):
    con = conectar()
    try:
        cs = todos(con, "SELECT * FROM clients WHERE status='ACTIVE' ORDER BY last_service_at DESC")
        _SCAN.update(total=len(cs), done=0)
        tot = {"gmail": 0, "docusign": 0}
        for c in cs:
            r = _varrer_cliente(con, c)
            tot["gmail"] += r["gmail"]; tot["docusign"] += r["docusign"]
            _SCAN["done"] += 1
            if any(a.startswith(("gmail:", "docusign:")) and "não conectado" in a.lower() for a in r["avisos"]):
                break
        auditar(con, "client.scan_all", f"user:{user_id}", user_id=user_id, detail=tot)
        _SCAN["result"] = tot
    except Exception as e:
        _SCAN["result"] = {"erro": f"{type(e).__name__}: {str(e)[:300]}"}
    finally:
        _SCAN["running"] = False; _SCAN["finished_at"] = agora(); con.close()


@r.post("/client-scan-all", status_code=202)
def clients_scan_all(u=Depends(auth.exige("OPERATOR"))):
    if _SCAN["running"]:
        return {"started": False, **_SCAN}
    _SCAN.update(running=True, done=0, total=0, result=None, finished_at=None)
    threading.Thread(target=_scan_all_thread, args=(u["id"],), daemon=True).start()
    return {"started": True, **_SCAN}


@r.get("/client-scan-all")
def clients_scan_all_status(u=Depends(auth.usuario_atual)):
    return _SCAN


# ============================================================ Criação manual pelo painel (portas humanas)
from command_center.providers.sync import PROJETO_URACE, SECOES_DIAS, _upsert_cliente, _liga, ASANA_LINK  # noqa: E402

MODELO_SESSAO = os.environ.get("ASANA_MODELO_SESSAO", "1208702559561159")
RATE_CARD_ID = "160efDlmavKKGbtGfJKCTOV_3Q9JEO3Lc6xA1mEMMNyo"


class ClienteNovoIn(BaseModel):
    name: str
    pilot_name: str | None = None
    pilot_dob: str | None = None
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    notes: str | None = None
    vip: bool = False
    irmao_de: int | None = None          # #204: card de irmão — o card do irmão (Vincular ao cliente)


@r.post("/clients", status_code=201)
def client_create(dados: ClienteNovoIn, request: Request, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    """Cliente criado à mão no painel. Se já existir (e-mail, telefone, nome), devolve o existente em vez de duplicar.
    Com `irmao_de`, cria o card do irmão: mesmo responsável, e-mail e telefone daquele card, piloto próprio."""
    if dados.irmao_de:
        try:
            cid, novo = identidade.criar_irmao(con, dados.irmao_de, dados.pilot_name, (dados.pilot_dob or "").strip() or None,
                                               (dados.notes or "").strip() or None)
        except identidade.ErroIrmao as e:
            raise HTTPException(400, str(e))
        auditar(con, "client.sibling" if novo else "client.match", f"user:{u['id']}", user_id=u["id"], entity_type="client",
                entity_id=cid, detail={"irmao_de": dados.irmao_de, "piloto": (dados.pilot_name or "").strip(), "novo": novo},
                ip=auth._ip(request))
        return {"id": cid, "created": novo, "irmao_de": dados.irmao_de}
    nome = (dados.name or "").strip()
    if len(nome) < 2:
        raise HTTPException(400, "Nome do responsável é obrigatório.")
    email = (dados.email or "").strip().lower() or None
    if email and "@" not in email:
        raise HTTPException(400, "E-mail inválido.")
    cid, novo = _upsert_cliente(con, nome, email, (dados.phone or "").strip() or None, (dados.pilot_name or "").strip() or None,
                                (dados.pilot_dob or "").strip() or None, True if dados.vip else None, source="manual")
    if dados.company or dados.notes:
        con.execute("UPDATE clients SET company=COALESCE(?, company), notes=COALESCE(?, notes) WHERE id=?", (dados.company, dados.notes, cid))
    if novo:
        con.execute("UPDATE clients SET status='NEW' WHERE id=?", (cid,))
    auditar(con, "client.create" if novo else "client.match", f"user:{u['id']}", user_id=u["id"], entity_type="client", entity_id=cid,
            detail={"name": nome, "email": email, "novo": novo}, ip=auth._ip(request))
    return {"id": cid, "created": novo}


CATEGORIAS = ("Using Own Kart", "Baby Kart", "4 stroke", "2 stroke", "Adult Shifter", "F4")
PRODUTOS = {
    "Urace Daily": "treino avulso (Practice / Professional Coaching); preço na aba Academy da Rate Card",
    "Lead and Follow": "coach na pista junto com o piloto (2T); fechado com antecedência = $769 por piloto; aba Academy",
    "Academy": "mensal, 4 sessões [1/4 … 4/4]; preço na aba Academy",
    "Corrida": "Race Support / Trackside Support; preço na aba Racing team",
    "Arrive and Drive": "kart da URACE; aba Academy",
    "Summer Camp": "camp; aba Academy",
    "Test Drive": "primeira experiência; aba Academy",
}


def nome_tarefa(piloto, produto, categoria, n, total):
    """'Renato Faixa Pistoni_Urace Daily_2T [1/1]' — o padrão que o quadro e a IA leem."""
    base = f"{piloto.strip()}_{produto.strip()}" + (f"_{categoria.strip()}" if categoria else "")
    return f"{base} [{max(1, int(n or 1))}/{max(1, int(total or 1))}]"


class TarefaNovaIn(BaseModel):
    client_id: int | None = None
    pilot_name: str
    responsible: str | None = None
    email: str | None = None
    phone: str | None = None
    dob: str | None = None
    height: str | None = None
    weight: str | None = None
    waist: str | None = None
    experience: str | None = None
    product: str                         # Urace Daily | Academy | Corrida | Arrive and Drive | Summer Camp | Test Drive
    category: str | None = None          # 2T, 4T, Baby Kart, F4, X30, KA100
    package_n: int = 1                   # Academy: sessão 1..4 do mês
    package_total: int = 1               # Academy: 4
    days: int = 1                        # compatibilidade
    due_on: str                          # AAAA-MM-DD
    section_gid: str | None = None       # coluna do dia; se vazio, deduz do due_on
    extra_notes: str | None = None


def _secao_do_dia(due_on):
    from datetime import date as _d
    nomes = {1: "TUESDAY", 2: "WEDNESDAY", 3: "THURSDAY", 4: "FRIDAY", 5: "SATURDAY", 6: "SUNDAY"}
    wd = _d.fromisoformat(due_on).weekday()
    nome = nomes.get(wd)
    for gid, n in SECOES_DIAS.items():
        if n == nome:
            return gid, n
    return None, None


@r.post("/tasks", status_code=201)
def task_create(dados: TarefaNovaIn, request: Request, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    """Botão 'Nova tarefa': instancia o modelo oficial no Asana, na coluna do dia, e espelha aqui."""
    from datetime import date as _d
    try:
        _d.fromisoformat(dados.due_on)
    except ValueError:
        raise HTTPException(400, "Data inválida (AAAA-MM-DD).")
    faltam = [k for k, v in (("piloto", dados.pilot_name), ("e-mail", dados.email), ("telefone", dados.phone)) if not (v or "").strip()]
    if faltam:
        raise HTTPException(400, "Obrigatório: " + ", ".join(faltam) + ".")
    if "@" not in (dados.email or ""):
        raise HTTPException(400, "E-mail inválido.")
    if dados.category and dados.category not in CATEGORIAS:
        raise HTTPException(400, f"Categoria deve ser uma de: {', '.join(CATEGORIAS)}.")
    sec_gid, sec_nome = (dados.section_gid, SECOES_DIAS.get(dados.section_gid)) if dados.section_gid else _secao_do_dia(dados.due_on)
    if not sec_gid:
        raise HTTPException(400, "A data cai numa segunda-feira: o quadro não tem coluna. Escolha outra data ou a coluna.")
    piloto = dados.pilot_name.strip()
    resp = (dados.responsible or piloto).strip()
    if dados.product not in PRODUTOS:
        raise HTTPException(400, f"Produto deve ser um de: {', '.join(PRODUTOS)}.")
    n, total = (dados.package_n, dados.package_total) if dados.product == "Academy" else (1, max(1, int(dados.days or 1)))
    nome = nome_tarefa(piloto, dados.product, dados.category, n, total)
    idade = None
    if dados.dob:
        try:
            b = _d.fromisoformat(dados.dob); h = _d.today()
            idade = h.year - b.year - ((h.month, h.day) < (b.month, b.day))
        except ValueError:
            raise HTTPException(400, "Data de nascimento inválida (AAAA-MM-DD).")
    if idade is not None and idade < 18 and not (dados.responsible or "").strip():
        raise HTTPException(400, "Piloto menor de idade: o responsável é obrigatório (é quem assina a waiver e paga).")
    if idade is None and not (dados.responsible or "").strip():
        raise HTTPException(400, "Informe a data de nascimento do piloto ou o responsável.")
    from command_center.api import acoes as _ac
    notas = _ac.notas_servico(piloto, resp, dados.email, dados.phone, dados.dob, dados.due_on, dados.product, dados.category, None,
                              dados.height, dados.weight, dados.waist, dados.experience, dados.extra_notes, por=u["name"])
    campos = {} if dados.product in ("Corrida",) else {"Race": "Practice Bushnell" if re.search(r"bushnell", (dados.extra_notes or "") + (dados.category or ""), re.I) else _ac.RACE_PADRAO}
    try:
        res = modulo("asana").criar_do_modelo_humano(MODELO_SESSAO, nome, sec_gid, notas, dados.due_on, campos)
    except NaoConectado as ex:
        raise HTTPException(503, f"Asana não conectado: {ex}")
    except Exception as ex:
        raise HTTPException(502, str(ex)[:300])
    cid = dados.client_id
    if not cid:
        cid, _ = _upsert_cliente(con, resp, (dados.email or "").lower() or None, dados.phone, piloto if piloto != resp else None, dados.dob, source="manual")
    tid = inserir(con, "tasks", client_id=cid, title=res.get("nome") or nome, project="U-RACE", section=sec_nome, section_gid=sec_gid,
                  status="open", due_on=dados.due_on, synced_at=agora())
    _liga(con, "task", tid, "asana", res["gid"], res.get("link") or ASANA_LINK.format(proj=PROJETO_URACE, gid=res["gid"]))
    _liga(con, "client", cid, "asana", res["gid"], res.get("link"))
    auditar(con, "task.create", f"user:{u['id']}", user_id=u["id"], entity_type="task", entity_id=tid,
            detail={"gid": res["gid"], "nome": nome, "secao": sec_nome, "client_id": cid}, ip=auth._ip(request))
    from command_center.api import motor
    motor.registrar_evento(con, "task.created", "task", tid, cid, f"{nome} em {sec_nome} ({dados.due_on}) — criada pelo painel")
    return {"id": tid, "client_id": cid, "gid": res["gid"], "link": res.get("link"), "section": sec_nome}


class WaiverEnviarIn(BaseModel):
    template: str                        # parental | adult
    signer_name: str
    signer_email: str
    service: str | None = None
    client_id: int | None = None


@r.post("/waivers/send", status_code=201)
def waiver_send(dados: WaiverEnviarIn, request: Request, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    """Botão 'Enviar waiver': clique humano; as travas de duplicidade do DocuSign continuam valendo."""
    templates = {"parental": os.environ.get("DOCUSIGN_TEMPLATE_PARENTAL", "6dbf2094-39da-4c21-95dd-feda7ac28022"),
                 "adult": os.environ.get("DOCUSIGN_TEMPLATE_ADULT", "c51aede4-bba5-40df-9f14-24c340e2bd3e")}
    if dados.template not in templates:
        raise HTTPException(400, "Modelo deve ser parental ou adult.")
    email = dados.signer_email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(400, "E-mail inválido.")
    if email.endswith("@urace.us"):
        raise HTTPException(400, "E-mail do domínio da URACE não é de cliente. Confira o e-mail do responsável.")
    try:
        res = modulo("docusign").enviar_waiver_humano(templates[dados.template], dados.signer_name.strip(), email, dados.service or "")
    except NaoConectado as ex:
        raise HTTPException(503, f"DocuSign não conectado: {ex}")
    except Exception as ex:
        raise HTTPException(409 if "RECUSADO" in str(ex) or "NÃO ENVIAR" in str(ex) else 502, str(ex)[:300])
    env = res.get("envelopeId") if isinstance(res, dict) else None
    cid = dados.client_id or (_acha := None)
    if not cid:
        c = um(con, "SELECT id FROM clients WHERE email=?", (email,))
        cid = c["id"] if c else None
    wid = inserir(con, "waivers", client_id=cid, signer_name=dados.signer_name.strip(), signer_email=email, template=dados.template,
                  status="sent", sent_at=agora(), link_reason="enviada pelo painel", link_by="human" if cid else None, synced_at=agora())
    if env:
        _liga(con, "waiver", wid, "docusign", env, f"https://apps.docusign.com/send/documents/details/{env}")
    auditar(con, "waiver.send", f"user:{u['id']}", user_id=u["id"], entity_type="waiver", entity_id=wid,
            detail={"envelope": env, "template": dados.template, "email": email}, ip=auth._ip(request))
    from command_center.api import rastro        # dono, 21/09: a tarefa registra, com a hora
    rastro.waiver_enviada(con, cid, dados.signer_name.strip(), email, modelo=dados.template)
    return {"id": wid, "envelope": env, "result": res}


@r.get("/rate-card/check")
def rate_card_check(u=Depends(auth.usuario_atual)):
    """A IA precisa ler a planilha de preços. Prova: lê as primeiras células ao vivo."""
    try:
        r = chamar("gmail", "sheets_ler", conta="urace", planilha_id=RATE_CARD_ID, intervalo="A1:D6")
        return {"ok": True, "linhas": r.get("linhas", [])[:6], "id": RATE_CARD_ID}
    except NaoConectado as e:
        return {"ok": False, "reason": str(e), "id": RATE_CARD_ID}
    except Exception as e:
        return {"ok": False, "reason": f"{type(e).__name__}: {str(e)[:200]}", "id": RATE_CARD_ID}


# ============================================================ Pro Racing Drivers, mensalidade, contrato, equipamento, corridas (09/09)
CONTRACT_DIR = os.path.join(os.environ.get("URACE_DIR", os.path.expanduser("~/.urace")), "contracts")
IMAGE_DIR = os.path.join(os.environ.get("URACE_DIR", os.path.expanduser("~/.urace")), "images")


mes_da_invoice = contrato.mes_da_invoice          # #340: mora no contrato (o contador do cliente usa a mesma regra)


def resumo_mensalidade(con, cid, meses=4):
    """Por mês: invoice da mensalidade (memo Academy), sessões usadas (tarefas de treino), restantes, e se falta invoice."""
    from datetime import date as _d
    hoje = _d.today()
    # #340: a mensalidade do mês pelo espelho mora no contrato (a invoice de uma sessão do site não é mensalidade)
    por_mes, invs = contrato.mensalidades_por_mes(con, cid)
    saida = []
    por_mes_n = contrato.sessoes_por_mes(con, cid)      # o número do contrato do card (#61); sem número, 4
    for k in range(meses):
        y, mo = hoje.year, hoje.month - k
        while mo <= 0:
            mo += 12; y -= 1
        mes = f"{y}-{mo:02d}"
        u = contrato.usadas(con, cid, mes)          # Asana + agendamentos do site (#61)
        usadas = u["asana"] + [{**x, "site": True} for x in u["site"]]
        inv = por_mes.get(mes)
        # #314: a vaga é a do pacote (a sessão extra e a paga no Stripe não ocupam vaga); "acima do contrato" é o que
        # passou do pacote mais as extras — a do Stripe e a avulsa não entram
        pac = contrato.usadas_do_pacote(con, cid, mes)
        acima = max(0, pac - por_mes_n) + sum(1 for x in u["site"] if x["coverage"] == "extra")
        saida.append({"month": mes, "invoice": ({"id": inv["id"], "doc_number": inv["doc_number"], "amount": inv["amount"], "balance": inv["balance"], "status": inv["status"], "memo": inv["memo"]} if inv else None),
                      "sessions_used": len(usadas), "sessions_left": max(0, por_mes_n - pac),
                      "sessions": usadas,
                      "sessions_over": acima, "closed": k > 0,
                      "needs_invoice": inv is None and (k == 0 or len(usadas) > 0)})
    ultimo = next((i for i in invs if not i.get("_sessao") and contrato.EH_MENSALIDADE.search((i.get("memo") or "") + " " + i.get("_linhas", ""))), None)
    return {"months": saida, "last_monthly_amount": ultimo["amount"] if ultimo else None, "last_monthly_memo": ultimo["memo"] if ultimo else None,
            "sessions_per_month": por_mes_n, "sessions_per_month_set": bool(um(con, "SELECT monthly_sessions FROM clients WHERE id=?", (cid,))["monthly_sessions"])}


@r.get("/clients/{cid}/monthly")
def client_monthly(cid: int, u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    if not um(con, "SELECT id FROM clients WHERE id=?", (cid,)):
        raise HTTPException(404, "Client not found.")
    r_ = resumo_mensalidade(con, cid)
    # #340 (dono, 19/10): o contador que o cliente vê (do pacote, mensalidade do mês, extras, em aberto) — aqui com
    # quais sessões e quais invoices estão em aberto; e o aviso do piloto pro sem mensalidade no card
    r_["counter"] = contrato.contador(con, cid, equipe=True)
    r_["pro_sem_mensal"] = contrato.pro_sem_mensal(con, cid)
    if not auth.pode(u["role"], "MANAGER"):                          # financeiro só para gerente+
        for m in r_["months"]:
            if m["invoice"]:
                m["invoice"] = {k: v for k, v in m["invoice"].items() if k not in ("amount", "balance")}
        r_["last_monthly_amount"] = None
        k = r_["counter"]
        if k:
            if k["monthly_invoice"]:
                k["monthly_invoice"] = {x: v for x, v in k["monthly_invoice"].items() if x not in ("amount", "balance")}
            k["extras"] = [{x: v for x, v in e.items() if x != "price"} for e in k["extras"]]
            k["open"]["amount"] = None
            k["open"]["invoices"] = [{x: v for x, v in i.items() if x != "balance"} for i in k["open"]["invoices"]]
    r_["contracts"] = todos(con, "SELECT c.*, us.name AS added_by_name FROM contracts c LEFT JOIN users us ON us.id=c.added_by WHERE c.client_id=? ORDER BY c.id DESC", (cid,))
    return r_


class EquipIn(BaseModel):
    plan_type: str | None = None          # monthly | daily
    pro_driver: bool | None = None
    chassis_id: int | None = None
    engine_id: int | None = None
    equipment_notes: str | None = None


@r.patch("/clients/{cid}/profile")
def client_profile(cid: int, dados: EquipIn, request: Request, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    if not um(con, "SELECT id FROM clients WHERE id=?", (cid,)):
        raise HTTPException(404, "Client not found.")
    campos = {}
    if dados.plan_type is not None:
        if dados.plan_type not in ("monthly", "daily", ""):
            raise HTTPException(400, "plan_type: monthly ou daily.")
        campos["plan_type"] = dados.plan_type or None
    if dados.pro_driver is not None:
        if not auth.pode(u["role"], "MANAGER"):
            raise HTTPException(403, "Só gerente marca Pro Racing Driver.")
        campos["pro_driver"] = 1 if dados.pro_driver else 0
    for k in ("chassis_id", "engine_id", "equipment_notes"):
        v = getattr(dados, k)
        if v is not None:
            campos[k] = v or None
    if not campos:
        return {"ok": True}
    sets = ", ".join(f"{k}=?" for k in campos)
    con.execute(f"UPDATE clients SET {sets}, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?", (*campos.values(), cid))
    auditar(con, "client.profile", f"user:{u['id']}", user_id=u["id"], entity_type="client", entity_id=cid, detail=campos, ip=auth._ip(request))
    return {"ok": True}


@r.get("/clients/{cid}/equipment")
def client_equipment(cid: int, u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    c = um(con, "SELECT chassis_id, engine_id, equipment_notes FROM clients WHERE id=?", (cid,))
    if not c:
        raise HTTPException(404, "Client not found.")
    ch = um(con, "SELECT * FROM catalog_chassis WHERE id=?", (c["chassis_id"],)) if c["chassis_id"] else None
    en = um(con, "SELECT * FROM catalog_engines WHERE id=?", (c["engine_id"],)) if c["engine_id"] else None
    parts = todos(con, "SELECT * FROM catalog_parts WHERE engine_id=? AND active=1 ORDER BY name", (c["engine_id"],)) if c["engine_id"] else []
    return {"chassis": ch, "engine": en, "parts": parts, "notes": c["equipment_notes"]}


# ---- contrato da Academy: upload ou achado no DocuSign
@r.post("/clients/{cid}/contract", status_code=201)
async def contract_upload(cid: int, request: Request, file: UploadFile = File(...), title: str = Form(""),
                          u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    if not um(con, "SELECT id FROM clients WHERE id=?", (cid,)):
        raise HTTPException(404, "Client not found.")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".pdf", ".png", ".jpg", ".jpeg"):
        raise HTTPException(400, "Contrato em PDF (ou imagem).")
    dados = await file.read()
    if not dados or len(dados) > MAX_BYTES:
        raise HTTPException(400, "Arquivo vazio ou maior que 25 MB.")
    os.makedirs(CONTRACT_DIR, exist_ok=True)
    caminho = os.path.join(CONTRACT_DIR, f"cliente-{cid}-{_slug(os.path.splitext(file.filename or 'contrato')[0])}{ext}")
    with open(caminho, "wb") as f:
        f.write(dados)
    os.chmod(caminho, 0o600)
    kid = inserir(con, "contracts", client_id=cid, kind="academy", source="upload", file_path=caminho, title=(title or file.filename or "Contrato")[:120], added_by=u["id"], status="completed")
    con.execute("UPDATE clients SET plan_type=COALESCE(plan_type,'monthly') WHERE id=?", (cid,))
    auditar(con, "contract.upload", f"user:{u['id']}", user_id=u["id"], entity_type="contract", entity_id=kid, detail={"client_id": cid, "nome": os.path.basename(caminho)}, ip=auth._ip(request))
    return {"id": kid}


@r.get("/contracts/{kid}/download")
def contract_download(kid: int, request: Request, u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    from fastapi.responses import FileResponse, Response
    k = um(con, "SELECT * FROM contracts WHERE id=?", (kid,))
    if not k:
        raise HTTPException(404, "Not found.")
    if k["file_path"] and os.path.isfile(k["file_path"]):
        return FileResponse(k["file_path"], filename=os.path.basename(k["file_path"]), headers={"Cache-Control": "no-store"})
    if k["envelope_id"]:
        try:
            pdf = modulo("docusign").baixar_documento_humano(k["envelope_id"])
        except NaoConectado as ex:
            raise HTTPException(503, f"DocuSign não conectado: {ex}")
        except Exception as ex:
            raise HTTPException(502, str(ex)[:300])
        auditar(con, "contract.download", f"user:{u['id']}", user_id=u["id"], entity_type="contract", entity_id=kid, ip=auth._ip(request))
        return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="contrato-{kid}.pdf"', "Cache-Control": "no-store"})
    raise HTTPException(404, "Contrato sem arquivo nem envelope.")


def _contratos_do_docusign(con, c):
    """Envelopes do cliente cujo assunto fala de Academy/contract viram contratos (fonte DocuSign)."""
    email = (c["email"] or "").lower()
    if not email:
        return 0
    n = 0
    try:
        r = chamar("docusign", "docusign_waivers_de", email=email)
    except Exception:
        return 0
    for grupo in ("waiver_valida", "em_aberto", "historico"):
        for e in r.get(grupo) or []:
            assunto = (e.get("assunto") or "").lower()
            if not re.search(r"academy|contract|contrato|program", assunto) or re.search(r"waiver", assunto):
                continue
            if um(con, "SELECT 1 FROM contracts WHERE envelope_id=?", (e["envelopeId"],)):
                continue
            inserir(con, "contracts", client_id=c["id"], kind="academy", source="docusign", envelope_id=e["envelopeId"], status=e.get("status"),
                    signed_at=e.get("concluido_em"), title=e.get("assunto"))
            if e.get("status") == "completed":
                con.execute("UPDATE clients SET plan_type=COALESCE(plan_type,'monthly') WHERE id=?", (c["id"],))
            n += 1
    return n


# ---- catálogo de equipamento (editável)
@r.get("/catalog")
def catalog(u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    return {"chassis": todos(con, "SELECT * FROM catalog_chassis ORDER BY active DESC, brand, model"),
            "engines": todos(con, "SELECT * FROM catalog_engines ORDER BY active DESC, brand, model"),
            "parts": todos(con, "SELECT p.*, e.brand AS engine_brand, e.model AS engine_model FROM catalog_parts p LEFT JOIN catalog_engines e ON e.id=p.engine_id ORDER BY p.engine_id, p.name")}


class ChassisIn(BaseModel):
    brand: str | None = None
    model: str | None = None
    size: str | None = None
    tire_front: str | None = None
    tire_rear: str | None = None
    notes: str | None = None
    active: bool | None = None


class EngineIn(BaseModel):
    brand: str | None = None
    model: str | None = None
    stroke: str | None = None
    category: str | None = None
    notes: str | None = None
    active: bool | None = None


class PartIn(BaseModel):
    engine_id: int | None = None
    name: str | None = None
    part_number: str | None = None
    price: float | None = None
    notes: str | None = None
    active: bool | None = None


_TABELAS = {"chassis": ("catalog_chassis", ChassisIn), "engines": ("catalog_engines", EngineIn), "parts": ("catalog_parts", PartIn)}


def _catalogo_upsert(con, kind, dados, cid, u, request):
    tabela, _ = _TABELAS[kind]
    campos = {k: (1 if v else 0) if k == "active" else v for k, v in dados.model_dump().items() if v is not None}
    if cid is None:
        if kind == "chassis" and not campos.get("brand"):
            raise HTTPException(400, "Marca é obrigatória.")
        if kind == "engines" and not (campos.get("brand") and campos.get("model")):
            raise HTTPException(400, "Marca e modelo são obrigatórios.")
        if kind == "parts" and not (campos.get("name") and campos.get("engine_id")):
            raise HTTPException(400, "Nome e motor são obrigatórios.")
        cid = inserir(con, tabela, **campos)
    else:
        if not um(con, f"SELECT id FROM {tabela} WHERE id=?", (cid,)):
            raise HTTPException(404, "Not found.")
        if campos:
            con.execute(f"UPDATE {tabela} SET " + ", ".join(f"{k}=?" for k in campos) + " WHERE id=?", (*campos.values(), cid))
    auditar(con, "catalog.save", f"user:{u['id']}", user_id=u["id"], entity_type=tabela, entity_id=cid, detail=campos, ip=auth._ip(request))
    return {"id": cid}


@r.post("/catalog/chassis", status_code=201)
def chassis_create(dados: ChassisIn, request: Request, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    return _catalogo_upsert(con, "chassis", dados, None, u, request)


@r.patch("/catalog/chassis/{cid}")
def chassis_patch(cid: int, dados: ChassisIn, request: Request, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    return _catalogo_upsert(con, "chassis", dados, cid, u, request)


@r.post("/catalog/engines", status_code=201)
def engine_create(dados: EngineIn, request: Request, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    return _catalogo_upsert(con, "engines", dados, None, u, request)


@r.patch("/catalog/engines/{cid}")
def engine_patch(cid: int, dados: EngineIn, request: Request, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    return _catalogo_upsert(con, "engines", dados, cid, u, request)


@r.post("/catalog/parts", status_code=201)
def part_create(dados: PartIn, request: Request, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    return _catalogo_upsert(con, "parts", dados, None, u, request)


@r.patch("/catalog/parts/{cid}")
def part_patch(cid: int, dados: PartIn, request: Request, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    return _catalogo_upsert(con, "parts", dados, cid, u, request)


@r.post("/catalog/{kind}/{cid}/image")
async def catalog_image(kind: str, cid: int, request: Request, file: UploadFile = File(...), u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    if kind not in ("chassis", "engines"):
        raise HTTPException(404, "Not found.")
    tabela = _TABELAS[kind][0]
    if not um(con, f"SELECT id FROM {tabela} WHERE id=?", (cid,)):
        raise HTTPException(404, "Not found.")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(400, "Imagem em PNG, JPG ou WEBP.")
    dados = await file.read()
    if not dados or len(dados) > 5 * 1024 * 1024:
        raise HTTPException(400, "Imagem vazia ou maior que 5 MB.")
    from command_center.providers import imagem
    try:
        dados, ext = imagem.comprimir(dados)
    except imagem.ImagemInvalida:
        raise HTTPException(400, "Essa imagem não abriu. Tente outra.")
    os.makedirs(IMAGE_DIR, exist_ok=True)
    caminho = os.path.join(IMAGE_DIR, f"{kind}-{cid}{ext}")
    with open(caminho, "wb") as f:
        f.write(dados)
    con.execute(f"UPDATE {tabela} SET image_path=? WHERE id=?", (caminho, cid))
    auditar(con, "catalog.image", f"user:{u['id']}", user_id=u["id"], entity_type=tabela, entity_id=cid, ip=auth._ip(request))
    return {"ok": True}


@r.get("/catalog/{kind}/{cid}/image")
def catalog_image_get(kind: str, cid: int, u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    from fastapi.responses import FileResponse
    if kind not in ("chassis", "engines"):
        raise HTTPException(404, "Not found.")
    c = um(con, f"SELECT image_path FROM {_TABELAS[kind][0]} WHERE id=?", (cid,))
    if not c or not c["image_path"] or not os.path.isfile(c["image_path"]):
        raise HTTPException(404, "Sem imagem.")
    return FileResponse(c["image_path"], headers={"Cache-Control": "private, max-age=3600"})


# ---- corridas e convites
def _corrida_out(con, rc):
    rc["invited"] = todos(con, """SELECT i.*, c.name, c.pilot_name, cmd.status AS estimate_status FROM race_invites i JOIN clients c ON c.id=i.client_id
                                  LEFT JOIN ai_commands cmd ON cmd.id=i.estimate_cmd WHERE i.race_id=? ORDER BY i.id""", (rc["id"],))
    rc["task"] = None
    if rc.get("task_id"):
        t = um(con, "SELECT id, title, status, due_on, section, subtasks_total, subtasks_done, assignee, synced_at FROM tasks WHERE id=?", (rc["task_id"],))
        if t:
            t["links"] = _links(con, "task", t["id"])
            rc["task"] = t
    return rc


@r.get("/races")
def races(all: bool = False, client_id: int | None = None, u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    """Calendário de corridas: a coluna RACES do Asana (uma por tarefa) mais as manuais."""
    where, p = ["1=1"], []
    if not all:
        where.append("r.active=1")
    if client_id:
        where.append("r.id IN (SELECT race_id FROM race_invites WHERE client_id=?)"); p.append(client_id)
    rows = todos(con, f"SELECT r.*, (SELECT COUNT(*) FROM race_invites i WHERE i.race_id=r.id) AS invites FROM races r WHERE {' AND '.join(where)} ORDER BY COALESCE(r.date_start,'9999')", p)
    return [_corrida_out(con, rc) for rc in rows]


def _comenta_na_corrida(con, rid, texto):
    """Espelha no Asana o convite/confirmação (comentário na tarefa da corrida). Sem Asana, segue em silêncio."""
    r = um(con, "SELECT task_id FROM races WHERE id=?", (rid,))
    if not r or not r["task_id"]:
        return None
    l = um(con, "SELECT external_id FROM entity_links WHERE entity_type='task' AND entity_id=? AND system='asana'", (r["task_id"],))
    if not l:
        return None
    try:
        return modulo("asana").comentar_humano(l["external_id"], texto)
    except Exception as e:
        return {"erro": f"{type(e).__name__}: {str(e)[:200]}"}


class RaceIn(BaseModel):
    name: str | None = None
    series: str | None = None
    track: str | None = None
    city: str | None = None
    date_start: str | None = None
    date_end: str | None = None
    notes: str | None = None
    active: bool | None = None
    local_only: bool | None = None


@r.post("/races", status_code=201)
def race_create(dados: RaceIn, request: Request, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    """Nova corrida = tarefa criada do modelo oficial "New Race [Race + City/Track]" na coluna
    RACES do Asana (vem com as subtarefas do modelo). Sem Asana: 503, a não ser que
    `local_only` (só no painel)."""
    if not (dados.name or "").strip():
        raise HTTPException(400, "Nome da corrida é obrigatório.")
    campos = {k: v for k, v in dados.model_dump().items() if v is not None and k not in ("active", "local_only")}
    task_id = None
    if not dados.local_only:
        try:
            m = modulo("asana")
            secoes = chamar("asana", "asana_secoes", projeto_gid=PROJETO_URACE)
            races_gid = next((x["gid"] for x in secoes if x["nome"].strip().upper() == "RACES"), None)
            if not races_gid:
                raise HTTPException(409, "Coluna RACES não encontrada no quadro U-RACE.")
            local = " / ".join(x for x in (dados.city, dados.track) if x)
            nome = f"{dados.name.strip()}" + (f" [{local}]" if local else "")
            notas = "\n".join(x for x in ((f"Série: {dados.series}" if dados.series else ""), (f"Pista: {dados.track}" if dados.track else ""),
                                          (f"Cidade: {dados.city}" if dados.city else ""), (f"Fim: {dados.date_end}" if dados.date_end else ""), dados.notes or "") if x)
            novo = m.criar_do_modelo_humano(m.MODELO_CORRIDA, nome, secao_gid=races_gid, notas=notas or None, vence_em=dados.date_start)
            gid = novo.get("gid") or (novo.get("tarefa") or {}).get("gid")
            if gid:
                task_id, _ = sy._grava_tarefa(con, gid, dict(client_id=None, title=nome, project="U-RACE", section="RACES", section_gid=races_gid,
                                                             status="open", due_on=dados.date_start, subtasks_total=novo.get("subtarefas"), subtasks_done=0, synced_at=agora()))
            campos["name"] = nome
        except HTTPException:
            raise
        except NaoConectado as e:
            raise HTTPException(503, f"Asana não conectado: {e}. Marque 'só no painel' para criar sem o Asana.")
        except Exception as e:
            raise HTTPException(502, f"Asana: {str(e)[:300]}")
    rid = inserir(con, "races", source="asana" if task_id else "manual", task_id=task_id, **campos)
    auditar(con, "race.create", f"user:{u['id']}", user_id=u["id"], entity_type="race", entity_id=rid, detail={**campos, "task_id": task_id}, ip=auth._ip(request))
    return {"id": rid, "task_id": task_id}


@r.patch("/races/{rid}")
def race_patch(rid: int, dados: RaceIn, request: Request, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    if not um(con, "SELECT id FROM races WHERE id=?", (rid,)):
        raise HTTPException(404, "Not found.")
    campos = {k: (1 if v else 0) if k == "active" else v for k, v in dados.model_dump().items() if v is not None}
    if campos:
        con.execute("UPDATE races SET " + ", ".join(f"{k}=?" for k in campos) + " WHERE id=?", (*campos.values(), rid))
    auditar(con, "race.update", f"user:{u['id']}", user_id=u["id"], entity_type="race", entity_id=rid, detail=campos, ip=auth._ip(request))
    return {"ok": True}


class ConviteIn(BaseModel):
    client_id: int


@r.post("/races/{rid}/invite", status_code=201)
def race_invite(rid: int, dados: ConviteIn, request: Request, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    if not um(con, "SELECT id FROM races WHERE id=?", (rid,)):
        raise HTTPException(404, "Race not found.")
    c = um(con, "SELECT id, pro_driver FROM clients WHERE id=?", (dados.client_id,))
    if not c:
        raise HTTPException(404, "Client not found.")
    if um(con, "SELECT 1 FROM race_invites WHERE race_id=? AND client_id=?", (rid, dados.client_id)):
        raise HTTPException(409, "Já convidado.")
    iid = inserir(con, "race_invites", race_id=rid, client_id=dados.client_id, invited_by=u["id"])
    piloto = um(con, "SELECT COALESCE(pilot_name, name) AS p FROM clients WHERE id=?", (dados.client_id,))["p"]
    _comenta_na_corrida(con, rid, f"[Command Center] Convidado: {piloto} — aguardando confirmação.")
    auditar(con, "race.invite", f"user:{u['id']}", user_id=u["id"], entity_type="race", entity_id=rid, detail={"client_id": dados.client_id}, ip=auth._ip(request))
    return {"id": iid}


class ConviteStatusIn(BaseModel):
    status: str


@r.patch("/invites/{iid}")
def invite_status(iid: int, dados: ConviteStatusIn, request: Request, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    if dados.status not in ("invited", "confirmed", "declined", "done"):
        raise HTTPException(400, "status inválido.")
    if not um(con, "SELECT id FROM race_invites WHERE id=?", (iid,)):
        raise HTTPException(404, "Not found.")
    con.execute("UPDATE race_invites SET status=? WHERE id=?", (dados.status, iid))
    i = um(con, "SELECT i.race_id, COALESCE(c.pilot_name, c.name) AS p FROM race_invites i JOIN clients c ON c.id=i.client_id WHERE i.id=?", (iid,))
    rotulo = {"confirmed": "CONFIRMADO", "declined": "não vai", "done": "correu", "invited": "convidado, aguardando confirmação"}.get(dados.status, dados.status)
    _comenta_na_corrida(con, i["race_id"], f"[Command Center] {i['p']}: {rotulo}.")
    auditar(con, "race.invite.status", f"user:{u['id']}", user_id=u["id"], entity_type="race_invite", entity_id=iid, detail={"status": dados.status}, ip=auth._ip(request))
    return {"ok": True}


def _estimativa_thread(iid, cid_cmd, texto, session_key, user_id):
    from command_center.api import ia
    ia._executa(cid_cmd, texto, session_key, user_id)
    con = conectar()
    try:
        c = um(con, "SELECT status, output, error FROM ai_commands WHERE id=?", (cid_cmd,))
        con.execute("UPDATE race_invites SET estimate_text=? WHERE id=?", ((c["output"] if c and c["status"] == "DONE" else f"falhou: {c['error'] if c else '?'}")[:4000], iid))
    finally:
        con.close()


@r.post("/invites/{iid}/estimate", status_code=202)
def invite_estimate(iid: int, request: Request, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    """Prévia de custo da corrida para este piloto: a IA lê a aba Racing team da Rate Card e o equipamento. Não cria nada no QuickBooks."""
    from command_center.api import ia, motor
    i = um(con, "SELECT i.*, r.name AS race, r.series, r.track, r.city, r.date_start, r.date_end, r.notes AS race_notes FROM race_invites i JOIN races r ON r.id=i.race_id WHERE i.id=?", (iid,))
    if not i:
        raise HTTPException(404, "Not found.")
    c = um(con, "SELECT * FROM clients WHERE id=?", (i["client_id"],))
    eq = client_equipment(i["client_id"], u, con)
    prompt = (f"PRÉVIA DE CUSTO (não crie nada no QuickBooks, não envie nada): quanto custaria para o piloto {c['pilot_name'] or c['name']} "
              f"(responsável {c['name']}, plano {c['plan_type'] or '?'}/{c['monthly_plan'] or 'sem mensal'}) correr em '{i['race']}' "
              f"({i['series'] or ''} {i['track'] or ''} {i['city'] or ''} {i['date_start'] or ''}–{i['date_end'] or ''}). "
              f"Equipamento: chassi {json.dumps(eq['chassis'], ensure_ascii=False) if eq['chassis'] else 'não informado'}; motor {json.dumps(eq['engine'], ensure_ascii=False) if eq['engine'] else 'não informado'}. "
              "Use a aba 'Racing team' da Rate Card (sheets_ler) e, se a corrida for fora do Orlando Kart Center, some hotel/comida/transporte conforme a planilha. "
              "Responda com uma tabela curta: item, quantidade, unitário, total; e o total geral. Diga o que assumiu. ACAO: nenhuma."
              + motor.aprendizados(con, c["id"]))
    session_key = f"agent:{ia.AGENTE}:estimativa-{iid}"
    cmd = inserir(con, "ai_commands", user_id=u["id"], text=prompt, session_key=session_key)
    con.execute("UPDATE race_invites SET estimate_cmd=?, estimate_text=NULL WHERE id=?", (cmd, iid))
    auditar(con, "race.estimate", f"user:{u['id']}", user_id=u["id"], entity_type="race_invite", entity_id=iid, detail={"command_id": cmd}, ip=auth._ip(request))
    threading.Thread(target=_estimativa_thread, args=(iid, cmd, prompt, session_key, u["id"]), daemon=True).start()
    return {"command_id": cmd}
