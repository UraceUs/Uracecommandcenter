"""Suits (Alpha Line) — as rotas (#153). As regras moram em `providers/suits.py`.

**Quem pode o quê:** ver, registrar, anotar e avançar etapa é OPERATOR (é quem atende o
cliente); importar do Asana, editar o modelo do e-mail e os fornecedores é MANAGER.
Foto de cada nota fica em ~/.urace/suits (WebP, ≤ 1600 px, sem EXIF) e só sai com sessão.
"""
import json
import os
import re
import sqlite3
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel

from command_center.api import auth
from command_center.api.cache_api import paginar
from command_center.db import agora, atualizar, auditar, get_db, inserir, todos, um
from command_center.providers import suits

r = APIRouter(prefix="/ops/api/suits", tags=["suits"])
IMAGEM_MAX = 8 * 1024 * 1024
ARQUIVO_MAX = 25 * 1024 * 1024       # #447: o arquivo da nota que não é imagem (PDF, planilha, arte, vídeo curto)
TIPOS_IMAGEM = {"image/png", "image/jpeg", "image/webp"}


def pasta_imagens():
    caminho = os.path.join(os.environ.get("URACE_DIR", os.path.expanduser("~/.urace")), "suits")
    os.makedirs(caminho, exist_ok=True)
    return caminho


def _aud(con, request, u, evento, eid, detalhe=None, tipo="suit_order"):
    auditar(con, evento, f"user:{u['id']}", user_id=u["id"], entity_type=tipo, entity_id=eid, detail=detalhe,
            ip=auth._ip(request) if request else None)


def _pedido(con, pid):
    p = suits.detalhe(con, pid)
    if not p:
        raise HTTPException(404, "Pedido não encontrado.")
    return p


def _invalido(e):
    return HTTPException(400, str(e))


# ------------------------------------------------------------------ o básico
@r.get("/etapas")
def etapas(u=Depends(auth.exige("OPERATOR"))):
    """O que a tela precisa para montar o formulário: etapas, medidas e campos de design."""
    return {"etapas": [{"codigo": c, "nome": n, "descricao": d} for c, n, d in suits.ETAPAS],
            "medidas": [{"chave": k, "numero": num, "nome": nome, "tipo": t} for k, num, nome, t in suits.MEDIDAS],
            "design": [{"chave": k, "nome": n} for k, n in suits.DESIGN],
            "transicoes": {k: list(v) for k, v in suits.TRANSICOES.items()}, "so_da_equipe": list(suits.SO_DA_EQUIPE)}


@r.get("/resumo")
def resumo(con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    por = {x["status"]: x["n"] for x in todos(con, """SELECT status, COUNT(*) AS n FROM suit_orders
                                                      WHERE closed=0 AND discarded_at IS NULL AND is_test=0 GROUP BY status""")}
    return {"por_etapa": por, "abertos": sum(por.values()),
            "fechados": um(con, "SELECT COUNT(*) AS n FROM suit_orders WHERE closed=1 AND discarded_at IS NULL AND is_test=0")["n"],
            "descartados": um(con, "SELECT COUNT(*) AS n FROM suit_orders WHERE discarded_at IS NOT NULL AND is_test=0")["n"],
            "testes": um(con, "SELECT COUNT(*) AS n FROM suit_orders WHERE is_test=1 AND discarded_at IS NULL")["n"],
            "leads": um(con, "SELECT COUNT(*) AS n FROM suit_leads WHERE status='aberto'")["n"],
            "fornecedores": um(con, "SELECT COUNT(*) AS n FROM suit_suppliers")["n"]}


@r.get("")
def listar(response: Response, estado: str = "abertos", status: str | None = None, q: str | None = None,
           limit: int | None = 50, offset: int = 0, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    where, p = [], []
    if estado == "descartados":                   # #195: o que não era pedido de macacão, guardado para conferência
        where.append("o.discarded_at IS NOT NULL")
    else:
        where.append("o.discarded_at IS NULL")
        if estado in ("abertos", "fechados"):
            where.append("o.closed=?"); p.append(1 if estado == "fechados" else 0)
    if status:
        where.append("o.status=?"); p.append(suits.etapa_valida(status) if status in suits.CODIGOS else "_")
    if q and q.strip():
        t = f"%{q.strip().lower()}%"
        where.append("(lower(o.title) LIKE ? OR lower(coalesce(o.customer_name,'')) LIKE ? OR lower(coalesce(o.driver_name,'')) LIKE ? "
                     "OR lower(coalesce(o.customer_email,'')) LIKE ?)")
        p += [t, t, t, t]
    sql = f"""SELECT o.id, o.title, o.product, o.quantity, o.customer_name, o.driver_name, o.status, o.closed, o.order_date, o.due_on,
                     o.source, o.created_at, o.updated_at, o.discarded_at, o.discard_reason, o.ia_ligada, o.is_test, s.name AS fornecedor,
                     (SELECT COUNT(*) FROM suit_notes n WHERE n.order_id=o.id AND n.kind!='etapa') AS notas,
                     (SELECT MAX(created_at) FROM suit_notes n WHERE n.order_id=o.id) AS ultima_nota,
                     (SELECT COUNT(*) FROM atelie_wa_saidas w WHERE w.order_id=o.id
                      AND w.estado IN ('rascunho','falhou')) AS wa_rascunhos
              FROM suit_orders o LEFT JOIN suit_suppliers s ON s.id=o.supplier_id
              {'WHERE ' + ' AND '.join(where) if where else ''}
              ORDER BY o.closed, coalesce(o.discarded_at, o.updated_at, o.created_at) DESC, o.id DESC"""
    return paginar(con, sql, p, response, limit, offset)


class MedidasIn(BaseModel):
    valores: dict[str, str | float | int | None] = {}
    unidade: str = "cm"
    unidade_peso: str = "kg"


class PedidoIn(BaseModel):
    title: str | None = None
    product: str | None = None
    quantity: int | None = None
    customer_name: str | None = None
    customer_email: str | None = None
    customer_phone: str | None = None
    ship_address: str | None = None
    driver_name: str | None = None
    language: str | None = None
    client_id: int | None = None
    supplier_id: int | None = None
    designer_id: int | None = None      # #481: o designer deste pedido (da lista da Alpha Line)
    order_date: str | None = None
    due_on: str | None = None
    paid_at: str | None = None
    tracking: str | None = None
    site_order: str | None = None
    gmail_thread_cliente: str | None = None
    gmail_thread_designer: str | None = None
    gmail_thread_fornecedor: str | None = None
    design: dict[str, str | None] | None = None
    medidas: MedidasIn | None = None
    status: str | None = None
    nota: str | None = None
    ia_ligada: bool | None = None       # #382: pode nascer com a IA desligada (a ponte não age nem um instante)
    is_test: bool | None = None         # #382: pedido de TESTE — nunca manda e-mail real e não conta nem avisa


CAMPOS = ("title", "product", "quantity", "customer_name", "customer_email", "customer_phone", "ship_address",
          "driver_name", "language", "client_id", "supplier_id", "designer_id", "order_date", "due_on", "paid_at", "tracking",
          "site_order", "gmail_thread_cliente", "gmail_thread_designer", "gmail_thread_fornecedor", "ia_ligada", "is_test")


def _limpo(v):
    return v.strip() if isinstance(v, str) else v


def thread_do_link(v):
    """Aceita o id da thread (hex, como a API devolve) ou o link do Gmail colado: o 'thread-f:<número>'
    do link é o mesmo id, em decimal."""
    v = (v or "").strip()
    m = re.search(r"thread-f:(\d+)", v)
    if m:
        return format(int(m.group(1)), "x")
    m = re.search(r"\b([0-9a-f]{16})\b", v)
    return m.group(1) if m else (v or None)


def gravar(con, dados: dict, u_id, pid=None, fonte="manual"):
    """Cria (pid None) ou atualiza um pedido. `dados` no formato de PedidoIn. Devolve o id.
    Tudo ou nada (#382): se a etapa pedida for recusada, nada do resto fica gravado."""
    con.execute("SAVEPOINT gravar")
    try:
        pid = _gravar(con, dados, u_id, pid, fonte)
    except BaseException:
        con.execute("ROLLBACK TO gravar")
        con.execute("RELEASE gravar")
        raise
    con.execute("RELEASE gravar")
    return pid


def _gravar(con, dados: dict, u_id, pid=None, fonte="manual"):
    campos = {k: _limpo(dados[k]) for k in CAMPOS if k in dados and dados[k] is not None}
    for k in ("ia_ligada", "is_test"):
        if k in campos:
            campos[k] = 1 if campos[k] in (True, 1, "1", "true") else 0
    if fonte == "ia" and pid:
        campos.pop("is_test", None)                    # #382: a IA não tira a marca de teste de um pedido
    ia_depois = campos.pop("ia_ligada", None) if pid else None    # no pedido que já existe, a chave deixa o rastro (#198)
    if fonte == "ia" and not pid and campos.get("customer_email"):
        from command_center.providers import suits_ponte
        e = suits_ponte._email_de(campos["customer_email"])
        if suits_ponte._nosso(e) or suits_ponte.robo(e):          # #195: a URACE ou um robô não encomendam macacão
            raise suits.Invalido("este e-mail é da URACE ou de um remetente automático: não é pedido de macacão")
    for k in ("gmail_thread_cliente", "gmail_thread_designer", "gmail_thread_fornecedor"):
        if k in campos:
            campos[k] = thread_do_link(campos[k])
    if "quantity" in campos and not (1 <= int(campos["quantity"]) <= 50):
        raise suits.Invalido("quantidade entre 1 e 50")
    if campos.get("supplier_id") and not um(con, "SELECT id FROM suit_suppliers WHERE id=?", (campos["supplier_id"],)):
        raise suits.Invalido("fornecedor não existe")
    if campos.get("designer_id") and not um(con, "SELECT id FROM suit_designers WHERE id=?", (campos["designer_id"],)):
        raise suits.Invalido("designer não existe")
    for k in ("supplier_id", "designer_id"):        # 0 = voltar para o padrão (o atual da lista)
        if dados.get(k) == 0:
            campos[k] = None
    if campos.get("client_id") and not um(con, "SELECT id FROM clients WHERE id=?", (campos["client_id"],)):
        raise suits.Invalido("cliente não existe")
    if dados.get("client_id") == 0:          # 0 = desvincular (a tela manda 0 quando tira o cliente)
        campos["client_id"] = None
    atual = um(con, "SELECT * FROM suit_orders WHERE id=?", (pid,)) if pid else None
    if pid and not atual:
        raise LookupError("Pedido não encontrado.")
    if dados.get("design") is not None:
        d = json.loads(atual["design"] or "{}") if atual else {}
        d.update({k: (v or "").strip() for k, v in dados["design"].items() if k in dict(suits.DESIGN)})
        campos["design"] = json.dumps({k: v for k, v in d.items() if v}, ensure_ascii=False)
    if dados.get("medidas"):
        m = dados["medidas"]
        novas = suits.normalizar_medidas(m.get("valores"), m.get("unidade", "cm"), m.get("unidade_peso", "kg"))
        antes = json.loads(atual["measurements"] or "{}") if atual else {}
        depois = dict(antes)
        apagar = [k for k, v in (m.get("valores") or {}).items() if v is None or str(v).strip() == ""]
        depois.update(novas)
        for k in apagar:
            depois.pop(k, None)
        campos["measurements"] = json.dumps(depois, ensure_ascii=False)
        if atual:                                   # #382 (E): mudou o valor, a medida volta a "preenchida"
            sit = suits.situacao_depois_de_mudar(antes, depois, suits._json(atual["measurement_status"], {}))
            campos["measurement_status"] = json.dumps(sit, ensure_ascii=False)
    if not pid:
        titulo = campos.get("title") or campos.get("customer_name") or campos.get("driver_name")
        if not titulo:
            raise suits.Invalido("Diga pelo menos o nome do cliente.")
        campos.setdefault("title", titulo)
        if dados.get("status"):
            campos["status"] = suits.etapa_valida(dados["status"])
            if campos["status"] not in suits.INICIAIS:      # #382: aprovado em diante só pelas travas, nunca ao nascer
                raise suits.Invalido("Um pedido novo nasce antes da aprovação (Standby até Design Under Client Review) ou "
                                     "cancelado: as etapas seguintes passam pelas travas (aprovação final, fotos, rastreio).")
            campos["closed"] = 1 if campos["status"] in suits.FECHADAS else 0
        campos.setdefault("order_date", datetime.now(ZoneInfo("America/New_York")).date().isoformat())
        pid = inserir(con, "suit_orders", source=fonte, created_by=u_id, updated_at=agora(), **campos)
        suits.anotar(con, pid, "Pedido registrado" + (" pela IA" if fonte == "ia" else ""), "etapa",
                     campos.get("status", "standby"), user_id=u_id)
    else:
        if campos:
            atualizar(con, "suit_orders", pid, updated_at=agora(), **campos)
        if "measurements" in campos:
            suits.conferir_aprovacao(con, pid, u_id)
        if dados.get("status"):
            suits.mudar_etapa(con, pid, dados["status"], u_id, por_ia=(fonte == "ia"))
    if ia_depois is not None:
        suits.ligar_ia(con, pid, bool(ia_depois), u_id)
    if dados.get("nota"):
        p = um(con, "SELECT status FROM suit_orders WHERE id=?", (pid,))
        suits.anotar(con, pid, dados["nota"], "nota", p["status"], user_id=u_id)
    suits.vincular_por_email(con, pid)
    return pid


@r.post("", status_code=201)
def criar(dados: PedidoIn, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    try:
        pid = gravar(con, dados.model_dump(exclude_unset=True), u["id"])
    except suits.Invalido as e:
        raise _invalido(e)
    _aud(con, request, u, "suit.created", pid, {"title": dados.title or dados.customer_name})
    return _pedido(con, pid)


# --------------------------------------------------------------------- modelo
class ModeloIn(BaseModel):
    subject: str
    body: str


@r.get("/modelo")
def ver_modelo(con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    return dict(suits.modelo(con), campos=list(suits.CAMPOS_MODELO), padrao=suits.MODELO_PADRAO)


@r.put("/modelo")
def salvar_modelo(dados: ModeloIn, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("MANAGER"))):
    if not dados.subject.strip() or "{medidas}" not in dados.body:
        raise HTTPException(400, "O modelo precisa de assunto e do campo {medidas}.")
    con.execute("""INSERT INTO suit_templates (key, subject, body, updated_at, updated_by) VALUES ('fornecedor',?,?,?,?)
                   ON CONFLICT(key) DO UPDATE SET subject=excluded.subject, body=excluded.body,
                   updated_at=excluded.updated_at, updated_by=excluded.updated_by""",
                (dados.subject.strip()[:200], dados.body[:8000], agora(), u["id"]))
    _aud(con, request, u, "suit.template", "fornecedor", tipo="suit_template")
    return suits.modelo(con)


# ------------------------------------------------------------------- leads
@r.get("/leads")
def leads(response: Response, estado: str = "aberto", q: str | None = None, limit: int | None = 100, offset: int = 0,
          con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    where, p = [], []
    if estado in ("aberto", "convertido", "perdido"):
        where.append("status=?"); p.append(estado)
    if q and q.strip():
        t = f"%{q.strip().lower()}%"
        where.append("(lower(name) LIKE ? OR lower(coalesce(email,'')) LIKE ? OR lower(coalesce(notes,'')) LIKE ?)"); p += [t, t, t]
    sql = f"SELECT * FROM suit_leads {'WHERE ' + ' AND '.join(where) if where else ''} ORDER BY id DESC"
    return paginar(con, sql, p, response, limit, offset)


class LeadIn(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None
    status: str | None = None
    client_id: int | None = None


@r.post("/leads", status_code=201)
def criar_lead(dados: LeadIn, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    if not (dados.name or "").strip():
        raise HTTPException(400, "Diga o nome.")
    if dados.client_id and not um(con, "SELECT id FROM clients WHERE id=?", (dados.client_id,)):
        raise HTTPException(400, "Cliente não existe.")
    lid = inserir(con, "suit_leads", name=dados.name.strip(), email=_limpo(dados.email) or None,
                  phone=_limpo(dados.phone) or None, notes=_limpo(dados.notes) or None, client_id=dados.client_id,
                  updated_at=agora())
    _aud(con, request, u, "suit.lead.created", lid, tipo="suit_lead")
    return um(con, "SELECT * FROM suit_leads WHERE id=?", (lid,))


@r.patch("/leads/{lid}")
def mudar_lead(lid: int, dados: LeadIn, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    if not um(con, "SELECT id FROM suit_leads WHERE id=?", (lid,)):
        raise HTTPException(404, "Lead não encontrado.")
    campos = {k: _limpo(v) for k, v in dados.model_dump(exclude_unset=True).items()}
    if "status" in campos and campos["status"] not in ("aberto", "convertido", "perdido"):
        raise HTTPException(400, "Situação inválida.")
    if campos.get("client_id") and not um(con, "SELECT id FROM clients WHERE id=?", (campos["client_id"],)):
        raise HTTPException(400, "Cliente não existe.")
    if campos:
        atualizar(con, "suit_leads", lid, updated_at=agora(), **campos)
    _aud(con, request, u, "suit.lead.updated", lid, {"campos": list(campos)}, tipo="suit_lead")
    return um(con, "SELECT * FROM suit_leads WHERE id=?", (lid,))


@r.post("/leads/{lid}/pedido", status_code=201)
def lead_vira_pedido(lid: int, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    lead = um(con, "SELECT * FROM suit_leads WHERE id=?", (lid,))
    if not lead:
        raise HTTPException(404, "Lead não encontrado.")
    if lead["order_id"]:
        return _pedido(con, lead["order_id"])
    pid = gravar(con, {"customer_name": lead["name"], "customer_email": lead["email"], "customer_phone": lead["phone"],
                       "client_id": lead["client_id"],
                       "nota": f"Veio do lead: {lead['notes']}" if lead["notes"] else None}, u["id"])
    atualizar(con, "suit_leads", lid, status="convertido", order_id=pid, updated_at=agora())
    _aud(con, request, u, "suit.lead.converted", lid, {"pedido": pid}, tipo="suit_lead")
    return _pedido(con, pid)


# -------------------------------------------------------------- fornecedores
@r.get("/fornecedores")
def fornecedores(con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    return todos(con, """SELECT s.*, (SELECT COUNT(*) FROM suit_orders o WHERE o.supplier_id=s.id) AS pedidos
                         FROM suit_suppliers s ORDER BY s.is_current DESC, pedidos DESC, s.name""")


class FornecedorIn(BaseModel):
    name: str | None = None
    contact: str | None = None
    email: str | None = None
    phone: str | None = None
    has_fia: int | None = None
    status: str | None = None
    price: str | None = None
    shipping: str | None = None
    payment: str | None = None
    lead_time: str | None = None
    comments: str | None = None
    is_current: bool | None = None


def _forn_campos(dados):
    c = {k: _limpo(v) for k, v in dados.model_dump(exclude_unset=True).items()}
    if "is_current" in c:
        c["is_current"] = 1 if c["is_current"] else 0
    return c


@r.post("/fornecedores", status_code=201)
def criar_fornecedor(dados: FornecedorIn, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("MANAGER"))):
    c = _forn_campos(dados)
    if not (c.get("name") or "").strip():
        raise HTTPException(400, "Diga o nome do fornecedor.")
    if c.get("is_current"):
        con.execute("UPDATE suit_suppliers SET is_current=0")
    fid = inserir(con, "suit_suppliers", updated_at=agora(), **c)
    _aud(con, request, u, "suit.supplier.created", fid, tipo="suit_supplier")
    return um(con, "SELECT * FROM suit_suppliers WHERE id=?", (fid,))


@r.patch("/fornecedores/{fid}")
def mudar_fornecedor(fid: int, dados: FornecedorIn, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("MANAGER"))):
    if not um(con, "SELECT id FROM suit_suppliers WHERE id=?", (fid,)):
        raise HTTPException(404, "Fornecedor não encontrado.")
    c = _forn_campos(dados)
    if c.get("is_current"):
        con.execute("UPDATE suit_suppliers SET is_current=0")       # o atual é um só
    if c:
        atualizar(con, "suit_suppliers", fid, updated_at=agora(), **c)
    _aud(con, request, u, "suit.supplier.updated", fid, {"campos": list(c)}, tipo="suit_supplier")
    return um(con, "SELECT * FROM suit_suppliers WHERE id=?", (fid,))


# -------------------------------------------------------------- designers (#481)
@r.get("/designers")
def designers(con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    """Os designers da Alpha Line (nome e e-mail fixo); a Ponte de e-mail do pedido escolhe um deles."""
    _ponte().semear_designers(con)
    return todos(con, """SELECT d.*, (SELECT COUNT(*) FROM suit_orders o WHERE o.designer_id=d.id) AS pedidos
                         FROM suit_designers d ORDER BY d.is_current DESC, d.name""")


class DesignerIn(BaseModel):
    name: str | None = None
    email: str | None = None
    notes: str | None = None
    is_current: bool | None = None


def _designer_campos(dados):
    c = {k: _limpo(v) for k, v in dados.model_dump(exclude_unset=True).items()}
    if "is_current" in c:
        c["is_current"] = 1 if c["is_current"] else 0
    if c.get("email") and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", c["email"]):
        raise HTTPException(400, "E-mail do designer inválido.")
    if "name" in c and not (c["name"] or "").strip():
        raise HTTPException(400, "Diga o nome do designer.")
    return c


@r.post("/designers", status_code=201)
def criar_designer(dados: DesignerIn, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("MANAGER"))):
    c = _designer_campos(dados)
    if not (c.get("name") or "").strip():
        raise HTTPException(400, "Diga o nome do designer.")
    if c.get("is_current"):
        con.execute("UPDATE suit_designers SET is_current=0")
    did = inserir(con, "suit_designers", updated_at=agora(), **c)
    _aud(con, request, u, "suit.designer.created", did, tipo="suit_designer")
    return um(con, "SELECT * FROM suit_designers WHERE id=?", (did,))


@r.patch("/designers/{did}")
def mudar_designer(did: int, dados: DesignerIn, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("MANAGER"))):
    if not um(con, "SELECT id FROM suit_designers WHERE id=?", (did,)):
        raise HTTPException(404, "Designer não encontrado.")
    c = _designer_campos(dados)
    if c.get("is_current"):
        con.execute("UPDATE suit_designers SET is_current=0")       # o padrão é um só
    if c:
        atualizar(con, "suit_designers", did, updated_at=agora(), **c)
    _aud(con, request, u, "suit.designer.updated", did, {"campos": list(c)}, tipo="suit_designer")
    return um(con, "SELECT * FROM suit_designers WHERE id=?", (did,))


# ------------------------------------------------------------ importar do Asana
@r.post("/importar")
def importar(request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("MANAGER"))):
    """Lê o projeto SUITS do Asana (só leitura) e traz pedidos, leads e fornecedores. Pode repetir."""
    from command_center.providers import NaoConectado, modulo
    try:
        tarefas = modulo("asana").tarefas_do_suits()
    except NaoConectado as e:
        raise HTTPException(503, f"Asana não conectado: {e}")
    except Exception as e:
        raise HTTPException(502, f"Não deu para ler o Asana: {str(e)[:200]}")
    res = suits.importar(con, tarefas)
    _aud(con, request, u, "suit.import.asana", "1205661933760052", res, tipo="asana_project")
    return res


# ------------------------------------------------------------ ponte de e-mail
def _ponte():
    from command_center.providers import suits_ponte
    return suits_ponte


@r.get("/ponte")
def ver_ponte(con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    from command_center.api import ia
    sp = _ponte()
    ult = um(con, "SELECT at, detail FROM audit_logs WHERE event='suit.bridge.round' ORDER BY id DESC LIMIT 1")
    return {"config": sp.config(con), "manual": os.path.isfile(sp.manual_pdf()),
            "motor": ia.motor_da_ia(), "ultima_rodada": dict(ult) if ult else None}


class PonteIn(BaseModel):
    ponte_ligada: bool | None = None
    envio_automatico: bool | None = None
    designer_nome: str | None = None
    designer_email: str | None = None
    assinatura: str | None = None
    boas_vindas: str | None = None
    politica: str | None = None


@r.get("/ponte/saude")
def saude_da_ponte(con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    """#382 (F): o topo da aba — a última rodada da ponte (quando, quantos eventos, erros) e se está em simulação."""
    sp = _ponte()
    cfg = sp.config(con)
    return {"ultima_rodada": sp.ultima_rodada(con), "simulacao": cfg["envio_automatico"] != "1",
            "ligada": cfg["ponte_ligada"] == "1", "manual": os.path.isfile(sp.manual_pdf()),
            "preparados": um(con, """SELECT COUNT(*) AS n FROM suit_outbox x JOIN suit_orders o ON o.id=x.order_id
                                     WHERE x.status='preparado' AND o.discarded_at IS NULL""")["n"],
            "com_erro": um(con, """SELECT COUNT(*) AS n FROM suit_orders WHERE closed=0 AND discarded_at IS NULL AND is_test=0
                                   AND bridge_last_error_at IS NOT NULL
                                   AND (bridge_last_ok_at IS NULL OR bridge_last_error_at > bridge_last_ok_at)""")["n"]}


@r.put("/ponte")
def salvar_ponte(dados: PonteIn, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("MANAGER"))):
    sp = _ponte()
    d = dados.model_dump(exclude_unset=True)
    for k in ("ponte_ligada", "envio_automatico"):
        if k in d and d[k] is not None:
            d[k] = "1" if d[k] else "0"
    try:
        cfg = sp.salvar_config(con, d, u["id"])
    except sp.Recusado as e:
        raise HTTPException(400, str(e))
    _aud(con, request, u, "suit.bridge.config", "ponte", {k: (v if k != "boas_vindas" else "…") for k, v in d.items()}, tipo="suit_bridge")
    return {"config": cfg, "manual": os.path.isfile(sp.manual_pdf())}


@r.post("/ponte/manual")
async def subir_manual(request: Request, arquivo: UploadFile = File(...), con: sqlite3.Connection = Depends(get_db),
                       u=Depends(auth.exige("MANAGER"))):
    """O PDF do manual de medidas que vai nas boas-vindas."""
    dados = await arquivo.read(IMAGEM_MAX + 1)
    if not dados.startswith(b"%PDF") or len(dados) > IMAGEM_MAX:
        raise HTTPException(400, "Mande o PDF do manual (até 8 MB).")
    with open(_ponte().manual_pdf(), "wb") as f:
        f.write(dados)
    _aud(con, request, u, "suit.bridge.manual", "ponte", {"bytes": len(dados)}, tipo="suit_bridge")
    return {"ok": True, "bytes": len(dados)}


@r.post("/ponte/manual/gmail")
def manual_do_gmail(request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("MANAGER"))):
    """Busca o 'GUIDE TO FILLING IN SIZING - URACE FORM.pdf' no último e-mail enviado com ele."""
    from command_center.providers import NaoConectado, modulo
    sp = _ponte()
    try:
        gm = modulo("gmail")
        r = gm.gmail_buscar(sp.CONTA, 'in:sent filename:"GUIDE TO FILLING IN SIZING"', so_inbox=False, maximo=1)
        for t in r.get("threads") or []:
            for m in reversed(gm.mensagens_da_thread(sp.CONTA, t["thread_id"])["mensagens"]):
                for a in m.get("anexos") or []:
                    if (a.get("nome") or "").lower().endswith(".pdf") and "sizing" in (a.get("nome") or "").lower():
                        dados = gm.anexo_bytes(sp.CONTA, m["message_id"], a["attachment_id"])
                        with open(sp.manual_pdf(), "wb") as f:
                            f.write(dados)
                        _aud(con, request, u, "suit.bridge.manual", "ponte", {"de": "gmail", "bytes": len(dados)}, tipo="suit_bridge")
                        return {"ok": True, "bytes": len(dados), "nome": a["nome"]}
    except NaoConectado as e:
        raise HTTPException(503, f"Gmail não conectado: {e}")
    raise HTTPException(404, "Não achei o PDF do manual nos e-mails enviados. Suba o arquivo à mão.")


@r.get("/ponte/manual")
def baixar_manual(u=Depends(auth.exige("OPERATOR"))):
    caminho = _ponte().manual_pdf()
    if not os.path.isfile(caminho):
        raise HTTPException(404)
    from fastapi.responses import FileResponse
    return FileResponse(caminho, media_type="application/pdf", filename="GUIDE TO FILLING IN SIZING - URACE FORM.pdf",
                        headers={"Cache-Control": "private, max-age=60"})


@r.post("/ponte/rodar")
def rodar_ponte(request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("MANAGER"))):
    """Roda um ciclo agora (em segundo plano), em vez de esperar os 15 minutos."""
    ok = _ponte().rodar_em_segundo_plano()
    _aud(con, request, u, "suit.bridge.run", "ponte", {"iniciada": ok}, tipo="suit_bridge")
    return {"iniciada": ok, "nota": None if ok else "Já tem um ciclo rodando."}


# ------------------------------------------------------------ vincular ao cliente
@r.get("/cliente/{cid}")
def dados_do_cliente(cid: int, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    """O que o cadastro já sabe do cliente, para o formulário puxar (#158)."""
    d = suits.dados_do_cliente(con, cid)
    if not d:
        raise HTTPException(404, "Cliente não encontrado.")
    return d


# ------------------------------------------------------------------- pedido
@r.get("/notas/{nid}/imagem")
def imagem_da_nota(nid: int, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    """A foto sai pelo servidor, com sessão — nunca por link público adivinhável."""
    n = um(con, "SELECT image_path FROM suit_notes WHERE id=?", (nid,))
    if not n or not n["image_path"]:
        raise HTTPException(404)
    caminho = os.path.join(pasta_imagens(), os.path.basename(n["image_path"]))
    if not os.path.isfile(caminho):
        raise HTTPException(404)
    from fastapi.responses import FileResponse
    return FileResponse(caminho, media_type="image/webp", headers={"Cache-Control": "private, max-age=300"})


@r.get("/{pid}")
def ver(pid: int, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    p = _pedido(con, pid)
    for n in p["notas"]:                          # o que a IA respondeu a cada nota
        if n.get("command_id"):
            c = um(con, "SELECT status, output, error FROM ai_commands WHERE id=?", (n["command_id"],))
            n["ia"] = dict(c) if c else None
    p["preparados"] = _ponte().preparados(con, pid)          # #382: e-mails ao designer esperando o clique
    p["designer"] = _ponte().designer_do_pedido(con, p)      # #481: o designer que vale (o escolhido ou o padrão)
    return p


class DescarteIn(BaseModel):
    motivo: str | None = None


@r.post("/{pid}/descartar")
def descartar(pid: int, dados: DescarteIn, request: Request, con: sqlite3.Connection = Depends(get_db),
              u=Depends(auth.exige("OPERATOR"))):
    """#195: "não é pedido de macacão". Sai das listas e da ponte; nada é apagado."""
    try:
        feito = suits.descartar(con, pid, dados.motivo, u["id"])
    except LookupError:
        raise HTTPException(404, "Pedido não encontrado.")
    if feito:
        _aud(con, request, u, "suit.discarded", pid, {"motivo": (dados.motivo or suits.MOTIVO_PADRAO)[:200]})
    return ver(pid, con, u)


class IaIn(BaseModel):
    ligada: bool


@r.post("/{pid}/ia")
def ligar_ia(pid: int, dados: IaIn, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    """#198: a chave "IA neste pedido"."""
    try:
        feito = suits.ligar_ia(con, pid, dados.ligada, u["id"])
    except LookupError:
        raise HTTPException(404, "Pedido não encontrado.")
    if feito:
        _aud(con, request, u, "suit.ai.on" if dados.ligada else "suit.ai.off", pid)
    return ver(pid, con, u)


@r.post("/{pid}/restaurar")
def restaurar(pid: int, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    try:
        feito = suits.restaurar(con, pid, u["id"])
    except LookupError:
        raise HTTPException(404, "Pedido não encontrado.")
    if feito:
        _aud(con, request, u, "suit.restored", pid)
    return ver(pid, con, u)


@r.patch("/{pid}")
def mudar(pid: int, dados: PedidoIn, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    d = dados.model_dump(exclude_unset=True)
    try:
        gravar(con, d, u["id"], pid)
    except LookupError:
        raise HTTPException(404, "Pedido não encontrado.")
    except suits.Invalido as e:
        raise _invalido(e)
    _aud(con, request, u, "suit.updated", pid, {"campos": [k for k in d if k != "medidas"] + (["medidas"] if "medidas" in d else [])})
    return ver(pid, con, u)


def pedir_a_ia(con, pid, u, nota_id, texto, imagem, arquivo=None):
    """Leva a nota (e a imagem) ao AI Command, na conversa de quem escreveu: a IA lê o pedido,
    entende e avança. A resposta aparece aqui na nota e no AI Command."""
    from command_center.api import acoes, ia, motor
    p = suits.detalhe(con, pid)
    etapa = dict((c, n) for c, n, _ in suits.ETAPAS)[p["status"]]
    pedido = (f"SUITS — pedido de macacão #{pid} ({p['title']}), etapa atual: {etapa}.\n"
              f"Nota de {u.get('name') or 'alguém da equipe'}: {texto or '(sem texto)'}\n"
              + (f"Screenshot anexado à nota: {os.path.join(pasta_imagens(), imagem)} (leia a imagem).\n" if imagem else "")
              + (f"Arquivo anexado à nota: {os.path.join(_ponte().pasta(pid), arquivo)} (está nos arquivos do pedido).\n"
                 if arquivo else "")
              + "Leia o pedido inteiro (suits_pedido), entenda a nota e avance o pedido: atualize os dados, as medidas e a "
                "etapa (suits_atualizar_pedido) e registre o que fez (suits_anotar). Mensagem ao cliente ou ao designer: no "
                "idioma do cliente, educada e comercial (ainda é venda), respeitando o que ele pediu.")
    prompt = pedido + motor.aprendizados(con) + acoes.estado_do_dia(con, u["id"])
    sk = f"agent:{ia.AGENTE}:web-{u['id']}-{datetime.now(ZoneInfo('America/New_York')).date().isoformat()}"
    cid = inserir(con, "ai_commands", user_id=u["id"], text=f"Suits #{pid}: {texto or 'imagem'}"[:4000], prompt=prompt, session_key=sk)
    con.execute("UPDATE suit_notes SET command_id=? WHERE id=?", (cid, nota_id))
    auditar(con, "ai.command", f"user:{u['id']}", user_id=u["id"], entity_type="ai_command", entity_id=cid,
            detail={"suit": pid, "nota": nota_id})
    threading.Thread(target=ia._executa, args=(cid, texto or "", sk, u["id"], prompt), daemon=True).start()
    return cid


@r.post("/{pid}/notas", status_code=201)
async def nova_nota(pid: int, request: Request, texto: str = Form(""), status: str = Form(""), pedir_ia: bool = Form(False),
                    imagem: UploadFile | None = File(None), arquivo: UploadFile | None = File(None),
                    con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    """Nota em qualquer etapa, com um arquivo opcional; pode mudar a etapa e pedir à IA para seguir.
    #447: `arquivo` aceita qualquer tipo — imagem segue o caminho da foto (WebP, sem EXIF, na linha do tempo); o
    resto vai para os arquivos do pedido, sai só com sessão e sempre como download."""
    p = um(con, "SELECT id, status FROM suit_orders WHERE id=?", (pid,))
    if not p:
        raise HTTPException(404, "Pedido não encontrado.")
    texto = (texto or "").strip()
    nome_img = nome_arq = None
    if arquivo is not None and (arquivo.filename or arquivo.size):
        if (arquivo.content_type or "").lower() in TIPOS_IMAGEM:
            imagem = arquivo
        else:
            dados_arq = await arquivo.read(ARQUIVO_MAX + 1)
            if not dados_arq:
                raise HTTPException(400, "O arquivo veio vazio.")
            if len(dados_arq) > ARQUIVO_MAX:
                raise HTTPException(400, "Arquivo grande demais (máximo 25 MB).")
    if status and status != p["status"]:              # #382: a etapa recusada não deixa foto solta para trás
        try:
            suits.etapa_valida(status)
            suits.checar_etapa(con, pid, status)
        except suits.Invalido as e:
            raise _invalido(e)
    if imagem is not None and (imagem.filename or imagem.size):
        if (imagem.content_type or "").lower() not in TIPOS_IMAGEM:
            raise HTTPException(400, "Use PNG, JPG ou WEBP.")
        dados = await imagem.read(IMAGEM_MAX + 1)
        if len(dados) > IMAGEM_MAX:
            raise HTTPException(400, "Imagem grande demais (máximo 8 MB).")
        from command_center.providers import imagem as img
        try:
            dados, ext = img.comprimir(dados)
        except img.ImagemInvalida:
            raise HTTPException(400, "Essa imagem não abriu. Tente outra.")
        nome_img = f"pedido-{pid}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}{ext}"
        with open(os.path.join(pasta_imagens(), nome_img), "wb") as f:
            f.write(dados)
    if arquivo is not None and imagem is not arquivo and (arquivo.filename or arquivo.size):
        nome_arq = _ponte().guardar_anexo(pid, arquivo.filename or "arquivo", dados_arq)
    if not texto and not nome_img and not nome_arq and not status:
        raise HTTPException(400, "Escreva a nota, anexe um arquivo ou mude a etapa.")
    try:
        if status and status != p["status"]:
            suits.mudar_etapa(con, pid, status, u["id"])
    except suits.Invalido as e:
        raise _invalido(e)
    nid = None
    if texto or nome_img or nome_arq:
        nid = suits.anotar(con, pid, texto, "nota", status or p["status"], nome_img, u["id"], arquivo=nome_arq)
        atualizar(con, "suit_orders", pid, updated_at=agora())
    cid = pedir_a_ia(con, pid, u, nid, texto, nome_img, nome_arq) if pedir_ia and nid and not suits.ia_desligada(con, pid) else None
    _aud(con, request, u, "suit.note", pid, {"nota": nid, "imagem": bool(nome_img), "arquivo": nome_arq, "etapa": status or None, "ia": cid})
    return {"id": nid, "command_id": cid}


@r.get("/{pid}/anexos")
def anexos(pid: int, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    if not um(con, "SELECT id FROM suit_orders WHERE id=?", (pid,)):
        raise HTTPException(404, "Pedido não encontrado.")
    sp = _ponte()
    return [{"nome": n, "bytes": os.path.getsize(os.path.join(sp.pasta(pid), n))} for n in sp.anexos_do_pedido(pid)]


@r.get("/{pid}/anexos/{nome}")
def anexo(pid: int, nome: str, u=Depends(auth.exige("OPERATOR"))):
    sp = _ponte()
    caminho = os.path.join(sp.pasta(pid), os.path.basename(nome))
    if not os.path.isfile(caminho):
        raise HTTPException(404)
    from fastapi.responses import FileResponse
    return FileResponse(caminho, filename=os.path.basename(nome), headers={"Cache-Control": "private, max-age=300"})


@r.post("/{pid}/ponte/simular", status_code=202)
def simular(pid: int, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    """A IA faz o próximo passo da ponte neste pedido, sem mandar nada: os e-mails viram nota."""
    p = um(con, "SELECT id, discarded_at FROM suit_orders WHERE id=?", (pid,))
    if not p:
        raise HTTPException(404, "Pedido não encontrado.")
    if p["discarded_at"]:
        raise HTTPException(409, "Pedido descartado (não é pedido de macacão): restaure antes de simular.")
    if suits.ia_desligada(con, pid):
        raise HTTPException(409, "A IA está desligada neste pedido: ligue a chave antes de simular.")
    sp = _ponte()

    def _vai():
        from command_center.db import conectar
        c = conectar()
        try:
            sp.simular_pedido(c, pid)
        except Exception as e:
            suits.anotar(c, pid, f"A simulação não rodou: {type(e).__name__}: {str(e)[:200]}", "ia")
        finally:
            c.close()
    threading.Thread(target=_vai, daemon=True, name=f"cc-suits-sim-{pid}").start()
    _aud(con, request, u, "suit.bridge.simulate", pid)
    return {"iniciada": True}


@r.post("/{pid}/ponte/puxar")
def puxar_conversas(pid: int, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    """#481: procura no Gmail e liga ao pedido as conversas que faltam (cliente, designer, fornecedor). Só lê."""
    from command_center.providers import NaoConectado
    try:
        r_ = _ponte().achar_conversas(con, pid)
    except LookupError:
        raise HTTPException(404, "Pedido não encontrado.")
    except _ponte().Recusado as e:
        raise HTTPException(400, str(e))
    except NaoConectado as e:          # a tela procura sozinha ao abrir o pedido: Gmail fora vira aviso, não erro
        r_ = {"ligadas": {}, "faltam": [], "aviso": f"Gmail não conectado: {str(e)[:200]}"}
    except Exception as e:             # noqa: BLE001 - o Gmail respondeu erro: nada foi ligado, a tela mostra o motivo
        r_ = {"ligadas": {}, "faltam": [], "aviso": f"O Gmail não respondeu: {str(e)[:200]}"}
    if r_["ligadas"]:
        _aud(con, request, u, "suit.bridge.linked", pid, {"ligadas": list(r_["ligadas"])})
    return dict(ver(pid, con, u), puxadas=r_)


@r.get("/{pid}/email-fornecedor")
def email_fornecedor(pid: int, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    p = um(con, "SELECT * FROM suit_orders WHERE id=?", (pid,))
    if not p:
        raise HTTPException(404, "Pedido não encontrado.")
    f = um(con, "SELECT * FROM suit_suppliers WHERE id=?", (p["supplier_id"],)) if p["supplier_id"] else \
        um(con, "SELECT * FROM suit_suppliers WHERE is_current=1")
    return dict(suits.email_fornecedor(con, dict(p), dict(f) if f else None, u), fornecedor=dict(f) if f else None)


def _gmail_rascunho(para, assunto, corpo, anexos=None):
    """Rascunho no Gmail do urace@: o clique da pessoa é a autorização (APLICAR=1 só nesta chamada)."""
    from command_center.providers import NaoConectado, chamar
    anterior = os.environ.get("APLICAR")
    os.environ["APLICAR"] = "1"
    try:
        extra = {"anexos": anexos} if anexos else {}
        return chamar("gmail", "gmail_rascunho", conta="urace", para=para, assunto=assunto, corpo=corpo, **extra)
    except NaoConectado as ex:
        raise HTTPException(503, f"Gmail não conectado: {ex}")
    except Exception as ex:                  # debug 29/10: o Gmail recusou ou caiu — o motivo vai à tela, não um 500
        raise HTTPException(502, f"O Gmail não criou o rascunho ({type(ex).__name__}: {str(ex)[:200]}). Tente de novo.")
    finally:
        if anterior is None:
            os.environ.pop("APLICAR", None)
        else:
            os.environ["APLICAR"] = anterior


def _fornecedor_do(con, p):
    f = um(con, "SELECT * FROM suit_suppliers WHERE id=?", (p["supplier_id"],)) if p["supplier_id"] else \
        um(con, "SELECT * FROM suit_suppliers WHERE is_current=1")
    return dict(f) if f else None


def pacote_aprovado(con, pid):
    """Revisão do Mio (#382): o que vai ao fornecedor é o PACOTE APROVADO — a arte final e as medidas que estão na
    aprovação válida, conferidas pelo mesmo hash. Devolve (aprovação, medidas, [(nome, bytes, mime)])."""
    import mimetypes
    sp = _ponte()
    e = suits.estado_aprovacao(con, pid)
    if not e or e["estado"] != "valida":
        raise HTTPException(400, "Sem a aprovação final do cliente válida para a arte e as medidas de agora, o pedido não vai "
                                 "ao fornecedor.")
    ap = e["aprovacao"]
    medidas = suits._json(ap.get("measures"), None)
    if medidas is None or suits.hash_medidas(medidas) != ap["measures_hash"]:
        raise HTTPException(409, "As medidas guardadas na aprovação não batem com o hash dela: registre a aprovação de novo.")
    nomes = ap.get("files") or []
    if not nomes or suits.hash_arte(pid, nomes) != ap["art_hash"]:
        raise HTTPException(409, "A arte final aprovada não está mais igual na pasta do pedido: registre a aprovação de novo.")
    anexos = []
    for nome in nomes:
        with open(os.path.join(sp.pasta(pid), os.path.basename(nome)), "rb") as f:
            dados = f.read()
        mime = mimetypes.guess_type(nome)[0] or "application/octet-stream"
        try:
            dados = sp._sem_metadados(nome, dados, mime)
        except sp.Recusado as ex:
            raise HTTPException(400, str(ex))
        anexos.append((nome, dados, mime))
    return ap, medidas, anexos


@r.post("/{pid}/email-fornecedor/rascunho")
def rascunho_fornecedor(pid: int, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    """O pedido de produção vira um RASCUNHO no Gmail do urace@, já com a arte final aprovada anexada e as medidas
    aprovadas no corpo (o pacote da aprovação). Enviar continua sendo humano. Sem endereço: ele vai depois do OK das fotos."""
    p = um(con, "SELECT * FROM suit_orders WHERE id=?", (pid,))
    if not p:
        raise HTTPException(404, "Pedido não encontrado.")
    f = _fornecedor_do(con, p)
    ap, medidas, anexos = pacote_aprovado(con, pid)
    e = suits.email_fornecedor(con, dict(p, measurements=json.dumps(medidas), final_art=json.dumps(ap.get("files") or [])), f, u)
    if e["faltam"]:
        raise HTTPException(400, "Falta " + " e ".join(e["faltam"]) + " para montar o pedido ao fornecedor.")
    res = _gmail_rascunho(e["para"], e["assunto"], e["corpo"], anexos)
    suits.anotar(con, pid, f"Rascunho do pedido ao fornecedor criado no Gmail (para {e['para']}), com a arte final aprovada "
                 f"anexada ({', '.join(a[0] for a in anexos)}): confira e envie.", "email", p["status"], user_id=u["id"])
    _aud(con, request, u, "suit.supplier.draft", pid, {"para": e["para"], "draft": res.get("draft_id"), "aprovacao": ap["id"],
                                                     "anexos": [a[0] for a in anexos]})
    return {"ok": True, "draft_id": res.get("draft_id"), "para": e["para"], "anexos": [a[0] for a in anexos]}


# ------------------------------------------------------- aprovação final (#382, A)
class LiberarIn(BaseModel):
    motivo: str


@r.post("/{pid}/aprovar-admin")
def aprovar_pelo_admin(pid: int, dados: LiberarIn, request: Request, con: sqlite3.Connection = Depends(get_db),
                       u=Depends(auth.exige("ADMIN"))):
    """#448: o administrador move para Approved sem a aprovação escrita registrada, com o motivo. A IA não chama
    sozinha: no painel_api e no conector esta rota pede o clique (`mcp_operar.PEDE_CONFIRMACAO`)."""
    try:
        sem = suits.liberar_aprovado(con, pid, u["id"], dados.motivo)
    except LookupError:
        raise HTTPException(404, "Pedido não encontrado.")
    except suits.Invalido as e:
        raise _invalido(e)
    _aud(con, request, u, "suit.approved.admin", pid, {"sem_aprovacao_escrita": sem, "motivo": dados.motivo.strip()[:500]})
    return ver(pid, con, u)


class AprovacaoIn(BaseModel):
    trecho: str
    message_id: str | None = None
    data: str | None = None


@r.post("/{pid}/aprovacao")
def registrar_aprovacao(pid: int, dados: AprovacaoIn, request: Request, con: sqlite3.Connection = Depends(get_db),
                        u=Depends(auth.exige("OPERATOR"))):
    """A equipe registra à mão a aprovação final escrita do cliente (o trecho do e-mail, o id e a data)."""
    try:
        ap = suits.registrar_aprovacao(con, pid, dados.trecho, dados.message_id, dados.data, "manual", u["id"])
    except LookupError:
        raise HTTPException(404, "Pedido não encontrado.")
    except suits.Invalido as e:
        raise _invalido(e)
    _aud(con, request, u, "suit.approval", pid, {"aprovacao": ap["id"], "versao": ap["versao"], "message_id": dados.message_id})
    return ver(pid, con, u)


class ArteIn(BaseModel):
    nome: str
    final: bool = True


@r.post("/{pid}/arte-final")
def arte_final(pid: int, dados: ArteIn, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    try:
        suits.marcar_arte_final(con, pid, dados.nome, dados.final, u["id"])
    except LookupError:
        raise HTTPException(404, "Pedido não encontrado.")
    except suits.Invalido as e:
        raise _invalido(e)
    _aud(con, request, u, "suit.final_art", pid, {"nome": os.path.basename(dados.nome), "final": dados.final})
    return ver(pid, con, u)


class EstadoMedidaIn(BaseModel):
    chaves: list[str]
    estado: str
    motivo: str | None = None


@r.post("/{pid}/medidas/estado")
def estado_medidas(pid: int, dados: EstadoMedidaIn, request: Request, con: sqlite3.Connection = Depends(get_db),
                   u=Depends(auth.exige("OPERATOR"))):
    """#382 (E): preenchida, conferida ou suspeita (com o motivo). Suspeita ou não conferida trava a aprovação final."""
    try:
        suits.marcar_medidas(con, pid, dados.chaves, dados.estado, dados.motivo, u["id"])
    except LookupError:
        raise HTTPException(404, "Pedido não encontrado.")
    except suits.Invalido as e:
        raise _invalido(e)
    _aud(con, request, u, "suit.measures.state", pid, {"chaves": dados.chaves[:40], "estado": dados.estado})
    return ver(pid, con, u)


# ------------------------------------------------ endereço ao fornecedor (#382, D)
@r.get("/{pid}/endereco-fornecedor")
def endereco_fornecedor(pid: int, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    p = um(con, "SELECT * FROM suit_orders WHERE id=?", (pid,))
    if not p:
        raise HTTPException(404, "Pedido não encontrado.")
    return suits.mensagem_endereco(dict(p), _fornecedor_do(con, p), u)


@r.post("/{pid}/endereco-fornecedor/rascunho")
def rascunho_endereco(pid: int, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    """Só depois do OK das fotos (Checked): o endereço do cliente vai ao FORNECEDOR, como rascunho no Gmail."""
    e = endereco_fornecedor(pid, con, u)
    if e["faltam"]:
        raise HTTPException(400, "Falta " + " e ".join(e["faltam"]) + " para passar o endereço ao fornecedor.")
    res = _gmail_rascunho(e["para"], e["assunto"], e["corpo"])
    st = um(con, "SELECT status FROM suit_orders WHERE id=?", (pid,))["status"]
    suits.anotar(con, pid, f"Rascunho com o endereço de entrega criado no Gmail (para o fornecedor, {e['para']}): confira e envie; "
                 "depois mude a etapa para Address sent to supplier.", "email", st, user_id=u["id"])
    _aud(con, request, u, "suit.supplier.address_draft", pid, {"para": e["para"], "draft": res.get("draft_id")})
    return {"ok": True, "draft_id": res.get("draft_id"), "para": e["para"]}


# ------------------------------------------------ e-mail preparado ao designer (#382, C)
@r.post("/{pid}/preparados/{oid}/enviar")
def enviar_preparado(pid: int, oid: int, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    """O clique "Enviar ao designer" (OPERATOR ou acima): envia de verdade, com a auditoria."""
    sp = _ponte()
    item = um(con, "SELECT order_id FROM suit_outbox WHERE id=?", (oid,))
    if not item or item["order_id"] != pid:
        raise HTTPException(404, "Item não encontrado.")
    from command_center.providers import NaoConectado
    try:
        res = sp.enviar_preparado(con, oid, u["id"])
    except sp.Recusado as e:
        raise HTTPException(400, str(e))
    except NaoConectado as e:
        raise HTTPException(503, f"Gmail não conectado: {e}")
    except Exception as e:
        # debug 29/10: o Gmail recusou ou caiu — o motivo vai à tela, não um 500. O item continua preparado e o próximo
        # clique confere no Gmail antes de mandar (envio sem repetição, #382).
        raise HTTPException(502, f"O Gmail não mandou agora ({type(e).__name__}: {str(e)[:200]}). Tente de novo.")
    _aud(con, request, u, "suit.designer.send_click", pid, {"item": oid, "repetido": bool(res.get("repetido"))})
    return ver(pid, con, u)


@r.post("/{pid}/preparados/{oid}/descartar")
def descartar_preparado(pid: int, oid: int, request: Request, con: sqlite3.Connection = Depends(get_db),
                        u=Depends(auth.exige("OPERATOR"))):
    sp = _ponte()
    item = um(con, "SELECT order_id FROM suit_outbox WHERE id=?", (oid,))
    if not item or item["order_id"] != pid:
        raise HTTPException(404, "Item não encontrado.")
    try:
        sp.descartar_preparado(con, oid, u["id"])
    except sp.Recusado as e:
        raise HTTPException(400, str(e))
    _aud(con, request, u, "suit.designer.discard", pid, {"item": oid})
    return ver(pid, con, u)


# ------------------------------------------------------------- para a IA (#152)
# As ferramentas que a IA da PONTE recebe num evento (#382, C): o mínimo dos Suits. Leads (dados de outros clientes)
# e fornecedores ficam de fora; o painel geral (clientes, Atenção, QuickBooks, Gmail) também (agente_sdk._opcoes).
DA_PONTE = ("suits_pedidos", "suits_pedido", "suits_criar_pedido", "suits_atualizar_pedido", "suits_anotar", "suits_email",
            "suits_anexos", "suits_precisa_humano", "suits_registrar_aprovacao", "suits_pedir_aprovacao_final",
            "suits_marcar_arte_final", "suits_medida_suspeita")


def _permitidos(con, escopo):
    """Os pedidos que este evento pode tocar: o dele; no marcador sem pedido, os abertos com o e-mail de quem escreveu
    (até a IA escolher ou criar um, que passa a ser o único)."""
    if escopo.get("pedido"):
        return {int(escopo["pedido"])}
    if not escopo.get("email"):
        return set()
    return {r["id"] for r in todos(con, """SELECT id FROM suit_orders WHERE discarded_at IS NULL AND closed=0
                                            AND lower(customer_email)=?""", (escopo["email"],))}


def _normal(t):
    return re.sub(r"\s+", " ", (t or "")).strip().lower()


def ferramentas_ia(escopo=None):
    """As ferramentas da aba Suits para o agente do AI Command: (nome, descrição, propriedades,
    obrigatórios, função(con, user_id, **args)). Ler e trabalho interno — nada sai da empresa.
    `escopo` (um evento da ponte, #382): só as da ponte, e cada uma só alcança o pedido do evento."""
    def pedidos(con, uid, busca=None, estado="abertos", **_):
        where, p = ["discarded_at IS NULL"], []          # #195: descartado não é pedido
        if estado in ("abertos", "fechados"):
            where.append("closed=?"); p.append(1 if estado == "fechados" else 0)
        if busca:
            t = f"%{str(busca).lower()}%"
            where.append("(lower(title) LIKE ? OR lower(coalesce(customer_name,'')) LIKE ? OR lower(coalesce(customer_email,'')) LIKE ?)")
            p += [t, t, t]
        return todos(con, f"""SELECT id, title, product, customer_name, customer_email, driver_name, status, order_date, due_on,
                                      ia_ligada FROM suit_orders WHERE {' AND '.join(where)} ORDER BY id DESC LIMIT 100""", p)

    def pedido(con, uid, id, **_):
        p = suits.detalhe(con, int(id))
        if not p:
            return {"erro": "pedido não encontrado"}
        f = um(con, "SELECT * FROM suit_suppliers WHERE id=?", (p["supplier_id"],)) if p.get("supplier_id") else \
            um(con, "SELECT * FROM suit_suppliers WHERE is_current=1")
        crua = um(con, "SELECT * FROM suit_orders WHERE id=?", (int(id),))
        p["email_fornecedor"] = suits.email_fornecedor(con, dict(crua), dict(f) if f else None, {"name": ""})
        return p

    def criar(con, uid, **args):
        return {"id": gravar(con, args, uid, fonte="ia")}

    def _pode_mexer(con, id):
        if (um(con, "SELECT discarded_at FROM suit_orders WHERE id=?", (int(id),)) or {}).get("discarded_at"):
            return {"erro": "pedido descartado (não é pedido de macacão): não mexa nele"}
        if suits.ia_desligada(con, id):
            return {"erro": "a IA está desligada neste pedido (a chave no pedido): não mexa nele, a equipe cuida"}
        return None

    def atualizar_pedido(con, uid, id, **args):
        erro = _pode_mexer(con, id)
        if erro:
            return erro
        try:
            gravar(con, args, uid, int(id), fonte="ia")
        except suits.Invalido as e:
            return {"recusado": str(e)}
        return {"ok": True, "id": int(id)}

    def anotar_(con, uid, id, texto, **_):
        st = um(con, "SELECT status, discarded_at FROM suit_orders WHERE id=?", (int(id),))
        if not st:
            return {"erro": "pedido não encontrado"}
        if st["discarded_at"]:
            return {"erro": "pedido descartado (não é pedido de macacão): não anote nele"}
        if suits.ia_desligada(con, id):
            return {"erro": "a IA está desligada neste pedido (a chave no pedido): a equipe cuida"}
        return {"id": suits.anotar(con, int(id), texto, "ia", st["status"], user_id=uid)}

    def email_(con, uid, id, para, assunto, corpo, anexos=None, responder=True, tipo=None, **_):
        from command_center.providers import suits_ponte
        try:
            return suits_ponte.enviar(con, int(id), para, assunto, corpo, anexos or [], bool(responder), uid, tipo=tipo)
        except suits_ponte.Recusado as e:
            return {"recusado": str(e)}

    def anexos_(con, uid, id, **_):
        from command_center.providers import suits_ponte
        p = um(con, "SELECT final_art FROM suit_orders WHERE id=?", (int(id),)) or {}
        return {"pasta": suits_ponte.pasta(int(id)), "arquivos": suits_ponte.anexos_do_pedido(int(id)),
                "arte_final": suits.arte_final(p), "manual_medidas": os.path.isfile(suits_ponte.manual_pdf())}

    def humano_(con, uid, id, motivo, **_):
        from command_center.providers import suits_ponte
        return suits_ponte.precisa_humano(con, int(id), motivo, uid)

    def leads_(con, uid, busca=None, **_):
        t = f"%{str(busca or '').lower()}%"
        return todos(con, "SELECT * FROM suit_leads WHERE lower(name) LIKE ? OR lower(coalesce(notes,'')) LIKE ? ORDER BY id DESC LIMIT 100", (t, t))

    def fornecedores_(con, uid, **_):
        return todos(con, "SELECT * FROM suit_suppliers ORDER BY is_current DESC, name")

    def aprovacao_(con, uid, id, message_id, trecho, **_):
        """Só num evento da ponte, com o e-mail do cliente que está NESTE evento e o trecho exato dele."""
        from command_center.providers import suits_ponte
        esc = escopo or suits_ponte.ESCOPO.get()
        if not esc:
            return {"recusado": "a aprovação final por e-mail só é registrada pela ponte, com o e-mail do cliente; "
                                "fora dela, a equipe registra à mão na tela do pedido"}
        m = (esc.get("mensagens") or {}).get(message_id)
        if not m or m.get("papel") != "cliente":
            return {"recusado": "o message_id não é de um e-mail do cliente neste evento: use o id que veio em MENSAGENS NOVAS"}
        if not _normal(trecho) or _normal(trecho) not in _normal(m.get("corpo")):
            return {"recusado": "o trecho tem de ser copiado exatamente do e-mail do cliente"}
        p = um(con, "SELECT final_request FROM suit_orders WHERE id=?", (int(id),)) or {}
        pf = suits._json(p.get("final_request"), None)
        e = suits.estado_aprovacao(con, int(id)) or {}
        if not pf or pf.get("arte") != e.get("hash_arte") or pf.get("medidas") != e.get("hash_medidas"):
            return {"recusado": "o cliente ainda não recebeu o e-mail de aprovação final DESTA versão (a arte ou as medidas "
                                "mudaram, ou ele não saiu): mande com suits_pedir_aprovacao_final e espere ele aprovar por escrito"}
        if pf.get("simulado") and not suits_ponte.SIMULAR.get():
            return {"recusado": "o e-mail de aprovação final desta versão não saiu (a ponte está em simulação): a equipe "
                                "confere e registra à mão. Use suits_precisa_humano."}
        if suits_ponte.SIMULAR.get():
            st = um(con, "SELECT status FROM suit_orders WHERE id=?", (int(id),))["status"]
            suits.anotar(con, int(id), f"SIMULAÇÃO — a IA registraria a aprovação final da versão {e.get('versao')}: «{trecho[:300]}»",
                         "ia", st)
            return {"simulado": True, "versao": e.get("versao")}
        try:
            ap = suits.registrar_aprovacao(con, int(id), trecho, message_id, m.get("data"), "ia")
        except suits.Invalido as ex:
            return {"recusado": str(ex)}
        return {"ok": True, "aprovacao": ap["id"], "versao": ap["versao"]}

    def pedir_final_(con, uid, id, introducao=None, **_):
        from command_center.providers import suits_ponte
        erro = _pode_mexer(con, id)
        if erro:
            return erro
        try:
            return suits_ponte.pedir_aprovacao_final(con, int(id), introducao, uid)
        except suits_ponte.Recusado as e:
            return {"recusado": str(e)}

    def arte_(con, uid, id, nome, final=True, **_):
        erro = _pode_mexer(con, id)
        if erro:
            return erro
        try:
            return {"arte_final": suits.marcar_arte_final(con, int(id), nome, bool(final), uid, por_ia=True)}
        except suits.Invalido as e:
            return {"recusado": str(e)}

    def suspeita_(con, uid, id, chave, motivo, **_):
        erro = _pode_mexer(con, id)
        if erro:
            return erro
        try:
            suits.marcar_medidas(con, int(id), [chave], "suspeita", motivo, uid, por_ia=True)
        except suits.Invalido as e:
            return {"recusado": str(e)}
        return {"ok": True}

    s, n, o = {"type": "string"}, {"type": "integer"}, {"type": "object"}
    campos_pedido = {"title": s, "product": s, "quantity": n, "customer_name": s, "customer_email": s, "customer_phone": s,
                     "ship_address": s, "driver_name": s, "language": dict(s, description="idioma do cliente: en, pt, es…"),
                     "supplier_id": n, "order_date": s, "due_on": s, "paid_at": s, "tracking": s,
                     "design": dict(o, description="ideia, cores, logos, posicao_logos, nome, bandeira, observacoes"),
                     "medidas": dict(o, description='{"valores": {"head": 59, "foot": "42 EUR"}, "unidade": "cm|in", "unidade_peso": "kg|lb"}'),
                     "client_id": dict(n, description="o card do cliente no painel (urace_clientes), quando já existe"),
                     "status": dict(s, enum=suits.CODIGOS), "nota": s, "site_order": s,
                     "ia_ligada": dict({"type": "boolean"}, description="false: o pedido nasce com a IA desligada"),
                     "is_test": dict({"type": "boolean"}, description="pedido de teste: nunca manda e-mail real"),
                     "gmail_thread_cliente": s, "gmail_thread_designer": s, "gmail_thread_fornecedor": s}
    lista = [
        ("suits_pedidos", "Pedidos de macacão (aba Suits), mais recentes primeiro. Filtra por nome ou e-mail.",
         {"busca": s, "estado": dict(s, enum=["abertos", "fechados", "todos"])}, [], pedidos),
        ("suits_pedido", "Um pedido de macacão inteiro: cliente, etapa, as 29 medidas (com o estado de cada uma), design, arte "
         "final, aprovação, notas e o e-mail ao fornecedor já montado pelo modelo.", {"id": n}, ["id"], pedido),
        ("suits_criar_pedido", "Registra um pedido de macacão novo na aba Suits (etapa standby se não disser outra). "
         "Nunca invente medida ou dado do cliente.", campos_pedido, [], criar),
        ("suits_atualizar_pedido", "Atualiza um pedido de macacão: dados, design, medidas (só as que vierem) e etapa. "
         "As travas valem: approved e sent_to_supplier pedem a aprovação final válida; in_transit pede o rastreio; fotos "
         "recebidas, conferido e endereço enviado são da equipe.", dict(campos_pedido, id=n), ["id"], atualizar_pedido),
        ("suits_anotar", "Escreve na linha do tempo do pedido o que a IA fez ou descobriu.", {"id": n, "texto": s},
         ["id", "texto"], anotar_),
        ("suits_email", "Manda e-mail sobre o pedido para o CLIENTE ou o FORNECEDOR daquele pedido (o endereço vem do pedido, "
         "não de você), respondendo na conversa que já existe; ao DESIGNER, o e-mail fica PREPARADO e uma pessoa da equipe "
         "envia. Anexos: nomes de suits_anexos, ou \"manual_medidas\" (o PDF do manual de medidas, obrigatório nas "
         "boas-vindas: tipo=\"boas_vindas\"). Para o designer, só o design e \"Suits #id\": nunca nome completo, e-mail, "
         "telefone, endereço, valor ou pagamento do cliente. Para o cliente, nunca o nome ou o contato do designer. Se a "
         "ponte estiver em simulação, o e-mail vira nota no pedido e não sai.",
         {"id": n, "para": dict(s, enum=["cliente", "designer", "fornecedor"]), "assunto": s, "corpo": s,
          "anexos": {"type": "array", "items": s}, "responder": {"type": "boolean"},
          "tipo": dict(s, enum=["boas_vindas", "outro"])},
         ["id", "para", "assunto", "corpo"], email_),
        ("suits_anexos", "Os arquivos do pedido (o que chegou por e-mail: medidas, inspiração, logos, arte), qual é a arte "
         "final e onde lê-los.", {"id": n}, ["id"], anexos_),
        ("suits_precisa_humano", "Para e chama a equipe: aparece em Precisa de atenção e na linha do tempo do pedido.",
         {"id": n, "motivo": s}, ["id", "motivo"], humano_),
        ("suits_pedir_aprovacao_final", "Manda ao cliente o e-mail de APROVAÇÃO FINAL montado pelo painel: a versão exata, a "
         "arte final anexada, as medidas e a política (não retornável, não reembolsável). Só quando a arte final estiver "
         "marcada e TODAS as medidas conferidas pela equipe. `introducao`: uma ou duas frases suas, no idioma do cliente.",
         {"id": n, "introducao": s}, ["id"], pedir_final_),
        ("suits_registrar_aprovacao", "Registra a aprovação final escrita do cliente. SÓ quando ele aprovar expressamente a "
         "versão final mostrada no e-mail de aprovação final; \"gostei\" ou aprovação de versão anterior não contam. "
         "`message_id`: o id da mensagem dele em MENSAGENS NOVAS; `trecho`: copiado exatamente dela.",
         {"id": n, "message_id": s, "trecho": s}, ["id", "message_id", "trecho"], aprovacao_),
        ("suits_marcar_arte_final", "Marca (ou desmarca, final=false) um arquivo do pedido como ARTE FINAL: a versão que o "
         "cliente aprova e que vai ao fornecedor. Mudar a arte final derruba a aprovação.",
         {"id": n, "nome": s, "final": {"type": "boolean"}}, ["id", "nome"], arte_),
        ("suits_medida_suspeita", "Marca uma medida como SUSPEITA (o número parece errado), com o motivo. Trava a aprovação "
         "final até a equipe conferir. Conferir é só da equipe.",
         {"id": n, "chave": dict(s, enum=sorted(suits.CHAVES)), "motivo": s}, ["id", "chave", "motivo"], suspeita_),
        ("suits_leads", "Leads de macacão (oportunidades guardadas para vender de novo).", {"busca": s}, [], leads_),
        ("suits_fornecedores", "Fornecedores de macacão com contato, FIA, preço e qual é o atual.", {}, [], fornecedores_),
    ]
    if escopo is None:
        return lista
    return [(nome, desc, props, obrig, _no_escopo(nome, fn, escopo)) for nome, desc, props, obrig, fn in lista if nome in DA_PONTE]


def _no_escopo(nome, fn, escopo):
    """Cada ferramenta só alcança o pedido do evento (#382, C). Outro id é recusado."""
    def recusa(id_):
        return {"recusado": f"Neste evento da ponte só dá para ler e mexer no pedido dele; o pedido #{id_} é outro. É "
                            "proibido trazer dados de outros clientes."}

    def envolta(con, uid, **args):
        if nome == "suits_pedidos":
            ok = _permitidos(con, escopo)
            return [p for p in fn(con, uid, estado="todos") if p["id"] in ok]
        if nome == "suits_criar_pedido":
            if escopo.get("pedido") or _permitidos(con, escopo):
                return {"recusado": "esta pessoa já tem pedido neste evento: atualize o dela (suits_atualizar_pedido) em vez de criar"}
            res = fn(con, uid, **args)
            escopo["pedido"] = res["id"]               # daqui em diante, o evento é deste pedido
            return res
        id_ = args.get("id")
        try:
            id_ = int(id_)
        except (TypeError, ValueError):
            return {"recusado": "diga o id do pedido deste evento"}
        if id_ not in _permitidos(con, escopo):
            return recusa(id_)
        escopo["pedido"] = id_                         # o marcador escolheu o pedido dela: só ele, daqui em diante
        return fn(con, uid, **args)
    return envolta
