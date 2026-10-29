"""Debug de 29/10 — as guardas dos Suits olham o CONTEÚDO de verdade.

Regra que nunca muda (guia do Lucas, §9): o designer não recebe nome completo, e-mail, telefone ou endereço do
cliente; "arquivo que contenha qualquer um deles não sai". O PDF de verdade (o que o cliente manda, o que a equipe
anexa na nota desde o #447) guarda o texto comprimido: procurar nos bytes crus não acha nada.
Só dados fictícios (@example.com, 555-01xx, nomes inventados)."""
import io

import pytest

from command_center.db import aplicar_schema, conectar, um
from command_center.providers import suits_ponte as sp


@pytest.fixture()
def con(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "guardas.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path / "urace"))
    monkeypatch.setenv("CC_EMAIL_FAKE", str(tmp_path / "enviados.jsonl"))
    c = conectar(); aplicar_schema(c)
    c.execute("INSERT INTO users (email, name, role, pw_salt, pw_hash) VALUES ('a@urace.us','Admin','ADMIN','x','x')")
    yield c
    c.close()


def _pedido(con, **kw):
    campos = {"title": "Dario Fictício", "customer_name": "Dario Fictício", "customer_email": "dario@example.com",
              "customer_phone": "(407) 555-0142", "ship_address": "742 Rua Inventada\nCidade Teste FL", "language": "en", **kw}
    cols = ", ".join(campos)
    return con.execute(f"INSERT INTO suit_orders ({cols}) VALUES ({', '.join('?' * len(campos))})", tuple(campos.values())).lastrowid


def _pdf(*linhas):
    """Um PDF como os de verdade: o reportlab comprime o conteúdo da página (FlateDecode)."""
    from reportlab.pdfgen import canvas
    b = io.BytesIO()
    c = canvas.Canvas(b)
    for i, linha in enumerate(linhas):
        c.drawString(72, 700 - 20 * i, linha)
    c.save()
    return b.getvalue()


@pytest.mark.parametrize("linha,rotulo", [("Contact: dario@example.com", "e-mail do cliente"),
                                          ("Phone +1 (407) 555-0142", "telefone do cliente"),
                                          ("Ship to 742 Rua Inventada", "endereço do cliente"),
                                          ("Customer: Dario Fictício", "nome completo do cliente")])
def test_pdf_comprimido_com_dado_do_cliente_nao_vai_ao_designer(con, linha, rotulo):
    pid = _pedido(con)
    p = dict(um(con, "SELECT * FROM suit_orders WHERE id=?", (pid,)))
    dados = _pdf("Sizing form", linha, "Chest 98 cm")
    assert linha.split()[-1].encode() not in dados, "o teste precisa de um PDF com o texto comprimido"
    with pytest.raises(sp.Recusado, match=rotulo):
        sp.limpar_para_designer([("ficha.pdf", dados, "application/pdf")], p)


def test_pdf_comprimido_so_com_o_design_continua_indo(con):
    pid = _pedido(con)
    p = dict(um(con, "SELECT * FROM suit_orders WHERE id=?", (pid,)))
    (nome, dados, _), = sp.limpar_para_designer([("brief.pdf", _pdf(f"Suits #{pid}", "Red and black, flag on the arm"),
                                                  "application/pdf")], p)
    assert nome == "brief.pdf" and dados.startswith(b"%PDF")


def test_o_email_ao_designer_com_a_ficha_do_cliente_nao_fica_preparado(con):
    """O caminho inteiro: a ficha que o cliente mandou (ou a equipe anexou na nota) não vira e-mail ao designer."""
    sp.salvar_config(con, {"designer_email": "designer@example.com"})
    pid = _pedido(con)
    sp.guardar_anexo(pid, "ficha-medidas.pdf", _pdf("Name: Dario Fictício", "Email: dario@example.com"))
    with pytest.raises(sp.Recusado, match="não vai ao designer"):
        sp.enviar(con, pid, "designer", f"Suits #{pid} - briefing", "Design attached.", ["ficha-medidas.pdf"])
    assert um(con, "SELECT COUNT(*) AS n FROM suit_outbox")["n"] == 0
