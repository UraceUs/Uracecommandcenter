"""Robô SDR no SMS (Dialpad) e no e-mail (support@), dono 20/10.

Nada sai da máquina: a ponte do robô responde por arquivo (CC_PONTE_FAKE), o SMS vai para CC_DIALPAD_FAKE e o
e-mail para CC_EMAIL_FAKE; a caixa da support@ vem de CC_GMAIL_FAKE.
"""
import json
import os
import tempfile

import pytest

os.environ["URACE_ENV"] = "/nao/existe"

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api import auth  # noqa: E402
from command_center.api.main import app  # noqa: E402
from command_center.db import aplicar_schema, conectar, inserir, um  # noqa: E402
from command_center.providers import sdr_canais  # noqa: E402

B = "/ops/api"
SENHA = "senha-forte-123"
CHAVE = "chave-do-hook-de-teste"
LEAD = "+14075550199"


@pytest.fixture()
def ambiente(monkeypatch):
    pasta = tempfile.mkdtemp()
    os.environ["CC_DB_PATH"] = os.path.join(pasta, "cc.sqlite")
    os.environ["DIALPAD_ENV"] = "/nao/existe"
    monkeypatch.setenv("DIALPAD_HOOK_KEY", CHAVE)
    monkeypatch.delenv("DIALPAD_HOOK_SECRET", raising=False)
    monkeypatch.setenv("SDR_CANAIS_ENV", "/nao/existe")
    for k in ("SDR_CANAL_SMS", "SDR_CANAL_EMAIL", "SDR_CANAL_SO_PARA", "SDR_CANAL_HORARIO", "SDR_CANAL_DIAS",
              "SDR_CANAL_ESPERA_MIN", "SDR_CANAL_FILA_HORAS"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("SDR_CANAL_LOTE_MIN", "0")       # na hora; os testes do lote (21/10) ligam o ritmo
    monkeypatch.setenv("CC_DIALPAD_FAKE", os.path.join(pasta, "sms.jsonl"))
    monkeypatch.setenv("CC_EMAIL_FAKE", os.path.join(pasta, "email.jsonl"))
    monkeypatch.setenv("CC_PONTE_FAKE", os.path.join(pasta, "ponte.json"))
    monkeypatch.setenv("CC_GMAIL_FAKE", os.path.join(pasta, "caixa.json"))
    monkeypatch.setattr(sdr_canais, "nivel", lambda: "atender")
    con = conectar(); aplicar_schema(con)
    auth.criar_usuario(con, "admin@urace.us", "Admin", "ADMIN", SENHA)
    inserir(con, "clients", name="Rafael Pistoni", email="rafael.pistoni@example.com",
            phone="+1 305-555-0145", status="ACTIVE", source="asana")
    con.commit()
    ponte({"rota": "responder", "motivo": None, "mensagens": ["Oi! Aqui é o Chase, da URACE.",
                                                              "É pra você ou pra outra pessoa?"],
           "precisa_gente": False, "nota": ""})
    yield {"pasta": pasta, "con": con}
    con.close()


def ponte(resposta):
    with open(os.environ["CC_PONTE_FAKE"], "w", encoding="utf-8") as f:
        json.dump(resposta, f)


def enviados(nome):
    caminho = os.environ["CC_DIALPAD_FAKE" if nome == "sms" else "CC_EMAIL_FAKE"]
    if not os.path.exists(caminho):
        return []
    with open(caminho, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def sms(texto, numero=LEAD, direcao="inbound", sid="s-1"):
    return {"id": sid, "direction": direcao, "from_number": numero if direcao == "inbound" else "+14075550100",
            "to_number": ["+14075550100"] if direcao == "inbound" else [numero], "text": texto,
            "contact": {"name": "Ana Souza"}}


# ------------------------------------------------------------------ SMS
def test_evento_de_sms_nao_e_ligacao():
    assert sdr_canais.eh_sms(sms("oi"))
    assert not sdr_canais.eh_sms({"call_id": "c-1", "state": "hangup"})
    assert not sdr_canais.eh_sms({"call": {"id": 1}})


def test_sms_com_canal_desligado_so_guarda(ambiente):
    con = ambiente["con"]
    r = sdr_canais.sms_evento(con, sms("Oi, quanto custa?"), esperar=False)
    assert "desligado" in r["robo"] and enviados("sms") == []
    assert um(con, "SELECT COUNT(*) AS n FROM sdr_canal_mensagens WHERE por='lead'")["n"] == 1


def test_sms_de_lead_o_robo_responde_em_baloes(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_SMS", "1")
    con = ambiente["con"]
    r = sdr_canais.sms_evento(con, sms("Oi, quanto custa?"), esperar=False)
    assert r["robo"] == "respondeu" and r["baloes"] == 2
    saida = enviados("sms")
    assert [s["text"] for s in saida] == ["Oi! Aqui é o Chase, da URACE.", "É pra você ou pra outra pessoa?"]
    assert all(s["to"] == LEAD for s in saida)
    c = um(con, "SELECT * FROM sdr_canal_contatos WHERE canal='sms'")
    assert c["respostas"] == 1 and c["contato"] == "14075550199" and c["nome"] == "Ana Souza"
    # o mesmo evento de novo (o Dialpad reenvia) não gera outra resposta
    assert sdr_canais.sms_evento(con, sms("Oi, quanto custa?"), esperar=False)["sms"] == "duplicado"
    assert len(enviados("sms")) == 2


def test_eco_do_robo_nao_pausa_e_resposta_da_equipe_pausa(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_SMS", "1")
    con = ambiente["con"]
    sdr_canais.sms_evento(con, sms("Oi"), esperar=False)
    # a assinatura "all" devolve o que o robô mandou: é eco, não é a equipe
    eco = sdr_canais.sms_evento(con, sms("É pra você ou pra outra pessoa?", direcao="outbound", sid="o-1"), esperar=False)
    assert eco["sms"] == "eco do robô"
    assert not sdr_canais.pausado(um(con, "SELECT * FROM sdr_canal_contatos WHERE canal='sms'"))
    # uma pessoa respondeu à mão pelo Dialpad: o robô sai da conversa
    r = sdr_canais.sms_evento(con, sms("Oi Ana, aqui é da equipe, te ligo já", direcao="outbound", sid="o-2"),
                              esperar=False)
    assert "pausado" in r["sms"]
    antes = len(enviados("sms"))
    r = sdr_canais.sms_evento(con, sms("Ok, obrigada", sid="s-2"), esperar=False)
    assert "pessoa assumiu" in r["robo"] and len(enviados("sms")) == antes


def test_sms_de_cliente_o_robo_nao_responde(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_SMS", "1")
    r = sdr_canais.sms_evento(ambiente["con"], sms("Amanhã tem treino?", numero="+13055550145"), esperar=False)
    assert "cliente" in r["robo"] and enviados("sms") == []


def test_lista_de_teste_como_a_tag_teste_sdr(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_SMS", "1")
    monkeypatch.setenv("SDR_CANAL_SO_PARA", "(407) 555-0111, teste@example.com")
    r = sdr_canais.sms_evento(ambiente["con"], sms("Oi"), esperar=False)
    assert "lista de teste" in r["robo"] and enviados("sms") == []
    r = sdr_canais.sms_evento(ambiente["con"], sms("Oi", numero="+14075550111", sid="s-9"), esperar=False)
    assert r["robo"] == "respondeu"


def test_nivel_organizar_nao_envia(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_SMS", "1")
    monkeypatch.setattr(sdr_canais, "nivel", lambda: "organizar")
    r = sdr_canais.sms_evento(ambiente["con"], sms("Oi"), esperar=False)
    assert "organizar" in r["robo"] and enviados("sms") == []


def test_pare_o_robo_confirma_e_nunca_mais_escreve(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_SMS", "1")
    con = ambiente["con"]
    ponte({"rota": "confirmar_opt_out", "motivo": "OPT_OUT", "precisa_gente": False,
           "mensagens": ["Tudo certo, não vamos mais te mandar mensagens por aqui."]})
    sdr_canais.sms_evento(con, sms("pare de mandar mensagem"), esperar=False)
    assert um(con, "SELECT opt_out FROM sdr_canal_contatos WHERE canal='sms'")["opt_out"] == 1
    r = sdr_canais.sms_evento(con, sms("oi de novo", sid="s-3"), esperar=False)
    assert "parar" in r["robo"] and len(enviados("sms")) == 1


def test_robo_passa_para_a_equipe_vira_atencao(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_SMS", "1")
    con = ambiente["con"]
    ponte({"rota": "escalar", "motivo": "NEGOCIACAO", "precisa_gente": True,
           "nota": "Objeção de preço: a ponte oferece a call e passa a conversa para a equipe.",
           "mensagens": ["Entendo. Que tal uma call rápida de 15 minutos com o nosso time?", "https://cal"]})
    sdr_canais.sms_evento(con, sms("Tá caro, faz por 500?"), esperar=False)
    from command_center.api import atencao
    itens = [i for i in atencao.coletar(con) if i["key"].startswith("sdr-canal")]
    assert len(itens) == 1 and "SMS" in itens[0]["title"] and "Objeção" in itens[0]["why"]


def test_webhook_do_dialpad_aceita_sms(ambiente):
    with TestClient(app, base_url="https://cc.test") as cli:
        r = cli.post(f"{B}/dialpad/webhook?key={CHAVE}", json=sms("Oi, vocês têm aula pra criança?"))
    assert r.status_code == 200 and r.json()["sms"] == "recebido"
    con = conectar()
    assert um(con, "SELECT texto FROM sdr_canal_mensagens WHERE por='lead'")["texto"].startswith("Oi, vocês")
    assert um(con, "SELECT COUNT(*) AS n FROM calls")["n"] == 0, "SMS não vira ligação"
    con.close()


# ------------------------------------------------------------------ e-mail (support@)
def caixa(threads):
    with open(os.environ["CC_GMAIL_FAKE"], "w", encoding="utf-8") as f:
        json.dump(threads, f)


def thread(tid="t-1", de='"Ana Souza" <ana@example.com>', corpo="Hi, how much is a day on track?", extra=None,
           cabecalhos=None, marcadores=None, mid="m-1"):
    msgs = list(extra or []) + [{"message_id": mid, "de": de, "assunto": "Karting for my son",
                                 "message_id_header": f"<{mid}@mail.example.com>", "corpo": corpo,
                                 "marcadores": marcadores or ["INBOX", "UNREAD"], "cabecalhos": cabecalhos or {}}]
    return {"thread_id": tid, "mensagens": msgs}


def test_email_de_lead_o_robo_responde_na_mesma_conversa(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_EMAIL", "1")
    con = ambiente["con"]
    caixa([thread(corpo="Hi, how much is a day on track?\n\nOn Mon, Oct 19 someone wrote:\n> old stuff")])
    r = sdr_canais.ler_email(con)
    assert r["conversas"][0]["robo"] == "respondeu"
    e = enviados("email")
    assert len(e) == 1 and e[0]["to"] == "ana@example.com" and e[0]["subject"] == "Re: Karting for my son"
    assert e[0]["thread_id"] == "t-1" and e[0]["in_reply_to"] == "<m-1@mail.example.com>"
    assert e[0]["text"].endswith(sdr_canais.ASSINATURA) and "Oi! Aqui é o Chase" in e[0]["text"]
    lead = um(con, "SELECT texto FROM sdr_canal_mensagens WHERE canal='email' AND por='lead'")["texto"]
    assert "old stuff" not in lead, "a citação da mensagem anterior não vai para o robô"
    # a segunda passada não responde de novo a mesma mensagem
    sdr_canais.ler_email(con)
    assert len(enviados("email")) == 1


@pytest.mark.parametrize("ajuste", [
    {"de": "Booking <no-reply@booking.com>"},
    {"de": "Team <team@urace.us>"},
    {"cabecalhos": {"List-Unsubscribe": "<mailto:x@y>"}},
    {"cabecalhos": {"Auto-Submitted": "auto-replied"}},
    {"cabecalhos": {"Precedence": "bulk"}},
    {"marcadores": ["INBOX", "Label_123"]},
    {"marcadores": ["INBOX", "CATEGORY_PROMOTIONS"]},
])
def test_email_automatico_ou_filtrado_o_robo_nao_responde(ambiente, monkeypatch, ajuste):
    monkeypatch.setenv("SDR_CANAL_EMAIL", "1")
    caixa([thread(**ajuste)])
    sdr_canais.ler_email(ambiente["con"])
    assert enviados("email") == []


def test_email_de_cliente_o_robo_nao_responde(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_EMAIL", "1")
    caixa([thread(de="Rafael <rafael.pistoni@example.com>", corpo="Can we move Saturday?")])
    r = sdr_canais.ler_email(ambiente["con"])
    assert "cliente" in r["conversas"][0]["robo"] and enviados("email") == []


def test_email_que_a_equipe_ja_respondeu_e_da_equipe(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_EMAIL", "1")
    equipe = {"message_id": "m-0", "de": "URACE <support@urace.us>", "corpo": "Hi Ana, call me", "marcadores": []}
    caixa([thread(extra=[equipe], mid="m-2", corpo="Thanks! What about Sunday?")])
    r = sdr_canais.ler_email(ambiente["con"])
    assert "pessoa assumiu" in r["conversas"][0]["robo"] and enviados("email") == []


def test_email_desligado_nao_le_a_caixa(ambiente):
    caixa([thread()])
    assert sdr_canais.ler_email(ambiente["con"]) == {"email": "desligado"}
    assert enviados("email") == []


# ------------------------------------------------------------------ painel e script
def test_painel_lista_e_reativa(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_SMS", "1")
    con = ambiente["con"]
    sdr_canais.sms_evento(con, sms("Oi"), esperar=False)
    sdr_canais.sms_evento(con, sms("Oi Ana, é da equipe", direcao="outbound", sid="o-9"), esperar=False)
    with TestClient(app, base_url="https://cc.test") as cli:
        assert cli.post(f"{B}/auth/login", json={"email": "admin@urace.us", "password": SENHA}).status_code == 200
        h = {"X-CSRF": cli.cookies.get("cc_csrf")}
        resumo = cli.get(f"{B}/sdr/canais").json()
        assert resumo["sms"]["ligado"] and resumo["contatos"][0]["pausado_ate"]
        cid = resumo["contatos"][0]["id"]
        conversa = cli.get(f"{B}/sdr/canais/{cid}").json()
        assert [m["por"] for m in conversa["mensagens"]] == ["lead", "robo", "robo", "equipe"]
        assert cli.post(f"{B}/sdr/canais/{cid}", json={"acao": "reativar"}, headers=h).status_code == 200
    con2 = conectar()
    assert um(con2, "SELECT pausado_ate FROM sdr_canal_contatos WHERE id=?", (cid,))["pausado_ate"] is None
    con2.close()


def test_script_do_dialpad_nunca_mostra_chave():
    import importlib.util
    from pathlib import Path
    caminho = Path(__file__).resolve().parents[2] / "adminai" / "deploy" / "dialpad_sms.py"
    spec = importlib.util.spec_from_file_location("dialpad_sms", caminho)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    texto = m.mascarar('{"hook_url": "https://ops.urace.us/ops/api/dialpad/webhook?key=abc123", "secret": "s3cr3t"}')
    assert "abc123" not in texto and "s3cr3t" not in texto and "key=***" in texto


# ------------------------------------------------------------------ revisão: STOP, rajada, eco, só lead, falha
@pytest.mark.parametrize("texto", ["STOP", "Stop.", "stop", " PARE ", "unsubscribe"])
def test_stop_sozinho_encerra_sem_resposta_mesmo_com_o_robo_desligado(ambiente, texto):
    con = ambiente["con"]
    r = sdr_canais.sms_evento(con, sms(texto), esperar=False)
    assert "STOP" in r["robo"] and enviados("sms") == []
    assert um(con, "SELECT opt_out FROM sdr_canal_contatos WHERE canal='sms'")["opt_out"] == 1


def test_start_devolve_o_contato(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_SMS", "1")
    con = ambiente["con"]
    sdr_canais.sms_evento(con, sms("STOP"), esperar=False)
    sdr_canais.sms_evento(con, sms("UNSTOP", sid="s-2"), esperar=False)
    assert um(con, "SELECT opt_out FROM sdr_canal_contatos WHERE canal='sms'")["opt_out"] == 0


def test_rajada_com_threads_de_verdade_uma_resposta_so(ambiente, monkeypatch):
    """O caminho do servidor: cada SMS abre uma thread que espera; só a da última mensagem responde."""
    import threading
    import time
    monkeypatch.setenv("SDR_CANAL_SMS", "1")
    monkeypatch.setenv("SDR_CANAL_RAJADA_SEG", "0.3")
    chamadas = []
    original = sdr_canais.perguntar_ao_robo

    def ponte_lenta(*a, **k):
        chamadas.append(a[2])
        time.sleep(0.5)
        return original(*a, **k)
    monkeypatch.setattr(sdr_canais, "perguntar_ao_robo", ponte_lenta)
    monkeypatch.setattr(sdr_canais, "_intervalo", lambda t: 0)
    con = ambiente["con"]
    sdr_canais.sms_evento(con, sms("Oi", sid="r-1"))
    time.sleep(0.1)
    sdr_canais.sms_evento(con, sms("quanto custa?", sid="r-2"))
    for t in [t for t in threading.enumerate() if t.name == "sdr-sms"]:
        t.join(timeout=5)
    assert chamadas == ["Oi\nquanto custa?"], chamadas
    assert len(enviados("sms")) == 2


def test_eco_que_chega_durante_o_envio_nao_pausa_o_robo(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_SMS", "1")
    con = ambiente["con"]
    original = sdr_canais.enviar_sms

    def envia_e_ecoa(numero, texto):
        saida = original(numero, texto)
        from command_center.db import conectar as c2
        outra = c2()
        sdr_canais.sms_evento(outra, sms(texto, direcao="outbound", sid=f"eco-{len(texto)}"), esperar=False)
        outra.close()
        return saida
    monkeypatch.setattr(sdr_canais, "enviar_sms", envia_e_ecoa)
    sdr_canais.sms_evento(con, sms("Oi"), esperar=False)
    row = um(con, "SELECT * FROM sdr_canal_contatos WHERE canal='sms'")
    assert not sdr_canais.pausado(row), row


def test_conversa_ja_passada_para_a_equipe_o_robo_fica_quieto(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_SMS", "1")
    con = ambiente["con"]
    ponte({"rota": "escalar", "motivo": "PEDIDO_HUMANO", "precisa_gente": True, "nota": "Pediu uma pessoa.",
           "mensagens": ["Já passei para a equipe."]})
    sdr_canais.sms_evento(con, sms("quero falar com uma pessoa"), esperar=False)
    r = sdr_canais.sms_evento(con, sms("alô?", sid="s-2"), esperar=False)
    assert "passou esta conversa" in r["robo"] and len(enviados("sms")) == 1


def test_card_do_kommo_com_a_equipe_o_robo_nao_responde(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_SMS", "1")
    con = ambiente["con"]
    inserir(con, "crm_leads", external_id="k-1", name="Ana", stage_name="ATENDIMENTO", contact_phone="+1 407 555 0199",
            tags="[]")
    con.commit()
    r = sdr_canais.sms_evento(con, sms("Oi"), esperar=False)
    assert "ATENDIMENTO" in r["robo"] and enviados("sms") == []


def test_card_do_kommo_na_entrada_e_do_robo(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_SMS", "1")
    con = ambiente["con"]
    inserir(con, "crm_leads", external_id="k-2", name="Ana", stage_name="ENTRADA", contact_phone="+1 407 555 0199",
            tags="[]")
    con.commit()
    assert sdr_canais.sms_evento(con, sms("Oi"), esperar=False)["robo"] == "respondeu"


def test_falha_no_envio_vira_atencao(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_SMS", "1")
    con = ambiente["con"]

    def recusa(numero, texto):
        raise RuntimeError("Dialpad recusou o SMS (403)")
    monkeypatch.setattr(sdr_canais, "enviar_sms", recusa)
    r = sdr_canais.sms_evento(con, sms("Oi"), esperar=False)
    assert r["robo"] == "falhou o envio"
    c = um(con, "SELECT * FROM sdr_canal_contatos WHERE canal='sms'")
    assert c["precisa_gente"] == 1 and "não conseguiu enviar" in c["precisa_motivo"]
    assert um(con, "SELECT COUNT(*) AS n FROM sdr_canal_mensagens WHERE por='robo'")["n"] == 0


def test_email_de_oportunidade_com_o_closer_fica_com_a_equipe(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_EMAIL", "1")
    con = ambiente["con"]
    inserir(con, "opportunities", name="Ana Souza", email="ana@example.com", stage="CONVERSA", source="site",
            closer_user_id=1)
    con.commit()
    caixa([thread()])
    r = sdr_canais.ler_email(con)
    assert "closer" in r["conversas"][0]["robo"] and enviados("email") == []


def test_ligar_o_canal_nao_responde_email_velho_de_uma_vez(ambiente, monkeypatch):
    con = ambiente["con"]
    caixa([thread()])
    monkeypatch.setenv("SDR_CANAL_EMAIL", "1")
    monkeypatch.setenv("SDR_CANAL_SO_PARA", "outra@example.com")
    sdr_canais.ler_email(con)                                  # visto, mas fora da lista
    con.execute("UPDATE sdr_canal_mensagens SET at='2026-01-01T00:00:00.000Z'")
    con.commit()
    monkeypatch.delenv("SDR_CANAL_SO_PARA")                   # liberou para todos
    sdr_canais.ler_email(con)
    assert enviados("email") == []
    n = um(con, "SELECT COUNT(*) AS n FROM audit_logs WHERE event='sdr.canal.email.sem_resposta'")["n"]
    assert n == 1, "uma auditoria por mensagem, não uma por passada"


def test_resumo_mostra_onde_esta_a_configuracao(ambiente):
    r = sdr_canais.resumo(ambiente["con"])
    assert r["configuracao"]["arquivo"] == "/nao/existe" and r["configuracao"]["existe"] is False


def test_numero_de_10_digitos_vira_com_1():
    assert sdr_canais.contato_de("sms", "(407) 555-0199") == "14075550199"
    assert sdr_canais.contato_de("sms", "+1 407 555 0199") == "14075550199"


# ------------------------------------------------------------------ formulário do site (dono, 20/10)
def _formulario(monkeypatch, mensagem="My son is 9, when can he start?"):
    monkeypatch.setenv("CC_SDR_FORMULARIO_SINCRONO", "1")
    monkeypatch.delenv("CC_SITE_HOSTS", raising=False)
    monkeypatch.delenv("CC_SITE_PREVIEW", raising=False)
    with TestClient(app, base_url="https://novo.urace.us") as cli:
        return cli.post("/ops/api/vitrine/contato", json={"nome": "Ana Lima", "email": "ana@exemplo.com",
                                                         "assunto": "academy", "mensagem": mensagem})


def test_formulario_do_site_o_robo_escreve_o_follow_up(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_EMAIL", "1")
    r = _formulario(monkeypatch)
    assert r.status_code == 200
    e = enviados("email")
    para_ana = [m for m in e if m["to"] == "ana@exemplo.com"]
    assert len(para_ana) == 1, e
    assert para_ana[0]["from"] == "support@urace.us" and "Oi! Aqui é o Chase" in para_ana[0]["text"]
    assert "We got your message" not in para_ana[0]["subject"], "a confirmação genérica não sai junto"
    assert any(m["to"] == "support@urace.us" for m in e), "a equipe continua avisada"
    con = conectar()
    assert um(con, "SELECT title FROM opp_events WHERE actor='sdr'")["title"].startswith("O robô respondeu")
    con.close()


def test_formulario_robo_falhou_sai_a_confirmacao_de_sempre(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_EMAIL", "1")

    def fora(*a, **k):
        raise RuntimeError("ponte fora do ar")
    monkeypatch.setattr(sdr_canais, "perguntar_ao_robo", fora)
    _formulario(monkeypatch)
    para_ana = [m for m in enviados("email") if m["to"] == "ana@exemplo.com"]
    assert len(para_ana) == 1 and "We got your message" in para_ana[0]["subject"]


def test_oportunidade_nova_do_site_e_lead_e_com_closer_e_da_equipe(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_EMAIL", "1")
    con = ambiente["con"]
    oid = inserir(con, "opportunities", name="Ana", email="ana@example.com", stage="NOVO", source="Site")
    con.commit()
    caixa([thread()])
    assert sdr_canais.ler_email(con)["conversas"][0]["robo"] == "respondeu"
    con.execute("UPDATE opportunities SET closer_user_id=1 WHERE id=?", (oid,))
    con.commit()
    caixa([thread(mid="m-5", corpo="And Sundays?")])
    assert "closer" in sdr_canais.ler_email(con)["conversas"][0]["robo"]


@pytest.mark.parametrize("texto", ["HELP", "help", "Info"])
def test_help_quem_responde_e_o_dialpad(ambiente, monkeypatch, texto):
    monkeypatch.setenv("SDR_CANAL_SMS", "1")
    r = sdr_canais.sms_evento(ambiente["con"], sms(texto), esperar=False)
    assert "HELP" in r["robo"] and enviados("sms") == []


def test_sim_depois_do_stop_nao_reativa(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_SMS", "1")
    con = ambiente["con"]
    sdr_canais.sms_evento(con, sms("STOP"), esperar=False)
    r = sdr_canais.sms_evento(con, sms("yes", sid="s-2"), esperar=False)
    assert "parar" in r["robo"] and enviados("sms") == []


def test_sms_sai_em_nome_do_escritorio(monkeypatch):
    """20/10: o SMS saiu pela linha pessoal; com o grupo, sai pelo número do escritório."""
    import urllib.request
    monkeypatch.delenv("CC_DIALPAD_FAKE", raising=False)
    monkeypatch.setenv("DIALPAD_ENV", "/nao/existe")
    monkeypatch.setenv("DIALPAD_API_KEY", "k")
    monkeypatch.setenv("DIALPAD_USER_ID", "4984574604558336")
    monkeypatch.setenv("DIALPAD_SMS_GRUPO", "office:6037417788784640")
    pedidos = []

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"id": "1"}'
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=0: pedidos.append(json.loads(req.data)) or Resp())
    sdr_canais.enviar_sms("+14075550199", "Oi")
    corpo = pedidos[0]
    assert corpo["sender_group_type"] == "office" and corpo["sender_group_id"] == "6037417788784640"
    assert corpo["user_id"] == "4984574604558336" and "from_number" not in corpo and corpo["to_numbers"] == ["+14075550199"]


# ------------------------------------------------------------------ ritmo: de hora em hora, no expediente (21/10)
def _orlando(dia, hora, minuto=0):
    from datetime import datetime
    return datetime(2026, 10, dia, hora, minuto, tzinfo=sdr_canais.FUSO)     # 19/10/2026 é segunda


def test_volta_so_no_expediente_e_uma_por_hora(monkeypatch):
    monkeypatch.setenv("SDR_CANAIS_ENV", "/nao/existe")
    for k in ("SDR_CANAL_LOTE_MIN", "SDR_CANAL_HORARIO", "SDR_CANAL_DIAS"):
        monkeypatch.delenv(k, raising=False)
    assert sdr_canais.lote_min() == 60 and sdr_canais.horario() == (8, 18)
    assert sdr_canais.vez_do_lote(_orlando(21, 7, 59)) is None                 # antes de abrir
    assert sdr_canais.vez_do_lote(_orlando(21, 8, 0)) == sdr_canais.vez_do_lote(_orlando(21, 8, 59))
    assert sdr_canais.vez_do_lote(_orlando(21, 9, 0)) != sdr_canais.vez_do_lote(_orlando(21, 8, 59))
    assert sdr_canais.vez_do_lote(_orlando(21, 17, 30)) is not None
    assert sdr_canais.vez_do_lote(_orlando(21, 18, 0)) is not None             # a volta do fechamento
    assert sdr_canais.vez_do_lote(_orlando(21, 18, 1)) is None                 # fechou
    assert sdr_canais.vez_do_lote(_orlando(25, 10)) is not None                # domingo: todos os dias por padrão
    monkeypatch.setenv("SDR_CANAL_DIAS", "1-5")
    assert sdr_canais.vez_do_lote(_orlando(25, 10)) is None and sdr_canais.vez_do_lote(_orlando(23, 10))
    monkeypatch.setenv("SDR_CANAL_HORARIO", "lixo")
    assert sdr_canais.horario() == (8, 18)
    monkeypatch.setenv("SDR_CANAL_LOTE_MIN", "0")
    assert sdr_canais.vez_do_lote(_orlando(21, 10)) is None


def test_com_lote_o_sms_espera_a_volta_e_sai_numa_resposta_so(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_SMS", "1")
    monkeypatch.setenv("SDR_CANAL_LOTE_MIN", "60")
    monkeypatch.setenv("SDR_CANAL_ESPERA_MIN", "0")
    monkeypatch.setattr(sdr_canais, "_intervalo", lambda t: 0)
    con = ambiente["con"]
    chamadas = []
    original = sdr_canais.perguntar_ao_robo
    monkeypatch.setattr(sdr_canais, "perguntar_ao_robo", lambda *a, **k: chamadas.append(a[2]) or original(*a, **k))
    assert "fila" in sdr_canais.sms_evento(con, sms("Oi", sid="f-1"))["robo"]
    sdr_canais.sms_evento(con, sms("quanto custa?", sid="f-2"))
    assert enviados("sms") == [] and chamadas == []                          # nada na hora
    r = sdr_canais.volta(con, esperar=False)
    assert r["sms"]["conversas"][0]["robo"] == "respondeu"
    assert chamadas == ["Oi\nquanto custa?"] and len(enviados("sms")) == 2
    assert sdr_canais.volta(con, esperar=False)["sms"]["conversas"] == []     # a volta seguinte não repete


def test_lote_deixa_para_a_volta_seguinte_quem_ainda_esta_escrevendo(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_SMS", "1")
    monkeypatch.setenv("SDR_CANAL_LOTE_MIN", "60")
    con = ambiente["con"]
    sdr_canais.sms_evento(con, sms("Oi"))
    assert sdr_canais.fila_sms(con) == []                                    # chegou agora (espera 10 min)
    con.execute("UPDATE sdr_canal_mensagens SET at='2020-01-01T00:00:00.000Z'")
    assert sdr_canais.fila_sms(con) == []                                    # velho demais (72 h)


def test_lote_nao_responde_help_nem_o_que_chegou_bloqueado(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_SMS", "1")
    monkeypatch.setenv("SDR_CANAL_LOTE_MIN", "60")
    monkeypatch.setenv("SDR_CANAL_ESPERA_MIN", "0")
    con = ambiente["con"]
    sdr_canais.sms_evento(con, sms("HELP"))
    monkeypatch.setenv("SDR_CANAL_SO_PARA", "(407) 555-0111")
    sdr_canais.sms_evento(con, sms("Oi", numero="+14075550122", sid="s-2"))   # fora da lista
    monkeypatch.delenv("SDR_CANAL_SO_PARA")                                  # abriu a lista depois
    assert sdr_canais.fila_sms(con) == [] and enviados("sms") == []


def test_lote_responde_o_email_na_volta(ambiente, monkeypatch):
    monkeypatch.setenv("SDR_CANAL_EMAIL", "1")
    monkeypatch.setenv("SDR_CANAL_LOTE_MIN", "60")
    caixa([thread()])
    r = sdr_canais.volta(ambiente["con"], esperar=False)
    assert r["email"]["conversas"][0]["robo"] == "respondeu" and len(enviados("email")) == 1
    assert "sms" not in r                                                    # SMS desligado: nem passa


def test_email_de_dias_atras_o_robo_nao_responde(ambiente, monkeypatch):
    """Lista de teste aberta para todo lead: e-mail de dias atrás que o robô nunca viu não ganha resposta do nada."""
    from email.utils import format_datetime
    from datetime import datetime, timedelta, timezone
    monkeypatch.setenv("SDR_CANAL_EMAIL", "1")
    velho = thread()
    velho["mensagens"][-1]["data"] = format_datetime(datetime.now(timezone.utc) - timedelta(days=3))
    novo = thread(tid="t-2", de="Bia <bia@example.com>", mid="m-2")
    novo["mensagens"][-1]["data"] = format_datetime(datetime.now(timezone.utc) - timedelta(hours=2))
    caixa([velho, novo])
    r = sdr_canais.ler_email(ambiente["con"])
    assert [c["robo"] for c in r["conversas"]] == ["e-mail velho demais", "respondeu"]
    assert [e["to"] for e in enviados("email")] == ["bia@example.com"]
    assert sdr_canais.ler_email(ambiente["con"])["conversas"] == []        # a volta seguinte não volta nele
    assert not sdr_canais.velho("lixo") and not sdr_canais.velho(None)
