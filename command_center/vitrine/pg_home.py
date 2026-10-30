"""A home, a About e a página de programas do urace.us de 29/10 (#507), montadas por blocos (#502).

Dono, 29/10: *"sim, pode trazer o texto e recriar a winter"*. O texto é o que o urace.us publicou em 29/10 (a home
"home-new", a About reescrita na voz do Italo e a Programs com o título novo), na ordem de lá, nos endereços do site novo.
O que fica diferente, de propósito:

- **preço por chave, nunca escrito**: o "From $719" do Arrive and Drive é a chave `kart` (painel); o "$1,200 / month" do
  Sim2Grid e o "$2,756.90 / month" da Academy (About) são as chaves `sim2grid` e `academy` (#525, `conteudo.PRECOS`,
  os valores do urace.us). Na Programs,
  o "What it will cost" do Sim2Grid são os programas do painel (Site › Cartões das páginas, `sim2grid`); os outros
  valores de lá (taxas, depósito, passes da pista) não têm fonte no painel e ficam de fora;
- as avaliações do Google são as de `conteudo.AVALIACOES` (#508, o texto e o nome como estão lá), com o link para todas;
  a nota e o número de avaliações ("4.9", "38 reviews") não se escrevem à mão: ficam velhos;
- os três vídeos de "Straight from the paddock" (mp4 do WordPress) e a faixa dos parceiros ainda não têm bloco;
- vídeo do YouTube é link (a política do site não deixa player de fora);
- o que o texto de lá ainda diz e o dono já mudou fica de fora da Programs: a remarcação (fica na página do programa),
  as idades dos karts (dono, 08/10), o passo a passo do carrinho do WooCommerce (a reserva é a do site), os nomes Kart
  School e Professional Coaching (#254) e o "Until then you cannot book" do Sim2Grid (#392: já se reserva). Termos,
  reembolso e a pista de cada programa estão na página dele.

As landings do Arrive and Drive (#506) e a Winter (#505) são de outras frentes. Os links para elas: o cartão da Winter
só aparece quando a página dela existe (com os dias até a largada contados do contador dela); os dois do Arrive and
Drive levam, até as landings entrarem, à página do Arrive and Drive (`AD_EXPERIENCIA`, `AD_RESERVA`).
"""
from datetime import datetime, timezone

from command_center.vitrine import blocos
from command_center.vitrine.conteudo import AVALIACOES, FECHO_DUVIDAS, GOOGLE, GRUPOS, LIGACAO, RESULTADOS, TRACK
from command_center.vitrine.paginas import _marca

# o "Talk to us" da About e o "Book a 15-min call" da Programs são a `conteudo.LIGACAO`; o "Book a call" da home de lá
# é outra agenda
CONVERSA_HOME = "https://calendar.app.google/whLkkpp82fUzsfvT8"
# as landings do Arrive and Drive (#506): /arrive-and-drive-karting-experience/ e /arrive-and-drive-karting-booking/
AD_EXPERIENCIA = "/services/arrive-and-drive/"
AD_RESERVA = "/services/arrive-and-drive/#reservar"
WINTER = "/winter/"

# as fotos (as mesmas da home de lá; as de cartão se cortam iguais no CSS)
BANDEIRADA = "frankie-iadevaia-checkered-flag-flkc-jacksonville.webp"
JACKSONVILLE = "frankie-iadevaia-urace-driver-jacksonville.webp"
BUSHNELL = "urace-team-bushnell-p1-p3.webp"
SIM2GRID_KV = "sim2grid-key-visual.webp"
PRIMEIRA_CURVA = "arrive-and-drive-first-corner.webp"
ACADEMY_FOTO = "img-7762-scaled.webp"
ITALO = "italo-da-silveira-urace-founder.webp"

# #521: "On the top step" é `conteudo.RESULTADOS`, o mesmo da Academy e das landings
TOPO = [{"foto": f, "alt": a, "titulo": t, "legenda": x} for f, a, t, x in RESULTADOS]
SIM_ABRE = "Opens 1 Nov 2026"
# o quarto depoimento da home de lá (não é do Google): o começo do depoimento do Aaron Benoit
AARON = ("Aaron Benoit", "SKUSA X30 Senior race winner",
         "I’ve had the pleasure of learning from Italo since I was a rookie. Through coaching, data review, and lead/follow "
         "sessions, my on track skills have improved significantly.")


# ------------------------------------------------------------------ "Pick your line": a Winter, quando existir
ESCOLHA = {
    "tipo": "cartoes", "eyebrow": "Plan your next lap", "titulo": "Pick your line", "ancora": "pick-your-line",
    "itens": [
        {"foto": BANDEIRADA, "alt": "", "titulo": "Race the Winter 2027",
         "texto": ("Snow stops racing. Orlando doesn’t. Four SKUSA Winter rounds at Orlando Kart Center, January to March. "
                   "Test, race, come home faster."),
         "link": ("See the winter program", WINTER)},
        {"foto": BUSHNELL, "alt": "", "rotulo": "Career simulator", "titulo": "Plan your career",
         "texto": ("From a sim seat in Orlando to F1, IndyCar or NASCAR. Find your step on the ladder and build the real "
                   "budget, rung by rung."),
         "link": ("Find your step", "/career/")},
        {"foto": SIM2GRID_KV, "alt": "", "rotulo": "Our services", "titulo": "From the sim to the grid",
         "texto": ("Every program in one place: Sim2Grid, Arrive and Drive, URACE Academy and the Racing Team. See them side "
                   "by side and pick your step."),
         "link": ("See all programs", "/services/")},
    ],
}


def _agora():
    return datetime.now(timezone.utc)


def _largada(pagina):
    """O alvo do primeiro contador da página (a largada da Winter), ou None."""
    alvo = next((b.get("alvo") for b in pagina.get("blocos", ()) if b.get("tipo") == "contador"), None)
    try:
        largada = datetime.fromisoformat(alvo) if alvo else None
    except ValueError:
        return None
    return largada if largada and largada.tzinfo else None       # sem fuso não se sabe quando é: sem rótulo


def _dias_para_a_largada(pagina):
    """O "78 days to lights out" do urace.us (lá, um script conta): aqui, os dias inteiros até o contador da Winter,
    contados a cada página servida. Sem contador na página, sem rótulo."""
    largada = _largada(pagina)
    if not largada:
        return None
    dias = max(0, int((largada - _agora()).total_seconds() // 86400))
    return f"{dias} day{'' if dias == 1 else 's'} to lights out"


def _escolha(host, ctx):
    winter = blocos.registro().get(WINTER)
    itens = []
    for c in ESCOLHA["itens"]:
        if c["link"][1] == WINTER:
            if not winter:
                continue                 # a página da Winter (#505) ainda não existe: o cartão não leva a um 404
            rotulo = _dias_para_a_largada(winter)
            c = {**c, "rotulo": rotulo} if rotulo else c
        itens.append(c)
    return blocos.DESENHO["cartoes"]({**ESCOLHA, "itens": itens}, ctx["indice"], host, ctx)


# ------------------------------------------------------------------ a home (urace.us/, "home-new" de 29/10)
HOME = {
    "caminho": "/", "nome": "Home",
    "titulo": "URACE | Professional Racing Team, Kart Academy & Sim2Grid",
    # a de lá termina em "4.9 on Google." — a nota não se escreve à mão
    "descricao": ("Professional kart racing team in Orlando. From your first session to national grids: Arrive and Drive, "
                  "driver training, URACE Academy and Sim2Grid."),
    "foto": BANDEIRADA,
    # #252: quem é a URACE (Organization) e qual é o site (WebSite), como o Yoast publica
    "schemas": (lambda host: _marca(host)[0], lambda host: _marca(host)[1]),
    "blocos": [
        {"tipo": "hero", "eyebrow": "URACE · Orlando, Florida", "h1": "The Champions Factory",
         "sub": ("We are a race team in Orlando that runs its own drivers, simulator to grid. We don’t sell seat time. We "
                 "find where your tenths are, show you the trace, and tell you straight whether the next step is worth "
                 "your money."),
         "ctas": [("Join the race team", "/professional-kart-team-racing-team/"), ("Start driving with us", AD_EXPERIENCIA)],
         "foto": BANDEIRADA, "alt": "URACE driver Frankie Iadevaia takes the checkered flag at FLKC Jacksonville",
         "nota": "**P1** Frankie Iadevaia · FLKC Rounds 7 & 8 · Jacksonville · October 2026"},
        {"tipo": "figuras", "eyebrow": "This season", "titulo": "On the top step", "fundo": "clara",
         "ancora": "top-step", "itens": TOPO},
        {"tipo": "funcao", "render": _escolha, "dados": ESCOLHA},
        {"tipo": "cartoes", "eyebrow": "Choose your level", "titulo": "Where are you on track?", "itens": [
            {"titulo": "First time in a kart",
             "texto": "Arrive and Drive with a dedicated coach. We teach fundamentals with real data from session one.",
             "link": ("Book Arrive and Drive", AD_RESERVA)},
            {"titulo": "Already racing",
             "texto": ("Evaluation session, your data compared to our reference lap, and a training plan built from your "
                       "level."),
             "link": ("Book an evaluation", "/kart-training-packages/")},
            {"titulo": "Competing regionally or nationally",
             "texto": "Full race-team program: setup, engines, data, race-weekend coaching and trackside support.",
             "link": ("Talk to the team", "/professional-kart-team-racing-team/")}]},
        {"tipo": "numeros", "eyebrow": "The method", "titulo": "Built around your level, not a template.",
         "intro": ("First-season driver or national-level racer, the program starts where you are. Day one we pull your "
                   "data, compare it to a reference lap, and build the plan from there. Beginners get fundamentals. "
                   "Experienced drivers get setup work, telemetry overlays, racecraft and race-weekend support. Same "
                   "standard, different plan."),
         "itens": [("300+", "Drivers trained by Italo and URACE"), ("500+", "Race wins by drivers trained by Italo and URACE")]},
        {"tipo": "figuras", "eyebrow": "Our drivers", "titulo": "Built by URACE", "fundo": "clara", "ancora": "drivers",
         "itens": [
             {"foto": JACKSONVILLE, "alt": "Frankie Iadevaia", "titulo": "Frankie Iadevaia",
              "legenda": "**P1** · FLKC Rounds 7 & 8, Jacksonville · Oct 2026"},
             {"foto": "leonardo-1.webp", "alt": "Leonardo Escorpioni", "titulo": "Leonardo Escorpioni",
              "legenda": "Multi national race winner · now racing USF200 Pro"},
             {"foto": "enzo-1.webp", "alt": "Enzo Vidmontiene", "titulo": "Enzo Vidmontiene",
              "legenda": "Multi national race winner"},
             {"foto": "emmo-2.webp", "alt": "Emmo Fittipaldi", "titulo": "Emmo Fittipaldi", "legenda": "Now racing Eurocup3"}]},
        {"tipo": "cartoes", "eyebrow": "The ladder", "titulo": "Four steps. One team.", "ancora": "the-ladder",
         "intro": ("Nobody skips to the top and nobody buys their way in. Your coach tells you when you are ready. Already "
                   "racing? You enter at the step your data says you belong in."),
         "itens": [
             {"foto": SIM2GRID_KV, "alt": "", "rotulo": "Step 1", "titulo": "Sim2Grid",
              "texto": ("VR motion simulator. Learn the lines, the braking points and the habits before you ever sit in a "
                        "kart.", SIM_ABRE),
              "link": ("See Sim2Grid", "/sim2grid-racing-simulator/")},
             {"foto": PRIMEIRA_CURVA, "alt": "", "rotulo": "Step 2", "titulo": "Arrive and Drive",
              "texto": ("A real race kart and a dedicated pro coach. Telemetry, onboard review and precise corrections from "
                        "session one.", "Track admission is paid separately to Orlando Kart Center."),
              "preco": "kart", "link": ("Book Arrive and Drive", AD_RESERVA)},
             {"foto": ACADEMY_FOTO, "alt": "", "rotulo": "Step 3", "titulo": "URACE Academy",
              "texto": ("Monthly training with data analysis, onboard video study and the theory behind every correction. "
                        "You don’t just do it, you know why."),
              "link": ("See the Academy", "/academy/")},
             {"foto": BANDEIRADA, "alt": "", "rotulo": "Step 4", "titulo": "URACE Racing Team",
              "texto": ("Full race-team program for regional, national and international grids: chassis and engine setup, "
                        "data and video after every run, race-weekend coaching and trackside support."),
              "link": ("Talk to the team", "/professional-kart-team-racing-team/")}],
         "ctas": [("Plan your career, from here to F1, IndyCar or NASCAR", "/career/")]},
        # lá, esta faixa tem também três vídeos (mp4 do WordPress), que a política do site não toca
        {"tipo": "depoimentos", "titulo": "Straight from the paddock", "ancora": "reviews", "itens": [*AVALIACOES, AARON],
         "link": ("Read them all on Google", GOOGLE)},
        {"tipo": "videos", "eyebrow": "URACE Shorts", "titulo": "Onboard: watch the method", "itens": [
            ("URACE Karting Team Orlando", "https://www.youtube.com/watch?v=44IvXhh2T9o"),
            ("Watch Lando’s story", "https://www.youtube.com/watch?v=piaonkkc-yQ"),
            ("From karting to Formula 1", "https://www.youtube.com/watch?v=xMwAP1xlruc"),
            ("What it takes to develop a driver", "https://www.youtube.com/watch?v=TlLKzFPvI5g"),
            ("Professional kart racing team", "https://www.youtube.com/watch?v=NvDTpl4BT_0"),
            ("2026: your year to accelerate", "https://www.youtube.com/watch?v=gvrIxUxVRDU")]},
        {"tipo": "texto", "eyebrow": "About", "titulo": "I’ve raced. I’ve won. I know the way.", "ancora": "about",
         "paragrafos": ["Racing has been our passion for generations. Our kart racing story started 26+ years ago in Brazil. "
                        "Team principal Italo Silveira began by racing karts, winning numerous Brazilian regional and "
                        "national championships. A professional car racing career followed in the Brazilian stock car "
                        "series. In 2016, Italo moved to Florida and launched URACE, a karting team, to pass along his "
                        "knowledge and passion to young drivers."],
         "ctas": [("More about URACE", "/about/")], "foto": ITALO, "alt": "Italo da Silveira, URACE team principal"},
        {"tipo": "posts", "eyebrow": "From the paddock", "titulo": "Read before you race", "n": 3},
        {"tipo": "texto", "eyebrow": "Group events", "titulo": "Group events",
         "paragrafos": ["Real race karts on a real circuit, run like a race weekend: practice, grid order, timed final, "
                        "results on a sheet at the end. For corporate teams, birthdays and groups."],
         "ctas": [("Birthdays", "/services/birthday-party/"), ("Corporate events", "/services/corporate-events/"),
                  ("Social gatherings", "/services/group-events/")]},
        {"tipo": "cta", "titulo": "Box, box. Let’s talk.",
         "texto": "Tell us who the driver is and where they race today. We tell you straight which step is next.",
         "ctas": [("Book a call", CONVERSA_HOME), ("Get in touch", "/contact/")]},
    ],
}

# ------------------------------------------------------------------ About (urace.us/about/, reescrita em 29/10)
ABOUT = {
    "caminho": "/about/", "nome": "About", "trilha": (("About", "/about/"),),
    "titulo": "About URACE - Professional Racing Team in Orlando",
    "descricao": ("URACE is a professional racing team in Orlando with a career path to F1, NASCAR, IMSA and IndyCar, "
                  "starting with URACE Academy and URACE Sim2Grid."),
    "foto": ITALO,
    "blocos": [
        {"tipo": "hero", "eyebrow": "About URACE · Since 2016 in Orlando", "h1": "I’ve raced. I’ve won. I know the way.",
         "sub": ("Racing has been our passion for generations. Our kart racing story started 26+ years ago in Brazil. Team "
                 "principal Italo da Silveira raced karts, won Brazilian regional and national championships and went on "
                 "to a professional career in the Brazilian stock car series. In 2016 he moved to Florida and launched "
                 "URACE to pass that knowledge on to young drivers."),
         "ctas": [("Meet the Racing Team", "/professional-kart-team-racing-team/"), ("Talk to us", LIGACAO)],
         "foto": ITALO, "alt": "Italo da Silveira, URACE founder and team principal"},
        # a de lá tem um quarto número, "4.9 · On Google, 38 reviews": a nota não se escreve à mão
        {"tipo": "numeros", "eyebrow": "The method", "titulo": "Same standard. Different plan.",
         "intro": ("Day one we pull your data, compare it to a reference lap, and build the plan from there. Beginners get "
                   "fundamentals. Experienced drivers get setup work, telemetry overlays, racecraft and race-weekend "
                   "support."),
         "itens": [("300+", "Drivers trained by Italo and URACE"), ("500+", "Race wins by drivers trained by Italo and URACE"),
                   ("4", "Steps, one team: Sim2Grid, Arrive and Drive, Academy, Racing Team")]},
        {"tipo": "figuras", "eyebrow": "This season", "titulo": "On the top step", "fundo": "clara",
         "ancora": "top-step", "itens": TOPO},
        {"tipo": "depoimentos", "eyebrow": "Google reviews", "ancora": "reviews", "itens": list(AVALIACOES),
         "link": ("Read them all on Google", GOOGLE)},
        {"tipo": "cartoes", "eyebrow": "Where to start", "titulo": "Find your step", "ancora": "find-your-step",
         "intro": "Four steps, one team. Your coach tells you when you are ready for the next one.",
         "itens": [
             {"titulo": "Sim2Grid", "texto": ("VR motion simulator. Lines, braking points and habits before the kart.", SIM_ABRE),
              "preco": "sim2grid", "link": ("See Sim2Grid", "/sim2grid-racing-simulator/")},
             {"titulo": "URACE Academy",
              "texto": "Four coached sessions a month, kart and equipment included. Month to month.",
              "preco": "academy", "link": ("See the Academy", "/academy/")},
             {"titulo": "URACE Racing Team", "texto": "Race-team program for regional, national and international grids.",
              "link": ("Talk to the team", "/professional-kart-team-racing-team/")}]},
    ],
}

# ------------------------------------------------------------------ Programs (urace.us/services/, título de 29/10)
PROGRAMAS = (("Sim2Grid", "/sim2grid-racing-simulator/"), ("Arrive and Drive", "/services/arrive-and-drive/"),
             ("URACE Academy", "/academy/"), ("URACE Racing Team", "/pro-team/"),
             ("Birthday Party", "/services/birthday-party/"), ("Corporate Events", "/services/corporate-events/"))


def _lista_de_programas(host):
    return {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [
        {"@type": "ListItem", "position": n, "name": nome, "url": f"https://{host}{c}"}
        for n, (nome, c) in enumerate(PROGRAMAS, 1)]}


PROGRAMS = {
    "caminho": "/services/", "nome": "Programs", "trilha": (("Programs", "/services/"),),
    "titulo": "Programs: URACE Academy, Sim2Grid & Racing Team | Orlando",
    "descricao": ("Every URACE program in Orlando: Sim2Grid racing school on simulators, URACE Academy kart school, "
                  "coaching and the race team. Learn on our equipment."),
    "foto": SIM2GRID_KV,
    "schemas": (_lista_de_programas,),
    "blocos": [
        {"tipo": "hero", "eyebrow": "Driver Development · Orlando, FL",
         "h1": "Kart racing in Orlando — from the simulator to the grid",
         "sub": ("URACE Racing Team develops its own drivers. Everyone on our grid started on one of the four steps below — "
                 "find the one you are on today, and we will tell you straight which it is.")},
        # Sim 2 Grid
        {"tipo": "texto", "ancora": "sim-2-grid", "eyebrow": "Opening 1 November 2026", "titulo": "Sim 2 Grid",
         "paragrafos": ["Most people’s idea of a racing simulator is a game. This is not that. It is a full motion cockpit — "
                        "competition seat and harness, direct-drive wheel, racing pedals, triple screen. It moves. It loads "
                        "you up in the corners and punishes the same mistakes a real car does, and our own drivers learn a "
                        "circuit on it before they ever see it. No track fee, no equipment, no weather. That makes it the "
                        "cheapest honest way to find out whether this is a hobby or a career — and it is the first rung of "
                        "the ladder that leads to Arrive and Drive, the URACE Academy and the URACE Racing Team. The rig "
                        "opens on **1 November 2026**."],
         "ctas": [("Book your sim session", "/sim2grid-racing-simulator/")], "foto": SIM2GRID_KV, "alt": "URACE Sim2Grid"},
        {"tipo": "faq", "ancora": "sim-2-grid-details", "itens": [
            ("How will this work?", ("Tell us the driver’s level — never driven, drives a kart, races on weekends. It changes "
                                     "the car, the circuit and the assists we set up.",
                                     "From 1 November, book your hour. Give us a date and a time.",
                                     "Turn up. Nothing to bring: no helmet, no suit, no licence, no track fee.")),
            ("What you are actually buying", ("The rig is not what you are buying. You are buying the first step. This is "
                                              "where a career will start — not a toy and not an arcade, but the bottom rung "
                                              "of the same ladder that runs through Arrive and Drive and the URACE Academy "
                                              "to the Racing Team.",
                                              "A kart day depends on the circuit’s hours, the forecast and a driver pass. "
                                              "This step depends on nothing but you showing up."))]},
        # "What it will cost": os programas do Sim2Grid com o preço do painel (o de lá não bate com o painel)
        {"tipo": "cartoes_painel", "pagina": "sim2grid", "eyebrow": "What it will cost", "ancora": "sim-2-grid-cost"},
        # Arrive and Drive
        {"tipo": "texto", "ancora": "driving-experience", "titulo": "Arrive and Drive",
         "paragrafos": ["Are you visiting Orlando and looking for something more exciting than the go karts at Magic "
                        "Kingdom's Tomorrowland Speedway or the monotony of Epcot's Test Track? Drive one of our 70 MPH racing "
                        "karts at Orlando Kart Center. The 8/10 mile professional kart racing track. Located just off the "
                        "Florida Turnpike and near the Central Florida Pkwy. We are just minutes from most of Orlando's main "
                        "attractions. This experience is for kids and adults, all ages are welcome! And for drivers who "
                        "catch the racing bug, it's more than a fun afternoon — it's lap one of a real path: Arrive and Drive "
                        "is the first rung of the ladder that leads to URACE Academy and, eventually, the URACE Racing Team."],
         "ctas": [("Join URACE", "/kart-lessons-for-beginners/")], "foto": "group-482140-1.webp", "alt": "Arrive and Drive"},
        {"tipo": "faq", "ancora": "driving-experience-details", "itens": [
            ("The experience", ("Are you visiting Orlando and looking for something more exciting than the go karts at Magic "
                                "Kingdom's Tomorrowland Speedway or the monotony of Epcot's Test Track?",
                                "Drive one of our 70 MPH racing go-karts at Orlando Kart Center. The 8/10 mile professional "
                                "kart racing track. Located just off the Florida Turnpike and near the Central Florida Pkwy. "
                                "We are just minutes from most of Orlando's main attractions.",
                                "This experience is for kids and adults, all ages are welcome!",
                                "Book your reservation and be ready to have a blast!",
                                "These are not the typical put-put go-karts, they are authentic, professional racing karts.",
                                "We will start by providing safety and driving technique instructions, after the first "
                                "instructions you will have 3 or 6 10 minutes driving sessions, according to your choice. The "
                                "experience total time, will be around 2h for 3 sessions and 4-5 h for 6 sessions from "
                                "arrival until the end.",
                                "What URACE Provides:", "- The high performance go-kart", "- Safety instructions",
                                "- Safety equipment.",
                                "What YOU Need to Bring:", "1. MUST wear long pants, closed toe shoes and a jacket.",
                                "2. Make a reservation", "3. Come prepared for fun and leave with lasting smiles.",
                                "→ Available Experience Days : Experiences are available every day, 8 AM – 8 PM. Please "
                                "confirm availability when booking.")),
            ("The track", (TRACK,))]},
        # URACE Academy
        {"tipo": "texto", "ancora": "urace-academy", "titulo": "URACE Academy", "fundo": "escura",
         "paragrafos": ["Embark on a comprehensive racing education with URACE Academy, our kart school, designed "
                        "specifically for novice drivers eager to excel. Our structured program combines theoretical "
                        "knowledge with hands-on training, equipping students with the skills and confidence to succeed. "
                        "Beyond the driving itself, every Academy driver gets a career specialist who helps plan the path "
                        "forward — from which categories and tracks make sense next, to how the Racing Team and competitive "
                        "racing fit into the picture."],
         "ctas": [("Join URACE", "/kart-training-packages/"), ("Talk to Our Career Specialist", LIGACAO)],
         "foto": "group-482139-1.webp", "alt": "URACE Academy"},
        {"tipo": "faq", "ancora": "urace-academy-details", "fundo": "escura", "itens": [
            ("Why motorsport builds champions", (
                "Karting looks like a hobby from the outside, but the skills it demands behind the wheel are the ones "
                "researchers tie to healthy child development. A young driver is constantly reading the track, adjusting "
                "their line, and making split-second calls under pressure — fast, consequence-driven decision-making that's "
                "hard to practice anywhere else.",
                "The research on youth sport backs this up. A large study published in PLOS One found sport's overall "
                "impact on child development is strongly positive, including gains in self-esteem and communication. A "
                "separate study comparing competitive athletes to recreational and instructional-level peers found the "
                "competitive group scored significantly higher on cognitive skills and goal-setting. And researchers who "
                "study youth sport broadly — including work out of Texas A&M — point to competition itself as a key driver "
                "of resilience: learning to lose a race, work out what went wrong, and come back faster teaches persistence "
                "in a way few other childhood activities do.",
                "At URACE Academy, every session is built around that exact process. Coaches don't just teach a driving "
                "line — they walk each driver through onboard video and lap-time data, then set a specific target for the "
                "next session. It's the same cycle of goal-setting, performance, and reflection the research points to, just "
                "happening at 50 mph.",
                "We're not claiming karting replaces coaching, school, or therapy. But for a sport that asks a 7-year-old to "
                "process more information per second than almost any other youth activity, it's hard to find a better "
                "training ground for focus, composure under pressure, and the discipline to keep improving.")),
            ("Your path: Arrive and Drive → Academy → Racing Team", (
                "URACE Academy isn't a standalone class — it's the middle rung of a ladder. Drivers usually start at Arrive "
                "and Drive, where they get their first real laps and we get our first read on their potential. Academy is "
                "where that potential becomes a plan: four sessions a month of structured coaching, video and data review, "
                "and a career specialist tracking progress alongside the driving.",
                "From there, Academy drivers who are ready move up to the URACE Racing Team — our motorsport hub, where they "
                "compete under the URACE banner on the path toward the main leagues of the sport.",
                "We're also building a racing simulator program, launching soon, to give Academy and Racing Team drivers "
                "extra seat time between track days without the cost of extra track sessions.",
                f"Not sure where your driver fits on that path? [Talk to Our Career Specialist]({LIGACAO}) and we'll map it "
                "out with you.")),
            ("Career planning, specialists & add-on services", (
                "Every Academy family works with a career specialist, not just a coach. That means real planning behind the "
                "driving, not only laps:",
                "- Career path analysis: our specialists assess the driver's progress and lay out realistic next steps, "
                "categories, and timelines.",
                "- Track planning: deciding which tracks and race weekends make sense for where the driver is right now.",
                "- Logistics planning: coordinating travel, scheduling, and race-weekend logistics around school and family "
                "life.",
                "- Cost-efficiency planning: budgeting the season so spending matches the driver's actual stage and goals, "
                "not guesswork.",
                "- Brand & sponsorship association: once a driver is competitive, we help shape their story and connect it "
                "with potential sponsors and brand partners.",
                "- On-track team: the same mechanic who preps the equipment and the coach who reviews the laps, working "
                "together on every session.",
                "Available as paid add-ons, negotiated separately once a driver is ready for them:",
                "- Press & PR advisory for the driver and family.",
                "- Video content production for the driver's own highlight reels and sponsor material.")),
            ("Package includes", (
                "- Kart: High-performance kart provided for each session.",
                "- Coach: Expert coaching from professional instructors.",
                "- Mechanic: On-site mechanical support to keep the kart race-ready.",
                "- Career planning: Ongoing guidance from your career specialist.",
                "- In-depth safety instructions.",
                "- Driver Pass: Access to the track for the driver.",
                "- 1 Guest Pass: Bring one guest (family or friend) to accompany and support you (Additional guests subject "
                "to track pass price)."))]},
        # Racing Team (o parágrafo de lá começa com o texto do Professional Coaching, que virou o Arrive and Drive — #254)
        {"tipo": "texto", "ancora": "racing-team", "titulo": "Racing Team",
         "paragrafos": ["The Racing Team is also URACE's motorsport hub — it's where Academy drivers who are ready take the "
                        "next step, competing under the URACE banner and working toward the leagues that lead to "
                        "professional racing."],
         "ctas": [("Join URACE", "/professional-kart-team-racing-team/")], "foto": BANDEIRADA, "alt": "URACE Racing Team"},
        # Birthday party / Corporate Events
        {"tipo": "texto", "ancora": "birthday-party-corporate-events", "titulo": "Birthday party / Corporate Events",
         "fundo": "escura", "paragrafos": [GRUPOS], "ctas": [("Request a quote", "/contact/")],
         "foto": "group-482140-2.webp", "alt": "Birthday party / Corporate Events"},
        {"tipo": "cta", "ancora": "book-a-call", "titulo": "Not sure which one is right?", "fundo": "clara",
         "texto": ("Tell us who the driver is and whether they have been in a race kart before. That one answer decides "
                   "everything else — and we will tell you honestly which of these is your starting point, even if it is "
                   "the cheapest one."),
         "ctas": [("Book a 15-min call", LIGACAO)]},
        {"tipo": "cta", "titulo": FECHO_DUVIDAS[0], "texto": FECHO_DUVIDAS[1], "ctas": [("Get in touch", "/contact/")]},
    ],
}

PAGINAS = (HOME, ABOUT, PROGRAMS)
