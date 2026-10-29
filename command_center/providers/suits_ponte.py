"""Ponte de e-mail dos Suits (#153): o fluxo que o Ítalo montou no ChatGPT, rodando no VPS.

Ítalo (áudio de 08/10, pelo dono): *"entrou uma venda de macacão, ali pelo site ... manda um
e-mail automaticamente para o cliente agradecendo pela compra ... manda por favor as medidas, e
entregar o PDF ... e falar para o cliente mandar o design que ele quer ou a inspiração ... Quando
o cliente responde ... sem dar a informação do cliente ... extrai tudo e manda para o Matheus ...
se o Matheus tiver alguma pergunta, a IA faz aquele meio de campo ... Quando o Matheus entregar a
arte, a IA pega a arte, extrai a informação do Matheus e manda para o cliente ... eu pedi para
tudo passar por minha aprovação por isso que eu fui o gargalo"*. Dono: *"rode na nossa mente de
testes, faça simulações"*.

Como funciona, a cada ciclo do painel (15 min):
1. **Venda nova** no site (o e-mail "[Urace]: You've got a new order" com macacão) → abre o pedido.
2. **Resposta** na conversa do cliente, do designer ou do fornecedor de um pedido aberto.
3. **Marcador `Suits`** do Gmail numa conversa que ainda não é de pedido nenhum.
Cada mensagem é lida uma vez (`suit_email_seen`). Para cada evento a IA do AI Command (#152) lê
o pedido e o e-mail (com os anexos baixados) e age pelas ferramentas `suits_*`.

**Quem recebe é o painel que decide**, não o modelo: `enviar()` só manda para o cliente, o
designer ou o fornecedor DAQUELE pedido. O designer nunca recebe e-mail, telefone, endereço ou
nome completo do cliente; o cliente nunca recebe o nome ou o contato do designer.

**Simulação primeiro**: com `envio_automatico` desligado (o padrão), nada sai — o e-mail que a IA
mandaria fica na linha do tempo do pedido, para a equipe conferir. Ligou, sai sem aprovação
(era o gargalo). Teste nunca manda: `CC_EMAIL_FAKE=<arquivo>` grava em vez de enviar.
"""
import contextvars
import hashlib
import json
import mimetypes
import os
import re
import threading

from command_center.db import agora, auditar, conectar, inserir, todos, um

CONTA = "urace"
NOSSOS = ("urace@urace.us", "support@urace.us", "noreply@urace.us", "info@urace.us")
ANEXO_MAX = 15 * 1024 * 1024
ENVIO_MAX = 20 * 1024 * 1024          # o Gmail aceita 25 MB somados
POR_CICLO = int(os.environ.get("CC_SUITS_POR_CICLO", "5"))
SIMULAR = contextvars.ContextVar("suits_simular", default=False)
# #382 (C): durante um evento da ponte, o pedido daquele evento. As ferramentas `suits_*` só leem e mexem nele, e o
# agente não recebe as ferramentas gerais do painel (clientes, Atenção, QuickBooks, Gmail). Sem evento: None.
ESCOPO = contextvars.ContextVar("suits_escopo", default=None)
LIMITE_TENTATIVAS = int(os.environ.get("CC_SUITS_TENTATIVAS", "3"))

BOAS_VINDAS = """Hi {first name}, thank you for your order! We're excited to build your custom suit.

To get started: do you have a design, colors, or references in mind? Send any inspiration and your logos in high resolution.

For the fit, please fill in the attached sizing form, it has diagrams showing exactly how to take each measurement. Also send the driver's name as you want it on the suit, nationality, a frontal body photo, and note if he wears a rib protector.

A few things that make the measurements go faster: use a flexible tailor tape and have someone help you; take them against bare skin, with the muscles relaxed; if a number looks off, measure three times and use the average.

Before production, three rounds of design revisions are included at no charge. Because every suit is made to order, custom suits are not eligible for voluntary returns or refunds. If anything is wrong on our side, we fix it at no cost; if a measurement error makes the suit unusable, we offer 50% off a replacement, and if a design you provided requires a new suit, 33% off a replacement. All subject to the terms of your purchase.

Once I have the design and measurements, I'll send the mockup for approval and confirm the timeline!"""

# Contexto do robô do Ítalo (Mio, 08/10, #156): a política que ele passou para os macacões. Vale para os
# pedidos novos, sujeita aos termos da compra e aos direitos do cliente; conflito sobe para a equipe.
POLITICA = """Três rodadas de revisão do design antes da produção, sem custo.
Macacão personalizado não tem devolução voluntária nem reembolso.
Erro causado pela URACE: corrigido sem custo.
Erro de medida do cliente que torne o macacão inutilizável: 50% de desconto na troca.
Erro do design fornecido pelo cliente que exija macacão novo: 33% de desconto na troca.
Tudo sujeito aos termos da compra e aos direitos do cliente; conflito com isso sobe para a equipe."""

PADROES = {
    "ponte_ligada": "1",
    "envio_automatico": "0",
    # Mio do Ítalo: "Mateus (carvalhovisual1@gmail.com) é designer de suits, não deve ser apresentado ao cliente como fabricante"
    "designer_nome": "Mateus",
    "designer_email": "carvalhovisual1@gmail.com",
    # Mio do Ítalo: "replicate Eduardo Resende's URACE signature exactly except for the display name George"
    "assinatura": "Best regards,\nGeorge\n\nUrace\n+1(407)2502291\nurace@urace.us\nwww.urace.us\n10724 Cosmonaut Blvd, Orlando, FL 32824, USA",
    "boas_vindas": BOAS_VINDAS,
    "politica": POLITICA,
}


class Recusado(ValueError):
    """O e-mail não pode sair como está; a mensagem diz por quê (a IA lê e corrige)."""


# ------------------------------------------------------------------ configuração
def config(con):
    c = dict(PADROES)
    for r in todos(con, "SELECT key, value FROM suit_settings"):
        if r["key"] in c:
            c[r["key"]] = r["value"] if r["value"] is not None else ""
    return c


def salvar_config(con, dados, uid=None):
    for k, v in dados.items():
        if k not in PADROES or v is None:
            continue
        v = str(v) if k in ("boas_vindas", "assinatura", "politica") else str(v).strip()
        if k in ("ponte_ligada", "envio_automatico"):
            v = "1" if v in ("1", "true", "True") else "0"
        if k == "designer_email" and v and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
            raise Recusado("e-mail do designer inválido")
        con.execute("""INSERT INTO suit_settings (key, value, updated_at, updated_by) VALUES (?,?,?,?)
                       ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at,
                       updated_by=excluded.updated_by""", (k, v, agora(), uid))
    return config(con)


def raiz():
    caminho = os.path.join(os.environ.get("URACE_DIR", os.path.expanduser("~/.urace")), "suits")
    os.makedirs(caminho, exist_ok=True)
    return caminho


def pasta(pid):
    caminho = os.path.join(raiz(), "anexos", str(int(pid)))
    os.makedirs(caminho, exist_ok=True)
    return caminho


def manual_pdf():
    return os.path.join(raiz(), "manual-medidas.pdf")


def anexos_do_pedido(pid):
    p = pasta(pid)
    return sorted(n for n in os.listdir(p) if os.path.isfile(os.path.join(p, n)))


def _nome_seguro(nome):
    base = re.sub(r"[^\w.\- ]+", "_", os.path.basename(nome or "anexo")).strip() or "anexo"
    return base[:120]


def guardar_anexo(pid, nome, dados):
    """Grava o arquivo na pasta do pedido sem sobrescrever outro; devolve o nome usado."""
    nome = _nome_seguro(nome)
    raiz_n, ext = os.path.splitext(nome)
    destino, n = os.path.join(pasta(pid), nome), 1
    while os.path.exists(destino):
        n += 1
        nome = f"{raiz_n}-{n}{ext}"
        destino = os.path.join(pasta(pid), nome)
    with open(destino, "wb") as f:
        f.write(dados)
    return nome


# ------------------------------------------------------------------ o envio
def _digitos(s):
    return re.sub(r"\D", "", s or "")


RX_DINHEIRO = re.compile(r"(?:US)?\$\s?\d|\b\d+(?:[.,]\d{2})?\s?(?:USD|dollars?|d[óo]lares|reais)\b", re.I)


def _sem_acento(t):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", t or "") if not unicodedata.combining(c))


def _marcas_do_cliente(pedido):
    """O que identifica o cliente: e-mail, telefone, endereço e nome completo (só o que existe no pedido)."""
    texto, digitos = [], []
    email = (pedido.get("customer_email") or "").strip().lower()
    if email:
        texto.append(("o e-mail do cliente", email))
    tel = _digitos(pedido.get("customer_phone"))
    if len(tel) >= 7:
        digitos.append(("o telefone do cliente", tel[-10:] if len(tel) >= 10 else tel))
    for linha in (pedido.get("ship_address") or "").splitlines():
        if len(linha.strip()) >= 8:
            texto.append(("o endereço do cliente", re.sub(r"\s+", " ", linha.strip().lower())))
    nome = re.sub(r"\s+", " ", (pedido.get("customer_name") or "").strip().lower())
    if len(nome.split()) >= 2:
        texto.append(("o nome completo do cliente", nome))
    return texto, digitos


def _guardas(pedido, papel, texto, cfg):
    """O designer não vê dado do cliente (nem pagamento); o cliente não vê o designer."""
    t = re.sub(r"\s+", " ", (texto or "").lower())
    if papel == "designer":
        marcas, digitos = _marcas_do_cliente(pedido)
        problemas = [rot for rot, m in marcas if m in t]
        problemas += [rot for rot, d in digitos if d[-7:] in _digitos(texto)]
        if RX_DINHEIRO.search(texto or ""):
            problemas.append("valor ou pagamento")
        if problemas:
            raise Recusado("O designer não pode receber " + ", ".join(dict.fromkeys(problemas)) + ". Reescreva só com o design "
                           f"e o número do pedido (Suits #{pedido['id']}).")
    if papel == "cliente":
        for dado in (cfg.get("designer_email"), cfg.get("designer_nome")):
            if dado and len(dado) >= 3 and dado.lower() in t:
                raise Recusado("O cliente não pode ver o nome nem o contato do designer: fale como a URACE.")


def destinatario(con, pedido, papel, cfg):
    if papel == "cliente":
        return pedido.get("customer_email")
    if papel == "designer":
        return cfg.get("designer_email") or None
    if papel == "fornecedor":
        f = um(con, "SELECT email FROM suit_suppliers WHERE id=?", (pedido["supplier_id"],)) if pedido.get("supplier_id") \
            else um(con, "SELECT email FROM suit_suppliers WHERE is_current=1")
        return f["email"] if f else None
    raise Recusado("para quem? cliente, designer ou fornecedor")


def _arquivos(pid, nomes):
    saida, total = [], 0
    for nome in nomes or []:
        if nome == "manual_medidas":
            caminho, nome_final = manual_pdf(), "GUIDE TO FILLING IN SIZING - URACE FORM.pdf"
        else:
            nome_final = os.path.basename(nome)
            caminho = os.path.join(pasta(pid), nome_final)
        if not os.path.isfile(caminho):
            raise Recusado(f"anexo não encontrado: {nome}" + (" (o manual de medidas ainda não foi carregado na aba Suits › Ponte de e-mail)"
                                                               if nome == "manual_medidas" else ""))
        with open(caminho, "rb") as f:
            dados = f.read()
        total += len(dados)
        if total > ENVIO_MAX:
            raise Recusado("anexos passam de 20 MB: mande em dois e-mails")
        saida.append((nome_final, dados, mimetypes.guess_type(nome_final)[0] or "application/octet-stream"))
    return saida


def _marcas_do_designer(cfg):
    m = []
    email = (cfg.get("designer_email") or "").strip().lower()
    if email:
        m += [email, email.split("@")[0]]
    nome = (cfg.get("designer_nome") or "").strip().lower()
    if len(nome) >= 3:
        m.append(nome)
    return [x for x in m if len(x) >= 3]


LIMPAVEIS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


def _sem_metadados(nome, dados, mime):
    """Imagem (PNG, JPG, WEBP) e PDF saem sem autor, EXIF, comentário ou XMP. Revisão do Mio (#382): o que não
    dá para limpar NÃO sai — tipo não suportado ou limpeza que falhou viram recusa, nunca "manda o original"."""
    import io
    ext = os.path.splitext(nome)[1].lower()
    if mime in LIMPAVEIS:
        try:
            from PIL import Image
            im = Image.open(io.BytesIO(dados))
            im.load()
            im.info = {}
            fmt = LIMPAVEIS[mime]
            if fmt == "JPEG" and im.mode not in ("RGB", "L", "CMYK"):
                im = im.convert("RGB")
            limpa = Image.frombytes(im.mode, im.size, im.tobytes())   # só os pixels: nada do arquivo original vem junto
            if im.mode == "P" and im.getpalette():
                limpa.putpalette(im.getpalette())
            saida = io.BytesIO()
            extra = {"quality": 95} if fmt in ("JPEG", "WEBP") else {"optimize": True}
            limpa.save(saida, fmt, **extra)
            return saida.getvalue()
        except Exception as e:
            raise Recusado(f"não deu para limpar {nome} ({type(e).__name__}): o arquivo não sai. Peça o arquivo exportado "
                           "de novo em PNG, JPG ou PDF.")
    if mime == "application/pdf" or ext == ".pdf":
        try:
            from pypdf import PdfReader, PdfWriter
            r, w = PdfReader(io.BytesIO(dados)), PdfWriter()
            for pg in r.pages:
                w.add_page(pg)
            w.add_metadata({"/Producer": "URACE"})
            saida = io.BytesIO()
            w.write(saida)
            return saida.getvalue()
        except Exception as e:
            raise Recusado(f"não deu para limpar {nome} ({type(e).__name__}): o arquivo não sai. Peça o PDF exportado de novo.")
    raise Recusado(f"{nome}: este tipo de arquivo não é limpo pelo painel, então não sai (só PNG, JPG, WEBP ou PDF). "
                   "Peça o arquivo exportado num desses formatos.")


def limpar_para_cliente(arquivos, cfg):
    """Mio do Ítalo: nunca expor ao cliente o endereço, a assinatura ou os METADADOS do designer. O nome do
    arquivo também não leva o designer; e se o conteúdo ainda carregar o nome ou o e-mail dele, não sai."""
    marcas = _marcas_do_designer(cfg)
    saida = []
    for i, (nome, dados, mime) in enumerate(arquivos, 1):
        if nome.startswith("GUIDE TO FILLING IN SIZING"):
            saida.append((nome, dados, mime))
            continue
        dados = _sem_metadados(nome, dados, mime)
        if any(m in nome.lower() for m in marcas):
            nome = f"URACE-design-{i}{os.path.splitext(nome)[1].lower()}"
        baixo = dados.lower()
        if any(m.encode() in baixo for m in marcas):
            raise Recusado(f"o arquivo {nome} ainda carrega o nome ou o contato do designer: peça a arte exportada de novo "
                           "(ou em PNG/JPG/PDF) antes de mandar ao cliente.")
        saida.append((nome, dados, mime))
    return saida


VETORES = {".ai": "application/postscript", ".eps": "application/postscript", ".svg": "image/svg+xml"}


def _vetor_sem_metadados(nome, dados):
    """Dono, 22/10 (#382): AI, EPS e SVG (logo do cliente, arte do designer) entram pelo e-mail e vão ao designer;
    ao cliente continua só PNG, JPG, WEBP ou PDF. Do SVG saem <metadata>, <title>, <desc> e comentários; do AI e
    do EPS saem as linhas %%For, %%Creator, %%Title e %%Author do cabeçalho. O resto do arquivo vai como está e
    passa pela mesma busca de e-mail, telefone, endereço e nome do cliente."""
    ext = os.path.splitext(nome)[1].lower()
    if ext == ".svg":
        t = dados.decode("utf-8", "replace")
        t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
        t = re.sub(r"<(metadata|title|desc)\b[^>]*>.*?</\1\s*>|<(metadata|title|desc)\b[^>]*/>", "", t, flags=re.S | re.I)
        return t.encode("utf-8")
    return re.sub(rb"(?m)^%%(?:For|Creator|Title|Author|CreationDate):[^\r\n]*[\r\n]*", b"", dados)


def limpar_para_designer(arquivos, pedido):
    """#382 (C): o que vai ao designer sai sem metadados, e o arquivo que ainda contenha o e-mail, o telefone, o
    endereço ou o nome completo do cliente não sai. O nome do arquivo com o nome ou o e-mail do cliente é trocado."""
    marcas, digitos = _marcas_do_cliente(pedido)
    saida = []
    for i, (nome, dados, mime) in enumerate(arquivos, 1):
        if os.path.splitext(nome)[1].lower() in VETORES:
            dados = _vetor_sem_metadados(nome, dados)
        else:
            dados = _sem_metadados(nome, dados, mime)
        nome_baixo = _sem_acento(re.sub(r"[_\-.]+", " ", nome.lower()))
        if any(_sem_acento(m) in nome_baixo or m in nome.lower() for _, m in marcas):
            nome = f"Suits-{pedido['id']}-ref-{i}{os.path.splitext(nome)[1].lower()}"
        baixo = dados.lower()
        achou = [rot for rot, m in marcas if m.encode() in baixo]
        achou += [rot for rot, d in digitos if d.encode() in dados]
        if achou:
            raise Recusado(f"o arquivo {nome} contém {', '.join(dict.fromkeys(achou))}: não vai ao designer. Use um arquivo "
                           "só com o design.")
        saida.append((nome, dados, mime))
    return saida


def _envio_real(para, assunto, corpo, anexos, thread_id, em_resposta_a):
    falso = os.environ.get("CC_EMAIL_FAKE")
    if falso:
        with open(falso, "a", encoding="utf-8") as f:
            f.write(json.dumps({"to": para, "subject": assunto, "text": corpo, "anexos": [a[0] for a in anexos],
                                "thread_id": thread_id, "em_resposta_a": em_resposta_a}) + "\n")
        n = os.path.getsize(falso)
        return {"id": f"fake-msg-{n}", "thread_id": thread_id or f"fake-thread-{n}"}
    from command_center.providers import modulo
    return modulo("gmail").enviar_sistema(CONTA, para, assunto, corpo, anexos, thread_id, em_resposta_a)


def _chave_envio(pid, papel, assunto, corpo, arquivos):
    """Pedido + papel + hash de assunto, corpo e anexos: o mesmo e-mail tem sempre a mesma chave."""
    h = hashlib.sha256(f"{int(pid)}|{papel}|{assunto.strip()}|{corpo.strip()}".encode())
    for nome, dados, _ in arquivos:
        h.update(nome.encode() + b"\0" + hashlib.sha256(dados).digest())
    return h.hexdigest()


def _sem_re(a):
    return re.sub(r"^(re|fwd?):\s*", "", (a or "").strip(), flags=re.I).lower()


def _ja_saiu(linha, gm=None):
    """O "enviando" que ficou para trás: a mensagem saiu mesmo? Confere na thread do Gmail (ou nos enviados).
    Devolve o id da mensagem, ou None (aí pode reenviar)."""
    falso = os.environ.get("CC_EMAIL_FAKE")
    if falso and gm is None:
        if os.path.exists(falso):
            for n, x in enumerate(open(falso, encoding="utf-8").read().splitlines()):
                e = json.loads(x)
                if e.get("to") == linha["para"] and _sem_re(e.get("subject")) == _sem_re(linha["assunto"]):
                    return f"fake-conferido-{n}"
        return None
    if gm is None:
        from command_center.providers import modulo
        gm = modulo("gmail")
    try:
        if linha.get("thread_id"):
            msgs = gm.mensagens_da_thread(CONTA, linha["thread_id"], limite=200)["mensagens"]
        else:
            ths = gm.gmail_buscar(CONTA, f'in:sent to:{linha["para"]} newer_than:3d', so_inbox=False, maximo=10).get("threads") or []
            msgs = [m for t in ths for m in gm.mensagens_da_thread(CONTA, t["thread_id"], limite=200)["mensagens"]]
    except Exception:
        return None
    for m in msgs:
        if _nosso(m.get("de")) and _sem_re(m.get("assunto")) == _sem_re(linha["assunto"]):
            return m.get("message_id")
    return None


def _mandar(con, pedido, papel, para, assunto, corpo, arquivos, responder, user_id, ator, gm=None):
    """O envio de verdade, sem repetição: grava "enviando" com a chave única ANTES de mandar; já enviado não sai de
    novo; "enviando" pendente é conferido no Gmail antes de reenviar."""
    from command_center.providers import suits
    pid = pedido["id"]
    if pedido.get("is_test"):
        raise Recusado("pedido de TESTE: nenhum e-mail real sai dele")
    thread = pedido.get(f"gmail_thread_{papel}") if responder else None
    chave = _chave_envio(pid, papel, assunto, corpo, arquivos)
    linha = um(con, "SELECT * FROM suit_sends WHERE chave=?", (chave,))
    lista = ", ".join(a[0] for a in arquivos)
    resumo = f"para {papel} ({para}) — {assunto}" + (f" · anexos: {lista}" if lista else "") + f"\n\n{corpo}"
    if linha and linha["status"] == "enviado":
        return {"simulado": False, "repetido": True, "para": para, "id": linha["message_id"],
                "nota": "este e-mail já foi enviado: não mandei de novo"}
    if linha:
        mid = _ja_saiu(linha, gm)
        if mid:
            con.execute("UPDATE suit_sends SET status='enviado', message_id=?, sent_at=? WHERE chave=?", (mid, agora(), chave))
            suits.anotar(con, pid, "E-mail conferido no Gmail (tinha saído antes de o painel registrar) " + resumo, "email",
                         pedido["status"], user_id=user_id)
            return {"simulado": False, "repetido": True, "para": para, "id": mid}
    else:
        inserir(con, "suit_sends", chave=chave, order_id=pid, papel=papel, para=para, assunto=assunto, thread_id=thread)
    em_resposta_a = None
    if thread:
        try:
            from command_center.providers import modulo
            msgs = (gm or modulo("gmail")).mensagens_da_thread(CONTA, thread, limite=200)["mensagens"]
            em_resposta_a = msgs[-1].get("message_id_header") if msgs else None
        except Exception:
            em_resposta_a = None
        if not assunto.lower().startswith("re:"):
            assunto = "Re: " + assunto
    r = _envio_real(para, assunto, corpo, arquivos, thread, em_resposta_a)
    con.execute("UPDATE suit_sends SET status='enviado', message_id=?, sent_at=?, thread_id=coalesce(thread_id, ?) WHERE chave=?",
                (r.get("id"), agora(), r.get("thread_id"), chave))
    if r.get("id"):                                   # o que nós mandamos não volta como evento
        con.execute("INSERT OR IGNORE INTO suit_email_seen (message_id, order_id, thread_id, papel) VALUES (?,?,?,?)",
                    (r["id"], pid, r.get("thread_id"), papel))
    if r.get("thread_id") and not pedido.get(f"gmail_thread_{papel}"):
        con.execute(f"UPDATE suit_orders SET gmail_thread_{papel}=? WHERE id=?", (r["thread_id"], pid))
    suits.anotar(con, pid, "E-mail enviado " + resumo, "email", pedido["status"], user_id=user_id)
    auditar(con, "suit.email.sent", ator, user_id=user_id, entity_type="suit_order", entity_id=pid,
            detail={"papel": papel, "para": para, "assunto": assunto, "anexos": [a[0] for a in arquivos]})
    return {"simulado": False, "para": para, "id": r.get("id"), "thread_id": r.get("thread_id")}


RX_BOAS_VINDAS = re.compile(r"thank you for (?:your|the) (?:order|purchase)|obrigad[oa] pel[ao] (?:sua )?(?:compra|pedido)"
                            r"|gracias por (?:tu|su) (?:compra|pedido)|sizing form|manual de medidas", re.I)


def _pasta_preparados(pid, oid):
    caminho = os.path.join(raiz(), "preparados", str(int(pid)), str(int(oid)))
    os.makedirs(caminho, exist_ok=True)
    return caminho


def preparar_designer(con, pedido, assunto, corpo, arquivos, responder=True, user_id=None):
    """#382 (C): o e-mail ao designer NÃO sai daqui. Vira um item "preparado" no pedido, com o assunto, o corpo e os
    anexos já limpos; alguém da equipe (OPERATOR ou acima) confere e clica "Enviar ao designer"."""
    from command_center.providers import suits
    oid = inserir(con, "suit_outbox", order_id=pedido["id"], papel="designer", subject=assunto, body=corpo,
                  attachments=json.dumps([a[0] for a in arquivos], ensure_ascii=False), reply=1 if responder else 0,
                  created_by=user_id)
    destino = _pasta_preparados(pedido["id"], oid)
    for nome, dados, _ in arquivos:
        with open(os.path.join(destino, os.path.basename(nome)), "wb") as f:
            f.write(dados)
    suits.anotar(con, pedido["id"], f"E-mail ao designer PREPARADO (item #{oid}): {assunto}. Alguém da equipe confere e envia.",
                 "email", pedido["status"], user_id=user_id)
    return {"preparado": True, "item": oid, "nota": "o e-mail ao designer ficou preparado: uma pessoa da equipe confere e envia"}


def enviar_preparado(con, oid, user_id, gm=None):
    """O clique "Enviar ao designer": confere de novo (guardas e limpeza) e manda de verdade, com a auditoria.
    Vale mesmo com a ponte em simulação: o clique da pessoa é a autorização."""
    item = um(con, "SELECT * FROM suit_outbox WHERE id=?", (int(oid),))
    if not item:
        raise LookupError("Item não encontrado.")
    if item["status"] != "preparado":
        raise Recusado(f"este item já está {item['status']}")
    pedido = dict(um(con, "SELECT * FROM suit_orders WHERE id=?", (item["order_id"],)))
    if pedido.get("discarded_at"):
        raise Recusado("pedido descartado (não é pedido de macacão): nada sai por ele")
    cfg = config(con)
    para = destinatario(con, pedido, "designer", cfg)
    if not para:
        raise Recusado("o e-mail do designer não está configurado (aba Suits › Ponte de e-mail)")
    _guardas(pedido, "designer", item["subject"] + "\n" + item["body"], cfg)
    pasta_item = _pasta_preparados(pedido["id"], item["id"])
    arquivos = []
    for nome in json.loads(item["attachments"] or "[]"):
        caminho = os.path.join(pasta_item, os.path.basename(nome))
        if not os.path.isfile(caminho):
            raise Recusado(f"anexo preparado não encontrado: {nome}")
        with open(caminho, "rb") as f:
            arquivos.append((nome, f.read(), mimetypes.guess_type(nome)[0] or "application/octet-stream"))
    arquivos = limpar_para_designer(arquivos, pedido)
    r = _mandar(con, pedido, "designer", para, item["subject"], item["body"], arquivos, bool(item["reply"]), user_id,
                f"user:{user_id}", gm)
    con.execute("UPDATE suit_outbox SET status='enviado', decided_by=?, decided_at=?, message_id=?, thread_id=? WHERE id=?",
                (user_id, agora(), r.get("id"), r.get("thread_id"), item["id"]))
    auditar(con, "suit.designer.sent", f"user:{user_id}", user_id=user_id, entity_type="suit_order", entity_id=pedido["id"],
            detail={"item": item["id"], "para": para, "assunto": item["subject"], "anexos": [a[0] for a in arquivos]})
    return dict(r, item=item["id"])


def descartar_preparado(con, oid, user_id):
    from command_center.providers import suits
    item = um(con, "SELECT * FROM suit_outbox WHERE id=?", (int(oid),))
    if not item:
        raise LookupError("Item não encontrado.")
    if item["status"] != "preparado":
        raise Recusado(f"este item já está {item['status']}")
    con.execute("UPDATE suit_outbox SET status='descartado', decided_by=?, decided_at=? WHERE id=?", (user_id, agora(), item["id"]))
    st = um(con, "SELECT status FROM suit_orders WHERE id=?", (item["order_id"],))["status"]
    suits.anotar(con, item["order_id"], f"E-mail preparado ao designer (item #{item['id']}) descartado.", "email", st, user_id=user_id)
    return True


def preparados(con, pid):
    return [dict(x, attachments=json.loads(x["attachments"] or "[]"))
            for x in todos(con, "SELECT * FROM suit_outbox WHERE order_id=? ORDER BY id DESC LIMIT 20", (int(pid),))]


def enviar(con, pid, papel, assunto, corpo, anexos=None, responder=True, user_id=None, tipo=None, gm=None):
    """O único caminho de e-mail da ponte. Simulação (padrão ou forçada): vira nota e não sai.
    Ao designer, nunca sai daqui: vira item preparado (#382). Boas-vindas sem o manual de medidas não saem."""
    from command_center.providers import suits
    pedido = dict(um(con, "SELECT * FROM suit_orders WHERE id=?", (pid,)) or {})
    if not pedido:
        raise Recusado("pedido não encontrado")
    if pedido.get("discarded_at"):
        raise Recusado("pedido descartado (não é pedido de macacão): nada sai por ele")
    if not pedido.get("ia_ligada", 1):
        raise Recusado("a IA está desligada neste pedido (#198): quem responde é a equipe")
    if papel not in ("cliente", "designer", "fornecedor"):
        raise Recusado("para quem? cliente, designer ou fornecedor")
    cfg = config(con)
    para = destinatario(con, pedido, papel, cfg)
    if not para:
        raise Recusado({"cliente": "o pedido não tem o e-mail do cliente",
                        "designer": "o e-mail do designer não está configurado (aba Suits › Ponte de e-mail)",
                        "fornecedor": "o fornecedor não tem e-mail"}[papel])
    assunto, corpo = (assunto or "").strip(), (corpo or "").strip()
    if not assunto or not corpo:
        raise Recusado("assunto e corpo são obrigatórios")
    anexos = list(anexos or [])
    boas_vindas = papel == "cliente" and (tipo == "boas_vindas" or "manual_medidas" in anexos
                                          or bool(RX_BOAS_VINDAS.search(assunto + "\n" + corpo)))
    if boas_vindas:
        if not os.path.isfile(manual_pdf()):
            raise Recusado("As boas-vindas não saem sem o manual de medidas (o PDF): a equipe sobe o arquivo em "
                           "Suits › Ponte de e-mail › Manual de medidas. Use suits_precisa_humano.")
        if "manual_medidas" not in anexos:
            anexos.append("manual_medidas")
    _guardas(pedido, papel, assunto + "\n" + corpo, cfg)
    arquivos = _arquivos(pid, anexos)
    if papel == "cliente":
        arquivos = limpar_para_cliente(arquivos, cfg)
    elif papel == "designer":
        arquivos = limpar_para_designer(arquivos, pedido)
    teste = bool(pedido.get("is_test"))               # #382: pedido de teste nunca manda e-mail real, em papel nenhum
    if papel == "designer" and not SIMULAR.get() and not teste:
        return preparar_designer(con, pedido, assunto, corpo, arquivos, responder, user_id)
    simulado = teste or SIMULAR.get() or cfg["envio_automatico"] != "1"
    lista = ", ".join(a[0] for a in arquivos)
    resumo = f"para {papel} ({para}) — {assunto}" + (f" · anexos: {lista}" if lista else "") + f"\n\n{corpo}"
    if simulado:
        if teste:
            resumo = "(pedido de TESTE: nunca sai) " + resumo
        quem = "a IA prepararia este e-mail ao designer (uma pessoa enviaria)" if papel == "designer" else "a IA mandaria este e-mail"
        nid = suits.anotar(con, pid, f"SIMULAÇÃO — {quem} " + resumo, "email", pedido["status"], user_id=user_id)
        return {"simulado": True, "nota": nid, "para": para}
    r = _mandar(con, pedido, papel, para, assunto, corpo, arquivos, responder, user_id, "ai:suits_ponte", gm)
    if boas_vindas and not r.get("repetido"):
        con.execute("UPDATE suit_orders SET welcome_sent_at=coalesce(welcome_sent_at, ?) WHERE id=?", (agora(), pid))
    return r


def pedir_aprovacao_final(con, pid, introducao=None, user_id=None):
    """#382 (A): o e-mail de aprovação final, montado pelo painel (não pela IA): a versão exata, os arquivos da arte
    final anexados, as medidas e a política (não retornável, não reembolsável). Fica gravado o que o cliente viu."""
    from command_center.providers import suits
    p = um(con, "SELECT * FROM suit_orders WHERE id=?", (int(pid),))
    if not p:
        raise Recusado("pedido não encontrado")
    e = suits.estado_aprovacao(con, pid)
    if e["bloqueios"]:
        raise Recusado("A aprovação final ainda não pode ir ao cliente: falta " + "; ".join(e["bloqueios"])
                       + ". Medida a conferir é da equipe: use suits_precisa_humano.")
    cfg = config(con)
    assunto, corpo = suits.texto_aprovacao_final(dict(p), e, introducao, cfg.get("assinatura") or "")
    r = enviar(con, pid, "cliente", assunto, corpo, e["arte_final"], True, user_id, tipo="aprovacao_final")
    registro = {"arte": e["hash_arte"], "medidas": e["hash_medidas"], "versao": e["versao"], "arquivos": e["arte_final"],
                "em": agora(), "simulado": bool(r.get("simulado")), "message_id": r.get("id"), "nota": r.get("nota")}
    con.execute("UPDATE suit_orders SET final_request=? WHERE id=?", (json.dumps(registro, ensure_ascii=False), int(pid)))
    return dict(r, versao=e["versao"])


def precisa_humano(con, pid, motivo, user_id=None):
    from command_center.providers import suits
    p = um(con, "SELECT title, status, is_test FROM suit_orders WHERE id=?", (pid,))
    if not p:
        raise Recusado("pedido não encontrado")
    suits.anotar(con, pid, f"Precisa de alguém da equipe: {motivo}", "ia", p["status"], user_id=user_id)
    if p.get("is_test"):                               # #382: pedido de teste não avisa na Atenção
        return {"ok": True, "teste": True}
    if not um(con, "SELECT id FROM ai_events WHERE kind='suit.humano' AND entity_id=? AND status='NEW'", (pid,)):
        inserir(con, "ai_events", kind="suit.humano", entity_type="suit_order", entity_id=pid,
                summary=f"Suits #{pid} ({p['title']}): {motivo}"[:300], status="NEW")
    return {"ok": True}


def precisa_humano_sem_pedido(con, motivo):
    """E-mail que não dá para ligar a um pedido só (casou com mais de um, ou a ponte desistiu): vai para a equipe
    em Precisa de atenção, sem ligar a pedido nenhum."""
    resumo = f"Suits: {motivo}"[:300]
    if not um(con, "SELECT id FROM ai_events WHERE kind='suit.humano' AND entity_id IS NULL AND summary=? AND status='NEW'", (resumo,)):
        inserir(con, "ai_events", kind="suit.humano", entity_type="suit_order", entity_id=None, summary=resumo, status="NEW")
    return {"ok": True}


def _ambiguo(con, msgs, thread, pids, quem):
    """Revisão do Mio (#382): casou com mais de um pedido → não liga a nenhum; a equipe decide."""
    _marcar(con, msgs, None, thread, "ambiguo")
    lista = ", ".join(f"#{x}" for x in sorted(pids))
    precisa_humano_sem_pedido(con, f"{quem} (thread {thread}) casa com mais de um pedido aberto ({lista}): não liguei a "
                                   "nenhum. Ligue a conversa ao pedido certo em Ponte de e-mail › Ligar conversas.")
    return {"thread_id": thread, "pedidos": sorted(pids)}


# ------------------------------------------------------------------ os eventos
def _nosso(de):
    """A URACE: as caixas da lista e qualquer pessoa da equipe com e-mail @urace.us (#182)."""
    d = (de or "").lower()
    return any(n in d for n in NOSSOS) or _email_de(d).endswith("@urace.us")


def _visto(con, mid):
    return um(con, "SELECT 1 AS x FROM suit_email_seen WHERE message_id=?", (mid,)) is not None


def _marcar(con, msgs, pid, thread, papel):
    for m in msgs:
        con.execute("INSERT OR IGNORE INTO suit_email_seen (message_id, order_id, thread_id, papel) VALUES (?,?,?,?)",
                    (m["message_id"], pid, thread, papel))


RX_VENDA = re.compile(r"\bsuits?\b|macac", re.I)

# #195 (dono, 13/10): "Vai estar claro na mensagem, no corpo ou no título do e-mail que vai ser um pedido
# de suit". O marcador Suits do Gmail sozinho não basta: o assunto ou o texto têm de falar de macacão.
RX_FALA_DE_SUIT = re.compile(
    r"\bsuits?\b|macac[ãa]o|macac[õo]es|\b(?:monos?|trajes?|buzos?)\s+de\s+(?:kart\w*|carreras?|piloto|corrida)"
    r"|\bcombinaisons?\b|\boverol\b|\btuta\s+(?:da\s+)?kart", re.I)
# Quem escreve por robô (cobrança, aviso, newsletter) nunca é cliente de macacão.
RX_ROBO = re.compile(r"^(?:no-?reply|do-?not-?reply|donotreply|mailer-daemon|postmaster|bounces?|notifications?|notify"
                     r"|newsletters?|news|marketing|billing|invoices?|receipts?|alerts?|updates?)(?:[+._-].*)?$", re.I)


def fala_de_suit(msgs):
    """O assunto ou o corpo de alguma mensagem da conversa fala de macacão."""
    return any(RX_FALA_DE_SUIT.search((m.get("assunto") or "") + "\n" + (m.get("corpo") or "")) for m in msgs)


def robo(email):
    """Remetente automático: noreply, cobrança, aviso, newsletter."""
    local = (email or "").split("@")[0]
    return bool(local) and bool(RX_ROBO.match(local))


def novas_vendas(con, gm):
    """O e-mail do WooCommerce de pedido novo, com macacão, que ainda não virou pedido."""
    eventos = []
    r = gm.gmail_buscar(CONTA, 'subject:"new order" newer_than:3d', so_inbox=False, maximo=20)
    for t in r.get("threads") or []:
        msgs = gm.mensagens_da_thread(CONTA, t["thread_id"])["mensagens"]
        novas = [m for m in msgs if not _visto(con, m["message_id"]) and "new order" in (m.get("assunto") or "").lower()]
        if not novas:
            continue
        m = novas[0]
        if not RX_VENDA.search(m.get("corpo") or ""):
            _marcar(con, novas, None, t["thread_id"], "venda")    # venda sem macacão: não é da ponte
            continue
        num = re.search(r"#\s?(\d{3,})", m.get("assunto") or "")
        site = num.group(1) if num else None
        ja = um(con, "SELECT id FROM suit_orders WHERE site_order=?", (site,)) if site else None
        pid = ja["id"] if ja else inserir(con, "suit_orders", title=f"Pedido do site #{site or '?'}", source="site",
                                          site_order=site, status="standby", updated_at=agora())
        if not ja:
            from command_center.providers import suits
            suits.anotar(con, pid, f"Venda no site{f' #{site}' if site else ''}: a IA abre o pedido e manda as boas-vindas.",
                         "etapa", "standby")
        eventos.append({"tipo": "venda", "pedido_id": pid, "thread_id": t["thread_id"], "mensagens": novas})
    return eventos


def respostas(con, gm):
    """Mensagem nova nas conversas de um pedido aberto, de quem não é a URACE."""
    eventos = []
    abertos = todos(con, """SELECT id, gmail_thread_cliente, gmail_thread_designer, gmail_thread_fornecedor
                           FROM suit_orders WHERE closed=0 AND discarded_at IS NULL AND (gmail_thread_cliente IS NOT NULL
                           OR gmail_thread_designer IS NOT NULL OR gmail_thread_fornecedor IS NOT NULL)""")
    donos = {}
    for p in abertos:
        for papel in ("cliente", "designer", "fornecedor"):
            if p[f"gmail_thread_{papel}"]:
                donos.setdefault(p[f"gmail_thread_{papel}"], set()).add(p["id"])
    ja_ambiguas = set()
    for p in abertos:
        for papel in ("cliente", "designer", "fornecedor"):
            th = p[f"gmail_thread_{papel}"]
            if not th:
                continue
            if len(donos[th]) > 1:                     # #382: a mesma conversa em dois pedidos não é de nenhum
                if th not in ja_ambiguas:
                    ja_ambiguas.add(th)
                    try:
                        msgs = [m for m in gm.mensagens_da_thread(CONTA, th)["mensagens"] if not _visto(con, m["message_id"])]
                    except Exception:
                        msgs = []
                    if msgs:
                        _ambiguo(con, msgs, th, donos[th], "uma conversa ligada")
                continue
            try:
                msgs = gm.mensagens_da_thread(CONTA, th)["mensagens"]
            except Exception:
                continue
            novas = [m for m in msgs if not _visto(con, m["message_id"]) and not _nosso(m.get("de"))]
            nossas = [m for m in msgs if not _visto(con, m["message_id"]) and _nosso(m.get("de"))]
            _marcar(con, nossas, p["id"], th, papel)               # o que a equipe mandou à mão não é evento
            if novas:
                eventos.append({"tipo": papel, "pedido_id": p["id"], "thread_id": th, "mensagens": novas})
    return eventos


RX_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def _email_de(de):
    m = RX_EMAIL.search(de or "")
    return m.group(0).lower() if m else ""


def _nome_de(de):
    n = (de or "").split("<")[0].strip().strip('"')
    return n if n and "@" not in n else ""


def _pedidos_do_fornecedor(con, assunto):
    """'SUIT - Bennie Shifter (…)' → os pedidos abertos cujo título ou piloto aparece no assunto. Revisão do Mio
    (#382): sem adivinhar — quem chama só liga quando é exatamente um."""
    a = (assunto or "").lower()
    achados = set()
    for p in todos(con, "SELECT id, title, driver_name FROM suit_orders WHERE closed=0 AND discarded_at IS NULL ORDER BY id DESC"):
        for nome in (p["title"], p["driver_name"]):
            n = (nome or "").strip().lower()
            # debug 29/10: o nome inteiro, como palavra — "ana fict" dentro de "ana ficticia" é o suit de outro cliente
            if len(n) >= 4 and re.search(r"(?<!\w)" + re.escape(n) + r"(?!\w)", a):
                achados.add(p["id"])
    return achados


def conversas_novas(con, gm, ignoradas=None):
    """Conversa nova que ainda não é de pedido nenhum: com o marcador Suits, do designer, ou de um
    cliente com pedido aberto. Quem mandou decide o papel; o pedido é achado antes da IA.
    As conversas de pedido descartado (#195) continuam em `ligadas`: são puladas, nunca reabrem nada."""
    eventos = []
    ignoradas = [] if ignoradas is None else ignoradas
    cfg = config(con)
    ligadas = {r["t"] for r in todos(con, """SELECT gmail_thread_cliente AS t FROM suit_orders WHERE gmail_thread_cliente IS NOT NULL
                                              UNION SELECT gmail_thread_designer FROM suit_orders WHERE gmail_thread_designer IS NOT NULL
                                              UNION SELECT gmail_thread_fornecedor FROM suit_orders WHERE gmail_thread_fornecedor IS NOT NULL""")}
    fornecedores = {r["email"].lower() for r in todos(con, "SELECT email FROM suit_suppliers WHERE email IS NOT NULL")}
    clientes = {}
    for r in todos(con, """SELECT lower(customer_email) AS e, id FROM suit_orders
                           WHERE closed=0 AND discarded_at IS NULL AND customer_email IS NOT NULL"""):
        if not _nosso(r["e"]) and not robo(_email_de(r["e"])):      # #195: a URACE e robô nunca são "o cliente"
            clientes.setdefault(r["e"], set()).add(r["id"])
    consultas = ["label:Suits newer_than:3d"]
    if cfg.get("designer_email"):
        consultas.append(f"from:{cfg['designer_email']} newer_than:3d")
    emails = sorted(clientes)
    for i in range(0, len(emails), 15):
        consultas.append("from:(" + " OR ".join(emails[i:i + 15]) + ") newer_than:3d")
    vistas = set()
    for q in consultas:
        for t in (gm.gmail_buscar(CONTA, q, so_inbox=False, maximo=20).get("threads") or []):
            th = t["thread_id"]
            if th in ligadas or th in vistas:
                continue
            vistas.add(th)
            msgs = gm.mensagens_da_thread(CONTA, th)["mensagens"]
            _marcar(con, [m for m in msgs if not _visto(con, m["message_id"]) and _nosso(m.get("de"))], None, th, "conversa")
            novas = [m for m in msgs if not _visto(con, m["message_id"]) and not _nosso(m.get("de"))]
            if not novas:
                continue
            de, assunto = _email_de(novas[-1].get("de")), novas[0].get("assunto") or ""
            if de in fornecedores:
                achados = _pedidos_do_fornecedor(con, assunto)
                if len(achados) > 1:
                    _ambiguo(con, novas, th, achados, f"e-mail do fornecedor ({assunto[:80]})")
                    continue
                pid = next(iter(achados)) if achados else None
                if pid and not um(con, "SELECT gmail_thread_fornecedor FROM suit_orders WHERE id=?", (pid,))["gmail_thread_fornecedor"]:
                    con.execute("UPDATE suit_orders SET gmail_thread_fornecedor=? WHERE id=?", (th, pid))
                eventos.append({"tipo": "fornecedor", "pedido_id": pid, "thread_id": th, "mensagens": novas})
            elif cfg.get("designer_email") and de == cfg["designer_email"].lower():
                # debug 29/10: o número inteiro (\b) — a cor "#1A1A1A" não é o pedido #1 de outro cliente
                ids = {int(x) for x in re.findall(r"#\s?(\d+)\b", assunto + " " + (novas[-1].get("corpo") or "")[:500])}
                ids = {x for x in ids if um(con, "SELECT 1 AS x FROM suit_orders WHERE id=? AND discarded_at IS NULL", (x,))}
                if len(ids) > 1:
                    _ambiguo(con, novas, th, ids, "e-mail do designer")
                    continue
                pid = next(iter(ids)) if ids else None
                if pid:
                    con.execute("UPDATE suit_orders SET gmail_thread_designer=coalesce(gmail_thread_designer, ?) WHERE id=?", (th, pid))
                eventos.append({"tipo": "designer", "pedido_id": pid, "thread_id": th, "mensagens": novas})
            elif de in clientes and len(clientes[de]) > 1:
                _ambiguo(con, novas, th, clientes[de], f"e-mail de um cliente com mais de um pedido aberto ({de})")
            elif de in clientes:
                pid = next(iter(clientes[de]))
                con.execute("UPDATE suit_orders SET gmail_thread_cliente=coalesce(gmail_thread_cliente, ?) WHERE id=?", (th, pid))
                eventos.append({"tipo": "cliente", "pedido_id": pid, "thread_id": th, "mensagens": novas, "historico": msgs})
            elif robo(de) or not fala_de_suit(msgs):
                # #195 (dono, 13/10: "Vai estar claro na mensagem, no corpo ou no título do e-mail que vai ser um
                # pedido de suit"): sem falar de macacão, ou vindo de robô, nem chega à IA. Lida uma vez e esquecida.
                _marcar(con, novas, None, th, "nao_suit")
                ignoradas.append({"thread_id": th, "de": de, "assunto": assunto[:120]})
            else:
                # #182 (dono, 09/10: "quando for um pedido de suit, ele adiciona lá"): o marcador Suits de quem
                # não tem pedido NÃO abre pedido. A IA lê primeiro e só cria se for pedido de macacão. Sem
                # pedido, a conversa não fica ligada a nada: se não couber neste ciclo, volta no próximo do
                # mesmo jeito (antes, voltava como "resposta do cliente" e o pedido ficava).
                eventos.append({"tipo": "marcador", "pedido_id": None, "thread_id": th, "mensagens": novas, "historico": msgs,
                                "remetente": {"nome": _nome_de(novas[-1].get("de")) or None, "email": de or None}})
    return eventos


def baixar_anexos(gm, pid, msg):
    """Os anexos da mensagem (e as imagens coladas no corpo) vão para a pasta do pedido."""
    nomes = []
    for a in msg.get("anexos") or []:
        if (a.get("bytes") or 0) > ANEXO_MAX:
            nomes.append(f"(não baixado, grande demais: {a.get('nome')})")
            continue
        try:
            nomes.append(guardar_anexo(pid, a.get("nome"), gm.anexo_bytes(CONTA, msg["message_id"], a["attachment_id"])))
        except Exception as e:
            nomes.append(f"(não baixado: {a.get('nome')}: {str(e)[:80]})")
    return nomes


# ------------------------------------------------------------------ a IA
QUE_FAZER = {
    "venda": ("VENDA NOVA NO SITE. Preencha o pedido com os dados da venda (suits_atualizar_pedido: title = nome do cliente, "
              "customer_name, customer_email, customer_phone, ship_address, driver_name se houver, product, quantity, "
              "paid_at se pago, language pelo país e pelo idioma do cliente). Depois mande ao cliente (suits_email "
              "para=\"cliente\", tipo=\"boas_vindas\", anexos=[\"manual_medidas\"]) as boas-vindas no idioma dele, a partir do "
              "MODELO DE BOAS-VINDAS, e mova para awaiting_measurements. As boas-vindas NUNCA saem sem o manual de medidas: "
              "se a ferramenta recusar por falta do PDF, suits_precisa_humano."),
    "cliente": ("O CLIENTE RESPONDEU. Leia tudo, inclusive as imagens e PDFs baixados. Grave as medidas que vierem "
                "(suits_atualizar_pedido medidas, na unidade que ele usou), o design (ideia, cores, logos, posicao_logos, nome, "
                "bandeira, observacoes) e o nome do piloto. Medida que parecer errada ou fora do comum: suits_medida_suspeita "
                "com o motivo, e pergunte ao cliente. Se faltar algo, responda pedindo SÓ o que falta. Quando houver "
                "design suficiente para começar, prepare ao designer (para=\"designer\") um briefing claro, com os anexos de "
                "inspiração e logos e a referência \"Suits #{id}\" — sem nome completo, e-mail, telefone, endereço, valor ou "
                "pagamento do cliente; o e-mail fica PREPARADO e uma pessoa da equipe envia — e mova para design_pending. "
                "Pediu ajuste: leve o ajuste ao designer.\n"
                "APROVAÇÃO FINAL (dono, 22/10: vale por e-mail). Só registre (suits_registrar_aprovacao, com o message_id da "
                "mensagem dele e o trecho EXATO em que aprova) quando o cliente aprovar EXPRESSAMENTE a versão final mostrada "
                "no e-mail de aprovação final (o que saiu por suits_pedir_aprovacao_final, com a versão, as medidas e a "
                "política). \"Gostei\", \"ficou legal\", \"perfeito\" sobre um mockup, ou aprovação de uma versão anterior, NÃO "
                "contam: nesse caso, se a arte final e as medidas conferidas estiverem prontas, mande o e-mail de aprovação "
                "final (suits_pedir_aprovacao_final) e peça que ele aprove por escrito aquela versão. A aprovação só vale "
                "para a arte e as medidas daquele momento; mudou algo, é preciso aprovar de novo."),
    "designer": ("O DESIGNER RESPONDEU. Pergunta: leve ao cliente com as suas palavras, como a URACE (sem nome nem contato do "
                 "designer). Arte entregue (anexo): marque o arquivo da versão a aprovar como arte final "
                 "(suits_marcar_arte_final), mande a arte ao cliente (anexos com os arquivos baixados) pedindo aprovação ou "
                 "ajustes, e mova para design_review. Quando o cliente gostar e as medidas estiverem conferidas pela equipe, "
                 "a aprovação final vai por suits_pedir_aprovacao_final."),
    "fornecedor": ("O FORNECEDOR ESCREVEU. Anote o que ele disse (suits_anotar); se confirmou o pedido, mova para "
                   "supplier_accepted; se avisou produção, in_production; se despachou, in_transit COM o rastreio (tracking). "
                   "O fornecedor manda as fotos do macacão pelo WhatsApp: fotos recebidas, conferido e endereço enviado são da "
                   "equipe, nunca seus. O endereço do cliente só vai ao fornecedor depois do OK da equipe, e nunca ao designer. "
                   "Se pedir decisão ou houver problema (medida errada, cor), suits_precisa_humano."),
    "marcador": ("E-MAIL COM O MARCADOR SUITS DE QUEM NÃO TEM PEDIDO ABERTO. NENHUM PEDIDO FOI CRIADO: classifique antes "
                 "(dono, 09/10: \"quando for um pedido de suit, ele adiciona lá\"). Leia a conversa inteira.\n"
                 "1) É PEDIDO DE MACACÃO só quando a pessoa (cliente, não a equipe nem fornecedor) quer comprar um macacão "
                 "novo: pede orçamento ou preço para fazer o dela, manda medidas ou design para encomendar, confirma que quer "
                 "fazer, ou pagou. Aí: veja em suits_pedidos se ela já tem pedido aberto (mesmo e-mail); se tem, "
                 "suits_atualizar_pedido nele com gmail_thread_cliente=\"{thread}\" e siga do ponto em que está; se não tem, "
                 "suits_criar_pedido com title e customer_name (o nome dela), customer_email, gmail_thread_cliente=\"{thread}\" "
                 "e o que ela já mandou, e responda com as boas-vindas (tipo=\"boas_vindas\", anexos=[\"manual_medidas\"]) ou "
                 "com o próximo passo.\n"
                 "2) NÃO É PEDIDO (e não crie nada): fornecedor ou fábrica, homologação/FIA, nota fiscal, frete, propaganda, "
                 "newsletter, conversa interna da equipe, dúvida geral sem intenção de comprar, agradecimento, assunto de outro "
                 "serviço, ou qualquer dúvida sobre ser pedido. Na dúvida, NÃO crie: responda só \"não é pedido: <motivo>\" "
                 "e pare. Não responda e-mail para quem não fez pedido."),
    "simulacao": ("SIMULAÇÃO NESTE PEDIDO (nada sai: os e-mails viram nota). Leia o pedido e as conversas abaixo e faça o próximo "
                  "passo do processo como se fosse de verdade."),
}

ISOLAMENTO = ("ISOLAMENTO (#382): neste evento você só enxerga e só mexe {alvo}. É PROIBIDO buscar, ler, citar ou trazer "
              "para este pedido dados de outros clientes ou de outros pedidos (nome, e-mail, telefone, endereço, medidas, "
              "design, valores ou conversas). As ferramentas recusam qualquer outro pedido.")


def prompt(con, ev, cfg, anexos_baixados):
    pid = ev.get("pedido_id")
    linhas = []
    for m, nomes in zip(ev["mensagens"], anexos_baixados):
        linhas.append(f"--- message_id: {m.get('message_id')} · de: {m.get('de')} · {m.get('data')} · assunto: {m.get('assunto')}\n"
                      f"{m.get('corpo') or ''}"
                      + (f"\nAnexos baixados (leia com Read em {pasta(pid) if pid else '—'}): {', '.join(nomes)}" if nomes else ""))
    historico = ""
    if ev.get("historico"):
        historico = "\nCONVERSA ANTERIOR (contexto):\n" + "\n".join(
            f"- {m.get('de')} · {m.get('data')}: {(m.get('corpo') or '')[:800]}" for m in ev["historico"] if m not in ev["mensagens"])
    designer = cfg.get("designer_nome") or "o designer"
    alvo = f"no pedido Suits #{pid}" if pid else "no pedido desta pessoa (o que ela já tem, pelo e-mail dela, ou o que você criar)"
    return (f"[PONTE DE E-MAIL DOS SUITS] Você é o meio de campo entre o cliente, {designer} e o fornecedor, no lugar da equipe "
            "(processo: 10_PROCESSOS/Pedido de macacão.md). "
            + (f"Pedido Suits #{pid}: leia com suits_pedido e os anexos com suits_anexos. " if pid else "")
            + f"Thread do Gmail: {ev.get('thread_id')}.\n\n"
            + ISOLAMENTO.replace("{alvo}", alvo) + "\n\n"
            + QUE_FAZER[ev["tipo"]].replace("{id}", str(pid or "?")).replace("{thread}", str(ev.get("thread_id") or ""))
            + (f"\nRemetente: {ev['remetente'].get('nome') or '—'} <{ev['remetente'].get('email') or '—'}>." if ev.get("remetente") else "")
            + "\n\nSEMPRE: no idioma do cliente, educado e comercial (ainda é venda), respeitando o que ele pediu; não prometa "
              "preço, prazo ou desconto que não esteja no pedido ou na POLÍTICA; assine com a ASSINATURA. Se a conversa já tem "
              "as boas-vindas da URACE (agradecimento + manual de medidas), não mande de novo: siga do ponto em que está; e em "
              "pedido que começou antes da ponte não mande adendo de política por conta própria. O designer é designer, não "
              "fabricante: nunca diga ao cliente quem desenha nem quem fabrica, nem repasse texto, assinatura ou conversa dele. "
              "Na dúvida (reclamação, reembolso, cancelamento, troca, mudança de preço, conflito com a política, algo estranho), "
              "não responda: suits_precisa_humano com o motivo. No fim, se houver pedido, suits_anotar com o que fez em uma linha."
            + ("" if cfg.get("designer_email") else "\nO e-mail do designer ainda não foi configurado: se precisar falar com ele, "
               "use suits_precisa_humano dizendo o que mandaria.")
            + _grupos_do_atelie()
            + f"\n\nPOLÍTICA DOS MACACÕES (do dono):\n{cfg['politica']}"
            + f"\n\nMODELO DE BOAS-VINDAS (referência; adapte ao idioma e ao pedido):\n{cfg['boas_vindas']}"
            + f"\n\nASSINATURA:\n{cfg['assinatura']}"
            + "\n\nMENSAGENS NOVAS:\n" + "\n".join(linhas) + historico)


def _grupos_do_atelie():
    """#383: com o grupo de design do WhatsApp configurado, o design vai ao designer por lá."""
    from command_center.providers import atelie_whatsapp
    return atelie_whatsapp.instrucao_para_ponte()


def _admin(con):
    a = um(con, "SELECT id FROM users WHERE role='ADMIN' AND active=1 ORDER BY id LIMIT 1")
    return a["id"] if a else None


def _executar_padrao(con, cid, texto, sk, uid, pr):
    from command_center.api import ia
    ia._executa(cid, texto, sk, uid, pr)


def _saude(con, pid, **campos):
    if pid and campos:
        con.execute(f"UPDATE suit_orders SET {', '.join(k + '=?' for k in campos)} WHERE id=?", (*campos.values(), int(pid)))


def escopo_do_evento(ev):
    """O que as ferramentas `suits_*` podem tocar neste evento (#382, C)."""
    papel = ev["tipo"] if ev["tipo"] in ("cliente", "designer", "fornecedor") else ("cliente" if ev["tipo"] in ("marcador", "venda") else None)
    return {"pedido": ev.get("pedido_id"), "tipo": ev["tipo"],
            "email": ((ev.get("remetente") or {}).get("email") or "").lower() or None,
            "mensagens": {m.get("message_id"): {"de": m.get("de"), "data": m.get("data"), "corpo": m.get("corpo") or "",
                                                "papel": papel or ("cliente" if "[cliente]" in (m.get("de") or "") else None)}
                          for m in ev["mensagens"] if m.get("message_id")}}


def tratar(con, ev, gm=None, executar=None, simular=False):
    """Um evento → um comando da IA (na conversa automática), com o pedido e os anexos. Bloqueia.
    Devolve o id do comando; levanta se a IA falhou (o evento volta no próximo ciclo)."""
    from command_center.providers import modulo, suits
    gm = gm or modulo("gmail")
    cfg = config(con)
    pid = ev.get("pedido_id")
    baixados = [baixar_anexos(gm, pid, m) if pid else [] for m in ev["mensagens"]]
    pr = prompt(con, ev, cfg, baixados)
    uid = _admin(con)
    if uid is None:
        return None
    texto = f"EVENTO AUTOMÁTICO — Suits{f' #{pid}' if pid else ''}: {ev['tipo']}"
    cid = inserir(con, "ai_commands", user_id=uid, text=texto, prompt=pr, session_key=f"suits-{pid or ev.get('thread_id')}")
    if pid:
        st = um(con, "SELECT status FROM suit_orders WHERE id=?", (pid,))["status"]
        suits.anotar(con, pid, {"venda": "A IA está abrindo o pedido da venda do site.", "cliente": "Chegou e-mail do cliente: a IA está tratando.",
                                "designer": "Chegou e-mail do designer: a IA está tratando.", "fornecedor": "Chegou e-mail do fornecedor.",
                                "simulacao": "Simulação da ponte neste pedido (nada sai)."}.get(ev["tipo"], "A IA está tratando."),
                     "ia", st, command_id=cid)
    _saude(con, pid, bridge_last_try_at=agora(),
           bridge_last_mode="simulacao" if (simular or cfg["envio_automatico"] != "1") else "real")
    marca = SIMULAR.set(bool(simular))
    escopo = escopo_do_evento(ev)
    marca_escopo = ESCOPO.set(escopo)
    try:
        (executar or _executar_padrao)(con, cid, texto, f"suits-{pid or ev.get('thread_id')}", uid, pr)
    except Exception as e:
        _saude(con, pid or escopo.get("pedido"), bridge_last_error=f"{type(e).__name__}: {str(e)[:160]}", bridge_last_error_at=agora())
        raise
    finally:
        SIMULAR.reset(marca)
        ESCOPO.reset(marca_escopo)
    pid = pid or escopo.get("pedido")              # o marcador que virou pedido
    c = um(con, "SELECT status, error FROM ai_commands WHERE id=?", (cid,))
    if c and c["status"] == "FAILED":
        _saude(con, pid, bridge_last_error=(c["error"] or "a IA falhou")[:200], bridge_last_error_at=agora())
        raise RuntimeError(f"a IA falhou: {(c['error'] or '')[:160]}")
    _saude(con, pid, bridge_last_ok_at=agora())
    return cid


def _tentativa(con, chave, pid, erro):
    """Mais uma falha deste evento. Devolve quantas já foram."""
    con.execute("""INSERT INTO suit_event_tries (chave, order_id, tries, last_error, updated_at) VALUES (?,?,1,?,?)
                   ON CONFLICT(chave) DO UPDATE SET tries=tries+1, last_error=excluded.last_error, updated_at=excluded.updated_at""",
                (chave, pid, erro[:300], agora()))
    return um(con, "SELECT tries FROM suit_event_tries WHERE chave=?", (chave,))["tries"]


def conferir_pendentes(con, gm=None):
    """O "enviando" que ficou para trás (o processo caiu entre o envio e o registro): confere no Gmail se saiu.
    Saiu, vira "enviado"; não saiu, fica (a próxima tentativa de mandar confere de novo antes de reenviar)."""
    conferidos = 0
    for linha in todos(con, "SELECT * FROM suit_sends WHERE status='enviando'"):
        mid = _ja_saiu(linha, gm)
        if mid:
            con.execute("UPDATE suit_sends SET status='enviado', message_id=?, sent_at=? WHERE chave=?", (mid, agora(), linha["chave"]))
            conferidos += 1
    return conferidos


def _guardar_rodada(con, res):
    resumo = {"at": agora(), "eventos": res.get("eventos", 0), "erros": len(res.get("erros") or []),
              "simulacao": res.get("simulacao"), "tratados": len(res.get("tratados") or []), "pulada": res.get("pulada"),
              "ambiguos": res.get("ambiguos", 0)}
    con.execute("""INSERT INTO suit_settings (key, value, updated_at) VALUES ('ultima_rodada', ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
                (json.dumps(resumo, ensure_ascii=False), agora()))


def ultima_rodada(con):
    r = um(con, "SELECT value FROM suit_settings WHERE key='ultima_rodada'")
    try:
        return json.loads(r["value"]) if r and r["value"] else None
    except ValueError:
        return None


def rodar(con, gm=None, executar=None):
    """Um ciclo da ponte. Devolve o resumo (vai para a auditoria e para o topo da aba)."""
    from command_center.api import ia
    from command_center.providers import modulo, suits
    cfg = config(con)
    if cfg["ponte_ligada"] != "1":
        res = {"pulada": "ponte desligada"}
        _guardar_rodada(con, res)
        return res
    if executar is None and ia.motor_da_ia() != "sdk":
        res = {"pulada": "a IA não está no motor novo (falta a chave da Anthropic no serviço)"}
        _guardar_rodada(con, res)
        return res
    gm = gm or modulo("gmail")
    eventos, erros, ignoradas = [], [], []
    try:
        conferir_pendentes(con, gm)
    except Exception as e:
        erros.append(f"conferir_pendentes: {type(e).__name__}: {str(e)[:160]}")
    antes_amb = um(con, "SELECT COUNT(*) AS n FROM suit_email_seen WHERE papel='ambiguo'")["n"]
    for nome, fonte in (("novas_vendas", lambda: novas_vendas(con, gm)), ("respostas", lambda: respostas(con, gm)),
                        ("conversas_novas", lambda: conversas_novas(con, gm, ignoradas))):
        try:
            eventos += fonte()
        except Exception as e:
            erros.append(f"{nome}: {type(e).__name__}: {str(e)[:160]}")
    feitos = []
    for ev in eventos[:POR_CICLO]:
        if ev.get("pedido_id") and suits.ia_desligada(con, ev["pedido_id"]):
            _marcar(con, ev["mensagens"], ev.get("pedido_id"), ev.get("thread_id"), ev["tipo"])
            try:
                feitos.append({"tipo": ev["tipo"], "pedido": ev["pedido_id"], "ia_desligada": True,
                               "anexos": [n for m in ev["mensagens"] for n in baixar_anexos(gm, ev["pedido_id"], m)]})
                quem = {"venda": "a venda do site", "cliente": "e-mail do cliente", "designer": "e-mail do designer",
                        "fornecedor": "e-mail do fornecedor"}.get(ev["tipo"], "e-mail")
                precisa_humano(con, ev["pedido_id"], f"chegou {quem} e a IA está desligada neste pedido: a equipe responde")
            except Exception as e:
                erros.append(f"{ev['tipo']} #{ev.get('pedido_id')}: {type(e).__name__}: {str(e)[:160]}")
            continue
        try:
            cid = tratar(con, ev, gm, executar)
            # #382: lido só DEPOIS de tratado; o que a IA criou (marcador → pedido) fica ligado ao pedido
            _marcar(con, ev["mensagens"], ev.get("pedido_id"), ev.get("thread_id"), ev["tipo"])
            feitos.append({"tipo": ev["tipo"], "pedido": ev.get("pedido_id"), "comando": cid})
        except Exception as e:
            erro = f"{type(e).__name__}: {str(e)[:160]}"
            erros.append(f"{ev['tipo']} #{ev.get('pedido_id')}: {erro}")
            chave = ev["mensagens"][0].get("message_id") or str(ev.get("thread_id"))
            n = _tentativa(con, chave, ev.get("pedido_id"), erro)
            if n >= LIMITE_TENTATIVAS:              # desiste: a equipe assume, e o evento não volta mais
                _marcar(con, ev["mensagens"], ev.get("pedido_id"), ev.get("thread_id"), ev["tipo"])
                motivo = f"a ponte tentou {n} vezes tratar um e-mail ({ev['tipo']}) e não conseguiu ({erro[:120]})"
                try:
                    if ev.get("pedido_id"):
                        precisa_humano(con, ev["pedido_id"], motivo)
                    else:
                        precisa_humano_sem_pedido(con, f"{motivo}; thread {ev.get('thread_id')}")
                except Exception:
                    pass
    ambiguos = um(con, "SELECT COUNT(*) AS n FROM suit_email_seen WHERE papel='ambiguo'")["n"] - antes_amb
    res = {"eventos": len(eventos), "tratados": feitos, "nao_sao_de_suit": ignoradas, "ficaram_para_o_proximo": max(0, len(eventos) - POR_CICLO),
           "simulacao": cfg["envio_automatico"] != "1", "erros": erros, "ambiguos": ambiguos}
    if eventos or erros or ignoradas or ambiguos:
        auditar(con, "suit.bridge.round", "system", detail=res)
    _guardar_rodada(con, res)
    return res


def simular_pedido(con, pid, gm=None, executar=None):
    """Roda a ponte num pedido, com as conversas ligadas a ele, sem mandar nada (dono: "faça simulações")."""
    from command_center.providers import modulo
    p = um(con, "SELECT * FROM suit_orders WHERE id=?", (pid,))
    if not p:
        raise Recusado("pedido não encontrado")
    if p["discarded_at"]:
        raise Recusado("pedido descartado: restaure antes de simular")
    if not p["ia_ligada"]:
        raise Recusado("a IA está desligada neste pedido: ligue antes de simular")
    gm = gm or modulo("gmail")
    msgs = []
    for papel in ("cliente", "designer", "fornecedor"):
        if p[f"gmail_thread_{papel}"]:
            msgs += [dict(m, de=f"{m.get('de')} [{papel}]") for m in gm.mensagens_da_thread(CONTA, p[f"gmail_thread_{papel}"])["mensagens"]]
    if not msgs:
        msgs = [{"message_id": "-", "de": "(sem conversa ligada)", "data": "", "assunto": "", "corpo": "Ainda não há e-mail ligado a este "
                 "pedido. Faça o próximo passo com o que está no pedido (por exemplo, as boas-vindas se ainda não houve)."}]
    return tratar(con, {"tipo": "simulacao", "pedido_id": pid, "thread_id": p["gmail_thread_cliente"], "mensagens": msgs}, gm,
                  executar, simular=True)


def suspeitos(con, gm=None):
    """#195, a reanálise: pedidos em andamento que vieram de e-mail ou da IA e não parecem de macacão.
    Só leitura: quem descarta é uma pessoa (tela ou `manage suits-descartar`)."""
    if gm is None:
        try:
            from command_center.providers import modulo
            gm = modulo("gmail")
        except Exception:
            gm = None
    out = []
    for p in todos(con, """SELECT id, title, customer_email, gmail_thread_cliente, source FROM suit_orders
                           WHERE closed=0 AND discarded_at IS NULL AND source NOT IN ('asana', 'site', 'manual') ORDER BY id"""):
        motivos, assunto = [], None
        e = _email_de(p["customer_email"])
        if e and _nosso(e):
            motivos.append("o cliente é um e-mail da URACE")
        if e and robo(e):
            motivos.append("o cliente é um remetente automático")
        if p["gmail_thread_cliente"] and gm is not None:
            try:
                msgs = gm.mensagens_da_thread(CONTA, p["gmail_thread_cliente"])["mensagens"]
                assunto = (msgs[0].get("assunto") if msgs else None) or None
                if not fala_de_suit(msgs):
                    motivos.append("a conversa não fala de macacão")
            except Exception as ex:
                motivos.append(f"não deu para ler a conversa ({type(ex).__name__})")
        if motivos:
            out.append({"id": p["id"], "title": p["title"], "customer_email": p["customer_email"], "assunto": assunto,
                        "motivos": motivos})
    return out


_LOCK = threading.Lock()


def rodar_em_segundo_plano():
    """Chamado pelo ciclo do painel: um ciclo por vez, sem travar a sincronia."""
    if not _LOCK.acquire(blocking=False):
        return False

    def _vai():
        con = conectar()
        try:
            rodar(con)
        except Exception as e:
            try:
                auditar(con, "suit.bridge.failed", "system", detail={"erro": f"{type(e).__name__}: {str(e)[:300]}"})
            except Exception:
                pass
        finally:
            con.close()
            _LOCK.release()
    threading.Thread(target=_vai, daemon=True, name="cc-suits-ponte").start()
    return True
