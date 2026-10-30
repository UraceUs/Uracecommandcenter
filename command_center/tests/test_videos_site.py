"""#526: os três vídeos curtos do urace.us ("On camera") na home e na /winter/, servidos pelo próprio site.

Dono, 30/10: os 3 vídeos "no site". O mp4 sai de static/video (comprimido, sem metadados) e o pôster de static/img (WebP);
o player é o do navegador (`<video controls>`), sem nada de fora, e nada baixa antes do play.
"""
import os
import re
import subprocess

import pytest

os.environ.setdefault("CC_AUTOSYNC", "0")

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from command_center.api.main import app  # noqa: E402
from command_center.vitrine import blocos, pg_home, pg_winter  # noqa: E402
from command_center.vitrine.conteudo import CURTAS  # noqa: E402
from command_center.vitrine.paginas import STATIC  # noqa: E402

SITE = "https://novo.urace.us"
# (sem nome de piloto aqui: o repositório é público; o nome publicado fica só no conteúdo do site, `vitrine/`)
# as legendas de lá (urace.us, 30/10), vídeo a vídeo, sem o nome
HOME = ["After the win · FLKC P1", "His first KA100 race", "Founder · why URACE exists"]
WINTER = ["After the win · FLKC P1 · 29 s", "His first KA100 race · 19 s", "Founder · why URACE exists · 20 s"]
ARQUIVOS = [CURTAS[k]["video"][:-4] for k in ("vitoria", "primeira", "fundador")]


def _bloco(pagina):
    return next(b for b in pagina["blocos"] if b["tipo"] == "videos" and b.get("ancora") == "on-camera")


@pytest.fixture()
def cli(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path))
    monkeypatch.delenv("CC_SITE_HOSTS", raising=False)
    monkeypatch.delenv("CC_SITE_PREVIEW", raising=False)
    with TestClient(app, base_url=SITE) as t:
        yield t


def _faixa(html):
    m = re.search(r'<section class="faixa escura" aria-labelledby="h-b(\d+)" id="on-camera">(.*?)</section>', html, re.S)
    assert m, "a faixa dos vídeos, com âncora #on-camera"
    return m.group(1), m.group(2)


@pytest.mark.parametrize("caminho, eyebrow, titulo, legendas, pagina", [
    ("/", "On camera", "Straight from the paddock", HOME, pg_home.HOME),
    ("/winter/", "On camera", "Hear it from the team", WINTER, pg_winter.WINTER)])
def test_os_tres_videos_na_pagina_com_o_texto_de_la(cli, caminho, eyebrow, titulo, legendas, pagina):
    r = cli.get(caminho)
    assert r.status_code == 200
    i, faixa = _faixa(r.text)
    assert f'<p class="eyebrow">{eyebrow}</p><h2 id="h-b{i}">{titulo}</h2>' in faixa
    videos = re.findall(r"<video ([^>]+)><source ([^>]+)>", faixa)
    assert len(videos) == 3
    nomes = [v["titulo"] for v in _bloco(pagina)["itens"]]
    assert [v["legenda"] for v in _bloco(pagina)["itens"]] == legendas
    for n, ((attrs, source), arq, nome, legenda) in enumerate(zip(videos, ARQUIVOS, nomes, legendas)):
        assert attrs.startswith('controls preload="none" playsinline poster="/_s/img/'), attrs
        assert re.search(rf'poster="/_s/img/{arq}-poster\.webp\?v=[0-9a-f]{{10}}"', attrs), attrs
        assert re.search(r'width="\d+" height="\d+"', attrs), "o tamanho reservado: a página não pula"
        assert "autoplay" not in attrs and "style=" not in attrs
        assert re.fullmatch(rf'src="/_s/video/{arq}\.mp4\?v=[0-9a-f]{{10}}" type="video/mp4"', source), source
        ident = f"v-b{i}-{n}"
        assert f'aria-labelledby="{ident}"' in attrs, "o player tem nome: o da legenda"
        assert f'<figcaption><strong id="{ident}">{nome}</strong><span>{legenda}</span></figcaption>' in faixa
    # nada de player de fora nem do WordPress
    assert "wp-content" not in r.text and "<iframe" not in r.text


def test_na_home_as_avaliacoes_seguem_logo_abaixo_dos_videos(cli):
    html = cli.get("/").text
    assert re.search(r'id="on-camera">.*?</section>\s*<section class="faixa escura" aria-label="Google reviews" id="reviews">',
                     html, re.S)


@pytest.mark.parametrize("arq", ARQUIVOS)
def test_o_video_sai_do_site_com_tipo_e_por_pedaco(cli, arq):
    """O navegador pede o vídeo aos pedaços (Range): 206 com o pedaço certo, sem gzip, e o tipo `video/mp4`."""
    caminho = os.path.join(STATIC, "video", f"{arq}.mp4")
    tamanho = os.path.getsize(caminho)
    inteiro = cli.get(f"/_s/video/{arq}.mp4?v=1")
    assert inteiro.status_code == 200 and inteiro.headers["content-type"] == "video/mp4"
    assert "content-encoding" not in inteiro.headers and len(inteiro.content) == tamanho
    r = cli.get(f"/_s/video/{arq}.mp4", headers={"Range": "bytes=0-1023"})
    assert r.status_code == 206
    assert r.headers["content-range"] == f"bytes 0-1023/{tamanho}" and r.headers["accept-ranges"] == "bytes"
    assert r.content == open(caminho, "rb").read(1024) and "content-encoding" not in r.headers
    assert r.headers["cache-control"].startswith("public")
    poster = cli.get(f"/_s/img/{arq}-poster.webp")
    assert poster.status_code == 200 and poster.headers["content-type"] == "image/webp"


def test_a_politica_do_site_deixa_tocar_o_video_do_proprio_site(cli):
    csp = cli.get("/").headers["content-security-policy"]
    d = dict(x.strip().split(" ", 1) for x in csp.split(";"))
    # sem `media-src`, vale o `default-src`: só o próprio site
    assert d.get("media-src", d["default-src"]) == "'self'"


@pytest.mark.parametrize("arq", ARQUIVOS)
def test_video_leve_e_pronto_para_a_web(arq):
    """Leve (≤ 3,5 MB), H.264 + AAC, `faststart` (o índice antes dos dados: toca antes de baixar tudo), sem metadados."""
    caminho = os.path.join(STATIC, "video", f"{arq}.mp4")
    assert os.path.getsize(caminho) <= 3_500_000
    with open(caminho, "rb") as f:
        cabeca = f.read(65536)
    assert 0 <= cabeca.find(b"moov") < cabeca.find(b"mdat") or b"mdat" not in cabeca, "faststart: moov antes de mdat"
    assert b"avc1" in cabeca and b"mp4a" in cabeca, "H.264 e AAC (toca em todo navegador)"
    for marca in (b"com.apple.quicktime", b"\xa9xyz", b"\xa9too", b"\xa9day", b"\xa9mak", b"\xa9mod"):
        assert marca not in cabeca, f"metadado no vídeo (aparelho, local, data, programa): {marca!r}"


def test_video_com_duracao_da_legenda():
    """A legenda da Winter diz quantos segundos o vídeo tem: ela bate com o arquivo (ffprobe, quando há)."""
    try:
        saida = {a: subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                    os.path.join(STATIC, "video", f"{a}.mp4")], capture_output=True, text=True,
                                   check=True).stdout for a in ARQUIVOS}
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("sem ffprobe")
    for a, legenda in zip(ARQUIVOS, WINTER):
        segundos = int(re.search(r"(\d+) s$", legenda).group(1))
        assert abs(float(saida[a]) - segundos) < 1, (a, saida[a], legenda)


@pytest.mark.parametrize("arq", ARQUIVOS)
def test_poster_webp_leve_sem_exif_e_do_tamanho_do_video(arq):
    caminho = os.path.join(STATIC, "img", f"{arq}-poster.webp")
    assert os.path.getsize(caminho) <= 60_000
    with Image.open(caminho) as im:
        assert im.format == "WEBP" and max(im.size) <= 1600
        assert not im.info.get("exif") and not im.info.get("xmp") and not dict(im.getexif())
        w, h = im.size
    assert abs(w / h - 9 / 16) < 0.01, "vertical 9:16, como o vídeo"


def test_curtas_apontam_para_arquivos_que_existem():
    for v in CURTAS.values():
        assert os.path.isfile(os.path.join(STATIC, "video", v["video"])), v
        assert os.path.isfile(os.path.join(STATIC, "img", v["poster"])), v


def test_bloco_videos_continua_aceitando_link_e_recusa_video_que_nao_existe():
    d = {"caminho": "/x/", "blocos": [{"tipo": "videos", "titulo": "Onboard", "itens": [
        {**CURTAS["primeira"], "titulo": "Primeira corrida", "legenda": "His first KA100 race"},
        ("From karting to Formula 1", "https://www.youtube.com/watch?v=xMwAP1xlruc")]}]}
    html = blocos.corpo("novo.urace.us", d)
    assert html.count("<video ") == 1
    assert '<ul class="videos"><li><a class="seta" href="https://www.youtube.com/watch?v=xMwAP1xlruc" rel="noopener">' in html
    with pytest.raises(blocos.ErroBloco):
        blocos.corpo("novo.urace.us", {"caminho": "/x/", "blocos": [{"tipo": "videos", "itens": [
            {"video": "nao-existe.mp4", "poster": CURTAS["primeira"]["poster"], "titulo": "x"}]}]})
    with pytest.raises(blocos.ErroBloco):
        blocos.corpo("novo.urace.us", {"caminho": "/x/", "blocos": [{"tipo": "videos", "itens": [
            {"video": "../../api/main.py", "poster": CURTAS["primeira"]["poster"], "titulo": "x"}]}]})
