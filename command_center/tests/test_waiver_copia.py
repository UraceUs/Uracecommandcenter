"""Cópia da waiver por e-mail e o histórico na área do cliente (#114; lacunas E-1 e E-2 do P-15).

O que estes testes trancam: logo depois de assinar (pela conta e pelo convite) sai um e-mail do noreply@, com
Reply-To support@, só para quem assinou, com o PDF assinado anexado (o hash do anexo é o `doc_sha256`); o message-id
fica na trilha (`copy_emailed`); o Gmail que falha vira `copy_email_failed` e a assinatura continua valendo; o envio
de verdade vai pelo upload do Gmail com o PDF dentro da mensagem; reenviar (cliente e equipe) vai sempre ao e-mail
que assinou, com intervalo e teto, e a anulada não se reenvia; nada disto mexe na linha da waiver; a área do cliente
lista todas as waivers da conta, vigentes, vencidas e anuladas, paginadas, e só a própria conta vê, baixa e pede
cópia. Os dados são fictícios (`@example.com`)."""
import email as email_lib
import hashlib
import json
import os
from datetime import timedelta

import pytest

from command_center.db import conectar, todos, um
from command_center.providers import copia_waiver, email_envio, portal
from command_center.tests.test_waiver_nativa import (CONTA, P, assina, cli, cliente, equipe, liga)  # noqa: F401 (fixture)

API = "/ops/api"


def emails(para=None, assunto=None):
    arq = os.environ["CC_EMAIL_FAKE"]
    linhas = [json.loads(x) for x in open(arq, encoding="utf-8").read().splitlines()] if os.path.exists(arq) else []
    return [x for x in linhas if (para is None or x["to"] == para) and (assunto is None or assunto in x["subject"])]


def copias(para=None):
    return emails(para, "Your signed URACE waiver")


def assinada(cli, nome="Leo Santos", nasc="2014-05-01", conta=CONTA):  # noqa: F811
    hc, (pid,) = cliente(cli, conta=conta, pilotos=((nome, nasc),))
    r = assina(cli, hc, pid)
    assert r.status_code == 201, r.text
    return r.json()["waiver_id"], pid, hc, r.json()


def _eventos(wid, *quais):
    return [dict(e, detail=json.loads(e["detail"] or "{}")) for e in
            todos(conectar(), "SELECT * FROM waiver_events WHERE waiver_id=? ORDER BY id", (wid,)) if not quais or e["event"] in quais]


def _sem_intervalo(monkeypatch):
    monkeypatch.setitem(copia_waiver.INTERVALO_MIN, "signer", 0)
    monkeypatch.setitem(copia_waiver.INTERVALO_MIN, "staff", 0)


# ------------------------------------------------------------------ a cópia logo depois de assinar
def test_depois_de_assinar_a_copia_sai_do_noreply_com_o_pdf_e_o_message_id_fica_na_trilha(cli):  # noqa: F811
    liga(cli)
    wid, pid, hc, resp = assinada(cli)
    assert resp["copy_to"] == "m••••@example.com", "a tela diz para onde a cópia vai, mascarado"
    con = conectar()
    w = um(con, "SELECT * FROM waivers WHERE id=?", (wid,))
    (m,) = copias()
    assert m["to"] == "maria@example.com" == w["signer_email"] and m["from"] == "noreply@urace.us"
    assert m["reply_to"] == "support@urace.us" and m["subject"] == "Your signed URACE waiver for Leo Santos"
    (anexo,) = m["attachments"]
    assert anexo["filename"] == f"URACE-waiver-{wid}.pdf" and anexo["content_type"] == "application/pdf"
    assert anexo["sha256"] == w["doc_sha256"] and anexo["size"] == os.path.getsize(w["pdf_path"])
    assert w["doc_sha256"] in m["text"] and "/ops/portal/waivers" in m["text"] and "html" in m
    (ev,) = _eventos(wid, "copy_emailed")
    d = ev["detail"]
    assert d["message_id"].startswith("fake-") and d["to"] == "m••••@example.com" and d["requested_by"] == "auto"
    assert d["attachment_sha256"] == w["doc_sha256"] and d["from"] == "noreply@urace.us" and d["reply_to"] == "support@urace.us"
    assert ev["flow"] == "account" and ev["account_id"] and ev["pilot_id"] == pid and ev["source"] == "server"
    aud = um(con, "SELECT * FROM audit_logs WHERE event='waiver.copy.emailed' AND entity_id=?", (str(wid),))
    assert json.loads(aud["detail"])["to"] == "maria@example.com" and json.loads(aud["detail"])["message_id"] == d["message_id"]
    assert "copy" not in json.loads(w["audit"]) and d["message_id"] not in w["audit"], "nada da cópia na linha imutável"
    from command_center.providers import trilha_waiver as tw
    assert tw.verificar(con)["ok"]


def test_pelo_convite_a_copia_vai_para_quem_assinou_e_nao_para_o_email_novo_do_card(cli, monkeypatch):  # noqa: F811
    from command_center.tests import test_convite_waiver as tc
    _sem_intervalo(monkeypatch)
    liga(cli)
    cid = tc.card(name="Bruno Adulto", email="bruno@example.com", pilot_name=None, pilot_dob="1990-02-02")
    assert tc.manda(cli, equipe(cli), cid, "bruno@example.com").status_code == 201
    token = tc.token_do_email("bruno@example.com")
    r = tc.assina(cli, token, typed_name="Bruno Adulto")
    assert r.status_code == 201, r.text
    assert r.json()["copy_to"] == "b••••@example.com"
    w = um(conectar(), "SELECT * FROM waivers WHERE client_id=? AND source='urace'", (cid,))
    (m,) = copias("bruno@example.com")
    assert m["attachments"][0]["sha256"] == w["doc_sha256"] and "/ops/portal/invite/" not in m["text"]
    (ev,) = _eventos(w["id"], "copy_emailed")
    assert ev["flow"] == "invite" and ev["invite_id"] and ev["client_id"] == cid
    # o card troca de e-mail: o reenvio da equipe vai para quem assinou, nunca para o e-mail novo
    c = conectar(); c.execute("UPDATE clients SET email='outro.dono@example.com' WHERE id=?", (cid,)); c.commit(); c.close()
    h = equipe(cli)
    r = cli.post(f"{API}/waivers/{w['id']}/copy", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["sent_to"] == "b••••@example.com" and len(copias("bruno@example.com")) == 2
    assert copias("outro.dono@example.com") == []


def test_gmail_que_falha_grava_a_falha_e_a_assinatura_continua_valendo(cli, monkeypatch):  # noqa: F811
    original = email_envio.enviar

    def so_o_anexo_falha(para, assunto, texto, html=None, anexos=None, responder_para=None):
        if anexos:
            raise email_envio.ErroEnvio("Gmail recusou o envio: HTTP 503")
        return original(para, assunto, texto, html=html)

    monkeypatch.setattr(email_envio, "enviar", so_o_anexo_falha)
    liga(cli)
    wid, pid, hc, _ = assinada(cli)
    con = conectar()
    assert um(con, "SELECT status FROM waivers WHERE id=?", (wid,))["status"] == "completed", "a assinatura vale"
    assert cli.get(f"{P}/waivers").json()["drivers"][0]["status"] == "signed"
    assert _eventos(wid, "copy_emailed") == []
    (ev,) = _eventos(wid, "copy_email_failed")
    assert ev["detail"]["reason"] == "gmail" and "503" in ev["detail"]["error"] and ev["detail"]["to"] == "m••••@example.com"
    assert um(con, "SELECT 1 AS x FROM audit_logs WHERE event='waiver.copy.failed' AND entity_id=?", (str(wid),))
    h = cli.get(f"{P}/waivers/history").json()["items"][0]
    assert h["copy"]["status"] == "failed", "o histórico mostra que a cópia não saiu"
    _sem_intervalo(monkeypatch)
    r = cli.post(f"{P}/waivers/{wid}/email", headers=hc)
    assert r.status_code == 503 and "could not email" in r.json()["detail"]


def test_o_envio_de_verdade_vai_pelo_upload_do_gmail_com_o_pdf_dentro(monkeypatch):
    monkeypatch.delenv("CC_EMAIL_FAKE", raising=False)
    import sys
    import types
    falso = types.ModuleType("adminai.google_auth")
    falso.access_token = lambda conta: f"token-de-teste-{conta}"
    monkeypatch.setitem(sys.modules, "adminai.google_auth", falso)
    import adminai
    monkeypatch.setattr(adminai, "google_auth", falso, raising=False)
    pedidos = []

    class Resposta:
        def __init__(self, corpo):
            self.corpo = corpo

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return self.corpo

    def urlopen(req, timeout=None):
        pedidos.append(req)
        return Resposta(json.dumps({"id": "18c0ffee"}).encode())

    monkeypatch.setattr(email_envio.urllib.request, "urlopen", urlopen)
    pdf = b"%PDF-1.4 documento de teste\n%%EOF"
    mid = email_envio.enviar("ana@example.com", "Your signed URACE waiver", "texto", html="<p>oi</p>",
                             anexos=[("URACE-waiver-7.pdf", pdf, "application/pdf")], responder_para="support@urace.us")
    assert mid == "18c0ffee"
    (req,) = pedidos
    assert req.full_url == email_envio.GMAIL_UPLOAD and req.get_header("Content-type") == "message/rfc822"
    assert req.get_header("Authorization") == "Bearer token-de-teste-noreply"
    msg = email_lib.message_from_bytes(req.data)
    assert msg["From"] == "URACE.US <noreply@urace.us>" and msg["To"] == "ana@example.com" and msg["Reply-To"] == "support@urace.us"
    partes = [p for p in msg.walk() if p.get_filename()]
    assert [p.get_filename() for p in partes] == ["URACE-waiver-7.pdf"] and partes[0].get_content_type() == "application/pdf"
    assert partes[0].get_payload(decode=True) == pdf
    # sem anexo, continua o `raw` em JSON de sempre
    pedidos.clear()
    email_envio.enviar("ana@example.com", "Your URACE code: 123456", "texto")
    assert pedidos[0].full_url == email_envio.GMAIL and pedidos[0].get_header("Content-type") == "application/json"


def test_anexo_grande_demais_nao_tenta_sair(monkeypatch):
    monkeypatch.setattr(email_envio, "MAX_ANEXOS", 10)
    with pytest.raises(email_envio.ErroEnvio, match="grande demais"):
        email_envio.enviar("ana@example.com", "x", "y", anexos=[("a.pdf", b"x" * 11, "application/pdf")])


def test_pdf_mexido_no_disco_nao_sai_e_fica_a_falha(cli, monkeypatch):  # noqa: F811
    _sem_intervalo(monkeypatch)
    liga(cli)
    wid, pid, hc, _ = assinada(cli)
    caminho = um(conectar(), "SELECT pdf_path FROM waivers WHERE id=?", (wid,))["pdf_path"]
    os.chmod(caminho, 0o600)
    with open(caminho, "ab") as f:
        f.write(b"\n% mexido")
    antes = len(copias())
    r = cli.post(f"{P}/waivers/{wid}/email", headers=hc)
    assert r.status_code == 503
    assert len(copias()) == antes, "o PDF que não é o assinado não sai"
    assert _eventos(wid, "copy_email_failed")[-1]["detail"]["reason"] == "pdf_changed"


# ------------------------------------------------------------------ reenvio
def test_email_me_a_copy_vai_so_para_quem_assinou_com_intervalo_e_teto(cli, monkeypatch):  # noqa: F811
    liga(cli)
    wid, pid, hc, _ = assinada(cli)
    r = cli.post(f"{P}/waivers/{wid}/email", headers=hc)
    assert r.status_code == 429 and "just emailed a copy" in r.json()["detail"], "a cópia automática acabou de sair"
    monkeypatch.setitem(copia_waiver.INTERVALO_MIN, "signer", 0)
    c = conectar(); c.execute("UPDATE portal_accounts SET email='maria.nova@example.com'"); c.commit(); c.close()
    for _ in range(copia_waiver.POR_DIA["signer"]):
        r = cli.post(f"{P}/waivers/{wid}/email", headers=hc)
        assert r.status_code == 200, r.text
        assert r.json()["sent_to"] == "m••••@example.com"
    r = cli.post(f"{P}/waivers/{wid}/email", headers=hc)
    assert r.status_code == 429 and "several times today" in r.json()["detail"]
    assert len(copias("maria@example.com")) == 1 + copia_waiver.POR_DIA["signer"] and copias("maria.nova@example.com") == []
    pedidos = [e["detail"]["requested_by"] for e in _eventos(wid, "copy_emailed")]
    assert pedidos == ["auto"] + ["signer"] * copia_waiver.POR_DIA["signer"]


def test_outra_conta_nao_ve_nao_baixa_e_nao_pede_copia(cli):  # noqa: F811
    liga(cli)
    wid, *_ = assinada(cli)
    _, (outro,) = cliente(cli, conta={**CONTA, "email": "outra@example.com"})
    h = {"X-CSRF": cli.cookies.get("cp_csrf")}
    r = cli.get(f"{P}/waivers/history")
    assert r.status_code == 200 and r.json()["items"] == [] and r.headers["X-Total-Count"] == "0"
    assert cli.get(f"{P}/waivers/{wid}/pdf").status_code == 404
    assert cli.post(f"{P}/waivers/{wid}/email", headers=h).status_code == 404
    assert len(copias()) == 1
    cli.cookies.clear()
    assert cli.get(f"{P}/waivers/history").status_code == 401


def test_a_anulada_nao_se_reenvia_mas_continua_no_historico_para_baixar(cli, monkeypatch):  # noqa: F811
    _sem_intervalo(monkeypatch)
    liga(cli)
    wid, pid, hc, _ = assinada(cli)
    h = equipe(cli, "ger@urace.us")
    assert cli.post(f"{API}/waivers/{wid}/void", json={"reason": "assinada pelo responsável errado"}, headers=h).status_code == 200
    r = cli.post(f"{API}/waivers/{wid}/copy", headers=h)
    assert r.status_code == 409 and "anulada" in r.json()["detail"]
    cli.cookies.clear()
    assert cli.post(f"{P}/login", json={"email": CONTA["email"], "password": CONTA["password"]}).status_code == 200
    hc = {"X-CSRF": cli.cookies.get("cp_csrf")}
    r = cli.post(f"{P}/waivers/{wid}/email", headers=hc)
    assert r.status_code == 409 and "voided" in r.json()["detail"]
    (item,) = cli.get(f"{P}/waivers/history").json()["items"]
    assert item["status"] == "voided" and item["voided_at"]
    assert "reason" not in json.dumps(item), "o motivo interno da anulação não vai para o cliente"
    assert cli.get(f"{P}{item['pdf'].removeprefix('/ops/api/portal')}").status_code == 200


def test_a_equipe_reenvia_pelo_card_e_o_card_e_o_site_mostram_a_ultima_copia(cli, monkeypatch):  # noqa: F811
    liga(cli)
    wid, pid, hc, _ = assinada(cli)
    c = conectar()
    cid = c.execute("INSERT INTO clients (name, email, pilot_name, status, source) VALUES ('Maria Santos', 'maria@example.com', "
                    "'Leo Santos', 'ACTIVE', 'manual')").lastrowid
    c.execute("UPDATE waivers SET client_id=?, link_by='human', link_reason='teste' WHERE id=?", (cid, wid)); c.commit()
    antes = um(c, "SELECT * FROM waivers WHERE id=?", (wid,))
    c.close()
    from command_center.api import auth
    from command_center.tests.test_waiver_nativa import SENHA
    c = conectar(); auth.criar_usuario(c, "op@urace.us", "Operador", "OPERATOR", SENHA); c.commit(); c.close()
    h = equipe(cli, "op@urace.us")
    r = cli.post(f"{API}/waivers/{wid}/copy", headers=h)
    assert r.status_code == 429, "a automática acabou de sair: espera um minuto"
    monkeypatch.setitem(copia_waiver.INTERVALO_MIN, "staff", 0)
    r = cli.post(f"{API}/waivers/{wid}/copy", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["sent_to"] == "m••••@example.com" and r.json()["message_id"].startswith("fake-")
    ev = _eventos(wid, "copy_emailed")[-1]
    assert ev["flow"] == "staff" and ev["detail"]["by"] == "Operador" and ev["detail"]["requested_by"] == "staff"
    w = next(x for x in cli.get(f"{API}/clients/{cid}").json()["waivers"] if x["id"] == wid)
    assert w["copy"]["status"] == "sent" and w["copy"]["message_id"] == r.json()["message_id"] and w["copy"]["to"] == "m••••@example.com"
    assert um(conectar(), "SELECT * FROM waivers WHERE id=?", (wid,)) == antes, "reenviar não mexe na linha da waiver"
    gh = equipe(cli, "ger@urace.us")
    item = next(x for x in cli.get(f"{API}/site/waiver-nativa").json()["assinadas"]["itens"] if x["id"] == wid)
    assert item["copy"]["status"] == "sent"
    # a do DocuSign não tem cópia por aqui
    c = conectar()
    ds = c.execute("INSERT INTO waivers (client_id, signer_email, template, status, source) VALUES (?, 'maria@example.com', "
                   "'adult', 'completed', 'docusign')", (cid,)).lastrowid
    c.commit(); c.close()
    assert cli.post(f"{API}/waivers/{ds}/copy", headers=gh).status_code == 404


def test_reenviar_da_equipe_tem_teto_por_dia(cli, monkeypatch):  # noqa: F811
    _sem_intervalo(monkeypatch)
    monkeypatch.setitem(copia_waiver.POR_DIA, "staff", 2)
    liga(cli)
    wid, *_ = assinada(cli)
    h = equipe(cli)
    assert [cli.post(f"{API}/waivers/{wid}/copy", headers=h).status_code for _ in range(3)] == [200, 200, 429]


# ------------------------------------------------------------------ o histórico na área do cliente (E-2)
def test_o_historico_lista_vigentes_vencidas_e_anuladas_paginado(cli, monkeypatch):  # noqa: F811
    liga(cli)
    hc, (a, b) = cliente(cli, pilotos=(("Leo Santos", "2014-05-01"), ("Ana Santos", "2016-03-03")))
    assert assina(cli, hc, a).status_code == 201
    c = conectar(); c.execute("UPDATE portal_codes SET created_at='2000-01-01T00:00:00Z'"); c.commit(); c.close()
    assert assina(cli, hc, b).status_code == 201
    s = cli.get(f"{P}/waivers").json()
    assert s["signed_total"] == 2
    r = cli.get(f"{P}/waivers/history")
    assert r.status_code == 200 and r.headers["X-Total-Count"] == "2" and r.headers["Cache-Control"] == "private, no-cache"
    itens = r.json()["items"]
    assert [x["driver"] for x in itens] == ["Ana Santos", "Leo Santos"], "das mais novas para as mais velhas"
    assert {x["status"] for x in itens} == {"valid"} and all(x["copy"]["status"] == "sent" for x in itens)
    assert itens[0]["document"] == "Parental consent Waiver liability" and itens[0]["signed_via"] == "account"
    assert itens[0]["copy"]["to"] == "m••••@example.com" and "message_id" not in itens[0]["copy"]
    r = cli.get(f"{P}/waivers/history?limit=1&offset=1")
    assert r.json()["total"] == 2 and [x["driver"] for x in r.json()["items"]] == ["Leo Santos"]
    assert r.headers["X-Total-Count"] == "2"
    # 400 dias depois: as duas venceram, continuam na lista e continuam baixando
    daqui = portal.hoje() + timedelta(days=400)
    monkeypatch.setattr(portal, "hoje", lambda: daqui)
    itens = cli.get(f"{P}/waivers/history").json()["items"]
    assert [x["status"] for x in itens] == ["expired", "expired"]
    assert cli.get(f"{P}/waivers/{itens[1]['id']}/pdf").status_code == 200
    assert cli.get(f"{P}/waivers").json()["drivers"][0]["status"] == "none", "vencida, o piloto volta a precisar assinar"


def test_parental_vencida_quando_o_piloto_fez_18(cli, monkeypatch):  # noqa: F811
    liga(cli)
    wid, pid, hc, _ = assinada(cli)
    assert cli.get(f"{P}/waivers/history").json()["items"][0]["status"] == "valid"
    c = conectar(); c.execute("UPDATE portal_pilots SET birth_date='2000-01-01' WHERE id=?", (pid,)); c.commit(); c.close()
    (item,) = cli.get(f"{P}/waivers/history").json()["items"]
    assert item["status"] == "expired", "a parental não vale depois dos 18, mesmo antes da data gravada"


def test_o_historico_so_mostra_o_que_existe(cli):  # noqa: F811
    liga(cli)
    cliente(cli)
    r = cli.get(f"{P}/waivers/history")
    assert r.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}
    assert cli.get(f"{P}/waivers").json()["signed_total"] == 0


def test_o_hash_do_anexo_e_o_do_arquivo_entregue_pelo_download(cli):  # noqa: F811
    liga(cli)
    wid, *_ = assinada(cli)
    pdf = cli.get(f"{P}/waivers/{wid}/pdf").content
    assert hashlib.sha256(pdf).hexdigest() == copias()[0]["attachments"][0]["sha256"]
