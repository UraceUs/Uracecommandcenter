"""#354 (dono, 20/10): "as novas waivers entram quando as atuais forem vencendo" e "mostrar o IP do servidor de onde
o sistema opera". O convite não sai com waiver valendo, só nos últimos 30 dias dela (a renovação, com o item em
"Precisa de atenção"); os eventos da equipe gravam o IP do servidor e o aparelho fixo; o de quem assina não muda."""
import json
from datetime import timedelta

from command_center.db import conectar, inserir, todos, um
from command_center.providers import convite_waiver as cw, portal, trilha_waiver as tw
from command_center.tests.test_convite_waiver import card, manda
from command_center.tests.test_waiver_nativa import cli, equipe, liga  # noqa: F401 (fixture)
from command_center.tests.test_waiver_prova import _arquivos, _baixa, _cert, _pelo_convite

API = "/ops/api"
IP_VPS = "203.0.113.50"


def _docusign(cid, dias_atras):
    """Uma waiver do DocuSign assinada no card há `dias_atras` dias (vale 1 ano da assinatura)."""
    con = conectar()
    try:
        quando = (portal.hoje() - timedelta(days=dias_atras)).isoformat() + "T15:00:00.000Z"
        return inserir(con, "waivers", client_id=cid, signer_name="Bruno Teste", signer_email="bruno.teste@example.com",
                       template="adult", status="completed", source="docusign", completed_at=quando)
    finally:
        con.close()


def _adulto():
    return card(name="Bruno Teste", email="bruno.teste@example.com", pilot_name=None, pilot_dob="1990-02-02")


def test_convite_recusado_com_waiver_valendo(cli):  # noqa: F811
    liga(cli)
    cid = _adulto()
    _docusign(cid, 100)                                   # vale mais 265 dias
    h = equipe(cli)
    d = cli.get(f"{API}/clients/{cid}/waiver-invite").json()["destino"]
    assert d["can_send"] is False and d["renewal"] is False and d["valid_waiver_source"] == "docusign"
    assert "renovação libera" in d["reason"]
    r = manda(cli, h, cid, "bruno.teste@example.com")
    assert r.status_code == 409 and "valendo" in r.json()["detail"]
    assert not todos(conectar(), "SELECT id FROM waiver_invites WHERE client_id=?", (cid,))


def test_convite_liberado_quando_vence_em_ate_30_dias_e_item_na_atencao(cli):  # noqa: F811
    liga(cli)
    cid = _adulto()
    _docusign(cid, 365 - 12)                              # vence em 12 dias
    longe = _adulto()
    _docusign(longe, 100)
    h = equipe(cli)
    d = cli.get(f"{API}/clients/{cid}/waiver-invite").json()["destino"]
    assert d["can_send"] and d["renewal"] and d["renewal_days"] == cw.RENOVACAO_DIAS
    itens = [a for a in cli.get(f"{API}/needs-attention").json() if a["key"].startswith("waiver-renovar:")]
    assert [a["client_id"] for a in itens] == [cid], "só a que vence em até 30 dias"
    assert itens[0]["entity"]["type"] == "waiver_renewal" and "12 dia" in itens[0]["title"]
    assert not [e for e in _emails_para("bruno.teste@example.com")], "o item não manda nada sozinho"
    r = manda(cli, h, cid, "bruno.teste@example.com")
    assert r.status_code == 201, r.text
    a = um(conectar(), "SELECT detail FROM audit_logs WHERE event='waiver.invite.sent' AND entity_id=?", (str(cid),))
    assert json.loads(a["detail"])["renewal"] is True


def _emails_para(para):
    from command_center.tests.test_convite_waiver import emails
    return [e for e in emails() if e["to"] == para]


def test_evento_da_equipe_grava_o_ip_do_servidor_e_o_do_cliente_fica(monkeypatch, cli):  # noqa: F811
    monkeypatch.setenv("CC_SERVER_IP", IP_VPS)
    con = conectar()
    e = tw.registrar(con, "downloaded", "staff", ip="198.51.100.7", user_agent="Mozilla/5.0 (Equipe)",
                     detail={"by": "Gerente", "user_id": 1}, waiver_id=1)
    c = tw.registrar(con, "screen_opened", "invite", source="client", ip="198.51.100.8", user_agent="Mozilla/5.0 (Cliente)",
                     invite_id=1)
    s = tw.registrar(con, "invite_sent", "invite", ip="198.51.100.7", invite_id=1, detail={"by": "user:1"})
    con.commit()
    linhas = {r["id"]: r for r in todos(con, "SELECT * FROM waiver_events")}
    assert (linhas[e["id"]]["ip"], linhas[e["id"]]["user_agent"]) == (IP_VPS, tw.UA_EQUIPE)
    assert json.loads(linhas[e["id"]]["detail"])["by"] == "Gerente", "quem fez continua"
    assert (linhas[s["id"]]["ip"], linhas[s["id"]]["user_agent"]) == (IP_VPS, tw.UA_EQUIPE)
    assert (linhas[c["id"]]["ip"], linhas[c["id"]]["user_agent"]) == ("198.51.100.8", "Mozilla/5.0 (Cliente)")
    assert tw.verificar(con)["ok"]
    monkeypatch.delenv("CC_SERVER_IP")
    monkeypatch.setattr(tw, "_ip_descoberto", None)
    monkeypatch.setattr(tw.socket, "socket", _sem_rede)
    assert tw.ip_do_servidor() == "server", "sem a variável e sem descobrir, grava 'server'"


def _sem_rede(*_a, **_k):
    raise OSError("sem rede")


def test_pacote_antigo_mostra_o_ip_do_servidor_nas_linhas_da_equipe_e_a_cadeia_fica(monkeypatch, cli):  # noqa: F811
    # antes do #354: o evento da equipe gravava o IP da pessoa (simulado desligando a troca na gravação)
    with monkeypatch.context() as m:
        m.setattr(tw, "da_equipe", lambda *_: False)
        wid, _cid, _token = _pelo_convite(cli)
        con = conectar()
        tw.registrar(con, "downloaded", "staff", ip="198.51.100.7", user_agent="Mozilla/5.0 (Equipe)",
                     detail={"by": "Gerente"}, waiver_id=wid)
        con.commit()
    monkeypatch.setenv("CC_SERVER_IP", IP_VPS)
    _z, arq = _arquivos(_baixa(cli, wid).content)
    linhas = json.loads(arq["audit_logs.json"])["rows"]
    da_equipe = [x for x in linhas if str(x["actor"]).startswith("user:")]
    assert da_equipe and all(x["ip"] == IP_VPS for x in da_equipe)
    assert all(x["ip"] != IP_VPS for x in linhas if not str(x["actor"]).startswith("user:"))
    ev = json.loads(arq["events.json"])
    antigo = [e for e in ev["events"] if e["event"] == "downloaded" and e["flow"] == "staff"]
    assert antigo and antigo[0]["ip"] == "198.51.100.7", "o events.json fica como foi gravado"
    assert ev["integrity"]["ok"] and tw.verificar(conectar())["ok"]
    cert = _cert(arq["certificate-of-completion.pdf"])
    assert f"IP {IP_VPS} (URACE's server)" in cert and "198.51.100.7" not in cert
    assert tw.UA_EQUIPE in cert
