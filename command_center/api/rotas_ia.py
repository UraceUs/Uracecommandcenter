"""Rotas da IA que age (#436: saíram do rotas.py, sem mudar rota): instrução, memória,
eventos e regras; fontes de contexto (planilhas, links e arquivos).
"""
import os
import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from command_center.api import auth
from command_center.api.rotas import BASE
from command_center.db import agora, auditar, get_db, inserir, todos, um
from command_center.providers import NaoConectado, chamar

r = APIRouter(prefix=BASE)


# ============================================================ IA que age: instrução, memória, eventos, regras
from command_center.api import motor  # noqa: E402


class InstruirIn(BaseModel):
    key: str
    text: str
    remember: bool = True
    title: str | None = None
    why: str | None = None
    client_id: int | None = None
    entity_type: str | None = None
    entity_id: str | None = None


@r.post("/needs-attention/instruct", status_code=202)
def attention_instruct(dados: InstruirIn, request: Request, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    """Balão do item: manda a instrução para o agente com o contexto do item; com remember, vira memória."""
    texto = (dados.text or "").strip()
    if not texto or len(texto) > 4000:
        raise HTTPException(400, "Escreva a instrução (até 4000 caracteres).")
    item = {"title": dados.title, "why": dados.why, "client_id": dados.client_id,
            "entity": {"type": dados.entity_type, "id": dados.entity_id}}
    cid = motor.instruir(con, u["id"], dados.key, texto, item, dados.remember)
    return {"command_id": cid, "remembered": bool(dados.remember)}


class InstruirTarefaIn(BaseModel):
    text: str
    remember: bool = False


@r.post("/tasks/{tid}/instruct", status_code=202)
def task_instruct(tid: int, dados: InstruirTarefaIn, request: Request, u=Depends(auth.exige("OPERATOR")),
                  con: sqlite3.Connection = Depends(get_db)):
    """Caixa da IA dentro da tarefa (dono, 16/09): a instrução vai com o gid, título,
    cliente, subtarefas e descrição desta tarefa, e a IA age nela — e só nela."""
    texto = (dados.text or "").strip()
    if not texto or len(texto) > 4000:
        raise HTTPException(400, "Escreva a instrução (até 4000 caracteres).")
    cid = motor.instruir_tarefa(con, u["id"], tid, texto, dados.remember)
    if cid is None:
        raise HTTPException(404, "Task not found.")
    return {"command_id": cid, "remembered": bool(dados.remember)}


SO_HUMANO = [
    ("Kommo", "responder no chat, mover etapa, marcar tag, anotar, atribuir — pelo painel"),
    ("Clientes", "tornar ★ Pro, equipamento, contrato, criar cliente à mão"),
    ("Administração", "aprovar e rejeitar ações da IA, políticas, usuários, auditoria imutável"),
    ("Gmail", "confirmar o manual dos marcadores; criar filtros nativos; mover por clique"),
    ("QuickBooks", "escolher quais invoices têm lembrete recorrente (ligar/desligar); conectar a conta"),
    ("DocuSign", "enviar waiver pelo botão; escolher o PDF que substitui um modelo"),
]


@r.get("/ai/capabilities")
def ai_capabilities(u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    """O que a IA pode fazer, lido de onde vive: as ferramentas registradas nos MCPs, a tabela de
    políticas, as ações do painel e as regras de automação. Nunca desatualiza (dono, 16/09)."""
    import importlib
    from command_center.api import acoes, acoes_painel
    politicas = {p["action"]: p for p in todos(con, "SELECT action, policy, note FROM action_policies")}
    ferramentas = []
    for sistema, modulo_ in (("asana", "asana_mcp"), ("docusign", "docusign_mcp"), ("gmail", "gmail_mcp"), ("quickbooks", "quickbooks_mcp"), ("kommo", "kommo_mcp")):
        try:
            m = importlib.import_module(modulo_)
        except Exception as e:
            ferramentas.append({"system": sistema, "name": f"({modulo_})", "description": f"não carregou: {e}", "policy": None, "kind": "erro"}); continue
        for nome, (desc, _schema, _fn) in getattr(m, "srv")._ferramentas.items():
            leitura = acoes.eh_consulta(nome)
            pol = politicas.get(nome)
            ferramentas.append({"system": sistema, "name": nome, "description": desc, "kind": "leitura" if leitura else "escrita",
                                "policy": "SAFE" if leitura else (pol["policy"] if pol else "REQUIRES_CONFIRMATION"), "note": (pol or {}).get("note"), "classified": bool(pol) or leitura})
    for a in acoes_painel.descrever_todas():
        pol = politicas.get(a["name"])
        ferramentas.append({"system": "painel", "name": a["name"], "description": a["description"], "kind": "escrita",
                            "policy": pol["policy"] if pol else "REQUIRES_CONFIRMATION", "note": (pol or {}).get("note"), "classified": bool(pol)})
    bloqueadas = [{"name": a, "note": p["note"]} for a, p in politicas.items() if p["policy"] == "BLOCKED"]
    regras = todos(con, "SELECT name, enabled, trigger, schedule, last_run_at, last_result FROM automation_rules ORDER BY id")
    return {"tools": ferramentas, "blocked": bloqueadas, "rules": regras, "human_only": [{"area": a, "what": w} for a, w in SO_HUMANO]}


@r.get("/ai/learnings")
def learnings(all: bool = False, u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    sql = "SELECT l.*, us.name AS created_by_name FROM ai_learnings l LEFT JOIN users us ON us.id=l.created_by"
    if not all:
        sql += " WHERE l.active=1"
    return todos(con, sql + " ORDER BY l.id DESC LIMIT 300")


class AprenderIn(BaseModel):
    text: str
    client_id: int | None = None
    entity_type: str | None = None


@r.post("/ai/learnings", status_code=201)
def learning_create(dados: AprenderIn, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    if not (dados.text or "").strip():
        raise HTTPException(400, "Texto vazio.")
    return {"id": motor.aprender(con, dados.text, u["id"], dados.client_id, dados.entity_type)}


@r.post("/ai/learnings/{lid}/toggle")
def learning_toggle(lid: int, request: Request, u=Depends(auth.exige("MANAGER")), con: sqlite3.Connection = Depends(get_db)):
    l = um(con, "SELECT * FROM ai_learnings WHERE id=?", (lid,))
    if not l:
        raise HTTPException(404, "Not found.")
    con.execute("UPDATE ai_learnings SET active=? WHERE id=?", (0 if l["active"] else 1, lid))
    auditar(con, "ai.learning.toggle", f"user:{u['id']}", user_id=u["id"], entity_type="ai_learning", entity_id=lid, detail={"active": not l["active"]}, ip=auth._ip(request))
    return {"ok": True, "active": not l["active"]}


@r.get("/ai/events")
def ai_events(limit: int = 100, u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    return todos(con, """SELECT e.*, c.name AS client_name, c.pilot_name, cmd.status AS command_status,
                                (SELECT COUNT(*) FROM ai_actions a WHERE a.command_id=e.command_id) AS actions
                         FROM ai_events e LEFT JOIN clients c ON c.id=e.client_id LEFT JOIN ai_commands cmd ON cmd.id=e.command_id
                         ORDER BY e.id DESC LIMIT ?""", (max(1, min(limit, 500)),))


@r.post("/ai/events/process", status_code=202)
def ai_events_process(u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    return {"disparados": motor.processar_eventos(con, u["id"])}


@r.get("/automation/rules")
def automation_rules(u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    return todos(con, "SELECT * FROM automation_rules ORDER BY id")


class RegraIn(BaseModel):
    enabled: bool


@r.put("/automation/rules/{name}")
def automation_rule_put(name: str, dados: RegraIn, request: Request, u=Depends(auth.exige("ADMIN")), con: sqlite3.Connection = Depends(get_db)):
    if not um(con, "SELECT id FROM automation_rules WHERE name=?", (name,)):
        raise HTTPException(404, "Unknown rule.")
    con.execute("UPDATE automation_rules SET enabled=? WHERE name=?", (1 if dados.enabled else 0, name))
    auditar(con, "automation.rule", f"user:{u['id']}", user_id=u["id"], entity_type="automation_rule", entity_id=name, detail={"enabled": dados.enabled}, ip=auth._ip(request))
    return {"ok": True}


# ============================================================ Fontes de contexto da IA (Integrações → Planilhas / Arquivos)
from fastapi import File, Form, UploadFile  # noqa: E402

CONTEXT_DIR = os.path.join(os.environ.get("URACE_DIR", os.path.expanduser("~/.urace")), "context")
EXT_OK = {".pdf", ".txt", ".md", ".csv", ".json", ".docx", ".xlsx", ".png", ".jpg", ".jpeg"}
MAX_BYTES = 25 * 1024 * 1024


def _workspace_contexto():
    agente = os.environ.get("OPENCLAW_AGENT", "urace-admin")
    return os.path.expanduser(f"~/.openclaw/workspace/{agente}/contexto")


def _sheet_id(url):
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]{20,})", url or "")
    return m.group(1) if m else ((url or "").strip() if re.fullmatch(r"[A-Za-z0-9_-]{20,}", (url or "").strip()) else None)


def _slug(nome):
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", nome.strip()).strip("-.")[:80] or "arquivo"
    return base


def _extrair_texto(caminho, mime):
    """PDF → texto (pypdf, se instalado). txt/md/csv/json → o próprio arquivo. Outros: sem texto."""
    ext = os.path.splitext(caminho)[1].lower()
    if ext in (".txt", ".md", ".csv", ".json"):
        return caminho
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            partes = []
            for pg in PdfReader(caminho).pages[:200]:
                partes.append(pg.extract_text() or "")
            txt = "\n\n".join(partes).strip()
            if txt:
                alvo = caminho + ".txt"
                with open(alvo, "w", encoding="utf-8") as f:
                    f.write(txt)
                return alvo
        except Exception:
            return None
    return None


def _publicar_no_workspace(src):
    """Copia o arquivo (e o texto extraído) para o workspace do agente: é lá que ele lê."""
    import shutil
    try:
        dst_dir = _workspace_contexto()
        os.makedirs(dst_dir, exist_ok=True)
        for pth in (src["path"], src["text_path"]):
            if pth and os.path.isfile(pth):
                shutil.copy2(pth, os.path.join(dst_dir, os.path.basename(pth)))
        return True
    except Exception:
        return False


@r.get("/context")
def context_list(u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    rows = todos(con, "SELECT c.*, us.name AS added_by_name FROM context_sources c LEFT JOIN users us ON us.id=c.added_by ORDER BY c.kind, c.id")
    for c in rows:
        c["workspace_name"] = os.path.basename(c["text_path"] or c["path"] or "") if c["kind"] == "file" else None
    return rows


class PlanilhaIn(BaseModel):
    title: str
    url: str
    description: str | None = None
    sheet_range: str | None = None


@r.post("/context/sheet", status_code=201)
def context_sheet(dados: PlanilhaIn, request: Request, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    sid = _sheet_id(dados.url)
    if not sid:
        raise HTTPException(400, "Cole o link da planilha do Google (docs.google.com/spreadsheets/d/…).")
    if not (dados.title or "").strip():
        raise HTTPException(400, "Dê um título.")
    if um(con, "SELECT id FROM context_sources WHERE sheet_id=?", (sid,)):
        raise HTTPException(409, "Essa planilha já está cadastrada.")
    cid = inserir(con, "context_sources", kind="sheet", title=dados.title.strip()[:120], description=(dados.description or "").strip()[:500] or None,
                  url=f"https://docs.google.com/spreadsheets/d/{sid}", sheet_id=sid, sheet_range=(dados.sheet_range or "").strip()[:60] or None, added_by=u["id"])
    auditar(con, "context.add", f"user:{u['id']}", user_id=u["id"], entity_type="context", entity_id=cid, detail={"kind": "sheet", "title": dados.title}, ip=auth._ip(request))
    return {"id": cid, **_checar(con, cid)}


class LinkIn(BaseModel):
    title: str
    url: str
    description: str | None = None


@r.post("/context/link", status_code=201)
def context_link(dados: LinkIn, request: Request, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    if not (dados.url or "").startswith("http"):
        raise HTTPException(400, "Link inválido.")
    cid = inserir(con, "context_sources", kind="link", title=dados.title.strip()[:120], description=(dados.description or "").strip()[:500] or None,
                  url=dados.url.strip()[:500], added_by=u["id"])
    auditar(con, "context.add", f"user:{u['id']}", user_id=u["id"], entity_type="context", entity_id=cid, detail={"kind": "link", "title": dados.title}, ip=auth._ip(request))
    return {"id": cid}


@r.post("/context/file", status_code=201)
async def context_file(request: Request, file: UploadFile = File(...), title: str = Form(""), description: str = Form(""),
                       u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in EXT_OK:
        raise HTTPException(400, f"Tipo não aceito ({ext or 'sem extensão'}). Aceitos: {', '.join(sorted(EXT_OK))}.")
    dados = await file.read()
    if not dados:
        raise HTTPException(400, "Arquivo vazio.")
    if len(dados) > MAX_BYTES:
        raise HTTPException(413, "Arquivo maior que 25 MB.")
    os.makedirs(CONTEXT_DIR, exist_ok=True)
    nome = _slug(os.path.splitext(file.filename or "arquivo")[0]) + ext
    caminho = os.path.join(CONTEXT_DIR, nome)
    n = 1
    while os.path.exists(caminho):
        n += 1; caminho = os.path.join(CONTEXT_DIR, f"{_slug(os.path.splitext(file.filename or 'arquivo')[0])}-{n}{ext}")
    with open(caminho, "wb") as f:
        f.write(dados)
    os.chmod(caminho, 0o600)
    texto = _extrair_texto(caminho, file.content_type)
    cid = inserir(con, "context_sources", kind="file", title=(title or file.filename or nome).strip()[:120], description=(description or "").strip()[:500] or None,
                  path=caminho, text_path=texto, mime=file.content_type, size=len(dados), added_by=u["id"])
    ok = _publicar_no_workspace({"path": caminho, "text_path": texto})
    con.execute("UPDATE context_sources SET last_check_at=?, last_check_ok=?, last_check_msg=? WHERE id=?",
                (agora(), 1 if ok else 0, ("no workspace do agente" + ("" if texto else "; sem texto extraído — a IA só vê o nome")) if ok else "não consegui copiar para o workspace do agente", cid))
    auditar(con, "context.add", f"user:{u['id']}", user_id=u["id"], entity_type="context", entity_id=cid,
            detail={"kind": "file", "nome": os.path.basename(caminho), "bytes": len(dados), "texto": bool(texto)}, ip=auth._ip(request))
    return {"id": cid, "name": os.path.basename(caminho), "text": bool(texto), "workspace": ok}


def _checar(con, cid):
    c = um(con, "SELECT * FROM context_sources WHERE id=?", (cid,))
    ok, msg = False, ""
    try:
        if c["kind"] == "sheet":
            r = chamar("gmail", "sheets_ler", conta="urace", planilha_id=c["sheet_id"], intervalo=c["sheet_range"] or "A1:D5")
            linhas = r.get("linhas", [])
            ok, msg = True, f"{len(linhas)} linha(s) lidas; primeira: {(linhas[0] if linhas else [])[:4]}"
        elif c["kind"] == "file":
            ok = _publicar_no_workspace(c)
            msg = "no workspace do agente" if ok else "não consegui copiar para o workspace do agente"
        else:
            ok, msg = True, "link registrado (a IA recebe o endereço)"
    except NaoConectado as e:
        msg = f"não conectado: {e}"
    except Exception as e:
        msg = f"{type(e).__name__}: {str(e)[:200]}"
    con.execute("UPDATE context_sources SET last_check_at=?, last_check_ok=?, last_check_msg=? WHERE id=?", (agora(), 1 if ok else 0, msg[:300], cid))
    return {"ok": ok, "msg": msg}


@r.post("/context/{cid}/check")
def context_check(cid: int, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    if not um(con, "SELECT id FROM context_sources WHERE id=?", (cid,)):
        raise HTTPException(404, "Not found.")
    return _checar(con, cid)


@r.post("/context/{cid}/toggle")
def context_toggle(cid: int, request: Request, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    c = um(con, "SELECT * FROM context_sources WHERE id=?", (cid,))
    if not c:
        raise HTTPException(404, "Not found.")
    con.execute("UPDATE context_sources SET active=? WHERE id=?", (0 if c["active"] else 1, cid))
    auditar(con, "context.toggle", f"user:{u['id']}", user_id=u["id"], entity_type="context", entity_id=cid, detail={"active": not c["active"]}, ip=auth._ip(request))
    return {"ok": True, "active": not c["active"]}


@r.get("/context/{cid}/download")
def context_download(cid: int, u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    from fastapi.responses import FileResponse
    c = um(con, "SELECT * FROM context_sources WHERE id=? AND kind='file'", (cid,))
    if not c or not c["path"] or not os.path.isfile(c["path"]):
        raise HTTPException(404, "Arquivo não encontrado.")
    return FileResponse(c["path"], filename=os.path.basename(c["path"]), headers={"Cache-Control": "no-store"})
