"""Race the Winter 2027 (#505): a página /winter/ do urace.us, refeita por blocos.

Dono, 29/10: *"sim, pode trazer o texto e recriar a winter"*. O texto é o da página de hoje (urace.us/winter/, outubro de
2026), capítulo a capítulo, sem reescrever. O que muda, de propósito:

- o circuito em 3D (three.js, traçado por satélite) sai; as cinco fases que ele contava viram passos;
- os três vídeos curtos ("On camera · Hear it from the team") saem do próprio site (#526, static/video, comprimidos), numa
  faixa logo depois da prova, em grade (no celular, de lado dentro da faixa) em vez do carrossel com setas de lá. A vitória
  continua no link do Instagram;
- "Build your winter" é o formulário por blocos: cai em Vendas (Racing Team) com o plano na nota (campos `x_*`);
- a estimativa é a diária do kart do PAINEL (os serviços do Arrive and Drive, `Site › Serviços e preços`) × os dias de
  teste. O que não tem fonte no painel (o apoio do fim de semana de corrida, a faixa de ±) não vira número:
  "quoted per event";
- o contato direto da equipe sai pelo formulário e pela agenda do Lucas (o telefone da página de hoje não entra no
  repositório público, #244).

O que o urace.us de hoje esconde (`display:none`) fica de fora, como lá: "We bring everything / The work nobody sees / The
long game", "The season on one page" (07), o "Next step" e o "What that is worth"; a numeração dos capítulos segue a de lá.
"""
from datetime import date, timedelta

from command_center.vitrine import blocos
from command_center.vitrine.blocos import e, img, inline
from command_center.vitrine.conteudo import CURTAS
from command_center.vitrine.paginas import _karts_do_painel, usd

CAMINHO = "/winter/"
ALVO = "2027-01-15T08:00:00-05:00"                                  # lights out, SKUSA Winter R1: 15 Jan 2027, 8:00 am ET
AGENDA = "https://calendar.app.google/whLkkpp82fUzsfvT8"             # "Pick a slot on Lucas’s calendar" (a página de hoje)
EMAIL = "lucas@urace.us"
MESES = ("Jan", "Feb", "Mar")

# ------------------------------------------------------------------ o texto da página de hoje
ORIGENS = (   # "Racing from" do topo: chave, rótulo e a frase de cada origem
    ("europe", "Europe", "Cold tracks, season over in Europe. **We are open all year.** From January the winter grids race "
                         "in Florida while Europe waits for spring."),
    ("north", "Northern US & Canada", "Snow on your track means no racing. **No snow in Orlando.** We run all year, and "
                                      "January to March is race season here."),
    ("other", "Elsewhere", "**We are open all year.** From January to March the winter grids meet in Florida, at our home "
                           "track."),
)

FASES = (     # "The winter, lap by lap · Orlando Kart Center" (o que o circuito em 3D mostrava, fase a fase)
    ("Adapt to the circuit", "Arrive · first week of your stay",
     "Seat fit, chassis set-up and a baseline lap on a track the driver may never have driven. We start from the set-up "
     "we already run here."),
    ("Race-pace testing", "Testing · 19–21 Jan · 25–28 Jan · 1–11 Feb",
     "Starts, consistent runs and race craft, on the same asphalt as the championship: the three things that decide a race."),
    ("SKUSA R1–2", "Race weekend · 15–17 Jan 2027",
     "The first two SKUSA Winter Series rounds, at our home track. The first international result of the year."),
    ("SKUSA R3–4", "Race weekend · 12–14 Feb 2027",
     "Four weeks of testing later, the second half of the championship on a circuit the driver now knows better than most "
     "of the grid."),
    ("Extend or go home", "Optional races · 26–28 Feb · 12–14 Mar",
     "Either add the Florida Winter Tour rounds in March, or close the campaign here with a winter behind you."),
)

RODADAS = (   # os três cartões do calendário: quando, rodada, nome, datas, onde, se é a decisiva
    ("2a · First", "Rounds 1–2 · Home track", "SKUSA Winter", "15–17 Jan", "Orlando Kart Center · IAME", False),
    ("The championship decider", "Rounds 3–4 · Home track", "SKUSA Winter", "12–14 Feb",
     "Orlando Kart Center · same asphalt, four weeks of testing later", True),
    ("2b · Optional", "Round 1 · Florida Winter Tour", "Sebring", "22–24 Jan", "Sebring International Raceway · ROK", False),
)

PROVAS = (    # as sete provas, como no calendário de hoje (o `inicio`/`fim` vão para a conta do plano)
    {"dia": "15", "ate": "to 17 Jan", "datas": "15–17 Jan", "titulo": "SKUSA Winter Series · Rounds 1 & 2",
     "texto": "**Orlando Kart Center.** Our home circuit. IAME engine package.", "tipo": "home", "tag": "Home track",
     "motor": "iame", "inicio": "2027-01-15", "fim": "2027-01-17"},
    {"dia": "22", "ate": "to 24 Jan", "datas": "22–24 Jan", "titulo": "Florida Winter Tour · Round 1",
     "texto": "Sebring International Raceway, on a temporary circuit. ROK engine package.", "tipo": "opt", "tag": "Optional",
     "motor": "rok", "inicio": "2027-01-22", "fim": "2027-01-24"},
    {"dia": "23", "ate": "to 24 Jan", "datas": "23–24 Jan", "titulo": "Rotax Winter Trophy · Round 1",
     "texto": "**Orlando Kart Center.** Rotax engine package. Dates reported but not yet confirmed by the organiser.",
     "tipo": "tbc", "tag": "To confirm", "motor": "rotax", "inicio": "2027-01-23", "fim": "2027-01-24"},
    {"dia": "29", "ate": "to 31 Jan", "datas": "29–31 Jan", "titulo": "FLKC Florida Open · the “0 Plate”",
     "texto": "A one-off weekend outside the championships, with Sunday finals and a 0 Plate for each class. Venue still to "
              "be announced.", "tipo": "opt", "tag": "Optional", "motor": "", "inicio": "2027-01-29", "fim": "2027-01-31"},
    {"dia": "12", "ate": "to 14 Feb", "datas": "12–14 Feb", "titulo": "SKUSA Winter Series · Rounds 3 & 4",
     "texto": "**Orlando Kart Center.** Same track, four weeks later: the second half of the championship.", "tipo": "home",
     "tag": "Home track", "motor": "iame", "inicio": "2027-02-12", "fim": "2027-02-14"},
    {"dia": "20", "ate": "to 21 Feb", "datas": "20–21 Feb", "titulo": "Rotax Winter Trophy · Round 2",
     "texto": "Orlando Kart Center. Same caveat as Round 1: reported, not yet confirmed.", "tipo": "tbc", "tag": "To confirm",
     "motor": "rotax", "inicio": "2027-02-20", "fim": "2027-02-21"},
    {"dia": "26", "ate": "Feb–Mar", "datas": "26–28 Feb · 12–14 Mar", "titulo": "Florida Winter Tour · Rounds 2 & 3",
     "texto": "26–28 February and 12–14 March. Both venues still to be announced by the organiser.", "tipo": "opt",
     "tag": "Optional", "motor": "rok", "inicio": "2027-02-26", "fim": "2027-03-14"},
)
JANELAS = (("2027-01-19", "2027-01-21"), ("2027-01-25", "2027-01-28"), ("2027-02-01", "2027-02-11"))   # testing windows

PECAS = (     # "Your kart, ready on the stand": as oito peças do desenho de hoje, com o texto de cada uma
    {"t": "Steering wheel", "s": "The first thing the driver touches",
     "x": "Position and reach set for the driver before the first lap. The display on the wheel is where lap times and "
          "data start, and we read them with the driver after every session.",
     "us": "Wheel position, reach and display set-up", "you": "Honest feedback after every run"},
    {"t": "Seat", "s": "Part of the set-up, not just a place to sit",
     "x": "On a kart the seat moves weight around the chassis, so where it sits changes how the kart handles. Fitted to the "
          "driver on arrival, and checked again as they grow.",
     "us": "Seat fit and position", "you": "The driver, in full gear, for the fitting"},
    {"t": "Pedals", "s": "Small adjustment, big braking points",
     "x": "Brake and throttle reach set for the driver’s legs, so every input uses full travel. It sounds small. It decides "
          "where the braking points are.",
     "us": "Pedal position and reach", "you": "Driving boots"},
    {"t": "Engine", "s": "Rotax, IAME or ROK",
     "x": "Prepared and run by our mechanic all weekend. Which package depends on the championships you choose, and that "
          "is chapter 04.",
     "us": "Engine preparation and running", "you": "Fuel and consumables"},
    {"t": "Chassis", "s": "A known baseline on a known track",
     "x": "A prepared chassis with a set-up that starts from a known baseline, because we run this circuit all year, and "
          "carries over from test to race.",
     "us": "Chassis, set-up and spares package", "you": "Parts beyond the spares package"},
    {"t": "Tyres", "s": "Where weekends are won and lost",
     "x": "Tyre management across a weekend: pressures, which set for which session, and when a new set is worth it.",
     "us": "Pressures and the tyre plan", "you": "Tyres, bought for the event"},
    {"t": "Data & onboard", "s": "Every session, reviewed",
     "x": "Data and onboard from every session, reviewed with the coach between runs and between rounds. Send us a lap "
          "before you land and the review starts early.",
     "us": "Data and onboard review, coach on the driver", "you": "A recent onboard, if you have one"},
    {"t": "Helmet", "s": "Mental performance · the part nobody trains",
     "x": "Lap time lives in the head too. Our mental performance coach works with the driver trackside: focus over a long "
          "run, reset after a mistake, nerves on the grid, a debrief that builds instead of breaks. Skill training, not a "
          "pep talk.",
     "us": "Mental performance coach, group sessions and trackside days", "you": "Show up open to the work"},
)

MOTORES = (   # "Engine package · our call": a ordem de hoje, com o IAME de padrão
    {"nome": "Rotax", "sub": "Only if the plan needs it", "tag": "Only if needed", "tipo": "tbc", "padrao": False,
     "texto": "Rotax Winter Trophy, at our track. Familiar to many visiting drivers. We add it only if the dates firm up "
              "and it fits the plan."},
    {"nome": "IAME", "sub": "Our default · SKUSA Winter", "tag": "Our default", "tipo": "home", "padrao": True,
     "texto": "Four SKUSA Winter rounds at our home track, the strongest grid of the winter. This is where we start."},
    {"nome": "ROK", "sub": "Only if the plan needs it", "tag": "Only if needed", "tipo": "opt", "padrao": False,
     "texto": "Florida Winter Tour. Round 1 at Sebring, the rest still to be announced. We add it only if the driver needs "
              "more race miles."},
)

# O localizador de categoria: as classes como rodaram na SKUSA Winter Series 2026, exatamente como no JS da página de hoje
# (idade de corrida mínima e máxima — None é "e acima" —, peso mínimo de kart + piloto em libras e o motor).
CATEGORIAS = (
    {"nome": "Micro Swift", "idade": (7, 10), "peso_lb": 220, "motor": "IAME Mini Swift 60 (16 mm header)"},
    {"nome": "Mini Swift", "idade": (9, 13), "peso_lb": 245, "motor": "IAME Mini Swift 60"},
    {"nome": "KA100 Junior", "idade": (12, 15), "peso_lb": 320, "motor": "IAME KA100 (22 mm header)"},
    {"nome": "X30 Junior", "idade": (12, 15), "peso_lb": 320, "motor": "IAME X30 (22.7 mm header)"},
    {"nome": "KA100 Senior", "idade": (15, None), "peso_lb": 355, "motor": "IAME KA100"},
    {"nome": "Pro X30", "idade": (15, None), "peso_lb": 360, "motor": "IAME X30"},
    {"nome": "Pro Shifter", "idade": (15, None), "peso_lb": 390, "motor": "KZ 125cc shifter"},
    {"nome": "KA100 Master", "idade": (30, None), "peso_lb": 390, "motor": "IAME KA100 · 21+ with a 200 lb driver at 400 lb"},
)
CATEGORIAS_FONTE = "Classes as run in the 2026 SKUSA Winter Series. 2027 classes are confirmed by SKUSA before entry."

# A estimativa: o kart do painel (a chave `site_kart` do serviço do Arrive and Drive) → como a página de hoje o chama.
# O PREÇO não está aqui: é o do serviço ativo no painel, lido a cada página (`_karts_com_preco`).
KARTS_DA_ESTIMATIVA = (
    {"chave": "Baby Kart", "kt": "baby", "rotulo": "Kid · Baby kart", "nome": "Baby kart (kid, 4–7)", "idade": "Age 4–7",
     "nota": "Not a SKUSA Winter class: race weekends are priced for local events, roughly."},
    {"chave": "4-stroke", "kt": "4s", "rotulo": "4-stroke", "nome": "4-stroke", "idade": "Age 7+",
     "nota": "Not a SKUSA Winter class: race weekends are priced for local events, roughly."},
    {"chave": "2-stroke", "kt": "2s", "rotulo": "2-stroke · SKUSA", "nome": "2-stroke", "idade": "Age 7+",
     "nota": "SKUSA Winter classes all run 2-stroke engines."},
    {"chave": "Adult Shifter", "kt": "shift", "rotulo": "Adult · Shifter", "nome": "Adult shifter", "idade": "Age 14+",
     "nota": "Adult shifter: experience required. Pro Shifter is 15+ in SKUSA."},
)

BASES = ("Lake Nona Wave Hotel", "Partner hotel", "Vacation home", "Own plans")
EXTRAS = (    # "Add to the package": campo, nome, texto, marcado de início (como hoje) e o resto da linha da estimativa
    ("x_concierge", "Concierge", "Airport, car, hotel, dinners. One contact off track.", True,
     "airport, car, hotel, dinners"),
    ("x_mental_performance", "Mental performance", "Coach trackside and between rounds.", False,
     "trackside and between rounds"),
    ("x_athletic_camp", "Athletic camp", "Lake Nona Performance Club: track, turf, gym, pool.", False,
     "Lake Nona Performance Club"),
)
CHEGADAS = tuple(date(2027, 1, 4) + timedelta(weeks=n) for n in range(10))    # "Week of 4 Jan" … (segundas)
VOLTAS = tuple(date(2027, 1, 17) + timedelta(weeks=n) for n in range(10))     # "Sunday 17 Jan" …
CHEGADA, VOLTA = date(2027, 1, 11), date(2027, 2, 14)                          # o que a página de hoje traz marcado


def _dia(d):
    return f"{d.day} {MESES[d.month - 1]}"


# ------------------------------------------------------------------ peças
def _funcao(desenho, **b):
    """Um bloco `funcao` com o texto à vista: a conferência (`blocos.problemas`) lê tudo do bloco, menos o `render`."""
    bloco = {"tipo": "funcao", **b}
    bloco["render"] = lambda host, ctx: desenho(bloco, ctx["indice"], host, ctx)
    return bloco


def _secao(b, i, miolo, classe, largura="largura"):
    """A faixa de um bloco desta página: a mesma de `blocos`, com uma classe a mais (o espaço e a grade de cada uma)."""
    fundo = b.get("fundo") or "clara"
    rotulo = f' aria-labelledby="h-b{i}"' if b.get("titulo") else f' aria-label="{e(b["rotulo_secao"])}"'
    ident = f' id="{b["ancora"]}"' if b.get("ancora") else ""
    return f'<section class="faixa {fundo} {classe}"{rotulo}{ident}><div class="{largura}">{miolo}</div></section>'


def _chips(rotulo, attr, opcoes, marcada, gancho, prefixo=""):
    """Botões de escolha (aria-pressed), escondidos até o `winter.js` ligar (`gancho`): sem JavaScript, tudo fica à vista."""
    bs = "".join(f'<button type="button" class="winter-chip" {attr}="{k}" aria-pressed="{"true" if k == marcada else "false"}">'
                 f"{e(r)}</button>" for k, r in opcoes)
    return f'<div class="winter-chips" role="group" aria-label="{e(rotulo)}" {gancho} hidden>{prefixo}{bs}</div>'


# ------------------------------------------------------------------ os blocos que só esta página tem
def _origem(b, i, host, ctx):
    """"Racing from": com JavaScript, três botões e a frase da origem escolhida (e o formulário acompanha); sem, as três."""
    chips = _chips("Where are you racing from?", "data-origem", [(k, r) for k, r, _t in b["itens"]], "europe",
                   "data-origem-botoes", '<span class="winter-chips-rotulo">Racing from</span>')
    linhas = "".join(f'<div data-origem-linha="{k}"><dt>Racing from {e(r)}</dt><dd>{inline(t)}</dd></div>'
                     for k, r, t in b["itens"])
    miolo = f'{chips}<dl class="winter-origem-linhas" aria-live="polite">{linhas}</dl><p class="small muted" data-preparado hidden></p>'
    return _secao(b, i, miolo, "winter-origem")


def _citacao(b, i, host, ctx):
    """A palavra do Italo, com a foto (blockquote: o editor do painel não reescreve a fala de ninguém)."""
    grande, sub = b["citacao"]
    miolo = f"""<figure class="winter-citacao">{img(b["foto"], b["alt"])}
  <blockquote><p class="winter-citacao-grande">{inline(grande[0])} <span>{e(grande[1])}</span></p><p>{e(sub)}</p></blockquote>
  <figcaption><strong>{e(b["quem"])}</strong> <span>{e(b["papel"])}</span></figcaption>
</figure>"""
    return _secao(b, i, miolo, "winter-italo")


def _calendario(b, i, host, ctx):
    """As rodadas de casa, as opcionais e as a confirmar: a lista é o essencial; o filtro, um atalho (com JavaScript)."""
    rodadas = "".join(
        f'<article class="cartao winter-rodada"><p class="winter-quando{" winter-decisiva" if decisiva else ""}">{e(quando)}</p>'
        f'<h3>{e(nome)}</h3><p>{e(rodada)}</p><p class="winter-data">{e(datas)}</p><p>{e(onde)}</p></article>'
        for quando, rodada, nome, datas, onde, decisiva in b["rodadas"])
    filtro = _chips("Filter races", "data-f", (("all", f"All {len(b['provas'])}"), ("home", "Home track"), ("opt", "Optional"),
                                              ("tbc", "To confirm")), "all", "data-filtro")
    provas = "".join(
        f'<li data-tipo="{p["tipo"]}"><p class="winter-prova-dia"><strong>{e(p["dia"])}</strong> <span>{e(p["ate"])}</span></p>'
        f'<div class="winter-prova-txt"><p class="winter-prova-nome">{e(p["titulo"])}</p><p>{inline(p["texto"])}</p></div>'
        f'<p class="winter-tag winter-tag-{p["tipo"]}">{e(p["tag"])}</p></li>' for p in b["provas"])
    nota_t, nota = b["nota"]
    miolo = (blocos._cabeca(b, i) + f'<div class="cartoes winter-rodadas">{rodadas}</div>{filtro}'
             f'<ul class="winter-provas" data-provas>{provas}</ul>'
             f'<div class="winter-nota"><p><strong>{e(nota_t)}</strong></p><p>{e(nota)}</p></div>'
             f'<p class="small muted">{e(b["datas"])}</p>')
    return _secao(b, i, miolo, "winter-calendario")


def _maquina(b, i, host, ctx):
    """As oito peças do kart (sem o desenho interativo de hoje): uma lista que abre peça a peça, a 1ª aberta."""
    pecas = "".join(
        f'<details class="winter-peca" id="kart-part-{n}"{" open" if n == 1 else ""}><summary><span class="winter-peca-n">{n}</span>'
        f'<span class="winter-peca-t"><strong>{e(p["t"])}</strong><small>{e(p["s"])}</small></span></summary>'
        f'<div class="winter-peca-corpo"><p>{e(p["x"])}</p><dl class="winter-quem"><div><dt>URACE</dt><dd>{e(p["us"])}</dd></div>'
        f'<div><dt>Your side</dt><dd>{e(p["you"])}</dd></div></dl></div></details>' for n, p in enumerate(b["pecas"], 1))
    foto, alt, legenda = b["kart"]
    equipe_t, equipe = b["equipe"]
    duo = "".join(f'<figure class="winter-foto">{img(f, a)}<figcaption>{e(c)}</figcaption></figure>' for f, a, c in equipe)
    miolo = (blocos._cabeca(b, i) + f'<div class="winter-maquina-grade"><div class="winter-pecas">{pecas}</div>'
             f'<figure class="winter-foto">{img(foto, alt)}<figcaption>{e(legenda)}</figcaption></figure></div>'
             f'<p class="winter-kicker">{e(equipe_t)}</p><div class="winter-duo">{duo}</div>')
    return _secao(b, i, miolo, "winter-maquina")


def _idade(c):
    a, z = c["idade"]
    return f"Age {a}–{z}" if z else f"Age {a}+"


def _escolha(b, i, host, ctx):
    """O motor (a escolha é nossa) e o localizador de categoria: data de nascimento → idade de corrida em 1º de janeiro de
    2027 → as classes da SKUSA abertas. Sem JavaScript fica a tabela das classes."""
    motores = "".join(
        f'<article class="winter-motor{" padrao" if m["padrao"] else ""}"><h3>{e(m["nome"])}</h3>'
        f'<p class="winter-motor-sub">{e(m["sub"])}</p><p>{e(m["texto"])}</p>'
        f'<p class="winter-tag winter-tag-{m["tipo"]}">{e(m["tag"])}</p></article>' for m in b["motores"])
    classes = "".join(
        f'<li data-min="{c["idade"][0]}" data-max="{c["idade"][1] or 99}" data-peso-lb="{c["peso_lb"]}">'
        f'<strong>{e(c["nome"])}</strong><span>{_idade(c)}</span>'
        f'<span>Min {c["peso_lb"]} lb · {round(c["peso_lb"] * 0.4536)} kg</span><span>{e(c["motor"])}</span></li>'
        for c in b["categorias"])
    texto = "".join(f"<p>{inline(t)}</p>" for t in b["regras"])
    calc = f"""<form class="winter-calc" data-categoria aria-label="Class finder">
  <div class="winter-calc-campos" data-so-js hidden>
    <label>Date of birth<input type="date" min="1950-01-01" max="2022-12-31" data-dob></label>
    <label>Weight in full gear<span class="winter-unidade"><input type="number" min="15" max="400" step="0.5" inputmode="decimal" placeholder="e.g. 32" data-peso><select aria-label="Weight unit" data-peso-un><option value="kg">kg</option><option value="lb">lb</option></select></span></label>
    <label>Height <span class="opcional">(optional)</span><span class="winter-unidade"><input type="number" min="80" max="230" step="1" inputmode="numeric" placeholder="e.g. 135" data-altura><select aria-label="Height unit" data-altura-un><option value="cm">cm</option><option value="in">in</option></select></span></label>
  </div>
  <p class="winter-idade" data-so-js hidden><strong data-idade>–</strong> <span>racing age on 1 Jan 2027</span></p>
  <ul class="winter-classes" data-classes>{classes}</ul>
  <p class="winter-dica" data-dica data-so-js hidden aria-live="polite">Drop in the date of birth to light up the classes open to the driver.</p>
  <p class="winter-dica" data-dica2 aria-live="polite"></p>
</form>"""
    miolo = (blocos._cabeca(b, i) + f'<p class="winter-kicker">{e(b["motores_titulo"])}</p><div class="winter-motores">{motores}</div>'
             f'<div class="winter-categorias"><div class="winter-categorias-texto"><h3>{e(b["categorias_titulo"])}</h3>{texto}'
             f'<p class="small muted">{e(b["fonte"])}</p></div>{calc}</div>')
    return _secao(b, i, miolo, "winter-escolha")


def _karts_com_preco(servicos):
    """Os karts da estimativa com a diária do PAINEL: o serviço ativo de cada kart do Arrive and Drive (#263), pela mesma
    regra da página dele (`paginas._karts_do_painel`). `servicos` são os do painel, que a rota passa no contexto
    (`api.vitrine._servicos_do_site`). Kart sem serviço ativo (ou com dois) sai da estimativa; banco fora (None), a página
    cai no preço de sempre do site (`conteudo.KARTS`), como o Arrive and Drive."""
    precos = {k["nome"].lower(): (sv["price"] if sv else k["preco"])
              for k, sv in _karts_do_painel(servicos) if not k.get("proprio")}
    return [(k, precos[k["chave"].lower()]) for k in KARTS_DA_ESTIMATIVA if k["chave"].lower() in precos]


def _estimativa(b, i, host, ctx):
    """"What it costs": a diária do kart do painel × os dias de teste que cabem na estadia do plano (o `winter.js` faz a
    conta; o número nunca é texto da página). O fim de semana de corrida e as opções: "quoted per event / separately"."""
    karts = _karts_com_preco(ctx["servicos"]() if ctx.get("servicos") else None)
    marcado = "2s" if any(k["kt"] == "2s" for k, _p in karts) else (karts[0][0]["kt"] if karts else None)
    botoes = "".join(
        f'<button type="button" class="winter-kt" data-kt="{k["kt"]}" data-preco="{preco:g}" data-nome="{e(k["nome"])}" '
        f'data-nota="{e(k["nota"])}" aria-pressed="{"true" if k["kt"] == marcado else "false"}">{e(k["rotulo"])}'
        f'<small>{e(k["idade"])} · {usd(preco)}/day</small></button>' for k, preco in karts)
    nota = next((k["nota"] for k, _p in karts if k["kt"] == marcado), "")
    kart = (f'<fieldset class="winter-karts"><legend>{e(b["kart_titulo"])}</legend><div class="winter-kts">{botoes}</div>'
            f'<p class="small" data-kt-nota>{e(nota)}</p></fieldset>') if karts else ""
    corrida, testes, opcional = b["linhas"]
    extras = "".join(
        f'<div class="winter-opcional"><span>{e(nome)}<small data-extra-sub="{e(nome)}" data-resto=" · {e(resto)}">'
        f'{"In your plan" if no_plano else "Available on request"} · {e(resto)}</small></span><b>{e(opcional)}</b></div>'
        for _campo, nome, _t, no_plano, resto in EXTRAS)
    form = f"""<form class="winter-estimativa" data-estimativa aria-label="Estimate">
  <div class="winter-est-esq">{kart}
    <div class="winter-testes" data-so-js hidden><label>{e(b["testes_titulo"])} <strong data-testes-v>0</strong>
      <input type="range" min="0" max="0" value="0" step="1" data-testes></label><p class="small" data-testes-dica></p></div>
    <div class="winter-linhas">
      <div><span>{e(corrida[0])}<small data-sub-corrida>{e(corrida[1])}</small></span><b>{e(corrida[2])}</b></div>
      <div data-linha-testes hidden><span>{e(testes[0])}<small data-sub-testes></small></span><b data-total-testes></b></div>
      {extras}
    </div>
    <p class="small winter-letra-miuda">{e(b["letra_miuda"])}</p>
  </div>
  <div class="winter-total">
    <p class="winter-total-t">Estimated investment</p>
    <p class="winter-total-v"><span aria-hidden="true">≈</span> <strong data-total>–</strong></p>
    <p class="small" data-total-nota>{e(b["total_nota"])}</p>
    <p class="small muted" data-quem aria-live="polite"></p>
    <div class="hero-acoes"><a class="btn" href="{AGENDA}" rel="noopener">{e(b["cta"])}</a><a class="btn btn-linha-branca" href="#build">Build your winter</a></div>
    <p class="small">{e(b["agenda"])} <a href="mailto:{EMAIL}">{EMAIL}</a></p>
  </div>
</form>"""
    return _secao(b, i, blocos._cabeca(b, i) + form, "winter-custo")


# ------------------------------------------------------------------ o formulário (Build your winter)
def _extras_do_plano():
    """Os campos do plano, no formulário por blocos: cada `x_*` vira uma linha da nota da oportunidade em Vendas."""
    origens = "".join(f'<option value="{e(r)}" data-origem="{k}">{e(r)}</option>' for k, r, _t in ORIGENS)
    fins = "".join(
        f'<label class="opcao winter-opcao"><input type="checkbox" name="x_weekend_{n}" value="{e(p["datas"] + " · " + p["titulo"])}"'
        f'{" checked" if p["tipo"] == "home" else ""} data-inicio="{p["inicio"]}" data-fim="{p["fim"]}" data-motor="{p["motor"]}"'
        f' data-tipo="{p["tipo"]}"><span><strong>{e(p["datas"])}</strong> {e(p["titulo"])}'
        f'<small>{e(p["tag"] + (" · " + p["motor"].upper() if p["motor"] else ""))}</small></span></label>'
        for n, p in enumerate(PROVAS, 1))
    janelas = " ".join(f"{a}/{z}" for a, z in JANELAS)
    chegadas = "".join(f'<option value="Week of {_dia(d)}" data-dia="{d.isoformat()}"{" selected" if d == CHEGADA else ""}>'
                       f"Week of {_dia(d)}</option>" for d in CHEGADAS)
    voltas = "".join(f'<option value="Sunday {_dia(d)}" data-dia="{d.isoformat()}"{" selected" if d == VOLTA else ""}>'
                     f"Sunday {_dia(d)}</option>" for d in VOLTAS)
    bases = "".join(f'<option value="{e(x)}">{e(x)}</option>' for x in BASES)
    extras = "".join(
        f'<label class="opcao winter-opcao"><input type="checkbox" name="{campo}" value="Yes"{" checked" if marcado else ""}'
        f' data-extra="{e(nome)}"><span><strong>{e(nome)}</strong><small>{e(texto)}</small></span></label>'
        for campo, nome, texto, marcado, _resto in EXTRAS)
    return f"""<input type="hidden" name="x_season" value="Winter Season 2027">
    <div class="winter-duas">
      <label>Driver <span class="opcional">(optional)</span><input name="x_driver" maxlength="40" placeholder="First name" autocomplete="off" data-piloto></label>
      <label>Racing from<select name="x_racing_from" data-origem-select>{origens}</select></label>
    </div>
    <div class="winter-duas">
      <label>Racing age on 1 Jan 2027 <span class="opcional">(optional)</span><input name="x_racing_age" type="number" min="3" max="99" inputmode="numeric" data-idade-campo></label>
      <label>Weight in full gear <span class="opcional">(optional)</span><input name="x_weight_in_full_gear" maxlength="20" placeholder="e.g. 32 kg" data-peso-campo></label>
    </div>
    <fieldset class="winter-opcoes" data-fins data-janelas="{janelas}"><legend>Race weekends</legend>{fins}</fieldset>
    <div class="winter-duas">
      <label>Arrive in Florida<select name="x_arrive" data-chegada>{chegadas}</select></label>
      <label>Fly home<select name="x_fly_home" data-volta>{voltas}</select></label>
    </div>
    <label>Base camp<select name="x_base_camp">{bases}</select></label>
    <fieldset class="winter-opcoes"><legend>Add to the package</legend>{extras}</fieldset>
    <div class="winter-resumo" data-resumo hidden>
      <p class="winter-resumo-t">Your winter</p>
      <dl class="winter-resumo-n"><div><dt>Race weekends</dt><dd data-n-fins>0</dd></div><div><dt>Testing days</dt><dd data-n-testes>0</dd></div><div><dt>Weeks in FL</dt><dd data-n-semanas>0</dd></div></dl>
      <ul class="winter-alertas" data-alertas aria-live="polite"></ul>
    </div>
    """


# ------------------------------------------------------------------ o JSON-LD: as rodadas de casa (o que a página afirma)
_OKC = {"@type": "Place", "name": "Orlando Kart Center",
        "address": {"@type": "PostalAddress", "streetAddress": "10724 Cosmonaut Blvd", "addressLocality": "Orlando",
                    "addressRegion": "FL", "postalCode": "32824", "addressCountry": "US"}}


def _rodadas_de_casa(host):
    """As duas rodadas da SKUSA Winter Series em Orlando, com data e lugar. As opcionais ficam fora: a página não dá o
    endereço de Sebring, e as outras estão "to confirm" ou com local a anunciar."""
    def evento(nome, inicio, fim):
        return {"@type": "SportsEvent", "name": nome, "startDate": inicio, "endDate": fim, "sport": "Kart racing",
                "eventStatus": "https://schema.org/EventScheduled",
                "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode", "location": _OKC,
                "organizer": {"@type": "Organization", "name": "SKUSA"}, "url": f"https://{host}{CAMINHO}",
                "description": "Dates as published Oct 2026 · we reconfirm before entry"}
    return {"@context": "https://schema.org", "@graph": [
        evento("SKUSA Winter Series 2027 · Rounds 1 & 2", ALVO, "2027-01-17"),
        evento("SKUSA Winter Series 2027 · Rounds 3 & 4", "2027-02-12", "2027-02-14")]}


# ------------------------------------------------------------------ a página
WINTER = {
    "caminho": CAMINHO,
    "titulo": "Race the Winter 2027 | URACE",
    "descricao": ("Race the Winter 2027 with URACE: 80 days of testing and four SKUSA Winter Series rounds at Orlando Kart "
                  "Center. Proven: Frankie Iadevaia, P1 at FLKC Jacksonville."),
    "foto": "frankie-iadevaia-urace-driver-jacksonville.webp",
    "indexar": True,
    "trilha": (("Race the Winter 2027", CAMINHO),),
    "schemas": (_rodadas_de_casa,),
    "scripts": ("winter.js",),
    "blocos": [
        {"tipo": "hero", "eyebrow": "Winter Season · January to March 2027 · Orlando, Florida", "h1": "Race the winter",
         "sub": ("From January the winter grids race in Florida. All four 2027 SKUSA Winter rounds run at Orlando Kart "
                 "Center, our home track. Land, suit up, drive: the kart, the crew and the plan are ready."),
         "ctas": [("Build your winter", "#build"), ("Get your quote", AGENDA)],
         "foto": "frankie-iadevaia-urace-driver-jacksonville.webp",
         "alt": "Frankie Iadevaia, URACE program driver, after his win in Jacksonville"},
        _funcao(_origem, fundo="escura", rotulo_secao="Racing from", itens=ORIGENS),
        {"tipo": "contador", "eyebrow": "Next round · 15–17 Jan 2027 · Orlando Kart Center",
         "titulo": "SKUSA Winter Series · R1–2", "alvo": ALVO, "rotulo": "to lights out · 15 Jan 2027 · 8:00 am ET",
         "texto": "That is your prep window: seat fit, testing, class call. Lights out 15 Jan 2027 · SKUSA Winter R1."},
        {"tipo": "numeros", "rotulo_secao": "Winter Season 2027", "itens": [
            ("4", "SKUSA Winter rounds at our home track"), ("7", "Race weekends, Jan to Mar"),
            ("3", "Engine packages: Rotax · IAME · ROK"), ("1", "Crew, from first test to the flag")]},
        _funcao(_citacao, ancora="italo", rotulo_secao="Italo da Silveira, founder of URACE",
                foto="italo-da-silveira-urace-founder.webp", alt="Italo da Silveira, founder of URACE",
                citacao=(("I’ve raced. I’ve won.", "I know the way."),
                         "If your kid has the pace, I’ll show them the line. Same kart, same crew, every lap of the winter, "
                         "from the first test to the last flag."),
                quem="Italo da Silveira", papel="Driver · Founder, URACE"),
        {"tipo": "texto", "ancora": "proof", "eyebrow": "Proof · October 2026", "titulo": "P1. Rounds 7 & 8. Jacksonville.",
         "paragrafos": ["Frankie Iadevaia came through the URACE program and won both FLKC rounds at North Florida Kart "
                        "Center. Same team, same method, same engineers you get this winter.",
                        "**Frankie Iadevaia** · URACE program driver · FLKC winner",
                        "[See the win on Instagram](https://www.instagram.com/p/DeKcd53lDao/)"],
         "foto": "frankie-iadevaia-checkered-flag-flkc-jacksonville.webp",
         "alt": "Frankie Iadevaia takes the checkered flag at FLKC Jacksonville in a URACE kart"},
        {"tipo": "videos", "ancora": "on-camera", "fundo": "escura", "eyebrow": "On camera", "titulo": "Hear it from the team",
         "itens": [{**CURTAS["vitoria"], "titulo": "Frankie Iadevaia", "legenda": "After the win · FLKC P1 · 29 s"},
                   {**CURTAS["primeira"], "titulo": "Brody", "legenda": "His first KA100 race · 19 s"},
                   {**CURTAS["fundador"], "titulo": "Italo", "legenda": "Founder · why URACE exists · 20 s"}]},
        {"tipo": "passos", "ancora": "window", "eyebrow": "01 · The window", "titulo": "Snow stops racing. Orlando doesn’t.",
         "intro": ["No snow, no break. All four SKUSA Winter rounds run at Orlando Kart Center, our home track.",
                   "**The winter, lap by lap · Orlando Kart Center**"],
         "itens": [(t, (f"**{quando}**", x)) for t, quando, x in FASES]},
        {"tipo": "texto", "fundo": "escura", "eyebrow": "URACE on track · Winter testing", "titulo": "January is race season here",
         "foto": "urace-kart-corner.webp", "alt": "A URACE kart at speed through a corner"},
        _funcao(_calendario, ancora="races", eyebrow="02 · The calendar", titulo="Your race weekends",
                intro="Two home weekends are the backbone. The rest bolt on if you want them.", rodadas=RODADAS,
                provas=PROVAS,
                nota=("Two weekends are ours by default.",
                      "15–17 Jan and 12–14 Feb run at Orlando Kart Center: the driver races on the asphalt they tested on "
                      "all winter. Testing windows in between: 19–21 Jan, 25–28 Jan and 1–11 Feb."),
                datas="Dates as published Oct 2026 · we reconfirm before entry"),
        _funcao(_maquina, ancora="machine", eyebrow="03 · The machine", titulo="Your kart, ready on the stand",
                intro="You bring the driver and the helmet. The kart is ready when you land. Tap a part.", pecas=PECAS,
                kart=("arrive-drive-kart-on-track.webp", "A URACE kart on track",
                      "The real thing: a URACE kart on the grid, prepared by the same crew that runs the winter."),
                equipe=("The crew", (
                    ("arrive-drive-first-corner.webp", "A URACE kart through the first corner", "Race day at Orlando Kart Center."),
                    ("banner-topo-lp-urace-1.webp", "URACE karts on track",
                     "Trackside, every session. The same people from first test to last round.")))),
        _funcao(_escolha, fundo="escura", ancora="decision", eyebrow="04 · Our call", titulo="The engine call is ours",
                intro="Three championships, three engines. We pick the package. That’s our job.",
                motores_titulo="Engine package · our call", motores=MOTORES,
                categorias_titulo="Class finder · the call is still ours", categorias=CATEGORIAS, fonte=CATEGORIAS_FONTE,
                regras=("**Racing age = age on 1 January.** Not race day. Ages overlap between classes (9–10, 12–13, 15), "
                        "so an age can open two doors.",
                        "**Weight is kart + driver in gear.** Every class has a minimum. Light drivers run ballast to reach "
                        "it; heavy drivers carry the extra.",
                        "**Move up and there is no moving back.** So we put the driver in the right class first. Worth "
                        "more than any set-up.")),
        {"tipo": "formulario", "ancora": "build", "eyebrow": "05 · Build your winter", "titulo": "Pick your weekends",
         "texto": "Pick your weekends and what you want around the track. Send it, we come back with the full plan.",
         "assunto": "team", "enviar": "Send plan to URACE", "extras": _extras_do_plano()},
        {"tipo": "cartoes", "ancora": "terms", "eyebrow": "06 · The package", "titulo": "In the paddock. Out of it.",
         "intro": ["On track we run the weekend. Off track we run the rest, so the driver only thinks about the next lap.",
                   "**On track · who brings what**"],
         "itens": [
             {"titulo": "URACE brings", "lista": [
                 "Kart and engine, prepared", "Spares package at every event", "Tent and hospitality",
                 "Mechanic and engineer on the weekend", "A coach on the driver all weekend",
                 "Testing and set-up at Orlando Kart Center", "Data and onboard review between rounds"]},
             {"titulo": "Your side", "lista": [
                 "The driver, licensed and medically cleared", "Racing suit and safety gear", "Entries, track passes and tyres",
                 "Dates of the Florida stay, in advance"]}]},
        {"tipo": "cartoes", "eyebrow": "Off track · options we arrange", "rotulo_secao": "Off track · options we arrange",
         "itens": [
             {"rotulo": "Base camp · our pick", "titulo": "Lake Nona Wave Hotel",
              "texto": "About 6 minutes from Orlando International Airport (MCO). Outdoor pool, Chopra spa, Technogym studio "
                       "and access to Lake Nona Performance Club. Two of its restaurants, BACÁN and Nami, are in the 2026 "
                       "MICHELIN Guide.",
              "link": ("Photos & map", "https://www.google.com/maps/search/?api=1&query=Lake+Nona+Wave+Hotel%2C+6100+Wave"
                                       "+Hotel+Dr%2C+Orlando%2C+FL+32827")},
             {"rotulo": "Hotels & homes", "titulo": "Your pit, your way",
              "texto": "Orlando has one of the biggest hotel networks in the US. Prefer a vacation home with space for the "
                       "whole family and the gear? We book that too, close to the track.",
              "link": ("Track photos & map", "https://www.google.com/maps/search/?api=1&query=Orlando+Kart+Center%2C+10724"
                                             "+Cosmonaut+Blvd%2C+Orlando%2C+FL+32824")},
             {"rotulo": "Athletic camp · optional", "titulo": "Lake Nona Performance Club",
              "texto": "Indoor track and turf field, sport-specific training programmes, pools and a climbing gym. A fitness "
                       "block can go into the package.",
              "link": ("Photos & map", "https://www.google.com/maps/search/?api=1&query=Lake+Nona+Performance+Club%2C+Orlando%2C+FL")},
             {"rotulo": "Mental performance · optional", "titulo": "Train the head",
              "texto": "Our mental performance coach works with drivers trackside and between rounds: focus, reset after a "
                       "mistake, nerves on the grid. Group sessions or full trackside weekends.",
              "link": ("Part 8 of the kart", "#kart-part-8")},
             {"rotulo": "Concierge", "titulo": "One call, all sorted",
              "texto": "Airport pickup, car, hotel, restaurant bookings and the schedule between sessions. One contact for "
                       "everything off track.",
              "link": ("Ask the concierge", f"mailto:{EMAIL}?subject=Winter%20Season%202027%20%C2%B7%20concierge")},
             {"rotulo": "Pit-stop dinners · 2026 MICHELIN Guide", "titulo": "Where Orlando eats", "lista": [
                 "[Sorekara](https://www.google.com/maps/search/?api=1&query=Sorekara%2C+Baldwin+Park) · 2 stars · Baldwin Park",
                 "[Camille](https://www.google.com/maps/search/?api=1&query=Camille%2C+Baldwin+Park) · 1 star · Baldwin Park",
                 "[Kadence](https://www.google.com/maps/search/?api=1&query=Kadence%2C+Audubon+Park) · 1 star · Audubon Park",
                 "[ÔMO by Jônt](https://www.google.com/maps/search/?api=1&query=%C3%94MO+by+J%C3%B4nt%2C+Winter+Park) · 1 star "
                 "· Winter Park",
                 "[Soseki Modern Omakase](https://www.google.com/maps/search/?api=1&query=Soseki+Modern+Omakase%2C+Winter+Park)"
                 " · 1 star · Winter Park",
                 "[Victoria & Albert’s](https://www.google.com/maps/search/?api=1&query=Victoria+%26+Albert%27s%2C+Disney%27s"
                 "+Grand+Floridian) · 1 star · Disney’s Grand Floridian",
                 "Plus 14 Bib Gourmand picks across the city. We book the table."]}]},
        _funcao(_estimativa, fundo="escura", ancora="price", eyebrow="08 · Estimate", titulo="What it costs",
                intro="Built from your plan above. An estimate, not a quote: the final number comes once class and dates are locked.",
                kart_titulo="Kart & equipment", testes_titulo="Testing days with the crew",
                linhas=(("Race Weekend Support", "kart prep and trackside support", "Quoted per event"),
                        ("Testing days",), "Optional · quoted separately"),
                total_nota="+ Race Weekend Support · quoted per event",
                letra_miuda=("USD, before taxes. Day rates from the urace.us rate card by kart type (Arrive & Drive); race "
                             "weekend support is quoted per event. Not included: race entries, tyres, track passes, fuel and "
                             "consumables, travel and accommodation. Concierge, mental performance and the Lake Nona "
                             "Performance Club camp are offered as options and quoted separately."),
                cta="Get the real quote",
                agenda="Pick a slot on Lucas’s calendar and we walk through this estimate together. Prefer email?"),
    ],
}

PAGINAS = (WINTER,)
