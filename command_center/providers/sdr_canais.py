"""Robô SDR no SMS (Dialpad) e no e-mail (support@).

Dono, 20/10: "esse robô precisa ler o Dialpad para atender por lá e e-mail também". Respostas dele:
envio **automático, igual ao Instagram**; e-mail **só a caixa support@ e só lead**; o SMS chega pelo VPS
(o Heroku antigo não existe mais).

Quem faz o quê:
  * a **ponte do robô** (salesagent, `/tools/canal`) decide o que responder, com a mesma persona, as mesmas
    rotas e a mesma guarda do Instagram, sem tocar no Kommo;
  * este módulo é **dono do canal**: recebe o SMS (webhook do Dialpad) e o e-mail (leitura curta da support@),
    filtra quem não é lead, chama a ponte, envia, guarda a conversa e põe em "Precisa de atenção" o que o
    robô passou para a equipe.

Travas, todas em código (nenhuma depende do modelo):
  * desligado por padrão: `SDR_CANAL_SMS=1` e `SDR_CANAL_EMAIL=1` em `sdr-canais.env` (na pasta do bridge.env)
    ligam cada canal;
  * `SDR_CANAL_SO_PARA` (telefones e e-mails separados por vírgula) faz o papel da tag `teste-sdr`: com a
    lista, o robô só responde a quem está nela;
  * o nível do robô no painel vale aqui também: só **Atender** envia;
  * **só lead**: cliente do painel e oportunidade em aberto com o closer nunca recebem resposta do robô;
  * e-mail automático, newsletter, lista, resposta de férias e qualquer coisa de @urace.us são ignorados
    (robô nunca responde a robô);
  * **a pessoa assume**: SMS que saiu do número da empresa sem ser do robô, ou e-mail da equipe na conversa,
    pausa o robô naquele contato (`SDR_CANAL_PAUSA_HORAS`, 72 h por padrão);
  * "pare" / STOP: o robô confirma uma vez e nunca mais escreve para o contato;
  * sem follow-up automático nesta fase (SMS de follow-up é solicitação pela lei da Flórida, a FTSA).

Teste nunca envia: `CC_DIALPAD_FAKE=<arquivo>` e `CC_EMAIL_FAKE` gravam em arquivo, e `CC_PONTE_FAKE` responde
no lugar da ponte.
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from command_center.db import agora, atualizar, auditar, inserir, todos, um

CAIXA = "support"
CAIXA_EMAIL = "support@urace.us"
ASSINATURA = "Chase\nURACE · urace.us"

# ------------------------------------------------------------------ configuração
_cache_env = {"lido": None, "valores": {}}


def _caminho_env():
    # a mesma pasta do bridge.env que o painel já usa (URACE_DIR do serviço), não a home de quem roda
    base = os.environ.get("URACE_DIR") or os.path.expanduser("~/.urace")
    return Path(os.path.expanduser(os.environ.get("SDR_CANAIS_ENV") or os.path.join(base, "sdr-canais.env")))


def _ler_env():
    caminho = _caminho_env()
    try:
        marca = caminho.stat().st_mtime
    except OSError:
        return {}
    if _cache_env["lido"] != marca:
        valores = {}
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                k, v = linha.split("=", 1)
                valores[k.strip()] = v.strip().strip("'\"")
        _cache_env.update(lido=marca, valores=valores)
    return _cache_env["valores"]


def cfg(nome, padrao=""):
    return os.environ.get(nome) or _ler_env().get(nome, padrao)


def ligado(canal):
    return cfg(f"SDR_CANAL_{canal.upper()}") == "1"


def so_digitos(tel):
    return re.sub(r"\D", "", tel or "")


def contato_de(canal, valor):
    if canal != "sms":
        return (valor or "").strip().lower()
    d = so_digitos(valor)
    return "1" + d if len(d) == 10 else d                   # número dos EUA sem o 1 vira +1…


def permitido(canal, contato):
    """A lista de teste (`SDR_CANAL_SO_PARA`). Vazia: todo lead. Telefone compara pelos últimos 10 dígitos."""
    lista = [x.strip() for x in cfg("SDR_CANAL_SO_PARA").split(",") if x.strip()]
    if not lista:
        return True
    if canal == "sms":
        return any(so_digitos(x)[-10:] == contato[-10:] for x in lista if so_digitos(x))
    return contato in {x.lower() for x in lista}


def nivel():
    from command_center.api import sdr as sdr_api
    try:
        return sdr_api.nivel_gravado()
    except Exception:                                        # noqa: BLE001 — sem bridge.env: não atende
        return "observar"


def pausa_horas():
    try:
        return max(1, int(cfg("SDR_CANAL_PAUSA_HORAS", "72")))
    except ValueError:
        return 72


def _menos_minutos(m):
    return (datetime.now(timezone.utc) - timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _mais_horas(h):
    return (datetime.now(timezone.utc) + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


# ------------------------------------------------------------------ contatos e conversa
def contato(con, canal, valor, nome=None):
    c = contato_de(canal, valor)
    row = um(con, "SELECT * FROM sdr_canal_contatos WHERE canal=? AND contato=?", (canal, c))
    if not row:
        inserir(con, "sdr_canal_contatos", canal=canal, contato=c, nome=(nome or None))
        row = um(con, "SELECT * FROM sdr_canal_contatos WHERE canal=? AND contato=?", (canal, c))
    elif nome and not row["nome"]:
        atualizar(con, "sdr_canal_contatos", row["id"], nome=nome)
        row = dict(row, nome=nome)
    return row


def guardar(con, canal, contato_, direcao, por, texto, external_id=None, rota=None, motivo=None):
    """Grava a mensagem. Com `external_id` repetido não grava de novo e devolve False (evento duplicado)."""
    if external_id and um(con, "SELECT 1 FROM sdr_canal_mensagens WHERE canal=? AND external_id=?", (canal, external_id)):
        return False
    inserir(con, "sdr_canal_mensagens", canal=canal, contato=contato_, direcao=direcao, por=por,
            texto=(texto or "")[:4000], external_id=external_id, rota=rota, motivo=motivo, at=agora())
    return True


def pausado(row):
    return bool(row.get("pausado_ate")) and row["pausado_ate"] > agora()


def pausar(con, row, motivo):
    atualizar(con, "sdr_canal_contatos", row["id"], pausado_ate=_mais_horas(pausa_horas()), pausa_motivo=motivo)
    auditar(con, f"sdr.canal.{row['canal']}.pausa", "system", entity_type="sdr_canal", entity_id=row["id"],
            detail={"motivo": motivo, "horas": pausa_horas()})


# As etapas do Kommo em que o robô atende (as mesmas do Instagram); fora delas o card é da equipe.
ETAPAS_DO_ROBO = {"first contact", "cold leads", "follow up 1", "entrada"}
TAGS_DA_EQUIPE = {"escalated", "sdr:handoff", "sdr:agora-nao"}


def oportunidade_da_equipe(opp):
    """Oportunidade que já está com uma pessoa: tem closer, ou passou de NOVO. A que acabou de chegar pelo
    formulário do site (NOVO, sem closer) é lead para o robô (dono, 20/10: "ele monta o e-mail para follow up")."""
    return bool(opp.get("closer_user_id")) or (opp.get("stage") or "NOVO") != "NOVO"


def da_equipe(con, canal, valor):
    """Por que este contato é da equipe e não do robô (None = é lead para o robô). Cliente, oportunidade em
    aberto com o closer e card do Kommo fora das etapas do robô ou com tag de passagem."""
    from command_center.providers import identidade
    if canal == "sms":
        from command_center.api import dialpad
        achado = dialpad.liga_a_quem(con, valor)
        if achado.get("client_id"):
            return "cliente do painel: é a equipe que responde"
        if achado.get("opportunity_id"):
            opp = um(con, "SELECT stage, closer_user_id FROM opportunities WHERE id=?", (achado["opportunity_id"],))
            if opp and oportunidade_da_equipe(opp):
                return "oportunidade em aberto com o closer"
        lead = um(con, "SELECT * FROM crm_leads WHERE id=?", (achado["lead_id"],)) if achado.get("lead_id") else None
    else:
        email = contato_de("email", valor)
        cli, _ = identidade.acha_pessoa(con, email=email)
        if cli:
            return "cliente do painel: é a equipe que responde"
        for opp in todos(con, "SELECT stage, closer_user_id FROM opportunities WHERE email=? AND stage NOT IN ('GANHO','PERDIDO')",
                         (email,)):
            if oportunidade_da_equipe(opp):
                return "oportunidade em aberto com o closer"
        lead = um(con, "SELECT * FROM crm_leads WHERE contact_email=? ORDER BY id DESC LIMIT 1", (email,))
    if lead:
        try:
            tags = {str(x).lower() for x in json.loads(lead.get("tags") or "[]")}
        except (ValueError, TypeError):
            tags = set()
        if tags & TAGS_DA_EQUIPE:
            return f"card do Kommo com a equipe ({', '.join(sorted(tags & TAGS_DA_EQUIPE))})"
        etapa = (lead.get("stage_name") or "").strip().lower()
        if etapa and etapa not in ETAPAS_DO_ROBO:
            return f"card do Kommo em {lead.get('stage_name')}: é a equipe que responde"
    return None


def bloqueio(con, canal, row, cliente=False):
    """Por que o robô NÃO responde a este contato agora (None = pode responder)."""
    if not ligado(canal):
        return f"canal {canal} desligado (SDR_CANAL_{canal.upper()})"
    if nivel() != "atender":
        return f"nível do robô: {nivel()} (só Atender envia)"
    if not permitido(canal, row["contato"]):
        return "fora da lista de teste (SDR_CANAL_SO_PARA)"
    if row.get("opt_out"):
        return "pediu para parar"
    if pausado(row):
        return f"uma pessoa assumiu ({row.get('pausa_motivo') or 'pausa'})"
    if row.get("precisa_gente"):
        return "o robô já passou esta conversa para a equipe (resolva em Precisa de atenção)"
    if cliente:
        return cliente if isinstance(cliente, str) else "cliente ou oportunidade com o closer: é a equipe que responde"
    return None


# ------------------------------------------------------------------ a ponte do robô
def perguntar_ao_robo(canal, contato_, texto, nome, primeira):
    """POST /tools/canal na ponte. Devolve {rota, motivo, mensagens, precisa_gente, nota, ...}."""
    falso = os.environ.get("CC_PONTE_FAKE")
    if falso:                                    # teste: a resposta da ponte vem de um arquivo JSON
        return json.loads(Path(falso).read_text(encoding="utf-8"))
    from command_center.api import sdr as sdr_api
    chave = sdr_api._chave_da_ponte()
    if not chave:
        raise RuntimeError("a ponte do robô não está configurada neste servidor (AGENT_API_KEY)")
    corpo = json.dumps({"canal": canal, "contato": contato_, "texto": texto, "nome": nome or "",
                        "primeira": bool(primeira)}).encode()
    pedido = urllib.request.Request(sdr_api.PONTE + "/tools/canal", data=corpo, method="POST",
                                    headers={"Content-Type": "application/json", "X-Api-Key": chave})
    with urllib.request.urlopen(pedido, timeout=150) as resp:
        return json.loads(resp.read() or b"{}")


def falhou_envio(con, row, canal, erro):
    atualizar(con, "sdr_canal_contatos", row["id"], precisa_gente=1,
              precisa_motivo=f"O robô não conseguiu enviar a resposta por {canal}: {str(erro)[:160]}")
    auditar(con, f"sdr.canal.{canal}.falhou", "system", entity_type="sdr_canal", entity_id=row["id"],
            detail={"erro": f"{type(erro).__name__}: {str(erro)[:300]}"})
    con.commit()


def _depois_de_responder(con, row, resposta, quando):
    campos = {"respostas": (row.get("respostas") or 0) + 1, "ultima_resposta_em": quando}
    if resposta.get("rota") == "confirmar_opt_out":
        campos["opt_out"] = 1
    if resposta.get("precisa_gente"):
        campos["precisa_gente"] = 1
        campos["precisa_motivo"] = (resposta.get("nota") or resposta.get("motivo") or "o robô passou para a equipe")[:300]
    atualizar(con, "sdr_canal_contatos", row["id"], **campos)


# ------------------------------------------------------------------ SMS (Dialpad)
def eh_sms(ev):
    """O evento do webhook é de SMS (e não de ligação)? Os nomes exatos se confirmam no primeiro evento real,
    que fica em dialpad-webhook-ultimo.json; aqui valem as variações conhecidas."""
    if not isinstance(ev, dict) or ev.get("call_id") or isinstance(ev.get("call"), dict):
        return False
    tipo = str(ev.get("event_type") or ev.get("type") or "").lower()
    return "sms" in tipo or any(k in ev for k in ("text", "text_content", "message_status", "mms"))


def normaliza_sms(ev):
    direcao = str(ev.get("direction") or "").lower()
    saida = direcao.startswith("out")
    para = ev.get("to_number") or ev.get("to_numbers") or ev.get("to")
    if isinstance(para, list):
        para = para[0] if para else None
    contato_ev = ev.get("contact") if isinstance(ev.get("contact"), dict) else {}
    externo = (para if saida else (ev.get("from_number") or ev.get("from"))) or contato_ev.get("phone_number") or contato_ev.get("phone")
    return {
        "id": str(ev.get("id") or ev.get("message_id") or ev.get("sms_id") or "") or None,
        "saida": saida,
        "numero": str(externo or ""),
        "texto": str(ev.get("text") or ev.get("text_content") or ev.get("body") or "").strip(),
        "nome": contato_ev.get("name") or ev.get("contact_name"),
        "interno": bool(ev.get("is_internal")),
    }


def _norm_texto(t):
    return " ".join((t or "").lower().split())


def enviar_sms(numero, texto):
    """POST /api/v2/sms do Dialpad, do número da empresa. Corpo confirmado no primeiro envio real."""
    falso = os.environ.get("CC_DIALPAD_FAKE")
    if falso:
        with open(falso, "a", encoding="utf-8") as f:
            f.write(json.dumps({"to": numero, "text": texto}, ensure_ascii=False) + "\n")
        return {"id": f"fake-{time.time_ns()}"}
    from command_center.api import dialpad
    api = dialpad._cfg("DIALPAD_API_KEY")
    if not api:
        raise RuntimeError("DIALPAD_API_KEY ausente em ~/.urace/dialpad.env")
    corpo = {"text": texto, "to_numbers": [numero if numero.startswith("+") else "+" + so_digitos(numero)],
             "infer_country_code": False}
    remetente = dialpad._cfg("DIALPAD_SMS_FROM")
    usuario = dialpad._cfg("DIALPAD_SMS_USER_ID") or dialpad._cfg("DIALPAD_USER_ID")
    if remetente:
        corpo["from_number"] = remetente
    if usuario:
        corpo["user_id"] = usuario
    req = urllib.request.Request("https://dialpad.com/api/v2/sms", data=json.dumps(corpo).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {api}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            return json.loads(res.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Dialpad recusou o SMS ({e.code}): {e.read().decode('utf-8', 'replace')[:200]}")


def _intervalo(texto):
    return min(6.0, 1.5 + 0.03 * len(texto or ""))


def sms_evento(con, ev, esperar=True):
    """Um evento de SMS do webhook. Grava; se for do lead e o robô puder, responde (em segundo plano no
    servidor, para o webhook voltar rápido ao Dialpad). Devolve o que foi decidido."""
    s = normaliza_sms(ev)
    if not s["numero"] or s["interno"]:
        return {"sms": "ignorado", "motivo": "sem número ou SMS interno"}
    row = contato(con, "sms", s["numero"], s["nome"])
    if s["saida"]:
        # o eco do que o robô mandou volta aqui (assinatura "all"); o resto foi uma pessoa da equipe
        recentes = todos(con, """SELECT texto FROM sdr_canal_mensagens WHERE canal='sms' AND contato=? AND por='robo'
                                 AND direcao='saida' ORDER BY id DESC LIMIT 12""", (row["contato"],))
        if any(_norm_texto(r["texto"]) == _norm_texto(s["texto"]) for r in recentes):
            return {"sms": "eco do robô"}
        if guardar(con, "sms", row["contato"], "saida", "equipe", s["texto"], s["id"]):
            pausar(con, row, "a equipe respondeu por SMS")
            con.commit()
        return {"sms": "a equipe respondeu: robô pausado neste número"}
    if not s["texto"]:
        return {"sms": "ignorado", "motivo": "sem texto"}
    if not guardar(con, "sms", row["contato"], "entrada", "lead", s["texto"], s["id"]):
        return {"sms": "duplicado"}
    atualizar(con, "sdr_canal_contatos", row["id"], ultima_entrada_em=agora())
    # STOP (lei e operadora): vale sempre, com o robô ligado ou não. Quem confirma é o Dialpad (ele trata STOP, UNSTOP
    # e HELP sozinho e bloqueia a resposta para quem mandou STOP); o robô só nunca mais escreve. UNSTOP/START devolve.
    if _STOP.match(s["texto"]):
        atualizar(con, "sdr_canal_contatos", row["id"], opt_out=1)
        auditar(con, "sdr.canal.sms.stop", "system", entity_type="sdr_canal", entity_id=row["id"])
        con.commit()
        return {"sms": "recebido", "robo": "STOP: nunca mais escreve para este número"}
    if _HELP.match(s["texto"]):
        con.commit()
        return {"sms": "recebido", "robo": "HELP: o Dialpad responde com a mensagem de ajuda"}
    if _START.match(s["texto"]) and row.get("opt_out"):
        atualizar(con, "sdr_canal_contatos", row["id"], opt_out=0)
        row = dict(row, opt_out=0)
    con.commit()
    motivo = bloqueio(con, "sms", row, cliente=da_equipe(con, "sms", s["numero"]))
    if motivo:
        auditar(con, "sdr.canal.sms.sem_resposta", "system", entity_type="sdr_canal", entity_id=row["id"],
                detail={"motivo": motivo})
        con.commit()
        return {"sms": "recebido", "robo": motivo}
    gatilho = um(con, "SELECT MAX(id) AS id FROM sdr_canal_mensagens WHERE canal='sms' AND contato=? AND por='lead'",
                 (row["contato"],))["id"]
    if not esperar:
        return {"sms": "recebido", **responder_sms(con, row["id"], esperar=False)}
    threading.Thread(target=_responder_sms_depois, args=(row["id"], gatilho), daemon=True, name="sdr-sms").start()
    return {"sms": "recebido", "robo": "respondendo"}


_STOP = re.compile(r"^\W*(stop|stopall|unsubscribe|cancel|end|quit|pare|parar|alto|arr[eê]t)\W*$", re.I)
_START = re.compile(r"^\W*(start|unstop)\W*$", re.I)
# HELP/INFO sozinho: o Dialpad responde sozinho com a mensagem de ajuda do escritório (Admin Settings → Office →
# Help Message). O robô não responde junto (duas respostas para o mesmo HELP).
_HELP = re.compile(r"^\W*(help|info|ajuda|ayuda)\W*$", re.I)
_TRAVAS = {}
_TRAVAS_LOCK = threading.Lock()


def _trava(contato_id):
    with _TRAVAS_LOCK:
        return _TRAVAS.setdefault(contato_id, threading.Lock())


def _responder_sms_depois(contato_id, gatilho):
    from command_center.db import conectar
    time.sleep(float(cfg("SDR_CANAL_RAJADA_SEG", "8")))     # "oi" + "quanto custa" logo em seguida: uma resposta só
    con = conectar()
    try:
        row = um(con, "SELECT contato FROM sdr_canal_contatos WHERE id=?", (contato_id,))
        ultima = um(con, "SELECT MAX(id) AS id FROM sdr_canal_mensagens WHERE canal='sms' AND contato=? AND por='lead'",
                    (row["contato"],))["id"]
        if ultima and gatilho and ultima > gatilho:
            return                                          # chegou mensagem mais nova: a thread dela responde tudo
        responder_sms(con, contato_id)
    except Exception as e:                                  # noqa: BLE001 — nunca derruba o servidor
        auditar(con, "sdr.canal.sms.falhou", "system", entity_type="sdr_canal", entity_id=contato_id,
                detail={"erro": f"{type(e).__name__}: {str(e)[:300]}"})
        con.commit()
    finally:
        con.close()


def responder_sms(con, contato_id, esperar=True):
    """Responde o que o lead mandou desde a última resposta do robô, numa resposta só (uma por vez por contato)."""
    with _trava(contato_id):
        return _responder_sms(con, contato_id, esperar)


def _responder_sms(con, contato_id, esperar):
    row = um(con, "SELECT * FROM sdr_canal_contatos WHERE id=?", (contato_id,))
    novas = todos(con, """SELECT * FROM sdr_canal_mensagens WHERE canal='sms' AND contato=? AND por='lead'
                          AND id > COALESCE((SELECT MAX(id) FROM sdr_canal_mensagens WHERE canal='sms' AND contato=?
                                             AND direcao='saida'), 0) ORDER BY id""", (row["contato"], row["contato"]))
    if not novas or (row.get("ultima_tratada") and novas[-1]["external_id"] == row["ultima_tratada"]):
        return {"robo": "nada novo"}
    motivo = bloqueio(con, "sms", row)                       # pode ter mudado durante a espera (a pessoa assumiu)
    if motivo:
        return {"robo": motivo}
    texto = "\n".join(m["texto"] for m in novas)
    resposta = perguntar_ao_robo("sms", row["contato"], texto, row.get("nome"), (row.get("respostas") or 0) == 0)
    baloes = [b for b in (resposta.get("mensagens") or []) if b.strip()]
    for i, balao in enumerate(baloes):
        if i and esperar:
            time.sleep(_intervalo(balao))
        # grava ANTES de enviar: o eco do Dialpad pode chegar antes do envio voltar, e sem a linha o robô
        # pausaria a si mesmo achando que foi a equipe
        guardar(con, "sms", row["contato"], "saida", "robo", balao, None, resposta.get("rota"), resposta.get("motivo"))
        mid = um(con, "SELECT MAX(id) AS id FROM sdr_canal_mensagens WHERE canal='sms' AND contato=? AND por='robo'",
                 (row["contato"],))["id"]
        con.commit()
        try:
            enviado = enviar_sms("+" + row["contato"], balao)
        except Exception as e:                              # noqa: BLE001
            con.execute("DELETE FROM sdr_canal_mensagens WHERE id=?", (mid,))
            falhou_envio(con, row, "SMS", e)
            return {"robo": "falhou o envio", "erro": str(e)[:200]}
        if enviado.get("id"):
            atualizar(con, "sdr_canal_mensagens", mid, external_id=str(enviado["id"]))
            con.commit()
    _depois_de_responder(con, row, resposta, agora())
    atualizar(con, "sdr_canal_contatos", row["id"], ultima_tratada=novas[-1]["external_id"])
    auditar(con, "sdr.canal.sms.resposta", "system", entity_type="sdr_canal", entity_id=row["id"],
            detail={"rota": resposta.get("rota"), "motivo": resposta.get("motivo"), "baloes": len(baloes)})
    con.commit()
    return {"robo": "respondeu", "rota": resposta.get("rota"), "baloes": len(baloes)}


# ------------------------------------------------------------------ e-mail (support@)
_AUTOMATICO = re.compile(r"(no-?reply|do-?not-?reply|mailer-daemon|postmaster|notifications?@|bounce|"
                         r"newsletter|marketing@|news@|info@.*\.(?:mailchimp|sendgrid))", re.I)
_LABELS_OK = {"INBOX", "UNREAD", "IMPORTANT", "STARRED", "CATEGORY_PERSONAL"}
_CITACAO = re.compile(r"^(On .+ wrote:|Em .+ escreveu:|El .+ escribió:|Le .+ a écrit ?:|-----Original Message-----|"
                      r"From: .+|De: .+|Sent from my )", re.M)


def _email_de(remetente):
    m = re.search(r"<([^>]+)>", remetente or "")
    return (m.group(1) if m else (remetente or "")).strip().lower()


def _nome_de(remetente):
    nome = (remetente or "").split("<")[0].strip().strip('"')
    return nome if nome and "@" not in nome else None


def sem_citacao(corpo):
    """Só o que a pessoa escreveu agora: corta a citação da mensagem anterior."""
    texto = corpo or ""
    m = _CITACAO.search(texto)
    if m:
        texto = texto[:m.start()]
    linhas = [l for l in texto.splitlines() if not l.lstrip().startswith(">")]
    return "\n".join(linhas).strip()[:3000]


def automatico(remetente, cabecalhos, marcadores):
    """E-mail que não é de uma pessoa escrevendo para nós: o robô não responde."""
    email = _email_de(remetente)
    if not email or "@" not in email or email.endswith("@urace.us") or _AUTOMATICO.search(email):
        return "remetente automático ou da URACE"
    h = {k.lower(): (v or "").lower() for k, v in (cabecalhos or {}).items()}
    if h.get("auto-submitted") and h["auto-submitted"] != "no":
        return "resposta automática (Auto-Submitted)"
    if h.get("precedence") in ("bulk", "list", "junk", "auto_reply"):
        return "lista ou envio em massa (Precedence)"
    if h.get("list-unsubscribe") or h.get("list-id"):
        return "newsletter ou lista"
    if h.get("x-autoreply") or h.get("x-autorespond"):
        return "resposta automática"
    extras = [m for m in (marcadores or []) if m not in _LABELS_OK]
    if extras:
        return f"marcado pelo filtro do Gmail ({', '.join(extras[:3])}): não é lead"
    return None


def enviar_email(para, assunto, corpo, thread_id, em_resposta_a):
    from command_center.providers import chamar
    if os.environ.get("CC_EMAIL_FAKE"):
        with open(os.environ["CC_EMAIL_FAKE"], "a", encoding="utf-8") as f:
            f.write(json.dumps({"from": CAIXA_EMAIL, "to": para, "subject": assunto, "text": corpo,
                                "thread_id": thread_id, "in_reply_to": em_resposta_a}, ensure_ascii=False) + "\n")
        return {"id": f"fake-{time.time_ns()}", "thread_id": thread_id}
    return chamar("gmail", "enviar_sistema", conta=CAIXA, para=para, assunto=assunto, corpo=corpo,
                  thread_id=thread_id, em_resposta_a=em_resposta_a)


def _ler_caixa():
    """As conversas recentes da support@ na inbox e a thread de cada uma (gmail_mcp). Em teste, um arquivo."""
    falso = os.environ.get("CC_GMAIL_FAKE")
    if falso:
        return json.loads(Path(falso).read_text(encoding="utf-8"))
    from command_center.providers import chamar
    r = chamar("gmail", "gmail_buscar", conta=CAIXA, consulta="newer_than:2d", so_inbox=True, maximo=25)
    saida = []
    for t in r.get("threads", []):
        th = chamar("gmail", "mensagens_da_thread", conta=CAIXA, thread_id=t["thread_id"], limite=6000)
        if th.get("mensagens"):
            ultima = th["mensagens"][-1]
            ultima["cabecalhos"] = chamar("gmail", "cabecalhos", conta=CAIXA, message_id=ultima["message_id"])
        saida.append(th)
    return saida


def ler_email(con):
    """Uma passada na support@: responde o que for lead e ainda não foi respondido."""
    if not ligado("email"):
        return {"email": "desligado"}
    feitos = []
    robo_ids = {r["external_id"] for r in todos(con, """SELECT external_id FROM sdr_canal_mensagens
                                                       WHERE canal='email' AND por='robo' AND external_id IS NOT NULL""")}
    for th in _ler_caixa():
        msgs = th.get("mensagens") or []
        if not msgs:
            continue
        ultima = msgs[-1]
        remetente = ultima.get("de") or ""
        email = _email_de(remetente)
        if email == CAIXA_EMAIL or email.endswith("@urace.us"):
            continue                                         # a última é nossa: nada a responder
        row = contato(con, "email", email, _nome_de(remetente))
        if row.get("ultima_tratada") == ultima["message_id"]:
            continue
        # uma pessoa da equipe já escreveu nesta conversa (e não foi o robô): é dela
        equipe = [m for m in msgs[:-1] if _email_de(m.get("de")).endswith("@urace.us") and m["message_id"] not in robo_ids]
        auto = automatico(remetente, ultima.get("cabecalhos"), ultima.get("marcadores"))
        cliente = da_equipe(con, "email", email)
        nova = guardar(con, "email", row["contato"], "entrada", "lead", sem_citacao(ultima.get("corpo")), ultima["message_id"])
        if nova:
            atualizar(con, "sdr_canal_contatos", row["id"], ultima_entrada_em=agora(), thread_id=th.get("thread_id"))
        else:
            vista = um(con, "SELECT at FROM sdr_canal_mensagens WHERE canal='email' AND external_id=?", (ultima["message_id"],))
            if vista and vista["at"] < _menos_minutos(30):
                # visto há mais de 30 min e não respondido (canal desligado, fora da lista): ligar o robô não
                # dispara resposta para e-mail velho de uma vez
                atualizar(con, "sdr_canal_contatos", row["id"], ultima_tratada=ultima["message_id"])
                con.commit()
                continue
        if equipe and not pausado(row):
            pausar(con, row, "a equipe respondeu por e-mail")
            row = um(con, "SELECT * FROM sdr_canal_contatos WHERE id=?", (row["id"],))
        motivo = auto or bloqueio(con, "email", row, cliente=cliente)
        if motivo:
            if auto or cliente or row.get("opt_out") or pausado(row) or row.get("precisa_gente"):   # definitivo
                atualizar(con, "sdr_canal_contatos", row["id"], ultima_tratada=ultima["message_id"])
            if nova:                                          # uma auditoria por mensagem, não uma por passada
                auditar(con, "sdr.canal.email.sem_resposta", "system", entity_type="sdr_canal", entity_id=row["id"],
                        detail={"motivo": motivo})
            con.commit()
            feitos.append({"para": email, "robo": motivo})
            continue
        texto = sem_citacao(ultima.get("corpo"))
        if (row.get("respostas") or 0) == 0 and ultima.get("assunto"):
            texto = f"{ultima['assunto']}\n{texto}"
        resposta = perguntar_ao_robo("email", row["contato"], texto, row.get("nome"), (row.get("respostas") or 0) == 0)
        baloes = [b for b in (resposta.get("mensagens") or []) if b.strip()]
        if not baloes:
            atualizar(con, "sdr_canal_contatos", row["id"], ultima_tratada=ultima["message_id"])
            con.commit()
            feitos.append({"para": email, "robo": resposta.get("nota") or "sem resposta"})
            continue
        assunto = ultima.get("assunto") or "URACE"
        if not assunto.lower().startswith("re:"):
            assunto = "Re: " + assunto
        corpo = "\n\n".join(baloes) + "\n\n" + ASSINATURA
        try:
            enviado = enviar_email(email, assunto, corpo, th.get("thread_id"), ultima.get("message_id_header"))
        except Exception as e:                                # noqa: BLE001
            atualizar(con, "sdr_canal_contatos", row["id"], ultima_tratada=ultima["message_id"])
            falhou_envio(con, row, "e-mail", e)
            feitos.append({"para": email, "robo": "falhou o envio"})
            continue
        guardar(con, "email", row["contato"], "saida", "robo", corpo, enviado.get("id"), resposta.get("rota"),
                resposta.get("motivo"))
        _depois_de_responder(con, row, resposta, agora())
        atualizar(con, "sdr_canal_contatos", row["id"], ultima_tratada=ultima["message_id"])
        auditar(con, "sdr.canal.email.resposta", "system", entity_type="sdr_canal", entity_id=row["id"],
                detail={"rota": resposta.get("rota"), "motivo": resposta.get("motivo"), "paragrafos": len(baloes)})
        con.commit()
        feitos.append({"para": email, "robo": "respondeu", "rota": resposta.get("rota")})
    return {"email": "lido", "conversas": feitos}


# ------------------------------------------------------------------ formulário do site (dono, 20/10)
def vai_responder_formulario(con, email):
    """O robô vai escrever o follow-up de quem preencheu o formulário? (Senão sai a confirmação de sempre.)"""
    row = contato(con, "email", email)
    return bloqueio(con, "email", row, cliente=da_equipe(con, "email", email)) is None


def responder_formulario(con, oid, nome, email, assunto, mensagem):
    """O follow-up do formulário de contato: o robô lê o que a pessoa escreveu e responde da support@, no lugar da
    confirmação genérica. A resposta dela cai na support@ e segue com o robô (ou com quem assumir). Devolve True
    se enviou; com False, quem chamou manda a confirmação de sempre."""
    row = contato(con, "email", email, nome)
    if bloqueio(con, "email", row, cliente=da_equipe(con, "email", email)):
        return False
    texto = f"{assunto}\n{mensagem}"
    guardar(con, "email", row["contato"], "entrada", "lead", texto, f"site-{oid}")
    resposta = perguntar_ao_robo("email", row["contato"], texto, nome, (row.get("respostas") or 0) == 0)
    baloes = [b for b in (resposta.get("mensagens") or []) if b.strip()]
    if not baloes:
        return False
    corpo = "\n\n".join(baloes) + "\n\n" + ASSINATURA
    try:
        enviado = enviar_email(email, f"{assunto} | URACE", corpo, None, None)
    except Exception as e:                                    # noqa: BLE001
        falhou_envio(con, row, "e-mail", e)
        return False
    guardar(con, "email", row["contato"], "saida", "robo", corpo, enviado.get("id"), resposta.get("rota"),
            resposta.get("motivo"))
    _depois_de_responder(con, row, resposta, agora())
    atualizar(con, "sdr_canal_contatos", row["id"], ultima_entrada_em=agora(),
              thread_id=enviado.get("thread_id") or row.get("thread_id"))
    inserir(con, "opp_events", opp_id=oid, kind="note", title="O robô respondeu por e-mail (support@)",
            detail=corpo[:2000], at=agora(), actor="sdr")
    auditar(con, "sdr.canal.email.formulario", "system", entity_type="opportunity", entity_id=oid,
            detail={"rota": resposta.get("rota"), "paragrafos": len(baloes)})
    con.commit()
    return True


def laco_email():
    """Lê a support@ a cada `SDR_CANAL_EMAIL_MIN` minutos (3 por padrão), antes da triagem arquivar."""
    from command_center.db import conectar
    time.sleep(30)
    while True:
        if ligado("email"):
            con = conectar()
            try:
                ler_email(con)
            except Exception as e:                           # noqa: BLE001
                try:
                    auditar(con, "sdr.canal.email.falhou", "system", detail={"erro": f"{type(e).__name__}: {str(e)[:300]}"})
                    con.commit()
                except Exception:                            # noqa: BLE001
                    pass
            finally:
                con.close()
        try:
            minutos = max(1, int(cfg("SDR_CANAL_EMAIL_MIN", "3")))
        except ValueError:
            minutos = 3
        time.sleep(60 * minutos)


# ------------------------------------------------------------------ painel
def resumo(con):
    contatos = todos(con, """SELECT id, canal, contato, nome, respostas, opt_out, pausado_ate, pausa_motivo, precisa_gente,
                                    precisa_motivo, ultima_entrada_em, ultima_resposta_em
                               FROM sdr_canal_contatos ORDER BY COALESCE(ultima_entrada_em, '') DESC LIMIT 50""")
    caminho = _caminho_env()
    return {"configuracao": {"arquivo": str(caminho), "existe": caminho.exists()},
            "sms": {"ligado": ligado("sms")}, "email": {"ligado": ligado("email"), "caixa": CAIXA_EMAIL},
            "nivel": nivel(), "lista_de_teste": bool(cfg("SDR_CANAL_SO_PARA")),
            "pausa_horas": pausa_horas(), "contatos": contatos}
