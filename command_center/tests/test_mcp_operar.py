"""MCP que opera o painel pelo papel de quem usa (#73).

Dono, 02/10: *"todas as funcionalidades sejam operáveis pela API, não só como visualização...
de acordo com o nível de hierarquia ali do operador ou gerente"*.

O que estes testes trancam: o MCP chama as MESMAS rotas do painel, como a pessoa — o operador
não faz o que é do gerente, o acesso de leitura não escreve, o que vai para o cliente pede
confirmação, e tudo fica na auditoria com o nome de quem fez.
"""
import json
import os
import tempfile

import pytest

os.environ["URACE_ENV"] = "/nao/existe"

from fastapi.testclient import TestClient  # noqa: E402

from command_center import providers  # noqa: E402
from command_center.api import auth, mcp_operar, oauth  # noqa: E402
from command_center.api.main import app  # noqa: E402
from command_center.db import aplicar_schema, conectar, inserir, todos, um  # noqa: E402

SENHA = "senha-forte-123"
MCP = "/ops/mcp"


@pytest.fixture(scope="module")
def cli():
    pasta = tempfile.mkdtemp()
    os.environ["CC_DB_PATH"] = os.path.join(pasta, "cc.sqlite")
    os.environ["URACE_DIR"] = pasta
    con = conectar(); aplicar_schema(con)
    auth.criar_usuario(con, "vendas@urace.us", "Vendedor", "OPERATOR", SENHA)
    auth.criar_usuario(con, "ger@urace.us", "Gerente", "MANAGER", SENHA)
    auth.criar_usuario(con, "ver@urace.us", "Só Vê", "VIEWER", SENHA)
    inserir(con, "oauth_clients", client_id="claude-code", name="Claude Code", redirect_uris='["http://localhost/cb"]')
    inserir(con, "clients", name="Joseph Kartian", pilot_name="Enzo Kartian", email="joe.kartian@example.com", status="ACTIVE",
            source="manual", monthly_amount=2756.9, monthly_item_id="7")
    inserir(con, "qbo_items", id="7", name="Academy Monthly", price=2756.9, active=1)
    con.commit(); con.close()
    with TestClient(app, base_url="https://cc.test") as c:
        yield c


@pytest.fixture(autouse=True)
def sem_sistemas_de_fora(monkeypatch):
    def nada(sistema, ferramenta, **_):
        raise AssertionError(f"falou com {sistema}.{ferramenta} sem confirmar")
    monkeypatch.setattr(providers, "chamar", nada)


def token(email, operar=True):
    con = conectar()
    uid = um(con, "SELECT id FROM users WHERE email=?", (email,))["id"]
    escopo = f"{oauth.ESCOPO} {oauth.ESCOPO_OPERAR}" if operar else oauth.ESCOPO
    t = oauth._emitir(con, "claude-code", uid, escopo)["access_token"]
    con.commit(); con.close()
    return {"Authorization": f"Bearer {t}"}


def ferramenta(cli, h, nome, **args):
    cli.cookies.clear()
    r = cli.post(MCP, json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                            "params": {"name": nome, "arguments": args}}, headers=h)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert "error" not in corpo, corpo
    res = corpo["result"]
    texto = res["content"][0]["text"]
    return (json.loads(texto) if not res["isError"] else texto), res["isError"]


def test_vendedor_cria_cliente_pelo_mcp_e_fica_auditado_com_o_nome_dele(cli):
    h = token("vendas@urace.us")
    res, erro = ferramenta(cli, h, "urace_api", metodo="POST", caminho="/ops/api/clients",
                           corpo={"name": "Maria Santos", "pilot_name": "Leo Santos", "email": "maria@x.com"})
    assert not erro and res["status"] == 201 and res["resposta"]["created"] is True, res
    con = conectar()
    vend = um(con, "SELECT id FROM users WHERE email='vendas@urace.us'")["id"]
    c = um(con, "SELECT * FROM clients WHERE email='maria@x.com'")
    assert c and c["pilot_name"] == "Leo Santos"
    ev = {a["event"]: a for a in todos(con, "SELECT event, actor, detail FROM audit_logs")}
    assert ev["client.create"]["actor"] == f"user:{vend}", "a rota de sempre auditou, com o vendedor"
    assert json.loads(ev["mcp.call"]["detail"])["caminho"] == "/ops/api/clients"


def test_operador_nao_faz_o_que_e_do_gerente(cli):
    cid = um(conectar(), "SELECT id FROM clients WHERE name='Joseph Kartian'")["id"]
    res, erro = ferramenta(cli, token("vendas@urace.us"), "urace_api", metodo="PATCH",
                           caminho=f"/ops/api/clients/{cid}/mensal", corpo={"monthly_amount": 1})
    assert erro and "MANAGER" in res
    assert um(conectar(), "SELECT monthly_amount FROM clients WHERE id=?", (cid,))["monthly_amount"] == 2756.9
    lista, _ = ferramenta(cli, token("vendas@urace.us"), "urace_operacoes", busca="mensal", limite=300)
    assert all(o["papel"] in ("VIEWER", "OPERATOR") for o in lista["operacoes"])


def test_gerente_faz_o_que_e_dele(cli):
    cid = um(conectar(), "SELECT id FROM clients WHERE name='Joseph Kartian'")["id"]
    res, erro = ferramenta(cli, token("ger@urace.us"), "urace_api", metodo="PATCH",
                           caminho=f"/ops/api/clients/{cid}/mensal", corpo={"monthly_sessions": 4},
                           confirmar=True)
    assert not erro and res["ok"], res
    assert um(conectar(), "SELECT monthly_sessions FROM clients WHERE id=?", (cid,))["monthly_sessions"] == 4


def test_o_que_vai_para_o_cliente_pede_confirmacao(cli):
    """A primeira chamada só mostra; sem confirmar, nada é criado nem enviado."""
    cid = um(conectar(), "SELECT id FROM clients WHERE name='Joseph Kartian'")["id"]
    res, erro = ferramenta(cli, token("ger@urace.us"), "urace_api", metodo="POST",
                           caminho=f"/ops/api/clients/{cid}/mensal/recorrencia", corpo={"meses": 6})
    assert not erro and res["precisa_confirmar"] is True and res["vai_fazer"]["corpo"] == {"meses": 6}
    assert not todos(conectar(), "SELECT id FROM monthly_recurring WHERE client_id=?", (cid,))


def test_acesso_de_leitura_nao_escreve_mas_le(cli):
    h = token("vendas@urace.us", operar=False)
    res, erro = ferramenta(cli, h, "urace_api", metodo="POST", caminho="/ops/api/clients", corpo={"name": "Não Pode"})
    assert erro and "só de leitura" in res
    assert not um(conectar(), "SELECT id FROM clients WHERE name='Não Pode'")
    res, erro = ferramenta(cli, h, "urace_api", metodo="GET", caminho="/ops/api/clients")
    assert not erro and res["status"] == 200
    lista, _ = ferramenta(cli, h, "urace_operacoes", limite=300)
    assert lista["opera"] is False and {o["metodo"] for o in lista["operacoes"]} == {"GET"}


def test_viewer_nao_ganha_escopo_de_operar_nem_pedindo():
    """O escopo sozinho não basta: precisa do papel. Rebaixada a pessoa, o token volta a ler."""
    con = conectar()
    uid = um(con, "SELECT id FROM users WHERE email='ver@urace.us'")["id"]
    t = oauth._emitir(con, "claude-code", uid, f"{oauth.ESCOPO} {oauth.ESCOPO_OPERAR}")["access_token"]
    assert oauth.usuario_do_token(con, t)["somente_leitura"] is True
    vid = um(con, "SELECT id FROM users WHERE email='vendas@urace.us'")["id"]
    t2 = oauth._emitir(con, "claude-code", vid, f"{oauth.ESCOPO} {oauth.ESCOPO_OPERAR}")["access_token"]
    assert oauth.usuario_do_token(con, t2)["somente_leitura"] is False
    con.execute("UPDATE users SET role='VIEWER' WHERE id=?", (vid,))
    assert oauth.usuario_do_token(con, t2)["somente_leitura"] is True
    con.execute("UPDATE users SET role='OPERATOR' WHERE id=?", (vid,))
    con.commit(); con.close()


def test_login_chaves_e_area_do_cliente_ficam_fora(cli):
    h = token("ger@urace.us")
    for metodo, caminho in (("POST", "/ops/api/auth/api-keys"), ("GET", "/ops/api/portal/me"), ("GET", "/ops/health")):
        res, erro = ferramenta(cli, h, "urace_api", metodo=metodo, caminho=caminho)
        assert erro, caminho
    res, erro = ferramenta(cli, h, "urace_api", metodo="GET", caminho="/ops/api/../health")
    assert erro


def test_catalogo_tem_o_dia_a_dia_de_vendas():
    caminhos = {(o["metodo"], o["caminho"]) for o in mcp_operar.catalogo()}
    assert ("POST", "/ops/api/clients") in caminhos
    assert any(c.startswith("/ops/api/site/agendamentos") for m, c in caminhos if m == "POST")
    assert any(c.startswith("/ops/api/sales") for m, c in caminhos if m == "POST")
    assert not any(c.startswith(("/ops/api/auth", "/ops/api/portal")) for _, c in caminhos)
    assert len(caminhos) > 150, "o painel inteiro, não um pedaço"


def test_cartao_conectar_o_claude_mostra_o_endereco_do_login_e_o_papel(cli):
    """#77 (dono, 02/10): "deixe o connector visível para os usuários". O endereço é o mesmo
    que o servidor de login anuncia; quem é VIEWER fica sabendo que o acesso só lê."""
    for email, opera in (("vendas@urace.us", True), ("ver@urace.us", False)):
        cli.cookies.clear()
        assert cli.post("/ops/api/auth/login", json={"email": email, "password": SENHA}).status_code == 200
        d = cli.get("/ops/api/equipe/conector-claude").json()
        assert d["url"] == oauth.emissor() + "/ops/mcp" and d["pode_operar"] is opera
        assert d["terminal"] == f"claude mcp add --transport http urace {d['url']}"
    cli.cookies.clear()
    assert cli.get("/ops/api/equipe/conector-claude").status_code == 401


# --------------------------------------------------------------- #362: papel x conector
def _admin_do_teste():
    con = conectar()
    if not um(con, "SELECT id FROM users WHERE email='admin.teste@example.com'"):
        auth.criar_usuario(con, "admin.teste@example.com", "Admin Teste", "ADMIN", SENHA)
        con.commit()
    con.close()
    return "admin.teste@example.com"


def test_admin_com_conector_so_de_leitura_explica_que_o_bloqueio_e_do_conector(cli):
    """#362 (dono): "explicar no painel por que ADMIN está com opera=false, separando papel do
    usuário e permissão do conector"."""
    h = token(_admin_do_teste(), operar=False)
    lista, _ = ferramenta(cli, h, "urace_operacoes", limite=5)
    assert lista["papel"] == "ADMIN" and lista["opera"] is False
    assert lista["papel_permite_operar"] is True and lista["conector_permite_operar"] is False
    esperado = ("Seu papel (ADMIN) permite operar, mas este conector foi autorizado só para leitura: "
                "desconecte e conecte de novo marcando 'Também operar o painel como você'.")
    assert lista["por_que"] == esperado
    res, erro = ferramenta(cli, h, "urace_api", metodo="POST", caminho="/ops/api/clients", corpo={"name": "Não Pode"})
    assert erro and esperado in res, "o erro de urace_api usa o mesmo texto"


def test_viewer_explica_que_o_bloqueio_e_do_papel(cli):
    for operar in (False, True):
        lista, _ = ferramenta(cli, token("ver@urace.us", operar=operar), "urace_operacoes", limite=5)
        assert lista["papel"] == "VIEWER" and lista["opera"] is False
        assert lista["papel_permite_operar"] is False and lista["conector_permite_operar"] is operar
        assert "seu papel (VIEWER) só permite ler" in lista["por_que"].replace("Seu papel", "seu papel")
        assert "OPERATOR ou acima" in lista["por_que"]


def test_tudo_liberado_explica_que_opera(cli):
    lista, _ = ferramenta(cli, token(_admin_do_teste()), "urace_operacoes", limite=5)
    assert lista["opera"] is True and lista["papel_permite_operar"] and lista["conector_permite_operar"]
    assert lista["por_que"].startswith("Seu papel (ADMIN) permite operar e este conector foi autorizado para operar")


def test_cartao_lista_os_conectores_da_propria_pessoa_sem_token(cli):
    email = _admin_do_teste()
    con = conectar()
    if not um(con, "SELECT 1 FROM oauth_clients WHERE client_id='chatgpt-teste'"):
        inserir(con, "oauth_clients", client_id="chatgpt-teste", name="ChatGPT", redirect_uris='["http://localhost/cb"]')
        inserir(con, "oauth_clients", client_id="revogado-teste", name="Revogado", redirect_uris='["http://localhost/cb"]')
    adm = um(con, "SELECT id FROM users WHERE email=?", (email,))["id"]
    outro = um(con, "SELECT id FROM users WHERE email='ger@urace.us'")["id"]
    lido = oauth._emitir(con, "chatgpt-teste", adm, oauth.ESCOPO)
    oauth._emitir(con, "claude-code", adm, f"{oauth.ESCOPO} {oauth.ESCOPO_OPERAR}")
    oauth._emitir(con, "chatgpt-teste", outro, f"{oauth.ESCOPO} {oauth.ESCOPO_OPERAR}")   # de outra pessoa
    oauth._emitir(con, "revogado-teste", adm, oauth.ESCOPO)
    con.execute("UPDATE oauth_tokens SET revoked_at=? WHERE client_id='revogado-teste'", ("2026-01-01T00:00:00.000Z",))
    con.commit(); con.close()

    cli.cookies.clear()
    assert cli.post("/ops/api/auth/login", json={"email": email, "password": SENHA}).status_code == 200
    r = cli.get("/ops/api/equipe/conector-claude")
    d = r.json()
    por_nome = {c["nome"]: c for c in d["conectores"]}
    assert set(por_nome) == {"ChatGPT", "Claude Code"}, "só os da pessoa, e só os que valem"
    assert por_nome["ChatGPT"]["escopo"] == "leitura" and por_nome["ChatGPT"]["opera"] is False
    assert "foi autorizado só para leitura" in por_nome["ChatGPT"]["por_que"]
    assert por_nome["Claude Code"]["escopo"] == "operar" and por_nome["Claude Code"]["opera"] is True
    assert all(c["autorizado_em"] for c in d["conectores"])
    assert lido["access_token"] not in r.text and lido["refresh_token"] not in r.text
    assert not any(k in r.text for k in ("token_hash", "secret", "client_id"))
    cli.cookies.clear()
