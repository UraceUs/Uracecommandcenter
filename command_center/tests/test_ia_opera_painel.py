"""#420 (dono, 28/10): a IA do painel opera o Command Center inteiro, não só lê.

*"Ela tem autonomia para fazer tudo ali dentro, não é só ler. Ela precisa fazer tudo ali ... operar, editar,
mudar o que for preciso"* — o caso real: pediram para corrigir o nome do responsável no card e a IA respondeu
que só conseguia ler. Agora ela usa a mesma rota do botão, como a pessoa que pediu: o papel dela vale, a rota
valida e audita, e o que sai para fora, cobra ou apaga continua no aprovar de um clique.

Nada aqui fala com a Anthropic nem com sistema externo.
"""
import json

import pytest

from command_center.api import agente_sdk, mcp_operar, motor
from command_center.db import aplicar_schema, conectar, inserir, um


@pytest.fixture()
def con(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    monkeypatch.setenv("URACE_ENV", "/nao/existe")
    c = conectar(); aplicar_schema(c)
    yield c
    c.close()


def _pessoa(con, email, papel):
    return con.execute("INSERT INTO users (email, name, role, pw_salt, pw_hash) VALUES (?,?,?,'x','x')",
                       (email, email.split("@")[0].title(), papel)).lastrowid


def _card(con):
    return inserir(con, "clients", name="Equipe Fictícia Racing", email="manager.ficticio@example.com",
                   phone="555-555-0140", status="ACTIVE", source="asana")


def test_ia_classifica_a_rota_ler_fazer_e_aprovar(con):
    c = agente_sdk.classificar
    assert c(con, "painel_operacoes") == "ler"
    assert c(con, "painel_api", {"metodo": "GET", "caminho": "/clients/1"}) == "ler"
    assert c(con, "painel_api", {"metodo": "PATCH", "caminho": "/clients/1"}) == "fazer"          # editar o card: direto
    assert c(con, "painel_api", {"metodo": "POST", "caminho": "/clients/1/waiver-invite"}) == "aprovar"   # sai para o cliente
    assert c(con, "painel_api", {"metodo": "DELETE", "caminho": "/estoque/item/3"}) == "aprovar"  # apagar: clique
    # #422: unir cards e remover não voltam atrás — clique, como o painel_unir_clientes sempre foi
    assert c(con, "painel_api", {"metodo": "POST", "caminho": "/client-merge"}) == "aprovar"
    assert c(con, "painel_api", {"metodo": "POST", "caminho": "/site/agenda/bloqueios/4/remover"}) == "aprovar"
    assert c(con, "painel_api", {"metodo": "POST", "caminho": "/compras/7/cancelar"}) == "fazer"      # interno
    con.execute("UPDATE action_policies SET policy='BLOCKED' WHERE action='apagar_qualquer_coisa'")
    assert c(con, "painel_api", {"metodo": "DELETE", "caminho": "/estoque/item/3"}) == "bloqueada"   # "a IA nunca apaga"
    assert c(con, "painel_api", {"metodo": "PATCH", "caminho": "/clients/1"}) == "fazer"
    con.execute("INSERT INTO action_policies (action, policy) VALUES ('painel_api', 'BLOCKED')")
    assert c(con, "painel_api", {"metodo": "PATCH", "caminho": "/clients/1"}) == "bloqueada"      # o dono desliga tudo


def test_ia_corrige_o_nome_do_responsavel_no_card_como_quem_pediu(con):
    """O caso do card 621: a IA troca o responsável e preenche o piloto, sem mexer no e-mail do manager."""
    uid = _pessoa(con, "operador@urace.us", "OPERATOR")
    cid = _card(con)
    con.commit()
    r = mcp_operar.executar_como(uid, "PATCH", f"/clients/{cid}", {"name": "Pai Fictício Silva", "pilot_name": "Filho Fictício Silva"})
    assert r["ok"], r
    c = um(con, "SELECT name, pilot_name, email FROM clients WHERE id=?", (cid,))
    assert (c["name"], c["pilot_name"], c["email"]) == ("Pai Fictício Silva", "Filho Fictício Silva", "manager.ficticio@example.com")
    a = um(con, "SELECT user_id, detail FROM audit_logs WHERE event='client.update' AND entity_id=?", (str(cid),))
    assert a["user_id"] == uid and json.loads(a["detail"])["antes"]["name"] == "Equipe Fictícia Racing"   # no nome de quem pediu
    assert um(con, "SELECT 1 AS x FROM audit_logs WHERE event='ai.painel_api' AND user_id=?", (uid,))
    # a credencial interna vale só aquela chamada
    assert um(con, "SELECT COUNT(*) AS n FROM sessions WHERE user_id=? AND revoked_at IS NULL", (uid,))["n"] == 0


def test_a_rota_valida_igual_ao_botao(con):
    uid = _pessoa(con, "operador@urace.us", "OPERATOR")
    cid = _card(con)
    con.commit()
    r = mcp_operar.executar_como(uid, "PATCH", f"/clients/{cid}", {"name": " "})
    assert r["status"] == 400 and um(con, "SELECT name FROM clients WHERE id=?", (cid,))["name"] == "Equipe Fictícia Racing"


def test_o_papel_de_quem_pediu_vale(con):
    viewer = _pessoa(con, "viewer@urace.us", "VIEWER")
    op = _pessoa(con, "operador@urace.us", "OPERATOR")
    cid = _card(con)
    con.commit()
    with pytest.raises(ValueError, match="papel"):
        mcp_operar.executar_como(viewer, "PATCH", f"/clients/{cid}", {"name": "Outro Nome"})
    with pytest.raises(ValueError, match="papel MANAGER"):          # o operador não faz o que é do gerente
        mcp_operar.executar_como(op, "PUT", f"/clients/{cid}/waiver-flow", {"flow": "docusign"}, aprovado=True)


def test_sair_para_fora_ou_apagar_nunca_roda_sem_o_aprovar(con):
    uid = _pessoa(con, "dono@urace.us", "ADMIN")
    cid = _card(con)
    con.commit()
    for metodo, caminho in (("POST", f"/clients/{cid}/waiver-invite"), ("DELETE", "/estoque/item/1"), ("POST", "/client-merge")):
        with pytest.raises(ValueError, match="aprovar"):
            mcp_operar.executar_como(uid, metodo, caminho, {})
    with pytest.raises(ValueError, match="não são operados"):
        mcp_operar.executar_como(uid, "POST", "/auth/logout")


def test_portao_roda_o_interno_e_transforma_o_que_apaga_num_aprovar_que_executa_pela_rota(con):
    uid = _pessoa(con, "operador@urace.us", "OPERATOR")
    cmd = inserir(con, "ai_commands", user_id=uid, text="tira a peça fictícia do estoque", session_key="s")
    item = inserir(con, "stock_items", kind="peca", tracking="quantidade", name="Peça Fictícia 108")
    con.commit()
    p = agente_sdk.Portao(cmd, user_id=uid)
    assert p.decidir("mcp__operar__painel_api", {"metodo": "PATCH", "caminho": "/clients/1"}) is None   # roda direto
    args = {"metodo": "DELETE", "caminho": f"/estoque/item/{item}"}
    motivo = p.decidir("mcp__operar__painel_api", args)
    assert motivo and "aprovação #" in motivo
    a = um(con, "SELECT * FROM ai_actions WHERE command_id=? AND action='painel_api'", (cmd,))
    assert a["status"] == "PROPOSED" and json.loads(a["payload"])["args"] == args
    assert f"DELETE /estoque/item/{item}" in json.loads(a["payload"])["descricao"]       # o cartão diz o que vai fazer
    assert um(con, "SELECT active FROM stock_items WHERE id=?", (item,))["active"] == 1      # nada rodou ainda
    con.execute("UPDATE ai_actions SET status='APPROVED' WHERE id=?", (a["id"],))
    con.commit()
    motor.executar_acao(a["id"], uid)                          # o clique: roda pela rota, como quem aprovou
    a = um(con, "SELECT status, result FROM ai_actions WHERE id=?", (a["id"],))
    assert a["status"] == "DONE", a["result"]
    assert um(con, "SELECT active FROM stock_items WHERE id=?", (item,))["active"] == 0      # saiu das prateleiras, sem apagar


def test_o_que_rodou_direto_fica_como_acao_feita(con):
    uid = _pessoa(con, "operador@urace.us", "OPERATOR")
    cmd = inserir(con, "ai_commands", user_id=uid, text="t", session_key="s")
    con.commit()
    p = agente_sdk.Portao(cmd, user_id=uid)
    p.registrar("mcp__operar__painel_api", {"metodo": "PATCH", "caminho": "/clients/1", "corpo": {"name": "X Y"}}, {"ok": True})
    p.registrar("mcp__operar__painel_api", {"metodo": "GET", "caminho": "/clients/1"}, {"ok": True})
    feitas = con.execute("SELECT action, status FROM ai_actions WHERE command_id=?", (cmd,)).fetchall()
    assert [(f["action"], f["status"]) for f in feitas] == [("painel_api", "DONE")]       # a leitura não vira ação


def test_as_ferramentas_de_operar_entram_so_com_uma_pessoa(con, monkeypatch):
    import claude_agent_sdk
    criados = {}
    monkeypatch.setattr(claude_agent_sdk, "create_sdk_mcp_server",
                        lambda nome, versao, tools: criados.__setitem__(nome, [t.name for t in tools]) or {"name": nome})
    monkeypatch.setattr(agente_sdk, "servidores_mcp", lambda: {})
    uid = _pessoa(con, "operador@urace.us", "OPERATOR")
    con.commit()
    o = agente_sdk._opcoes("m", "s", agente_sdk.Portao(1, user_id=uid), 2, None, 10)
    assert "operar" in o.mcp_servers and criados["operar"] == ["painel_operacoes", "painel_api"]
    assert "mcp__operar__*" in o.allowed_tools
    o = agente_sdk._opcoes("m", "s", agente_sdk.Portao(1), 2, None, 10)       # rotina sem pessoa: só lê
    assert "operar" not in o.mcp_servers
    assert "painel_api" in agente_sdk.instrucoes() and "Nunca diga que só consegue ler o painel" in agente_sdk.instrucoes()


def test_lista_do_que_da_para_fazer_e_a_do_papel(con):
    op = _pessoa(con, "operador@urace.us", "OPERATOR")
    con.commit()
    quem = mcp_operar._quem_pelo_id(con, op)
    r = mcp_operar.operacoes(quem, "clients")
    caminhos = {(o["metodo"], o["caminho"]) for o in r["operacoes"]}
    assert ("PATCH", "/ops/api/clients/{cid}") in caminhos
    assert ("PUT", "/ops/api/clients/{cid}/waiver-flow") not in caminhos        # é do gerente
