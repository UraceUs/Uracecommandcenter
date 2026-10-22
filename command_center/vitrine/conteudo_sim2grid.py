"""A página do SIM2GRID (#392) com o texto da LP de hoje (urace.us/sim2grid-racing-simulator/, lida em 22/10/2026).

Dono, 22/10: *"na pagina do sim2grid eu preciso replicar essa lp ... ali dentro sera um serviço um diferente das aulas
de kart podendo agendar ate 5 pessoas para a mesma hora, o valor do serviço é cobrado por hora. monte assim como montou
o arrive and drive com todas as configurações ajustaveis"*.

Aqui mora só o texto e os valores **de fábrica** (a semente do banco, que entra uma vez). O que a página mostra de preço,
horário, vaga, depósito, waiver, idade e aviso vem do painel (Site › Sim2Grid e Site › Serviços e preços); estes valores
só valem com o banco fora. Os preços e horários são os da LP; idade mínima a LP não diz (manda ligar), então nasce vazia.
"""

from command_center.vitrine.conteudo import SITE

CAMINHO = "/sim2grid-racing-simulator/"
TELEFONE = "+1 (407) 250-2291"
# A LP de hoje escreve "Box 5"; o endereço do site é o da decisão do dono de 01/10 (Box 3), o mesmo de todas as páginas
# (test_vitrine trava). Se o simulador fica mesmo em outro box, muda aqui e no SITE junto, com o dono.
ENDERECO = (SITE["endereco"]["rua"], "Orlando, Florida", SITE["endereco"]["onde"])

# ------------------------------------------------------------------ a semente do painel (entra uma vez)
# (chave, nome no painel, nome no site, linha de baixo, texto, preço "a partir de", ordem). `kind='sim'` em
# booking_services: a hora de simulador, que não é sessão de kart (não ocupa a agenda do Arrive and Drive).
FORMATOS = (
    ("sim2grid-solo", "SIM2GRID · Simulator hour", "Hourly · Without coaching", "Simulator / without coaching",
     "Your time. Your practice. Book simulator time without a coach.", 50, 10),
    ("sim2grid-coach", "SIM2GRID · Simulator hour with coaching", "Hourly · With coaching", "Simulator + coaching",
     "One session. Your next step. Work with a coach without enrolling in a monthly program.", 100, 20),
)
# (chave da faixa, formato, dias [0 = segunda], início, fim [24 = meia-noite], preço por hora [None = ligar], ordem)
FAIXAS = (
    ("solo:semana:dia", "sim2grid-solo", "01234", 7, 17, 50, 10),
    ("solo:semana:noite", "sim2grid-solo", "01234", 18, 24, 75, 20),
    ("solo:fds", "sim2grid-solo", "56", 8, 24, None, 30),
    ("coach:semana:dia", "sim2grid-coach", "01234", 7, 17, 100, 10),
    ("coach:semana:noite", "sim2grid-coach", "01234", 18, 24, 120, 20),
    ("coach:fds", "sim2grid-coach", "56", 8, 24, 120, 30),
)
REGRAS = {
    "online": 1,                    # vende pelo site (o mesmo carrinho e Stripe do Arrive and Drive)
    "capacity": 5,                  # dono: "até 5 pessoas para a mesma hora" = 5 simuladores
    "min_hours": 1,
    "max_hours": 3,
    "horizon_days": 60,
    "min_notice_hours": 2,
    "open_from": "2026-11-01",      # a abertura que a LP anuncia
    "closed_dates": None,
    "min_age": None,                # a LP não diz: manda ligar antes de reservar para criança
    "waiver_required": 1,
    "notice": ("Booking for a child? Call us before booking to confirm age, height and participation requirements. "
               "For an hourly session, confirm the cancellation and rescheduling terms with URACE before payment."),
    "raffle_text": "I want to participate on the monthly raffle for Kart time, sim time or URACE products",
}

# Os programas mensais: cartões da página (site_offers, page='sim2grid'), editáveis em Site › Cartões das páginas.
PLANOS_GRUPO = "Monthly programs · 30 students total · 10 places per plan"
PLANOS = (
    ("3 sessions per week", "Initial allocation: 10 students", "Fixed weekly days and times. Each coached session lasts 2 hours: 1h40 in the simulator plus setup and debrief.", "$1,800", "/ month"),
    ("2 sessions per week", "Initial allocation: 10 students", "Fixed weekly days and times. Each coached session lasts 2 hours: 1h40 in the simulator plus setup and debrief.", "$1,500", "/ month"),
    ("1 session per week", "Initial allocation: 10 students", "Fixed weekly days and times. Each coached session lasts 2 hours: 1h40 in the simulator plus setup and debrief.", "$900", "/ month"),
)

# ------------------------------------------------------------------ o texto da página (da LP)
PAGINA = {
    "caminho": CAMINHO,
    "titulo": "SIM2GRID Racing Simulator in Orlando | URACE",
    "descricao": ("Book your first one-hour racing simulator session at URACE in Orlando, with or without coaching. "
                  "SIM2GRID opens November 1, 2026, inside the Orlando Kart Center."),
    "eyebrow": "For gamers with racing ambitions",
    "h1": "Your first step into motorsport starts here",
    "sub": "Book your first one-hour racing simulator session at URACE in Orlando. {desde}, with optional coaching available.",
    "selo": "SIM2GRID · Opening November 1 · Book now",
    "trilha": "Simulator → Karting → Driver development → Racing.",
    "reserva_eyebrow": "SIM2GRID / Your starting line",
    "reserva_titulo": "Make time for your ambition.",
    "reserva_sub": ("Build a regular training routine or start with an hourly session. Choose your format and continue to "
                    "payment to book your place."),
    "passo1": "01 · Choose your format",
    "passo2": "02 · Choose your session",
    "passo2_sub": "Choose a date and a session start time. Your time is held while you complete payment.",
    "fuso": "All times are Orlando local time.",
    "nota": ("Payment is processed securely at checkout. Your booking is confirmed once payment is complete. Next: the "
             "session goes to your cart. Sign in or create your URACE account, then pay with Stripe — card, Apple Pay or "
             "Google Pay."),
    "planos_titulo": "Fixed schedule. Consistent training.",
    "planos_sub": ("Your weekly days and times are fixed once booked. Missed sessions cannot be made up. Each coached "
                   "session lasts 2 hours: 1h40 in the simulator plus setup and debrief. Billed monthly until you cancel. "
                   "Places are limited."),
    "planos_capacidade": "Initial program capacity: 30 students total · 10 places per plan",
    "caminho_eyebrow": "From racing games to racing ambitions",
    "caminho_titulo": "You can see the driver. Now see the path.",
    "caminho_texto": (
        "Maybe it started with a racing game. Maybe it’s the dream of lining up on a real grid — in karting, Formula 4, or "
        "one day even Formula 1. That ambition deserves more than another “what if.”",
        "Start by experiencing the simulator at URACE. Then get to know the next stages available: your first karting "
        "experience, structured training, and support for competitive racing. Your goals, experience, and readiness help "
        "shape the next step.",
        "You don’t need your whole racing future mapped out to take the first step."),
    "paixao_eyebrow": "A first experience with a bigger purpose",
    "paixao_titulo": "Bring the passion. Discover the possibilities.",
    "paixao": (
        ("01 / Get behind the wheel", "Put your ambition in motion.", "Your racing interest has a place here.",
         "Step into the SIM2GRID cockpit at URACE. Experience the challenge of braking, steering, and putting a consistent "
         "lap together.", ("Start my racing journey", "#booking")),
        ("02 / Meet your next step", "Look toward the track.", "See how you could take it further.",
         "Discover Arrive & Drive: a separate, one-day karting experience with professional guidance. It’s an opportunity "
         "to explore driving beyond the simulator.", ("Explore the pathway", "/services/arrive-and-drive/")),
        ("03 / Think like a driver", "Give your dream direction.", "Turn “what’s next?” into a conversation.",
         "Get to know URACE Academy and Racing Team. Talk with the team about your goals, the commitment involved, and "
         "which program could fit your stage.", ("See what comes next", "/academy/")),
    ),
    "degraus_eyebrow": "The URACE driver pathway",
    "degraus_titulo": "One passion. A world of possibilities.",
    "degraus_sub": ("Your racing story can begin in the simulator. See how that first experience connects to karting, "
                    "structured development, and competition. Explore the stages. Picture your future. Start with the step "
                    "that’s right in front of you."),
    "degraus": (
        ("01", "Experience the simulator", "SIM2GRID", "Your first experience",
         "Get behind the wheel at URACE. Experience the challenge of putting a lap together and discover where your racing "
         "ambition could take you.", "#booking"),
        ("02", "Take it to the track", "Arrive & Drive", "Your first time on a kart",
         "A separate, one-day karting experience with professional guidance. It’s an opportunity to explore driving beyond "
         "the simulator.", "/services/arrive-and-drive/"),
        ("03", "Develop as a driver", "URACE Academy", "Structured driver development",
         "Structured training to keep developing as a driver. Talk with the team about your goals and the commitment "
         "involved.", "/academy/"),
        ("04", "Prepare for competition", "URACE Racing Team", "Competitive racing support",
         "Support for drivers getting ready for competitive racing. Talk with the team about which program could fit your "
         "stage.", "/pro-team/"),
    ),
    "faq_eyebrow": "Before you book",
    "faq_titulo": "A clear start. No guesswork.",
    "faq_sub": ("Your first visit should feel straightforward. Get answers about experience, coaching, pricing, and what "
                "comes next. Still unsure? Talk to our Orlando team."),
    # {solo} e {coach}: as faixas de preço do painel, escritas por extenso (o texto nunca diz um preço que o painel não tem)
    "faq": (
        ("I play racing games. Is SIM2GRID a good next step?",
         ("SIM2GRID gives you a place to explore that interest in person at URACE, using a racing simulator with a seat, "
          "steering wheel, and pedals. Start with a single session to experience the setup. You don’t have to commit to a "
          "racing career or a monthly program.",)),
        ("What makes this different from playing at home?",
         ("You’ll visit URACE in Orlando and drive on its simulator setup. You can book time without coaching, add a coached "
          "session, or explore regular training. It’s also an opportunity to meet the team and learn about URACE’s separate "
          "karting and driver development programs.",)),
        ("Do I need to be an experienced driver?",
         ("SIM2GRID is positioned as a starting point for exploring motorsport, not just a program for competitive drivers. "
          "If you’re new to simulators and want guidance, consider a coached session. Unsure which format fits your "
          "experience? Call our team before booking.",)),
        ("What does a simulator hour cost?",
         ("Simulator time without coaching: {solo}. Coaching, karting, and monthly programs are separate options. Choose "
          "your date and time to see the session rate.",)),
        ("Do I have to pay for coaching?",
         ("No. Choose “Without coaching” to book simulator time without a coach. If you want to work with a coach, select "
          "“With coaching”: {coach}.",)),
        ("Can I try it once without signing up for a membership?",
         ("Yes. Book one hourly session, with or without coaching. An individual session does not enroll you in a monthly "
          "subscription. If you decide you want regular training later, you can explore the monthly programs separately.",)),
        ("How long is a session, and where do I go?",
         (f"Hourly sessions are booked by the hour at URACE, {SITE['endereco']['rua']}, Orlando, FL {SITE['endereco']['cep']}, "
          "inside the Orlando Kart Center. The announced opening date is November 1, 2026. All booking times are local to Orlando. "
          "Monthly program sessions use a different format: two hours, including 1h40 in the simulator plus setup and "
          "debrief.",)),
        ("Can I bring friends at the same time?",
         ("Yes. Up to {capacidade} people can drive at the same time, one simulator each. Each driver books and pays their "
          "own hour.",)),
        ("Can I book this for my child?",
         ("Before booking for a child, call URACE to confirm age, height, and participation requirements and which session "
          "format is suitable. Our team can help you choose an appropriate starting point before you pay.",)),
        ("What if I need to change my booking?",
         ("For an hourly session, confirm the cancellation and rescheduling terms with URACE before payment. Monthly "
          "programs follow fixed weekly days and times, and missed sessions cannot be made up. If your schedule changes "
          "often, consider an individual session first.",)),
        ("Can this lead to real karting or racing?",
         ("It can be your introduction to URACE and a conversation about your next step. The team also offers one-day "
          "karting experiences, Academy development, and Racing Team support. Those programs are booked separately; your "
          "simulator session doesn’t include track time or guarantee progression into competition.",)),
    ),
    "fecho_eyebrow": "SIM2GRID by URACE",
    "fecho": "Next lap: yours.",
    "fecho_sub": "You can already picture the grid. Start exploring your way there with SIM2GRID.",
    "foto": "simulator-kv.webp",
    "fotos": ("driver-kv.webp", "simulator-kv.webp"),
}
