"""#447 (dono, 29/10): "onde tem anexar print precisa ter para anexar qualquer tipo de arquivo".

A nota do pedido de Suits aceita qualquer arquivo. Imagem segue o caminho da foto (WebP, sem EXIF, na linha do
tempo); o resto vai para os arquivos do pedido, aparece na nota e sai só com sessão, sempre como download."""
import io
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from command_center.api import auth
from command_center.api import suits as rota
from command_center.api.main import app
from command_center.db import aplicar_schema, conectar

SENHA = "senha-forte-123"
B = "/ops/api/suits"


@pytest.fixture(scope="module")
def cli():
    pasta = tempfile.mkdtemp()
    antes = os.environ.get("URACE_DIR")
    os.environ["URACE_DIR"] = pasta
    os.environ["CC_DB_PATH"] = os.path.join(pasta, "cc-suits-arquivo.sqlite")
    con = conectar(); aplicar_schema(con)
    auth.criar_usuario(con, "op@urace.us", "Operador Fictício", "OPERATOR", SENHA)
    con.close()
    with TestClient(app, base_url="https://cc.test") as c:
        c.post("/ops/api/auth/login", json={"email": "op@urace.us", "password": SENHA})
        c.h = {"X-CSRF": c.cookies.get("cc_csrf")}
        c.pid = c.post(B, headers=c.h, json={"customer_name": "Cliente Fictício Arquivo"}).json()["id"]
        yield c
    if antes is None:
        os.environ.pop("URACE_DIR", None)
    else:
        os.environ["URACE_DIR"] = antes


def test_nota_anexa_um_pdf_que_vai_para_os_arquivos_do_pedido(cli):
    pdf = b"%PDF-1.4\n% ficha ficticia\n"
    r = cli.post(f"{B}/{cli.pid}/notas", headers=cli.h, data={"texto": "ficha do cliente"},
                 files={"arquivo": ("Ficha Medidas.pdf", pdf, "application/pdf")})
    assert r.status_code == 201, r.text
    p = cli.get(f"{B}/{cli.pid}").json()
    n = [x for x in p["notas"] if x["kind"] == "nota"][-1]
    assert n["arquivo"] == "Ficha Medidas.pdf" and not n["tem_imagem"] and n["text"] == "ficha do cliente"
    assert "Ficha Medidas.pdf" in [a["nome"] for a in cli.get(f"{B}/{cli.pid}/anexos").json()]
    d = cli.get(f"{B}/{cli.pid}/anexos/Ficha%20Medidas.pdf")
    assert d.status_code == 200 and d.content == pdf
    assert d.headers["content-disposition"].startswith("attachment")         # baixa, nunca abre como página


@pytest.mark.parametrize("nome,mime", [("arte.ai", "application/postscript"), ("planilha.xlsx", "application/octet-stream"),
                                       ("pagina.html", "text/html"), ("pacote.zip", "application/zip")])
def test_qualquer_tipo_entra_e_html_sai_como_download(cli, nome, mime):
    r = cli.post(f"{B}/{cli.pid}/notas", headers=cli.h, files={"arquivo": (nome, b"conteudo ficticio " + nome.encode(), mime)})
    assert r.status_code == 201, r.text
    d = cli.get(f"{B}/{cli.pid}/anexos/{nome}")
    assert d.status_code == 200 and d.headers["content-disposition"].startswith("attachment")


def test_imagem_pelo_mesmo_campo_continua_virando_foto(cli):
    from PIL import Image
    b = io.BytesIO(); Image.new("RGB", (40, 20), (10, 20, 30)).save(b, "PNG")
    r = cli.post(f"{B}/{cli.pid}/notas", headers=cli.h, files={"arquivo": ("print.png", b.getvalue(), "image/png")})
    assert r.status_code == 201, r.text
    n = [x for x in cli.get(f"{B}/{cli.pid}").json()["notas"] if x["kind"] == "nota"][-1]
    assert n["tem_imagem"] and not n["arquivo"]
    assert cli.get(f"{B}/notas/{n['id']}/imagem").headers["content-type"] == "image/webp"


def test_arquivo_vazio_ou_grande_demais_e_recusado(cli, monkeypatch):
    assert cli.post(f"{B}/{cli.pid}/notas", headers=cli.h, files={"arquivo": ("vazio.pdf", b"", "application/pdf")}).status_code == 400
    monkeypatch.setattr(rota, "ARQUIVO_MAX", 10)
    r = cli.post(f"{B}/{cli.pid}/notas", headers=cli.h, files={"arquivo": ("grande.pdf", b"x" * 11, "application/pdf")})
    assert r.status_code == 400 and "25 MB" in r.json()["detail"]


def test_o_arquivo_so_sai_com_sessao(cli):
    cli.post(f"{B}/{cli.pid}/notas", headers=cli.h, files={"arquivo": ("privado.pdf", b"%PDF-1.4 x", "application/pdf")})
    with TestClient(app, base_url="https://cc.test") as anon:
        assert anon.get(f"{B}/{cli.pid}/anexos/privado.pdf").status_code == 401
