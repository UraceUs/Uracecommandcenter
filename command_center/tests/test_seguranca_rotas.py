"""#438: auditoria de segurança — toda rota com a porta certa, e o que a auditoria achou, travado.

1. Toda rota do app exige login (da equipe: `auth.usuario_atual`/`auth.exige`; ou do cliente: `portal.cliente_atual`),
   menos as da lista `PUBLICAS` abaixo, cada uma com o motivo. Rota nova sem porta quebra este teste: ou ganha a
   dependência, ou entra na lista com o porquê (e, se for webhook, com a conferência do segredo).
2. Cabeçalhos e cookies do painel e da área do cliente.
3. A IA do painel (#420) e o conector MCP (#73) não pulam o aprovar com caminho codificado, nem chegam ao cofre.
4. A foto do lead do Kommo não leva o token da conta para fora do Kommo nem busca endereço interno (SSRF).
5. O registro aberto do OAuth tem limite por conexão.

Tudo fictício: @example.com, 555-01xx, nomes inventados.
"""
import os

import pytest

os.environ["URACE_ENV"] = "/nao/existe"

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api import auth, mcp_operar  # noqa: E402
from command_center.api.main import app  # noqa: E402
from command_center.db import aplicar_schema, conectar, inserir, um  # noqa: E402

SENHA = "senha-forte-123"

# ------------------------------------------------------------------ 1. a lista das rotas públicas
_SITE = "site público (páginas e dados que qualquer visitante vê; formulário com limite por IP e honeypot)"
_PORTA_DO_CLIENTE = "entrada da área do cliente: login, cadastro e senha, com limite por IP e por e-mail"
_CONVITE = "waiver por convite: o token longo do link (32 bytes) é a credencial; código por e-mail com limite"
_OAUTH = "OAuth do conector (RFC 7591/8414/9728): descoberta e registro abertos; autorizar pede sessão + CSRF + PKCE"
_WEBHOOK = "webhook: confere segredo/assinatura antes de tocar em qualquer coisa (test_webhooks_recusam_sem_segredo)"

PUBLICAS = {
    # saúde e o SPA (o HTML do painel não tem dado; a API é que pede login)
    ("GET", "/ops/health"): "saúde do serviço, sem dado",
    ("GET", "/ops/ready"): "saúde do banco, sem dado",
    ("GET", "/ops"): "o HTML do SPA (noindex); os dados vêm da API com login",
    ("GET", "/ops/"): "o HTML do SPA",
    ("GET", "/ops/{caminho:path}"): "o HTML do SPA e os arquivos soltos do build (só dentro de web/dist)",
    ("GET", "/{caminho:path}"): "a última rota: página do site (ou 404)",
    # login da equipe
    ("POST", "/ops/api/auth/login"): "login do painel (login_attempts: 5 erros/15 min por IP e por e-mail)",
    ("POST", "/ops/api/auth/logout"): "sair: só derruba a sessão do próprio cookie",
    ("POST", "/ops/api/auth/passe/entrar"): "passe do balcão (#311): uso único, 30 s, host e Origin conferidos, limite por IP",
    ("POST", "/ops/api/system/cliente"): "erro do navegador e Web Vitals: 4 KB, limite por IP por minuto, nada vira dado",
    # OAuth do conector
    ("GET", "/.well-known/oauth-authorization-server"): _OAUTH,
    ("GET", "/.well-known/oauth-authorization-server/ops"): _OAUTH,
    ("GET", "/.well-known/oauth-protected-resource"): _OAUTH,
    ("GET", "/.well-known/oauth-protected-resource/ops/mcp"): _OAUTH,
    ("POST", "/ops/oauth/register"): _OAUTH + " (#438: limite por IP)",
    ("GET", "/ops/oauth/authorize"): _OAUTH + " (sem sessão, manda para o login)",
    ("POST", "/ops/oauth/authorize"): _OAUTH + " (confere a sessão e o CSRF à mão)",
    ("POST", "/ops/oauth/token"): _OAUTH + " (código de uso único + PKCE S256)",
    ("POST", "/ops/oauth/revoke"): _OAUTH + " (só revoga o token que a pessoa já tem)",
    # volta do OAuth de terceiros: o `state` assinado/guardado é a prova
    ("GET", "/ops/api/qbo/callback"): "volta do QuickBooks: state de uso único conferido",
    ("GET", "/ops/api/google/callback"): "volta do Google (#220): state + nonce no cookie conferidos",
    # webhooks
    ("POST", "/ops/api/crm/hook"): _WEBHOOK + " — Kommo Salesbot: ?key= = KOMMO_HOOK_KEY (+ JWT do bot se houver)",
    ("POST", "/ops/api/crm/webhook"): _WEBHOOK + " — Kommo: KOMMO_WEBHOOK_SECRET ou a chave do hook",
    ("POST", "/ops/api/dialpad/webhook"): _WEBHOOK + " — Dialpad: ?key= = DIALPAD_HOOK_KEY (+ JWT HS256 se assinado)",
    ("GET", "/ops/api/whatsapp/webhook"): _WEBHOOK + " — verificação da Meta: hub.verify_token",
    ("POST", "/ops/api/whatsapp/webhook"): _WEBHOOK + " — Meta: X-Hub-Signature-256 com WA_APP_SECRET",
    ("POST", "/ops/api/atelie/whatsapp/entrada"): _WEBHOOK + " — OpenClaw local: só 127.0.0.1 + token do ateliê",
    ("POST", "/ops/api/stripe/webhook"): _WEBHOOK + " — Stripe-Signature (HMAC + 5 min) com STRIPE_WEBHOOK_SECRET",
    # área do cliente: a entrada (o resto usa portal.cliente_atual)
    ("POST", "/ops/api/portal/signup"): _PORTA_DO_CLIENTE,
    ("POST", "/ops/api/portal/login"): _PORTA_DO_CLIENTE,
    ("POST", "/ops/api/portal/logout"): _PORTA_DO_CLIENTE,
    ("POST", "/ops/api/portal/password/forgot"): _PORTA_DO_CLIENTE,
    ("POST", "/ops/api/portal/password/reset"): _PORTA_DO_CLIENTE + " (token de 32 bytes, 30 min, uso único)",
    ("GET", "/ops/api/portal/invite/{token}"): _CONVITE,
    ("GET", "/ops/api/portal/invite/{token}/pdf"): _CONVITE,
    ("POST", "/ops/api/portal/invite/{token}/code"): _CONVITE,
    ("POST", "/ops/api/portal/invite/{token}/events"): _CONVITE,
    ("POST", "/ops/api/portal/invite/{token}/review"): _CONVITE,
    ("POST", "/ops/api/portal/invite/{token}/sign"): _CONVITE,
    ("GET", "/ops/api/portal/invite/{token}/signed.pdf"): _CONVITE,
    # site público
    ("GET", "/robots.txt"): _SITE,
    ("GET", "/sitemap.xml"): _SITE,
    ("GET", "/"): _SITE,
    ("GET", "/services/arrive-and-drive"): _SITE,
    ("GET", "/services/arrive-and-drive/"): _SITE,
    ("GET", "/ops/api/vitrine/planos"): _SITE,
    ("GET", "/ops/api/vitrine/agenda"): _SITE,
    ("GET", "/ops/api/vitrine/servicos"): _SITE,
    ("GET", "/ops/api/vitrine/sim2grid"): _SITE,
    ("POST", "/ops/api/vitrine/contato"): _SITE,
    ("POST", "/ops/api/vitrine/pedido"): _SITE,
    ("POST", "/ops/api/vitrine/checkout"): _SITE + "; comprar pede a conta do cliente",
    ("POST", "/ops/api/vitrine/carrinho"): _SITE + " (só cota preço)",
    ("POST", "/ops/api/vitrine/carrinho/checkout"): _SITE + "; pede a conta do cliente",
    ("GET", "/cart/thanks/"): _SITE,
    ("GET", "/store/thanks/"): _SITE,
    ("GET", "/store/cancelled/"): _SITE,
    ("GET", "/order/{token}/"): _SITE + " — página do pedido: o token longo do link é a credencial",
    ("GET", "/order/{token}/cart/"): _SITE + " — idem",
    ("POST", "/order/{token}/retry"): _SITE + " — idem, com limite",
    ("GET", "/_f/{nome}"): _SITE + " — foto do editor: nome = hash (regex fechada, sem caminho)",
    ("GET", "/store/img/{nome}"): _SITE + " — foto da loja: nome = id-hash (regex fechada, sem caminho)",
    ("POST", "/language/"): _SITE + " — idioma: volta só para caminho da lista (idioma.volta_ok)",
}

PORTAS = {"usuario_atual", "cliente_atual"}


def _rotas():
    """Toda rota do app, também as dos routers incluídos (o FastAPI novo os guarda num `_IncludedRouter`)."""
    def anda(rs):
        for r in rs:
            if hasattr(r, "effective_route_contexts"):
                yield from r.effective_route_contexts()
            elif getattr(r, "dependant", None) is not None:
                yield r
    return list(anda(app.routes))


def _tem_porta(dep):
    return any(getattr(d.call, "__name__", "") in PORTAS or _tem_porta(d) for d in dep.dependencies)


def _sem_porta():
    out = set()
    for r in _rotas():
        if not _tem_porta(r.dependant):
            for m in r.methods - {"HEAD", "OPTIONS"}:
                out.add((m, r.path))
    return out


def test_o_teste_enxerga_as_rotas():
    """Se o jeito de listar rotas mudar de novo (FastAPI), este teste não pode passar vazio."""
    assert len(_rotas()) > 400
    assert any(r.path == "/ops/api/clients/{cid}" for r in _rotas())


def test_toda_rota_sem_login_esta_na_lista_de_publicas():
    novas = sorted(_sem_porta() - set(PUBLICAS))
    assert not novas, ("rota sem login e fora da lista de públicas (#438): ponha auth.exige/usuario_atual "
                       f"ou cliente_atual, ou entre em PUBLICAS com o motivo: {novas}")


def test_a_lista_de_publicas_nao_tem_rota_que_ja_nao_existe_ou_ganhou_login():
    sobra = sorted(set(PUBLICAS) - _sem_porta())
    assert not sobra, f"tire da lista (a rota não existe mais ou já pede login): {sobra}"


@pytest.fixture(scope="module")
def cli(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("seg")
    os.environ["CC_DB_PATH"] = str(pasta / "cc.sqlite")
    os.environ["URACE_DIR"] = str(pasta)
    con = conectar(); aplicar_schema(con)
    auth.criar_usuario(con, "admin.ficticio@example.com", "Admin Fictício", "ADMIN", SENHA)
    con.commit(); con.close()
    with TestClient(app, base_url="https://cc.test") as c:
        yield c


def test_rota_com_login_responde_401_sem_credencial(cli):
    """A dependência existe E funciona: sem cookie nem chave, toda rota da equipe e do cliente diz 401."""
    import re
    cli.cookies.clear()
    furos = []
    for r in _rotas():
        if not _tem_porta(r.dependant):
            continue
        caminho = re.sub(r"\{[^}]+\}", "1", r.path)
        for m in sorted(r.methods - {"HEAD", "OPTIONS"}):
            s = cli.request(m, caminho).status_code
            if s != 401:
                furos.append((m, r.path, s))
    assert not furos, f"rota com login que não respondeu 401 sem credencial: {furos[:20]}"


def test_webhooks_recusam_sem_segredo(cli, monkeypatch):
    for k in ("KOMMO_HOOK_KEY", "KOMMO_WEBHOOK_SECRET", "DIALPAD_HOOK_KEY", "WA_APP_SECRET", "WA_VERIFY_TOKEN",
              "STRIPE_WEBHOOK_SECRET"):
        monkeypatch.delenv(k, raising=False)
    from command_center.api import crm, dialpad
    from command_center.providers import whatsapp as wa
    monkeypatch.setattr(crm, "_chave_hook", lambda: "")
    monkeypatch.setattr(dialpad, "_chave_hook", lambda: "")
    monkeypatch.setattr(wa, "_carrega_env", lambda: None)
    cli.cookies.clear()
    corpo = {"lead_id": 1, "text": "oi"}
    # sem segredo configurado: tudo recusa (nunca "aberto por padrão")
    assert cli.post("/ops/api/crm/hook?key=", content=b"x").status_code == 403
    assert cli.post("/ops/api/crm/webhook", json=corpo).status_code == 403
    assert cli.post("/ops/api/dialpad/webhook?key=", json=corpo).status_code == 409
    assert cli.post("/ops/api/whatsapp/webhook", json={"entry": []}).status_code == 403
    assert cli.get("/ops/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=&hub.challenge=1").status_code == 403
    assert cli.post("/ops/api/stripe/webhook", json={"id": "evt_1"}).status_code == 503
    # com segredo configurado: o errado recusa
    monkeypatch.setattr(crm, "_chave_hook", lambda: "chave-certa-ficticia")
    monkeypatch.setattr(dialpad, "_chave_hook", lambda: "chave-certa-ficticia")
    monkeypatch.setenv("WA_APP_SECRET", "segredo-ficticio")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_ficticio")
    assert cli.post("/ops/api/crm/hook?key=errada", content=b"x").status_code == 403
    assert cli.post("/ops/api/crm/webhook?key=errada", json=corpo).status_code == 403
    assert cli.post("/ops/api/dialpad/webhook?key=errada", json=corpo).status_code == 403
    assert cli.post("/ops/api/whatsapp/webhook", json={"entry": []},
                    headers={"X-Hub-Signature-256": "sha256=" + "0" * 64}).status_code == 403
    assert cli.post("/ops/api/stripe/webhook", json={"id": "evt_1"},
                    headers={"Stripe-Signature": "t=1,v1=" + "0" * 64}).status_code == 400
    # a entrada do OpenClaw só da própria máquina (o cliente de teste não é 127.0.0.1)
    assert cli.post("/ops/api/atelie/whatsapp/entrada", json={}).status_code == 403


# ------------------------------------------------------------------ área do cliente: A não lê B
def test_cliente_a_nao_alcanca_o_que_e_do_cliente_b(cli):
    from command_center.tests.dados_portal import piloto
    P = "/ops/api/portal"
    conta = {"name": "Bruna Ficticia", "email": "bruna.ficticia@example.com", "password": "corrida-segura-9",
             "birth_date": "1985-04-12", "phone": "(407) 555-0142", "address_line1": "100 Main St", "city": "Orlando",
             "state": "fl", "zip": "32809", "accept_terms": True}
    cli.cookies.clear()
    assert cli.post(f"{P}/signup", json=conta).status_code == 201
    hb = {"X-CSRF": cli.cookies.get("cp_csrf")}
    pid_b = cli.post(f"{P}/drivers", headers=hb, json=piloto("Davi Ficticio")).json()["drivers"][0]["id"]
    con = conectar()
    try:
        conta_b = um(con, "SELECT id FROM portal_accounts WHERE email=?", (conta["email"],))["id"]
        bid_b = inserir(con, "bookings", account_id=conta_b, pilot_id=pid_b, date="2030-01-10", period="manha",
                        status="pendente")
        con.commit()
    finally:
        con.close()
    cli.cookies.clear()
    assert cli.post(f"{P}/signup", json={**conta, "name": "Alice Ficticia", "email": "alice.ficticia@example.com"}).status_code == 201
    ha = {"X-CSRF": cli.cookies.get("cp_csrf")}
    assert cli.get(f"{P}/bookings/{bid_b}").status_code == 404
    assert cli.post(f"{P}/bookings/{bid_b}/cancel", headers=ha).status_code in (400, 404)
    assert cli.get(f"{P}/drivers/{pid_b}/qr.svg").status_code == 404
    assert cli.patch(f"{P}/drivers/{pid_b}", headers=ha, json={"name": "Invasor Ficticio"}).status_code == 404
    assert all(b["id"] != bid_b for b in cli.get(f"{P}/bookings").json()["bookings"])
    con = conectar()
    try:
        assert um(con, "SELECT status FROM bookings WHERE id=?", (bid_b,))["status"] == "pendente"
        assert um(con, "SELECT name FROM portal_pilots WHERE id=?", (pid_b,))["name"] == "Davi Ficticio"
    finally:
        con.close()
    # a sessão do cliente não abre o painel
    assert cli.get("/ops/api/clients").status_code == 401


# ------------------------------------------------------------------ 2. cabeçalhos e cookies
def test_cabecalhos_do_painel(cli):
    for caminho in ("/ops/", "/ops/api/auth/me", "/ops/health"):
        r = cli.get(caminho)
        h = r.headers
        assert h["x-content-type-options"] == "nosniff", caminho
        assert h["referrer-policy"] == "no-referrer", caminho
        assert h["strict-transport-security"].startswith("max-age=31536000"), caminho
        assert h["x-robots-tag"] == "noindex, nofollow", caminho
        csp = h["content-security-policy"]
        assert "frame-ancestors 'none'" in csp and "unsafe-eval" not in csp, caminho
        assert "script-src" not in csp or "'unsafe-inline'" not in csp.split("script-src", 1)[1].split(";")[0]


def test_hsts_so_por_https():
    """Em http puro (máquina local) o navegador ignoraria, e o teste local não pode prender o localhost em https."""
    with TestClient(app, base_url="http://127.0.0.1") as c:
        assert "strict-transport-security" not in c.get("/ops/health").headers


def test_cookies_de_sessao_do_painel_e_do_cliente(cli):
    cli.cookies.clear()
    r = cli.post("/ops/api/auth/login", json={"email": "admin.ficticio@example.com", "password": SENHA})
    assert r.status_code == 200
    linhas = r.headers.get_list("set-cookie")
    sess = next(x for x in linhas if x.startswith("cc_session="))
    csrf = next(x for x in linhas if x.startswith("cc_csrf="))
    for c in (sess, csrf):
        assert "Secure" in c and "samesite=strict" in c.lower() and "Path=/" in c
    assert "HttpOnly" in sess and "HttpOnly" not in csrf        # o CSRF é lido pelo JavaScript (duplo envio)
    cli.cookies.clear()
    r = cli.post("/ops/api/portal/signup", json={"name": "Carla Ficticia", "email": "carla.ficticia@example.com",
                                                 "password": "corrida-segura-9", "birth_date": "1985-04-12",
                                                 "phone": "(407) 555-0143", "address_line1": "100 Main St",
                                                 "city": "Orlando", "state": "fl", "zip": "32809", "accept_terms": True})
    assert r.status_code == 201, r.text
    cp = next(x for x in r.headers.get_list("set-cookie") if x.startswith("cp_session="))
    assert "HttpOnly" in cp and "Secure" in cp and "samesite=lax" in cp.lower()


def test_corpo_de_email_vem_com_sandbox_no_cabecalho(cli, monkeypatch):
    """Aberto direto numa aba (fora do iframe com sandbox), o e-mail continua numa origem opaca."""
    from command_center.api import rotas_gmail
    cli.cookies.clear()
    cli.post("/ops/api/auth/login", json={"email": "admin.ficticio@example.com", "password": SENHA})
    con = conectar()
    try:
        eid = inserir(con, "emails", mailbox="urace", subject="Teste")
        con.commit()
    finally:
        con.close()

    class Gm:
        def mensagem_html(self, conta, mid):
            return {"html": "<p>Oi<script>alert(1)</script><img src=x onerror=alert(2)></p>", "assunto": "S"}
    monkeypatch.setattr(rotas_gmail, "modulo", lambda s: Gm())
    r = cli.get(f"/ops/api/emails/{eid}/html/abc123def")
    assert r.status_code == 200 and "<script" not in r.text and "onerror" not in r.text
    csp = r.headers["content-security-policy"]
    assert "sandbox" in csp and "allow-scripts" not in csp and "allow-same-origin" not in csp
    assert "script-src" not in csp            # default-src 'none' vale para script


# ------------------------------------------------------------------ 3. a IA e o conector não pulam o aprovar
@pytest.fixture()
def con_ia(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "cc.sqlite"))
    c = conectar(); aplicar_schema(c)
    yield c
    c.close()


def _pessoa(con, email, papel):
    uid = con.execute("INSERT INTO users (email, name, role, pw_salt, pw_hash) VALUES (?,?,?,'x','x')",
                      (email, "Pessoa Ficticia", papel)).lastrowid
    con.commit()
    return uid


CAMINHOS_TORTOS = [
    "/clients/1%2Fmensal",          # %2F: o modelo /clients/{cid} (fazer) casava; o roteador decodifica e cai no /mensal
    "/clients/1%252Fmensal",        # codificado duas vezes
    "/clients/1/%6Densal",          # letra codificada
    "/clients//1/mensal",
    "/clients/1/mensal/",
    "/clients/x/../1/mensal",
    "/clients/1/mensal?x=1",
    "/clients/1/mensal#x",
    "/clients\\1\\mensal",
    "/clients/1/men\x00sal",
]


def test_ia_nao_executa_rota_de_aprovar_por_caminho_torto(con_ia, monkeypatch):
    """#438: nenhum jeito de escrever o caminho faz o portão ver "fazer" e o roteador executar "aprovar"."""
    from command_center.api import agente_sdk
    executou = []
    monkeypatch.setattr(mcp_operar, "_requisicao", lambda ctx, m, c, corpo, q: executou.append((m, c)) or (200, {}))
    uid = _pessoa(con_ia, "dono.ficticio@example.com", "ADMIN")
    assert mcp_operar.tipo_para_ia("PATCH", "/clients/1/mensal") == "aprovar"
    for metodo in ("PATCH", "patch", "Patch"):
        for caminho in CAMINHOS_TORTOS:
            tipo = agente_sdk.classificar(con_ia, "painel_api", {"metodo": metodo, "caminho": caminho})
            if tipo == "fazer":            # o portão deixou passar: então o executar_como tem de recusar
                with pytest.raises(ValueError):
                    mcp_operar.executar_como(uid, metodo, caminho, {"monthly_amount": 1})
            else:
                assert tipo == "aprovar", (metodo, caminho, tipo)
            with pytest.raises(ValueError):                 # sem o clique, nunca roda
                mcp_operar.executar_como(uid, metodo, caminho, {"monthly_amount": 1})
    assert not executou, executou


def test_caminho_codificado_e_decodificado_antes_de_classificar():
    assert mcp_operar.normalizar("clients/1%2Fmensal") == "/ops/api/clients/1/mensal"
    assert mcp_operar.caminho_seguro("/clients/7") == "/ops/api/clients/7"
    assert mcp_operar.caminho_seguro("/suits/3/anexos/foto%20da%20pe%C3%A7a.jpg") == "/ops/api/suits/3/anexos/foto da peça.jpg"
    for ruim in ("/a%252Fb", "/a//b", "/a/../b", "/a/./b", "/a\\b", "/a?b", "/a#b", "/a\x00b"):
        with pytest.raises(ValueError):
            mcp_operar.caminho_seguro(ruim)


def test_conector_mcp_pede_confirmacao_tambem_com_caminho_codificado(con_ia, monkeypatch):
    executou = []
    monkeypatch.setattr(mcp_operar, "_requisicao", lambda ctx, m, c, corpo, q: executou.append((m, c)) or (200, {}))
    uid = _pessoa(con_ia, "gerente.ficticio@example.com", "ADMIN")
    quem = {"id": uid, "role": "ADMIN", "via": "key:abc", "somente_leitura": False}
    r = mcp_operar.chamar(quem, {}, "PATCH", "clients/1%2Fmensal", {"monthly_amount": 1})
    assert r.get("precisa_confirmar") is True and r["vai_fazer"]["caminho"] == "/ops/api/clients/1/mensal"
    for caminho in ("clients/1%252Fmensal", "clients//1/mensal", "clients/1/mensal?x=1"):
        with pytest.raises(ValueError):
            mcp_operar.chamar(quem, {}, "PATCH", caminho, {"monthly_amount": 1}, confirmar=True, aprovacao="apr_x")
    assert not executou


def test_cofre_fica_fora_da_ia_e_do_conector(con_ia, monkeypatch):
    """A sessão interna da IA é de navegador: o `so_livre` do cofre a deixava entrar como o dono."""
    uid = _pessoa(con_ia, auth.ACESSO_LIVRE[0], "ADMIN")
    assert not [o for o in mcp_operar.catalogo() if o["caminho"].startswith("/ops/api/cofre")]
    for metodo, caminho in (("GET", "/cofre"), ("POST", "/cofre/1/revelar"), ("POST", "/cofre/desbloquear")):
        with pytest.raises(ValueError, match="cofre"):
            mcp_operar.executar_como(uid, metodo, caminho, aprovado=True)
        with pytest.raises(ValueError):
            mcp_operar.chamar({"id": uid, "role": "ADMIN", "free": True}, {}, metodo, caminho)


def test_atualizar_o_servidor_pela_ia_pede_o_clique():
    assert mcp_operar.tipo_para_ia("POST", "/system/update") == "aprovar"
    assert mcp_operar.tipo_para_ia("PATCH", "/clients/1") == "fazer"


# ------------------------------------------------------------------ 4. a foto do lead (SSRF e token)
def _lead_com_foto(url):
    con = conectar()
    try:
        lid = inserir(con, "crm_leads", external_id="ficticio-avatar-" + str(abs(hash(url)) % 10**8), name="Lead Ficticio",
                      contact_avatar=url)
        con.commit()
        return lid
    finally:
        con.close()


def test_foto_do_lead_nao_leva_o_token_para_fora_do_kommo_nem_busca_ip_interno(cli, monkeypatch):
    import socket

    from command_center.api import crm
    monkeypatch.setenv("KOMMO_TOKEN", "token-ficticio-da-conta")
    cli.cookies.clear()
    cli.post("/ops/api/auth/login", json={"email": "admin.ficticio@example.com", "password": SENHA})
    pedidos = []

    class R:
        headers = {"Content-Type": "image/jpeg"}
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, n=None): return b"\xff\xd8imagem"
    monkeypatch.setattr(crm, "_abrir_sem_redirecionar", lambda req: pedidos.append((req.full_url, req.get_header("Authorization"))) or R())
    ips = {"amojo.kommo.com": "93.184.215.14", "cdn.example.com": "93.184.215.15", "interno.example.com": "10.0.0.5"}
    monkeypatch.setattr(socket, "getaddrinfo", lambda h, *a, **k: [(2, 1, 6, "", (ips.get(h, h), 0))])

    # host de fora do Kommo: busca sem o token
    lid = _lead_com_foto("https://cdn.example.com/f.jpg")
    assert cli.get(f"/ops/api/crm/leads/{lid}/avatar").status_code == 200
    assert pedidos == [("https://cdn.example.com/f.jpg", None)]
    # endereço interno: nem busca
    pedidos.clear()
    for url in ("https://127.0.0.1/f.jpg", "https://169.254.169.254/latest/meta-data", "https://interno.example.com/f.jpg",
                "https://amojo.kommo.com:8443/f.jpg", "https://u:p@amojo.kommo.com/f.jpg"):
        assert cli.get(f"/ops/api/crm/leads/{_lead_com_foto(url)}/avatar").status_code == 404, url
    assert pedidos == []
    # o próprio Kommo: com o token
    lid = _lead_com_foto("https://amojo.kommo.com/attachments/profiles/x/g.jpg")
    assert cli.get(f"/ops/api/crm/leads/{lid}/avatar").status_code == 200
    assert pedidos[0][1] == "Bearer token-ficticio-da-conta"
    # "kommo.com" no meio do nome não engana
    assert not crm._host_do_kommo("https://amojo.kommo.com.example.com/x.jpg")
    assert not crm._host_do_kommo("https://evilkommo.com/x.jpg")


# ------------------------------------------------------------------ 5. abuso
def test_registro_oauth_tem_limite_por_conexao(cli):
    from command_center.api import oauth
    cli.cookies.clear()
    corpo = {"client_name": "Cliente Ficticio", "redirect_uris": ["https://cliente.example.com/cb"]}
    codigos = [cli.post("/ops/oauth/register", json=corpo).status_code for _ in range(oauth.REGISTROS_POR_HORA + 1)]
    assert codigos[:-1] == [201] * oauth.REGISTROS_POR_HORA and codigos[-1] == 429
