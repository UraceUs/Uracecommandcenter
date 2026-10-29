"""Debug de 29/10 — a conversa nova do designer só liga ao pedido pelo número DO PEDIDO.

A ponte liga o e-mail novo do designer ao pedido pelo "#número" do assunto ou do começo do corpo. Designer escreve
cor em hexadecimal ("#1A1A1A", "#0055A4"): o começo do código virava o número de um pedido (o #1, o #55), e a arte
ia para a pasta e para a IA do pedido de outro cliente. Só dados fictícios."""
import pytest

from command_center.db import aplicar_schema, conectar, um
from command_center.providers import suits_ponte as sp
from command_center.tests.test_suits_ponte import Gmail


@pytest.fixture()
def con(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "designer-numero.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path / "urace"))
    monkeypatch.setenv("CC_EMAIL_FAKE", str(tmp_path / "enviados.jsonl"))
    c = conectar(); aplicar_schema(c)
    c.execute("INSERT INTO users (email, name, role, pw_salt, pw_hash) VALUES ('a@urace.us','Admin','ADMIN','x','x')")
    sp.salvar_config(c, {"designer_email": "designer@example.com", "designer_nome": "Designer Ficticio"})
    yield c
    c.close()


def _pedido(con, nome):
    return con.execute("INSERT INTO suit_orders (title, customer_name, status) VALUES (?, ?, 'design_pending')",
                       (nome, nome)).lastrowid


def _evento(con, assunto, corpo):
    gm = Gmail()
    gm.threads = {"t-arte": [{"message_id": "d1", "de": "Designer Ficticio <designer@example.com>", "assunto": assunto,
                              "corpo": corpo, "anexos": []}]}
    gm.buscas = {"from:designer@example.com": ["t-arte"]}
    eventos = sp.conversas_novas(con, gm)
    assert len(eventos) == 1 and eventos[0]["tipo"] == "designer"
    return eventos[0]


def test_cor_em_hexadecimal_nao_vira_numero_de_pedido(con):
    um_ = _pedido(con, "Cliente Um Ficticio")                     # o pedido #1, de outro cliente
    ev = _evento(con, "New art", "Here is the new version. Colors: #1A1A1A (black) and #E10600 (red).")
    assert ev["pedido_id"] is None
    assert um(con, "SELECT gmail_thread_designer FROM suit_orders WHERE id=?", (um_,))["gmail_thread_designer"] is None


def test_numero_do_pedido_com_cor_em_hexadecimal_liga_so_ao_pedido(con):
    _pedido(con, "Cliente Um Ficticio")
    dois = _pedido(con, "Cliente Dois Ficticio")
    ev = _evento(con, f"Suits #{dois} - art v2", "Main color #1A1A1A, details in #0055A4.")
    assert ev["pedido_id"] == dois
    assert um(con, "SELECT gmail_thread_designer FROM suit_orders WHERE id=?", (dois,))["gmail_thread_designer"] == "t-arte"
