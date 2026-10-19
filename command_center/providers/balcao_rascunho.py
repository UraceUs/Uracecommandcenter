"""Rascunho de invoice do balcão (#341).

Dono, 19/10: *"Aqui no galpão eu preciso conseguir colocar peças e valores em um rascunho de bulk para o cliente
e dali o command center cria a invoice com os itens que eu falar; se não tiver item ele cria; coloque também todo
o inventário do QuickBooks como opção para selecionar lá a peça também."*

- **Um rascunho aberto por card** (índice único no banco). Fica no servidor: recarregar a tela ou abrir em outro
  aparelho mostra o mesmo. Nunca aparece em outro card: toda linha é procurada pelo rascunho do card da URL.
- **Linha** = peça do estoque do Command Center (lida pelo leitor ou buscada), item do catálogo do QuickBooks
  (o espelho `qbo_items`, o inventário inteiro) ou **linha livre** (nome e preço que não existem em lugar nenhum).
  O preço é o da linha. Veio da tabela (preço final da peça ou o do item no QuickBooks) e ninguém mexeu: sem marca.
  Digitado diferente da tabela, ou sem tabela: `price_by` guarda quem digitou, a tela marca "preço digitado" e a
  auditoria registra o de antes e o de agora. **Linha sem preço não deixa criar a invoice** (nada de preço inventado).
- **Criar invoice** (gerente, como o envio e o item do QuickBooks no balcão): (1) a linha sem item no QuickBooks
  ganha o item lá (`item_avulso_sistema`: pelo nome, reusa; senão cria, com `requestid`); (2) o painel grava primeiro:
  a peça do estoque sai como no COBRAR (venda, do local do rascunho, com a cobrança) e o rascunho fica 'criando' com
  a `requestid` da invoice; (3) uma invoice só no QuickBooks, sem enviar; (4) o rascunho vira 'faturado' e a invoice
  entra nas invoices de peças (`parts_invoices.draft_id`), com o "Enviar" e o "Cobrar no cartão" de sempre.
  Recusa certa do QuickBooks (`InvoiceNaoCriada`): a peça volta ao estoque e o rascunho volta a ser editável.
  Sem resposta: o rascunho fica 'criando' e o "Criar invoice" de novo manda a MESMA `requestid` (não duplica, #310).
"""
import math
import re
import unicodedata
import uuid

from command_center.db import agora, atualizar, auditar, inserir, todos, transacao, um
from command_center.providers import balcao as b, estoque

ORIGENS = ("estoque", "quickbooks", "livre")
MAX_LINHAS = 100
MAX_QTY = 1000
MAX_PRECO = 100000
_NADA = object()


def _aud(con, evento, por, eid, detalhe, ip=None):
    auditar(con, evento, f"user:{por}" if por else "system", user_id=por, entity_type="counter_draft", entity_id=eid,
            detail=detalhe, ip=ip)


# ------------------------------------------------------------------ inventário do QuickBooks
def catalogo_qbo(con, busca=None, limit=30, offset=0):
    """O inventário do QuickBooks (produtos e serviços, sem as categorias), do espelho `qbo_items`, paginado.
    Cada palavra da busca tem de estar no nome (com a categoria)."""
    args, filtro = [], ""
    for p in (busca or "").lower().split()[:6]:
        filtro += " AND LOWER(COALESCE(full_name,'') || ' ' || name) LIKE ?"
        args.append(f"%{p}%")
    onde = f"FROM qbo_items WHERE active=1 AND COALESCE(type,'')!='Category'{filtro}"
    total = um(con, f"SELECT COUNT(*) AS n {onde}", tuple(args))["n"]
    itens = todos(con, f"""SELECT id, name, full_name, price, type {onde} ORDER BY LOWER(COALESCE(full_name, name)), id
                           LIMIT ? OFFSET ?""", (*args, int(limit), int(offset)))
    return {"itens": itens, "total": total, "limit": limit, "offset": offset,
            "atualizado": um(con, "SELECT MAX(synced_at) AS m FROM qbo_items")["m"]}


ATUALIZAR_A_CADA_S = 300


def atualizar_catalogo(con, forcar=False):
    """Traz o catálogo do QuickBooks para o espelho, sob demanda (a sincronia de sempre também traz). No máximo uma
    vez a cada 5 minutos: o resto do tempo, a busca usa o espelho (cache) e a tela não espera o QuickBooks."""
    from datetime import datetime, timezone
    ult = um(con, "SELECT MAX(synced_at) AS m FROM qbo_items")["m"]
    if ult and not forcar:
        try:
            idade = (datetime.now(timezone.utc) - datetime.fromisoformat(ult.replace("Z", "+00:00"))).total_seconds()
        except ValueError:
            idade = ATUALIZAR_A_CADA_S
        if idade < ATUALIZAR_A_CADA_S:
            return {"atualizados": 0, "recente": True, "atualizado": ult}
    itens = b._qbo().qbo_itens(maximo=5000)            # paginado de 1000 em 1000 lá dentro (#187)
    agora_ = agora()
    for i in itens:
        if not i.get("id"):
            continue
        con.execute("""INSERT INTO qbo_items (id, name, full_name, price, type, active, synced_at) VALUES (?,?,?,?,?,?,?)
                       ON CONFLICT(id) DO UPDATE SET name=excluded.name, full_name=excluded.full_name, price=excluded.price,
                       type=excluded.type, active=excluded.active, synced_at=excluded.synced_at""",
                    (str(i["id"]), i.get("nome") or "", i.get("nome_completo"), i.get("preco"), i.get("tipo"),
                     1 if i.get("ativo", True) else 0, agora_))
    return {"atualizados": len(itens), "recente": False, "atualizado": agora_}


# ------------------------------------------------------------------ o rascunho
def aberto(con, client_id):
    return um(con, "SELECT * FROM counter_drafts WHERE client_id=? AND status IN ('rascunho','criando')", (client_id,))


def _linhas(con, did):
    return todos(con, "SELECT * FROM counter_draft_lines WHERE draft_id=? ORDER BY id", (did,))


def _digitado(preco, ref):
    return preco is not None and (ref is None or abs(float(preco) - float(ref)) >= 0.005)


def publico(con, d):
    if not d:
        return None
    ls = []
    for x in _linhas(con, d["id"]):
        t = None if x["unit_price"] is None else round(float(x["qty"]) * float(x["unit_price"]), 2)
        # a peça do estoque sem saldo da URACE no local do rascunho não sai: a tela avisa antes de "Criar invoice"
        falta = x["source"] == "estoque" and d["status"] == "rascunho" and \
            estoque.vendavel(con, x["item_id"], estoque.local(con, d["location"])["id"]) < float(x["qty"])
        ls.append({"id": x["id"], "origem": x["source"], "item_id": x["item_id"], "qbo_item_id": x["qbo_item_id"],
                   "nome": x["name"], "descricao": x["description"], "qty": x["qty"], "preco": x["unit_price"],
                   "preco_tabela": x["ref_price"], "preco_digitado": bool(x["price_by"]), "total": t,
                   "sem_saldo": bool(falta)})
    sem = [x["nome"] for x in ls if x["preco"] is None]
    total = round(sum(x["total"] or 0 for x in ls), 2)
    p = um(con, "SELECT status, sent_to, paid_at FROM parts_invoices WHERE id=?", (d["parts_invoice_id"],)) \
        if d["parts_invoice_id"] else None
    return {"id": d["id"], "client_id": d["client_id"], "status": d["status"], "local": d["location"],
            "linhas": ls, "total": total, "sem_preco": sem, "pronto": bool(ls) and not sem and d["status"] == "rascunho",
            "erro": d["error"], "incerto": bool(d["uncertain"]), "doc_number": d["doc_number"],
            "qbo_invoice_id": d["qbo_invoice_id"], "parts_invoice_id": d["parts_invoice_id"],
            "invoice_status": p["status"] if p else None, "atualizado": d["updated_at"]}


def do_cliente(con, client_id):
    """O rascunho aberto do card e os últimos faturados dele (só deste card)."""
    if not um(con, "SELECT 1 AS x FROM clients WHERE id=?", (client_id,)):
        raise LookupError("cliente não existe")
    fat = todos(con, """SELECT * FROM counter_drafts WHERE client_id=? AND status='faturado'
                        ORDER BY closed_at DESC, id DESC LIMIT 3""", (client_id,))
    return {"rascunho": publico(con, aberto(con, client_id)), "faturados": [publico(con, d) for d in fat]}


def abertos(con, limit=50, offset=0):
    """Os rascunhos abertos de todos os cards (a tela sem cliente mostra a lista, para ninguém esquecer um)."""
    total = um(con, "SELECT COUNT(*) AS n FROM counter_drafts WHERE status IN ('rascunho','criando')")["n"]
    ds = todos(con, """SELECT d.*, COALESCE(c.pilot_name, c.name) AS cliente,
                              (SELECT COUNT(*) FROM counter_draft_lines l WHERE l.draft_id=d.id) AS n_linhas,
                              (SELECT ROUND(COALESCE(SUM(l.qty * l.unit_price), 0), 2) FROM counter_draft_lines l
                                WHERE l.draft_id=d.id) AS total_linhas
                         FROM counter_drafts d JOIN clients c ON c.id=d.client_id
                        WHERE d.status IN ('rascunho','criando') ORDER BY d.updated_at DESC, d.id DESC LIMIT ? OFFSET ?""",
               (limit, offset))
    return {"itens": [{"id": d["id"], "client_id": d["client_id"], "cliente": d["cliente"], "status": d["status"],
                       "linhas": d["n_linhas"], "total": d["total_linhas"], "atualizado": d["updated_at"],
                       "incerto": bool(d["uncertain"])} for d in ds],
            "total": total, "limit": limit, "offset": offset}


def _qty(v):
    try:
        q = float(v)
    except (TypeError, ValueError):
        raise b.ErroBalcao("quantidade inválida")
    if not math.isfinite(q) or q <= 0 or q > MAX_QTY:
        raise b.ErroBalcao(f"a quantidade vai de mais de 0 até {MAX_QTY}")
    return round(q, 3)


def _preco(v):
    if v is None:
        return None
    try:
        p = float(v)
    except (TypeError, ValueError):
        raise b.ErroBalcao("preço inválido")
    if not math.isfinite(p) or p < 0 or p > MAX_PRECO:
        raise b.ErroBalcao(f"o preço vai de 0 a {MAX_PRECO}")
    return round(p, 2)


def _texto(v, rotulo, maximo, obrigatorio=False):
    t = " ".join((v or "").split())
    if obrigatorio and not t:
        raise b.ErroBalcao(f"{rotulo}: escreva o nome")
    if len(t) > maximo:
        raise b.ErroBalcao(f"{rotulo}: no máximo {maximo} caracteres")
    return t or None


def _editavel(con, client_id, por, local=None):
    """O rascunho aberto do card (cria se não há). Devolve (rascunho, novo). 'criando' não muda: a nova tentativa
    tem de mandar ao QuickBooks exatamente o que foi da primeira vez."""
    d = aberto(con, client_id)
    if d and d["status"] == "criando":
        raise b.ErroBalcao("a invoice deste rascunho está sendo criada no QuickBooks: espere ou toque em "
                           "'Criar invoice' de novo (não duplica)")
    if d:
        return d, False
    loc = estoque.local(con, local or estoque.SEDE)["code"]
    did = inserir(con, "counter_drafts", client_id=client_id, location=loc, created_by=por)
    return um(con, "SELECT * FROM counter_drafts WHERE id=?", (did,)), True


def adicionar(con, client_id, origem, por, item_id=None, qbo_item_id=None, nome=None, qty=1, preco=None,
              descricao=None, local=None, confirmado=False, rascunho=None):
    """Uma linha no rascunho do card. Devolve (rascunho, linha, novo_rascunho, preco_digitado). `rascunho`: o já
    faturado que o gerente está revisando (#346); a linha entra nele, sempre como linha nova."""
    if origem not in ORIGENS:
        raise b.ErroBalcao("origem inválida")
    c = um(con, "SELECT * FROM clients WHERE id=?", (client_id,))
    if not c:
        raise LookupError("cliente não existe")
    qty, preco = _qty(qty), _preco(preco)
    descricao = _texto(descricao, "descrição", 300)
    if origem == "estoque":
        it = estoque.item(con, item_id)
        if not it["active"]:
            raise b.ErroBalcao(f"{it['name']} foi excluída do estoque")
        if it["tracking"] == "serie":
            raise b.ErroBalcao(f"{it['name']} tem número de série: lance pela tela de Estoque")
        if not confirmado and estoque.saldo(con, it["id"], client_id=client_id) > 0:
            raise b.Confirmar("tem_do_cliente", f"{c['pilot_name'] or c['name']} tem {it['name']} guardado com a gente. "
                                                "Usar a dele (sem cobrar) ou cobrar uma nova?")
        ref, qid, nome = it["price"], it["qbo_item_id"], it["name"]
    elif origem == "quickbooks":
        q = um(con, "SELECT * FROM qbo_items WHERE id=? AND active=1 AND COALESCE(type,'')!='Category'", (str(qbo_item_id or ""),))
        if not q:
            raise b.ErroBalcao("item do QuickBooks não encontrado: atualize o inventário e tente de novo")
        ref, qid, nome, item_id = q["price"], q["id"], q["full_name"] or q["name"], None
    else:
        nome = _texto(nome, "nome da linha", 100, obrigatorio=True)
        ref, qid, item_id = None, None, None
    if preco is None:
        preco = None if ref is None else round(float(ref), 2)
    d, novo = (rascunho, False) if rascunho else _editavel(con, client_id, por, local)
    if um(con, "SELECT COUNT(*) AS n FROM counter_draft_lines WHERE draft_id=?", (d["id"],))["n"] >= MAX_LINHAS:
        raise b.ErroBalcao(f"o rascunho tem o máximo de {MAX_LINHAS} linhas: crie esta invoice e comece outro")
    digitado = _digitado(preco, ref)
    # a mesma peça (ou o mesmo item) com o mesmo preço soma na linha que já existe: ler 3 vezes é 3 unidades
    ja = None
    if origem != "livre" and not rascunho:
        ja = um(con, f"""SELECT * FROM counter_draft_lines WHERE draft_id=? AND source=? AND
                         {'item_id' if origem == 'estoque' else 'qbo_item_id'}=? AND
                         COALESCE(unit_price, -1)=COALESCE(?, -1) ORDER BY id LIMIT 1""",
                (d["id"], origem, item_id if origem == "estoque" else qid, preco))
    if ja:
        nova_qty = round(float(ja["qty"]) + qty, 3)
        if nova_qty > MAX_QTY:
            raise b.ErroBalcao(f"a quantidade vai até {MAX_QTY}")
        atualizar(con, "counter_draft_lines", ja["id"], qty=nova_qty, updated_at=agora())
        lid = ja["id"]
    else:
        lid = inserir(con, "counter_draft_lines", draft_id=d["id"], source=origem, item_id=item_id, qbo_item_id=qid,
                      name=nome, description=descricao, qty=qty, unit_price=preco, ref_price=ref,
                      price_by=por if digitado else None, qbo_requestid=uuid.uuid4().hex, created_by=por)
    atualizar(con, "counter_drafts", d["id"], updated_at=agora(), error=None)
    return d, um(con, "SELECT * FROM counter_draft_lines WHERE id=?", (lid,)), novo, digitado


def _linha_do_card(con, client_id, lid):
    """A linha do rascunho aberto DESTE card. De outro card (ou de rascunho fechado) é igual a não existir."""
    d = aberto(con, client_id)
    li = um(con, "SELECT * FROM counter_draft_lines WHERE id=? AND draft_id=?", (lid, d["id"])) if d else None
    if not li:
        raise LookupError("linha não encontrada neste rascunho")
    if d["status"] != "rascunho":
        raise b.ErroBalcao("a invoice deste rascunho está sendo criada no QuickBooks: as linhas não mudam agora")
    return d, li


def editar(con, client_id, lid, por, qty=None, preco=_NADA, descricao=_NADA, nome=None):
    """Muda quantidade, preço, descrição (e o nome, na linha livre). Devolve (antes, depois)."""
    d, li = _linha_do_card(con, client_id, lid)
    campos = {}
    if qty is not None:
        campos["qty"] = _qty(qty)
    if preco is not _NADA:
        p = _preco(preco)
        if p is None:
            raise b.ErroBalcao("digite o preço da linha")
        campos["unit_price"] = p
        campos["price_by"] = por if _digitado(p, li["ref_price"]) else None
    if descricao is not _NADA:
        campos["description"] = _texto(descricao, "descrição", 300)
    if nome is not None:
        if li["source"] != "livre":
            raise b.ErroBalcao("o nome só muda na linha livre (a peça e o item têm o nome deles)")
        campos["name"] = _texto(nome, "nome da linha", 100, obrigatorio=True)
        if li["qbo_item_id"]:
            campos["qbo_item_id"] = None          # nome novo: o item do QuickBooks é outro
            campos["qbo_requestid"] = uuid.uuid4().hex
    if not campos:
        return li, li
    atualizar(con, "counter_draft_lines", li["id"], updated_at=agora(), **campos)
    atualizar(con, "counter_drafts", d["id"], updated_at=agora(), error=None)
    return li, um(con, "SELECT * FROM counter_draft_lines WHERE id=?", (li["id"],))


def remover(con, client_id, lid):
    d, li = _linha_do_card(con, client_id, lid)
    con.execute("DELETE FROM counter_draft_lines WHERE id=?", (li["id"],))
    atualizar(con, "counter_drafts", d["id"], updated_at=agora(), error=None)
    return li


def descartar(con, client_id, por):
    d = aberto(con, client_id)
    if not d:
        raise LookupError("este card não tem rascunho aberto")
    if d["status"] != "rascunho":
        raise b.ErroBalcao("a invoice deste rascunho está sendo criada no QuickBooks: não dá para descartar agora")
    n = um(con, "SELECT COUNT(*) AS n FROM counter_draft_lines WHERE draft_id=?", (d["id"],))["n"]
    atualizar(con, "counter_drafts", d["id"], status="descartado", closed_by=por, closed_at=agora(), updated_at=agora())
    return d, n


# ------------------------------------------------------------------ criar a invoice
def _devolver_ao_estoque(con, d, por):
    """A invoice com certeza não saiu: a peça que saiu para ela volta (como o desfazer do COBRAR)."""
    for li in _linhas(con, d["id"]):
        if li["source"] == "estoque" and li["charge_id"]:       # #350: o "sem saldo" se cancela, o resto volta
            estoque.devolver_venda(con, li["item_id"], li["qty"], para=d["location"], ref=f"linha:{li['id']}",
                                   by_user_id=por, notes=f"rascunho #{d['id']}: a invoice não saiu")
            if li["charge_id"]:
                atualizar(con, "stock_charges", li["charge_id"], status="waived", resolved_by=por, resolved_at=agora(),
                          notes=f"rascunho #{d['id']}: a invoice não saiu")
            atualizar(con, "counter_draft_lines", li["id"], move_id=None, charge_id=None)
    atualizar(con, "counter_drafts", d["id"], stock_out=0)


def _falhou(con, did, por, msg, devolver):
    with transacao(con, imediata=True):
        d = um(con, "SELECT * FROM counter_drafts WHERE id=?", (did,))
        if devolver and d["stock_out"]:
            _devolver_ao_estoque(con, d, por)
        atualizar(con, "counter_drafts", did, status="rascunho", uncertain=0, requestid=None, doc_number=None, error=msg[:400],
                  updated_at=agora())
        _aud(con, "balcao.rascunho.invoice_recusada", por, did, {"erro": msg[:300]})


def _itens_no_qbo(con, d, por, ip):
    """Toda linha ganha o item dela no QuickBooks antes da invoice. Pelo nome, reusa; senão cria (uma vez só: o nome
    e a `requestid` da linha seguram a repetição)."""
    qbo = b._qbo()
    for li in _linhas(con, d["id"]):
        if li["qbo_item_id"]:
            continue
        nome = li["name"]
        r = qbo.item_avulso_sistema(nome=nome, preco=li["unit_price"], descricao=li["description"] or nome,
                                    requestid=li["qbo_requestid"])
        if not r.get("id"):
            raise b.ErroBalcao("o QuickBooks não devolveu o item criado")
        qid = str(r["id"])
        with transacao(con):
            con.execute("""INSERT INTO qbo_items (id, name, full_name, price, type, active, synced_at) VALUES (?,?,?,?,?,1,?)
                           ON CONFLICT(id) DO UPDATE SET name=excluded.name, full_name=excluded.full_name""",
                        (qid, r.get("nome") or nome, r.get("nome_completo"), r.get("preco"), r.get("tipo"), agora()))
            atualizar(con, "counter_draft_lines", li["id"], qbo_item_id=qid, updated_at=agora())
            if li["source"] == "estoque" and li["item_id"]:      # a peça fica ligada: a próxima vez já tem item
                it = estoque.item(con, li["item_id"])
                if not it["qbo_item_id"]:
                    atualizar(con, "stock_items", it["id"], qbo_item_id=qid,
                              qbo_item_name=r.get("nome_completo") or r.get("nome") or nome)
            _aud(con, "balcao.rascunho.item_qbo", por, d["id"],
                 {"linha": li["id"], "qbo_item": qid, "nome": r.get("nome") or nome, "preco": li["unit_price"],
                  "ja_existia": bool(r.get("ja_existia")), "origem": li["source"], "client_id": d["client_id"]}, ip)


def faturar(con, client_id, por, ip=None, gerente=True):
    """'Criar invoice'. Devolve o rascunho faturado (público). Erro para a tela: ErroBalcao (a mensagem diz o que
    fazer); LookupError sem rascunho. Ver o docstring do módulo para a ordem e a idempotência. #346: quem não é
    gerente cria também, e a invoice fica aguardando a revisão do gerente (não envia nem cobra antes)."""
    from command_center.providers import NaoConectado
    d = aberto(con, client_id)
    if not d:
        raise LookupError("este card não tem rascunho aberto")
    if d["status"] == "criando" and not d["uncertain"]:
        raise b.ErroBalcao("a invoice deste rascunho já está sendo criada agora: espere um instante")
    ls = _linhas(con, d["id"])
    if not ls:
        raise b.ErroBalcao("o rascunho não tem linha")
    sem = [li["name"] for li in ls if li["unit_price"] is None]
    if sem:
        raise b.ErroBalcao(f"sem preço: {', '.join(sem[:5])}. Digite o preço da linha antes de criar a invoice")
    cliente = b.cliente_qbo(con, client_id)
    if not cliente:
        raise b.ErroBalcao("este card não está ligado a um cliente do QuickBooks (sem invoice e sem e-mail que bata). "
                           "Ligue no card antes de criar a invoice")
    if d["status"] == "rascunho":
        try:
            _itens_no_qbo(con, d, por, ip)
            numero = b._qbo().proximo_numero_sistema()    # #346: reservado antes, é por ele que se confere depois
        except NaoConectado:
            raise b.ErroBalcao("QuickBooks não está conectado: o rascunho fica salvo, crie a invoice depois")
        except b.ErroBalcao:
            raise
        except Exception as e:                       # noqa: BLE001 — item recusado: nada da invoice saiu
            raise b.ErroBalcao(f"QuickBooks (item): {str(e)[:300]}")
        # o painel grava primeiro: a peça do estoque sai (como no COBRAR) e a requestid fica guardada
        with transacao(con, imediata=True):
            d = um(con, "SELECT * FROM counter_drafts WHERE id=?", (d["id"],))
            if d["status"] != "rascunho":
                raise b.ErroBalcao("a invoice deste rascunho já está sendo criada agora: espere um instante")
            ls = _linhas(con, d["id"])
            if not ls or any(li["unit_price"] is None or not li["qbo_item_id"] for li in ls):
                raise b.ErroBalcao("o rascunho mudou enquanto os itens eram criados: toque em 'Criar invoice' de novo")
            for li in ls:
                if li["source"] == "estoque":
                    _sai_do_estoque(con, d, li, li["qty"], por)
            atualizar(con, "counter_drafts", d["id"], status="criando", uncertain=0, stock_out=1, error=None,
                      requestid=d["requestid"] or uuid.uuid4().hex, doc_number=str(numero), created_by=d["created_by"] or por,
                      closed_by=por, updated_at=agora())
            d = um(con, "SELECT * FROM counter_drafts WHERE id=?", (d["id"],))
    ls = _linhas(con, d["id"])
    corpo = [{"item_id": li["qbo_item_id"], "quantidade": li["qty"], "unitario": li["unit_price"],
              "descricao": li["description"] or li["name"]} for li in ls]
    data = b.hoje()
    try:
        r = b._qbo().invoice_rascunho_sistema(cliente_id=cliente, linhas=corpo, memo=b.memo(con, {"client_id": client_id,
                                              "service_date": data}), data=data, requestid=d["requestid"],
                                              numero=d["doc_number"])
    except NaoConectado:
        _falhou(con, d["id"], por, "QuickBooks não está conectado", devolver=True)
        raise b.ErroBalcao("QuickBooks não está conectado: o rascunho fica salvo, crie a invoice depois")
    except Exception as e:                           # noqa: BLE001 — separa "não saiu" de "não sei"
        if getattr(e, "nada_saiu", False):
            _falhou(con, d["id"], por, str(e), devolver=True)
            raise b.ErroBalcao(f"O QuickBooks recusou a invoice (nada foi criado): {str(e)[:300]}")
        with transacao(con, imediata=True):
            atualizar(con, "counter_drafts", d["id"], uncertain=1, updated_at=agora(),
                      error=f"O QuickBooks não respondeu ({str(e)[:200]}). Toque em 'Criar invoice' de novo: "
                            "é a mesma tentativa e não cria outra invoice. O gerente pode também 'Conferir no QuickBooks'.")
            _aud(con, "balcao.rascunho.invoice_incerta", por, d["id"], {"erro": str(e)[:300], "requestid": d["requestid"],
                                                                         "numero": d["doc_number"]}, ip)
        raise b.ErroBalcao("O QuickBooks não respondeu. Toque em 'Criar invoice' de novo: é a mesma tentativa e não "
                           "cria outra invoice.")
    return _registrar(con, d, r, por, gerente, ip)


def _sai_do_estoque(con, d, li, qty, por, pid=None):
    """A peça do estoque sai (venda, do local do rascunho) com a cobrança no preço da linha, como no COBRAR."""
    # #350: sem saldo não trava (o estoque pode estar desatualizado): o que falta vai para a lista de recontar
    move, falta = estoque.vender_mesmo_sem_saldo(con, li["item_id"], qty, de=d["location"], para_cliente_id=d["client_id"],
                                                 ref=f"linha:{li['id']}", by_user_id=por,
                                                 notes=f"balcão: rascunho #{d['id']}")
    if falta:
        _aud(con, "estoque.vendida_sem_saldo", por, d["id"], {"linha": li["id"], "item": li["item_id"], "nome": li["name"],
                                                               "falta": falta, "client_id": d["client_id"]})
    ch = estoque.registrar_cobranca(con, li["item_id"], d["client_id"], qty, move_id=move, by_user_id=por,
                                    notes=f"balcão: rascunho #{d['id']}")
    campos = {"unit_price": li["unit_price"]}                   # o preço da linha, não o da ficha
    if pid:
        campos.update(status="invoiced", parts_invoice_id=pid)
    atualizar(con, "stock_charges", ch, **campos)
    atualizar(con, "counter_draft_lines", li["id"], move_id=move, charge_id=ch)


def _registrar(con, d, r, por, gerente, ip):
    """A invoice saiu: entra nas invoices de peças. Criada por quem não é gerente, fica aguardando a revisão (#346)."""
    ls = _linhas(con, d["id"])
    total = round(sum(float(li["qty"]) * float(li["unit_price"]) for li in ls), 2)
    data = b.hoje()
    with transacao(con, imediata=True):
        atual = um(con, "SELECT * FROM counter_drafts WHERE id=?", (d["id"],))
        if atual["status"] == "faturado":            # duas telas ao mesmo tempo: o QuickBooks devolveu a mesma
            return publico(con, atual)
        pid = inserir(con, "parts_invoices", client_id=d["client_id"], service_date=data, status="aberta",
                      qbo_invoice_id=str(r.get("id") or ""), doc_number=r.get("numero"), total=total,
                      qbo_synced_at=agora(), created_by=por, draft_id=d["id"], review_pending=0 if gerente else 1,
                      reviewed_by=por if gerente else None, reviewed_at=agora() if gerente else None)
        ids = [li["charge_id"] for li in ls if li["charge_id"]]
        if ids:
            con.execute(f"UPDATE stock_charges SET status='invoiced', parts_invoice_id=? WHERE id IN ({','.join('?' * len(ids))})",
                        (pid, *ids))
        atualizar(con, "counter_drafts", d["id"], status="faturado", uncertain=0, error=None, parts_invoice_id=pid,
                  qbo_invoice_id=str(r.get("id") or ""), doc_number=r.get("numero"), total=total, closed_by=por,
                  closed_at=agora(), updated_at=agora())
        _aud(con, "balcao.rascunho.invoice", por, d["id"],
             {"client_id": d["client_id"], "invoice_pecas": pid, "qbo": r.get("id"), "numero": r.get("numero"),
              "total": total, "linhas": len(ls), "precos_digitados": sum(1 for li in ls if li["price_by"]),
              "requestid": d["requestid"], "aguardando_revisao": not gerente}, ip)
    return publico(con, um(con, "SELECT * FROM counter_drafts WHERE id=?", (d["id"],)))


def conferir(con, client_id, por, ip=None):
    """#346: o QuickBooks não respondeu e o rascunho ficou 'criando'. O gerente confere lá pelo número reservado:
    a invoice existe (do mesmo cliente) → liga ao rascunho; não existe → a peça volta ao estoque e o rascunho volta
    a ser editável. Nada é liberado sem conferir."""
    from command_center.providers import NaoConectado
    d = aberto(con, client_id)
    if not d:
        raise LookupError("este card não tem rascunho aberto")
    if d["status"] != "criando":
        raise b.ErroBalcao("não há invoice esperando resposta do QuickBooks neste rascunho")
    if not d["doc_number"]:
        raise b.ErroBalcao("este rascunho não guardou o número da invoice: confira direto no QuickBooks")
    cliente = b.cliente_qbo(con, client_id)
    try:
        inv = b._qbo().invoice_por_numero(d["doc_number"])
    except NaoConectado:
        raise b.ErroBalcao("QuickBooks não está conectado: não dá para conferir agora")
    if inv and cliente and str(inv.get("cliente_id")) != str(cliente):
        raise b.ErroBalcao(f"a invoice {d['doc_number']} existe no QuickBooks, mas é de outro cliente: confira lá")
    with transacao(con):
        _aud(con, "balcao.rascunho.conferido", por, d["id"],
             {"client_id": client_id, "numero": d["doc_number"], "achou": bool(inv), "qbo": inv.get("id") if inv else None}, ip)
    if inv:
        p = um(con, "SELECT 1 AS x FROM parts_invoices WHERE draft_id=?", (d["id"],))
        criador = um(con, "SELECT role FROM users WHERE id=?", (d["closed_by"],)) if d["closed_by"] else None
        from command_center.api import auth
        g = bool(criador) and auth.pode(criador["role"], "MANAGER")
        return publico(con, d) if p else _registrar(con, d, {"id": inv.get("id"), "numero": inv.get("numero")}, d["closed_by"] or por, g, ip)
    _falhou(con, d["id"], por, f"Conferido no QuickBooks: a invoice {d['doc_number']} não saiu. O rascunho voltou a ser "
                               "editável e a peça voltou ao estoque.", devolver=True)
    return publico(con, um(con, "SELECT * FROM counter_drafts WHERE id=?", (d["id"],)))


# ------------------------------------------------------------------ #346: a revisão do gerente
def _revisavel(con, pid):
    p = um(con, "SELECT * FROM parts_invoices WHERE id=?", (pid,))
    if not p or not p["draft_id"]:
        raise LookupError("invoice de peças não encontrada")
    if not p["review_pending"]:
        raise b.ErroBalcao("esta invoice já foi revisada")
    if p["status"] != "aberta" or p["paid_at"]:
        raise b.ErroBalcao(f"esta invoice já está {'paga' if p['paid_at'] else p['status']}")
    return p, um(con, "SELECT * FROM counter_drafts WHERE id=?", (p["draft_id"],))


def revisao(con, pid):
    p, d = _revisavel(con, pid)
    return {"invoice": b.invoice_publica(con, p), "rascunho": publico(con, d)}


def _sync(con, pid):
    return b.sincronizar_qbo(con, pid)


def revisar_adicionar(con, pid, por, ip=None, **linha):
    p, d = _revisavel(con, pid)
    with transacao(con, imediata=True):
        _, li, _, digitado = adicionar(con, d["client_id"], linha.pop("origem"), por, rascunho=d, **linha)
    if not li["qbo_item_id"]:
        try:
            _itens_no_qbo(con, d, por, ip)
        except Exception as e:                       # noqa: BLE001 — sem item, a linha não fica
            with transacao(con):
                con.execute("DELETE FROM counter_draft_lines WHERE id=?", (li["id"],))
            raise b.ErroBalcao(f"QuickBooks (item): {str(e)[:300]}")
    with transacao(con, imediata=True):
        li = um(con, "SELECT * FROM counter_draft_lines WHERE id=?", (li["id"],))
        if li["source"] == "estoque":
            _sai_do_estoque(con, d, li, li["qty"], por, pid)
        _aud(con, "balcao.revisao.adicionar", por, d["id"],
             {"invoice_pecas": pid, "linha": li["id"], "nome": li["name"], "qty": li["qty"], "preco": li["unit_price"],
              "preco_tabela": li["ref_price"]}, ip)
    return _sync(con, pid)


def revisar_editar(con, pid, lid, por, qty=None, preco=None, ip=None):
    p, d = _revisavel(con, pid)
    with transacao(con, imediata=True):
        li = um(con, "SELECT * FROM counter_draft_lines WHERE id=? AND draft_id=?", (lid, d["id"]))
        if not li:
            raise LookupError("linha não encontrada nesta invoice")
        campos = {}
        if qty is not None and _qty(qty) != float(li["qty"]):
            nova = _qty(qty)
            if li["source"] == "estoque" and li["charge_id"]:
                delta = round(nova - float(li["qty"]), 3)
                if delta > 0:                                   # #350: a mais, sai mesmo sem saldo
                    _, falta = estoque.vender_mesmo_sem_saldo(con, li["item_id"], delta, de=d["location"],
                                                              para_cliente_id=d["client_id"], ref=f"linha:{li['id']}",
                                                              by_user_id=por, notes=f"revisão do gerente: rascunho #{d['id']}")
                    if falta:
                        _aud(con, "estoque.vendida_sem_saldo", por, d["id"], {"linha": li["id"], "item": li["item_id"],
                                                                               "nome": li["name"], "falta": falta}, ip)
                else:
                    estoque.devolver_venda(con, li["item_id"], -delta, para=d["location"], ref=f"linha:{li['id']}",
                                           by_user_id=por, notes=f"revisão do gerente: rascunho #{d['id']}")
                if li["charge_id"]:
                    atualizar(con, "stock_charges", li["charge_id"], qty=nova)
            campos["qty"] = nova
        if preco is not None and _preco(preco) != li["unit_price"]:
            campos["unit_price"] = _preco(preco)
            campos["price_by"] = por if _digitado(campos["unit_price"], li["ref_price"]) else None
            if li["charge_id"]:
                atualizar(con, "stock_charges", li["charge_id"], unit_price=campos["unit_price"])
        if not campos:
            return p
        atualizar(con, "counter_draft_lines", li["id"], updated_at=agora(), **campos)
        _aud(con, "balcao.revisao.editar", por, d["id"],
             {"invoice_pecas": pid, "linha": li["id"], "nome": li["name"],
              "antes": {"qty": li["qty"], "preco": li["unit_price"]},
              "depois": {"qty": campos.get("qty", li["qty"]), "preco": campos.get("unit_price", li["unit_price"])}}, ip)
    return _sync(con, pid)


def revisar_remover(con, pid, lid, por, ip=None):
    p, d = _revisavel(con, pid)
    with transacao(con, imediata=True):
        li = um(con, "SELECT * FROM counter_draft_lines WHERE id=? AND draft_id=?", (lid, d["id"]))
        if not li:
            raise LookupError("linha não encontrada nesta invoice")
        if li["source"] == "estoque" and li["charge_id"]:
            estoque.devolver_venda(con, li["item_id"], li["qty"], para=d["location"], ref=f"linha:{li['id']}",
                                   by_user_id=por, notes=f"revisão do gerente: rascunho #{d['id']}")
            if li["charge_id"]:
                atualizar(con, "stock_charges", li["charge_id"], status="waived", resolved_by=por, resolved_at=agora(),
                          notes="removida na revisão do gerente")
        con.execute("DELETE FROM counter_draft_lines WHERE id=?", (li["id"],))
        _aud(con, "balcao.revisao.remover", por, d["id"],
             {"invoice_pecas": pid, "linha": li["id"], "nome": li["name"], "qty": li["qty"], "preco": li["unit_price"]}, ip)
    return _sync(con, pid)


def revisar_confirmar(con, pid, por, ip=None):
    p, d = _revisavel(con, pid)
    if p["qbo_error"]:
        raise b.ErroBalcao("a invoice no QuickBooks não está igual a esta: toque em 'Tentar de novo' antes de confirmar")
    with transacao(con, imediata=True):
        atualizar(con, "parts_invoices", pid, review_pending=0, reviewed_by=por, reviewed_at=agora())
        _aud(con, "balcao.revisao.confirmar", por, d["id"],
             {"invoice_pecas": pid, "numero": p["doc_number"], "total": p["total"], "criada_por": p["created_by"],
              "linhas": len(_linhas(con, d["id"]))}, ip)
    return um(con, "SELECT * FROM parts_invoices WHERE id=?", (pid,))


# ------------------------------------------------------------------ #346: o mais próximo do que foi lido
def _norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]", "", s)


def _palavras(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return [w for w in re.split(r"[^a-z0-9]+", s) if len(w) >= 2]


def _lev(a, b_, teto=3):
    """Distância de edição, parando cedo: acima de `teto` devolve teto+1."""
    if abs(len(a) - len(b_)) > teto:
        return teto + 1
    ant = list(range(len(b_) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b_, 1):
            cur.append(min(ant[j] + 1, cur[j - 1] + 1, ant[j - 1] + (ca != cb)))
        if min(cur) > teto:
            return teto + 1
        ant = cur
    return ant[-1]


def _nota_codigo(n, c):
    if not n or not c or len(n) < 3 or len(c) < 3:
        return 0
    if n == c:
        return 100
    curto = min(len(n), len(c))
    d = _lev(n, c, 2) if curto >= 5 else 9
    if d == 1:
        return 90
    if d == 2 and curto >= 8:
        return 78
    if curto >= 4 and (c.startswith(n) or n.startswith(c)):
        return max(60, 85 - 3 * abs(len(n) - len(c)))
    if len(n) >= 4 and n in c:
        return 60
    return 0


def _nota_nome(ws, n, nome):
    if not ws:
        return 0
    nw = _palavras(nome)
    if not nw:
        return 0
    bate = sum(1 for w in ws if any(x.startswith(w) or (len(w) >= 4 and _lev(w, x, 1) <= 1) for x in nw))
    if not bate:
        return 0
    nota = 45 + 40 * bate / len(ws)
    if _norm(nome).startswith(n):
        nota += 5
    return round(nota)


def aproximado(con, texto, limit=8):
    """O que mais se parece com o que o leitor (ou a pessoa) mandou: peça do estoque (código da embalagem, etiqueta,
    SKU, número da peça ou nome) e item do QuickBooks (nome). Em ordem de proximidade; `destaque` quando só um é
    muito próximo. Nada entra no rascunho sem um toque."""
    t = (texto or "").strip()[:120]
    n, ws = _norm(t), _palavras(t)
    if len(n) < 2:
        return {"texto": t, "itens": [], "destaque": None}
    melhor = {}
    for r in todos(con, """SELECT i.id, i.name, i.price, i.sku, i.part_number, b.code FROM stock_items i
                           LEFT JOIN stock_barcodes b ON b.item_id=i.id WHERE i.active=1"""):
        nota = max([_nota_codigo(n, _norm(c)) for c in (r["code"], r["sku"], r["part_number"]) if c] + [0])
        nota = max(nota, _nota_nome(ws, n, r["name"]))
        k = ("estoque", r["id"])
        if nota and nota > melhor.get(k, {}).get("nota", 0):
            melhor[k] = {"origem": "estoque", "item_id": r["id"], "nome": r["name"], "preco": r["price"],
                         "codigo": r["code"], "nota": nota}
    for q in todos(con, "SELECT id, name, full_name, price FROM qbo_items WHERE active=1 AND COALESCE(type,'')!='Category'"):
        nota = max(_nota_nome(ws, n, q["full_name"] or q["name"]), _nota_codigo(n, _norm(q["name"])))
        if nota:
            melhor[("quickbooks", q["id"])] = {"origem": "quickbooks", "qbo_item_id": q["id"],
                                               "nome": q["full_name"] or q["name"], "preco": q["price"], "nota": nota}
    itens = sorted((x for x in melhor.values() if x["nota"] >= 55), key=lambda x: (-x["nota"], len(x["nome"]), x["nome"]))[:limit]
    destaque = itens[0] if itens and itens[0]["nota"] >= 75 and (len(itens) == 1 or itens[0]["nota"] - itens[1]["nota"] >= 10) else None
    return {"texto": t, "itens": itens, "destaque": destaque}
