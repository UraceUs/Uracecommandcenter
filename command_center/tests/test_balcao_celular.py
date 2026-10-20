"""Balcão no celular (dono, 20/10): cliente primeiro, COBRAR/GUARDAR, o campo da peça e o pop-up da peça nova.

*"não tem aquela peça no sistema. Quando for aí, abre o pop-up para poder registrar a peça. Quando salvar a peça
registrada, já adiciona no cliente"* e *"mostra o que está guardando para poder confirmar naquele cliente … lá embaixo
um botãozinho de confirmar"*. Dados fictícios.
"""
from command_center.db import conectar, todos, um
from command_center.providers import estoque
from command_center.tests.test_balcao_rascunho import B, cli, entra  # noqa: F401 — o fixture do rascunho

__all__ = ["cli"]


def test_peca_nova_no_guardar_entra_na_lista_e_o_confirmar_poe_no_estoque_do_cliente(cli):  # noqa: F811
    h = entra(cli)
    r = cli.post(f"{B}/peca-nova", json={"client_id": cli.leo, "modo": "guardar", "nome": "Seat strut (teste)",
                                         "category": None, "codigo": "5550001234"}, headers=h)
    assert r.status_code == 201, r.text
    item = r.json()["item"]["id"]
    assert [x["nome"] for x in r.json()["guardando"]] == ["Seat strut (teste)"]
    assert estoque.saldo(conectar(), item, client_id=cli.leo) == 0, "pendente: ainda não está no estoque"
    # a segunda peça, já conhecida, pela lista; e o código da etiqueta já identifica a nova
    assert cli.get(f"{B}/ler", params={"codigo": "5550001234"}, headers=h).json()["item"]["id"] == item
    r = cli.post(f"{B}/cliente/{cli.leo}/guardando", json={"item_id": cli.para, "qty": 2}, headers=h)
    assert r.status_code == 201 and len(r.json()["guardando"]) == 2
    # o card de outro não vê nem confirma a lista deste
    assert cli.get(f"{B}/cliente/{cli.outro}/guardando", headers=h).json()["guardando"] == []
    lid = r.json()["guardando"][1]["id"]
    assert cli.patch(f"{B}/cliente/{cli.outro}/guardando/{lid}", json={"qty": 9}, headers=h).status_code == 404
    assert cli.post(f"{B}/cliente/{cli.outro}/guardando/confirmar", headers=h).status_code == 400
    r = cli.post(f"{B}/cliente/{cli.leo}/guardando/confirmar", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["guardadas"] == 2 and r.json()["guardando"] == []
    assert {g["name"]: g["qty"] for g in r.json()["guardado"]} == {"Seat strut (teste)": 1, "Front bumper (teste)": 2}
    con = conectar()
    assert estoque.saldo(con, cli.para, client_id=cli.outro) == 0
    eventos = [a["event"] for a in todos(con, "SELECT event FROM audit_logs")]
    assert "balcao.peca_nova" in eventos and eventos.count("balcao.guardar") == 2
    assert um(con, "SELECT COUNT(*) AS n FROM counter_scans WHERE client_id=? AND mode='guardar'", (cli.leo,))["n"] == 2


def test_peca_nova_no_cobrar_ja_entra_no_rascunho_do_cliente_com_o_preco_marcado(cli):  # noqa: F811
    h = entra(cli)
    r = cli.post(f"{B}/peca-nova", json={"client_id": cli.leo, "modo": "cobrar", "nome": "Brake pad (teste)",
                                         "price": 42}, headers=h)
    assert r.status_code == 201, r.text
    ls = r.json()["rascunho"]["linhas"]
    assert [(x["nome"], x["preco"], x["preco_digitado"]) for x in ls] == [("Brake pad (teste)", 42, True)], \
        "o preço do mecânico vale para a linha e fica marcado"
    assert estoque.item(conectar(), r.json()["item"]["id"])["price"] is None, "o preço final da peça é do gerente"
    # o gerente: o preço vira o da peça e a linha não fica marcada; o item do QuickBooks nasce no Criar invoice
    hg = entra(cli, "ger@urace.us")
    r = cli.post(f"{B}/peca-nova", json={"client_id": cli.leo, "modo": "cobrar", "nome": "Chain guard (teste)",
                                         "price": 15}, headers=hg)
    assert r.status_code == 201, r.text
    assert [x["preco_digitado"] for x in r.json()["rascunho"]["linhas"]] == [True, False]
    assert cli.post(f"{B}/cliente/{cli.leo}/rascunho/faturar", headers=hg).status_code == 200
    assert sorted(c[1] for c in cli.qbo.chamadas if c[0] == "item") == ["Brake pad (teste)", "Chain guard (teste)"]
