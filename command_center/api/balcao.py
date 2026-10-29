"""Balcão (#87): a tela do leitor de QR e de código de barras.

As regras moram em `providers/balcao.py`; aqui fica quem pode o quê:

- **ler, lançar (cobrar / guardar / usar a peça do cliente), desfazer, cadastrar código e
  imprimir etiqueta** é OPERATOR: é o mecânico com o leitor na mão (dono, 05/10: *"o mecânico
  vai lançar as peças e assim que ele lançar a peça já salva a invoice"*).
- **criar o item no QuickBooks e enviar a invoice** é MANAGER: um mexe no catálogo da
  contabilidade, o outro manda cobrança para o cliente.
- **conferir o documento com foto de quem assinou a waiver** (#117) é OPERATOR: é quem está no
  check-in. Sem imagem e sem número do documento; o corpo só aceita os campos da lista.

Cada lançamento grava primeiro aqui (commit) e depois leva a invoice ao QuickBooks. Se o
QuickBooks falhar, a leitura fica salva e a tela mostra o erro com "Tentar de novo".
"""
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from command_center.api import auth
from command_center.db import auditar, get_db, um
from command_center.providers import balcao as b, estoque

r = APIRouter(prefix="/ops/api/balcao", tags=["balcao"])


def _aud(con, request, u, evento, tipo, eid, detalhe):
    auditar(con, evento, f"user:{u['id']}", user_id=u["id"], entity_type=tipo, entity_id=eid, detail=detalhe,
            ip=auth._ip(request))


def _erro(e):
    if isinstance(e, b.Confirmar):
        return HTTPException(409, {"motivo": e.motivo, "mensagem": str(e)})
    return HTTPException(400, str(e))


def _gerente(u):
    return bool(u.get("free")) or auth.pode(u.get("role"), "MANAGER")


@r.get("/ler")
def ler(codigo: str, client_id: int | None = None, con: sqlite3.Connection = Depends(get_db),
        u=Depends(auth.exige("OPERATOR"))):
    """O que o leitor mandou: QR de cliente, peça conhecida ou código novo."""
    try:
        return b.ler(con, codigo, client_id)
    except (b.ErroBalcao, estoque.ErroEstoque) as e:
        raise _erro(e)


@r.get("/cliente/{client_id}")
def cliente(client_id: int, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    try:
        out = {**b.do_cliente(con, client_id), "gerente": _gerente(u)}
    except LookupError:
        raise HTTPException(404, "Cliente não encontrado.")
    con.commit()                                     # o código do QR nasce na primeira vez
    return out


@r.get("/cliente/{client_id}/qr.svg")
def qr(client_id: int, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    try:
        svg = b.qr_svg(con, client_id)
    except LookupError:
        raise HTTPException(404, "Cliente não encontrado.")
    con.commit()
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "private, no-store"})


@r.get("/c/{codigo}")
def pelo_qr(codigo: str, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    """O QR lido pela câmera de um celular qualquer abre /ops/c/<código>: a tela pergunta aqui de quem é."""
    c = b.cliente_pelo_codigo(con, codigo)
    if not c:
        raise HTTPException(404, "QR de cliente não reconhecido.")
    return b.resumo_cliente(c)


class IdCheckIn(BaseModel):
    """#117: o que a equipe conferiu. Lista fechada e nada mais: um campo de imagem ou de número do documento é 422."""
    model_config = ConfigDict(extra="forbid")
    client_id: int = Field(..., ge=1, le=2**63 - 1)        # o card aberto na tela: a waiver tem de ser dele
    document_type: Literal["drivers_license", "passport", "state_id", "other_government_id"]
    name_matches: StrictBool
    minor_age_matches: StrictBool | None = None             # só na parental (piloto menor); obrigatório nela


@r.post("/waivers/{wid}/id-check", status_code=201)
def conferir_documento(dados: IdCheckIn, request: Request, wid: int = Path(..., ge=1, le=2**63 - 1),
                       con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    """#117: o documento com foto de quem assinou foi conferido no balcão. Vira `id_checked` (ou `id_check_failed`, que
    aparece em "Precisa de atenção") na trilha da waiver e `waiver.id_check` na auditoria. Não bloqueia nada."""
    try:
        res = b.conferir_documento(con, wid, dados.client_id, dados.document_type, dados.name_matches,
                                   dados.minor_age_matches, usuario=u, ip=auth._ip(request),
                                   user_agent=request.headers.get("user-agent"))
    except LookupError:
        raise HTTPException(404, "Waiver não encontrada neste card.")
    except b.ForaDeVigor as e:
        raise HTTPException(409, str(e))
    except b.ErroBalcao as e:
        raise HTTPException(400, str(e))
    return {**res, "waivers": b.waivers_do_card(con, dados.client_id)}


class LancarIn(BaseModel):
    client_id: int
    item_id: int
    modo: str
    qty: float = 1
    local: str = estoque.SEDE
    codigo: str | None = None
    confirmado: bool = False


def _sincronizar(con, pinv_id):
    if pinv_id:
        b.sincronizar_qbo(con, pinv_id)
        con.commit()


@r.post("/lancar", status_code=201)
def lancar(dados: LancarIn, request: Request, con: sqlite3.Connection = Depends(get_db),
           u=Depends(auth.exige("OPERATOR"))):
    try:
        s = b.lancar(con, dados.client_id, dados.item_id, dados.modo, dados.qty, dados.local, u["id"],
                     dados.codigo, dados.confirmado)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except (b.ErroBalcao, estoque.ErroEstoque) as e:
        con.rollback()
        raise _erro(e)
    _aud(con, request, u, f"balcao.{dados.modo}", "client", dados.client_id,
         {"item": dados.item_id, "qty": dados.qty, "leitura": s["id"], "invoice_pecas": s["parts_invoice_id"]})
    con.commit()
    _sincronizar(con, s["parts_invoice_id"])
    return {"leitura": dict(s), **b.do_cliente(con, dados.client_id)}


@r.post("/leituras/{scan_id}/desfazer")
def desfazer(scan_id: int, request: Request, con: sqlite3.Connection = Depends(get_db),
             u=Depends(auth.exige("OPERATOR"))):
    try:
        s = b.desfazer(con, scan_id, u["id"])
    except LookupError:
        raise HTTPException(404, "Leitura não encontrada.")
    except (b.ErroBalcao, estoque.ErroEstoque) as e:
        con.rollback()
        raise _erro(e)
    _aud(con, request, u, "balcao.desfazer", "client", s["client_id"], {"leitura": scan_id, "modo": s["mode"]})
    con.commit()
    _sincronizar(con, s["parts_invoice_id"])
    return b.do_cliente(con, s["client_id"])


class CodigoIn(BaseModel):
    codigo: str
    item_id: int | None = None
    # peça nova, cadastrada na hora em que o código aparece (o mecânico pode: dono, 23/09)
    nome: str | None = None
    kind: str = "peca"
    category: str | None = None
    # gerente: preço final e o item no QuickBooks, criado na hora (dono, 05/10)
    price: float | None = None
    qbo_item_id: str | None = None
    qbo_categoria_id: str | None = None


@r.post("/codigos", status_code=201)
def cadastrar(dados: CodigoIn, request: Request, con: sqlite3.Connection = Depends(get_db),
              u=Depends(auth.exige("OPERATOR"))):
    gerente = _gerente(u)
    if (dados.price is not None or dados.qbo_item_id or dados.qbo_categoria_id) and not gerente:
        raise HTTPException(403, "Preço e item do QuickBooks são do gerente.")
    try:
        # a peça nova (ou o preço) e o código numa transação só: código recusado não deixa peça órfã na prateleira
        # (a conexão é autocommit; o rollback de antes não desfazia o que já estava gravado)
        with transacao(con, imediata=True):
            item_id = dados.item_id
            if not item_id:
                item_id = estoque.criar_item(con, dados.kind, dados.nome or "", category=dados.category, price=dados.price)
            elif dados.price is not None:
                estoque.atualizar_item(con, item_id, price=dados.price)
            cod = b.cadastrar_codigo(con, dados.codigo, item_id, u["id"])
            _aud(con, request, u, "balcao.codigo", "stock_item", item_id, {"codigo": cod, "novo": not dados.item_id})
    except (b.ErroBalcao, estoque.ErroEstoque) as e:
        raise _erro(e)
    aviso = None
    if gerente and (dados.qbo_item_id or dados.qbo_categoria_id):
        try:
            b.ligar_item_qbo(con, item_id, dados.qbo_item_id, dados.qbo_categoria_id)
            _aud(con, request, u, "balcao.item_qbo", "stock_item", item_id,
                 {"qbo_item": dados.qbo_item_id, "categoria": dados.qbo_categoria_id})
            con.commit()
        except Exception as e:                       # noqa: BLE001 — o código já está salvo
            con.rollback()
            aviso = f"Código salvo, mas o item do QuickBooks não foi criado: {str(e)[:300]}"
    return {"codigo": cod, "item": b.item_publico(con, estoque.item(con, item_id)), "aviso": aviso}


class ItemQboIn(BaseModel):
    qbo_item_id: str | None = None
    categoria_id: str | None = None
    price: float | None = None


@r.post("/itens/{item_id}/quickbooks")
def item_qbo(item_id: int, dados: ItemQboIn, request: Request, con: sqlite3.Connection = Depends(get_db),
             u=Depends(auth.exige("MANAGER"))):
    from command_center.providers import NaoConectado
    try:
        if dados.price is not None:
            estoque.atualizar_item(con, item_id, price=dados.price)
        it = b.ligar_item_qbo(con, item_id, dados.qbo_item_id, dados.categoria_id)
    except NaoConectado:
        con.rollback()
        raise HTTPException(503, "QuickBooks não está conectado.")
    except (b.ErroBalcao, estoque.ErroEstoque) as e:
        con.rollback()
        raise _erro(e)
    except Exception as e:                           # noqa: BLE001 — recusa do QuickBooks
        con.rollback()
        raise HTTPException(502, f"QuickBooks: {str(e)[:300]}")
    _aud(con, request, u, "balcao.item_qbo", "stock_item", item_id, {"qbo_item": it["qbo_item_id"]})
    con.commit()
    return {"item": b.item_publico(con, it)}


@r.get("/categorias")
def categorias(con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("MANAGER"))):
    """As categorias do QuickBooks e os itens de peça que já existem lá (do espelho)."""
    from command_center.providers import NaoConectado
    try:
        cats, conectado = b._qbo().categorias_sistema(), True
    except NaoConectado:                             # a tela avisa e o item fica para depois
        cats, conectado = [], False
    itens = [dict(x) for x in con.execute("SELECT id, name, full_name, price FROM qbo_items WHERE active=1 "
                                          "AND COALESCE(type,'')!='Category' ORDER BY full_name").fetchall()]
    return {"categorias": cats, "itens": itens, "conectado": conectado}


@r.post("/itens/{item_id}/codigo-urace", status_code=201)
def codigo_urace(item_id: int, request: Request, con: sqlite3.Connection = Depends(get_db),
                 u=Depends(auth.exige("OPERATOR"))):
    try:
        cod = b.codigo_urace(con, item_id, u["id"])
    except (b.ErroBalcao, estoque.ErroEstoque) as e:
        raise _erro(e)
    con.commit()
    return {"codigo": cod}


@r.get("/itens/{item_id}/etiqueta.pdf")
def etiqueta(item_id: int, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    try:
        pdf = b.etiqueta_pdf(con, item_id)
    except estoque.ErroEstoque as e:
        raise _erro(e)
    con.commit()
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="etiqueta-{item_id}.pdf"', "Cache-Control": "no-store"})


# ------------------------------------------------------------------ etiquetas de prateleira (#187)
def _cats(categorias):
    return [c for c in (x.strip() for x in (categorias or "").split("|")) if c] or None


@r.get("/etiquetas")
def etiquetas_resumo(categorias: str | None = None, con: sqlite3.Connection = Depends(get_db),
                     u=Depends(auth.exige("MANAGER"))):
    """Os produtos do catálogo do QuickBooks que viram etiqueta, e as duplicatas (só relatório)."""
    from command_center.providers import etiquetas as et
    itens = et.produtos(con, _cats(categorias))
    return {"categorias": et.categorias(con), "total": len(itens), "duplicatas": et.duplicatas(et.produtos(con)),
            "atualizado": (um(con, "SELECT MAX(synced_at) AS m FROM qbo_items") or {}).get("m")}


@r.get("/etiquetas.pdf")
def etiquetas_pdf(categorias: str | None = None, formato: str = Query("folha", pattern="^(folha|uma)$"),
                  con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("MANAGER"))):
    from command_center.providers import etiquetas as et
    try:
        pdf = et.pdf(et.produtos(con, _cats(categorias)), formato)
    except et.ErroEtiqueta as e:
        raise HTTPException(400, str(e))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="urace-etiquetas-{formato}.pdf"',
                             "Cache-Control": "no-store"})


@r.get("/invoices")
def invoices(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
             con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    """Invoices de peças abertas: o que falta enviar."""
    return {**b.a_enviar(con, limit, offset), "gerente": _gerente(u)}


@r.post("/invoices/{pinv_id}/sincronizar")
def sincronizar(pinv_id: int, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    p = b.sincronizar_qbo(con, pinv_id)
    if not p:
        raise HTTPException(404, "Invoice de peças não encontrada.")
    con.commit()
    return b.invoice_publica(con, p)


@r.post("/invoices/{pinv_id}/conferir-pagamento")
def conferir_pagamento(pinv_id: int, request: Request, con: sqlite3.Connection = Depends(get_db),
                       u=Depends(auth.exige("OPERATOR"))):
    """Depois de passar o cartão no GoPayment: confere no QuickBooks se a invoice ficou paga."""
    from command_center.providers import NaoConectado
    if not b.cartao_ligado():
        raise HTTPException(404, "Cartão no balcão desligado (CC_BALCAO_CARTAO=0).")
    try:
        r = b.conferir_pagamento(con, pinv_id, u["id"])
    except LookupError:
        raise HTTPException(404, "Invoice de peças não encontrada.")
    except b.ErroBalcao as e:
        raise HTTPException(400, str(e))
    except NaoConectado:
        raise HTTPException(503, "QuickBooks não está conectado.")
    con.commit()
    return {**r, "invoice": b.invoice_publica(con, um(con, "SELECT * FROM parts_invoices WHERE id=?", (pinv_id,)))}


@r.post("/invoices/{pinv_id}/enviar")
def enviar(pinv_id: int, request: Request, con: sqlite3.Connection = Depends(get_db),
           u=Depends(auth.exige("MANAGER"))):
    from command_center.providers import NaoConectado
    try:
        p = b.enviar(con, pinv_id, u["id"])
    except LookupError:
        raise HTTPException(404, "Invoice de peças não encontrada.")
    except NaoConectado:
        raise HTTPException(503, "QuickBooks não está conectado.")
    except b.ErroBalcao as e:
        raise _erro(e)
    except Exception as e:                           # noqa: BLE001 — recusa do QuickBooks
        raise HTTPException(502, f"QuickBooks: {str(e)[:300]}")
    _aud(con, request, u, "balcao.enviar", "client", p["client_id"],
         {"invoice_pecas": p["id"], "qbo": p["qbo_invoice_id"], "para": p["sent_to"]})
    con.commit()
    return b.invoice_publica(con, um(con, "SELECT * FROM parts_invoices WHERE id=?", (p["id"],)))


# ------------------------------------------------------------------ #180: celular, uma mão
# O mecânico lê a peça e toca no piloto do dia; a leitura fica PENDENTE e o gerente confirma na
# Revisão. Ler e registrar é OPERATOR (o mecânico); revisar é MANAGER (dono, 09/10: "eles não
# precisam ter acesso disso pelo celular").
from command_center.providers import balcao_rapido as br  # noqa: E402

_DATA = r"^\d{4}-\d{2}-\d{2}$"


@r.get("/rapido")
def rapido(data: str | None = Query(None, pattern=_DATA), con: sqlite3.Connection = Depends(get_db),
           u=Depends(auth.exige("OPERATOR"))):
    """A tela do celular: os pilotos do dia (botões) e as últimas leituras de quem está lendo."""
    data = data or b.hoje()
    return {"data": data, "hoje": b.hoje(), "pilotos": br.pilotos_do_dia(con, data), "minhas": br.minhas(con, data, u["id"])}


@r.get("/rapido/auditoria")
def rapido_auditoria(data: str = Query(..., pattern=_DATA), con: sqlite3.Connection = Depends(get_db),
                     u=Depends(auth.exige("OPERATOR"))):
    """#189: quem lançou o quê naquele dia (gerente e acesso livre)."""
    if not _gerente(u):
        raise HTTPException(403, "A auditoria do balcão é do gerente.")
    return br.auditoria(con, data)


@r.get("/rapido/clientes")
def rapido_clientes(q: str = Query(..., min_length=2, max_length=80), con: sqlite3.Connection = Depends(get_db),
                    u=Depends(auth.exige("OPERATOR"))):
    """#189: o piloto não está no calendário do dia — busca pelo nome (só o nome volta)."""
    return br.buscar_clientes(con, q)


class RapidoIn(BaseModel):
    codigo: str
    data: str | None = None
    client_id: int | None = None
    pilot_id: int | None = None
    local: str | None = None                      # #206: de onde a peça sai (galpão, trailer, pista)


@r.post("/rapido", status_code=201)
def rapido_registrar(dados: RapidoIn, request: Request, con: sqlite3.Connection = Depends(get_db),
                     u=Depends(auth.exige("OPERATOR"))):
    import re as _re
    data = dados.data or b.hoje()
    if not _re.fullmatch(_DATA, data):
        raise HTTPException(400, "data inválida")
    try:
        p = br.registrar(con, dados.codigo, data, dados.client_id, dados.pilot_id, u["id"], dados.local)
    except (b.ErroBalcao, br.ErroRapido, estoque.ErroEstoque) as e:
        raise HTTPException(400, str(e))
    _aud(con, request, u, "balcao.rapido.os" if p["direto"] else "balcao.rapido",
         "counter_scan" if p["direto"] else "counter_pending", p["id"],
         {"codigo": p["code"], "cliente": p["client_id"], "piloto": p["pilot_id"], "data": data, "motivo": p.get("motivo")})
    con.commit()
    if p["direto"]:
        _sincronizar(con, p["parts_invoice_id"])   # a OS do dia sobe para o QuickBooks (não é enviada)
    return p


@r.post("/rapido/{pid}/desfazer")
def rapido_desfazer(pid: int, request: Request, con: sqlite3.Connection = Depends(get_db),
                    u=Depends(auth.exige("OPERATOR"))):
    try:
        br.desfazer(con, pid, None if _gerente(u) else u["id"])
    except LookupError:
        raise HTTPException(404, "Leitura não encontrada.")
    except br.ErroRapido as e:
        raise HTTPException(400, str(e))
    _aud(con, request, u, "balcao.rapido.desfazer", "counter_pending", pid, None)
    return {"ok": True}


@r.post("/rapido/lancada/{scan_id}/desfazer")
def rapido_desfazer_lancada(scan_id: int, request: Request, con: sqlite3.Connection = Depends(get_db),
                            u=Depends(auth.exige("OPERATOR"))):
    """#206: desfazer pelo celular a peça que foi direto para a OS."""
    try:
        s = br.desfazer_lancada(con, scan_id, u["id"], _gerente(u))
    except LookupError:
        raise HTTPException(404, "Leitura não encontrada.")
    except (b.ErroBalcao, br.ErroRapido, estoque.ErroEstoque) as e:
        con.rollback()
        raise HTTPException(400, str(e))
    _aud(con, request, u, "balcao.rapido.desfazer_os", "client", s["client_id"], {"leitura": scan_id})
    con.commit()
    _sincronizar(con, s["parts_invoice_id"])
    return {"ok": True}


@r.get("/revisao")
def revisao(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
            con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("MANAGER"))):
    return br.revisao(con, limit, offset)


class ConfirmarIn(BaseModel):
    modo: str
    client_id: int | None = None
    item_id: int | None = None
    confirmado: bool = False
    local: str | None = None                      # #206: galpão, trailer ou pista (antes, sempre o galpão)


@r.post("/revisao/{pid}/confirmar")
def revisao_confirmar(pid: int, dados: ConfirmarIn, request: Request, con: sqlite3.Connection = Depends(get_db),
                      u=Depends(auth.exige("MANAGER"))):
    con.execute("BEGIN IMMEDIATE")
    try:
        s = br.confirmar(con, pid, dados.modo, u["id"], dados.client_id, dados.item_id, dados.confirmado, dados.local)
    except LookupError as e:
        con.execute("ROLLBACK")
        raise HTTPException(404, str(e))
    except (b.ErroBalcao, br.ErroRapido, estoque.ErroEstoque) as e:
        con.execute("ROLLBACK")
        raise _erro(e)
    except Exception:
        con.execute("ROLLBACK")
        raise
    _aud(con, request, u, f"balcao.revisao.{dados.modo}", "counter_pending", pid,
         {"leitura": s["id"], "cliente": s["client_id"], "item": s["item_id"], "invoice_pecas": s["parts_invoice_id"]})
    con.execute("COMMIT")
    _sincronizar(con, s["parts_invoice_id"])
    return {"leitura": dict(s), **br.revisao(con)}


class DescartarIn(BaseModel):
    nota: str | None = None


@r.post("/revisao/{pid}/descartar")
def revisao_descartar(pid: int, dados: DescartarIn, request: Request, con: sqlite3.Connection = Depends(get_db),
                      u=Depends(auth.exige("MANAGER"))):
    try:
        br.descartar(con, pid, u["id"], dados.nota)
    except LookupError:
        raise HTTPException(404, "Leitura não encontrada.")
    except br.ErroRapido as e:
        raise HTTPException(400, str(e))
    _aud(con, request, u, "balcao.revisao.descartar", "counter_pending", pid, {"nota": dados.nota})
    return br.revisao(con)


# ------------------------------------------------------------------ #341: rascunho de invoice em lote
# Dono, 19/10: "colocar peças e valores em um rascunho de bulk para o cliente e dali o command center cria a invoice
# com os itens que eu falar; se não tiver item ele cria". Montar o rascunho (linhas, quantidade, PREÇO da linha,
# descrição) e criar a invoice é OPERATOR (#346, dono, 19/10: "as peças que o mecânico lê os códigos geram a invoice
# e salve, fica pendente só a revisão para confirmar/alterar pelo gerente"). A invoice de quem não é gerente fica
# aguardando a REVISÃO (MANAGER): confirmar, ou alterar as linhas, que atualiza a mesma invoice no QuickBooks. Enviar e
# cobrar no cartão só depois da revisão. "Conferir no QuickBooks" (resposta perdida) é MANAGER.
from command_center.db import transacao  # noqa: E402
from command_center.providers import balcao_rascunho as rz  # noqa: E402



@r.get("/quickbooks/itens")
def qbo_itens(q: str | None = Query(None, max_length=80), limit: int = Query(30, ge=1, le=100),
              offset: int = Query(0, ge=0, le=100000), con: sqlite3.Connection = Depends(get_db),
              u=Depends(auth.exige("OPERATOR"))):
    """O inventário inteiro do QuickBooks (produtos e serviços), do espelho, com busca e paginação."""
    return rz.catalogo_qbo(con, q, limit, offset)


@r.post("/quickbooks/itens/atualizar")
def qbo_itens_atualizar(request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    """Traz o catálogo do QuickBooks agora (no máximo a cada 5 minutos; a busca não espera por isto)."""
    from command_center.providers import NaoConectado
    try:
        res = rz.atualizar_catalogo(con)
    except NaoConectado:
        raise HTTPException(503, "QuickBooks não está conectado: a busca mostra o catálogo da última sincronia.")
    except Exception as e:                           # noqa: BLE001 — recusa do QuickBooks
        raise HTTPException(502, f"QuickBooks: {str(e)[:300]}")
    if not res["recente"]:
        _aud(con, request, u, "balcao.catalogo_qbo", "qbo_items", None, {"itens": res["atualizados"]})
    return res


@r.get("/rascunhos")
def rascunhos(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0, le=100000),
              con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    """Os rascunhos abertos de todos os cards (para nenhum ficar esquecido)."""
    return rz.abertos(con, limit, offset)


@r.get("/cliente/{client_id}/rascunho")
def rascunho(client_id: int = Path(..., ge=1, le=2**63 - 1), con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    try:
        return {**rz.do_cliente(con, client_id), "gerente": _gerente(u)}
    except LookupError:
        raise HTTPException(404, "Cliente não encontrado.")


class LinhaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origem: Literal["estoque", "quickbooks", "livre"]
    item_id: int | None = Field(None, ge=1, le=2**63 - 1)          # peça do estoque
    qbo_item_id: str | None = Field(None, min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    nome: str | None = Field(None, max_length=100)                  # linha livre
    descricao: str | None = Field(None, max_length=300)
    qty: float = Field(1, gt=0, le=rz.MAX_QTY)
    preco: float | None = Field(None, ge=0, le=rz.MAX_PRECO)
    local: Literal["sede", "trailer", "pista"] | None = None
    confirmado: StrictBool = False


def _resposta(con, client_id, u):
    return {**rz.do_cliente(con, client_id), "gerente": _gerente(u)}


@r.post("/cliente/{client_id}/rascunho/linhas", status_code=201)
def rascunho_linha(dados: LinhaIn, request: Request, client_id: int = Path(..., ge=1, le=2**63 - 1), con: sqlite3.Connection = Depends(get_db),
                   u=Depends(auth.exige("OPERATOR"))):
    try:
        with transacao(con, imediata=True):
            d, li, novo, digitado = rz.adicionar(con, client_id, dados.origem, u["id"], item_id=dados.item_id,
                                                 qbo_item_id=dados.qbo_item_id, nome=dados.nome, qty=dados.qty,
                                                 preco=dados.preco, descricao=dados.descricao, local=dados.local,
                                                 confirmado=dados.confirmado)
            if novo:
                _aud(con, request, u, "balcao.rascunho.criar", "counter_draft", d["id"], {"client_id": client_id})
            _aud(con, request, u, "balcao.rascunho.linha", "counter_draft", d["id"],
                 {"client_id": client_id, "linha": li["id"], "origem": li["source"], "item": li["item_id"],
                  "qbo_item": li["qbo_item_id"], "nome": li["name"], "qty": dados.qty, "preco": li["unit_price"]})
            if digitado:
                _aud(con, request, u, "balcao.rascunho.preco", "counter_draft", d["id"],
                     {"client_id": client_id, "linha": li["id"], "nome": li["name"], "preco_tabela": li["ref_price"],
                      "preco": li["unit_price"]})
    except LookupError as e:
        raise HTTPException(404, str(e))
    except (b.ErroBalcao, estoque.ErroEstoque) as e:
        raise _erro(e)
    return {"linha": li["id"], **_resposta(con, client_id, u)}


class EditarLinhaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    qty: float | None = Field(None, gt=0, le=rz.MAX_QTY)
    preco: float | None = Field(None, ge=0, le=rz.MAX_PRECO)
    descricao: str | None = Field(None, max_length=300)
    nome: str | None = Field(None, max_length=100)


@r.patch("/cliente/{client_id}/rascunho/linhas/{lid}")
def rascunho_editar(dados: EditarLinhaIn, request: Request, client_id: int = Path(..., ge=1, le=2**63 - 1), lid: int = Path(..., ge=1, le=2**63 - 1),
                    con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    mudou = dados.model_dump(exclude_unset=True)
    try:
        with transacao(con, imediata=True):
            antes, depois = rz.editar(con, client_id, lid, u["id"], qty=mudou.get("qty"),
                                      preco=mudou["preco"] if "preco" in mudou else rz._NADA,
                                      descricao=mudou["descricao"] if "descricao" in mudou else rz._NADA,
                                      nome=mudou.get("nome"))
            _aud(con, request, u, "balcao.rascunho.editar", "counter_draft", antes["draft_id"],
                 {"client_id": client_id, "linha": lid, "campos": sorted(mudou)})
            if "preco" in mudou and depois["price_by"] and antes["unit_price"] != depois["unit_price"]:
                _aud(con, request, u, "balcao.rascunho.preco", "counter_draft", antes["draft_id"],
                     {"client_id": client_id, "linha": lid, "nome": depois["name"], "preco_tabela": depois["ref_price"],
                      "antes": antes["unit_price"], "preco": depois["unit_price"]})
    except LookupError:
        raise HTTPException(404, "Linha não encontrada neste rascunho.")
    except b.ErroBalcao as e:
        raise _erro(e)
    return _resposta(con, client_id, u)


@r.delete("/cliente/{client_id}/rascunho/linhas/{lid}")
def rascunho_remover(request: Request, client_id: int = Path(..., ge=1, le=2**63 - 1), lid: int = Path(..., ge=1, le=2**63 - 1), con: sqlite3.Connection = Depends(get_db),
                     u=Depends(auth.exige("OPERATOR"))):
    try:
        with transacao(con, imediata=True):
            li = rz.remover(con, client_id, lid)
            _aud(con, request, u, "balcao.rascunho.remover", "counter_draft", li["draft_id"],
                 {"client_id": client_id, "linha": lid, "nome": li["name"], "qty": li["qty"], "preco": li["unit_price"]})
    except LookupError:
        raise HTTPException(404, "Linha não encontrada neste rascunho.")
    except b.ErroBalcao as e:
        raise _erro(e)
    return _resposta(con, client_id, u)


@r.post("/cliente/{client_id}/rascunho/descartar")
def rascunho_descartar(request: Request, client_id: int = Path(..., ge=1, le=2**63 - 1), con: sqlite3.Connection = Depends(get_db),
                       u=Depends(auth.exige("OPERATOR"))):
    try:
        with transacao(con, imediata=True):
            d, n = rz.descartar(con, client_id, u["id"])
            _aud(con, request, u, "balcao.rascunho.descartar", "counter_draft", d["id"], {"client_id": client_id, "linhas": n})
    except LookupError:
        raise HTTPException(404, "Este card não tem rascunho aberto.")
    except b.ErroBalcao as e:
        raise _erro(e)
    return _resposta(con, client_id, u)


@r.post("/cliente/{client_id}/rascunho/faturar")
def rascunho_faturar(request: Request, client_id: int = Path(..., ge=1, le=2**63 - 1), con: sqlite3.Connection = Depends(get_db),
                     u=Depends(auth.exige("OPERATOR"))):
    """Cria UMA invoice no QuickBooks com as linhas do rascunho (cria o item da linha que não tem). Não envia: o
    "Enviar invoice por e-mail" é o da invoice de peças, que aparece logo acima. #346 (dono, 19/10): o mecânico cria
    também; a dele fica aguardando a revisão do gerente (não envia nem cobra antes)."""
    try:
        rz.faturar(con, client_id, u["id"], ip=auth._ip(request), gerente=_gerente(u))
    except LookupError:
        raise HTTPException(404, "Este card não tem rascunho aberto.")
    except (b.ErroBalcao, estoque.ErroEstoque) as e:
        raise _erro(e)
    return {**_resposta(con, client_id, u), **b.do_cliente(con, client_id)}


@r.post("/cliente/{client_id}/rascunho/conferir")
def rascunho_conferir(request: Request, client_id: int = Path(..., ge=1, le=2**63 - 1), con: sqlite3.Connection = Depends(get_db),
                      u=Depends(auth.exige("MANAGER"))):
    """#346: o QuickBooks não respondeu. Procura a invoice pelo número reservado: existe, liga; não existe, libera."""
    try:
        rz.conferir(con, client_id, u["id"], ip=auth._ip(request))
    except LookupError:
        raise HTTPException(404, "Este card não tem rascunho aberto.")
    except (b.ErroBalcao, estoque.ErroEstoque) as e:
        raise _erro(e)
    return {**_resposta(con, client_id, u), **b.do_cliente(con, client_id)}


@r.get("/aproximado")
def aproximado(q: str = Query(..., min_length=2, max_length=120), con: sqlite3.Connection = Depends(get_db),
               u=Depends(auth.exige("OPERATOR"))):
    """#346 (dono, 19/10: "se não ler, coloque o que tiver de mais aproximado"): as peças e os itens mais parecidos."""
    return rz.aproximado(con, q)


# ------------------------------------------------------------------ #346: a revisão do gerente
def _revisao_erro(fn):
    try:
        return fn()
    except LookupError as e:
        raise HTTPException(404, str(e))
    except (b.ErroBalcao, estoque.ErroEstoque) as e:
        raise _erro(e)


@r.get("/invoices/{pid}/revisao")
def inv_revisao_invoice(pid: int = Path(..., ge=1, le=2**63 - 1), con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("MANAGER"))):
    return _revisao_erro(lambda: rz.revisao(con, pid))


@r.post("/invoices/{pid}/revisao/linhas", status_code=201)
def inv_revisao_adicionar(dados: LinhaIn, request: Request, pid: int = Path(..., ge=1, le=2**63 - 1), con: sqlite3.Connection = Depends(get_db),
                      u=Depends(auth.exige("MANAGER"))):
    campos = dados.model_dump(exclude={"local"})
    _revisao_erro(lambda: rz.revisar_adicionar(con, pid, u["id"], ip=auth._ip(request), **campos))
    return _revisao_erro(lambda: rz.revisao(con, pid))


class RevisaoLinhaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    qty: float | None = Field(None, gt=0, le=rz.MAX_QTY)
    preco: float | None = Field(None, ge=0, le=rz.MAX_PRECO)


@r.patch("/invoices/{pid}/revisao/linhas/{lid}")
def inv_revisao_editar(dados: RevisaoLinhaIn, request: Request, pid: int = Path(..., ge=1, le=2**63 - 1), lid: int = Path(..., ge=1, le=2**63 - 1),
                   con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("MANAGER"))):
    _revisao_erro(lambda: rz.revisar_editar(con, pid, lid, u["id"], qty=dados.qty, preco=dados.preco, ip=auth._ip(request)))
    return _revisao_erro(lambda: rz.revisao(con, pid))


@r.delete("/invoices/{pid}/revisao/linhas/{lid}")
def inv_revisao_remover(request: Request, pid: int = Path(..., ge=1, le=2**63 - 1), lid: int = Path(..., ge=1, le=2**63 - 1), con: sqlite3.Connection = Depends(get_db),
                    u=Depends(auth.exige("MANAGER"))):
    _revisao_erro(lambda: rz.revisar_remover(con, pid, lid, u["id"], ip=auth._ip(request)))
    return _revisao_erro(lambda: rz.revisao(con, pid))


@r.post("/invoices/{pid}/revisao/confirmar")
def inv_revisao_confirmar(request: Request, pid: int = Path(..., ge=1, le=2**63 - 1), con: sqlite3.Connection = Depends(get_db),
                      u=Depends(auth.exige("MANAGER"))):
    p = _revisao_erro(lambda: rz.revisar_confirmar(con, pid, u["id"], ip=auth._ip(request)))
    return b.invoice_publica(con, p)


# ------------------------------------------------------------------ balcão no celular (dono, 20/10)
# GUARDAR: a peça entra na lista do card, pendente; o "Confirmar" põe tudo no estoque do cliente numa vez só.
# Peça que não existe: o pop-up registra e já adiciona ao cliente (na lista do GUARDAR ou no rascunho do COBRAR).
from command_center.providers import balcao_guardar as bg  # noqa: E402


def _guardando(con, client_id):
    return {"guardando": bg.lista(con, client_id)}


class GuardandoIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_id: int = Field(..., ge=1, le=2**63 - 1)
    qty: float = Field(1, gt=0, le=bg.MAX_QTY)
    local: str | None = Field(None, max_length=20)
    codigo: str | None = Field(None, max_length=200)


@r.get("/cliente/{client_id}/guardando")
def guardando(client_id: int = Path(..., ge=1, le=2**63 - 1), con: sqlite3.Connection = Depends(get_db),
              u=Depends(auth.exige("OPERATOR"))):
    try:
        bg._cliente(con, client_id)
    except LookupError as e:
        raise HTTPException(404, str(e))
    return _guardando(con, client_id)


@r.post("/cliente/{client_id}/guardando", status_code=201)
def guardando_adicionar(dados: GuardandoIn, request: Request, client_id: int = Path(..., ge=1, le=2**63 - 1),
                        con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    def f():
        with transacao(con, imediata=True):
            lid = bg.adicionar(con, client_id, dados.item_id, u["id"], dados.qty, dados.local, dados.codigo)
            _aud(con, request, u, "balcao.guardando.adicionar", "client", client_id,
                 {"linha": lid, "item": dados.item_id, "qty": dados.qty, "local": dados.local})
        return {"linha": lid, **_guardando(con, client_id)}
    return _revisao_erro(f)


class GuardandoEditarIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    qty: float | None = Field(None, gt=0, le=bg.MAX_QTY)
    local: str | None = Field(None, max_length=20)


@r.patch("/cliente/{client_id}/guardando/{lid}")
def guardando_editar(dados: GuardandoEditarIn, request: Request, client_id: int = Path(..., ge=1, le=2**63 - 1),
                     lid: int = Path(..., ge=1, le=2**63 - 1), con: sqlite3.Connection = Depends(get_db),
                     u=Depends(auth.exige("OPERATOR"))):
    def f():
        with transacao(con, imediata=True):
            antes = bg.editar(con, client_id, lid, dados.qty, dados.local)
            _aud(con, request, u, "balcao.guardando.editar", "client", client_id,
                 {"linha": lid, "item": antes["item_id"], "qty_antes": antes["qty"], "qty": dados.qty,
                  "local_antes": antes["location"], "local": dados.local})
        return _guardando(con, client_id)
    return _revisao_erro(f)


@r.delete("/cliente/{client_id}/guardando/{lid}")
def guardando_remover(request: Request, client_id: int = Path(..., ge=1, le=2**63 - 1), lid: int = Path(..., ge=1, le=2**63 - 1),
                      con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    def f():
        with transacao(con, imediata=True):
            li = bg.remover(con, client_id, lid)
            _aud(con, request, u, "balcao.guardando.remover", "client", client_id,
                 {"linha": lid, "item": li["item_id"], "qty": li["qty"]})
        return _guardando(con, client_id)
    return _revisao_erro(f)


@r.post("/cliente/{client_id}/guardando/confirmar")
def guardando_confirmar(request: Request, client_id: int = Path(..., ge=1, le=2**63 - 1),
                        con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("OPERATOR"))):
    feitas = _revisao_erro(lambda: bg.confirmar(con, client_id, u["id"], ip=auth._ip(request)))
    return {"guardadas": len(feitas), **b.do_cliente(con, client_id)}


class PecaNovaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: int = Field(..., ge=1, le=2**63 - 1)
    modo: Literal["guardar", "cobrar"]
    nome: str = Field(..., min_length=1, max_length=100)
    category: str | None = Field(None, max_length=40)
    codigo: str | None = Field(None, max_length=200)
    price: float | None = Field(None, ge=0, le=rz.MAX_PRECO)
    qty: float = Field(1, gt=0, le=bg.MAX_QTY)
    local: str | None = Field(None, max_length=20)


@r.post("/peca-nova", status_code=201)
def peca_nova(dados: PecaNovaIn, request: Request, con: sqlite3.Connection = Depends(get_db),
              u=Depends(auth.exige("OPERATOR"))):
    """A peça que o sistema não conhece: cria a peça (e o código da etiqueta, se veio) e **já adiciona ao cliente** —
    no GUARDAR, na lista para confirmar; no COBRAR, no rascunho de invoice do card (o item do QuickBooks nasce no
    "Criar invoice", como toda linha do rascunho). O preço final da peça é do gerente; o do mecânico vale só para a
    linha e fica marcado como digitado."""
    gerente = _gerente(u)
    nome = " ".join(dados.nome.split())

    def f():
        with transacao(con, imediata=True):
            bg._cliente(con, dados.client_id)
            item_id = estoque.criar_item(con, "peca", nome, category=dados.category or None,
                                         price=dados.price if gerente else None)
            cod = b.cadastrar_codigo(con, dados.codigo, item_id, u["id"]) if (dados.codigo or "").strip() else None
            _aud(con, request, u, "balcao.peca_nova", "stock_item", item_id,
                 {"client_id": dados.client_id, "modo": dados.modo, "codigo": cod, "nome": nome,
                  "preco": dados.price, "preco_da_peca": gerente and dados.price is not None})
            if dados.modo == "guardar":
                lid = bg.adicionar(con, dados.client_id, item_id, u["id"], dados.qty, dados.local, cod)
                _aud(con, request, u, "balcao.guardando.adicionar", "client", dados.client_id,
                     {"linha": lid, "item": item_id, "qty": dados.qty, "local": dados.local, "peca_nova": True})
                return {"item": b.item_publico(con, estoque.item(con, item_id)), "modo": "guardar",
                        **_guardando(con, dados.client_id)}
            d, li, novo, digitado = rz.adicionar(con, dados.client_id, "estoque", u["id"], item_id=item_id, qty=dados.qty,
                                                 preco=dados.price, local=dados.local, confirmado=True)
            if novo:
                _aud(con, request, u, "balcao.rascunho.criar", "counter_draft", d["id"], {"client_id": dados.client_id})
            _aud(con, request, u, "balcao.rascunho.linha", "counter_draft", d["id"],
                 {"client_id": dados.client_id, "linha": li["id"], "origem": "estoque", "item": item_id, "nome": nome,
                  "qty": dados.qty, "preco": li["unit_price"], "peca_nova": True})
            if digitado:
                _aud(con, request, u, "balcao.rascunho.preco", "counter_draft", d["id"],
                     {"client_id": dados.client_id, "linha": li["id"], "nome": nome, "preco_tabela": li["ref_price"],
                      "preco": li["unit_price"]})
        return {"item": b.item_publico(con, estoque.item(con, item_id)), "modo": "cobrar", **_resposta(con, dados.client_id, u)}
    return _revisao_erro(f)
