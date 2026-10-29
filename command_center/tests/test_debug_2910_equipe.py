"""Debug 29/10: chat da equipe no servidor. Abrir uma conversa longa traz as mensagens mais novas (não as 300 mais
velhas)."""
import os
import tempfile

import pytest

os.environ["URACE_ENV"] = "/nao/existe"

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api import auth, equipe  # noqa: E402
from command_center.api.main import app  # noqa: E402
from command_center.db import aplicar_schema, conectar, um  # noqa: E402

B = "/ops/api"
SENHA = "senha-forte-123"


@pytest.fixture()
def cli():
    os.environ["CC_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "cc.sqlite")
    con = conectar(); aplicar_schema(con)
    auth.criar_usuario(con, "chefe@urace.us", "Chefe", "ADMIN", SENHA)
    auth.criar_usuario(con, "mec@urace.us", "Mecânico", "OPERATOR", SENHA)
    con.commit(); con.close()
    with TestClient(app, base_url="https://cc.test") as c:
        yield c


def entra(cli, email):
    cli.cookies.clear()
    assert cli.post(f"{B}/auth/login", json={"email": email, "password": SENHA}).status_code == 200
    return {"X-CSRF": cli.cookies.get("cc_csrf")}


def test_abrir_conversa_longa_traz_as_mensagens_mais_novas(cli):
    h = entra(cli, "chefe@urace.us")
    cid = cli.post(f"{B}/equipe/canais", headers=h, json={"name": "Pista"}).json()["id"]
    con = conectar()
    try:
        for i in range(1, 321):
            equipe.guardar_mensagem(con, cid, f"mensagem {i}", "Mecânico", origem="painel")
        con.commit()
        ultimo = um(con, "SELECT MAX(id) AS m FROM team_messages WHERE channel_id=?", (cid,))["m"]
    finally:
        con.close()
    d = cli.get(f"{B}/equipe/canais/{cid}?desde=0", headers=h).json()
    ids = [m["id"] for m in d["mensagens"]]
    assert len(ids) == 300 and ids == sorted(ids) and ids[-1] == ultimo         # as 300 mais novas, em ordem
    assert d["mensagens"][-1]["text"] == "mensagem 320"
    # quem já viu até aqui pede só o que é novo: nada
    assert cli.get(f"{B}/equipe/canais/{cid}?desde={ultimo}", headers=h).json()["mensagens"] == []


def test_csrf_com_acento_no_painel_e_recusado_com_403_e_nao_com_erro_500(cli):
    """Debug 29/10: o mesmo da área do cliente, no painel da equipe — o cabeçalho de segurança com acento dava 500."""
    entra(cli, "chefe@urace.us")
    r = cli.post(f"{B}/equipe/canais", headers={"X-CSRF": "é".encode("utf-8")}, json={"name": "Pista"})
    assert r.status_code == 403
