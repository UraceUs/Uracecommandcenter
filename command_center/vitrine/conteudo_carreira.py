"""O simulador de carreira do /career/ (#528): os dados do "Plan your career" do urace.us.

Dono, 30/10: *"sim pfvr"* (refazer o simulador no site novo) e, sobre os preços, *"usa os valores do urace us"*.
A fonte é o script da página urace.us/plan-your-career/ (modificada em 29/10/2026): as listas `BASE`, `BRANCH`,
`FARA` e `LEGS` (os degraus e as três rotas), `LEG_META` (o nome e a frase de cada destino), `SPECS` ("Typical
figures for this step"), `RESULTS` e `decide()` ("Find your step") e `PLAN_ITEMS`/`PLAN_FOR` ("My career plan").
O texto está como lá, sem reescrever (só sai o HTML de dentro: `&amp;` vira `&`, `<small>mph</small>` vira " mph").
De cada degrau entra o 1º parágrafo da aba "Overview", como o modo passo a passo de lá mostra.

O que fica diferente, de propósito:

- **Preço é número aqui** e a página escreve com `usd()`: `(1200, "month")` sai "$1,200 / month", como lá. O
  `carreira.js` não tem preço nenhum: lê o `data-preco` de cada linha do plano.
- **Academy**: o urace.us mostra $2,756.90 / $2,688.43 / $2,619.06 (1, 3 e 6 meses); a página /academy/ segue a
  planilha (#273). O dono mandou usar os do urace.us no simulador (30/10); a diferença está no PR para ele decidir.
- **Professional Coaching — 4-hour session** (um "quote" do plano de lá) não entra: o nome saiu do site (#254, dono
  15/10: *"o professional coaching se tornou o arrive and drive"*). O Racing Team continua "quote · by invitation".
- **Taxa da pista**: a nota do plano de lá traz $100–230 / $100–125 / $22; o site segue a taxa do robô SDR (dono, 20/10,
  `test_reserva_addon_kart_proprio`). A nota diz só que a taxa é à parte; o valor do site está no aviso da página.
- "Who is driving?" (criança × adulto) de lá só troca o boneco do desenho: não entra. O carro que sobe a escada, as
  fotos e os desenhos dos carros também não (o site não desenha à mão).
"""

LIGACAO = "https://calendar.app.google/KBbHhXjoRMS6sbHv8"     # "Talk to us" / "Talk through this plan" (o mesmo de lá)

# ------------------------------------------------------------------ os rótulos de lá
QUEM_NOSSO = "URACE runs this rung"
QUEM_FORA = "Outside URACE — we prepare and enter drivers"
QUEM_BIFURCA = "The ladder splits here"
QUEM_DESTINO = "The destination"

SIMULADOR = {
    "eyebrow": "URACE Career Simulator",
    "titulo": "Select your career",
    "texto": ("Three destinations, one ladder, eleven steps. Pick where you want to end up and we will walk you up the "
              "whole thing — what each step is, what it costs, and where we hand you over."),
    "numeros": "Typical figures for this step",
    "fim": ("Talk to us about step 1", LIGACAO),
}


def _degrau(chave, passo, nome, curto, quem, texto, numeros, nivel=(), custo=None, quando=None, link=None):
    """Um degrau. `custo` = (valor, unidade) ou "quote"; `nivel` = as linhas do `meta` de lá que não são preço."""
    return {"chave": chave, "passo": passo, "nome": nome, "curto": curto, "quem": quem, "texto": texto,
            "numeros": numeros, "nivel": tuple(nivel), "custo": custo, "quando": quando, "link": link}


# os quatro degraus vermelhos (a URACE faz) e o National Karting, que as três rotas dividem
BASE = (
    _degrau("sim2grid", "Step 1", "Sim2Grid", "Sim2Grid", QUEM_NOSSO,
            "A full motion cockpit: competition seat and harness, direct-drive wheel, racing pedals, triple screen. It "
            "moves. It loads you up in the corners and punishes the same mistakes a real car does. Our own drivers learn "
            "a circuit on it before they ever see it.",
            (("Top speed", "Any car"), ("Cockpit", "Full motion"), ("Track fee", "$0")),
            quando="Opens 1 Nov 2026", custo=(1200, "month"), link="/sim2grid-racing-simulator/"),
    _degrau("arrive-and-drive", "", "Arrive and Drive", "Arrive & Drive", QUEM_NOSSO,
            "Most people's idea of a go-kart is a theme park ride. This is not that. These are authentic, professional "
            "racing karts at the Orlando Kart Center — an 8/10 mile professional circuit just off the Florida Turnpike, "
            "minutes from most of Orlando's attractions.",
            (("Top speed", "50–70 mph"), ("Session", "10 min"), ("Circuit", "8/10 mile")),
            custo=(719, "day"), link="/services/arrive-and-drive/"),
    _degrau("academy", "", "URACE Academy", "Academy", QUEM_NOSSO,
            "The Academy is where a driver stops having fun days and starts getting faster on purpose.",
            (("Top speed", "50–70 mph"), ("Track time", "1 h / day"), ("Days", "4 / month")),
            custo=(2756.90, "month"), link="/academy/"),
    _degrau("racing-team", "Step 2 – 3", "URACE Racing Team", "Racing Team", QUEM_NOSSO,
            "The Racing Team is the top of our ladder — and URACE's motorsport hub. It's where Academy drivers who are "
            "ready start competing under the URACE banner: Florida state karting first, then the US national "
            "championships.",
            (("Top speed", "~75 mph"), ("Engine", "~30 hp"), ("Level", "State → National")),
            nivel=("Florida State", "US National"), custo="quote", link="/pro-team/"),
)
BIFURCACAO = _degrau(
    "national-karting", "Step 4", "National Karting", "Nat. Karting", QUEM_BIFURCA,
    "National karting is the last rung every route shares. From here the ladder splits by age and by destination: under "
    "14 the driver keeps building in karting, and from 14 the Formula FARA selective opens.",
    (("Top speed", "~75 mph"), ("Engine", "~30 hp"), ("Age", "7–13")),
    nivel=("Ages 7 – 13", "or FARA selective at 14+"))
FARA = _degrau(
    "formula-fara", "Step 5", "Formula FARA", "FARA", QUEM_FORA,
    "The first rung in a car rather than a kart, and the point where a driver finds out how much of their karting "
    "translates.",
    (("Top speed", "~130 mph"), ("Power", "~180 hp"), ("Wheels", "Open")), nivel=("First car",))


def _fora(chave, passo, nome, curto, nivel, texto, numeros, destino=False):
    return _degrau(chave, passo, nome, curto, QUEM_DESTINO if destino else QUEM_FORA, texto, numeros, nivel=(nivel,))


# chave, nome, a etiqueta e a frase da escolha (LEG_META), a nota da rota (LEGS[...].note) e os degraus de cima
ROTAS = (
    {"chave": "f1", "nome": "Formula 1", "tag": "The European route",
     "linha": "The longest and most expensive route, and the one where a karting record counts for most.",
     "nota": ("The open-wheel route out of the United States. Longest and most expensive of the three, and the one where "
              "a karting record counts for most."),
     "degraus": (
         FARA,
         _fora("formula-4", "Step 6", "Formula 4", "F4", "First single-seater series",
               "The entry single-seater category recognised by the FIA, run as national championships around the world.",
               (("Top speed", "~160 mph"), ("Power", "~160 hp"), ("0–60", "~4 s"))),
         _fora("formula-regional", "Step 7", "Formula Regional", "F Regional", "Regional single-seater",
               "The step between F4 and FIA F3, run as regional championships. The first rung where a driver is normally "
               "racing full-time.",
               (("Top speed", "~165 mph"), ("Power", "~270 hp"), ("0–60", "~3 s"))),
         _fora("fia-formula-3", "Step 8", "FIA Formula 3", "F3", "F1 support series",
               "Runs on Formula 1 weekends. From here a driver is inside the F1 paddock and visible to the teams.",
               (("Top speed", "~190 mph"), ("Power", "~380 hp"), ("0–60", "~3 s"))),
         _fora("fia-formula-2", "Step 9", "FIA Formula 2", "F2", "F1 support series",
               "The last rung before Formula 1, and the one most current F1 drivers came through.",
               (("Top speed", "~200 mph"), ("Power", "~620 hp"), ("0–60", "~2.9 s"))),
         _fora("formula-1", "Step 10", "Formula 1", "F1", "20 seats in the world",
               "Twenty seats, worldwide. Nobody can promise this rung, and we don't — what we can promise is that every "
               "rung below it is a real one and that we know how it's climbed.",
               (("Top speed", "~215 mph"), ("Power", "~1,000 hp"), ("0–60", "~2.6 s")), destino=True))},
    {"chave": "indy", "nome": "IndyCar", "tag": "The Road to Indy",
     "linha": "The American open-wheel ladder, with scholarship money attached to winning each rung.",
     "nota": ("The Road to Indy. The American open-wheel route, with a defined scholarship structure between its rungs — "
              "the cheapest of the three single-seater paths to a top-level seat."),
     "degraus": (
         FARA,
         _fora("usf-juniors", "Step 6", "USF Juniors", "USF Jr", "Entry rung",
               "The entry category of the USF Pro Championships, built as the first car step for drivers coming straight "
               "out of karting.",
               (("Top speed", "~130 mph"), ("Power", "~120 hp"), ("Wheels", "Open"))),
         _fora("usf2000", "Step 7", "USF2000", "USF2000", "Road to Indy",
               "The first full rung of the Road to Indy ladder, racing on IndyCar weekends.",
               (("Top speed", "~140 mph"), ("Power", "~175 hp"), ("0–60", "~4 s"))),
         _fora("usf-pro-2000", "Step 8", "USF Pro 2000", "USF Pro", "Road to Indy",
               "More power, more downforce, and the rung where the scholarship money starts to be worth real seasons.",
               (("Top speed", "~160 mph"), ("Power", "~275 hp"), ("0–60", "~3.4 s"))),
         _fora("indy-nxt", "Step 9", "Indy NXT", "Indy NXT", "IndyCar support series",
               "The final rung of the ladder, running on IndyCar weekends including the Indianapolis road course.",
               (("Top speed", "~190 mph"), ("Power", "~450 hp"), ("0–60", "~3 s"))),
         _fora("indycar", "Step 10", "IndyCar", "IndyCar", "The Indianapolis 500",
               "The top of American open-wheel racing. The Road to Indy is the most clearly defined ladder in "
               "motorsport, which is exactly why we map a driver onto it early.",
               (("Top speed", "~235 mph"), ("Power", "~700 hp"), ("0–60", "~2.9 s")), destino=True))},
    {"chave": "nascar", "nome": "NASCAR", "tag": "The stock car route",
     "linha": "Leaves karting earliest of the three. The decision gets made young.",
     "nota": ("The stock car route. It leaves karting earliest of the three — a driver moves into a car with fenders while "
              "the open-wheel routes are still karting."),
     "degraus": (
         _fora("legends-bandolero", "Step 5", "Legends & Bandolero", "Legends", "First stock car",
               "Small, cheap, heavily subscribed stock cars on short ovals and road courses. The usual first car for a "
               "driver heading toward NASCAR.",
               (("Top speed", "~110 mph"), ("Power", "~125 hp"), ("Weight", "~1,300 lb"))),
         _fora("late-models", "Step 6", "Late Models", "Late Model", "Regional short track",
               "Regional short-track racing, and the rung where a driver learns the close-quarters craft that defines "
               "stock car racing.",
               (("Top speed", "~120 mph"), ("Power", "~400 hp"), ("Surface", "Short track"))),
         _fora("arca-menards-series", "Step 7", "ARCA Menards Series", "ARCA", "National entry",
               "The first national rung, racing on some of the same superspeedways as the NASCAR national series.",
               (("Top speed", "~180 mph"), ("Power", "~670 hp"), ("Level", "National"))),
         _fora("craftsman-truck-series", "Step 8", "Craftsman Truck Series", "Truck", "NASCAR national",
               "The first of NASCAR's three national series, and the usual professional debut.",
               (("Top speed", "~180 mph"), ("Power", "~650 hp"), ("Level", "NASCAR"))),
         _fora("xfinity-series", "Step 9", "Xfinity Series", "Xfinity", "NASCAR national",
               "The last rung before Cup, run as a support series on most Cup weekends.",
               (("Top speed", "~190 mph"), ("Power", "~650 hp"), ("Level", "NASCAR"))),
         _fora("nascar-cup-series", "Step 10", "NASCAR Cup Series", "Cup", "The Daytona 500",
               "The top of American stock car racing. The route here leaves karting earliest, which is why the branch "
               "point matters — the decision gets made young.",
               (("Top speed", "~200 mph"), ("Power", "~670 hp"), ("0–60", "~3.4 s")), destino=True))},
)
PADRAO = "f1"            # lá, a escada abre na rota do Formula 1 (`curLeg="f1"`)


def rota(chave):
    return next(r for r in ROTAS if r["chave"] == chave)


def caminho(chave):
    """Os degraus de uma rota, de baixo para cima (o `buildSeq` de lá): os quatro da URACE, o National Karting e os da
    rota. São onze nas três."""
    return (*BASE, BIFURCACAO, *rota(chave)["degraus"])


# ------------------------------------------------------------------ "Find your step" (RESULTS e decide() de lá)
LOCALIZADOR = {
    "titulo": "Find your step",
    "texto": "Three questions. The same three we ask every driver who calls us — they decide everything else.",
    "resultado": "Your starting rung",
    "abrir": "Open this rung",
    "perguntas": (
        ("who", "1 · Who is the driver?", (("child", "My child"), ("me", "Me"))),
        ("age", "2 · How old?", (("4", "4 – 6"), ("7", "7 – 10"), ("11", "11 – 15"), ("16", "16 +"))),
        ("exp", "3 · Been in a race kart before?", (("never", "Never"), ("some", "A few times"), ("races", "Races already"))),
    ),
}
RESULTADOS = {
    "sim": ("sim2grid", "Start in the simulator. It's the cheapest honest way to find out whether this is a hobby or a "
                        "career, it costs $60 for an hour on your own or $150 with a coach beside you, and there's no "
                        "track fee, no equipment and no weather in the way."),
    "ad": ("arrive-and-drive", "Start with one full day in a real race kart — kart, gear and a coach all day, $719. One "
                               "day with data afterwards tells you more than a year of wondering, and nothing is "
                               "committed after it."),
    "academy": ("academy", "You skip Sim2Grid — there's already something to build on, and open track time would waste "
                           "it. The Academy turns laps into a plan: a coach, data and video review, and a development "
                           "plan that carries month to month."),
    "team": ("racing-team", "You skip the simulator and the Academy entirely. A driver who already races does not need an "
                            "introduction, they need a record — and this is where that record gets built, under the URACE "
                            "banner, with the professional side built alongside it."),
}


def decidir(quem, idade, experiencia):
    """O `decide()` de lá: sem as três respostas, nada; quem já corre vai ao Racing Team, quem já andou à Academy,
    quem nunca andou e tem até 6 anos ao Arrive and Drive, e o resto começa no simulador."""
    if not quem or not idade or not experiencia:
        return None
    if experiencia == "races":
        return "team"
    if experiencia == "some":
        return "academy"
    return "ad" if int(idade) <= 6 else "sim"


# ------------------------------------------------------------------ "My career plan" (PLAN_ITEMS e PLAN_FOR de lá)
PLANO = {
    "titulo": "My career plan",
    "texto": ("Add rungs as you read them and this builds the actual budget — one-off costs on one side, monthly on the "
              "other. It’s the same arithmetic we do with a family on a call, except you can do it yourself first, with "
              "nobody selling at you."),
    "nota": ("The circuit's track fee is charged separately by the Orlando Kart Center and is not in these totals. "
             "Simulator hours have no track fee."),
    "falar": ("Talk through this plan", LIGACAO),
}
# chave, rótulo, preço (None = "we quote this"), unidade ("once", "month" ou "quote"), a linha de baixo, o degrau
ITENS_PLANO = (
    ("sim-solo", "Sim2Grid — solo hour", 60, "once", "per hour", "sim2grid"),
    ("sim-coach", "Sim2Grid — coached hour", 150, "once", "per hour", "sim2grid"),
    ("sim-school", "URACE Sim2Grid — 12 coached hours", 1200, "month", "per month", "sim2grid"),
    ("ad-day", "Arrive and Drive — full day", 719, "once", "per driver, per day", "arrive-and-drive"),
    ("ac-1", "URACE Academy — monthly", 2756.90, "month", "per driver, per month", "academy"),
    ("ac-3", "URACE Academy — 3-month rate", 2688.43, "month", "per driver, per month", "academy"),
    ("ac-6", "URACE Academy — 6-month rate", 2619.06, "month", "per driver, per month", "academy"),
    ("team", "URACE Racing Team — season", None, "quote", "by invitation", "racing-team"),
)
SO_UM = ("ac-1", "ac-3", "ac-6")       # lá, escolher uma tarifa da Academy tira as outras do plano (`ACADEMY`)


def totais(plano):
    """A conta do plano (o `planText()` de lá): {chave: quantidade} → (avulso, por mês, itens a cotar)."""
    itens = {k: (p, u) for k, _l, p, u, _n, _d in ITENS_PLANO}
    avulso = mensal = 0
    cotar = 0
    for k, q in plano.items():
        if k not in itens:
            continue
        p, u = itens[k]
        if p is None:
            cotar += 1
        elif u == "month":
            mensal += p * q
        else:
            avulso += p * q
    return round(avulso, 2), round(mensal, 2), cotar
