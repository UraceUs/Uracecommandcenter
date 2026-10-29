"""Debug de 29/10 — o endereço do cliente só vai ao fornecedor com o OK da equipe nas fotos VALENDO.

Regra 11 do guia do Lucas (#382): "endereço ao fornecedor só depois do OK nas fotos". O OK é a etapa Checked; a
tabela de transições deixa voltar de Checked para Photos received (a foto tinha defeito) e reabrir o cancelado. Nesses
casos o OK deixou de valer e o endereço volta a ficar travado. Só dados fictícios (@example.com, 555-01xx)."""
import json

import pytest

from command_center.db import aplicar_schema, conectar, um
from command_center.providers import atelie_whatsapp as wa
from command_center.providers import suits
from command_center.providers import suits_ponte as sp

USMAN = "120363000000000002@g.us"


@pytest.fixture()
def con(tmp_path, monkeypatch):
    (tmp_path / "urace").mkdir()
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "endereco.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path / "urace"))
    monkeypatch.setenv("CC_WA_FAKE", str(tmp_path / "wa.jsonl"))
    monkeypatch.setenv("CC_EMAIL_FAKE", str(tmp_path / "enviados.jsonl"))
    monkeypatch.delenv("CC_WA_GRUPOS_ENV", raising=False)
    (tmp_path / "urace" / "whatsapp-grupos.env").write_text(
        f"WA_GRUPOS_APLICAR=0\nWA_GRUPOS=fornecedor\nWA_GRUPO_FORNECEDOR_NOME=Fornecedor Ficticio\nWA_GRUPO_FORNECEDOR_JID={USMAN}\n")
    c = conectar(); aplicar_schema(c)
    c.execute("INSERT INTO users (email, name, role, pw_salt, pw_hash) VALUES ('a@urace.us','Admin','ADMIN','x','x')")
    c.execute("INSERT INTO suit_suppliers (name, contact, email, is_current) VALUES "
              "('Fornecedor Ficticio', 'Usman Ficticio', 'fornecedor@example.com', 1)")
    yield c
    c.close()


def _pedido(con, status="photos_received"):
    campos = dict(title="Bruno Ficticio", customer_name="Bruno Ficticio", driver_name="Leo Ficticio", status=status,
                  customer_email="bruno@example.com", customer_phone="(407) 555-0142",
                  ship_address="742 Evergreen Terrace\nOrlando, FL 32801", design=json.dumps({"nome": "Leo Ficticio"}))
    cols = ", ".join(campos)
    pid = con.execute(f"INSERT INTO suit_orders ({cols}) VALUES ({', '.join('?' * len(campos))})", list(campos.values())).lastrowid
    suits.anotar(con, pid, "Foto do suit (WhatsApp)", "nota", "photos_received", "foto-ficticia.webp", 1)
    return pid


def _crua(con, pid):
    return dict(um(con, "SELECT * FROM suit_orders WHERE id=?", (pid,)))


def _fornecedor(con):
    return dict(um(con, "SELECT * FROM suit_suppliers WHERE is_current=1"))


def test_voltar_de_checked_para_photos_received_tira_o_ok_das_fotos(con):
    pid = _pedido(con)
    suits.mudar_etapa(con, pid, "checked", 1)
    assert suits.mensagem_endereco(_crua(con, pid), _fornecedor(con))["faltam"] == []      # com o OK, o endereço pode ir
    suits.mudar_etapa(con, pid, "photos_received", 1, "a foto mostrou um defeito na manga")
    p = _crua(con, pid)
    assert "o OK da equipe nas fotos (Checked)" in suits.mensagem_endereco(p, _fornecedor(con))["faltam"]
    with pytest.raises(wa.Recusado, match="endereço do cliente"):
        wa.guardas(p, "fornecedor", "Suits #1 — please ship to 742 Evergreen Terrace, Orlando")
    # a IA no grupo do fornecedor também não passa o endereço (nem como rascunho)
    with pytest.raises(wa.Recusado, match="endereço do cliente"):
        wa.propor(con, pid, "fornecedor", "Please ship it to 742 Evergreen Terrace, Orlando, FL 32801")
    assert um(con, "SELECT COUNT(*) AS n FROM atelie_wa_saidas")["n"] == 0


def test_reabrir_o_pedido_cancelado_tira_o_ok_das_fotos(con):
    pid = _pedido(con)
    suits.mudar_etapa(con, pid, "checked", 1)
    suits.mudar_etapa(con, pid, "canceled", 1)
    suits.mudar_etapa(con, pid, "standby", 1, "o cliente voltou")
    p = _crua(con, pid)
    assert "o OK da equipe nas fotos (Checked)" in suits.mensagem_endereco(p, _fornecedor(con))["faltam"]
    with pytest.raises(wa.Recusado, match="endereço do cliente"):
        wa.guardas(p, "fornecedor", "Call (407) 555-0142 at 742 Evergreen Terrace")


def test_conferir_de_novo_devolve_o_ok(con):
    pid = _pedido(con)
    suits.mudar_etapa(con, pid, "checked", 1)
    suits.mudar_etapa(con, pid, "photos_received", 1, "outra foto")
    suits.mudar_etapa(con, pid, "checked", 1)
    p = _crua(con, pid)
    assert p["checked_at"] and suits.mensagem_endereco(p, _fornecedor(con))["faltam"] == []
    wa.guardas(p, "fornecedor", "Please ship to 742 Evergreen Terrace")           # não levanta


# ------------------------------------------------------------------ o e-mail da ponte ao fornecedor
def _enviados(tmp_path):
    f = tmp_path / "enviados.jsonl"
    return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []


@pytest.mark.parametrize("corpo", ["Please ship it to 742 Evergreen Terrace, Orlando, FL 32801.",
                                   "The customer phone is +1 (407) 555-0142, call before delivery."])
def test_email_da_ia_ao_fornecedor_nao_leva_endereco_nem_telefone_antes_do_ok(con, tmp_path, corpo):
    """O grupo do WhatsApp já recusava; o e-mail (`suits_email para="fornecedor"`) mandava, e com o envio automático
    ligado saía de verdade."""
    sp.salvar_config(con, {"envio_automatico": "1"})
    pid = _pedido(con, status="in_production")
    with pytest.raises(sp.Recusado, match="depois do OK da equipe nas fotos"):
        sp.enviar(con, pid, "fornecedor", "SUIT - Leo Ficticio", f"Hi Usman,\n\n{corpo}\n\nBest regards")
    assert _enviados(tmp_path) == []


def test_email_ao_fornecedor_sem_dado_do_cliente_e_com_o_ok_continua_saindo(con, tmp_path):
    sp.salvar_config(con, {"envio_automatico": "1"})
    pid = _pedido(con, status="in_production")
    assert sp.enviar(con, pid, "fornecedor", "SUIT - Leo Ficticio", "Hi Usman, any update on this suit?")["simulado"] is False
    suits.mudar_etapa(con, pid, "photos_received", 1)
    suits.mudar_etapa(con, pid, "checked", 1)
    sp.enviar(con, pid, "fornecedor", "SUIT - Leo Ficticio", "Please ship it to 742 Evergreen Terrace, Orlando, FL 32801.")
    assert [e["to"] for e in _enviados(tmp_path)] == ["fornecedor@example.com", "fornecedor@example.com"]
