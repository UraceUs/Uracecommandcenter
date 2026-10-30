"""A página do SIM2GRID (#392) com o texto da LP de hoje (urace.us/sim2grid-racing-simulator/, lida em 22/10/2026).

Dono, 22/10: *"na pagina do sim2grid eu preciso replicar essa lp ... ali dentro sera um serviço um diferente das aulas
de kart podendo agendar ate 5 pessoas para a mesma hora, o valor do serviço é cobrado por hora. monte assim como montou
o arrive and drive com todas as configurações ajustaveis"*.

Aqui mora só o texto e os valores **de fábrica** (a semente do banco, que entra uma vez). O que a página mostra de preço,
horário, vaga, depósito, waiver, idade e aviso vem do painel (Site › Sim2Grid e Site › Serviços e preços); estes valores
só valem com o banco fora. Os preços são os que o dono aprovou em 22/10 (#392, no lugar dos da LP: com coach 125/150/150,
sem coach 50/75/90 no fim de semana, vale o horário de início; programa mensal com sessões de 2 h conforme a
disponibilidade); idade mínima a LP não diz (manda ligar), então nasce vazia.
"""

from command_center.vitrine.conteudo import SITE

CAMINHO = "/sim2grid-racing-simulator/"
TELEFONE = "+1 (407) 250-2291"
# Dono, 22/10 (#392): o SIM2GRID fica no Box 5. Desde 30/10 (#527) o Box só vai na confirmação da reserva
# (`conteudo.endereco_com_box("sim2grid")`); a página mostra a rua.
RUA = SITE["endereco"]["rua"]
ENDERECO = (RUA, "Orlando, Florida", SITE["endereco"]["onde"])

# ------------------------------------------------------------------ a semente do painel (entra uma vez)
# (chave, nome no painel, nome no site, linha de baixo, texto, preço "a partir de", ordem). `kind='sim'` em
# booking_services: a hora de simulador, que não é sessão de kart (não ocupa a agenda do Arrive and Drive).
FORMATOS = (
    ("sim2grid-solo", "SIM2GRID · Simulator hour", "Hourly · Without coaching", "Simulator / without coaching",
     "Your time. Your practice. Book simulator time without a coach.", 50, 10),
    ("sim2grid-coach", "SIM2GRID · Simulator hour with coaching", "Hourly · With coaching", "Simulator + coaching",
     "One session. Your next step. Work with a coach without enrolling in a monthly program.", 125, 20),
)
# (chave da faixa, formato, dias [0 = segunda], início, fim [24 = meia-noite], preço por hora [None = ligar], ordem)
FAIXAS = (
    ("solo:semana:dia", "sim2grid-solo", "01234", 7, 17, 50, 10),
    ("solo:semana:noite", "sim2grid-solo", "01234", 18, 24, 75, 20),
    ("solo:fds", "sim2grid-solo", "56", 8, 24, 90, 30),
    ("coach:semana:dia", "sim2grid-coach", "01234", 7, 17, 125, 10),
    ("coach:semana:noite", "sim2grid-coach", "01234", 18, 24, 150, 20),
    ("coach:fds", "sim2grid-coach", "56", 8, 24, 150, 30),
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
# #525 (dono, 30/10: *"use o que está no urace.us"*): os preços e a linha de cada programa como o urace.us de 29/10
# mostra. O banco que já tinha os de 22/10 ($1,500 e $900) passa a estes só se ninguém mexeu (`PLANOS_ANTES`).
PLANOS_TEXTO = "Coaching included. Each session lasts 2 hours, scheduled according to availability."
PLANOS = (
    ("3 sessions per week", "Initial allocation: 10 students",
     f"$69.28/hr of coaching · 10% off 4-stroke and 15% off 2-stroke Academy. {PLANOS_TEXTO}", "$1,800", "/ month"),
    ("2 sessions per week", "Initial allocation: 10 students",
     f"$78.52/hr of coaching · 5% off 4-stroke and 10% off 2-stroke Academy. {PLANOS_TEXTO}", "$1,360", "/ month"),
    ("1 session per week", "Initial allocation: 10 students",
     f"$87.75/hr of coaching · 5% off any Academy program. {PLANOS_TEXTO}", "$760", "/ month"),
)
PLANOS_ANTES = ("$1,800", "$1,500", "$900")

# ------------------------------------------------------------------ o texto da página
# #396 (dono, 23/10): *"muita informacao · pensa no usuario de mobile ... imagina vc indo ao cinema na hora de construir
# ... tipo lan house era ... tem que virar um point"*. A página virou um app de cinema: a foto, uma frase e a reserva
# (dia → horário com os lugares → quantos → Book). O texto longo da LP saiu; ficou o essencial, curto: o que inclui,
# preço, amigos, criança e cancelamento no FAQ (o FAQPage do Google lê o mesmo).
PAGINA = {
    "caminho": CAMINHO,
    "titulo": "SIM2GRID Racing Simulator in Orlando | URACE",
    "descricao": ("Book a racing simulator by the hour at URACE in Orlando: train with a coach or race your friends side "
                  "by side. SIM2GRID opens November 1, 2026, inside the Orlando Kart Center."),
    "selo": "SIM2GRID · Opening November 1",
    "h1": "Racing simulators in Orlando",
    # {capacidade}: os simuladores do painel; {desde}: a menor faixa com preço ("Starting at $50")
    "sub": "Train like a driver or race your friends. {capacidade} cockpits, by the hour · {desde}",
    "reserva_titulo": "Book your seat",
    "fuso": "Orlando time. The rate is set by the start time.",
    "nota": "Next: your cart. Pick each driver and pay with Stripe — card, Apple Pay or Google Pay.",
    "amigos": "Bring friends",
    "planos_titulo": "Monthly programs",
    "planos_sub": "Coaching included · 2-hour sessions, scheduled with the team · billed monthly until you cancel.",
    # o caminho até o Racing Team, numa linha (dono: "caminho até o Racing Team em 1 linha com link")
    "trilha": (("Simulator", "#booking"), ("Arrive & Drive", "/services/arrive-and-drive/"), ("Academy", "/academy/"),
               ("Racing Team", "/pro-team/")),
    "trilha_rotulo": "Your path",
    "faq_titulo": "Before you book",
    # {solo}, {coach} e {capacidade}: o painel, por extenso (o texto nunca diz um preço que o painel não tem)
    "faq": (
        ("What’s included in a simulator hour?",
         ("One cockpit per driver — competition seat, steering wheel and pedals — for the hours you book. Choose “with "
          "coach” and a coach works with you during the session. Karting and the monthly programs are separate: a "
          f"simulator session doesn’t include track time. Find us at {RUA}, Orlando, inside the Orlando Kart Center.",)),
        ("How much does it cost?",
         ("Without coaching: {solo}. With coaching: {coach}. The rate is set by the start time.",)),
        ("Can I bring friends at the same time?",
         ("Yes. Up to {capacidade} people can drive at the same time, one simulator each. Pick the hour, set how many "
          "drivers, and each one gets their own seat in the cart.",)),
        ("Can I book this for my child?",
         ("Before booking for a child, call URACE to confirm age, height, and participation requirements and which session "
          "format is suitable. Our team can help you choose an appropriate starting point before you pay.",)),
        ("What if I need to change or cancel my booking?",
         ("For an hourly session, confirm the cancellation and rescheduling terms with URACE before payment. Monthly "
          "program sessions are scheduled with the team according to availability.",)),
    ),
    "foto": "simulator-kv.webp",
    "foto_topo": "simulator-cockpit.webp",       # #396: o cockpit recortado do cartaz (sem o texto da arte)
    "fotos": ("driver-kv.webp", "simulator-kv.webp"),
}

# ------------------------------------------------------------------ as landings de formulário (#493)
# O urace.us publicou em 22/10 a mesma landing do SIM2GRID com um formulário de interesse em dois endereços, um por canal
# da campanha (formulário por telefone e SMS). O texto abaixo é o dessas páginas (lidas em 29/10/2026); o preço nunca é
# escrito aqui: {solo_desde}, {coach_desde}, {solo}, {coach} e {inicio} vêm das faixas do painel (Site › Sim2Grid).
FORM_CAMINHOS = {"/sim2grid-from-racing-simulator-to-the-grid-form/": "form",
                 "/sim2grid-from-racing-simulator-to-the-grid-form-sms/": "sms"}
FORM = {
    "titulo": "URACE Sim2Grid: Racing School on Simulators in Orlando",
    "descricao": ("URACE Sim2Grid, our racing school on simulators, opens November 1, 2026 in the URACE simulator lounge in "
                  "Orlando. Book now, then move on to URACE Academy."),
    "selo": "For gamers with racing ambitions",
    "h1": "Your first step into motorsport starts here",
    "sub": ("Book your first one-hour racing simulator session at URACE in Orlando. {solo_desde_frase}, with optional "
            "coaching available."),
    "abertura": "SIM2GRID · Opening November 1 · Book now",
    "cta": "Book my first session",
    "caminho_curto": "Simulator → Karting → Driver development → Racing.",
    "form_rotulo": "SIM2GRID / Your first step",
    "form_titulo": "Tell us about your goals.",
    "form_texto": ("Tell us what you’re looking for and choose your session type. Our team will review your information and "
                   "contact you to help you get started."),
    "obrigatorio": "All fields are required.",
    "objetivo_rotulo": "What would you like to get out of your session?",
    "objetivos": ("Try a racing simulator for the first time", "Improve my driving skills",
                  "Explore a first step into motorsport", "Find an experience for my child"),
    "sessao_rotulo": "Which session are you interested in?",
    "sessoes": (("Without coaching", "Simulator session", "solo"), ("With coaching", "Simulator session + coaching", "coach")),
    "inicio": "Starting rates apply {inicio}. Evening and weekend rates vary by session type.",
    "telefone_dica": "Include your country code if you’re outside the U.S.",
    "enviar": "Send my information",
    "consentimento": ("By submitting, you’re asking URACE to contact you about your inquiry.",
                      "No payment required. This inquiry does not reserve a session."),
    "proximo_rotulo": "Your next step",
    "proximo_titulo": "Let’s talk about your first session.",
    "proximo_texto": "Want to discuss your options with the team? You can call URACE directly.",
    "o_que_rotulo": "What is SIM2GRID?",
    "o_que_titulo": "This is SIM2GRID. Get in. Drive.",
    "o_que": (
        "SIM2GRID is URACE’s in-person racing simulator experience in Orlando. Take a seat in a professional racing "
        "simulator, use a steering wheel and pedals, and drive on virtual circuits.",
        "The setup is here. Experience a dedicated racing cockpit without buying a simulator of your own.",
        "One hour to make it yours. Enjoy the drive, practice braking and cornering, and challenge yourself to put a lap "
        "together. No monthly membership required.",
        "Coaching is your choice. Book simulator time without coaching, or choose a coached session for guidance as you drive.",
        "Start with the experience. See where your interest in racing takes you.",
    ),
    "caminho_rotulo": "The URACE driver pathway",
    "caminho_titulo": "One passion. A world of possibilities.",
    "caminho_texto": ("Your racing story can begin in the simulator. See how that first experience connects to karting, "
                      "structured development, and competition.",
                      "Explore the stages. Picture your future. Start with the step that’s right in front of you."),
    "etapas": (
        ("Experience the simulator", "Your first experience",
         "Get behind the wheel at URACE. Experience the challenge of putting a lap together and discover where your racing "
         "ambition could take you.", "#formulario"),
        ("Take it to the track", "Your first time on a kart",
         "A separate, one-day karting experience with professional guidance. It’s an opportunity to explore driving beyond "
         "the simulator.", "/services/arrive-and-drive/"),
        ("Develop as a driver", "Structured driver development",
         "Structured training to keep developing as a driver. Talk with the team about your goals and the commitment involved.",
         "/academy/"),
        ("Prepare for competition", "Competitive racing support",
         "Support for drivers getting ready for competitive racing. Talk with the team about which program could fit your "
         "stage.", "/pro-team/"),
    ),
    "faq_rotulo": "Before you book",
    "faq_titulo": "A clear start. No guesswork.",
    "faq_texto": ("Your first visit should feel straightforward. Get answers about experience, coaching, pricing, and what "
                  "comes next. Still unsure? Talk to our Orlando team."),
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
          "experience? Call our team.",)),
        ("What exactly do I get for a session without coaching?",
         ("A one-hour simulator session without coaching. Rates by start time: {solo}. Coaching, karting, and monthly "
          "programs are separate.",)),
        ("Do I have to pay for coaching?",
         ("No. Choose “Without coaching” to book simulator time without a coach. If you want to work with a coach, select "
          "“With coaching”: {coach}.",)),
        ("Can I try it once without signing up for a membership?",
         ("Yes. Book one hourly session, with or without coaching. An individual session does not enroll you in a monthly "
          "subscription. If you decide you want regular training later, you can explore the monthly programs separately.",)),
        ("How long is a session, and where do I go?",
         (f"Individual sessions last one hour at URACE, {RUA}, Orlando, FL 32824. The announced opening date is November 1, "
          "2026. All booking times are local to Orlando. Monthly program sessions last two hours each, using two one-hour "
          "slots of the regular weekly timetable.",)),
        ("Can I book this for my child?",
         ("Before booking for a child, call URACE to confirm age, height, and participation requirements.",)),
        ("What if I need to change my booking?",
         ("For an hourly session, confirm the cancellation and rescheduling terms with URACE before payment. Monthly programs "
          "are scheduled based on availability, ideally on a fixed weekly schedule, and missed sessions cannot be made up. If "
          "your schedule changes often, consider an individual session first.",)),
        ("Can this lead to real karting or racing?",
         ("It can be your introduction to URACE and a conversation about your next step. The team also offers one-day "
          "karting experiences, Academy development, and Racing Team support. Those programs are booked separately; your "
          "simulator session doesn’t include track time or guarantee progression into competition.",)),
    ),
    "fim_rotulo": "SIM2GRID by URACE",
    "fim_titulo": "Next lap: yours.",
    "fim_texto": "You can already picture the grid. Start exploring your way there with SIM2GRID.",
    "fim_cta": "Start my racing journey",
}
