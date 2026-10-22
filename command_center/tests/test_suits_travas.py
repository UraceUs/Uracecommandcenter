"""#382 — as travas do fluxo dos Suits: aprovação final amarrada, anexos obrigatórios, isolamento por pedido,
entrega direta ao cliente, medidas conferidas, saúde da ponte e (revisão do Mio) transições, associação sem
adivinhar, limpeza que não deixa passar, envio sem repetição, pedido de teste.

Dono, 22/10: "o envio sera direto ao cliente sem precisar enviar para a urace ... o fornecedor nos envia fotos dos
suit no whats app conferimos e passamos o endereço para o envio". A aprovação final escrita vale por e-mail; o envio
ao designer continua passando por uma pessoa. Só dados fictícios (@example.com, 555-01xx, nomes inventados).
"""
import io
import json
import os
import sqlite3
import subprocess

import pytest
from fastapi.testclient import TestClient

from command_center.api import auth
from command_center.api import suits as api_suits
from command_center.api.main import app
from command_center.db import aplicar_schema, conectar, todos, um
from command_center.providers import suits
from command_center.providers import suits_ponte as sp

TODAS = {m[0]: 50 for m in suits.MEDIDAS if m[3] == "comp" and m[0] != "bust"} | {"weight": 70, "foot": "42 EUR"}


@pytest.fixture()
def con(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "travas.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path / "urace"))
    monkeypatch.setenv("CC_EMAIL_FAKE", str(tmp_path / "enviados.jsonl"))
    c = conectar(); aplicar_schema(c)
    c.execute("INSERT INTO users (email, name, role, pw_salt, pw_hash) VALUES ('a@urace.us','Admin','ADMIN','x','x')")
    yield c
    c.close()


def _enviados(tmp_path):
    f = tmp_path / "enviados.jsonl"
    return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []


def _png(cor=(10, 20, 30)):
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (40, 30), cor).save(b, "PNG")
    return b.getvalue()


def _pedido(con, **kw):
    campos = {"title": "Dario Fictício", "customer_name": "Dario Fictício", "customer_email": "dario@example.com",
              "customer_phone": "(407) 555-0142", "ship_address": "742 Rua Inventada\nCidade Teste FL", "language": "en", **kw}
    cols = ", ".join(campos)
    return con.execute(f"INSERT INTO suit_orders ({cols}) VALUES ({', '.join('?' * len(campos))})", tuple(campos.values())).lastrowid


def _pronto(con, pid, conferir=True):
    """Arte final marcada e as medidas preenchidas (e conferidas pela equipe)."""
    con.execute("UPDATE suit_orders SET measurements=? WHERE id=?", (json.dumps(suits.normalizar_medidas(TODAS)), pid))
    sp.guardar_anexo(pid, "arte-v2.png", _png())
    suits.marcar_arte_final(con, pid, "arte-v2.png", True, 1)
    if conferir:
        suits.marcar_medidas(con, pid, list(TODAS), "conferida", user_id=1)


def _ferr(escopo=None):
    return {nome: fn for nome, _, _, _, fn in api_suits.ferramentas_ia(escopo)}


# ------------------------------------------------------------------ D: etapas e migração
def test_migracao_refaz_o_check_das_etapas_sem_perder_nada(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "antigo.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path / "urace"))
    antigo = subprocess.run(["git", "show", "origin/claude/commandcenter-vps:command_center/db/schema.sql"],
                            capture_output=True, text=True, cwd=os.path.dirname(__file__))
    if antigo.returncode != 0 or "photos_received" in antigo.stdout:
        pytest.skip("sem o schema antigo no git")
    c = sqlite3.connect(str(tmp_path / "antigo.sqlite"))
    c.executescript(antigo.stdout)
    c.execute("INSERT INTO suit_orders (title, status, tracking) VALUES ('Pedido antigo', 'in_production', 'TRK1')")
    c.execute("INSERT INTO suit_notes (order_id, text) VALUES (1, 'nota antiga')")
    c.commit(); c.close()
    con = conectar(); aplicar_schema(con)
    p = um(con, "SELECT * FROM suit_orders WHERE id=1")
    assert (p["title"], p["status"], p["tracking"]) == ("Pedido antigo", "in_production", "TRK1")    # nada mudou de etapa
    assert um(con, "SELECT text FROM suit_notes WHERE order_id=1")["text"] == "nota antiga"
    con.execute("UPDATE suit_orders SET status='photos_received' WHERE id=1")                          # a etapa nova cabe
    aplicar_schema(con)                                                                                 # de novo: não refaz
    assert um(con, "SELECT status FROM suit_orders WHERE id=1")["status"] == "photos_received"
    con.close()


def test_tabela_de_transicoes_recusa_o_salto_com_o_motivo(con):
    pid = _pedido(con)
    with pytest.raises(suits.Invalido, match="não vai para In Transit"):
        suits.mudar_etapa(con, pid, "in_transit", 1)
    con.execute("UPDATE suit_orders SET status='delivered' WHERE id=?", (pid,))
    with pytest.raises(suits.Invalido, match="nenhuma"):
        suits.mudar_etapa(con, pid, "standby", 1)
    assert set(suits.TRANSICOES) == set(suits.CODIGOS)
    assert all(d in suits.CODIGOS for v in suits.TRANSICOES.values() for d in v)


def test_entrega_direta_fotos_conferido_endereco_e_rastreio(con):
    pid = _pedido(con, status="in_production")
    with pytest.raises(suits.Invalido, match="da equipe"):
        suits.mudar_etapa(con, pid, "photos_received", por_ia=True)              # a IA não sobe foto do WhatsApp
    suits.mudar_etapa(con, pid, "photos_received", 1)
    with pytest.raises(suits.Invalido, match="exige foto"):
        suits.mudar_etapa(con, pid, "checked", 1)
    suits.anotar(con, pid, "fotos do WhatsApp", "nota", "photos_received", "foto.webp", 1)
    with pytest.raises(suits.Invalido, match="da equipe"):
        suits.mudar_etapa(con, pid, "checked", por_ia=True)
    p = um(con, "SELECT * FROM suit_orders WHERE id=?", (pid,))
    assert suits.mensagem_endereco(p, {"email": "f@example.com", "name": "Fornecedor"})["faltam"] == ["o OK da equipe nas fotos (Checked)"]
    suits.mudar_etapa(con, pid, "checked", 1)
    p = um(con, "SELECT * FROM suit_orders WHERE id=?", (pid,))
    assert p["checked_at"] and p["checked_by"] == 1
    m = suits.mensagem_endereco(p, {"email": "f@example.com", "name": "Fornecedor"})
    assert m["faltam"] == [] and "742 Rua Inventada" in m["corpo"] and "742 Rua Inventada" in m["whatsapp"]
    suits.mudar_etapa(con, pid, "address_sent", 1)
    with pytest.raises(suits.Invalido, match="rastreio"):
        suits.mudar_etapa(con, pid, "in_transit", 1)
    con.execute("UPDATE suit_orders SET tracking='TRK-0001' WHERE id=?", (pid,))
    suits.mudar_etapa(con, pid, "in_transit", 1)
    suits.mudar_etapa(con, pid, "delivered", 1)
    assert um(con, "SELECT closed FROM suit_orders WHERE id=?", (pid,))["closed"] == 1


def test_o_endereco_nunca_vai_ao_designer_nem_no_pedido_de_producao(con):
    sp.salvar_config(con, {"designer_email": "designer@example.com"})
    pid = _pedido(con)
    with pytest.raises(sp.Recusado, match="endereço"):
        sp.enviar(con, pid, "designer", f"Suits #{pid}", "Ship to 742 Rua Inventada, please")
    p = dict(um(con, "SELECT * FROM suit_orders WHERE id=?", (pid,)))
    con.execute("INSERT INTO suit_templates (key, subject, body) VALUES ('fornecedor', 'S', '{medidas}\n742 Rua Inventada')")
    e = suits.email_fornecedor(con, p, {"email": "f@example.com"}, {"name": "X"})
    assert any("endereço" in f for f in e["faltam"])


# ------------------------------------------------------------------ A: aprovação final amarrada
def test_aprovacao_amarrada_ao_hash_cai_quando_a_arte_ou_a_medida_muda(con):
    pid = _pedido(con, status="design_review")
    with pytest.raises(suits.Invalido, match="Sem a aprovação final"):
        suits.mudar_etapa(con, pid, "approved", 1)
    _pronto(con, pid)
    ap = suits.registrar_aprovacao(con, pid, "I approve the final version", "m-9", "2026-10-22", "manual", 1)
    assert ap["art_hash"] and ap["measures_hash"] and json.loads(ap["files"]) == ["arte-v2.png"]
    assert um(con, "SELECT status FROM suit_orders WHERE id=?", (pid,))["status"] == "approved"
    assert suits.aprovacao_valida(con, pid)
    # a arte final mudou (outro arquivo marcado): desatualizada, e o pedido volta para revisão
    sp.guardar_anexo(pid, "arte-v3.png", _png((200, 0, 0)))
    suits.marcar_arte_final(con, pid, "arte-v3.png", True, 1)
    e = suits.estado_aprovacao(con, pid)
    assert e["estado"] == "desatualizada" and "arte final mudou" in e["aprovacao"]["stale_reason"]
    assert um(con, "SELECT status FROM suit_orders WHERE id=?", (pid,))["status"] == "design_review"
    # nova aprovação; agora uma medida marcada suspeita derruba de novo
    suits.registrar_aprovacao(con, pid, "approved, v3", None, None, "manual", 1)
    suits.marcar_medidas(con, pid, ["waist"], "suspeita", "cintura menor que o quadril em 30 cm", por_ia=True)
    assert suits.estado_aprovacao(con, pid)["estado"] == "desatualizada"
    assert len(todos(con, "SELECT id FROM suit_approvals WHERE order_id=?", (pid,))) == 2          # nada é apagado


def test_email_de_aprovacao_final_mostra_versao_medidas_e_politica(con, tmp_path):
    sp.salvar_config(con, {"envio_automatico": "1"})
    pid = _pedido(con, status="design_review", language="pt", driver_name="Piloto Inventado")
    with pytest.raises(sp.Recusado, match="arte final"):
        sp.pedir_aprovacao_final(con, pid)
    _pronto(con, pid, conferir=False)
    with pytest.raises(sp.Recusado, match="não conferida"):
        sp.pedir_aprovacao_final(con, pid)                                  # medida não conferida trava (E)
    suits.marcar_medidas(con, pid, list(TODAS), "conferida", user_id=1)
    r = sp.pedir_aprovacao_final(con, pid, "Olá! Segue a versão final.")
    e = _enviados(tmp_path)[-1]
    v = suits.estado_aprovacao(con, pid)["versao"]
    assert r["versao"] == v and v in e["subject"] and f"version {v}" in e["text"] and f"versão final {v}" in e["text"]
    assert "non-returnable and non-refundable" in e["text"] and "não tem devolução nem reembolso" in e["text"]
    assert "1 – Head circumference — 50 cm" in e["text"] and e["anexos"] == ["arte-v2.png"]
    pf = json.loads(um(con, "SELECT final_request FROM suit_orders WHERE id=?", (pid,))["final_request"])
    assert pf["versao"] == v and pf["simulado"] is False


def test_ia_so_registra_a_aprovacao_expressa_da_versao_mostrada(con):
    sp.salvar_config(con, {"envio_automatico": "1"})
    pid = _pedido(con, status="design_review")
    _pronto(con, pid)
    msgs = {"m-gostei": {"de": "Dario <dario@example.com>", "data": "Wed, 21 Oct 2026", "corpo": "Gostei muito do mockup!",
                         "papel": "cliente"},
            "m-aprovo": {"de": "Dario <dario@example.com>", "data": "Thu, 22 Oct 2026", "corpo": "Yes, I approve the final version.",
                         "papel": "cliente"}}
    esc = {"pedido": pid, "tipo": "cliente", "email": "dario@example.com", "mensagens": msgs}
    f = _ferr(esc)
    # fora da ponte, a IA não registra
    assert "recusado" in _ferr()["suits_registrar_aprovacao"](con, 1, pid, "m-aprovo", "I approve")
    # sem o e-mail de aprovação final desta versão, "aprovo" não vale (o "gostei" era de antes)
    assert "ainda não recebeu" in f["suits_registrar_aprovacao"](con, 1, id=pid, message_id="m-gostei", trecho="Gostei muito")["recusado"]
    f["suits_pedir_aprovacao_final"](con, 1, id=pid, introducao="Here it is.")
    # trecho inventado ou mensagem que não está no evento: recusa
    assert "exatamente" in f["suits_registrar_aprovacao"](con, 1, id=pid, message_id="m-aprovo", trecho="I approve everything")["recusado"]
    assert "message_id" in f["suits_registrar_aprovacao"](con, 1, id=pid, message_id="m-x", trecho="approve")["recusado"]
    # a arte mudou depois do e-mail: o "aprovo" é de uma versão anterior e não conta
    sp.guardar_anexo(pid, "arte-v3.png", _png((1, 2, 3)))
    suits.marcar_arte_final(con, pid, "arte-v3.png", True, 1)
    assert "ainda não recebeu" in f["suits_registrar_aprovacao"](con, 1, id=pid, message_id="m-aprovo", trecho="I approve")["recusado"]
    f["suits_pedir_aprovacao_final"](con, 1, id=pid)
    r = f["suits_registrar_aprovacao"](con, 1, id=pid, message_id="m-aprovo", trecho="I approve the final version")
    assert r["ok"] and suits.aprovacao_valida(con, pid)
    ap = um(con, "SELECT * FROM suit_approvals WHERE id=?", (r["aprovacao"],))
    assert (ap["message_id"], ap["approved_at"], ap["source"]) == ("m-aprovo", "Thu, 22 Oct 2026", "ia")


def test_em_simulacao_o_email_final_nao_saiu_e_a_ia_nao_registra(con):
    pid = _pedido(con, status="design_review")
    _pronto(con, pid)
    msgs = {"m1": {"de": "dario@example.com", "data": "d", "corpo": "I approve the final version", "papel": "cliente"}}
    f = _ferr({"pedido": pid, "tipo": "cliente", "email": "dario@example.com", "mensagens": msgs})
    f["suits_pedir_aprovacao_final"](con, 1, id=pid)                     # envio automático desligado: virou nota
    assert "simulação" in f["suits_registrar_aprovacao"](con, 1, id=pid, message_id="m1", trecho="I approve")["recusado"]
    assert not suits.aprovacao_valida(con, pid)


# ------------------------------------------------------------------ B: anexos obrigatórios
def test_boas_vindas_nao_saem_sem_o_manual_e_o_manual_vai_junto(con, tmp_path):
    sp.salvar_config(con, {"envio_automatico": "1"})
    pid = _pedido(con)
    with pytest.raises(sp.Recusado, match="manual de medidas"):
        sp.enviar(con, pid, "cliente", "Welcome", "Hi Dario, thank you for your order!", tipo="boas_vindas")
    with pytest.raises(sp.Recusado, match="manual de medidas"):
        sp.enviar(con, pid, "cliente", "Welcome", "Hi Dario, thank you for your order!")       # detecta pelo texto
    with open(sp.manual_pdf(), "wb") as f:
        f.write(b"%PDF-1.4 manual")
    sp.enviar(con, pid, "cliente", "Welcome", "Hi Dario, thank you for your order!")
    assert _enviados(tmp_path)[-1]["anexos"] == ["GUIDE TO FILLING IN SIZING - URACE FORM.pdf"]
    assert um(con, "SELECT welcome_sent_at FROM suit_orders WHERE id=?", (pid,))["welcome_sent_at"]


def test_gmail_rascunho_aceita_anexos():
    import importlib.util
    caminho = os.path.join(os.path.dirname(__file__), "..", "..", "adminai", "mcp", "gmail_mcp.py")
    spec = importlib.util.spec_from_file_location("gmail_mcp_teste", caminho)
    gm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gm)
    import inspect
    assert "anexos" in inspect.signature(gm.gmail_rascunho).parameters
    gm._contas = {"urace": {"email": "urace@urace.us"}}
    os.environ.pop("APLICAR", None)
    r = gm.gmail_rascunho("urace", "f@example.com", "SUIT", "corpo", anexos=[("arte.png", b"\x89PNG", "image/png")])
    assert r["aplicado"] is False and "1 anexo" in r["teria_feito"]
    with pytest.raises(Exception):
        gm.gmail_rascunho("urace", "f@example.com", "SUIT", "corpo", anexos=["arte.png"])


# ------------------------------------------------------------------ C: isolamento e designer
def test_ferramentas_da_ponte_so_alcancam_o_pedido_do_evento(con):
    meu = _pedido(con)
    outro = _pedido(con, title="Outra Pessoa", customer_name="Outra Pessoa", customer_email="outra@example.com")
    f = _ferr({"pedido": meu, "tipo": "cliente", "email": "dario@example.com", "mensagens": {}})
    assert "suits_leads" not in f and "suits_fornecedores" not in f
    assert "proibido" in f["suits_pedido"](con, 1, id=outro)["recusado"]
    assert "recusado" in f["suits_atualizar_pedido"](con, 1, id=outro, title="x")
    assert "recusado" in f["suits_anotar"](con, 1, id=outro, texto="x")
    assert "recusado" in f["suits_email"](con, 1, id=outro, para="cliente", assunto="a", corpo="b")
    assert [p["id"] for p in f["suits_pedidos"](con, 1, busca="", estado="abertos")] == [meu]
    assert f["suits_pedido"](con, 1, id=meu)["id"] == meu
    assert "recusado" in f["suits_criar_pedido"](con, 1, title="Novo")
    # marcador sem pedido: só os da pessoa; depois de criar, só o criado
    g = _ferr({"pedido": None, "tipo": "marcador", "email": "nova@example.com", "mensagens": {}})
    assert g["suits_pedidos"](con, 1) == []
    novo = g["suits_criar_pedido"](con, 1, title="Nova Cliente", customer_email="nova@example.com")["id"]
    assert "recusado" in g["suits_pedido"](con, 1, id=meu) and g["suits_pedido"](con, 1, id=novo)["id"] == novo


def test_prompt_da_ponte_proibe_dados_de_outros_clientes(con):
    pid = _pedido(con)
    pr = sp.prompt(con, {"tipo": "cliente", "pedido_id": pid, "thread_id": "t", "mensagens": [{"message_id": "m1", "corpo": "oi"}]},
                   sp.config(con), [[]])
    assert "PROIBIDO" in pr and "outros clientes" in pr and "message_id: m1" in pr
    assert "Gostei" in pr and "EXPRESSAMENTE" in pr


def test_agente_da_ponte_nao_tem_o_painel_geral_nem_le_outro_pedido(con):
    from command_center.api import agente_sdk
    pid = _pedido(con)
    outro = _pedido(con, customer_email="outra@example.com")
    p = agente_sdk.Portao(1, True, 1, escopo={"pedido": pid, "mensagens": {}})
    assert "não está liberada" in p.decidir("mcp__painel__urace_atencao", {})
    assert "não está liberada" in p.decidir("mcp__painel__urace_clientes", {})
    assert "não está liberada" in p.decidir("mcp__gmail__gmail_buscar", {})
    assert "não está liberada" in p.decidir("WebFetch", {"url": "https://example.com"})
    assert p.decidir("Read", {"file_path": os.path.join(sp.pasta(pid), "x.png")}) is None
    assert "DESTE pedido" in p.decidir("Read", {"file_path": os.path.join(sp.pasta(outro), "x.png")})
    assert p.decidir("mcp__suits__suits_pedido", {"id": pid}) is None
    # sem evento da ponte, nada muda para o AI Command
    assert agente_sdk.Portao(1, True, 1).decidir("WebFetch", {}) is None


def test_limpar_para_designer_tira_metadados_e_recusa_dado_do_cliente(con):
    pid = _pedido(con)
    p = dict(um(con, "SELECT * FROM suit_orders WHERE id=?", (pid,)))
    from PIL import Image
    im = Image.new("RGB", (30, 20), (1, 2, 3))
    exif = Image.Exif(); exif[0x013B] = "dario@example.com"
    b = io.BytesIO(); im.save(b, "JPEG", exif=exif.tobytes())
    assert b"dario@example.com" in b.getvalue()
    (nome, dados, _), = sp.limpar_para_designer([("dario_ficticio_logo.jpg", b.getvalue(), "image/jpeg")], p)
    assert b"dario@example.com" not in dados and nome == f"Suits-{pid}-ref-1.jpg"          # metadado e nome saem
    w = io.BytesIO()
    from pypdf import PdfWriter
    pw = PdfWriter(); pw.add_blank_page(50, 50); pw.add_metadata({"/Title": "Ligar 4075550142"}); pw.write(w)
    assert sp.limpar_para_designer([("brief.pdf", w.getvalue(), "application/pdf")], p)[0][0] == "brief.pdf"
    # o PDF com o e-mail do cliente no CONTEÚDO (não é metadado: a limpeza não tira) não vai
    from pypdf.generic import DecodedStreamObject, NameObject
    pw = PdfWriter(); pg = pw.add_blank_page(100, 100)
    st = DecodedStreamObject(); st.set_data(b"BT /F1 8 Tf 10 10 Td (dario@example.com) Tj ET")
    pg[NameObject("/Contents")] = pw._add_object(st)
    w = io.BytesIO(); pw.write(w)
    with pytest.raises(sp.Recusado, match="e-mail do cliente"):
        sp.limpar_para_designer([("ficha.pdf", w.getvalue(), "application/pdf")], p)
    with pytest.raises(sp.Recusado, match="não sai"):
        sp.limpar_para_designer([("logo.ai", b"%!PS dario@example.com", "application/postscript")], p)


def test_guardas_do_designer_recusam_valor_e_endereco_em_qualquer_linha(con):
    sp.salvar_config(con, {"designer_email": "designer@example.com"})
    pid = _pedido(con)
    for corpo in ("Customer paid $420.75", "City: Cidade Teste FL", "Call (407) 555-0142"):
        with pytest.raises(sp.Recusado):
            sp.enviar(con, pid, "designer", f"Suits #{pid}", corpo)


def test_designer_preparado_vale_mesmo_com_envio_automatico_e_so_operator_envia(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "api.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path / "urace"))
    monkeypatch.setenv("CC_EMAIL_FAKE", str(tmp_path / "enviados.jsonl"))
    c = conectar(); aplicar_schema(c)
    auth.criar_usuario(c, "op@urace.us", "Op Teste", "OPERATOR", "senha-forte-123")
    auth.criar_usuario(c, "viewer@urace.us", "Viewer Teste", "VIEWER", "senha-forte-123")
    sp.salvar_config(c, {"envio_automatico": "1", "designer_email": "designer@example.com"})
    pid = _pedido(c)
    sp.guardar_anexo(pid, "inspiracao.png", _png())
    r = sp.enviar(c, pid, "designer", f"Suits #{pid} brief", "Black and red, number 7", ["inspiracao.png"])
    assert r["preparado"] and _enviados(tmp_path) == []
    c.close()
    with TestClient(app, base_url="https://cc.test") as cli:
        def entra(email):
            cli.cookies.clear()
            assert cli.post("/ops/api/auth/login", json={"email": email, "password": "senha-forte-123"}).status_code == 200
            return {"X-CSRF": cli.cookies.get("cc_csrf")}
        h = entra("viewer@urace.us")
        assert cli.post(f"/ops/api/suits/{pid}/preparados/{r['item']}/enviar", headers=h).status_code == 403
        h = entra("op@urace.us")
        p = cli.get(f"/ops/api/suits/{pid}").json()
        assert p["preparados"][0]["status"] == "preparado" and p["preparados"][0]["attachments"] == ["inspiracao.png"]
        p = cli.post(f"/ops/api/suits/{pid}/preparados/{r['item']}/enviar", headers=h).json()
        assert p["preparados"][0]["status"] == "enviado"
        assert _enviados(tmp_path)[-1]["to"] == "designer@example.com" and _enviados(tmp_path)[-1]["anexos"] == ["inspiracao.png"]


# ------------------------------------------------------------------ E: medidas
def test_estado_das_medidas_ia_so_marca_suspeita_e_mudar_o_valor_volta_a_preenchida(con):
    pid = _pedido(con)
    con.execute("UPDATE suit_orders SET measurements=? WHERE id=?", (json.dumps(suits.normalizar_medidas({"head": 59})), pid))
    with pytest.raises(suits.Invalido, match="só marca"):
        suits.marcar_medidas(con, pid, ["head"], "conferida", por_ia=True)
    with pytest.raises(suits.Invalido, match="por que"):
        suits.marcar_medidas(con, pid, ["head"], "suspeita", "", por_ia=True)
    with pytest.raises(suits.Invalido, match="não foi preenchida"):
        suits.marcar_medidas(con, pid, ["neck"], "conferida", user_id=1)
    e = suits.marcar_medidas(con, pid, ["head"], "suspeita", "59 cm parece pouco", por_ia=True)
    assert e["head"] == {"estado": "suspeita", "motivo": "59 cm parece pouco", "por": "ia", "em": e["head"]["em"]}
    assert "1 medida(s) suspeita(s)" in suits.estado_aprovacao(con, pid)["bloqueios"]
    assert len(suits.faltando(json.loads(um(con, "SELECT measurements FROM suit_orders WHERE id=?", (pid,))["measurements"]))) == 28
    antes = {"head": {"v": 59.0, "u": "cm"}}
    assert suits.situacao_depois_de_mudar(antes, {"head": {"v": 60.0, "u": "cm"}}, {"head": {"e": "conferida"}}) == {}
    assert suits.situacao_depois_de_mudar(antes, antes, {"head": {"e": "conferida"}}) == {"head": {"e": "conferida"}}


# ------------------------------------------------------------------ F: saúde da ponte
class Gmail:
    def __init__(self):
        self.threads, self.buscas = {}, {}

    def gmail_buscar(self, conta, consulta, so_inbox=True, maximo=20):
        for chave, ids in self.buscas.items():
            if chave in consulta:
                return {"threads": [{"thread_id": t} for t in ids]}
        return {"threads": []}

    def mensagens_da_thread(self, conta, thread_id, limite=8000):
        return {"thread_id": thread_id, "mensagens": [dict(m) for m in self.threads.get(thread_id, [])]}

    def anexo_bytes(self, *a):
        return b""


def test_saude_por_pedido_e_ultima_rodada(con):
    pid = _pedido(con, gmail_thread_cliente="t-cli")
    gm = Gmail()
    gm.threads = {"t-cli": [{"message_id": "c1", "de": "Dario <dario@example.com>", "assunto": "Re", "corpo": "oi", "anexos": []}]}

    def falha(con_, cid, *a):
        con_.execute("UPDATE ai_commands SET status='FAILED', error='a IA caiu no teste' WHERE id=?", (cid,))
    r = sp.rodar(con, gm, falha)
    p = suits.detalhe(con, pid)
    assert p["saude_ponte"]["ultima_tentativa"] and p["saude_ponte"]["ultimo_erro"] == "a IA caiu no teste"
    assert p["saude_ponte"]["modo"] == "simulacao" and p["saude_ponte"]["ultimo_sucesso"] is None
    assert p["proxima_acao"] and r["erros"]
    u = sp.ultima_rodada(con)
    assert u["eventos"] == 1 and u["erros"] == 1 and u["simulacao"] is True
    # falhou: o e-mail NÃO foi dado por lido; volta no próximo ciclo e, depois do limite, vai para a equipe
    assert not um(con, "SELECT 1 AS x FROM suit_email_seen WHERE message_id='c1'")
    sp.rodar(con, gm, falha)
    assert not um(con, "SELECT 1 AS x FROM suit_email_seen WHERE message_id='c1'")
    sp.rodar(con, gm, falha)
    assert um(con, "SELECT 1 AS x FROM suit_email_seen WHERE message_id='c1'")
    assert um(con, "SELECT 1 AS x FROM ai_events WHERE kind='suit.humano' AND entity_id=?", (pid,))
    assert sp.rodar(con, gm, falha)["eventos"] == 0
    # deu certo: último sucesso
    gm.threads["t-cli"].append({"message_id": "c2", "de": "dario@example.com", "assunto": "Re", "corpo": "de novo", "anexos": []})
    sp.rodar(con, gm, lambda *a: None)
    assert suits.detalhe(con, pid)["saude_ponte"]["ultimo_sucesso"]
    assert um(con, "SELECT 1 AS x FROM suit_email_seen WHERE message_id='c2'")


# ------------------------------------------------------------------ revisão do Mio: associação sem adivinhar
def test_email_que_casa_com_dois_pedidos_nao_liga_a_nenhum(con):
    um_ = _pedido(con)
    dois = _pedido(con, title="Dario Fictício (2)", driver_name="Dario Fictício")
    con.execute("INSERT INTO suit_suppliers (name, email, is_current) VALUES ('Fornecedor','f@example.com',1)")
    gm, chamadas = Gmail(), []
    gm.threads = {"t-novo": [{"message_id": "n1", "de": "Dario <dario@example.com>", "assunto": "my suit", "corpo": "the suit"}],
                  "t-forn": [{"message_id": "f1", "de": "f@example.com", "assunto": "Re: SUIT - Dario Fictício", "corpo": "ok"}]}
    gm.buscas = {"from:(dario@example.com)": ["t-novo"], "label:Suits": ["t-forn"]}
    r = sp.rodar(con, gm, lambda c, cid, *a: chamadas.append(cid))
    assert chamadas == [] and r["ambiguos"] == 2
    for pid in (um_, dois):
        p = um(con, "SELECT gmail_thread_cliente, gmail_thread_fornecedor FROM suit_orders WHERE id=?", (pid,))
        assert p["gmail_thread_cliente"] is None and p["gmail_thread_fornecedor"] is None
    avisos = todos(con, "SELECT summary FROM ai_events WHERE kind='suit.humano' AND entity_id IS NULL")
    assert len(avisos) == 2 and all("mais de um pedido" in a["summary"] for a in avisos)
    # a mesma thread ligada a dois pedidos também não vira evento de nenhum
    con.execute("UPDATE suit_orders SET gmail_thread_cliente='t-dupla' WHERE id IN (?,?)", (um_, dois))
    gm.threads["t-dupla"] = [{"message_id": "d1", "de": "dario@example.com", "assunto": "Re", "corpo": "?"}]
    gm.buscas = {}
    assert sp.rodar(con, gm, lambda c, cid, *a: chamadas.append(cid))["eventos"] == 0 and chamadas == []


# ------------------------------------------------------------------ revisão do Mio: limpeza que não deixa passar
def test_limpeza_que_falha_bloqueia_nos_dois_sentidos(con):
    sp.salvar_config(con, {"envio_automatico": "1", "designer_email": "designer@example.com"})
    pid = _pedido(con)
    sp.guardar_anexo(pid, "quebrada.png", b"\x89PNG isto nao e uma imagem")
    with pytest.raises(sp.Recusado, match="não deu para limpar"):
        sp.enviar(con, pid, "cliente", "Your art", "Attached.", ["quebrada.png"])
    with pytest.raises(sp.Recusado, match="não deu para limpar"):
        sp.enviar(con, pid, "designer", f"Suits #{pid}", "Attached.", ["quebrada.png"])
    sp.guardar_anexo(pid, "vetor.svg", b"<svg/>")
    with pytest.raises(sp.Recusado, match="não sai"):
        sp.enviar(con, pid, "cliente", "Your art", "Attached.", ["vetor.svg"])


# ------------------------------------------------------------------ revisão do Mio: envio sem repetição
def test_mesmo_email_nao_sai_duas_vezes_e_o_enviando_pendente_e_conferido(con, tmp_path):
    sp.salvar_config(con, {"envio_automatico": "1"})
    pid = _pedido(con, gmail_thread_cliente="t-cli")
    r1 = sp.enviar(con, pid, "cliente", "Update", "Your suit is in production.", gm=Gmail())
    r2 = sp.enviar(con, pid, "cliente", "Update", "Your suit is in production.", gm=Gmail())
    assert not r1.get("repetido") and r2["repetido"] and len(_enviados(tmp_path)) == 1
    # o processo caiu entre o envio e o registro: a linha ficou "enviando"; a mensagem está na thread → não reenvia
    gm = Gmail()
    gm.threads = {"t-cli": [{"message_id": "ja-saiu", "de": "URACE <urace@urace.us>", "assunto": "Re: Shipping soon"}]}
    chave = sp._chave_envio(pid, "cliente", "Shipping soon", "It ships next week.", [])
    con.execute("INSERT INTO suit_sends (chave, order_id, papel, para, assunto, thread_id) VALUES (?,?,?,?,?,?)",
                (chave, pid, "cliente", "dario@example.com", "Shipping soon", "t-cli"))
    assert sp.conferir_pendentes(con, gm) == 1
    r = sp.enviar(con, pid, "cliente", "Shipping soon", "It ships next week.", gm=gm)
    assert r["repetido"] and r["id"] == "ja-saiu" and len(_enviados(tmp_path)) == 1
    # "enviando" que NÃO saiu: confere, não acha, e manda
    chave = sp._chave_envio(pid, "cliente", "Other", "Another text.", [])
    con.execute("INSERT INTO suit_sends (chave, order_id, papel, para, assunto, thread_id) VALUES (?,?,?,?,?,?)",
                (chave, pid, "cliente", "dario@example.com", "Other", "t-cli"))
    assert not sp.enviar(con, pid, "cliente", "Other", "Another text.", gm=Gmail()).get("repetido")
    assert len(_enviados(tmp_path)) == 2 and um(con, "SELECT status FROM suit_sends WHERE chave=?", (chave,))["status"] == "enviado"


# ------------------------------------------------------------------ revisão do Mio: IA desligada ao nascer, pedido de teste
def test_pedido_nasce_com_a_ia_desligada_e_pedido_de_teste_nunca_envia(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "api.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path / "urace"))
    monkeypatch.setenv("CC_EMAIL_FAKE", str(tmp_path / "enviados.jsonl"))
    c = conectar(); aplicar_schema(c)
    auth.criar_usuario(c, "op@urace.us", "Op Teste", "OPERATOR", "senha-forte-123")
    sp.salvar_config(c, {"envio_automatico": "1", "designer_email": "designer@example.com"})
    c.close()
    with TestClient(app, base_url="https://cc.test") as cli:
        cli.post("/ops/api/auth/login", json={"email": "op@urace.us", "password": "senha-forte-123"})
        h = {"X-CSRF": cli.cookies.get("cc_csrf")}
        p = cli.post("/ops/api/suits", headers=h, json={"customer_name": "Sem IA", "ia_ligada": False}).json()
        assert p["ia_ligada"] == 0
        t = cli.post("/ops/api/suits", headers=h, json={"customer_name": "Card de Teste", "customer_email": "teste@example.com",
                                                        "is_test": True}).json()
        assert t["is_test"] == 1
        resumo = cli.get("/ops/api/suits/resumo").json()
        assert resumo["abertos"] == 1 and resumo["testes"] == 1                       # o de teste não conta
    con = conectar()
    try:
        for papel in ("cliente", "designer", "fornecedor"):
            if papel == "fornecedor":
                con.execute("INSERT INTO suit_suppliers (name, email, is_current) VALUES ('F','f@example.com',1)")
            r = sp.enviar(con, t["id"], papel, f"Suits #{t['id']}", "Black and red.")
            assert r["simulado"] is True
        assert _enviados(tmp_path) == []
        sp.precisa_humano(con, t["id"], "teste")
        assert not um(con, "SELECT 1 AS x FROM ai_events WHERE kind='suit.humano' AND entity_id=?", (t["id"],))   # nem na Atenção
        f = _ferr()
        assert f["suits_criar_pedido"](con, 1, title="IA sem IA", ia_ligada=False)["id"]
    finally:
        con.close()
