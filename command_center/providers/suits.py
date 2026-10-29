"""Suits (Alpha Line): as regras dos pedidos de macacão (#153). As rotas moram em `api/suits.py`.

Dono, 08/10: *"na aba de suítes ... registrar novo pedido ... Sempre dê a oportunidade ali de eu
adicionar uma nota, às vezes um screenshot para IA poder entender, já avançar com aquilo ali no
status que estiver"* e *"O envio ao Usman ... tem um padrão de envio. Salva esse padrão como
template"*. Processo: `brain/10_PROCESSOS/Pedido de macacão.md`.

- **Etapas**: as nove do quadro SUITS do Asana mais "Approved" (o "aprovado, podemos mandar para
  produção?" que o dono descreveu), e desde 22/10 (#382) a entrega direta ao cliente: aceito pelo
  fornecedor, fotos recebidas (WhatsApp), conferido e endereço enviado — catorze ao todo.
- **Travas (#382)**: `approved` e o pedido ao fornecedor exigem a aprovação final escrita do cliente,
  amarrada ao hash da arte final e das medidas (`estado_aprovacao`); `checked` exige foto e é da
  equipe; `address_sent` só depois de `checked`; `in_transit` exige rastreio.
- **Medidas**: as 29 do formulário (+ 6bis, só mulheres), na ordem que o fornecedor lê. O valor
  fica como o cliente deu (número e unidade); o e-mail mostra as duas unidades. O tamanho do pé
  é texto: EUR ↔ US não tem conta exata, e NO FAKE DATA.
- **E-mail do fornecedor**: o padrão dos e-mails já enviados ao Usman, guardado como modelo
  editável (`suit_templates`).
- **Importar do Asana**: o projeto SUITS, só leitura, sem duplicar se rodar de novo.
"""
import hashlib
import json
import os
import re

from command_center.db import agora, inserir, todos, um

ETAPAS = [
    ("standby", "Standby", "pedido criado, esperando o próximo passo"),
    ("awaiting_measurements", "Awaiting Measurements", "esperando o cliente mandar as medidas"),
    ("design_pending", "Design Pending", "pago, com as ideias de design: o designer trabalha"),
    ("design_review", "Design Under Client Review", "o cliente está revisando o design"),
    ("approved", "Approved", "o cliente aprovou por escrito a versão final e as medidas conferidas: pode ir para produção"),
    ("sent_to_supplier", "Order sent to supplier", "pedido de produção enviado ao fornecedor (sem endereço)"),
    ("supplier_accepted", "Accepted by supplier", "o fornecedor confirmou o pedido"),
    ("in_production", "In Production", "o fornecedor está produzindo"),
    ("photos_received", "Photos received", "o fornecedor mandou as fotos pelo WhatsApp e a equipe subiu como nota"),
    ("checked", "Checked", "a equipe conferiu as fotos: OK para despachar"),
    ("address_sent", "Address sent to supplier", "a equipe passou ao fornecedor o endereço do cliente"),
    ("in_transit", "In Transit", "o fornecedor despachou direto ao cliente, com rastreio"),
    ("delivered", "Delivered", "entregue ao cliente"),
    ("canceled", "Canceled", "cancelado"),
]
CODIGOS = [e[0] for e in ETAPAS]
FECHADAS = ("delivered", "canceled")

# status do Asana (campo "Status" do projeto SUITS) → etapa daqui
DO_ASANA = {"Standby": "standby", "Awaiting Measurements": "awaiting_measurements", "Design Pending": "design_pending",
            "Design Under Client Review": "design_review", "Order sent to Usman": "sent_to_supplier",
            "In Production": "in_production", "In Transit": "in_transit", "Delivered": "delivered", "Canceled": "canceled"}

# (chave, número no formulário, nome em inglês — como o fornecedor lê, tipo)
MEDIDAS = [
    ("head", "1", "Head circumference", "comp"),
    ("forehead_neck", "2", "Distance from forehead to neck", "comp"),
    ("neck", "3", "Neck circumference", "comp"),
    ("chin_neck", "4", "Distance from chin to neck", "comp"),
    ("shoulder", "5", "Shoulder width", "comp"),
    ("chest", "6", "Chest circumference", "comp"),
    ("bust", "6bis", "Bust circumference", "comp"),          # só mulheres
    ("waist", "7", "Waist circumference", "comp"),
    ("hip", "8", "Hip circumference", "comp"),
    ("neck_back", "9", "Distance from neck to back", "comp"),
    ("neck_tailbone", "10", "Distance from neck to tail bone", "comp"),
    ("arm", "11", "Arm length", "comp"),
    ("elbow_wrist", "12", "Distance from elbow to wrist", "comp"),
    ("biceps", "13", "Biceps circumference", "comp"),
    ("elbow", "14", "Elbow circumference", "comp"),
    ("forearm", "15", "Forearm circumference", "comp"),
    ("wrist", "16", "Wrist circumference", "comp"),
    ("thigh", "17", "Thigh circumference", "comp"),
    ("knee", "18", "Knee circumference", "comp"),
    ("calf", "19", "Calf circumference", "comp"),
    ("ankle", "20", "Ankle circumference", "comp"),
    ("waist_ankle", "21", "Distance from waist to ankle", "comp"),
    ("groin_ankle", "22", "Distance from groin to ankle", "comp"),
    ("knee_ankle", "23", "Distance from knee to ankle", "comp"),
    ("trapezius_ankle", "24", "Distance from trapezius to ankle", "comp"),
    ("trapezius_floor", "25", "Distance from trapezius to floor", "comp"),
    ("nipple_ankle", "26", "Distance from nipple to ankle", "comp"),
    ("height", "27", "Height", "comp"),
    ("weight", "28", "Weight", "peso"),
    ("foot", "29", "Foot size", "texto"),
]
CHAVES = {m[0] for m in MEDIDAS}
OBRIGATORIAS = [m[0] for m in MEDIDAS if m[0] != "bust"]

DESIGN = [("ideia", "Ideia / mockup de referência"), ("cores", "Cores (Pantone, se tiver)"), ("logos", "Logos"),
          ("posicao_logos", "Onde vai cada logo"), ("nome", "Nome a aplicar"), ("bandeira", "Bandeira"),
          ("observacoes", "Observações do cliente"),
          ("instrucoes", "Instruções extras ao fornecedor")]   # #383: as que vierem com o PDF de medidas


class Invalido(ValueError):
    """Dado que não dá para gravar; a mensagem vai para a tela."""


# ------------------------------------------------------------------ medidas
def _num(v):
    if isinstance(v, bool):
        raise Invalido("medida inválida")
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d+)?", s):
        raise Invalido(f"'{v}' não é um número")
    return float(s)


def normalizar_medidas(valores, unidade="cm", unidade_peso="kg"):
    """{chave: valor} da tela → {chave: {"v": número, "u": unidade}} (ou {"t": texto} para o pé).
    Vazio some (não vira zero). Chave desconhecida é recusada."""
    if unidade not in ("cm", "in") or unidade_peso not in ("kg", "lb"):
        raise Invalido("unidade inválida")
    saida = {}
    for chave, valor in (valores or {}).items():
        if chave not in CHAVES:
            raise Invalido(f"medida desconhecida: {chave}")
        if valor is None or str(valor).strip() == "":
            continue
        tipo = next(m[3] for m in MEDIDAS if m[0] == chave)
        if tipo == "texto":
            saida[chave] = {"t": str(valor).strip()[:40]}
        else:
            n = _num(valor)
            if n <= 0 or n > 400:
                raise Invalido(f"{chave}: valor fora do razoável ({valor})")
            saida[chave] = {"v": n, "u": unidade_peso if tipo == "peso" else unidade}
    return saida


def _fmt(n):
    return f"{n:.1f}".rstrip("0").rstrip(".")


def _pes_polegadas(pol):
    meio = round(pol * 2) / 2
    pes, resto = int(meio // 12), meio - 12 * int(meio // 12)
    return f"{pes}'{_fmt(resto)}\"" if pes else f"{_fmt(resto)}\""


def texto_medida(chave, m):
    """'59 cm / 1'11"' — as duas unidades, como o fornecedor lê."""
    if not m:
        return ""
    if "t" in m:
        return m["t"]
    v, u = m["v"], m["u"]
    if u == "kg":
        return f"{_fmt(v)} kg / {_fmt(round(v * 2.20462, 1))} lb"
    if u == "lb":
        return f"{_fmt(round(v / 2.20462, 1))} kg / {_fmt(v)} lb"
    cm, pol = (v, v / 2.54) if u == "cm" else (round(v * 2.54, 1), v)
    return f"{_fmt(cm)} cm / {_pes_polegadas(pol)}"


def faltando(medidas):
    return [m[0] for m in MEDIDAS if m[0] in OBRIGATORIAS and m[0] not in (medidas or {})]


def bloco_medidas(medidas):
    linhas = []
    for chave, num, nome, _ in MEDIDAS:
        m = (medidas or {}).get(chave)
        if chave == "bust" and not m:
            continue
        linhas.append(f"{num} – {nome} — {texto_medida(chave, m) if m else '(missing)'}")
    return "\n".join(linhas)


# ---------------------------------------------------------- estado de cada medida (#382, E)
# Cada medida preenchida é "preenchida" até a equipe conferir. "suspeita" (a equipe ou a IA desconfiou do número)
# leva o motivo. Suspeita ou não conferida trava a aprovação final; mudou o valor, volta para "preenchida".
ESTADOS_MEDIDA = ("preenchida", "conferida", "suspeita")


def _json(v, padrao):
    try:
        return json.loads(v) if v else padrao
    except (TypeError, ValueError):
        return padrao


def estados_medidas(medidas, situacao):
    """{chave: {"estado", "motivo"}} só das medidas preenchidas (a que falta não tem estado: falta)."""
    saida = {}
    for chave in (medidas or {}):
        e = (situacao or {}).get(chave) or {}
        estado = e.get("e") if e.get("e") in ("conferida", "suspeita") else "preenchida"
        saida[chave] = {"estado": estado, "motivo": e.get("motivo") if estado == "suspeita" else None,
                        "por": e.get("por"), "em": e.get("em")}
    return saida


def situacao_depois_de_mudar(antes, depois, situacao):
    """O valor mudou (ou sumiu): aquela medida volta a "preenchida" (sai do registro de estados)."""
    s = dict(situacao or {})
    for chave in list(s):
        if chave not in (depois or {}) or (antes or {}).get(chave) != (depois or {}).get(chave):
            s.pop(chave, None)
    return s


def marcar_medidas(con, pid, chaves, estado, motivo=None, user_id=None, por_ia=False):
    """Marca o estado de uma ou mais medidas. A IA só pode marcar "suspeita" (conferir é da equipe)."""
    if estado not in ESTADOS_MEDIDA:
        raise Invalido("estado da medida: preenchida, conferida ou suspeita")
    if por_ia and estado != "suspeita":
        raise Invalido("a IA só marca medida como suspeita: conferir é da equipe")
    motivo = (motivo or "").strip()[:300]
    if estado == "suspeita" and not motivo:
        raise Invalido("diga por que a medida parece errada")
    p = um(con, "SELECT id, status, measurements, measurement_status FROM suit_orders WHERE id=?", (int(pid),))
    if not p:
        raise LookupError("Pedido não encontrado.")
    medidas = _json(p["measurements"], {})
    chaves = [c for c in (chaves or []) if c]
    if not chaves:
        raise Invalido("diga qual medida")
    for c in chaves:
        if c not in CHAVES:
            raise Invalido(f"medida desconhecida: {c}")
        if c not in medidas:
            raise Invalido(f"{c}: a medida ainda não foi preenchida")
    sit = _json(p["measurement_status"], {})
    for c in chaves:
        if estado == "preenchida":
            sit.pop(c, None)
        else:
            sit[c] = {"e": estado, "motivo": motivo or None, "por": "ia" if por_ia else user_id, "em": agora()}
    con.execute("UPDATE suit_orders SET measurement_status=?, updated_at=? WHERE id=?",
                (json.dumps(sit, ensure_ascii=False), agora(), p["id"]))
    nomes = ", ".join(next(f"{m[1]} {m[2]}" for m in MEDIDAS if m[0] == c) for c in chaves[:6]) + ("…" if len(chaves) > 6 else "")
    anotar(con, p["id"], f"Medida(s) {estado}: {nomes}" + (f" — {motivo}" if motivo else ""), "ia" if por_ia else "nota",
           p["status"], user_id=None if por_ia else user_id)
    conferir_aprovacao(con, p["id"], user_id)
    return estados_medidas(medidas, sit)


# ----------------------------------------------------------- arte final e aprovação (#382, A)
def arte_final(pedido):
    return [n for n in _json((pedido or {}).get("final_art"), []) if isinstance(n, str)]


def _pasta(pid):
    from command_center.providers import suits_ponte
    return suits_ponte.pasta(pid)


def hash_arte(pid, nomes):
    """O conteúdo dos arquivos marcados como arte final (nome + sha256 de cada um). Arquivo sumido entra como tal."""
    h = hashlib.sha256()
    for nome in sorted(nomes or []):
        caminho = os.path.join(_pasta(pid), os.path.basename(nome))
        if os.path.isfile(caminho):
            with open(caminho, "rb") as f:
                dig = hashlib.sha256(f.read()).hexdigest()
        else:
            dig = "ausente"
        h.update(f"{nome}\0{dig}\n".encode())
    return h.hexdigest()


def hash_medidas(medidas):
    return hashlib.sha256(json.dumps(medidas or {}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def versao(hash_a, hash_m):
    """O código curto da versão que o cliente vê no e-mail de aprovação final."""
    return hashlib.sha256(f"{hash_a}:{hash_m}".encode()).hexdigest()[:8].upper()


def marcar_arte_final(con, pid, nome, final=True, user_id=None, por_ia=False):
    p = um(con, "SELECT id, status, final_art FROM suit_orders WHERE id=?", (int(pid),))
    if not p:
        raise LookupError("Pedido não encontrado.")
    nome = os.path.basename(nome or "")
    if not nome or not os.path.isfile(os.path.join(_pasta(p["id"]), nome)):
        raise Invalido(f"arquivo não encontrado no pedido: {nome or '—'}")
    lista = arte_final(p)
    if final and nome not in lista:
        lista.append(nome)
    elif not final and nome in lista:
        lista.remove(nome)
    else:
        return lista
    con.execute("UPDATE suit_orders SET final_art=?, updated_at=? WHERE id=?", (json.dumps(lista, ensure_ascii=False), agora(), p["id"]))
    anotar(con, p["id"], (f"Arte final: {nome}" if final else f"{nome} deixou de ser arte final"), "ia" if por_ia else "nota",
           p["status"], user_id=None if por_ia else user_id)
    conferir_aprovacao(con, p["id"], user_id)
    return lista


def _aprovacao_atual(con, pid):
    return um(con, "SELECT * FROM suit_approvals WHERE order_id=? AND status='valida' ORDER BY id DESC LIMIT 1", (int(pid),))


def estado_aprovacao(con, pid):
    """Se a aprovação final vale para o que o pedido tem AGORA, e o que impede registrar uma.
    estado: valida | desatualizada | nenhuma."""
    p = um(con, "SELECT id, measurements, measurement_status, final_art, final_request FROM suit_orders WHERE id=?", (int(pid),))
    if not p:
        return None
    medidas = _json(p["measurements"], {})
    est = estados_medidas(medidas, _json(p["measurement_status"], {}))
    nomes = arte_final(p)
    bloqueios = []
    if not nomes:
        bloqueios.append("marcar a arte final (o arquivo da versão que o cliente aprova)")
    sumidos = [n for n in nomes if not os.path.isfile(os.path.join(_pasta(p["id"]), n))]
    if sumidos:
        bloqueios.append("a arte final sumiu da pasta do pedido: " + ", ".join(sumidos))
    if faltando(medidas):
        bloqueios.append(f"{len(faltando(medidas))} medida(s) faltando")
    suspeitas = [c for c, e in est.items() if e["estado"] == "suspeita"]
    nao_conf = [c for c, e in est.items() if e["estado"] == "preenchida"]
    if suspeitas:
        bloqueios.append(f"{len(suspeitas)} medida(s) suspeita(s)")
    if nao_conf:
        bloqueios.append(f"{len(nao_conf)} medida(s) não conferida(s) pela equipe")
    ha, hm = hash_arte(p["id"], nomes), hash_medidas(medidas)
    ap = _aprovacao_atual(con, p["id"])
    ultima = ap or um(con, "SELECT * FROM suit_approvals WHERE order_id=? ORDER BY id DESC LIMIT 1", (p["id"],))
    if ap and ap["art_hash"] == ha and ap["measures_hash"] == hm and not bloqueios:
        estado = "valida"
    elif ultima:
        estado = "desatualizada"
    else:
        estado = "nenhuma"
    pedido_final = _json(p["final_request"], None)
    if pedido_final:
        pedido_final["atual"] = pedido_final.get("arte") == ha and pedido_final.get("medidas") == hm
    if ultima:
        ultima = dict(ultima, files=_json(ultima.get("files"), []))
    return {"estado": estado, "aprovacao": ultima, "bloqueios": bloqueios, "arte_final": nomes, "hash_arte": ha,
            "hash_medidas": hm, "versao": versao(ha, hm), "suspeitas": suspeitas, "nao_conferidas": nao_conf,
            "pedido_final": pedido_final}


def aprovacao_valida(con, pid):
    e = estado_aprovacao(con, pid)
    return bool(e) and e["estado"] == "valida"


ANTES_DE_APROVAR = ("standby", "awaiting_measurements", "design_pending", "design_review")


def registrar_aprovacao(con, pid, trecho, message_id=None, data=None, fonte="manual", user_id=None, command_id=None):
    """Grava a aprovação final escrita do cliente (dono, 22/10: vale por e-mail) amarrada à arte final e às
    medidas de agora. Pedido ainda antes de `approved` passa para `approved`."""
    p = um(con, "SELECT id, status, discarded_at FROM suit_orders WHERE id=?", (int(pid),))
    if not p:
        raise LookupError("Pedido não encontrado.")
    if p["discarded_at"]:
        raise Invalido("pedido descartado: não é pedido de macacão")
    trecho = re.sub(r"\s+", " ", (trecho or "")).strip()
    if len(trecho) < 3:
        raise Invalido("copie o trecho do e-mail em que o cliente aprova")
    e = estado_aprovacao(con, p["id"])
    if e["bloqueios"]:
        raise Invalido("Ainda não dá para registrar a aprovação final: falta " + "; ".join(e["bloqueios"]) + ".")
    con.execute("UPDATE suit_approvals SET status='substituida' WHERE order_id=? AND status='valida'", (p["id"],))
    aid = inserir(con, "suit_approvals", order_id=p["id"], message_id=(message_id or "").strip()[:200] or None,
                  excerpt=trecho[:1000], approved_at=(data or "").strip()[:80] or agora(), source=fonte,
                  art_hash=e["hash_arte"], measures_hash=e["hash_medidas"], files=json.dumps(e["arte_final"], ensure_ascii=False),
                  measures=json.dumps(_json(um(con, "SELECT measurements FROM suit_orders WHERE id=?", (p["id"],))["measurements"], {}),
                                      ensure_ascii=False),
                  user_id=user_id if fonte == "manual" else None, command_id=command_id)
    anotar(con, p["id"], f"Aprovação final registrada ({'pela IA, do e-mail do cliente' if fonte == 'ia' else 'pela equipe'}), "
           f"versão {e['versao']}: «{trecho[:300]}»" + (f" · e-mail {message_id}" if message_id else ""),
           "ia" if fonte == "ia" else "etapa", p["status"], user_id=None if fonte == "ia" else user_id)
    if p["status"] in ANTES_DE_APROVAR:
        mudar_etapa(con, p["id"], "approved", None if fonte == "ia" else user_id, "aprovação final escrita do cliente",
                    por_ia=(fonte == "ia"))
    return dict(um(con, "SELECT * FROM suit_approvals WHERE id=?", (aid,)), versao=e["versao"])


def conferir_aprovacao(con, pid, user_id=None):
    """Depois de mexer na arte final ou nas medidas: se a aprovação válida não bate mais, ela fica desatualizada
    (nunca apagada) e o pedido que estava em `approved` volta para revisão. Devolve o motivo, ou None."""
    ap = _aprovacao_atual(con, pid)
    if not ap:
        return None
    e = estado_aprovacao(con, pid)
    motivos = []
    if ap["art_hash"] != e["hash_arte"]:
        motivos.append("a arte final mudou")
    if ap["measures_hash"] != e["hash_medidas"]:
        motivos.append("as medidas mudaram")
    if e["suspeitas"] or e["nao_conferidas"]:
        motivos.append("há medida suspeita ou não conferida")
    if not motivos:
        return None
    motivo = " e ".join(motivos)
    con.execute("UPDATE suit_approvals SET status='desatualizada', stale_at=?, stale_reason=? WHERE id=?", (agora(), motivo, ap["id"]))
    p = um(con, "SELECT status FROM suit_orders WHERE id=?", (int(pid),))
    anotar(con, int(pid), f"Aprovação final desatualizada: {motivo}. Precisa de uma aprovação nova da versão atual.", "etapa",
           p["status"], user_id=user_id)
    if p["status"] == "approved":
        mudar_etapa(con, int(pid), "design_review", user_id, f"aprovação desatualizada ({motivo})")
    elif p["status"] not in ANTES_DE_APROVAR and p["status"] not in FECHADAS:
        from command_center.providers import suits_ponte
        suits_ponte.precisa_humano(con, int(pid), f"a aprovação final ficou desatualizada depois do envio ao fornecedor ({motivo}): "
                                                  "confira com o fornecedor e com o cliente", user_id)
    return motivo


# O que o cliente lê no e-mail de aprovação final: a versão exata, as medidas e a política (não retornável,
# não reembolsável). Inglês sempre; o português e o espanhol vão junto quando é o idioma do cliente.
APROVACAO_FINAL = {
    "en": ("FINAL APPROVAL — version {versao}\n\nAttached is the final version of your suit: {arquivos}.\n\n"
           "Measurements we will send to production:\n{medidas}\n\n"
           "Please note: every suit is made to order. Once you approve this final version it goes to production, and custom "
           "suits are non-returnable and non-refundable (subject to the terms of your purchase).\n\n"
           "To approve, reply to this e-mail saying that you approve the final version {versao}. If anything needs to change, "
           "tell us what and we will send a new version."),
    "pt": ("APROVAÇÃO FINAL — versão {versao}\n\nEm anexo, a versão final do seu macacão: {arquivos}.\n"
           "As medidas acima são as que vão para a produção.\n\nImportante: cada macacão é feito sob medida. Aprovada esta "
           "versão final, ele entra em produção e não tem devolução nem reembolso (conforme os termos da compra).\n\n"
           "Para aprovar, responda a este e-mail dizendo que aprova a versão final {versao}. Se algo precisar mudar, diga o "
           "quê e mandamos uma versão nova."),
    "es": ("APROBACIÓN FINAL — versión {versao}\n\nAdjunta, la versión final de su traje: {arquivos}.\n"
           "Las medidas de arriba son las que van a producción.\n\nImportante: cada traje se hace a medida. Aprobada esta "
           "versión final, entra en producción y no tiene devolución ni reembolso (según los términos de la compra).\n\n"
           "Para aprobar, responda a este correo diciendo que aprueba la versión final {versao}. Si algo debe cambiar, "
           "díganos qué y le enviamos una versión nueva."),
}


def texto_aprovacao_final(pedido, e, introducao=None, assinatura=""):
    """(assunto, corpo) do e-mail de aprovação final, montado pelo painel: a versão, os arquivos, as medidas e a política."""
    medidas = pedido.get("measurements")
    medidas = _json(medidas, {}) if isinstance(medidas, str) or medidas is None else medidas
    valores = {"{versao}": e["versao"], "{arquivos}": ", ".join(e["arte_final"]), "{medidas}": bloco_medidas(medidas)}
    blocos = []
    for lang in ["en"] + ([pedido.get("language")] if pedido.get("language") in ("pt", "es") else []):
        t = APROVACAO_FINAL[lang]
        for k, v in valores.items():
            t = t.replace(k, v)
        blocos.append(t)
    corpo = "\n\n".join(x for x in [(introducao or "").strip(), *blocos, (assinatura or "").strip()] if x)
    piloto = pedido.get("driver_name") or ""
    return f"Final approval — your custom suit{(' for ' + piloto) if piloto else ''} (version {e['versao']})", corpo


# ------------------------------------------------------------ as travas das etapas (#382, D)
SO_DA_EQUIPE = ("photos_received", "checked", "address_sent")
PRECISAM_DE_APROVACAO = ("approved", "sent_to_supplier")


def tem_foto_do_fornecedor(con, pid):
    return um(con, "SELECT 1 AS x FROM suit_notes WHERE order_id=? AND image_path IS NOT NULL AND status='photos_received' LIMIT 1",
              (int(pid),)) is not None


# Revisão do Mio (#382): de cada etapa, para onde dá para ir. Vale para a tela, a nota, a IA e a correção
# automática (aprovação desatualizada volta para revisão). Fora daqui, a mudança é recusada com o motivo.
_ABERTAS = ("standby", "awaiting_measurements", "design_pending", "design_review")
TRANSICOES = {
    "standby": ("awaiting_measurements", "design_pending", "design_review", "approved", "canceled"),
    "awaiting_measurements": ("standby", "design_pending", "design_review", "approved", "canceled"),
    "design_pending": ("standby", "awaiting_measurements", "design_review", "approved", "canceled"),
    "design_review": ("standby", "awaiting_measurements", "design_pending", "approved", "canceled"),
    "approved": ("design_review", "sent_to_supplier", "canceled"),
    "sent_to_supplier": ("approved", "supplier_accepted", "in_production", "canceled"),
    "supplier_accepted": ("in_production", "canceled"),
    "in_production": ("photos_received", "canceled"),
    "photos_received": ("in_production", "checked", "canceled"),
    "checked": ("photos_received", "address_sent", "canceled"),
    "address_sent": ("in_transit", "canceled"),
    "in_transit": ("delivered", "canceled"),
    "delivered": (),
    "canceled": ("standby",),
}
# Etapas em que um pedido pode NASCER (registro à mão ou pela IA): antes da aprovação, ou cancelado.
INICIAIS = _ABERTAS + ("canceled",)


def checar_transicao(atual, nova):
    nome = dict((x[0], x[1]) for x in ETAPAS)
    if nova not in TRANSICOES.get(atual, ()):
        destinos = ", ".join(nome[x] for x in TRANSICOES.get(atual, ())) or "nenhuma (pedido entregue)"
        raise Invalido(f"De {nome.get(atual, atual)} o pedido não vai para {nome[nova]}. Dá para ir para: {destinos}.")


def checar_etapa(con, pid, nova, por_ia=False, liberado_pelo_admin=False):
    """O que impede ir para `nova` (Invalido com o motivo): a tabela de transições e as travas do #382.
    #482 (dono, 29/10: "libera essas travas. Quando acontecer algo que não for pelo Command Center ... eu tenho que
    conseguir colocar na etapa de produção"): `liberado_pelo_admin` solta a ordem das etapas e as travas — vem só da
    rota de ADMIN (`mover_pelo_admin`), com o motivo, nunca da IA."""
    if liberado_pelo_admin and not por_ia:
        return
    p = um(con, "SELECT * FROM suit_orders WHERE id=?", (int(pid),)) or {}
    if p:
        checar_transicao(p["status"], nova)
    if nova in SO_DA_EQUIPE and por_ia:
        raise Invalido("fotos recebidas, conferido e endereço enviado são da equipe (as fotos chegam pelo WhatsApp): "
                       "a IA não muda para essas etapas")
    if nova in PRECISAM_DE_APROVACAO and not aprovacao_valida(con, pid):
        e = estado_aprovacao(con, pid)
        raise Invalido("Sem a aprovação final escrita do cliente, válida para a arte e as medidas de agora, o pedido não vai "
                       f"para {dict((x[0], x[1]) for x in ETAPAS)[nova]}"
                       + (" (a última está desatualizada)" if e and e["estado"] == "desatualizada" else "")
                       + (". Falta: " + "; ".join(e["bloqueios"]) if e and e["bloqueios"] else "") + ".")
    if nova == "checked" and not tem_foto_do_fornecedor(con, pid):
        raise Invalido("Conferido exige foto: suba as fotos do WhatsApp como nota na etapa Photos received.")
    if nova == "address_sent":
        if not p.get("checked_at"):
            raise Invalido("O endereço só vai ao fornecedor depois do OK da equipe (Checked).")
        if not (p.get("ship_address") or "").strip():
            raise Invalido("O pedido não tem o endereço de entrega.")
    if nova == "in_transit" and not (p.get("tracking") or "").strip():
        raise Invalido("Em trânsito exige o rastreio: preencha o Rastreio do pedido.")


# ------------------------------------------------------------ e-mail ao fornecedor
MODELO_PADRAO = {
    "subject": "SUIT - {piloto}",
    "body": ("Hi {fornecedor},\n\nWe have a new order:\n\n{medidas}\n\n{design}"
             "Best regards,\n{assinatura}\nUrace\n+1(407)2502291\nurace@urace.us\nwww.urace.us\n"
             "10724 Cosmonaut Blvd, Orlando, FL 32824, USA"),
}
CAMPOS_MODELO = ("{piloto}", "{fornecedor}", "{medidas}", "{design}", "{assinatura}", "{quantidade}")


def modelo(con):
    m = um(con, "SELECT subject, body, updated_at FROM suit_templates WHERE key='fornecedor'")
    return dict(m) if m else dict(MODELO_PADRAO, updated_at=None)


def email_fornecedor(con, pedido, fornecedor, quem):
    """O e-mail do pedido de produção, montado pelo modelo. `faltam` lista o que impede enviar."""
    med = json.loads(pedido.get("measurements") or "{}")
    des = json.loads(pedido.get("design") or "{}")
    faltam = []
    if faltando(med):
        faltam.append(f"{len(faltando(med))} medida(s)")
    if not fornecedor or not fornecedor.get("email"):
        faltam.append("e-mail do fornecedor")
    if con is not None and pedido.get("id"):
        if not arte_final(pedido):
            faltam.append("a arte final marcada")
        if not aprovacao_valida(con, pedido["id"]):
            faltam.append("a aprovação final do cliente (válida para a arte e as medidas de agora)")
    linhas_design = []
    if des.get("cores"):
        linhas_design.append(f"Colors: {des['cores']}")
    if des.get("instrucoes"):
        linhas_design.append(f"Additional instructions: {des['instrucoes']}")
    if (pedido.get("quantity") or 1) > 1:
        linhas_design.append(f"Quantity: {pedido['quantity']} suits")
    design = ("\n".join(linhas_design) + "\nThe final mockup is attached.\n\n") if linhas_design else "The final mockup is attached.\n\n"
    piloto = pedido.get("driver_name") or pedido.get("customer_name") or pedido.get("title") or ""
    nome_forn = (fornecedor or {}).get("contact") or (fornecedor or {}).get("name") or "there"
    valores = {"{piloto}": piloto, "{fornecedor}": nome_forn.split()[0] if nome_forn else "", "{medidas}": bloco_medidas(med),
               "{design}": design, "{assinatura}": (quem or {}).get("name") or "", "{quantidade}": str(pedido.get("quantity") or 1)}
    m = modelo(con)
    assunto, corpo = m["subject"], m["body"]
    for k, v in valores.items():
        assunto, corpo = assunto.replace(k, v), corpo.replace(k, v)
    end = [x.strip().lower() for x in (pedido.get("ship_address") or "").splitlines() if len(x.strip()) >= 8]
    if any(x in corpo.lower() for x in end):            # #382: o pedido de produção não leva o endereço do cliente
        faltam.append("tirar o endereço do cliente do e-mail de produção (ele vai depois, só após o OK das fotos)")
    return {"para": (fornecedor or {}).get("email"), "assunto": assunto, "corpo": corpo, "faltam": faltam,
            "anexos": arte_final(pedido)}


def mensagem_endereco(pedido, fornecedor, quem=None):
    """#382 (dono, 22/10: "conferimos e passamos o endereço para o envio"): o e-mail ou a mensagem de WhatsApp ao
    FORNECEDOR com o endereço do cliente, depois do OK das fotos. Nunca vai ao designer."""
    faltam = []
    if not pedido.get("checked_at"):
        faltam.append("o OK da equipe nas fotos (Checked)")
    if not (pedido.get("ship_address") or "").strip():
        faltam.append("o endereço de entrega")
    if not fornecedor or not fornecedor.get("email"):
        faltam.append("e-mail do fornecedor")
    piloto = pedido.get("driver_name") or pedido.get("customer_name") or pedido.get("title") or ""
    nome_forn = ((fornecedor or {}).get("contact") or (fornecedor or {}).get("name") or "there").split()[0]
    destinatario = "\n".join(x for x in [pedido.get("customer_name"), (pedido.get("ship_address") or "").strip(),
                                         pedido.get("customer_phone")] if x)
    texto = (f"The photos of the suit for {piloto} are approved. Please ship it directly to the customer:\n\n{destinatario}\n\n"
             "Please send us the tracking number as soon as it ships.")
    corpo = f"Hi {nome_forn},\n\n{texto}\n\nBest regards,\n{(quem or {}).get('name') or ''}\nUrace"
    return {"para": (fornecedor or {}).get("email"), "assunto": f"SHIPPING ADDRESS - SUIT - {piloto}", "corpo": corpo,
            "whatsapp": texto, "faltam": faltam}


# ------------------------------------------------------------ vincular ao cliente (#158)
# Dono, 08/10: "Todo lugar que a gente for fazer inserção manual, sempre coloque um para vincular com o
# cliente ... para poder vincular e puxar as informações pré-definidas ali daquele cliente."
# Medidas da área do cliente (portal) que são as MESMAS do formulário do macacão. Inseam e manga não
# entram: não são nenhuma das 29 (NO FAKE DATA).
DO_PORTAL = {"height_in": ("height", "in"), "weight_lb": ("weight", "lb"), "chest_in": ("chest", "in"),
             "waist_in": ("waist", "in"), "hips_in": ("hip", "in")}


def _endereco(conta):
    if not conta or not conta["address_line1"]:
        return None
    cidade = ", ".join(x for x in (conta["city"], " ".join(x for x in (conta["state"], conta["zip"]) if x)) if x)
    linhas = [conta["address_line1"], conta["address_line2"], cidade,
              conta["country"] if conta["country"] and conta["country"] != "US" else None]
    return "\n".join(x for x in linhas if x)


def dados_do_cliente(con, cid):
    """O que o cadastro já sabe deste cliente, para preencher o pedido: o card, a conta do site
    (endereço) e o piloto da área do cliente (medidas). Só o que existe; nada inventado."""
    c = um(con, "SELECT * FROM clients WHERE id=?", (cid,))
    if not c:
        return None
    piloto = um(con, "SELECT * FROM portal_pilots WHERE client_id=? AND active=1", (cid,))
    conta = um(con, "SELECT * FROM portal_accounts WHERE client_id=?", (cid,)) or (
        um(con, "SELECT * FROM portal_accounts WHERE id=?", (piloto["account_id"],)) if piloto else None)
    if conta and not piloto:
        pilotos = todos(con, "SELECT * FROM portal_pilots WHERE account_id=? AND active=1", (conta["id"],))
        if len(pilotos) == 1:
            piloto = pilotos[0]
    medidas = {}
    if piloto and piloto["measures"]:
        try:
            md = json.loads(piloto["measures"])
        except ValueError:
            md = {}
        for k, (chave, _) in DO_PORTAL.items():
            if isinstance(md.get(k), (int, float)) and md[k] > 0:
                medidas[chave] = md[k]
    return {"client_id": c["id"], "customer_name": c["name"], "customer_email": c["email"] or (conta["email"] if conta else None),
            "customer_phone": c["phone"] or (conta["phone"] if conta else None),
            "driver_name": c["pilot_name"] or (piloto["name"] if piloto and not piloto["is_self"] else None),
            "ship_address": _endereco(conta),
            "medidas": {"valores": medidas, "unidade": "in", "unidade_peso": "lb"} if medidas else None,
            "de_onde": {"card": True, "conta_do_site": bool(conta), "piloto": piloto["name"] if piloto else None}}


def vincular_por_email(con, pid):
    """Pedido sem cliente, com e-mail: liga sozinho quando há EXATAMENTE um cliente com aquele e-mail."""
    p = um(con, "SELECT client_id, customer_email FROM suit_orders WHERE id=?", (pid,))
    if not p or p["client_id"] or not p["customer_email"]:
        return None
    achados = todos(con, "SELECT id FROM clients WHERE lower(email)=lower(?) OR lower(coalesce(email_alt,''))=lower(?)",
                    (p["customer_email"].strip(), p["customer_email"].strip()))
    if len(achados) != 1:
        return None
    con.execute("UPDATE suit_orders SET client_id=? WHERE id=?", (achados[0]["id"], pid))
    return achados[0]["id"]


# ------------------------------------------------------------------- pedidos
def etapa_valida(s):
    if s not in CODIGOS:
        raise Invalido(f"etapa desconhecida: {s}")
    return s


def detalhe(con, pid):
    p = um(con, """SELECT o.*, s.name AS fornecedor, s.email AS fornecedor_email, u.name AS criado_por,
                          c.name AS cliente_nome, c.pilot_name AS cliente_piloto
                   FROM suit_orders o LEFT JOIN suit_suppliers s ON s.id=o.supplier_id
                   LEFT JOIN users u ON u.id=o.created_by LEFT JOIN clients c ON c.id=o.client_id WHERE o.id=?""", (pid,))
    if not p:
        return None
    p = dict(p)
    p["measurements"] = json.loads(p.get("measurements") or "{}")
    p["design"] = json.loads(p.get("design") or "{}")
    p["medidas_texto"] = {k: texto_medida(k, v) for k, v in p["measurements"].items()}
    p["faltam_medidas"] = faltando(p["measurements"])
    p["estado_medidas"] = estados_medidas(p["measurements"], _json(p.pop("measurement_status", None), {}))
    p["arte_final"] = arte_final(p)
    p.pop("final_art", None)
    p["final_request"] = _json(p.get("final_request"), None)
    p["aprovacao"] = estado_aprovacao(con, pid)
    p["proxima_acao"] = proxima_acao(p)
    p["saude_ponte"] = {"ultima_tentativa": p.pop("bridge_last_try_at", None), "ultimo_sucesso": p.pop("bridge_last_ok_at", None),
                        "ultimo_erro": p.pop("bridge_last_error", None), "ultimo_erro_em": p.pop("bridge_last_error_at", None),
                        "modo": p.pop("bridge_last_mode", None)}
    p["notas"] = [dict(n) for n in todos(con, """SELECT n.id, n.status, n.kind, n.text, n.image_path IS NOT NULL AS tem_imagem,
                                                        n.file_name AS arquivo, n.command_id, n.created_at, u.name AS autor
                                                 FROM suit_notes n LEFT JOIN users u ON u.id=n.user_id
                                                 WHERE n.order_id=? ORDER BY n.id""", (pid,))]
    return p


def anotar(con, pid, texto=None, kind="nota", status=None, imagem=None, user_id=None, command_id=None, arquivo=None):
    return inserir(con, "suit_notes", order_id=pid, status=status, kind=kind, text=(texto or None) and texto[:4000],
                   image_path=imagem, user_id=user_id, command_id=command_id, file_name=arquivo)


def mudar_etapa(con, pid, nova, user_id=None, motivo=None, por_ia=False, liberado_pelo_admin=False):
    """Troca a etapa e deixa o rastro na linha do tempo. Entregue/cancelado fecham o pedido.
    As travas do #382 (`checar_etapa`) valem para quem chamar: a tela, a nota, a IA."""
    etapa_valida(nova)
    p = um(con, "SELECT status FROM suit_orders WHERE id=?", (pid,))
    if not p or p["status"] == nova:
        return False
    checar_etapa(con, pid, nova, por_ia, liberado_pelo_admin)
    extra = {"sent_to_supplier_at": agora()} if nova == "sent_to_supplier" else {}
    if nova == "checked":
        extra = {"checked_at": agora(), "checked_by": user_id}
    if nova == "address_sent":
        extra = {"address_sent_at": agora()}
    if CODIGOS.index(nova) < CODIGOS.index("checked"):
        # debug 29/10: voltou para antes de Checked (a foto tinha defeito, o pedido reabriu): o OK das fotos deixa de
        # valer, e com ele o endereço ao fornecedor (#382). Quem conferiu e quando continua na linha do tempo.
        extra.update(checked_at=None, checked_by=None)
    sets = ", ".join(f"{k}=?" for k in extra)
    con.execute(f"UPDATE suit_orders SET status=?, closed=?, updated_at=?{', ' + sets if sets else ''} WHERE id=?",
                (nova, 1 if nova in FECHADAS else 0, agora(), *extra.values(), pid))
    nome = dict((e[0], e[1]) for e in ETAPAS)
    anotar(con, pid, f"{nome[p['status']]} → {nome[nova]}" + (f": {motivo}" if motivo else ""), "etapa", nova, user_id=user_id)
    return True


def mover_pelo_admin(con, pid, nova, user_id, motivo):
    """#482 (dono, 29/10): o que aconteceu fora do Command Center (aprovou mostrando, já foi para a produção) entra à
    mão: o administrador leva o pedido a qualquer etapa, sem a ordem das etapas e sem as travas, com o motivo na linha
    do tempo. As datas da etapa (enviado, conferido, endereço) são gravadas como no caminho normal. Devolve a etapa
    de antes."""
    etapa_valida(nova)
    motivo = re.sub(r"\s+", " ", motivo or "").strip()
    if len(motivo) < 5:
        raise Invalido("Escreva o motivo de mover à mão (ex.: aprovou pessoalmente; já foi para a produção pelo WhatsApp).")
    p = um(con, "SELECT status, discarded_at FROM suit_orders WHERE id=?", (int(pid),))
    if not p:
        raise LookupError("Pedido não encontrado.")
    if p["discarded_at"]:
        raise Invalido("pedido descartado: não é pedido de macacão")
    if p["status"] == nova:
        raise Invalido(f"O pedido já está em {dict((x[0], x[1]) for x in ETAPAS)[nova]}.")
    sem = nova in PRECISAM_DE_APROVACAO and not aprovacao_valida(con, pid)
    texto = ("liberado pelo administrador sem a aprovação final escrita registrada: " if sem
             else "movido à mão pelo administrador: ") + motivo[:500]
    mudar_etapa(con, int(pid), nova, user_id, texto, liberado_pelo_admin=True)
    return p["status"]


def liberar_aprovado(con, pid, user_id, motivo):
    """#448 (dono, 29/10): "mover para aprovado com o nível de admin pra cima". Hoje é um caso do `mover_pelo_admin`."""
    sem = not aprovacao_valida(con, pid)
    mover_pelo_admin(con, pid, "approved", user_id, motivo)
    return sem


PROXIMA = {
    "standby": "a IA manda as boas-vindas com o manual de medidas",
    "awaiting_measurements": "esperar o cliente mandar as medidas e o design",
    "design_pending": "o designer entrega a arte (o e-mail ao designer espera o clique de alguém da equipe)",
    "design_review": "conferir as medidas, marcar a arte final e mandar a aprovação final ao cliente",
    "approved": "criar o rascunho do pedido ao fornecedor (com a arte final anexada) e enviar",
    "sent_to_supplier": "esperar o fornecedor confirmar o pedido",
    "supplier_accepted": "esperar o fornecedor começar a produção",
    "in_production": "esperar as fotos do fornecedor pelo WhatsApp e subir como nota",
    "photos_received": "a equipe confere as fotos e dá o OK (Checked)",
    "checked": "passar o endereço do cliente ao fornecedor",
    "address_sent": "esperar o fornecedor despachar e mandar o rastreio",
    "in_transit": "acompanhar a entrega pelo rastreio",
}


def proxima_acao(p):
    """A próxima ação esperada do pedido, em uma linha (#382, F)."""
    if p.get("discarded_at"):
        return "descartado: nada a fazer"
    if p.get("status") in FECHADAS:
        return "pedido fechado"
    st = p.get("status")
    if st == "standby" and p.get("welcome_sent_at"):
        return "esperar o cliente mandar as medidas e o design"
    if st == "design_review":
        ap = p.get("aprovacao") or {}
        if ap.get("bloqueios"):
            return "antes da aprovação final: " + "; ".join(ap["bloqueios"])
        if (ap.get("pedido_final") or {}).get("atual"):
            return f"esperar o cliente aprovar por escrito a versão {ap.get('versao')}"
        return f"mandar ao cliente o e-mail de aprovação final da versão {ap.get('versao')}"
    return PROXIMA.get(st, "—")


# ------------------------------------------------------------- descartar (#195)
# Dono, 13/10: "nenhum desse aí foi e-mail de suit … Não era nem pra estar aí. Então, cessa isso,
# limpa esses daí". Descartar não apaga nada: o pedido some de Em andamento e do Histórico, a
# ponte para de ler as conversas dele e o e-mail dele deixa de contar como cliente. Dá para restaurar.
MOTIVO_PADRAO = "não é pedido de macacão"


def descartar(con, pid, motivo=None, user_id=None):
    """Tira o pedido das listas e da ponte. Devolve False se já estava descartado."""
    p = um(con, "SELECT id, status, discarded_at FROM suit_orders WHERE id=?", (int(pid),))
    if not p:
        raise LookupError("Pedido não encontrado.")
    if p["discarded_at"]:
        return False
    motivo = (motivo or "").strip()[:300] or MOTIVO_PADRAO
    con.execute("UPDATE suit_orders SET discarded_at=?, discard_reason=?, discarded_by=?, closed=1, updated_at=? WHERE id=?",
                (agora(), motivo, user_id, agora(), p["id"]))
    anotar(con, p["id"], f"Descartado: {motivo}. Saiu das listas e a ponte de e-mail não lê mais este pedido.",
           "etapa", p["status"], user_id=user_id)
    con.execute("UPDATE ai_events SET status='SKIPPED', handled_at=?, note=? WHERE kind='suit.humano' AND entity_id=? "
                "AND status='NEW'", (agora(), "pedido descartado", p["id"]))
    return True


def ia_desligada(con, pid):
    """#198: a chave "IA neste pedido" está desligada."""
    p = um(con, "SELECT ia_ligada FROM suit_orders WHERE id=?", (int(pid),)) if pid else None
    return bool(p) and not p["ia_ligada"]


def ligar_ia(con, pid, ligada, user_id=None):
    """#198 (dono, 13/10: "um switch para poder ligar e desligar IA naquele pedido"). Desligada, a IA não
    age no pedido: a ponte não a chama, ela não manda e-mail nem altera nada, e o que chegar vai para a
    equipe. Devolve False se já estava assim."""
    p = um(con, "SELECT id, status, ia_ligada FROM suit_orders WHERE id=?", (int(pid),))
    if not p:
        raise LookupError("Pedido não encontrado.")
    if bool(p["ia_ligada"]) == bool(ligada):
        return False
    con.execute("UPDATE suit_orders SET ia_ligada=?, updated_at=? WHERE id=?", (1 if ligada else 0, agora(), p["id"]))
    anotar(con, p["id"], "IA ligada neste pedido: a ponte volta a tratar os e-mails dele." if ligada else
           "IA desligada neste pedido: a IA não responde nem altera nada aqui; o que chegar por e-mail fica para a equipe.",
           "etapa", p["status"], user_id=user_id)
    return True


def restaurar(con, pid, user_id=None):
    """Desfaz o descarte: o pedido volta para a lista da etapa em que estava."""
    p = um(con, "SELECT id, status, discarded_at FROM suit_orders WHERE id=?", (int(pid),))
    if not p:
        raise LookupError("Pedido não encontrado.")
    if not p["discarded_at"]:
        return False
    con.execute("UPDATE suit_orders SET discarded_at=NULL, discard_reason=NULL, discarded_by=NULL, closed=?, updated_at=? "
                "WHERE id=?", (1 if p["status"] in FECHADAS else 0, agora(), p["id"]))
    anotar(con, p["id"], "Restaurado: o pedido voltou para a lista.", "etapa", p["status"], user_id=user_id)
    return True


# ------------------------------------------------------------ importar do Asana
SECOES_PEDIDO = {"Order", "Standby", "Seção sem título"}


def _produto(nome):
    n = nome.lower()
    if "t-shirt" in n or "tshirt" in n:
        return "T-shirt"
    if "table cover" in n:
        return "Table cover"
    if "sample" in n:
        return "Sample"
    return "Suit"


def _campos(t):
    return {c.get("name"): c.get("display_value") for c in t.get("custom_fields") or []}


_ROTULOS_FORN = {"contato": "contact", "e-mail": "email", "telefone": "phone", "tem fia": "has_fia", "status": "status",
                 "valor por macacão": "price", "frete por macacão": "shipping", "frete do sample": "shipping",
                 "forma de pagamento": "payment", "prazos internos": "lead_time", "comentários": "comments"}


def fornecedor_das_notas(notas):
    """'Contato: Asrar\\nE-mail: x@y\\nTem FIA: Não…' (a ficha do Asana) → campos. '—' é vazio."""
    saida = {}
    for linha in (notas or "").splitlines():
        if ":" not in linha:
            continue
        rot, val = linha.split(":", 1)
        campo = _ROTULOS_FORN.get(rot.strip().lower())
        val = val.strip()
        if not campo or not val or val in ("—", "-"):
            continue
        if campo == "has_fia":
            saida[campo] = 1 if val.lower().startswith("sim") else 0 if val.lower().startswith("n") else None
        elif campo == "email":
            saida[campo] = val.split(",")[0].strip()
            if "," in val:
                saida["comments"] = ((saida.get("comments") or "") + f" Outros e-mails: {val}").strip()
        else:
            saida[campo] = val
    return saida


def _fornecedor_por_nome(con, nome):
    if not nome:
        return None
    f = um(con, "SELECT id FROM suit_suppliers WHERE lower(name)=lower(?)", (nome.strip(),))
    if f:
        return f["id"]
    return inserir(con, "suit_suppliers", name=nome.strip())


def importar(con, tarefas):
    """As tarefas do projeto SUITS (com seção, campos e notas) → pedidos, leads e fornecedores.
    Já importada (mesmo gid) não é tocada: o que a equipe mudou aqui vale mais que o Asana."""
    res = {"pedidos": 0, "leads": 0, "fornecedores": 0, "ja_tinha": 0, "ignoradas": 0}
    for t in tarefas:
        gid, nome = t.get("gid"), (t.get("name") or "").strip()
        secao = next((m.get("section", {}).get("name") for m in t.get("memberships") or [] if m.get("section")), None)
        if not gid or not nome or nome.startswith("📋"):
            res["ignoradas"] += 1
            continue
        tabela = ("suit_orders" if secao in SECOES_PEDIDO else "suit_leads" if secao == "SUIT LEADS"
                  else "suit_suppliers" if secao == "Seleção de fornecedores" and nome != "Links" else None)
        if not tabela:
            res["ignoradas"] += 1
            continue
        if um(con, f"SELECT id FROM {tabela} WHERE asana_gid=?", (gid,)):
            res["ja_tinha"] += 1
            continue
        c = _campos(t)
        if tabela == "suit_suppliers":
            inserir(con, "suit_suppliers", name=nome, asana_gid=gid, **fornecedor_das_notas(t.get("notes")))
            res["fornecedores"] += 1
        elif tabela == "suit_leads":
            notas = (t.get("notes") or "").strip()
            email = next(iter(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", notas)), None)
            extra = "; ".join(f"{k}: {v}" for k, v in c.items() if v and k in ("Status", "Obs", "Pedido"))
            inserir(con, "suit_leads", name=nome, email=email, notes="\n".join(x for x in (notas, extra) if x) or None,
                    status="perdido" if c.get("Status") == "Canceled" else "aberto", asana_gid=gid)
            res["leads"] += 1
        else:
            asana_status = c.get("Status")
            status = etapa_valida(DO_ASANA.get(asana_status or "", "standby"))   # #382: só etapa que existe
            fechado = 1 if t.get("completed") or status in FECHADAS else 0
            forn = c.get("Fornecedor") or c.get("Supplier")
            inserir(con, "suit_orders", title=nome, product=_produto(nome), customer_name=nome, status=status,
                    order_date=(c.get("Order Date") or "")[:10] or None, due_on=t.get("due_on"),
                    supplier_id=_fornecedor_por_nome(con, forn), source="asana", asana_gid=gid,
                    asana_notes=(t.get("notes") or None), asana_status=asana_status, closed=fechado,
                    created_at=t.get("created_at") or agora())
            res["pedidos"] += 1
    return res
