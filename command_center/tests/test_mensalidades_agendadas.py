"""Mensalidade agendada (#63): cada mês sai no dia 1 às 01:00 (hora da Flórida), uma vez só.

Dono, 01/10: *"sempre que colocar criar invoice recorrente, já crie todos os meses, a situação
é só enviado ou a enviar e a data que vai ser enviada... uma hora da manhã, naquele dia já
enviar essa invoice."*
"""
import os
from datetime import date, datetime

import pytest

os.environ["URACE_ENV"] = "/nao/existe"

from command_center.db import aplicar_schema, conectar, inserir, todos, um  # noqa: E402
from command_center.providers import mensalidades as ms  # noqa: E402


@pytest.fixture()
def con(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    c = conectar(); aplicar_schema(c)
    yield c
    c.close()


def _cliente(con):
    cid = inserir(con, "clients", name="Joseph Kartian", pilot_name="Enzo", email="joe.kartian@example.com",
                  status="ACTIVE", source="manual")
    inserir(con, "invoices", client_id=cid, doc_number="URACE-0010", amount=2756.9, balance=0, status="paid",
            issued_on="2026-09-17", customer_ref="485", memo="")
    return cid


def _agenda(con, cid, inicio=date(2026, 11, 1), meses=3):
    return ms.agendar(con, None, cid, None, inicio, meses, 2756.9, "7", "Academy Monthly — Enzo", "joe.kartian@example.com")


def fl(texto):
    return datetime.fromisoformat(texto).replace(tzinfo=ms.FUSO)


def test_memo_traz_o_mes_em_ingles():
    assert ms.memo_do_mes("2026-11") == "Urace Academy Training Program [November, 2026]"


def test_so_envia_quando_chega_1h_do_dia_1(con):
    cid = _cliente(con)
    _agenda(con, cid)
    enviados = []

    def enviar(**kw):
        enviados.append(kw)
        return {"aplicado": True, "id": "901", "numero": f"URACE-00{20 + len(enviados)}", "enviado": True}
    assert ms.enviar_devidas(con, fl("2026-11-01T00:59"), enviar) == [], "00:59 ainda não"
    feitas = ms.enviar_devidas(con, fl("2026-11-01T01:00"), enviar)
    assert [f[1] for f in feitas] == ["enviada"] and len(enviados) == 1
    kw = enviados[0]
    assert kw["cliente_id"] == "485" and kw["email"] == "joe.kartian@example.com" and kw["vence_em"] == "2026-11-01"
    assert kw["memo"] == "Urace Academy Training Program [November, 2026]"
    assert kw["linhas"] == [{"item_id": "7", "quantidade": 1, "unitario": 2756.9, "descricao": "Academy Monthly — Enzo"}]
    m = um(con, "SELECT * FROM monthly_invoices WHERE month='2026-11'")
    assert m["status"] == "enviada" and m["doc_number"] == "URACE-0021" and m["sent_at"]
    assert ms.enviar_devidas(con, fl("2026-11-20T09:00"), enviar) == [], "uma vez só por mês"
    assert um(con, "SELECT status FROM monthly_invoices WHERE month='2026-12'")["status"] == "a_enviar"
    assert any(a["event"] == "client.monthly.sent" for a in todos(con, "SELECT event FROM audit_logs"))


def test_falha_fica_registrada_e_tenta_ate_3_vezes(con):
    cid = _cliente(con)
    _agenda(con, cid, meses=1)
    tentativas = []

    def quebra(**kw):
        tentativas.append(1)
        raise RuntimeError("QuickBooks fora do ar")
    for _ in range(5):
        ms.enviar_devidas(con, fl("2026-11-01T02:00"), quebra)
    m = um(con, "SELECT * FROM monthly_invoices")
    assert len(tentativas) == 3 and m["status"] == "falhou" and m["attempts"] == 3
    assert "QuickBooks fora do ar" in m["error"]


def test_simulacao_nao_conta_como_enviada(con):
    cid = _cliente(con)
    _agenda(con, cid, meses=1)
    ms.enviar_devidas(con, fl("2026-11-01T02:00"), lambda **kw: {"aplicado": False})
    assert um(con, "SELECT status FROM monthly_invoices")["status"] == "falhou"


def test_invoice_que_chegou_no_espelho_nao_e_enviada_de_novo(con):
    """Se alguém já mandou a do mês pelo QuickBooks (memo ou item Academy), a linha só registra."""
    cid = _cliente(con)
    _agenda(con, cid, meses=2)
    iid = inserir(con, "invoices", client_id=cid, doc_number="URACE-0030", amount=2756.9, balance=2756.9, status="open",
                  issued_on="2026-11-01", customer_ref="485", memo=None)
    inserir(con, "invoice_lines", invoice_id=iid, line_no=1, item_name="Academy Monthly", description="", amount=2756.9)
    ms.enviar_devidas(con, fl("2026-12-01T01:00"), lambda **kw: {"aplicado": True, "id": "1", "numero": "URACE-0031"})
    st = {m["month"]: (m["status"], m["doc_number"], m["note"]) for m in ms.do_cliente(con, cid)}
    assert st["2026-11"] == ("enviada", "URACE-0030", "já existia no QuickBooks")
    assert st["2026-12"] == ("enviada", "URACE-0031", None)


def test_cancelada_nao_sai_e_libera_o_mes(con):
    cid = _cliente(con)
    ids = _agenda(con, cid, meses=1)
    ms.cancelar(con, None, ids[0], cid)
    assert ms.enviar_devidas(con, fl("2026-11-02T01:00"), lambda **kw: pytest.fail("enviou cancelada")) == []
    _agenda(con, cid, meses=1)                         # o mês cancelado pode ser agendado de novo
    with pytest.raises(ms.ErroMensalidade, match="duas vezes"):
        _agenda(con, cid, meses=1)


def test_sem_cliente_no_quickbooks_falha_sem_enviar(con):
    cid = inserir(con, "clients", name="Sem QBO", status="ACTIVE", source="manual")
    _agenda(con, cid, meses=1)
    ms.enviar_devidas(con, fl("2026-11-01T01:00"), lambda **kw: pytest.fail("enviou sem cliente"))
    assert "não encontrado no QuickBooks" in um(con, "SELECT error FROM monthly_invoices")["error"]


def test_invoice_da_sessao_extra_do_site_nao_e_a_mensalidade_do_mes(con):
    """Debug 29/10: a extra marcada no site (#314/#340) sai com o item "Academy | Extra session" no QuickBooks. No mês
    em que ela foi emitida, a mensalidade agendada achava que "já existia" (item com Academy) e o mês nascia "enviada"
    com o número da extra: a mensalidade daquele mês nunca era cobrada. A invoice de uma sessão do site nunca é a
    mensalidade (a mesma regra do contador do card, `contrato.mensalidades_por_mes`)."""
    cid = _cliente(con)
    conta = inserir(con, "portal_accounts", email="joe.kartian@example.com", pw_salt="x", pw_hash="x", name="Joseph Kartian",
                    birth_date="1980-01-01", terms_accepted_at="2026-09-30T00:00:00Z", client_id=cid)
    pil = inserir(con, "portal_pilots", account_id=conta, name="Enzo", client_id=cid)
    inserir(con, "bookings", account_id=conta, pilot_id=pil, date="2026-11-05", period="manha", status="confirmada",
            coverage="extra", charge_kind="invoice", price=689.23, qbo_invoice_id="5501", invoice_doc="URACE-0040")
    iid = inserir(con, "invoices", client_id=cid, doc_number="URACE-0040", amount=689.23, balance=689.23, status="open",
                  issued_on="2026-11-03", customer_ref="485", memo="URACE extra session: 11/05/2026 (morning).")
    inserir(con, "invoice_lines", invoice_id=iid, line_no=1, item_name="Academy | Extra session (beyond monthly 4)",
            description="Extra session (Academy 4 stroke) · 11/05/2026 (morning)", amount=689.23)
    con.execute("INSERT INTO entity_links (entity_type, entity_id, system, external_id) VALUES ('invoice', ?, 'quickbooks', '5501')",
                (iid,))
    assert ms.invoice_do_mes(con, cid, "2026-11") is None
    _agenda(con, cid, meses=1)                         # o gerente agenda no meio do mês, começando neste
    assert um(con, "SELECT status FROM monthly_invoices WHERE month='2026-11'")["status"] == "a_enviar"
    enviados = []

    def enviar(**kw):
        enviados.append(kw)
        return {"aplicado": True, "id": "9", "numero": "URACE-0041", "enviado": True}
    ms.enviar_devidas(con, fl("2026-11-10T09:00"), enviar)
    m = um(con, "SELECT * FROM monthly_invoices WHERE month='2026-11'")
    assert len(enviados) == 1 and (m["status"], m["doc_number"]) == ("enviada", "URACE-0041")


@pytest.mark.parametrize("erro", ["desligado", "fora do ar"])
def test_quickbooks_sem_resposta_ao_achar_o_cliente_nao_derruba_a_rodada(con, monkeypatch, erro):
    """Debug 29/10: o cliente do QuickBooks era procurado fora da proteção da rodada. Card sem invoice no espelho (o
    aluno novo) e o QuickBooks desligado ou com erro: `enviar_devidas` levantava, o mês ficava "a_enviar" sem motivo
    e o laço do autosync parava ali a cada 15 min (a cobrança da agenda, a loja, os avisos e o Asana não rodavam)."""
    from command_center import providers
    cid = inserir(con, "clients", name="Nova Aluna", pilot_name="Bia", email="nova.aluna@example.com", status="ACTIVE",
                  source="manual")
    _agenda(con, cid, meses=1)

    def chamar(sistema, ferramenta, **kw):
        if erro == "desligado":
            raise providers.NaoConectado("sem refresh token do QuickBooks")
        raise RuntimeError("sem conexão com o QuickBooks: timed out")
    monkeypatch.setattr(providers, "chamar", chamar)
    feitas = ms.enviar_devidas(con, fl("2026-11-01T01:00"), lambda **kw: pytest.fail("enviou sem o cliente do QuickBooks"))
    m = um(con, "SELECT * FROM monthly_invoices")
    assert feitas == [(m["id"], "falhou")] and (m["status"], m["attempts"]) == ("falhou", 1)
    assert "QuickBooks" in m["error"]
