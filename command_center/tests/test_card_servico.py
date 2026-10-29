"""#460 (dono, 29/10): "antes de linha do tempo, coloca dados do cliente ... medidas, nome responsável, idade, waiver,
... parentesco, classe" e "ir para o card do serviço do cliente dentro do Command Center ... ver mais pelo Command
Center do que pelo Asana".

O card do cliente traz os dados (medidas, parentesco, classe) e, na linha do tempo, o resumo de cada serviço; o card
do serviço lê o espelho; anotar e concluir subtarefa escrevem no Asana e o espelho relê. Tudo fictício."""
import json

import pytest

from command_center import providers
from command_center.db import inserir, um
from command_center.providers import espelho_asana, sync
from command_center.tests.test_espelho_asana import B, Asana, _tid, cli, con  # noqa: F401 - fixtures


def _h(c):
    return {"X-CSRF": c.cookies.get("cc_csrf")}


ROTAS_DE_ESCRITA = ("comentar_humano", "concluir_subtarefa_humano")


class AsanaQueEscreve(Asana):
    """O Asana fictício que também aceita comentário e conclusão de subtarefa (e guarda o que veio)."""

    def __init__(self):
        super().__init__()
        self.escritas = []

    def __call__(self, sistema, ferramenta, **a):
        if ferramenta == "comentar_humano":
            self.escritas.append((ferramenta, a))
            self.t[a["gid"]]["coms"].append({"gid": "c-novo", "quando": "2026-10-29T15:00:00.000Z", "quem": "Integração", "texto": a["texto"]})
            self.t[a["gid"]]["mod"] = "2026-10-29T15:00:00.000Z"
            return {"aplicado": True, "story_gid": "c-novo"}
        if ferramenta == "concluir_subtarefa_humano":
            self.escritas.append((ferramenta, a))
            for s in self.t[a["gid_tarefa"]]["subs"]:
                if s["gid"] == a["gid_subtarefa"]:
                    s["concluida"] = True
            return {"aplicado": True}
        return super().__call__(sistema, ferramenta, **a)


@pytest.fixture()
def espelhado(con, monkeypatch):  # noqa: F811
    asana = AsanaQueEscreve()
    for mod in (sync, espelho_asana, providers):
        monkeypatch.setattr(mod, "chamar", asana)
    sync.sync_asana(con); con.commit()
    tid = _tid(con, "7001")
    cid = inserir(con, "clients", name="Nina Ficticia", pilot_name="Theo Ficticio", pilot_dob="2014-03-02",
                  email="nina.ficticia@example.com", phone="555-0142", status="ACTIVE")
    con.execute("UPDATE tasks SET client_id=? WHERE id=?", (cid, tid)); con.commit()
    return asana, tid, cid


def test_comentar_escreve_no_asana_com_o_nome_e_o_espelho_rele(cli, con, espelhado):  # noqa: F811
    asana, tid, _ = espelhado
    r = cli.post(B + f"/tasks/{tid}/comentar", headers=_h(cli), json={"texto": "  trocou o banco  "})
    assert r.status_code == 200, r.text
    assert asana.escritas == [("comentar_humano", {"gid": "7001", "texto": "Admin (Command Center): trocou o banco"})]
    assert r.json()["comments"][-1]["texto"] == "Admin (Command Center): trocou o banco"
    assert um(con, "SELECT 1 FROM audit_logs WHERE event='task.comment' AND entity_id=?", (str(tid),))
    assert cli.post(B + f"/tasks/{tid}/comentar", headers=_h(cli), json={"texto": "   "}).status_code == 400
    assert cli.post(B + f"/tasks/{tid}/comentar", headers=_h(cli), json={"texto": "x" * 4001}).status_code == 400
    assert len(asana.escritas) == 1


def test_comentar_em_tarefa_protegida_volta_409_sem_gravar(cli, con, espelhado, monkeypatch):  # noqa: F811
    asana, tid, _ = espelhado

    def recusa(sistema, ferramenta, **a):
        if ferramenta in ROTAS_DE_ESCRITA:
            raise RuntimeError("RECUSADO (tarefa do ADM URACE)")
        return asana(sistema, ferramenta, **a)
    monkeypatch.setattr(providers, "chamar", recusa)
    assert cli.post(B + f"/tasks/{tid}/comentar", headers=_h(cli), json={"texto": "oi"}).status_code == 409
    assert not um(con, "SELECT 1 FROM audit_logs WHERE event='task.comment'")


def test_concluir_subtarefa_so_a_aberta_e_do_proprio_servico(cli, con, espelhado):  # noqa: F811
    asana, tid, _ = espelhado
    assert cli.post(B + f"/tasks/{tid}/subtarefas/s1/concluir", headers=_h(cli)).status_code == 409        # já concluída
    assert cli.post(B + f"/tasks/{tid}/subtarefas/nao-existe/concluir", headers=_h(cli)).status_code == 404
    r = cli.post(B + f"/tasks/{tid}/subtarefas/s2/concluir", headers=_h(cli))
    assert r.status_code == 200, r.text
    assert asana.escritas == [("concluir_subtarefa_humano", {"gid_tarefa": "7001", "gid_subtarefa": "s2"})]
    assert all(s["concluida"] for s in r.json()["task"]["subtarefas_lista"])


def test_card_do_servico_traz_cliente_pecas_e_checklist(cli, con, espelhado):  # noqa: F811
    _, tid, cid = espelhado
    dia = um(con, "SELECT due_on FROM tasks WHERE id=?", (tid,))["due_on"]
    item = inserir(con, "stock_items", kind="peca", tracking="quantidade", name="Corrente 428")
    pi = inserir(con, "parts_invoices", client_id=cid, service_date=dia, status="aberta", total=86.0)
    inserir(con, "stock_charges", client_id=cid, parts_invoice_id=pi, item_id=item, qty=1)
    inserir(con, "parts_invoices", client_id=cid, service_date=dia, status="anulada", total=10.0)
    con.execute("UPDATE clients SET measures=? WHERE id=?", (json.dumps({"suit_size": "Kid 10", "height_in": 55}), cid)); con.commit()
    d = cli.get(B + f"/tasks/{tid}/servico").json()
    assert d["tarefa"]["id"] == tid and d["servico"]["connected"]
    assert d["cliente"]["id"] == cid and d["cliente"]["tamanhos"] == {"suit_size": "Kid 10"}
    assert [p["id"] for p in d["pecas_do_dia"]] == [pi] and d["pecas_do_dia"][0]["itens"] == [{"nome": "Corrente 428", "qtd": 1}]
    assert d["pecas_do_dia"][0]["total"] == 86.0                      # o ADMIN vê o financeiro
    assert cli.get(B + "/tasks/999999/servico").status_code == 404


def test_dados_do_cliente_parentesco_classe_e_medidas(cli, con, espelhado):  # noqa: F811
    _, tid, cid = espelhado
    assert cli.patch(B + f"/clients/{cid}", headers=_h(cli), json={"racing_class": "Formula Ficticia"}).status_code == 400
    assert cli.patch(B + f"/clients/{cid}", headers=_h(cli), json={"measures": {"height_in": 500}}).status_code == 400
    r = cli.patch(B + f"/clients/{cid}", headers=_h(cli), json={"relationship": "mãe", "racing_class": "Cadet",
                                              "measures": {"height_in": "55", "suit_size": "Kid 10", "chave_estranha": 1}})
    assert r.status_code == 200, r.text
    c = cli.get(B + f"/clients/{cid}").json()
    d = c["client"]["dados"]
    assert d["parentesco"] == "mãe" and d["parentesco_de"] == "card"
    assert d["classe"] == "Cadet" and d["classe_de"] == "card" and "Cadet" in d["classes"]
    assert d["medidas"] == {"height_in": 55.0, "suit_size": "Kid 10"} and d["medidas_fonte"][0]["de"] == "equipe"
    ev = next(e for e in c["timeline"] if e["kind"] == "SERVICE" and e["entity"]["id"] == tid)
    assert ev["servico"]["subtarefas"] == [1, 2] and ev["servico"]["comentarios"] == 2
    assert ev["servico"]["ultimo_comentario"]["texto"] == "melhor volta 41.2"
    assert all("notes" not in t for t in c["tasks"])                 # a descrição do Asana não vai nas listas


def test_card_do_servico_waiver_anulada_nao_vale_e_a_valida_vence_a_reenviada(cli, con, espelhado):  # noqa: F811
    """debug 29/10: o card do serviço lia a waiver mais recente pelo status cru — a anulada (que continua `completed`)
    aparecia como assinada, e um reenvio ainda não assinado escondia a assinada que vale (o card do cliente já separava)."""
    _, tid, cid = espelhado
    base = dict(client_id=cid, template="adult", signer_name="Nina Ficticia", signer_email="nina.ficticia@example.com")
    anulada = inserir(con, "waivers", status="completed", sent_at="2026-09-01T10:00:00Z", completed_at="2026-09-01T11:00:00Z",
                      expires_at="2027-09-01", **base)
    inserir(con, "waiver_voids", waiver_id=anulada, by_name="Gerente", reason="assinada pelo responsável errado")
    con.commit()
    assert cli.get(B + f"/tasks/{tid}/servico").json()["cliente"]["waiver"]["status"] == "voided"
    inserir(con, "waivers", status="completed", sent_at="2026-09-02T10:00:00Z", completed_at="2026-09-02T11:00:00Z",
            expires_at="2027-09-02", **base)
    inserir(con, "waivers", status="sent", sent_at="2026-10-20T10:00:00Z", **base)
    con.commit()
    w = cli.get(B + f"/tasks/{tid}/servico").json()["cliente"]["waiver"]
    assert w["status"] == "completed" and w["expires_at"] == "2027-09-02"


def test_limpar_parentesco_e_classe_com_null_como_a_tela_manda(cli, con, espelhado):  # noqa: F811
    """debug 29/10: a tela de Editar dados manda `null` para esvaziar o parentesco e a classe, e o servidor tratava
    `null` como "não mexe": o campo voltava igual. Sem a chave, continua não mexendo."""
    _, _, cid = espelhado
    assert cli.patch(B + f"/clients/{cid}", headers=_h(cli), json={"relationship": "mãe", "racing_class": "Cadet"}).status_code == 200
    assert cli.patch(B + f"/clients/{cid}", headers=_h(cli), json={"notes": "só a nota"}).status_code == 200
    c = um(con, "SELECT relationship, racing_class FROM clients WHERE id=?", (cid,))
    assert (c["relationship"], c["racing_class"]) == ("mãe", "Cadet")
    assert cli.patch(B + f"/clients/{cid}", headers=_h(cli), json={"relationship": None, "racing_class": None}).status_code == 200
    c = um(con, "SELECT relationship, racing_class FROM clients WHERE id=?", (cid,))
    assert (c["relationship"], c["racing_class"]) == (None, None)


def test_medida_editada_pela_equipe_nao_congela_as_do_site(cli, con, espelhado):  # noqa: F811
    """Debug 29/10: editar UMA medida no card não copia as do site como "da equipe"; o que o cliente atualizar depois
    no site continua aparecendo, e esvaziar a medida da equipe volta a valer a do site."""
    _, _, cid = espelhado
    conta = con.execute("""INSERT INTO portal_accounts (email, pw_salt, pw_hash, name, birth_date, phone, address_line1, city,
                           state, zip, terms_accepted_at, client_id) VALUES ('nina.site@example.com','s','h','Nina Ficticia',
                           '1985-02-01','555-0142','100 Rua Ficticia','Orlando','FL','32824','2026-09-01T00:00:00Z',?)""",
                        (cid,)).lastrowid
    pil = con.execute("INSERT INTO portal_pilots (account_id, name, client_id, measures, measures_updated_at) VALUES (?, 'Theo Ficticio', ?, ?, ?)",
                      (conta, cid, json.dumps({"height_in": 55, "weight_lb": 80}), "2026-10-01T12:00:00Z")).lastrowid
    con.commit()
    assert cli.patch(B + f"/clients/{cid}", headers=_h(cli), json={"measures": {"weight_lb": "82"}}).status_code == 200
    assert json.loads(um(con, "SELECT measures FROM clients WHERE id=?", (cid,))["measures"]) == {"weight_lb": 82.0}
    # a tela manda só o que mudou: mudar o peito depois não apaga o peso que a equipe já tinha conferido
    assert cli.patch(B + f"/clients/{cid}", headers=_h(cli), json={"measures": {"chest_in": "30"}}).status_code == 200
    assert json.loads(um(con, "SELECT measures FROM clients WHERE id=?", (cid,))["measures"]) == {"weight_lb": 82.0, "chest_in": 30.0}
    con.execute("UPDATE portal_pilots SET measures=?, measures_updated_at=? WHERE id=?",
                (json.dumps({"height_in": 57, "weight_lb": 81}), "2026-10-29T12:00:00Z", pil)); con.commit()
    d = cli.get(B + f"/clients/{cid}").json()["client"]["dados"]["medidas"]
    assert d["height_in"] == 57 and d["weight_lb"] == 82.0          # o site atualizou a altura; o peso é o que a equipe conferiu
    assert cli.patch(B + f"/clients/{cid}", headers=_h(cli), json={"measures": {"weight_lb": ""}}).status_code == 200
    d = cli.get(B + f"/clients/{cid}").json()["client"]["dados"]["medidas"]
    assert d["weight_lb"] == 81                                         # esvaziar volta a valer a do site
