"""Piloto pro marca pelo pacote (#340): contador para o cliente, só o serviço do plano, vários dias e a invoice das
extras e dos add-ons na hora da marcação.

Dono, 19/10: *"verifica para mim como esta a marcação dos pilotos pro, ela deve ser diferente pois eles ja pagam
mensal, entao precisa mostrar tanto para nos quanto para eles a quantidade de sessões que eles tem pagas ou em
aberto, e nao cobrar na marcação e sim na invoice pelo QuickBooks"* — *"se ele selecionar mais do que ele tem paga
ja gerar a invoice e enviar das sessões a mais"* — *"deixe os add ons disponiveis tb"* — e, sobre a mensalidade em
aberto: *"pode"* (marcar continua liberado).

O que estes testes trancam: o card pro sem mensalidade vai para Precisa de atenção, nunca para o carrinho e nunca é
cobrado pelo preço da tabela; o GET /plan manda o contador (usadas, livres, mensalidade do mês, extras, em aberto); o
em aberto conta a extra feita e não paga, a sessão do pacote feita num mês com a mensalidade aberta, e zera com tudo
pago; o recorrente vê só o serviço do kart do plano; o pedido com extras cria UMA invoice na hora com o valor certo
e não cria outra na rodada seguinte (a requestid é a mesma); pedido só do pacote não cria invoice; o add-on vai na
invoice do pedido (sozinho, ou junto com a extra). Dados fictícios (@example.com, nomes inventados)."""
import os
from datetime import timedelta

import pytest

os.environ["URACE_ENV"] = "/nao/existe"

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api import atencao, portal as api_portal  # noqa: E402
from command_center.api.main import app  # noqa: E402
from command_center.db import aplicar_schema, conectar, inserir, todos, um  # noqa: E402
from command_center.providers import agenda_sessoes as ag  # noqa: E402
from command_center.providers import carrinho, cobranca_agenda as cob, contrato, mensalidades  # noqa: E402
from command_center.tests.dados_portal import ENDERECO, piloto  # noqa: E402
from command_center.tests.test_agenda_sessoes import abre, proximo  # noqa: E402

P = "/ops/api/portal"
CONTA = {"name": "Nina Pista", "email": "nina.pista@example.com", "password": "corrida-segura-9", "birth_date": "1984-03-03",
         "accept_terms": True, **ENDERECO}


class Qbo:
    """O QuickBooks de mentira: guarda cada chamada; a mesma requestid devolve a mesma invoice (como o de verdade)."""
    def __init__(self):
        self.chamadas, self.por_req = [], {}

    def __call__(self, **kw):
        self.chamadas.append(kw)
        if kw.get("requestid") in self.por_req:
            return self.por_req[kw["requestid"]]
        n = len(self.por_req) + 1
        r = {"id": f"70{n}", "numero": f"URACE-70{n}", "total": round(sum(x["unitario"] for x in kw["linhas"]), 2),
             "link": f"https://qbo.test/inv/70{n}", "link_pagamento": f"https://connect.intuit.com/pay/70{n}", "enviado": True,
             "enviado_para": kw["email"]}
        self.por_req[kw.get("requestid")] = r
        return r


def _mes(n=0):
    h = ag._agora_fl().date()
    t = h.year * 12 + h.month - 1 + n
    return f"{t // 12:04d}-{t % 12 + 1:02d}"


@pytest.fixture()
def amb(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path))
    c = conectar(); aplicar_schema(c)
    inserir(c, "qbo_items", id="892", name="Academy | Extra session (beyond monthly 4)", price=689)
    inserir(c, "qbo_items", id="77", name="Lead and Follow", price=769)
    c.execute("UPDATE booking_services SET qbo_item_id='77' WHERE kind='addon'")
    abre(c, cap=2)
    c.commit(); c.close()
    qbo = Qbo()
    monkeypatch.setattr(cob, "_enviar_padrao", qbo)
    monkeypatch.setattr(mensalidades, "_cliente_qbo", lambda con, cid: "42")
    with TestClient(app, base_url="https://cc.test") as t:
        assert t.post(f"{P}/signup", json=CONTA).status_code == 201
        h = {"X-CSRF": t.cookies.get("cp_csrf")}
        pid = t.post(f"{P}/drivers", headers=h, json=piloto("Theo Pista")).json()["drivers"][0]["id"]
        c = conectar()
        card = inserir(c, "clients", name="Nina Pista", pilot_name="Theo Pista", email="nina.pista@example.com", status="ACTIVE",
                       pro_driver=1)
        c.execute("UPDATE portal_pilots SET client_id=? WHERE id=?", (card, pid))
        c.commit()
        quatro = um(c, "SELECT id FROM booking_services WHERE site_kart='4-stroke'")["id"]
        yield {"cli": t, "h": h, "con": c, "pid": pid, "card": card, "qbo": qbo, "quatro": quatro}
        c.close()


def mensal(a, sessoes=2, valor=1378.45, plano="Academy 4 stroke"):
    """A equipe preenche a Mensalidade do card (números fictícios do teste)."""
    a["con"].execute("UPDATE clients SET monthly_sessions=?, monthly_amount=?, monthly_plan=? WHERE id=?", (sessoes, valor, plano, a["card"]))
    a["con"].commit()


def quartas(n, a_partir=3):
    d = proximo(2, a_partir)
    return [(d + timedelta(days=7 * i)).isoformat() for i in range(n)]


def do_mesmo_mes(n):
    """n quartas do mesmo mês (o pacote é por mês)."""
    for a in range(3, 60, 7):
        ds = quartas(n, a)
        if len({d[:7] for d in ds}) == 1:
            return ds
    raise AssertionError("sem quartas no mesmo mês")


def pedir(a, dias, addon=(), servico=None):
    slots = [{"date": d, "period": "manha", **({"addon": True} if d in addon else {})} for d in dias]
    corpo = {"service_id": servico or a["quatro"], "driver_id": a["pid"], "slots": slots}
    q = a["cli"].post(f"{P}/bookings/quote", headers=a["h"], json=corpo)
    assert q.status_code == 200, q.text
    r = a["cli"].post(f"{P}/bookings/batch", headers=a["h"], json={**corpo, "quote": q.json()["hash"]})
    assert r.status_code == 201, r.text
    return q.json(), r.json()


# ------------------------------------------------------------------ o pro sem mensalidade no card
def test_pro_sem_mensal_vai_para_atencao_nunca_para_o_carrinho_e_nao_cobra_pela_tabela(amb, monkeypatch):
    con, cli = amb["con"], amb["cli"]
    itens = [x for x in atencao.coletar(con) if x["key"] == f"pro-sem-mensal:client:{amb['card']}"]
    assert len(itens) == 1 and itens[0]["client_id"] == amb["card"]
    assert itens[0]["title"].startswith("Piloto pro sem mensalidade no card: preencha sessões por mês e valor mensal")
    monkeypatch.setattr(api_portal, "carrinho_ligado", lambda request: True)          # o Stripe está ligado
    r = cli.get(f"{P}/plan").json()
    p = r["drivers"][0]
    assert r["cart"] is True and p["payment"] == "equipe" and p["setup"] is True and p["recurring"] is False, \
        "o pro em montagem nunca vai para o carrinho"
    # a equipe aceita: nenhuma invoice sai pelo preço da tabela; fica escrito o que fazer
    dia = quartas(1)[0]
    bid = cli.post(f"{P}/bookings", headers=amb["h"], json={"date": dia, "period": "manha", "service_id": amb["quatro"],
                                                             "driver_id": amb["pid"]}).json()["id"]
    cob.aceitar(con, 1, bid, enviar_waiver=lambda *a: {"envelopeId": "e"})
    b = um(con, "SELECT * FROM bookings WHERE id=?", (bid,))
    assert not amb["qbo"].chamadas and b["qbo_invoice_id"] is None and b["charge_kind"] is None
    assert "piloto pro sem mensalidade" in b["charge_error"]
    # preenchida a Mensalidade, some da atenção e a rodada aloca no pacote, sem invoice
    mensal(amb)
    assert not [x for x in atencao.coletar(con) if x["key"].startswith("pro-sem-mensal:")]
    cob.rodar(con, enviar_waiver=lambda *a: {"envelopeId": "e"}, enviar_email=lambda *a: None)
    b = um(con, "SELECT * FROM bookings WHERE id=?", (bid,))
    assert (b["coverage"], b["charge_kind"]) == ("plano", "contrato") and not amb["qbo"].chamadas


def test_carrinho_recusa_a_sessao_do_piloto_pro(amb):
    con = amb["con"]
    conta = um(con, "SELECT account_id FROM portal_pilots WHERE id=?", (amb["pid"],))["account_id"]
    c = carrinho.cotar(con, [{"tipo": "sessao", "servico": amb["quatro"], "data": quartas(1)[0], "turno": "manha",
                              "piloto": amb["pid"]}], conta_id=conta, para_pagar=True)
    erro = next(x for x in c["linhas"] if x["tipo"] == "sessao")["erro"]
    assert erro and "Pro driver" in erro and "Remove it from the cart" in erro


# ------------------------------------------------------------------ o contador para o cliente
def test_plan_manda_o_contador_e_a_mensalidade_do_mes(amb):
    con, cli = amb["con"], amb["cli"]
    mensal(amb)
    m = _mes()
    p = cli.get(f"{P}/plan").json()["drivers"][0]
    k = p["counter"]
    assert (k["used"], k["sessions_per_month"], k["left"], k["month"]) == (0, 2, 2, m)
    assert k["monthly_invoice"] is None, "sem invoice do mês: '—' (nada inventado)"
    assert k["resets_on"] == f"{_mes(1)}-01"
    # a invoice de mensalidade do mês chega no espelho do QuickBooks, aberta
    nome = mensalidades.MESES_EN[int(m[5:7]) - 1]
    iid = inserir(con, "invoices", client_id=amb["card"], doc_number="URACE-5001", amount=1378.45, balance=1378.45, status="open",
                  issued_on=f"{m}-01", memo=f"Urace Academy Training Program [{nome}, {m[:4]}]")
    con.execute("INSERT INTO entity_links (entity_type, entity_id, system, external_id) VALUES ('invoice', ?, 'quickbooks', '5001')", (iid,))
    con.commit()
    k = cli.get(f"{P}/plan").json()["drivers"][0]["counter"]
    assert k["monthly_invoice"]["status"] == "open" and k["monthly_invoice"]["doc"] == "URACE-5001"
    con.execute("UPDATE invoices SET balance=0, status='paid' WHERE id=?", (iid,))
    con.commit()
    assert cli.get(f"{P}/plan").json()["drivers"][0]["counter"]["monthly_invoice"]["status"] == "paid"
    # marcar continua liberado com a mensalidade aberta (dono, 19/10: "pode")
    con.execute("UPDATE invoices SET balance=1378.45, status='open' WHERE id=?", (iid,))
    con.commit()
    pedir(amb, [quartas(1)[0]])
    assert len(todos(con, "SELECT id FROM bookings")) == 1


def _sessao(con, a, dia, **mais):
    conta = um(con, "SELECT account_id FROM portal_pilots WHERE id=?", (a["pid"],))["account_id"]
    return inserir(con, "bookings", account_id=conta, pilot_id=a["pid"], date=dia, period="manha", status="confirmada",
                   service_name="Arrive and Drive 4-stroke", **mais)


def _invoice(con, a, doc, ext, saldo, mes=None, memo=None):
    iid = inserir(con, "invoices", client_id=a["card"], doc_number=doc, amount=689.23 if not memo else 1378.45, balance=saldo,
                  status="paid" if not saldo else "open", issued_on=f"{mes or _mes(-1)}-02", memo=memo)
    con.execute("INSERT INTO entity_links (entity_type, entity_id, system, external_id) VALUES ('invoice', ?, 'quickbooks', ?)", (iid, ext))
    return iid


def test_em_aberto_extra_feita_e_nao_paga_mes_com_mensalidade_aberta_e_tudo_pago(amb):
    con = amb["con"]
    mensal(amb)
    m = _mes(-1)                                                        # o mês passado: as sessões já foram feitas
    nome = mensalidades.MESES_EN[int(m[5:7]) - 1]
    _sessao(con, amb, f"{m}-03", coverage="plano", charge_kind="contrato", price=0)
    _sessao(con, amb, f"{m}-10", coverage="plano", charge_kind="contrato", price=0)
    _sessao(con, amb, f"{m}-17", coverage="extra", charge_kind="invoice", price=689.23, qbo_invoice_id="801",
            invoice_doc="URACE-801", invoice_total=689.23)
    mens = _invoice(con, amb, "URACE-800", "800", 1378.45, m, f"Urace Academy Training Program [{nome}, {m[:4]}]")
    _invoice(con, amb, "URACE-801", "801", 689.23)
    a = contrato.em_aberto(con, amb["card"])
    assert a["count"] == 3, "2 do pacote (mensalidade aberta) + a extra não paga"
    assert a["amount"] == 2067.68, "o saldo das duas invoices abertas, cada uma uma vez"
    assert {(x["kind"], x["invoice"]) for x in a["sessions"]} == {("plano", "URACE-800"), ("extra", "URACE-801")}
    assert len(a["invoices"]) == 2 and a["not_invoiced"] == 0
    # a mensalidade paga: fica só a extra
    con.execute("UPDATE invoices SET balance=0, status='paid' WHERE id=?", (mens,))
    a = contrato.em_aberto(con, amb["card"])
    assert (a["count"], a["amount"]) == (1, 689.23) and a["sessions"][0]["kind"] == "extra"
    # tudo pago: nada em aberto
    con.execute("UPDATE bookings SET paid_at='2026-01-01T00:00:00Z' WHERE qbo_invoice_id='801'")
    a = contrato.em_aberto(con, amb["card"])
    assert (a["count"], a["amount"], a["not_invoiced"]) == (0, None, 0)
    # a invoice da extra (com o item "Academy | Extra session") nunca é a mensalidade
    por_mes, _ = contrato.mensalidades_por_mes(con, amb["card"])
    assert por_mes[m]["doc_number"] == "URACE-800"


def test_em_aberto_sem_invoice_conta_sem_inventar_valor(amb):
    con = amb["con"]
    mensal(amb)
    _sessao(con, amb, f"{_mes(-1)}-05", coverage="plano", charge_kind="contrato", price=0)
    a = contrato.em_aberto(con, amb["card"])
    assert (a["count"], a["not_invoiced"], a["amount"]) == (1, 1, None), "not invoiced yet, sem valor"
    k = amb["cli"].get(f"{P}/plan").json()["drivers"][0]["counter"]
    assert k["open"] == {"count": 1, "amount": None, "not_invoiced": 1}
    assert "sessions" not in k["open"], "a lista de quais sessões é da equipe"


def test_equipe_ve_o_contador_no_card(amb, monkeypatch):
    from command_center.api import auth
    mensal(amb)
    app.dependency_overrides[auth.usuario_atual] = lambda: {"id": 1, "role": "OWNER", "name": "Dono"}
    try:
        r = amb["cli"].get(f"/ops/api/clients/{amb['card']}/monthly").json()
    finally:
        app.dependency_overrides.clear()
    assert r["counter"]["sessions_per_month"] == 2 and "sessions" in r["counter"]["open"] and r["pro_sem_mensal"] is False


# ------------------------------------------------------------------ só o serviço do plano
def test_recorrente_ve_so_o_servico_do_kart_do_plano(amb):
    mensal(amb, plano="Academy 4 stroke")
    p = amb["cli"].get(f"{P}/plan").json()["drivers"][0]
    assert p["services"] == [amb["quatro"]] and p["services_matched"] is True
    assert p["addon"]["name"] == "Lead and Follow" and p["addon"]["price"] == 769.0
    outro = um(amb["con"], "SELECT id FROM booking_services WHERE site_kart='2-stroke'")["id"]
    q = amb["cli"].post(f"{P}/bookings/quote", headers=amb["h"], json={"service_id": outro, "driver_id": amb["pid"],
                                                                        "slots": [{"date": quartas(1)[0], "period": "manha"}]}).json()
    assert q["slots"][0]["reason"] == "fora_do_plano" and "not in your monthly plan" in q["slots"][0]["message"]
    # o plano sem kart (ex.: "Contrato 12 meses"): todos, como antes
    mensal(amb, plano="Contrato 12 meses")
    p = amb["cli"].get(f"{P}/plan").json()["drivers"][0]
    assert p["services_matched"] is False and len(p["services"]) == 5


# ------------------------------------------------------------------ a invoice na hora da marcação
def test_pedido_com_extras_cria_uma_invoice_na_hora_e_nao_cria_de_novo(amb):
    con = amb["con"]
    mensal(amb, sessoes=2, valor=1378.45)
    dias = do_mesmo_mes(4)
    q, r = pedir(amb, dias)
    assert (q["included"], q["extras"], q["invoice_total"]) == (2, 2, 1378.46), "2 do pacote + 2 extras de 689,23"
    ch = amb["qbo"].chamadas
    assert len(ch) == 1, "uma invoice só, na hora da marcação (sem a equipe aceitar)"
    assert [x["item_id"] for x in ch[0]["linhas"]] == ["892", "892"] and [x["unitario"] for x in ch[0]["linhas"]] == [689.23, 689.23]
    assert all("deposit" not in x["descricao"].lower() for x in ch[0]["linhas"]), "sem depósito"
    bs = todos(con, "SELECT * FROM bookings WHERE group_id=? ORDER BY date", (r["group_id"],))
    assert all(b["accepted_at"] is None for b in bs), "não esperou a equipe"
    assert {b["qbo_invoice_id"] for b in bs if b["coverage"] == "extra"} == {"701"}
    assert {b["qbo_invoice_id"] for b in bs if b["coverage"] == "plano"} == {None}
    # a rodada seguinte não cobra de novo; o aceite também não
    cob.rodar(con, enviar_waiver=lambda *a: {"envelopeId": "e"}, enviar_email=lambda *a: None)
    cob.aceitar(con, 1, bs[0]["id"], enviar_waiver=lambda *a: {"envelopeId": "e"})
    assert len(ch) == 1


def test_falha_do_quickbooks_fica_escrita_e_a_rodada_repete_a_mesma_requestid(amb, monkeypatch):
    con = amb["con"]
    mensal(amb, sessoes=1)
    chamadas = []

    def caiu(**kw):
        chamadas.append(kw)
        raise RuntimeError("tempo esgotado")
    monkeypatch.setattr(cob, "_enviar_padrao", caiu)
    _, r = pedir(amb, do_mesmo_mes(2))
    b = um(con, "SELECT * FROM bookings WHERE group_id=? AND coverage='extra'", (r["group_id"],))
    assert "tempo esgotado" in b["charge_error"] and b["qbo_invoice_id"] is None
    qbo = amb["qbo"]
    cob.rodar(con, enviar_invoice=qbo, enviar_waiver=lambda *a: {"envelopeId": "e"}, enviar_email=lambda *a: None)
    assert len(qbo.chamadas) == 1 and qbo.chamadas[0]["requestid"] == chamadas[0]["requestid"], \
        "a mesma cobrança, a mesma requestid: o QuickBooks não cria a segunda"
    assert um(con, "SELECT qbo_invoice_id FROM bookings WHERE id=?", (b["id"],))["qbo_invoice_id"] == "701"


def test_pedido_so_do_pacote_nao_cria_invoice(amb):
    mensal(amb, sessoes=4)
    q, r = pedir(amb, do_mesmo_mes(2))
    assert (q["included"], q["extras"], q["invoice_total"]) == (2, 0, 0.0)
    assert not amb["qbo"].chamadas
    cob.rodar(amb["con"], enviar_waiver=lambda *a: {"envelopeId": "e"}, enviar_email=lambda *a: None)
    assert not amb["qbo"].chamadas


def test_pacote_com_add_on_cria_invoice_so_do_add_on(amb):
    con = amb["con"]
    mensal(amb, sessoes=4)
    dias = do_mesmo_mes(2)
    q, r = pedir(amb, dias, addon={dias[0]})
    assert (q["included"], q["extras"], q["addons"], q["invoice_total"]) == (2, 0, 1, 769.0)
    ch = amb["qbo"].chamadas
    assert len(ch) == 1 and [(x["item_id"], x["unitario"]) for x in ch[0]["linhas"]] == [("77", 769.0)]
    b = um(con, "SELECT * FROM bookings WHERE group_id=? AND date=?", (r["group_id"], dias[0]))
    assert (b["coverage"], b["addon_name"], b["qbo_invoice_id"]) == ("plano", "Lead and Follow", "701")
    cob.aceitar(con, 1, b["id"], enviar_waiver=lambda *a: {"envelopeId": "e"})
    b = um(con, "SELECT * FROM bookings WHERE id=?", (b["id"],))
    assert b["charge_kind"] == "contrato" and len(ch) == 1, "a sessão continua do pacote; nada cobrado de novo"


def test_extra_com_add_on_vai_numa_invoice_com_os_dois(amb):
    mensal(amb, sessoes=1)
    dias = do_mesmo_mes(2)
    q, _ = pedir(amb, dias, addon={dias[1]})
    assert (q["included"], q["extras"], q["addons"]) == (1, 1, 1)
    ch = amb["qbo"].chamadas
    assert len(ch) == 1
    assert sorted((x["item_id"], x["unitario"]) for x in ch[0]["linhas"]) == [("77", 769.0), ("892", 1378.45)]
    assert ch[0]["memo"].startswith("URACE extra session and add-on")


def test_contador_e_em_aberto_nao_misturam_o_card_do_irmao(amb):
    """Cada piloto tem o seu card (#65): a sessão e a invoice do irmão, na mesma conta, nunca entram no contador."""
    con = amb["con"]
    mensal(amb)
    conta = um(con, "SELECT account_id FROM portal_pilots WHERE id=?", (amb["pid"],))["account_id"]
    irmao = inserir(con, "clients", name="Nina Pista", pilot_name="Lia Pista", email="lia.pista@example.com", status="ACTIVE",
                    monthly_sessions=2, monthly_amount=1378.45)
    pid2 = inserir(con, "portal_pilots", account_id=conta, name="Lia Pista", client_id=irmao)
    m = _mes(-1)
    inserir(con, "bookings", account_id=conta, pilot_id=pid2, date=f"{m}-04", period="manha", status="confirmada",
            coverage="extra", charge_kind="invoice", price=689.23, qbo_invoice_id="901", invoice_doc="URACE-901", invoice_total=689.23)
    # #451: "ainda não feita" é hoje (na Flórida), sempre no mês corrente; o dia 28 fixo já tinha passado do 29 ao 31
    inserir(con, "bookings", account_id=conta, pilot_id=pid2, date=ag._agora_fl().date().isoformat(), period="manha",
            status="pendente", coverage="plano", price=0)
    a = contrato.em_aberto(con, amb["card"])
    assert a["count"] == 0 and not a["invoices"], "a extra do irmão não é do card do Theo"
    k = contrato.contador(con, amb["card"])
    assert (k["used"], k["extras"]) == (0, []), "a do pacote do irmão não ocupa a vaga do Theo"
    assert contrato.em_aberto(con, irmao)["count"] == 1 and contrato.contador(con, irmao)["used"] == 1


# ------------------------------------------------------------------ "Training Day X/Y" (#355)
def test_recorrente_marca_training_day_numerado_e_o_nome_fica_no_agendamento(amb):
    """Dono, 20/10: "será training day sendo 1/4, sendo o X/4 a sessão atual da mensalidade vigente". 4 por mês e 1
    usada: a próxima é 2/4; um pedido de 4 dias no mês vira 2/4, 3/4, 4/4 e uma extra."""
    con = amb["con"]
    mensal(amb, sessoes=4, valor=2756.90)
    dias = do_mesmo_mes(4)
    mes = dias[0][:7]
    _sessao(con, amb, f"{mes}-01", coverage="plano", charge_kind="contrato", price=0)
    from command_center.providers import agenda_lote
    assert agenda_lote.proximo_titulo(con, amb["card"], mes) == "Training Day 2/4"
    if mes == _mes():
        assert amb["cli"].get(f"{P}/plan").json()["drivers"][0]["training_day"] == "Training Day 2/4"
    q, r = pedir(amb, dias)
    assert [x["title"] for x in sorted(q["slots"], key=lambda y: y["date"])] == \
        ["Training Day 2/4", "Training Day 3/4", "Training Day 4/4", "Training Day · extra $689.23"]
    nomes = [b["service_name"] for b in todos(con, "SELECT service_name FROM bookings WHERE group_id=? ORDER BY date", (r["group_id"],))]
    assert nomes == ["Training Day 2/4", "Training Day 3/4", "Training Day 4/4", "Training Day · extra $689.23"], \
        "o nome vai para Agendamentos, Asana e e-mails"


def test_pro_sem_mensal_marca_training_day_sem_numero(amb):
    p = amb["cli"].get(f"{P}/plan").json()["drivers"][0]
    assert p["setup"] is True and p["training_day"] == "Training Day", "sem a Mensalidade, nenhum número inventado"
    r = amb["cli"].post(f"{P}/bookings", headers=amb["h"], json={"date": quartas(1)[0], "period": "manha",
                                                                  "service_id": amb["quatro"], "driver_id": amb["pid"]})
    assert r.status_code == 201, r.text
    assert um(amb["con"], "SELECT service_name FROM bookings WHERE id=?", (r.json()["id"],))["service_name"] == "Training Day"
    r = amb["cli"].post(f"{P}/bookings", headers=amb["h"], json={"date": quartas(2)[1], "period": "manha", "avulsa": True,
                                                                  "service_id": amb["quatro"], "driver_id": amb["pid"]})
    assert um(amb["con"], "SELECT service_name FROM bookings WHERE id=?", (r.json()["id"],))["service_name"] == \
        "Arrive and Drive 4-stroke", "a avulsa fica com o nome do serviço"
