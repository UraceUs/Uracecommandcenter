"""Isola os testes do mundo real ANTES de qualquer import da aplicação.

No VPS os testes rodavam com ~/.urace/google-token.json presente: o
gmail_mcp usa esse caminho por padrão quando GOOGLE_TOKEN_JSON não está
definido, e o teste "sem credencial" chamou o Gmail de verdade
(04/09). Aqui HOME vira um diretório vazio e toda credencial conhecida
é apagada do ambiente. Teste nunca fala com sistema real.
"""
import atexit
import os
import shutil
import tempfile

import pytest

# #125: todo mkdtemp/NamedTemporaryFile dos testes cai numa pasta desta execução, que sai inteira
# no fim. Antes cada suíte deixava ~500 MB no /tmp — e o deploy do VPS roda a suíte a cada deploy.
_TMP = tempfile.mkdtemp(prefix="cc-testes-")
tempfile.tempdir = _TMP
atexit.register(shutil.rmtree, _TMP, ignore_errors=True)

os.environ["HOME"] = tempfile.mkdtemp(prefix="cc-home-")
os.environ["URACE_DIR"] = os.path.join(os.environ["HOME"], ".urace")   # 17/09: no VPS o deploy exporta URACE_DIR real; teste nunca escreve lá
for k in ("URACE_ENV", "GOOGLE_TOKEN_JSON", "GOOGLE_TOKEN_JSON_SUPPORT"):
    os.environ[k] = "/nao/existe"
for k in list(os.environ):
    # ANTHROPIC_/CLAUDE_CODE_OAUTH_TOKEN (#152): com a chave no ambiente, o AI Command iria ao Claude de verdade
    # CC_GOOGLE_ (#220): o cliente OAuth Web e o endereço do Google; o teste usa o Google falso
    if k.startswith(("ASANA_", "DOCUSIGN_", "QBO_", "GOOGLE_CLIENT", "OPENCLAW_GATEWAY", "ANTHROPIC_", "CC_GOOGLE_")) \
            or k in ("APLICAR", "CLAUDE_CODE_OAUTH_TOKEN", "CC_IA_MOTOR", "CC_WAIVER_TSA", "CC_WAIVER_SEAL_DIR"):
        del os.environ[k]
os.environ["CC_AUTOSYNC"] = "0"          # teste não roda o laço de sincronia


# #110: o PDF da waiver nativa sai selado (PAdES + carimbo RFC 3161). Em teste, todo teste tem um selo de TESTE
# (gerado uma vez por execução, em pasta temporária, nunca no repositório) e a TSA falsa do pyHanko no lugar da
# real: o CI não tem rede. O teste "sem selo" aponta CC_WAIVER_SEAL_DIR para uma pasta vazia.
@pytest.fixture(scope="session")
def _pasta_do_selo(tmp_path_factory):
    from command_center.tests import selo_teste
    pasta = tmp_path_factory.mktemp("selo-de-teste") / "selo"
    selo_teste.criar_selo(pasta)
    return str(pasta)


@pytest.fixture(autouse=True)
def _selo_de_teste(_pasta_do_selo, monkeypatch):
    from command_center.providers import selo_waiver
    from command_center.tests import selo_teste
    selo_teste.guardar_o_real()
    monkeypatch.setenv("CC_WAIVER_SEAL_DIR", _pasta_do_selo)
    monkeypatch.setattr(selo_waiver, "_carimbadores", lambda: [("urn:test:tsa-falsa", selo_teste.tsa())])


@pytest.fixture(autouse=True)
def _limites_do_site_zerados():
    """#485 guarda na memória do processo quantos envios cada IP/e-mail fez nos formulários do site. Entre testes isso
    vazava: conforme a divisão do CI em partes, um teste anterior gastava o limite de um e-mail e o seguinte levava
    400 (debug 29/10). Cada teste começa com os limites zerados."""
    import sys
    vitrine = sys.modules.get("command_center.api.vitrine")
    if vitrine is not None:
        vitrine._envios.clear()
    yield
