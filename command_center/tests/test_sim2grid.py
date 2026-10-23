"""#392 — SIM2GRID: a LP como página do site e a hora de simulador como serviço próprio.

Dono, 22/10: *"na pagina do sim2grid eu preciso replicar essa lp ... ali dentro sera um serviço um diferente das aulas
de kart podendo agendar ate 5 pessoas para a mesma hora, o valor do serviço é cobrado por hora. monte assim como montou
o arrive and drive com todas as configurações ajustaveis"*.

O que estes testes trancam:
- a semente: dois formatos (sem coach, com coach), as faixas da LP, 5 simuladores e os 3 programas, **uma vez**;
- o preço é a soma das horas pela faixa de cada uma, por formato (coach ou não); faixa sem preço é "ligue";
- a capacidade: até 5 pessoas na mesma hora (ajustável), contando o carrinho, as pagas e as seguradas no Stripe;
- o calendário público mostra as vagas que sobram em cada hora;
- reserva → checkout (o horário fica segurado) → pago (vira reserva paga no card do piloto, venda GANHO);
- a página: texto da LP, SEO (canonical, título, um h1, JSON-LD com preço por hora), sitemap e os links do site;
- o painel muda tudo (regras e faixas) sem código, e a página e o carrinho seguem na hora.
Nada fala com o Stripe, o DocuSign ou o QuickBooks de verdade. Nomes e e-mails fictícios."""
import json
import re
from datetime import date, datetime, timedelta

import pytest

from command_center.db import aplicar_schema, inserir, todos, um
from command_center.providers import carrinho, sim2grid
from command_center.providers.agenda_sessoes import FUSO
from command_center.tests.test_carrinho import _checkout, _entrar, _pagar
from command_center.tests.test_stripe_loja import _emails, amb  # noqa: F401
from command_center.tests.test_vitrine import _le
from command_center.vitrine import conteudo_sim2grid as SG

CAMINHO = "/sim2grid-racing-simulator/"


def dia(semana, a_partir=3):
    """Uma data futura naquele dia da semana (0 = segunda), dentro do horizonte."""
    d = datetime.now(FUSO).date() + timedelta(days=a_partir)
    while d.weekday() != semana:
        d += timedelta(days=1)
    return d


@pytest.fixture()
def sim(amb):  # noqa: F811
    cli, con, st, qbo, tmp = amb
    # a abertura de 01/11/2026 é regra do painel; aqui o teste não depende do dia em que roda
    sim2grid.mudar_config(con, None, {"open_from": ""})
    con.commit()
    solo = um(con, "SELECT id FROM booking_services WHERE site_kart='sim2grid-solo'")["id"]
    coach = um(con, "SELECT id FROM booking_services WHERE site_kart='sim2grid-coach'")["id"]
    return cli, con, st, qbo, tmp, solo, coach


def _item(sid, d, hora, horas=1, piloto=None, **extra):
    return {"tipo": "sessao", "servico": sid, "data": d.isoformat(), "hora": hora, "horas": horas, "piloto": piloto, **extra}


def _cotar(cli, itens):
    r = cli.post("/ops/api/vitrine/carrinho", json={"itens": itens})
    assert r.status_code == 200, r.text
    return r.json()


def _hora(cli, d, h):
    j = cli.get("/ops/api/vitrine/sim2grid").json()
    x = next((x for x in j["dias"] if x["date"] == d.isoformat()), None)
    return next((y for y in x["hours"] if y["h"] == h), None) if x else None


# ------------------------------------------------------------------ a semente
def test_a_semente_da_lp_entra_uma_vez_e_o_que_a_equipe_muda_fica(sim):
    cli, con, st, qbo, tmp, solo, coach = sim
    forms = todos(con, "SELECT * FROM booking_services WHERE kind='sim' ORDER BY sort")
    assert [(f["site_kart"], f["deposit"], f["active"]) for f in forms] == [("sim2grid-solo", 0, 1), ("sim2grid-coach", 0, 1)]
    fs = {(f["service_id"], f["days"], f["start_hour"], f["end_hour"]): f["price"] for f in sim2grid.faixas(con)}
    # os preços aprovados pelo dono em 22/10 (#392)
    assert fs == {(solo, "01234", 7, 17): 50, (solo, "01234", 18, 24): 75, (solo, "56", 8, 24): 90,
                  (coach, "01234", 7, 17): 125, (coach, "01234", 18, 24): 150, (coach, "56", 8, 24): 150}
    cfg = sim2grid.config(con)
    assert (cfg["capacity"], cfg["min_hours"], cfg["online"], cfg["waiver_required"], cfg["min_age"]) == (5, 1, 1, 1, None)
    planos = todos(con, "SELECT title, price, per FROM site_offers WHERE page='sim2grid' ORDER BY sort")
    assert [(p["title"], p["price"]) for p in planos] == [("3 sessions per week", "$1,800"), ("2 sessions per week", "$1,500"),
                                                          ("1 session per week", "$900")]
    # a equipe muda; a próxima subida não desfaz nem duplica
    f = next(x for x in sim2grid.faixas(con) if x["seed_key"] == "solo:semana:dia")
    sim2grid.mudar_faixa(con, None, f["id"], {"price": 55})
    sim2grid.mudar_config(con, None, {"capacity": 4})
    con.commit()
    aplicar_schema(con)
    assert um(con, "SELECT price FROM sim_rates WHERE id=?", (f["id"],))["price"] == 55
    assert sim2grid.config(con)["capacity"] == 4
    assert um(con, "SELECT COUNT(*) AS n FROM sim_rates")["n"] == 6
    assert um(con, "SELECT COUNT(*) AS n FROM booking_services WHERE kind='sim'")["n"] == 2
    assert um(con, "SELECT COUNT(*) AS n FROM site_offers WHERE page='sim2grid'")["n"] == 3


# ------------------------------------------------------------------ o preço
def test_o_preco_segue_a_faixa_do_inicio_e_o_coach(sim):
    cli, con, st, qbo, tmp, solo, coach = sim
    terca, sabado = dia(1), dia(5)
    d = _cotar(cli, [_item(solo, terca, 9), _item(solo, terca, 18, 2), _item(coach, terca, 9), _item(coach, terca, 20, 3),
                     _item(coach, sabado, 10), _item(solo, terca, 16, 2), _item(solo, sabado, 10), _item(solo, terca, 17),
                     _item(solo, terca, 9, preco=1, unitario=1)])
    ls = d["linhas"]
    assert [x["unitario"] for x in ls[:8]] == [50, 150, 125, 450, 150, 100, 90, 50], "sem coach 50/75/90, com coach 125/150/150"
    assert all(x["erro"] is None for x in ls[:8])
    # dono, 22/10: vale o horário de início — 16h por 2 h é diurna inteira, e começar às 17h usa a tarifa diurna
    assert ls[5]["detalhe"].endswith("4 PM–6 PM (2 h)") and ls[7]["detalhe"].endswith("5 PM–6 PM (1 h)")
    assert ls[8]["unitario"] == 50, "o preço do navegador não vale"
    assert ls[1]["detalhe"].endswith("6 PM–8 PM (2 h)")
    # o painel muda a faixa e o carrinho segue na hora
    f = next(x for x in sim2grid.faixas(con) if x["seed_key"] == "solo:semana:noite")
    sim2grid.mudar_faixa(con, None, f["id"], {"price": 80})
    con.commit()
    assert _cotar(cli, [_item(solo, terca, 18, 2)])["linhas"][0]["unitario"] == 160


def test_horas_minimas_e_maximas_do_painel(sim):
    cli, con, st, qbo, tmp, solo, coach = sim
    terca = dia(1)
    assert "from 1 to 3 hours" in _cotar(cli, [_item(solo, terca, 18, 4)])["linhas"][0]["erro"]
    sim2grid.mudar_config(con, None, {"min_hours": 2, "max_hours": 4})
    con.commit()
    ls = _cotar(cli, [_item(solo, terca, 18, 4), _item(solo, terca, 18, 1)])["linhas"]
    assert ls[0]["erro"] is None and ls[0]["unitario"] == 300
    assert "from 2 to 4 hours" in ls[1]["erro"]
    with pytest.raises(sim2grid.ErroSim):
        sim2grid.mudar_config(con, None, {"min_hours": 5})


# ------------------------------------------------------------------ a capacidade
def test_cinco_pessoas_na_mesma_hora_e_a_sexta_nao_entra(sim):
    cli, con, st, qbo, tmp, solo, coach = sim
    terca = dia(1)
    itens = [_item(solo, terca, 18) for _ in range(3)] + [_item(coach, terca, 18) for _ in range(2)] + [_item(solo, terca, 18)]
    ls = _cotar(cli, itens)["linhas"]
    assert all(x["erro"] is None for x in ls[:5]), "os formatos dividem os mesmos 5 simuladores"
    assert "full" in ls[5]["erro"]
    assert _cotar(cli, [_item(solo, terca, 19)])["linhas"][0]["erro"] is None, "a hora seguinte é outra"
    # o painel muda a capacidade: 2 simuladores
    sim2grid.mudar_config(con, None, {"capacity": 2})
    con.commit()
    ls = _cotar(cli, itens[:3])["linhas"]
    assert [x["erro"] is None for x in ls] == [True, True, False]


def test_o_calendario_mostra_as_vagas_que_sobram_por_hora(sim):
    cli, con, st, qbo, tmp, solo, coach = sim
    terca = dia(1)
    h = _hora(cli, terca, 18)
    assert h == {"h": 18, "spots": 5, "prices": {str(solo): 75, str(coach): 150}}
    assert _hora(cli, terca, 17)["prices"] == {str(solo): 50, str(coach): 125}, "começar às 17h: tarifa diurna"
    assert _hora(cli, terca, 6) is None, "antes das 7h não abre"
    sab = _hora(cli, dia(5), 10)
    assert sab["prices"] == {str(solo): 90, str(coach): 150}
    # duas pagas e uma segurada no Stripe ocupam; a segurada que venceu não ocupa
    agora = datetime.utcnow()
    for st_, ate in (("paga", None), ("paga", None), ("segurada", agora + timedelta(minutes=20)), ("segurada", agora - timedelta(minutes=1)),
                     ("liberada", None)):
        inserir(con, "sim_bookings", date=terca.isoformat(), start_hour=17 if st_ == "liberada" else 18, hours=2, price=150, status=st_,
                hold_until=ate.strftime("%Y-%m-%dT%H:%M:%S.000Z") if ate else None)
    con.commit()
    assert _hora(cli, terca, 18)["spots"] == 2 and _hora(cli, terca, 19)["spots"] == 2 and _hora(cli, terca, 20)["spots"] == 5
    ls = _cotar(cli, [_item(solo, terca, 19, 2) for _ in range(3)])["linhas"]
    assert [x["erro"] is None for x in ls] == [True, True, False]


def test_abertura_datas_fechadas_e_venda_desligada(sim):
    cli, con, st, qbo, tmp, solo, coach = sim
    terca = dia(1)
    sim2grid.mudar_config(con, None, {"closed_dates": f"{terca.isoformat()}, 2030-01-01"})
    con.commit()
    assert _hora(cli, terca, 18) is None
    assert "no longer available" in _cotar(cli, [_item(solo, terca, 18)])["linhas"][0]["erro"]
    sim2grid.mudar_config(con, None, {"closed_dates": "", "open_from": (terca + timedelta(days=1)).isoformat()})
    con.commit()
    assert _hora(cli, terca, 18) is None, "antes da abertura nada abre"
    sim2grid.mudar_config(con, None, {"open_from": "", "online": False})
    con.commit()
    assert "closed right now" in _cotar(cli, [_item(solo, terca, 18)])["linhas"][0]["erro"]
    html = cli.get(CAMINHO).text
    assert 'data-online="0"' in html and "Online booking is not open right now" in html


# ------------------------------------------------------------------ a reserva, o checkout e o pagamento
def test_reserva_segura_no_checkout_e_o_pago_vira_reserva_no_card_do_piloto(sim):
    cli, con, st, qbo, tmp, solo, coach = sim
    terca = dia(1)
    conta, pid = _entrar(cli, con)
    d = _cotar(cli, [_item(solo, terca, 18, 2)])
    assert d["linhas"][0]["falta_piloto"] and not d["ok"], "logado, cada simulador pede o piloto da conta"
    r = _checkout(cli, [_item(solo, terca, 18, 2, pid, sorteio=True)])
    assert r.status_code == 200, r.text
    (_, _, campos, _), = st.chamadas
    (linha,) = campos["line_items"]
    assert linha["price_data"]["unit_amount"] == 15000 and "Theo Souza" in linha["price_data"]["product_data"]["name"]
    assert campos["expires_at"] > 0, "o horário fica segurado só enquanto o Checkout vale"
    (b,) = todos(con, "SELECT * FROM sim_bookings")
    assert (b["status"], b["start_hour"], b["hours"], b["price"], b["pilot_id"], b["raffle"]) == ("segurada", 18, 2, 150, pid, 1)
    (x,) = carrinho.itens(con, um(con, "SELECT id FROM store_orders")["id"])
    assert (x["kind"], x["product_slug"], x["period"]) == ("sessao", "sim:18:2", None)
    assert not todos(con, "SELECT id FROM bookings"), "a hora de simulador não ocupa a agenda do kart"
    # segurada: outra pessoa vê uma vaga a menos
    cli2_vagas = _hora(cli, terca, 18)["spots"]
    assert cli2_vagas == 5, "a própria conta não se vê ocupando (é ela voltando do Stripe)"
    assert sim2grid.ocupacao(con, terca.isoformat(), terca.isoformat())[(terca.isoformat(), 18)] == 1
    # pago
    assert _pagar(cli, st, next(iter(st.sessoes))).json()["resultado"] == "pago"
    b = um(con, "SELECT * FROM sim_bookings WHERE id=?", (b["id"],))
    card = um(con, "SELECT client_id FROM portal_pilots WHERE id=?", (pid,))["client_id"]
    assert b["status"] == "paga" and card and b["client_id"] == card
    x = um(con, "SELECT * FROM store_order_items WHERE id=?", (x["id"],))
    assert (x["status"], x["client_id"]) == ("marcada", card)
    (opp,) = todos(con, "SELECT * FROM opportunities")
    assert (opp["stage"], opp["client_id"], opp["amount"]) == ("GANHO", card, 150)
    conf = next(m for m in _emails(tmp) if m["to"] == "lia@example.com")
    assert "SIM2GRID" in conf["text"] and "Box 5" in conf["text"] and "6 PM–8 PM" in conf["text"]
    # a waiver do piloto, pelo mesmo caminho da sessão de kart
    enviados = []
    carrinho.seguir_sessoes(con, x["order_id"], enviar_waiver=lambda *a: enviados.append(a) or {"envelopeId": "env-fict-1"})
    b = um(con, "SELECT * FROM sim_bookings WHERE id=?", (b["id"],))
    assert b["waiver_ref"] and enviados and enviados[0][1] == "Lia Souza", "a waiver sai para quem assina pelo piloto"
    w = um(con, "SELECT * FROM waivers WHERE id=?", (b["waiver_ref"],))
    assert w["client_id"] == card and "SIM2GRID" in w["link_reason"]
    assert um(con, "SELECT 1 AS x FROM audit_logs WHERE event='sim2grid.waiver'")
    sim2grid.mudar_config(con, None, {"waiver_required": False})
    # o painel vê a reserva, com o card
    assert sim2grid.reservas(con)["itens"][0]["client_id"] == card


def test_hora_que_encheu_antes_do_pagamento_fica_para_a_equipe(sim):
    cli, con, st, qbo, tmp, solo, coach = sim
    terca = dia(1)
    conta, pid = _entrar(cli, con)
    _checkout(cli, [_item(solo, terca, 18, 1, pid)])
    # o checkout venceu e outras 5 pessoas pagaram a mesma hora
    con.execute("UPDATE sim_bookings SET hold_until='2000-01-01T00:00:00.000Z'")
    for _ in range(5):
        inserir(con, "sim_bookings", date=terca.isoformat(), start_hour=18, hours=1, price=75, status="paga")
    con.commit()
    assert _pagar(cli, st, next(iter(st.sessoes))).json()["resultado"] == "pago"
    o = um(con, "SELECT * FROM store_orders")
    (x,) = carrinho.itens(con, o["id"])
    assert x["status"] == "sem_vaga" and "encheu" in x["note"] and o["attention"]
    assert um(con, "SELECT COUNT(*) AS n FROM sim_bookings WHERE status='paga'")["n"] == 5, "não passa dos 5 simuladores"


def test_mesmo_piloto_nao_ocupa_dois_simuladores_na_mesma_hora(sim):
    cli, con, st, qbo, tmp, solo, coach = sim
    terca = dia(1)
    conta, pid = _entrar(cli, con)
    ls = _cotar(cli, [_item(solo, terca, 18, 2, pid), _item(coach, terca, 19, 1, pid), _item(solo, terca, 20, 1, pid)])["linhas"]
    assert ls[0]["erro"] is None and "already in this cart" in ls[1]["erro"] and ls[2]["erro"] is None


# ------------------------------------------------------------------ a página
def test_pagina_da_lp_com_seo_e_os_precos_do_painel(sim):
    cli, con, st, qbo, tmp, solo, coach = sim
    r = cli.get(CAMINHO)
    assert r.status_code == 200
    p = _le(r.text)
    assert [t for n, t in p.h if n == "h1"] == [SG.PAGINA["h1"]]
    assert '<link rel="canonical" href="https://novo.urace.us/sim2grid-racing-simulator/">' in r.text
    assert f"<title>{SG.PAGINA['titulo']}</title>" in r.text
    # #396: a página de cinema — a reserva logo depois da foto; o texto longo da LP saiu
    for trecho in ("Book your seat", "Monthly programs", "10724 Cosmonaut Blvd, Box 5", "Starting at $50",
                   "What’s included in a simulator hour?", "Can I book this for my child?",
                   "What if I need to change or cancel my booking?", 'role="switch"', "With coach", "from $125/h",
                   "3 sessions per week", "$1,800", 'href="/pro-team/"', 'data-online="1"', "sim2grid.js", 'class="sim-barra"',
                   "Bring friends", "simulator-cockpit.webp"):
        assert trecho in r.text, trecho
    for saiu in ("You can see the driver. Now see the path.", "Bring the passion. Discover the possibilities.",
                 "One passion. A world of possibilities.", "Next lap: yours."):
        assert saiu not in r.text, saiu
    assert r.text.count("<details>") == 5, "o FAQ tem 5 perguntas, fechadas"
    servico = next(x for x in p.ld if x.get("@type") == "Service")
    precos = {o["priceSpecification"]["price"] for o in servico["offers"] if "priceSpecification" in o}
    assert precos == {"50.00", "75.00", "90.00", "125.00", "150.00"} and all(
        o["priceSpecification"]["unitCode"] == "HUR" for o in servico["offers"] if "priceSpecification" in o)
    assert any(x.get("@type") == "FAQPage" for x in p.ld)
    faq = next(x for x in p.ld if x.get("@type") == "FAQPage")
    custo = next(q for q in faq["mainEntity"] if q["name"] == "How much does it cost?")
    assert "Monday–Friday, 7 AM–5 PM: $50 per hour" in custo["acceptedAnswer"]["text"]
    assert "Monday–Friday, 7 AM–5 PM: $125 per hour" in custo["acceptedAnswer"]["text"]
    assert len(faq["mainEntity"]) == 5
    # o painel muda: a página segue (preço, faixa desativada, formato desativado)
    f = next(x for x in sim2grid.faixas(con) if x["seed_key"] == "solo:semana:dia")
    sim2grid.mudar_faixa(con, None, f["id"], {"price": 45})
    con.execute("UPDATE booking_services SET active=0 WHERE id=?", (coach,))
    con.commit()
    html = cli.get(CAMINHO).text
    assert "Starting at $45" in html and "from $125/h" not in html and 'role="switch"' not in html


def test_links_do_site_apontam_para_a_pagina_e_ela_esta_no_sitemap(sim):
    cli, con, st, qbo, tmp, solo, coach = sim
    home = cli.get("/").text
    assert f'href="{CAMINHO}"' in home and "/services/#sim2grid" not in home
    hub = cli.get("/services/").text
    assert f'href="{CAMINHO}"' in hub and "Until then you cannot book" not in hub
    mapa = cli.get("/sitemap.xml").text
    assert f"https://novo.urace.us{CAMINHO}" in mapa
    contato = cli.get("/contact/?assunto=sim2grid&produto=1%20session%20per%20week").text
    assert 'value="sim2grid" selected' in contato


# ------------------------------------------------------------------ o painel
SENHA = "pista-molhada-7"


@pytest.fixture()
def painel(sim):
    """O painel (outro endereço, o mesmo banco): um gerente e um operador fictícios."""
    from fastapi.testclient import TestClient

    from command_center.api import auth
    from command_center.api.main import app
    cli, con, *_ = sim
    auth.criar_usuario(con, "gerente.sim@example.com", "Gerente Sim", "MANAGER", SENHA)
    auth.criar_usuario(con, "op.sim@example.com", "Operador Sim", "OPERATOR", SENHA)
    con.commit()
    with TestClient(app, base_url="https://cc.test") as t:
        yield t


def _entra(t, email):
    t.cookies.clear()
    assert t.post("/ops/api/auth/login", json={"email": email, "password": SENHA}).status_code == 200
    t.headers["X-CSRF"] = t.cookies.get("cc_csrf") or ""


def test_painel_edita_regras_e_faixas_e_o_operador_so_ve(sim, painel):
    cli, con, st, qbo, tmp, solo, coach = sim
    eq = painel
    assert eq.get("/ops/api/site/sim2grid").status_code == 401, "sem login, nada"
    _entra(eq, "op.sim@example.com")
    assert eq.get("/ops/api/site/sim2grid").status_code == 200
    assert eq.patch("/ops/api/site/sim2grid/config", json={"capacity": 3}).status_code == 403, "o operador só vê"
    _entra(eq, "gerente.sim@example.com")
    d = eq.get("/ops/api/site/sim2grid").json()
    assert d["config"]["capacity"] == 5 and len(d["faixas"]) == 6 and d["pagina"] == CAMINHO and d["desde"] == 50
    r = eq.patch("/ops/api/site/sim2grid/config", json={"capacity": 3, "notice": "Arrive 10 minutes early.", "min_age": 12})
    assert r.status_code == 200 and r.json()["config"]["capacity"] == 3
    assert eq.patch("/ops/api/site/sim2grid/config", json={"capacity": 0}).status_code == 400
    r = eq.post("/ops/api/site/sim2grid/faixas", json={"service_id": solo, "days": "56", "start_hour": 8, "end_hour": 12, "price": "65"})
    assert r.status_code == 201
    fid = r.json()["id"]
    assert eq.post("/ops/api/site/sim2grid/faixas", json={"service_id": solo, "days": "56", "start_hour": 12, "end_hour": 9,
                                                           "price": "65"}).status_code == 400
    html = cli.get(CAMINHO).text
    assert "Drivers must be 12 or older." in html and "Arrive 10 minutes early." in html and "Up to 3 people" in html
    # a faixa nova vem antes da do fim de semana (US$ 90)? Não: vale a primeira da ordem
    sab = dia(5)
    assert _cotar(cli, [_item(solo, sab, 9)])["linhas"][0]["unitario"] == 90
    assert eq.patch(f"/ops/api/site/sim2grid/faixas/{fid}", json={"sort": 0}).status_code == 200
    assert _cotar(cli, [_item(solo, sab, 9)])["linhas"][0]["unitario"] == 65
    # e a auditoria registra quem mudou
    assert um(con, "SELECT COUNT(*) AS n FROM audit_logs WHERE event LIKE 'sim2grid.%'")["n"] >= 3


def test_formato_novo_de_simulador_pelo_painel_de_servicos(sim):
    cli, con, st, qbo, tmp, solo, coach = sim
    from command_center.providers import servicos_site as sv
    sid = sv.criar(con, None, {"name": "SIM2GRID · Endurance hour", "price": 90, "kind": "sim", "site_title": "Endurance"})
    sim2grid.criar_faixa(con, None, {"service_id": sid, "days": [0, 1, 2], "start_hour": 9, "end_hour": 12, "price": 90})
    con.commit()
    assert sv.onde_no_site(sv.lista(con))[sid]["onde"] == "sim2grid"
    assert "Endurance" in cli.get(CAMINHO).text
    assert _cotar(cli, [_item(sid, dia(0), 10, 2)])["linhas"][0]["unitario"] == 180
    with pytest.raises(sim2grid.ErroSim):
        sim2grid.criar_faixa(con, None, {"service_id": um(con, "SELECT id FROM booking_services WHERE site_kart='4-stroke'")["id"],
                                         "days": "0", "start_hour": 9, "end_hour": 10, "price": 1})


def test_texto_das_faixas_e_das_horas():
    fs = [{"service_id": 1, "days": "01234", "start_hour": 7, "end_hour": 17, "price": 50, "active": 1},
          {"service_id": 1, "days": "56", "start_hour": 8, "end_hour": 24, "price": None, "active": 1}]
    assert sim2grid.texto_das_faixas(fs, 1) == ("Monday–Friday, 7 AM–5 PM: $50 per hour; Saturday–Sunday, 8 AM–midnight: "
                                                "call our team for options")
    assert sim2grid.quando("2026-11-03", 18, 2) == "Tue, Nov 3, 2026 · 6 PM–8 PM (2 h)"
    assert sim2grid.do_slug("sim:18:2") == (18, 2) and sim2grid.do_slug("addon:3") is None
    assert date.fromisoformat(SG.REGRAS["open_from"]) == date(2026, 11, 1)
    assert json.dumps(SG.PAGINA) and re.search(r"\{desde\}", SG.PAGINA["sub"]) and re.search(r"\{capacidade\}", SG.PAGINA["sub"])


# ------------------------------------------------------------------ a etiqueta do dia (#396)
def _dia_api(cli, d):
    j = cli.get("/ops/api/vitrine/sim2grid").json()
    return next((x for x in j["dias"] if x["date"] == d.isoformat()), None)


def test_etiqueta_do_dia_nasce_vazia_e_aparece_no_calendario(sim):
    """#396, dono 23/10: "alguns dias frequentados por pilotos · outros dias por pessoas que vao levar como
    entretenimento". Nada nasce marcado; a etiqueta da equipe aparece no dia (a data antes do dia da semana)."""
    cli, con, st, qbo, tmp, solo, coach = sim
    assert um(con, "SELECT COUNT(*) AS n FROM sim_day_tags")["n"] == 0, "a semente é vazia: a equipe define"
    aplicar_schema(con)
    assert um(con, "SELECT COUNT(*) AS n FROM sim_day_tags")["n"] == 0, "a migração é idempotente e não semeia"
    j = cli.get("/ops/api/vitrine/sim2grid").json()
    assert j["dias"] and all(x["tags"] == [] for x in j["dias"])
    terca, sabado = dia(1), dia(5)
    noite = sim2grid.criar_etiqueta(con, None, {"label": "Fun night", "icon": "🎮", "days": "1", "start_hour": 18, "end_hour": 24})
    sim2grid.criar_etiqueta(con, None, {"label": "Pilot day", "icon": "🏁", "days": [5, 6], "note": "Coaches on site"})
    sim2grid.criar_etiqueta(con, None, {"label": "League night", "date": terca.isoformat()})
    con.commit()
    assert _dia_api(cli, terca)["tags"] == [
        {"label": "League night", "icon": "", "note": "", "start": None, "end": None},
        {"label": "Fun night", "icon": "🎮", "note": "", "start": 18, "end": 24}], "a data vem antes do dia da semana"
    assert _dia_api(cli, sabado)["tags"] == [{"label": "Pilot day", "icon": "🏁", "note": "Coaches on site", "start": None, "end": None}]
    assert _dia_api(cli, dia(2))["tags"] == []
    # desativar tira do site e não apaga
    sim2grid.mudar_etiqueta(con, None, noite, {"active": False})
    con.commit()
    assert [t["label"] for t in _dia_api(cli, terca)["tags"]] == ["League night"]
    assert um(con, "SELECT COUNT(*) AS n FROM sim_day_tags")["n"] == 3
    for ruim in ({"label": "", "days": "1"}, {"label": "X" * 25, "days": "1"}, {"label": "Pilot day"},
                 {"label": "Pilot day", "days": "1", "start_hour": 18}, {"label": "Pilot day", "days": "1", "start_hour": 20, "end_hour": 18},
                 {"label": "Pilot day", "date": "23/10/2026"}, {"label": "Pilot day", "days": "1", "icon": "🏁" * 9}):
        with pytest.raises(sim2grid.ErroSim):
            sim2grid.criar_etiqueta(con, None, ruim)


def test_painel_edita_a_etiqueta_do_dia_e_o_operador_so_ve(sim, painel):
    cli, con, st, qbo, tmp, solo, coach = sim
    eq = painel
    _entra(eq, "op.sim@example.com")
    r = eq.get("/ops/api/site/sim2grid")
    assert r.status_code == 200 and r.json()["etiquetas"] == []
    assert eq.get("/ops/api/site/sim2grid", headers={"If-None-Match": r.headers["etag"]}).status_code == 304, "GET com ETag"
    assert eq.post("/ops/api/site/sim2grid/etiquetas", json={"label": "Pilot day", "days": "0"}).status_code == 403, "o operador só vê"
    _entra(eq, "gerente.sim@example.com")
    r = eq.post("/ops/api/site/sim2grid/etiquetas", json={"label": "Pilot day", "icon": "🏁", "days": [0, 1, 2]})
    assert r.status_code == 201
    tid = r.json()["id"]
    assert [t["label"] for t in r.json()["etiquetas"]] == ["Pilot day"]
    assert eq.post("/ops/api/site/sim2grid/etiquetas", json={"label": "Fun night"}).status_code == 400, "sem dia nem data"
    segunda = dia(0)
    r = eq.patch(f"/ops/api/site/sim2grid/etiquetas/{tid}", json={"label": "Fun night", "icon": "🎮", "start_hour": 18, "end_hour": 24})
    assert r.status_code == 200
    assert _dia_api(cli, segunda)["tags"] == [{"label": "Fun night", "icon": "🎮", "note": "", "start": 18, "end": 24}]
    # por data: o dia da semana deixa de valer
    assert eq.patch(f"/ops/api/site/sim2grid/etiquetas/{tid}", json={"date": dia(3).isoformat(), "days": None}).status_code == 200
    assert _dia_api(cli, segunda)["tags"] == [] and _dia_api(cli, dia(3))["tags"][0]["label"] == "Fun night"
    assert eq.patch("/ops/api/site/sim2grid/etiquetas/9999", json={"label": "X"}).status_code == 404
    assert um(con, "SELECT COUNT(*) AS n FROM audit_logs WHERE event LIKE 'sim2grid.tag.%'")["n"] == 3
