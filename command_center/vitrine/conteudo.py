"""O que o site novo diz, copiado do urace.us (#148; texto atualizado em 13/10/2026, #207).

Dono, 07/10: *"use todas as informações que ja temos no site"*; dono, 13/10 (#207): *"vou pegar o
copy que tá no site atual e jogar naquele outro site lá, o novo.urace.us"*. Nada aqui é inventado:
cada texto saiu da página citada ao lado, do jeito que está no urace.us de 13/10.

O que fica diferente do site atual, de propósito:
- o endereço público é o da pista, sem o Box. O Box (3 para o kart, 5 para o SIM2GRID) vai só na confirmação do
  agendamento (dono, 30/10, #527: *"somente na confirmação de agendamento isso será passado"*);
- remarcação com **48 horas** de antecedência e a taxa de US$ 95 (dono, 30/10, #527: *"48h"*; de 08/10 a 30/10
  foram 24 h);
- idade dos karts: a do produto (Baby 4–7, 4-stroke 7+, 2-stroke 7+, Adult Shifter 14+; dono, 08/10);
- o nome da marca sai sempre "URACE" (o site atual alterna Urace, URace e URrace);
- preço de serviço não é texto fixo: vem do sistema (`KARTS`, os planos do painel) ou não aparece.
"""

SITE = {
    "nome": "URACE",
    "slogan": "the Champion's Factory",
    "endereco": {"rua": "10724 Cosmonaut Blvd", "cidade": "Orlando", "estado": "FL", "cep": "32824",
                 "pais": "US", "onde": "inside the Orlando Kart Center"},
    "telefone": "+1 (407) 250 2291",
    "telefone_e164": "+14072502291",
    "emails": ("support@urace.us", "urace@urace.us"),
    "redes": {
        "Instagram": "https://www.instagram.com/urace.us/",
        "Facebook": "https://www.facebook.com/Urace.us/",
        "TikTok": "https://www.tiktok.com/@urace.usa",
    },
    "whatsapp": "https://wa.me/14072502291?text=Hi!%20I%27d%20like%20to%20know%20more%20about%20karting%20at%20URACE.",
    "horario": "Open every day, 8 AM – 8 PM",
    # #252: o resto do LocalBusiness que o urace.us de hoje já publica (Yoast). Tudo isto vem de lá,
    # e sem isto a troca de domínio perderia o SEO local: mapa, cidade atendida, Yelp e TripAdvisor.
    # #254 (dono, 15/10): "o kart school se tornou Urace academy" — o nome alternativo que o Yoast
    # publicava passa a ser o nome novo, para o Google não ensinar o nome que acabou
    "outro_nome": "URACE Academy",
    "descricao_negocio": ("Kart racing school in Orlando, Florida. Arrive and drive days in real race karts, "
                          "professional coaching and a monthly kart academy, based at the Orlando Kart Center."),
    "faixa_preco": "$$$",
    "moeda": "USD",
    "geo": (28.4108348, -81.377619),
    "mapa": "https://www.google.com/maps/place/Urace+-+Kart+team+and+school/@28.4108348,-81.377619,17z",
    "atende": (("City", "Orlando"), ("City", "Kissimmee"), ("City", "Winter Garden"), ("State", "Florida")),
    "perfis": ("https://www.yelp.com/biz/urace-kart-school-orlando",
               "https://www.tripadvisor.com/Attraction_Review-g34515-d32848914-Reviews-Urace_Us_Kart_And_School-"
               "Orlando_Florida.html",
               "https://www.google.com/maps/place/Urace+-+Kart+team+and+school/@28.4108348,-81.377619,17z"),
}

# #527 (dono, 30/10): o Box não sai nas páginas; vai só no que o cliente recebe depois de marcar ou comprar
# (a confirmação da sessão e a retirada da loja). Box 3 é o do kart e da loja; Box 5, o do SIM2GRID (#392).
BOX = {"kart": "Box 3", "sim2grid": "Box 5"}


def endereco_com_box(onde="kart"):
    """O endereço inteiro, com o Box, para a confirmação: "10724 Cosmonaut Blvd, Box 3, Orlando, FL 32824"."""
    end = SITE["endereco"]
    return f'{end["rua"]}, {BOX[onde]}, {end["cidade"]}, {end["estado"]} {end["cep"]}'


# #511: a faixa antes do rodapé do urace.us de 29/10: "Powered by" o Orlando Kart Center e os parceiros, com o nome e o
# logo como estão lá (sem link). Os logos moram em static/img.
POWERED_BY = ("Orlando Kart Center", "parceiro-orlando-kart-center.webp")
PARCEIROS = (("ILX Group", "parceiro-ilx-group.svg"), ("AZ Car Rental", "parceiro-az-car-rental.svg"),
             ("CANOTOPS", "parceiro-canotops.webp"), ("Allure Global Events", "parceiro-allure.webp"))

# O site inteiro mora aqui (#164): nenhum link do menu volta ao WordPress.
ANTIGO = "https://urace.us"
# #207: os rótulos do menu do urace.us de 13/10, nos caminhos do site novo. "Events" (um submenu sem
# página própria) e o "Home" (o logo já leva à home) ficam de fora do topo.
# #394 (dono, 22/10, o menu da KartSport): quatro grupos que abrem (⌄). O título leva à página do grupo e os
# subitens ficam na caixa. "Our Services" saiu do topo e segue no rodapé e nas páginas. Na Store, os subitens são
# categorias da loja (slug, rótulo) e só aparecem as que têm produto (`paginas.grupos_do_menu`).
SIM2GRID = "/sim2grid-racing-simulator/"          # #392: a página própria do SIM2GRID
MENU = (
    {"titulo": "URACE Academy", "link": "/academy/",
     "itens": (("Academy", "/academy/"), ("Racing Team", "/pro-team/"), ("Arrive and Drive", "/services/arrive-and-drive/"))},
    {"titulo": "For Beginners", "link": "/for-beginners/",
     "itens": (("Sim 2 Grid", SIM2GRID), ("Plan Your Career", "/career/"))},
    {"titulo": "Store", "link": "/store/",
     "loja": (("engines", "Engines"), ("chassis", "Chassis"), ("tires", "Tires"), ("parts", "Parts"),
              ("official-urace-products", "Apparel"), ("custom-kart-suits", "Suits"))},
    {"titulo": "About", "link": "/about/",
     "itens": (("About URACE", "/about/"), ("Blog", "/blog/"), ("Contact us", "/contact/"))},
)
# O botão vermelho do topo: a reserva do Arrive and Drive (a mesma dos botões "Book" do site)
RESERVAR = "/services/arrive-and-drive/#reservar"
# O rodapé do urace.us de 13/10 ("Navigation"); "Sponsors" não tem página no site novo.
RODAPE = (
    ("Home", "/"),
    ("Store", "/store/"),
    ("Our Services", "/services/"),
    ("About", "/about/"),
    ("Blog", "/blog/"),
    ("Contact Us", "/contact/"),
)

# ------------------------------------------------------------------ blocos comuns (FAQ das páginas de serviço)
TRACK = ("Orlando Kart Center’s 8/10 mile professional kart racing track is your textbook. A challenging circuit, the "
         "variety of corners is the ideal training ground. URACE is not the racetrack; we are a racing team that provides "
         "services to racers using a third-party track. We must adhere to their rules and operating hours. Both team "
         "members and drivers are required to pay admission fees to access the track.")

TERMOS = (
    "The program price is URACE’s fee for coaching and trackside support only. Track fees are not included: driver and "
    "guest passes are paid directly to the Orlando Kart Center: driver pass $90 Monday to Friday and $65 Saturday "
    "and Sunday, spectator pass $5, charged directly by the track.",
    # idades: decisão do dono de 08/10 (o site atual ainda lista Micro/Mini 6–13 e Junior/Senior 11+)
    "There are different categories of kart available: Baby Kart (ages 4–7), 4-stroke (7+), 2-stroke (7+) and Adult "
    "Shifter (14+, experience required). The difference between 2t and 4t kart options is the performance. We recommend "
    "new entrants to the sport to start with the 4t options, and we can move the driver to the 2t option whenever we "
    "judge that the driver is capable of handling the 2t kart.",
    "This package consists of 3 or 6 sessions of 10 minutes each, 30 minutes or 1 hour of total track time, according to "
    "your choice. The scheduled arrival time at the track is 8 am. We kindly request that you arrive on time. If less "
    "than 75% track time is achieved, there is a possibility of receiving a proportional credit for a future session. "
    "Each case will be decided individually based on the reason for not meeting the minimum track time.",
    "To cover potential crash damage caused by the driver and track fees a $400 deposit will be charged in advance for "
    "security purposes, however this amount will be fully refunded at the end of the event in case of no "
    "incidents/damages to the kart.",
    "Any damages caused to the kart are not included in this price, regardless of the driver’s fault or not in the "
    "incident, and will be billed to you for the costs of repair. Clarifying: If the kart breaks down and it was not "
    "caused by the driver, (crash, going off of the track or aggressive driving style) the costs of repair will be "
    "covered by URACE. If the kart gets damaged in the result of a crash, regardless of driver’s fault in the incident, "
    "the costs of repair will be billed to you. Understanding why: each driver in a race track is fully liable for his "
    "own equipment and safety. Meaning, even if someone else crashes into you or your child, you are responsible for "
    "your and or child’s equipment. You are not responsible for the other person in the other kart, nor the other "
    "person’s equipment even if you or your child caused the incident.",
    "Kids under 10 years old must be accompanied by an adult. We provide a childcare assistant for extra $200 in case "
    "you are unable to stay with your child. This service must be requested beforehand.",
    "Racing is a high-risk activity. By booking this appointment you agree and acknowledge that URACE is not responsible "
    "for any injuries, damages, or losses of any nature that might happen to you, or your family during track "
    "activities or while on site.",
)

# Dono, 30/10 (#527): remarcação com 48 h e a taxa (de 08/10 a 30/10 foram 24 h).
REEMBOLSO = (
    "Our service requires planning, preparation, coordination and transportation to the track on our end, for those "
    "reasons we do not offer refunds. Rescheduling will be available with a minimum notice of 48h and potential costs "
    "of rearrangement.",
    "Rescheduling Policy: if a class is rescheduled with less than 48 hours’ notice, a flat fee of $95 will be charged. "
    "If a Driver Pass is required, it will be charged additionally.",
    "To avoid this fee, we recommend notifying us of any changes at least 48 hours in advance.",
)

HORARIO = ("We’re open every day, from 8 AM to 8 PM.",)

# #508: o "Book a call" / "Talk to us" do urace.us de 29/10 (a agenda do Google da equipe, na Academy e no Contact)
LIGACAO = "https://calendar.app.google/KBbHhXjoRMS6sbHv8"
GOOGLE = ("https://www.google.com/maps/place/URACE/@28.4108348,-81.377619,17z/data=!4m8!3m7!1s0x88e77d37e3e0fd25:"
          "0xa9426dd3f3d2290e!8m2!3d28.4108348!4d-81.377619!9m1!1b1")
# #521: "On the top step", os resultados da temporada que o urace.us de 29/10 mostra (foto, alt, título, legenda): os mesmos
# na home, na About, na Academy e nas landings. Resultado novo entra aqui, uma vez.
# #526: os três vídeos curtos do urace.us (home e /winter/, "On camera"), servidos pelo próprio site: o mp4 em
# static/video (H.264 + AAC, `faststart`, sem metadados) e o pôster em static/img (WebP do tamanho do vídeo). Para trocar
# um: o arquivo novo com outro nome nas duas pastas e o nome aqui (o playbook geral, "Site › Vídeos", tem o passo a passo).
CURTAS = {n: {"video": f"{a}.mp4", "poster": f"{a}-poster.webp"} for n, a in (
    ("vitoria", "frankie-iadevaia-urace-after-the-win"), ("primeira", "brody-urace-first-race-k100"),
    ("fundador", "italo-urace-founder-story"))}

RESULTADOS = (("urace-team-bushnell-p1-p3.webp", "URACE team with the trophy after Frankie Iadevaia's P1 in Bushnell, Florida",
               "P1 + P3 · Bushnell, Florida", "Frankie Iadevaia wins Saturday, podium Sunday. The whole crew on the grid."),
              ("urace-driver-jacksonville-p1.webp", "Frankie Iadevaia in his URACE suit, Jacksonville",
               "P1 · FLKC Rounds 7 & 8 · Jacksonville", "Frankie Iadevaia, URACE program driver. October 2026."))
# as avaliações do Google que o urace.us mostra (29/10): o texto e o nome como estão lá — o número de avaliações não se
# escreve (fica velho); o link leva a todas
AVALIACOES = (("Claire Baillie", "Parent · UK · Google review",
               "Hayden, who is currently racing as a cadet, has been karting since the age of five and races nationally in "
               "the UK. U Race seamlessly caters to everyone from complete novices to professional drivers."),
              ("Samira Torres", "Parent · visiting Orlando · Google review",
               "The coaching is extremely professional, organized, and focused on real driver development, not just "
               "recreational karting."),
              ("Tyron", "Driver · racing in France · Google review",
               "It was a great experience. Thank you Italo for everything you taught me."))

FAQ_COMUM = (
    ("The track", (TRACK,)),
    ("Terms and conditions", TERMOS),
    ("Refund policy", REEMBOLSO),
    ("Opening hours", HORARIO),
)

# Os termos de grupos e eventos (urace.us/services/, bloco "Birthday party / Corporate Events", e
# urace.us/plan-your-career/, bloco "Not on the ladder").
FAQ_EVENTO = (
    ("The track", ("Orlando Kart Center’s 8/10 mile professional kart racing track is your textbook. A challenging "
                   "circuit, the variety of corners is the ideal training ground.",
                   "URACE is not the racetrack; we are a racing team that provides services to racers and enthusiasts "
                   "using a third-party track. We must adhere to their rules and operating hours.")),
    ("Terms and conditions", ("Crashes or damages caused by the driver are not included in the price. The program listed "
                              "price is the URACE fee for kart rental and trackside support only. A deposit for "
                              "incidentals will be collected the day before the event. The deposit is refunded in case "
                              "of no incidents at the end of the event after deducting the 3.5% credit card processing fee.",
                              "Racing is a high-risk sports activity and environment. By booking this appointment, you "
                              "agree and acknowledge that URACE is not responsible for any injuries, damages, or losses "
                              "of any nature that may happen while on site.")),
    ("Refund policy", ("Our service requires planning, preparation, coordination and transportation to the track on our "
                       "end, for those reasons we cannot offer a refund. Rescheduling will be available with a minimum "
                       "of 48h notice.",
                       "Rescheduling policy. If a class is rescheduled with less than 48 hours’ notice: a flat fee of $95 "
                       "will be charged, and if a Driver Pass is required it will be charged additionally. To avoid this "
                       "fee, we recommend notifying us of any changes at least 48 hours in advance.",
                       "Please note that if a training session needs to be rescheduled due to circumstances outside of "
                       "URACE’s control, a fee will be charged to cover our costs of preparation. This fee will be "
                       "calculated based on the cost to reschedule the session and the amount of drivers involved. This "
                       "fee will be in addition to any other costs associated with the session itself. By using URACE’s "
                       "services, you agree to this policy and understand that rescheduling fees may apply in the event "
                       "of unforeseen circumstances.")),
)

# "What Our Clients Say" das páginas de serviço (o terceiro nome, "Christopher H.", não tem texto no
# site atual e fica de fora).
DEPOIMENTOS_EVENTOS = (
    ("Ivan P.", "My son’s birthday was a hit! The kids had the time of their lives, and everything was so well organized!"),
    ("Daniel M., Team Leader", "Best corporate outing we’ve done! Everyone’s still talking about it weeks later."),
)

GRUPOS = ("Team Up for a Turbo-Charged Experience! Bring your crew and get ready for an unforgettable adventure! Our "
          "high-speed racing kart experience is perfect for corporate events, birthday parties, and group outings. "
          "Challenge your colleagues or friends to a thrilling competition, reaching speeds of over 50mph on our "
          "professional-grade track. Our expert staff ensure a safe and enjoyable experience for all.")

FECHO_DUVIDAS = ("Do you still have questions?",
                 "Contact our team by clicking the button below to get all the information about our products and services.")

# ------------------------------------- Arrive and Drive (urace.us/services/arrive-and-drive/ e o produto 4787)
# #254 (dono, 15/10): *"o professional coaching se tornou o arrive and drive"* — o texto que fazia sentido da
# página /services/professional-coaching/ entrou aqui; a página antiga virou 301 para esta.
# Preços e idades: as variações do produto 4787 que o site público mostra (Store API pública).
# A "Your Own Kart" ($500) existe no WooCommerce mas não aparece no site, então também não aparece aqui.
#
# #263 (dono, 15/10): `nome` é a **chave do kart**. É ela que viaja no `?kart=` da reserva e é ela
# que o painel guarda em `booking_services.site_kart` para dizer "este serviço é deste kart". O site
# casa serviço e kart por essa chave, igual e exata — nunca por "o nome do serviço contém o nome do
# kart", que foi o que fez um serviço chamado "teste" aparecer como se fosse o produto.
# Trocar o nome de um kart aqui é trocar a chave: o `site_kart` dos serviços muda no mesmo passo
# (`test_servico_do_kart.py` tranca).
AVISO_KART_PROPRIO = ("Your kart must arrive at the track at least 2 days before your session, so our mechanics can "
                      "check it and do the necessary maintenance.")

# #279 (dono, 15/10): "o lead and follow é um add on que pode ser adicionado no dia de treino … somente o de 769
# por dia de treino". É um serviço do painel (preço do painel, #50) ligado por esta chave, como os karts.
LEAD_AND_FOLLOW = {"chave": "Lead and Follow", "nome": "Lead and Follow", "preco": 769,
                   "texto": "A partner coach on track with you, for this training day."}

KARTS = (
    {"nome": "Baby Kart", "idade": "Ages 4–7", "min": 4, "max": 7, "preco": 719},
    {"nome": "4-stroke", "idade": "Ages 7+", "min": 7, "max": None, "preco": 719},
    {"nome": "2-stroke", "idade": "Ages 7+", "min": 7, "max": None, "preco": 819},
    {"nome": "Adult Shifter", "idade": "Ages 14+, experience required", "min": 14, "max": None, "preco": 899},
    # #279 (dono, 15/10): "sim como a 5 opção e coloque um warning que o kart precisa ser enviado com no mínimo
    # 2 dias de antecedência para ser checado e feito a manutenção necessária". Preço e idade da planilha
    # ("Using Own Kart (all categories) · 4 years and up · $500"). Sem depósito: o depósito reembolsável cobre
    # o kart da URACE, e aqui o kart é do cliente (o gerente muda no painel, se quiser).
    {"nome": "Own kart", "idade": "Ages 4+ · all categories · you bring your kart", "min": 4, "max": None,
     "preco": 500, "deposito": 0, "proprio": True, "aviso": AVISO_KART_PROPRIO},
)

ARRIVE = {
    "caminho": "/services/arrive-and-drive/",
    "titulo": "Arrive and Drive Kart Racing in Orlando | URACE",
    "descricao": ("Drive a real racing kart in Orlando. Kart, safety gear and professional coaching included - bring "
                  "nothing. No licence needed. Book your session."),
    "eyebrow": "Kart Arrive and Drive in Orlando",
    "h1": "Live the real Kart Racing Experience in Orlando",
    "sub": ("Feel the speed, control the kart, and enjoy a full track day with professional equipment and coaching — "
            "with video and data analysis to sharpen your technique. No license required."),
    "foto": "arrive-and-drive-hero.webp",
    "foto_equipe": "arrive-and-drive-equipe.webp",
    # #254: os quatro últimos vêm do "What to expect from your Coaching Session" da página de
    # Professional Coaching, que se fundiu aqui (dono, 15/10).
    "esperar": ("Feel the rush of real speed. Up to 70 MPH on a pro racing track",
                "Get race-ready with a safety + driving technique briefing from expert coaches",
                "Suit up and strap in: this isn’t a theme park ride, it’s the real thing",
                "Create unforgettable memories for families, friends, and adrenaline junkies alike",
                "Walk away buzzing with adrenaline, confidence, and maybe a new obsession",
                "A training program tailored to the driver’s level",
                "Professional coaching, data and video analysis",
                "Technique and mindset training",
                "Performance tracking, session after session"),
    "fornece": ("The high performance go-kart", "Safety instructions", "Safety equipment.",
                "Expert coaching from professional instructors"),
    "trazer": ("MUST wear long pants, closed toe shoes and a jacket.", "Make a reservation",
               "Come prepared for fun and leave with lasting smiles"),
    "porque": ("Real Racing Karts – Not slow rental karts.", "Feel Like a Racer - This is the real deal.",
               "Just Arrive & Drive – No prep, no hassle.", "Pro-Level Track",
               "Gear up, get briefed, go fast – We handle everything.",
               # #254: do "Real coaching from a championship-level kart team" da página de coaching
               "Theory and mechanics simplified", "Mentorship by winning drivers",
               "Confidence, reflexes and racing mindset"),
    "porque_fecho": "Ready to feel what real racing is like? Spots are limited.",
    "quem": ("Adults and kids looking for real speed", "Racing fans visiting Orlando", "Families seeking next-level fun",
             "First-timers curious about karting",
             # #254: a página de coaching era para quem já corre
             "Drivers who already race and want to find real lap time",
             "Drivers aiming for confidence, speed and race results"),
    # os 3 primeiros passos são os da reserva do site (agenda e área do cliente); o resto é o texto do site atual
    # #262 (dono, 15/10): um caminho só — carrinho → conta → Stripe → waiver. Nada de invoice no site.
    "passos": ("Pick your kart, your day and morning or afternoon, and add it to your cart",
               "Sign in or create your account and add your drivers",
               "Tell us if you want Lead and Follow ($769) — a coach on track with you — and we add it to your session",
               "Pay with Stripe (card, Apple Pay or Google Pay) and sign the driver’s waiver in your account — "
               "your spot is confirmed",
               "Arrive 10 minutes early. Check in, get settled, feel the excitement building.",
               "Gear up + Safety Briefing",
               "Hit the track. Time to feel the speed, the grip, the thrill — like a real racer.",
               "Enjoy the speed and excitement. It’s just the beginning!",
               "Schedule your next race. Already hooked? Let’s get your next session booked and keep the adrenaline going!"),
    "faq": (
        ("The experience",
         ("Are you visiting Orlando and looking for something more exciting than the go karts at Magic Kingdom’s "
          "Tomorrowland Speedway or the monotony of Epcot’s Test Track? This experience is for kids and adults, all ages "
          "are welcome!",
          "Book your reservation and be ready to have a blast!",
          "These are not the typical put-put go-karts, they are authentic, professional racing karts.",
          "We will start by providing safety and driving technique instructions, after the first instructions you will have "
          "3 or 6 10 minutes driving sessions, according to your choice. The experience total time, will be around 2h for "
          "3 sessions and 4-5 h for 6 sessions from arrival until the end.",
          "Available Experience Days: Experiences are available every day, 8 AM – 8 PM. Please confirm availability when "
          "booking.")),
        # #254: o que a página de Professional Coaching dizia. #273 (dono, 15/10): o Lead and Follow é um add-on
        # do dia de treino — Arrive and Drive ou Academy — e no site vale só o de $769 por dia de treino.
        ("Coaching, data and Lead and Follow",
         ("Our teaching method includes data analysis, on-board video study and explanation of the theories involved in "
          "all the driving aspects we discuss: the driver leaves knowing what to change, not only how fast they went.",
          "Lead and Follow is an add-on for any training day — Arrive and Drive or URACE Academy: a partner trainer on "
          "track with you, if you don’t wanna do it alone. It is $769 per training day.",
          "All weekday training sessions must be confirmed by Sunday. All weekend sessions must be confirmed 24h in "
          "advance. Please call if you have any questions.")),
        ("Track fees (paid to the Orlando Kart Center)",
         # dono, 20/10: "siga o do robô" (os mesmos valores que o robô SDR diz no chat)
         ("Driver pass Monday to Friday $90.", "Driver pass Saturday and Sunday $65.",
          "Spectator pass $5, charged directly by the track.")),
        *FAQ_COMUM,
    ),
    "depoimentos": DEPOIMENTOS_EVENTOS,
    "fecho": "If you're serious about racing, this is where it starts. Shall we begin?",
    "fecho_sub": "With an affordable price aimed at the democratization of Karting.",
}


def preco_minimo():
    """O "a partir de" do site é o aluguel do kart da URACE: o kart próprio (#279) não entra, senão o
    site anunciaria $500 para quem não tem kart."""
    return min(k["preco"] for k in KARTS if not k.get("proprio"))


def kart_da_chave(chave):
    """O kart do site com essa chave, sem distinguir maiúscula nem espaço à toa. None se não é kart."""
    c = " ".join(str(chave or "").split()).lower()
    return next((k for k in KARTS if k["nome"].lower() == c), None)
