"""GUARDAR no balcão do celular: a lista de peças para guardar, pendente até o "Confirmar".

Dono, 20/10: *"a primeira coisa no balcão a ser mostrada é qual cliente que é. E aí seleciona se é para cobrar, se é
para guardar. E aí, logo abaixo […] mostra o que está guardando para poder confirmar naquele cliente. Se tem, por
exemplo, salvou duas peças para guardar daquele cliente. Aí lá embaixo um botãozinho de confirmar."*

- Cada peça lida, digitada ou registrada na hora entra em `counter_keep_lines`, ligada ao card. **Não mexe no
  estoque**: dá para remover, mudar a quantidade ou o local.
- **Confirmar** põe todas no estoque do cliente numa transação só: cada linha vira a leitura `guardar` de sempre
  (`balcao.lancar`: entrada no estoque do cliente, `counter_scans`, desfazer) e a auditoria `balcao.guardar`.
- Toda linha é procurada pelo card da URL: a de outro card é igual a não existir (nunca no card de outro).
"""
import math

from command_center.db import atualizar, auditar, inserir, todos, transacao, um
from command_center.providers import balcao as b, estoque

MAX_QTY = 1000
MAX_LINHAS = 100


def _qty(v):
    try:
        q = float(v)
    except (TypeError, ValueError):
        raise b.ErroBalcao("quantidade inválida")
    if not math.isfinite(q) or q <= 0 or q > MAX_QTY:
        raise b.ErroBalcao(f"a quantidade vai de mais de 0 até {MAX_QTY}")
    return round(q, 3)


def _cliente(con, client_id):
    if not um(con, "SELECT 1 AS x FROM clients WHERE id=?", (client_id,)):
        raise LookupError("cliente não existe")


def lista(con, client_id):
    ls = todos(con, """SELECT k.id, k.item_id, k.qty, k.location, k.code, i.name FROM counter_keep_lines k
                       JOIN stock_items i ON i.id=k.item_id WHERE k.client_id=? ORDER BY k.id""", (client_id,))
    return [{"id": x["id"], "item_id": x["item_id"], "nome": x["name"], "qty": x["qty"], "local": x["location"],
             "codigo": x["code"]} for x in ls]


def adicionar(con, client_id, item_id, por, qty=1, local=None, codigo=None):
    """Põe a peça na lista do card. A mesma peça no mesmo local soma: ler duas vezes são duas unidades."""
    _cliente(con, client_id)
    it = estoque.item(con, item_id)
    if not it["active"]:
        raise b.ErroBalcao(f"{it['name']} foi excluída do estoque")
    if it["tracking"] == "serie":
        raise b.ErroBalcao(f"{it['name']} tem número de série: lance pela tela de Estoque")
    qty = _qty(qty)
    loc = estoque.local(con, local or estoque.SEDE)["code"]
    ja = um(con, "SELECT * FROM counter_keep_lines WHERE client_id=? AND item_id=? AND location=?", (client_id, it["id"], loc))
    if ja:
        nova = round(float(ja["qty"]) + qty, 3)
        if nova > MAX_QTY:
            raise b.ErroBalcao(f"a quantidade vai até {MAX_QTY}")
        atualizar(con, "counter_keep_lines", ja["id"], qty=nova)
        return ja["id"]
    if um(con, "SELECT COUNT(*) AS n FROM counter_keep_lines WHERE client_id=?", (client_id,))["n"] >= MAX_LINHAS:
        raise b.ErroBalcao(f"a lista tem o máximo de {MAX_LINHAS} peças: confirme e comece outra")
    return inserir(con, "counter_keep_lines", client_id=client_id, item_id=it["id"], qty=qty, location=loc,
                   code=codigo or None, created_by=por)


def _linha(con, client_id, lid):
    li = um(con, "SELECT * FROM counter_keep_lines WHERE id=? AND client_id=?", (lid, client_id))
    if not li:
        raise LookupError("peça não encontrada na lista deste cliente")
    return li


def editar(con, client_id, lid, qty=None, local=None):
    li = _linha(con, client_id, lid)
    mud = {}
    if qty is not None:
        mud["qty"] = _qty(qty)
    if local is not None:
        mud["location"] = estoque.local(con, local)["code"]
    if mud:
        atualizar(con, "counter_keep_lines", li["id"], **mud)
    return li


def remover(con, client_id, lid):
    li = _linha(con, client_id, lid)
    con.execute("DELETE FROM counter_keep_lines WHERE id=?", (li["id"],))
    return li


def confirmar(con, client_id, por, ip=None):
    """Tudo da lista entra no estoque do cliente, numa transação só. Devolve as leituras criadas."""
    _cliente(con, client_id)
    with transacao(con, imediata=True):
        ls = todos(con, "SELECT * FROM counter_keep_lines WHERE client_id=? ORDER BY id", (client_id,))
        if not ls:
            raise b.ErroBalcao("nada na lista para guardar")
        feitas = []
        for li in ls:
            s = b.lancar(con, client_id, li["item_id"], "guardar", li["qty"], li["location"], por, li["code"])
            auditar(con, "balcao.guardar", f"user:{por}" if por else "system", user_id=por, entity_type="client",
                    entity_id=client_id, detail={"item": li["item_id"], "qty": li["qty"], "leitura": s["id"],
                                                 "local": li["location"], "confirmado_da_lista": True}, ip=ip)
            feitas.append(s["id"])
        con.execute("DELETE FROM counter_keep_lines WHERE client_id=?", (client_id,))
    return feitas
