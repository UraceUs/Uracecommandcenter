"""Debug de 29/10 — a mensagem do grupo do ateliê que a IA não conseguiu tratar não some.

A mensagem do fornecedor ou do designer no WhatsApp vai para a IA a cada ciclo. Ela era marcada como tratada antes de a
IA rodar; quando a IA falhava, ficava "a IA está tratando" na linha do tempo e ninguém era chamado. A ponte de e-mail
já faz o certo (#382): falhou, volta no ciclo seguinte; depois de 3 tentativas, vai para a equipe. Só dados fictícios."""
import json

import pytest

from command_center.db import aplicar_schema, conectar, um
from command_center.providers import atelie_whatsapp as wa
from command_center.providers import suits_ponte as sp

USMAN = "120363000000000002@g.us"


@pytest.fixture()
def con(tmp_path, monkeypatch):
    (tmp_path / "urace").mkdir()
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "atelie-falha.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path / "urace"))
    monkeypatch.setenv("CC_WA_FAKE", str(tmp_path / "wa.jsonl"))
    monkeypatch.delenv("CC_WA_GRUPOS_ENV", raising=False)
    (tmp_path / "urace" / "whatsapp-grupos.env").write_text(
        f"WA_GRUPOS_APLICAR=0\nWA_GRUPOS=fornecedor\nWA_GRUPO_FORNECEDOR_NOME=Fornecedor Ficticio\nWA_GRUPO_FORNECEDOR_JID={USMAN}\n")
    c = conectar(); aplicar_schema(c)
    c.execute("INSERT INTO users (email, name, role, pw_salt, pw_hash) VALUES ('a@urace.us','Admin','ADMIN','x','x')")
    yield c
    c.close()


def _pedido(con):
    return con.execute("INSERT INTO suit_orders (title, customer_name, driver_name, status, design) VALUES "
                       "('Bruno Ficticio', 'Bruno Ficticio', 'Leo Ficticio', 'in_production', ?)",
                       (json.dumps({"nome": "Leo Ficticio"}),)).lastrowid


def _falha(con, cid, texto, sk, uid, pr):
    """O que `ia._executa` faz quando o agente não responde: não levanta, grava o comando como FAILED."""
    con.execute("UPDATE ai_commands SET status='FAILED', error='o agente não respondeu' WHERE id=?", (cid,))


def _estado(con, mid):
    return um(con, "SELECT estado FROM atelie_wa_mensagens WHERE id=?", (mid,))["estado"]


def _humano(con, pid):
    return um(con, "SELECT summary FROM ai_events WHERE kind='suit.humano' AND entity_id=? AND status='NEW'", (pid,))


@pytest.mark.parametrize("executar", [_falha, lambda *a: (_ for _ in ()).throw(RuntimeError("motor fora do ar"))])
def test_ia_que_falha_tenta_de_novo_e_depois_chama_a_equipe(con, executar):
    pid = _pedido(con)
    mid = wa.receber(con, {"grupo_jid": USMAN, "message_id": "f1", "remetente_nome": "Fornecedor Ficticio",
                           "texto": f"Suits #{pid}: the zipper is out of stock, can we use velcro?"})["id"]
    for _ in range(sp.LIMITE_TENTATIVAS - 1):
        feitos = wa.tratar_pendentes(con, executar)
        assert feitos and feitos[0].get("erro")
        assert _estado(con, mid) == "nova", "falhou: volta no ciclo seguinte"
        assert _humano(con, pid) is None
    wa.tratar_pendentes(con, executar)
    assert _estado(con, mid) == "tratada"
    assert _humano(con, pid) and "não conseguiu" in _humano(con, pid)["summary"]
    assert wa.tratar_pendentes(con, executar) == [], "depois de chamar a equipe, a mensagem não volta mais"


def test_ia_que_trata_continua_marcando_uma_vez(con):
    pid = _pedido(con)
    mid = wa.receber(con, {"grupo_jid": USMAN, "message_id": "f2", "texto": f"Suits #{pid} shipped today"})["id"]
    chamadas = []
    assert wa.tratar_pendentes(con, lambda *a: chamadas.append(a))[0].get("comando")
    assert _estado(con, mid) == "tratada" and len(chamadas) == 1 and _humano(con, pid) is None
