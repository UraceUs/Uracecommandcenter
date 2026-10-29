"""Debug 29/10: avisos no celular. Quem foi desativado na equipe deixa de receber o aviso (nome de quem escreveu e da conversa)."""
import os
import tempfile

import pytest

os.environ["URACE_ENV"] = "/nao/existe"

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api import auth, push  # noqa: E402
from command_center.api.main import app  # noqa: E402
from command_center.db import aplicar_schema, conectar, um  # noqa: E402
from command_center.tests.test_push import WebPushFalso  # noqa: E402


@pytest.fixture()
def cli(monkeypatch, tmp_path):
    os.environ["CC_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "cc.sqlite")
    monkeypatch.setenv("URACE_DIR", str(tmp_path))
    con = conectar(); aplicar_schema(con)
    auth.criar_usuario(con, "mec@urace.us", "Mecânico Pedro", "OPERATOR", "senha-forte-123")
    auth.criar_usuario(con, "saiu@urace.us", "Ex Funcionário", "OPERATOR", "senha-forte-123")
    con.close()
    with TestClient(app, base_url="https://cc.test") as c:
        yield c


def test_aviso_nao_vai_para_usuario_desativado(cli, monkeypatch):
    falso = WebPushFalso().instalar(monkeypatch)
    con = conectar()
    try:
        ativo, inativo = (um(con, "SELECT id FROM users WHERE email=?", (e,))["id"] for e in ("mec@urace.us", "saiu@urace.us"))
        con.execute("UPDATE users SET active=0 WHERE id=?", (inativo,))
        for uid, ponta in ((ativo, "https://push.exemplo/ativo"), (inativo, "https://push.exemplo/inativo")):
            con.execute("INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth) VALUES (?,?,?,?)",
                        (uid, ponta, "chave-publica", "segredo"))
        r = push.avisar(con, [ativo, inativo], "Pedro em Pista", "Nova mensagem no chat da equipe.", "/ops/equipe/1")
    finally:
        con.close()
    assert [e[0] for e in falso.enviados] == ["https://push.exemplo/ativo"]
    assert r["enviados"] == 1
