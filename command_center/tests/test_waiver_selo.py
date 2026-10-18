"""Selo PAdES e carimbo de tempo RFC 3161 no PDF da waiver nativa (#110, lacunas D-2 e G-3).

Feito quando (issue): o validador do pyHanko aceita o PDF (com TSA falsa local); alterar 1 byte invalida o selo; sem
chave configurada, a assinatura não acontece e a tela dá uma mensagem clara. E mais: `doc_sha256` é o hash do arquivo
selado; o token do carimbo fica numa tabela append-only; com a TSA fora, 503, nada gravado e o código do e-mail
continua valendo; ligar exige o selo. As chaves são de TESTE, geradas na hora (nada no repositório)."""
import hashlib
import io
import json
import os
import sqlite3
import stat
from datetime import timezone

import pytest

from command_center.db import conectar, todos, um
from command_center.providers import selo_waiver as sw
from command_center.tests import selo_teste
from command_center.tests.test_waiver_nativa import (  # noqa: F401 (cli é fixture)
    P, S, _assinatura, cli, cliente, confirma_email, equipe, liga, ultimo_codigo)

MENSAGEM = "Online signing is temporarily unavailable"


def _vc():
    """Confia na raiz do selo de teste e na raiz da TSA falsa, como quem confere o PDF com a raiz pública da URACE."""
    from cryptography import x509
    from pyhanko_certvalidator import ValidationContext
    with open(os.path.join(os.environ["CC_WAIVER_SEAL_DIR"], "root-cert.pem"), "rb") as f:
        raiz = x509.load_pem_x509_certificate(f.read())
    return ValidationContext(trust_roots=[sw._asn1(raiz), sw._asn1(selo_teste.raiz_tsa())], allow_fetching=False)


def _valida(pdf):
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    (s,) = PdfFileReader(io.BytesIO(pdf)).embedded_signatures
    return s, validate_pdf_signature(s, signer_validation_context=_vc(), ts_validation_context=_vc())


def _corpo(**mais):
    from datetime import datetime, timezone
    return {"typed_name": "Maria Santos", "signature": _assinatura(), "read_and_agree": True, "consent_esign": True,
            "english_understood": True, "relationship": "mother", "guardian_declaration": True,
            "document_read_at": datetime.now(timezone.utc).isoformat(), "document_read_mode": "pdf_viewer", **mais}


def _ate_o_clique_final(cli, hc, pid):  # noqa: F811
    """Como a tela, até antes do clique final: lê o PDF, revisa (passo 1) e pede o código do e-mail."""
    cli.get(f"{P}/waivers/model/parental/pdf")
    email = confirma_email(cli, hc)
    corpo = _corpo()
    r = cli.post(f"{P}/drivers/{pid}/waiver/review", json=corpo, headers=hc)
    assert r.status_code == 201, r.text
    assert cli.post(f"{P}/waivers/code", headers=hc).status_code == 200
    return {**corpo, "review_id": r.json()["review_id"], "sign_code": ultimo_codigo(email)}


def _assinados():
    return sorted(n for n in os.listdir(os.environ["CC_WAIVERS_DIR"]) if n.startswith("urace-"))


def _nada_gravado(con):
    assert um(con, "SELECT COUNT(*) AS n FROM waivers WHERE source='urace'")["n"] == 0
    assert um(con, "SELECT COUNT(*) AS n FROM waiver_timestamps")["n"] == 0
    assert not todos(con, "SELECT id FROM waiver_events WHERE event='signed'")
    assert not _assinados(), "nenhum PDF assinado no disco"


# ------------------------------------------------------------------ o PDF selado
def test_o_pdf_assinado_sai_selado_com_carimbo_e_o_pyhanko_valida(cli):  # noqa: F811
    liga(cli)
    hc, (pid,) = cliente(cli)
    r = cli.post(f"{P}/drivers/{pid}/waiver", json=_ate_o_clique_final(cli, hc, pid), headers=hc)
    assert r.status_code == 201, r.text
    con = conectar()
    w = um(con, "SELECT * FROM waivers WHERE id=?", (r.json()["waiver_id"],))
    pdf = open(w["pdf_path"], "rb").read()
    assert hashlib.sha256(pdf).hexdigest() == w["doc_sha256"], "o hash guardado é o do arquivo selado"
    s, st = _valida(pdf)
    assert s.field_name == "URACE-Seal"
    assert st.intact and st.valid and st.trusted and st.bottom_line, st.summary()
    assert st.coverage.name == "ENTIRE_FILE" and s.docmdp_level.name == "NO_CHANGES", "certificação: nenhuma alteração"
    assert st.timestamp_validity is not None, "PAdES-B-T: o carimbo da TSA vai dentro da assinatura"
    ts = st.timestamp_validity
    assert ts.intact and ts.valid and ts.trusted
    # a trilha (na linha da waiver e na auditoria) guarda o selo; o token fica também na tabela própria
    selo = json.loads(w["audit"])["seal"]
    assert selo["standard"] == "PAdES-B-T" and selo["tsa_url"] == "urn:test:tsa-falsa"
    assert selo["gen_time"] == ts.timestamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "a hora é a da TSA"
    assert selo["seal_cert_sha256"] == sw.estado()["seal_sha256"] and selo["root_cert_sha256"] == sw.estado()["root_sha256"]
    t = um(con, "SELECT * FROM waiver_timestamps WHERE waiver_id=?", (w["id"],))
    assert t and t["signature_id"] == json.loads(w["audit"])["signature_id"] and t["document_sha256"] == w["doc_sha256"]
    assert hashlib.sha256(t["token"]).hexdigest() == t["token_sha256"] == selo["token_sha256"]
    assert t["gen_time"] == selo["gen_time"] and t["serial"] == selo["serial"]
    dentro = [a["values"][0].dump() for a in s.signer_info["unsigned_attrs"] if a["type"].native == "signature_time_stamp_token"]
    assert dentro == [t["token"]], "o token guardado é o mesmo que está dentro do PDF"
    trilha = json.loads(um(con, "SELECT detail FROM audit_logs WHERE event='waiver.signed.trail'")["detail"])
    assert trilha["seal"] == selo and trilha["document_sha256"] == w["doc_sha256"]
    # o selo é o próprio validador da URACE também (o que `selo-waiver conferir` usa)
    assert sw.validar(pdf, raizes=[selo_teste.raiz_tsa()])["ok"] is True
    from command_center.tests.test_waiver_nativa import certificado
    assert "RFC 3161 time-stamping authority" in certificado(w["pdf_path"])
    # a lista de Site › Waiver mostra quando foi carimbada
    equipe(cli)
    a = cli.get(f"{S}/waiver-nativa").json()["assinadas"]["itens"][0]
    assert a["sealed_at"] == selo["gen_time"] and a["seal_tsa"] == "urn:test:tsa-falsa"


def test_um_byte_mudado_quebra_o_selo():
    pdf = sw.pdf_de_teste()
    selado, _info, _tok = sw.selar(pdf)
    s, st = _valida(selado)
    assert st.intact and st.bottom_line
    i = selado.index(b"stream", 20) + 30                  # dentro do conteúdo da página, coberto pela assinatura
    assert s.byte_range[0] <= i < s.byte_range[1]
    ruim = bytearray(selado)
    ruim[i] ^= 0x01
    _s, st2 = _valida(bytes(ruim))
    assert not st2.intact and not st2.bottom_line
    assert sw.validar(bytes(ruim), raizes=[selo_teste.raiz_tsa()])["ok"] is False


def test_a_tabela_do_carimbo_e_append_only(cli):  # noqa: F811
    liga(cli)
    hc, (pid,) = cliente(cli)
    assert cli.post(f"{P}/drivers/{pid}/waiver", json=_ate_o_clique_final(cli, hc, pid), headers=hc).status_code == 201
    con = conectar()
    for sql in ("UPDATE waiver_timestamps SET gen_time='2020-01-01T00:00:00Z'", "UPDATE waiver_timestamps SET token=x'00'",
                "DELETE FROM waiver_timestamps"):
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            con.execute(sql)
    assert um(con, "SELECT COUNT(*) AS n FROM waiver_timestamps")["n"] == 1


# ------------------------------------------------------------------ sem selo ou sem TSA: 503, nada gravado
def test_sem_chave_nao_assina_da_503_claro_e_o_codigo_continua_valendo(cli, tmp_path, monkeypatch):  # noqa: F811
    liga(cli)
    hc, (pid,) = cliente(cli)
    corpo = _ate_o_clique_final(cli, hc, pid)
    con = conectar()
    real = os.environ["CC_WAIVER_SEAL_DIR"]
    monkeypatch.setenv("CC_WAIVER_SEAL_DIR", str(tmp_path / "sem-selo"))     # a chave sumiu do servidor
    r = cli.post(f"{P}/drivers/{pid}/waiver", json=corpo, headers=hc)
    assert r.status_code == 503 and r.json()["detail"].startswith(MENSAGEM) and "in person" in r.json()["detail"]
    assert "seal-key.pem" not in r.json()["detail"], "o caminho da chave não vai para o cliente"
    _nada_gravado(con)
    assert um(con, "SELECT used_at FROM portal_codes WHERE purpose='waiver_sign' ORDER BY id DESC LIMIT 1")["used_at"] is None
    assert not todos(con, "SELECT id FROM waiver_events WHERE event='code_verified'"), "o código nem chegou a ser conferido"
    f = um(con, "SELECT * FROM audit_logs WHERE event='waiver.seal_failed' ORDER BY id DESC LIMIT 1")
    assert f and json.loads(f["detail"])["stage"] == "sign" and "seal-key.pem" in json.loads(f["detail"])["reason"]
    # a revisão também avisa antes (ninguém chega ao clique final para dar 503)
    r = cli.post(f"{P}/drivers/{pid}/waiver/review", json=_corpo(), headers=hc)
    assert r.status_code == 503 and r.json()["detail"].startswith(MENSAGEM)
    # a chave voltou: o MESMO código e a mesma revisão assinam
    monkeypatch.setenv("CC_WAIVER_SEAL_DIR", real)
    r = cli.post(f"{P}/drivers/{pid}/waiver", json=corpo, headers=hc)
    assert r.status_code == 201, r.text


def test_tsa_fora_do_ar_da_503_nada_gravado_e_o_codigo_nao_se_perde(cli, monkeypatch):  # noqa: F811
    liga(cli)
    hc, (pid,) = cliente(cli)
    corpo = _ate_o_clique_final(cli, hc, pid)
    monkeypatch.setattr(sw, "_carimbadores", lambda: [("http://tsa-1.example.com", selo_teste.TsaQueFalha().carimbador),
                                                      ("http://tsa-2.example.com", selo_teste.TsaQueFalha().carimbador)])
    r = cli.post(f"{P}/drivers/{pid}/waiver", json=corpo, headers=hc)
    assert r.status_code == 503 and r.json()["detail"].startswith(MENSAGEM)
    con = conectar()
    _nada_gravado(con)
    assert um(con, "SELECT used_at FROM portal_codes WHERE purpose='waiver_sign' ORDER BY id DESC LIMIT 1")["used_at"] is None
    assert um(con, "SELECT used_at FROM waiver_reviews ORDER BY id DESC LIMIT 1")["used_at"] is None
    f = json.loads(um(con, "SELECT detail FROM audit_logs WHERE event='waiver.seal_failed' ORDER BY id DESC LIMIT 1")["detail"])
    assert f["flow"] == "account" and "tsa-1.example.com" in f["reason"] and "tsa-2.example.com" in f["reason"]
    # a TSA voltou: o mesmo código assina
    monkeypatch.setattr(sw, "_carimbadores", lambda: [("urn:test:tsa-falsa", selo_teste.tsa())])
    r = cli.post(f"{P}/drivers/{pid}/waiver", json=corpo, headers=hc)
    assert r.status_code == 201, r.text
    assert um(con, "SELECT COUNT(*) AS n FROM waiver_timestamps")["n"] == 1


def test_pelo_convite_tsa_fora_da_503_e_o_codigo_do_convite_continua(cli, monkeypatch):  # noqa: F811
    from command_center.tests import test_convite_waiver as tc
    liga(cli)
    cid = tc.card(name="Bruno Adulto", email="bruno@example.com", pilot_name=None, pilot_dob="1990-02-02")
    h = equipe(cli)
    assert tc.manda(cli, h, cid, "bruno@example.com").status_code == 201
    token = tc.token_do_email("bruno@example.com")
    monkeypatch.setattr(sw, "_carimbadores", lambda: [("http://tsa-1.example.com", selo_teste.TsaQueFalha().carimbador)])
    r = tc.assina(cli, token)
    assert r.status_code == 503 and r.json()["detail"].startswith(MENSAGEM)
    con = conectar()
    _nada_gravado(con)
    assert um(con, "SELECT used_at FROM waiver_invite_codes ORDER BY id DESC LIMIT 1")["used_at"] is None
    assert um(con, "SELECT used_at FROM waiver_invites WHERE client_id=?", (cid,))["used_at"] is None, "o link continua valendo"
    a = um(con, "SELECT * FROM audit_logs WHERE event='waiver.seal_failed' ORDER BY id DESC LIMIT 1")
    assert a["entity_type"] == "client" and a["entity_id"] == str(cid) and json.loads(a["detail"])["flow"] == "invite"
    assert token not in a["detail"], "o link nunca vai para a auditoria"
    monkeypatch.setattr(sw, "_carimbadores", lambda: [("urn:test:tsa-falsa", selo_teste.tsa())])
    r = tc.assina(cli, token, sign_code=tc.codigo_do_email("bruno@example.com"))
    assert r.status_code == 201, r.text


# ------------------------------------------------------------------ ligar e Site › Waiver
def test_ligar_exige_o_selo_e_site_waiver_mostra_o_estado(cli, tmp_path, monkeypatch):  # noqa: F811
    h = equipe(cli)
    assert cli.post(f"{S}/waiver-nativa/importar", headers=h).status_code == 200
    real = os.environ["CC_WAIVER_SEAL_DIR"]
    monkeypatch.setenv("CC_WAIVER_SEAL_DIR", str(tmp_path / "selo"))
    d = cli.get(f"{S}/waiver-nativa").json()["selo"]
    assert d["configured"] is False and "selo-waiver criar" in d["reason"]
    r = cli.post(f"{S}/waiver-nativa/ligar", json={"ligada": True}, headers=h)
    assert r.status_code == 409 and "selo" in r.json()["detail"]
    assert cli.get(f"{S}/waiver-nativa").json()["ligada"] is False
    monkeypatch.setenv("CC_WAIVER_SEAL_DIR", real)
    d = cli.get(f"{S}/waiver-nativa").json()["selo"]
    assert d["configured"] is True and len(d["root_sha256"]) == 64 and d["field"] == "URACE-Seal"
    assert cli.post(f"{S}/waiver-nativa/ligar", json={"ligada": True}, headers=h).json()["ligada"] is True
    # desligar não depende do selo
    monkeypatch.setenv("CC_WAIVER_SEAL_DIR", str(tmp_path / "selo"))
    assert cli.post(f"{S}/waiver-nativa/ligar", json={"ligada": False}, headers=h).json()["ligada"] is False


# ------------------------------------------------------------------ criar, conferir e a lista de TSAs
def test_criar_nunca_sobrescreve_e_a_chave_fica_so_para_o_dono(tmp_path):
    onde = tmp_path / "selo"
    r = sw.criar(str(onde))
    assert sorted(os.listdir(onde)) == ["root-cert.pem", "seal-cert.pem", "seal-key.pem"], "a chave da raiz não é guardada"
    assert stat.S_IMODE(os.stat(onde / "seal-key.pem").st_mode) == 0o600
    assert stat.S_IMODE(os.stat(onde).st_mode) == 0o700
    antes = {n: (onde / n).read_bytes() for n in os.listdir(onde)}
    with pytest.raises(FileExistsError, match="Nada foi mudado"):
        sw.criar(str(onde))
    assert {n: (onde / n).read_bytes() for n in os.listdir(onde)} == antes
    e = sw.estado(str(onde))
    assert e["configured"] and e["root_sha256"] == r["root_sha256"] and e["seal_sha256"] == r["seal_sha256"]
    os.chmod(onde / "seal-key.pem", 0o644)
    assert not sw.estado(str(onde))["configured"] and "chmod 600" in sw.estado(str(onde))["reason"]
    os.chmod(onde / "seal-key.pem", 0o600)
    # uma só das três peças também não se cria por cima
    (onde / "seal-key.pem").unlink()
    with pytest.raises(FileExistsError):
        sw.criar(str(onde))
    assert not sw.estado(str(onde))["configured"]


def test_a_chave_ou_a_raiz_de_outro_selo_nao_servem(tmp_path):
    import shutil
    a, b, c = tmp_path / "a", tmp_path / "b", tmp_path / "c"
    sw.criar(str(a)); sw.criar(str(b))
    shutil.copytree(a, c)
    shutil.copyfile(b / "seal-key.pem", a / "seal-key.pem")          # a chave de outro selo
    assert "não é a do certificado" in sw.estado(str(a))["reason"]
    os.chmod(c / "root-cert.pem", 0o644)
    shutil.copyfile(b / "root-cert.pem", c / "root-cert.pem")        # a raiz de outro selo
    assert "não foi emitido pela raiz" in sw.estado(str(c))["reason"]
    with pytest.raises(sw.SeloIndisponivel):
        sw._carregar(str(c))


def test_as_tsas_vem_da_lista_e_a_que_esta_fora_passa_para_a_proxima(monkeypatch):
    monkeypatch.delenv("CC_WAIVER_TSA", raising=False)
    assert sw.tsas() == ["http://timestamp.digicert.com", "https://freetsa.org/tsr"], "padrão: DigiCert e depois FreeTSA"
    monkeypatch.setattr(sw, "_carimbadores", selo_teste.carimbadores_reais())
    assert all(c.timeout == 10 for _u, c in sw._carimbadores()), "10 s por TSA"
    import socket
    s = socket.socket(); s.bind(("127.0.0.1", 0)); fechada = s.getsockname()[1]; s.close()
    tsa = selo_teste.TsaFalsa()
    try:
        monkeypatch.setenv("CC_WAIVER_TSA", f" http://127.0.0.1:{fechada}/tsr , {tsa.url}")
        selado, info, tok = sw.selar(sw.pdf_de_teste())
        assert info["tsa_url"] == tsa.url and tsa.pedidos == 1, "um pedido só por selo (sem o de estimar tamanho)"
        assert sw.validar(selado, raizes=[selo_teste.raiz_tsa()])["ok"]
        monkeypatch.setenv("CC_WAIVER_TSA", f"http://127.0.0.1:{fechada}/tsr")
        with pytest.raises(sw.SeloIndisponivel, match="nenhuma TSA"):
            sw.selar(sw.pdf_de_teste())
    finally:
        tsa.parar()


def test_manage_selo_waiver_criar_e_conferir(tmp_path, monkeypatch, capsys):
    from command_center import manage
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    monkeypatch.setenv("CC_WAIVER_SEAL_DIR", str(tmp_path / "selo"))
    monkeypatch.setattr(sw, "_carimbadores", selo_teste.carimbadores_reais())
    assert manage.main(["manage", "selo-waiver", "conferir"]) == 1
    assert "selo não configurado" in capsys.readouterr().out
    assert manage.main(["manage", "selo-waiver", "criar"]) == 0
    saida = capsys.readouterr().out
    assert sw.impressao(sw.estado()["root_sha256"]) in saida and "GUARDE UMA CÓPIA" in saida
    assert manage.main(["manage", "selo-waiver", "criar"]) == 1
    assert "Nada foi mudado" in capsys.readouterr().out
    tsa = selo_teste.TsaFalsa()
    try:
        monkeypatch.setenv("CC_WAIVER_TSA", tsa.url)
        assert manage.main(["manage", "selo-waiver", "conferir"]) == 0
        saida = capsys.readouterr().out
        assert "selo e carimbo conferem" in saida and "NTP ok" in saida and tsa.url in saida
        # o selo de um PDF já assinado, e o mesmo com 1 byte mudado
        selado, _i, _t = sw.selar(sw.pdf_de_teste())
        (tmp_path / "ok.pdf").write_bytes(selado)
        ruim = bytearray(selado); ruim[selado.index(b"stream", 20) + 30] ^= 1
        (tmp_path / "ruim.pdf").write_bytes(bytes(ruim))
        assert manage.main(["manage", "selo-waiver", "conferir", str(tmp_path / "ok.pdf")]) == 0
        assert "o arquivo não mudou desde a assinatura" in capsys.readouterr().out
        assert manage.main(["manage", "selo-waiver", "conferir", str(tmp_path / "ruim.pdf")]) == 1
        assert "íntegro=False" in capsys.readouterr().out
    finally:
        tsa.parar()
    con = conectar()
    assert um(con, "SELECT 1 AS x FROM audit_logs WHERE event='waiver.seal_created'")
