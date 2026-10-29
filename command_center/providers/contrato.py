"""Contrato mensal: quantas sessões o cliente já usou no mês (#61), quanto custa a sessão a mais (#314) e o
contador que o aluno recorrente vê (#340).

Dono, 01/10: *"se ele tivesse um contrato com a gente... as sessões são para ser usadas
naquele mês... ele fica com o contador de quantas sessões daquele mês do contrato já
utilizou. Passou o mês, zera"*.

Dono, 19/10 (#340), mudando a de 01/10 (*"não deixa o cliente ter essa informação"*): *"precisa mostrar tanto
para nos quanto para eles a quantidade de sessões que eles tem pagas ou em aberto, e nao cobrar na marcação e sim
na invoice pelo QuickBooks"*. O contador (`contador`) vai para a área do cliente e para a equipe.

- Sessões por mês: o número do card (`clients.monthly_sessions`); sem número, o padrão da
  Academy (4), que é o que o card já usava.
- **Usadas no mês** são as sessões do Asana do card (as mesmas que o card já contava) **mais**
  os agendamentos do site da conta ligada ao card (não cancelados nem recusados). A conta é
  de cada mês: virou o mês, começa do zero, sem apagar nada.

Dono, 16/10 (#314): *"Quando for cliente do Kart School … pagam pelo QuickBooks. O invoice deles é
recorrente … quando ele for para a área do cliente para ele poder agendar a sessão dele, ele não precisa
efetuar o pagamento, a não ser que as sessões daquele pacote dele … Se ele já tiver usado as sessões
daquele pacote dele mensal, aí ele paga uma sessão adicional. Aí a sessão é dividida pelo valor do
mensal dele … ou então usa aqueles valores que eu te passei."* (Academy e Kart School são a mesma coisa.)

- **Vigente** (`vigente`): o card tem contrato, o plano comprado no site já teve a 1ª mensalidade paga
  e a recorrência (quando existe) não acabou. Pro Racing Driver sem mensal no card não é recorrente: é
  `pro_sem_mensal`, que vai para "Precisa de atenção" e nunca para o carrinho (#340).
- **Vaga do pacote** (`usadas_do_pacote`): conta a sessão do plano; a extra e a paga no Stripe não
  ocupam vaga. Cancelada devolve a vaga do mês. O pacote é por mês (zera no dia 1), também nos
  contratos de 6 e 12 meses.
- **Preço da extra** (`preco_extra`): o valor configurado no card > o do plano > mensal do card ÷
  sessões do mês, em centavos com arredondamento comercial (2.756,90 ÷ 4 = 689,23).
- **Item da extra** (`item_extra`): o do card > o do plano > o item "Extra session" do QuickBooks.
- **Alocar** (`alocar`): por mês e em ordem de data, os dias pedidos ocupam as vagas livres do
  pacote; o resto é extra.

**O contador** (`contador`, #340), por mês e por piloto (cada piloto tem o seu card):

- *Do pacote*: usadas (`usadas_do_pacote`) de Y (`sessoes_por_mes`) e livres (Y − usadas, nunca negativo);
  zera no dia 1.
- *Mensalidade do mês* (`mensalidade_do_mes`): a invoice de mensalidade do QuickBooks daquele mês, pelo espelho
  (memo ou linha com Academy/monthly/training program, mês do memo "[October, 2026]" ou o de emissão; a invoice de
  uma sessão do site — extra ou avulsa — nunca conta como mensalidade). Paga (saldo 0 ou "paid") / aberta / sem
  invoice (None). A mensalidade aberta não trava a marcação (dono, 19/10: *"pode"*): só mostra.
- *Extras do mês*: cada sessão extra do mês e a situação da invoice dela (paga, aberta, ainda sem invoice).
- *Em aberto* (`em_aberto`; dono, 19/10: *"em aberto = sessões que possam ter sido feitas mas não foram pagas
  ainda, isso precisa ser contabilizado pelas invoices do cliente e pelos serviços prestados"*): a sessão já feita
  (serviço prestado: o agendamento do site com data passada e não cancelado/recusado, e a tarefa do Asana do mês que
  conta no card, concluída ou com data passada) que não está coberta por invoice paga. A do pacote (e a do Asana)
  é coberta pela mensalidade do mês dela; a extra e a avulsa pela invoice dela (a do Stripe já entra paga); o
  add-on da sessão do pacote pela invoice dele. O valor em aberto é o saldo das invoices abertas ligadas a essas
  sessões (cada invoice uma vez; o saldo do espelho, senão o total que o QuickBooks devolveu ao criar). Sessão sem
  invoice nenhuma entra como "not invoiced yet", sem valor (NO FAKE DATA). Olha os últimos 3 meses.
"""
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from command_center.db import todos, um

PADRAO_SESSOES = 4
CENTAVO = Decimal("0.01")
ZERO = Decimal("0.00")


# O card de um agendamento do site (#65): o do driver; sem driver marcado, o da conta.
# Driver ainda sem card não cai no card do irmão — fica sem card até a equipe vincular.
CARD_DO_AGENDAMENTO = "(CASE WHEN b.pilot_id IS NULL THEN a.client_id ELSE p.client_id END)"
# #314: a sessão que ocupa a vaga do pacote. A de antes (sem `coverage`) conta se não foi cobrada à parte.
DO_PACOTE = "(b.coverage='plano' OR (b.coverage IS NULL AND COALESCE(b.charge_kind,'') IN ('','contrato')))"


def sessoes_por_mes(con, cid):
    c = um(con, "SELECT monthly_sessions FROM clients WHERE id=?", (cid,))
    return (c and c["monthly_sessions"]) or PADRAO_SESSOES


def tem_contrato(con, cid):
    c = um(con, "SELECT plan_type, monthly_sessions, monthly_amount FROM clients WHERE id=?", (cid,)) if cid else None
    return bool(c and (c["plan_type"] == "monthly" or c["monthly_sessions"] or c["monthly_amount"]))


def _mes_de_hoje():
    from command_center.providers.agenda_sessoes import _agora_fl
    return _agora_fl().date().isoformat()[:7]


def plano_do_site(con, cid):
    """O último plano comprado no site para este card (#169), ou None."""
    return um(con, "SELECT * FROM plan_orders WHERE client_id=? AND status<>'cancelada' ORDER BY id DESC LIMIT 1",
              (cid,)) if cid else None


def plano_pago(con, o):
    """A 1ª mensalidade do plano do site está paga (conferida direto ou pelo espelho do QuickBooks)?"""
    if o["status"] == "ativa" or o["paid_at"]:
        return True
    from command_center.providers.cobranca_agenda import invoice_paga
    return invoice_paga(con, o)


def plano_encerrado(con, cid, mes):
    """A recorrência do card acabou antes deste mês. Sem recorrência no painel, o card manda (o de sempre)."""
    recs = todos(con, "SELECT status, end_on FROM monthly_recurring WHERE client_id=? AND status IN ('active','ended')", (cid,))
    return bool(recs) and not any(r["status"] == "active" and r["end_on"] >= f"{mes}-01" for r in recs)


def vigente(con, cid, mes=None):
    """O card é de aluno recorrente neste mês (#314): marca na área dele, a sessão do pacote sai sem custo
    e a extra vai pela invoice do QuickBooks. Decisões de 16/10: o plano comprado no site só libera as sessões
    depois da 1ª mensalidade paga; o plano encerrado não libera mais."""
    if not cid or not tem_contrato(con, cid):
        return False
    o = plano_do_site(con, cid)
    if o and o["status"] == "pendente" and not plano_pago(con, o):
        return False
    return not plano_encerrado(con, cid, mes or _mes_de_hoje())


def sessoes_asana(con, cid, mes):
    """As tarefas de treino do mês no Asana (o mesmo critério que o card usava desde 09/09)."""
    from command_center.providers.agenda_asana import GIDS_DE_AGENDAMENTO   # #67: a do site já conta pelo agendamento
    return todos(con, f"""SELECT title, due_on, status FROM tasks WHERE id NOT IN ({GIDS_DE_AGENDAMENTO}) AND (
                           client_id=? AND due_on LIKE ? AND project='U-RACE'
                           AND LOWER(COALESCE(section,'')) NOT IN ('races','finished services') OR (client_id=? AND due_on LIKE ? AND status='completed' AND LOWER(COALESCE(section,''))='finished services'))""",
                 (cid, mes + "%", cid, mes + "%"))


def sessoes_site(con, cid, mes, so_do_pacote=False, sem=()):
    """Agendamentos feitos na área do cliente para o driver deste card (#65: cada driver tem o
    seu card; a sessão do irmão não conta aqui). Agendamento sem driver conta no card da conta.
    `so_do_pacote` (#314): só as que ocupam vaga do pacote; `sem`: ids que não entram na conta."""
    filtro = f" AND {DO_PACOTE}" if so_do_pacote else ""
    if sem:
        filtro += f" AND b.id NOT IN ({','.join('?' * len(sem))})"
    return todos(con, f"""SELECT b.id, b.date AS due_on, COALESCE(b.service_name, 'Site booking') AS title, b.status, b.coverage
                           FROM bookings b JOIN portal_accounts a ON a.id=b.account_id LEFT JOIN portal_pilots p ON p.id=b.pilot_id
                          WHERE {CARD_DO_AGENDAMENTO}=? AND b.date LIKE ? AND b.status IN ('pendente','confirmada'){filtro}
                          ORDER BY b.date""",
                 (cid, mes + "%", *sem))


def usadas(con, cid, mes):
    a, s = sessoes_asana(con, cid, mes), sessoes_site(con, cid, mes)
    return {"asana": a, "site": s, "total": len(a) + len(s)}


def usadas_do_pacote(con, cid, mes, sem=()):
    """As vagas do pacote do mês já ocupadas: o Asana e as sessões do plano. A extra e a do Stripe não contam."""
    return len(sessoes_asana(con, cid, mes)) + len(sessoes_site(con, cid, mes, so_do_pacote=True, sem=sem))


# ------------------------------------------------------------------ a sessão extra (#314)
def centavos(v):
    """Decimal com 2 casas, arredondamento comercial (689,225 → 689,23). Nada de float na conta."""
    return Decimal(str(v)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def servico_do_plano(con, cid):
    """O plano (booking_services kind='plan') do card: o do último plano comprado no site, ou o de mesmo nome
    do plano escrito no card. None quando não há."""
    o = plano_do_site(con, cid)
    if o:
        s = um(con, "SELECT * FROM booking_services WHERE id=?", (o["service_id"],))
        if s:
            return s
    c = um(con, "SELECT monthly_plan FROM clients WHERE id=?", (cid,))
    if c and c["monthly_plan"]:
        achados = todos(con, "SELECT * FROM booking_services WHERE kind='plan' AND LOWER(name)=LOWER(?)", (c["monthly_plan"],))
        if len(achados) == 1:
            return achados[0]
    return None


def extra(con, cid):
    """{preco: Decimal | None, origem: 'card' | 'plano' | 'mensal' | None, conta: '2,756.90 ÷ 4'}. A ordem é a
    do dono (16/10): o valor configurado no card, depois o do plano, depois o mensal ÷ sessões do mês."""
    c = um(con, "SELECT extra_session_price, monthly_amount FROM clients WHERE id=?", (cid,)) if cid else None
    if not c:
        return {"preco": None, "origem": None, "conta": None}
    if c["extra_session_price"]:
        return {"preco": centavos(c["extra_session_price"]), "origem": "card", "conta": None}
    s = servico_do_plano(con, cid)
    if s and s["extra_price"]:
        return {"preco": centavos(s["extra_price"]), "origem": "plano", "conta": None}
    if c["monthly_amount"]:
        n = sessoes_por_mes(con, cid)
        return {"preco": (Decimal(str(c["monthly_amount"])) / n).quantize(CENTAVO, rounding=ROUND_HALF_UP), "origem": "mensal",
                "conta": f"{c['monthly_amount']:,.2f} ÷ {n}"}
    return {"preco": None, "origem": None, "conta": None}


def preco_extra(con, cid):
    return extra(con, cid)["preco"]


def item_extra(con, cid):
    """O item do QuickBooks da sessão extra: o do card, o do plano, ou o item "Extra session" do espelho
    (no QuickBooks da URACE: "Academy | Extra session (beyond monthly 4)"). None quando não há nenhum."""
    c = um(con, "SELECT extra_item_id FROM clients WHERE id=?", (cid,)) if cid else None
    if c and c["extra_item_id"]:
        return c["extra_item_id"]
    s = servico_do_plano(con, cid) if cid else None
    if s and s["extra_item_id"]:
        return s["extra_item_id"]
    i = um(con, """SELECT id FROM qbo_items WHERE active=1 AND (LOWER(name) LIKE '%extra session%'
                    OR LOWER(COALESCE(full_name,'')) LIKE '%extra session%')
                  ORDER BY (LOWER(COALESCE(full_name, name)) LIKE '%academy%') DESC, name LIMIT 1""")
    return i["id"] if i else None


def alocar(con, cid, datas, sem=()):
    """Os dias pedidos (AAAA-MM-DD, na ordem do pedido) → [{coverage, price}] na mesma ordem. Por mês, em
    ordem de data: as vagas livres do pacote viram `plano` (sem custo); o resto, `extra` (preço da extra).
    O mês em que o card não é vigente (plano acabou) fica `None`: é sessão avulsa. `sem`: os ids dos
    agendamentos que estão sendo alocados (não contam como já usados)."""
    total = sessoes_por_mes(con, cid)
    preco = preco_extra(con, cid)
    livres, ok, saida = {}, {}, [None] * len(datas)
    for i in sorted(range(len(datas)), key=lambda k: (datas[k], k)):
        mes = datas[i][:7]
        if mes not in ok:
            ok[mes] = vigente(con, cid, mes)
            livres[mes] = max(0, total - usadas_do_pacote(con, cid, mes, sem)) if ok[mes] else 0
        if not ok[mes]:
            saida[i] = {"coverage": None, "price": None}
        elif livres[mes] > 0:
            livres[mes] -= 1
            saida[i] = {"coverage": "plano", "price": ZERO}
        else:
            saida[i] = {"coverage": "extra", "price": preco}
    return saida


def situacao_do_agendamento(con, cid, data_iso, b=None, cache=None):
    """Para a lista da equipe: o agendamento cabe no contrato daquele mês? None sem contrato.
    #314: a vaga é a do pacote (extra e Stripe não ocupam); com `b`, vale o que foi alocado.
    #340: e a mensalidade daquele mês pelo espelho (paid / open / None = sem invoice). `cache`: um dict para a
    lista não reler as invoices do mesmo card a cada linha."""
    if not tem_contrato(con, cid):
        return None
    total = sessoes_por_mes(con, cid)
    n = usadas_do_pacote(con, cid, data_iso[:7])
    cob = (b or {}).get("coverage")
    if cache is None or cid not in cache:
        pm = mensalidades_por_mes(con, cid)[0]
        if cache is not None:
            cache[cid] = pm
    else:
        pm = cache[cid]
    mens = mensalidade_do_mes(con, cid, data_iso[:7], pm)
    return {"usadas": n, "sessoes_por_mes": total, "acima": cob == "extra" if cob else n > total,
            "mensalidade": mens["status"] if mens else None, "mensalidade_doc": mens["doc"] if mens else None}



# ------------------------------------------------------------------ piloto pro (#340)
def e_pro(con, cid):
    c = um(con, "SELECT pro_driver FROM clients WHERE id=?", (cid,)) if cid else None
    return bool(c and c["pro_driver"])


def pro_sem_mensal(con, cid):
    """Dono, 19/10: o piloto pro já paga mensal. Card com Pro Racing Driver e sem mensalidade configurada (sessões
    por mês, valor mensal ou tipo mensal) ainda não sabe o pacote: a equipe preenche (Precisa de atenção). Nada é
    inventado aqui: nem sessões, nem valor."""
    return e_pro(con, cid) and not tem_contrato(con, cid)


# O kart do plano, para a tela de marcar mostrar só o serviço do plano (#340). Chave do kart → apelidos no nome.
APELIDOS_DO_KART = {"baby kart": ("babykart",), "4-stroke": ("4stroke", "4tempos"), "2-stroke": ("2stroke", "2tempos"),
                    "adult shifter": ("adultshifter", "shifter"), "own kart": ("ownkart", "kartproprio", "kartpróprio")}


def _sem_espaco(t):
    return re.sub(r"[^0-9a-zà-ú]", "", (t or "").lower())


def karts_do_plano(con, cid):
    """As chaves de kart do plano do card: o `site_kart` do plano do site, senão as que aparecem no nome do plano
    (o do site ou o escrito no card, ex.: "Academy 4 stroke" → 4-stroke). Vazio quando o plano não diz o kart."""
    s = servico_do_plano(con, cid)
    if s and s["site_kart"] and s["site_kart"].strip().lower() in APELIDOS_DO_KART:
        return {s["site_kart"].strip().lower()}
    c = um(con, "SELECT monthly_plan FROM clients WHERE id=?", (cid,)) if cid else None
    nomes = _sem_espaco(" ".join(x for x in ((s["name"] if s else None), (c or {}).get("monthly_plan")) if x))
    achados = {k for k, apelidos in APELIDOS_DO_KART.items() if any(a in nomes for a in apelidos)}
    if "own kart" in achados:
        achados = {"own kart"}            # "Academy kart próprio": o kart é do cliente, não o da URACE
    return achados


def servicos_do_plano(con, cid, servicos):
    """Dos serviços de sessão (`servicos_site.para_cliente`), os do kart do plano. Vazio quando o plano não diz o
    kart ou nenhum serviço é desse kart: a tela mostra todos (o de antes) e a equipe completa o Plano mensal do card."""
    karts = karts_do_plano(con, cid)
    if not karts:
        return []
    apelidos = [a for k in karts for a in (*APELIDOS_DO_KART[k], _sem_espaco(k))]
    return [x for x in servicos if (x.get("site_kart") or "").strip().lower() in karts
            or any(a in _sem_espaco(x.get("name")) for a in apelidos)]


# ------------------------------------------------------------------ o contador (#340)
MESES_EN = {m: i for i, m in enumerate(("january", "february", "march", "april", "may", "june", "july", "august",
                                        "september", "october", "november", "december"), 1)}
EH_MENSALIDADE = re.compile(r"academy|monthly|training program|mensal", re.I)
JANELA_EM_ABERTO = 3                   # meses olhados no "em aberto" (o deste e os 2 de antes)


def mes_da_invoice(inv):
    """'Urace Academy Training Program + Tuner [August, 2026]' → '2026-08'; senão o mês de emissão."""
    m = re.search(r"\[\s*([A-Za-z]+)[,\s]+(\d{4})\s*\]", inv.get("memo") or "")
    if m and m.group(1).lower() in MESES_EN:
        return f"{m.group(2)}-{MESES_EN[m.group(1).lower()]:02d}"
    return (inv.get("issued_on") or "")[:7] or None


def _id_qbo(con, inv_id):
    r = um(con, """SELECT external_id FROM entity_links WHERE entity_type='invoice' AND entity_id=?
                    AND system IN ('quickbooks','qbo') LIMIT 1""", (inv_id,))
    return r["external_id"] if r else None


def invoices_das_sessoes(con, cid):
    """Os ids no QuickBooks das invoices das sessões do site do card (extra, avulsa, add-on): nenhuma é a mensalidade."""
    return {str(r["qbo_invoice_id"]) for r in todos(con, f"""SELECT DISTINCT b.qbo_invoice_id FROM bookings b
                       JOIN portal_accounts a ON a.id=b.account_id LEFT JOIN portal_pilots p ON p.id=b.pilot_id
                      WHERE {CARD_DO_AGENDAMENTO}=? AND b.qbo_invoice_id IS NOT NULL""", (cid,))} if cid else set()


def mensalidades_por_mes(con, cid):
    """({mês: invoice de mensalidade}, [todas as invoices do card]) pelo espelho do QuickBooks. A invoice de uma
    sessão do site (extra, avulsa, add-on) nunca é a mensalidade, mesmo com o item "Academy | Extra session"."""
    invs = todos(con, "SELECT * FROM invoices WHERE client_id=? ORDER BY issued_on DESC", (cid,)) if cid else []
    das_sessoes = invoices_das_sessoes(con, cid)
    por_mes = {}
    for i in invs:
        # 01/10 (#63): a invoice de mensalidade também é reconhecida pelo item da linha (a de 17/09 não tem memo,
        # só o item "Academy Monthly")
        linhas = " ".join(f"{x['item_name'] or ''} {x['description'] or ''}" for x in
                          todos(con, "SELECT item_name, description FROM invoice_lines WHERE invoice_id=?", (i["id"],)))
        i["_linhas"] = linhas
        if das_sessoes and _id_qbo(con, i["id"]) in das_sessoes:
            i["_sessao"] = True
            continue
        if EH_MENSALIDADE.search((i.get("memo") or "") + " " + (i.get("doc_number") or "") + " " + linhas):
            por_mes.setdefault(mes_da_invoice(i), i)
    return por_mes, invs


def _paga(i):
    return (i["balance"] is not None and i["balance"] <= 0) or (i["status"] or "").lower() == "paid"


def _link_de_pagar(con, qbo_id):
    """O link de pagamento do CLIENTE que o painel guardou ao criar a invoice (o do plano do site ou o da sessão)."""
    if not qbo_id:
        return None
    r = um(con, """SELECT pay_link FROM plan_orders WHERE qbo_invoice_id=? AND pay_link IS NOT NULL
                   UNION ALL SELECT pay_link FROM bookings WHERE qbo_invoice_id=? AND pay_link IS NOT NULL LIMIT 1""",
           (str(qbo_id), str(qbo_id)))
    return r["pay_link"] if r else None


def mensalidade_do_mes(con, cid, mes, por_mes=None):
    """A mensalidade do mês pelo espelho: {status: 'paid' | 'open', doc, amount, balance, link} ou None (sem invoice)."""
    if por_mes is None:
        por_mes = mensalidades_por_mes(con, cid)[0]
    i = por_mes.get(mes)
    if not i:
        return None
    pago = _paga(i)
    qid = _id_qbo(con, i["id"])
    return {"status": "paid" if pago else "open", "doc": i["doc_number"], "amount": i["amount"],
            "balance": 0.0 if pago else (i["balance"] if i["balance"] is not None else i["amount"]),
            "link": None if pago else _link_de_pagar(con, qid), "_chave": f"m{i['id']}"}


def invoice_da_sessao(con, b):
    """A invoice de uma sessão do site: {status: 'paid' | 'open' | 'not_invoiced', doc, balance, link}."""
    from command_center.providers.cobranca_agenda import invoice_paga
    b = dict(b)
    if b.get("charge_kind") == "stripe":
        return {"status": "paid", "doc": None, "balance": 0.0, "link": None, "_chave": f"s{b['id']}"}
    if not b.get("qbo_invoice_id"):
        return {"status": "not_invoiced", "doc": None, "balance": None, "link": None, "_chave": None}
    if invoice_paga(con, b):
        return {"status": "paid", "doc": b.get("invoice_doc"), "balance": 0.0, "link": None, "_chave": f"q{b['qbo_invoice_id']}"}
    i = um(con, """SELECT i.balance FROM invoices i JOIN entity_links l ON l.entity_type='invoice' AND l.entity_id=i.id
                     AND l.system IN ('quickbooks','qbo') WHERE l.external_id=?""", (str(b["qbo_invoice_id"]),))
    saldo = i["balance"] if i and i["balance"] is not None else b.get("invoice_total")
    return {"status": "open", "doc": b.get("invoice_doc"), "balance": saldo, "link": b.get("pay_link"),
            "_chave": f"q{b['qbo_invoice_id']}"}


def _mes_somado(mes, n):
    t = int(mes[:4]) * 12 + int(mes[5:7]) - 1 + n
    return f"{t // 12:04d}-{t % 12 + 1:02d}"


def _hoje():
    from command_center.providers.agenda_sessoes import _agora_fl
    return _agora_fl().date()


def _sessoes_do_site_do_mes(con, cid, mes):
    return todos(con, f"""SELECT b.* FROM bookings b JOIN portal_accounts a ON a.id=b.account_id
                           LEFT JOIN portal_pilots p ON p.id=b.pilot_id
                          WHERE {CARD_DO_AGENDAMENTO}=? AND b.date LIKE ? AND b.status IN ('pendente','confirmada')
                          ORDER BY b.date, b.id""", (cid, mes + "%"))


def em_aberto(con, cid, hoje=None, meses=JANELA_EM_ABERTO, por_mes=None):
    """As sessões já feitas e ainda não cobertas por invoice paga (a regra está no docstring do módulo).
    {count, amount, not_invoiced, sessions: [{date, title, kind, invoice, status}], invoices: [{doc, balance, link, kind}]}."""
    hoje = (hoje or _hoje()).isoformat()
    por_mes = mensalidades_por_mes(con, cid)[0] if por_mes is None else por_mes
    sessoes, invoices = [], {}

    def abre(sessao, inv, tipo):
        sessoes.append({**sessao, "invoice": inv["doc"] if inv else None,
                        "status": inv["status"] if inv else "not_invoiced"})
        if inv and inv["status"] == "open" and inv["_chave"] not in invoices:
            invoices[inv["_chave"]] = {"doc": inv["doc"], "balance": inv["balance"], "link": inv["link"], "kind": tipo}

    mes0 = hoje[:7]
    for k in range(meses - 1, -1, -1):
        mes = _mes_somado(mes0, -k)
        mens = mensalidade_do_mes(con, cid, mes, por_mes)
        for t in sessoes_asana(con, cid, mes):
            if t["status"] == "completed" or (t["due_on"] or "9999") < hoje:
                if not mens or mens["status"] != "paid":
                    abre({"date": t["due_on"], "title": t["title"], "kind": "asana"}, mens, "monthly")
        for b in _sessoes_do_site_do_mes(con, cid, mes):
            if b["date"] >= hoje:
                continue                                              # ainda não feita
            base = {"date": b["date"], "title": b["service_name"] or "Site booking", "kind": b["coverage"] or "avulsa"}
            do_pacote = b["coverage"] == "plano" or (b["coverage"] is None and (b["charge_kind"] or "") in ("", "contrato")
                                                      and tem_contrato(con, cid))
            if do_pacote:
                if not mens or mens["status"] != "paid":
                    abre(base, mens, "monthly")
                elif b["addon_price"] and (inv := invoice_da_sessao(con, b))["status"] != "paid":
                    abre({**base, "kind": "addon"}, inv if inv["status"] == "open" else None, "addon")
            else:
                inv = invoice_da_sessao(con, b)
                if inv["status"] != "paid":
                    abre(base, inv if inv["status"] == "open" else None, "extra" if b["coverage"] == "extra" else "session")
    saldos = [x["balance"] for x in invoices.values() if x["balance"] is not None]
    return {"count": len(sessoes), "amount": float(sum((centavos(v) for v in saldos), ZERO)) if saldos else None,
            "not_invoiced": sum(1 for x in sessoes if x["status"] == "not_invoiced"),
            "sessions": sessoes, "invoices": list(invoices.values())}


def contador(con, cid, mes=None, hoje=None, equipe=False):
    """O contador do mês do card (#340), o mesmo para o cliente e para a equipe. None sem contrato.
    `equipe=True` traz também quais sessões e quais invoices estão em aberto."""
    if not cid or not tem_contrato(con, cid):
        return None
    hoje = hoje or _hoje()
    mes = mes or hoje.isoformat()[:7]
    total = sessoes_por_mes(con, cid)
    usadas_ = usadas_do_pacote(con, cid, mes)
    por_mes = mensalidades_por_mes(con, cid)[0]
    mens = mensalidade_do_mes(con, cid, mes, por_mes)
    extras = []
    for b in _sessoes_do_site_do_mes(con, cid, mes):
        if b["coverage"] == "extra":
            inv = invoice_da_sessao(con, b)
            extras.append({"date": b["date"], "period": b["period"], "price": b["price"], "invoice": inv["doc"],
                           "status": inv["status"], "link": inv["link"]})
    ab = em_aberto(con, cid, hoje, por_mes=por_mes)
    prox = date.fromisoformat(f"{_mes_somado(mes, 1)}-01")
    saida = {"month": mes, "sessions_per_month": total, "used": usadas_, "left": max(0, total - usadas_),
             "over": max(0, usadas_ - total), "resets_on": prox.isoformat(),
             "monthly_invoice": {k: v for k, v in mens.items() if not k.startswith("_")} if mens else None,
             "extras": extras,
             "open": {"count": ab["count"], "amount": ab["amount"], "not_invoiced": ab["not_invoiced"]}}
    if equipe:
        saida["open"].update(sessions=ab["sessions"], invoices=ab["invoices"])
    return saida
