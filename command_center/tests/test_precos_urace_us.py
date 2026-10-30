"""#525 (dono, 30/10): *"usa os valores do urace us"* e *"URACE Boost: sim volta"*.

Os programas com o preço do urace.us de 29/10 (`conteudo.PRECOS`, que a Rate Card confirma), o Boost de volta, o painel
que já tinha o preço de fábrica antigo passa ao novo (o editado fica) e a estimativa da /winter/ com a conta de lá.
"""
import os
import re

import pytest

os.environ.setdefault("CC_AUTOSYNC", "0")

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api.main import app  # noqa: E402
from command_center.db import aplicar_schema, conectar, todos  # noqa: E402
from command_center.vitrine import blocos  # noqa: E402
from command_center.vitrine import conteudo as C  # noqa: E402

SITE = "https://novo.urace.us"


@pytest.fixture()
def cli(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path))
    monkeypatch.delenv("CC_SITE_HOSTS", raising=False)
    monkeypatch.delenv("CC_SITE_PREVIEW", raising=False)
    with TestClient(app, base_url=SITE) as t:
        yield t


def test_precos_sao_os_do_urace_us():
    assert C.PRECOS == {"academy": 2756.90, "academy_sessao": 689.23, "boost": 5000, "boost_sessao": 625, "sim2grid": 1200,
                        "race_weekend": 4500}
    assert round(C.PRECOS["academy"] / 4, 2) == C.PRECOS["academy_sessao"], "a sessão é o mensal ÷ 4 (Rate Card)"
    assert C.PRECOS["boost"] / 8 == C.PRECOS["boost_sessao"], "8 sessões em 30 dias"
    assert blocos.com_precos("at {boost_sessao} a session; {academy}; {academy_k}/mo; {boost_k}/mo") == \
        "at $625 a session; $2,756.90; $3K/mo; $5K/mo"
    assert blocos.preco("boost") == ("$5,000", "/ 30 days") and blocos.preco("sim2grid") == ("$1,200", "/ month")
    # a marca fica no texto; a conferência não vê número escrito
    assert not blocos.problemas({"caminho": "/x/", "titulo": "t", "descricao": "d",
                                 "blocos": [{"tipo": "hero", "h1": "x"}, {"tipo": "texto", "paragrafos": ["{boost_sessao}"]}]})


def test_formulario_das_landings_com_os_precos(cli):
    html = cli.get("/kart-driving-school/").text
    opcoes = re.findall(r'name="x_option" value="([^"]+)"', html)
    assert "($719/day" in opcoes[0]
    assert opcoes[1].endswith("join the Academy ($2,756.90/mo)") and opcoes[2].endswith("Racing Team ($5,000/mo +)")


def test_driver_factory_com_o_a_partir_de_do_urace_us(cli):
    texto = re.sub(r"<[^>]+>", "", cli.get("/the-driver-factory/").text)
    assert "Programs starting at $3K/mo" in texto and "Programs starting at $5K/mo" in texto


def test_academy_e_pro_team_com_o_boost(cli):
    academy = cli.get("/academy/").text
    assert "URACE Boost · $625 per session" in academy and "Eight sessions in 30 days for faster progression" in academy
    # o Boost vem logo depois do grupo do 4 stroke
    grupos = re.findall(r'<h3 class="mt">([^<]+)</h3>', academy)
    assert grupos[:2] == ["4-stroke and Baby Kart · $689 per session", "URACE Boost · $625 per session"], grupos
    pro = cli.get("/pro-team/").text
    titulos = re.findall(r'<article class="plano"><h3>([^<]+)</h3>', pro)
    assert titulos == ["URACE Academy", "URACE Boost", "Race Weekend Support"]
    assert "Three ways in" in pro


def test_painel_com_o_preco_antigo_de_fabrica_passa_ao_do_urace_us(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path / "urace"))
    from command_center.vitrine import conteudo_sim2grid as SG
    con = conectar()
    aplicar_schema(con)
    # como o banco de produção estava em 30/10
    con.execute("UPDATE site_offers SET price='$2,756' WHERE seed_key='academy:0:0'")
    con.execute("UPDATE site_offers SET price='$3,156' WHERE seed_key='academy:1:0'")
    con.execute("UPDATE site_offers SET price='$1,500', body=? WHERE seed_key='sim2grid:1'", (SG.PLANOS_TEXTO,))
    con.execute("UPDATE site_offers SET price='$999' WHERE seed_key='sim2grid:2'")          # alguém editou
    con.execute("DELETE FROM site_offers WHERE seed_key IN ('academy:3:0', 'pro-team:2')")   # o Boost ainda não existia
    con.commit()
    aplicar_schema(con)
    preco = {r["seed_key"]: (r["price"], r["body"], r["sort"]) for r in todos(con, "SELECT * FROM site_offers")}
    assert preco["academy:0:0"][0] == "$2,756.90" and preco["academy:1:0"][0] == "$3,156.90"
    assert preco["sim2grid:1"][:2] == ("$1,360", SG.PLANOS[1][2])
    assert preco["sim2grid:2"][0] == "$999", "o que a equipe mudou fica"
    assert (preco["academy:3:0"][0], preco["academy:3:0"][2]) == ("$5,000", 50)
    assert preco["pro-team:2"][0] == "{boost}" and preco["pro-team:2"][2] == 5
    con.close()


def test_estimativa_da_winter_leva_as_tarifas_do_urace_us(cli):
    html = cli.get("/winter/").text
    form = re.search(r'<form class="winter-estimativa" ([^>]+)>', html).group(1)
    assert 'data-sessao="689.23" data-boost="625" data-corrida="4500" data-base-teste="719" data-base-corrida="819"' in form
    assert "<b data-total-corrida>Quoted per event</b>" in html, "sem JavaScript, o fim de semana fica a cotar"
    js = cli.get("/_s/winter.js").text
    for trecho in ("tarifa('boost')", "k >= 8", "/ 50) * 50", "total * 0.9 / 100", "total * 1.15 / 100"):
        assert trecho in js, trecho
