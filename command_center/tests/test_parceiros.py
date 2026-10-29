"""#511: a faixa "Powered by" o Orlando Kart Center e os parceiros, antes do rodapé, como no urace.us de 29/10."""
import os
import re

import pytest

os.environ.setdefault("CC_AUTOSYNC", "0")

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from command_center.api.main import app  # noqa: E402
from command_center.vitrine import conteudo as C  # noqa: E402
from command_center.vitrine.paginas import STATIC  # noqa: E402

SITE = "https://novo.urace.us"
NOMES = ["Orlando Kart Center", "ILX Group", "AZ Car Rental", "CANOTOPS", "Allure Global Events"]


@pytest.fixture()
def cli(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path))
    monkeypatch.delenv("CC_SITE_HOSTS", raising=False)
    monkeypatch.delenv("CC_SITE_PREVIEW", raising=False)
    with TestClient(app, base_url=SITE) as t:
        yield t


@pytest.mark.parametrize("caminho", ["/", "/academy/", "/services/birthday-party/", "/contact/", "/store/"])
def test_faixa_dos_parceiros_antes_do_rodape(cli, caminho):
    html = cli.get(caminho).text
    m = re.search(r"</main>\s*(<aside class=\"parceiros\" aria-label=\"Powered by and partners\">.*?</aside>)\s*<footer", html, re.S)
    assert m, "a faixa fica entre o conteúdo e o rodapé"
    faixa = m.group(1)
    assert re.findall(r'<p class="parceiros-rot">([^<]+)</p>', faixa) == ["Powered by", "Partners"]
    imgs = re.findall(r"<img ([^>]+)>", faixa)
    assert [re.search(r'alt="([^"]+)"', i).group(1) for i in imgs] == NOMES
    for i in imgs:
        assert re.search(r'width="\d+" height="\d+"', i), i      # o tamanho reservado: a página não pula
        assert 'loading="lazy"' in i and "style=" not in i
        src = re.search(r'src="/_s/img/([^"?]+)\?v=', i).group(1)
        assert cli.get(f"/_s/img/{src}").status_code == 200, src
    assert "<a " not in faixa, "os logos não levam a site de fora"


def test_logos_leves_e_limpos():
    for _nome, arq in (C.POWERED_BY, *C.PARCEIROS):
        caminho = os.path.join(STATIC, "img", arq)
        assert os.path.getsize(caminho) <= 30_000, arq
        if arq.endswith(".svg"):
            s = open(caminho, encoding="utf-8").read()
            # o SVG não traz script, estilo (a política do site) nem nada de fora, e tem tamanho próprio
            assert not re.search(r"<script|<style|<image|<foreignObject|href=\"http|\bon\w+=", s, re.I), arq
            assert re.search(r'<svg [^>]*width="[\d.]+" height="[\d.]+"', s), arq
        else:
            assert arq.endswith(".webp"), arq
            with Image.open(caminho) as im:
                assert im.format == "WEBP" and max(im.size) <= 1600 and not im.info.get("exif"), arq
