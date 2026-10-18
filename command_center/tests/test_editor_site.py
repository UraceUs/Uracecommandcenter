"""#300 (dono, 16/10): *"no Command Center separe o site público uma seção para o site público aí no site público a
gente tenha é, como alterar o design, layout, puxando e arrastando e soltando de uma forma bem simples e conseguir
editar por lá como se fosse realmente um WordPress"*. Decisão: **livre, tipo Elementor**.

O que estes testes trancam:
- o modelo guarda só o que é do modelo (nada de HTML solto, script, link estranho, foto de fora);
- página nova: rascunho fora do ar; publicar confere as regras do site (um h1, sem pular nível, foto com descrição,
  título e descrição); publicada, sai no endereço dela, no sitemap, com canonical e JSON-LD;
- página que já existe: as faixas dela viram seções originais que se movem e se escondem; sem mexer, sai igual;
  "Voltar ao original" devolve a página do código;
- cada publicação guarda uma versão; voltar uma versão traz ela para o rascunho;
- karts, produtos e cartões vêm do banco; ver é do operador, mudar e publicar é do gerente.
"""
import io
import json
import os
import re

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from command_center.api import auth
from command_center.api.main import app
from command_center.db import aplicar_schema, conectar, um
from command_center.providers import editor_site as es
from command_center.providers import servicos_site
from command_center.vitrine import editor as ed
from command_center.vitrine import html_seguro

SENHA = "pista-molhada-7"


@pytest.fixture()
def amb(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path))
    monkeypatch.delenv("CC_SITE_HOSTS", raising=False)
    con = conectar(); aplicar_schema(con)
    auth.criar_usuario(con, "ger@example.com", "Gerente", "MANAGER", SENHA)
    auth.criar_usuario(con, "op@example.com", "Operador", "OPERATOR", SENHA)
    con.commit()
    with TestClient(app, base_url="https://cc.test") as painel, TestClient(app, base_url="https://novo.urace.us") as site:
        yield painel, site, con
    con.close()


def _entra(t, email="ger@example.com"):
    t.cookies.clear()
    assert t.post("/ops/api/auth/login", json={"email": email, "password": SENHA}).status_code == 200
    return {"X-CSRF": t.cookies.get("cc_csrf")}


def _nova(painel, h, **kw):
    r = painel.post("/ops/api/site/editor/paginas", headers=h, json={"title": "Summer Kart Camp 2027", "path": "/summer-camp/", **kw})
    assert r.status_code == 201, r.text
    return r.json()


def _salvar(painel, h, pid, **kw):
    return painel.patch(f"/ops/api/site/editor/paginas/{pid}", headers=h, json=kw)


def _secao(*widgets, fundo="clara", colunas=1):
    cols = [list(widgets)] + [[] for _ in range(colunas - 1)]
    return {"id": ed.novo_id(), "tipo": "secao", "fundo": fundo, "espaco": "m", "colunas": colunas, "itens": cols}


H1 = {"id": "h1a", "tipo": "titulo", "texto": "Summer Kart Camp", "nivel": 1}
DESC = "Five days of kart racing camp in Orlando for drivers 7 and up, with coaches, karts and gear included."


# ------------------------------------------------------------------ o modelo
@pytest.mark.parametrize("conteudo, erro", [
    ({"itens": [{"tipo": "html", "html": "<script>x</script>"}]}, "inválido"),
    ({"itens": [_secao({"tipo": "botao", "texto": "Go", "link": "javascript:alert(1)"})]}, "link"),
    ({"itens": [_secao({"tipo": "imagem", "src": "https://outro.example.com/x.png", "alt": "x"})]}, "foto"),
    ({"itens": [_secao({"tipo": "widget-novo"})]}, "desconhecido"),
    ({"itens": [{"tipo": "original", "indice": 0}]}, "original"),
])
def test_o_modelo_recusa_o_que_nao_e_dele(conteudo, erro):
    with pytest.raises(ed.ErroEditor, match=erro):
        ed.limpar(conteudo)


def test_texto_sai_limpo_e_nada_vira_html_solto():
    c = ed.limpar({"itens": [_secao({"tipo": "texto", "html": '<p onclick="x()">Hi <b>there</b><script>alert(1)</script></p>'},
                                    {"tipo": "titulo", "texto": "<img src=x onerror=alert(1)>", "nivel": 2})]})
    html = ed.corpo(c)
    assert "<p>Hi <b>there</b></p>" in html and "alert" not in html.replace("&lt;img src=x onerror=alert(1)&gt;", "")
    assert "&lt;img src=x onerror=alert(1)&gt;" in html, "título é texto, nunca HTML"


# ------------------------------------------------------------------ página nova
def test_pagina_nova_fica_fora_do_ar_ate_publicar_e_publicar_confere_as_regras(amb):
    painel, site, con = amb
    h = _entra(painel)
    p = _nova(painel, h)["pagina"]
    assert site.get("/summer-camp/").status_code == 404, "rascunho não sai no site"
    # sem descrição e com dois h1: não publica, e diz por quê
    _salvar(painel, h, p["id"], conteudo={"itens": [_secao(H1, {"tipo": "titulo", "texto": "Again", "nivel": 1})]})
    r = painel.post(f"/ops/api/site/editor/paginas/{p['id']}/publicar", headers=h)
    assert r.status_code == 400 and "um título nível 1" in r.json()["detail"] and "descrição" in r.json()["detail"]
    # título que pula de nível também não
    _salvar(painel, h, p["id"], description=DESC, conteudo={"itens": [_secao(H1, {"tipo": "titulo", "texto": "Deep", "nivel": 3})]})
    assert "pula de nível" in painel.post(f"/ops/api/site/editor/paginas/{p['id']}/publicar", headers=h).json()["detail"]
    _salvar(painel, h, p["id"], conteudo={"itens": [
        _secao(H1, {"tipo": "texto", "html": "<p>Learn from <strong>pro coaches</strong>.</p>"}, fundo="escura"),
        _secao({"tipo": "titulo", "texto": "What you get", "nivel": 2}, {"tipo": "lista", "itens": ["Karts", "Coaching"]},
               {"tipo": "botao", "texto": "Book the camp", "link": "/contact/?assunto=camp"}, colunas=2)]})
    r = painel.post(f"/ops/api/site/editor/paginas/{p['id']}/publicar", headers=h)
    assert r.status_code == 200, r.text
    html = site.get("/summer-camp/").text
    assert html.count("<h1") == 1 and "Summer Kart Camp" in html and "<strong>pro coaches</strong>" in html
    assert '<link rel="canonical" href="https://novo.urace.us/summer-camp/">' in html
    assert "<title>Summer Kart Camp 2027</title>" in html and DESC in html
    assert 'class="faixa escura ed-secao' in html and "ed-grade ed-c2" in html
    assert "application/ld+json" in html, "o JSON-LD do negócio"
    assert "/summer-camp/" in site.get("/sitemap.xml").text


def test_o_rascunho_muda_e_o_site_so_muda_quando_publica_de_novo(amb):
    painel, site, con = amb
    h = _entra(painel)
    pid = _nova(painel, h)["pagina"]["id"]
    _salvar(painel, h, pid, description=DESC, conteudo={"itens": [_secao(H1)]})
    painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h)
    r = _salvar(painel, h, pid, conteudo={"itens": [_secao({**H1, "texto": "Winter Kart Camp"})]})
    assert r.json()["pagina"]["estado"] == "mudou"
    assert "Summer Kart Camp" in site.get("/summer-camp/").text and "Winter Kart Camp" not in site.get("/summer-camp/").text
    prev = painel.get(f"/ops/api/site/editor/paginas/{pid}/previa", headers=h)
    assert prev.status_code == 200 and "Winter Kart Camp" in prev.text, "a pré-visualização mostra o rascunho"
    assert prev.headers["x-frame-options"] == "SAMEORIGIN" and "frame-ancestors 'self'" in prev.headers["content-security-policy"]
    assert 'name="robots" content="noindex' in prev.text
    painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h)
    assert "Winter Kart Camp" in site.get("/summer-camp/").text


def test_versoes_guardam_cada_publicacao_e_voltam_para_o_rascunho(amb):
    painel, site, con = amb
    h = _entra(painel)
    pid = _nova(painel, h)["pagina"]["id"]
    for nome in ("Version One Camp", "Version Two Camp"):
        _salvar(painel, h, pid, description=DESC, conteudo={"itens": [_secao({**H1, "texto": nome})]})
        assert painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h).status_code == 200
    vs = painel.get(f"/ops/api/site/editor/paginas/{pid}/versoes", headers=h).json()["versoes"]
    assert len(vs) == 2
    r = painel.post(f"/ops/api/site/editor/paginas/{pid}/versoes/{vs[-1]['id']}/voltar", headers=h)
    assert "Version One Camp" in json.dumps(r.json()["pagina"]["draft"])
    assert "Version Two Camp" in site.get("/summer-camp/").text, "voltar só mexe no rascunho"
    painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h)
    assert "Version One Camp" in site.get("/summer-camp/").text


@pytest.mark.parametrize("caminho", ["/store/x/", "/ops/x/", "/", "/academy/", "/legal/x/"])
def test_endereco_do_sistema_ou_de_pagina_que_existe_nao_vira_pagina_nova(amb, caminho):
    painel, site, con = amb
    h = _entra(painel)
    r = painel.post("/ops/api/site/editor/paginas", headers=h, json={"title": "Some page title", "path": caminho})
    assert r.status_code == 400, r.text


# ------------------------------------------------------------------ página que já existe
def test_pagina_existente_vira_faixas_que_se_movem_e_voltar_ao_original(amb):
    painel, site, con = amb
    h = _entra(painel)
    antes = site.get("/about/").text
    r = painel.post("/ops/api/site/editor/paginas", headers=h, json={"base": "/about/"})
    assert r.status_code == 201, r.text
    p = r.json()
    itens = p["pagina"]["draft"]["itens"]
    assert itens and all(x["tipo"] == "original" for x in itens) and len(p["originais"]) == len(itens)
    pid = p["pagina"]["id"]
    # publicar sem mexer: o mesmo conteúdo
    assert painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h).status_code == 200
    depois = site.get("/about/").text
    corpo = lambda x: re.search(r'<main id="conteudo">(.*)</main>', x, re.S).group(1)  # noqa: E731
    assert re.sub(r"\s+", "", corpo(depois)) == re.sub(r"\s+", "", corpo(antes)), "sem mexer, sai igual"
    # esconde a última faixa, põe uma seção nova antes da primeira e move a segunda para o fim
    novo = [_secao({"tipo": "titulo", "texto": "Meet the team in person", "nivel": 2},
                   {"tipo": "botao", "texto": "Visit us", "link": "/contact/"}, fundo="cinza")]
    orig = [dict(x) for x in itens]
    orig[-1]["oculto"] = True
    ordem = [orig[0], *novo, *orig[2:], orig[1]]
    r = _salvar(painel, h, pid, conteudo={"itens": ordem})
    assert r.status_code == 200, r.text
    assert painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h).status_code == 200, "o h1 é o da faixa original"
    html = site.get("/about/").text
    assert "Meet the team in person" in html and "ed-cinza" in html and html.count("<h1") == 1
    # voltar ao original
    assert painel.post(f"/ops/api/site/editor/paginas/{pid}/despublicar", headers=h).status_code == 200
    assert re.sub(r"\s+", "", corpo(site.get("/about/").text)) == re.sub(r"\s+", "", corpo(antes))
    assert um(con, "SELECT COUNT(*) AS n FROM site_page_versions WHERE page_id=?", (pid,))["n"] == 2, "as versões ficam"


# ------------------------------------------------------------------ o que vem do banco
def test_karts_e_cartoes_vem_do_painel(amb):
    painel, site, con = amb
    h = _entra(painel)
    sid = um(con, "SELECT id FROM booking_services WHERE site_kart='4-stroke'")["id"]
    servicos_site.mudar(con, None, sid, {"price": "655", "site_title": "Rental 4T"})
    con.commit()
    pid = _nova(painel, h)["pagina"]["id"]
    titulo = {"tipo": "titulo", "texto": "Pick your kart", "nivel": 2}       # os cartões têm h3: o h2 vem antes
    _salvar(painel, h, pid, description=DESC, conteudo={"itens": [_secao(H1, titulo, {"tipo": "karts"}, {"tipo": "cartoes", "pagina": "academy"})]})
    assert painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h).status_code == 200
    html = site.get("/summer-camp/").text
    assert "Rental 4T" in html and "$655" in html, "o kart e o preço do painel"
    assert "12-month contract" in html, "os cartões da Academy do painel"


# ------------------------------------------------------------------ fotos e permissões
def test_foto_do_editor_vira_webp_sem_exif_e_exige_descricao(amb):
    painel, site, con = amb
    h = _entra(painel)
    buf = io.BytesIO()
    ex = Image.Exif(); ex[0x010F] = "Fabricante"
    Image.new("RGB", (2400, 1600), (10, 120, 200)).save(buf, "JPEG", exif=ex)
    r = painel.post("/ops/api/site/editor/fotos", headers=h, files={"arquivo": ("f.jpg", buf.getvalue(), "image/jpeg")})
    assert r.status_code == 201, r.text
    f = r.json()
    assert f["src"].startswith("/_f/") and max(f["largura"], f["altura"]) == 1600
    img = site.get(f["src"])
    assert img.status_code == 200 and not Image.open(io.BytesIO(img.content)).getexif()
    pid = _nova(painel, h)["pagina"]["id"]
    w = {"tipo": "imagem", "src": f["src"], "alt": "", "largura": f["largura"], "altura": f["altura"]}
    _salvar(painel, h, pid, description=DESC, conteudo={"itens": [_secao(H1, w)]})
    assert "sem descrição" in painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h).json()["detail"]
    _salvar(painel, h, pid, conteudo={"itens": [_secao(H1, {**w, "alt": "Drivers on the track at sunset"})]})
    assert painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h).status_code == 200
    assert f'src="{f["src"]}" alt="Drivers on the track at sunset"' in site.get("/summer-camp/").text


def test_operador_ve_e_so_o_gerente_muda_e_publica(amb):
    painel, site, con = amb
    h = _entra(painel)
    pid = _nova(painel, h)["pagina"]["id"]
    h = _entra(painel, "op@example.com")
    assert painel.get("/ops/api/site/editor/paginas", headers=h).status_code == 200
    assert painel.get(f"/ops/api/site/editor/paginas/{pid}/previa", headers=h).status_code == 200
    assert _salvar(painel, h, pid, title="Changed by operator").status_code == 403
    assert painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h).status_code == 403
    assert um(con, "SELECT COUNT(*) AS n FROM audit_logs WHERE event='site.page.create'")["n"] == 1


# ------------------------------------------------------------------ #315: o editor como o Canva
# Dono, 16/10: *"ele abre uma mini visualização de como é o site público. E dali a pessoa consegue, por ali, clicar no
# que ela precisa editar. Ela edita, ela puxa, ela arrasta, ela solta … É como se fosse um Canva."*
def _previa(painel, h, pid, editar=True):
    return painel.get(f"/ops/api/site/editor/paginas/{pid}/previa" + ("?editar=1" if editar else ""), headers=h)


def test_a_previa_de_edicao_marca_cada_peca_e_o_site_continua_igual(amb, monkeypatch):
    """A prévia de edição tem os `data-ed-*` (seção, coluna, elemento, faixa original) e o CSS do editor, sem medição
    e com a política do site (sem script nem estilo inline); o site e a prévia de sempre não levam nada disso."""
    painel, site, con = amb
    monkeypatch.setenv("SITE_GTM_ID", "GTM-59CCNDC")          # com a medição ligada no site
    h = _entra(painel)
    pid = _nova(painel, h)["pagina"]["id"]
    sec = _secao(H1, {"id": "bt1", "tipo": "botao", "texto": "Book the camp", "link": "/contact/"},
                 {"id": "li1", "tipo": "lista", "itens": []}, colunas=2)
    _salvar(painel, h, pid, description=DESC, conteudo={"itens": [sec]})
    r = _previa(painel, h, pid)
    ed_html = r.text
    # a prévia roda na origem do painel, com a sessão do gerente: a política dela é a do site (nada inline)
    pol = r.headers["content-security-policy"]
    diretivas = dict(x.strip().split(" ", 1) for x in pol.split(";"))
    assert diretivas["script-src"] == "'self'" and diretivas["style-src"] == "'self'"
    assert "unsafe" not in pol and diretivas["frame-ancestors"] == "'self'"
    assert f'data-ed-s="{sec["id"]}"' in ed_html and f'data-ed-col="{sec["id"]}:0"' in ed_html
    assert f'data-ed-col="{sec["id"]}:1"' in ed_html, "a coluna vazia também é um lugar para soltar"
    assert '<h1 data-ed-w="h1a" data-ed-tipo="titulo" class="ed-t' in ed_html
    assert 'data-ed-w="bt1" data-ed-tipo="botao"' in ed_html
    assert 'class="lista ed-lista ed-vazio"' in ed_html, "a lista vazia continua clicável para escrever"
    assert "/_s/editor-previa.css?v=" in ed_html
    assert "medicao.js" not in ed_html and "GTM-59CCNDC" not in ed_html, "quem edita não é visita"
    assert 'name="robots" content="noindex' in ed_html
    assert painel.get("/_s/editor-previa.css").status_code == 200
    # a prévia de sempre e o site: nada do editor
    assert painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h).status_code == 200
    for html in (_previa(painel, h, pid, editar=False).text, site.get("/summer-camp/").text):
        assert "data-ed-" not in html and "editor-previa.css" not in html and "ed-vazio" not in html
    assert "GTM-59CCNDC" in site.get("/summer-camp/").text, "o site continua medindo"


def test_a_previa_de_edicao_de_pagina_que_existe_marca_as_faixas_e_mostra_a_escondida_apagada(amb):
    painel, site, con = amb
    h = _entra(painel)
    p = painel.post("/ops/api/site/editor/paginas", headers=h, json={"base": "/about/"}).json()
    itens = [dict(x) for x in p["pagina"]["draft"]["itens"]]
    itens[1]["oculto"] = True
    _salvar(painel, h, p["pagina"]["id"], conteudo={"itens": itens})
    html = _previa(painel, h, p["pagina"]["id"]).text
    assert '<section data-ed-s="o0" data-ed-o="0"' in html
    assert '<section data-ed-s="o1" data-ed-o="1" data-ed-oculto=""' in html, "a escondida aparece apagada na prévia"
    publica = re.search(r'<main id="conteudo">(.*)</main>', _previa(painel, h, p["pagina"]["id"], editar=False).text, re.S).group(1)
    assert publica.count("<section") == html.count("<section") - 1, "fora da edição, a escondida some"


def test_salvar_com_a_revisao_velha_recusa_em_vez_de_apagar_o_que_o_outro_fez(amb):
    painel, site, con = amb
    h = _entra(painel)
    p = _nova(painel, h)["pagina"]
    rev = p["rev"]
    r = _salvar(painel, h, p["id"], rev=rev, conteudo={"itens": [_secao({**H1, "texto": "Gerente A"})]})
    assert r.status_code == 200 and r.json()["pagina"]["rev"] == rev + 1
    r = _salvar(painel, h, p["id"], rev=rev, conteudo={"itens": [_secao({**H1, "texto": "Gerente B"})]})
    assert r.status_code == 409 and r.json()["detail"]["motivo"] == "rev"
    assert "Gerente A" in json.dumps(painel.get(f"/ops/api/site/editor/paginas/{p['id']}", headers=h).json()["pagina"]["draft"])
    # publicar também confere: só vai para o ar o rascunho que a tela mostra
    _salvar(painel, h, p["id"], description=DESC)
    r = painel.post(f"/ops/api/site/editor/paginas/{p['id']}/publicar", headers=h, json={"rev": rev + 1})
    assert r.status_code == 409 and site.get("/summer-camp/").status_code == 404
    r = painel.post(f"/ops/api/site/editor/paginas/{p['id']}/publicar", headers=h, json={"rev": rev + 2})
    assert r.status_code == 200, r.text


def test_titulo_vazio_salva_no_rascunho_e_trava_a_publicacao(amb):
    painel, site, con = amb
    h = _entra(painel)
    pid = _nova(painel, h)["pagina"]["id"]
    r = _salvar(painel, h, pid, description=DESC, conteudo={"itens": [_secao(H1, {"id": "t2", "tipo": "titulo", "texto": "", "nivel": 2},
                                                                                {"id": "b2", "tipo": "botao", "texto": "Go", "link": ""})]})
    assert r.status_code == 200, r.text
    assert any("título(s) vazio(s)" in x for x in r.json()["problemas"])
    assert any("sem texto ou sem link" in x for x in r.json()["problemas"])
    r = painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h)
    assert r.status_code == 400 and "vazio" in r.json()["detail"]


def test_link_que_nao_passa_fica_o_de_antes_e_volta_o_motivo(amb):
    painel, site, con = amb
    h = _entra(painel)
    pid = _nova(painel, h)["pagina"]["id"]
    bt = {"id": "bt9", "tipo": "botao", "texto": "Book", "link": "/contact/"}
    _salvar(painel, h, pid, conteudo={"itens": [_secao(H1, bt)]})
    for ruim in ("javascript:alert(1)", "/con tato"):
        r = _salvar(painel, h, pid, conteudo={"itens": [_secao({**H1, "texto": "Other text kept"}, {**bt, "link": ruim})]})
        assert r.status_code == 200, "o resto da página salva"
        assert "link" in r.json()["erros"]["bt9"]
        d = json.dumps(r.json()["pagina"]["draft"])
        assert '"link": "/contact/"' in d and "javascript" not in d and "Other text kept" in d


def test_desenhar_devolve_so_as_secoes_novas_marcadas(amb):
    painel, site, con = amb
    h = _entra(painel)
    p = painel.post("/ops/api/site/editor/paginas", headers=h, json={"base": "/about/"}).json()
    nova = _secao({"id": "tt1", "tipo": "titulo", "texto": "Meet the team", "nivel": 2})
    itens = [*p["pagina"]["draft"]["itens"], nova]
    r = _salvar(painel, h, p["pagina"]["id"], conteudo={"itens": itens}, desenhar=True).json()
    assert [s["id"] for s in r["secoes"]] == [nova["id"]], "as faixas originais não vão de novo"
    assert 'data-ed-w="tt1"' in r["secoes"][0]["html"] and r["secoes"][0]["html"].startswith("<section")
    assert "secoes" not in _salvar(painel, h, p["pagina"]["id"], conteudo={"itens": itens}).json()


def test_texto_vindo_da_previa_sai_limpo():
    """O texto editado na prévia chega como HTML do contenteditable: script e evento somem, <div> vira parágrafo,
    e o título é sempre texto."""
    c = ed.limpar({"itens": [_secao(
        {"id": "x1", "tipo": "texto", "html": '<div>One <b>bold</b></div><div><img src=x onerror="alert(1)">Two</div><script>alert(2)</script>'},
        {"id": "x2", "tipo": "titulo", "texto": "Hello<br>World<div>x</div>", "nivel": 2},
        {"id": "x3", "tipo": "lista", "itens": ["<b>Karts</b>", ""]})]}, rascunho=True)
    html = ed.corpo(c)
    assert "<p>One <b>bold</b></p><p>Two</p>" in html, html
    assert "onerror" not in html and "alert" not in html and "<script" not in html
    assert "Hello&lt;br&gt;World&lt;div&gt;x&lt;/div&gt;" in html and "<br>" not in html
    assert "<li>&lt;b&gt;Karts&lt;/b&gt;</li>" in html


def test_endereco_que_nao_passa_nao_trava_o_resto_do_rascunho(amb):
    """#315: o painel salva sozinho enquanto se escreve o endereço; o endereço pela metade fica o de antes, volta o
    motivo, e o que mudou na página salva do mesmo jeito."""
    painel, site, con = amb
    h = _entra(painel)
    pid = _nova(painel, h)["pagina"]["id"]
    r = _salvar(painel, h, pid, path="/summer camp/", conteudo={"itens": [_secao({**H1, "texto": "Saved anyway"})]})
    assert r.status_code == 200, r.text
    assert "endereço" in r.json()["erros"]["pagina"] and r.json()["pagina"]["path"] == "/summer-camp/"
    assert "Saved anyway" in json.dumps(r.json()["pagina"]["draft"])


# ------------------------------------------------------------------ #315: a revisão no Voltar versão e no salvar
def _gerente_id(con):
    return um(con, "SELECT id FROM users WHERE email=?", ("ger@example.com",))["id"]


def _publicada(painel, h, texto="Published Camp"):
    pid = _nova(painel, h)["pagina"]["id"]
    _salvar(painel, h, pid, description=DESC, conteudo={"itens": [_secao({**H1, "texto": texto})]})
    assert painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h).status_code == 200
    vid = painel.get(f"/ops/api/site/editor/paginas/{pid}/versoes", headers=h).json()["versoes"][0]["id"]
    return pid, vid


def test_voltar_versao_com_a_revisao_velha_recusa_e_nao_apaga_o_rascunho_do_outro(amb):
    """A tela que ficou para trás (outra pessoa salvou depois) não troca o rascunho dela pela versão antiga: 409. Com a
    revisão em dia, volta e soma 1; a tela que tinha a revisão de antes do voltar também recusa."""
    painel, site, con = amb
    h = _entra(painel)
    pid, vid = _publicada(painel, h)
    rev_n = painel.get(f"/ops/api/site/editor/paginas/{pid}", headers=h).json()["pagina"]["rev"]
    r = _salvar(painel, h, pid, rev=rev_n, conteudo={"itens": [_secao({**H1, "texto": "B work never published"})]})
    assert r.status_code == 200 and r.json()["pagina"]["rev"] == rev_n + 1
    voltar = f"/ops/api/site/editor/paginas/{pid}/versoes/{vid}/voltar"
    r = painel.post(voltar, headers=h, json={"rev": rev_n})
    assert r.status_code == 409 and r.json()["detail"]["motivo"] == "rev", r.text
    assert "B work never published" in json.dumps(painel.get(f"/ops/api/site/editor/paginas/{pid}", headers=h).json()["pagina"]["draft"])
    r = painel.post(voltar, headers=h, json={"rev": rev_n + 1})
    assert r.status_code == 200, r.text
    assert r.json()["pagina"]["rev"] == rev_n + 2 and r.json()["erros"] == {}
    assert "Published Camp" in json.dumps(r.json()["pagina"]["draft"])
    r = _salvar(painel, h, pid, rev=rev_n + 1, conteudo={"itens": [_secao({**H1, "texto": "Stale tab"})]})
    assert r.status_code == 409, "o voltar soma a revisão: a tela de antes dele não passa por cima"
    assert painel.post(f"/ops/api/site/editor/paginas/{pid}/versoes/999999/voltar", headers=h, json={"rev": rev_n + 2}).status_code == 404


def test_voltar_versao_com_um_salvar_no_meio_recusa_em_vez_de_repetir_a_revisao(amb, monkeypatch):
    """A outra aba salva entre a leitura da revisão e a gravação do voltar: o voltar recusa (a troca confere a revisão
    na mesma gravação) e o que a outra aba salvou fica."""
    painel, site, con = amb
    h = _entra(painel)
    pid, vid = _publicada(painel, h)
    p = es.uma(con, pid)
    agora, feito = es.agora, []

    def no_meio():
        if not feito:
            feito.append(1)
            con.execute("UPDATE site_pages SET draft = ?, rev = rev + 1 WHERE id = ?",
                        (json.dumps({"itens": [_secao({**H1, "texto": "Tab B in the middle"})]}), pid))
        return agora()
    monkeypatch.setattr(es, "agora", no_meio)
    with pytest.raises(es.Conflito):
        es.voltar(con, _gerente_id(con), pid, vid, rev=p["rev"])
    depois = es.uma(con, pid)
    assert feito and depois["rev"] == p["rev"] + 1
    assert "Tab B in the middle" in json.dumps(depois["draft"])


def test_salvar_confere_a_revisao_na_mesma_gravacao(amb, monkeypatch):
    """Outra gravação entre a leitura do rascunho e o UPDATE: o salvar recusa (o `WHERE rev = ?`), sem gravar."""
    painel, site, con = amb
    h = _entra(painel)
    pid = _nova(painel, h)["pagina"]["id"]
    p = es.uma(con, pid)
    limpar = ed.limpar

    def e_no_meio(*a, **kw):
        out = limpar(*a, **kw)
        con.execute("UPDATE site_pages SET rev = rev + 1 WHERE id = ?", (pid,))
        return out
    monkeypatch.setattr(ed, "limpar", e_no_meio)
    with pytest.raises(es.Conflito):
        es.salvar(con, _gerente_id(con), pid, {"conteudo": {"itens": [_secao({**H1, "texto": "Lost in the race"})]}}, rev=p["rev"], erros={})
    assert "Lost in the race" not in json.dumps(es.uma(con, pid)["draft"])


# ------------------------------------------------------------------ #315: o rascunho tolerante segura o que não passa
def test_rascunho_guarda_a_foto_de_antes_quando_a_nova_e_de_fora(amb):
    painel, site, con = amb
    h = _entra(painel)
    pid = _nova(painel, h)["pagina"]["id"]
    im = {"id": "im1", "tipo": "imagem", "src": "/_f/0123456789abcdef.webp", "alt": "Kart on the track"}
    assert _salvar(painel, h, pid, conteudo={"itens": [_secao(H1, im)]}).status_code == 200
    r = _salvar(painel, h, pid, conteudo={"itens": [_secao(H1, {**im, "src": "//outro.example.com/x.png"})]})
    assert r.status_code == 200, r.text
    assert "imagem" in r.json()["erros"]["im1"]
    d = json.dumps(r.json()["pagina"]["draft"])
    assert "/_f/0123456789abcdef.webp" in d and "outro.example.com" not in d


def test_rascunho_guarda_o_texto_de_antes_quando_o_novo_e_longo_demais(amb):
    painel, site, con = amb
    h = _entra(painel)
    pid = _nova(painel, h)["pagina"]["id"]
    tx = {"id": "tx1", "tipo": "texto", "html": "<p>Short and kept.</p>"}
    assert _salvar(painel, h, pid, conteudo={"itens": [_secao(H1, tx)]}).status_code == 200
    r = _salvar(painel, h, pid, conteudo={"itens": [_secao(H1, {**tx, "html": "<p>" + "a" * (html_seguro.MAX + 10) + "</p>"})]})
    assert r.status_code == 200, r.text
    assert "longo" in r.json()["erros"]["tx1"]
    d = json.dumps(r.json()["pagina"]["draft"])
    assert "Short and kept." in d and "a" * 100 not in d


def test_pergunta_sem_resposta_salva_no_rascunho_e_trava_a_publicacao(amb):
    painel, site, con = amb
    h = _entra(painel)
    pid = _nova(painel, h)["pagina"]["id"]
    faq = {"id": "fq1", "tipo": "faq", "itens": [{"pergunta": "How old?", "resposta": ""}]}
    r = _salvar(painel, h, pid, description=DESC, conteudo={"itens": [_secao(H1, faq)]})
    assert r.status_code == 200, r.text
    assert any("pergunta(s) frequente(s)" in x for x in r.json()["problemas"]), r.json()["problemas"]
    r = painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h)
    assert r.status_code == 400 and "pergunta" in r.json()["detail"]
    assert site.get("/summer-camp/").status_code == 404


def test_o_css_da_previa_usa_os_tokens_de_motion_do_site():
    """CLAUDE.md: durações e curvas dos tokens do CSS. A prévia carrega o site.css antes, com `--dur` e `--curva`."""
    css = open(os.path.join(os.path.dirname(ed.__file__), "static", "editor-previa.css"), encoding="utf-8").read()
    assert "var(--dur) var(--curva)" in css
    assert not re.search(r"\d+ms|cubic-bezier", css), "duração ou curva fixa no CSS da prévia"


# ------------------------------------------------------------------ #315, etapa 4: o texto das faixas originais
# A página que já existe (a do código) passa a ter o texto escrito no lugar: só as folhas de texto puro, fora dos
# blocos de dado (NO FAKE DATA e uma fonte só: preço, kart, plano e cartão vêm do painel e nunca viram texto escrito).
def _faixas(caminho):
    from command_center.api import editor_site as api_ed
    return api_ed._original(caminho, api_ed._host(None))["secoes"]


def _folha(caminho, i, tag, texto=None):
    """A chave da primeira folha `tag` da faixa `i` (com o `texto`, se dado) que se escreve no editor."""
    return next(f.chave for f in ed._analisar(_faixas(caminho)[i])[0] if f.tag == tag and (texto is None or texto in f.texto))


def _travada(caminho, trecho):
    """(faixa, chave, área) do primeiro texto travado com `trecho`."""
    for i, s in enumerate(_faixas(caminho)):
        for k, (area, texto) in ed._analisar(s)[1].items():
            if trecho in texto:
                return i, k, area
    raise AssertionError(f"nenhum texto travado com {trecho!r} em {caminho}")


def _abre(painel, h, caminho):
    r = painel.post("/ops/api/site/editor/paginas", headers=h, json={"base": caminho})
    assert r.status_code == 201, r.text
    return r.json()


def _com_textos(itens, i, textos):
    return [{**x, "textos": textos} if x["tipo"] == "original" and x["indice"] == i else x for x in itens]


def _main(html):
    return re.search(r'<main id="conteudo">(.*)</main>', html, re.S).group(1)


NOVO_H1 = "Coached every week, faster every month"


def test_troca_de_texto_da_faixa_original_vale_com_o_hash_certo(amb):
    """O h1 da Academy (faixa 1) trocado no editor sai no site; a prévia de edição marca o texto (com o do código em
    `data-ed-orig`) e o JSON-LD diz o mesmo que a página (a pergunta trocada)."""
    painel, site, con = amb
    h = _entra(painel)
    p = _abre(painel, h, "/academy/")
    pid, itens = p["pagina"]["id"], p["pagina"]["draft"]["itens"]
    k = _folha("/academy/", 0, "h1")
    i_faq = next(i for i, s in enumerate(_faixas("/academy/")) if "<summary>" in s)
    pergunta = next(f for f in ed._analisar(_faixas("/academy/")[i_faq])[0] if f.tag == "summary")
    r = _previa(painel, h, pid)
    previa, pol = r.text, r.headers["content-security-policy"]
    assert f'data-ed-t="{k}"' in previa, "o h1 da faixa original se escreve na prévia"
    assert "script-src 'self';" in pol and "unsafe" not in pol, "a prévia roda com a sessão do gerente: nada inline"
    itens = _com_textos(_com_textos(itens, 0, {k: NOVO_H1}), i_faq, {pergunta.chave: "Who is the Academy made for?"})
    r = _salvar(painel, h, pid, conteudo={"itens": itens})
    assert r.status_code == 200 and r.json()["erros"] == {}, r.text
    assert r.json()["pagina"]["draft"]["itens"][0]["textos"] == {k: NOVO_H1}
    assert r.json()["originais"][0] == NOVO_H1, "o nome da faixa nas Camadas é o título trocado"
    previa = _previa(painel, h, pid).text
    assert f'data-ed-t="{k}" data-ed-orig="' in previa and NOVO_H1 in previa
    assert painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h).status_code == 200
    html = site.get("/academy/").text
    assert f"<h1>{NOVO_H1}</h1>" in html and "Four coached sessions a month" not in _main(html)
    assert "data-ed-" not in html, "o site não leva nada do editor"
    lds = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
    faq = next(x for x in lds if x.get("@type") == "FAQPage")
    nomes = [q["name"] for q in faq["mainEntity"]]
    assert "Who is the Academy made for?" in nomes and pergunta.texto not in nomes, "o Google lê a pergunta da página"


def test_codigo_mudou_a_troca_fica_de_fora_e_vira_texto_orfao(amb, monkeypatch):
    """Se a página do código muda o texto, o hash não bate: a troca é ignorada (o site mostra o texto novo do código,
    nunca o escrito em outro lugar) e vira pendência "texto órfão" até ser descartada."""
    from command_center.vitrine import conteudo_paginas as P
    painel, site, con = amb
    h = _entra(painel)
    p = _abre(painel, h, "/academy/")
    pid = p["pagina"]["id"]
    k = _folha("/academy/", 0, "h1")
    itens = _com_textos(p["pagina"]["draft"]["itens"], 0, {k: NOVO_H1})
    assert _salvar(painel, h, pid, conteudo={"itens": itens}).status_code == 200
    assert painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h).status_code == 200
    monkeypatch.setitem(P.ACADEMY, "h1", "Monthly coaching for drivers who want more")       # o código mudou
    html = site.get("/academy/").text
    assert "<h1>Monthly coaching for drivers who want more</h1>" in html and NOVO_H1 not in html
    s = painel.get(f"/ops/api/site/editor/paginas/{pid}", headers=h).json()
    assert s["orfaos"] == {"o0": [k]}
    assert any("1 texto(s) órfão(s)" in x for x in s["problemas"]), s["problemas"]
    assert NOVO_H1 not in _previa(painel, h, pid).text, "nem na prévia a troca entra"
    r = painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h)
    assert r.status_code == 400 and "órfão" in r.json()["detail"]
    # descartar (o painel manda a faixa sem a troca): publica de novo
    r = _salvar(painel, h, pid, conteudo={"itens": p["pagina"]["draft"]["itens"]})
    assert r.json()["orfaos"] == {} and not any("órfão" in x for x in r.json()["problemas"])
    assert painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h).status_code == 200


@pytest.mark.parametrize("caminho, trecho, area", [
    ("/", "Starting at $", "precos"),                          # o "a partir de" do kart, do painel
    ("/academy/", "4-stroke and Baby Kart", "cartoes"),        # o grupo de planos (kart e preço por sessão)
    ("/academy/", "12-month contract", "cartoes"),             # o cartão da Academy
    ("/services/arrive-and-drive/", "Pick a day", "reserva"),  # a agenda da reserva (os karts e o total)
])
def test_texto_de_preco_kart_ou_cartao_e_recusado(amb, caminho, trecho, area):
    painel, site, con = amb
    h = _entra(painel)
    p = _abre(painel, h, caminho)
    i, k, achada = _travada(caminho, trecho)
    assert achada == area
    itens = _com_textos(p["pagina"]["draft"]["itens"], i, {k: "Only $1 today"})
    r = _salvar(painel, h, p["pagina"]["id"], conteudo={"itens": itens})
    assert r.status_code == 200, r.text
    assert "vem do painel" in r.json()["erros"][f"o{i}"]
    assert "textos" not in r.json()["pagina"]["draft"]["itens"][i], "a troca do texto travado não é guardada"
    assert "Only $1 today" not in _previa(painel, h, p["pagina"]["id"]).text
    assert f'data-ed-trava="{area}"' in _previa(painel, h, p["pagina"]["id"]).text, "a prévia mostra o bloco travado"
    with pytest.raises(ed.ErroEditor, match="vem do painel"):            # fora do rascunho, recusa de vez
        ed.limpar({"itens": itens}, com_originais=True, n_originais=len(itens), originais=_faixas(caminho))


def test_nenhum_texto_que_se_escreve_fica_dentro_de_bloco_de_dado(amb):
    """A lista dos blocos travados, conferida em todas as páginas que o editor abre: nenhum texto que se escreve tem
    preço, nem fica dentro de planos, cartões, karts, agenda, reserva, blog, loja, formulário, depoimentos ou
    campeões; e os blocos de dado de cada página aparecem travados na prévia."""
    from html.parser import HTMLParser

    from command_center.api import vitrine
    assert {"planos", "mt", "preco", "hero-preco", "preco-grande", "servicos-grade", "karts", "agenda", "posts-grade",
            "produtos-grade", "depoimentos", "campeoes"} <= set(ed.TRAVADOS) and {"form", "fieldset"} <= set(ed.TAGS_TRAVADAS)
    dado = {"planos", "plano", "plano-preco", "preco", "hero-preco", "preco-grande", "karts", "kart", "agenda",
            "agenda-total", "agenda-deposito", "posts-grade", "post-card", "produtos-grade", "depoimentos",
            "campeoes", "servicos-grade"}

    class Dentro(HTMLParser):
        def __init__(self):
            super().__init__()
            self.pilha, self.ruins, self.n = [], [], 0

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag in ("img", "br", "input", "meta", "link", "source", "hr", "wbr"):
                return
            if "data-ed-t" in a:
                self.n += 1
                pais = {c for _, cs in self.pilha for c in cs} | ({tag} & {"form", "fieldset"})
                if pais & (dado | {"form", "fieldset"}) or {t for t, _ in self.pilha} & {"form", "fieldset"}:
                    self.ruins.append(a["data-ed-t"])
            self.pilha.append((tag, set((a.get("class") or "").split())))

        def handle_endtag(self, tag):
            while self.pilha and self.pilha.pop()[0] != tag:
                pass

    travas = {}
    for caminho in vitrine.EDITAVEIS:
        p = Dentro()
        for i, s in enumerate(_faixas(caminho)):
            m = ed.marcar_original(s, i)
            p.feed(m)
            travas[caminho] = travas.get(caminho, set()) | set(re.findall(r'data-ed-trava="([a-z]+)"', m))
            assert not [f.texto for f in ed._analisar(s)[0] if ed.PRECO.search(f.texto)], (caminho, i)
        assert p.n > 0 and not p.ruins, (caminho, p.ruins)
    assert {"precos", "blog", "pessoas"} <= travas["/"]
    assert {"reserva", "precos"} <= travas["/services/arrive-and-drive/"]
    m = ed.marcar_original('<section><form action="/x/"><p>Send it</p></form><p>Say hi</p></section>', 0)
    assert '<form data-ed-trava="formulario"' in m and "<p>Send it</p>" in m and '<p data-ed-t="p.0:' in m, m
    assert "cartoes" in travas["/academy/"] and "cartoes" in travas["/pro-team/"] and "cartoes" in travas["/for-beginners/"]


def test_um_h1_contando_a_troca(amb):
    """O h1 trocado continua sendo o h1 da página: uma seção nova com outro h1 trava a publicação; sem ela, publica e
    o site tem um h1 só, o trocado."""
    painel, site, con = amb
    h = _entra(painel)
    p = _abre(painel, h, "/academy/")
    pid = p["pagina"]["id"]
    itens = _com_textos(p["pagina"]["draft"]["itens"], 0, {_folha("/academy/", 0, "h1"): NOVO_H1})
    r = _salvar(painel, h, pid, conteudo={"itens": [*itens, _secao({**H1, "texto": "A second big title"})]})
    assert any("exatamente um título nível 1 (h1); tem 2" in x for x in r.json()["problemas"]), r.json()["problemas"]
    assert painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h).status_code == 400
    _salvar(painel, h, pid, conteudo={"itens": itens})
    assert painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h).status_code == 200
    html = _main(site.get("/academy/").text)
    assert html.count("<h1") == 1 and f"<h1>{NOVO_H1}</h1>" in html


def test_texto_com_html_ou_script_sai_escapado_e_vai_ate_400(amb):
    painel, site, con = amb
    h = _entra(painel)
    p = _abre(painel, h, "/about/")
    pid = p["pagina"]["id"]
    k = _folha("/about/", 0, "h1")
    ruim = '<img src=x onerror="alert(1)"><script>alert(2)</script> About us'
    r = _salvar(painel, h, pid, conteudo={"itens": _com_textos(p["pagina"]["draft"]["itens"], 0, {k: ruim})})
    assert r.status_code == 200, r.text
    assert painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h).status_code == 200
    html = site.get("/about/").text
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;&lt;script&gt;alert(2)&lt;/script&gt; About us" in html
    assert "<script>alert" not in html and "<img src=x" not in html
    for previa in (_previa(painel, h, pid).text, _previa(painel, h, pid, editar=False).text):
        assert "<script>alert" not in previa and "<img src=x" not in previa
    # 400 caracteres: no rascunho, o resto é cortado e avisado; fora dele, recusa
    longo = "Fast " * 100
    r = _salvar(painel, h, pid, conteudo={"itens": _com_textos(p["pagina"]["draft"]["itens"], 0, {k: longo})})
    assert "até 400" in r.json()["erros"]["o0"]
    assert len(r.json()["pagina"]["draft"]["itens"][0]["textos"][k]) <= 400
    with pytest.raises(ed.ErroEditor, match="até 400"):
        ed.limpar({"itens": [{"tipo": "original", "indice": 0, "textos": {k: longo}}]}, com_originais=True, n_originais=1)
    for chave in ("h4.0:00000000", "p.0:xyz", "<p>", "p.0:0123abcd extra"):          # só a chave de uma folha
        with pytest.raises(ed.ErroEditor, match="textos"):
            ed.limpar({"itens": [{"tipo": "original", "indice": 0, "textos": {chave: "x"}}]}, com_originais=True, n_originais=1)


def test_sem_troca_a_faixa_sai_igual_byte_a_byte(amb):
    """Sem troca, cada faixa de cada página sai igual à do código, byte a byte; a prévia de edição só acrescenta os
    `data-ed-*`; e com uma troca só muda o texto daquela folha."""
    from command_center.api import vitrine
    for caminho in vitrine.EDITAVEIS:
        for i, s in enumerate(_faixas(caminho)):
            assert ed.aplicar_textos(s, None) == (s, []) and ed.aplicar_textos(s, {}) == (s, [])
            assert re.sub(r' data-ed-(?:t|s|o|trava)="[^"]*"', "", ed.marcar_original(s, i)) == s, (caminho, i)
    painel, site, con = amb
    h = _entra(painel)
    p = _abre(painel, h, "/academy/")
    pid = p["pagina"]["id"]
    assert painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h).status_code == 200
    publico = site.get("/academy/").text
    faixas = _faixas("/academy/")
    assert all(s in publico for s in faixas), "publicada sem mexer: cada faixa igual, byte a byte"
    k = _folha("/academy/", 0, "h1")
    _salvar(painel, h, pid, conteudo={"itens": _com_textos(p["pagina"]["draft"]["itens"], 0, {k: NOVO_H1})})
    painel.post(f"/ops/api/site/editor/paginas/{pid}/publicar", headers=h)
    publico = site.get("/academy/").text
    assert all(s in publico for s in faixas[1:]), "as outras faixas não mudam"
    velho = re.search(r"<h1>(.*?)</h1>", faixas[0]).group(1)
    assert faixas[0].replace(f"<h1>{velho}</h1>", f"<h1>{NOVO_H1}</h1>") in publico, "na faixa 1, só o texto do h1"
