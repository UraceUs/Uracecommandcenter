"""#528: o simulador de carreira do urace.us (urace.us/plan-your-career/, 29/10) no /career/ do site novo.

Dono, 30/10: *"sim pfvr"* e *"usa os valores do urace us"*. Os dados moram em `conteudo_carreira` (copiados do script
de lá); a página sai do servidor (funciona sem JavaScript) e o `carreira.js` só liga a escolha, as perguntas e o plano.
"""
import os
import re
from html import unescape

import pytest

os.environ.setdefault("CC_AUTOSYNC", "0")

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api.main import app  # noqa: E402
from command_center.vitrine import conteudo_carreira as K  # noqa: E402
from command_center.vitrine.paginas import STATIC, usd  # noqa: E402

SITE = "https://novo.urace.us"


@pytest.fixture()
def cli(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path))
    monkeypatch.delenv("CC_SITE_HOSTS", raising=False)
    monkeypatch.delenv("CC_SITE_PREVIEW", raising=False)
    with TestClient(app, base_url=SITE) as t:
        yield t


@pytest.fixture()
def html(cli):
    r = cli.get("/career/")
    assert r.status_code == 200
    return r.text


def _txt(h):
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))).strip()


def _secao(html, ident):
    m = re.search(rf'<section [^>]*id="{ident}".*?</section>', html, re.S)
    assert m, ident
    return m.group(0)


# ------------------------------------------------------------------ os dados (o que o urace.us publica)
def test_tres_destinos_onze_degraus_e_os_quatro_vermelhos_sao_da_urace():
    """"Three destinations, one ladder, eleven steps" e "URACE runs the four red rungs": a mesma escada nas três rotas,
    os quatro de baixo são da URACE, o National Karting é onde se divide e o último é o destino."""
    assert [r["nome"] for r in K.ROTAS] == ["Formula 1", "IndyCar", "NASCAR"]
    for r in K.ROTAS:
        passos = K.caminho(r["chave"])
        assert len(passos) == 11, r["chave"]
        assert [d["nome"] for d in passos[:5]] == ["Sim2Grid", "Arrive and Drive", "URACE Academy", "URACE Racing Team",
                                                   "National Karting"]
        assert sum(d["quem"] == K.QUEM_NOSSO for d in passos) == 4
        assert passos[-1]["quem"] == K.QUEM_DESTINO and passos[-1]["passo"] == "Step 10"
        assert [d["passo"] for d in passos[4:]] == [f"Step {n}" for n in range(4, 11)], "Step 4 a Step 10, sem pular"
        assert all(d["texto"] and len(d["numeros"]) == 3 for d in passos)
    assert [K.caminho(k)[-1]["nome"] for k in ("f1", "indy", "nascar")] == ["Formula 1", "IndyCar", "NASCAR Cup Series"]
    assert K.caminho("nascar")[5]["nome"] == "Legends & Bandolero", "a rota do NASCAR sai do kart sem passar pela FARA"


def test_precos_do_urace_us_e_a_conta_do_plano():
    """Os preços de lá (dono, 30/10) e a conta do `planText()` de lá: avulso × quantidade, mensal × quantidade, e o que
    é "quote" só conta como item a cotar."""
    custos = {d["nome"]: d["custo"] for d in K.BASE}
    assert custos == {"Sim2Grid": (1200, "month"), "Arrive and Drive": (719, "day"), "URACE Academy": (2756.90, "month"),
                      "URACE Racing Team": "quote"}
    precos = {k: (p, u) for k, _r, p, u, _n, _d in K.ITENS_PLANO}
    assert precos == {"sim-solo": (60, "once"), "sim-coach": (150, "once"), "sim-school": (1200, "month"),
                      "ad-day": (719, "once"), "ac-1": (2756.90, "month"), "ac-3": (2688.43, "month"),
                      "ac-6": (2619.06, "month"), "team": (None, "quote")}
    assert "Professional Coaching" not in str(K.ITENS_PLANO), "#254: o nome saiu do site"
    assert K.totais({}) == (0, 0, 0)
    assert K.totais({"sim-coach": 2, "ad-day": 1, "ac-3": 1, "sim-school": 1, "team": 1}) == (1019, 3888.43, 1)
    assert K.totais({"ac-6": 3}) == (0, 7857.18, 0)


@pytest.mark.parametrize("quem, idade, exp, esperado", [
    ("child", "4", "never", "ad"), ("me", "4", "never", "ad"), ("child", "7", "never", "sim"), ("me", "16", "never", "sim"),
    ("child", "4", "some", "academy"), ("me", "11", "some", "academy"), ("child", "4", "races", "team"),
    ("me", "16", "races", "team"), (None, "7", "never", None), ("me", None, "never", None), ("me", "7", None, None)])
def test_find_your_step_e_o_decide_do_urace_us(quem, idade, exp, esperado):
    assert K.decidir(quem, idade, exp) == esperado


# ------------------------------------------------------------------ a página
def test_a_pagina_tem_um_h1_e_os_niveis_de_titulo_nao_pulam(html):
    niveis = [int(n) for n in re.findall(r"<h([1-6])[\s>]", html)]
    assert niveis.count(1) == 1
    assert all(b - a <= 1 for a, b in zip(niveis, niveis[1:])), niveis
    assert '<a class="btn" href="#find-your-step">Find your step</a>' in html
    assert 'href="#simulator">Play the career simulator</a>' in html
    assert "The ladder ends on our grid" not in html, "a escada antiga virou o simulador"


def test_o_simulador_sai_do_servidor_com_os_dados_do_conteudo(html):
    sim = _secao(html, "simulator")
    assert '<h2 id="h-sim">Select your career</h2>' in sim
    # os radios do destino (escondidos até o script), o F1 marcado como lá, e a região que anuncia a escolha
    radios = re.findall(r'<input type="radio" name="destino" value="(\w+)"( checked)?>', sim)
    assert radios == [("f1", " checked"), ("indy", ""), ("nascar", "")]
    assert re.search(r'<fieldset class="car-alvos" data-car-alvos hidden>', sim)
    assert '<p class="car-anuncio" aria-live="polite" data-car-anuncio></p>' in sim
    for r in K.ROTAS:
        resumo = re.search(rf'<div class="car-rota" data-rota="{r["chave"]}" data-anuncio="([^"]+)">(.*?)</div>', sim, re.S)
        assert resumo, r["chave"]
        passos = K.caminho(r["chave"])
        assert unescape(resumo.group(1)) == f"{r['nome']}, {r['tag']}: 11 steps, from Sim2Grid to {passos[-1]['nome']}."
        assert r["nota"] in unescape(resumo.group(2))
        trilha = re.findall(r"<li[^>]*><a href=\"#([\w-]+)\"><i>(\d+)</i><b>([^<]+)</b><small>([^<]+)</small></a></li>",
                            resumo.group(2))
        assert [int(n) for _a, n, _b, _c in trilha] == list(range(1, 12))
        assert [unescape(b) for _a, _n, b, _c in trilha] == [d["curto"] for d in passos]
        for ancora, _n, _b, _c in trilha:
            assert f'id="{ancora}"' in sim, ancora              # cada passo do caminho leva ao degrau
        # o preço de cada degrau da URACE, escrito com o usd() do site
        assert [unescape(c) for _a, _n, _b, c in trilha][:4] == ["$1,200 / month", "$719 / day", "$2,756.90 / month", "Quote"]
        ramo = re.search(rf'data-rota-degraus="{r["chave"]}">(.*?)</ol></div>', sim, re.S).group(1)
        assert _txt(ramo).startswith(f"↑ the ladder splits here — this leg heads for {passos[-1]['nome']}")
        for d in r["degraus"]:
            assert d["nome"] in unescape(ramo) and d["texto"] in unescape(ramo), d["nome"]
    for d in (*K.BASE, K.BIFURCACAO):
        li = re.search(rf'<li class="car-degrau[^"]*" id="step-{d["chave"]}">(.*?)</li>', sim, re.S)
        assert li, d["chave"]
        texto = unescape(li.group(1))
        assert d["texto"] in texto and d["quem"] in texto
        for a, b in d["numeros"]:
            assert f"<dt>{a}</dt><dd>{b}</dd>" in texto
    assert "URACE runs the four red rungs." in _txt(sim)


def test_find_your_step_sem_javascript_mostra_as_quatro_respostas(html):
    achar = _secao(html, "find-your-step")
    assert '<form class="car-perguntas" data-car-localizador hidden' in achar
    assert '<div class="car-respostas" aria-live="polite" data-car-respostas>' in achar
    for q, _t, op in K.LOCALIZADOR["perguntas"]:
        assert [v for v, _r in op] == re.findall(rf'name="{q}" value="(\w+)"', achar)
    resp = dict(re.findall(r'data-resultado="(\w+)">(.*?)</div>', achar, re.S))
    assert list(resp) == ["sim", "ad", "academy", "team"]
    for k, (degrau, porque) in K.RESULTADOS.items():
        assert porque in unescape(resp[k]) and f'href="#step-{degrau}"' in resp[k]
    # a condição de cada resposta, tirada da regra
    assert _txt(resp["ad"]).startswith("Been in a race kart before? Never · How old? 4 – 6 ")
    assert _txt(resp["sim"]).startswith("Been in a race kart before? Never · How old? 7 – 10, 11 – 15, 16 + ")
    assert _txt(resp["academy"]).startswith("Been in a race kart before? A few times Your starting rung")
    assert _txt(resp["team"]).startswith("Been in a race kart before? Races already Your starting rung")


def test_o_plano_lista_os_precos_e_o_script_le_o_data_preco(html):
    plano = _secao(html, "my-plan")
    linhas = re.findall(r'<li class="car-item" data-item="([\w-]+)" data-preco="([\d.]*)" data-unidade="(\w+)" '
                        r'data-rotulo="([^"]+)">.*?<span class="car-item-preco">([^<]+)</span>', plano)
    assert [(k, unescape(r), u) for k, _p, u, r, _v in linhas] == [(k, r, u) for k, r, _p, u, _n, _d in K.ITENS_PLANO]
    for (k, preco, _u, _r, visto), (_k, _r2, p, _u2, _n, _d) in zip(linhas, K.ITENS_PLANO):
        assert preco == ("" if p is None else f"{p:.2f}") and unescape(visto) == ("Quote" if p is None else usd(p)), k
    assert '<div class="car-totais" data-car-totais data-so-js hidden aria-live="polite">' in plano
    assert K.PLANO["nota"] in unescape(plano)
    assert "$100–230" not in plano and "$22" not in plano, "a taxa da pista do site é a do robô (dono, 20/10)"


def test_o_script_e_nosso_com_versao_e_nao_tem_preco(cli, html):
    m = re.search(r'<script src="(/_s/carreira\.js\?v=[0-9a-f]{10})" defer></script>', html)
    assert m, "o carreira.js entra como o winter.js: do próprio site, com a versão no endereço"
    r = cli.get(m.group(1))
    assert r.status_code == 200 and "javascript" in r.headers["content-type"]
    with open(os.path.join(STATIC, "carreira.js"), encoding="utf-8") as f:
        js = f.read()
    assert not re.search(r"\$\s?\d|\b(719|1200|2756|2688|2619)\b", js), "nenhum preço mora no script"
    assert "<script>" not in html.split("</head>")[1], "nenhum script inline"
    assert ' style="' not in _secao(html, "simulator")


def test_endereco_antigo_e_o_cartao_da_home(cli):
    r = cli.get("/plan-your-career/", follow_redirects=False)
    assert r.status_code == 301 and r.headers["location"] == "/career/"
    home = cli.get("/").text
    assert re.search(r'href="/career/#simulator"[^>]*>\s*Find your step', home), "o cartão da home vai direto ao simulador"
