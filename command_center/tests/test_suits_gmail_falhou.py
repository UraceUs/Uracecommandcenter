"""Debug de 29/10 — o Gmail que falha no clique da equipe vira um aviso claro, não "Internal Server Error".

"Enviar ao designer" e os rascunhos no Gmail (endereço e pedido ao fornecedor) chamam o Gmail na hora do clique. Com
o Gmail recusando ou fora do ar, a rota estourava em 500; agora devolve 502 com o motivo, e nada fica marcado como
enviado (o clique de novo confere no Gmail antes de mandar). Nada sai da máquina; só dados fictícios."""
import pytest
from fastapi.testclient import TestClient

import command_center.providers as prov
from command_center.api import auth
from command_center.api.main import app
from command_center.db import aplicar_schema, conectar, um
from command_center.providers import suits_ponte as sp

SENHA = "senha-forte-123"


class GmailFora:
    """O Gmail recusando: o que a API devolve quando cai (ou o token não serve mais para enviar)."""

    def enviar_sistema(self, *a, **k):
        raise RuntimeError("Gmail API 500: backendError")

    def mensagens_da_thread(self, *a, **k):
        raise RuntimeError("Gmail API 500: backendError")

    def gmail_buscar(self, *a, **k):
        raise RuntimeError("Gmail API 500: backendError")


@pytest.fixture()
def cli(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "gmail-falhou.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path / "urace"))
    monkeypatch.delenv("CC_EMAIL_FAKE", raising=False)
    monkeypatch.setattr(prov, "modulo", lambda s: GmailFora())

    def chamar(sistema, ferramenta, **args):
        raise RuntimeError("Gmail API 500: backendError")
    monkeypatch.setattr(prov, "chamar", chamar)
    c = conectar(); aplicar_schema(c)
    auth.criar_usuario(c, "op@urace.us", "Operador Fictício", "OPERATOR", SENHA)
    sp.salvar_config(c, {"designer_email": "designer@example.com"})
    c.execute("INSERT INTO suit_suppliers (name, email, is_current) VALUES ('Fornecedor Ficticio', 'fornecedor@example.com', 1)")
    pid = c.execute("""INSERT INTO suit_orders (title, customer_name, customer_phone, ship_address, status, checked_at)
                       VALUES ('Bruno Ficticio', 'Bruno Ficticio', '(407) 555-0142', '742 Evergreen Terrace\nOrlando, FL 32801',
                               'checked', '2026-10-29T14:00:00.000Z')""").lastrowid
    p = dict(um(c, "SELECT * FROM suit_orders WHERE id=?", (pid,)))
    item = sp.preparar_designer(c, p, f"Suits #{pid} - briefing", "Black and red, number 7.", [])["item"]
    c.close()
    with TestClient(app, base_url="https://cc.test", raise_server_exceptions=False) as t:
        assert t.post("/ops/api/auth/login", json={"email": "op@urace.us", "password": SENHA}).status_code == 200
        t.h = {"X-CSRF": t.cookies.get("cc_csrf")}
        t.pid, t.item = pid, item
        yield t


def test_enviar_ao_designer_com_o_gmail_fora_avisa_e_nao_marca_enviado(cli):
    r = cli.post(f"/ops/api/suits/{cli.pid}/preparados/{cli.item}/enviar", headers=cli.h)
    assert r.status_code == 502 and "Gmail" in r.json()["detail"]
    con = conectar()
    try:
        assert um(con, "SELECT status FROM suit_outbox WHERE id=?", (cli.item,))["status"] == "preparado"
    finally:
        con.close()


def test_rascunho_do_endereco_com_o_gmail_fora_avisa(cli):
    r = cli.post(f"/ops/api/suits/{cli.pid}/endereco-fornecedor/rascunho", headers=cli.h)
    assert r.status_code == 502 and "Gmail" in r.json()["detail"]
