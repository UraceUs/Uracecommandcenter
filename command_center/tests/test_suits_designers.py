"""#481 (dono, 29/10): "designer 1, designer 2, designer 3, com os endereços de e-mail fixos. E aí eu seleciono qual que é
o nome do designer nessa parte aí do ponte de e-mail e ele puxa esses e-mails de lá" e "eu preciso que já venha a
conversa com o cliente, venha com o e-mail do cliente, ele puxa de lá".

Os designers ficam numa lista (como os fornecedores); o pedido escolhe um; a ponte manda para ele, reconhece e-mail de
qualquer designer da lista e o cliente não vê nenhum deles. "Puxar do Gmail" liga as conversas que faltam. Tudo fictício."""
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from command_center.api import auth
from command_center.api.main import app
from command_center.db import aplicar_schema, conectar, inserir, um
from command_center.providers import suits_ponte as sp
from command_center.tests.test_suits_ponte import Gmail

SENHA = "senha-forte-123"
B = "/ops/api/suits"


@pytest.fixture()
def con(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "designers.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path / "urace"))
    monkeypatch.setenv("CC_EMAIL_FAKE", str(tmp_path / "enviados.jsonl"))
    c = conectar(); aplicar_schema(c)
    sp.salvar_config(c, {"designer_email": "designer.antigo@example.com", "designer_nome": "Designer Antigo"})
    yield c
    c.close()


def _designers(con):
    d1 = inserir(con, "suit_designers", name="Designer Um", email="designer.um@example.com", is_current=1)
    d2 = inserir(con, "suit_designers", name="Designer Dois", email="designer.dois@example.com", is_current=0)
    return d1, d2


def _pedido(con, **kw):
    campos = dict(title="Theo Ficticio", customer_name="Nina Ficticia", customer_email="nina.ficticia@example.com",
                  driver_name="Theo Ficticio", status="design_pending")
    campos.update(kw)
    return inserir(con, "suit_orders", **campos)


def test_o_pedido_manda_ao_designer_escolhido_e_sem_escolha_ao_padrao(con):
    d1, d2 = _designers(con)
    cfg = sp.config(con)
    pid = _pedido(con)
    assert sp.destinatario(con, um(con, "SELECT * FROM suit_orders WHERE id=?", (pid,)), "designer", cfg) == "designer.um@example.com"
    con.execute("UPDATE suit_orders SET designer_id=? WHERE id=?", (d2, pid))
    assert sp.destinatario(con, um(con, "SELECT * FROM suit_orders WHERE id=?", (pid,)), "designer", cfg) == "designer.dois@example.com"


def test_o_cliente_nao_ve_nenhum_designer_da_lista(con):
    _designers(con)
    cfg = sp.config(con)
    pedido = um(con, "SELECT * FROM suit_orders WHERE id=?", (_pedido(con),))
    for texto in ("Designer Dois fez a arte", "fale com designer.um@example.com", "Designer Antigo mandou"):
        with pytest.raises(sp.Recusado, match="designer"):
            sp._guardas(pedido, "cliente", texto, cfg)
    sp._guardas(pedido, "cliente", "Your design is ready for review.", cfg)


def test_nome_curto_de_designer_so_trava_como_palavra_inteira(con):
    """debug 29/10: o nome do designer (3 letras ou mais) era procurado como pedaço de texto: com uma designer "Ana" na lista,
    "Hi Mariana" ou "Luciana" travavam o e-mail ao cliente. Agora é a palavra inteira; o e-mail continua por pedaço."""
    inserir(con, "suit_designers", name="Ana", email="ana.designer@example.com", is_current=1)
    cfg = sp.config(con)
    pedido = um(con, "SELECT * FROM suit_orders WHERE id=?", (_pedido(con, customer_name="Mariana Ficticia"),))
    sp._guardas(pedido, "cliente", "Hi Mariana, your design is ready. Thanks, Luciana's team.", cfg)
    for texto in ("Ana fez a arte", "a arte da ana.", "fale com ana.designer@example.com"):
        with pytest.raises(sp.Recusado, match="designer"):
            sp._guardas(pedido, "cliente", texto, cfg)


def test_email_de_qualquer_designer_da_lista_e_do_designer(con):
    _, d2 = _designers(con)
    pid = _pedido(con)
    gm = Gmail()
    gm.threads = {"t-arte": [{"message_id": "d1", "de": "Designer Dois <designer.dois@example.com>",
                              "assunto": f"Arte Suits #{pid}", "corpo": "segue a v2", "anexos": []}]}
    gm.buscas = {"from:designer.dois@example.com": ["t-arte"]}
    eventos = sp.conversas_novas(con, gm)
    assert [(e["tipo"], e["pedido_id"]) for e in eventos] == [("designer", pid)]


def test_puxar_do_gmail_liga_so_o_que_falta_e_so_a_conversa_certa(con):
    d1, _ = _designers(con)
    forn = inserir(con, "suit_suppliers", name="Ateliê Fictício", email="atelie@example.com", is_current=1)
    outro = _pedido(con, title="Outro Ficticio", customer_email="outro@example.com", driver_name="Outro Ficticio",
                    gmail_thread_cliente="t-de-outro")
    pid = _pedido(con)
    gm = Gmail()
    gm.threads = {
        "t-de-outro": [{"message_id": "x", "de": "nina.ficticia@example.com", "assunto": "suit", "corpo": "racing suit", "anexos": []}],
        "t-academy": [{"message_id": "a", "de": "nina.ficticia@example.com", "assunto": "Academy", "corpo": "training day", "anexos": []}],
        "t-suit": [{"message_id": "s", "de": "nina.ficticia@example.com", "assunto": "My custom suit", "corpo": "the racing suit measurements", "anexos": []}],
        "t-design": [{"message_id": "d", "de": "designer.um@example.com", "assunto": f"Suits #{pid}", "corpo": "arte v1", "anexos": []}],
        "t-design-outro": [{"message_id": "e", "de": "designer.um@example.com", "assunto": f"Suits #{pid}5", "corpo": "", "anexos": []}],
        "t-forn": [{"message_id": "f", "de": "atelie@example.com", "assunto": "SUIT - Theo Ficticio", "corpo": "ok", "anexos": []}],
    }
    gm.buscas = {"nina.ficticia@example.com": ["t-de-outro", "t-academy", "t-suit"],
                 "designer.um@example.com": ["t-design-outro", "t-design"], "atelie@example.com": ["t-forn"]}
    r = sp.achar_conversas(con, pid, gm)
    assert r["ligadas"] == {"cliente": "t-suit", "designer": "t-design", "fornecedor": "t-forn"} and r["faltam"] == []
    p = um(con, "SELECT * FROM suit_orders WHERE id=?", (pid,))
    assert (p["gmail_thread_cliente"], p["gmail_thread_designer"], p["gmail_thread_fornecedor"]) == ("t-suit", "t-design", "t-forn")
    assert um(con, "SELECT gmail_thread_cliente FROM suit_orders WHERE id=?", (outro,))["gmail_thread_cliente"] == "t-de-outro"
    # de novo: nada falta, nada muda
    assert sp.achar_conversas(con, pid, gm) == {"ligadas": {}, "faltam": []}
    assert forn and d1


@pytest.fixture()
def cli(tmp_path):
    os.environ["CC_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "cc-designers.sqlite")
    os.environ["URACE_DIR"] = str(tmp_path / "urace")
    c = conectar(); aplicar_schema(c)
    sp.salvar_config(c, {"designer_email": "designer.antigo@example.com", "designer_nome": "Designer Antigo"})
    for email, papel in (("gerente@urace.us", "MANAGER"), ("op@urace.us", "OPERATOR")):
        auth.criar_usuario(c, email, papel.title() + " Fictício", papel, SENHA)
    c.commit(); c.close()
    with TestClient(app, base_url="https://cc.test") as t:
        yield t


def entra(cli, email):
    cli.cookies.clear()
    assert cli.post("/ops/api/auth/login", json={"email": email, "password": SENHA}).status_code == 200
    return {"X-CSRF": cli.cookies.get("cc_csrf")}


def test_lista_de_designers_comeca_com_o_da_configuracao_e_o_pedido_escolhe(cli):
    h = entra(cli, "gerente@urace.us")
    lista = cli.get(f"{B}/designers").json()
    assert [(d["name"], d["email"], d["is_current"]) for d in lista] == [("Designer Antigo", "designer.antigo@example.com", 1)]
    assert cli.post(f"{B}/designers", headers=h, json={"name": "Designer Dois", "email": "nao-e-email"}).status_code == 400
    novo = cli.post(f"{B}/designers", headers=h, json={"name": "Designer Dois", "email": "designer.dois@example.com"}).json()
    assert len(cli.get(f"{B}/designers").json()) == 2
    pid = cli.post(B, headers=h, json={"customer_name": "Cliente Fictício Designer"}).json()["id"]
    assert cli.get(f"{B}/{pid}").json()["designer"]["email"] == "designer.antigo@example.com"      # sem escolha, o padrão
    assert cli.patch(f"{B}/{pid}", headers=h, json={"designer_id": 9999}).status_code == 400
    assert cli.patch(f"{B}/{pid}", headers=h, json={"designer_id": novo["id"]}).status_code == 200
    assert cli.get(f"{B}/{pid}").json()["designer"]["email"] == "designer.dois@example.com"
    assert cli.patch(f"{B}/{pid}", headers=h, json={"designer_id": 0}).status_code == 200            # volta ao padrão
    assert cli.get(f"{B}/{pid}").json()["designer"]["email"] == "designer.antigo@example.com"
    h = entra(cli, "op@urace.us")
    assert cli.post(f"{B}/designers", headers=h, json={"name": "Designer Tres"}).status_code == 403   # cadastro é do gerente


def test_puxar_com_gmail_fora_vira_aviso_e_nao_erro(cli, monkeypatch):
    from command_center import providers

    def fora(nome):
        raise providers.NaoConectado("sem token do Gmail")
    monkeypatch.setattr(providers, "modulo", fora)
    h = entra(cli, "op@urace.us")
    pid = cli.post(B, headers=h, json={"customer_name": "Cliente Fictício Gmail", "customer_email": "cliente.gmail@example.com"}).json()["id"]
    r = cli.post(f"{B}/{pid}/ponte/puxar", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["puxadas"]["ligadas"] == {} and "Gmail não conectado" in r.json()["puxadas"]["aviso"]
    assert cli.post(f"{B}/99999/ponte/puxar", headers=h).status_code == 404


def test_a_ia_recebe_o_designer_e_o_fornecedor_do_pedido_com_o_contexto(con):
    """#495 (dono, 29/10: "já com os contextos"): o prompt da ponte diz quem são o designer e o fornecedor deste pedido."""
    _, d2 = _designers(con)
    con.execute("UPDATE suit_designers SET notes='entrega a arte em 48 h' WHERE id=?", (d2,))
    f = inserir(con, "suit_suppliers", name="Ateliê Fictício", contact="Ana Ateliê", email="atelie@example.com",
                comments="produz em 3 semanas; manda fotos pelo WhatsApp", is_current=0)
    pid = _pedido(con, designer_id=d2, supplier_id=f)
    cfg = sp.config(con)
    txt = sp.prompt(con, {"tipo": "cliente", "pedido_id": pid, "thread_id": "t1", "mensagens": []}, cfg, [])
    assert "DESIGNER DESTE PEDIDO: Designer Dois <designer.dois@example.com>. Contexto da equipe: entrega a arte em 48 h" in txt
    assert "FORNECEDOR DESTE PEDIDO: Ateliê Fictício (contato: Ana Ateliê) <atelie@example.com>" in txt
    assert "manda fotos pelo WhatsApp" in txt
