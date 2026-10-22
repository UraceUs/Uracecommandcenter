"""WhatsApp dos grupos do ateliê (#383) — as rotas. As regras moram em `providers/atelie_whatsapp.py`.

- `POST /whatsapp/entrada`: só o plugin `urace-atelie` do OpenClaw, na mesma máquina. Vale com as três
  coisas juntas: pedido de 127.0.0.1 (o uvicorn troca pelo IP real quando vem pelo Caddy), sem cabeçalho de
  proxy (X-Forwarded-For) e com o segredo `WA_GRUPOS_TOKEN` de ~/.urace/whatsapp-grupos.env. Nada do corpo
  vai para o log.
- O resto é a tela: ver, aprovar/descartar rascunho, ligar mensagem ao pedido, suit aprovado e rastreio
  (OPERATOR, como o resto da aba Suits).
"""
import hmac
import json
import os
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from command_center.api import auth
from command_center.api.cache_api import paginar
from command_center.db import auditar, get_db, um
from command_center.providers import atelie_whatsapp as wa

r = APIRouter(prefix="/ops/api/atelie", tags=["atelie"])
LOCAIS = ("127.0.0.1", "::1")
CORPO_MAX = 80 * 1024 * 1024


def _aud(con, request, u, evento, eid, detalhe=None, tipo="suit_order"):
    auditar(con, evento, f"user:{u['id']}", user_id=u["id"], entity_type=tipo, entity_id=eid, detail=detalhe,
            ip=auth._ip(request) if request else None)


# ------------------------------------------------------------------ entrada (o plugin do OpenClaw)
@r.post("/whatsapp/entrada")
async def entrada(request: Request, con: sqlite3.Connection = Depends(get_db)):
    host = request.client.host if request.client else ""
    if host not in LOCAIS or request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip") or request.headers.get("forwarded"):
        raise HTTPException(403, "só da própria máquina")
    cfg = wa.config()
    chave = request.headers.get("x-urace-atelie-token", "")
    if not cfg["token"] or not hmac.compare_digest(chave.encode(), cfg["token"].encode()):
        raise HTTPException(401, "segredo errado")
    corpo = await request.body()
    if len(corpo) > CORPO_MAX:
        raise HTTPException(413, "grande demais")
    try:
        dados = json.loads(corpo or b"{}")
    except ValueError:
        raise HTTPException(400, "JSON inválido")
    if not isinstance(dados, dict):
        raise HTTPException(400, "JSON inválido")
    return wa.receber(con, dados, cfg)


# ------------------------------------------------------------------ a tela
def _publico(cfg):
    """O estado da configuração sem segredo: o número só nos 4 últimos dígitos."""
    num = cfg["numero"] or ""
    return {"existe": cfg["existe"], "aplicar": cfg["aplicar"], "tem_segredo": bool(cfg["token"]),
            "numero": f"…{num[-4:]}" if len(num) >= 4 else None,
            "grupos": [{"papel": g["papel"], "nome": g["nome"], "configurado": bool(g["jid"]), "idioma": g["idioma"]} for g in cfg["grupos"]]}


@r.get("/whatsapp")
def estado(con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    from command_center.providers import suits_ponte
    return {"config": _publico(wa.config()), "envio_automatico": suits_ponte.config(con)["envio_automatico"] == "1",
            "rascunhos": um(con, "SELECT COUNT(*) AS n FROM atelie_wa_saidas WHERE estado IN ('rascunho','falhou')")["n"],
            "sem_pedido": um(con, "SELECT COUNT(*) AS n FROM atelie_wa_mensagens WHERE estado IN ('sem_pedido','ambigua')")["n"]}


@r.get("/whatsapp/rascunhos")
def rascunhos(response: Response, limit: int | None = 50, offset: int = 0, con: sqlite3.Connection = Depends(get_db),
              u=Depends(auth.exige("OPERATOR"))):
    sql = """SELECT s.id, s.order_id, s.papel, s.motivo, s.texto, s.anexos, s.estado, s.erro, s.created_at, o.title
             FROM atelie_wa_saidas s JOIN suit_orders o ON o.id=s.order_id
             WHERE s.estado IN ('rascunho','falhou') ORDER BY s.id DESC"""
    return paginar(con, sql, [], response, limit, offset)


@r.get("/whatsapp/sem-pedido")
def sem_pedido(response: Response, limit: int | None = 50, offset: int = 0, con: sqlite3.Connection = Depends(get_db),
               u=Depends(auth.exige("OPERATOR"))):
    sql = """SELECT id, papel, remetente_nome, texto, anexos, estado, candidatos, at FROM atelie_wa_mensagens
             WHERE estado IN ('sem_pedido','ambigua') ORDER BY id DESC"""
    return paginar(con, sql, [], response, limit, offset)


@r.get("/pedidos/{pid}")
def do_pedido(pid: int, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    p = um(con, "SELECT id, tracking, suit_approved_at, address_sent_at FROM suit_orders WHERE id=?", (pid,))
    if not p:
        raise HTTPException(404, "Pedido não encontrado.")
    cfg = wa.config()
    return dict(wa.mensagens_do_pedido(con, pid), pedido=dict(p), config=_publico(cfg))


class AprovarIn(BaseModel):
    texto: str | None = None


@r.post("/saidas/{sid}/aprovar")
def aprovar(sid: int, dados: AprovarIn, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    try:
        res = wa.aprovar(con, sid, u["id"], dados.texto)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except wa.Recusado as e:
        raise HTTPException(400, str(e))
    _aud(con, request, u, "atelie.draft.approved", sid, tipo="atelie_wa_saida")
    return res


@r.post("/saidas/{sid}/descartar")
def descartar(sid: int, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    try:
        feito = wa.descartar(con, sid, u["id"])
    except LookupError as e:
        raise HTTPException(404, str(e))
    if feito:
        _aud(con, request, u, "atelie.draft.discarded", sid, tipo="atelie_wa_saida")
    return {"ok": True, "descartado": feito}


class EscreverIn(BaseModel):
    papel: str
    texto: str


@r.post("/pedidos/{pid}/escrever")
def escrever(pid: int, dados: EscreverIn, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    """A equipe escreve no grupo pelo pedido: quem escreveu é a aprovação (sai na hora, com as mesmas guardas)."""
    try:
        res = wa.propor(con, pid, dados.papel, dados.texto, criado_por=f"user:{u['id']}", user_id=u["id"])
    except wa.Recusado as e:
        raise HTTPException(400, str(e))
    _aud(con, request, u, "atelie.whatsapp.written", pid, {"papel": dados.papel})
    return res


@r.post("/pedidos/{pid}/suit-aprovado")
def suit_aprovado(pid: int, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    try:
        res = wa.aprovar_suit(con, pid, u["id"])
    except wa.Recusado as e:
        raise HTTPException(400, str(e))
    _aud(con, request, u, "atelie.suit.approved", pid)
    return res


class RastreioIn(BaseModel):
    codigo: str
    transportadora: str | None = None


@r.post("/pedidos/{pid}/rastreio")
def rastreio(pid: int, dados: RastreioIn, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    try:
        res = wa.registrar_rastreio(con, pid, dados.codigo, dados.transportadora, u["id"])
    except wa.Recusado as e:
        raise HTTPException(400, str(e))
    _aud(con, request, u, "atelie.tracking", pid)
    return res


class VincularIn(BaseModel):
    order_id: int


@r.post("/mensagens/{mid}/vincular")
def vincular(mid: int, dados: VincularIn, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    try:
        wa.vincular(con, mid, dados.order_id, u["id"])
    except LookupError as e:
        raise HTTPException(404, str(e))
    except wa.Recusado as e:
        raise HTTPException(400, str(e))
    _aud(con, request, u, "atelie.message.linked", mid, {"pedido": dados.order_id}, tipo="atelie_wa_mensagem")
    return {"ok": True}


@r.get("/mensagens/{mid}/anexos/{nome}")
def anexo_solto(mid: int, nome: str, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    """O arquivo de uma mensagem ainda sem pedido (o ligado vive na pasta do pedido, rota de Suits)."""
    m = um(con, "SELECT order_id FROM atelie_wa_mensagens WHERE id=?", (mid,))
    if not m or m["order_id"]:
        raise HTTPException(404)
    caminho = os.path.join(wa._urace_dir(), "atelie", "whatsapp", str(mid), os.path.basename(nome))
    if not os.path.isfile(caminho):
        raise HTTPException(404)
    from fastapi.responses import FileResponse
    return FileResponse(caminho, filename=os.path.basename(nome), headers={"Cache-Control": "private, max-age=300"})

