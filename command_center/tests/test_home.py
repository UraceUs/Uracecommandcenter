"""A home, a About e a Programs do urace.us de 29/10 (#507), montadas por blocos: o texto de lá, o preço só do painel, os
links do site novo, o JSON-LD e o cartão da Winter que só aparece quando a página dela existe."""
import json
import os
import re
from datetime import datetime, timezone
from html import escape

import pytest

os.environ.setdefault("CC_AUTOSYNC", "0")
os.environ["URACE_ENV"] = "/nao/existe"

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api import vitrine  # noqa: E402
from command_center.api.main import app  # noqa: E402
from command_center.vitrine import blocos, conteudo as C, editor as ed, pg_home  # noqa: E402

SITE = "https://novo.urace.us"
TRES = ("/", "/about/", "/services/")


@pytest.fixture()
def cli(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path))
    monkeypatch.delenv("CC_SITE_HOSTS", raising=False)
    with TestClient(app, base_url=SITE) as t:
        yield t


def _main(html):
    return re.search(r'<main id="conteudo">(.*)</main>', html, re.S).group(1)


def _texto(html):
    """O texto que se lê na página: a marcação de dentro da frase (negrito, link) some; a de bloco vira espaço."""
    sem_inline = re.sub(r"</?(?:strong|em|b|a|span|small)\b[^>]*>", "", _main(html))
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", sem_inline))


def _lds(html):
    return [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]


def _titulos(html):
    return [re.sub(r"<[^>]+>", "", t) for t in re.findall(r"<h2[^>]*>(.*?)</h2>", _main(html), re.S)]


def test_as_tres_paginas_sao_as_do_urace_us_de_29_10(cli):
    """O título, a descrição, o h1 e as seções na ordem de lá (o que ficou de fora está na docstring de `pg_home`)."""
    home = cli.get("/")
    assert home.status_code == 200
    assert "<title>URACE | Professional Racing Team, Kart Academy &amp; Sim2Grid</title>" in home.text
    assert "<h1>The Champions Factory</h1>" in home.text
    assert _titulos(home.text) == ["On the top step", "Pick your line", "Where are you on track?",
                                   "Built around your level, not a template.", "Built by URACE", "Four steps. One team.",
                                   "Straight from the paddock", "Onboard: watch the method", "I’ve raced. I’ve won. I know the way.",
                                   "Read before you race", "Group events", "Box, box. Let’s talk."]
    texto = _texto(home.text)
    # (sem nome de piloto aqui: o repositório é público; o nome publicado fica só no conteúdo do site, `vitrine/`)
    for trecho in ("We don’t sell seat time.", "wins Saturday, podium Sunday. The whole crew on the grid.",
                   "Evaluation session, your data compared to our reference lap", "Same standard, different plan.",
                   "Multi national race winner · now racing USF200 Pro", "Your coach tells you when you are ready.",
                   "From karting to Formula 1", "moved to Florida and launched URACE, a karting team",
                   "For corporate teams, birthdays and groups."):
        assert trecho in texto, trecho
    about = cli.get("/about/").text
    assert "<title>About URACE - Professional Racing Team in Orlando</title>" in about
    assert "<h1>I’ve raced. I’ve won. I know the way.</h1>" in about
    assert _titulos(about) == ["Same standard. Different plan.", "On the top step", "Find your step"]
    assert "Steps, one team: Sim2Grid, Arrive and Drive, Academy, Racing Team" in _texto(about)
    programas = cli.get("/services/").text
    assert "<title>Programs: URACE Academy, Sim2Grid &amp; Racing Team | Orlando</title>" in programas
    assert "<h1>Kart racing in Orlando — from the simulator to the grid</h1>" in programas
    assert _titulos(programas) == ["Sim 2 Grid", "Arrive and Drive", "URACE Academy", "Racing Team",
                                   "Birthday party / Corporate Events", "Not sure which one is right?",
                                   "Do you still have questions?"]
    for pergunta in ("How will this work?", "What you are actually buying", "The experience", "The track",
                     "Why motorsport builds champions", "Your path: Arrive and Drive → Academy → Racing Team",
                     "Career planning, specialists &amp; add-on services", "Package includes"):
        assert f"<summary>{pergunta}</summary>" in programas, pergunta
    # as três vêm dos blocos (#502), não dos moldes de antes
    assert {c: blocos.registro()[c] for c in TRES} == {d["caminho"]: d for d in pg_home.PAGINAS}
    assert not set(TRES) & set(vitrine.PAGINAS)


def test_preco_so_do_painel_e_nenhum_escrito(cli, monkeypatch):
    """O "From" do Arrive and Drive é o menor preço de kart do painel, ao vivo; o resto de lá não tem número. Na Programs,
    o "What it will cost" do Sim2Grid são os cartões do painel."""
    from command_center.providers import cartoes_site
    monkeypatch.setattr(cartoes_site, "preco_kart", lambda con: 650)
    home = cli.get("/").text
    assert '<p class="plano-preco"><strong>From $650</strong></p>' in home
    for c in TRES:
        main = _main(cli.get(c).text)
        # tirado o preço dos cartões (do painel), não sobra nenhum "$" na página
        sem_painel = re.sub(r'<p class="plano-preco">.*?</p>', "", main, flags=re.S)
        assert not re.search(r"\$\s?\d", sem_painel), (c, re.findall(r".{40}\$\s?\d.{20}", sem_painel))
        texto = _texto(cli.get(c).text)
        for velho in ("$1,200", "$2,756.90", "$719", "$150", "$60", "$400", "$95", "$200", "38 reviews", "4.9"):
            assert velho not in texto, (c, velho)
    servicos = cli.get("/services/").text
    assert "What it will cost" in servicos and "$1,800" in servicos and "Apply for a place" in servicos, "os cartões do painel"


def test_avaliacoes_do_google_sao_as_da_508_sem_nota_escrita(cli):
    """As avaliações do Google vêm de `conteudo.AVALIACOES` (#508: uma fonte só, o texto e o nome como estão lá); na home
    vai também o quarto depoimento de lá. A nota e o número de avaliações não se escrevem (ficam velhos)."""
    for c, n in (("/", len(C.AVALIACOES) + 1), ("/about/", len(C.AVALIACOES))):
        main = _main(cli.get(c).text)
        assert main.count("<blockquote>") == n, c
        for nome, quem, texto in C.AVALIACOES:
            assert f"<footer>{escape(nome)} · {escape(quem)}</footer>" in main, (c, nome)
            assert texto in _texto(cli.get(c).text), (c, nome)
    assert pg_home.AARON[2] in _texto(cli.get("/").text) and pg_home.AARON[2] not in _texto(cli.get("/about/").text)


def test_programs_nao_traz_de_volta_o_que_o_dono_ja_mudou(cli):
    """A remarcação não sai na Programs (fica na página do programa, com 48 h desde 30/10, #527), idades dos karts de 08/10, a reserva do site (não o carrinho do WooCommerce), Kart School e
    Professional Coaching (#254) e o "Until then you cannot book" do Sim2Grid (#392)."""
    texto = _texto(cli.get("/services/").text)
    for velho in ("24h", "24 hours", "Add to Cart", "Age 11+", "Age 6-13", "Kart School", "Professional Coaching",
                  "Until then you cannot book", "representatives will reach out"):
        assert velho not in texto, velho
    assert "The rig opens on 1 November 2026." in texto and "Book your sim session" in texto


def test_links_sao_os_do_site_novo_e_todos_abrem(cli):
    """Os destinos de lá nos endereços do site novo (sem o 301 quando o novo existe); nenhum link volta ao WordPress e
    todo link interno abre (200, ou um 301 de landing que ainda não entrou para a página que abre)."""
    hrefs = {c: re.findall(r'href="([^"]+)"', _main(cli.get(c).text)) for c in TRES}
    todos = {h for hs in hrefs.values() for h in hs}
    assert not [h for h in todos if h.startswith(("https://urace.us", "http://"))]
    for velho in ("/plan-your-career/", "/urace-academy/", "/birthday-party/", "/corporate-events/",
                  "/group-events-social-gatherings/"):
        assert velho not in todos, velho
    for novo in ("/career/", "/academy/", "/services/birthday-party/", "/services/corporate-events/",
                 "/services/group-events/", "/sim2grid-racing-simulator/", "/professional-kart-team-racing-team/",
                 "/kart-training-packages/", pg_home.AD_RESERVA, "/about/", "/services/", "/contact/", "/blog/"):
        assert novo in todos, novo
    assert {"/kart-lessons-for-beginners/", C.LIGACAO} <= set(hrefs["/services/"])
    assert pg_home.CONVERSA_HOME in hrefs["/"] and C.LIGACAO in hrefs["/about/"]
    assert C.GOOGLE in hrefs["/"] and C.GOOGLE in hrefs["/about/"], "Read them all on Google"
    assert "https://www.youtube.com/watch?v=xMwAP1xlruc" in hrefs["/"], "vídeo é link (nada de player de fora)"
    for h in sorted(x.split("#")[0] for x in todos if x.startswith("/")):
        r = cli.get(h, follow_redirects=False)
        if r.status_code == 301:
            r = cli.get(r.headers["location"], follow_redirects=False)
        assert r.status_code == 200, h


def test_json_ld_do_negocio_da_marca_e_dos_programas(cli):
    home = {x["@type"] if isinstance(x["@type"], str) else "LocalBusiness": x for x in _lds(cli.get("/").text)}
    assert {"LocalBusiness", "Organization", "WebSite"} <= set(home) and "BreadcrumbList" not in home
    assert home["Organization"]["@id"] == f"{SITE}/#organization" and home["WebSite"]["publisher"]["@id"] == f"{SITE}/#organization"
    about = {x["@type"] if isinstance(x["@type"], str) else "LocalBusiness": x for x in _lds(cli.get("/about/").text)}
    assert [i["name"] for i in about["BreadcrumbList"]["itemListElement"]] == ["Home", "About"]
    lds = _lds(cli.get("/services/").text)
    programas = next(x for x in lds if x.get("@type") == "ItemList")
    assert [i["url"] for i in programas["itemListElement"]] == [f"{SITE}{c}" for _, c in pg_home.PROGRAMAS]
    faq = next(x for x in lds if x.get("@type") == "FAQPage")
    assert faq["mainEntity"][0]["name"] == "How will this work?"
    assert next(x for x in lds if x.get("@type") == "BreadcrumbList")["itemListElement"][-1]["name"] == "Programs"


def test_busca_do_wordpress_na_home_continua_indo_para_a_loja(cli):
    """#261: `/?s=` é a busca da loja. Com a home por blocos (registrada antes do resto), o redirecionamento vem antes."""
    r = cli.get("/?s=mxc", follow_redirects=False)
    assert r.status_code == 301 and r.headers["location"] == "/store/?s=mxc"


# ------------------------------------------------------------------ o cartão da Winter (#505)
WINTER = {"caminho": "/winter/", "titulo": "Race the Winter 2027 | URACE", "descricao": "x" * 90, "blocos": [
    {"tipo": "hero", "h1": "Race the Winter 2027"},
    {"tipo": "contador", "titulo": "Lights out", "alvo": "2027-01-15T08:00:00-05:00", "rotulo": "SKUSA Winter R1"}]}


def _registro_com(monkeypatch, *extras):
    """O registro das páginas por blocos sem a Winter de verdade (#505, outra frente) e com as `extras`."""
    paginas = {**{c: d for c, d in blocos.registro().items() if c != pg_home.WINTER}, **{d["caminho"]: d for d in extras}}
    monkeypatch.setattr(blocos, "registro", lambda: paginas)


def test_cartao_da_winter_so_aparece_com_a_pagina_dela(monkeypatch):
    """Sem a página da Winter, nada de link para um 404; com ela, o cartão leva a ela."""
    _registro_com(monkeypatch)
    sem = blocos.corpo("novo.urace.us", pg_home.HOME)
    assert 'href="/winter/"' not in sem and "Race the Winter 2027" not in sem
    assert "Plan your career" in sem and "From the sim to the grid" in sem
    _registro_com(monkeypatch, WINTER)
    com = blocos.corpo("novo.urace.us", pg_home.HOME)
    assert 'href="/winter/"' in com and "<h3>Race the Winter 2027</h3>" in com
    # a ordem de lá: a Winter primeiro
    assert com.index("Race the Winter 2027") < com.index("Plan your career") < com.index("From the sim to the grid")


@pytest.mark.parametrize("agora, rotulo", [
    ("2026-10-29T12:00:00+00:00", "78 days to lights out"),       # o mesmo "78" que o urace.us mostrava em 29/10
    ("2027-01-14T08:00:00-05:00", "1 day to lights out"),
    ("2027-01-15T07:59:00-05:00", "0 days to lights out"),
    ("2027-03-01T10:00:00-05:00", "0 days to lights out"),         # passou: não conta para trás
])
def test_dias_ate_a_largada_saem_do_contador_da_winter(monkeypatch, agora, rotulo):
    _registro_com(monkeypatch, WINTER)
    monkeypatch.setattr(pg_home, "_agora", lambda: datetime.fromisoformat(agora).astimezone(timezone.utc))
    html = blocos.corpo("novo.urace.us", pg_home.HOME)
    assert f'<p class="plano-sub">{rotulo}</p><h3>Race the Winter 2027</h3>' in html


@pytest.mark.parametrize("blocos_da_winter", [
    WINTER["blocos"][:1],                                                            # sem contador
    WINTER["blocos"][:1] + [{**WINTER["blocos"][1], "alvo": "2027-01-15T08:00:00"}],   # data sem fuso: não se sabe quando
])
def test_winter_sem_contador_com_data_fica_sem_o_rotulo(monkeypatch, blocos_da_winter):
    _registro_com(monkeypatch, {**WINTER, "blocos": blocos_da_winter})
    html = blocos.corpo("novo.urace.us", pg_home.HOME)
    assert "<h3>Race the Winter 2027</h3>" in html and "to lights out" not in html


def test_a_conferencia_ve_o_texto_do_cartao_da_winter():
    """O bloco da escolha é uma função (o cartão da Winter depende da página dela), mas o texto dele passa pela
    conferência como o de qualquer bloco: um preço escrito ali seria acusado."""
    estragado = {**pg_home.ESCOLHA, "itens": [{**pg_home.ESCOLHA["itens"][0], "texto": "Race the Winter from $999."}]}
    d = {**pg_home.HOME, "blocos": [b if b["tipo"] != "funcao" else {**b, "dados": estragado} for b in pg_home.HOME["blocos"]]}
    assert any("preço escrito" in p for p in blocos.problemas(d))


# ------------------------------------------------------------------ o editor do painel
def test_no_editor_o_preco_do_painel_na_home_fica_travado():
    """O "From $719" dos cartões por blocos não é texto que se escreve: a prévia de edição marca o bloco como do painel."""
    from command_center.api import editor_site as api_ed
    faixas = api_ed._original("/", api_ed._host(None))["secoes"]
    escada = next(s for s in faixas if "Four steps. One team." in s)
    assert '<p data-ed-trava="precos" class="plano-preco">' in ed.marcar_original(escada, 0)
    assert not [f.texto for s in faixas for f in ed._analisar(s)[0] if ed.PRECO.search(f.texto)]
