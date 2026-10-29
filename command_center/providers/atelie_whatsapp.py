"""WhatsApp dos grupos do ateliê (#383): o agente de Suits também nos grupos internos, pelo OpenClaw.

Dono, 22/10: o OpenClaw serve só para a VPS acessar os grupos internos da URACE. Dois grupos, por ora:
"Macacão design Urace" (o pedido de design vai ao designer, a arte volta, o ajuste vai de novo) e
"Urace Suits - Usman" (o fornecedor: cobrar, conferir o suit e, depois de aprovado, mandar o endereço de
envio e pedir o rastreio). DM desligada; outro grupo ou pessoa nem chega aqui. A lista é configurável.

Como funciona:
- **Entrada.** O plugin `urace-atelie` do OpenClaw (adminai/openclaw/urace-atelie) cala o agente do OpenClaw
  nesses grupos e manda cada mensagem (com a mídia) para `POST /ops/api/atelie/whatsapp/entrada`, só de
  127.0.0.1 e com o segredo de `~/.urace/whatsapp-grupos.env`. `receber()` grava, liga ao pedido só com
  evidência clara (resposta citando a nossa mensagem, "#número", nome do piloto/do design) e, se ambíguo,
  manda para a equipe. Nunca adivinha.
- **O agente.** A cada ciclo do painel, a mensagem nova de um pedido vai para a IA de Suits (a mesma da
  ponte de e-mail, #153/#152) com as ferramentas `atelie_*`; a cobrança diária é do painel, não da IA.
- **Saída.** `propor()` é o único caminho para um grupo. Segue a MESMA chave "envio automático" da ponte:
  desligada (o padrão), vira rascunho com "aprovar" de um clique no pedido; ligada, sai sozinho. Sair de
  verdade é `openclaw message send` — e só com `WA_GRUPOS_APLICAR=1` no env; antes disso, tudo fica rascunho.
- **Guardas.** O designer recebe só o design (sem nome completo, e-mail, telefone, endereço ou pagamento do
  cliente; os anexos passam pela `limpar_para_designer` da ponte, #382). O endereço só vai ao fornecedor com o pedido
  em Checked (o OK da equipe nas fotos, #382), e mandar o endereço move para Address sent. Pedido de teste
  (`is_test`) nunca manda de verdade: vira nota.
Teste nunca manda: `CC_WA_FAKE=<arquivo>` grava em vez de chamar o OpenClaw.
"""
import base64
import json
import os
import re
import shutil
import subprocess
import threading
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

from command_center.db import agora, auditar, conectar, inserir, todos, um

FUSO = ZoneInfo("America/New_York")
PAPEIS = {"design": "grupo de design", "fornecedor": "grupo do fornecedor"}
MIDIA_MAX = 25 * 1024 * 1024
POR_CICLO = int(os.environ.get("CC_ATELIE_POR_CICLO", "5"))
HORAS_COBRANCA = (9, 18)            # cobra entre 09:00 e 17:59 da Flórida, de segunda a sábado


class Recusado(ValueError):
    """A mensagem não pode ir ao grupo como está; o texto diz por quê (a IA lê e corrige)."""


# ------------------------------------------------------------------ configuração
def _urace_dir():
    return os.environ.get("URACE_DIR", os.path.expanduser("~/.urace"))


def arquivo_env():
    return os.environ.get("CC_WA_GRUPOS_ENV") or os.path.join(_urace_dir(), "whatsapp-grupos.env")


def ler_env(caminho=None):
    """KEY=VALOR por linha (aspas opcionais, # comenta). Arquivo ausente = {}."""
    caminho = caminho or arquivo_env()
    saida = {}
    try:
        with open(caminho, encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha or linha.startswith("#") or "=" not in linha:
                    continue
                k, v = linha.split("=", 1)
                v = v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                    v = v[1:-1]
                saida[k.strip()] = v
    except OSError:
        return {}
    return saida


def config():
    """O que vale agora (lido do arquivo a cada vez: mudar o env não pede reiniciar o serviço)."""
    e = ler_env()
    grupos = []
    for papel in re.split(r"[,\s]+", e.get("WA_GRUPOS", "design,fornecedor").strip().lower()):
        if not re.fullmatch(r"[a-z_]{2,30}", papel or ""):
            continue
        p = papel.upper()
        jid = e.get(f"WA_GRUPO_{p}_JID", "").strip()
        grupos.append({"papel": papel, "nome": e.get(f"WA_GRUPO_{p}_NOME", "").strip(),
                       "jid": jid if jid.endswith("@g.us") else "",
                       "idioma": (e.get(f"WA_GRUPO_{p}_IDIOMA") or ("pt" if papel == "design" else "en")).strip()})
    return {"existe": os.path.isfile(arquivo_env()), "arquivo": arquivo_env(), "aplicar": e.get("WA_GRUPOS_APLICAR") == "1",
            "token": e.get("WA_GRUPOS_TOKEN") or None, "conta": e.get("WA_GRUPOS_CONTA") or None,
            "numero": e.get("WA_GRUPOS_NUMERO") or None, "grupos": grupos}


def grupo(cfg, papel=None, jid=None):
    for g in cfg["grupos"]:
        if g["jid"] and ((papel and g["papel"] == papel) or (jid and g["jid"] == jid)):
            return g
    return None


def _ponte():
    from command_center.providers import suits_ponte
    return suits_ponte


def _hoje():
    return datetime.now(FUSO)


# ------------------------------------------------------------------ vincular ao pedido
def _norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


RX_NUMERO = re.compile(r"(?:\bsuits?\s*#?\s*|\bpedido\s*#?\s*|\border\s*#?\s*|#\s?)(\d{1,6})\b", re.I)


def _abertos(con):
    return todos(con, """SELECT id, title, driver_name, design FROM suit_orders
                         WHERE closed=0 AND discarded_at IS NULL ORDER BY id""")


def evidencia(con, texto, nomes_arquivos=(), resposta_a=None, grupo_jid=None):
    """(pedido | None, vínculo, candidatos). Só evidência clara: a resposta citando uma mensagem já ligada,
    o "#número" de um pedido, ou o nome (piloto / nome do design / título) de UM pedido aberto. Mais de um
    pedido possível → ambígua (a equipe escolhe). Nada → sem pedido."""
    alvo = " ".join([texto or "", *nomes_arquivos])
    validos = {r["id"] for r in todos(con, "SELECT id FROM suit_orders WHERE discarded_at IS NULL")}
    por_numero = {int(n) for n in RX_NUMERO.findall(alvo) if int(n) in validos}
    por_nome = set()
    t = _norm(alvo)
    for p in _abertos(con):
        try:
            nome_design = (json.loads(p["design"] or "{}") or {}).get("nome")
        except ValueError:
            nome_design = None
        for nome in {p["driver_name"], nome_design, p["title"]}:
            n = _norm(nome).strip()
            if len(n) >= 4 and re.search(r"(?<![\w])" + re.escape(n) + r"(?![\w])", t):
                por_nome.add(p["id"])
    citado = None
    if resposta_a:
        r = um(con, """SELECT order_id FROM atelie_wa_mensagens WHERE message_id=? AND order_id IS NOT NULL
                       AND (? IS NULL OR grupo_jid=?)""", (resposta_a, grupo_jid, grupo_jid))
        citado = r["order_id"] if r else None
    if citado:
        if por_numero and por_numero != {citado}:
            return None, None, sorted(por_numero | {citado})
        return citado, "resposta", []
    if por_numero:
        if len(por_numero) == 1 and (not por_nome or por_numero & por_nome):
            return next(iter(por_numero)), "numero", []
        return None, None, sorted(por_numero | por_nome)
    if len(por_nome) == 1:
        return next(iter(por_nome)), "nome", []
    return None, None, sorted(por_nome)


# ------------------------------------------------------------------ entrada
def _pasta_solta(mid):
    caminho = os.path.join(_urace_dir(), "atelie", "whatsapp", str(int(mid)))
    os.makedirs(caminho, exist_ok=True)
    return caminho


def _guardar(destino_pid, mid, nome, dados):
    sp = _ponte()
    if destino_pid:
        return sp.guardar_anexo(destino_pid, nome, dados)
    nome = sp._nome_seguro(nome)
    with open(os.path.join(_pasta_solta(mid), nome), "wb") as f:
        f.write(dados)
    return nome


def _humano_solto(con, mid, motivo):
    if not um(con, "SELECT id FROM ai_events WHERE kind='atelie.humano' AND entity_id=? AND status='NEW'", (mid,)):
        inserir(con, "ai_events", kind="atelie.humano", entity_type="atelie_wa_mensagem", entity_id=mid,
                summary=f"WhatsApp do ateliê, mensagem #{mid}: {motivo}"[:300], status="NEW")


def receber(con, dados, cfg=None):
    """Uma mensagem de um grupo da lista. Grupo fora da lista ou conversa individual: nem é gravada."""
    cfg = cfg or config()
    jid = str(dados.get("grupo_jid") or "").strip()
    g = grupo(cfg, jid=jid) if jid.endswith("@g.us") else None
    if not g:
        return {"ignorada": "não é um grupo da lista"}
    msg_id = (str(dados.get("message_id") or "").strip() or None)
    if msg_id and um(con, "SELECT id FROM atelie_wa_mensagens WHERE grupo_jid=? AND message_id=?", (jid, msg_id)):
        return {"repetida": True}
    texto = (dados.get("texto") or "")[:8000]
    midias = [m for m in (dados.get("midias") or []) if isinstance(m, dict)][:10]
    nomes = [str(m.get("nome") or "anexo") for m in midias]
    de_mim = bool(dados.get("de_mim"))
    acionavel = g["papel"] in PAPEIS and not de_mim
    pid, vinculo, cand = evidencia(con, texto, nomes, dados.get("resposta_a"), jid)
    if pid and um(con, "SELECT discarded_at FROM suit_orders WHERE id=?", (pid,))["discarded_at"]:
        pid, vinculo = None, None
    estado = ("registro" if not acionavel else "nova" if pid else "ambigua" if len(cand) > 1 else "sem_pedido")
    mid = inserir(con, "atelie_wa_mensagens", grupo_jid=jid, papel=g["papel"], direcao="saida" if de_mim else "entrada",
                  message_id=msg_id, remetente=(str(dados.get("remetente") or "")[:80] or None),
                  remetente_nome=(str(dados.get("remetente_nome") or "")[:120] or None), texto=texto or None,
                  resposta_a=dados.get("resposta_a") or None, resposta_texto=(dados.get("resposta_texto") or "")[:2000] or None,
                  order_id=pid, vinculo=vinculo, estado=estado, candidatos=json.dumps(cand) if cand else None,
                  at=dados.get("at") or agora())
    anexos = []
    for m in midias:
        try:
            bruto = base64.b64decode(m.get("base64") or "", validate=False)
        except (ValueError, TypeError):
            continue
        if not bruto or len(bruto) > MIDIA_MAX:
            anexos.append({"nome": str(m.get("nome") or "anexo"), "tipo": m.get("tipo"), "bytes": len(bruto), "nao_guardado": True})
            continue
        anexos.append({"nome": _guardar(pid, mid, str(m.get("nome") or "anexo"), bruto), "tipo": m.get("tipo"), "bytes": len(bruto)})
    if anexos:
        con.execute("UPDATE atelie_wa_mensagens SET anexos=? WHERE id=?", (json.dumps(anexos, ensure_ascii=False), mid))
    if pid:
        from command_center.providers import suits
        st = um(con, "SELECT status FROM suit_orders WHERE id=?", (pid,))["status"]
        quem = dados.get("remetente_nome") or PAPEIS.get(g["papel"], g["papel"])
        suits.anotar(con, pid, f"WhatsApp ({g['nome'] or g['papel']}) — {quem}: {texto[:600] or '(sem texto)'}"
                     + (f" · anexos: {', '.join(a['nome'] for a in anexos)}" if anexos else ""), "whatsapp", st)
    elif estado == "ambigua":
        _humano_solto(con, mid, f"pode ser de mais de um pedido ({', '.join('#' + str(c) for c in cand)}): escolha o certo")
    elif estado == "sem_pedido" and anexos:
        _humano_solto(con, mid, "chegou arquivo sem dizer de qual pedido é: ligue ao pedido certo")
    return {"ok": True, "id": mid, "pedido": pid, "estado": estado, "anexos": [a["nome"] for a in anexos]}


def vincular(con, mid, pid, user_id=None):
    """A equipe liga a mensagem ao pedido (a ambígua ou a sem pedido). Os arquivos vão para a pasta do pedido."""
    from command_center.providers import suits
    m = um(con, "SELECT * FROM atelie_wa_mensagens WHERE id=?", (int(mid),))
    if not m:
        raise LookupError("Mensagem não encontrada.")
    p = um(con, "SELECT id, status, discarded_at FROM suit_orders WHERE id=?", (int(pid),))
    if not p or p["discarded_at"]:
        raise Recusado("pedido não encontrado (ou descartado)")
    if m["order_id"]:
        raise Recusado(f"a mensagem já está no pedido #{m['order_id']}")
    anexos = json.loads(m["anexos"] or "[]")
    solta = os.path.join(_urace_dir(), "atelie", "whatsapp", str(m["id"]))
    for a in anexos:
        origem = os.path.join(solta, a["nome"])
        if os.path.isfile(origem):
            with open(origem, "rb") as f:
                a["nome"] = _ponte().guardar_anexo(p["id"], a["nome"], f.read())
    shutil.rmtree(solta, ignore_errors=True)
    novo = "nova" if m["papel"] in PAPEIS and m["direcao"] == "entrada" else "registro"
    con.execute("UPDATE atelie_wa_mensagens SET order_id=?, vinculo='equipe', estado=?, anexos=?, candidatos=NULL WHERE id=?",
                (p["id"], novo, json.dumps(anexos, ensure_ascii=False) if anexos else None, m["id"]))
    con.execute("UPDATE ai_events SET status='DONE', handled_at=?, note=? WHERE kind='atelie.humano' AND entity_id=? AND status='NEW'",
                (agora(), f"ligada ao pedido #{p['id']}", m["id"]))
    suits.anotar(con, p["id"], f"WhatsApp ({m['papel']}) ligado a este pedido pela equipe — {m['remetente_nome'] or ''}: "
                 f"{(m['texto'] or '(sem texto)')[:600]}", "whatsapp", p["status"], user_id=user_id)
    return True


# ------------------------------------------------------------------ guardas
RX_PAGAMENTO = re.compile(r"\$\s?\d|\b(?:usd|paid|payment|pagamento|pago|pagou|invoice|fatura|stripe|card|cartão|cartao)\b", re.I)


def _digitos(s):
    return re.sub(r"\D", "", s or "")


def guardas(pedido, papel, texto):
    """O designer não vê dado nem pagamento do cliente; o endereço só vai ao fornecedor em Checked (#382)."""
    t = _norm(texto)
    problemas = []
    email = (pedido.get("customer_email") or "").lower()
    if email and email in t:
        problemas.append("o e-mail do cliente")
    tel = _digitos(pedido.get("customer_phone"))
    endereco = [x.strip() for x in (pedido.get("ship_address") or "").splitlines() if len(x.strip()) >= 8]
    com_endereco = papel == "fornecedor" and pedido.get("checked_at")
    if not com_endereco:
        if len(tel) >= 7 and tel[-7:] in _digitos(texto):
            problemas.append("o telefone do cliente")
        if any(_norm(x) in t for x in endereco):
            problemas.append("o endereço do cliente" + ("" if papel == "design" else " (só depois do OK da equipe nas fotos, Checked)"))
    if papel == "design":
        nome = (pedido.get("customer_name") or "").strip()
        try:
            no_design = {_norm(json.loads(pedido.get("design") or "{}").get("nome")), _norm(pedido.get("driver_name"))}
        except (ValueError, AttributeError):
            no_design = {_norm(pedido.get("driver_name"))}
        if len(nome.split()) >= 2 and _norm(nome) in t and _norm(nome) not in no_design:
            problemas.append("o nome completo do cliente")
        if RX_PAGAMENTO.search(texto or ""):
            problemas.append("pagamento ou valor")
    if problemas:
        raise Recusado(f"O {PAPEIS.get(papel, papel)} não pode receber " + ", ".join(problemas) +
                       f". Reescreva só com o necessário e o número do pedido (Suits #{pedido['id']}).")


# ------------------------------------------------------------------ saída
def _bin():
    return os.environ.get("OPENCLAW_BIN") or shutil.which("openclaw") or "openclaw"


def _message_id(obj):
    if isinstance(obj, dict):
        for k in ("messageId", "message_id", "id"):
            if isinstance(obj.get(k), str) and obj[k]:
                return obj[k]
        for v in obj.values():
            r = _message_id(v)
            if r:
                return r
    if isinstance(obj, list):
        for v in obj:
            r = _message_id(v)
            if r:
                return r
    return None


def enviar_cli(jid, texto, caminhos=(), conta=None):
    """`openclaw message send` para o grupo. Devolve o id da mensagem (quando o OpenClaw diz)."""
    falso = os.environ.get("CC_WA_FAKE")
    if falso:
        with open(falso, "a", encoding="utf-8") as f:
            f.write(json.dumps({"target": jid, "message": texto, "media": [os.path.basename(c) for c in caminhos],
                                "account": conta}, ensure_ascii=False) + "\n")
        return f"fake-wa-{os.path.getsize(falso)}"
    cmd = [_bin(), "message", "send", "--channel", "whatsapp", "--target", jid, "--message", texto, "--json"]
    if conta:
        cmd += ["--account", conta]
    for c in caminhos:
        cmd += ["--media", c]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Recusado(f"o OpenClaw não respondeu: {type(e).__name__}")
    saida = (r.stdout or "").strip()
    try:
        dados = json.loads(saida[saida.find("{"):]) if "{" in saida else {}
    except ValueError:
        dados = {}
    if r.returncode != 0 or (isinstance(dados, dict) and dados.get("ok") is False):
        erro = (dados.get("error") if isinstance(dados, dict) else None) or (r.stderr or saida)[-300:]
        raise Recusado(f"o OpenClaw não mandou: {str(erro)[:300]}")
    return _message_id(dados)


def _arquivos(pedido, papel, nomes):
    """Os anexos saem da pasta do pedido por uma cópia temporária, limpos pela MESMA regra do e-mail: ao designer,
    `limpar_para_designer` da ponte (#382: sem metadados, AI/EPS/SVG pelo `_vetor_sem_metadados`, e o arquivo com
    dado do cliente não sai); ao fornecedor, sem metadados (`_sem_metadados`)."""
    import mimetypes
    sp = _ponte()
    pid = pedido["id"]
    arquivos = []
    for nome in nomes or []:
        nome = os.path.basename(nome)
        origem = os.path.join(sp.pasta(pid), nome)
        if not os.path.isfile(origem):
            raise Recusado(f"anexo não encontrado no pedido: {nome}")
        with open(origem, "rb") as f:
            arquivos.append((nome, f.read(), mimetypes.guess_type(nome)[0] or "application/octet-stream"))
    try:
        if papel == "design":
            arquivos = sp.limpar_para_designer(arquivos, pedido)
        else:
            arquivos = [(n, sp._sem_metadados(n, d, m), m) for n, d, m in arquivos]
    except sp.Recusado as e:
        raise Recusado(str(e))
    tmp = os.path.join(_urace_dir(), "atelie", "envio", f"{pid}-{datetime.now().strftime('%H%M%S%f')}")
    caminhos = []
    for nome, dados, _ in arquivos:
        os.makedirs(tmp, exist_ok=True)
        destino = os.path.join(tmp, os.path.basename(nome))
        with open(destino, "wb") as f:
            f.write(dados)
        caminhos.append(destino)
    return tmp, caminhos


def _com_referencia(pid, texto):
    return texto if re.search(rf"#\s?{int(pid)}\b", texto) else f"Suits #{pid} — {texto}"


def _pedido(con, pid):
    p = um(con, "SELECT * FROM suit_orders WHERE id=?", (int(pid),))
    if not p:
        raise Recusado("pedido não encontrado")
    return dict(p)


def propor(con, pid, papel, texto, anexos=None, motivo="mensagem", criado_por="ia", command_id=None, dia=None, user_id=None):
    """O único caminho para um grupo. Simulação da ponte: vira nota. Envio automático desligado: rascunho
    (aprovar de um clique). Ligado (e com WA_GRUPOS_APLICAR=1 e a IA ligada no pedido): sai agora."""
    from command_center.providers import suits
    sp = _ponte()
    pedido = _pedido(con, pid)
    if pedido.get("discarded_at"):
        raise Recusado("pedido descartado: nada sai por ele")
    if criado_por in ("ia", "sistema") and not pedido.get("ia_ligada", 1):
        raise Recusado("a IA está desligada neste pedido (#198): quem fala nos grupos é a equipe")
    if papel not in PAPEIS:
        raise Recusado("grupo: design ou fornecedor")
    cfg = config()
    g = grupo(cfg, papel=papel)
    if not g:
        raise Recusado(f"o {PAPEIS[papel]} ainda não está configurado (~/.urace/whatsapp-grupos.env)")
    texto = (texto or "").strip()
    if not texto:
        raise Recusado("a mensagem está vazia")
    if motivo == "endereco" and pedido.get("status") != "checked":
        raise Recusado("o endereço só vai ao fornecedor com o pedido em Checked (o OK da equipe nas fotos)")
    texto = _com_referencia(pid, texto[:3500])
    guardas(pedido, papel, texto)
    nomes = [os.path.basename(n) for n in (anexos or [])]
    for n in nomes:
        if not os.path.isfile(os.path.join(sp.pasta(pid), n)):
            raise Recusado(f"anexo não encontrado no pedido: {n} (veja suits_anexos)")
    lista = f" · anexos: {', '.join(nomes)}" if nomes else ""
    if sp.SIMULAR.get() or pedido.get("is_test"):
        quem = "a IA escreveria" if criado_por == "ia" else "iria"
        nid = suits.anotar(con, pid, ("PEDIDO DE TESTE (nada sai)" if pedido.get("is_test") else "SIMULAÇÃO")
                           + f" — {quem} no {PAPEIS[papel]}{lista}:\n\n{texto}", "whatsapp", pedido["status"])
        return {"simulado": True, "nota": nid}
    sid = inserir(con, "atelie_wa_saidas", order_id=int(pid), papel=papel, motivo=motivo, texto=texto,
                  anexos=json.dumps(nomes) if nomes else None, dia=dia, criado_por=criado_por, command_id=command_id)
    if criado_por.startswith("user:"):                     # quem escreveu na tela é a aprovação
        return aprovar(con, sid, user_id)
    # o designer passa por uma pessoa (#382): ao grupo de design, sempre rascunho, mesmo com o envio automático
    auto = papel != "design" and sp.config(con)["envio_automatico"] == "1" and cfg["aplicar"] and pedido.get("ia_ligada", 1)
    if auto:
        try:
            return aprovar(con, sid, None)
        except Recusado as e:
            return {"rascunho": sid, "falhou": str(e)}
    suits.anotar(con, pid, f"Rascunho para o {PAPEIS[papel]} (aprovar no pedido){lista}:\n\n{texto}", "whatsapp", pedido["status"])
    return {"rascunho": sid, "simulacao": True,
            "nota": "fica como rascunho: a equipe aprova com um clique no pedido (envio automático desligado)"}


def aprovar(con, sid, user_id=None, texto=None):
    """Manda o rascunho (pode vir com o texto corrigido). As guardas valem de novo."""
    from command_center.providers import suits
    s = um(con, "SELECT * FROM atelie_wa_saidas WHERE id=?", (int(sid),))
    if not s:
        raise LookupError("Rascunho não encontrado.")
    if s["estado"] not in ("rascunho", "falhou"):
        raise Recusado(f"este rascunho já está {s['estado']}")
    pedido = _pedido(con, s["order_id"])
    if pedido.get("discarded_at"):
        raise Recusado("pedido descartado: nada sai por ele")
    if pedido.get("is_test"):
        raise Recusado("pedido de teste: nada sai para os grupos")
    if s["motivo"] == "endereco":
        if pedido.get("status") != "checked":
            raise Recusado("o endereço só vai ao fornecedor com o pedido em Checked (o OK da equipe nas fotos)")
        if not user_id:
            raise Recusado("o endereço ao fornecedor é da equipe: aprove no pedido")
        try:
            suits.checar_etapa(con, pedido["id"], "address_sent")
        except suits.Invalido as e:
            raise Recusado(str(e))
    corpo = _com_referencia(pedido["id"], (texto or s["texto"]).strip()[:3500])
    guardas(pedido, s["papel"], corpo)
    cfg = config()
    g = grupo(cfg, papel=s["papel"])
    if not g:
        raise Recusado(f"o {PAPEIS.get(s['papel'], s['papel'])} não está configurado")
    if not cfg["aplicar"]:
        raise Recusado("o WhatsApp dos grupos ainda está em simulação (WA_GRUPOS_APLICAR=1 no ~/.urace/whatsapp-grupos.env)")
    tmp, caminhos = _arquivos(pedido, s["papel"], json.loads(s["anexos"] or "[]"))
    try:
        msg_id = enviar_cli(g["jid"], corpo, caminhos, cfg["conta"])
    except Recusado as e:
        con.execute("UPDATE atelie_wa_saidas SET estado='falhou', erro=? WHERE id=?", (str(e)[:300], s["id"]))
        raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    con.execute("UPDATE atelie_wa_saidas SET estado='enviado', texto=?, message_id=?, decidido_por=?, decidido_em=?, erro=NULL "
                "WHERE id=?", (corpo, msg_id, user_id, agora(), s["id"]))
    inserir(con, "atelie_wa_mensagens", grupo_jid=g["jid"], papel=s["papel"], direcao="saida", message_id=msg_id,
            texto=corpo, order_id=pedido["id"], vinculo="enviada", estado="registro",
            anexos=json.dumps([{"nome": n} for n in json.loads(s["anexos"] or "[]")]) if s["anexos"] else None, at=agora())
    if s["motivo"] == "endereco":                      # #382: a etapa da equipe, pela tabela de transições
        suits.mudar_etapa(con, pedido["id"], "address_sent", user_id, "endereço enviado no grupo do fornecedor")
    suits.anotar(con, pedido["id"], f"WhatsApp enviado ao {PAPEIS.get(s['papel'], s['papel'])}"
                 + (" (aprovado)" if user_id else " (envio automático)") + f":\n\n{corpo}", "whatsapp", pedido["status"], user_id=user_id)
    auditar(con, "atelie.whatsapp.sent", f"user:{user_id}" if user_id else "ai:atelie", user_id=user_id,
            entity_type="suit_order", entity_id=pedido["id"], detail={"papel": s["papel"], "saida": s["id"], "motivo": s["motivo"]})
    return {"enviado": True, "saida": s["id"], "message_id": msg_id}


def descartar(con, sid, user_id=None):
    s = um(con, "SELECT * FROM atelie_wa_saidas WHERE id=?", (int(sid),))
    if not s:
        raise LookupError("Rascunho não encontrado.")
    if s["estado"] not in ("rascunho", "falhou"):
        return False
    con.execute("UPDATE atelie_wa_saidas SET estado='descartado', decidido_por=?, decidido_em=? WHERE id=?", (user_id, agora(), s["id"]))
    return True


# ------------------------------------------------------------------ fotos, endereço e rastreio (as etapas do #382)
TEXTOS = {
    "cobranca_design": {"pt": "Bom dia! Como está a arte deste pedido? Se tiver alguma dúvida, é só falar.",
                        "en": "Hi! How is the artwork for this order going? Let us know if you have any question."},
    "cobranca_producao": {"en": "Hi! Any update on this suit? Photos of the progress are welcome.",
                          "pt": "Olá! Alguma novidade deste suit? Fotos do andamento são bem-vindas."},
    "cobranca_rastreio": {"en": "Hi! Has this suit shipped? Please send us the tracking code.",
                          "pt": "Olá! O suit já foi despachado? Mande o código de rastreio, por favor."},
}


def _texto(chave, idioma, **kw):
    t = TEXTOS[chave].get(idioma) or TEXTOS[chave]["en"]
    return t.format(**kw)


def mandar_endereco(con, pid, user_id):
    """#382/#383: com o pedido em Checked (a equipe conferiu as fotos), a equipe manda o endereço ao grupo do
    fornecedor com um clique (o texto é o `mensagem_endereco` da ponte) e o pedido vai para Address sent."""
    from command_center.providers import suits
    p = _pedido(con, pid)
    if p.get("discarded_at"):
        raise Recusado("pedido descartado")
    f = um(con, "SELECT * FROM suit_suppliers WHERE id=?", (p["supplier_id"],)) if p.get("supplier_id") else \
        um(con, "SELECT * FROM suit_suppliers WHERE is_current=1")
    m = suits.mensagem_endereco(p, dict(f) if f else None)
    falta = [x for x in m["faltam"] if "e-mail" not in x]
    if falta:
        raise Recusado("Falta " + " e ".join(falta) + " para mandar o endereço.")
    return propor(con, pid, "fornecedor", m["whatsapp"], motivo="endereco", criado_por=f"user:{user_id}", user_id=user_id)


RX_RASTREIO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{5,39}$")


def registrar_rastreio(con, pid, codigo, transportadora=None, user_id=None):
    """O código que o fornecedor passou vai para o pedido (a equipe passa ao cliente). Despachou: In Transit."""
    from command_center.providers import suits
    codigo = re.sub(r"\s+", "", codigo or "")
    if not RX_RASTREIO.fullmatch(codigo):
        raise Recusado("código de rastreio inválido (só letras, números e hífen, 6 a 40)")
    p = _pedido(con, pid)
    if p.get("discarded_at"):
        raise Recusado("pedido descartado")
    valor = f"{transportadora.strip()[:40]} {codigo}" if transportadora and transportadora.strip() else codigo
    con.execute("UPDATE suit_orders SET tracking=?, updated_at=? WHERE id=?", (valor, agora(), p["id"]))
    suits.anotar(con, p["id"], f"Rastreio do fornecedor: {valor}. A equipe passa ao cliente.", "whatsapp", p["status"], user_id=user_id)
    if "in_transit" in suits.TRANSICOES.get(p["status"], ()):       # #382: só pela tabela (de Address sent)
        suits.mudar_etapa(con, p["id"], "in_transit", user_id, "o fornecedor mandou o rastreio")
    return {"ok": True, "tracking": valor}


def foto_do_suit(con, mid, nome, user_id):
    """A equipe usa a foto que o fornecedor mandou no grupo como a foto do suit (#382: Photos received exige foto
    em nota). A imagem vira nota (WebP, sem EXIF) e o pedido vai para Photos received pela tabela de etapas."""
    from command_center.api.suits import pasta_imagens
    from command_center.providers import imagem as img
    from command_center.providers import suits
    m = um(con, "SELECT * FROM atelie_wa_mensagens WHERE id=?", (int(mid),))
    if not m or not m["order_id"]:
        raise Recusado("ligue a mensagem ao pedido antes")
    nome = os.path.basename(nome or "")
    if nome not in [a["nome"] for a in json.loads(m["anexos"] or "[]")]:
        raise Recusado("este arquivo não é desta mensagem")
    caminho = os.path.join(_ponte().pasta(m["order_id"]), nome)
    if not os.path.isfile(caminho):
        raise Recusado("arquivo não encontrado no pedido")
    with open(caminho, "rb") as f:
        try:
            dados, ext = img.comprimir(f.read())
        except img.ImagemInvalida:
            raise Recusado("não é uma imagem (use PNG, JPG ou WEBP)")
    p = _pedido(con, m["order_id"])
    if p["status"] != "photos_received":
        try:
            suits.mudar_etapa(con, p["id"], "photos_received", user_id, "fotos do fornecedor no WhatsApp")
        except suits.Invalido as e:
            raise Recusado(str(e))
    arq = f"pedido-{p['id']}-wa-{m['id']}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}{ext}"
    with open(os.path.join(pasta_imagens(), arq), "wb") as f:
        f.write(dados)
    suits.anotar(con, p["id"], f"Foto do suit (WhatsApp, {m['remetente_nome'] or 'fornecedor'}): {nome}", "nota", "photos_received", arq, user_id)
    return {"ok": True, "nota_imagem": arq}


# ------------------------------------------------------------------ cobrança diária
def _ultima(con, pid, papel):
    return um(con, "SELECT direcao, at, created_at FROM atelie_wa_mensagens WHERE order_id=? AND papel=? ORDER BY id DESC LIMIT 1",
              (pid, papel))


def _horas_desde(iso):
    try:
        d = datetime.fromisoformat((iso or "").replace("Z", "+00:00"))
    except ValueError:
        return 0
    if d.tzinfo is None:
        d = d.replace(tzinfo=ZoneInfo("UTC"))
    return (datetime.now(ZoneInfo("UTC")) - d).total_seconds() / 3600


def cobrancas(con, agora_local=None):
    """No máximo uma cobrança por pedido, por grupo e por dia, do que está em aberto há mais de 20 h:
    a arte (grupo de design, quando a última mensagem foi nossa), a produção e o rastreio (fornecedor)."""
    agora_local = agora_local or _hoje()
    if agora_local.weekday() == 6 or not (HORAS_COBRANCA[0] <= agora_local.hour < HORAS_COBRANCA[1]):
        return []
    dia = agora_local.date().isoformat()
    cfg = config()
    feitas = []
    for p in todos(con, """SELECT * FROM suit_orders WHERE closed=0 AND discarded_at IS NULL AND ia_ligada=1
                           AND coalesce(is_test, 0)=0"""):
        p = dict(p)
        pedidos = []
        g = grupo(cfg, papel="design")
        ult = _ultima(con, p["id"], "design")
        if g and p["status"] == "design_pending" and ult and ult["direcao"] == "saida" and _horas_desde(ult["created_at"]) >= 20:
            pedidos.append(("design", _texto("cobranca_design", g["idioma"])))
        g = grupo(cfg, papel="fornecedor")
        ult = _ultima(con, p["id"], "fornecedor")
        velha = (_horas_desde(ult["created_at"]) >= 20) if ult else (_horas_desde(p.get("sent_to_supplier_at")) >= 20)
        if g and velha:
            if p["status"] == "address_sent" and not p.get("tracking"):
                pedidos.append(("fornecedor", _texto("cobranca_rastreio", g["idioma"])))
            elif p["status"] in ("sent_to_supplier", "supplier_accepted", "in_production") and (ult or p.get("sent_to_supplier_at")):
                pedidos.append(("fornecedor", _texto("cobranca_producao", g["idioma"])))
        for papel, texto in pedidos:
            if um(con, "SELECT id FROM atelie_wa_saidas WHERE order_id=? AND papel=? AND dia=? AND motivo='cobranca'", (p["id"], papel, dia)):
                continue
            if um(con, "SELECT id FROM atelie_wa_saidas WHERE order_id=? AND papel=? AND estado='rascunho'", (p["id"], papel)):
                continue                                   # já tem rascunho esperando: não empilha
            try:
                feitas.append({"pedido": p["id"], "papel": papel,
                               **propor(con, p["id"], papel, texto, motivo="cobranca", criado_por="sistema", dia=dia)})
            except Exception as e:
                feitas.append({"pedido": p["id"], "papel": papel, "erro": str(e)[:160]})
    return feitas


# ------------------------------------------------------------------ a IA
QUE_FAZER = {
    "design": ("O DESIGNER ESCREVEU NO GRUPO DE DESIGN (WhatsApp). Arte entregue (PDF/imagem, já baixada no pedido): confira "
               "que é deste pedido, mande ao cliente por e-mail (suits_email para=\"cliente\", anexos com os arquivos) pedindo "
               "aprovação ou ajustes, como a URACE (sem nome nem contato do designer), e mova para design_review. Pergunta do "
               "designer: leve ao cliente por e-mail com as suas palavras. O cliente já pediu ajuste: devolva ao grupo "
               "(atelie_grupo_escrever grupo=\"design\"), só com o design."),
    "fornecedor": ("O FORNECEDOR ESCREVEU NO GRUPO DELE (WhatsApp). Anote o que ele disse (suits_anotar). Fotos do suit pronto: "
                   "estão no pedido; chame a equipe (suits_precisa_humano \"fotos do suit no WhatsApp: usar como foto do suit "
                   "(Photos received) e conferir (Checked)\") — fotos, conferido e endereço são da equipe: NUNCA escreva endereço. "
                   "Código de rastreio: atelie_rastreio. Confirmou o pedido: supplier_accepted; avisou produção: in_production "
                   "(pela tabela de etapas). Pergunta simples sobre o "
                   "pedido: responda no grupo (atelie_grupo_escrever grupo=\"fornecedor\", em inglês). Problema ou decisão "
                   "(medida errada, cor, prazo, preço): suits_precisa_humano."),
}


def prompt(con, pid, papel, msgs):
    sp = _ponte()
    linhas = []
    for m in msgs:
        anexos = [a["nome"] for a in json.loads(m["anexos"] or "[]") if not a.get("nao_guardado")]
        linhas.append(f"--- {m['remetente_nome'] or m['remetente'] or '?'} · {m['at']}"
                      + (f" · respondendo a: {(m['resposta_texto'] or '')[:300]}" if m["resposta_texto"] else "")
                      + f"\n{m['texto'] or '(sem texto)'}"
                      + (f"\nAnexos baixados (leia com Read em {sp.pasta(pid)}): {', '.join(anexos)}" if anexos else ""))
    return (f"[WHATSAPP DO ATELIÊ] Pedido Suits #{pid}: leia com suits_pedido, as mensagens do grupo com atelie_grupo_mensagens "
            "e os arquivos com suits_anexos (processo: 10_PROCESSOS/Pedido de macacão.md).\n\n" + QUE_FAZER[papel]
            + "\n\nPDF ou imagem de MEDIDAS ou instruções extras: leia (Read) e grave (suits_atualizar_pedido: medidas na unidade "
              "que vier, e design.instrucoes com as instruções extras ao fornecedor); o e-mail ao fornecedor se monta com elas "
              "(suits_pedido → email_fornecedor) e a equipe cria o rascunho no Gmail. Nunca invente medida."
            + "\n\nSEMPRE: no grupo de design, só o design e \"Suits #id\" (nunca nome completo, e-mail, telefone, endereço ou "
              "pagamento do cliente). O que vai ao grupo segue a chave de envio automático (desligada = rascunho para a equipe "
              "aprovar). Na dúvida, suits_precisa_humano. No fim, suits_anotar com o que fez em uma linha."
            + "\n\nMENSAGENS NOVAS NO GRUPO:\n" + "\n".join(linhas))


def tratar_pendentes(con, executar=None):
    """As mensagens novas ligadas a um pedido vão à IA (uma chamada por pedido e grupo)."""
    sp = _ponte()
    from command_center.providers import suits
    novas = todos(con, "SELECT * FROM atelie_wa_mensagens WHERE estado='nova' AND order_id IS NOT NULL ORDER BY id")
    grupos = {}
    for m in novas:
        grupos.setdefault((m["order_id"], m["papel"]), []).append(m)
    feitos = []
    for (pid, papel), msgs in list(grupos.items())[:POR_CICLO]:
        con.execute(f"UPDATE atelie_wa_mensagens SET estado='tratada' WHERE id IN ({','.join('?' * len(msgs))})", [m["id"] for m in msgs])
        p = um(con, "SELECT status, discarded_at, ia_ligada FROM suit_orders WHERE id=?", (pid,))
        if not p or p["discarded_at"]:
            continue
        if not p["ia_ligada"]:
            sp.precisa_humano(con, pid, f"chegou mensagem no {PAPEIS.get(papel, papel)} e a IA está desligada neste pedido: a equipe responde")
            feitos.append({"pedido": pid, "papel": papel, "ia_desligada": True})
            continue
        uid = sp._admin(con)
        if uid is None:
            continue
        pr = prompt(con, pid, papel, msgs)
        texto = f"EVENTO AUTOMÁTICO — Suits #{pid}: WhatsApp ({papel})"
        cid = inserir(con, "ai_commands", user_id=uid, text=texto, prompt=pr, session_key=f"suits-{pid}")
        suits.anotar(con, pid, f"Chegou mensagem no {PAPEIS.get(papel, papel)}: a IA está tratando.", "ia", p["status"], command_id=cid)
        marca = sp.ESCOPO.set({"pedido": pid, "tipo": f"whatsapp-{papel}", "email": None, "mensagens": {}})   # #382: só este pedido
        try:
            (executar or sp._executar_padrao)(con, cid, texto, f"suits-{pid}", uid, pr)
            c = um(con, "SELECT status, error FROM ai_commands WHERE id=?", (cid,))
            if c and c["status"] == "FAILED":                # `ia._executa` não levanta: a falha fica no comando
                raise RuntimeError(f"a IA falhou: {(c['error'] or '')[:160]}")
            feitos.append({"pedido": pid, "papel": papel, "comando": cid})
        except Exception as e:
            erro = f"{type(e).__name__}: {str(e)[:160]}"
            feitos.append({"pedido": pid, "papel": papel, "erro": erro})
            # debug 29/10: como na ponte de e-mail (#382), a mensagem que a IA não tratou volta no ciclo seguinte e,
            # passado o limite de tentativas, vai para a equipe. Antes ficava "tratada" e ninguém era chamado.
            n = sp._tentativa(con, f"atelie:{msgs[0]['id']}", pid, erro)
            if n < sp.LIMITE_TENTATIVAS:
                con.execute(f"UPDATE atelie_wa_mensagens SET estado='nova' WHERE id IN ({','.join('?' * len(msgs))})",
                            [m["id"] for m in msgs])
            else:
                sp.precisa_humano(con, pid, f"a IA tentou {n} vezes tratar a mensagem no {PAPEIS.get(papel, papel)} e não "
                                            f"conseguiu ({erro[:120]}): a equipe responde")
        finally:
            sp.ESCOPO.reset(marca)
    return feitos


def instrucao_para_ponte():
    """Uma linha para o prompt da ponte de e-mail: com o grupo de design configurado, o design vai por lá."""
    try:
        cfg = config()
    except Exception:
        return ""
    if not grupo(cfg, papel="design"):
        return ""
    return ("\n\nGRUPO DE DESIGN NO WHATSAPP (#383): o pedido de design e os ajustes vão ao designer pelo grupo "
            "(atelie_grupo_escrever grupo=\"design\", com os anexos de inspiração e logos e \"Suits #id\"), não por e-mail. "
            "A cobrança diária do que está em aberto é do painel. O pedido de produção ao fornecedor continua por e-mail.")


def ler_fila(con, cfg=None):
    """O que o plugin guardou porque o Command Center não respondeu na hora (~/.urace/atelie/fila/*.json)."""
    pasta = os.path.join(_urace_dir(), "atelie", "fila")
    if not os.path.isdir(pasta):
        return 0
    n = 0
    for nome in sorted(os.listdir(pasta))[:200]:
        caminho = os.path.join(pasta, nome)
        if not nome.endswith(".json"):
            continue
        try:
            with open(caminho, encoding="utf-8") as f:
                receber(con, json.load(f), cfg)
            n += 1
        except (OSError, ValueError):
            pass
        try:
            os.remove(caminho)
        except OSError:
            pass
    return n


def rodar(con, executar=None, agora_local=None):
    """Um ciclo: a IA nas mensagens novas e a cobrança diária. Sem o env, não faz nada."""
    from command_center.api import ia
    cfg = config()
    if not cfg["existe"] or not any(g["jid"] for g in cfg["grupos"]):
        return {"pulada": "grupos do WhatsApp não configurados"}
    if _ponte().config(con)["ponte_ligada"] != "1":
        return {"pulada": "ponte de Suits desligada"}
    res = {"fila": ler_fila(con, cfg), "ia": [], "cobrancas": [], "erros": []}
    if executar is not None or ia.motor_da_ia() == "sdk":
        try:
            res["ia"] = tratar_pendentes(con, executar)
        except Exception as e:
            res["erros"].append(f"ia: {type(e).__name__}: {str(e)[:160]}")
    try:
        res["cobrancas"] = cobrancas(con, agora_local)
    except Exception as e:
        res["erros"].append(f"cobrancas: {type(e).__name__}: {str(e)[:160]}")
    if res["fila"] or res["ia"] or res["cobrancas"] or res["erros"]:
        auditar(con, "atelie.whatsapp.round", "system", detail=res)
    return res


_LOCK = threading.Lock()


def rodar_em_segundo_plano():
    if not _LOCK.acquire(blocking=False):
        return False

    def _vai():
        con = conectar()
        try:
            rodar(con)
        except Exception as e:
            try:
                auditar(con, "atelie.whatsapp.failed", "system", detail={"erro": f"{type(e).__name__}: {str(e)[:300]}"})
            except Exception:
                pass
        finally:
            con.close()
            _LOCK.release()
    threading.Thread(target=_vai, daemon=True, name="cc-atelie-whatsapp").start()
    return True


# ------------------------------------------------------------------ ferramentas da IA
def mensagens_do_pedido(con, pid):
    return {"mensagens": todos(con, """SELECT id, papel, direcao, remetente_nome, texto, resposta_texto, anexos, vinculo, at
                                       FROM atelie_wa_mensagens WHERE order_id=? ORDER BY id DESC LIMIT 60""", (int(pid),)),
            "saidas": todos(con, """SELECT id, papel, motivo, texto, anexos, estado, created_at FROM atelie_wa_saidas
                                    WHERE order_id=? ORDER BY id DESC LIMIT 30""", (int(pid),))}


def ferramentas_ia():
    """(nome, descrição, propriedades, obrigatórios, função(con, user_id, **args)) — entram no servidor `suits` do agente."""
    def ler(con, uid, id, **_):
        return mensagens_do_pedido(con, id)

    def escrever(con, uid, id, grupo, texto, anexos=None, **_):
        try:
            return propor(con, int(id), grupo, texto, anexos or [])
        except Recusado as e:
            return {"recusado": str(e)}

    def rastreio(con, uid, id, codigo, transportadora=None, **_):
        if (um(con, "SELECT ia_ligada FROM suit_orders WHERE id=?", (int(id),)) or {"ia_ligada": 0})["ia_ligada"] == 0:
            return {"erro": "a IA está desligada neste pedido: a equipe cuida"}
        try:
            return registrar_rastreio(con, int(id), codigo, transportadora, uid)
        except Recusado as e:
            return {"recusado": str(e)}

    s, n = {"type": "string"}, {"type": "integer"}
    return [
        ("atelie_grupo_mensagens", "As mensagens dos grupos do ateliê no WhatsApp (design e fornecedor) ligadas a um pedido "
         "de macacão, e o que já foi (ou está esperando aprovação para ir) ao grupo.", {"id": n}, ["id"], ler),
        ("atelie_grupo_escrever", "Escreve no grupo do WhatsApp do pedido: \"design\" (o designer: só o design e \"Suits #id\", "
         "nunca nome completo, e-mail, telefone, endereço ou pagamento do cliente) ou \"fornecedor\" (o Usman: cobrar, conferir, "
         "perguntar; NUNCA endereço — ele é da equipe, depois do OK nas fotos, Checked). Anexos: nomes de suits_anexos. Ao designer é "
         "sempre rascunho; ao fornecedor, rascunho com o envio automático desligado.",
         {"id": n, "grupo": dict(s, enum=list(PAPEIS)), "texto": s, "anexos": {"type": "array", "items": s}},
         ["id", "grupo", "texto"], escrever),
        ("atelie_rastreio", "Grava no pedido o código de rastreio que o fornecedor mandou (e move para In Transit).",
         {"id": n, "codigo": s, "transportadora": s}, ["id", "codigo"], rastreio),
    ]
