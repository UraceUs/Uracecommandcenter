"""Debug 29/10 — estoque, compras e corridas: defeitos achados na revisão, cada um com o teste que o prova."""
import os
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


