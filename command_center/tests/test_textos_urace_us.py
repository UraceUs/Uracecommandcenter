"""#508: o texto do urace.us de 29/10 nas páginas que o site novo já tinha (Academy, eventos, Pro Team, Contact e Career).

Dono, 29/10: *"sim, pode trazer o texto"*. As decisões anteriores continuam: preço só do painel, um caminho só para
reservar, Kart School virou URACE Academy.
"""
import html as h
import os
import re
from datetime import date

import pytest

os.environ.setdefault("CC_AUTOSYNC", "0")

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api.main import app  # noqa: E402
from command_center.vitrine import conteudo as C  # noqa: E402
from command_center.vitrine import paginas_site  # noqa: E402
from command_center.vitrine.paginas import preco_kart, usd  # noqa: E402

SITE = "https://novo.urace.us"
EVENTOS = ("/services/birthday-party/", "/services/corporate-events/", "/services/group-events/")


@pytest.fixture()
def cli(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path))
    monkeypatch.delenv("CC_SITE_HOSTS", raising=False)
    monkeypatch.delenv("CC_SITE_PREVIEW", raising=False)
    with TestClient(app, base_url=SITE) as t:
        yield t


def _titulo(html):
    return h.unescape(re.search(r"<title>([^<]*)</title>", html).group(1))


def _descricao(html):
    return h.unescape(re.search(r'<meta name="description" content="([^"]*)"', html).group(1))


def _agenda(html):
    """Os botões que abrem a agenda da equipe (o "Book a call" do urace.us), pelo rótulo."""
    return re.findall(rf'<a class="btn[^"]*" href="{re.escape(C.LIGACAO)}" rel="noopener">([^<]+)</a>', html)


def _avaliacoes(html):
    """Os nomes das avaliações do Google na seção delas, e se ela leva a todas."""
    m = re.search(r'<section class="faixa escura" aria-labelledby="h-google">(.*?)</section>', html, re.S)
    if not m:
        return [], False
    nomes = re.findall(r"<footer>([^<·]+?) · ", m.group(1))
    return [h.unescape(n) for n in nomes], f'href="{h.escape(C.GOOGLE)}"' in m.group(1)


NOMES = [n for n, _q, _t in C.AVALIACOES]


def test_titulos_e_descricoes_com_o_posicionamento_novo(cli):
    """Os títulos e as descrições do Yoast do urace.us de 29/10 ("Professional Racing Team")."""
    esperado = {
        "/academy/": ("URACE Academy: Kart School in Orlando | URACE", "URACE Academy is our kart school at Orlando Kart Center"),
        "/pro-team/": ("URACE: Professional Kart Racing Team in Florida", "runs race weekends in SKUSA, USPKS and Florida series"),
        "/contact/": ("Contact URACE - Professional Racing Team in Orlando", "Talk to URACE about URACE Academy, URACE Sim2Grid"),
        "/career/": ("Racing Career Path to F1, NASCAR, IMSA & IndyCar | URACE", "Plan a racing career step by step"),
    }
    for caminho, (titulo, trecho) in esperado.items():
        html = cli.get(caminho).text
        assert _titulo(html) == titulo, caminho
        assert trecho in _descricao(html), caminho
        assert len(_descricao(html)) <= 160, caminho
    # o contato diz onde e como ligar
    assert "10724 Cosmonaut Blvd. Call " + C.SITE["telefone"] in _descricao(cli.get("/contact/").text)


def test_academy_segue_a_pagina_de_hoje(cli):
    html = cli.get("/academy/").text
    assert re.findall(r"<h1[^>]*>([^<]+)</h1>", html) == ["URACE Academy. Kart school in Orlando."]
    assert "Step 3 · URACE Academy · Orlando" in html
    assert _agenda(html) == ["Talk to us"], "o segundo botão do hero abre a agenda"
    # currículo, planos (com âncora, os links "Pick your pace" do urace.us caem nela) e o "Not sure yet?"
    assert 'id="h-curr">Real coaching. Not just seat time.</h2>' in html
    assert re.search(r'<section [^>]*id="planos"><div class="largura">\s*<p class="eyebrow">Plans</p><h2 id="h-planos">Pick your pace</h2>', html)
    nao_sei = re.search(r"<h3>Not sure yet\?</h3>.*?</article>", html, re.S).group(0)
    assert f"<strong>{usd(preco_kart())}</strong>" in nao_sei, "o preço é o do Arrive and Drive no painel, nunca texto"
    assert 'href="/services/arrive-and-drive/#reservar"' in nao_sei
    assert _avaliacoes(html) == (NOMES, True)
    # a informação prática da página antiga fica na FAQ
    for pergunta in ("What the plan includes", "What to bring", "How joining works"):
        assert f">{pergunta}<" in html, pergunta
    assert "MUST wear long pants, closed toe shoes and a jacket." in html
    # o próximo degrau é o Racing Team
    assert re.search(r'id="h-fecho">When you are ready: the Racing Team</h2>.*?href="/pro-team/">See the Racing Team</a>', html, re.S)


@pytest.mark.parametrize("caminho", EVENTOS)
def test_eventos_tem_book_a_call_e_as_avaliacoes_do_google(cli, caminho):
    html = cli.get(caminho).text
    assert _agenda(html) == ["Book a call"], caminho
    assert _avaliacoes(html) == (NOMES, True), caminho


def test_pro_team_contact_e_career(cli):
    pro = cli.get("/pro-team/").text
    assert _agenda(pro) == ["Book a call"]
    assert _avaliacoes(pro) == (NOMES, True)
    assert 'id="h-cal">Next rounds on the calendar</h2>' in pro
    assert "SKAPA Winter Series" not in pro, "a prova de 18/10 já passou e não aparece como próxima"
    contato = cli.get("/contact/").text
    assert _agenda(contato) == ["Book a call"]
    career = cli.get("/career/").text
    assert '<p class="eyebrow">Career plan · Orlando</p>' in career
    assert "Every pro climbed the same ladder." in career


def test_calendario_so_mostra_a_prova_que_ainda_vem():
    cal = (("Oct 18, 2026", "A"), ("Nov 22, 2026", "B"), ("Jan–Mar 2027", "C"), ("To be confirmed", "D"))
    assert paginas_site._proximas(cal, date(2026, 10, 29)) == [cal[1], cal[2], cal[3]]
    assert paginas_site._proximas(cal, date(2026, 11, 22)) == [cal[1], cal[2], cal[3]], "no dia da prova ela ainda aparece"
    assert paginas_site._proximas(cal, date(2027, 3, 31)) == [cal[2], cal[3]], "o intervalo vale até o fim do último mês"
    assert paginas_site._proximas(cal, date(2027, 4, 1)) == [cal[3]], "o que não dá para ler fica"
    # sem prova por vir, a seção não sai
    d = {"calendario": cal[:3], "calendario_rotulo": "Where we are racing", "calendario_titulo": "Next rounds",
         "calendario_sub": ""}
    assert "<dt>Jan–Mar 2027</dt>" in paginas_site._calendario(d, date(2027, 3, 31))
    assert paginas_site._calendario(d, date(2027, 4, 1)) == ""


# ------------------------------------------------------------------ #521: as frentes juntas
LANDINGS_COM_RESULTADOS = ("/kart-lessons-for-beginners/", "/kart-driving-school/", "/kart-training-packages/",
                           "/professional-kart-team-racing-team/")


def _calendario_html(html):
    m = re.search(r'<dl class="calendario">(.*?)</dl>', html, re.S)
    return m.group(1) if m else ""


def test_calendario_do_racing_team_leva_a_winter_nas_duas_paginas(cli):
    """O "Race the winter →" do urace.us, agora que a /winter/ existe; o /pro-team/ e a landing leem a mesma lista."""
    listas = []
    for caminho in ("/pro-team/", "/professional-kart-team-racing-team/"):
        cal = _calendario_html(cli.get(caminho).text)
        assert re.search(r'<a href="/winter/">Race the winter →</a>', cal), caminho
        listas.append(re.findall(r"<dt>([^<]+)</dt>", cal))
    assert listas[0] == listas[1] and listas[0][-1] == "Jan–Mar 2027"
    assert cli.get("/winter/").status_code == 200


def test_resultados_da_temporada_iguais_na_academy_na_home_na_about_e_nas_landings(cli):
    titulos = [t for _f, _a, t, _x in C.RESULTADOS]
    for caminho in ("/academy/", "/", "/about/", *LANDINGS_COM_RESULTADOS):
        html = cli.get(caminho).text
        m = re.search(r'<section [^>]*id="top-step"[^>]*>.*?</section>|<section [^>]*>(?:(?!</section>).)*On the top step.*?</section>',
                      html, re.S)
        assert m, caminho
        secao = h.unescape(m.group(0))
        for (foto, alt, titulo, texto) in C.RESULTADOS:
            assert titulo in secao and texto in secao and alt in secao, (caminho, titulo)
            assert re.search(rf'<img src="/_s/img/{re.escape(foto)}\?v=\w+" alt="[^"]*" width="\d+" height="\d+" loading="lazy"',
                             m.group(0)), (caminho, foto)
        assert [t for t in titulos if t in secao] == titulos, caminho
    # na Academy: um h1, a seção com h2 e os resultados em h3 (sem pular nível)
    academy = cli.get("/academy/").text
    assert academy.count("<h1") == 1
    assert re.search(r'<h2 id="h-b1">On the top step</h2>.*?<h3>P1 \+ P3 · Bushnell, Florida</h3>', academy, re.S)
