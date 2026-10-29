"""#448 (dono, 29/10): "é possível também mover para aprovado com o nível de admin pra cima".

Sem a aprovação final escrita registrada, o pedido de Suits só vai para Approved pelo administrador, com o motivo
na linha do tempo e na auditoria. Operador e gerente continuam com a trava do #382; a IA não libera sozinha.
#482: o administrador também move para qualquer etapa à mão (aconteceu fora do Command Center)."""
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from command_center.api import auth, mcp_operar
from command_center.api.main import app
from command_center.db import aplicar_schema, conectar, um
from command_center.providers import suits

SENHA = "senha-forte-123"
B = "/ops/api/suits"


@pytest.fixture(scope="module")
def cli():
    os.environ["CC_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "cc-suits-admin.sqlite")
    con = conectar(); aplicar_schema(con)
    for email, papel in (("admin@urace.us", "ADMIN"), ("gerente@urace.us", "MANAGER"), ("op@urace.us", "OPERATOR")):
        auth.criar_usuario(con, email, papel.title() + " Fictício", papel, SENHA)
    con.close()
    with TestClient(app, base_url="https://cc.test") as c:
        yield c


def entra(cli, email):
    cli.cookies.clear()
    assert cli.post("/ops/api/auth/login", json={"email": email, "password": SENHA}).status_code == 200
    return {"X-CSRF": cli.cookies.get("cc_csrf")}


def _pedido(cli, h, nome):
    pid = cli.post(B, headers=h, json={"customer_name": nome}).json()["id"]
    assert cli.patch(f"{B}/{pid}", headers=h, json={"status": "design_pending"}).status_code == 200
    return pid


def test_operador_e_gerente_continuam_com_a_trava(cli):
    h = entra(cli, "op@urace.us")
    pid = _pedido(cli, h, "Cliente Fictício Trava")
    r = cli.patch(f"{B}/{pid}", headers=h, json={"status": "approved"})
    assert r.status_code == 400 and "aprovação final escrita" in r.json()["detail"]
    for email in ("op@urace.us", "gerente@urace.us"):
        h = entra(cli, email)
        assert cli.post(f"{B}/{pid}/aprovar-admin", headers=h, json={"motivo": "aprovou por WhatsApp"}).status_code == 403
    assert cli.get(f"{B}/{pid}").json()["status"] == "design_pending"


def test_admin_libera_para_approved_com_o_motivo_na_linha_do_tempo_e_na_auditoria(cli):
    h = entra(cli, "admin@urace.us")
    pid = _pedido(cli, h, "Cliente Fictício Liberado")
    assert cli.patch(f"{B}/{pid}", headers=h, json={"status": "approved"}).status_code == 400    # o caminho comum continua travado
    assert cli.post(f"{B}/{pid}/aprovar-admin", headers=h, json={"motivo": "  "}).status_code == 400   # sem motivo, não
    r = cli.post(f"{B}/{pid}/aprovar-admin", headers=h, json={"motivo": "cliente aprovou por WhatsApp"})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["status"] == "approved"
    etapa = [n for n in p["notas"] if n["kind"] == "etapa"][-1]
    assert "Approved" in etapa["text"] and "sem a aprovação final escrita" in etapa["text"] and "WhatsApp" in etapa["text"]
    assert etapa["autor"] == "Admin Fictício"
    con = conectar()
    a = um(con, "SELECT user_id, detail FROM audit_logs WHERE event='suit.approved.admin' AND entity_id=?", (str(pid),))
    con.close()
    assert a and '"sem_aprovacao_escrita": true' in a["detail"]
    # o pedido ao fornecedor continua pedindo a aprovação registrada
    r = cli.patch(f"{B}/{pid}", headers=h, json={"status": "sent_to_supplier"})
    assert r.status_code == 400 and "aprovação final escrita" in r.json()["detail"]
    assert cli.post(f"{B}/{pid}/aprovar-admin", headers=h, json={"motivo": "de novo, já está"}).status_code == 400


def test_admin_move_para_qualquer_etapa_a_mao(cli):
    """#482 (dono, 29/10): "libera essas travas ... já foi aprovado pelo cliente, fora de e-mail ... eu tenho que
    conseguir colocar na etapa de produção". O administrador pula a ordem e as travas, com o motivo."""
    h = entra(cli, "admin@urace.us")
    pid = _pedido(cli, h, "Cliente Fictício Producao")
    assert cli.patch(f"{B}/{pid}", headers=h, json={"status": "in_production"}).status_code == 400   # o caminho comum trava
    assert cli.post(f"{B}/{pid}/etapa-admin", headers=h, json={"etapa": "in_production", "motivo": "x"}).status_code == 400
    assert cli.post(f"{B}/{pid}/etapa-admin", headers=h, json={"etapa": "voando", "motivo": "aprovou pessoalmente"}).status_code == 400
    r = cli.post(f"{B}/{pid}/etapa-admin", headers=h, json={"etapa": "in_production", "motivo": "aprovou pessoalmente, já na produção"})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["status"] == "in_production"
    etapa = [n for n in p["notas"] if n["kind"] == "etapa"][-1]
    assert "In Production" in etapa["text"] and "movido à mão pelo administrador: aprovou pessoalmente" in etapa["text"]
    con = conectar()
    a = um(con, "SELECT detail FROM audit_logs WHERE event='suit.stage.admin' AND entity_id=?", (str(pid),))
    con.close()
    assert a and '"para": "in_production"' in a["detail"]
    # do cancelado e para trás também; e depois o caminho comum segue a tabela de transições
    assert cli.post(f"{B}/{pid}/etapa-admin", headers=h, json={"etapa": "in_transit", "motivo": "fornecedor despachou"}).status_code == 200
    assert cli.post(f"{B}/{pid}/etapa-admin", headers=h, json={"etapa": "in_transit", "motivo": "de novo, já está"}).status_code == 400
    for email in ("op@urace.us", "gerente@urace.us"):
        h2 = entra(cli, email)
        assert cli.post(f"{B}/{pid}/etapa-admin", headers=h2, json={"etapa": "delivered", "motivo": "entregue em mãos"}).status_code == 403


def test_a_ia_nao_libera_sozinha():
    assert mcp_operar.tipo_para_ia("POST", "/suits/1/aprovar-admin") == "aprovar"       # vira cartão de aprovar
    assert mcp_operar.tipo_para_ia("POST", "/suits/1/etapa-admin") == "aprovar"
    con = conectar()
    try:
        pid = con.execute("INSERT INTO suit_orders (title, status) VALUES ('Pedido Fictício IA', 'design_review')").lastrowid
        with pytest.raises(suits.Invalido, match="aprovação final escrita"):
            suits.mudar_etapa(con, pid, "approved", None, por_ia=True, liberado_pelo_admin=True)
    finally:
        con.rollback(); con.close()
