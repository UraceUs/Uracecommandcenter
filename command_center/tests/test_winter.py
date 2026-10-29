"""Race the Winter 2027 (#505): a /winter/ do urace.us, refeita por blocos (`vitrine/pg_winter.py`).

Dono, 29/10: *"sim, pode trazer o texto e recriar a winter"*. O que estes testes trancam:
- a página responde com um h1, o título e a descrição de hoje, entra no sitemap e diz ao Google a trilha e as duas
  rodadas de casa (data e lugar, só o que a página afirma);
- o contador vai até a largada da R1 (15 Jan 2027, 8:00 am ET);
- o calendário tem as sete provas, o kart as oito peças, e o localizador as classes da SKUSA como estão na página de hoje;
- "Build your winter" cai em Vendas (Racing Team) com o plano na nota, e volta para a página;
- a estimativa usa a diária do kart do PAINEL (mudou lá, muda aqui; kart desativado sai) e nenhum preço é texto;
- o contato da equipe é o formulário, a agenda e o e-mail @urace.us: nenhum telefone além do principal (#244)."""
import os
import re

import pytest

os.environ.setdefault("CC_AUTOSYNC", "0")

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api import vitrine  # noqa: E402
from command_center.api.main import app  # noqa: E402
from command_center.db import aplicar_schema, conectar  # noqa: E402
from command_center.tests.test_vitrine import _le  # noqa: E402
from command_center.vitrine import blocos, conteudo, pg_winter  # noqa: E402

SITE = "https://novo.urace.us"


@pytest.fixture()
def cli(tmp_path, monkeypatch):
    """O site com o banco deste teste: os serviços do Arrive and Drive nascem da migração (#263), como no painel."""
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path))
    monkeypatch.setenv("CC_EMAIL_FAKE", str(tmp_path / "emails.jsonl"))
    monkeypatch.delenv("CC_SITE_HOSTS", raising=False)
    con = conectar(); aplicar_schema(con); con.close()
    vitrine._envios.clear()
    with TestClient(app, base_url=SITE) as t:
        yield t
    vitrine._envios.clear()            # o limite do formulário é da memória do processo: não vaza para o próximo teste


def _karts(cli):
    """{kart da estimativa: diária no `data-preco`} como a página sai agora."""
    return dict(re.findall(r'data-kt="([a-z0-9]+)" data-preco="([\d.]+)"', cli.get("/winter/").text))


def test_a_winter_responde_com_um_h1_e_o_titulo_e_a_descricao_de_hoje(cli):
    r = cli.get("/winter/")
    assert r.status_code == 200
    p = _le(r.text)
    assert [t for n, t in p.h if n == "h1"] == ["Race the winter"]
    niveis = [int(n[1]) for n, _ in p.h]
    assert niveis[1] == 2 and all(b - a <= 1 for a, b in zip(niveis, niveis[1:])), "h1 → h2 → h3, sem pular nível"
    assert "<title>Race the Winter 2027 | URACE</title>" in r.text
    metas = {a.get("name") or a.get("property"): a.get("content") for t, a in p.attrs if t == "meta"}
    assert metas["description"] == pg_winter.WINTER["descricao"]
    assert metas["description"].startswith("Race the Winter 2027 with URACE: 80 days of testing and four SKUSA Winter Series")
    assert [a["href"] for t, a in p.attrs if t == "link" and a.get("rel") == "canonical"] == [SITE + "/winter/"]
    # o JavaScript é nosso e vem de arquivo: nada inline, nada de fora, e nenhum estilo solto
    assert re.search(r'<script src="/_s/winter\.js\?v=[0-9a-f]+" defer></script>', r.text)
    assert not re.findall(r'<script(?![^>]*\bsrc="/_s/)(?![^>]*type="application/ld\+json")', r.text)
    assert "style=" not in r.text and "<canvas" not in r.text and "three.min.js" not in r.text, "sem o circuito em 3D"
    # as fotos têm tamanho; só a do topo carrega na hora
    imgs = re.findall(r"<img [^>]+>", re.search(r'<main id="conteudo">(.*)</main>', r.text, re.S).group(1))
    assert imgs and all('width="' in i and 'height="' in i for i in imgs)
    assert sum('fetchpriority="high"' in i for i in imgs) == 1 and sum('loading="lazy"' in i for i in imgs) == len(imgs) - 1


def test_a_winter_esta_no_sitemap_e_no_google(cli):
    assert "/winter/" in blocos.caminhos_indexaveis()
    assert "/winter/</loc>" in cli.get("/sitemap.xml").text


def test_json_ld_tem_a_trilha_e_as_duas_rodadas_de_casa(cli):
    p = _le(cli.get("/winter/").text)
    trilha = next(x for x in p.ld if x.get("@type") == "BreadcrumbList")
    assert trilha["itemListElement"][-1] == {"@type": "ListItem", "position": 2, "name": "Race the Winter 2027",
                                             "item": SITE + "/winter/"}
    eventos = next(x for x in p.ld if "@graph" in x)["@graph"]
    assert [(e["@type"], e["startDate"], e["endDate"]) for e in eventos] == [
        ("SportsEvent", "2027-01-15T08:00:00-05:00", "2027-01-17"), ("SportsEvent", "2027-02-12", "2027-02-14")]
    for e in eventos:
        assert e["location"]["name"] == "Orlando Kart Center" and e["location"]["address"]["postalCode"] == "32824"
        assert e["description"] == "Dates as published Oct 2026 · we reconfirm before entry"


def test_contador_ate_a_largada_da_primeira_rodada(cli):
    html = cli.get("/winter/").text
    assert 'class="contador" data-alvo="2027-01-15T08:00:00-05:00"' in html
    assert "to lights out · 15 Jan 2027 · 8:00 am ET" in html
    assert re.search(r'<script src="/_s/blocos\.js\?v=[0-9a-f]+" defer></script>', html)


def test_calendario_pecas_do_kart_e_classes_da_skusa_como_na_pagina_de_hoje(cli):
    html = cli.get("/winter/").text
    assert re.findall(r'<li data-tipo="(home|opt|tbc)">', html) == ["home", "opt", "tbc", "opt", "home", "tbc", "opt"]
    assert "Dates as published Oct 2026 · we reconfirm before entry" in html
    assert len(re.findall(r'<details class="winter-peca" id="kart-part-\d"', html)) == 8
    classes = re.findall(r'<li data-min="(\d+)" data-max="(\d+)" data-peso-lb="(\d+)"><strong>([^<]+)</strong>', html)
    assert classes == [("7", "10", "220", "Micro Swift"), ("9", "13", "245", "Mini Swift"), ("12", "15", "320", "KA100 Junior"),
                       ("12", "15", "320", "X30 Junior"), ("15", "99", "355", "KA100 Senior"), ("15", "99", "360", "Pro X30"),
                       ("15", "99", "390", "Pro Shifter"), ("30", "99", "390", "KA100 Master")]
    assert "Classes as run in the 2026 SKUSA Winter Series. 2027 classes are confirmed by SKUSA before entry." in html


def test_o_plano_cai_em_vendas_com_os_campos_na_nota(cli):
    """Sem JavaScript (POST normal): a oportunidade nasce em Vendas, Racing Team, com cada campo do plano numa linha."""
    form = re.search(r'<form class="form-contato".*?</form>', cli.get("/winter/").text, re.S).group(0)
    assert 'name="assunto" value="team"' in form and 'name="volta" value="/winter/"' in form
    nomes = re.findall(r'name="(x_[a-z0-9_]+)"', form)
    assert {"x_season", "x_driver", "x_racing_from", "x_racing_age", "x_weight_in_full_gear", "x_arrive", "x_fly_home",
            "x_base_camp", "x_concierge", "x_mental_performance", "x_athletic_camp"} <= set(nomes)
    assert [n for n in nomes if n.startswith("x_weekend_")] == [f"x_weekend_{n}" for n in range(1, 8)]
    assert len(nomes) <= 20, "o contato lê até 20 campos extras"
    r = cli.post("/ops/api/vitrine/contato", data={
        "nome": "Ana Exemplo", "email": "ana@example.com", "assunto": "team", "volta": "/winter/",
        "x_season": "Winter Season 2027", "x_driver": "Leo", "x_racing_from": "Europe", "x_racing_age": "12",
        "x_weekend_1": "15–17 Jan · SKUSA Winter Series · Rounds 1 & 2", "x_arrive": "Week of 11 Jan",
        "x_fly_home": "Sunday 14 Feb", "x_base_camp": "Lake Nona Wave Hotel", "x_concierge": "Yes"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/winter/?sent=1"
    assert "aviso-ok" in cli.get("/winter/?sent=1").text
    con = conectar()
    o = con.execute("SELECT name, service, source, notes FROM opportunities").fetchone()
    con.close()
    assert (o["name"], o["service"], o["source"]) == ("Ana Exemplo", "Racing Team", "Site")
    assert o["notes"] == ("[Racing Team] Season: Winter Season 2027\nDriver: Leo\nRacing from: Europe\nRacing age: 12\n"
                          "Weekend 1: 15–17 Jan · SKUSA Winter Series · Rounds 1 & 2\nArrive: Week of 11 Jan\n"
                          "Fly home: Sunday 14 Feb\nBase camp: Lake Nona Wave Hotel\nConcierge: Yes")


def test_a_estimativa_usa_a_diaria_do_kart_do_painel(cli):
    """A diária de cada kart é a do serviço do Arrive and Drive no painel (#50, #263): mudou lá, muda aqui; o kart que o
    painel desativou sai da estimativa."""
    con = conectar()
    precos = {r["site_kart"]: r["price"] for r in con.execute(
        "SELECT site_kart, price FROM booking_services WHERE active=1 AND COALESCE(kind,'session')='session'")}
    assert _karts(cli) == {kt: f"{precos[chave]:g}" for chave, kt in (("Baby Kart", "baby"), ("4-stroke", "4s"),
                                                                       ("2-stroke", "2s"), ("Adult Shifter", "shift"))}
    con.execute("UPDATE booking_services SET price=845.5 WHERE site_kart='2-stroke'")
    con.execute("UPDATE booking_services SET active=0 WHERE site_kart='Adult Shifter'")
    con.close()
    k = _karts(cli)
    assert k["2s"] == "845.5" and "shift" not in k
    html = cli.get("/winter/").text
    assert "Age 7+ · $845.50/day" in html and 'data-kt="2s" data-preco="845.5"' in html


def test_nenhum_preco_escrito_na_pagina(cli):
    """O número da estimativa sai do painel; fora dela, nenhum `$`. E a conferência pega preço escrito em qualquer texto
    desta página, inclusive nos blocos que só ela tem."""
    assert blocos.problemas(pg_winter.WINTER) == []
    main = re.search(r'<main id="conteudo">(.*)</main>', cli.get("/winter/").text, re.S).group(1)
    assert "$" not in re.sub(r'<form class="winter-estimativa".*?</form>', "", main, flags=re.S)
    ultimo = pg_winter.WINTER["blocos"][-1]
    estragada = {**pg_winter.WINTER, "blocos": [*pg_winter.WINTER["blocos"][:-1], {**ultimo, "total_nota": "From $719 a day"}]}
    assert any("preço escrito" in x for x in blocos.problemas(estragada))


def test_contato_da_equipe_sem_telefone_alem_do_principal(cli):
    """#244: o telefone direto da página de hoje não entra no repositório; o contato é o formulário, a agenda do Lucas
    (https) e o e-mail @urace.us. O único telefone é o principal (o do rodapé)."""
    html = cli.get("/winter/").text
    assert set(re.findall(r'href="tel:([^"]+)"', html)) <= {conteudo.SITE["telefone_e164"]}
    assert 'href="mailto:lucas@urace.us"' in html
    assert 'href="https://calendar.app.google/whLkkpp82fUzsfvT8" rel="noopener"' in html


def test_o_que_o_urace_us_de_hoje_esconde_fica_de_fora(cli):
    """No urace.us de 29/10 estes trechos estão com `display:none`: o dono tirou da página, então aqui também não saem."""
    html = cli.get("/winter/").text
    for trecho in ("We bring everything", "The work nobody sees", "The long game", "The season on one page",
                   "Send three things", "What that is worth"):
        assert trecho not in html, trecho
    # o que lá está à mostra continua
    for trecho in ("Snow stops racing. Orlando doesn", "Your race weekends", "The engine call is ours", "What it costs"):
        assert trecho in html, trecho
