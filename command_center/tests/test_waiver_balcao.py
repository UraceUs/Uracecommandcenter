"""Conferência do documento com foto no balcão (#117; lacunas A-4 e F-4 do P-15).

Dono, 06/10: *"sim, no check-in"*: a equipe confere o documento com foto de quem assinou a waiver.

O que estes testes trancam: ler o QR do cliente traz as waivers que valem para ESTE card (a nativa e a do DocuSign),
nunca as de outro card; a conferência (tipo de documento de uma lista fechada, se o nome confere e, pelo menor, se a
idade confere) vira um evento append-only da trilha e a auditoria `waiver.id_check`, sem imagem, sem número do
documento e sem mexer na linha da waiver; o cliente não alcança a rota (401) e a conta sem papel recebe 403; o que
não conferiu aparece em "Precisa de atenção" e nada é bloqueado; o nascimento do piloto com waiver valendo não muda
(409), e sem ela, ou depois de anular, muda; a parental do card deixa de valer quando o piloto faz 18.
Os dados são fictícios (`@example.com`, nomes inventados)."""
import json
from datetime import timedelta

import pytest

from command_center.api import auth
from command_center.db import conectar, inserir, todos, um
from command_center.providers import balcao, portal, trilha_waiver as tw
from command_center.tests.test_waiver_nativa import (P, S, SENHA, assina, cli, cliente, equipe, liga)  # noqa: F401 (fixture)

B = "/ops/api/balcao"
API = "/ops/api"


def _hoje():
    return portal.hoje()


def _nasc(anos, dias=0):
    """O nascimento de quem fez `anos` anos há `dias` dias (no fuso da Flórida)."""
    d = _hoje() - timedelta(days=dias)
    return d.replace(year=d.year - anos, day=min(d.day, 28) if d.month == 2 else d.day).isoformat()


def card(con, **campos):
    base = {"name": "Rosa Teste", "email": "rosa@example.com", "pilot_name": "Davi Teste", "pilot_dob": _nasc(30),
            "status": "ACTIVE", "source": "manual"}
    return inserir(con, "clients", **{**base, **campos})


def nativa(con, client_id, **campos):
    """Uma waiver nativa assinada, gravada direto (o INSERT é livre: a trava do #109 segura a linha depois)."""
    quando = (_hoje() - timedelta(days=10)).isoformat() + "T15:00:00.000Z"
    base = dict(client_id=client_id, signer_name="Davi Teste", signer_email="davi@example.com", template="adult",
                status="completed", sent_at=quando, completed_at=quando,
                expires_at=(_hoje() + timedelta(days=355)).isoformat(), source="urace", doc_sha256="b" * 64,
                audit=json.dumps({"driver_name": "Davi Teste"}), pdf_path="/nao/existe.pdf")
    return inserir(con, "waivers", **{**base, **campos})


def docusign(con, client_id, **campos):
    quando = (_hoje() - timedelta(days=30)).isoformat() + "T15:00:00Z"
    base = dict(client_id=client_id, signer_name="Davi Teste", signer_email="davi@example.com", template="adult",
                status="completed", sent_at=quando, completed_at=quando)
    return inserir(con, "waivers", **{**base, **campos})


def usuarios():
    con = conectar()
    auth.criar_usuario(con, "op@urace.us", "Operador", "OPERATOR", SENHA)
    auth.criar_usuario(con, "olho@urace.us", "Visitante", "VIEWER", SENHA)
    con.commit(); con.close()


def confere(cli, h, wid, client_id, **mais):  # noqa: F811
    corpo = {"client_id": client_id, "document_type": "drivers_license", "name_matches": True, **mais}
    return cli.post(f"{B}/waivers/{wid}/id-check", json=corpo, headers=h)


# ------------------------------------------------------------------ a leitura do QR traz as waivers do card certo
def test_ler_o_qr_traz_as_waivers_do_card_e_nunca_as_de_outro(cli):  # noqa: F811
    usuarios()
    con = conectar()
    a, b = card(con), card(con, name="Outra Familia", email="outra@example.com", pilot_name="Ana Outra")
    na = nativa(con, a)
    da = docusign(con, a)
    nb = nativa(con, b, signer_name="Ana Outra")
    nativa(con, a, expires_at=(_hoje() - timedelta(days=1)).isoformat())                 # vencida: não aparece
    anulada = nativa(con, a)
    inserir(con, "waiver_voids", waiver_id=anulada, by_name="Gerente", reason="assinada pelo responsável errado")
    docusign(con, a, status="sent")                                                       # enviada, não assinada
    docusign(con, a, completed_at=(_hoje() - timedelta(days=400)).isoformat() + "T15:00:00Z")   # de mais de um ano
    cod = balcao.codigo_do_cliente(con, a)
    con.commit(); con.close()
    equipe(cli, "op@urace.us")
    r = cli.get(f"{B}/ler", params={"codigo": f"https://ops.urace.us/ops/c/{cod}"})
    assert r.status_code == 200, r.text
    assert [(w["id"], w["source"]) for w in r.json()["waivers"]] == [(na, "urace"), (da, "docusign")]
    assert nb not in [w["id"] for w in r.json()["waivers"]], "nunca a waiver de outro card"
    assert [w["id"] for w in cli.get(f"{B}/cliente/{a}").json()["waivers"]] == [na, da], "a tela do card aberto mostra as mesmas"
    assert [w["id"] for w in cli.get(f"{B}/cliente/{b}").json()["waivers"]] == [nb]
    w = r.json()["waivers"][0]
    assert w["signer_name"] == "Davi Teste" and w["kind"] == "adult" and w["minor"] is False and w["id_check"] is None
    assert "signer_email" not in w, "o balcão não precisa do e-mail de quem assinou"


# ------------------------------------------------------------------ conferir: evento, auditoria, nada na waiver
def test_conferir_grava_o_evento_na_trilha_e_a_auditoria_sem_mexer_na_waiver(cli):  # noqa: F811
    usuarios()
    con = conectar()
    a, b = card(con), card(con, name="Outra Familia", email="outra@example.com")
    wid = nativa(con, a)
    vencida = nativa(con, a, expires_at=(_hoje() - timedelta(days=1)).isoformat())
    de_b = nativa(con, b)
    con.commit()
    antes = um(con, "SELECT * FROM waivers WHERE id=?", (wid,))
    con.close()
    h = equipe(cli, "op@urace.us")
    r = confere(cli, h, wid, a, document_type="passport")
    assert r.status_code == 201, r.text
    assert r.json()["ok"] is True and r.json()["event"] == "id_checked"
    assert r.json()["waivers"][0]["id_check"]["ok"] is True and r.json()["waivers"][0]["id_check"]["by"] == "Operador"
    con = conectar()
    (e,) = todos(con, "SELECT * FROM waiver_events WHERE waiver_id=?", (wid,))
    d = json.loads(e["detail"])
    assert e["event"] == "id_checked" and e["flow"] == "staff" and e["client_id"] == a and e["kind"] == "adult"
    assert d == {"document_type": "passport", "name_matches": True, "minor_age_matches": None, "checked": "signer",
                 "waiver_source": "urace", "by": "Operador", "user_id": d["user_id"]}
    aud = um(con, "SELECT * FROM audit_logs WHERE event='waiver.id_check' AND entity_id=?", (str(wid),))
    assert aud and json.loads(aud["detail"])["result"] == "ok" and json.loads(aud["detail"])["event_id"] == e["id"]
    assert um(con, "SELECT * FROM waivers WHERE id=?", (wid,)) == antes, "a linha assinada não muda (#109)"
    assert tw.verificar(con)["ok"]
    # sem imagem e sem número do documento: o corpo só aceita a lista
    for extra in ({"document_number": "D1234567"}, {"image": "data:image/png;base64,AAAA"}, {"photo": "x"}):
        assert confere(cli, h, wid, a, **extra).status_code == 422, extra
    assert confere(cli, h, wid, a, document_type="selfie").status_code == 422
    assert confere(cli, h, wid, a, name_matches="sim").status_code == 422
    assert confere(cli, h, de_b, a).status_code == 404, "waiver de outro card: igual a não existir"
    assert confere(cli, h, vencida, a).status_code == 409
    assert confere(cli, h, 2**63, a).status_code == 422 and confere(cli, h, 0, a).status_code == 422
    assert len(todos(conectar(), "SELECT id FROM waiver_events WHERE event LIKE 'id_check%'")) == 1, "recusa não grava nada"
    # o evento aparece na trilha da waiver (Site › Waiver › Trilha), depois de assinar
    equipe(cli, "ger@urace.us")
    ev = cli.get(f"{S}/waiver-nativa/{wid}/eventos").json()["eventos"]
    assert [(x["phase"], x["event"]) for x in ev] == [("after", "id_checked")]
    assert ev[0]["label"] == "Photo ID checked at the track" and ev[0]["detail"]["document_type"] == "passport"


def test_a_do_docusign_tambem_se_confere(cli):  # noqa: F811
    usuarios()
    con = conectar()
    a = card(con)
    wid = docusign(con, a)
    con.commit(); con.close()
    h = equipe(cli, "op@urace.us")
    r = confere(cli, h, wid, a, document_type="state_id")
    assert r.status_code == 201, r.text
    e = um(conectar(), "SELECT * FROM waiver_events WHERE waiver_id=?", (wid,))
    assert e["event"] == "id_checked" and json.loads(e["detail"])["waiver_source"] == "docusign"


# ------------------------------------------------------------------ quem alcança a rota
def test_cliente_nao_alcanca_a_rota_e_conta_sem_papel_recebe_403(cli):  # noqa: F811
    usuarios()
    con = conectar()
    a = card(con)
    wid = nativa(con, a)
    con.commit(); con.close()
    cli.cookies.clear()
    assert confere(cli, {}, wid, a).status_code == 401
    hc, _ = cliente(cli)                                      # logado na área do cliente (cookie cp_session)
    assert confere(cli, hc, wid, a).status_code == 401, "a sessão do cliente não é a da equipe"
    h = equipe(cli, "olho@urace.us")
    assert confere(cli, h, wid, a).status_code == 403
    assert um(conectar(), "SELECT COUNT(*) AS n FROM waiver_events")["n"] == 0


# ------------------------------------------------------------------ menor: a idade; não confere: alerta, não bloqueia
def test_menor_pede_a_idade_e_o_que_nao_confere_vai_para_a_atencao_sem_bloquear(cli):  # noqa: F811
    from command_center.api import atencao
    from command_center.providers import waiver_nativa as wn
    usuarios()
    con = conectar()
    a = card(con, pilot_name="Davi Teste", pilot_dob=_nasc(12))
    wid = nativa(con, a, template="parental", signer_name="Rosa Teste", minor_name="Davi Teste",
                 audit=json.dumps({"driver_name": "Davi Teste", "driver_birth_date": _nasc(12)}))
    con.commit(); con.close()
    h = equipe(cli, "op@urace.us")
    w = cli.get(f"{B}/cliente/{a}").json()["waivers"][0]
    assert w["minor"] and w["driver_birth_date"] == _nasc(12) and w["driver_age"] == 12
    r = confere(cli, h, wid, a)
    assert r.status_code == 400 and "idade" in r.json()["detail"], "pelo menor, a idade é obrigatória"
    r = confere(cli, h, wid, a, minor_age_matches=False)
    assert r.status_code == 201 and r.json()["ok"] is False and r.json()["event"] == "id_check_failed"
    chave = f"waiver-documento:waiver:{wid}"
    (it,) = [i for i in atencao.coletar(conectar()) if i["key"] == chave]
    assert it["level"] == "HIGH" and it["link"] == f"/balcao/{a}" and "a idade do menor não confere" in it["why"]
    assert it["client_id"] == a and "a equipe decide" in it["why"]
    assert [x["id"] for x in cli.get(f"{B}/cliente/{a}").json()["waivers"]] == [wid], "nada é bloqueado sozinho"
    assert confere(cli, h, wid, a, name_matches=False, minor_age_matches=True).json()["event"] == "id_check_failed"
    assert "o nome não confere" in [i for i in atencao.coletar(conectar()) if i["key"] == chave][0]["why"]
    # conferiu de novo e bateu: sai da atenção
    assert confere(cli, h, wid, a, minor_age_matches=True).json()["event"] == "id_checked"
    assert not [i for i in atencao.coletar(conectar()) if i["key"] == chave]
    # não conferiu e a equipe anulou: a decisão foi tomada, sai sozinho (fica em "mostrar ocultos")
    assert confere(cli, h, wid, a, minor_age_matches=False).status_code == 201
    con = conectar()
    wn.anular(con, wid, {"id": None, "name": "Gerente"}, "documento não conferiu no balcão")
    assert not [i for i in atencao.coletar(con) if i["key"] == chave]
    assert [i for i in atencao.coletar(con, incluir_ocultos=True) if i["key"] == chave][0]["dismissed"]["auto"]


def test_adulto_ignora_a_idade_do_menor(cli):  # noqa: F811
    usuarios()
    con = conectar()
    a = card(con)
    wid = nativa(con, a)
    con.commit(); con.close()
    h = equipe(cli, "op@urace.us")
    assert confere(cli, h, wid, a, minor_age_matches=False).json()["event"] == "id_checked"
    assert json.loads(um(conectar(), "SELECT detail FROM waiver_events WHERE waiver_id=?", (wid,))["detail"])["minor_age_matches"] is None


# ------------------------------------------------------------------ o nascimento travado
def test_mudar_o_nascimento_com_waiver_vigente_volta_409_vencida_ou_anulada_passa(cli, monkeypatch):  # noqa: F811
    liga(cli)
    hc, (pid, outro) = cliente(cli, pilotos=(("Leo Teste", "2014-05-01"), ("Bia Teste", "2015-06-02")))
    r = assina(cli, hc, pid)
    assert r.status_code == 201, r.text
    wid = r.json()["waiver_id"]
    r = cli.patch(f"{P}/drivers/{pid}", json={"birth_date": "2014-06-01"}, headers=hc)
    assert r.status_code == 409, r.text
    assert "can't be changed while their signed waiver is valid" in r.json()["detail"] and "contact URACE" in r.json()["detail"]
    con = conectar()
    assert um(con, "SELECT birth_date FROM portal_pilots WHERE id=?", (pid,))["birth_date"] == "2014-05-01"
    assert um(con, "SELECT 1 AS x FROM audit_logs WHERE event='portal.driver.birth_date_locked'")
    con.close()
    # o resto do piloto continua editável, e mandar o mesmo nascimento (a tela manda o formulário inteiro) passa
    assert cli.patch(f"{P}/drivers/{pid}", json={"birth_date": "2014-05-01", "notes": "Two years in Mini"}, headers=hc).status_code == 200
    # o irmão sem waiver muda à vontade
    assert cli.patch(f"{P}/drivers/{outro}", json={"birth_date": "2015-07-02"}, headers=hc).status_code == 200
    # vencida (daqui a 400 dias), também passa; de volta a hoje, continua travado
    depois = _hoje() + timedelta(days=400)
    with monkeypatch.context() as m:
        m.setattr(portal, "hoje", lambda: depois)
        assert cli.patch(f"{P}/drivers/{pid}", json={"birth_date": "2014-05-02"}, headers=hc).status_code == 200
        assert cli.patch(f"{P}/drivers/{pid}", json={"birth_date": "2014-05-01"}, headers=hc).status_code == 200
    assert cli.patch(f"{P}/drivers/{pid}", json={"birth_date": "2014-06-01"}, headers=hc).status_code == 409
    # a equipe anulou: o nascimento volta a mudar (e o cliente assina outra com a data certa)
    h = equipe(cli, "ger@urace.us")
    assert cli.post(f"{API}/waivers/{wid}/void", json={"reason": "nascimento declarado errado"}, headers=h).status_code == 200
    cli.cookies.clear()
    assert cli.post(f"{P}/login", json={"email": "maria@example.com", "password": "corrida-segura-9"}).status_code == 200
    hc = {"X-CSRF": cli.cookies.get("cp_csrf")}
    assert cli.patch(f"{P}/drivers/{pid}", json={"birth_date": "2014-06-01"}, headers=hc).status_code == 200
    assert um(conectar(), "SELECT birth_date FROM portal_pilots WHERE id=?", (pid,))["birth_date"] == "2014-06-01"


# ------------------------------------------------------------------ o convite confere os 18, como `vigente`
@pytest.fixture()
def con(tmp_path, monkeypatch):
    from command_center.db import aplicar_schema
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    c = conectar(); aplicar_schema(c)
    yield c
    c.close()


def test_vigente_do_card_nao_ve_a_parental_de_quem_fez_18(con):
    from command_center.providers import convite_waiver as cw
    fez = card(con, pilot_dob=_nasc(18, dias=1))                 # fez 18 ontem
    menor = card(con, name="Outra Familia", email="outra@example.com", pilot_dob=_nasc(17))
    # assinadas pela regra antiga (1 ano, sem olhar os 18): a linha não se reescreve (#109), então nasce assim
    w_fez = nativa(con, fez, template="parental", expires_at=(_hoje() + timedelta(days=200)).isoformat())
    w_menor = nativa(con, menor, template="parental", expires_at=(_hoje() + timedelta(days=200)).isoformat())
    con.commit()
    assert cw._vigente_do_card(con, fez, "parental") is None, "fez 18: a parental não vale mais"
    assert cw._vigente_do_card(con, menor, "parental")["id"] == w_menor
    assert [w["id"] for w in balcao.waivers_do_card(con, fez)] == [], "o balcão também não a mostra"
    assert w_fez not in [w["id"] for w in balcao.waivers_do_card(con, menor)]


def test_vigente_do_card_usa_o_nascimento_do_piloto_da_conta(con):
    from command_center.providers import convite_waiver as cw
    cid = card(con, pilot_dob=None)
    conta = inserir(con, "portal_accounts", name="Rosa Teste", email="rosa@example.com", pw_salt="x", pw_hash="x",
                    birth_date=_nasc(40), terms_accepted_at=_hoje().isoformat())
    pid = inserir(con, "portal_pilots", account_id=conta, name="Davi Teste", birth_date=_nasc(18, dias=3), client_id=cid)
    nativa(con, cid, template="parental", pilot_id=pid, expires_at=(_hoje() + timedelta(days=200)).isoformat())
    con.commit()
    assert cw._vigente_do_card(con, cid, "parental") is None


# ------------------------------------------------------------------ revisão do #336: o card certo, sempre
def _aviso(con, wid, ocultos=False):
    from command_center.api import atencao
    return [i for i in atencao.coletar(con, incluir_ocultos=ocultos) if i["key"] == f"waiver-documento:waiver:{wid}"]


def _nao_conferiu(cli):  # noqa: F811
    """Uma waiver do DocuSign casada no card errado (A), que não conferiu no balcão. Devolve (h, a, b, wid)."""
    usuarios()
    con = conectar()
    a = card(con, name="Card Errado", email="errado@example.com", pilot_name="Piloto Errado")
    b = card(con, name="Card Certo", email="certo@example.com", pilot_name="Piloto Certo")
    wid = docusign(con, a, signer_name="Pessoa Certa")
    con.commit(); con.close()
    h = equipe(cli, "op@urace.us")
    assert confere(cli, h, wid, a, name_matches=False).json()["event"] == "id_check_failed"
    return h, a, b, wid


def test_o_aviso_segue_a_waiver_religada_a_outro_card(cli):  # noqa: F811
    h, a, b, wid = _nao_conferiu(cli)
    hg = equipe(cli, "ger@urace.us")
    assert cli.post(f"{API}/waivers/{wid}/link", json={"client_id": b}, headers=hg).status_code == 200
    (it,) = _aviso(conectar(), wid)
    assert it["client_id"] == b and it["link"] == f"/balcao/{b}" and it["title"].startswith("Piloto Certo:"), it
    h = equipe(cli, "op@urace.us")
    assert confere(cli, h, wid, a).status_code == 404 and confere(cli, h, wid, b).status_code == 201
    assert not _aviso(conectar(), wid), "conferiu pelo card certo: sai da atenção"


def test_o_aviso_vai_para_o_card_que_ficou_ao_unir(cli):  # noqa: F811
    from command_center.providers import identidade
    h, a, b, wid = _nao_conferiu(cli)
    con = conectar()
    assert identidade.unir(con, b, a, "teste", "duplicado")
    con.commit()
    (it,) = _aviso(con, wid)
    assert it["client_id"] == b and it["link"] == f"/balcao/{b}"


@pytest.mark.parametrize("como", ["oculta", "sem card", "vencida"])
def test_o_aviso_some_sozinho_quando_a_waiver_sai_do_balcao(cli, monkeypatch, como):  # noqa: F811
    h, a, b, wid = _nao_conferiu(cli)
    con = conectar()
    if como == "oculta":
        con.execute("UPDATE waivers SET hidden=1 WHERE id=?", (wid,))
    elif como == "sem card":
        con.execute("UPDATE waivers SET client_id=NULL, link_by='human', link_reason='desvinculado' WHERE id=?", (wid,))
    else:
        depois = _hoje() + timedelta(days=400)
        monkeypatch.setattr(portal, "hoje", lambda: depois)
    con.commit()
    assert not _aviso(con, wid), como
    (it,) = _aviso(con, wid, ocultos=True)
    motivo = {"oculta": "a waiver foi ocultada", "sem card": "a waiver não está ligada a nenhum card",
              "vencida": "a waiver não vale mais (vencida ou de quem fez 18)"}[como]
    assert it["dismissed"] == {"by": None, "at": None, "reason": motivo, "auto": True}


def test_o_aviso_nao_vale_para_documento_interno(cli):  # noqa: F811
    h, a, b, wid = _nao_conferiu(cli)
    con = conectar()
    con.execute("UPDATE waivers SET internal=1 WHERE id=?", (wid,))
    con.commit()
    assert not _aviso(con, wid, ocultos=True), "documento da empresa não é waiver de cliente (como as outras regras)"


def test_envelope_que_nao_e_waiver_nao_esconde_a_do_docusign(con):
    a = card(con)
    real = docusign(con, a)                                        # a waiver adult, de 30 dias atrás
    quando = (_hoje() - timedelta(days=3)).isoformat() + "T15:00:00Z"
    docusign(con, a, template="other", subject="Please DocuSign: Membership Agreement", completed_at=quando, sent_at=quando)
    docusign(con, a, template=None, completed_at=quando, sent_at=quando)
    con.commit()
    assert [(w["id"], w["kind"]) for w in balcao.waivers_do_card(con, a)] == [(real, "adult")]


def test_parental_do_docusign_de_quem_fez_18_sai_do_balcao_e_o_nascimento_e_o_do_card(con):
    fez = card(con, pilot_dob=_nasc(19))
    docusign(con, fez, template="parental", minor_name="Davi Teste")
    menor = card(con, name="Outra Familia", email="outra@example.com", pilot_dob=_nasc(15))
    w = docusign(con, menor, template="parental", minor_name="Ana Outra")
    con.commit()
    assert balcao.waivers_do_card(con, fez) == []
    (x,) = balcao.waivers_do_card(con, menor)
    assert x["id"] == w and x["driver_birth_date"] == _nasc(15) and x["driver_birth_date_from"] == "card"
    nat = nativa(con, menor, template="parental", audit=json.dumps({"driver_name": "Ana Outra", "driver_birth_date": _nasc(15, dias=2)}))
    con.commit()
    y = next(v for v in balcao.waivers_do_card(con, menor) if v["id"] == nat)
    assert y["driver_birth_date"] == _nasc(15, dias=2) and y["driver_birth_date_from"] == "waiver"


def test_piloto_religado_a_outro_card_leva_a_waiver_junto(cli):  # noqa: F811
    from command_center.providers import vinculo_site
    usuarios()
    con = conectar()
    a = card(con, name="Card Errado", email="errado@example.com", pilot_name="Outro Piloto")
    b = card(con, name="Rosa Teste", email="rosa2@example.com", pilot_name="Davi Teste")
    conta = inserir(con, "portal_accounts", name="Rosa Teste", email="rosa2@example.com", pw_salt="x", pw_hash="x",
                    birth_date=_nasc(40), terms_accepted_at=_hoje().isoformat())
    pid = inserir(con, "portal_pilots", account_id=conta, name="Davi Teste", birth_date=_nasc(30), client_id=a)
    wid = nativa(con, a, pilot_id=pid, link_by="sync")            # assinada quando o piloto estava (errado) no card A
    con.commit()
    antes = um(con, "SELECT * FROM waivers WHERE id=?", (wid,))
    vinculo_site.desvincular_driver(con, pid)
    con.commit()
    assert balcao.waivers_do_card(con, a) == [], "solto do card, a waiver não fica no card antigo"
    vinculo_site.vincular_driver(con, pid, b, None)
    con.commit()
    assert [w["id"] for w in balcao.waivers_do_card(con, a)] == []
    assert [w["id"] for w in balcao.waivers_do_card(con, b)] == [wid]
    assert um(con, "SELECT * FROM waivers WHERE id=?", (wid,)) == antes, "nada escrito na waiver assinada"
    con.close()
    h = equipe(cli, "op@urace.us")
    assert confere(cli, h, wid, a).status_code == 404
    r = confere(cli, h, wid, b)
    assert r.status_code == 201 and um(conectar(), "SELECT client_id FROM waiver_events WHERE id=?",
                                       (r.json()["event_id"],))["client_id"] == b
    # vínculo feito à mão pela equipe vale mais que o do piloto
    hg = equipe(cli, "ger@urace.us")
    assert cli.post(f"{API}/waivers/{wid}/link", json={"client_id": a}, headers=hg).status_code == 200
    con = conectar()
    assert [w["id"] for w in balcao.waivers_do_card(con, a)] == [wid] and balcao.waivers_do_card(con, b) == []


def test_a_parental_vale_pelo_nascimento_gravado_nela(cli):  # noqa: F811
    """O card diz 16 e o piloto da conta diz 18: o convite mandou a parental pelo nascimento do card, e é ele que está
    na waiver. Ela continua valendo: o card mostra que já há waiver válida e um segundo convite não assina outra."""
    from command_center.providers import convite_waiver as cw
    con = conectar()
    cid = card(con, pilot_dob=_nasc(16))
    conta = inserir(con, "portal_accounts", name="Rosa Teste", email="rosa@example.com", pw_salt="x", pw_hash="x",
                    birth_date=_nasc(40), terms_accepted_at=_hoje().isoformat())
    pid = inserir(con, "portal_pilots", account_id=conta, name="Davi Teste", birth_date=_nasc(18, dias=3), client_id=cid)
    w = nativa(con, cid, template="parental", pilot_id=pid,
               audit=json.dumps({"driver_name": "Davi Teste", "driver_birth_date": _nasc(16)}))
    con.commit()
    v = cw._vigente_do_card(con, cid, "parental")
    assert v and v["id"] == w
    assert cw.destino(con, cid)["valid_waiver_until"] == v["expires_at"]
    from command_center.providers import waiver_nativa as wn
    assert wn.vigente(con, pid)["id"] == w
