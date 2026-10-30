"""#527 (dono, 30/10): o Box só na confirmação do agendamento, a remarcação com 48 h e o horário da pista do painel.

Dono: *"não informe isso de cara assim, somente na confirmação de agendamento isso será passado"*; *"48h"*; o horário
da pista *"é regulado pelo command center"* (a agenda do painel, Site › Agenda).
"""
import os
import re

import pytest

os.environ.setdefault("CC_AUTOSYNC", "0")

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api.main import app  # noqa: E402
from command_center.db import aplicar_schema, conectar  # noqa: E402
from command_center.providers import agenda_sessoes as ag  # noqa: E402
from command_center.vitrine import conteudo as C  # noqa: E402
from command_center.vitrine import pg_landings  # noqa: E402

SITE = "https://novo.urace.us"


@pytest.fixture()
def cli(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path))
    monkeypatch.delenv("CC_SITE_HOSTS", raising=False)
    monkeypatch.delenv("CC_SITE_PREVIEW", raising=False)
    with TestClient(app, base_url=SITE) as t:
        yield t


def _texto(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>", "", html, flags=re.S)))


def test_endereco_com_box_so_para_a_confirmacao():
    assert C.SITE["endereco"]["rua"] == "10724 Cosmonaut Blvd"
    assert C.endereco_com_box("kart") == "10724 Cosmonaut Blvd, Box 3, Orlando, FL 32824"
    assert C.endereco_com_box("sim2grid") == "10724 Cosmonaut Blvd, Box 5, Orlando, FL 32824"


@pytest.mark.parametrize("caminho", ["/", "/contact/", "/terms/", "/sim2grid-racing-simulator/", "/academy/",
                                     "/services/arrive-and-drive/", "/kart-lessons-for-beginners/"])
def test_pagina_publica_nao_mostra_o_box(cli, caminho):
    html = cli.get(caminho).text
    assert "10724 Cosmonaut Blvd" in html, caminho
    assert not re.search(r"\bBox \d", html), caminho


def test_remarcacao_com_48_horas(cli):
    for caminho in ("/terms/", "/academy/", "/services/arrive-and-drive/", "/kart-lessons-for-beginners/"):
        texto = _texto(cli.get(caminho).text)
        assert re.search(r"48 ?h", texto), caminho
        assert not re.search(r"(notice of|least|less than) 24 ?h|24 ?hours[’'] notice|least 24 hours", texto), caminho


AGENDA = {"config": {"morning_start": "09:00", "morning_end": "13:00", "afternoon_start": "13:00", "afternoon_end": "17:00"},
          "semana": [{"weekday": d, "period": p, "open": (d, p) in {(2, "manha"), (2, "tarde"), (5, "manha"), (6, "manha")}}
                     for d in range(7) for p in ("manha", "tarde")]}


def test_horario_da_pista_sai_da_agenda():
    assert pg_landings.horario_da_pista(AGENDA) == "Wednesday 9am–1pm or 1pm–5pm; Saturday and Sunday 9am–1pm"
    # a sexta de manhã aberta no painel entra sozinha, junto do fim de semana
    sexta = {**AGENDA, "semana": [{**r, "open": r["open"] or (r["weekday"], r["period"]) == (4, "manha")}
                                  for r in AGENDA["semana"]]}
    assert pg_landings.horario_da_pista(sexta) == "Wednesday 9am–1pm or 1pm–5pm; Friday, Saturday and Sunday 9am–1pm"
    assert pg_landings.horario_da_pista({**AGENDA, "config": {**AGENDA["config"], "morning_start": "07:30"}}).startswith(
        "Wednesday 7:30am–1pm")
    assert pg_landings.horario_da_pista(None) == ""
    assert pg_landings.horario_da_pista({**AGENDA, "semana": []}) == ""


def test_formulario_das_landings_diz_o_horario_do_painel(cli):
    con = conectar()
    try:
        aplicar_schema(con)
        ag.mudar_semana(con, [{"weekday": r["weekday"], "period": r["period"], "open": r["open"]} for r in AGENDA["semana"]])
        con.commit()
    finally:
        con.close()
    html = cli.get("/kart-lessons-for-beginners/").text
    opcao = re.search(r'<input type="radio" name="x_option" value="(A - [^"]+)"', html).group(1)
    assert opcao.endswith(" - track sessions: Wednesday 9am–1pm or 1pm–5pm; Saturday and Sunday 9am–1pm)"), opcao
    assert "7am to 1pm" not in html
