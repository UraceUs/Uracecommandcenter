"""Páginas montadas por blocos (#502).

Dono, 29/10: *"sim, pode trazer o texto e recriar a winter"*. O urace.us ganhou estrutura nova em quase todas as
páginas (home, About, Academy, Programs, landings, Winter). Aqui uma página é um dicionário e cada faixa dela um bloco,
desenhado com os mesmos componentes do resto do site (faixa, cartões, planos, passos, números, depoimentos, FAQ).

Uma página::

    {"caminho": "/winter/", "titulo": "...", "descricao": "...", "foto": "winter.webp", "indexar": True,
     "trilha": (("Winter", "/winter/"),), "schemas": (...), "blocos": [...]}

As páginas moram em módulos `pg_*.py` desta pasta, cada um com `PAGINAS = (...)` — uma frente por arquivo, sem disputar a
mesma linha. `registro()` junta todas; a rota, o sitemap e o editor do painel leem de lá.

Os blocos (`tipo`):

- ``hero``: eyebrow, h1, sub, ctas [(rótulo, href)], foto, alt, nota
- ``texto``: eyebrow, titulo, paragrafos, lista, ctas, foto, alt
- ``cartoes``: eyebrow, titulo, intro, itens [{rotulo, titulo, texto, lista, preco, link: (rótulo, href), foto, alt}]
- ``passos``: eyebrow, titulo, intro, itens [(titulo, texto)]
- ``numeros``: eyebrow, titulo, intro, itens [(valor, rótulo)]
- ``figuras``: eyebrow, titulo, intro, itens [{foto, alt, titulo, legenda}]
- ``depoimentos``: eyebrow, titulo, intro, itens [(nome, quem, texto)], link (rótulo, href)
- ``videos``: eyebrow, titulo, intro, itens [(titulo, url)]
- ``definicoes``: eyebrow, titulo, intro, itens [(termo, descrição)]
- ``faq``: eyebrow, titulo, intro, itens [(pergunta, resposta | (parágrafos,))] — vira FAQPage no JSON-LD
- ``formulario``: eyebrow, titulo, texto, assunto, enviar, mensagem (rótulo do campo de texto, opcional), nota, obrigado,
  extras (HTML de campos a mais, do código: cada `name="x_<nome>"` entra na nota da oportunidade, uma linha por campo)
  (o caminho de uma página registrada: depois de enviar, a pessoa vai para lá — a campanha conta a conversão pela URL)
- ``contador``: eyebrow, titulo, texto, alvo (ISO 8601 com fuso), rotulo (o que acontece na data)
- ``cta``: titulo, texto, ctas
- ``posts``: eyebrow, titulo, intro, n — os artigos no ar (do banco)
- ``cartoes_painel``: eyebrow, titulo, intro, pagina — os cartões de Site › Cartões das páginas (academy, pro-team…)
- ``funcao``: render — `render(host, ctx) -> html` para o que só uma página tem (a calculadora da Winter). O `ctx` da rota
  traz `cartoes(pagina)`, `planos()` e `servicos()` (os do painel; None com o banco fora), `caminho` e `enviado`

Todo bloco aceita ``fundo`` (clara, escura, vermelha) e ``ancora`` (o `id` da seção, para link `#ancora`).

Texto é texto: sai escapado. Dentro dele, ``[rótulo](href)`` vira link e ``**assim**`` vira negrito. Link só para o próprio
site (``/…``, ``#…``), ``https://``, ``tel:`` e ``mailto:``.

**Preço nunca é texto** (Rate Card e painel são a fonte): o ``preco`` de um cartão é uma chave do painel (``kart``: "From
$719", o menor preço de kart do Arrive and Drive). `problemas()` acusa preço escrito em qualquer texto, e o teste roda
`problemas()` em todas as páginas registradas.
"""
import importlib
import json
import os
import pkgutil
import re
from functools import lru_cache
from html import escape

from command_center.vitrine.paginas import _negocio, estatico, layout, preco_kart, tamanho_estatico, usd

FUNDOS = ("clara", "escura", "vermelha")
TIPOS = ("hero", "texto", "cartoes", "passos", "numeros", "figuras", "depoimentos", "videos", "definicoes", "faq",
         "formulario", "contador", "cta", "posts", "cartoes_painel", "funcao")
# o preço escrito ($99, US$ 99, USD 99, 99 USD, 99 dollars) — o mesmo critério do editor do painel (#315)
PRECO = re.compile(r"(?:US)?\$\s?\d|\bUSD\s?\d|\d\s?USD\b|\b\d[\d,.]*\s*dollars?\b", re.I)
LINK = re.compile(r"\[([^\]\n]{1,160})\]\(([^)\s]{1,400})\)")
NEGRITO = re.compile(r"\*\*([^*\n]{1,200})\*\*")
HREF_OK = re.compile(r"(?:/(?!/)[^\s\"'<>]*|#[A-Za-z][\w-]{0,60}|https://[^\s\"'<>]+|tel:\+?[\d-]{7,20}|mailto:[^\s\"'<>@]+@[^\s\"'<>]+)")
ANCORA = re.compile(r"[a-z][a-z0-9-]{0,40}")
CAMINHO_SITE = re.compile(r"/(?:[a-z0-9]+(?:-[a-z0-9]+)*/)+")
PRECOS_DO_PAINEL = ("kart",)


class ErroBloco(ValueError):
    pass


def e(v):
    return escape(str(v), quote=True)


# ------------------------------------------------------------------ o registro
@lru_cache(maxsize=1)
def registro():
    """caminho → página, de todos os módulos `pg_*.py` desta pasta."""
    pasta = os.path.dirname(__file__)
    out = {}
    for m in sorted(x.name for x in pkgutil.iter_modules([pasta]) if x.name.startswith("pg_")):
        for p in importlib.import_module(f"command_center.vitrine.{m}").PAGINAS:
            if p["caminho"] in out:
                raise ErroBloco(f"{p['caminho']} está em dois módulos")
            out[p["caminho"]] = p
    return out


def caminhos_indexaveis():
    return [c for c, p in registro().items() if p.get("indexar", True)]


def obrigados():
    """As páginas de obrigado dos formulários (só caminhos registrados: o contato nunca redireciona para fora)."""
    return {b["obrigado"] for p in registro().values() for b in p["blocos"]
            if b["tipo"] == "formulario" and b.get("obrigado") in registro()}


def voltas_de_formulario():
    """As páginas com formulário: o contato volta para elas (com e sem JavaScript)."""
    return {c for c, p in registro().items() if any(b["tipo"] == "formulario" for b in p["blocos"])}


# ------------------------------------------------------------------ peças
def href(h):
    h = str(h or "")
    if not HREF_OK.fullmatch(h):
        raise ErroBloco(f"link não permitido: {h!r}")
    return e(h)


def _externo(h):
    return ' rel="noopener"' if str(h).startswith("https://") else ""


def inline(t):
    """Texto escapado, com [rótulo](href) e **negrito**."""
    t = str(t or "")
    partes, fim = [], 0
    for m in LINK.finditer(t):
        partes.append(_negrito(e(t[fim:m.start()])))
        alvo = m.group(2)
        partes.append(f'<a href="{href(alvo)}"{_externo(alvo)}>{_negrito(e(m.group(1)))}</a>')
        fim = m.end()
    partes.append(_negrito(e(t[fim:])))
    return "".join(partes)


def _negrito(html_escapado):
    return NEGRITO.sub(lambda m: f"<strong>{m.group(1)}</strong>", html_escapado)


def _ps(textos, classe=""):
    cl = f' class="{classe}"' if classe else ""
    return "".join(f"<p{cl}>{inline(t)}</p>" for t in (textos or ()))


def _lista(itens, classe="checks"):
    return f'<ul class="{classe}">' + "".join(f"<li>{inline(i)}</li>" for i in itens) + "</ul>" if itens else ""


def img(nome, alt, lazy=True, classe=""):
    w, h = tamanho_estatico(nome)
    if not w:
        raise ErroBloco(f"foto que não está em static/img: {nome}")
    cl = f' class="{classe}"' if classe else ""
    carga = ' loading="lazy"' if lazy else ' fetchpriority="high"'
    return f'<img{cl} src="{estatico("img/" + nome)}" alt="{e(alt or "")}" width="{w}" height="{h}"{carga}>'


def _botoes(ctas, primeiro="btn", resto="btn btn-linha", centro=False):
    if not ctas:
        return ""
    bs = "".join(f'<a class="{primeiro if i == 0 else resto}" href="{href(h)}"{_externo(h)}>{e(r)}</a>'
                 for i, (r, h) in enumerate(ctas))
    return f'<div class="hero-acoes{" centro" if centro else ""}">{bs}</div>'


def preco(chave):
    if chave == "kart":
        return f"From {usd(preco_kart())}"
    raise ErroBloco(f"preço sem fonte no painel: {chave!r}")


def _cabeca(b, i, nivel_extra=""):
    """O eyebrow, o h2 (com o id que a seção cita) e a introdução."""
    ey = f'<p class="eyebrow">{e(b["eyebrow"])}</p>' if b.get("eyebrow") else ""
    titulo = f'<h2 id="h-b{i}">{inline(b["titulo"])}</h2>' if b.get("titulo") else ""
    intro = _ps((b["intro"],) if isinstance(b.get("intro"), str) else b.get("intro"), "lede") if b.get("intro") else ""
    return ey + titulo + intro + nivel_extra


def _secao(b, i, miolo, largura="largura", padrao="clara"):
    fundo = b.get("fundo") or padrao
    if fundo not in FUNDOS:
        raise ErroBloco(f"fundo: {fundo}")
    ancora = b.get("ancora")
    if ancora and not ANCORA.fullmatch(ancora):
        raise ErroBloco(f"âncora: {ancora}")
    if b.get("titulo"):
        rotulo = f' aria-labelledby="h-b{i}"'
    elif b.get("rotulo_secao"):
        rotulo = f' aria-label="{e(b["rotulo_secao"])}"'
    else:
        rotulo = ""
    ident = f' id="{ancora}"' if ancora else ""
    return f'<section class="faixa {fundo}"{rotulo}{ident}><div class="{largura}">{miolo}</div></section>'


# ------------------------------------------------------------------ os blocos
def _hero(b, i, host, ctx):
    foto = img(b["foto"], b.get("alt", ""), lazy=False, classe="hero-foto") if b.get("foto") else ""
    nota = f'<p class="hero-nota small">{inline(b["nota"])}</p>' if b.get("nota") else ""
    return f"""<section class="hero hero-servico hero-bloco">{foto}
  <div class="hero-in">
    {f'<p class="eyebrow">{e(b["eyebrow"])}</p>' if b.get("eyebrow") else ''}
    <h1>{inline(b['h1'])}</h1>
    {f'<p class="hero-sub">{inline(b["sub"])}</p>' if b.get("sub") else ''}
    {_botoes(b.get("ctas"), "btn", "btn btn-linha-branca")}{nota}
  </div>
</section>"""


def _texto(b, i, host, ctx):
    corpo = _cabeca(b, i) + _ps(b.get("paragrafos")) + _lista(b.get("lista")) + _botoes(b.get("ctas"))
    if b.get("foto"):
        return _secao(b, i, f'<div class="texto">{corpo}</div>{img(b["foto"], b.get("alt", ""), classe="foto-redonda")}', "largura duas")
    return _secao(b, i, f'<div class="texto">{corpo}</div>', "largura estreita")


def _cartoes(b, i, host, ctx):
    escuro = (b.get("fundo") or "clara") != "clara"
    cards = []
    for c in b["itens"]:
        partes = []
        if c.get("foto"):
            partes.append(img(c["foto"], c.get("alt", "")))
        if c.get("rotulo"):
            partes.append(f'<p class="plano-sub">{e(c["rotulo"])}</p>')
        partes.append(f'<h3>{inline(c["titulo"])}</h3>')
        partes.append(_ps((c["texto"],) if isinstance(c.get("texto"), str) else c.get("texto")))
        partes.append(_lista(c.get("lista"), "lista"))
        if c.get("preco"):
            partes.append(f'<p class="plano-preco"><strong>{e(preco(c["preco"]))}</strong></p>')
        if c.get("link"):
            r, h = c["link"]
            partes.append(f'<a class="{"btn btn-sm" if escuro else "seta"}" href="{href(h)}"{_externo(h)}>{e(r)}</a>')
        cards.append(f'<article class="{"plano" if escuro else "cartao"}">{"".join(partes)}</article>')
    return _secao(b, i, _cabeca(b, i) + f'<div class="{"planos" if escuro else "cartoes"}">{"".join(cards)}</div>' + _botoes(b.get("ctas")))


def _passos(b, i, host, ctx):
    itens = "".join(f"<li><h3>{inline(t)}</h3>{_ps((x,) if isinstance(x, str) else x)}</li>" for t, x in b["itens"])
    return _secao(b, i, _cabeca(b, i) + f'<ol class="passos">{itens}</ol>' + _botoes(b.get("ctas")), padrao="escura")


def _numeros(b, i, host, ctx):
    itens = "".join(f'<div class="numero"><strong>{e(v)}</strong><span>{inline(r)}</span></div>' for v, r in b["itens"])
    return _secao(b, i, _cabeca(b, i) + f'<div class="numeros">{itens}</div>', padrao="escura")


def _figura(f):
    titulo = f"<strong>{inline(f['titulo'])}</strong>" if f.get("titulo") else ""
    legenda = f"<span>{inline(f['legenda'])}</span>" if f.get("legenda") else ""
    return f"<figure>{img(f['foto'], f.get('alt', ''))}<figcaption>{titulo}{legenda}</figcaption></figure>"


def _figuras(b, i, host, ctx):
    itens = "".join(_figura(f) for f in b["itens"])
    return _secao(b, i, _cabeca(b, i) + f'<div class="figuras">{itens}</div>', padrao="escura")


def _depoimentos(b, i, host, ctx):
    def um(d):
        n, quem, t = d
        return f'<blockquote><p>{inline(t)}</p><footer>{e(n)}{f" · {e(quem)}" if quem else ""}</footer></blockquote>'
    link = ""
    if b.get("link"):
        r, h = b["link"]
        link = f'<p><a class="seta" href="{href(h)}"{_externo(h)}>{e(r)}</a></p>'
    return _secao(b, i, _cabeca(b, i) + f'<div class="depoimentos">{"".join(um(d) for d in b["itens"])}</div>' + link, padrao="escura")


def _videos(b, i, host, ctx):
    itens = "".join(f'<li><a class="seta" href="{href(u)}"{_externo(u)}>{e(t)}</a></li>' for t, u in b["itens"])
    return _secao(b, i, _cabeca(b, i) + f'<ul class="videos">{itens}</ul>')


def _definicoes(b, i, host, ctx):
    itens = "".join(f"<div><dt>{inline(t)}</dt><dd>{inline(d)}</dd></div>" for t, d in b["itens"])
    return _secao(b, i, _cabeca(b, i) + f'<dl class="calendario">{itens}</dl>' + _botoes(b.get("ctas")), "largura estreita")


def _faq_itens(b):
    return [(q, (r,) if isinstance(r, str) else tuple(r)) for q, r in b["itens"]]


def _faq(b, i, host, ctx):
    detalhes = "".join(f'<details><summary>{e(q)}</summary><div class="faq-corpo">{_ps(r)}</div></details>'
                       for q, r in _faq_itens(b))
    return _secao(b, i, _cabeca(b, i) + f'<div class="faq">{detalhes}</div>', "largura estreita")


def _formulario(b, i, host, ctx):
    """O formulário de interesse: cai em Vendas pelo mesmo caminho do contato (`contato.js`, sem JavaScript também),
    com o assunto e a página de onde veio, e volta para esta página."""
    caminho = ctx["caminho"]
    enviado = ctx.get("enviado")
    obrigado = b.get("obrigado")
    if obrigado and not CAMINHO_SITE.fullmatch(obrigado):
        raise ErroBloco(f"obrigado: {obrigado!r}")
    obrigado_attr = f' data-obrigado="{e(obrigado)}"' if obrigado else ""
    obrigado_campo = f'<input type="hidden" name="obrigado" value="{e(obrigado)}">' if obrigado else ""
    mensagem = (f'<label>{e(b["mensagem"])} <span class="opcional">(optional)</span>'
                f'<textarea name="mensagem" maxlength="2000" rows="4"></textarea></label>') if b.get("mensagem") else ""
    miolo = _cabeca(b, i) + (f'<p>{inline(b["texto"])}</p>' if b.get("texto") else "") + f"""
  {'<p class="aviso-ok" role="status">Thank you! We got your information and will contact you shortly.</p>' if enviado else ''}
  <form class="form-contato" method="post" action="/ops/api/vitrine/contato" data-contato{obrigado_attr}>
    <input type="hidden" name="assunto" value="{e(b.get('assunto') or 'other')}"><input type="hidden" name="volta" value="{e(caminho)}">{obrigado_campo}
    <label>Full name<input name="nome" required autocomplete="name" maxlength="120"></label>
    <label>Email<input name="email" type="email" required autocomplete="email" maxlength="160"></label>
    <label>Phone<input name="telefone" type="tel" autocomplete="tel" maxlength="40"></label>
    {b.get("extras") or ""}{mensagem}
    <label class="escondido" aria-hidden="true">Leave this empty<input name="site" tabindex="-1" autocomplete="off"></label>
    <button class="btn btn-cheio" type="submit">{e(b.get('enviar') or 'Send')}</button>
    <p class="small muted">{inline(b.get('nota') or 'By sending this form, you agree to be contacted by the URACE team about your inquiry.')}</p>
    <p class="form-estado" role="status" aria-live="polite"></p>
  </form>"""
    return _secao(b, i, miolo, "largura estreita")


def _contador(b, i, host, ctx):
    """Dias, horas, minutos e segundos até `alvo` (o `blocos.js` conta; sem JavaScript fica a data por extenso)."""
    alvo = b["alvo"]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?[+-]\d{2}:\d{2}", alvo):
        raise ErroBloco(f"alvo do contador: {alvo!r} (ISO 8601 com fuso)")
    partes = "".join(f'<div><strong data-n="{k}">–</strong><span>{r}</span></div>'
                     for k, r in (("d", "days"), ("h", "hrs"), ("m", "min"), ("s", "sec")))
    miolo = _cabeca(b, i) + f"""<div class="contador" data-alvo="{e(alvo)}" role="timer" aria-live="off">{partes}</div>
  <p class="small muted">{inline(b.get('rotulo') or '')}</p>{_ps((b['texto'],)) if b.get('texto') else ''}"""
    return _secao(b, i, miolo, "largura centro", padrao="escura")


def _cta(b, i, host, ctx):
    miolo = f'<h2 id="h-b{i}">{inline(b["titulo"])}</h2>' + (f'<p class="fecho-sub">{inline(b["texto"])}</p>' if b.get("texto") else "")
    fundo = b.get("fundo") or "vermelha"
    primeiro = "btn btn-branco" if fundo == "vermelha" else "btn"
    return _secao({**b, "fundo": fundo}, i, miolo + _botoes(b.get("ctas"), primeiro, "btn btn-linha-branca", centro=True), "largura centro")


def _posts(b, i, host, ctx):
    from command_center.vitrine.paginas_site import _post_card, posts
    lista = (posts() or [])[: int(b.get("n") or 3)]
    if not lista:
        return ""                     # sem artigo no ar, a faixa não aparece (#172)
    link = '<p><a class="seta" href="/blog/">See all posts</a></p>'
    return _secao(b, i, _cabeca(b, i) + f'<div class="posts-grade">{"".join(_post_card(p) for p in lista)}</div>' + link, padrao="escura")


def _cartoes_painel(b, i, host, ctx):
    """Os cartões que a equipe edita em Site › Cartões das páginas (#297), com o preço do painel. Sem cartão: nada."""
    from command_center.vitrine.paginas_site import _grupos_dos_cartoes
    cartoes = (ctx.get("cartoes") or (lambda p: None))(b["pagina"])
    if not cartoes:
        return ""
    planos = (ctx.get("planos") or (lambda: None))()
    return _secao(b, i, _cabeca(b, i) + _grupos_dos_cartoes(cartoes, planos, b.get("assunto") or b["pagina"]), padrao="escura")


def _funcao(b, i, host, ctx):
    return b["render"](host, {**ctx, "indice": i})


DESENHO = {"hero": _hero, "texto": _texto, "cartoes": _cartoes, "passos": _passos, "numeros": _numeros,
           "figuras": _figuras, "depoimentos": _depoimentos, "videos": _videos, "definicoes": _definicoes, "faq": _faq,
           "formulario": _formulario, "contador": _contador, "cta": _cta, "posts": _posts,
           "cartoes_painel": _cartoes_painel, "funcao": _funcao}


# ------------------------------------------------------------------ a página
def corpo(host, d, ctx=None):
    ctx = {"caminho": d["caminho"], **(ctx or {})}
    return "\n".join(DESENHO[b["tipo"]](b, i, host, ctx) for i, b in enumerate(d["blocos"]))


def _trilha(host, d):
    passos = d.get("trilha") or ((d.get("nome") or d["titulo"].split(" | ")[0], d["caminho"]),)
    itens = [{"@type": "ListItem", "position": 1, "name": "Home", "item": f"https://{host}/"}]
    itens += [{"@type": "ListItem", "position": n, "name": nome, "item": f"https://{host}{c}"} for n, (nome, c) in enumerate(passos, 2)]
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": itens}


def schemas(host, d):
    out = [_negocio(host)]
    if d["caminho"] != "/":
        out.append(_trilha(host, d))
    faqs = [q for b in d["blocos"] if b["tipo"] == "faq" for q in _faq_itens(b)]
    if faqs:
        out.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": " ".join(_sem_marcas(x) for x in r)}}
            for q, r in faqs]})
    for s in d.get("schemas") or ():
        out.append(s(host) if callable(s) else s)
    return tuple(out)


def _sem_marcas(t):
    return NEGRITO.sub(r"\1", LINK.sub(r"\1", str(t)))


def pagina(host, d, ctx=None):
    scripts = ["contato.js"] if any(b["tipo"] == "formulario" for b in d["blocos"]) else []
    if any(b["tipo"] == "contador" for b in d["blocos"]):
        scripts.append("blocos.js")
    scripts += list(d.get("scripts") or ())
    return layout(host=host, caminho=d["caminho"], titulo=d["titulo"], descricao=d["descricao"], corpo=corpo(host, d, ctx),
                  schemas=schemas(host, d), scripts=tuple(dict.fromkeys(scripts)), foto=d.get("foto"),
                  indexar=d.get("indexar", True))


# ------------------------------------------------------------------ a conferência
def _textos(x):
    """Todo texto de um bloco (para a conferência), sem os campos que não são texto."""
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for k, v in x.items():
            if k not in ("tipo", "foto", "fundo", "ancora", "alvo", "render", "pagina", "preco", "assunto"):
                yield from _textos(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            yield from _textos(v)


def problemas(d):
    """O que impede a página de ir ao ar: sem título ou descrição, h1 ≠ 1, tipo ou fundo desconhecido, preço escrito."""
    out = []
    if not d.get("titulo") or not d.get("descricao"):
        out.append("título e descrição")
    if not str(d.get("caminho", "")).startswith("/") or not str(d.get("caminho", "")).endswith("/"):
        out.append("caminho começa e termina com /")
    hs = sum(1 for b in d.get("blocos", ()) if b.get("tipo") == "hero")
    if hs != 1:
        out.append(f"um hero (o h1) por página: {hs}")
    for n, b in enumerate(d.get("blocos", ())):
        if b.get("tipo") not in TIPOS:
            out.append(f"bloco {n}: tipo {b.get('tipo')!r}")
        if b.get("fundo") and b["fundo"] not in FUNDOS:
            out.append(f"bloco {n}: fundo {b['fundo']!r}")
        if b.get("tipo") == "cartoes":
            for c in b.get("itens", ()):
                if c.get("preco") and c["preco"] not in PRECOS_DO_PAINEL:
                    out.append(f"bloco {n}: preço sem fonte no painel: {c['preco']!r}")
    for t in _textos(d):
        if PRECO.search(t):
            out.append(f"preço escrito no texto (vem do painel): {t[:80]!r}")
    return out


def json_ld(d, host="novo.urace.us"):
    return json.dumps(schemas(host, d), ensure_ascii=False)
