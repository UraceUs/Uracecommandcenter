"""#455 (dono, 29/10): "as informações que estiverem no Asana serão as mesmas que estarão no Command Center,
sempre. Seja de comentários…" e "pode seguir com o espelho completo do Asana".

A descrição, as subtarefas, os comentários e os anexos de cada tarefa do quadro U-RACE ficam no banco; a
sincronia relê só o que mudou no Asana, com teto por rodada; nada se apaga; o detalhe da tarefa lê do espelho
e "Atualizar do Asana" relê na hora; o anexo abre por uma rota do painel com um link novo do Asana.
Nada aqui fala com o Asana de verdade: tudo é fictício."""
import os
from datetime import date, timedelta

import pytest

os.environ["URACE_ENV"] = "/nao/existe"

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api import auth, rotas_qbo  # noqa: E402
from command_center.api.main import app  # noqa: E402
from command_center.db import aplicar_schema, conectar, inserir, todos, um  # noqa: E402
from command_center.providers import NaoConectado, espelho_asana, sync  # noqa: E402

B = "/ops/api"
SENHA = "senha-forte-123"
SAB = "1205141832260878"          # a coluna SATURDAY do quadro (sync.SECOES_DIAS)


def _dia(n):
    return (date.today() + timedelta(days=n)).isoformat()


class Asana:
    """O Asana de mentira: seções, tarefas com descrição, subtarefas, comentários e anexos."""

    def __init__(self):
        self.secoes = [{"gid": SAB, "nome": "SATURDAY"}, {"gid": "s-races", "nome": "RACES"}, {"gid": "s-matt", "nome": "Matt tasks"}]
        self.t = {
            "7001": dict(secao=SAB, nome="Theo Ficticio_Academy [3/4]", concluida=False, vence_em=_dia(2), mod="2026-10-29T10:00:00.000Z",
                         notas="Driver's name: Theo Ficticio\nResponsible Name: Nina Ficticia\nEmail: nina.ficticia@example.com\nPhone: 555-0142",
                         subs=[{"gid": "s1", "nome": "Signed waiver?", "concluida": True, "concluida_em": "2026-10-28T12:00:00.000Z"},
                               {"gid": "s2", "nome": "Payment", "concluida": False, "responsavel": "Operador Ficticio"}],
                         coms=[{"gid": "c1", "quando": "2026-10-28T12:00:00.000Z", "quem": "Mecanico Ficticio", "texto": "trocou a corrente"},
                               {"gid": "c2", "quando": "2026-10-28T13:00:00.000Z", "quem": "Coach Ficticio", "texto": "melhor volta 41.2"}],
                         anexos=[{"gid": "a1", "nome": "waiver.pdf", "origem": "asana", "quando": "2026-10-28T12:00:00.000Z", "tamanho": 1234}]),
            "7002": dict(secao="s-races", nome="Copa Ficticia Etapa 4", concluida=False, vence_em=_dia(10), mod="2026-10-29T09:00:00.000Z",
                         notas="Pista: OKC", subs=[], anexos=[],
                         coms=[{"gid": "c9", "quando": "2026-10-27T12:00:00.000Z", "quem": "Coach Ficticio", "texto": "inscrições abertas"}]),
            "7003": dict(secao="s-matt", nome="Nunca espelhada", concluida=False, vence_em=_dia(1), mod="x", notas="sensível", subs=[], coms=[], anexos=[]),
        }
        self.chamadas = []
        self.falha = {}

    def __call__(self, sistema, ferramenta, **a):
        gid = a.get("gid") or a.get("secao_gid")
        self.chamadas.append((ferramenta, gid))
        if (ferramenta, gid) in self.falha:
            raise self.falha[(ferramenta, gid)]
        if ferramenta == "asana_secoes":
            return self.secoes
        if ferramenta == "asana_tarefas_da_secao":
            return [{"gid": g, "nome": x["nome"], "concluida": x["concluida"], "vence_em": x["vence_em"], "subtarefas": len(x["subs"]),
                     "modificada_em": x["mod"]} for g, x in self.t.items() if x["secao"] == a["secao_gid"]]
        if ferramenta == "anexo_link":
            return {"gid": gid, "download": "https://asana-anexos.example.com/arquivo-novo?assinado=1"}
        x = self.t[gid]
        if ferramenta == "asana_tarefa":
            return {"gid": gid, "nome": x["nome"], "concluida": x["concluida"], "vence_em": x["vence_em"], "notas": x["notas"],
                    "criada_em": "2026-10-01T12:00:00.000Z", "modificada_em": x["mod"], "concluida_em": None,
                    "subtarefas_lista": [dict(s) for s in x["subs"]]}
        if ferramenta == "asana_comentarios":
            return [dict(c) for c in x["coms"]]
        if ferramenta == "asana_anexos":
            return [dict(n) for n in x["anexos"]]
        raise AssertionError(ferramenta)

    def contar(self, ferramenta, gid=None):
        return sum(1 for f, g in self.chamadas if f == ferramenta and (gid is None or g == gid))


@pytest.fixture()
def con(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    c = conectar(); aplicar_schema(c)
    yield c
    c.close()


def _tid(con, gid):
    return um(con, "SELECT entity_id FROM entity_links WHERE entity_type='task' AND system='asana' AND external_id=?", (gid,))["entity_id"]


def test_sincronia_espelha_descricao_subtarefas_comentarios_e_anexos(con, monkeypatch):
    asana = Asana()
    monkeypatch.setattr(sync, "chamar", asana)
    r = sync.sync_asana(con); con.commit()
    assert r["ok"] and r["espelho"]["espelhadas"] == 2 and r["espelho"]["na_fila"] == 0
    t = um(con, "SELECT * FROM tasks WHERE id=?", (_tid(con, "7001"),))
    assert t["notes"].startswith("Driver's name: Theo Ficticio") and t["mirrored_at"] and t["asana_modified_at"] == "2026-10-29T10:00:00.000Z"
    assert (t["subtasks_total"], t["subtasks_done"]) == (2, 1)
    subs = todos(con, "SELECT gid, name, completed, assignee FROM task_subtasks WHERE task_id=? ORDER BY sort", (t["id"],))
    assert [(s["gid"], s["completed"]) for s in subs] == [("s1", 1), ("s2", 0)] and subs[1]["assignee"] == "Operador Ficticio"
    assert [c["text"] for c in todos(con, "SELECT text FROM task_comments WHERE task_id=? ORDER BY created_at", (t["id"],))] == \
        ["trocou a corrente", "melhor volta 41.2"]
    assert um(con, "SELECT name, size FROM task_attachments WHERE task_id=?", (t["id"],)) == {"name": "waiver.pdf", "size": 1234}
    # a coluna de corrida só lê o resumo da lista: o espelho lê a tarefa inteira uma vez
    corrida = um(con, "SELECT * FROM tasks WHERE id=?", (_tid(con, "7002"),))
    assert corrida["notes"] == "Pista: OKC" and um(con, "SELECT text FROM task_comments WHERE task_id=?", (corrida["id"],))["text"] == "inscrições abertas"
    # "Matt tasks": nada, nunca
    assert not any(g == "7003" for _, g in asana.chamadas)
    # segunda rodada sem mudança no Asana: nenhum comentário ou anexo relido
    antes = asana.contar("asana_comentarios")
    r = sync.sync_asana(con); con.commit()
    assert r["espelho"]["espelhadas"] == 0 and asana.contar("asana_comentarios") == antes
    assert asana.contar("asana_tarefa", "7002") == 1, "a corrida sem mudança não é relida por inteiro"


def test_o_que_sumiu_do_asana_fica_marcado_e_nada_se_apaga(con, monkeypatch):
    asana = Asana()
    monkeypatch.setattr(sync, "chamar", asana)
    sync.sync_asana(con); con.commit()
    x = asana.t["7001"]
    x["coms"] = [x["coms"][1], {"gid": "c3", "quando": "2026-10-29T11:00:00.000Z", "quem": "Mecanico Ficticio", "texto": "banco no 2"}]
    x["subs"] = x["subs"][:1]
    x["mod"] = "2026-10-29T11:00:00.000Z"
    sync.sync_asana(con); con.commit()
    tid = _tid(con, "7001")
    linhas = {c["gid"]: c["gone_at"] for c in todos(con, "SELECT gid, gone_at FROM task_comments WHERE task_id=?", (tid,))}
    assert set(linhas) == {"c1", "c2", "c3"} and linhas["c1"] and not linhas["c2"] and not linhas["c3"]
    assert um(con, "SELECT gone_at FROM task_subtasks WHERE gid='s2'")["gone_at"]
    d = espelho_asana.detalhe(con, tid, B)
    assert [c["texto"] for c in d["comments"]] == ["melhor volta 41.2", "banco no 2"]
    assert [s["gid"] for s in d["task"]["subtarefas_lista"]] == ["s1"]


def test_teto_por_rodada_das_abertas_e_mais_perto_de_hoje_para_as_antigas(con):
    asana = Asana()
    ids = {}
    for gid, status, dia in (("8001", "completed", _dia(-200)), ("8002", "open", _dia(30)), ("8003", "open", _dia(1)), ("8004", "completed", _dia(-2))):
        asana.t[gid] = dict(secao="x", nome=f"Tarefa {gid}", concluida=status == "completed", vence_em=dia, mod="m1", notas=gid, subs=[], coms=[], anexos=[])
        ids[gid] = inserir(con, "tasks", title=f"Tarefa {gid}", project="U-RACE", status=status, due_on=dia)
        inserir(con, "entity_links", entity_type="task", entity_id=ids[gid], system="asana", external_id=gid)
    fila = [(ids[g], g, None) for g in ("8001", "8002", "8003", "8004")]
    r = espelho_asana.rodada(con, fila, limite=2, chamar_fn=asana)
    assert (r["espelhadas"], r["na_fila"]) == (2, 2)
    feitas = {g for g in ids if um(con, "SELECT mirrored_at FROM tasks WHERE id=?", (ids[g],))["mirrored_at"]}
    assert feitas == {"8003", "8002"}, "as abertas primeiro, a mais perto de hoje antes"
    resto = [f for f in fila if espelho_asana.precisa(con, f[0], "m1")]
    espelho_asana.rodada(con, resto, limite=2, chamar_fn=asana)
    assert all(um(con, "SELECT mirrored_at FROM tasks WHERE id=?", (i,))["mirrored_at"] for i in ids.values())


def test_limite_da_api_para_a_rodada_sem_derrubar_a_sincronia(con, monkeypatch):
    asana = Asana()
    asana.falha[("asana_comentarios", "7001")] = Exception("HTTP 429 em GET /tasks/7001/stories: rate limit")
    monkeypatch.setattr(sync, "chamar", asana)
    r = sync.sync_asana(con); con.commit()
    assert r["ok"] and "429" in r["espelho"]["parou"]
    tid = _tid(con, "7001")
    assert um(con, "SELECT mirrored_at FROM tasks WHERE id=?", (tid,))["mirrored_at"] is None
    assert um(con, "SELECT notes FROM tasks WHERE id=?", (tid,))["notes"], "a descrição lida na sincronia já ficou"
    asana.falha.clear()
    r = sync.sync_asana(con); con.commit()
    assert um(con, "SELECT mirrored_at FROM tasks WHERE id=?", (tid,))["mirrored_at"] and r["espelho"]["parou"] is None


def test_erro_numa_tarefa_fica_nela_e_a_rodada_segue(con, monkeypatch):
    asana = Asana()
    asana.falha[("asana_anexos", "7001")] = Exception("HTTP 500 em GET /tasks/7001/attachments")
    monkeypatch.setattr(sync, "chamar", asana)
    r = sync.sync_asana(con); con.commit()
    assert r["espelho"]["erros"] == 1 and r["espelho"]["espelhadas"] == 1
    assert "HTTP 500" in um(con, "SELECT mirror_error FROM tasks WHERE id=?", (_tid(con, "7001"),))["mirror_error"]
    assert um(con, "SELECT mirrored_at FROM tasks WHERE id=?", (_tid(con, "7002"),))["mirrored_at"]


# ------------------------------------------------------------------ as rotas
@pytest.fixture()
def cli(con):
    auth.criar_usuario(con, "admin@urace.us", "Admin", "ADMIN", SENHA)
    con.commit()
    with TestClient(app, base_url="https://cc.test") as c:
        assert c.post(B + "/auth/login", json={"email": "admin@urace.us", "password": SENHA}).status_code == 200
        yield c


def _espelhado(con, monkeypatch):
    asana = Asana()
    monkeypatch.setattr(sync, "chamar", asana)
    sync.sync_asana(con); con.commit()
    return asana, _tid(con, "7001")


def _nao_chama(*a, **k):
    raise AssertionError("o detalhe espelhado não pode chamar o Asana")


def test_detalhe_le_do_espelho_sem_chamar_o_asana(cli, con, monkeypatch):
    _, tid = _espelhado(con, monkeypatch)
    monkeypatch.setattr(espelho_asana, "chamar", _nao_chama)
    d = cli.get(B + f"/tasks/{tid}/detail").json()
    assert d["connected"] and d["task"]["notas"].startswith("Driver's name") and len(d["task"]["subtarefas_lista"]) == 2
    assert [c["quem"] for c in d["comments"]] == ["Mecanico Ficticio", "Coach Ficticio"]
    assert d["attachments"][0]["download"] == f"/ops/api/tasks/{tid}/anexos/a1"
    assert d["espelho"]["em"] and d["espelho"]["aviso"] is None


def test_atualizar_do_asana_rele_na_hora_e_asana_fora_mostra_o_espelho(cli, con, monkeypatch):
    asana, tid = _espelhado(con, monkeypatch)
    asana.t["7001"]["coms"].append({"gid": "c4", "quando": "2026-10-29T12:00:00.000Z", "quem": "Nina Ficticia", "texto": "chegamos 9h"})
    asana.t["7001"]["mod"] = "2026-10-29T12:00:00.000Z"
    monkeypatch.setattr(espelho_asana, "chamar", asana)
    d = cli.get(B + f"/tasks/{tid}/detail", params={"atualizar": 1}).json()
    assert d["comments"][-1]["texto"] == "chegamos 9h" and d["task"]["modificada_em"] == "2026-10-29T12:00:00.000Z"

    def fora(*a, **k):
        raise NaoConectado("sem token do Asana")
    monkeypatch.setattr(espelho_asana, "chamar", fora)
    d = cli.get(B + f"/tasks/{tid}/detail", params={"atualizar": 1}).json()
    assert d["connected"] and "Asana fora" in d["espelho"]["aviso"] and d["comments"][-1]["texto"] == "chegamos 9h"


def test_tarefa_nunca_espelhada_le_na_hora_ou_avisa(cli, con, monkeypatch):
    tid = inserir(con, "tasks", title="Theo Ficticio_Academy [3/4]", project="U-RACE", status="open", due_on=_dia(2))
    inserir(con, "entity_links", entity_type="task", entity_id=tid, system="asana", external_id="7001")
    con.commit()

    def fora(*a, **k):
        raise NaoConectado("sem token do Asana")
    monkeypatch.setattr(espelho_asana, "chamar", fora)
    assert cli.get(B + f"/tasks/{tid}/detail").json() == {"connected": False, "reason": "sem token do Asana"}
    monkeypatch.setattr(espelho_asana, "chamar", Asana())
    d = cli.get(B + f"/tasks/{tid}/detail").json()
    assert d["connected"] and len(d["comments"]) == 2
    assert um(conectar(), "SELECT mirrored_at FROM tasks WHERE id=?", (tid,))["mirrored_at"], "e ficou no espelho"


def test_anexo_abre_com_link_novo_do_asana(cli, con, monkeypatch):
    asana, tid = _espelhado(con, monkeypatch)
    monkeypatch.setattr(rotas_qbo, "chamar", asana)
    r = cli.get(B + f"/tasks/{tid}/anexos/a1", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "https://asana-anexos.example.com/arquivo-novo?assinado=1"
    assert r.headers["cache-control"] == "no-store"
    assert cli.get(B + f"/tasks/{tid}/anexos/nao-existe", follow_redirects=False).status_code == 404
    monkeypatch.setattr(rotas_qbo, "chamar", lambda *a, **k: {"download": "javascript:alert(1)"})
    assert cli.get(B + f"/tasks/{tid}/anexos/a1", follow_redirects=False).status_code == 404
    with TestClient(app, base_url="https://cc.test") as anon:
        assert anon.get(B + f"/tasks/{tid}/anexos/a1", follow_redirects=False).status_code == 401


# ------------------------------------------------------------------ a leitura do Asana
def test_comentarios_paginados_com_gid_e_link_do_anexo_com_reserva(monkeypatch):
    import asana_mcp as a
    pedidos = []

    def paginar(caminho, params, limite=500):
        pedidos.append((caminho, limite))
        return [{"gid": f"st{i}", "created_at": f"2026-10-0{i}T00:00:00Z", "created_by": {"name": "Coach Ficticio"},
                 "text": f"t{i}", "resource_subtype": "comment_added" if i % 2 else "section_changed"} for i in range(1, 6)]
    monkeypatch.setattr(a, "_paginar", paginar)
    coms = a.asana_comentarios("123")
    assert [c["gid"] for c in coms] == ["st1", "st3", "st5"] and pedidos == [("/tasks/123/stories", 5000)]
    monkeypatch.setattr(a, "_req", lambda caminho, **k: {"data": {"gid": "9", "name": "foto.png", "download_url": None,
                                                                  "view_url": "https://app.asana.com/app/asana/-/get_asset?x=1", "host": "asana"}})
    assert a.anexo_link("9")["download"] == "https://app.asana.com/app/asana/-/get_asset?x=1"
