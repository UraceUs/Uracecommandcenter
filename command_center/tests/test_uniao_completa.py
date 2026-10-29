"""Unir dois cards leva TUDO do card que sai, ou não muda nada (debug 29/10).

A união repassava só as tabelas de uma lista feita à mão em 10/09. As que nasceram depois (ligação do Dialpad,
mensalidade, balcão, estoque, pedidos e agendamentos do site, Suits, Biblioteca, pendências da IA…) ficavam
apontando para o card que sai, e o DELETE dele batia na chave estrangeira DEPOIS de a união já ter movido tarefas,
waivers e e-mails e gravado o registro: card pela metade, erro no botão Unir, e a união automática da sincronia do
Asana quebrando a rodada inteira. Nomes, e-mails e telefones aqui são inventados.
"""
import os
import sqlite3

import pytest

os.environ["URACE_ENV"] = "/nao/existe"

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api import auth, main  # noqa: E402
from command_center.db import aplicar_schema, conectar, inserir, todos, um  # noqa: E402
from command_center.providers import identidade  # noqa: E402

SENHA = "senha-forte-123"


@pytest.fixture()
def con(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path))
    c = conectar(); aplicar_schema(c)
    auth.criar_usuario(c, "adm@urace.us", "Admin", "ADMIN", SENHA)
    yield c
    c.close()


@pytest.fixture()
def cli(con):
    with TestClient(main.app, base_url="https://cc.test") as t:
        assert t.post("/ops/api/auth/login", json={"email": "adm@urace.us", "password": SENHA}).status_code == 200
        t.headers["X-CSRF"] = t.cookies.get("cc_csrf")
        yield t


def _dois_cards(con):
    fica = inserir(con, "clients", name="Lia Fictícia", email="lia@example.com", phone="407-555-0101",
                   status="ACTIVE", source="asana")
    sai = inserir(con, "clients", name="Lia Fictícia", email="lia.f@example.com", status="ACTIVE", source="manual")
    tarefa = inserir(con, "tasks", client_id=sai, title="Lia Fictícia_Practice", project="U-RACE", status="open",
                     due_on="2026-11-02")
    return fica, sai, tarefa


def _o_que_so_o_card_que_sai_tem(con, sai):
    """Uma linha do card que sai em tabelas que nasceram depois da lista de 10/09."""
    return {
        "calls": inserir(con, "calls", client_id=sai, direction="entrada", external_number="+14075550102"),
        "monthly_recurring": inserir(con, "monthly_recurring", client_id=sai, amount=1, item_id="1", months=1,
                                     start_on="2026-11-01", end_on="2026-11-01"),
        "library_docs": inserir(con, "library_docs", client_id=sai, kind="contrato", ref="teste-1", title="Contrato de teste"),
        "ai_pendencias": inserir(con, "ai_pendencias", client_id=sai, titulo="Tarefa de teste", faltando='["horário"]'),
    }


def test_unir_leva_tudo_do_card_que_sai(con):
    fica, sai, tarefa = _dois_cards(con)
    linhas = _o_que_so_o_card_que_sai_tem(con, sai)
    assert identidade.unir(con, fica, sai, "user:1", "mesma pessoa") is True
    assert um(con, "SELECT id FROM clients WHERE id=?", (sai,)) is None
    assert um(con, "SELECT client_id FROM tasks WHERE id=?", (tarefa,))["client_id"] == fica
    for tabela, lid in linhas.items():
        assert um(con, f"SELECT client_id FROM {tabela} WHERE id=?", (lid,))["client_id"] == fica, tabela


def test_toda_tabela_que_aponta_para_o_card_vai_junto(con):
    """A lista não fica mais para trás: o que tem client_id apontando para clients é levado, inclusive tabela nova."""
    fica, sai, _ = _dois_cards(con)
    con.execute("CREATE TABLE coisa_nova (id INTEGER PRIMARY KEY, client_id INTEGER REFERENCES clients(id))")
    nova = inserir(con, "coisa_nova", client_id=sai)
    assert identidade.unir(con, fica, sai, "user:1", "mesma pessoa") is True
    assert um(con, "SELECT client_id FROM coisa_nova WHERE id=?", (nova,))["client_id"] == fica


def test_uniao_que_falha_no_meio_nao_fica_pela_metade(con):
    fica, sai, tarefa = _dois_cards(con)
    con.execute("CREATE TEMP TRIGGER falha_de_teste BEFORE DELETE ON clients BEGIN SELECT RAISE(ABORT, 'falha de teste'); END")
    with pytest.raises(sqlite3.IntegrityError, match="falha de teste"):
        identidade.unir(con, fica, sai, "user:1", "mesma pessoa")
    assert um(con, "SELECT id FROM clients WHERE id=?", (sai,)), "o card que sai continua"
    assert um(con, "SELECT client_id FROM tasks WHERE id=?", (tarefa,))["client_id"] == sai, "nada se moveu"
    assert not todos(con, "SELECT id FROM client_merges"), "nenhuma união registrada"
    assert not con.in_transaction


def test_o_botao_unir_leva_a_ligacao_e_a_mensalidade(cli, con):
    fica, sai, tarefa = _dois_cards(con)
    linhas = _o_que_so_o_card_que_sai_tem(con, sai)
    r = cli.post("/ops/api/client-merge", json={"keep_id": fica, "drop_id": sai, "reason": "mesma pessoa"})
    assert r.status_code == 200, r.text
    assert um(con, "SELECT id FROM clients WHERE id=?", (sai,)) is None
    assert um(con, "SELECT client_id FROM calls WHERE id=?", (linhas["calls"],))["client_id"] == fica


def test_os_dois_com_rascunho_aberto_no_balcao_nao_se_unem_e_nada_muda(cli, con):
    """Rascunho aberto é um por card: unir sem alguém fechar um deles não cabe. Diz o porquê e não mexe em nada."""
    fica, sai, tarefa = _dois_cards(con)
    inserir(con, "counter_drafts", client_id=fica)
    inserir(con, "counter_drafts", client_id=sai)
    r = cli.post("/ops/api/client-merge", json={"keep_id": fica, "drop_id": sai, "reason": "mesma pessoa"})
    assert r.status_code == 409 and "rascunho" in r.json()["detail"], r.text
    assert um(con, "SELECT id FROM clients WHERE id=?", (sai,)) and \
        um(con, "SELECT client_id FROM tasks WHERE id=?", (tarefa,))["client_id"] == sai
    assert not todos(con, "SELECT id FROM client_merges")


def test_a_uniao_automatica_da_sincronia_nao_quebra_a_rodada(con):
    """`deduplicar` roda dentro da sincronia do Asana: o par que não cabe fica para uma pessoa, e o resto segue."""
    a = inserir(con, "clients", name="Rui Exemplo", email="rui@example.com", status="ACTIVE", source="asana")
    b = inserir(con, "clients", name="Rui E.", email="rui@example.com", status="ACTIVE", source="manual")
    inserir(con, "calls", client_id=b, direction="saida", external_number="+14075550103")
    c = inserir(con, "clients", name="Ana Modelo", email="ana@example.com", status="ACTIVE", source="asana")
    d = inserir(con, "clients", name="Ana M.", email="ana@example.com", status="ACTIVE", source="manual")
    inserir(con, "counter_drafts", client_id=c)
    inserir(con, "counter_drafts", client_id=d)
    assert identidade.deduplicar(con) == 1
    assert um(con, "SELECT id FROM clients WHERE id=?", (b,)) is None, "o par que cabe se une"
    assert um(con, "SELECT client_id FROM calls")["client_id"] == a, "com a ligação"
    assert um(con, "SELECT id FROM clients WHERE id=?", (d,)), "o que não cabe fica para decisão humana"
