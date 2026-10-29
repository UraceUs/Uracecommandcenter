"""#394 (dono, 22/10): o menu em dropdown do site (o da KartSport) e as animações do urace.us.

O menu aprovado: Urace Academy, For Beginners, Store e About abrem (⌄); conta, busca da loja e carrinho em ícones;
"Book now" vermelho. Nenhum link de hoje some do site, a Store só mostra categoria que tem produto, e toda
animação é transform/opacity com os tokens e desliga com prefers-reduced-motion."""
import os
import re

import pytest

os.environ["URACE_ENV"] = "/nao/existe"

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api.main import app  # noqa: E402
from command_center.vitrine import conteudo, paginas, paginas_site  # noqa: E402

SITE = "https://novo.urace.us"
STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vitrine", "static")


@pytest.fixture()
def cli(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path))
    monkeypatch.delenv("CC_SITE_HOSTS", raising=False)
    monkeypatch.delenv("CC_SITE_PREVIEW", raising=False)
    with TestClient(app, base_url=SITE) as t:
        yield t


def _menu(html):
    return html.split('<nav class="menu" aria-label="Main" data-menu>')[1].split("</nav>")[0]


def _grupos(menu):
    """[(título, link, id da caixa, aria-expanded, aria-controls, [(rótulo, link), …])] do menu do computador."""
    out = []
    for g in re.findall(r'<li class="grupo[^"]*" data-grupo>(.*?)</ul></li>', menu, re.S):
        tit = re.search(r'<a class="grupo-t" href="([^"]+)"[^>]*>([^<]+)</a>', g)
        bot = re.search(r'<button type="button" class="grupo-abre" aria-expanded="(\w+)" aria-controls="([\w-]+)"', g)
        caixa = re.search(r'<ul class="grupo-itens" id="([\w-]+)">', g)
        subs = re.findall(r'<li><a href="([^"]+)"[^>]*>([^<]+)</a></li>', g)
        out.append((tit.group(2), tit.group(1), caixa.group(1), bot.group(1), bot.group(2), [(r, h) for h, r in subs]))
    return out


def test_menu_em_quatro_grupos_com_o_botao_que_abre_e_aria(cli):
    """O topo do dono: quatro grupos, cada título leva à página dele e o ⌄ é um botão com `aria-expanded` que
    controla a caixa (`aria-controls` = id da lista). Sim 2 Grid vai para a página própria (#392)."""
    gs = _grupos(_menu(cli.get("/").text))
    assert [(t, h) for t, h, *_ in gs] == [("URACE Academy", "/academy/"), ("For Beginners", "/for-beginners/"),
                                           ("Store", "/store/"), ("About", "/about/")]
    for tit, _, caixa, expandido, controla, _ in gs:
        assert expandido == "false" and controla == caixa, tit
    subs = {t: s for t, _, _, _, _, s in gs}
    assert subs["URACE Academy"] == [("Academy", "/academy/"), ("Racing Team", "/pro-team/"),
                                     ("Arrive and Drive", "/services/arrive-and-drive/")]
    assert subs["For Beginners"] == [("Sim 2 Grid", "/sim2grid-racing-simulator/"), ("Plan Your Career", "/career/")]
    assert subs["About"] == [("About URACE", "/about/"), ("Blog", "/blog/"), ("Contact us", "/contact/")]
    # a loja de hoje tem produto nas seis categorias do menu
    assert subs["Store"] == [("Engines", "/store/engines/"), ("Chassis", "/store/chassis/"), ("Tires", "/store/tires/"),
                             ("Parts", "/store/parts/"), ("Apparel", "/store/official-urace-products/"),
                             ("Suits", "/store/custom-kart-suits/")]


def test_store_do_menu_so_mostra_categoria_que_tem_produto():
    """Categoria sem produto não entra no menu (o link levaria a uma loja vazia); as que têm, entram com o link de
    categoria que a loja já usa (`/store/<categoria>/`). O alias do WooCommerce (suits) conta como a categoria dele."""
    so = [{"slug": "a", "categories": [{"slug": "engines"}]}, {"slug": "b", "categories": [{"slug": "suits"}]}]
    marca = paginas_site.PRODUTOS.set(lambda: so)
    try:
        topo = paginas._cabecalho("/")
    finally:
        paginas_site.PRODUTOS.reset(marca)
    loja = next(s for t, *_, s in _grupos(_menu(topo)) if t == "Store")
    assert loja == [("Engines", "/store/engines/"), ("Suits", "/store/custom-kart-suits/")]
    cel = topo.split('aria-label="Main (mobile)"')[1]
    assert "/store/tires/" not in topo and "/store/chassis/" not in cel and 'href="/store/engines/"' in cel


def test_icones_conta_busca_carrinho_e_book_now_vermelho(cli):
    """À direita: conta (portal), a busca da loja (o campo que a loja já tem) e o carrinho com o contador; e o
    "Book now" vermelho leva à reserva, a mesma dos botões de reservar do site."""
    html = cli.get("/about/").text
    topo = html.split('<header class="topo" data-topo>')[1].split("</header>")[0]
    assert '<a class="icone conta" href="/ops/portal" aria-label="My account">' in topo
    assert '<a class="icone busca" href="/store/#loja-s" aria-label="Search the store">' in topo
    assert re.search(r'<a class="icone carrinho-topo" href="/cart/" aria-label="Cart">.*?data-carrinho-n', topo, re.S)
    assert '<a class="btn btn-sm btn-reservar" href="/services/arrive-and-drive/#reservar">Book now</a>' in topo
    assert 'href="/services/arrive-and-drive/#reservar">Book Arrive and Drive</a>' in cli.get("/").text   # #507
    assert 'id="loja-s"' in cli.get("/store/").text, "o ícone leva ao campo de busca que existe"


def test_menu_do_celular_tem_os_mesmos_links_em_grupos_que_abrem():
    """Celular: o menu de tela cheia é um <details>; cada grupo é um <details> que abre e fecha no toque (sem JS). O
    título do grupo vira o primeiro link, sem repetir subitem; o grupo da página aberta já vem aberto."""
    topo = paginas._cabecalho("/career/")
    desk, cel = _menu(topo), topo.split('aria-label="Main (mobile)">')[1].split("</nav>")[0]
    assert cel.count('<details class="grupo-cel"') == 4
    assert set(re.findall(r'href="([^"]+)"', desk)) <= set(re.findall(r'href="([^"]+)"', cel))
    assert '<details class="grupo-cel" open><summary>For Beginners' in cel
    assert cel.count('href="/about/"') == 1 and cel.count('href="/for-beginners/"') == 1
    assert 'href="/ops/portal">My account</a>' in cel and 'href="/store/#loja-s">Search the store</a>' in cel
    assert '<a aria-current="page"' not in desk and 'href="/career/" aria-current="page"' in desk


def test_nenhum_link_do_menu_de_antes_some_do_site(cli):
    """Os onze links do topo de antes (#207) seguem na página: no dropdown, no rodapé ou no corpo. O "Sim 2 Grid"
    agora vai para a página própria (#392)."""
    antes = ("/about/", "/services/", "/career/", "/for-beginners/", conteudo.SIM2GRID, "/services/arrive-and-drive/",
             "/academy/", "/pro-team/", "/store/", "/blog/", "/contact/")
    for c in ("/", "/about/", "/store/"):
        links = set(re.findall(r'href="([^"]+)"', cli.get(c).text))
        assert not [h for h in antes if h not in links], c


def test_todas_as_paginas_levam_o_menu_novo_e_o_site_js(cli):
    for c in ("/", "/services/", "/academy/", "/blog/", "/store/", "/contact/", "/cart/"):
        html = cli.get(c).text
        assert 'data-menu' in html and 'class="grupo-abre"' in html and 'class="menu-cel"' in html, c
        assert re.search(r'<script src="/_s/site\.js\?v=\w+" defer></script>', html), c


def _css():
    with open(os.path.join(STATIC, "site.css"), encoding="utf-8") as f:
        return f.read()


def test_animacoes_so_transform_e_opacidade_com_os_tokens():
    """Motion do CLAUDE.md: as animações novas só mexem em transform/opacity, com as durações dos tokens."""
    css = _css()
    for nome, corpo in re.findall(r"@keyframes ([\w-]+) \{(.*?\})\s*\}", css, re.S):
        props = set(re.findall(r"([a-z-]+)\s*:", corpo))
        assert props <= {"opacity", "transform"}, (nome, props)
    for k in ("menu-desce", "reservar-pulso"):
        assert f"@keyframes {k}" in css
    for anim in re.findall(r"animation: ([^;}]+)", css):
        if "none" not in anim:
            assert re.search(r"var\(--dur[\w-]*\)", anim), anim
    assert "--dur-surge:" in css and "--dur-pulso:" in css
    # botão sobe 2 px, cartão sobe 4 px (a sombra acende por opacidade)
    assert ".btn:hover { transform: translateY(-2px)" in css
    assert re.search(r"\.produto-card a:hover \{ transform: translateY\(-4px\) \}", css)


def test_reduced_motion_desliga_o_que_nao_e_essencial():
    css = _css()
    blocos = re.findall(r"@media \(prefers-reduced-motion: reduce\) \{(.*?)\n\}", css, re.S)
    tudo = "\n".join(blocos)
    assert "animation: none !important" in tudo and "transition: none !important" in tudo
    assert re.search(r"\.surge \{ opacity: 1; transform: none \}", tudo), "a seção nunca fica escondida"
    assert ".btn-reservar::after { display: none }" in tudo and ".produto-card a:hover" in tudo
    with open(os.path.join(STATIC, "site.js"), encoding="utf-8") as f:
        js = f.read()
    # sem IntersectionObserver ou com reduced-motion, nenhuma seção ganha `.surge` (nada se esconde sem JS)
    assert "prefers-reduced-motion: reduce" in js and "if (!calmo && 'IntersectionObserver' in window)" in js
    assert "classList.add('surge')" in js
