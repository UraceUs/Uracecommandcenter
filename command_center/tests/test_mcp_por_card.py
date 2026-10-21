"""Consultas do MCP por card (#363).

Dono, 20/10: *"permitir filtrar reservas, pedidos e pagamentos pelo mesmo card, evitando buscar
dados de outros clientes durante um diagnóstico."*

O que estes testes trancam: com dois cards fictícios, o card Alfa nunca vê nada do card Bravo — nem
quando o pedido do Bravo foi feito com o e-mail do Alfa, nem quando o piloto do Bravo está na conta do
portal do Alfa. A junção é pelo `client_id`, nunca por nome ou e-mail.
"""
import json
import os
import tempfile

import pytest

from command_center.api import mcp_http
from command_center.db import aplicar_schema, conectar, conectar_somente_leitura, inserir

EMAIL_ALFA = "alfa.teste@example.com"


@pytest.fixture(scope="module")
def banco():
    caminho = os.path.join(tempfile.mkdtemp(), "cc.sqlite")
    con = conectar(caminho)
    aplicar_schema(con)
    alfa = inserir(con, "clients", name="Alfa Teste", email=EMAIL_ALFA, phone="407-555-0101", source="manual")
    bravo = inserir(con, "clients", name="Bravo Teste", email="bravo.teste@example.com",
                    phone="407-555-0102", source="manual")
    servico = inserir(con, "booking_services", name="Daily", price=100)
    # A conta do portal é do Alfa; um dos pilotos dela tem o card Bravo (irmão, #65).
    conta = inserir(con, "portal_accounts", email=EMAIL_ALFA, pw_salt="x", pw_hash="x", name="Alfa Teste",
                    birth_date="1980-01-01", terms_accepted_at="2026-10-01", client_id=alfa)
    piloto_bravo = inserir(con, "portal_pilots", account_id=conta, name="Bravo Teste", client_id=bravo)
    inserir(con, "bookings", account_id=conta, date="2026-10-10", period="dia", status="confirmada",
            service_name="Sessao Alfa", price=100, invoice_doc="A-100", qbo_invoice_id="q1")
    inserir(con, "bookings", account_id=conta, pilot_id=piloto_bravo, date="2026-10-11", period="manha",
            status="confirmada", service_name="Sessao Bravo", price=90, invoice_doc="B-100")
    corrida_a = inserir(con, "races", name="Corrida Alfa", track="Pista Teste", date_start="2026-11-01")
    corrida_b = inserir(con, "races", name="Corrida Bravo", track="Pista Teste", date_start="2026-11-02")
    inserir(con, "race_invites", race_id=corrida_a, client_id=alfa, status="confirmed")
    inserir(con, "race_invites", race_id=corrida_b, client_id=bravo, status="invited")

    def pedido(card, nome, email, sessao):
        o = inserir(con, "store_orders", product_slug="x", product_name=nome, quantity=1, unit_price=50,
                    amount=50, delivery="retirada", status="pago", stripe_session_id=f"cs_{nome}",
                    amount_paid=50, email=email, paid_at="2026-10-05", client_id=card)
        inserir(con, "store_order_items", order_id=o, kind="sessao", name=sessao, unit_price=10, amount=10,
                date="2026-10-20", status="sem_vaga", client_id=card)
        inserir(con, "store_deposit_refunds", order_id=o, amount=25, status="feito",
                stripe_refund_id=f"re_{nome}")
        return o
    for i in range(3):
        pedido(alfa, f"Luva Alfa {i}", EMAIL_ALFA, "Sessao carrinho Alfa")
    pedido(bravo, "Luva Bravo", EMAIL_ALFA, "Sessao carrinho Bravo")   # o e-mail do Alfa, o card do Bravo

    for card, nome in ((alfa, "Alfa"), (bravo, "Bravo")):
        inserir(con, "plan_orders", account_id=conta, service_id=servico, service_name=f"Plano {nome}",
                price=400, months=3, start_month="2026-11", client_id=card)
        inserir(con, "suit_orders", title=f"Suit {nome}", client_id=card, customer_email=EMAIL_ALFA)
        inserir(con, "invoices", client_id=card, doc_number=f"INV-{nome}", amount=500, balance=200,
                status="sent", issued_on="2026-10-01")
        inserir(con, "monthly_invoices", client_id=card, month="2026-10", amount=400, item_id="1",
                description=f"Mensal {nome}", send_at="2026-10-01 09:00")
        inserir(con, "parts_invoices", client_id=card, service_date="2026-10-02", doc_number=f"PEC-{nome}")
    con.commit()
    con.close()
    yield {"caminho": caminho, "alfa": alfa, "bravo": bravo}


def chamar(banco, nome, args):
    con = conectar_somente_leitura(banco["caminho"])
    try:
        r = mcp_http.tratar({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                             "params": {"name": nome, "arguments": args}}, con, {"somente_leitura": True})
    finally:
        con.close()
    return r


def dado(banco, nome, args):
    r = chamar(banco, nome, args)
    assert "error" not in r, r
    assert not r["result"]["isError"], r["result"]
    return json.loads(r["result"]["content"][0]["text"])


FERRAMENTAS = ("urace_cliente_reservas", "urace_cliente_pedidos", "urace_cliente_pagamentos")


@pytest.mark.parametrize("nome", FERRAMENTAS)
def test_o_card_alfa_nunca_ve_o_card_bravo(banco, nome):
    for meu, outro, nome_outro in ((banco["alfa"], banco["bravo"], "Bravo"),
                                   (banco["bravo"], banco["alfa"], "Alfa")):
        d = dado(banco, nome, {"client_id": meu, "limit": 100})
        texto = json.dumps(d, ensure_ascii=False)
        assert d["client_id"] == meu and d["total"] > 0
        assert nome_outro not in texto.replace(EMAIL_ALFA, ""), f"{nome}: o card {meu} viu dado do {outro}"


def test_reservas_juntam_agendamento_corrida_e_carrinho_do_card(banco):
    d = dado(banco, "urace_cliente_reservas", {"client_id": banco["alfa"]})
    assert d["por_fonte"] == {"agendamento_site": 1, "corrida": 1, "sessao_do_carrinho": 3}
    agenda = [x for x in d["reservas"] if x["fonte"] == "agendamento_site"]
    assert agenda[0]["descricao"].startswith("Sessao Alfa") and agenda[0]["documento"] == "A-100"
    # o piloto Bravo está na conta do Alfa, mas o agendamento dele é do card Bravo
    b = dado(banco, "urace_cliente_reservas", {"client_id": banco["bravo"]})
    assert [x["descricao"] for x in b["reservas"] if x["fonte"] == "agendamento_site"] == ["Sessao Bravo (manha)"]


def test_pedidos_e_pagamentos_por_fonte(banco):
    p = dado(banco, "urace_cliente_pedidos", {"client_id": banco["alfa"]})
    assert p["por_fonte"] == {"loja": 3, "plano": 1, "suit": 1}
    g = dado(banco, "urace_cliente_pagamentos", {"client_id": banco["alfa"]})
    assert g["por_fonte"] == {"invoice_qbo": 1, "mensalidade": 1, "invoice_pecas": 1, "stripe": 3,
                              "deposito_reembolso": 3}
    assert "stripe_events" in g["fora"], "o que não junta por client_id é dito no retorno"


def test_paginacao_com_limit_offset_e_total(banco):
    um_ = dado(banco, "urace_cliente_pagamentos", {"client_id": banco["alfa"], "limit": 4})
    dois = dado(banco, "urace_cliente_pagamentos", {"client_id": banco["alfa"], "limit": 4, "offset": 4})
    assert um_["total"] == dois["total"] == 9
    assert len(um_["pagamentos"]) == 4 and len(dois["pagamentos"]) == 4 and dois["offset"] == 4
    ids = {(x["fonte"], x["id"]) for x in um_["pagamentos"]} & {(x["fonte"], x["id"]) for x in dois["pagamentos"]}
    assert not ids, "a segunda página repetiu linha da primeira"
    assert dado(banco, "urace_cliente_pedidos", {"client_id": banco["alfa"], "limit": 5000})["limit"] == 100
    assert dado(banco, "urace_cliente_pedidos", {"client_id": banco["alfa"]})["limit"] == 20


def test_client_id_e_obrigatorio(banco):
    for nome in FERRAMENTAS:
        r = chamar(banco, nome, {})
        assert r["error"]["code"] == -32602 and "client_id" in r["error"]["message"]
        r = chamar(banco, nome, {"client_id": 999999})
        assert r["result"]["isError"], "card que não existe volta como erro legível"


def test_invoices_e_corridas_aceitam_client_id(banco):
    d = dado(banco, "urace_invoices", {"client_id": banco["alfa"]})
    assert [i["doc_number"] for i in d["invoices"]] == ["INV-Alfa"] and d["total_em_aberto"] == 200
    assert len(dado(banco, "urace_invoices", {})["invoices"]) == 2, "sem client_id, continua tudo"
    c = dado(banco, "urace_corridas", {"client_id": banco["bravo"]})
    assert [x["name"] for x in c["corridas"]] == ["Corrida Bravo"] and c["corridas"][0]["convite"] == "invited"


def test_instrucoes_falam_da_consulta_por_card():
    texto = mcp_http._instrucoes({"somente_leitura": True})
    assert "Comece por urace_resumo" in texto
    for nome in FERRAMENTAS:
        assert nome in texto


# ------------------------------------------- cada linha diz de que card é (#372)
@pytest.mark.parametrize("nome", FERRAMENTAS)
def test_cada_linha_traz_o_client_id_do_card_e_quando_mudou(banco, nome):
    """Dono, 21/10 (validação do Mio): "como verificar que todas as linhas pertencem ao card
    solicitado". Cada linha traz o card que o banco ligou a ela; quem lê confere uma por uma."""
    for card in (banco["alfa"], banco["bravo"]):
        d = dado(banco, nome, {"client_id": card, "limit": 100})
        linhas = d[d["tipo"]]
        assert linhas and len(linhas) == d["total"]
        assert all(x["client_id"] == card for x in linhas), linhas
        assert all("atualizado_em" in x for x in linhas)
        assert all(x["atualizado_em"] for x in linhas if x["fonte"] != "invoice_qbo")


def test_a_versao_do_servidor_e_o_commit_implantado():
    """O ChatGPT guarda o catálogo; com a versão fixa em 1.0.0 nada dizia que ele mudou (#372)."""
    r = mcp_http.tratar({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}, None,
                        {"somente_leitura": True})
    versao = r["result"]["serverInfo"]["version"]
    assert versao != "1.0.0"
    if mcp_http.COMMIT:
        assert versao.endswith("+" + mcp_http.COMMIT)


# ------------------------------- invoices e corridas paginadas; resumo com versão e sincronia (#374)
def test_invoices_e_corridas_paginam_e_dizem_o_card_de_cada_linha(banco):
    """Validação do Mio, 21/10: "Invoices e corridas: listas vazias, sem total/limit/offset"."""
    for card in (banco["alfa"], banco["bravo"]):
        inv = dado(banco, "urace_invoices", {"client_id": card})
        assert (inv["total"], inv["limit"], inv["offset"]) == (1, 80, 0)
        assert all(i["client_id"] == card for i in inv["invoices"])
        cor = dado(banco, "urace_corridas", {"client_id": card})
        assert (cor["client_id"], cor["total"], cor["offset"]) == (card, 1, 0)
        assert all(x["client_id"] == card for x in cor["corridas"])
    pag = dado(banco, "urace_invoices", {"limit": 1, "offset": 1})
    assert pag["total"] == 2 and len(pag["invoices"]) == 1 and pag["limit"] == 1
    assert dado(banco, "urace_corridas", {"limite": 1})["limit"] == 1, "o nome antigo continua valendo"


def test_resumo_traz_a_versao_do_servidor_e_a_ultima_sincronia(banco):
    r = dado(banco, "urace_resumo", {})
    assert r["servidor"]["versao"] == mcp_http.VERSAO and "commit" in r["servidor"]
    assert isinstance(r["sincronia"], list)
    assert all({"sistema", "status", "ultima_ok", "ultima_tentativa"} <= set(x) for x in r["sincronia"])
