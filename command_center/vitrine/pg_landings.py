"""As landings do urace.us no site novo (#506), montadas por blocos (#502).

Dono, 29/10: *"sim, pode trazer o texto"*. A home nova do urace.us e as campanhas levam a estas páginas; na troca do
domínio elas não podem quebrar. O texto é o da página de hoje (lida em 29/10), no desenho do site novo:

- as quatro de anúncio, reescritas em 29/10 e no Google: `/kart-lessons-for-beginners/`, `/kart-driving-school/`,
  `/kart-training-packages/` e `/professional-kart-team-racing-team/` (antes eram 301 para For Beginners, Academy e
  Pro Team);
- as três do Arrive & Drive, publicadas em 27/10 fora do Google: a de interesse (formulário), a de reserva e o obrigado;
- a The Driver Factory (16/10), de novo página própria (era 301 para o /career/), com o obrigado dela.

O que não é cópia literal, de propósito:
- **Preço por chave, nunca escrito.** O "from $719" do Arrive and Drive é a chave `kart` (painel); a Academy, o Boost
  e o Sim2Grid são as chaves `academy`, `boost` e `sim2grid` e, no texto, as marcas `{academy}`, `{boost_sessao}`…
  (#525, dono 30/10: *"usa os valores do urace us"*, `conteudo.PRECOS`). O security deposit sai sem o número.
- **O URACE Boost voltou** (#525, dono 30/10: *"sim volta"*): o "Three ways in" das landings da Academy e do Racing
  Team tem os três cartões do urace.us.
- **A reserva é a do site** (dono, 15/10, #262: um caminho só para reservar): a agenda da página de reserva do urace.us
  (kart, dia, Lead and Follow, checkout do WooCommerce) vira o botão para `/services/arrive-and-drive/#reservar`.
- **O nome é URACE** (o urace.us escreve "URace" nas páginas do Arrive & Drive); citação de avaliação fica como está.
- O número e a nota das avaliações do Google não se escrevem à mão (ficam velhos): fica o link para o Google.
- O formulário visível nas quatro de anúncio e na Driver Factory é um formulário do Kommo (carregado por script); os
  campos são os do "Form LP URace" da própria página (o mesmo título e o mesmo aviso). O do Arrive & Drive é o do
  plugin da página, que leva ao obrigado — aqui também (a campanha conta a conversão pela URL).
"""
from html import escape

from command_center.vitrine import conteudo as C
from command_center.vitrine import conteudo_paginas as P

RESERVAR = "/services/arrive-and-drive/#reservar"          # agenda + carrinho + Stripe, com o preço do painel
CONVERSA = C.LIGACAO                                        # o "Talk to us" do urace.us: a agenda de 15 min com a equipe
FUNDADOR = "https://www.youtube.com/watch?v=KQPMDLgVW3s"    # "A message from our founder" (o site não embute vídeo)
TELEFONE, TEL = "+1 (407) 250-2291", "tel:+14072502291"
OBRIGADO_AD = "/arrive-and-drive-karting-thank-you/"
OBRIGADO_DF = "/the-driver-factory-thank-you-page/"


# ------------------------------------------------------------------ as quatro de anúncio (o mesmo molde)
# o asterisco do "from $719*" do botão; o valor do depósito ($400) é do painel e sai do texto
LETRA_MIUDA = ("Taxes and fees not included. A refundable security deposit is added at checkout and returned within 5 "
               "business days after your session if there is no damage to the kart. Track admission is not included: "
               "driver and guest passes are paid separately to Orlando Kart Center. Rescheduling: requests made at least "
               "48 hours before your session will be accommodated based on availability. Sessions missed without notice "
               "may be forfeited.")


def _o_que_vem(reservar):
    """"What you get" e, embaixo, o preço do painel com a letra miúda dele (no urace.us o preço ia no botão do topo)."""
    return [
        {"tipo": "cartoes", "eyebrow": "What you get", "titulo": "One session. A real start.", "itens": [
            {"titulo": "Real race kart", "texto": "Chosen to fit the driver: age, size and experience."},
            {"titulo": "Dedicated pro coach", "texto": "One coach on your driver, start to finish."},
            {"titulo": "Telemetry and onboard", "texto": "Data pulled after every run, onboard reviewed corner by corner."},
            {"titulo": "Corrections that stick", "texto": "The two things costing time, not twenty."}]},
        {"tipo": "cartoes", "rotulo_secao": "Arrive and Drive", "itens": [
            {"titulo": "Arrive and Drive", "texto": LETRA_MIUDA, "preco": "kart"}],
         "ctas": [(reservar, RESERVAR)]},
    ]


def _fundador(proximo, fundo="escura"):
    """O vídeo do fundador vira link (a política do site não deixa embutir o YouTube)."""
    return {"tipo": "texto", "fundo": fundo, "eyebrow": "A message from our founder",
            "titulo": "The right guidance can change a driver's journey",
            "paragrafos": [f"[Watch on YouTube]({FUNDADOR})"], "ctas": [("Find my next step", proximo)]}


def _hora(h):
    """ "09:00" → "9am", "13:30" → "1:30pm" (como o urace.us escreve: "from 7am to 1pm")."""
    hh, mm = (int(x) for x in h.split(":"))
    return f"{(hh - 1) % 12 + 1}{f':{mm:02d}' if mm else ''}{'am' if hh < 12 else 'pm'}"


DIAS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def horario_da_pista(agenda):
    """#527: os dias e os horários de sessão na pista, da agenda do painel (Site › Agenda), que é quem manda (dono, 30/10:
    *"deixe que isso é regulado pelo command center"*). Ex.: "Wednesday 9am–1pm or 1pm–5pm; Saturday and Sunday 9am–1pm".
    Sem agenda (banco fora) ou sem nada aberto, devolve ""."""
    if not agenda:
        return ""
    c = agenda["config"]
    faixa = {"manha": f'{_hora(c["morning_start"])}–{_hora(c["morning_end"])}',
             "tarde": f'{_hora(c["afternoon_start"])}–{_hora(c["afternoon_end"])}'}
    por_dia = {}
    for r in agenda["semana"]:
        if r["open"]:
            por_dia.setdefault(r["weekday"], []).append(r["period"])
    grupos = []                                         # dias seguidos com os mesmos períodos vão juntos
    for d in sorted(por_dia):
        ps = tuple(p for p in ("manha", "tarde") if p in por_dia[d])
        if grupos and grupos[-1][1] == ps:
            grupos[-1][0].append(d)
        else:
            grupos.append(([d], ps))
    def dias(ds):
        nomes = [DIAS[d] for d in ds]
        return nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " and " + nomes[-1]
    return "; ".join(f'{dias(ds)} {" or ".join(faixa[p] for p in ps)}' for ds, ps in grupos)


def _campos_lp(ctx=None):
    """Os campos do "Form LP URace" (o formulário da página no urace.us). O horário da pista da opção A sai da agenda
    do painel (#527); os preços, das chaves (#525: o kart do painel, a Academy e o Boost do urace.us)."""
    from command_center.vitrine.blocos import valor
    def radio(nome, valor):
        v = escape(valor, quote=True)
        return f'<label class="opcao"><input type="radio" name="{nome}" value="{v}" required> <span>{v}</span></label>'
    agenda = (ctx or {}).get("agenda")
    pista = horario_da_pista(agenda() if callable(agenda) else agenda)
    opcoes = ("A - I only want to try it and see if it is for me without commitment to continue"
              f" ({valor('kart')}/day" + (f" - track sessions: {pista})" if pista else ")"),
              f"B - I am new to the sport and I want to join the Academy ({valor('academy')}/mo)",
              f"C - I already have experience and I want to join the Racing Team ({valor('boost')}/mo +)",
              "D - I don't have the budget for any of the options above (😔In another moment when you are ready we will "
              "be happy to help)")
    experiencia = ("No previous experience", "Recreational karting experience", "Karting school or training experience",
                   "Currently competing in races")
    return ('<label>Address <span class="opcional">(optional)</span><input name="x_address" autocomplete="address-level2" '
            'maxlength="120" placeholder="City, State"></label>'
            '<fieldset><legend>Pick one option below:</legend>' + "".join(radio("x_option", o) for o in opcoes) + '</fieldset>'
            '<fieldset><legend>Does The Driver Have Previous Karting Or Racing Experience?</legend>'
            + "".join(radio("x_previous_experience", o) for o in experiencia) + '</fieldset>')


def _formulario_lp(assunto, obrigado=None):
    b = {"tipo": "formulario", "ancora": "form", "titulo": "Tell us about your goals",
         "texto": ("Our team will review your information and contact you to understand which URACE experience or "
                   "development program best matches your current stage."),
         "assunto": assunto, "extras": _campos_lp, "enviar": "Send",
         "nota": "By submitting this form, you agree to be contacted by the URACE team regarding your inquiry."}
    if obrigado:
        b["obrigado"] = obrigado
    return b


# duas fotos lado a lado: em cartões (as `figuras` são para galeria — com duas, ficam estreitas no computador)
TEMPORADA = {"tipo": "cartoes", "eyebrow": "This season", "titulo": "On the top step",       # #521: conteudo.RESULTADOS
             "itens": [{"foto": f, "alt": a, "titulo": t, "texto": x} for f, a, t, x in C.RESULTADOS]}

# as três avaliações do Google do urace.us (as mesmas do resto do site); a nota e o número de avaliações não se escrevem
# à mão (ficam velhos): fica o link para o Google
AVALIACOES = {"tipo": "depoimentos", "eyebrow": "Google reviews", "rotulo_secao": "Google reviews", "itens": C.AVALIACOES,
              "link": ("Read them all on Google", C.GOOGLE)}

# #525: o Sim2Grid e a Academy com o preço do urace.us (as chaves `sim2grid` e `academy`)
ESCADA = {"tipo": "cartoes", "eyebrow": "Your next step", "titulo": "The ladder keeps going",
          "intro": "Four steps, one team. Your coach tells you when you are ready for the next one.", "itens": [
              {"rotulo": "Opens 1 Nov 2026", "titulo": "Sim2Grid",
               "texto": "VR motion simulator. Lines, braking points and habits before the kart.", "preco": "sim2grid",
               "link": ("See Sim2Grid", "/sim2grid-racing-simulator/")},
              {"titulo": "URACE Academy", "texto": "Four coached sessions a month, kart and equipment included. Month to month.",
               "preco": "academy", "link": ("See the Academy", "/academy/")},
              {"titulo": "URACE Racing Team", "texto": "Race-team program for regional, national and international grids.",
               "link": ("Talk to the team", "/professional-kart-team-racing-team/")}]}

# #525: os três cartões do urace.us de 29/10, com a Academy e o Boost pela chave de preço
CAMINHOS = {"tipo": "cartoes", "eyebrow": "How we work with competitive drivers",
            "titulo": "Three ways in, depending on where you are", "itens": [
                {"titulo": "URACE Academy",
                 "texto": ("Not racing yet? Start here. Four coached sessions a month with kart, full equipment, "
                           "maintenance and a professional coach included. Month to month, no minimum term."),
                 "preco": "academy", "link": ("Join URACE Academy", "/academy/")},
                {"titulo": "URACE Boost",
                 "texto": ("Eight sessions in 30 days. A standalone intensive month for drivers preparing for a race or a "
                           "season, at {boost_sessao} a session, our lowest per-session rate. No contract."),
                 "preco": "boost", "link": ("Talk to our racing team", CONVERSA)},
                {"titulo": "Race Weekend Support",
                 "texto": ("We run the kart. You drive. Kart preparation and trackside support at the rounds we are "
                           "entered in. Entries, tyres, fuel and consumables are quoted per event.",
                           "**Let’s talk** · per event"),
                 "link": ("Talk to our racing team", CONVERSA)}]}

BEGINNERS = {
    "caminho": "/kart-lessons-for-beginners/", "nome": "Kart Lessons for Beginners",
    "titulo": "Kart Lessons for Beginners in Orlando | URACE",
    "descricao": ("First time in a race kart? URACE coaches beginners at Orlando Kart Center, with professional coaching "
                  "and a clear path from first laps to racing."),
    "foto": "arrive-and-drive-first-corner.webp",
    "blocos": [
        {"tipo": "hero", "eyebrow": "Step 2 · Arrive and Drive · Orlando", "h1": "Your first real race kart. With a pro coach.",
         "sub": ("For all ages and experience levels. Choose the kart that fits your driver, tell us about them, and we "
                 "tailor the session from there: a first time on track or a warm-up between Academy sessions."),
         "ctas": [("Book Arrive and Drive", RESERVAR), ("Talk to us", CONVERSA)],
         "foto": "arrive-and-drive-first-corner.webp", "alt": "URACE on track"},
        *_o_que_vem("Book Arrive and Drive"),
        _fundador(CONVERSA),
        _formulario_lp("arrive-and-drive"),
        TEMPORADA, AVALIACOES, ESCADA,
    ],
}

DRIVING_SCHOOL = {
    "caminho": "/kart-driving-school/", "nome": "Kart Driving School",
    "titulo": "Kart Driving Lessons in Orlando, FL | URACE Academy",
    "descricao": ("Looking for a kart driving school in Orlando? The URACE Academy at Orlando Kart Center gives "
                  "professional coaching, from first laps to competitive racing."),
    "foto": "arrive-and-drive-first-corner.webp",
    "blocos": [
        {"tipo": "hero", "eyebrow": "Kart driving school · Orlando, Florida", "h1": "Kart driving school. Real karts, real coaching.",
         "sub": ("Learn to drive a race kart the right way: a dedicated pro coach, telemetry and onboard review from your "
                 "first session at Orlando Kart Center. Kids and adults."),
         "ctas": [("Book a session", RESERVAR), ("Talk to us", CONVERSA)],
         "foto": "arrive-and-drive-first-corner.webp", "alt": "URACE on track"},
        *_o_que_vem("Book a session"),
        _fundador(CONVERSA),
        _formulario_lp("arrive-and-drive"),
        TEMPORADA, AVALIACOES, ESCADA,
    ],
}

TRAINING_PACKAGES = {
    "caminho": "/kart-training-packages/", "nome": "Kart Training Packages",
    "titulo": "Kart Training Packages: Monthly URACE Academy in Orlando",
    "descricao": ("Four coached sessions a month for drivers past their first day. We bring the kart, full equipment, "
                  "maintenance and a professional coach. Orlando, FL."),
    "foto": "img-7762-scaled.webp",
    "blocos": [
        {"tipo": "hero", "eyebrow": "Kart training packages · Orlando",
         "h1": "Four coached sessions a month. One driver getting faster.",
         "sub": ("Structured driver development with professional coaching, track time, evaluation and mentorship. "
                 "Month to month, no long-term contract."),
         "ctas": [("Join URACE Academy", "/academy/"), ("Talk to us", CONVERSA)],
         "foto": "img-7762-scaled.webp", "alt": "URACE on track"},
        CAMINHOS,
        _fundador(CONVERSA),
        _formulario_lp("academy"),
        TEMPORADA, AVALIACOES,
    ],
}

# as próximas provas: a mesma lista do /pro-team/ (#521), com o "Race the winter →" da /winter/
CALENDARIO = {"eyebrow": P.PRO_TEAM["calendario_rotulo"], "titulo": P.PRO_TEAM["calendario_titulo"],
              "intro": P.PRO_TEAM["calendario_sub"], "itens": P.PRO_TEAM["calendario"]}


def _proximas_provas(host, ctx, hoje=None):
    """O calendário (o bloco `definicoes`) só com a prova que ainda vem, no dia da Flórida — a regra do /pro-team/
    (#508); sem nenhuma por vir, a seção não sai."""
    from command_center.vitrine import blocos, paginas_site
    provas = paginas_site._proximas(CALENDARIO["itens"], hoje)
    if not provas:
        return ""
    return blocos.DESENHO["definicoes"]({**CALENDARIO, "tipo": "definicoes", "itens": provas}, ctx["indice"], host, ctx)


RACING_TEAM = {
    "caminho": "/professional-kart-team-racing-team/", "nome": "URACE Racing Team",
    "titulo": "URACE Race Team Support with a Pro Coach | Orlando",
    "descricao": ("Already racing? URACE prepares your kart, runs the race weekend and puts a pro coach beside you, at "
                  "Orlando Kart Center and on Florida and national calendars."),
    "foto": "urace-team-bushnell-p1-p3.webp",
    "blocos": [
        {"tipo": "hero", "eyebrow": "URACE Racing Team · Orlando, Florida",
         "h1": "You already race. Now race with a team behind you.",
         "sub": ("URACE prepares the kart, runs the race weekend and puts a professional coach alongside the driver. "
                 "Based at Orlando Kart Center and entered in the Florida and national calendars."),
         "ctas": [("Talk to the team", CONVERSA), ("Join URACE Academy", "/academy/")],
         "foto": "urace-team-bushnell-p1-p3.webp",
         "alt": "URACE team with the trophy after Frankie Iadevaia's P1 in Bushnell, Florida",
         "nota": "**P1** · Frankie Iadevaia · FLKC Jacksonville · Oct 2026"},
        CAMINHOS,
        {"tipo": "funcao", "render": _proximas_provas, **CALENDARIO},
        _fundador(CONVERSA),
        _formulario_lp("team"),
        TEMPORADA, AVALIACOES,
    ],
}


# ------------------------------------------------------------------ Arrive & Drive (as três de 27/10, fora do Google)
AD_HERO = {"eyebrow": "One-day karting experience · Orlando, FL", "h1": "A day in the driver’s seat. A future to explore.",
           "sub": ("Experience real karting with professional guidance, technical support, and a team that develops racing "
                   "drivers. Your first day on track could be the start of something bigger."),
           "foto": "arrive-and-drive-lp-hero.webp", "alt": "",
           "nota": "One-day experience · Kart & gear included · Professional guidance · Technical support"}


def _historia(foto="arrive-and-drive-first-corner.webp"):
    return {"tipo": "texto", "fundo": "escura", "ancora": "story", "eyebrow": "Your first contact with motorsport",
            "titulo": "You’ve imagined the feeling. Now experience it.",
            "intro": "The ambition becomes real behind the wheel.",
            "paragrafos": ["The helmet goes on. Your hands find the wheel. The track you’ve been looking at becomes the "
                           "track you’re driving.",
                           "Spend a day discovering karting inside the world of URACE. With professional guidance and "
                           "technical support, you can focus on your first laps, learn from the experience, and explore "
                           "what being a driver feels like.",
                           "**One day to discover the feeling. A first step to discover your potential.**"],
            "ctas": [("Find out how to get started", "#support")],
            "foto": foto, "alt": "A URACE kart driver navigating a corner on track"}


def _apoio(cta):
    return {"tipo": "cartoes", "ancora": "support", "eyebrow": "The support behind your first laps",
            "titulo": "Bring your curiosity. We’ll help you get started.",
            "intro": "A one-day introduction, with no commitment to enroll in a long-term program.", "itens": [
                {"rotulo": "01 / Guidance", "titulo": "A coaching mindset.",
                 "texto": ("Get professional guidance as you discover karting. Start understanding how to approach the "
                           "track and what to work on behind the wheel.")},
                {"rotulo": "02 / Equipment", "titulo": "Your kart. Your first laps.",
                 "texto": ("A kart and gear are part of the experience. Our team will discuss the right fit and "
                           "participation requirements before your day is confirmed.")},
                {"rotulo": "03 / Team support", "titulo": "Focus on the experience.",
                 "texto": ("Discover the track with URACE’s technical support and a team involved in driver development "
                           "and competitive karting.")}],
            "ctas": [("Plan my first track day", cta)]}


def _caminho(cta):
    """"The URACE driver pathway": as três etapas (a 1ª com o preço do painel) e, depois, o que vem além do kart."""
    return [
        {"tipo": "cartoes", "fundo": "escura", "ancora": "pathway", "eyebrow": "The URACE driver pathway",
         "titulo": "Start with a day. See a bigger future.",
         "intro": ("Maybe you want an unforgettable first experience. Maybe you can already picture yourself on a racing "
                   "grid. Start by discovering the sport firsthand.",
                   "Then, if the ambition grows, explore structured training and competitive karting with URACE. The next "
                   "step depends on your goals, experience, and readiness."),
         "itens": [
             {"rotulo": "01 · Your starting line", "titulo": "Your first karting day",
              "texto": ("Experience a day behind the wheel with professional guidance and technical support. Discover the "
                        "feeling before deciding how far you want to take it.", "**One-day experience**"),
              "preco": "kart"},
             {"rotulo": "02 · Develop your foundation", "titulo": "URACE Academy",
              "texto": ("Structured training to keep developing as a driver. Talk with the team about your goals and the "
                        "commitment involved.", "**Structured driver development**")},
             {"rotulo": "03 · Grow through competition", "titulo": "URACE Racing Team",
              "texto": ("Support for drivers getting ready for competitive racing. Talk with the team about which program "
                        "could fit your stage.", "**Competitive racing support**")}],
         "ctas": [("Take my first step", cta)]},
        {"tipo": "texto", "fundo": "escura", "eyebrow": "Beyond karting", "titulo": "Dreaming of Formula 1? Understand the path.",
         "paragrafos": ["For drivers pursuing single-seater racing, future categories can include:",
                        "Formula 4 → Formula Regional → FIA Formula 3 → FIA Formula 2 → **Formula 1**",
                        "These are future aspirations beyond URACE’s programs, not included stages or guaranteed "
                        "placements. Progression depends on age, performance, licensing, funding, and available "
                        "opportunities. URACE is not affiliated with these championships."]},
    ]


# "What is included in the starting price?": o urace.us responde com "$719 per day"; o preço é o do cartão (painel)
AD_FAQ = (("Do I need karting experience?",
           "No. The one-day experience is made for first-time drivers: professional guidance and URACE technical support "
           "help you get comfortable on track. If you have driven before, tell the team when you get in touch."),
          ("What is included in the starting price?",
           "Experiences include the kart, gear, professional guidance, and URACE technical support. The track fee is "
           "charged separately."),
          ("Where does the karting experience take place?",
           "In Orlando, Florida. Your schedule and session format are confirmed with the URACE team before booking."),
          ("Am I committing to a training program?",
           "No. It is a one-day introduction, with no commitment to enroll in a long-term program. If the ambition grows, "
           "the team can talk with you about URACE Academy and the URACE Racing Team."),
          ("Can this be the beginning of a racing career?",
           "It can be a first step. Your first day helps you discover the sport alongside a team involved in driver "
           "development and competitive karting. What comes next depends on your goals, experience, and readiness."))


def _faq(*mais):
    return {"tipo": "faq", "ancora": "faq", "eyebrow": "Before your first day", "titulo": "A few things to know.",
            "itens": AD_FAQ + mais}


def _fecho(cta):
    return {"tipo": "cta", "titulo": "Make your first lap count.",
            "texto": "Your racing story has to start somewhere. One day. Professional guidance. A world of possibilities.",
            "ctas": [("Plan my first track day", cta)]}


AD_CAMPOS = ('<label>Who is this experience for?<select name="x_experience_for" required><option value="">Select an option'
             '</option><option>Myself</option><option>My child</option><option>Someone else</option></select></label>'
             '<label>Driver’s age<input name="x_driver_age" type="number" min="1" max="120" inputmode="numeric" required '
             'placeholder="Age in years"></label>'
             '<label>Karting experience<select name="x_karting_experience" required><option value="">Select an option'
             '</option><option>None, this would be my first time</option><option>Rental or recreational karting</option>'
             '<option>Some competitive karting</option></select></label>')

AD_EXPERIENCIA = {
    "caminho": "/arrive-and-drive-karting-experience/", "nome": "Arrive & Drive Karting Experience",
    "titulo": "Arrive & Drive Karting Experience in Orlando | URACE",
    "descricao": AD_HERO["sub"], "indexar": False, "foto": "arrive-and-drive-lp-hero.webp",
    "blocos": [
        {"tipo": "hero", **AD_HERO, "ctas": [("Plan my first track day", "#inquiry"), ("Discover the experience", "#story")]},
        # "Experiences starting at $719 / day" do topo: o preço é o do cartão, do painel
        {"tipo": "cartoes", "ancora": "inquiry", "eyebrow": "Your first day starts with a conversation",
         "titulo": "Let’s get you closer to the track.",
         "intro": ("Tell us who will be driving and a little about their experience. Ask about availability, requirements, "
                   "and the right setup for your first day."), "itens": [
             {"titulo": "One-day karting experience", "preco": "kart",
              "texto": "Kart, gear, professional guidance, and URACE technical support. Track fee charged separately."},
             {"titulo": "Prefer to talk?", "texto": "Ask about your first karting experience.", "link": (TELEFONE, TEL)}]},
        # o "Your email app will open…" do urace.us não vale aqui: o pedido cai em Vendas e a pessoa vai ao obrigado
        {"tipo": "formulario", "eyebrow": "Plan your first karting day", "titulo": "Tell us about the future driver.",
         "assunto": "arrive-and-drive", "obrigado": OBRIGADO_AD, "extras": AD_CAMPOS,
         "mensagem": "Anything you’d like us to know?", "enviar": "Email my track-day inquiry",
         "nota": "Availability and participation requirements will be confirmed by the team."},
        _historia(), _apoio("#inquiry"), *_caminho("#inquiry"), _faq(), _fecho("#inquiry"),
    ],
}

# A página de reserva do urace.us é uma agenda (kart, dia e turno, Lead and Follow, depósito e checkout do WooCommerce).
# No site novo a reserva é uma só, com o preço do painel: todo "Plan my first track day" leva a ela.
AD_RESERVA = {
    "caminho": "/arrive-and-drive-karting-booking/", "nome": "Book Arrive & Drive Karting",
    "titulo": "Book Arrive & Drive Karting in Orlando | URACE",
    "descricao": ("Choose your kart. Find your day. Experience real karting with professional guidance and a team "
                  "supporting your first step into motorsport."),
    "indexar": False, "foto": "arrive-and-drive-lp-hero.webp",
    "blocos": [
        {"tipo": "hero", **AD_HERO, "ctas": [("Plan my first track day", RESERVAR), ("Discover the experience", "#story")]},
        {"tipo": "cartoes", "ancora": "booking", "eyebrow": "Your first lap starts here",
         "titulo": "One day in the kart. A new chapter ahead.",
         "intro": ("Choose your kart. Find your day. Experience real karting with professional guidance and a team "
                   "supporting your first step into motorsport."), "itens": [
             {"titulo": "We get you ready.", "lista": ["Racing kart for your session", "Safety equipment and briefing",
                                                      "Professional coaching", "Technical support from URACE"]},
             {"titulo": "You bring the ambition.", "lista": ["Long pants, closed-toe shoes and a jacket",
                                                            "Your confirmed reservation",
                                                            "An adult accompanying drivers under 10"]},
             {"titulo": "One-day karting experience", "preco": "kart",
              "texto": ("Track admission is not included. Driver and guest passes are paid separately to Orlando Kart "
                        "Center.", "Your spot is confirmed after payment. The URACE team will send the driver’s waiver "
                        "before your session. [Review booking terms](/services/arrive-and-drive/).")},
             {"titulo": "Questions before your first lap?", "link": (f"Call {TELEFONE}", TEL)}],
         "ctas": [("Plan my first track day", RESERVAR)]},
        _historia(), _apoio(RESERVAR), *_caminho(RESERVAR),
        _faq(("How does the refundable deposit work?",
              "The deposit is refundable within 5 business days after your session if there is no damage to the kart. "
              "Damage above the deposit may be charged additionally.")),
        _fecho(RESERVAR),
    ],
}

# o "Text the URACE team" (sms:) não entra: o link de bloco aceita tel: e mailto:, não sms:
AD_OBRIGADO = {
    "caminho": OBRIGADO_AD, "nome": "Thank you",
    "titulo": "Thank you | Arrive & Drive Karting Experience | URACE",
    "descricao": ("The URACE team will contact you to confirm availability, participation requirements, and the right "
                  "setup for your first day."),
    "indexar": False,
    "blocos": [
        {"tipo": "hero", "eyebrow": "Plan your first karting day", "h1": "Thanks! Your inquiry is on its way.",
         "sub": ("The URACE team will contact you to confirm availability, participation requirements, and the right "
                 "setup for your first day."),
         "ctas": [("Call the URACE team", TEL)]},
    ],
}


# ------------------------------------------------------------------ The Driver Factory (16/10) e o obrigado dela
DRIVER_FACTORY = {
    "caminho": "/the-driver-factory/", "nome": "The Driver Factory",
    "titulo": "How to Become a Professional Racing Driver | URACE Orlando",
    "descricao": ("How to become a racing driver, step by step: where karting fits, what a real development path looks "
                  "like, and how to get into racing from Orlando."),
    "foto": "banner-topo-lp-urace-1.webp",
    "blocos": [
        {"tipo": "hero", "eyebrow": "Driver Development · Orlando, FL",
         "h1": "Your first step to becoming a professional racing driver starts here.",
         "sub": ("From your first karting experience to competitive racing, URACE provides professional coaching, "
                 "structured driver development and a clear path forward in motorsport."),
         "ctas": [("Find my next step", "#form")], "foto": "banner-topo-lp-urace-1.webp", "alt": ""},
        {"tipo": "texto", "titulo": "More than a karting school. We develop drivers.",
         "paragrafos": ["URACE is a driver development program based in Florida, created to guide young drivers through "
                        "every stage of their motorsport journey. From the first experience behind the wheel to "
                        "competitive racing, we provide professional coaching, structured development, mentorship and "
                        "racing opportunities.",
                        "Because becoming a driver requires more than speed. Motorsport develops discipline, focus, "
                        "decision-making, emotional control and a competitive mindset — skills that matter on the track "
                        "and far beyond it.",
                        "**We are the first step toward becoming a professional racing driver.**"],
         "foto": "imagem-segunda-dobra.webp", "alt": "URACE Academy coaching and go-kart racing at Orlando Kart Center"},
        # "Starting at $719" é o kart do painel; "Programs Starting at $3K/mo" e "$5K/mo" são a Academy e o Boost
        # arredondados em milhar, como o urace.us escreve (#525: as marcas `{academy_k}` e `{boost_k}`)
        {"tipo": "cartoes", "fundo": "escura", "eyebrow": "Where are you in your racing journey?",
         "titulo": "Every driver has a next step.", "itens": [
             {"titulo": "Arrive & Drive", "preco": "kart",
              "texto": ("**Experience karting for one day.**",
                        "Your first opportunity to experience real karting with professional guidance and URACE support. "
                        "Perfect for first-time drivers and families who want to discover motorsport."),
              "link": ("Experience karting", "/kart-lessons-for-beginners/")},
             {"titulo": "URACE Academy",
              "texto": ("**Start your development as a racing driver.**",
                        "A structured driver development program for young athletes who want to train, improve and build "
                        "the foundations required for competitive karting — with professional coaching, track experience, "
                        "evaluation and mentorship.", "Programs starting at **{academy_k}/mo**"),
              "link": ("Join URACE Academy", "#form")},
             {"titulo": "Racing Team",
              "texto": ("**Already competing? Pursue the next level.**",
                        "Professional support for competitive drivers who want to improve their performance and pursue "
                        "higher levels of motorsport — coaching, race preparation, competition experience and "
                        "professional guidance.", "Programs starting at **{boost_k}/mo**"),
              "link": ("Talk to our racing team", "#form")}]},
        _fundador("#form", fundo="clara"),
        {"tipo": "passos", "eyebrow": "The URACE driver pathway", "titulo": "Every driver starts somewhere.",
         "intro": ("URACE provides a structured environment where young drivers can experience motorsport, develop their "
                   "skills and progress toward increasingly competitive levels of racing."),
         "itens": [("Experience", "Discover karting and take your first laps with professional guidance."),
                   ("Develop", "Build technique, discipline, consistency and a competitive mindset through structured training."),
                   ("Compete", "Gain race experience and learn to perform in competitive environments."),
                   ("Pursue the next level", "Continue developing with professional coaching, racing experience and "
                                             "long-term guidance.")]},
        _formulario_lp("academy", OBRIGADO_DF),
        {"tipo": "cta", "titulo": "Future pros start here.",
         "texto": ("Every driver has a next step. Let's find yours. Whether you want to experience karting for the first "
                   "time, begin structured driver development or pursue higher levels of competition, URACE is ready to "
                   "help you move forward."),
         "ctas": [("Find my next step", "#form")]},
    ],
}

DF_OBRIGADO = {
    "caminho": OBRIGADO_DF, "nome": "Thank you",
    "titulo": "The driver factory thank you page - URACE",
    "descricao": "Thank you for getting in touch. We will be in touch soon.",
    "indexar": False,
    "blocos": [{"tipo": "hero", "h1": "Thank you for getting in touch", "sub": "We will be in touch soon.",
                "ctas": [("Go back to home", "/")]}],
}

PAGINAS = (BEGINNERS, DRIVING_SCHOOL, TRAINING_PACKAGES, RACING_TEAM, AD_EXPERIENCIA, AD_RESERVA, AD_OBRIGADO,
           DRIVER_FACTORY, DF_OBRIGADO)
