"""Debug 29/10 — estoque, compras e corridas: defeitos achados na revisão, cada um com o teste que o prova."""
import os
import sqlite3
import tempfile
from datetime import date, datetime, timedelta

import pytest

os.environ["URACE_ENV"] = "/nao/existe"

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api import auth  # noqa: E402
from command_center.api.main import app  # noqa: E402
from command_center.db import aplicar_schema, conectar, inserir, um  # noqa: E402
from command_center.providers import compras, estoque, portal, sync  # noqa: E402

SENHA = "senha-forte-123"


@pytest.fixture()
def con(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    c = conectar(); aplicar_schema(c)
    yield c
    c.close()


@pytest.fixture(scope="module")
def cli():
    pasta = tempfile.mkdtemp()
    os.environ["CC_DB_PATH"] = os.path.join(pasta, "cc.sqlite")
    os.environ["URACE_DIR"] = pasta
    c = conectar(); aplicar_schema(c)
    auth.criar_usuario(c, "mec@urace.us", "Mecânico", "OPERATOR", SENHA)
    auth.criar_usuario(c, "ger@urace.us", "Gerente", "MANAGER", SENHA)
    inserir(c, "clients", name="Enzo Kartian", status="ACTIVE", source="manual")
    c.close()
    with TestClient(app, base_url="https://cc.test") as t:
        yield t


def entra(cli, email):
    cli.cookies.clear()
    assert cli.post("/ops/api/auth/login", json={"email": email, "password": SENHA}).status_code == 200
    return {"X-CSRF": cli.cookies.get("cc_csrf")}


def test_unidade_do_proprio_cliente_usada_no_kart_dele_nao_vira_cobranca(cli):
    """Chassi com número de série que JÁ É do cliente: usar no kart dele não se cobra (é dele). A rota só olhava o
    `client_id` do pedido e, em ficha individual, o dono vem da unidade — o cliente era cobrado pela própria peça."""
    h = entra(cli, "ger@urace.us")
    enzo = um(conectar(), "SELECT id FROM clients WHERE name='Enzo Kartian'")["id"]
    iid = cli.post("/ops/api/estoque/item", headers=h, data={"name": "Chassi Tonykart", "kind": "chassi", "price": "300"}).json()["id"]
    con = conectar()
    uid = estoque.entrada(con, iid, serial="CHASSI-555-0101", client_id=enzo)["unit_id"]
    con.commit(); con.close()
    r = cli.post("/ops/api/estoque/saida", headers=h, json={"item_id": iid, "unit_id": uid, "para_cliente_id": enzo})
    assert r.status_code == 200, r.text
    assert "cobranca_id" not in r.json()
    assert um(conectar(), "SELECT COUNT(*) n FROM stock_charges")["n"] == 0


def test_mecanico_nao_ve_o_valor_dos_avisos_da_loja(cli):
    """Custo é do gerente: o valor que o e-mail da loja trouxe (`amount` nos eventos) também."""
    con = conectar()
    pid = compras.criar_compra(con, None, [{"description": "Corrente", "qty": 1}], pedir=True)
    inserir(con, "purchase_events", purchase_id=pid, kind="pagamento", amount=1234.5, subject="Payment received")
    con.commit(); con.close()
    h = entra(cli, "mec@urace.us")
    c = cli.get(f"/ops/api/compras/{pid}", headers=h).json()
    assert c["eventos"] and all(e["amount"] is None for e in c["eventos"])
    lista = next(x for x in cli.get("/ops/api/compras", headers=h).json()["compras"] if x["id"] == pid)
    assert all(e["amount"] is None for e in lista["eventos"])
    h = entra(cli, "ger@urace.us")
    assert cli.get(f"/ops/api/compras/{pid}", headers=h).json()["eventos"][0]["amount"] == 1234.5


def test_compra_atrasada_usa_o_dia_da_florida(con, monkeypatch):
    """Previsão de hoje (na Flórida) não é atraso, mesmo que o relógio do servidor (UTC) já esteja no dia seguinte."""
    hoje = date.today()
    monkeypatch.setattr(portal, "hoje", lambda: hoje - timedelta(days=1))
    pid = compras.criar_compra(con, None, [{"description": "Pneus", "qty": 4}], pedir=True,
                               expected_at=(hoje - timedelta(days=1)).isoformat())
    assert not compras.compra(con, pid)["atrasada"]
    monkeypatch.setattr(portal, "hoje", lambda: hoje)
    assert compras.compra(con, pid)["atrasada"]


def test_corrida_de_hoje_na_florida_segue_no_calendario(con, monkeypatch):
    """Tarefa de corrida concluída no Asana com data de hoje (Flórida) continua no calendário até o fim do dia."""
    ontem_utc = date.today() - timedelta(days=1)
    monkeypatch.setattr(portal, "hoje", lambda: ontem_utc)
    tid = inserir(con, "tasks", title="ROK Cup Rodada 3", project="U-RACE", section="RACES", status="completed",
                  due_on=ontem_utc.isoformat())
    sync.sincronizar_corridas(con)
    assert um(con, "SELECT active FROM races WHERE task_id=?", (tid,))["active"] == 1


def _intruso_tenta_gravar(monkeypatch, iid):
    """Entre a leitura do saldo e a gravação do novo, outra requisição tenta gravar: devolve o que aconteceu com ela."""
    visto = {}
    real = estoque._linha_saldo

    def espiada(*a, **k):
        r = real(*a, **k)
        if "bloqueado" not in visto:
            c2 = conectar()
            c2.execute("PRAGMA busy_timeout = 0")
            try:
                c2.execute("UPDATE stock_levels SET qty = qty + 1 WHERE item_id=?", (iid,))
                visto["bloqueado"] = False
            except sqlite3.OperationalError:
                visto["bloqueado"] = True
            finally:
                c2.close()
        return r
    monkeypatch.setattr(estoque, "_linha_saldo", espiada)
    return visto


@pytest.mark.parametrize("rota,corpo", [("entrada", {"qty": 1}), ("saida", {"qty": 1}), ("transferir", {"qty": 1, "para": "trailer"}),
                                        ("contar", {"qty": 3}), ("ajustar", {"qty": 1, "motivo": "teste"})])
def test_lancamento_de_estoque_trava_a_escrita_desde_a_leitura_do_saldo(cli, monkeypatch, rota, corpo):
    """Dois mecânicos lançando a mesma peça juntos: sem a trava, os dois liam 5 e gravavam 4 e 6 — o saldo perdia um
    lançamento e o razão deixava de bater. A rota tem de segurar a escrita desde a leitura (como o Balcão já faz)."""
    h = entra(cli, "ger@urace.us")
    iid = cli.post("/ops/api/estoque/item", headers=h, data={"name": f"Corrente {rota}", "category": "hardware", "qty": "5"}).json()["id"]
    visto = _intruso_tenta_gravar(monkeypatch, iid)
    r = cli.post(f"/ops/api/estoque/{rota}", headers=h, json={"item_id": iid, **corpo})
    assert r.status_code == 200, r.text
    assert visto.get("bloqueado") is True, "outra requisição conseguiu gravar no meio do lançamento"
