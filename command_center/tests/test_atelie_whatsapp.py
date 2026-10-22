"""WhatsApp dos grupos do ateliê (#383): entrada dos dois grupos → pedido certo, rascunho com aprovar,
saída pela CLI do OpenClaw (falsa aqui), guardas, cobrança diária, endereço e rastreio.

Dono, 22/10: "Urace Suits - Usman" e "Macacão design Urace"; DM desligada; mensagem de outro grupo ou pessoa
é ignorada; o que sai segue a chave "envio automático" da ponte de Suits. Tudo fictício (@example.com, 555-01xx).
"""
import base64
import json
import os
import shutil
import subprocess
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from command_center.api import auth
from command_center.api.main import app
from command_center.db import aplicar_schema, conectar, um
from command_center.providers import atelie_whatsapp as wa
from command_center.providers import suits_ponte as sp

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DESIGN, USMAN, OUTRO = "120363000000000001@g.us", "120363000000000002@g.us", "120363000000000009@g.us"
SEGREDO = "segredo-de-teste-do-atelie-0123456789"


def _env(tmp_path, aplicar=0, **extra):
    (tmp_path / "urace").mkdir(exist_ok=True)
    linhas = {"WA_GRUPOS_APLICAR": str(aplicar), "WA_GRUPOS_TOKEN": SEGREDO, "WA_GRUPOS": "design,fornecedor",
              "WA_GRUPO_DESIGN_NOME": "Macacão design Urace", "WA_GRUPO_DESIGN_JID": DESIGN,
              "WA_GRUPO_FORNECEDOR_NOME": "Urace Suits - Usman", "WA_GRUPO_FORNECEDOR_JID": USMAN, **extra}
    (tmp_path / "urace" / "whatsapp-grupos.env").write_text("\n".join(f"{k}={v}" for k, v in linhas.items()) + "\n")


@pytest.fixture()
def con(tmp_path, monkeypatch):
    (tmp_path / "urace").mkdir()
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "atelie.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path / "urace"))
    monkeypatch.setenv("CC_WA_FAKE", str(tmp_path / "wa.jsonl"))
    monkeypatch.delenv("CC_WA_GRUPOS_ENV", raising=False)
    _env(tmp_path)
    c = conectar(); aplicar_schema(c)
    c.execute("INSERT INTO users (email, name, role, pw_salt, pw_hash) VALUES ('a@urace.us','Admin','ADMIN','x','x')")
    yield c
    c.close()


def _pedido(con, titulo="Bruno Ficticio", piloto="Leo Ficticio", status="design_pending", **kw):
    campos = dict(title=titulo, customer_name=titulo, driver_name=piloto, status=status,
                  customer_email="bruno@example.com", customer_phone="(407) 555-0142",
                  ship_address="742 Evergreen Terrace\nOrlando, FL 32801", design=json.dumps({"nome": piloto}), **kw)
    cols = ", ".join(campos)
    cur = con.execute(f"INSERT INTO suit_orders ({cols}) VALUES ({', '.join('?' * len(campos))})", list(campos.values()))
    return cur.lastrowid


def _enviados(tmp_path):
    f = tmp_path / "wa.jsonl"
    return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []


def _msg(jid, texto, mid, **kw):
    return {"grupo_jid": jid, "message_id": mid, "remetente": "+14075550101", "remetente_nome": "Designer Teste",
            "texto": texto, **kw}


# ------------------------------------------------------------------ entrada e vínculo
def test_grupo_fora_da_lista_e_conversa_individual_nem_sao_gravados(con):
    assert wa.receber(con, _msg(OUTRO, "Suits #1 oi", "x1")) == {"ignorada": "não é um grupo da lista"}
    assert wa.receber(con, _msg("14075550101@s.whatsapp.net", "oi", "x2"))["ignorada"]
    assert um(con, "SELECT COUNT(*) AS n FROM atelie_wa_mensagens")["n"] == 0


def test_numero_do_pedido_liga_e_a_arte_vai_para_a_pasta_do_pedido(con):
    pid = _pedido(con)
    pdf = base64.b64encode(b"%PDF-1.4 arte").decode()
    r = wa.receber(con, _msg(DESIGN, f"Arte do Suits #{pid} pronta", "d1", midias=[{"nome": "arte.pdf", "tipo": "application/pdf", "base64": pdf}]))
    assert r["pedido"] == pid and r["estado"] == "nova" and r["anexos"] == ["arte.pdf"]
    assert "arte.pdf" in sp.anexos_do_pedido(pid)
    assert wa.receber(con, _msg(DESIGN, f"Arte do Suits #{pid} pronta", "d1")) == {"repetida": True}
    nota = um(con, "SELECT text FROM suit_notes WHERE order_id=? AND kind='whatsapp'", (pid,))
    assert "Arte do Suits" in nota["text"]


def test_nome_do_piloto_liga_so_quando_e_um_pedido_so(con):
    a = _pedido(con, "Cliente Um Ficticio", "Zeca Velozz")
    _pedido(con, "Cliente Dois Ficticio", "Nina Curva")
    assert wa.receber(con, _msg(DESIGN, "segue o layout com ZECA VELOZZ nas costas", "n1"))["pedido"] == a
    _pedido(con, "Cliente Tres Ficticio", "Zeca Velozz")             # dois pedidos com o mesmo piloto
    r = wa.receber(con, _msg(DESIGN, "outra versão do Zeca Velozz", "n2"))
    assert r["pedido"] is None and r["estado"] == "ambigua"
    ev = um(con, "SELECT summary FROM ai_events WHERE kind='atelie.humano' AND entity_id=?", (r["id"],))
    assert ev and "mais de um pedido" in ev["summary"]


def test_numero_e_nome_que_discordam_e_ambiguo_nunca_adivinha(con):
    a = _pedido(con, "Cliente Um Ficticio", "Zeca Velozz")
    b = _pedido(con, "Cliente Dois Ficticio", "Nina Curva")
    r = wa.receber(con, _msg(DESIGN, f"Suits #{a}: arte da Nina Curva", "c1"))
    assert r["pedido"] is None and r["estado"] == "ambigua"
    assert set(json.loads(um(con, "SELECT candidatos FROM atelie_wa_mensagens WHERE id=?", (r["id"],))["candidatos"])) == {a, b}


def test_arquivo_sem_pedido_vai_para_a_equipe_e_a_equipe_liga(con):
    pid = _pedido(con)
    png = base64.b64encode(b"\x89PNG foto").decode()
    r = wa.receber(con, _msg(USMAN, "photos", "u1", midias=[{"nome": "foto.png", "tipo": "image/png", "base64": png}]))
    assert r["pedido"] is None and r["estado"] == "sem_pedido"
    assert um(con, "SELECT id FROM ai_events WHERE kind='atelie.humano' AND entity_id=?", (r["id"],))
    wa.vincular(con, r["id"], pid, 1)
    m = um(con, "SELECT order_id, vinculo, estado FROM atelie_wa_mensagens WHERE id=?", (r["id"],))
    assert (m["order_id"], m["vinculo"], m["estado"]) == (pid, "equipe", "nova")
    assert "foto.png" in sp.anexos_do_pedido(pid)


def test_resposta_citando_a_nossa_mensagem_liga_ao_pedido(con, tmp_path):
    _env(tmp_path, aplicar=1)
    pid = _pedido(con)
    sid = wa.propor(con, pid, "design", "Briefing: preto e vermelho, nome nas costas")["rascunho"]
    enviado = wa.aprovar(con, sid, 1)
    r = wa.receber(con, _msg(DESIGN, "ok, amanhã mando", "r1", resposta_a=enviado["message_id"]))
    assert r["pedido"] == pid and um(con, "SELECT vinculo FROM atelie_wa_mensagens WHERE id=?", (r["id"],))["vinculo"] == "resposta"


# ------------------------------------------------------------------ saída
def test_envio_automatico_desligado_vira_rascunho_e_nada_sai(con, tmp_path):
    pid = _pedido(con)
    r = wa.propor(con, pid, "design", "Briefing do design")
    assert r["rascunho"] and _enviados(tmp_path) == []
    s = um(con, "SELECT estado, texto FROM atelie_wa_saidas WHERE id=?", (r["rascunho"],))
    assert s["estado"] == "rascunho" and s["texto"].startswith(f"Suits #{pid}")
    with pytest.raises(wa.Recusado, match="simulação"):                # sem WA_GRUPOS_APLICAR=1 não sai nem aprovado
        wa.aprovar(con, r["rascunho"], 1)
    _env(tmp_path, aplicar=1)
    wa.aprovar(con, r["rascunho"], 1)
    env = _enviados(tmp_path)
    assert len(env) == 1 and env[0]["target"] == DESIGN and f"Suits #{pid}" in env[0]["message"]
    assert um(con, "SELECT estado FROM atelie_wa_saidas WHERE id=?", (r["rascunho"],))["estado"] == "enviado"


def test_envio_automatico_ligado_sai_sozinho_menos_ao_designer_e_nunca_com_a_ia_desligada(con, tmp_path):
    _env(tmp_path, aplicar=1)
    sp.salvar_config(con, {"envio_automatico": "1"})
    pid = _pedido(con, status="in_production")
    assert wa.propor(con, pid, "fornecedor", "any update on this suit?")["enviado"] is True and len(_enviados(tmp_path)) == 1
    assert wa.propor(con, pid, "design", "Briefing")["rascunho"] and len(_enviados(tmp_path)) == 1   # #382: designer passa por uma pessoa
    con.execute("UPDATE suit_orders SET ia_ligada=0 WHERE id=?", (pid,))
    with pytest.raises(wa.Recusado, match="desligada"):
        wa.propor(con, pid, "fornecedor", "outra")


def test_pedido_de_teste_nunca_manda_de_verdade(con, tmp_path):
    _env(tmp_path, aplicar=1)
    sp.salvar_config(con, {"envio_automatico": "1"})
    pid = _pedido(con, status="in_production", is_test=1)
    assert wa.propor(con, pid, "fornecedor", "any update?")["simulado"] is True
    assert wa.propor(con, pid, "design", "oi", criado_por="user:1", user_id=1)["simulado"] is True
    assert _enviados(tmp_path) == [] and um(con, "SELECT COUNT(*) AS n FROM atelie_wa_saidas")["n"] == 0


def test_anexo_ao_designer_passa_pela_limpeza_da_ponte(con, tmp_path, monkeypatch):
    """#382: o que vai ao designer pelo grupo usa a mesma `limpar_para_designer` do e-mail."""
    _env(tmp_path, aplicar=1)
    pid = _pedido(con)
    sp.guardar_anexo(pid, "logo.svg", b"<svg><metadata>autor</metadata></svg>")
    chamadas = []

    def limpar(arquivos, pedido):
        chamadas.append((pedido["id"], [a[0] for a in arquivos]))
        if pedido.get("customer_email"):
            raise sp.Recusado("o arquivo logo.svg contém o e-mail do cliente")
        return arquivos
    monkeypatch.setattr(sp, "limpar_para_designer", limpar, raising=False)
    sid = wa.propor(con, pid, "design", "logo em anexo", ["logo.svg"])["rascunho"]
    with pytest.raises(wa.Recusado, match="e-mail do cliente"):
        wa.aprovar(con, sid, 1)
    assert chamadas == [(pid, ["logo.svg"])] and _enviados(tmp_path) == []
    con.execute("UPDATE suit_orders SET customer_email=NULL WHERE id=?", (pid,))
    wa.aprovar(con, sid, 1)
    assert _enviados(tmp_path)[-1]["media"] == ["logo.svg"]


def test_simulacao_da_ponte_vira_nota(con, tmp_path):
    pid = _pedido(con)
    marca = sp.SIMULAR.set(True)
    try:
        assert wa.propor(con, pid, "design", "Briefing")["simulado"] is True
    finally:
        sp.SIMULAR.reset(marca)
    assert um(con, "SELECT COUNT(*) AS n FROM atelie_wa_saidas")["n"] == 0


@pytest.mark.parametrize("texto, motivo", [
    ("o e-mail dele é bruno@example.com", "e-mail"),
    ("liga no 407-555-0142", "telefone"),
    ("entregar em 742 Evergreen Terrace", "endereço"),
    ("o Bruno Ficticio pediu assim", "nome completo"),
    ("ele já pagou $420", "pagamento"),
])
def test_designer_recebe_so_o_design(con, texto, motivo):
    pid = _pedido(con)
    with pytest.raises(wa.Recusado, match=motivo):
        wa.propor(con, pid, "design", texto)
    wa.propor(con, pid, "design", "nome nas costas: Leo Ficticio, bandeira do Brasil")   # o nome do design pode


def _png(cor="red"):
    import io

    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (40, 30), cor).save(b, "PNG")
    return base64.b64encode(b.getvalue()).decode()


def test_foto_do_grupo_vira_foto_do_suit_e_o_endereco_so_vai_com_checked(con, tmp_path):
    """#382 + #383: fotos (Photos received, com foto), conferido (Checked, da equipe) e só então o endereço,
    que move para Address sent; o rastreio leva a In Transit pela tabela de etapas."""
    from command_center.providers import suits
    _env(tmp_path, aplicar=1)
    pid = _pedido(con, status="in_production")
    with pytest.raises(wa.Recusado, match="endereço"):
        wa.propor(con, pid, "fornecedor", "ship to 742 Evergreen Terrace")
    with pytest.raises(wa.Recusado, match="Checked"):
        wa.mandar_endereco(con, pid, 1)
    r = wa.receber(con, _msg(USMAN, f"order #{pid} ready", "f1", midias=[{"nome": "suit.png", "tipo": "image/png", "base64": _png()}]))
    wa.foto_do_suit(con, r["id"], "suit.png", 1)
    assert um(con, "SELECT status FROM suit_orders WHERE id=?", (pid,))["status"] == "photos_received"
    assert suits.tem_foto_do_fornecedor(con, pid)
    suits.mudar_etapa(con, pid, "checked", 1)                       # o OK da equipe
    res = wa.mandar_endereco(con, pid, 1)
    assert res["enviado"] is True and "742 Evergreen Terrace" in _enviados(tmp_path)[-1]["message"]
    assert "bruno@example.com" not in _enviados(tmp_path)[-1]["message"]
    assert um(con, "SELECT status FROM suit_orders WHERE id=?", (pid,))["status"] == "address_sent"
    with pytest.raises(wa.Recusado):
        wa.registrar_rastreio(con, pid, "a b")
    wa.registrar_rastreio(con, pid, "1Z999AA10123456784", "UPS")
    p = um(con, "SELECT tracking, status FROM suit_orders WHERE id=?", (pid,))
    assert p["tracking"] == "UPS 1Z999AA10123456784" and p["status"] == "in_transit"


def test_rastreio_antes_do_endereco_grava_mas_nao_pula_etapa(con):
    pid = _pedido(con, status="in_production")
    wa.registrar_rastreio(con, pid, "1Z999AA10123456784")
    p = um(con, "SELECT tracking, status FROM suit_orders WHERE id=?", (pid,))
    assert p["tracking"] == "1Z999AA10123456784" and p["status"] == "in_production"


# ------------------------------------------------------------------ cobrança diária
def test_cobra_no_maximo_uma_vez_por_dia_por_grupo(con, tmp_path):
    _env(tmp_path, aplicar=1)
    pid = _pedido(con, status="sent_to_supplier", sent_to_supplier_at="2026-10-01T12:00:00Z")
    _pedido(con, "Pedido Teste Ficticio", "Teste Piloto", status="sent_to_supplier", sent_to_supplier_at="2026-10-01T12:00:00Z",
            is_test=1)                                                  # pedido de teste não é cobrado
    dez = datetime(2026, 10, 22, 10, 0, tzinfo=wa.FUSO)
    r = wa.cobrancas(con, dez)
    assert [(x["pedido"], x["papel"]) for x in r] == [(pid, "fornecedor")]
    assert wa.cobrancas(con, dez) == []                                # o rascunho do dia já existe
    con.execute("UPDATE atelie_wa_saidas SET estado='descartado'")
    assert wa.cobrancas(con, dez) == []                                # mesmo descartado: uma por dia
    assert wa.cobrancas(con, datetime(2026, 10, 22, 22, 0, tzinfo=wa.FUSO)) == []   # fora do horário
    con.execute("UPDATE suit_orders SET ia_ligada=0")
    assert wa.cobrancas(con, datetime(2026, 10, 23, 10, 0, tzinfo=wa.FUSO)) == []   # IA desligada: não cobra


# ------------------------------------------------------------------ a IA
def test_mensagem_nova_vai_a_ia_uma_vez_e_ia_desligada_chama_a_equipe(con):
    a, b = _pedido(con, "Cliente Um Ficticio", "Zeca Velozz"), _pedido(con, "Cliente Dois Ficticio", "Nina Curva")
    con.execute("UPDATE suit_orders SET ia_ligada=0 WHERE id=?", (b,))
    wa.receber(con, _msg(DESIGN, f"Suits #{a} arte pronta", "i1"))
    wa.receber(con, _msg(USMAN, f"order #{b} is ready", "i2", remetente_nome="Fornecedor Teste"))
    chamadas = []
    feitos = wa.tratar_pendentes(con, lambda con, cid, t, sk, uid, pr: chamadas.append(pr))
    assert len(chamadas) == 1 and "GRUPO DE DESIGN" in chamadas[0] and f"Suits #{a}" in chamadas[0]
    assert any(f.get("ia_desligada") for f in feitos)
    assert um(con, "SELECT id FROM ai_events WHERE kind='suit.humano' AND entity_id=?", (b,))
    assert wa.tratar_pendentes(con, lambda *x: chamadas.append(x)) == [] and len(chamadas) == 1


def test_ponte_de_email_manda_o_design_pelo_grupo_quando_configurado(con, tmp_path):
    pid = _pedido(con)
    pr = sp.prompt(con, {"tipo": "cliente", "pedido_id": pid, "thread_id": "t", "mensagens": []}, sp.config(con), [])
    assert 'atelie_grupo_escrever grupo="design"' in pr
    (tmp_path / "urace" / "whatsapp-grupos.env").unlink()
    assert "atelie_grupo_escrever" not in sp.prompt(con, {"tipo": "cliente", "pedido_id": pid, "thread_id": "t", "mensagens": []},
                                                    sp.config(con), [])


def test_ferramentas_da_ia_entram_no_servidor_de_suits():
    from command_center.api import agente_sdk
    nomes = [f[0] for f in wa.ferramentas_ia()]
    assert nomes == ["atelie_grupo_mensagens", "atelie_grupo_escrever", "atelie_rastreio"]
    assert "atelie_grupo_mensagens" in agente_sdk.LEITURAS
    assert not agente_sdk.RX_APROVAR.search("atelie_grupo_escrever")    # a aprovação é a do rascunho, no pedido


# ------------------------------------------------------------------ a rota de entrada
def test_entrada_so_local_com_segredo_e_sem_proxy(tmp_path, monkeypatch):
    (tmp_path / "urace").mkdir()
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "rota.sqlite"))
    monkeypatch.setenv("URACE_DIR", str(tmp_path / "urace"))
    _env(tmp_path)
    c = conectar(); aplicar_schema(c)
    auth.criar_usuario(c, "op@urace.us", "Operador Teste", "OPERATOR", "senha-forte-123")
    pid = _pedido(c)
    c.close()
    url = "/ops/api/atelie/whatsapp/entrada"
    corpo = _msg(DESIGN, f"Suits #{pid} arte", "e1")
    with TestClient(app, base_url="https://cc.test", client=("127.0.0.1", 5000)) as cli:
        assert cli.post(url, json=corpo).status_code == 401
        assert cli.post(url, json=corpo, headers={"X-Urace-Atelie-Token": "errado"}).status_code == 401
        assert cli.post(url, json=corpo, headers={"X-Urace-Atelie-Token": SEGREDO, "X-Forwarded-For": "203.0.113.9"}).status_code == 403
        r = cli.post(url, json=corpo, headers={"X-Urace-Atelie-Token": SEGREDO})
        assert r.status_code == 200 and r.json()["pedido"] == pid
        cli.post("/ops/api/auth/login", json={"email": "op@urace.us", "password": "senha-forte-123"})
        d = cli.get(f"/ops/api/atelie/pedidos/{pid}").json()
        assert d["mensagens"][0]["texto"] == f"Suits #{pid} arte" and "token" not in json.dumps(d["config"]).lower()
    with TestClient(app, base_url="https://cc.test", client=("203.0.113.9", 5000)) as fora:
        assert fora.post(url, json=corpo, headers={"X-Urace-Atelie-Token": SEGREDO}).status_code == 403


# ------------------------------------------------------------------ o instalador e o plugin
def test_instalador_acha_o_jid_pelo_nome_e_nao_escolhe_entre_dois(tmp_path):
    ajuda = os.path.join(RAIZ, "adminai", "deploy", "whatsapp_grupos", "grupos.py")
    envf = tmp_path / "w.env"
    shutil.copy(os.path.join(RAIZ, "adminai", "deploy", "whatsapp_grupos", "whatsapp-grupos.env.example"), envf)
    lista = tmp_path / "l.json"
    lista.write_text(json.dumps({"groups": [{"id": DESIGN, "name": "Macacao Design URACE"},
                                            {"id": USMAN, "name": "Urace Suits - Usman"},
                                            {"id": OUTRO, "name": "Urace Suits - Usman"}]}))
    subprocess.run(["python3", ajuda, "token", str(envf)], check=True, capture_output=True)
    out = subprocess.run(["python3", ajuda, "resolver", str(envf), str(lista)], check=True, capture_output=True, text=True).stdout
    assert "design: achado" in out and "fornecedor: 2 grupos" in out
    g = json.loads(subprocess.run(["python3", ajuda, "groups", str(envf)], check=True, capture_output=True, text=True).stdout)
    assert g == {DESIGN: {"requireMention": False}}
    texto = envf.read_text()
    assert "WA_GRUPOS_TOKEN=\n" not in texto and oct(os.stat(envf).st_mode)[-3:] == "600"


@pytest.mark.skipif(not shutil.which("node"), reason="sem node")
def test_plugin_cala_o_whatsapp_e_so_repassa_os_grupos_da_lista(tmp_path):
    _env(tmp_path)
    js = f"""
const m = await import({json.dumps(os.path.join(RAIZ, 'adminai/openclaw/urace-atelie/index.js'))});
const h = {{}}; const enviados = [];
globalThis.fetch = async (url, o) => {{ enviados.push(JSON.parse(o.body)); return {{ ok: true }} }};
m.default.register({{ pluginConfig: {{ envFile: {json.dumps(str(tmp_path / 'urace' / 'whatsapp-grupos.env'))} }}, on: (n, f) => h[n] = f }});
const calado = h.before_dispatch({{ channel: "whatsapp", isGroup: true }}, {{ channelId: "whatsapp" }});
const outro = h.before_dispatch({{ channel: "telegram" }}, {{ channelId: "telegram" }});
await h.message_received({{ content: "oi", messageId: "a" }}, {{ channelId: "whatsapp", conversationId: "{DESIGN}" }});
await h.message_received({{ content: "nao", messageId: "b" }}, {{ channelId: "whatsapp", conversationId: "{OUTRO}" }});
await h.message_received({{ content: "dm", messageId: "c" }}, {{ channelId: "whatsapp", conversationId: "+14075550101" }});
console.log(JSON.stringify({{ calado, outro: outro ?? null, enviados }}));
"""
    r = subprocess.run(["node", "--input-type=module", "-e", js], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout.strip().splitlines()[-1])
    assert d["calado"] == {"handled": True} and d["outro"] is None
    assert [e["message_id"] for e in d["enviados"]] == ["a"] and d["enviados"][0]["grupo_jid"] == DESIGN


def test_configuracao_de_exemplo_nao_tem_segredo_nem_numero_real():
    t = open(os.path.join(RAIZ, "adminai", "deploy", "whatsapp_grupos", "whatsapp-grupos.env.example"), encoding="utf-8").read()
    assert "WA_GRUPOS_APLICAR=0" in t and "WA_GRUPOS_TOKEN=\n" in t and "+14075550123" in t
    assert "WA_GRUPO_DESIGN_JID=\n" in t and "WA_GRUPO_FORNECEDOR_JID=\n" in t
