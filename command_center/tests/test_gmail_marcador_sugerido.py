"""Debug de 29/10 — o marcador que a IA sugeriu, o dono confirmou e criou no Gmail passa a valer na triagem.

A tela do manual diz: "Se confirmar, crie o marcador no Gmail com o mesmo nome; sem isso a IA não consegue aplicá-lo."
O "⟳ Reler a caixa" é o que descobre que ele passou a existir. A sugestão nasce sem caixa (`mailboxes` vazio) e fora
do Gmail (`in_gmail=0`); a releitura lia o vazio como "já está na urace@" e pulava a linha, então o marcador nunca
entrava na triagem."""
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from command_center.api import auth
from command_center.api.main import app
from command_center.db import aplicar_schema, conectar, um
from command_center.providers import triagem

B = "/ops/api"
SENHA = "senha-forte-123"
NOME = "Suppliers/Fornecedor Ficticio"


@pytest.fixture(scope="module")
def cli():
    os.environ["CC_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "cc-gmail-sugerido.sqlite")
    con = conectar(); aplicar_schema(con)
    auth.criar_usuario(con, "admin@urace.us", "Admin Fictício", "ADMIN", SENHA)
    con.close()
    with TestClient(app, base_url="https://cc.test") as c:
        assert c.post(B + "/auth/login", json={"email": "admin@urace.us", "password": SENHA}).status_code == 200
        c.h = {"X-CSRF": c.cookies.get("cc_csrf")}
        yield c


def _caixa(monkeypatch, *nomes):
    vivos = [{"nome": n, "id": f"l{i}", "tipo": "user"} for i, n in enumerate(nomes)]
    monkeypatch.setattr("command_center.api.rotas_gmail.chamar", lambda s, f, **a: vivos)


def test_sugestao_confirmada_e_criada_no_gmail_entra_na_triagem(cli, monkeypatch):
    con = conectar()
    try:
        assert triagem.guardar_sugestao(con, {"nome": NOME, "o_que": "Fornecedor fictício de adesivos.",
                                              "por_que": "fatura sem marcador que sirva"}, "teste")
        lid = um(con, "SELECT id FROM gmail_labels WHERE name=?", (NOME,))["id"]
    finally:
        con.close()
    # o dono confirma, cria o marcador na urace@ e relê a caixa (a primeira releitura depois da sugestão)
    assert cli.patch(f"{B}/gmail/manual/{lid}", headers=cli.h, json={"status": "confirmado"}).status_code == 200
    _caixa(monkeypatch, "wNews", NOME)
    assert cli.post(B + "/gmail/manual/refresh?mailbox=urace", headers=cli.h).status_code == 200
    con = conectar()
    try:
        linha = um(con, "SELECT in_gmail, mailboxes FROM gmail_labels WHERE id=?", (lid,))
        assert linha["in_gmail"] == 1 and '"urace"' in (linha["mailboxes"] or "")
        assert NOME in triagem.confirmados(con, "urace")
    finally:
        con.close()


def test_sugestao_criada_na_support_nao_aparece_como_se_estivesse_na_urace(cli, monkeypatch):
    nome = "Fornecedores/Outro Ficticio"
    con = conectar()
    try:
        assert triagem.guardar_sugestao(con, {"nome": nome, "o_que": "x", "por_que": "y"}, "teste")
        lid = um(con, "SELECT id FROM gmail_labels WHERE name=?", (nome,))["id"]
    finally:
        con.close()
    cli.patch(f"{B}/gmail/manual/{lid}", headers=cli.h, json={"status": "confirmado"})
    _caixa(monkeypatch, nome)
    assert cli.post(B + "/gmail/manual/refresh?mailbox=support", headers=cli.h).status_code == 200
    con = conectar()
    try:
        linha = um(con, "SELECT in_gmail, mailboxes FROM gmail_labels WHERE id=?", (lid,))
        assert linha["in_gmail"] == 1 and linha["mailboxes"] == '["support"]'
        assert nome in triagem.confirmados(con, "support") and nome not in triagem.confirmados(con, "urace")
    finally:
        con.close()
