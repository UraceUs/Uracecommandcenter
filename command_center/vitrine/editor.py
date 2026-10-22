"""O editor visual do site público (#300): o modelo da página, a validação e o desenho.

Dono, 16/10: *"no Command Center separe o site público uma seção para o site público aí no site público a gente
tenha é, como alterar o design, layout, puxando e arrastando e soltando de uma forma bem simples e conseguir editar
por lá como se fosse realmente um WordPress"*. Decisão: **livre, tipo Elementor**.

A página é uma lista de itens, de cima para baixo:
- **seção** (`secao`): fundo, espaçamento e 1 a 3 colunas; cada coluna tem os seus elementos;
- **seção original** (`original`): numa página que já existe no site, cada faixa dela vira um item que se move ou
  se esconde, e continua viva (o preço do painel, a agenda, a loja). Entre elas entram as seções novas.

Elementos: título (h1/h2/h3), texto (negrito, itálico, lista), imagem (WebP do painel), botão, lista, espaço, os
karts do Arrive and Drive, produtos da loja, os cartões de uma página e perguntas frequentes. Karts, produtos e
cartões vêm do banco (#297, #298), nunca de texto colado.

Cor, tamanho e espaçamento são escolhas da paleta do site (classes, sem estilo solto: a política do site não deixa
estilo inline, e a paleta garante o contraste). Na publicação, `problemas()` confere o que o editor gerou: um h1,
título sem pular nível, foto com descrição, título e descrição da página.

#315 (dono, 16/10: *"ele abre uma mini visualização de como é o site público. E dali a pessoa consegue, por ali, clicar
no que ela precisa editar … É como se fosse um Canva"*): a prévia virou a área de trabalho. Para isso:
- `corpo(..., marcar=True)` põe `data-ed-*` em cada seção, coluna e elemento (e um marcador no elemento vazio), só na
  prévia de edição; o HTML do site fica igual byte a byte;
- o **rascunho é tolerante** (`limpar(..., rascunho=True)`): título ou botão vazio passam e viram problema na publicação;
  link, foto ou texto que não passam ficam com o valor anterior do mesmo elemento e voltam em `erros`. Link inseguro
  nunca é gravado, nem no rascunho.

#315, etapa 4 (o texto das faixas originais): o item `original` ganha `textos` (`{"<tag>.<n>:<hash8>": "texto novo"}`).
- Só se escreve numa **folha de texto puro** da faixa (h1–h3, p, li, summary, figcaption, a.btn, sem nada dentro além
  de texto). A chave é a tag, a posição dela na faixa e o hash do texto do código.
- **Blocos de dado ficam travados** (`TRAVADOS`): planos e cartões, preços, a reserva (karts e agenda), o blog, a loja,
  formulários e as palavras de pessoas de verdade (depoimentos, campeões). Folha com preço (`$719`) também. NO FAKE DATA e
  uma fonte só: o que vem do banco nunca vira texto sobrescrito. O servidor recusa a chave de um texto travado.
- `aplicar_textos()` troca só onde o hash do texto do código bate. Se o código mudou, a troca fica de fora e aparece
  como **texto órfão** nas pendências (o painel descarta). Texto de até 400 caracteres, sempre escapado.
- Sem troca, a faixa sai byte a byte igual à de antes.
- Revisão do #337: a faixa original se acha pela **âncora** (o `id` ou o `aria-labelledby` da `<section>`, `ancoras()`),
  não pela posição: a home sem artigo no ar perde a faixa do blog e as de baixo sobem, mas cada item continua na faixa
  dele (`alinhar()`; o rascunho antigo, só com `indice`, ganha a âncora na leitura). A faixa que saiu da página fica no
  rascunho no lugar dela, e as trocas dela viram texto órfão. Texto escrito com preço (`$99`, `USD 99`, `99 dollars`),
  na faixa ou num elemento, é pendência: o preço vem do painel. O JSON-LD segue a folha (a pergunta frequente pela posição
  dela na faixa da FAQ; o `name` do serviço e da trilha pelo h1), não o texto igual em outro lugar.
"""
import functools
import hashlib
import json
import re
import secrets
from html import escape as e
from html import unescape
from html.parser import HTMLParser

from command_center.vitrine import html_seguro

FUNDOS = {"clara": "clara", "escura": "escura", "marca": "vermelha", "cinza": "ed-cinza"}
ESPACOS = ("p", "m", "g")
TAMANHOS = ("p", "m", "g")
CORES = ("padrao", "marca", "suave")
ALINHAR = ("esq", "centro")
FORMAS = ("larga", "media", "quadrada")
PAGINAS_CARTOES = ("academy", "pro-team", "for-beginners")
WIDGETS = ("titulo", "texto", "imagem", "botao", "lista", "espaco", "karts", "produtos", "cartoes", "faq")
MAX_ITENS = 60
MAX_POR_COLUNA = 30
MAX_TEXTO_ORIGINAL = 400
MAX_TEXTOS = 300             # trocas por faixa original
CHAVE_TEXTO = re.compile(r"(h1|h2|h3|p|li|summary|figcaption|a)\.[0-9]{1,4}:[0-9a-f]{8}")
ANCORA = re.compile(r"[A-Za-z0-9_.#~-]{1,80}")
CAMINHO = re.compile(r"/(?:[a-z0-9]+(?:-[a-z0-9]+)*/)+")
# o que não pode virar página nova: o painel, os arquivos, a loja, o blog, o carrinho, o pedido, as páginas legais
RESERVADOS = ("/ops/", "/_s/", "/_f/", "/store/", "/blog/", "/cart/", "/order/", "/legal/", "/contact/", "/sitemap", "/robots")


class ErroEditor(ValueError):
    pass


def novo_id():
    return secrets.token_hex(4)


def _txt(v, n, campo, obrigatorio=False):
    t = re.sub(r"\s+", " ", str(v or "")).strip()
    if obrigatorio and not t:
        raise ErroEditor(f"{campo}: escreva o texto")
    if len(t) > n:
        raise ErroEditor(f"{campo}: até {n} caracteres")
    return t


class _Rascunho:
    """#315: o que o rascunho deixa passar. Fora do rascunho (`ligado=False`) o erro sobe como sempre; no rascunho, o
    campo fica com o valor anterior do mesmo elemento e o motivo vai para `erros`."""
    def __init__(self, ligado, anterior):
        self.ligado, self.ant, self.erros = ligado, anterior or {}, []

    def campo(self, nome, fazer, padrao):
        try:
            return fazer()
        except ErroEditor as x:
            if not self.ligado:
                raise
            self.erros.append(str(x))
            return self.ant.get(nome, padrao)

    def texto(self, v, n, campo, obrigatorio=False):
        if self.ligado:     # no meio da edição: vazio passa (vira problema na publicação), comprido é cortado e avisado
            t = re.sub(r"\s+", " ", str(v or "")).strip()
            if len(t) > n:
                self.erros.append(f"{campo}: até {n} caracteres")
            return t[:n]
        return _txt(v, n, campo, obrigatorio)


def _escolha(v, opcoes, padrao):
    return v if v in opcoes else padrao


def link_ok(v):
    """Só caminho do próprio site ou https (nada de javascript:, data:)."""
    t = (v or "").strip()
    if re.fullmatch(r"/[A-Za-z0-9/_\-.?=&%#]*", t) or re.fullmatch(r"https://[^\s\"'<>]+", t) \
            or re.fullmatch(r"(tel:\+?[0-9 ()-]{6,20}|mailto:[^\s\"'<>@]+@[^\s\"'<>]+)", t):
        return t[:300]
    raise ErroEditor("link: use um caminho do site (ex.: /contact/), https://, tel: ou mailto:")


def foto_ok(src):
    """A foto tem de ser do site: subida no editor (/_f/…), da loja (/store/img/…) ou das fotos do site."""
    s = str(src or "")
    if re.fullmatch(r"/_f/[0-9a-f]{16}\.webp", s) or re.fullmatch(r"/store/img/[0-9]+-[0-9a-f]{16}\.webp", s):
        return s
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,150}\.(webp|jpg|jpeg|png|svg)", s) and ".." not in s:
        return s
    raise ErroEditor("imagem: suba a foto pelo editor")


# ------------------------------------------------------------------ validação
def _widget(w, rascunho=False, anterior=None):
    """Um elemento → o modelo. `rascunho` (#315): o estado do meio da edição passa (ver `_Rascunho`); `anterior` é o
    mesmo elemento como estava salvo. Devolve o elemento e a lista de erros (vazia fora do rascunho)."""
    if not isinstance(w, dict) or w.get("tipo") not in WIDGETS:
        raise ErroEditor("elemento desconhecido")
    t = w["tipo"]
    out = {"id": re.sub(r"[^a-z0-9]", "", str(w.get("id") or ""))[:12] or novo_id(), "tipo": t}
    r = _Rascunho(rascunho, anterior if isinstance(anterior, dict) and anterior.get("tipo") == t else None)
    if t in ("titulo", "texto", "botao"):
        out["alinhar"] = _escolha(w.get("alinhar"), ALINHAR, "esq")
    if t in ("titulo", "texto"):
        out["tamanho"] = _escolha(w.get("tamanho"), TAMANHOS, "m")
        out["cor"] = _escolha(w.get("cor"), CORES, "padrao")
    if t == "titulo":
        out["texto"] = r.texto(w.get("texto"), 160, "título", True)
        out["nivel"] = w.get("nivel") if w.get("nivel") in (1, 2, 3) else 2
    elif t == "texto":
        def html():
            # #315: o texto editado na prévia (contenteditable) separa as linhas com <div>: vira parágrafo
            h = html_seguro.limpar(re.sub(r"<(/?)div\b[^>]*>", r"<\1p>", str(w.get("html") or "")))
            if len(h) > html_seguro.MAX:
                raise ErroEditor("texto longo demais")
            return h
        out["html"] = r.campo("html", html, "")
    elif t == "imagem":
        src = w.get("src")
        out["src"] = "" if rascunho and not src else r.campo("src", lambda: foto_ok(src), "")
        out["alt"] = r.texto(w.get("alt"), 200, "descrição da foto")
        out["forma"] = _escolha(w.get("forma"), FORMAS, "larga")
        out["largura"] = max(1, min(4000, int(w.get("largura") or 1600)))
        out["altura"] = max(1, min(4000, int(w.get("altura") or 900)))
        out["legenda"] = r.texto(w.get("legenda"), 200, "legenda")
    elif t == "botao":
        out["texto"] = r.texto(w.get("texto"), 60, "botão", True)
        link = w.get("link")
        out["link"] = "" if rascunho and not str(link or "").strip() else r.campo("link", lambda: link_ok(link), "")
        out["estilo"] = _escolha(w.get("estilo"), ("cheio", "linha"), "cheio")
    elif t == "lista":
        itens = [r.texto(x, 200, "item da lista") for x in (w.get("itens") or [])][:30]
        out["itens"] = [x for x in itens if x]
    elif t == "espaco":
        out["tamanho"] = _escolha(w.get("tamanho"), TAMANHOS, "m")
    elif t == "produtos":
        out["categoria"] = re.sub(r"[^a-z0-9-]", "", str(w.get("categoria") or ""))[:40]
        out["quantos"] = max(3, min(12, int(w.get("quantos") or 6)))
    elif t == "cartoes":
        out["pagina"] = _escolha(w.get("pagina"), PAGINAS_CARTOES, "academy")
    elif t == "faq":
        itens = []
        for x in (w.get("itens") or [])[:20]:
            q = r.texto((x or {}).get("pergunta"), 200, "pergunta")
            a = r.texto((x or {}).get("resposta"), 1200, "resposta")
            if q and a or rascunho and (q or a):      # no rascunho, a pergunta ainda sem resposta fica
                itens.append({"pergunta": q, "resposta": a})
        out["itens"] = itens
    return out, r.erros


def _elementos(conteudo):
    """{id: elemento} de um conteúdo já guardado (o "anterior" do rascunho)."""
    if not isinstance(conteudo, dict):
        return {}
    return {w.get("id"): w for it in conteudo.get("itens") or [] if isinstance(it, dict) and it.get("tipo") == "secao"
            for c in it.get("itens") or [] if isinstance(c, list) for w in c if isinstance(w, dict)}


def _textos(v, html, rascunho, problemas, conferir=False, antes=None):
    """#315, etapa 4: as trocas de texto de uma faixa original → o que se guarda. Chave no formato da folha, texto
    numa linha, até 400 caracteres (só texto: o desenho escapa). Com o HTML da faixa (`html`), a troca de um texto
    travado (preço, plano, kart, reserva…) é recusada e a que volta ao texto do código sai.

    `conferir` (o painel manda as faixas do código): a chave que não está na faixa (ou a faixa que saiu da página,
    `html` None) só fica se já estava guardada (`antes`, as trocas de antes deste item): é o texto órfão, avisado nas
    pendências. Chave nova que não existe não se guarda (ninguém enche o rascunho de texto inventado)."""
    if v in (None, {}):
        return {}
    if not isinstance(v, dict) or len(v) > MAX_TEXTOS:
        raise ErroEditor("textos da faixa original inválidos")
    folhas, travadas, _ = _analisar(html) if html is not None else ((), {}, ())
    do_codigo = {f.chave: f.texto for f in folhas}
    antes = antes or {}
    out = {}
    for k, t in v.items():
        if not isinstance(k, str) or not CHAVE_TEXTO.fullmatch(k) or not isinstance(t, str):
            raise ErroEditor("textos da faixa original inválidos")
        if conferir and k not in do_codigo and k not in travadas and k not in antes:
            if not rascunho:
                raise ErroEditor("esse texto não está na faixa original")
            problemas.append("esse texto não está na faixa original (a página do código mudou): escreva de novo")
            continue
        if k in travadas and k not in do_codigo:
            msg = f"esse texto vem do painel ({AREAS_TRAVADAS[travadas[k][0]]}): mude lá, não na faixa"
            if not rascunho:
                raise ErroEditor(msg)
            problemas.append(msg)
            continue
        t = re.sub(r"\s+", " ", t).strip()
        if len(t) > MAX_TEXTO_ORIGINAL:
            if not rascunho:
                raise ErroEditor(f"texto da faixa original: até {MAX_TEXTO_ORIGINAL} caracteres")
            problemas.append(f"texto da faixa original: até {MAX_TEXTO_ORIGINAL} caracteres")
            t = t[:MAX_TEXTO_ORIGINAL].rstrip()
        if t and do_codigo.get(k) != t:       # vazio, ou igual ao do código: fica o do código
            out[k] = t
    return out


def limpar(conteudo, com_originais=False, n_originais=0, rascunho=False, anterior=None, erros=None, originais=None):
    """O que veio do painel → o modelo guardado. Recusa o que não é do modelo; nunca guarda HTML solto.

    `rascunho` (#315): o meio da edição passa (ver `_widget`); `anterior` é o conteúdo salvo antes (o valor que fica
    quando um campo não passa) e `erros` (um dict) recebe `{id do elemento: motivo}`. `originais` (etapa 4): o HTML
    das faixas da página do código, para conferir as trocas de texto delas (`_textos`)."""
    itens = (conteudo or {}).get("itens") if isinstance(conteudo, dict) else None
    if not isinstance(itens, list):
        raise ErroEditor("página sem itens")
    if len(itens) > MAX_ITENS:
        raise ErroEditor(f"até {MAX_ITENS} seções por página")
    antes = _elementos(anterior) if rascunho else {}
    anc = ancoras(originais) if originais is not None else None
    # as faixas originais de antes (as trocas guardadas e a faixa que saiu da página), pela âncora
    ant = {x["ancora"]: x for x in _alinhar_itens(anterior, anc)} if anc is not None and isinstance(anterior, dict) else {}
    out, vistos = [], set()
    for it in itens:
        if not isinstance(it, dict):
            raise ErroEditor("item inválido")
        if it.get("tipo") == "original":
            if not com_originais:
                raise ErroEditor("seção original só existe numa página que já está no site")
            a = it.get("ancora") if isinstance(it.get("ancora"), str) and ANCORA.fullmatch(it["ancora"]) else None
            if anc is None:                       # sem as faixas do código: confere só a posição
                i = int(it.get("indice", -1))
                if not 0 <= i < n_originais:
                    raise ErroEditor("seção original inválida")
            elif a is None:                       # o rascunho de antes da âncora: a posição dá a âncora
                i = int(it.get("indice", -1))
                if not 0 <= i < len(anc):
                    if rascunho:
                        continue                  # a faixa daquela posição não existe mais (nada guardado nela)
                    raise ErroEditor("seção original inválida")
                a = anc[i]
            elif a in anc:
                i = anc.index(a)
            elif a in ant:                        # a faixa saiu da página do código: fica no lugar, sem desenho
                i = None
            else:
                raise ErroEditor("seção original inválida")
            marca = a or i
            if marca in vistos:
                raise ErroEditor("seção original inválida")
            vistos.add(marca)
            o = {"id": f"o{i}" if i is not None else _id_ausente(a), "tipo": "original", "indice": -1 if i is None else i,
                 "oculto": bool(it.get("oculto"))}
            if a:
                o["ancora"] = a
            probs = []
            html = originais[i] if originais is not None and i is not None else None
            textos = _textos(it.get("textos"), html, rascunho, probs, conferir=anc is not None,
                             antes=(ant.get(a) or {}).get("textos"))
            if probs and erros is not None:
                erros[o["id"]] = "; ".join(dict.fromkeys(probs))
            if textos:          # sem troca, o item fica como sempre foi (o rascunho antigo continua igual ao publicado)
                o["textos"] = textos
            out.append(o)
            continue
        if it.get("tipo") != "secao":
            raise ErroEditor("item inválido")
        n = it.get("colunas") if it.get("colunas") in (1, 2, 3) else 1
        cols = list(it.get("itens") or [])[:n]
        cols += [[] for _ in range(n - len(cols))]
        colunas = []
        for c in cols:
            if not isinstance(c, list) or len(c) > MAX_POR_COLUNA:
                raise ErroEditor(f"até {MAX_POR_COLUNA} elementos por coluna")
            col = []
            for w in c:
                feito, problemas_w = _widget(w, rascunho, antes.get(str((w or {}).get("id") or "")) if isinstance(w, dict) else None)
                if problemas_w and erros is not None:
                    erros[feito["id"]] = "; ".join(dict.fromkeys(problemas_w))
                col.append(feito)
            colunas.append(col)
        out.append({"id": re.sub(r"[^a-z0-9]", "", str(it.get("id") or ""))[:12] or novo_id(), "tipo": "secao",
                    "fundo": _escolha(it.get("fundo"), FUNDOS, "clara"), "espaco": _escolha(it.get("espaco"), ESPACOS, "m"),
                    "colunas": n, "itens": colunas})
    return {"itens": out}


def slug(t):
    import unicodedata
    s = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60] or "page"


def caminho_novo(v):
    c = "/" + "/".join(p for p in str(v or "").strip().lower().split("/") if p) + "/"
    if not CAMINHO.fullmatch(c) or len(c) > 120:
        raise ErroEditor("endereço: use letras, números e hífen, como /summer-camp/")
    if c == "/" or any(c.startswith(r) for r in RESERVADOS):
        raise ErroEditor(f"o endereço {c} é do sistema; escolha outro")
    return c


# ------------------------------------------------------------------ as seções que a página já tem
def _linhas(html):
    """Onde começa cada linha, como o `HTMLParser.getpos()` conta: só o `\n` quebra linha (o `splitlines()` também
    quebraria em `\r`, `\x0c`, `\u2028`… e as posições escorregariam, corrompendo o HTML)."""
    out = [0]
    for linha in html.split("\n"):
        out.append(out[-1] + len(linha) + 1)
    return out


class _Secoes(HTMLParser):
    """Separa o `<main>` de uma página do site nas faixas de cima (`<section>` de primeiro nível)."""
    def __init__(self, html):
        super().__init__(convert_charrefs=False)
        self.html, self.pos, self.nivel, self.inicio, self.secoes = html, 0, 0, None, []
        self._linhas = _linhas(html)

    def _onde(self):
        ln, col = self.getpos()
        return self._linhas[ln - 1] + col

    def handle_starttag(self, tag, attrs):
        if tag == "section":
            if self.nivel == 0:
                self.inicio = self._onde()
            self.nivel += 1

    def handle_endtag(self, tag):
        if tag == "section" and self.nivel:
            self.nivel -= 1
            if self.nivel == 0 and self.inicio is not None:
                fim = self.html.index(">", self._onde()) + 1
                self.secoes.append(self.html[self.inicio:fim])
                self.inicio = None


def extrair(html):
    """Do HTML de uma página do site: as faixas (seções), o título, a descrição, o JSON-LD e os scripts dela."""
    m = re.search(r'<main id="conteudo">(.*)</main>', html, re.S)
    p = _Secoes(m.group(1) if m else "")
    p.feed(m.group(1) if m else "")
    titulo = re.search(r"<title>(.*?)</title>", html, re.S)
    desc = re.search(r'<meta name="description" content="(.*?)">', html, re.S)
    from html import unescape
    lds = []
    for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            lds.append(json.loads(x))
        except ValueError:
            pass
    padrao = {"campanha.js", "carrinho.js", "medicao.js", "site.js"}
    scripts = [s for s in re.findall(r'<script src="/_s/([a-z0-9_-]+\.js)\?v=', html) if s not in padrao]
    return {"secoes": p.secoes, "titulo": unescape(titulo.group(1)) if titulo else "",
            "descricao": unescape(desc.group(1)) if desc else "", "ld": lds, "scripts": list(dict.fromkeys(scripts))}


# ------------------------------------------------------------------ #315, etapa 4: o texto das faixas originais
# Os blocos que mostram dado do banco (ou do sistema) numa página do código: nada dentro deles vira texto escrito no
# editor. Levantado nas páginas que o editor abre (`api/vitrine.EDITAVEIS`); `test_editor_site` trava a lista.
# classe do bloco → área (de onde o dado vem e onde se muda; ver `AREAS_TRAVADAS` e a dica do painel)
TRAVADOS = {
    "planos": "cartoes",        # planos da Academy e do Pro Team, cartões das páginas (Serviços e preços, Cartões)
    "mt": "cartoes",            # o título de cada grupo de planos ("4-stroke and Baby Kart · $689 per session")
    "preco": "precos",          # "Starting at $719" da home (o menor preço de kart do painel)
    "hero-preco": "precos",     # "From $719 per driver" do Arrive and Drive
    "preco-grande": "precos",   # "Investment" dos eventos (o preço por piloto do painel)
    "servicos-grade": "precos",  # os programas do /services/ ("Starting at $719")
    "karts": "reserva",         # os karts da reserva, com o preço de cada um (Serviços e preços)
    "agenda": "reserva",        # a agenda e o total da reserva (agenda.js, os dias abertos e o depósito)
    "posts-grade": "blog",      # os artigos do blog na home (Site › Blog)
    "produtos-grade": "loja",   # produtos da loja (Produtos da loja e o estoque)
    "depoimentos": "pessoas",   # palavras de clientes de verdade: não se reescrevem
    "campeoes": "pessoas",      # nomes e resultados de pilotos de verdade
}
TAGS_TRAVADAS = {"form": "formulario", "fieldset": "formulario",   # o que o formulário envia é do sistema
                 "blockquote": "pessoas"}                          # a citação é a palavra de alguém de verdade
AREAS_TRAVADAS = {"cartoes": "Serviços e preços / Cartões das páginas", "precos": "Serviços e preços",
                  "reserva": "Serviços e preços", "blog": "Site › Blog", "loja": "Produtos da loja",
                  "pessoas": "palavras e nomes de pessoas de verdade", "formulario": "formulário do sistema"}
# preço escrito ($99, US$ 99, USD 99, 99 USD, 99 dollars): o preço é do painel, não do texto (a folha do código com
# preço fica travada; o texto novo com preço é pendência, `problemas()`)
PRECO = re.compile(r"(?:US)?\$\s?\d|\bUSD\s?\d|\d\s?USD\b|\b\d[\d,.]*\s*dollars?\b", re.I)
MSG_PRECO = "O preço vem de Serviços e preços / Loja; escreva sem o valor"
_FOLHAS = {"h1", "h2", "h3", "p", "li", "summary", "figcaption", "a"}
_VAZIAS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class _Folha:
    __slots__ = ("chave", "tag", "ini", "dentro", "fim", "texto", "faq")

    def __init__(self, chave, tag, ini, dentro, fim, texto, faq=None):
        self.chave, self.tag, self.ini, self.dentro, self.fim, self.texto = chave, tag, ini, dentro, fim, texto
        self.faq = faq      # (id da lista de perguntas, número da pergunta, "pergunta" ou "resposta"), ou None


def _chave(tag, n, texto):
    return f"{tag}.{n}:{hashlib.sha256(texto.encode()).hexdigest()[:8]}"


class _Analise(HTMLParser):
    """Percorre uma faixa: as folhas de texto puro (fora dos blocos travados) e os blocos travados."""
    def __init__(self, html):
        super().__init__(convert_charrefs=False)
        self.html, self.pilha, self.cont, self.cont_trava = html, [], {}, {}
        self.folhas, self.travadas, self.blocos = [], {}, []     # blocos: [(posição do atributo, área)]
        self.n_faq = {}                                           # perguntas vistas em cada lista (`div.faq`)
        self._linhas = _linhas(html)

    def _onde(self):
        ln, col = self.getpos()
        return self._linhas[ln - 1] + col

    def handle_starttag(self, tag, attrs):
        pai = self.pilha[-1] if self.pilha else None
        if pai:
            pai["filhos"] = True
        if tag in _VAZIAS:
            return
        ini = self._onde()
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        area = next((TRAVADOS[c] for c in classes if c in TRAVADOS), None) or TAGS_TRAVADAS.get(tag)
        trava = pai["trava"] if pai and pai["trava"] else None
        if area and not trava:
            self.blocos.append((ini + 1 + len(tag), area))
        # a posição na chave conta só o que está fora dos blocos travados: um plano ou um kart a mais no banco não
        # muda a chave dos textos que se escrevem (a conta de dentro é outra)
        cont = self.cont_trava if trava or area else self.cont
        cont[tag] = cont.get(tag, -1) + 1
        folha = tag in _FOLHAS and (tag != "a" or "btn" in classes)
        # onde a folha está numa lista de perguntas frequentes (o JSON-LD da FAQ segue a posição, não o texto)
        faq = pai["faq"] if pai else None
        if tag == "div" and "faq" in classes:
            faq = (a.get("id") or "faq", None, None)
        elif faq and tag == "details":
            self.n_faq[faq[0]] = self.n_faq.get(faq[0], -1) + 1
            faq = (faq[0], self.n_faq[faq[0]], None)
        elif faq and faq[1] is not None and tag == "summary":
            faq = (faq[0], faq[1], "pergunta")
        elif faq and faq[1] is not None and "faq-corpo" in classes:
            faq = (faq[0], faq[1], "resposta")
        self.pilha.append({"tag": tag, "ini": ini, "dentro": ini + len(self.get_starttag_text()), "n": cont[tag],
                           "folha": folha, "filhos": False, "texto": [], "trava": trava or area, "faq": faq})

    def handle_startendtag(self, tag, attrs):
        if self.pilha:
            self.pilha[-1]["filhos"] = True

    def _texto(self, t):
        if self.pilha:
            self.pilha[-1]["texto"].append(t)

    def handle_data(self, d):
        self._texto(d)

    def handle_entityref(self, nome):
        self._texto(f"&{nome};")

    def handle_charref(self, nome):
        self._texto(f"&#{nome};")

    def handle_endtag(self, tag):
        if not any(f["tag"] == tag for f in self.pilha):
            return
        fim = self._onde()
        while self.pilha:
            f = self.pilha.pop()
            if f["tag"] == tag:
                break
        if not f["folha"] or f["filhos"]:
            return
        texto = re.sub(r"\s+", " ", unescape("".join(f["texto"]))).strip()
        if not texto:
            return
        chave = _chave(tag, f["n"], texto)
        area = f["trava"] or ("precos" if PRECO.search(texto) else None)
        if area:
            self.travadas[chave] = (area, texto)
            if not f["trava"]:                # a folha com preço é o próprio bloco travado
                self.blocos.append((f["ini"] + 1 + len(tag), area))
            return
        faq = f["faq"] if f["faq"] and f["faq"][2] else None
        self.folhas.append(_Folha(chave, tag, f["ini"], f["dentro"], fim, texto, faq))


@functools.lru_cache(maxsize=256)
def _analisar(html):
    """(folhas de texto que se escrevem, {chave do texto travado: (área, texto)}, blocos travados) de uma faixa. A
    faixa é a mesma em cada requisição (a página do código), então a conta fica guardada."""
    p = _Analise(html)
    p.feed(html)
    p.close()
    return tuple(p.folhas), dict(p.travadas), tuple(sorted(p.blocos))


def _reescrever(html, textos, marcar=False, i=None, oculto=False):
    """A faixa com as trocas de texto (`textos`) e, na prévia de edição (`marcar`), os `data-ed-*`. Devolve o HTML e as
    chaves que não acharam a folha (os textos órfãos)."""
    folhas, _travadas, blocos = _analisar(html)
    textos = textos or {}
    mudas = []                          # (posição, quanto tira, o que põe)
    usadas = set()
    for f in folhas:
        novo = textos.get(f.chave)
        if marcar:
            orig = f' data-ed-orig="{e(f.texto)}"' if novo is not None else ""
            mudas.append((f.ini + 1 + len(f.tag), 0, f' data-ed-t="{f.chave}"{orig}'))
        if novo is not None:
            usadas.add(f.chave)
            mudas.append((f.dentro, f.fim - f.dentro, e(novo)))
    if marcar:
        mudas += [(pos, 0, f' data-ed-trava="{area}"') for pos, area in blocos]
        extra = f' data-ed-s="o{i}" data-ed-o="{i}"' + (' data-ed-oculto=""' if oculto else "")
        m = re.match(r"\s*<section\b", html)
        if m:
            mudas.append((m.end(), 0, extra))
    out = html
    for pos, tira, poe in sorted(mudas, key=lambda x: x[0], reverse=True):
        out = out[:pos] + poe + out[pos + tira:]
    return out, [k for k in textos if k not in usadas]


def aplicar_textos(html, textos):
    """A faixa original com as trocas de texto que ainda batem com o código: `(html, órfãs)`. Sem troca, o mesmo
    HTML, byte a byte."""
    if not textos:
        return html, []
    return _reescrever(html, textos)


def marcar_original(html, i, oculto=False, textos=None):
    """A faixa original na prévia de edição: `data-ed-s`/`data-ed-o` na `<section>` de fora (a escondida aparece
    apagada, `data-ed-oculto`, para dar para mostrar de novo clicando nela), `data-ed-t` em cada texto que se escreve
    (com `data-ed-orig`, o texto do código, quando já foi trocado) e `data-ed-trava` em cada bloco de dado."""
    return _reescrever(html, textos, marcar=True, i=i, oculto=oculto)[0]


def orfaos(conteudo, originais):
    """{id da faixa original: [chaves]} das trocas que não acham mais o texto: a página do código mudou o texto, ou a
    faixa inteira saiu da página (todas as trocas dela)."""
    out = {}
    for it in alinhar(conteudo, originais)["itens"]:
        if it["tipo"] != "original" or not it.get("textos"):
            continue
        o = list(it["textos"]) if not 0 <= it["indice"] < len(originais) else aplicar_textos(originais[it["indice"]], it["textos"])[1]
        if o:
            out[it["id"]] = o
    return out


def ld_com_textos(lds, conteudo, originais):
    """O JSON-LD da página do código dizendo o mesmo que ela, com as trocas que valem. Segue a **folha**, não o texto
    igual em outro lugar:
    - FAQPage: só a lista de perguntas que a alimenta (a da página com as mesmas perguntas do código, na mesma ordem);
      a pergunta trocada vira o `name` dela, e o parágrafo trocado entra na resposta dela (`text`), pela posição.
    - O h1: o `name` igual ao h1 do código (o do serviço, `Service`, e o último passo da trilha, `BreadcrumbList`)
      vira o h1 novo, o que a página mostra. Nenhum outro texto (o eyebrow, um parágrafo igual) mexe no JSON-LD."""
    faqs, h1 = {}, None           # faqs: {(faixa, lista): {pergunta: {"pergunta": texto do código, "nova": …, "resp": […]}}}
    for it in alinhar(conteudo, originais)["itens"]:
        if it["tipo"] != "original" or not 0 <= it["indice"] < len(originais):
            continue
        textos = it.get("textos") or {}
        for f in _analisar(originais[it["indice"]])[0]:
            novo = textos.get(f.chave)
            if f.faq:
                q = faqs.setdefault((it["indice"], f.faq[0]), {}).setdefault(f.faq[1], {"pergunta": None, "nova": None, "resp": []})
                if f.faq[2] == "pergunta":
                    q["pergunta"], q["nova"] = f.texto, novo
                elif novo is not None:
                    q["resp"].append((f.texto, novo))
            elif f.tag == "h1" and novo is not None:
                h1 = (f.texto, novo)
    mudou = h1 or any(q["nova"] or q["resp"] for lista in faqs.values() for q in lista.values())
    if not mudou:
        return list(lds)
    lds = json.loads(json.dumps(list(lds)))

    def faq_page(obj):
        perguntas = obj.get("mainEntity") or []
        nomes = [q.get("name") for q in perguntas if isinstance(q, dict)]
        lista = next((x for x in faqs.values() if [x[k]["pergunta"] for k in sorted(x)] == nomes), None)
        if lista is None:
            return
        for n, q in enumerate(perguntas):
            d = lista[sorted(lista)[n]]
            if d["nova"]:
                q["name"] = d["nova"]
            resp = q.get("acceptedAnswer") or {}
            for velho, novo in d["resp"]:
                if isinstance(resp.get("text"), str):
                    resp["text"] = resp["text"].replace(velho, novo, 1)

    def nome_h1(v):
        if isinstance(v, dict):
            if v.get("@type") == "FAQPage":
                return
            if h1 and v.get("name") == h1[0] and v.get("@type") in ("Service", "ListItem", "Course", "SportsTeam"):
                v["name"] = h1[1]
            for x in v.values():
                nome_h1(x)
        elif isinstance(v, list):
            for x in v:
                nome_h1(x)
    for obj in lds:
        if isinstance(obj, dict) and obj.get("@type") == "FAQPage":
            faq_page(obj)
        nome_h1(obj)
    return lds


def de_uma_pagina(n, ancs=None):
    """O conteúdo inicial de uma página que já existe: as faixas dela, na ordem, como seções originais (com a âncora
    de cada uma, `ancoras()`)."""
    return {"itens": [{"id": f"o{i}", "tipo": "original", "indice": i, "oculto": False,
                       **({"ancora": ancs[i]} if ancs else {})} for i in range(n)]}


def ancoras(secoes):
    """A âncora de cada faixa da página do código, o que não muda quando outra faixa entra ou sai: o `id` da
    `<section>` (`#reservar`), senão o `aria-labelledby` (`h-faq`), senão as classes (`.hero.hero-servico`). Repetida
    na página, ganha `~2`, `~3`…"""
    out, vistas = [], {}
    for s in secoes:
        m = re.match(r"\s*<section\b([^>]*)>", s)
        attrs = dict(re.findall(r'([a-z-]+)="([^"]*)"', m.group(1))) if m else {}
        a = (f"#{attrs['id']}" if attrs.get("id") else attrs.get("aria-labelledby")
             or "." + ".".join((attrs.get("class") or "section").split()))
        a = re.sub(r"[^A-Za-z0-9_.#-]", "", a)[:70] or "section"
        vistas[a] = vistas.get(a, 0) + 1
        out.append(a if vistas[a] == 1 else f"{a}~{vistas[a]}")
    return out


def _id_ausente(a):
    return "x" + hashlib.sha256(a.encode()).hexdigest()[:8]


def _alinhar_um(it, anc, vistas):
    """Um item `original` com a posição de hoje (pela âncora), ou None. O rascunho antigo (sem âncora) ganha a da
    posição dele; o que aponta para uma posição que não existe mais sai. A faixa que saiu da página fica, com `indice`
    -1 (sem desenho; as trocas dela são texto órfão)."""
    a = it.get("ancora")
    if not a:
        i = it.get("indice", -1)
        if not isinstance(i, int) or not 0 <= i < len(anc):
            return None
        a = anc[i]
    if a in vistas:
        return None
    vistas.add(a)
    i = anc.index(a) if a in anc else None
    return {**it, "id": f"o{i}" if i is not None else _id_ausente(a), "indice": -1 if i is None else i, "ancora": a}


def _alinhar_itens(conteudo, anc):
    vistas = set()
    feitos = (_alinhar_um(it, anc, vistas) for it in (conteudo or {}).get("itens") or []
              if isinstance(it, dict) and it.get("tipo") == "original")
    return [x for x in feitos if x]


def alinhar(conteudo, secoes):
    """O conteúdo com cada faixa original na posição de hoje da página do código (ver `_alinhar_um`)."""
    itens = conteudo.get("itens") or []
    if not secoes or not any(it.get("tipo") == "original" for it in itens):
        return conteudo
    anc, vistas, out = ancoras(secoes), set(), []
    for it in itens:
        x = _alinhar_um(it, anc, vistas) if it.get("tipo") == "original" else it
        if x:
            out.append(x)
    return {**conteudo, "itens": out}


def pagina_nova(titulo):
    """O começo de uma página nova: uma faixa escura com o h1 e um botão."""
    return {"itens": [{"id": novo_id(), "tipo": "secao", "fundo": "escura", "espaco": "g", "colunas": 1, "itens": [[
        {"id": novo_id(), "tipo": "titulo", "texto": titulo or "New page", "nivel": 1, "tamanho": "g", "cor": "padrao",
         "alinhar": "esq"},
        {"id": novo_id(), "tipo": "botao", "texto": "Book now", "link": "/services/arrive-and-drive/#reservar",
         "estilo": "cheio", "alinhar": "esq"}]]}]}


# ------------------------------------------------------------------ o desenho
def _classes(w):
    return " ".join(x for x in (f"ed-tam-{w.get('tamanho', 'm')}", f"ed-cor-{w.get('cor', 'padrao')}",
                                f"ed-al-{w.get('alinhar', 'esq')}") if x)


def _w(w, dados, primeira_foto, marcar=False):
    from command_center.vitrine import paginas_site as ps
    from command_center.vitrine.paginas import foto_url, usd
    t = w["tipo"]
    if t == "titulo":
        n = w["nivel"]
        return f'<h{n} class="ed-t {_classes(w)}">{e(w["texto"])}</h{n}>'
    if t == "texto":
        if not w["html"] and marcar:          # #315: o texto vazio continua clicável na prévia, para escrever nele
            return f'<div class="texto ed-tx {_classes(w)} ed-vazio"></div>'
        return f'<div class="texto ed-tx {_classes(w)}">{w["html"]}</div>' if w["html"] else ""
    if t == "imagem":
        if not w.get("src"):                  # #315: a imagem posta no rascunho que ainda espera a foto
            return '<figure class="ed-img ed-vazio"></figure>' if marcar else ""
        lazy = "" if primeira_foto[0] else ' loading="lazy"'
        primeira_foto[0] = False
        leg = f"<figcaption>{e(w['legenda'])}</figcaption>" if w.get("legenda") else ""
        return (f'<figure class="ed-img ed-img-{w["forma"]}"><img src="{e(foto_url(w["src"]))}" alt="{e(w["alt"])}" '
                f'width="{w["largura"]}" height="{w["altura"]}" decoding="async"{lazy}>{leg}</figure>')
    if t == "botao":
        cl = "btn" + (" btn-linha-escura" if w["estilo"] == "linha" else "")
        href = f' href="{e(w["link"])}"' if w.get("link") else ""
        return f'<p class="hero-acoes ed-al-{w["alinhar"]}"><a class="{cl}"{href}>{e(w["texto"])}</a></p>'
    if t == "lista":
        if not w["itens"] and marcar:
            return '<ul class="lista ed-lista ed-vazio"><li></li></ul>'
        return f'<ul class="lista ed-lista">{"".join(f"<li>{e(x)}</li>" for x in w["itens"])}</ul>' if w["itens"] else ""
    if t == "espaco":
        return f'<div class="ed-espaco ed-espaco-{w["tamanho"]}" aria-hidden="true"></div>'
    if t == "karts":
        ks = dados.get("karts") or []
        if not ks:
            return ""
        cards = "".join(
            f'<article class="plano"><h3>{e(k["titulo"])}</h3><p class="plano-sub">{e(k.get("linha") or "")}</p>'
            f'<p class="plano-preco"><strong>{usd(k["price"])}</strong><span>per session</span></p>'
            f'<a class="btn btn-sm" href="/services/arrive-and-drive/#reservar">Book {e(k["titulo"])}</a></article>' for k in ks)
        return f'<div class="planos">{cards}</div>'
    if t == "produtos":
        ps_ = [p for p in ps.produtos() if not w["categoria"] or ps._categoria(p)["slug"] == w["categoria"]]
        ps_ = [p for p in ps_ if p.get("in_stock")][:w["quantos"]]
        return f'<div class="produtos-grade">{"".join(ps._produto_card(p) for p in ps_)}</div>' if ps_ else ""
    if t == "cartoes":
        cs = (dados.get("cartoes") or {}).get(w["pagina"]) or []
        if w["pagina"] == "academy" and dados.get("planos"):
            # #312 (revisão): a mesma preferência da página: com plano ativo, a Academy mostra os planos, não os cartões
            html = ps._planos_do_painel(dados["planos"])
        else:
            html = ps._grupos_dos_cartoes(cs, dados.get("planos")) if cs else ""
        return f'<div class="ed-caixa">{html}</div>' if html and marcar else html     # #315: um nó só para clicar
    if t == "faq":
        return ps._faq([(x["pergunta"], (x["resposta"],)) for x in w["itens"]], ident=f"faq-{w['id']}") if w["itens"] else ""
    return ""


def _marca(html, w):
    """#315: o elemento na prévia de edição ganha `data-ed-w` (o id) e `data-ed-tipo` no primeiro nó; o que não tem
    nada para mostrar vira um marcador clicável (o painel escreve a dica dele)."""
    attrs = f'data-ed-w="{e(w["id"])}" data-ed-tipo="{w["tipo"]}"'
    if not html:
        return f'<div class="ed-vazio" {attrs}></div>'
    return re.sub(r"^<([a-z0-9]+)", lambda m: f"<{m.group(1)} {attrs}", html, count=1)


def partes(conteudo, dados=None, originais=(), marcar=False):
    """[(id do item, HTML)] na ordem do editor. `marcar` (#315): a prévia de edição, com os `data-ed-*`. A faixa
    original sai com as trocas de texto dela (etapa 4) e, sem troca, igual à do código."""
    dados = dados or {}
    out, primeira = [], [True]
    for it in alinhar(conteudo, originais)["itens"]:      # a faixa pela âncora; a que saiu da página não desenha
        if it["tipo"] == "original":
            if 0 <= it["indice"] < len(originais) and (marcar or not it.get("oculto")):
                html = originais[it["indice"]]
                out.append((it["id"], marcar_original(html, it["indice"], it.get("oculto"), it.get("textos")) if marcar
                            else aplicar_textos(html, it.get("textos"))[0]))
            continue
        if marcar:
            sid = e(it["id"])
            cols = "".join(f'<div class="ed-col" data-ed-col="{sid}:{ci}">'
                           f'{"".join(_marca(_w(w, dados, primeira, True), w) for w in c)}</div>'
                           for ci, c in enumerate(it["itens"]))
            out.append((it["id"], f'<section class="faixa {FUNDOS[it["fundo"]]} ed-secao ed-esp-{it["espaco"]}" id="s-{sid}" '
                                  f'data-ed-s="{sid}"><div class="largura"><div class="ed-grade ed-c{it["colunas"]}">{cols}'
                                  f'</div></div></section>'))
            continue
        cols = "".join(f'<div class="ed-col">{"".join(_w(w, dados, primeira) for w in c)}</div>' for c in it["itens"])
        out.append((it["id"], f'<section class="faixa {FUNDOS[it["fundo"]]} ed-secao ed-esp-{it["espaco"]}" id="s-{e(it["id"])}">'
                              f'<div class="largura"><div class="ed-grade ed-c{it["colunas"]}">{cols}</div></div></section>'))
    return out


def corpo(conteudo, dados=None, originais=(), marcar=False):
    """O HTML do `<main>`: as seções novas e as originais (as que não estão escondidas), na ordem do editor."""
    return "\n".join(h for _, h in partes(conteudo, dados, originais, marcar))


def ld_extra(conteudo):
    """O JSON-LD que os elementos pedem: as perguntas frequentes viram FAQPage."""
    from command_center.vitrine import paginas_site as ps
    faq = [(x["pergunta"], (x["resposta"],)) for it in conteudo["itens"] if it["tipo"] == "secao"
           for c in it["itens"] for w in c if w["tipo"] == "faq" for x in w["itens"]]
    return [ps._faq_ld(faq)] if faq else []


# ------------------------------------------------------------------ as regras do site
def _textos_escritos(conteudo):
    """Todo texto que a equipe escreveu na página: as trocas das faixas originais e o texto dos elementos (título,
    texto, botão, lista, perguntas). Não entra o que vem do banco (karts, produtos, cartões)."""
    for it in conteudo["itens"]:
        if it["tipo"] == "original":
            yield from (it.get("textos") or {}).values()
            continue
        for c in it["itens"]:
            for w in c:
                if w["tipo"] in ("titulo", "botao"):
                    yield w.get("texto") or ""
                elif w["tipo"] == "texto":
                    yield unescape(re.sub(r"<[^>]+>", " ", w.get("html") or ""))
                elif w["tipo"] == "lista":
                    yield from w.get("itens") or []
                elif w["tipo"] == "faq":
                    for x in w.get("itens") or []:
                        yield x.get("pergunta") or ""
                        yield x.get("resposta") or ""



def problemas(conteudo, html_corpo, titulo, descricao, orfas=None):
    """O que impede publicar: as regras do site (CLAUDE.md) conferidas no HTML que o editor gerou (com as trocas de
    texto das faixas originais: o h1 trocado continua sendo o h1). `orfas` (etapa 4): as trocas que não acham mais o
    texto na página do código (`orfaos()`)."""
    out = []
    n_orfas = sum(len(x) for x in (orfas or {}).values())
    com_preco = sum(1 for t in _textos_escritos(conteudo) if PRECO.search(t))
    if com_preco:
        out.append(f"{com_preco} texto(s) com preço escrito: {MSG_PRECO} (o site mostra o preço do painel)")
    if n_orfas:
        out.append(f"{n_orfas} texto(s) órfão(s) nas faixas originais: a página do código mudou e o texto escrito ali "
                   "não entra; escreva de novo ou descarte (aba Página)")
    if not 10 <= len(titulo or "") <= 70:
        out.append("título da aba: de 10 a 70 caracteres (o Google mostra até uns 60)")
    if not 50 <= len(descricao or "") <= 170:
        out.append("descrição: de 50 a 170 caracteres (é o texto do Google embaixo do título)")
    niveis = [int(n) for n in re.findall(r"<h([1-6])\b", html_corpo)]
    h1 = niveis.count(1)
    if h1 != 1:
        out.append(f"a página precisa de exatamente um título nível 1 (h1); tem {h1}")
    anterior = 0
    for n in niveis:
        if n > anterior + 1:
            out.append(f"um título pula de nível (de h{anterior} para h{n}): use o nível {anterior + 1} antes")
            break
        anterior = n
    ws = [w for it in conteudo["itens"] if it["tipo"] == "secao" for c in it["itens"] for w in c]
    # #315: o rascunho aceita o meio do caminho; publicar, não
    sem_texto = sum(1 for w in ws if w["tipo"] == "titulo" and not w.get("texto"))
    if sem_texto:
        out.append(f"{sem_texto} título(s) vazio(s): escreva o texto ou apague")
    botoes = sum(1 for w in ws if w["tipo"] == "botao" and not (w.get("texto") and w.get("link")))
    if botoes:
        out.append(f"{botoes} botão(ões) sem texto ou sem link")
    faq = sum(1 for w in ws if w["tipo"] == "faq" for x in w["itens"] if not (x.get("pergunta") and x.get("resposta")))
    if faq:
        out.append(f"{faq} pergunta(s) frequente(s) sem a pergunta ou sem a resposta")
    sem_foto = sum(1 for w in ws if w["tipo"] == "imagem" and not w.get("src"))
    if sem_foto:
        out.append(f"{sem_foto} imagem(ns) esperando a foto")
    sem = sum(1 for w in ws if w["tipo"] == "imagem" and w.get("src") and not w.get("alt"))
    if sem:
        out.append(f"{sem} foto(s) sem descrição: quem não vê a foto (e o Google) lê a descrição")
    if not re.sub(r"<[^>]+>|\s", "", html_corpo):
        out.append("a página está vazia")
    return out
