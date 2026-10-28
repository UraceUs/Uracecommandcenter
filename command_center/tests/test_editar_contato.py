"""#410 (dono, 28/10): o Editar do card muda nome, e-mail, telefone, piloto e nascimento —
validado, no formato da sincronia, sem pôr um cliente no card de outro, com o antes na auditoria,
e a sincronia não desfaz."""
import json
import os
import tempfile

import pytest

os.environ["URACE_ENV"] = "/nao/existe"

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api import auth  # noqa: E402
from command_center.api.main import app  # noqa: E402
from command_center.db import aplicar_schema, conectar, inserir, um  # noqa: E402
from command_center.providers import identidade  # noqa: E402
from command_center.providers.sync import _upsert_cliente  # noqa: E402

B = "/ops/api"
SENHA = "senha-forte-123"
IDS = {}


@pytest.fixture(scope="module")
def cli():
    os.environ["CC_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "cc.sqlite")
    con = conectar(); aplicar_schema(con)
    auth.criar_usuario(con, "admin@urace.us", "Admin", "ADMIN", SENHA)
    auth.criar_usuario(con, "viewer@urace.us", "Viewer", "VIEWER", SENHA)
    IDS["ana"] = inserir(con, "clients", name="Ana Testarossa", email="ana.errado@example.com", phone="555-0101",
                         pilot_name="Lia Testarossa", pilot_dob="2014-03-02", status="ACTIVE", source="asana")
    IDS["bia"] = inserir(con, "clients", name="Bia Kartella", email="bia.kartella@example.com", status="ACTIVE", source="asana")
    con.commit(); con.close()
    with TestClient(app, base_url="https://cc.test") as c:
        yield c


def entra(cli, email):
    cli.cookies.clear()
    assert cli.post(B + "/auth/login", json={"email": email, "password": SENHA}).status_code == 200
    return {"X-CSRF": cli.cookies.get("cc_csrf")}


def test_editar_muda_nome_email_telefone_piloto_e_nascimento(cli):
    h = entra(cli, "admin@urace.us")
    r = cli.patch(B + f"/clients/{IDS['ana']}", headers=h, json={
        "name": "  Ana Testarossa Silva ", "email": "mailto:Ana.Certo@Example.com", "email_alt": "",
        "phone": "(555) 555-0102", "pilot_name": "Lia T. Silva", "pilot_dob": "2014-03-12", "company": "Kart Fictício LLC"})
    assert r.status_code == 200, r.text
    c = cli.get(B + f"/clients/{IDS['ana']}").json()["client"]
    assert c["name"] == "Ana Testarossa Silva"
    assert c["email"] == "ana.certo@example.com"              # mesmo formato da sincronia
    assert c["phone"] == "555-555-0102"
    assert c["pilot_name"] == "Lia T. Silva" and c["pilot_dob"] == "2014-03-12"
    assert c["company"] == "Kart Fictício LLC"
    con = conectar()
    a = um(con, "SELECT detail FROM audit_logs WHERE event='client.update' AND entity_id=? ORDER BY id DESC LIMIT 1", (str(IDS["ana"]),))
    detalhe = json.loads(a["detail"])
    assert detalhe["email"] == "ana.certo@example.com" and detalhe["antes"]["email"] == "ana.errado@example.com"
    # a sincronia do Asana relê a descrição antiga: só preenche vazio, não desfaz a correção
    _upsert_cliente(con, "Ana Testarossa", "ana.certo@example.com", "555-0101", "Lia Testarossa", "2014-03-02")
    con.commit()
    c = um(con, "SELECT * FROM clients WHERE id=?", (IDS["ana"],))
    assert (c["name"], c["phone"], c["pilot_name"], c["pilot_dob"]) == ("Ana Testarossa Silva", "555-555-0102", "Lia T. Silva", "2014-03-12")
    con.close()


def test_apagar_campo_opcional_e_nao_apagar_o_responsavel(cli):
    h = entra(cli, "admin@urace.us")
    assert cli.patch(B + f"/clients/{IDS['ana']}", headers=h, json={"company": "", "pilot_name": ""}).status_code == 200
    c = cli.get(B + f"/clients/{IDS['ana']}").json()["client"]
    assert c["company"] is None and c["pilot_name"] is None
    assert cli.patch(B + f"/clients/{IDS['ana']}", headers=h, json={"name": " "}).status_code == 400


@pytest.mark.parametrize("campo,valor", [("email", "sem-arroba"), ("phone", "abc"), ("pilot_dob", "12/03/2014"), ("pilot_dob", "2999-01-01")])
def test_dado_invalido_e_recusado(cli, campo, valor):
    h = entra(cli, "admin@urace.us")
    r = cli.patch(B + f"/clients/{IDS['bia']}", headers=h, json={campo: valor})
    assert r.status_code == 400, (campo, valor, r.text)


def test_email_de_outro_card_e_recusado_mas_o_do_irmao_nao(cli):
    h = entra(cli, "admin@urace.us")
    r = cli.patch(B + f"/clients/{IDS['bia']}", headers=h, json={"email": "ana.certo@example.com"})
    assert r.status_code == 409 and str(IDS["ana"]) in r.json()["detail"]      # nunca no card de outro
    assert cli.get(B + f"/clients/{IDS['bia']}").json()["client"]["email"] == "bia.kartella@example.com"
    con = conectar()
    irmao, _ = identidade.criar_irmao(con, IDS["ana"], "Teo Testarossa")
    con.commit(); con.close()
    # o card do irmão tem o mesmo responsável: o mesmo e-mail é dele também
    assert cli.patch(B + f"/clients/{irmao}", headers=h, json={"email": "ana.certo@example.com", "pilot_dob": "2016-05-05"}).status_code == 200


def test_viewer_nao_edita(cli):
    h = entra(cli, "viewer@urace.us")
    assert cli.patch(B + f"/clients/{IDS['bia']}", headers=h, json={"name": "Outra Pessoa"}).status_code == 403


def test_card_antigo_com_email_repetido_continua_salvando_o_resto(cli):
    """Duplicata que já existia (a decidir em Unir) não trava o Editar quando o e-mail não muda."""
    con = conectar()
    dup = inserir(con, "clients", name="Bia Kartella", email="bia.kartella@example.com", status="ACTIVE", source="qbo")
    con.commit(); con.close()
    h = entra(cli, "admin@urace.us")
    r = cli.patch(B + f"/clients/{dup}", headers=h, json={"email": "bia.kartella@example.com", "phone": "555-555-0109", "status": "ACTIVE"})
    assert r.status_code == 200, r.text
