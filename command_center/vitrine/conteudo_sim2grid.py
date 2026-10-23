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
# Dono, 22/10 (#392): o SIM2GRID fica no Box 5, como na LP ("lp antiga"); o resto do site segue no Box 3 (01/10).
RUA = "10724 Cosmonaut Blvd, Box 5"
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
PLANOS = (
    ("3 sessions per week", "Initial allocation: 10 students", "Coaching included. Each session lasts 2 hours, scheduled according to availability.", "$1,800", "/ month"),
    ("2 sessions per week", "Initial allocation: 10 students", "Coaching included. Each session lasts 2 hours, scheduled according to availability.", "$1,500", "/ month"),
    ("1 session per week", "Initial allocation: 10 students", "Coaching included. Each session lasts 2 hours, scheduled according to availability.", "$900", "/ month"),
)

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
