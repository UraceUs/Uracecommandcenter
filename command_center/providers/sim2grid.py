"""A hora de simulador do SIM2GRID (#392): regras, faixas de preço, vagas por hora, reserva e pagamento.

Dono, 22/10: *"sera um serviço um diferente das aulas de kart podendo agendar ate 5 pessoas para a mesma hora, o valor
do serviço é cobrado por hora. monte assim como montou o arrive and drive com todas as configurações ajustaveis"*.

O modelo:
- **formatos** são os serviços do painel de `kind='sim'` (hoje: sem coach e com coach). Nome, texto, depósito,
  "depósito obrigatório" e o item do QuickBooks são os de Site › Serviços e preços, como no Arrive and Drive;
- **faixas** (`sim_rates`) dizem, para cada formato, em que dias e horas ele abre e quanto custa cada hora. Preço vazio
  é "ligue para nós": o horário aparece, mas não se vende online (nenhuma faixa nasce assim desde os preços do dono de 22/10);
- **regras** (`sim_config`): vender online ou não, quantos simuladores (vagas por hora, 5), horas mínimas e máximas
  seguidas, horizonte, antecedência, a abertura, datas fechadas, idade mínima, waiver, o aviso e o sorteio do mês;
- **vaga**: cada pessoa é um simulador. A hora está cheia quando as reservas pagas e as seguradas (checkout aberto no
  Stripe, até ele vencer) somam a capacidade. Os formatos dividem os mesmos simuladores.

Preço, vaga e depósito são sempre do servidor (o carrinho manda só a escolha). Tudo no relógio da Flórida.
"""
import re
from datetime import date, datetime, timedelta, timezone

from command_center.db import agora, atualizar, inserir, todos, um
from command_center.providers.agenda_sessoes import FUSO

DIAS_EN = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
LIMITES = {"capacity": (1, 50), "min_hours": (1, 12), "max_hours": (1, 12), "horizon_days": (1, 365),
           "min_notice_hours": (0, 24 * 30), "min_age": (1, 99)}


class ErroSim(ValueError):
    pass


def _agora_fl():
    return datetime.now(FUSO)


# ------------------------------------------------------------------ as regras
def config(con):
    c = um(con, "SELECT * FROM sim_config WHERE id=1")
    if not c:
        from command_center.vitrine.conteudo_sim2grid import REGRAS
        con.execute("INSERT OR IGNORE INTO sim_config (id, online, capacity, min_hours, max_hours, horizon_days, "
                    "min_notice_hours, open_from, waiver_required, notice, raffle_text) VALUES (1,?,?,?,?,?,?,?,?,?,?)",
                    (REGRAS["online"], REGRAS["capacity"], REGRAS["min_hours"], REGRAS["max_hours"], REGRAS["horizon_days"],
                     REGRAS["min_notice_hours"], REGRAS["open_from"], REGRAS["waiver_required"], REGRAS["notice"],
                     REGRAS["raffle_text"]))
        c = um(con, "SELECT * FROM sim_config WHERE id=1")
    return dict(c)


def _datas(v):
    """'2026-12-25, 2026-12-31' → ['2026-12-25', '2026-12-31'] (conferidas, sem repetir, em ordem)."""
    if v is None:
        return []
    partes = v if isinstance(v, (list, tuple)) else re.split(r"[\s,;]+", str(v))
    out = set()
    for p in partes:
        p = str(p).strip()
        if not p:
            continue
        try:
            out.add(date.fromisoformat(p).isoformat())
        except ValueError:
            raise ErroSim(f"data fechada inválida: {p} (use AAAA-MM-DD)")
    return sorted(out)


def fechadas(cfg):
    return set(_datas(cfg.get("closed_dates")))


def _texto(v, n):
    t = re.sub(r"\s+", " ", str(v or "").strip())
    return t[:n] or None


def mudar_config(con, por, d):
    """Devolve {campo: (antes, depois)} — vai para a auditoria."""
    atual = config(con)
    mud = {}
    for k in ("online", "waiver_required"):
        if k in d and d[k] is not None:
            mud[k] = 1 if d[k] else 0
    for k, (mi, ma) in LIMITES.items():
        if k not in d:
            continue
        if d[k] in (None, "") and k == "min_age":
            mud[k] = None
            continue
        if d[k] in (None, ""):
            continue
        try:
            v = int(d[k])
        except (TypeError, ValueError):
            raise ErroSim(f"{k}: use um número")
        if not mi <= v <= ma:
            raise ErroSim(f"{k} fora do limite ({mi}–{ma})")
        mud[k] = v
    if "open_from" in d:
        t = str(d["open_from"] or "").strip()
        if t:
            try:
                t = date.fromisoformat(t).isoformat()
            except ValueError:
                raise ErroSim("abertura: use AAAA-MM-DD")
        mud["open_from"] = t or None
    if "closed_dates" in d:
        mud["closed_dates"] = ", ".join(_datas(d["closed_dates"])) or None
    if "notice" in d:
        mud["notice"] = _texto(d["notice"], 400)
    if "raffle_text" in d:
        mud["raffle_text"] = _texto(d["raffle_text"], 200)
    novo = {**atual, **mud}
    if novo["min_hours"] > novo["max_hours"]:
        raise ErroSim("as horas mínimas não podem passar das máximas")
    mud = {k: (atual[k], v) for k, v in mud.items() if atual[k] != v}
    if mud:
        atualizar(con, "sim_config", 1, **{k: v for k, (_, v) in mud.items()}, updated_by=por, updated_at=agora())
    return mud


# ------------------------------------------------------------------ os formatos e as faixas
def formatos(con, ativos=True):
    """Os serviços de simulador do painel, na ordem do painel."""
    rs = todos(con, "SELECT * FROM booking_services WHERE kind='sim'" + (" AND active=1" if ativos else "") + " ORDER BY sort, id")
    return [{"id": s["id"], "name": s["name"], "titulo": s["site_title"] or s["name"], "linha": s["site_subtitle"] or "",
             "texto": s["description"] or "", "deposit": float(s["deposit"] or 0), "deposit_required": bool(s["deposit_required"]),
             "active": bool(s["active"]), "qbo_item_id": s["qbo_item_id"], "key": s["site_kart"]} for s in rs]


def faixas(con, ativos=False):
    sql = ("SELECT r.*, b.name AS service_name FROM sim_rates r JOIN booking_services b ON b.id=r.service_id"
           + (" WHERE r.active=1" if ativos else "") + " ORDER BY b.sort, b.id, r.sort, r.id")
    return [dict(r) for r in todos(con, sql)]


def _dias(v):
    t = "".join(sorted(set(re.sub(r"[^0-6]", "", str(v if not isinstance(v, (list, tuple)) else "".join(map(str, v)))))))
    if not t:
        raise ErroSim("escolha pelo menos um dia da semana")
    return t


def _preco(v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None                                            # "ligue para nós"
    from command_center.providers.servicos_site import ErroServico, preco
    try:
        return preco(v)
    except ErroServico as e:
        raise ErroSim(str(e))


def _faixa(con, d, parcial, atual=None):
    f = {}
    if not parcial or "service_id" in d:
        s = um(con, "SELECT id FROM booking_services WHERE id=? AND kind='sim'", (d.get("service_id"),))
        if not s:
            raise ErroSim("escolha o formato (serviço de simulador)")
        f["service_id"] = s["id"]
    if not parcial or "days" in d:
        f["days"] = _dias(d.get("days"))
    for k, (mi, ma) in (("start_hour", (0, 23)), ("end_hour", (1, 24))):
        if not parcial or k in d:
            try:
                v = int(d.get(k))
            except (TypeError, ValueError):
                raise ErroSim("horário: use a hora cheia (0 a 24)")
            if not mi <= v <= ma:
                raise ErroSim(f"horário fora do limite ({mi}–{ma})")
            f[k] = v
    if not parcial or "price" in d:
        f["price"] = _preco(d.get("price"))
    if "active" in d and d["active"] is not None:
        f["active"] = 1 if d["active"] else 0
    if "sort" in d and d["sort"] is not None:
        f["sort"] = int(d["sort"])
    novo = {**(atual or {}), **f}
    if novo["start_hour"] >= novo["end_hour"]:
        raise ErroSim("a faixa tem de terminar depois de começar")
    return f


def criar_faixa(con, por, d):
    f = _faixa(con, d, parcial=False)
    if "sort" not in f:
        ult = um(con, "SELECT COALESCE(MAX(sort), 0) AS s FROM sim_rates WHERE service_id=?", (f["service_id"],))
        f["sort"] = (ult["s"] or 0) + 10
    return inserir(con, "sim_rates", **f, updated_by=por, updated_at=agora())


def mudar_faixa(con, por, fid, d):
    atual = um(con, "SELECT * FROM sim_rates WHERE id=?", (fid,))
    if not atual:
        raise ErroSim("faixa não existe")
    f = _faixa(con, d, parcial=True, atual=atual)
    mud = {k: (atual[k], v) for k, v in f.items() if atual[k] != v}
    if mud:
        atualizar(con, "sim_rates", fid, **{k: v for k, (_, v) in mud.items()}, updated_by=por, updated_at=agora())
    return mud


def tarifa(fs, sid, dia_semana, hora):
    """A faixa ativa do formato para uma sessão que COMEÇA nesta hora (a primeira na ordem do painel), ou None (fechado).
    Dono, 22/10: *"vale o horário de início: uma sessão às 17h usa a tarifa diurna"* — a hora final da faixa também
    serve de início (7h–17h aceita começar às 17h), menos a meia-noite."""
    for f in fs:
        if (f["service_id"] == sid and f["active"] and str(dia_semana) in f["days"]
                and (f["start_hour"] <= hora < f["end_hour"] or hora == f["end_hour"] < 24)):
            return f
    return None


# ------------------------------------------------------------------ a etiqueta do dia (#396)
# Dono, 23/10: *"tem que virar um point · alguns dias frequentados por pilotos · outros dias por pessoas que vao levar
# como entretenimento"*. O selo do dia no calendário ("🏁 Pilot day", "🎮 Fun night"), por dia da semana ou por data,
# o dia inteiro ou uma faixa de horas. Nasce vazia: a equipe define. Desativar não apaga.
LIMITE_ROTULO, LIMITE_ICONE, LIMITE_NOTA = 24, 8, 120


def etiquetas(con, ativos=False):
    return [dict(r) for r in todos(con, "SELECT * FROM sim_day_tags" + (" WHERE active=1" if ativos else "")
                                   + " ORDER BY (date IS NULL), date, sort, id")]


def _hora_ou_nada(v, mi, ma):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        v = int(v)
    except (TypeError, ValueError):
        raise ErroSim("horário: use a hora cheia (0 a 24)")
    if not mi <= v <= ma:
        raise ErroSim(f"horário fora do limite ({mi}–{ma})")
    return v


def _etiqueta(d, parcial, atual=None):
    f = {}
    if not parcial or "label" in d:
        rot = _texto(d.get("label"), LIMITE_ROTULO + 1)
        if not rot:
            raise ErroSim("escreva o rótulo (ex.: Pilot day)")
        if len(rot) > LIMITE_ROTULO:
            raise ErroSim(f"rótulo curto: até {LIMITE_ROTULO} letras")
        f["label"] = rot
    if not parcial or "icon" in d:
        ic = _texto(d.get("icon"), LIMITE_ICONE + 1)
        if ic and len(ic) > LIMITE_ICONE:
            raise ErroSim(f"ícone curto: um emoji (até {LIMITE_ICONE} caracteres)")
        f["icon"] = ic
    if not parcial or "note" in d:
        f["note"] = _texto(d.get("note"), LIMITE_NOTA)
    if not parcial or "date" in d:
        t = str(d.get("date") or "").strip()
        if t:
            try:
                t = date.fromisoformat(t).isoformat()
            except ValueError:
                raise ErroSim("data: use AAAA-MM-DD")
        f["date"] = t or None
    if not parcial or "days" in d:
        v = d.get("days")
        f["days"] = _dias(v) if v not in (None, "", []) else None
    for k, (mi, ma) in (("start_hour", (0, 23)), ("end_hour", (1, 24))):
        if not parcial or k in d:
            f[k] = _hora_ou_nada(d.get(k), mi, ma)
    if "active" in d and d["active"] is not None:
        f["active"] = 1 if d["active"] else 0
    if "sort" in d and d["sort"] is not None:
        f["sort"] = int(d["sort"])
    novo = {**(atual or {}), **f}
    if novo.get("date"):
        novo["days"] = f["days"] = None                         # por data: o dia da semana não vale
    if not novo.get("date") and not novo.get("days"):
        raise ErroSim("escolha os dias da semana ou uma data")
    ini, fim = novo.get("start_hour"), novo.get("end_hour")
    if (ini is None) != (fim is None):
        raise ErroSim("faixa de horas: preencha o início e o fim (ou deixe os dois vazios para o dia inteiro)")
    if ini is not None and ini >= fim:
        raise ErroSim("a faixa tem de terminar depois de começar")
    return f


def criar_etiqueta(con, por, d):
    f = _etiqueta(d, parcial=False)
    if "sort" not in f:
        ult = um(con, "SELECT COALESCE(MAX(sort), 0) AS s FROM sim_day_tags")
        f["sort"] = (ult["s"] or 0) + 10
    return inserir(con, "sim_day_tags", **f, updated_by=por, updated_at=agora())


def mudar_etiqueta(con, por, tid, d):
    atual = um(con, "SELECT * FROM sim_day_tags WHERE id=?", (tid,))
    if not atual:
        raise ErroSim("etiqueta não existe")
    f = _etiqueta(d, parcial=True, atual=dict(atual))
    mud = {k: (atual[k], v) for k, v in f.items() if atual[k] != v}
    if mud:
        atualizar(con, "sim_day_tags", tid, **{k: v for k, (_, v) in mud.items()}, updated_by=por, updated_at=agora())
    return mud


def etiquetas_do_dia(ts, dia):
    """As etiquetas ativas de um dia (`date`): as da data primeiro, depois as do dia da semana, na ordem do painel.
    Cada uma com a faixa de horas (None = o dia inteiro) — o que o site mostra no calendário e no topo do dia."""
    iso, sem = dia.isoformat(), str(dia.weekday())
    da_data = [t for t in ts if t["active"] and t["date"] == iso]
    da_semana = [t for t in ts if t["active"] and not t["date"] and sem in (t["days"] or "")]
    return [{"label": t["label"], "icon": t["icon"] or "", "note": t["note"] or "", "start": t["start_hour"],
             "end": t["end_hour"]} for t in sorted(da_data, key=lambda t: (t["sort"], t["id"]))
            + sorted(da_semana, key=lambda t: (t["sort"], t["id"]))]


# ------------------------------------------------------------------ texto
def hora_txt(h):
    h = int(h) % 24
    if h == 0:
        return "midnight"
    if h == 12:
        return "noon"
    return f"{h % 12 or 12} {'AM' if h < 12 else 'PM'}"


def faixa_txt(ini, fim):
    return f"{hora_txt(ini)}–{'midnight' if fim >= 24 else hora_txt(fim)}"


def dias_txt(dias):
    ds = [int(c) for c in dias]
    if len(ds) > 1 and ds == list(range(ds[0], ds[-1] + 1)):
        return f"{DIAS_EN[ds[0]]}–{DIAS_EN[ds[-1]]}"
    return ", ".join(DIAS_EN[d] for d in ds)


def _usd(n):
    return f"${n:,.0f}" if float(n).is_integer() else f"${n:,.2f}"


def texto_das_faixas(fs, sid):
    """'Monday–Friday, 7 AM–5 PM: $50 per hour; …; Saturday–Sunday, 8 AM–midnight: call our team for options' (o FAQ)."""
    partes = [f"{dias_txt(f['days'])}, {faixa_txt(f['start_hour'], f['end_hour'])}: "
              + (f"{_usd(f['price'])} per hour" if f["price"] is not None else "call our team for options")
              for f in fs if f["service_id"] == sid and f["active"]]
    return "; ".join(partes) or "call our team for options"


def quando(d, hora, horas, lang="en"):
    """'Tue, Nov 3, 2026 · 6 PM–8 PM (2 h)'."""
    try:
        dia = date.fromisoformat(d)
    except (TypeError, ValueError):
        return str(d or "")
    if lang == "pt":
        from command_center.providers.pedido_site import DIAS_PT, MESES_PT
        txt = f"{DIAS_PT[dia.weekday()]}, {dia.day} de {MESES_PT[dia.month - 1]} de {dia.year}"
    else:
        txt = dia.strftime("%a, %b %d, %Y").replace(" 0", " ")
    return f"{txt} · {faixa_txt(hora, hora + horas)} ({horas} h)"


def slug(hora, horas):
    return f"sim:{int(hora)}:{int(horas)}"


def do_slug(s):
    """'sim:18:2' → (18, 2), ou None quando a linha não é de simulador."""
    m = re.fullmatch(r"sim:(\d{1,2}):(\d{1,2})", str(s or ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


# ------------------------------------------------------------------ vagas
def ocupacao(con, de, ate, sem_conta=None, sem_id=None):
    """{(dia, hora): pessoas} — as pagas e as seguradas que ainda valem. `sem_conta`: as seguradas desta conta não
    contam (é a mesma pessoa voltando do Stripe); `sem_id`: esta reserva não conta (conferindo ela mesma)."""
    rs = todos(con, """SELECT id, account_id, date, start_hour, hours, status, hold_until FROM sim_bookings
                        WHERE date BETWEEN ? AND ? AND (status='paga' OR (status='segurada' AND hold_until > ?))""",
               (str(de), str(ate), agora()))
    uso = {}
    for r in rs:
        if r["id"] == sem_id or (r["status"] == "segurada" and sem_conta and r["account_id"] == sem_conta):
            continue
        for h in range(r["start_hour"], r["start_hour"] + r["hours"]):
            uso[(r["date"], h)] = uso.get((r["date"], h), 0) + 1
    return uso


def _janela(cfg, hoje):
    de = hoje
    if cfg.get("open_from"):
        de = max(de, date.fromisoformat(cfg["open_from"]))
    return de, hoje + timedelta(days=cfg["horizon_days"])


def disponibilidade(con, conta=None):
    """O que o site mostra: os formatos, as regras públicas e, dia a dia, cada hora com as vagas e o preço de cada
    formato (None = ligar). Só entra hora que algum formato abre; hora passada da antecedência sai."""
    cfg = config(con)
    fs = faixas(con, ativos=True)
    forms = formatos(con)
    agora_ = _agora_fl()
    de, ate = _janela(cfg, agora_.date())
    uso = ocupacao(con, de.isoformat(), ate.isoformat(), sem_conta=conta)
    fora = fechadas(cfg)
    ts = etiquetas(con, ativos=True)
    limite = agora_ + timedelta(hours=cfg["min_notice_hours"])
    dias = []
    d = de
    while d <= ate and forms:
        iso = d.isoformat()
        horas = []
        if iso not in fora:
            for h in range(24):
                inicio = datetime(d.year, d.month, d.day, h, tzinfo=FUSO)
                if inicio < limite:
                    continue
                precos = {}
                for f in forms:
                    t = tarifa(fs, f["id"], d.weekday(), h)
                    if t:
                        precos[str(f["id"])] = t["price"]
                if precos:
                    horas.append({"h": h, "spots": max(0, cfg["capacity"] - uso.get((iso, h), 0)), "prices": precos})
        if horas:
            dias.append({"date": iso, "hours": horas, "tags": etiquetas_do_dia(ts, d)})
        d += timedelta(days=1)
    return {"config": publica(cfg), "formatos": [{k: f[k] for k in ("id", "name", "titulo", "linha", "texto", "deposit")}
                                                 for f in forms], "dias": dias}


def publica(cfg):
    return {"online": bool(cfg["online"]), "capacity": cfg["capacity"], "min_hours": cfg["min_hours"],
            "max_hours": cfg["max_hours"], "min_age": cfg["min_age"], "waiver_required": bool(cfg["waiver_required"]),
            "notice": cfg["notice"], "raffle_text": cfg["raffle_text"], "open_from": cfg["open_from"]}


def desde(con):
    """O menor preço por hora que se compra online (o "Starting at" da página), ou None."""
    ids = {f["id"] for f in formatos(con)}
    ps = [f["price"] for f in faixas(con, ativos=True) if f["price"] is not None and f["service_id"] in ids]
    return min(ps) if ps else None


# ------------------------------------------------------------------ a linha do carrinho
def linha(con, s, it, conta_id, uso, visao="cliente"):
    """A linha de simulador do carrinho (o serviço `s` é de kind='sim'). Preço = horas × a tarifa da faixa em que a
    sessão começa; cada hora precisa de vaga (contando o que já está no carrinho, em `uso`)."""
    cfg = config(con)
    d = str(it.get("data") or "")
    try:
        hora, horas = int(it.get("hora")), int(it.get("horas") or cfg["min_hours"])
    except (TypeError, ValueError):
        hora, horas = None, cfg["min_hours"]
    base = {"tipo": "sessao", "sim": True, "servico": s["id"], "data": d, "turno": None, "hora": hora, "horas": horas,
            "quantidade": 1, "piloto": _int(it.get("piloto")), "piloto_nome": None, "nome": s["name"],
            "detalhe": quando(d, hora, horas) if hora is not None else None, "unitario": 0,
            "deposito": float(s["deposit"] or 0), "link": "/sim2grid-racing-simulator/#booking", "erro": None,
            "sorteio": bool(it.get("sorteio")) and bool(cfg["raffle_text"])}
    if not cfg["online"]:
        return {**base, "erro": "Online booking for SIM2GRID is closed right now. Call us to book your session."}
    if s["deposit_required"] and not base["deposito"] > 0:
        return {**base, "erro": "This session can't be paid online right now. Please contact us to book it."}
    try:
        dia = date.fromisoformat(d)
    except ValueError:
        return {**base, "detalhe": None, "erro": "Choose a valid date."}
    if hora is None or not 0 <= hora <= 23:
        return {**base, "erro": "Choose a start time."}
    if not cfg["min_hours"] <= horas <= cfg["max_hours"]:
        return {**base, "erro": f"Choose from {cfg['min_hours']} to {cfg['max_hours']} hours in a row."}
    if hora + horas > 24:
        return {**base, "erro": "The session has to end by midnight."}
    agora_ = _agora_fl()
    de, ate = _janela(cfg, agora_.date())
    inicio = datetime(dia.year, dia.month, dia.day, hora, tzinfo=FUSO)
    if visao == "cliente" and (dia < de or dia > ate or dia.isoformat() in fechadas(cfg)
                               or inicio < agora_ + timedelta(hours=cfg["min_notice_hours"])):
        return {**base, "erro": "This time is no longer available. Please pick another one."}
    # vale o horário de início (dono, 22/10): todas as horas da sessão pela faixa em que ela começa
    t = tarifa(faixas(con, ativos=True), s["id"], dia.weekday(), hora)
    if not t:
        return {**base, "erro": "This time is no longer available. Please pick another one."}
    if t["price"] is None:
        return {**base, "erro": "This time is booked by phone. Call us and we book it for you."}
    base["unitario"] = round(float(t["price"]) * horas, 2)
    ocup = ocupacao(con, d, d, sem_conta=conta_id)
    if any(ocup.get((d, h), 0) + uso.get(("sim", d, h), 0) >= cfg["capacity"] for h in range(hora, hora + horas)):
        return {**base, "erro": "This time is full. Please pick another one."}
    for h in range(hora, hora + horas):
        uso[("sim", d, h)] = uso.get(("sim", d, h), 0) + 1
    return base


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def mesmo_piloto(uso, pid, d, hora, horas):
    """O mesmo piloto não fica em dois simuladores na mesma hora (no carrinho)."""
    hs = range(hora, hora + horas)
    if any(uso.get(("sim-piloto", pid, d, h)) for h in hs):
        return True
    for h in hs:
        uso[("sim-piloto", pid, d, h)] = 1
    return False


# ------------------------------------------------------------------ segurar, pagar, soltar
def _ate(minutos):
    t = datetime.now(timezone.utc) + timedelta(minutes=minutos)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


def segurar(con, o_id, item_id, conta_id, x, segundos):
    """O horário fica segurado enquanto o checkout do Stripe vale (dono, LP: "your time is held while you complete
    payment"). Uma linha por pessoa."""
    s = um(con, "SELECT name FROM booking_services WHERE id=?", (x["servico"],))
    return inserir(con, "sim_bookings", order_id=o_id, item_id=item_id, account_id=conta_id, pilot_id=x.get("piloto"),
                   service_id=x["servico"], service_name=(s or {}).get("name") or x["nome"], date=x["data"],
                   start_hour=x["hora"], hours=x["horas"], price=x["unitario"], status="segurada",
                   hold_until=_ate(segundos / 60), raffle=1 if x.get("sorteio") else 0, updated_at=agora())


def soltar_da_conta(con, conta_id):
    """Novo checkout da mesma conta: as seguradas dela de pedidos que não foram pagos deixam de ocupar."""
    if conta_id:
        con.execute("""UPDATE sim_bookings SET status='liberada', updated_at=?
                        WHERE account_id=? AND status='segurada'
                          AND order_id IN (SELECT id FROM store_orders WHERE status<>'pago')""", (agora(), conta_id))


def soltar_pedido(con, oid):
    """O checkout venceu ou falhou: as seguradas do pedido saem na hora (não esperam o relógio)."""
    con.execute("UPDATE sim_bookings SET status='liberada', updated_at=? WHERE order_id=? AND status='segurada'", (agora(), oid))


def do_item(con, item_id):
    return um(con, "SELECT * FROM sim_bookings WHERE item_id=? ORDER BY id DESC LIMIT 1", (item_id,))


def pagar(con, o, x):
    """O pedido foi pago: a segurada vira paga — se ainda cabe. Se a hora encheu (o checkout passou do prazo e outra
    pessoa pegou), devolve False e a linha fica "sem vaga" para a equipe; o pagamento não se perde."""
    b = do_item(con, x["id"])
    if not b:
        hd = do_slug(x["product_slug"])
        if not hd:
            return None
        bid = inserir(con, "sim_bookings", order_id=o["id"], item_id=x["id"], account_id=o["account_id"], pilot_id=x["pilot_id"],
                      service_id=x["service_id"], service_name=x["service_name"], date=x["date"], start_hour=hd[0], hours=hd[1],
                      price=x["unit_price"], status="liberada", updated_at=agora())
        b = um(con, "SELECT * FROM sim_bookings WHERE id=?", (bid,))
    if b["status"] == "paga":
        return b
    cfg = config(con)
    uso = ocupacao(con, b["date"], b["date"], sem_id=b["id"])
    if any(uso.get((b["date"], h), 0) >= cfg["capacity"] for h in range(b["start_hour"], b["start_hour"] + b["hours"])):
        atualizar(con, "sim_bookings", b["id"], status="liberada", note="a hora encheu antes do pagamento", updated_at=agora())
        return False
    atualizar(con, "sim_bookings", b["id"], status="paga", hold_until=None, updated_at=agora())
    return um(con, "SELECT * FROM sim_bookings WHERE id=?", (b["id"],))


# ------------------------------------------------------------------ o painel
def reservas(con, de=None, ate=None, limit=50, offset=0):
    """As reservas pagas e seguradas (a mais próxima primeiro), paginadas, com o card do piloto."""
    de = de or _agora_fl().date().isoformat()
    ate = ate or "9999-12-31"
    onde = "sb.date BETWEEN ? AND ? AND (sb.status='paga' OR (sb.status='segurada' AND sb.hold_until > ?))"
    args = (de, ate, agora())
    total = um(con, f"SELECT COUNT(*) AS n FROM sim_bookings sb WHERE {onde}", args)["n"]
    itens = todos(con, f"""SELECT sb.*, p.name AS pilot_name, a.name AS account_name, a.email AS account_email,
                                  c.name AS client_name
                             FROM sim_bookings sb LEFT JOIN portal_pilots p ON p.id=sb.pilot_id
                             LEFT JOIN portal_accounts a ON a.id=sb.account_id LEFT JOIN clients c ON c.id=sb.client_id
                            WHERE {onde} ORDER BY sb.date, sb.start_hour, sb.id LIMIT ? OFFSET ?""", (*args, limit, offset))
    return {"itens": itens, "total": total, "limit": limit, "offset": offset}


def painel(con):
    cfg = config(con)
    return {"config": cfg, "formatos": formatos(con, ativos=False), "faixas": faixas(con), "etiquetas": etiquetas(con)}
