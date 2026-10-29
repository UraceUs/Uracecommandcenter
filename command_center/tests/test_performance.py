"""Performance (issue #19): arquivo do build com cache imutável e resposta grande comprimida."""
import os
import re

import pytest

os.environ["URACE_ENV"] = "/nao/existe"

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api import auth, main  # noqa: E402
from command_center.db import aplicar_schema, conectar, inserir  # noqa: E402

SENHA = "senha-forte-123"


def test_arquivo_com_hash_e_imutavel_e_o_resto_nao():
    assert main.cache_de("/ops/assets/index-Co7pDqj7.js") == "public, max-age=31536000, immutable"
    assert main.cache_de("/ops/") is None and main.cache_de("/ops/api/dashboard") is None
    assert main.cache_de("/ops/assetsx/a.js") is None


@pytest.fixture()
def cli(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path))
    c = conectar(); aplicar_schema(c)
    auth.criar_usuario(c, "adm@urace.us", "Admin", "ADMIN", SENHA)
    c.commit(); c.close()
    with TestClient(main.app, base_url="https://cc.test") as t:
        yield t


def test_resposta_grande_vai_comprimida_e_pequena_nao(cli):
    cli.post("/ops/api/auth/login", json={"email": "adm@urace.us", "password": SENHA})
    grande = cli.get("/ops/api/policies", headers={"Accept-Encoding": "gzip"})
    assert grande.status_code == 200 and len(grande.content) > 1024
    assert grande.headers.get("content-encoding") == "gzip"
    assert grande.headers["cache-control"] == "private, no-cache", "dado da API: só no navegador, sempre revalidado (#20)"
    cli.cookies.clear()
    pequena = cli.get("/ops/api/dashboard", headers={"Accept-Encoding": "gzip"})
    assert pequena.status_code == 401 and pequena.headers.get("content-encoding") is None, "menos de 1 KB não compensa"


def test_a_lista_de_clientes_acha_o_que_e_de_cada_cliente_pelo_indice(cli, monkeypatch):
    """29/10, produção: GET /clients levava ~2,4 s com 315 clientes. Cada linha da lista conta tarefas, e-mails e a
    waiver do cliente numa subconsulta; sem índice em client_id, cada subconsulta varria a tabela inteira, uma vez
    por cliente (e as tabelas só crescem). O mesmo valia para o card e o recálculo de ativo/inativo."""
    from command_center import db
    con = conectar()
    cid = inserir(con, "clients", name="Nora Fictícia", email="nora@example.com", status="ACTIVE", source="manual")
    inserir(con, "tasks", client_id=cid, title="Nora Fictícia_Practice", project="U-RACE", status="open", due_on="2026-11-02")
    inserir(con, "emails", client_id=cid, mailbox="urace", subject="Treino", handled=0)
    inserir(con, "waivers", client_id=cid, signer_name="Nora Fictícia", template="adult", status="completed", sent_at="2026-10-01")
    con.commit(); con.close()
    vistos, original = [], db.conectar

    def conectar_rastreando(*a, **k):
        c = original(*a, **k)
        c.set_trace_callback(vistos.append)
        return c
    monkeypatch.setattr(db, "conectar", conectar_rastreando)
    cli.post("/ops/api/auth/login", json={"email": "adm@urace.us", "password": SENHA})
    assert cli.get("/ops/api/clients").status_code == 200
    sql = next(s for s in vistos if "FROM clients c LEFT JOIN client_stages" in s)
    con = original()
    plano = [r[3] for r in con.execute("EXPLAIN QUERY PLAN " + sql)]
    con.close()
    # t = tasks, e = emails, w = waivers: toda busca nelas vai direto às linhas do cliente
    varre = [p for p in plano if re.match(r"(SCAN|SEARCH) [tew]\b", p) and "client_id=?" not in p]
    assert not varre, plano
