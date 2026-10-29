"""Páginas montadas por blocos (#502): o desenho, a conferência (preço só do painel), a rota, o sitemap e o formulário."""
import json
import os
import re

import pytest

os.environ.setdefault("CC_AUTOSYNC", "0")

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api import vitrine  # noqa: E402
from command_center.api.main import app  # noqa: E402
from command_center.db import aplicar_schema, conectar  # noqa: E402
from command_center.tests.test_vitrine import _le  # noqa: E402
from command_center.vitrine import blocos  # noqa: E402

FOTO = "arrive-and-drive-hero.webp"

EXEMPLO = {
    "caminho": "/exemplo-blocos/", "titulo": "Example blocks page | URACE",
    "descricao": "An example page built from blocks, used by the tests of the block renderer of the URACE site.",
    "blocos": [
        {"tipo": "hero", "eyebrow": "URACE · Orlando", "h1": "The Champions Factory", "sub": "We run our own drivers.",
         "ctas": [("Book a session", "/services/arrive-and-drive/"), ("Talk to us", "/contact/")], "foto": FOTO,
         "alt": "Karts on track", "nota": "Opening November 1"},
        {"tipo": "texto", "eyebrow": "The method", "titulo": "Built around your level",
         "paragrafos": ["Day one we pull your data. [Call us](tel:+14072502291) or **read on**."], "lista": ["Data", "Video"],
         "foto": FOTO, "alt": "Coach and driver"},
        {"tipo": "cartoes", "titulo": "Pick your line", "itens": [
            {"rotulo": "Step 1", "titulo": "Arrive and Drive", "texto": "A real race kart.", "preco": "kart",
             "link": ("Book", "/services/arrive-and-drive/")},
            {"titulo": "Academy", "texto": "Monthly training.", "link": ("See the Academy", "/academy/")}]},
        {"tipo": "cartoes", "fundo": "escura", "titulo": "Where are you on track?", "itens": [
            {"titulo": "First time in a kart", "texto": "Fundamentals.", "link": ("Book", "/services/arrive-and-drive/")}]},
        {"tipo": "passos", "titulo": "Four steps. One team.", "itens": [("Sim2Grid", "Learn the lines."), ("Academy", "Monthly.")]},
        {"tipo": "numeros", "titulo": "Since 2004", "itens": [("+300", "Drivers trained"), ("+500", "Race wins")]},
        {"tipo": "figuras", "titulo": "Built by URACE", "itens": [{"foto": FOTO, "alt": "A driver", "titulo": "A driver", "legenda": "P1"}]},
        {"tipo": "depoimentos", "titulo": "What drivers say", "itens": [("Ana Lima", "Parent", "Great coaching.")],
         "link": ("Read them all on Google", "https://www.google.com/maps/place/URACE")},
        {"tipo": "videos", "titulo": "Onboard", "itens": [("From karting to Formula 1", "https://www.youtube.com/watch?v=xMwAP1xlruc")]},
        {"tipo": "definicoes", "titulo": "The calendar", "itens": [("R1–2 · Jan 15–17", "Orlando Kart Center")]},
        {"tipo": "faq", "titulo": "Before you book", "itens": [("Do I need experience?", "No."), ("Where?", ("Orlando.", "OKC."))]},
        {"tipo": "contador", "titulo": "Lights out", "alvo": "2027-01-15T08:00:00-05:00", "rotulo": "SKUSA Winter R1 · 15 Jan 2027"},
        {"tipo": "formulario", "titulo": "Tell us about the driver", "assunto": "team", "enviar": "Send", "mensagem": "Anything else?"},
        {"tipo": "posts", "titulo": "Read before you race"},
        {"tipo": "cta", "titulo": "Box, box. Let’s talk.", "texto": "Tell us who the driver is.", "ctas": [("Get in touch", "/contact/")]},
    ],
}


def test_o_exemplo_passa_na_conferencia_e_desenha_cada_bloco():
    assert blocos.problemas(EXEMPLO) == []
    html = blocos.corpo("novo.urace.us", EXEMPLO)
    assert html.count("<h1>") == 1
    # toda seção cita um título que existe
    for alvo in re.findall(r'aria-labelledby="([^"]+)"', html):
        assert f'id="{alvo}"' in html, alvo
    # títulos sem pular nível (h1 → h2 → h3)
    niveis = [int(n) for n in re.findall(r"<h([1-6])", html)]
    assert niveis[0] == 1 and all(b - a <= 1 for a, b in zip(niveis, niveis[1:]))
    # o preço é o do painel, não texto
    assert "From $719" in html
    # texto com link e negrito, e nada de estilo ou script inline
    assert '<a href="tel:+14072502291">Call us</a>' in html and "<strong>read on</strong>" in html
    assert "style=" not in html and "<script" not in html
    # foto com tamanho; só a do hero sem lazy
    imgs = re.findall(r"<img [^>]+>", html)
    assert all('width="' in i and 'height="' in i for i in imgs)
    assert sum('fetchpriority="high"' in i for i in imgs) == 1 and sum('loading="lazy"' in i for i in imgs) == len(imgs) - 1
    # link de fora abre sem levar o site junto
    assert 'href="https://www.youtube.com/watch?v=xMwAP1xlruc" rel="noopener"' in html
    assert 'data-alvo="2027-01-15T08:00:00-05:00"' in html
    assert 'name="volta" value="/exemplo-blocos/"' in html


def test_faq_vira_json_ld_e_a_trilha_leva_a_pagina():
    ld = json.loads(blocos.json_ld(EXEMPLO))
    faq = next(x for x in ld if x["@type"] == "FAQPage")
    assert [q["name"] for q in faq["mainEntity"]] == ["Do I need experience?", "Where?"]
    assert faq["mainEntity"][1]["acceptedAnswer"]["text"] == "Orlando. OKC."
    trilha = next(x for x in ld if x["@type"] == "BreadcrumbList")
    assert trilha["itemListElement"][-1]["item"] == "https://novo.urace.us/exemplo-blocos/"


@pytest.mark.parametrize("estrago,acusa", [
    ({"descricao": ""}, "título e descrição"),
    ({"blocos": EXEMPLO["blocos"] + [{"tipo": "hero", "h1": "Outro"}]}, "um hero"),
    ({"blocos": EXEMPLO["blocos"][:1] + [{"tipo": "texto", "titulo": "Price", "paragrafos": ["Sessions from $719."]}]}, "preço escrito"),
    ({"blocos": EXEMPLO["blocos"][:1] + [{"tipo": "cartoes", "itens": [{"titulo": "x", "preco": "1200"}]}]}, "preço sem fonte"),
    ({"blocos": EXEMPLO["blocos"][:1] + [{"tipo": "carrossel"}]}, "tipo 'carrossel'"),
])
def test_conferencia_acusa_o_que_nao_pode_ir_ao_ar(estrago, acusa):
    assert any(acusa in p for p in blocos.problemas({**EXEMPLO, **estrago}))


@pytest.mark.parametrize("link", ["javascript:alert(1)", "//outro.example/x", "http://outro.example", "data:text/html,x"])
def test_link_fora_da_regra_nao_desenha(link):
    with pytest.raises(blocos.ErroBloco):
        blocos.inline(f"[x]({link})")


def test_foto_que_nao_existe_nao_desenha():
    with pytest.raises(blocos.ErroBloco):
        blocos.img("nao-existe.webp", "x")


def test_toda_pagina_registrada_passa_na_conferencia_e_desenha():
    """Cada `pg_*.py` que entrar: sem preço escrito, um h1, título único, e o desenho não quebra."""
    titulos = set()
    for caminho, d in blocos.registro().items():
        assert blocos.problemas(d) == [], caminho
        assert d["titulo"] not in titulos, f"título repetido: {d['titulo']}"
        titulos.add(d["titulo"])
        assert blocos.corpo("novo.urace.us", d).count("<h1>") == 1


# ------------------------------------------------------------------ na rota
@pytest.fixture()
def cli(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path))
    monkeypatch.setenv("CC_EMAIL_FAKE", str(tmp_path / "emails.jsonl"))
    monkeypatch.delenv("CC_SITE_HOSTS", raising=False)
    vitrine._envios.clear()
    oculta = {**EXEMPLO, "caminho": "/exemplo-oculto/", "titulo": "Hidden example | URACE", "indexar": False}
    monkeypatch.setattr(blocos, "registro", lambda: {EXEMPLO["caminho"]: EXEMPLO, oculta["caminho"]: oculta})
    with TestClient(app, base_url="https://novo.urace.us") as t:
        yield t
    vitrine._envios.clear()            # o limite do formulário é da memória do processo: não vaza para o próximo teste


def test_a_pagina_por_blocos_responde_e_entra_no_sitemap(cli):
    r = cli.get("/exemplo-blocos/")
    assert r.status_code == 200 and "The Champions Factory" in r.text
    p = _le(r.text)
    assert [n for n, _ in p.h].count("h1") == 1
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert re.search(r'<script src="/_s/blocos\.js\?v=[0-9a-f]+" defer></script>', r.text), "o contador"
    assert re.search(r'<script src="/_s/contato\.js\?v=[0-9a-f]+" defer></script>', r.text), "o formulário"
    mapa = cli.get("/sitemap.xml").text
    assert "/exemplo-blocos/</loc>" in mapa and "/exemplo-oculto/" not in mapa, "noindex fica fora do sitemap"
    assert 'content="noindex' in cli.get("/exemplo-oculto/").text
    assert cli.get("/exemplo-blocos", follow_redirects=False).headers["location"] == "/exemplo-blocos/"
    assert vitrine.html_da_pagina("/exemplo-blocos/", "novo.urace.us") is not None, "o editor do painel abre a página"


def test_o_formulario_da_pagina_cai_em_vendas_e_volta_para_ela(cli):
    r = cli.post("/ops/api/vitrine/contato", data={"nome": "Davi Rocha", "email": "davi@example.com", "assunto": "team",
                                                  "volta": "/exemplo-blocos/"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/exemplo-blocos/?sent=1"
    assert "aviso-ok" in cli.get("/exemplo-blocos/?sent=1").text
    con = conectar(); aplicar_schema(con)
    o = con.execute("SELECT name, service, notes FROM opportunities").fetchone()
    assert o["name"] == "Davi Rocha" and "/exemplo-blocos/" in o["notes"]
    # volta para uma página que não é do site: cai no contato
    r = cli.post("/ops/api/vitrine/contato", data={"nome": "Eva Reis", "email": "eva@example.com", "mensagem": "Hi there",
                                                  "volta": "https://outro.example/"}, follow_redirects=False)
    assert r.headers["location"] == "/contact/?sent=1"
