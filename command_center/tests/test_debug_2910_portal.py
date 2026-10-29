"""Debug 29/10: área do cliente. Número de id absurdo (maior que o do banco) volta 404/422, nunca erro 500."""
import os

import pytest

os.environ["URACE_ENV"] = "/nao/existe"

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api.main import app  # noqa: E402
from command_center.db import aplicar_schema, conectar  # noqa: E402
from command_center.tests.dados_portal import piloto  # noqa: E402

P = "/ops/api/portal"
CONTA = {"name": "Maria Santos", "email": "maria@example.com", "password": "corrida-segura-9",
         "birth_date": "1985-04-12", "phone": "(407) 555-0142", "address_line1": "100 Main St", "city": "Orlando",
         "state": "fl", "zip": "32809", "accept_terms": True}
ENORME = 99999999999999999999


@pytest.fixture()
def cli(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path))
    c = conectar(); aplicar_schema(c); c.close()
    with TestClient(app, base_url="https://cc.test", raise_server_exceptions=False) as t:
        assert t.post(f"{P}/signup", json=CONTA).status_code == 201
        yield t


def test_id_enorme_na_url_ou_no_corpo_nao_vira_erro_500(cli):
    h = {"X-CSRF": cli.cookies.get("cp_csrf")}
    assert cli.post(f"{P}/drivers", headers=h, json=piloto("Pedro Santos")).status_code == 201
    pedidos = [
        ("patch", f"/drivers/{ENORME}", {"name": "Pedro Santos"}),
        ("get", f"/bookings/{ENORME}", None),
        ("get", f"/bookings/group/{ENORME}", None),
        ("get", f"/plans/{ENORME}", None),
        ("post", f"/bookings/{ENORME}/cancel", None),
        ("get", f"/drivers/{ENORME}/qr.svg", None),
        ("post", f"/drivers/{ENORME}/waiver/review", {"typed_name": "Pedro Santos", "signature": "x"}),
        ("post", f"/drivers/{ENORME}/waiver", {"typed_name": "Pedro Santos", "signature": "x"}),
        ("post", f"/drivers/{ENORME}/waiver/events", {"event": "x"}),
        ("post", "/bookings", {"date": "2030-01-01", "period": "manha", "driver_id": ENORME, "service_id": 1}),
        ("post", "/bookings", {"date": "2030-01-01", "period": "manha", "driver_id": 1, "service_id": ENORME}),
        ("post", "/bookings/quote", {"service_id": 1, "driver_id": ENORME, "slots": [{"date": "2030-01-01", "period": "manha"}]}),
        ("post", "/bookings/batch", {"service_id": ENORME, "driver_id": 1, "slots": [{"date": "2030-01-01", "period": "manha"}]}),
        ("post", "/plans", {"service_id": ENORME, "driver_id": 1}),
        ("post", "/plans", {"service_id": 1, "driver_id": ENORME}),
    ]
    ruins = []
    for metodo, url, corpo in pedidos:
        r = getattr(cli, metodo)(P + url, headers=h, **({"json": corpo} if corpo is not None else {}))
        if r.status_code >= 500:
            ruins.append((metodo, url, r.status_code))
    assert not ruins


def test_conta_de_outro_pais_que_e_o_proprio_piloto_nasce_inteira(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc2.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path))
    c = conectar(); aplicar_schema(c); c.close()
    with TestClient(app, base_url="https://cc.test", raise_server_exceptions=False) as t:
        corpo = {**CONTA, "email": "ana@example.com", "phone_country": "+55", "phone": "11 99955 0132", "country": "BR",
                 "zip": "01000-000", "state": "SP", "i_am_driver": True}
        r = t.post(f"{P}/signup", json=corpo)
        assert r.status_code == 201, r.text
        eu = r.json()
        assert [d["is_self"] for d in eu["drivers"]] == [True] and eu["drivers"][0]["phone"] == eu["phone"]

