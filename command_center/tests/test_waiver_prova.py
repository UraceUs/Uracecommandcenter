"""Pacote de prova da waiver nativa, para o advogado e o tribunal (#115, lacunas G-1 e G-2).

Feito quando (issue): o ZIP contém tudo da lista e o `sha256sum` confere; a exportação fica auditada; o modelo de
declaração está pronto para o advogado. E mais: o hash de `signed.pdf` é o `doc_sha256` e o que está no `audit_logs`;
o selo confere pela raiz que vem no próprio ZIP; o `.tst` é o token de `waiver_timestamps` (e o OpenSSL o confere);
o mesmo registro dá o mesmo ZIP, byte a byte; nenhum arquivo leva chave privada, cookie, token, senha ou link do
convite; operador 403, cliente 401, DocuSign 409; a anulada também exporta, com a anulação no certificado avulso.
Os dados são fictícios (`@example.com`, nomes inventados); as chaves são de TESTE, geradas na hora."""
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import zipfile

from command_center.api import auth
from command_center.db import conectar, inserir, todos, um
from command_center.providers import prova_waiver as pw, selo_waiver as sw, trilha_waiver as tw
from command_center.tests.test_waiver_nativa import (CONTA, P, SENHA, assina, cli, cliente, equipe, liga)  # noqa: F401

API = "/ops/api"
NOMES = ["signed.pdf", "audit.json", "waiver.json", "events.json", "events.csv", "audit_logs.json", "template.json",
         "template.pdf", "timestamp.tst", "timestamp.json", "seal-cert.pem", "seal-root.pem", "tsa/tsa-root.pem",
         "certificate-of-completion.pdf", "system-description.md", "declaration-DRAFT.md", "VERIFY.md", "SHA256SUMS"]


def _assinada(cli):  # noqa: F811
    """Uma parental assinada pela área do cliente; devolve (wid, cookies do cliente)."""
    liga(cli)
    hc, (pid,) = cliente(cli)
    r = assina(cli, hc, pid)
    assert r.status_code == 201, r.text
    return r.json()["waiver_id"], {k: v for k, v in cli.cookies.items()}


def _baixa(cli, wid, email="ger@urace.us"):  # noqa: F811
    equipe(cli, email)
    r = cli.get(f"{API}/waivers/{wid}/evidence.zip")
    assert r.status_code == 200, r.text
    return r


def _arquivos(b):
    z = zipfile.ZipFile(io.BytesIO(b))
    return z, {n: z.read(n) for n in z.namelist()}


def _cert(b):
    from pypdf import PdfReader
    return " ".join(" ".join((p.extract_text() or "").split()) for p in PdfReader(io.BytesIO(b)).pages)


def _cert_x509(pem):
    from cryptography import x509
    return x509.load_pem_x509_certificate(pem)


# ------------------------------------------------------------------ o que vai no ZIP
def test_o_zip_traz_tudo_da_lista_e_o_sha256sums_confere(cli):  # noqa: F811
    wid, _ = _assinada(cli)
    r = _baixa(cli, wid)
    assert r.headers["content-type"] == "application/zip"
    assert r.headers["cache-control"] == "private, no-store", "pacote com dado de cliente: nunca em cache"
    assert "etag" not in r.headers
    assert f'filename="URACE-waiver-{wid}-evidence.zip"' in r.headers["content-disposition"]
    assert r.headers["x-content-sha256"] == hashlib.sha256(r.content).hexdigest()
    z, arq = _arquivos(r.content)
    assert z.namelist() == NOMES, z.namelist()
    linhas = arq["SHA256SUMS"].decode().splitlines()
    assert [ln.split("  ", 1)[1] for ln in linhas] == NOMES[:-1], "todo arquivo, menos o próprio SHA256SUMS, na ordem"
    for ln in linhas:                                       # o `sha256sum -c` refeito em Python
        sha, nome = ln.split("  ", 1)
        assert hashlib.sha256(arq[nome]).hexdigest() == sha, nome
    if shutil.which("sha256sum"):                           # e o próprio sha256sum, como o VERIFY.md manda
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            z.extractall(d)
            p = subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=d, capture_output=True, text=True)
            assert p.returncode == 0 and p.stdout.count(": OK") == len(NOMES) - 1, p.stdout + p.stderr
    # os eventos da T8: cada hash se refaz como o VERIFY.md ensina, e a cadeia inteira foi conferida
    ev = json.loads(arq["events.json"])
    assert ev["chain"]["all_event_hashes_recompute"] and ev["chain"]["whole_event_table_chain_intact_when_exported"]
    for e in ev["events"]:
        canon = json.dumps({k: e[k] for k in ev["chain"]["fields"]}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        assert hashlib.sha256(f"{e['prev_hash'] or ''}|{canon}".encode()).hexdigest() == e["hash"], e["event"]
    nomes = [e["event"] for e in ev["events"]]
    for passo in ("pdf_delivered", "reviewed", "code_sent", "code_verified", "signed", "copy_emailed"):
        assert passo in nomes, (passo, nomes)
    assert [e["phase"] for e in ev["events"] if e["event"] == "signed"] == ["signed"]
    assert list(csv.reader(io.StringIO(arq["events.csv"].decode())))[1:] and \
        [r[2] for r in list(csv.reader(io.StringIO(arq["events.csv"].decode())))[1:]] == nomes, "o CSV tem os mesmos eventos"
    # o modelo é a versão que valia (#116): o mesmo hash da trilha
    trilha = json.loads(arq["audit.json"])
    assert hashlib.sha256(arq["template.pdf"]).hexdigest() == trilha["template_sha256"]
    t = json.loads(arq["template.json"])
    assert t["sha256"] == trilha["template_sha256"] and t["version_id"] == trilha["template_version_id"] and t["matches_signature"]
    assert "signatures" not in t and "current" not in t, "nada que mude com o tempo (o ZIP é determinístico)"


def test_o_hash_do_pdf_e_o_doc_sha256_e_o_do_audit_logs(cli):  # noqa: F811
    wid, _ = _assinada(cli)
    _z, arq = _arquivos(_baixa(cli, wid).content)
    con = conectar()
    w = um(con, "SELECT * FROM waivers WHERE id=?", (wid,))
    sha = hashlib.sha256(arq["signed.pdf"]).hexdigest()
    assert sha == w["doc_sha256"] == hashlib.sha256(open(w["pdf_path"], "rb").read()).hexdigest()
    assert arq["audit.json"].decode() == w["audit"], "a trilha exatamente como está gravada na linha da waiver"
    assert json.loads(arq["audit.json"])["document_sha256"] == sha
    assert json.loads(arq["waiver.json"])["doc_sha256"] == sha
    linhas = json.loads(arq["audit_logs.json"])["rows"]
    eventos = [x["event"] for x in linhas]
    trilha = next(x for x in linhas if x["event"] == "waiver.signed.trail")
    assert trilha["detail"]["document_sha256"] == sha and trilha["entity_id"] == str(wid)
    assert next(x for x in linhas if x["event"] == "portal.waiver.sign")["detail"]["sha256"] == sha
    for ev in ("portal.signup", "portal.email.verified", "portal.code.sent", "portal.waiver.document_view", "portal.driver.create",
               "waiver.copy.emailed"):
        assert ev in eventos, (ev, eventos)
    assert "waiver.evidence_export" not in eventos, "a exportação não entra no pacote (determinístico)"
    assert all(x.get("at_florida", "").endswith(("EDT", "EST")) for x in linhas), "hora da Flórida em cada linha"


def test_o_selo_confere_pela_raiz_do_proprio_zip_e_o_tst_e_o_de_waiver_timestamps(cli):  # noqa: F811
    wid, _ = _assinada(cli)
    _z, arq = _arquivos(_baixa(cli, wid).content)
    con = conectar()
    t = um(con, "SELECT * FROM waiver_timestamps WHERE waiver_id=?", (wid,))
    assert arq["timestamp.tst"] == bytes(t["token"]), "o token exatamente como está em waiver_timestamps"
    assert hashlib.sha256(arq["timestamp.tst"]).hexdigest() == t["token_sha256"] == json.loads(arq["timestamp.json"])["token_sha256"]
    raiz, selo, raiz_tsa = (_cert_x509(arq[n]) for n in ("seal-root.pem", "seal-cert.pem", "tsa/tsa-root.pem"))
    trilha = json.loads(arq["audit.json"])
    assert sw._sha_der(raiz) == trilha["seal"]["root_cert_sha256"]
    assert sw._sha_der(selo) == t["seal_cert_sha256"] == trilha["seal"]["seal_cert_sha256"]
    v = sw.validar(arq["signed.pdf"], raiz=raiz, raizes_tsa_extra=[raiz_tsa])
    assert v["ok"] and v["intact"] and v["coverage"] == "ENTIRE_FILE" and v["timestamp"]["trusted"], v
    mexido = bytearray(arq["signed.pdf"])
    mexido[200] ^= 0x01                                    # dentro do que o selo cobre
    assert not sw.validar(bytes(mexido), raiz=raiz, raizes_tsa_extra=[raiz_tsa])["ok"], "1 byte mudado não confere"
    info = json.loads(arq["timestamp.json"])
    assert info["message_imprint"] == info["seal_signature_value_sha256"], "o carimbo cobre a assinatura do selo"
    assert info["gen_time"] == t["gen_time"] and info["serial"] == t["serial"]
    if shutil.which("openssl"):                             # o passo 3 do VERIFY.md, como está escrito lá
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            _z.extractall(d)
            cmd = next(ln for ln in arq["VERIFY.md"].decode().splitlines() if ln.startswith("openssl ts -verify"))
            p = subprocess.run(cmd.split(), cwd=d, capture_output=True, text=True)
            assert p.returncode == 0 and "Verification: OK" in p.stdout, (cmd, p.stdout, p.stderr)


def test_o_mesmo_registro_da_o_mesmo_zip_byte_a_byte(cli):  # noqa: F811
    wid, _ = _assinada(cli)
    con = conectar()
    a, _ = pw.montar(con, wid)
    b, _ = pw.montar(con, wid)
    assert a == b, "montar duas vezes dá os mesmos bytes"
    r1, r2 = _baixa(cli, wid).content, _baixa(cli, wid).content
    assert r1 == r2 == a, "exportar de novo o mesmo registro dá o mesmo ZIP (a exportação não entra nele)"
    for zi in zipfile.ZipFile(io.BytesIO(r1)).infolist():
        assert zi.date_time == pw.DATA_FIXA, zi.filename


def test_nenhum_arquivo_leva_chave_privada_cookie_token_senha_ou_link_do_convite(cli):  # noqa: F811
    wid, cookies_cliente = _assinada(cli)
    r = _baixa(cli, wid)
    cookies = {**cookies_cliente, **{k: v for k, v in cli.cookies.items()}}
    assert {"cp_session", "cc_session"} <= set(cookies), cookies.keys()
    with open(os.path.join(os.environ["CC_WAIVER_SEAL_DIR"], "seal-key.pem"), "rb") as f:
        chave = f.read()
    corpo = b"".join(re.findall(rb"^[A-Za-z0-9+/=]{40,}$", chave, re.M))
    _z, arq = _arquivos(r.content)
    for nome, dados in arq.items():
        assert b"PRIVATE KEY" not in dados and corpo[:48] not in dados, f"chave privada em {nome}"
        for k, v in cookies.items():
            assert v.encode() not in dados, f"cookie {k} em {nome}"
        for segredo in (CONTA["password"], SENHA):
            assert segredo.encode() not in dados, f"senha em {nome}"
        assert b"/portal/invite/" not in dados, f"link do convite em {nome}"


def _pelo_convite(cli):  # noqa: F811
    """Uma adult assinada pelo convite por e-mail (a waiver nasce no card); devolve (wid, card, token do link)."""
    from command_center.tests.test_convite_waiver import assina as assina_convite, card, manda, token_do_email
    liga(cli)
    cid = card(name="Bruno Teste", email="bruno.teste@example.com", pilot_name=None, pilot_dob="1990-02-02")
    h = equipe(cli)
    assert manda(cli, h, cid, "bruno.teste@example.com").status_code == 201
    token = token_do_email("bruno.teste@example.com")
    assert assina_convite(cli, token).status_code == 201
    return um(conectar(), "SELECT id FROM waivers WHERE client_id=? AND source='urace'", (cid,))["id"], cid, token


def test_pelo_convite_o_pacote_traz_o_convite_e_nunca_o_link(cli):  # noqa: F811
    wid, _cid, token = _pelo_convite(cli)
    _z, arq = _arquivos(_baixa(cli, wid).content)
    eventos = [x["event"] for x in json.loads(arq["audit_logs.json"])["rows"]]
    for ev in ("waiver.invite.sent", "waiver.invite.opened", "waiver.invite.document_view", "waiver.invite.code_sent",
               "waiver.invite.signed", "waiver.signed.trail"):
        assert ev in eventos, (ev, eventos)
    assert "invite_sent" in [e["event"] for e in json.loads(arq["events.json"])["events"]]
    hash_do_token = hashlib.sha256(token.encode()).hexdigest()
    segredo = token.split(".")[0]
    for nome, dados in arq.items():
        assert token.encode() not in dados and segredo.encode() not in dados, f"o link do convite em {nome}"
        assert b"/portal/invite/" not in dados and hash_do_token.encode() not in dados, nome
    assert "invitation link emailed by URACE" in arq["audit.json"].decode()
    assert "a personal one-time invitation link" in arq["declaration-DRAFT.md"].decode()


# ------------------------------------------------------------------ quem exporta
def test_operador_403_cliente_401_docusign_409_e_inexistente_404(cli):  # noqa: F811
    wid, cookies_cliente = _assinada(cli)
    con = conectar()
    auth.criar_usuario(con, "op@urace.us", "Operador", "OPERATOR", SENHA)
    ds = inserir(con, "waivers", signer_name="Ana Docu", signer_email="ana.docu@example.com", template="adult",
                 status="completed", sent_at="2020-01-01T10:00:00Z", completed_at="2020-01-01T10:00:00Z")
    con.commit(); con.close()
    cli.cookies.clear()
    for k, v in cookies_cliente.items():                    # só a sessão do cliente
        if k.startswith("cp_"):
            cli.cookies.set(k, v)
    assert cli.get(f"{API}/waivers/{wid}/evidence.zip").status_code == 401, "o cliente não alcança o pacote"
    equipe(cli, "op@urace.us")
    assert cli.get(f"{API}/waivers/{wid}/evidence.zip").status_code == 403, "operador não exporta"
    equipe(cli, "ger@urace.us")
    r = cli.get(f"{API}/waivers/{ds}/evidence.zip")
    assert r.status_code == 409 and "DocuSign" in r.json()["detail"]
    assert cli.get(f"{API}/waivers/999999/evidence.zip").status_code == 404
    assert cli.get(f"{API}/waivers/0/evidence.zip").status_code == 422
    con = conectar()
    assert not todos(con, "SELECT id FROM audit_logs WHERE event='waiver.evidence_export'"), "nada exportado, nada registrado"
    assert not todos(con, "SELECT id FROM waiver_events WHERE event='evidence_exported'")


def test_pdf_que_nao_bate_com_o_hash_nao_exporta(cli):  # noqa: F811
    wid, _ = _assinada(cli)
    con = conectar()
    w = um(con, "SELECT * FROM waivers WHERE id=?", (wid,))
    os.chmod(w["pdf_path"], 0o600)
    with open(w["pdf_path"], "ab") as f:
        f.write(b"\n% mexido")
    equipe(cli, "ger@urace.us")
    r = cli.get(f"{API}/waivers/{wid}/evidence.zip")
    assert r.status_code == 409 and "não bate com o hash" in r.json()["detail"]
    assert not todos(conectar(), "SELECT id FROM audit_logs WHERE event='waiver.evidence_export'")


def test_a_exportacao_fica_auditada_e_na_trilha_com_o_hash_do_zip(cli):  # noqa: F811
    wid, _ = _assinada(cli)
    r = _baixa(cli, wid)
    sha = hashlib.sha256(r.content).hexdigest()
    con = conectar()
    a = todos(con, "SELECT * FROM audit_logs WHERE event='waiver.evidence_export'")
    assert len(a) == 1 and a[0]["entity_type"] == "waiver" and a[0]["entity_id"] == str(wid)
    d = json.loads(a[0]["detail"])
    assert d["zip_sha256"] == sha and d["zip_bytes"] == len(r.content) and d["by"] == "Gerente" and d["files"] == NOMES
    assert d["commit"] is None or re.fullmatch(r"[0-9a-f]{7,40}", d["commit"])
    e = todos(con, "SELECT * FROM waiver_events WHERE event='evidence_exported'")
    assert len(e) == 1 and e[0]["waiver_id"] == wid and e[0]["flow"] == "staff"
    assert json.loads(e[0]["detail"])["zip_sha256"] == sha and d["event_id"] == e[0]["id"]
    assert tw.verificar(con)["ok"], "a cadeia continua íntegra"
    # a trilha do painel mostra a exportação, depois de assinar
    trilha = cli.get(f"{API}/site/waiver-nativa/{wid}/eventos").json()["eventos"]
    assert [x["phase"] for x in trilha if x["event"] == "evidence_exported"] == ["after"]


# ------------------------------------------------------------------ textos
def test_a_declaracao_e_rascunho_para_o_advogado_e_a_descricao_leva_o_commit(cli):  # noqa: F811
    wid, _ = _assinada(cli)
    _z, arq = _arquivos(_baixa(cli, wid).content)
    dec = arq["declaration-DRAFT.md"].decode()
    assert dec.startswith("# DRAFT — FOR ATTORNEY REVIEW — NOT TO BE SIGNED\n"), dec[:80]
    assert "not to be signed" in dec.lower().split("\n", 3)[2]
    w = um(conectar(), "SELECT * FROM waivers WHERE id=?", (wid,))
    for trecho in (pw.CUSTODIANTE, "902(11)", "902(13)", "§90.902(11)", w["doc_sha256"], "Maria Santos", "Leo Santos",
                   f"record **{wid}**", "[ATTORNEY"):
        assert trecho in dec, trecho
    desc = arq["system-description.md"].decode()
    with open(pw.DOC_SISTEMA, encoding="utf-8") as f:
        doc = f.read()
    assert desc.endswith(doc), "a descrição do sistema é o docs/waiver-esign-system.md"
    from command_center.api import sistema
    commit = sistema.versao()["commit"]
    assert f"commit `{commit or 'unknown'}`" in desc
    ver = arq["VERIFY.md"].decode()
    for trecho in ("sha256sum -c SHA256SUMS", "pyhanko sign validate", "selo-waiver conferir signed.pdf --raiz seal-root.pem",
                   "openssl ts -verify -in timestamp.tst -token_in", w["doc_sha256"]):
        assert trecho in ver, trecho


def test_o_documento_do_sistema_cobre_o_que_a_issue_pede():
    with open(pw.DOC_SISTEMA, encoding="utf-8") as f:
        doc = f.read().lower()
    for assunto in ("screens", "authentication", "ntp", "sha-256", "pades", "rfc 3161", "where", "append-only", "trigger",
                    "backup", "who can access", "retention", "custodian", "x-forwarded-for", pw.CUSTODIANTE.lower()):
        assert assunto in doc, assunto


# ------------------------------------------------------------------ anulada e o que veio depois de assinar
def test_a_anulada_tambem_exporta_com_a_anulacao_e_o_depois_no_certificado_avulso(cli):  # noqa: F811
    wid, _ = _assinada(cli)
    h = equipe(cli, "ger@urace.us")
    assert cli.get(f"{API}/waivers/{wid}/download").status_code == 200          # PDF baixado pela equipe
    r = cli.post(f"{API}/waivers/{wid}/void", json={"reason": "assinada com o nascimento errado do piloto"}, headers=h)
    assert r.status_code == 200, r.text
    _z, arq = _arquivos(_baixa(cli, wid).content)
    ev = json.loads(arq["events.json"])["events"]
    depois = [e["event"] for e in ev if e["phase"] == "after"]
    for passo in ("copy_emailed", "downloaded", "voided"):
        assert passo in depois, (passo, depois)
    cert = _cert(arq["certificate-of-completion.pdf"])
    for trecho in ("STATUS: VOIDED BY URACE", "assinada com o nascimento errado do piloto", "Voided by URACE",
                   "Signed copy emailed to the signer", "Signed PDF downloaded", "after signing", "before signing",
                   "Event history (Florida time", "UTC", hashlib.sha256(arq["signed.pdf"]).hexdigest()):
        assert trecho in cert, trecho
    assert re.search(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d E[DS]T", cert), "hora da Flórida"
    assert json.loads(arq["waiver.json"])["voided"]["reason"] == "assinada com o nascimento errado do piloto"
    assert "waiver.void" in [x["event"] for x in json.loads(arq["audit_logs.json"])["rows"]]
    assert "voided this waiver" in arq["declaration-DRAFT.md"].decode()
    assert "Evidence package exported" not in cert, "a exportação não entra no certificado (determinístico)"


def test_a_conferencia_no_balcao_entra_no_certificado_avulso(cli):  # noqa: F811
    wid, cid, _ = _pelo_convite(cli)
    con = conectar()
    auth.criar_usuario(con, "op@urace.us", "Operador", "OPERATOR", SENHA)
    con.commit(); con.close()
    h = equipe(cli, "op@urace.us")
    r = cli.post(f"{API}/balcao/waivers/{wid}/id-check", json={"client_id": cid, "document_type": "drivers_license",
                                                               "name_matches": True}, headers=h)
    assert r.status_code == 201, r.text
    _z, arq = _arquivos(_baixa(cli, wid).content)
    cert = _cert(arq["certificate-of-completion.pdf"])
    assert "Photo ID checked at the track" in cert and "drivers_license" in cert and "after signing" in cert
    assert "waiver.id_check" in [x["event"] for x in json.loads(arq["audit_logs.json"])["rows"]]
    assert "id_checked" in [e["event"] for e in json.loads(arq["events.json"])["events"] if e["phase"] == "after"]


def test_o_certificado_avulso_com_muitos_eventos_muda_de_pagina(cli):  # noqa: F811
    from pypdf import PdfReader
    wid, _ = _assinada(cli)
    con = conectar()
    w = um(con, "SELECT * FROM waivers WHERE id=?", (wid,))
    for i in range(40):
        tw.registrar(con, "downloaded", "staff", detail={"by": f"Gerente {i}"}, waiver_id=wid, kind=w["template"])
    con.commit()
    z, _ = pw.montar(con, wid)
    cert = zipfile.ZipFile(io.BytesIO(z)).read("certificate-of-completion.pdf")
    paginas = PdfReader(io.BytesIO(cert)).pages
    assert len(paginas) >= 3
    texto = _cert(cert)
    assert "Gerente 39" in texto and "(continued)" in texto and "Integrity of the event trail" in texto


def test_depois_de_trocar_o_selo_a_raiz_vem_de_dentro_do_pdf_assinado(cli, monkeypatch):  # noqa: F811
    """A pasta do selo com outra raiz (selo trocado depois): o `seal-root.pem` do pacote é a raiz que selou ESTE PDF,
    tirada do próprio PDF pela impressão gravada na assinatura, e o selo confere por ela."""
    wid, _ = _assinada(cli)
    monkeypatch.setattr(sw, "_raiz_guardada", lambda: None)
    z, _ = pw.montar(conectar(), wid)
    _z, arq = _arquivos(z)
    trilha = json.loads(arq["audit.json"])
    raiz = _cert_x509(arq["seal-root.pem"])
    assert sw._sha_der(raiz) == trilha["seal"]["root_cert_sha256"]
    assert sw.validar(arq["signed.pdf"], raiz=raiz, raizes_tsa_extra=[_cert_x509(arq["tsa/tsa-root.pem"])])["ok"]
