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
