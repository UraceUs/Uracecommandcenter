"""Debug 29/10: CRM do Kommo. Chave estranha no hook não derruba (403, não 500) e mover de etapa
atualiza o funil e a ordem da coluna no painel, sem esperar a sincronia."""
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from command_center.api import auth, crm
from command_center.api.main import app
from command_center.db import aplicar_schema, conectar, inserir, um

B = "/ops/api"
SENHA = "senha-forte-123"


@pytest.fixture()
def cli(monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", os.path.join(tempfile.mkdtemp(), "cc-crm-debug.sqlite"))
    con = conectar(); aplicar_schema(con)
    auth.criar_usuario(con, "op@urace.us", "Op", "OPERATOR", SENHA)
    con.close()
    with TestClient(app, base_url="https://cc.test") as c:
        yield c


def test_chave_com_acento_no_hook_e_no_webhook_e_recusada_sem_erro(cli, monkeypatch):
    monkeypatch.setenv("KOMMO_HOOK_KEY", "chave-do-hook")
    monkeypatch.setenv("KOMMO_WEBHOOK_SECRET", "segredo-do-webhook")
    monkeypatch.setattr(crm, "modulo", lambda s: object())
    assert cli.post(f"{B}/crm/hook?key=chav%C3%A9", content=b"x=1").status_code == 403
    assert cli.post(f"{B}/crm/webhook?key=chav%C3%A9", json={"lead_id": "1", "text": "oi"}).status_code == 403
    assert cli.post(f"{B}/crm/webhook", json={"lead_id": "1", "text": "oi"},
                    headers={"X-Urace-Secret": "segredo".encode("latin-1") + b"\xe9"}).status_code == 403


class KommoOutroFunil:
    def mover_etapa_humano(self, lead_id, etapa_id, funil_id=None):
        return {"aplicado": True, "lead_id": lead_id, "etapa_id": etapa_id, "etapa": "Won", "funil": "Pós-venda", "ordem": 7}


def test_mover_de_etapa_atualiza_funil_e_ordem_da_coluna(cli, monkeypatch):
    monkeypatch.setattr(crm, "modulo", lambda s: KommoOutroFunil())
    con = conectar()
    lid = inserir(con, "crm_leads", external_id="7001", name="Lead fictício", pipeline_id="1", pipeline_name="Vendas",
                  stage_id="10", stage_name="Entrada", stage_order=1, synced_at="2026-01-01T00:00:00Z")
    con.close()
    assert cli.post(B + "/auth/login", json={"email": "op@urace.us", "password": SENHA}).status_code == 200
    h = {"X-CSRF": cli.cookies.get("cc_csrf")}
    assert cli.post(f"{B}/crm/leads/{lid}/stage", headers=h, json={"stage_id": "20", "pipeline_id": "2"}).status_code == 200
    con = conectar()
    try:
        l = um(con, "SELECT pipeline_id, pipeline_name, stage_name, stage_order FROM crm_leads WHERE id=?", (lid,))
    finally:
        con.close()
    assert (l["pipeline_id"], l["pipeline_name"], l["stage_name"], l["stage_order"]) == ("2", "Pós-venda", "Won", 7)
