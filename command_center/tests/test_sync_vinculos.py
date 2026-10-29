"""A sincronia não desfaz o vínculo de um registro com o card (debug 29/10).

Nada sai para fora aqui: as fontes são trocadas por respostas fixas, e nomes, e-mails e telefones são inventados.
"""
import os

import pytest

os.environ["URACE_ENV"] = "/nao/existe"

from command_center.db import aplicar_schema, conectar, inserir, um  # noqa: E402
from command_center.providers import sync  # noqa: E402


@pytest.fixture()
def con(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    c = conectar(); aplicar_schema(c)
    yield c
    c.close()


def _inbox(monkeypatch, threads):
    """A inbox do urace@ com estas conversas (thread → remetente da última mensagem)."""
    def chamar_falso(sistema, ferramenta, **a):
        if ferramenta == "gmail_marcadores":
            return []
        if ferramenta == "gmail_buscar":
            if a["conta"] != "urace":
                return {"threads": [], "proxima_pagina": None}
            return {"threads": [{"thread_id": t, "de": de, "assunto": "Treino de sábado", "mensagens": 2,
                                 "data": "Wed, 28 Oct 2026 10:00:00 -0400", "snippet": "ok", "marcadores": ["INBOX"]}
                                for t, de in threads.items()], "proxima_pagina": None}
        raise AssertionError(ferramenta)
    monkeypatch.setattr(sync, "chamar", chamar_falso)


def _card_do_email(con, thread):
    return um(con, """SELECT e.client_id FROM emails e JOIN entity_links l ON l.entity_type='email' AND l.entity_id=e.id
                      AND l.system='gmail' WHERE l.external_id=?""", (thread,))["client_id"]


def test_a_resposta_da_urace_nao_tira_a_conversa_do_card(con, monkeypatch):
    """A busca do Gmail dá o remetente da ÚLTIMA mensagem. Quando a URACE respondia e a conversa seguia na inbox, a
    sincronia procurava cliente pelo support@, não achava e gravava o vínculo vazio: a conversa sumia do card até o
    cliente escrever de novo."""
    bia = inserir(con, "clients", name="Bia Exemplo", email="bia@example.com", status="ACTIVE", source="manual")
    threads = {"t1": "Bia Exemplo <bia@example.com>"}
    _inbox(monkeypatch, threads)
    assert sync.sync_gmail(con)["ok"]
    assert _card_do_email(con, "t1") == bia
    threads["t1"] = "URACE <support@urace.us>"                     # a URACE respondeu; a conversa segue na inbox
    assert sync.sync_gmail(con)["ok"]
    assert _card_do_email(con, "t1") == bia


def test_a_conversa_que_a_varredura_ligou_ao_card_fica_nele(con, monkeypatch):
    """A varredura do card liga ao cliente a conversa em que ele aparece (de ou para). Se a última mensagem é de
    outro endereço, a sincronia seguinte não pode soltar."""
    bia = inserir(con, "clients", name="Bia Exemplo", email="bia@example.com", status="ACTIVE", source="manual")
    eid = inserir(con, "emails", client_id=bia, mailbox="urace", subject="Orçamento do kart", is_inbox=1, handled=0)
    inserir(con, "entity_links", entity_type="email", entity_id=eid, system="gmail", external_id="t2")
    _inbox(monkeypatch, {"t2": "Oficina Fictícia <oficina@example.com>"})
    assert sync.sync_gmail(con)["ok"]
    assert _card_do_email(con, "t2") == bia


def test_o_remetente_que_e_cliente_continua_ligando_a_conversa(con, monkeypatch):
    bia = inserir(con, "clients", name="Bia Exemplo", email="bia@example.com", status="ACTIVE", source="manual")
    _inbox(monkeypatch, {"t3": "Bia Exemplo <BIA@example.com>", "t4": "Desconhecido <x@example.com>"})
    assert sync.sync_gmail(con)["ok"]
    assert _card_do_email(con, "t3") == bia and _card_do_email(con, "t4") is None
