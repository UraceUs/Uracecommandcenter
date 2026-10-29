"""Troca do domínio (#462): no dia em que o urace.us apontar para a VPS, o Caddy entrega urace.us e
www.urace.us ao site (não ao painel), e `CC_SITE_PRINCIPAL=urace.us` leva www. e novo. para urace.us (301)."""
import os
import re
import subprocess
import sys

import pytest

os.environ.setdefault("CC_AUTOSYNC", "0")

from fastapi.testclient import TestClient  # noqa: E402

from command_center import enderecos  # noqa: E402
from command_center.api.main import app  # noqa: E402

TRES = "urace.us,www.urace.us,novo.urace.us"
SCRIPT = os.path.join(os.path.dirname(__file__), "..", "..", "adminai", "deploy", "command_center", "servir_command_center.sh")


@pytest.fixture()
def cli(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path))
    monkeypatch.setenv("CC_SITE_HOSTS", TRES)
    monkeypatch.delenv("CC_SITE_PRINCIPAL", raising=False)
    with TestClient(app, base_url="https://urace.us", follow_redirects=False) as t:
        yield t


def _get(cli, host, caminho):
    return cli.get(caminho, headers={"host": host})


def test_sem_principal_nada_redireciona(cli):
    """A prévia de hoje: sem a variável, cada nome responde a própria página."""
    for host in ("urace.us", "www.urace.us", "novo.urace.us"):
        assert _get(cli, host, "/").status_code == 200, host


def test_www_e_novo_levam_a_urace_us_com_o_caminho_e_a_query(cli, monkeypatch):
    monkeypatch.setenv("CC_SITE_PRINCIPAL", "urace.us")
    r = _get(cli, "www.urace.us", "/store/?s=wheel&orderby=price")
    assert r.status_code == 301 and r.headers["location"] == "https://urace.us/store/?s=wheel&orderby=price"
    r = _get(cli, "novo.urace.us", "/services/arrive-and-drive/")
    assert r.status_code == 301 and r.headers["location"] == "https://urace.us/services/arrive-and-drive/"
    assert r.headers["x-content-type-options"] == "nosniff", "o 301 passa pelos cabeçalhos da casa"
    # a área do cliente também (o mesmo login num nome só)
    r = _get(cli, "novo.urace.us", "/ops/portal")
    assert r.status_code == 301 and r.headers["location"] == "https://urace.us/ops/portal"
    # o principal abre a página
    assert _get(cli, "urace.us", "/").status_code == 200


def test_api_e_formulario_nao_redirecionam(cli, monkeypatch):
    """A página aberta antes da troca continua falando com o próprio nome: a API e o POST não mudam de endereço."""
    monkeypatch.setenv("CC_SITE_PRINCIPAL", "urace.us")
    assert _get(cli, "novo.urace.us", "/ops/api/vitrine/agenda").status_code != 301
    r = cli.post("/ops/api/vitrine/contato", headers={"host": "www.urace.us"}, data={"site": "robo"})
    assert r.status_code != 301


def test_nome_que_nao_e_do_site_nao_redireciona(cli, monkeypatch):
    monkeypatch.setenv("CC_SITE_PRINCIPAL", "urace.us")
    assert _get(cli, "ops.urace.us", "/ops/").status_code != 301
    # principal fora de CC_SITE_HOSTS: a variável é ignorada (nunca manda o site para um nome que ele não serve)
    monkeypatch.setenv("CC_SITE_PRINCIPAL", "outro.example")
    assert _get(cli, "www.urace.us", "/").status_code == 200


def test_links_do_servidor_usam_o_principal(monkeypatch):
    from command_center.api import blog, editor_site
    from command_center.providers import pedido_site
    monkeypatch.setenv("CC_SITE_HOSTS", "novo.urace.us,urace.us,www.urace.us")
    monkeypatch.delenv("CC_SITE_PRINCIPAL", raising=False)
    assert enderecos.site_principal() == "novo.urace.us"          # sem a variável: o primeiro, como antes
    monkeypatch.setenv("CC_SITE_PRINCIPAL", "urace.us")
    assert enderecos.site_principal() == "urace.us"
    assert pedido_site._host_do_site({}) == "urace.us"
    assert editor_site._host(None) == "urace.us"
    assert blog._host() == "urace.us"                               # antes: o 1º em ordem alfabética (novo.)
    monkeypatch.delenv("CC_SITE_HOSTS")
    monkeypatch.delenv("CC_SITE_PRINCIPAL")
    assert enderecos.site_principal() == "novo.urace.us"


# ------------------------------------------------------------------ o Caddy do deploy
def _trecho():
    return re.search(r"<<'PY2'\n(.*?)\nPY2\n", open(SCRIPT, encoding="utf-8").read(), re.S).group(1)


def _caddy(tmp_path, extra, site_hosts):
    caddy = tmp_path / "Caddyfile"
    if not caddy.exists():
        caddy.write_text("urace-bridge.duckdns.org {\n}\n")
    subprocess.run([sys.executable, "-c", _trecho()], check=True, capture_output=True,
                   env={**os.environ, "EXTRA": extra, "PORTA": "8787", "CADDYFILE": str(caddy), "SITE_HOSTS": site_hosts})
    return caddy.read_text()


def _bloco(s, nome):
    return re.search(r"(?:^|\n)" + re.escape(nome) + r" \{\n(.*?)\n\}", s, re.S).group(1)


def test_urace_us_e_www_viram_site_no_caddy(tmp_path):
    for nome in ("ops.urace.us", "urace.us", "www.urace.us"):
        s = _caddy(tmp_path, nome, TRES)
    for nome in ("urace.us", "www.urace.us"):
        b = _bloco(s, nome)
        assert "redir / /ops/" not in b, f"{nome}: a raiz não pode levar ao login da equipe"
        assert 'respond "not found" 404' not in b, f"{nome}: as páginas do site passam ao servidor"
        assert re.search(r"\thandle \{\n\t\treverse_proxy 127\.0\.0\.1:8787", b), nome
    assert "redir / /ops/ 302" in _bloco(s, "ops.urace.us"), "o painel continua o painel"


def _le_env(tmp_path, conteudo, **env):
    """As linhas do deploy que leem as variáveis do adminai.env, com o mesmo `set -euo pipefail` do script."""
    s = open(SCRIPT, encoding="utf-8").read()
    linhas = re.search(r"\n(_do_env\(\).*?\nCC_SITE_HOSTS=[^\n]*)\n", s, re.S).group(1)
    if conteudo is not None:
        (tmp_path / "adminai.env").write_text(conteudo)
    prog = f'set -euo pipefail\nURACE_DIR="{tmp_path}"\n{linhas}\necho "[$CC_DOMINIOS_EXTRAS][$CC_SITE_HOSTS]"\n'
    base = {k: v for k, v in os.environ.items() if k not in ("CC_DOMINIOS_EXTRAS", "CC_SITE_HOSTS")}
    return subprocess.run(["bash", "-c", prog], capture_output=True, text=True, env={**base, **env})


def test_deploy_le_as_variaveis_do_adminai_env(tmp_path):
    r = _le_env(tmp_path, 'X=1\nCC_SITE_HOSTS="urace.us,www.urace.us"\nCC_DOMINIOS_EXTRAS=\'ops.urace.us urace.us\'\n')
    assert r.returncode == 0 and r.stdout.strip() == "[ops.urace.us urace.us][urace.us,www.urace.us]"
    # a do terminal ganha
    r = _le_env(tmp_path, None, CC_SITE_HOSTS="novo.urace.us")
    assert r.stdout.strip() == "[ops.urace.us urace.us][novo.urace.us]"


def test_deploy_sem_adminai_env_nao_para(tmp_path):
    r = _le_env(tmp_path, None)
    assert r.returncode == 0 and r.stdout.strip() == "[][]"
