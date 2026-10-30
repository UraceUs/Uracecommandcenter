"""O simulador de carreira do /career/ (#528): o HTML das três partes, com os dados de `conteudo_carreira`.

Tudo sai do servidor e a página funciona sem JavaScript: as três rotas à vista (o resumo e os degraus de cada uma), as
quatro respostas do "Find your step" com a condição de cada uma e a lista de preços do "My career plan". O
`carreira.js` liga o resto: a escolha do destino (radios, só a rota escolhida fica à vista e a frase dela é anunciada),
as três perguntas (a resposta é anunciada) e o plano (pôr, tirar, quantidade, os totais, copiar e limpar). Nenhum preço
mora no script: ele lê o `data-preco` de cada linha do plano.
"""
from html import escape

from command_center.vitrine import conteudo_carreira as K
from command_center.vitrine.paginas import usd


def e(v):
    return escape(str(v), quote=True)


def _custo(d):
    """O preço do degrau como lá ("$1,200 / month"), "Quote" para o Racing Team, ou None (degrau de fora)."""
    if d["custo"] == "quote":
        return "Quote"
    if d["custo"]:
        valor, unidade = d["custo"]
        return f"{usd(valor)} / {unidade}"
    return None


def _ancora(d, rota=None):
    return f"step-{d['chave']}" if rota is None else f"step-{rota}-{d['chave']}"


def _degrau(d, rota=None):
    """Um degrau da escada: o passo, o nome, quem faz, o preço (ou o nível), o texto e os números típicos."""
    nosso = d["quem"] == K.QUEM_NOSSO
    classe = "car-degrau" + (" car-nosso" if nosso else "") + (" car-destino" if d["quem"] == K.QUEM_DESTINO else "")
    linhas = []
    if d["quando"]:
        linhas.append(f'<div><dt>Opens</dt><dd>{e(d["quando"].removeprefix("Opens "))}</dd></div>')
    custo = _custo(d)
    if custo:
        linhas.append(f'<div><dt>Cost</dt><dd data-custo>{e(custo)}</dd></div>')
    if d["nivel"]:
        linhas.append(f'<div><dt>Level</dt><dd>{"<br>".join(e(x) for x in d["nivel"])}</dd></div>')
    numeros = "".join(f"<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>" for a, b in d["numeros"])
    link = (f'<p class="car-mais"><a class="btn btn-sm btn-linha-escura" href="{e(d["link"])}">More about {e(d["curto"])}</a></p>'
            if d["link"] else "")
    return f"""<li class="{classe}" id="{_ancora(d, rota)}">
  <p class="car-passo">{e(d["passo"]) or "&nbsp;"}</p>
  <div class="car-degrau-corpo"><h4>{e(d["nome"])}</h4><p class="car-quem">{e(d["quem"])}</p>
  <dl class="car-linhas">{"".join(linhas)}</dl>
  <p>{e(d["texto"])}</p>
  <p class="car-numeros-titulo">{e(K.SIMULADOR["numeros"])}</p><dl class="car-numeros">{numeros}</dl>{link}</div>
</li>"""


def _anuncio(r):
    passos = K.caminho(r["chave"])
    return f"{r['nome']}, {r['tag']}: {len(passos)} steps, from {passos[0]['nome']} to {passos[-1]['nome']}."


def _resumo(r):
    """O caminho inteiro de uma rota numa fileira (o "strip" do modo passo a passo de lá), com o preço ou o nível."""
    itens = []
    for i, d in enumerate(K.caminho(r["chave"]), 1):
        rota = None if d in K.BASE or d is K.BIFURCACAO else r["chave"]
        baixo = _custo(d) or d["nivel"][0]
        itens.append(f'<li class="{"car-nosso" if d["quem"] == K.QUEM_NOSSO else ""}"><a href="#{_ancora(d, rota)}">'
                     f'<i>{i}</i><b>{e(d["curto"])}</b><small>{e(baixo)}</small></a></li>')
    return f"""<div class="car-rota" data-rota="{r["chave"]}" data-anuncio="{e(_anuncio(r))}">
  <h3>{e(r["nome"])} <span>{e(r["tag"])}</span></h3><p>{e(r["nota"])}</p>
  <ol class="car-trilha">{"".join(itens)}</ol>
</div>"""


def simulador(aviso):
    """"Select your career": os três destinos, o caminho de cada um e a escada (os degraus comuns e os de cada rota)."""
    s = K.SIMULADOR
    alvos = "".join(
        f'<label class="car-alvo"><input type="radio" name="destino" value="{r["chave"]}"'
        f'{" checked" if r["chave"] == K.PADRAO else ""}><span class="car-alvo-nome">{e(r["nome"])}</span>'
        f'<span class="car-alvo-tag">{e(r["tag"])}</span><span class="car-alvo-linha">{e(r["linha"])}</span></label>'
        for r in K.ROTAS)
    base = "".join(_degrau(d) for d in (*K.BASE, K.BIFURCACAO))
    rotas = "".join(
        f'<div class="car-ramo" data-rota-degraus="{r["chave"]}"><p class="car-divide">↑ the ladder splits here — this leg '
        f'heads for {e(r["degraus"][-1]["nome"])}</p><ol class="car-escada">{"".join(_degrau(d, r["chave"]) for d in r["degraus"])}</ol></div>'
        for r in K.ROTAS)
    avisos = "".join(f'<p class="muted small">{e(t)}</p>' for t in aviso)
    fim, href = s["fim"]
    return f"""<section class="faixa clara car-sim" id="simulator" aria-labelledby="h-sim"><div class="largura">
  <div class="car-cabeca"><p class="eyebrow">{e(s["eyebrow"])}</p><h2 id="h-sim">{e(s["titulo"])}</h2><p>{e(s["texto"])}</p></div>
  <fieldset class="car-alvos" data-car-alvos hidden><legend class="escondido">{e(s["titulo"])}</legend>{alvos}</fieldset>
  <p class="car-anuncio" aria-live="polite" data-car-anuncio></p>
  {"".join(_resumo(r) for r in K.ROTAS)}
  <h3 id="h-escada">The ladder</h3>
  <ol class="car-escada" aria-labelledby="h-escada">{base}</ol>
  {rotas}
  <p class="hero-acoes"><a class="btn" href="{e(href)}" rel="noopener">{e(fim)}</a></p>
  {avisos}
</div></section>"""


def _condicoes(chave):
    """Quando o "Find your step" dá esta resposta, tirado da própria regra (`decidir`): a experiência e as idades."""
    perguntas = {q: (t.split(" · ", 1)[1], dict(op)) for q, t, op in K.LOCALIZADOR["perguntas"]}
    quem = K.LOCALIZADOR["perguntas"][0][2][0][0]          # quem dirige não muda a resposta (lá também não)
    partes = []
    for exp, exp_rot in perguntas["exp"][1].items():
        idades = [rot for idade, rot in perguntas["age"][1].items() if K.decidir(quem, idade, exp) == chave]
        if not idades:
            continue
        txt = f'{e(perguntas["exp"][0])} <b>{e(exp_rot)}</b>'
        if len(idades) < len(perguntas["age"][1]):
            txt += f' · {e(perguntas["age"][0])} <b>{e(", ".join(idades))}</b>'
        partes.append(txt)
    return "<br>".join(partes)


def localizador():
    """"Find your step": as três perguntas (radios, com o `carreira.js`) e a resposta. Sem JavaScript, as quatro
    respostas com a condição de cada uma."""
    L = K.LOCALIZADOR
    nomes = {d["chave"]: d["nome"] for d in K.BASE}
    perguntas = "".join(
        f'<fieldset class="car-pergunta"><legend>{e(t)}</legend><div class="car-opcoes">'
        + "".join(f'<label class="car-opcao"><input type="radio" name="{q}" value="{v}"><span>{e(r)}</span></label>' for v, r in op)
        + "</div></fieldset>" for q, t, op in L["perguntas"])
    respostas = "".join(
        f'<div class="car-res" data-resultado="{k}"><p class="car-se" data-se>{_condicoes(k)}</p>'
        f'<p class="car-kicker" data-so-js hidden>{e(L["resultado"])}</p><h3>{e(nomes[degrau])}</h3><p>{e(porque)}</p>'
        f'<p><a class="btn btn-sm" href="#step-{degrau}">{e(L["abrir"])}</a></p></div>'
        for k, (degrau, porque) in K.RESULTADOS.items())
    return f"""<section class="faixa escura car-achar" id="find-your-step" aria-labelledby="h-achar"><div class="largura estreita">
  <h2 id="h-achar">{e(L["titulo"])}</h2><p>{e(L["texto"])}</p>
  <form class="car-perguntas" data-car-localizador hidden aria-label="{e(L["titulo"])}">{perguntas}</form>
  <div class="car-respostas" aria-live="polite" data-car-respostas>{respostas}</div>
</div></section>"""


def plano():
    """"My career plan": os itens de cada degrau com o preço. Com o `carreira.js`, pôr/tirar, quantidade e os totais."""
    P = K.PLANO
    grupos = []
    for d in K.BASE:
        itens = [i for i in K.ITENS_PLANO if i[5] == d["chave"]]
        linhas = "".join(
            f'<li class="car-item" data-item="{k}" data-preco="{"" if p is None else f"{p:.2f}"}" data-unidade="{u}" '
            f'data-rotulo="{e(rot)}"><span class="car-item-txt"><b>{e(rot)}</b><small>{e(n)}</small></span>'
            f'<span class="car-item-preco">{"Quote" if p is None else e(usd(p))}</span>'
            f'<span class="car-item-acoes" data-so-js hidden><button type="button" class="car-por" data-por aria-pressed="false">'
            f'<span data-por-txt>Add</span><span class="escondido"> {e(rot)}</span></button>'
            + ("" if p is None else
               f'<span class="car-qtd" data-qtd hidden><button type="button" data-q="-" aria-label="Remove one: {e(rot)}">−</button>'
               f'<output data-n>1</output><button type="button" data-q="+" aria-label="Add one: {e(rot)}">+</button></span>')
            + "</span></li>" for k, rot, p, u, n, _d in itens)
        grupos.append(f'<h3>{e(d["nome"])}</h3><ul class="car-itens">{linhas}</ul>')
    falar, href = P["falar"]
    return f"""<section class="faixa clara car-plano" id="my-plan" aria-labelledby="h-plano"><div class="largura estreita">
  <h2 id="h-plano">{e(P["titulo"])}</h2><p class="car-conta" data-plano-conta data-so-js hidden>Empty</p><p>{e(P["texto"])}</p>
  {"".join(grupos)}
  <div class="car-totais" data-car-totais data-so-js hidden aria-live="polite">
    <div><span>One-off</span><b data-tot-um>$0</b></div>
    <div><span>Every month</span><b><span data-tot-mes>$0</span><small> /mo</small></b></div>
    <div data-tot-cotar-linha hidden><span>We quote</span><b data-tot-cotar></b></div>
  </div>
  <p class="small muted">{e(P["nota"])}</p>
  <p class="hero-acoes"><a class="btn" href="{e(href)}" rel="noopener">{e(falar)}</a>
    <button type="button" class="btn btn-linha-escura" data-plano-copiar data-so-js hidden>Copy my plan</button>
    <button type="button" class="btn btn-linha-escura" data-plano-limpar data-so-js hidden>Clear</button></p>
</div></section>"""
