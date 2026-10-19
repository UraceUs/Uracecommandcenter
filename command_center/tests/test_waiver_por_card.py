"""Waiver por card: DocuSign ou nativa (#348).

Dono, 19/10: *"Um switch para escolher dentro do card de cada cliente se vamos usar o fluxo pelo DocuSign ou pela
waiver nativa."* O que estes testes trancam: `nativa` no card vale mesmo com a chave geral desligada (a área do
cliente oferece, a cobrança não manda DocuSign); `docusign` no card vale mesmo com a chave ligada; `padrao` segue a
chave; `nativa` sem selo é recusada (409); só gerente ou acima muda; e a escolha de um card não vaza para outro."""
from command_center.api import auth
from command_center.db import conectar, inserir, um
from command_center.providers import cobranca_agenda as cob
from command_center.providers import waiver_nativa as wn
from command_center.tests.test_cobranca_agenda import Docusign, Qbo, cenario, con, marca  # noqa: F401
from command_center.tests import test_waiver_nativa as _tn
from command_center.tests.test_waiver_nativa import P, S, SENHA, cliente, equipe

cli = _tn.cli                                   # a mesma fixture (banco, modelos falsos do DocuSign, equipe)


def _db(sql, args=()):
    c = conectar()
    c.execute(sql, args); c.commit(); c.close()


def _card(nome, email):
    c = conectar()
    cid = inserir(c, "clients", name=nome, email=email, status="ACTIVE")
    c.commit(); c.close()
    return cid


def _prepara(cli, geral):
    """Importa os modelos; liga ou não a chave geral. Devolve a conta (dois pilotos, cada um no seu card)."""
    h = equipe(cli)
    assert cli.post(f"{S}/waiver-nativa/importar", headers=h).status_code == 200
    if geral:
        assert cli.post(f"{S}/waiver-nativa/ligar", json={"ligada": True}, headers=h).status_code == 200
    hc, (p1, p2) = cliente(cli, pilotos=(("Leo Exemplo", "2014-05-01"), ("Ana Exemplo", "2012-03-02")))
    c1, c2 = _card("Leo Exemplo", "leo@example.com"), _card("Ana Exemplo", "ana@example.com")
    _db("UPDATE portal_pilots SET client_id=? WHERE id=?", (c1, p1))
    _db("UPDATE portal_pilots SET client_id=? WHERE id=?", (c2, p2))
    return hc, p1, p2, c1, c2


def _muda(cli, card, flow, quem="ger@urace.us"):
    h = equipe(cli, quem)
    return cli.put(f"/ops/api/clients/{card}/waiver-flow", json={"flow": flow}, headers=h)


def _portal(cli, hc_login=("maria@example.com", "corrida-segura-9")):
    cli.cookies.clear()
    assert cli.post(f"{P}/login", json={"email": hc_login[0], "password": hc_login[1]}).status_code == 200
    return {d["driver_id"]: d["enabled"] for d in cli.get(f"{P}/waivers").json()["drivers"]}


def test_nativa_no_card_com_a_chave_desligada_e_so_naquele_card(cli):
    _, p1, p2, c1, c2 = _prepara(cli, geral=False)
    r = _muda(cli, c1, "nativa")
    assert r.status_code == 200 and r.json()["effective"] == "nativa" and r.json()["general"] == "docusign"
    assert _portal(cli) == {p1: True, p2: False}, "o irmão no padrão segue a chave geral (desligada)"
    a = um(conectar(), "SELECT detail, user_id FROM audit_logs WHERE event='client.waiver_flow' ORDER BY id DESC LIMIT 1")
    assert '"antes": "padrao"' in a["detail"] and '"depois": "nativa"' in a["detail"] and a["user_id"]


def test_docusign_no_card_com_a_chave_ligada_nao_oferece_a_nativa(cli):
    _, p1, p2, c1, _ = _prepara(cli, geral=True)
    assert _muda(cli, c1, "docusign").json()["effective"] == "docusign"
    assert _portal(cli) == {p1: False, p2: True}
    h = {"X-CSRF": cli.cookies.get("cp_csrf")}
    assert cli.post(f"{P}/drivers/{p1}/waiver/events", json={"event": "screen_opened"}, headers=h).status_code == 404
    assert cli.post(f"{P}/drivers/{p2}/waiver/events", json={"event": "screen_opened"}, headers=h).status_code == 201


def test_nativa_sem_selo_e_recusada(cli, tmp_path, monkeypatch):
    _, _, _, c1, _ = _prepara(cli, geral=False)
    monkeypatch.setenv("CC_WAIVER_SEAL_DIR", str(tmp_path / "sem-selo"))
    r = _muda(cli, c1, "nativa")
    assert r.status_code == 409 and "selo" in r.json()["detail"]
    f = cli.get(f"/ops/api/clients/{c1}/waiver-flow").json()
    assert f["choice"] == "padrao" and f["native_available"] is False and f["native_reason"]


def test_viewer_e_operador_nao_mudam_e_sem_login_401(cli):
    _, _, _, c1, _ = _prepara(cli, geral=False)
    c = conectar()
    auth.criar_usuario(c, "ver@urace.us", "Viewer", "VIEWER", SENHA)
    auth.criar_usuario(c, "op@urace.us", "Operador", "OPERATOR", SENHA)
    c.commit(); c.close()
    assert _muda(cli, c1, "nativa", "ver@urace.us").status_code == 403
    assert _muda(cli, c1, "nativa", "op@urace.us").status_code == 403
    _portal(cli)                                         # o cliente logado na área dele não é equipe
    assert cli.put(f"/ops/api/clients/{c1}/waiver-flow", json={"flow": "nativa"},
                   headers={"X-CSRF": cli.cookies.get("cp_csrf") or ""}).status_code == 401


def test_cobranca_segue_o_card(con, cenario, monkeypatch):  # noqa: F811
    monkeypatch.setattr(wn, "_modelos_prontos", lambda con: True)
    # chave geral desligada + card nativa: não manda DocuSign
    con.execute("UPDATE clients SET waiver_flow='nativa' WHERE id=?", (cenario["card"],))
    ds = Docusign()
    cob.aceitar(con, 1, marca(con, cenario), enviar_invoice=Qbo(), enviar_waiver=ds)
    assert not ds.chamadas
    # chave geral ligada + card docusign: manda
    con.execute("UPDATE booking_config SET waiver_native=1 WHERE id=1")
    con.execute("UPDATE clients SET waiver_flow='docusign' WHERE id=?", (cenario["card"],))
    ds = Docusign()
    from command_center.tests.test_agenda_sessoes import proximo
    cob.aceitar(con, 1, marca(con, cenario, proximo(3)), enviar_invoice=Qbo(), enviar_waiver=ds)
    assert len(ds.chamadas) == 1
    # padrão: segue a chave geral (ligada) — outro card no padrão não herda o docusign deste
    outro = inserir(con, "clients", name="Outro Exemplo", email="o@example.com", status="ACTIVE")
    assert wn.fluxo_da_waiver(con, outro) == "nativa" and wn.fluxo_da_waiver(con, None) == "nativa"
    con.execute("UPDATE booking_config SET waiver_native=0 WHERE id=1")
    assert wn.fluxo_da_waiver(con, outro) == "docusign"
