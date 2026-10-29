"""As landings do urace.us no site novo (#506): os nove endereços abrem a página (antes eram 301 ou 404), com o título,
a descrição e o `noindex` da página de hoje; o formulário cai em Vendas, o do Arrive & Drive e o da Driver Factory vão
para o obrigado; a página de reserva leva à reserva do site; o preço é o do painel."""
import os
import re
import xml.etree.ElementTree as ET

import pytest

os.environ.setdefault("CC_AUTOSYNC", "0")

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api import vitrine  # noqa: E402
from command_center.api.main import app  # noqa: E402
from command_center.db import aplicar_schema, conectar  # noqa: E402
from command_center.tests.test_vitrine import _le  # noqa: E402
from command_center.vitrine import blocos, paginas_site  # noqa: E402

SITE = "https://novo.urace.us"
OBRIGADO_AD, OBRIGADO_DF = "/arrive-and-drive-karting-thank-you/", "/the-driver-factory-thank-you-page/"

# (caminho, título, no Google?) — como no urace.us lido em 29/10
LANDINGS = (
    ("/kart-lessons-for-beginners/", "Kart Lessons for Beginners in Orlando | URACE", True),
    ("/kart-driving-school/", "Kart Driving Lessons in Orlando, FL | URACE Academy", True),
    ("/kart-training-packages/", "Kart Training Packages: Monthly URACE Academy in Orlando", True),
    ("/professional-kart-team-racing-team/", "URACE Race Team Support with a Pro Coach | Orlando", True),
    ("/arrive-and-drive-karting-experience/", "Arrive & Drive Karting Experience in Orlando | URACE", False),
    ("/arrive-and-drive-karting-booking/", "Book Arrive & Drive Karting in Orlando | URACE", False),
    (OBRIGADO_AD, "Thank you | Arrive & Drive Karting Experience | URACE", False),
    ("/the-driver-factory/", "How to Become a Professional Racing Driver | URACE Orlando", True),
    (OBRIGADO_DF, "The driver factory thank you page - URACE", False),
)
CAMINHOS = [c for c, _t, _i in LANDINGS]

# (página, assunto → serviço em Vendas, para onde vai depois de enviar, campos a mais) — os formulários das landings
FORMULARIOS = (
    ("/kart-lessons-for-beginners/", "Arrive and Drive", None,
     {"x_option": "A - I only want to try it", "x_previous_experience": "No previous experience"}),
    ("/kart-driving-school/", "Arrive and Drive", None, {"x_previous_experience": "Recreational karting experience"}),
    ("/kart-training-packages/", "URACE Academy", None, {"x_option": "B - I am new to the sport"}),
    ("/professional-kart-team-racing-team/", "Racing Team", None, {"x_previous_experience": "Currently competing in races"}),
    ("/arrive-and-drive-karting-experience/", "Arrive and Drive", OBRIGADO_AD,
     {"x_experience_for": "My child", "x_driver_age": "9", "x_karting_experience": "None, this would be my first time"}),
    ("/the-driver-factory/", "URACE Academy", OBRIGADO_DF, {"x_address": "Orlando, FL"}),
)


@pytest.fixture()
def cli(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path))
    monkeypatch.setenv("CC_EMAIL_FAKE", str(tmp_path / "emails.jsonl"))
    monkeypatch.setenv("CC_SITE_PREVIEW", "0")          # fora da prévia: o `noindex` é o da página, não o do site todo
    monkeypatch.delenv("CC_SITE_HOSTS", raising=False)
    vitrine._envios.clear()
    with TestClient(app, base_url=SITE) as t:
        yield t
    vitrine._envios.clear()            # o limite do formulário é da memória do processo: não vaza para o próximo teste


def _pagina(cli, caminho):
    """A própria landing (sem seguir 301: antes desta issue o endereço levava a outra página, ou dava 404)."""
    r = cli.get(caminho, follow_redirects=False)
    assert r.status_code == 200, (caminho, r.status_code)
    return r.text


def test_as_nove_estao_registradas_e_passam_na_conferencia():
    reg = blocos.registro()
    for c in CAMINHOS:
        assert c in reg, c
        assert blocos.problemas(reg[c]) == [], c


@pytest.mark.parametrize("caminho, titulo, indexar", LANDINGS)
def test_cada_landing_abre_com_o_titulo_e_o_noindex_de_hoje(cli, caminho, titulo, indexar):
    """Antes: 301 para For Beginners, Academy, Pro Team e Career, ou 404 (as do Arrive & Drive e os obrigados)."""
    r = cli.get(caminho, follow_redirects=False)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html"), r.status_code
    p = _le(r.text)
    assert [n for n, _ in p.h].count("h1") == 1, "um h1 por página"
    niveis = [int(n[1]) for n, _ in p.h]
    assert all(b - a <= 1 for a, b in zip(niveis, niveis[1:])), "sem pular nível de título"
    assert re.search(r"<title>([^<]+)</title>", r.text).group(1) == titulo.replace("&", "&amp;")
    metas = {a.get("name"): a.get("content") for t, a in p.attrs if t == "meta"}
    assert len(metas["description"]) >= 50
    robots = metas.get("robots")
    assert (robots is None) if indexar else (robots == "noindex, nofollow"), robots
    assert [a["href"] for t, a in p.attrs if t == "link" and a.get("rel") == "canonical"] == [SITE + caminho]
    assert "style=" not in r.text and "script-src 'self'" in r.headers["content-security-policy"]
    imgs = re.findall(r"<img [^>]+>", r.text)
    assert all('width="' in i and 'height="' in i for i in imgs)


def test_sitemap_tem_as_do_google_e_nao_as_noindex(cli):
    locs = {u.text for u in ET.fromstring(cli.get("/sitemap.xml").content).iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")}
    for caminho, _t, indexar in LANDINGS:
        assert (SITE + caminho in locs) == indexar, caminho


def test_os_301_antigos_destes_enderecos_sairam(cli):
    """O mapa do urace.us de hoje não manda mais estes endereços para outra página (nem com a barra faltando)."""
    mapa = paginas_site.redirecionamentos()
    for c in CAMINHOS:
        assert c not in mapa and paginas_site.destino(c) is None, c
        r = cli.get(c.rstrip("/"), follow_redirects=False)
        assert r.status_code == 301 and r.headers["location"] == c, "sem a barra final: a própria página"


def test_titulo_e_descricao_nao_se_repetem_com_o_career(cli):
    """O /career/ herdou (#207) o título e a descrição da Driver Factory; com ela de volta, ficou com os do /plan-your-career/."""
    def meta(c):
        html = cli.get(c).text
        return re.search(r"<title>([^<]+)</title>", html).group(1), re.search(r'name="description" content="([^"]+)"', html).group(1)
    assert meta("/the-driver-factory/") != meta("/career/")
    assert meta("/career/")[0] == "Racing Career Path to F1, NASCAR, IMSA &amp; IndyCar | URACE"
    assert cli.get("/plan-your-career/", follow_redirects=False).headers["location"] == "/career/"


@pytest.mark.parametrize("caminho", CAMINHOS)
def test_preco_so_do_painel(cli, caminho):
    """O único valor em dólar das landings é o "a partir de" do kart, e ele é o do painel: o gerente muda no painel e a
    página muda junto. Academy, Boost, Sim2Grid, depósito e as opções do formulário saem sem número."""
    con = conectar(); aplicar_schema(con)
    con.execute("UPDATE booking_services SET price=650 WHERE site_kart IN ('Baby Kart', '4-stroke')")
    con.commit(); con.close()
    texto = re.sub(r"<[^>]+>", " ", _pagina(cli, caminho))
    assert set(re.findall(r"\$\s?[\d,.]+", texto)) <= {"$650"}, caminho
    for valor in ("$719", "$400", "$2,756.90", "$2756.90", "$5,000", "$5000", "$1,200", "$625", "$3K", "$5K", "$769"):
        assert valor not in texto, (caminho, valor)
    if caminho in ("/kart-lessons-for-beginners/", "/kart-driving-school/", "/arrive-and-drive-karting-experience/",
                   "/arrive-and-drive-karting-booking/", "/the-driver-factory/"):
        assert "From $650" in texto, "o cartão do Arrive and Drive mostra o preço do painel"


@pytest.mark.parametrize("pagina, servico, obrigado, extras", FORMULARIOS)
def test_formulario_da_landing_cai_em_vendas(cli, pagina, servico, obrigado, extras):
    html = _pagina(cli, pagina)
    assert html.count('<form class="form-contato"') == 1 and f'name="volta" value="{pagina}"' in html
    assert (f'data-obrigado="{obrigado}"' in html) == bool(obrigado)
    for nome in extras:
        assert f'name="{nome}"' in html, nome
    assunto = re.search(r'name="assunto" value="([^"]+)"', html).group(1)
    corpo = {"nome": "Davi Rocha", "email": "davi@example.com", "telefone": "407 555 0123", "assunto": assunto,
             "volta": pagina, **({"obrigado": obrigado} if obrigado else {}), **extras}
    r = cli.post("/ops/api/vitrine/contato", data=corpo, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == (obrigado or pagina + "?sent=1")
    con = conectar(); aplicar_schema(con)
    o = con.execute("SELECT name, service, source, notes FROM opportunities").fetchone()
    assert (o["name"], o["service"], o["source"]) == ("Davi Rocha", servico, "Site")
    for nome, valor in extras.items():
        assert f"{nome[2:].replace('_', ' ').capitalize()}: {valor}" in o["notes"], nome
    if obrigado:
        _pagina(cli, obrigado)


def test_formulario_do_arrive_and_drive_pede_o_que_a_pagina_de_hoje_pede(cli):
    html = _pagina(cli, "/arrive-and-drive-karting-experience/")
    form = html[html.index('<form class="form-contato"'):html.index("</form>")]
    for trecho in ('<select name="x_experience_for" required>', "<option>My child</option>",
                   'name="x_driver_age" type="number" min="1" max="120"', '<select name="x_karting_experience" required>',
                   "<option>Some competitive karting</option>", "Anything you’d like us to know?",
                   ">Email my track-day inquiry</button>"):
        assert trecho in form, trecho
    # "Your email app will open…" era do formulário antigo: aqui o pedido cai em Vendas
    assert "email app" not in html


def test_a_pagina_de_reserva_leva_a_reserva_do_site(cli):
    """A do urace.us é uma agenda (kart, dia, Lead and Follow e o checkout do WooCommerce). No site novo a reserva é uma
    só (dono, 15/10, #262): agenda + carrinho + Stripe, com o preço do painel. Nada de formulário aqui."""
    html = _pagina(cli, "/arrive-and-drive-karting-booking/")
    assert "<form" not in html
    botoes = re.findall(r'<a class="btn[^"]*" href="([^"]+)"[^>]*>Plan my first track day</a>', html)
    assert botoes and set(botoes) == {"/services/arrive-and-drive/#reservar"}
    assert 'id="reservar"' in cli.get("/services/arrive-and-drive/").text


@pytest.mark.parametrize("caminho", CAMINHOS)
def test_nenhum_link_da_landing_quebra_nem_volta_ao_wordpress(cli, caminho):
    html = _pagina(cli, caminho)
    corpo = html[html.index('<main id="conteudo">'):html.index("</main>")]
    assert "urace.us/" not in corpo.replace("novo.urace.us", "")
    ids = set(re.findall(r' id="([^"]+)"', html))
    for h in sorted(set(re.findall(r'href="([^"]+)"', corpo))):
        if h.startswith("#"):
            assert h[1:] in ids, (caminho, h)
        elif h.startswith("/"):
            alvo, _, ancora = h.partition("#")
            r = cli.get(alvo, follow_redirects=False)
            if r.status_code == 301:
                r = cli.get(r.headers["location"], follow_redirects=False)
            assert r.status_code == 200, (caminho, h)
            if ancora:
                assert f'id="{ancora}"' in r.text, (caminho, h)
        else:
            assert h.startswith(("https://", "tel:+1407")), (caminho, h)


def test_avaliacoes_com_link_para_o_google_e_sem_numero_a_mao(cli):
    """Nota e número de avaliações ficam velhos: a página leva ao Google, não escreve "4.9 · 38 reviews"."""
    html = _pagina(cli, "/kart-lessons-for-beginners/")
    assert 'href="https://www.google.com/maps/place/URACE/' in html and "Read them all on Google" in html
    assert not re.search(r"\b\d+ reviews\b|4\.9", html)
