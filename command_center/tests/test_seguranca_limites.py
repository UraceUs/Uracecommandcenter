"""#485: limites do login da área do cliente e dos formulários do site, achados na revisão de segurança de 29/10."""
import json
import os

import pytest

os.environ.setdefault("CC_AUTOSYNC", "0")

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api import auth, vitrine  # noqa: E402
from command_center.api.main import app  # noqa: E402
from command_center.db import aplicar_schema, conectar  # noqa: E402
from command_center.tests.test_stripe_loja import _comprar, _conta, _simples, amb  # noqa: E402,F401

SITE = "https://novo.urace.us"


@pytest.fixture()
def cli(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path))
    monkeypatch.setenv("CC_EMAIL_FAKE", str(tmp_path / "emails.jsonl"))
    monkeypatch.delenv("CC_SITE_HOSTS", raising=False)
    vitrine._envios.clear()
    # o IP de cada requisição vem do cabeçalho de teste (o servidor só confia no X-Forwarded-For do proxy)
    monkeypatch.setattr(auth, "_ip", lambda request: request.headers.get("x-teste-ip", "198.51.100.1"))
    with TestClient(app, base_url=SITE) as t:
        yield t


def _emails(tmp_path):
    caixa = tmp_path / "emails.jsonl"
    return [json.loads(x) for x in caixa.read_text(encoding="utf-8").splitlines()] if caixa.exists() else []


def _login(cli, ip, senha):
    return cli.post("/ops/api/portal/login", json={"email": "ana@exemplo.com", "password": senha}, headers={"x-teste-ip": ip})


def test_senha_errada_de_outro_lugar_nao_trava_o_dono_da_conta(cli):
    _conta(cli)
    cli.post("/ops/api/portal/logout")
    for _ in range(5):
        assert _login(cli, "203.0.113.9", "errada-123").status_code == 401
    assert _login(cli, "203.0.113.9", "errada-123").status_code == 429, "a conexão que errou fica travada"
    assert _login(cli, "198.51.100.7", "pista-molhada-7").status_code == 200, "o dono, de outro lugar, entra"
    # o mesmo /64 do IPv6 é a mesma conexão
    for i in range(5):
        _login(cli, f"2001:db8:1:2::{i:x}", "errada-123")
    assert _login(cli, "2001:db8:1:2::ffff", "pista-molhada-7").status_code == 429


def test_tentativa_espalhada_no_mesmo_email_trava_no_teto_geral(cli, monkeypatch):
    from command_center.api import portal
    monkeypatch.setattr(portal, "MAX_FALHAS_EMAIL_GERAL", 6)
    _conta(cli)
    cli.post("/ops/api/portal/logout")
    for i in range(6):
        _login(cli, f"203.0.113.{i + 10}", "errada-123")
    assert _login(cli, "198.51.100.7", "pista-molhada-7").status_code == 429


def _contato(cli, ip, email, nome="Ana Lima"):
    return cli.post("/ops/api/vitrine/contato", json={"nome": nome, "email": email, "mensagem": "When can I drive?"},
                    headers={"x-teste-ip": ip})


def test_formulario_conta_o_bloco_64_do_ipv6(cli):
    respostas = [_contato(cli, f"2001:db8:aa:bb::{i:x}", f"p{i}@exemplo.com").status_code for i in range(10)]
    assert respostas[:8] == [200] * 8 and respostas[8:] == [400, 400]


def test_teto_geral_de_confirmacoes_o_lead_entra_e_o_email_nao_sai(cli, tmp_path, monkeypatch):
    monkeypatch.setattr(vitrine, "_MAX_CONFIRMACOES_HORA", 2)
    for i in range(3):
        assert _contato(cli, f"203.0.113.{i}", f"p{i}@exemplo.com").json() == {"ok": True}
    con = conectar(); aplicar_schema(con)
    assert con.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0] == 3, "todo lead entra em Vendas"
    para = [m["to"] for m in _emails(tmp_path)]
    assert para.count("support@urace.us") == 3 and sorted(x for x in para if x != "support@urace.us") == ["p0@exemplo.com", "p1@exemplo.com"]


def test_confirmacao_so_cumprimenta_pelo_nome_quando_e_nome(cli, tmp_path):
    _contato(cli, "203.0.113.1", "a@exemplo.com", nome="https://phishing.example/login Lima")
    _contato(cli, "203.0.113.2", "b@exemplo.com", nome="José Lima")
    textos = {m["to"]: m["text"] for m in _emails(tmp_path) if m["to"] != "support@urace.us"}
    assert textos["a@exemplo.com"].startswith("Hi there,") and "phishing" not in textos["a@exemplo.com"]
    assert textos["b@exemplo.com"].startswith("Hi José,")


def test_buy_now_vindo_de_outro_site_e_recusado(amb):  # noqa: F811
    cli, con, *_ = amb
    _conta(cli)
    p = _simples()
    r = cli.post("/ops/api/vitrine/checkout", data={"produto": p["slug"], "quantidade": "1", "entrega": "retirada"},
                 headers={"Origin": "https://outro.example"}, follow_redirects=False)
    assert r.status_code == 403
    assert con.execute("SELECT COUNT(*) FROM store_orders").fetchone()[0] == 0
    assert _comprar(cli, p).status_code == 303, "sem Origin continua comprando"
    # o navegador manda "null" no formulário do próprio site (Referrer-Policy: no-referrer): tem que comprar
    r = cli.post("/ops/api/vitrine/checkout", data={"produto": p["slug"], "quantidade": "1", "entrega": "retirada"},
                 headers={"Origin": "null"}, follow_redirects=False)
    assert r.status_code == 303 and "checkout.stripe.com" in r.headers["location"]
