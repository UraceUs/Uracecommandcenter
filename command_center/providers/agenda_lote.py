"""Vários dias num pedido do aluno recorrente (#314, parte 2).

Dono, 16/10: *"para esses clientes, é interessante eles terem a oportunidade de marcar mais de um dia,
multi-seleção de dias. Então, se ele quiser marcar para quartas, toda quarta. Ou quartas e sábado dessa
semana, ou então sábado e domingo da outra, ele consegue marcar isso tudo em um book."*

- **Cotar** (`cotar`): os dias escolhidos, um a um, como o servidor os vê — aberto ou não (a agenda do
  cliente: horizonte e antecedência valem), conflito com outra sessão do piloto, e se cabe no pacote do mês
  ("Included in your plan") ou é extra ("Extra session · $X"). Nada é gravado. O `hash` resume a cotação.
- **Marcar** (`marcar`): o pedido inteiro numa transação — ou entram todos os dias, ou nenhum. Se a cotação
  mudou desde que o cliente viu (outra pessoa pegou a vaga, o preço mudou), o pedido volta para ele revisar.
- No máximo 12 dias por pedido. Só para quem tem plano mensal vigente: o cliente avulso marca um dia por vez.
- #340 (dono, 19/10): o contador do pacote vai para o cliente (`plano_do_piloto` → `counter`, o
  `contrato.contador`); a tela de marcar mostra só o(s) serviço(s) do kart do plano (`services`; os outros ficam
  atrás do "Book as a regular session"); e os add-ons continuam (dono: *"deixe os add ons disponiveis tb"*):
  cada dia pode levar o add-on do site (Lead and Follow, preço do painel), que vai na invoice do QuickBooks do
  pedido junto com as extras — criada e enviada na marcação (`cobranca_agenda.cobrar_pedido`), nunca no Stripe.

Mensagens em inglês: é o que o cliente lê.
"""
import hashlib
import json
from datetime import date

from command_center.db import atualizar, inserir, todos, um
from command_center.providers import agenda_sessoes as ag
from command_center.providers import contrato, servicos_site

MAX_DIAS = 12
PERIODOS = ("manha", "tarde", "dia")
MOTIVOS = {"invalido": "Choose a valid date and time.",
           "fechado": "This time is not available. Pick another one.",
           "repetido": "This day and time is twice in your booking.",
           "fora_do_plano": "Your monthly plan does not cover this date. Use \"Book as a regular session\" on this day.",
           "sem_addon": "This add-on is not open for online booking right now. Remove it to continue, or talk to us."}
FORA_DO_PLANO = "This session type is not in your monthly plan. Use \"Book as a regular session\" for it."
MUDOU = "Your booking changed since you reviewed it (a spot or a price). Please review it and book again."


class ErroLote(ValueError):
    """Mensagem em inglês: é o que o cliente lê."""


class CotacaoMudou(ErroLote):
    """A vaga ou o preço mudou entre a cotação e o pedido: o cliente revisa antes (409)."""


TRAINING_DAY = "Training Day"


def titulo(numero=None, total=None, extra=False, preco=None):
    """#355 (dono, 20/10): *"para clientes do mensal/pro colocar os serviços que vão aparecer para esse cliente mensal
    será training day sendo 1/4, sendo o X/4 a sessão atual da mensalidade vigente e 1/X a quantidade de sessões que
    estão inclusas na mensalidade"*. O nome da sessão do pacote: "Training Day 2/4" (X = a sessão do pacote no mês,
    Y = as incluídas); acima do pacote, "Training Day · extra $X"; sem a Mensalidade no card (pro em montagem), só
    "Training Day" — sem número inventado."""
    if extra:
        return f"{TRAINING_DAY} · extra" + (f" ${preco:,.2f}" if preco is not None else "")
    return f"{TRAINING_DAY} {numero}/{total}" if numero and total else TRAINING_DAY


def proximo_titulo(con, card, mes=None):
    """O nome da próxima sessão do pacote do mês: usadas + 1 de Y; com o pacote cheio, a extra."""
    mes = mes or contrato._hoje().isoformat()[:7]
    total, usadas = contrato.sessoes_por_mes(con, card), contrato.usadas_do_pacote(con, card, mes)
    if usadas >= total:
        return titulo(extra=True, preco=contrato.preco_extra(con, card))
    return titulo(usadas + 1, total)


def rotulo(cobertura, preco):
    """O que o cliente lê em cada dia. O contador do mês vem à parte, no `plano_do_piloto` (#340)."""
    if cobertura == "plano":
        return "Included in your plan"
    return "Extra session" + (f" · ${preco:,.2f}" if preco is not None else "")


def _piloto(con, conta_id, piloto_id):
    p = um(con, "SELECT * FROM portal_pilots WHERE id=? AND account_id=? AND active=1", (piloto_id, conta_id)) if piloto_id else None
    if not p:
        raise ErroLote("Choose the driver for these sessions.")
    return p


def servicos_para_o_plano(con, card):
    """Os serviços de sessão que o aluno recorrente marca pelo plano: os do kart do plano; sem kart no plano (ou sem
    serviço daquele kart), todos — e `matched` diz qual foi."""
    todos_ = servicos_site.para_cliente(con)
    do_plano = contrato.servicos_do_plano(con, card, todos_)
    return (do_plano or todos_), bool(do_plano)


def addon_para_o_plano(con):
    """O add-on do dia que o site vende (Lead and Follow), com o preço do painel, ou None."""
    a = servicos_site.addon_do_site(con)
    return {"id": a["id"], "name": a["name"], "price": float(a["price"]), "description": a["texto"]} if a else None


def plano_do_piloto(con, conta_id, piloto_id):
    """O piloto é aluno recorrente? O nome do plano, o preço da extra e, desde 19/10 (#340), o contador do mês
    (`counter`), os serviços do plano e o add-on. `setup`: piloto pro com a mensalidade ainda não configurada no
    card (a equipe está montando: nada de carrinho, o pedido vai para a equipe e sai por invoice)."""
    p = _piloto(con, conta_id, piloto_id)
    card = p["client_id"]
    rec = contrato.vigente(con, card)
    pro = contrato.e_pro(con, card)
    c = um(con, "SELECT monthly_plan FROM clients WHERE id=?", (card,)) if rec else None
    e = contrato.preco_extra(con, card) if rec else None
    saida = {"driver_id": p["id"], "recurring": rec, "plan": (c or {}).get("monthly_plan") or ("Monthly plan" if rec else None),
             "extra_price": float(e) if e is not None else None, "pro": pro, "setup": pro and not rec and contrato.pro_sem_mensal(con, card)}
    if rec:
        k = contrato.contador(con, card)
        servicos, achou = servicos_para_o_plano(con, card)
        saida.update(counter=k, services=[x["id"] for x in servicos], services_matched=achou, addon=addon_para_o_plano(con),
                     training_day=proximo_titulo(con, card))
    elif saida["setup"]:
        # #355: o pro em montagem também marca "Training Day" (sem número: o card ainda não diz quantas são incluídas)
        servicos, achou = servicos_para_o_plano(con, card)
        saida.update(services=[x["id"] for x in servicos], services_matched=achou, training_day=titulo())
    return saida


def _sobrepoe(a, b):
    return a == b or "dia" in (a, b)


def cotar(con, conta_id, piloto_id, servico_id, slots):
    """Cada dia pedido → {date, period, ok, reason, message, coverage, price, label}; e os totais."""
    if not isinstance(slots, list) or not slots:
        raise ErroLote("Choose at least one day.")
    if len(slots) > MAX_DIAS:
        raise ErroLote(f"Up to {MAX_DIAS} days per booking. Book the rest in another one.")
    try:
        servico = servicos_site.do_agendamento(con, servico_id)
    except servicos_site.ErroServico as e:
        raise ErroLote(str(e))
    p = _piloto(con, conta_id, piloto_id)
    card = p["client_id"]
    if not contrato.vigente(con, card):
        raise ErroLote("Booking several days at once is for students with a monthly plan. Book one session at a time.")
    # #340: pelo plano, só o serviço do plano; outro serviço é sessão avulsa ("Book as a regular session")
    servico_fora = servico["id"] not in [x["id"] for x in servicos_para_o_plano(con, card)[0]]
    addon = addon_para_o_plano(con)
    from command_center.providers import portal                      # import aqui: portal não depende da agenda
    falta = portal.pode_marcar(con, conta_id, piloto_id)
    if falta:
        raise ErroLote(falta)
    linhas = []
    for s in slots:
        d, per = str((s or {}).get("date") or "")[:10], str((s or {}).get("period") or "")
        try:
            dia = date.fromisoformat(d)
        except ValueError:
            dia = None
        linhas.append({"date": d, "period": per, "_dia": dia if per in PERIODOS else None, "addon": bool((s or {}).get("addon"))})
    validos = [x["_dia"] for x in linhas if x["_dia"]]
    disp = {x["date"]: x for x in ag.disponibilidade(con, min(validos), max(validos))["dias"]} if validos else {}
    ja = todos(con, """SELECT date, period FROM bookings WHERE account_id=? AND COALESCE(pilot_id,0)=? AND date BETWEEN ? AND ?
                        AND status IN ('pendente','confirmada')""",
               (conta_id, piloto_id, min(validos).isoformat(), max(validos).isoformat())) if validos else []
    vistos = []
    for x in linhas:
        motivo = None
        if not x["_dia"]:
            motivo = "invalido"
        elif any(y["date"] == x["date"] and _sobrepoe(y["period"], x["period"]) for y in ja):
            motivo = "ja_tem"
        elif not (disp.get(x["date"]) or {}).get("periods", {}).get(x["period"], {}).get("open"):
            motivo = "fechado"
        elif any(d == x["date"] and _sobrepoe(per, x["period"]) for d, per in vistos):
            motivo = "repetido"
        elif x["addon"] and not addon:
            motivo = "sem_addon"
        if not motivo:
            vistos.append((x["date"], x["period"]))
        x["reason"] = motivo
    bons = [x for x in linhas if not x["reason"]]
    for x, a in zip(bons, contrato.alocar(con, card, [x["date"] for x in bons])):
        if servico_fora:
            x["reason"], x["_msg"] = "fora_do_plano", FORA_DO_PLANO
        elif not a["coverage"]:
            x["reason"] = "fora_do_plano"
        else:
            x["coverage"], x["price"] = a["coverage"], (float(a["price"]) if a["price"] is not None else None)
    # #355: cada dia do pacote ganha o seu número no mês, em ordem de data ("Training Day 3/4"); a extra, o seu nome
    total_mes, seguinte = contrato.sessoes_por_mes(con, card), {}
    for x in sorted((y for y in linhas if not y["reason"]), key=lambda y: (y["date"], y["period"])):
        if x.get("coverage") == "plano":
            mes = x["date"][:7]
            if mes not in seguinte:
                seguinte[mes] = contrato.usadas_do_pacote(con, card, mes)
            seguinte[mes] += 1
            x["title"] = titulo(seguinte[mes], total_mes)
        elif x.get("coverage") == "extra":
            x["title"] = titulo(extra=True, preco=x.get("price"))
    saida = []
    for x in linhas:
        ok = not x["reason"]
        msg = None if ok else (f"{p['name']} already has a session at this time." if x["reason"] == "ja_tem"
                               else x.get("_msg") or MOTIVOS[x["reason"]])
        com_addon = ok and x["addon"] and addon
        saida.append({"date": x["date"], "period": x["period"], "ok": ok, "reason": x["reason"], "message": msg,
                      "coverage": x.get("coverage") if ok else None, "price": x.get("price") if ok else None,
                      "label": rotulo(x.get("coverage"), x.get("price")) if ok else None,
                      "title": x.get("title") if ok else None,
                      "addon": {"id": addon["id"], "name": addon["name"], "price": addon["price"]} if com_addon else None})
    extras = [x for x in saida if x["coverage"] == "extra"]
    total = sum((contrato.centavos(x["price"]) for x in extras if x["price"] is not None), contrato.ZERO)
    addons = [x["addon"] for x in saida if x["addon"]]
    total_addons = sum((contrato.centavos(a["price"]) for a in addons), contrato.ZERO)
    resumo = [[x["date"], x["period"], x["ok"], x["coverage"], x["price"], x["addon"] and [x["addon"]["id"], x["addon"]["price"]]]
              for x in saida]
    h = hashlib.sha256(json.dumps([servico["id"], piloto_id, resumo]).encode()).hexdigest()[:16]
    return {"slots": saida, "included": sum(1 for x in saida if x["coverage"] == "plano"), "extras": len(extras),
            "extras_total": float(total), "extra_price_missing": any(x["price"] is None for x in extras),
            "addons": len(addons), "addons_total": float(total_addons), "invoice_total": float(total + total_addons),
            "service": servico["name"], "hash": h}


def marcar(con, conta_id, piloto_id, servico_id, slots, cotacao, notas=None, origem=None, utm=None):
    """O pedido inteiro: chame dentro de `transacao` (ou entra tudo, ou nada). Devolve (grupo, [ids])."""
    from command_center.providers import cobranca_agenda as cob
    c = cotar(con, conta_id, piloto_id, servico_id, slots)
    ruim = next((x for x in c["slots"] if not x["ok"]), None)
    if ruim:
        quando = date.fromisoformat(ruim["date"]).strftime("%a, %b %d").replace(" 0", " ") if ruim["reason"] != "invalido" else ""
        raise ErroLote(f"{quando + ': ' if quando else ''}{ruim['message']}")
    if not cotacao or cotacao != c["hash"]:
        raise CotacaoMudou(MUDOU)
    gid = inserir(con, "booking_groups", account_id=conta_id, pilot_id=piloto_id, service_id=servico_id,
                  origin="site" if origem == "site" else "portal", utm=utm)
    ids = []
    for x in sorted(c["slots"], key=lambda y: (y["date"], y["period"])):
        try:
            bid = ag.agendar(con, conta_id, x["date"], x["period"], piloto_id, notas, servico_id)
        except ag.ErroAgenda as e:
            raise ErroLote(f"{date.fromisoformat(x['date']).strftime('%a, %b %d').replace(' 0', ' ')}: {e}")
        a = x["addon"] or {}
        atualizar(con, "bookings", bid, group_id=gid, origin="site" if origem == "site" else "portal", utm=utm,
                  **({"service_name": x["title"]} if x.get("title") else {}),
                  **({"addon_service_id": a["id"], "addon_name": a["name"], "addon_price": a["price"]} if a else {}))
        ids.append(bid)
    cob.alocar_grupo(con, ids)
    for bid in ids:
        cob.ao_marcar(con, bid)
    return gid, ids


def conferir(con, conta_id, piloto_id, servico_id, slots, cotacao):
    """O pedido de um dia do aluno recorrente (a Reserva do site): a cotação que o cliente viu ("Included in your
    plan" ou "Extra session · $X") ainda vale? Chame dentro da `transacao`, antes de marcar. Mudou (a última vaga
    do mês foi ocupada, o preço mudou, o plano acabou): CotacaoMudou (409), e o cliente revisa antes."""
    try:
        c = cotar(con, conta_id, piloto_id, servico_id, slots)
    except ErroLote:
        raise CotacaoMudou(MUDOU)
    if c["hash"] != cotacao:
        raise CotacaoMudou(MUDOU)
    return c
