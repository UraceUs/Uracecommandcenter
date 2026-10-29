"""Debug de 29/10 — o e-mail novo do fornecedor só liga ao pedido cujo nome aparece INTEIRO no assunto.

A ponte acha o pedido do e-mail do fornecedor pelo título ou pelo piloto no assunto ("SUIT - <piloto>"). A busca era
por pedaço de texto: o pedido aberto "Ana Fict" casava com o assunto do suit da "Ana Ficticia" (pedido já entregue),
e as fotos, o aceite ou o rastreio de um iam para o pedido do outro cliente. Só dados fictícios."""
import pytest

from command_center.db import aplicar_schema, conectar, um
from command_center.providers import suits_ponte as sp
from command_center.tests.test_suits_ponte import Gmail


@pytest.fixture()
def con(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "fornecedor-assunto.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path / "urace"))
    monkeypatch.setenv("CC_EMAIL_FAKE", str(tmp_path / "enviados.jsonl"))
    c = conectar(); aplicar_schema(c)
    c.execute("INSERT INTO users (email, name, role, pw_salt, pw_hash) VALUES ('a@urace.us','Admin','ADMIN','x','x')")
    c.execute("INSERT INTO suit_suppliers (name, email, is_current) VALUES ('Fornecedor Ficticio', 'fornecedor@example.com', 1)")
    yield c
    c.close()


def _pedido(con, nome, status="in_production", closed=0):
    return con.execute("INSERT INTO suit_orders (title, customer_name, driver_name, status, closed) VALUES (?,?,?,?,?)",
                       (nome, nome, nome, status, closed)).lastrowid


def _evento(con, assunto):
    gm = Gmail()
    gm.threads = {"t-forn": [{"message_id": "f1", "de": "Fornecedor <fornecedor@example.com>", "assunto": assunto,
                              "corpo": "Photos of the suit attached. Tracking 1Z999AA10123456784.", "anexos": []}]}
    gm.buscas = {"label:Suits": ["t-forn"]}
    eventos = sp.conversas_novas(con, gm)
    assert len(eventos) == 1 and eventos[0]["tipo"] == "fornecedor"
    return eventos[0]


def test_nome_que_e_pedaco_de_outro_nao_liga_o_email_do_fornecedor(con):
    aberto = _pedido(con, "Ana Fict")
    _pedido(con, "Ana Ficticia", status="delivered", closed=1)          # o suit do assunto, já entregue
    ev = _evento(con, "SUIT - Ana Ficticia - photos and tracking")
    assert ev["pedido_id"] is None
    assert um(con, "SELECT gmail_thread_fornecedor FROM suit_orders WHERE id=?", (aberto,))["gmail_thread_fornecedor"] is None


def test_o_nome_inteiro_no_assunto_continua_ligando(con):
    pid = _pedido(con, "Ana Ficticia")
    _pedido(con, "Bruno Ficticio")
    ev = _evento(con, "Re: SUIT - Ana Ficticia (photos)")
    assert ev["pedido_id"] == pid
