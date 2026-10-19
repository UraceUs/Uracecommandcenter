"""Rascunho de invoice do balcão (#341).

Dono, 19/10: *"colocar peças e valores em um rascunho de bulk para o cliente e dali o command center cria a invoice
com os itens que eu falar; se não tiver item ele cria; coloque também todo o inventário do QuickBooks"*.

O QuickBooks aqui é falso e se comporta como o de verdade no que importa: o nome do item é único e a mesma
`requestid` devolve a mesma resposta (não cria outra). Dados fictícios.
"""
import os

import pytest

os.environ["URACE_ENV"] = "/nao/existe"

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api import auth  # noqa: E402
from command_center.api.main import app  # noqa: E402
from command_center.db import aplicar_schema, conectar, inserir, todos, um  # noqa: E402
from command_center.providers import balcao, estoque  # noqa: E402

B = "/ops/api/balcao"
SENHA = "senha-forte-123"
HOJE = "2026-10-19"


class NaoCriada(Exception):
    nada_saiu = True


class QboFalso:
    def __init__(self):
        self.itens, self.invoices, self.por_req, self.chamadas = {}, [], {}, []
        self.perder_item = self.perder_invoice = self.recusar_invoice = False
        self.n_numero, self.atualizacoes = 200, []

    def proximo_numero_sistema(self):
        self.n_numero += 1
        return f"URACE-0{self.n_numero}"

    def invoice_por_numero(self, numero):
        return next(({"id": i["id"], "numero": i["numero"], "cliente_id": i["cliente_id"]}
                     for i in self.invoices if i["numero"] == numero), None)

    def invoice_pecas_sistema(self, cliente_id, linhas, memo, data, invoice_id=None):
        self.atualizacoes.append((invoice_id, linhas))
        inv = next(i for i in self.invoices if i["id"] == invoice_id)
        inv["linhas"] = linhas
        return {"id": invoice_id, "numero": inv["numero"]}

    def item_avulso_sistema(self, nome, preco, descricao=None, requestid=None):
        self.chamadas.append(("item", nome, requestid))
        if nome in self.itens:
            return {**self.itens[nome], "ja_existia": True}
        self.itens[nome] = {"id": f"qi-{len(self.itens) + 1}", "nome": nome, "preco": preco, "tipo": "Service"}
        if self.perder_item:
            self.perder_item = False
            raise TimeoutError("a resposta se perdeu")
        return {**self.itens[nome], "ja_existia": False}

    def invoice_rascunho_sistema(self, cliente_id, linhas, memo, data, requestid, numero=None):
        self.chamadas.append(("invoice", requestid))
        if self.recusar_invoice:
            self.recusar_invoice = False
            raise NaoCriada("HTTP 400: recusada")
        if requestid in self.por_req:
            return self.por_req[requestid]
        inv = {"id": f"inv-{len(self.invoices) + 1}", "numero": numero,
               "cliente_id": cliente_id, "linhas": linhas}
        self.invoices.append(inv)
        self.por_req[requestid] = inv
        if self.perder_invoice:
            self.perder_invoice = False
            raise TimeoutError("a resposta se perdeu")
        return inv

    def qbo_invoice(self, id):
        return {"saldo": 10, "total": 10}

    def enviar_invoice_sistema(self, invoice_id):
        self.chamadas.append(("enviar", invoice_id))
        return {"id": invoice_id, "enviado_para": "familia@example.com"}


@pytest.fixture()
def cli(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path))
    qbo = QboFalso()
    import command_center.providers as prov
    monkeypatch.setattr(prov, "modulo", lambda nome: qbo if nome == "quickbooks" else None)
    monkeypatch.setattr(balcao, "hoje", lambda: HOJE)
    con = conectar(); aplicar_schema(con)
    auth.criar_usuario(con, "mec@urace.us", "Mecânico", "OPERATOR", SENHA)
    auth.criar_usuario(con, "ger@urace.us", "Gerente", "MANAGER", SENHA)
    auth.criar_usuario(con, "olho@urace.us", "Visitante", "VIEWER", SENHA)
    leo = inserir(con, "clients", name="Maria Teste", pilot_name="Leo Teste", email="familia@example.com",
                  status="ACTIVE", source="manual")
    outro = inserir(con, "clients", name="Outro Teste", email="outro@example.com", status="ACTIVE", source="manual")
    for cid, ref in ((leo, "qbo-cust-7"), (outro, "qbo-cust-8")):
        inserir(con, "invoices", client_id=cid, doc_number=f"URACE-00{cid}", amount=10, balance=0, status="paid",
                issued_on="2026-09-01", customer_ref=ref)
    para = estoque.criar_item(con, "peca", "Front bumper (teste)", price=89.5)
    con.execute("UPDATE stock_items SET qbo_item_id='qb-50', qbo_item_name='Parts:Front bumper (teste)' WHERE id=?", (para,))
    estoque.entrada(con, para, qty=5)
    sem_preco = estoque.criar_item(con, "peca", "Rear bumper fixing bolt (teste)")     # sem preço final
    estoque.entrada(con, sem_preco, qty=10)
    con.execute("INSERT INTO qbo_items (id, name, full_name, price, type, active) VALUES ('qb-7','Chain 219','Parts:Chain 219',30,'Service',1)")
    con.execute("INSERT INTO qbo_items (id, name, full_name, price, type, active) VALUES ('qb-1','Parts','Parts',NULL,'Category',1)")
    con.close()
    with TestClient(app, base_url="https://cc.test") as c:
        c.qbo, c.leo, c.outro, c.para, c.sem_preco = qbo, leo, outro, para, sem_preco
        yield c


def entra(cli, email="mec@urace.us"):
    cli.cookies.clear()
    assert cli.post("/ops/api/auth/login", json={"email": email, "password": SENHA}).status_code == 200
    return {"X-CSRF": cli.cookies.get("cc_csrf")}


def linha(cli, h, cid=None, **corpo):
    return cli.post(f"{B}/cliente/{cid or cli.leo}/rascunho/linhas", json=corpo, headers=h)


def faturar(cli, cid=None):
    h = entra(cli, "ger@urace.us")
    return cli.post(f"{B}/cliente/{cid or cli.leo}/rascunho/faturar", headers=h)


def saldo(item):
    return estoque.vendavel(conectar(), item)


def test_rascunho_com_estoque_quickbooks_e_livre_vira_uma_invoice_com_os_precos_digitados(cli):
    h = entra(cli)
    assert linha(cli, h, origem="estoque", item_id=cli.para, qty=2, preco=80).status_code == 201
    assert linha(cli, h, origem="quickbooks", qbo_item_id="qb-7").status_code == 201
    r = linha(cli, h, origem="livre", nome="Solda no chassi", preco=45, descricao="solda (teste)")
    assert r.status_code == 201, r.text
    rz = cli.get(f"{B}/cliente/{cli.leo}/rascunho", headers=h).json()["rascunho"]
    assert [x["preco"] for x in rz["linhas"]] == [80, 30, 45] and rz["total"] == 235 and rz["pronto"]
    assert [x["preco_digitado"] for x in rz["linhas"]] == [True, False, True], "preço fora da tabela fica marcado"
    r = faturar(cli)
    assert r.status_code == 200, r.text
    assert len(cli.qbo.invoices) == 1
    inv = cli.qbo.invoices[0]
    assert inv["cliente_id"] == "qbo-cust-7"
    assert [(x["item_id"], x["quantidade"], x["unitario"]) for x in inv["linhas"]] == \
        [("qb-50", 2, 80), ("qb-7", 1, 30), ("qi-1", 1, 45)]
    assert [c[1] for c in cli.qbo.chamadas if c[0] == "item"] == ["Solda no chassi"], "só a livre cria item"
    assert saldo(cli.para) == 3, "a peça do estoque sai como no COBRAR"
    fat = r.json()["faturados"][0]
    assert fat["status"] == "faturado" and fat["doc_number"] == "URACE-0201" and r.json()["rascunho"] is None
    con = conectar()
    p = um(con, "SELECT * FROM parts_invoices WHERE draft_id=?", (fat["id"],))
    assert p["total"] == 235 and p["qbo_invoice_id"] == "inv-1"
    eventos = {a["event"] for a in todos(con, "SELECT event FROM audit_logs")}
    assert {"balcao.rascunho.criar", "balcao.rascunho.preco", "balcao.rascunho.item_qbo", "balcao.rascunho.invoice"} <= eventos
    # o COBRAR do dia não entra na invoice que nasceu do rascunho
    assert balcao._invoice_do_dia(con, cli.leo, HOJE, None)["id"] != p["id"]
    # enviar, como a invoice de peças de hoje
    hg = entra(cli, "ger@urace.us")
    assert cli.post(f"{B}/invoices/{p['id']}/enviar", headers=hg).status_code == 200
    assert ("enviar", "inv-1") in cli.qbo.chamadas


def test_linha_livre_cria_o_item_uma_vez_so(cli):
    h = entra(cli)
    linha(cli, h, origem="livre", nome="Mão de obra extra", preco=60)
    cli.qbo.perder_item = True                       # criou lá, mas a resposta não voltou
    assert faturar(cli).status_code == 400
    assert not cli.qbo.invoices
    assert faturar(cli).status_code == 200
    assert list(cli.qbo.itens) == ["Mão de obra extra"], "repetir não duplica o item"
    h = entra(cli)
    linha(cli, h, origem="livre", nome="Mão de obra extra", preco=60)
    assert faturar(cli).status_code == 200
    assert len(cli.qbo.itens) == 1 and len(cli.qbo.invoices) == 2


def test_resposta_perdida_nao_duplica_a_invoice(cli):
    h = entra(cli)
    linha(cli, h, origem="estoque", item_id=cli.para)
    cli.qbo.perder_invoice = True
    r = faturar(cli)
    assert r.status_code == 400 and "não respondeu" in r.json()["detail"]
    rz = cli.get(f"{B}/cliente/{cli.leo}/rascunho", headers=entra(cli)).json()["rascunho"]
    assert rz["status"] == "criando" and rz["incerto"]
    lid = rz["linhas"][0]["id"]
    assert cli.patch(f"{B}/cliente/{cli.leo}/rascunho/linhas/{lid}", json={"preco": 1}, headers=entra(cli)).status_code == 400
    assert faturar(cli).status_code == 200
    assert len(cli.qbo.invoices) == 1, "a mesma requestid: o QuickBooks devolve a mesma invoice"
    reqs = [c[1] for c in cli.qbo.chamadas if c[0] == "invoice"]
    assert len(reqs) == 2 and reqs[0] == reqs[1]
    assert saldo(cli.para) == 4, "a peça saiu uma vez só"


def test_recusa_certa_devolve_a_peca_e_o_rascunho_volta(cli):
    h = entra(cli)
    linha(cli, h, origem="estoque", item_id=cli.para)
    cli.qbo.recusar_invoice = True
    assert faturar(cli).status_code == 400
    assert saldo(cli.para) == 5
    rz = cli.get(f"{B}/cliente/{cli.leo}/rascunho", headers=entra(cli)).json()["rascunho"]
    assert rz["status"] == "rascunho" and rz["erro"]


def test_linha_sem_preco_bloqueia_e_a_peca_sem_preco_final_entra_com_o_preco_digitado(cli):
    h = entra(cli)
    r = linha(cli, h, origem="estoque", item_id=cli.sem_preco)
    assert r.status_code == 201 and r.json()["rascunho"]["sem_preco"] == ["Rear bumper fixing bolt (teste)"]
    r = faturar(cli)
    assert r.status_code == 400 and "sem preço" in r.json()["detail"]
    assert not cli.qbo.chamadas, "nada vai ao QuickBooks sem preço"
    h = entra(cli)
    lid = cli.get(f"{B}/cliente/{cli.leo}/rascunho", headers=h).json()["rascunho"]["linhas"][0]["id"]
    assert cli.patch(f"{B}/cliente/{cli.leo}/rascunho/linhas/{lid}", json={"preco": 3.5, "qty": 4}, headers=h).status_code == 200
    assert faturar(cli).status_code == 200
    assert cli.qbo.invoices[0]["linhas"][0]["unitario"] == 3.5 and saldo(cli.sem_preco) == 6
    assert estoque.item(conectar(), cli.sem_preco)["qbo_item_id"] == "qi-1", "a peça fica ligada ao item criado"


def test_rascunho_de_um_card_nao_aparece_em_outro_e_permissoes(cli):
    h = entra(cli)
    linha(cli, h, origem="livre", nome="Ajuste (teste)", preco=20)
    lid = cli.get(f"{B}/cliente/{cli.leo}/rascunho", headers=h).json()["rascunho"]["linhas"][0]["id"]
    assert cli.get(f"{B}/cliente/{cli.outro}/rascunho", headers=h).json()["rascunho"] is None
    assert cli.patch(f"{B}/cliente/{cli.outro}/rascunho/linhas/{lid}", json={"preco": 1}, headers=h).status_code == 404
    assert cli.delete(f"{B}/cliente/{cli.outro}/rascunho/linhas/{lid}", headers=h).status_code == 404
    assert faturar(cli, cli.outro).status_code == 404
    assert not cli.qbo.invoices
    entra(cli, "olho@urace.us")
    assert cli.get(f"{B}/cliente/{cli.leo}/rascunho").status_code == 403
    cli.cookies.clear()
    assert cli.get(f"{B}/cliente/{cli.leo}/rascunho").status_code == 401
    assert cli.get(f"{B}/quickbooks/itens").status_code == 401


def test_inventario_do_quickbooks_com_busca_e_paginacao(cli):
    h = entra(cli)
    r = cli.get(f"{B}/quickbooks/itens", params={"q": "chain", "limit": 10}, headers=h).json()
    assert r["total"] == 1 and r["itens"][0]["id"] == "qb-7"
    assert all(i["type"] != "Category" for i in cli.get(f"{B}/quickbooks/itens", headers=h).json()["itens"])


# ------------------------------------------------------------------ #346
def test_mecanico_cria_a_invoice_e_o_gerente_revisa_a_mesma_no_quickbooks(cli):
    h = entra(cli)
    linha(cli, h, origem="estoque", item_id=cli.para, qty=2)
    linha(cli, h, origem="livre", nome="Solda no chassi", preco=45)
    r = cli.post(f"{B}/cliente/{cli.leo}/rascunho/faturar", headers=h)
    assert r.status_code == 200, r.text
    con = conectar()
    p = um(con, "SELECT * FROM parts_invoices WHERE draft_id IS NOT NULL")
    assert p["review_pending"] == 1 and len(cli.qbo.invoices) == 1
    assert cli.post(f"{B}/invoices/{p['id']}/conferir-pagamento", headers=h).status_code == 400, "cartão só depois da revisão"
    assert cli.get(f"{B}/invoices/{p['id']}/revisao", headers=h).status_code == 403, "revisar é do gerente"
    hg = entra(cli, "ger@urace.us")
    assert cli.post(f"{B}/invoices/{p['id']}/enviar", headers=hg).status_code == 400, "enviar só depois da revisão"
    from command_center.api import atencao
    assert any("aguardando a sua revisão" in x["title"] for x in atencao.coletar(con))
    rv = cli.get(f"{B}/invoices/{p['id']}/revisao", headers=hg).json()
    bump, solda = rv["rascunho"]["linhas"]
    r = cli.patch(f"{B}/invoices/{p['id']}/revisao/linhas/{bump['id']}", json={"qty": 1, "preco": 85}, headers=hg)
    assert r.status_code == 200, r.text
    assert cli.delete(f"{B}/invoices/{p['id']}/revisao/linhas/{solda['id']}", headers=hg).status_code == 200
    assert len(cli.qbo.invoices) == 1, "a mesma invoice, nunca outra"
    inv_id, ls = cli.qbo.atualizacoes[-1]
    assert inv_id == "inv-1" and [(x["quantidade"], x["unitario"]) for x in ls] == [(1, 85)]
    assert saldo(cli.para) == 4, "a quantidade que voltou volta ao estoque"
    assert cli.post(f"{B}/invoices/{p['id']}/revisao/confirmar", headers=hg).status_code == 200
    assert um(conectar(), "SELECT total FROM parts_invoices WHERE id=?", (p["id"],))["total"] == 85
    assert cli.post(f"{B}/invoices/{p['id']}/enviar", headers=hg).status_code == 200
    eventos = [a["event"] for a in todos(conectar(), "SELECT event FROM audit_logs")]
    assert {"balcao.revisao.editar", "balcao.revisao.remover", "balcao.revisao.confirmar", "balcao.enviar"} <= set(eventos)


def test_conferir_no_quickbooks_liga_ou_libera(cli):
    h = entra(cli)
    linha(cli, h, origem="estoque", item_id=cli.para)
    cli.qbo.perder_invoice = True
    assert faturar(cli).status_code == 400
    hg = entra(cli, "ger@urace.us")
    r = cli.post(f"{B}/cliente/{cli.leo}/rascunho/conferir", headers=hg)
    assert r.status_code == 200 and r.json()["rascunho"] is None and r.json()["faturados"][0]["doc_number"] == "URACE-0201"
    assert len(cli.qbo.invoices) == 1
    # a invoice não saiu: conferir libera o rascunho e devolve a peça
    h = entra(cli)
    linha(cli, h, origem="estoque", item_id=cli.para)

    def sumiu(**kw):
        raise TimeoutError("sem resposta")
    cli.qbo.invoice_rascunho_sistema = sumiu
    assert faturar(cli).status_code == 400 and saldo(cli.para) == 3
    hg = entra(cli, "ger@urace.us")
    r = cli.post(f"{B}/cliente/{cli.leo}/rascunho/conferir", headers=hg).json()["rascunho"]
    assert r["status"] == "rascunho" and "não saiu" in r["erro"] and saldo(cli.para) == 4


def test_codigo_com_um_caractere_trocado_e_nome_parcial_acham_o_mais_proximo(cli):
    con = conectar()
    balcao.cadastrar_codigo(con, "7891234567895", cli.para)
    h = entra(cli)
    assert cli.get(f"{B}/ler", params={"codigo": "7891234567805", "client_id": cli.leo}, headers=h).json()["tipo"] == "desconhecido"
    r = cli.get(f"{B}/aproximado", params={"q": "7891234567805"}, headers=h).json()
    assert r["destaque"]["origem"] == "estoque" and r["destaque"]["item_id"] == cli.para
    r = cli.get(f"{B}/aproximado", params={"q": "chai 21"}, headers=h).json()
    assert r["itens"][0]["origem"] == "quickbooks" and r["itens"][0]["qbo_item_id"] == "qb-7"


def test_item_novo_da_linha_livre_entra_na_categoria_parts(monkeypatch):
    import importlib
    import sys
    sys.path.insert(0, "adminai/mcp")
    qb = importlib.import_module("quickbooks_mcp")
    qb._CATEGORIA_PARTS.clear()
    posts = []

    def _query(sql):
        if "Account" in sql:
            return {"Account": [{"Id": "79", "Name": "Sales"}]}
        if "Category" in sql:
            return {"Item": [{"Id": "c-parts", "Name": "Parts", "Type": "Category"}]}
        return {}

    def _req(caminho, metodo="GET", corpo=None, params=None):
        posts.append((caminho, corpo, params))
        return {"Item": {"Id": "it-1", "Name": corpo["Name"], "FullyQualifiedName": "Parts:" + corpo["Name"]}}
    monkeypatch.setattr(qb, "_query", _query)
    monkeypatch.setattr(qb, "_req", _req)
    r = qb.item_avulso_sistema("Solda no chassi", 45, requestid="rq-1")
    caminho, corpo, params = posts[-1]
    assert corpo["ParentRef"] == {"value": "c-parts"} and corpo["SubItem"] is True and params == {"requestid": "rq-1"}
    assert r["nome_completo"] == "Parts:Solda no chassi"
    # sem a categoria lá, cria uma vez
    qb._CATEGORIA_PARTS.clear()
    posts.clear()
    monkeypatch.setattr(qb, "_query", lambda sql: {"Account": [{"Id": "79", "Name": "Sales"}]} if "Account" in sql else {})

    def _req2(caminho, metodo="GET", corpo=None, params=None):
        posts.append(corpo)
        return {"Item": {"Id": "c-nova" if corpo.get("Type") == "Category" else "it-2", "Name": corpo["Name"]}}
    monkeypatch.setattr(qb, "_req", _req2)
    qb.item_avulso_sistema("Outra linha", 10)
    qb.item_avulso_sistema("Mais uma", 10)
    assert [c["Type"] for c in posts].count("Category") == 1 and posts[-1]["ParentRef"] == {"value": "c-nova"}
    qb._CATEGORIA_PARTS.clear()


def test_a_linha_e_a_da_url_e_nao_o_numero_do_cliente(cli):
    """Revisão do #343: o mesmo `Path` em dois parâmetros fazia o número da linha valer o do cliente."""
    h = entra(cli)
    linha(cli, h, cid=cli.outro, origem="livre", nome="Ajuste (teste)", preco=20)
    lid = cli.get(f"{B}/cliente/{cli.outro}/rascunho", headers=h).json()["rascunho"]["linhas"][0]["id"]
    assert lid != cli.outro
    r = cli.patch(f"{B}/cliente/{cli.outro}/rascunho/linhas/{lid}", json={"preco": 25}, headers=h)
    assert r.status_code == 200 and r.json()["rascunho"]["linhas"][0]["preco"] == 25


def test_rascunho_com_peca_sem_saldo_cria_a_invoice_e_marca_para_recontar(cli):
    """#350 (dono, 19/10: "permita criar mesmo sem ter no estoque pois pode ser que o estoque esteja desatualizado")."""
    con = conectar()
    estoque.contar(con, cli.para, 0)
    h = entra(cli)
    linha(cli, h, origem="estoque", item_id=cli.para, qty=2, preco=80)
    assert cli.get(f"{B}/cliente/{cli.leo}/rascunho", headers=h).json()["rascunho"]["linhas"][0]["sem_saldo"]
    r = cli.post(f"{B}/cliente/{cli.leo}/rascunho/faturar", headers=h)
    assert r.status_code == 200, r.text
    con = conectar()
    assert estoque.vendavel(con, cli.para) == 0 and [x["falta"] for x in estoque.a_recontar(con)] == [2]
    from command_center.api import atencao
    assert any("vendida(s) sem saldo" in x["title"] for x in atencao.coletar(con))
    # o gerente tira uma unidade na revisão e depois a linha: o "sem saldo" se cancela, nada entra na prateleira
    p = um(con, "SELECT id FROM parts_invoices WHERE draft_id IS NOT NULL")["id"]
    hg = entra(cli, "ger@urace.us")
    lid = cli.get(f"{B}/invoices/{p}/revisao", headers=hg).json()["rascunho"]["linhas"][0]["id"]
    assert cli.patch(f"{B}/invoices/{p}/revisao/linhas/{lid}", json={"qty": 1}, headers=hg).status_code == 200
    assert [x["falta"] for x in estoque.a_recontar(conectar())] == [1] and saldo(cli.para) == 0
    assert cli.delete(f"{B}/invoices/{p}/revisao/linhas/{lid}", headers=hg).status_code == 200
    assert saldo(cli.para) == 0 and not estoque.a_recontar(conectar()), "devolver volta ao saldo certo"
    # contar a prateleira tira da lista de recontar
    h = entra(cli)
    linha(cli, h, origem="estoque", item_id=cli.para)
    assert faturar(cli).status_code == 200 and estoque.a_recontar(conectar())
    estoque.contar(conectar(), cli.para, 3)
    assert not estoque.a_recontar(conectar())
