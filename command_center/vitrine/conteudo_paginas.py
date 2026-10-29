"""As páginas institucionais do site novo (#164) com o texto do urace.us de 13/10/2026 (#207): Academy,
Pro Team, For Beginners, Career (Plan Your Career), Contact e Accessibility. As landings de anúncio e a The Driver
Factory são páginas próprias de novo (#506, `pg_landings.py`); a About é por blocos (#507, `pg_home.py`).

Nada inventado: cada texto saiu da página citada. Correções de propósito: endereço com o Box 3
(decisão de 01/10); o telefone da acessibilidade era "205 2291" no site antigo e aqui é o da
empresa, (407) 250 2291; remarcação com 24 h e as idades dos karts do produto (dono, 08/10); os
botões de comprar levam à reserva do site. Preço de serviço não é texto fixo: os planos vêm do painel
(Site › Serviços) e o Arrive and Drive de `conteudo.KARTS`; o que o sistema não tem fica sem preço.
"""
from command_center.vitrine.conteudo import AVALIACOES, FAQ_EVENTO, FECHO_DUVIDAS, GOOGLE, LIGACAO, SITE  # noqa: F401

RESERVAR = "/ops/portal/reserve"
CONTATO = "/contact/"

MAIS_TITULO = "More than a karting school. We develop drivers."
MAIS = ("URACE is a driver development program based in Florida, created to guide young drivers through every stage of "
        "their motorsport journey. From the first experience behind the wheel to competitive racing, we provide "
        "professional coaching, structured development, mentorship and racing opportunities.",
        "Because becoming a driver requires more than speed. Motorsport develops discipline, focus, decision-making, "
        "emotional control and a competitive mindset — skills that matter on the track and far beyond it.",
        "We are the first step toward becoming a professional racing driver.")

FECHO_PROXIMO = ("Every driver has a next step. Let's find yours.",
                 "Whether you want to experience karting for the first time, begin structured driver development or pursue "
                 "higher levels of competition, URACE is ready to help you move forward.")

# ------------------------------------------------------------------ Academy (urace.us/urace-academy/ + /services/)
# #254 (dono, 15/10): *"o kart school se tornou Urace academy"* — o texto que fazia sentido da página
# /services/kart-school/ entrou aqui, e aquele endereço virou 301 para esta página.
ACADEMY = {
    "caminho": "/academy/",
    # #506: /kart-training-packages/ e /kart-driving-school/ são landings próprias de novo (pg_landings.py)
    "antigos": ("/urace-academy/", "/services/kart-school/"),
    # #508: o texto do urace.us de 29/10 (urace.us/urace-academy/): hero, currículo, planos, avaliações e o próximo passo
    "titulo": "URACE Academy: Kart School in Orlando | URACE",
    "descricao": ("URACE Academy is our kart school at Orlando Kart Center: monthly coached training on our karts and "
                  "equipment, with no big upfront investment."),
    "eyebrow": "Step 3 · URACE Academy · Orlando",
    "h1": "URACE Academy. Kart school in Orlando.",
    "sub": ("Four coached sessions a month with kart, full equipment, maintenance and a professional coach included. "
            "Month to month, no minimum term."),
    "foto": "imagem-segunda-dobra.webp",
    "cta": ("Join the Academy", RESERVAR + "?service=academy"),
    "cta2": ("Talk to us", LIGACAO),
    "curriculo_rotulo": "Curriculum",
    "curriculo_titulo": "Real coaching. Not just seat time.",
    "curriculo_itens": ("Acceleration, braking, cornering and racing technique.",
                        "Racing principles, track dynamics and safety protocols.",
                        "Setup, adjustments and performance, so the driver understands the kart.",
                        "Structured on-track sessions with real-time coaching and feedback."),
    "planos_rotulo": "Plans",
    "planos_titulo": "Pick your pace",
    "planos_sub": "The longer you commit, the less each session costs.",
    # o "Not sure yet?" da página de hoje: o preço é o do Arrive and Drive no painel (o menor kart), nunca texto
    "primeiro": ("Not sure yet?", "Start with one Arrive and Drive session. Your coach reads the data and tells you "
                 "straight which plan fits.", "+ refundable deposit", ("Book a first session", "/services/arrive-and-drive/#reservar")),
    # Só aparecem sem plano cadastrado no painel; aí o botão abre o contato. O texto é o do site atual,
    # sem os valores por sessão (o preço do plano é o do painel).
    # #273 (dono, 15/10): a planilha de preços é a fonte, e a Academy tem preço próprio para 4 stroke (e Baby
    # Kart) e para 2 stroke — "veja que tem academy para 4t e 2t". As contas batem com 4 × sessão,
    # 27 × sessão × 0,96 e 54 × sessão × 0,92, com entrada de 33% / 20% (test_vitrine trava). Saíram
    # 3 Months, 6 Months a 5% e o URACE Boost: não estão na planilha.
    # #390 (dono, 22/10: *"o texto maior seja sempre o valor do mes nao o total pois o total pode assustar"*): no
    # contrato, o preço grande é a parcela do mês; embaixo dele, o total e quanto economiza (dono: "o texto abaixo do
    # valor explicando o total a quantidade de desconto"); a entrada fica no texto.
    # grupo: (título, [(nome, sub, texto, preço, por)])
    "planos_grupos": (
        ("4-stroke and Baby Kart · $689 per session", (
            ("No contract", "4 sessions a month",
             "Kart, full safety equipment, maintenance and a professional coach included. No minimum term — cancel any "
             "time with thirty days written notice. Additional sessions $689 each.", "$2,756", "per month"),
            ("6-month contract", "27 sessions · 4% off",
             "$5,893.43 at signing (33%), then 5 monthly installments of $2,393.09. Contract total $17,858.88 "
             "(regular value $18,603.00). Recurring billing.", "$2,393.09",
             "per month · contract total $17,858.88 · you save $744.12 (4% off)"),
            ("12-month contract", "54 sessions · 8% off",
             "$6,845.90 at signing (20%), then 11 monthly installments of $2,489.42. Contract total $34,229.52 "
             "(regular value $37,206.00). Recurring billing.", "$2,489.42",
             "per month · contract total $34,229.52 · you save $2,976.48 (8% off)"))),
        ("2-stroke · $789 per session", (
            ("No contract", "4 sessions a month",
             "Kart, full safety equipment, maintenance and a professional coach included. No minimum term — cancel any "
             "time with thirty days written notice. Additional sessions $789 each.", "$3,156", "per month"),
            ("6-month contract", "27 sessions · 4% off",
             "$6,748.79 at signing (33%), then 5 monthly installments of $2,740.42. Contract total $20,450.88 "
             "(regular value $21,303.00). Recurring billing.", "$2,740.42",
             "per month · contract total $20,450.88 · you save $852.12 (4% off)"),
            ("12-month contract", "54 sessions · 8% off",
             "$7,839.50 at signing (20%), then 11 monthly installments of $2,850.73. Contract total $39,197.52 "
             "(regular value $42,606.00). Recurring billing.", "$2,850.73",
             "per month · contract total $39,197.52 · you save $3,408.48 (8% off)"))),
        ("Your own kart · no contract", (
            ("Your kart", "4 sessions a month",
             "You bring the kart; we bring the coaching, the track day and the support. Additional sessions $450 each.",
             "$1,800", "per month"),
            ("Your kart and your mechanic", "4 sessions a month",
             "You bring the kart and your mechanic; we bring the coaching and the track day. Additional sessions $300 each.",
             "$1,200", "per month"))),
    ),
    # #508: a página de hoje do urace.us é curta; o que é informação prática da página antiga (o que o plano inclui, o
    # que trazer e como entrar) fica aqui, na FAQ
    "faq": (("What the plan includes", ("Kart: High-performance kart provided for each session.",
                                        "Coach: Expert coaching from professional instructors.",
                                        "Mechanic: On-site mechanical support to keep the kart race-ready.",
                                        "Career planning: Ongoing guidance from your career specialist.",
                                        "In-depth safety instructions.", "Driver Pass: Access to the track for the driver.",
                                        "1 Guest Pass: Bring one guest (family or friend) to accompany and support you "
                                        "(Additional guests subject to track pass price).")),
            ("What to bring", ("MUST wear long pants, closed toe shoes and a jacket.",)),
            ("How joining works", ("Choose your plan above — the longer you commit, the less each session costs.",
                                   "Sign in or create your URACE account and tell us who the driver is (height and weight, "
                                   "so the kart is prepared).",
                                   "Pay the first month online and sign the waiver.",
                                   "Your four sessions a month are scheduled once a week, with your coach. Arrival at the "
                                   "track is 8 am.")),
            ("Add-ons, travel and track fees", (
                # #273: da planilha de preços do dono (15/10)
                "Lead and Follow is an add-on for any training day: a partner trainer on track with the driver, for $769 per training day.",
                "Academy services provided outside of the Orlando Kart Center are charged an extra $250 for hotel, food and transport.",
                "Track fees are not included in the price and must be paid directly to the track.")),
            ("A complete racing education", (
                # da Kart School (#254): "URACE Kart School" virou "URACE Academy" e "novice drivers" saiu,
                # porque a Academy é para quem já teve o primeiro dia de kart
                "Embark on a comprehensive racing education with the URACE Academy, designed for drivers eager to excel. "
                "Our structured program combines theoretical knowledge with hands-on training, equipping students with the "
                "skills and confidence to succeed.",)),
            ("Why motorsport builds champions", (
                "Karting looks like a hobby from the outside, but the skills it demands behind the wheel are the ones researchers "
                "tie to healthy child development. A young driver is constantly reading the track, adjusting their line, and "
                "making split-second calls under pressure — fast, consequence-driven decision-making that's hard to practice "
                "anywhere else.",
                "The research on youth sport backs this up. A large study published in PLOS One found sport's overall impact on "
                "child development is strongly positive, including gains in self-esteem and communication. A separate study "
                "comparing competitive athletes to recreational and instructional-level peers found the competitive group scored "
                "significantly higher on cognitive skills and goal-setting. And researchers who study youth sport broadly — "
                "including work out of Texas A&M — point to competition itself as a key driver of resilience: learning to lose a "
                "race, work out what went wrong, and come back faster teaches persistence in a way few other childhood "
                "activities do.",
                "At URACE Academy, every session is built around that exact process. Coaches don't just teach a driving line — "
                "they walk each driver through onboard video and lap-time data, then set a specific target for the next session. "
                "It's the same cycle of goal-setting, performance, and reflection the research points to, just happening at 50 mph.",
                "We're not claiming karting replaces coaching, school, or therapy. But for a sport that asks a 7-year-old to "
                "process more information per second than almost any other youth activity, it's hard to find a better training "
                "ground for focus, composure under pressure, and the discipline to keep improving.")),
            ("Terms and conditions", (
                "The program price is URACE’s fee for coaching, trackside support, kart rental, driver and one guest pass only; "
                "anything not in this list is excluded.",
                "This training consists of 4 days per month to be scheduled once/week, each day consists of 6 sessions of 10 "
                "minutes each session, or a total 1 hour of track time/day. The arrival time at the track is 8 am. We kindly "
                "request that you arrive on time. If less than 40 minutes of track time is achieved, there is a possibility of "
                "receiving a proportional credit for a future session. Each case will be decided individually based on the "
                "reason for not meeting the minimum track time.",
                "Any damages caused to the kart are not included in this price, regardless of the driver's fault or not in the "
                "incident, and will be billed to you for the costs of repair. Clarifying: If the kart breaks down and it was not "
                "caused by the driver, (crash, going off of the track or aggressive driving style) the costs of repair will be "
                "covered by URACE. If the kart gets damaged in the result of a crash, regardless of driver's fault in the "
                "incident, the costs of repair will be billed to you. Understanding why: Each driver in a race track is fully "
                "liable for his own equipment and safety. Meaning, even if someone else crashes into you or your child, you are "
                "responsible for your and or child's equipment. You are not responsible for the other person in the other kart, "
                "nor the other person's equipment even if you or your child caused the incident.",
                "Kids under 10 years old must be accompanied by an adult. We provide a childcare assistant for an extra $200/day "
                "in case you are unable to stay with your child. This service must be requested beforehand.")),
            ("Refund and rescheduling policy", (
                "Our service requires planning, preparation, coordination and transportation to the track on our end; for those "
                "reasons we do not offer refunds. Rescheduling is available with a minimum notice of 24 hours. With less than "
                "24 hours' notice, a flat fee of $95 is charged, plus the Driver Pass if required. To avoid this fee, we "
                "recommend notifying us of any changes at least 24 hours in advance.",
                "Please note that if a training session needs to be rescheduled due to circumstances outside of URACE's control, "
                "a fee will be charged to cover personnel costs. This fee will be in addition to any other costs associated with "
                "the session itself. By using URACE's services, you agree to this policy and understand that rescheduling fees "
                "may apply.")),
            ("Cancelling the plan", ("Renews month by month; cancel with 30 days written notice.",))),
    "fecho": "When you are ready: the Racing Team",
    "fecho_sub": "Race-team program for regional, national and international grids. Your coach tells you when.",
    "fecho_cta": ("See the Racing Team", "/pro-team/"),
}

# ------------------------------------------------------------------ Pro Team (urace.us/pro-team/)
# #506: /professional-kart-team-racing-team/ é landing própria de novo (pg_landings.py), não mais 301 para cá
PRO_TEAM = {
    "caminho": "/pro-team/",
    # #508: o título e a descrição do urace.us de 29/10
    "titulo": "URACE: Professional Kart Racing Team in Florida",
    "descricao": ("The URACE team runs race weekends in SKUSA, USPKS and Florida series, with kart prep, mechanics and "
                  "coaching, on the path to F1, NASCAR, IMSA and IndyCar."),
    "eyebrow": "Driver Development · Orlando, FL",
    "h1": "You already race. Now race with a team behind you.",
    "sub": ("URACE prepares the kart, runs the race weekend and puts a professional coach alongside the driver — based at "
            "the Orlando Kart Center and entered in the Florida and national calendars."),
    "foto": "banner-topo-lp-urace-1.webp",
    "cta": ("Talk to our racing team", CONTATO),
    "cta2": ("Book a call", LIGACAO),
    "metodo": ("Our teaching method includes data analysis, on-board video study and explanation of the theories involved "
               "in all the driving aspects we discuss. We offer full support for local, regional and national events."),
    "suporte_titulo": "Professional Kart Racing Team",
    # o site atual só descreve o primeiro; os outros são só o título
    "suporte": (("Travel logistics", "We handle everything, you only need to book your flights and hotel."),
                ("Equipment prep", ""), ("Engineering", ""), ("Coaching", ""), ("Hospitality", ""), ("High speed wifi", "")),
    "mais_titulo": MAIS_TITULO,
    "mais": MAIS,
    "opcoes_titulo": "How we work with competitive drivers",
    "opcoes_sub": "Two ways in, depending on where the driver is today.",
    # (nome, sub, texto, preço, por, link): o preço "academy"/"boost" é o do plano no painel; sem plano, sem preço
    "opcoes": (("URACE Academy", "Not racing yet? Start here.", "Four coached sessions a month with kart, full equipment, maintenance and a professional coach included. Month to month, no minimum term.", "academy", "Per month", "/academy/"),
               ("Race Weekend Support", "We run the kart. You drive.", "Kart preparation and trackside support at the rounds we are entered in. Race entries, tyres, fuel and consumables are quoted per event and are not part of the fee.", "Let’s talk", "Per event", CONTATO)),
    # #508: como no urace.us de 29/10. A prova que já passou sai sozinha da lista (paginas_site._proximas)
    "calendario_rotulo": "Where we are racing",
    "calendario_titulo": "Next rounds on the calendar",
    "calendario_sub": "If your driver comes with us, this is the season. Dates and venues as published by the series.",
    "calendario": (("Oct 18, 2026", "SKAPA Winter Series — Rounds 4 & 5"),
                   ("Oct 25, 2026", "AMR Karting Challenge — Round 9, Homestead, Florida"),
                   ("Nov 22, 2026", "AMR Karting Challenge — Round 10, Homestead, Florida"),
                   ("Dec 6, 2026", "Florida Karting Championship — Rounds 11 & 12, AMR Motorplex"),
                   ("Jan–Mar 2027", "SKUSA Winter Series and Florida winter rounds")),
    "fecho": "Future pros start here.",
    "fecho_sub": " ".join(FECHO_PROXIMO),
    "fecho_cta": ("Talk to our racing team", CONTATO),
}

# ------------------------------------------------------------------ For Beginners (urace.us/for-beginners/)
# #506: /kart-lessons-for-beginners/ é landing própria de novo (pg_landings.py), não mais 301 para cá
BEGINNERS = {
    "caminho": "/for-beginners/",
    "titulo": "How to Get Into Karting - Start in Orlando | URACE",
    "descricao": ("Never driven a race kart? Start here. How karting works, what to expect on your first day in Orlando, "
                  "and the path from first lap to competition."),
    "eyebrow": "For Beginners",
    "h1": "How to Get Into Karting in Orlando",
    "sub": "(All ages)",
    "foto": "banner-topo-lp-urace-1.webp",
    "cta": ("I want to start karting!", "/services/arrive-and-drive/"),
    "primeira_titulo": "First time in a kart?",
    "primeira": ("No stress. We've got you covered. From safety gear to first-time instructions, our team guides every step so "
                 "you can focus on enjoying the ride, learning, and discovering what you're made of.",
                 "At URACE, beginners are treated like future athletes. Our method is structured and serious, for kids who want "
                 "to start young or adults ready to take on a new challenge.",
                 "You'll learn real technique from day one: driving position, control, racing discipline, and decision-making. "
                 "You'll build the right foundation to progress with confidence."),
    "contato_titulo": "Arrive and Drive: First contact with karting",
    "contato": ("Personalized coaching with a dedicated professional coach, designed to accelerate driver development through "
                "structured training, advanced telemetry, technical analysis, and precise driving corrections. Each session "
                "focuses on building correct technique, consistency, and confidence on track. Ideal for drivers who want to "
                "train with purpose, evolve continuously, and reduce lap times with a high-performance approach.",),
    "contato_cta": "Schedule now",
    "proximo_titulo": "Where are you in your racing journey?",
    # (nome, sub, texto, preço, link, botão): "kart" = o menor preço de KARTS; os outros não têm preço no sistema
    "proximo": (("Arrive & Drive", "Experience karting for one day.", "Your first opportunity to experience real karting with professional guidance and URACE support. Perfect for first-time drivers and families who want to discover motorsport.", "kart", "/services/arrive-and-drive/", "Experience karting"),
                ("URACE Academy", "Start your development as a racing driver.", "A structured driver development program for young athletes who want to train, improve and build the foundations required for competitive karting — with professional coaching, track experience, evaluation and mentorship.", "", "/academy/", "Join URACE Academy"),
                ("Racing Team", "Already competing? Pursue the next level.", "Professional support for competitive drivers who want to improve their performance and pursue higher levels of motorsport — coaching, race preparation, competition experience and professional guidance.", "", "/pro-team/", "Talk to our racing team")),
    # perguntas de urace.us/plan-your-career/ (idades: decisão do dono de 08/10)
    "faq": (("How do I get my child into racing?", ("From four years old a child can drive a Baby Kart and learn driving lines and fundamentals. From seven they fit a 4-stroke, and from fourteen, with experience, the Adult Shifter. Start with one day — a race kart, full gear, a coach watching — and let the coach and the data tell you whether there's something there. Children under ten must be accompanied by an adult at the track. If they love it and want more, the Academy turns one good day into a monthly plan.",)),
            ("How do I know if my kid has potential?", ("Lap time on day one tells you almost nothing. What a coach reads is how fast a driver corrects a mistake, whether they repeat it, and how they behave when the session goes badly. That's visible within a few runs, and it's visible in the data rather than in opinion. We'll tell you what we saw honestly — including when the answer is that your child loves driving and isn't a future professional, which is a perfectly good answer.",)),
            ("Am I too old to start racing?", ("For Formula 1, almost certainly — that ladder is normally climbed from childhood. For racing itself, no. Masters karting categories exist precisely for adult drivers, and adults often learn the technical side faster than children because they can absorb data and theory. If your goal is to race competitively, be good, and enjoy it, age is not the barrier. If your goal is a professional seat, we'll tell you straight what's realistic.",)),
            ("What do I need to bring?", ("Long pants, closed toe shoes and a jacket. We provide the kart, the safety equipment and the instructions.",))),
    "fecho": FECHO_DUVIDAS[0],
    "fecho_sub": FECHO_DUVIDAS[1],
    "fecho_cta": ("Talk to us", CONTATO),
}

# ------------------------------------------------------------------ Career (urace.us/plan-your-career/)
# #506: a The Driver Factory voltou a ser página própria (pg_landings.py), com o título e a descrição dela no urace.us;
# o /career/ é o /plan-your-career/ (o endereço que ele substitui), com o título e a descrição de lá.
CAREER = {
    "caminho": "/career/",
    "antigos": ("/plan-your-career/",),
    # #508: o título e a abertura do urace.us de 29/10 (urace.us/plan-your-career/)
    "titulo": "Racing Career Path to F1, NASCAR, IMSA & IndyCar | URACE",
    "descricao": ("Plan a racing career step by step, from Sim2Grid and URACE Academy in Orlando to Formula 1, NASCAR, IMSA "
                  "or IndyCar."),
    "eyebrow": "Career plan · Orlando",
    "h1": "How to become a racing driver: one ladder. Start at the bottom.",
    "sub": ("Every pro climbed the same ladder. Here it is, from a sim seat in Orlando to F1, IndyCar or NASCAR. We run "
            "the bottom rungs and get drivers ready for the rest."),
    "foto": "enzo-1.webp",
    "cta": ("Find my next step", CONTATO),
    "degraus_titulo": "The ladder ends on our grid",
    "degraus_intro": ("Sim 2 Grid. Arrive and Drive. URACE Academy. URACE Racing Team. Four steps, one team. Nobody skips to "
                      "the top and nobody buys their way in — your coach tells you when you are ready, and not before."),
    "degraus": (("Sim 2 Grid", "Opening 1 November 2026. A full motion cockpit — competition seat and harness, direct-drive wheel, racing pedals, triple screen.", "/sim2grid-racing-simulator/"),
                ("Arrive and Drive", "Experience karting for one day. Your first opportunity to experience real karting with professional guidance and URACE support.", "/services/arrive-and-drive/"),
                ("URACE Academy", "Start your development as a racing driver. Four coached sessions a month.", "/academy/"),
                ("Racing Team", "Already competing? Pursue the next level.", "/pro-team/")),
    "perguntas_titulo": "Questions people actually ask",
    "perguntas_sub": "Straight answers, including the ones that cost us a sale.",
    "faq": (("Does my kid show potential?", ("There’s one honest way to find out, and it isn’t a quiz. Put them in a real race kart with a coach watching, and read the data afterwards. One day tells us more than a year of wondering — and we’ll tell you what we actually saw, including when the answer is “they love it, and that’s enough”.",)),
            ("I’m over 18 — is it too late?", ("For Formula 1, honestly, yes: that route is built around drivers already karting at ten, and it closes in your teens. For racing, no. Stock cars and sports cars have no age-gated junior ladder, and Masters leagues exist precisely for drivers who started as adults. We coach adults and seven-year-olds on the same day, on the same circuit. The ladder asks whether you learn the technical way, not when you were born — and that is teachable at any age. And if you already race, you skip the simulator and the Academy entirely.",)),
            ("How do I become a racing driver?", ("You start in a kart, you get coached, and you build a record that the next category will look at. There is no shortcut and no talent-spotting shortcut either — every professional on a grid today climbed the same kind of ladder, one paid rung at a time. What changes between drivers is how early they start, how good the coaching is, and how well the season is planned. The cheapest honest first move is a simulator hour or a single day in a race kart, because both tell you whether you want the next rung before you’ve spent anything serious.",)),
            ("How do I get my child into racing?", ("From four years old a child can drive a Baby Kart and learn driving lines and fundamentals. From seven they fit a 4-stroke, and from fourteen, with experience, the Adult Shifter. Start with one day — a race kart, full gear, a coach watching — and let the coach and the data tell you whether there’s something there. Children under ten must be accompanied by an adult at the track. If they love it and want more, the Academy turns one good day into a monthly plan.",)),
            ("How do I know if my kid has potential?", ("Lap time on day one tells you almost nothing. What a coach reads is how fast a driver corrects a mistake, whether they repeat it, and how they behave when the session goes badly. That’s visible within a few runs, and it’s visible in the data rather than in opinion. We’ll tell you what we saw honestly — including when the answer is that your child loves driving and isn’t a future professional, which is a perfectly good answer.",)),
            ("Am I too old to start racing?", ("For Formula 1, almost certainly — that ladder is normally climbed from childhood. For racing itself, no. Masters karting categories exist precisely for adult drivers, and adults often learn the technical side faster than children because they can absorb data and theory. If your goal is to race competitively, be good, and enjoy it, age is not the barrier. If your goal is a professional seat, we’ll tell you straight what’s realistic.",)),
            ("How do I get into NASCAR?", ("The stock car route leaves karting earlier than the open-wheel ones. A driver typically moves from karting into Legends or Bandolero cars, then regional Late Models, then the ARCA Menards Series, then NASCAR’s three national series in order: the Craftsman Truck Series, the Xfinity Series, and the Cup Series. Because the branch happens young, the decision about which destination you’re aiming at matters earlier than most families expect.",)),
            ("How do I get to IndyCar?", ("Through the Road to Indy, which is the most clearly defined ladder in motorsport: USF Juniors, then USF2000, then USF Pro 2000, then Indy NXT, then IndyCar. Each rung has a scholarship structure attached to winning it, which makes it the cheapest of the single-seater paths to a top-level seat — and the reason we map American drivers onto it early.",)),
            ("How do I get to Formula 1?", ("Karting, then Formula 4, then Formula Regional, then FIA Formula 3, then FIA Formula 2, then one of twenty seats in the world. It is the longest and most expensive of the three routes and the one where a karting record counts for most, which is why drivers aiming at it start young and race nationally as early as they can. Nobody can promise this rung. What can be promised is that every rung below it is real and that the climb is known.",)),
            ("Can a simulator really prepare you for real racing?", ("For circuit knowledge, braking points and racecraft, yes — our own drivers learn a circuit on the simulator before they ever see it. A full motion cockpit loads the driver up in the corners and punishes the same mistakes a real car does. What it can’t teach is the physical load of a real race weekend, which is why it’s the first rung and not the only one. It is, though, the only rung with no track fee, no equipment and no weather.",)),
            ("Where are you based?", ("We operate at the Orlando Kart Center, 10724 Cosmonaut Blvd, Orlando FL 32824 — an 8/10 mile professional kart circuit just off the Florida Turnpike, minutes from most of Orlando’s attractions. URACE is a racing team, not the racetrack: we provide coaching and programs at a third-party circuit and follow their rules and operating hours.",))),
    "pessoa_titulo": "We are building a person, not only a driver",
    "pessoa": ("Karting looks like a hobby from the outside. What it actually asks of a seven-year-old is to read a track, adjust a line, and make consequence-driven decisions at speed, over and over, for an hour. There are very few childhood activities that demand that much processing per second.",
               "A large study published in PLOS One found sport’s overall impact on child development is strongly positive, including gains in self-esteem and communication. A separate study comparing competitive athletes to recreational and instructional-level peers found the competitive group scored significantly higher on cognitive skills and goal-setting. And researchers who study youth sport — including work out of Texas A&M — point to competition itself as a key driver of resilience: learning to lose a race, work out what went wrong, and come back faster teaches persistence in a way few other childhood activities do.",
               "Every URACE session is built around that cycle. A coach doesn’t only teach a driving line — they walk the driver through onboard video and lap-time data, then set one specific target for next time. Goal, attempt, review, adjust. It happens to be happening at 50 mph.",
               "We’re not claiming karting replaces school, coaching or therapy. We’re saying the driver who comes back to you is more focused, steadier under pressure and harder to rattle — and that part is yours to keep whether or not they ever reach a professional grid."),
    "fotos": (("enzo-1.webp", "Enzo Vidmontiene, URACE driver"), ("leonardo-1.webp", "Leonardo Escorpioni, URACE driver"), ("emmo-2.webp", "Emmo Fittipaldi, URACE driver")),
    "profissional_titulo": "And a professional, not only an athlete",
    "profissional": ("Most people who make a living in motorsport never drive for one. They engineer, they manage, they run teams, they handle the commercial side. A driver who understands that industry is worth more inside it — and has somewhere to go if the seat never comes.",
                     "So we teach the business alongside the driving. From the Academy onward a driver works with a career specialist, not only a coach. By the time they reach the Racing Team, the work is as much about building a professional as a lap time."),
    "profissional_itens": (("Brand & identity", "Helmet and livery design, team kit, the visual identity a driver carries from one category to the next."),
                           ("Press & PR", "How to talk to media, how to handle a bad weekend in public, and advisory for the driver and the family."),
                           ("Social & content", "Building the channels, producing highlight reels and sponsor material that a brand can actually use."),
                           ("Sponsorship", "Shaping the driver’s story and connecting it with brands once there’s a record worth presenting."),
                           ("Season planning", "Which categories, which tracks, what it costs, and how it fits around school and family life."),
                           ("Race craft", "Reading a contract, running a weekend, working with a mechanic and an engineer as a professional does.")),
    "eventos_titulo": "Not on the ladder: groups and corporate events",
    "eventos": ("Bring the whole group. Everyone drives a real race kart on a professional circuit, with our staff running the session start to finish. Birthdays, corporate days, team offsites. This one isn’t a development step — it’s a day out, and it’s meant to be.",),
    "eventos_faq": FAQ_EVENTO,
    "aviso": ("URACE runs the four red rungs. The championships above them are run by their own organisers and governing bodies. "
              "URACE is not affiliated with, endorsed by or a partner of any of them — we prepare and enter drivers, nothing more.",
              "URACE is not the racetrack. We are a racing team providing coaching and programs to racers and enthusiasts at the "
              "Orlando Kart Center, a third-party circuit, and we follow their rules and operating hours. Track fees are charged "
              "by the circuit, separately from URACE services: driver pass $90 Monday to Friday, $65 Saturday and Sunday, "
              "spectator pass $5 — charged directly by the track."),
    "fecho": "You don’t need to know which rung is yours",
    "fecho_sub": ("Tell us who the driver is and whether they’ve been in a race kart before. That one answer decides the rest — "
                  "and we’ll tell you honestly where to start, even if it’s the cheapest rung on the ladder."),
    "fecho_cta": ("Find my next step", CONTATO),
}

# ------------------------------------------------------------------ Contact (urace.us/contact/)
CONTACT = {
    "caminho": "/contact/",
    # #508: o título e a descrição do urace.us de 29/10
    "titulo": "Contact URACE - Professional Racing Team in Orlando",
    "descricao": (f"Talk to URACE about URACE Academy, URACE Sim2Grid or the racing team. Orlando Kart Center, "
                  f"{SITE['endereco']['rua'].split(',')[0]}. Call {SITE['telefone']}."),
    "eyebrow": "Contact",
    "h1": "Talk to URACE",
    "sub": "New lead, question, or planning a group / corporate event? Fill out the form below and our team will get back to you.",
    # #254: não existe mais o programa "Professional Coaching"; o coaching na pista é o Lead and Follow
    "assuntos": (("arrive-and-drive", "Arrive and Drive"), ("sim2grid", "SIM2GRID racing simulator"), ("academy", "URACE Academy"), ("coaching", "Lead and Follow coaching"),
                 ("camp", "Intensive Training Camp"), ("team", "Racing Team"), ("event", "Birthday, corporate or group event"),
                 ("store", "Store: parts, suits and apparel"), ("other", "Something else")),
    "local_titulo": "Location",
}

# ------------------------------------------------------------------ Accessibility (urace.us/accessibility/)
ACCESSIBILITY = {
    "caminho": "/accessibility/",
    "titulo": "Accessibility - URACE",
    "descricao": ("Accessibility statement for URACE, the kart racing school at the Orlando Kart Center. How we work to keep "
                  "the site and the track usable for everyone."),
    "h1": "Accessibility Statement for URACE",
    "texto": ("This is an accessibility statement from URACE.",),
    "conformidade_titulo": "Conformance status",
    "conformidade": ("The Web Content Accessibility Guidelines (WCAG) defines requirements for designers and developers to improve "
                     "accessibility for people with disabilities. It defines three levels of conformance: Level A, Level AA, and "
                     "Level AAA. URACE is partially conformant with WCAG 2.1 level AA. Partially conformant means that some parts "
                     "of the content do not fully conform to the accessibility standard.",),
    "feedback_titulo": "Feedback",
    "feedback": "We welcome your feedback on the accessibility of URACE. Please let us know if you encounter accessibility barriers on URACE:",
    "data_titulo": "Date",
    "data": "This statement was created on 15 April 2026 using the W3C Accessibility Statement Generator Tool.",
}

# ------------------------------------------------------------------ Privacidade e Termos do site (#488)
# O "Privacy policy" do site levava ao documento do app interno (URACE Administrative AI, feito para a Intuit) e o
# "I accept the terms" do cadastro, ao EULA desse app; o urace.us de hoje não tem política nenhuma. Estes textos
# dizem só o que o site faz (o código: conta, piloto, carrinho, Stripe, medição com consentimento, chat do Kommo,
# QuickBooks, e-mail pelo Gmail) e repetem as regras já publicadas nas páginas de serviço. O dono revisa antes da troca.
ATUALIZADO = "October 29, 2026"

PRIVACY = {
    "caminho": "/privacy/",
    "titulo": "Privacy Policy | URACE",
    "descricao": ("How URACE (URACE.US INC, Orlando, FL) collects, uses and protects the information you share on urace.us: "
                  "your account, drivers, bookings, store orders, payments and cookies."),
    "h1": "Privacy Policy",
    "intro": ("This policy explains what information URACE.US INC (\u201cURACE\u201d, \u201cwe\u201d) collects through this "
              "website and our customer area, how we use it and the choices you have. It covers urace.us and the URACE "
              "customer area. Questions: write to support@urace.us or call +1 (407) 250 2291.",),
    "secoes": (
        ("Information you give us", (
            "Account: your full name, email address, password (stored only as a protected hash, never in plain text), "
            "date of birth, phone number and mailing address. The account holder must be 18 or older.",
            "Drivers: the name, date of birth and, when needed for equipment and racewear, the body measurements and sizes "
            "of each driver you add, including children you are responsible for.",
            "Bookings and orders: the sessions, dates, products, options and delivery details you choose, the shipping "
            "address you give at checkout and any notes or messages you send us.",
            "Contact and order request forms: your name, email, phone and message.",
            "Waivers: the participation waiver you sign for each driver, with the date and time of the signature.",
        )),
        ("Payments", (
            "Online payments are processed by Stripe on a secure Stripe page. We do not see or store your full card "
            "number; we receive the payment status, the amount and the name, email and address you give Stripe. "
            "Invoices and receipts are kept in our accounting system (QuickBooks).",
        )),
        ("Cookies and similar technologies", (
            "Essential: cookies that keep you signed in and protect your forms (session and security cookies), remember "
            "your language and keep your cart and campaign source in your browser. The site does not work without them.",
            "Measurement and advertising: Google Tag Manager / Google Analytics, the Meta Pixel and the OpenAI (ChatGPT) "
            "ads pixel load only after you choose Accept in the cookie banner. Decline keeps them off. You can change your choice at any time with "
            "\u201cCookie settings\u201d at the bottom of every page.",
            "Chat: the chat window is provided by Kommo, our customer messaging system, and may set its own cookies when "
            "it loads.",
        )),
        ("How we use your information", (
            "To create and run your account, schedule your sessions, prepare karts and equipment, process payments, "
            "deliver or hand over store orders, send confirmations, receipts and reminders, answer your messages, keep "
            "the required waivers and records, and keep the site secure (for example, limiting repeated attempts).",
            "With your consent to measurement cookies, to understand how the site is used and to measure our advertising.",
            "We do not sell your personal information.",
        )),
        ("Who we share it with", (
            "Only with the service providers that run these tasks for us: Stripe (payments), Intuit QuickBooks "
            "(invoices and receipts), Google (email delivery and, with your consent, analytics), Meta (advertising "
            "measurement, with your consent), OpenAI (ChatGPT advertising measurement, with your consent), Kommo (chat and customer messages) and Asana (scheduling our team). They "
            "process the information to provide their service to us. We may also disclose information when required by "
            "law.",
        )),
        ("Your choices and rights", (
            "You can see and update your account and drivers in the customer area. To request a copy of your information, "
            "a correction or the deletion of your account, write to support@urace.us. We may keep records that the law "
            "or our accounting requires, such as payments, invoices and signed waivers.",
        )),
        ("Security", (
            "The site uses HTTPS, passwords are stored as protected hashes, and access to customer information is "
            "restricted to the URACE team members who need it. No system is perfectly secure; if you think your account "
            "was accessed by someone else, change your password and contact us.",
        )),
        ("Children", (
            "Accounts are opened and managed by adults. A parent or guardian adds a child as a driver and gives the "
            "information needed for the activity.",
        )),
        ("Changes to this policy", (
            f"We will post any change on this page with a new date. Last updated: {ATUALIZADO}.",
        )),
    ),
}

TERMS = {
    "caminho": "/terms/",
    "titulo": "Terms of Use and Sale | URACE",
    "descricao": ("The terms for using urace.us and buying URACE sessions, programs and store products: accounts, payments, "
                  "deposits, rescheduling, refunds, safety and waivers."),
    "h1": "Terms of Use and Sale",
    "intro": ("These terms apply when you use urace.us or the URACE customer area and when you book or buy from URACE.US INC "
              "(\u201cURACE\u201d). By creating an account or completing a purchase you agree to them. Each service page "
              "may add details for that service.",),
    "secoes": (
        ("Your account", (
            "The account holder must be 18 or older and gives true information for themselves and for each driver they add. "
            "Keep your password private; you are responsible for the bookings and purchases made with your account.",
        )),
        ("Prices and payment", (
            "Prices are in US dollars and are the ones shown when you check out. Online payments are made through Stripe. "
            "A booking is confirmed when the payment is completed and the required waiver is signed.",
        )),
        ("Security deposit and damages", (
            "Where a service shows a refundable security deposit, it is charged with the booking to cover potential crash "
            "damage and track fees, and it is fully refunded at the end of the event when there are no incidents or "
            "damages to the kart.",
            "Damage to the kart caused by a crash, going off track or an aggressive driving style is billed to you for the "
            "cost of repair, regardless of fault. Mechanical failures not caused by the driver are covered by URACE.",
        )),
        ("Refunds and rescheduling", (
            "Our services require planning, preparation, coordination and transportation to the track, so we do not offer "
            "refunds. Rescheduling is available with a minimum notice of 24 hours. With less than 24 hours' notice, a flat "
            "fee of $95 is charged, and a Driver Pass, when required, is charged additionally.",
            "Track fees charged directly by the circuit are separate from URACE prices.",
        )),
        ("Monthly programs", (
            "Monthly programs renew month by month until cancelled with 30 days written notice, unless your contract says "
            "otherwise.",
        )),
        ("Store orders", (
            "Store products are sold as described on the product page, while in stock. Shipping, when chosen, is confirmed "
            "by our team. For questions about sizes, availability or a custom order, contact us before buying.",
        )),
        ("Safety and waiver", (
            "Racing is a high-risk activity. Each driver must have a signed participation waiver before driving. Children "
            "under 10 years old must be accompanied by an adult. Follow the instructions of the URACE team and the track at "
            "all times.",
        )),
        ("Using the site", (
            "Do not misuse the site, try to access accounts or information that are not yours, or interfere with its "
            "operation. Content and photos on this site belong to URACE or are used with permission.",
        )),
        ("Contact", (
            "URACE.US INC · 10724 Cosmonaut Blvd, Box 3, Orlando, FL 32824 · +1 (407) 250 2291 · support@urace.us.",
            f"Last updated: {ATUALIZADO}.",
        )),
    ),
}

PAGINAS = (ACADEMY, PRO_TEAM, BEGINNERS, CAREER, CONTACT, ACCESSIBILITY, PRIVACY, TERMS)
