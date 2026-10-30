"""#529: o vigia do urace.us acha o que mudou desde o conferido e avisa uma vez só (sem rede: a API é simulada)."""
import json
import os

from command_center.vitrine import vigia_urace_us as V

ANTES = {"pages": {"https://urace.us/": "2026-10-29T12:05:24", "https://urace.us/winter/": "2026-10-29T12:03:45",
                   "https://urace.us/old/": "2026-01-01T00:00:00"},
         "posts": {"https://urace.us/a/": "2026-10-01T00:00:00"}}


def test_conferido_do_repositorio_existe_e_e_do_urace_us():
    with open(V.CONFERIDO, encoding="utf-8") as f:
        d = json.load(f)
    assert set(d) == set(V.TIPOS)
    assert all(link.startswith("https://urace.us/") for itens in d.values() for link in itens)
    assert "https://urace.us/winter/" in d["pages"]


def test_mudancas_novo_mudou_e_saiu():
    hoje = {"pages": {"https://urace.us/": "2026-10-31T09:00:00", "https://urace.us/winter/": "2026-10-29T12:03:45",
                      "https://urace.us/nova/": "2026-10-31T10:00:00"},
            "posts": {"https://urace.us/a/": "2026-10-01T00:00:00"}}
    assert V.mudancas(ANTES, hoje) == [
        ("pages", "https://urace.us/", "2026-10-29T12:05:24", "2026-10-31T09:00:00"),
        ("pages", "https://urace.us/nova/", None, "2026-10-31T10:00:00"),
        ("pages", "https://urace.us/old/", "2026-01-01T00:00:00", None)]
    # tipo que não respondeu (fora de `hoje`) não acusa nada
    assert V.mudancas(ANTES, {"pages": ANTES["pages"]}) == []


def test_ler_site_pagina_e_pula_o_tipo_que_falha():
    chamadas = []

    def get(url):
        chamadas.append(url)
        if "/posts?" in url:
            raise OSError("fora do ar")
        if "/pages?" in url:
            pg = 1 if "page=1&" in url else 2
            return [{"link": f"https://urace.us/p{pg}/", "modified_gmt": "2026-10-29T00:00:00"}], {"X-WP-TotalPages": "2"}
        return [], {"X-WP-TotalPages": "1"}
    atual = V.ler_site(get)
    assert atual["pages"] == {"https://urace.us/p1/": "2026-10-29T00:00:00", "https://urace.us/p2/": "2026-10-29T00:00:00"}
    assert "posts" not in atual and set(atual) == set(V.TIPOS) - {"posts"}


class GitHub:
    def __init__(self):
        self.issues, self.comentarios = [], []

    def __call__(self, url, token=None, dados=None, metodo=None):
        assert token == "t"
        if metodo == "POST" and url.endswith("/issues"):
            self.issues.append({"number": 1, "title": dados["title"], "body": dados["body"]})
            return self.issues[-1], {}
        if metodo == "POST":
            self.comentarios.append({"body": dados["body"]})
            return {}, {}
        if "/comments" in url:
            return self.comentarios, {}
        return self.issues, {}


def test_avisa_uma_vez_e_completa_a_issue_aberta():
    gh = GitHub()
    m1 = [("pages", "https://urace.us/", "2026-10-29T12:05:24", "2026-10-31T09:00:00")]
    assert V.avisar(m1, "UraceUs/Uracecommandcenter", "t", gh) == 1
    assert len(gh.issues) == 1 and gh.issues[0]["title"] == V.TITULO and "https://urace.us/" in gh.issues[0]["body"]
    assert V.avisar(m1, "UraceUs/Uracecommandcenter", "t", gh) == 0, "a mesma mudança não volta"
    m2 = m1 + [("pages", "https://urace.us/", "2026-10-29T12:05:24", "2026-10-31T11:00:00")]
    assert V.avisar(m2, "UraceUs/Uracecommandcenter", "t", gh) == 1, "mudou de novo: comenta na mesma issue"
    assert len(gh.issues) == 1 and len(gh.comentarios) == 1 and "2026-10-31T11:00:00" in gh.comentarios[0]["body"]


def test_workflow_roda_a_cada_3_horas_com_permissao_so_de_issue():
    caminho = os.path.join(os.path.dirname(V.CONFERIDO), "..", "..", ".github", "workflows", "vigia-urace-us.yml")
    y = open(caminho, encoding="utf-8").read()
    assert 'cron: "17 */3 * * *"' in y and "workflow_dispatch" in y
    assert "contents: read" in y and "issues: write" in y
    assert "python -m command_center.vitrine.vigia_urace_us" in y
