"""MCP que OPERA o painel, pelo papel de quem está usando (#73).

Dono, 02/10: *"eu preciso que toda, todas as funcionalidades sejam operáveis pela API, não só
como visualização, mas como operação mesmo... os nossos vendedores... usam o Claude nas
máquinas deles... de acordo com o nível de hierarquia ali do operador ou gerente"*.

**Não existe um caminho paralelo.** A ferramenta `urace_api` chama a MESMA rota que o botão do
painel chama, dentro do processo, com a credencial de quem está no Claude. Por isso valem, sem
nada escrito de novo aqui:

- a checagem de papel de cada rota (`auth.exige`): o operador não faz o que é do gerente;
- a validação e as travas de cada rota (cobrar duas vezes, card de outro cliente, "nunca");
- a auditoria com o nome da pessoa;
- a trava de leitura: token sem o escopo de operar continua só lendo.

O que vai para o cliente ou mexe em dinheiro pede `confirmar: true`: a primeira chamada
devolve o que vai acontecer, e só a segunda faz. #378: a primeira chamada também devolve um código
de `aprovacao` amarrado àquele conteúdo; a segunda só executa com ele, e repetir não executa de novo. O resto do painel (login, chaves, área do
cliente) fica fora, porque não é operação de equipe.
"""
import asyncio
import hashlib
import inspect
import json
import re
import secrets
import sys
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from fastapi.routing import APIRoute

from command_center.api import auth
from command_center.db import auditar, conectar

PREFIXO = "/ops/api/"
# fora do MCP: credenciais e sessões (login, senha, chaves), a área do cliente (outra porta) e, #438, o cofre de
# senhas: a IA do painel entra com uma sessão de navegador interna e passava pelo `so_livre` do cofre como o dono.
FORA = re.compile(r"^/ops/api/(auth|portal|cofre)(/|$)")
METODOS = ("GET", "POST", "PATCH", "PUT", "DELETE")
# o que manda algo para fora (cliente, QuickBooks, DocuSign, e-mail, Kommo, Asana) ou cobra.
# #204: o chat do Kommo mora em /crm/* (responder, etapa, tags, nota): o documento já dizia que
# Kommo pede confirmação, mas a regra procurava "kommo" no caminho e deixava o /crm/ passar.
PEDE_CONFIRMACAO = re.compile(
    r"invoice|waiver|docusign|qbo|quickbooks|gmail|email|enviar|send|lembrete|reminder|kommo|/crm/|whatsapp|"
    r"recorrencia|mensal|fechar|close|step/|cobr|deposit|pagamento|payment|asana|tasks|agendamentos/|"
    r"aprovar-admin|"              # #448: liberar o Suits sem a aprovação escrita é clique do administrador, nunca da IA sozinha
    # debug 29/10: também saem para fora, e o nome da rota não dizia: a ligação do Dialpad para o cliente e o que
    # vai aos grupos do WhatsApp do ateliê (escrever, o endereço ao fornecedor, aprovar o rascunho)
    r"dialpad/call$|atelie/pedidos/[^/]+/(escrever|endereco)$|atelie/saidas/[^/]+/aprovar$", re.I)


def _papel_da_rota(dep):
    """O papel mínimo que `auth.exige(...)` pede nesta rota (procura nas dependências)."""
    for d in dep.dependencies:
        fn = d.call
        if getattr(fn, "__name__", "") == "_guarda" and "exige" in getattr(fn, "__qualname__", ""):
            return inspect.getclosurevars(fn).nonlocals.get("papel_minimo")
        achado = _papel_da_rota(d)
        if achado:
            return achado
    return None


def _usa_login(dep):
    return any(getattr(d.call, "__name__", "") == "usuario_atual" or _usa_login(d) for d in dep.dependencies)


_CATALOGO = None


def catalogo():
    """[(método, caminho, papel, descrição, campos)] de toda rota de equipe do painel."""
    global _CATALOGO
    if _CATALOGO is not None:
        return _CATALOGO
    from command_center.api.main import app
    spec = app.openapi()
    saida = []
    vistos = set()
    for nome, mod in list(sys.modules.items()):
        if not nome.startswith("command_center.api."):
            continue
        r = getattr(mod, "r", None)
        if not isinstance(r, APIRouter):
            continue
        for rota in r.routes:
            if not isinstance(rota, APIRoute) or not rota.path.startswith(PREFIXO) or FORA.match(rota.path):
                continue
            papel = _papel_da_rota(rota.dependant) or ("VIEWER" if _usa_login(rota.dependant) else None)
            if not papel:
                continue                        # rota pública ou de outra porta: não é operação de equipe
            for metodo in sorted(rota.methods & set(METODOS)):
                if (metodo, rota.path) in vistos:
                    continue
                vistos.add((metodo, rota.path))
                op = (spec.get("paths", {}).get(rota.path) or {}).get(metodo.lower()) or {}
                desc = (inspect.getdoc(rota.endpoint) or op.get("summary") or rota.name or "").strip()
                saida.append({"metodo": metodo, "caminho": rota.path, "papel": papel,
                              "descricao": desc.split("\n\n")[0][:400],
                              "campos": _campos(spec, op), "confirma": metodo != "GET" and bool(PEDE_CONFIRMACAO.search(rota.path))})
    saida.sort(key=lambda x: (x["caminho"], x["metodo"]))
    _CATALOGO = saida
    return saida


def _campos(spec, op):
    """Parâmetros (consulta) e corpo JSON, resumidos para o modelo saber o que mandar."""
    out = {}
    for p in op.get("parameters") or []:
        if p.get("in") == "query":
            out[p["name"]] = (p.get("schema") or {}).get("type", "string") + (" (obrigatório)" if p.get("required") else "")
    corpo = (((op.get("requestBody") or {}).get("content") or {}).get("application/json") or {}).get("schema") or {}
    ref = corpo.get("$ref", "")
    if ref.startswith("#/components/schemas/"):
        corpo = spec.get("components", {}).get("schemas", {}).get(ref.rsplit("/", 1)[1], {})
    obrig = set(corpo.get("required") or [])
    for k, v in (corpo.get("properties") or {}).items():
        tipo = v.get("type") or "/".join(x.get("type", "?") for x in v.get("anyOf", []) if x.get("type") != "null") or "valor"
        out[f"corpo.{k}"] = tipo + (" (obrigatório)" if k in obrig else "")
    return out


def _caminho_casa(modelo, caminho):
    return re.fullmatch(re.sub(r"\\\{[^}]+\\\}", r"[^/]+", re.escape(modelo)), caminho) is not None


def _operacao(metodo, caminho):
    return next((o for o in catalogo() if o["metodo"] == metodo and _caminho_casa(o["caminho"], caminho)), None)


def pode(quem, papel):
    return quem.get("free") or auth.pode(quem.get("role"), papel)


def permissao(quem):
    """#362: papel da pessoa e permissão do conector, separados, e o porquê em português.
    O conector OAuth vale pelo escopo `mcp:write` do token; a chave de API, por não ser só de
    leitura; a sessão do navegador não tem trava de conector."""
    from command_center.api import oauth
    quem = quem or {}
    if quem.get("via") == "oauth":
        conector = oauth.ESCOPO_OPERAR in (quem.get("escopo") or "").split()
    else:
        conector = not quem.get("somente_leitura")
    return oauth.permissao(quem.get("role"), conector, livre=quem.get("free"),
                           chave=str(quem.get("via") or "").startswith("key:"))


def operacoes(quem, busca=None, limite=60):
    """O que ESTA pessoa pode fazer pelo MCP: só as rotas que o papel dela alcança, e só
    leitura se o acesso dela é de leitura."""
    p = permissao(quem)
    so_ler = bool(quem.get("somente_leitura")) or not p["opera"]
    itens = [o for o in catalogo() if pode(quem, o["papel"]) and (not so_ler or o["metodo"] == "GET")]
    if busca:
        termos = [t for t in re.split(r"\s+", busca.lower()) if t]
        itens = [o for o in itens if all(t in f"{o['caminho']} {o['descricao']}".lower() for t in termos)]
    limite = max(1, min(int(limite or 60), 300))
    return {**p, "opera": not so_ler, "total": len(itens), "operacoes": itens[:limite],
            "como_usar": "chame urace_api com metodo e caminho (troque {id} pelo número); corpo é JSON. "
                         "O que tem confirma=true precisa de confirmar=true — antes disso só mostra o que vai fazer."}


APROVACAO_VALE_MIN = 15


def _agora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _hash(texto):
    return hashlib.sha256(texto.encode()).hexdigest()


def _conteudo(metodo, caminho, corpo, consulta):
    """O que foi mostrado à pessoa, numa forma só: mudar uma vírgula do corpo muda o hash."""
    return _hash(json.dumps({"metodo": metodo, "caminho": caminho, "corpo": corpo, "consulta": consulta},
                            sort_keys=True, ensure_ascii=False, default=str))


def _nova_aprovacao(quem, metodo, caminho, corpo, consulta):
    codigo = "apr_" + secrets.token_urlsafe(18)
    agora = datetime.now(timezone.utc)
    expira = (agora + timedelta(minutes=APROVACAO_VALE_MIN)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    con = conectar()
    try:
        con.execute("INSERT INTO mcp_aprovacoes (codigo_hash, user_id, conteudo_hash, resumo, criado_em, expira_em) "
                    "VALUES (?,?,?,?,?,?)",
                    (_hash(codigo), quem.get("id"), _conteudo(metodo, caminho, corpo, consulta),
                     json.dumps({"metodo": metodo, "caminho": caminho}), _agora(), expira))
        con.commit()
    finally:
        con.close()
    return codigo, expira


def _usar_aprovacao(quem, codigo, metodo, caminho, corpo, consulta):
    """Confere o código e o marca como usado ANTES de executar (dois pedidos ao mesmo tempo: só um
    passa). Devolve None para executar, ou o resultado guardado se o código já foi usado."""
    if not codigo:
        raise ValueError("falta o código de aprovacao: chame primeiro sem confirmar, mostre a prévia à "
                         "pessoa e repita com confirmar=true e o código que veio na prévia")
    con = conectar()
    try:
        a = con.execute("SELECT * FROM mcp_aprovacoes WHERE codigo_hash=?", (_hash(str(codigo)),)).fetchone()
        if not a or a["user_id"] != quem.get("id"):
            raise ValueError("código de aprovacao desconhecido: peça a prévia de novo")
        if a["conteudo_hash"] != _conteudo(metodo, caminho, corpo, consulta):
            raise ValueError("o pedido mudou depois da prévia (destinatário, valor ou caminho): a aprovação "
                             "não vale para ele. Peça uma prévia nova e mostre à pessoa")
        if a["usado_em"]:
            guardada = json.loads(a["resposta"]) if a["resposta"] else None
            return {"status": a["status"], "ok": bool(a["status"]) and 200 <= a["status"] < 300,
                    "resposta": guardada, "repetido": True,
                    "aviso": "esta aprovação já foi usada; nada foi executado de novo"}
        if a["expira_em"] < _agora():
            raise ValueError(f"a aprovação venceu ({APROVACAO_VALE_MIN} min): peça uma prévia nova")
        marcou = con.execute("UPDATE mcp_aprovacoes SET usado_em=? WHERE codigo_hash=? AND usado_em IS NULL",
                             (_agora(), a["codigo_hash"])).rowcount
        con.commit()
        if not marcou:
            return {"status": None, "ok": False, "resposta": None, "repetido": True,
                    "aviso": "esta aprovação já está sendo usada por outro pedido; nada foi executado de novo"}
        return None
    finally:
        con.close()


def _guardar_resultado(codigo, status, resposta):
    con = conectar()
    try:
        con.execute("UPDATE mcp_aprovacoes SET status=?, resposta=? WHERE codigo_hash=?",
                    (status, json.dumps(resposta, ensure_ascii=False, default=str)[:20000], _hash(str(codigo))))
        con.commit()
    finally:
        con.close()


def chamar(quem, ctx, metodo, caminho, corpo=None, consulta=None, confirmar=False, aprovacao=None):
    """Chama a rota do painel por dentro, como a pessoa. Devolve {status, resposta}."""
    metodo = str(metodo or "").upper()
    if metodo not in METODOS:
        raise ValueError(f"método inválido: use um de {', '.join(METODOS)}")
    caminho = caminho_seguro(caminho)
    if FORA.match(caminho):
        raise ValueError("login, chaves e área do cliente não são operados pelo MCP")
    op = _operacao(metodo, caminho)
    if not op:
        raise ValueError(f"{metodo} {caminho} não existe no painel (veja urace_operacoes)")
    if metodo != "GET":
        p = permissao(quem)
        if quem.get("somente_leitura") or not p["opera"]:
            raise ValueError(f"este acesso é só de leitura. {p['por_que']}")
    if not pode(quem, op["papel"]):
        raise ValueError(f"isto é do papel {op['papel']} ou acima; você é {quem.get('role')}")
    if op["confirma"] and not confirmar:
        codigo, expira = _nova_aprovacao(quem, metodo, caminho, corpo, consulta)
        return {"precisa_confirmar": True, "vai_fazer": {"metodo": metodo, "caminho": caminho, "corpo": corpo,
                                                          "consulta": consulta},
                "descricao": op["descricao"], "aprovacao": codigo, "aprovacao_expira_em": expira,
                "aviso": "isto vai para fora (cliente, QuickBooks, DocuSign, e-mail, Kommo ou Asana) ou cobra. "
                         "Mostre à pessoa o que vai acontecer e, com o sim dela, chame de novo com o MESMO "
                         "pedido, confirmar=true e este código de aprovacao (vale "
                         f"{APROVACAO_VALE_MIN} min, uma vez, só para este conteúdo)."}
    if op["confirma"]:
        repetido = _usar_aprovacao(quem, aprovacao, metodo, caminho, corpo, consulta)
        if repetido:
            return repetido
    status, resposta = _requisicao(ctx, metodo, caminho, corpo, consulta)
    if op["confirma"]:
        _guardar_resultado(aprovacao, status, resposta)
    if metodo != "GET":
        con = conectar()
        try:
            auditar(con, "mcp.call", f"user:{quem.get('id')}", user_id=quem.get("id"), entity_type="mcp",
                    detail={"metodo": metodo, "caminho": caminho, "status": status, "via": quem.get("via"),
                            "cliente_oauth": quem.get("client_id"), "confirmado": bool(confirmar),
                            "aprovacao": _hash(str(aprovacao))[:12] if op["confirma"] else None})
            con.commit()
        finally:
            con.close()
    return {"status": status, "ok": 200 <= status < 300, "resposta": resposta}


def normalizar(caminho):
    """'clients/621', '/clients/621' ou '/ops/api/clients/621' → '/ops/api/clients/621'.

    #438: o caminho sai DECODIFICADO (`%2F` vira `/`, `%6D` vira `m`), porque é assim que o roteador o enxerga.
    Antes, `PATCH /clients/1%2Fmensal` era classificado pelo modelo `/clients/{cid}` (fazer) e o roteador, que
    decodifica, executava `PATCH /clients/1/mensal` (cobrança mensal: aprovar) sem o clique."""
    from urllib.parse import unquote
    caminho = "/" + unquote(str(caminho or "")).lstrip("/")
    return caminho if caminho.startswith(PREFIXO) else PREFIXO + caminho.lstrip("/").removeprefix("ops/api/")


# #438: o que sobra depois de decodificar uma vez e ainda muda o destino: `%` (codificado duas vezes: o httpx
# manda `%6D` como está e o roteador decodifica), `..`/`.` como segmento, barra dupla, barra invertida,
# consulta ou âncora dentro do caminho e caractere de controle.
_CAMINHO_RUIM = re.compile(r"%|\\|//|\?|#|[\x00-\x1f\x7f]|(^|/)\.{1,2}(/|$)")


def caminho_seguro(caminho):
    """O caminho normalizado e decodificado, ou ValueError. O mesmo texto é o que se classifica e o que se chama."""
    c = normalizar(caminho)
    if _CAMINHO_RUIM.search(c) or ".." in c:
        raise ValueError("caminho inválido: passe a consulta em 'consulta', não na URL, e o caminho sem codificar")
    return c


# #422: o que não volta atrás, pelo caminho da rota (o mesmo critério do RX_APROVAR dos nomes de ferramenta):
# unir cards, anular, apagar/excluir/remover. Pela IA do painel, vira o aprovar de um clique.
NAO_VOLTA = re.compile(r"(^|[/_-])(merge|unir|void|anular|apagar|excluir|remover|delete)([/_-]|$)", re.I)
# #438: o que não sai para fora nem apaga, mas não é trabalho do dia a dia da IA: atualizar o servidor (deploy).
SO_COM_CLIQUE = re.compile(r"^/ops/api/system/update$")
# Debug 29/10: decisão de gente SOBRE a IA. Pelo painel_api ela chamava, como a pessoa, o "Aprovar" do próprio
# cartão (e executava o que devia esperar o clique) e o PUT da política (soltava o que o dono travou). Aprovar,
# recusar e mudar política são da pessoa no painel ("Administração" em rotas_ia.SO_HUMANO): nem com aprovar.
SO_GENTE = re.compile(r"^/ops/api/(ai/actions/\{[^}]+\}/(approve|reject)|policies/\{[^}]+\})$")
# Debug 29/10: rota cuja própria regra diz que é de uma pessoa rodava direto pelo painel_api, como a pessoa, e assim
# sem a trava que o módulo põe na IA: ligar conta ou driver do site ao card ("uma pessoa confirma": abre o histórico
# do card para quem tem a conta), registrar à mão a aprovação final do macacão (pela IA, só a ponte, com o e-mail do
# cliente) e conferir medida (a IA só marca suspeita). Pela IA viram o aprovar de um clique: quem clica é a pessoa.
DE_UMA_PESSOA = re.compile(r"^/ops/api/(site/(contas|drivers)/\{[^}]+\}/vincular|suits/\{[^}]+\}/(aprovacao|medidas/estado))$")


def _etapa_da_equipe(metodo, op, corpo):
    """Mudar o macacão para as etapas que são da equipe (fotos recebidas, conferido, endereço enviado): o
    `suits.checar_etapa` recusa pela IA, e pelo painel_api ela chegava como a pessoa."""
    if metodo != "PATCH" or op["caminho"] != "/ops/api/suits/{pid}" or not isinstance(corpo, dict):
        return False
    from command_center.providers import suits
    return corpo.get("status") in suits.SO_DA_EQUIPE


def tipo_para_ia(metodo, caminho, corpo=None):
    """#420: ler | fazer | aprovar | bloqueada — o que a IA do painel faz com esta rota. Lê e faz o trabalho interno
    direto; o que sai para fora, cobra (o `confirma` do conector), apaga, não volta atrás ou é de uma pessoa vira o
    cartão de aprovar; o que é decisão de uma pessoa sobre a própria IA (SO_GENTE) a IA não faz."""
    metodo = str(metodo or "").upper()
    if metodo == "GET":
        return "ler"
    try:
        caminho = caminho_seguro(caminho)
    except ValueError:
        return "fazer"                     # o `executar_como` recusa o caminho torto com a mensagem para a IA
    op = _operacao(metodo, caminho)
    if op and SO_GENTE.match(op["caminho"]):
        return "bloqueada"
    if op and (op["confirma"] or metodo == "DELETE" or NAO_VOLTA.search(op["caminho"]) or SO_COM_CLIQUE.match(op["caminho"])
               or DE_UMA_PESSOA.match(op["caminho"]) or _etapa_da_equipe(metodo, op, corpo)):
        return "aprovar"
    return "fazer"


def _quem_pelo_id(con, user_id):
    """A pessoa do painel, no mesmo formato que `auth.usuario_atual` devolve."""
    u = con.execute("SELECT id, email, name, role, cargo, active FROM users WHERE id=?", (user_id,)).fetchone()
    if not u or not u["active"]:
        raise ValueError("a pessoa que fez o pedido não está ativa no painel")
    return {"id": u["id"], "email": u["email"], "name": u["name"], "role": u["role"], "free": auth.livre(u["email"]),
            "cargo": None if auth.livre(u["email"]) else u["cargo"], "via": "ia"}


def executar_como(user_id, metodo, caminho, corpo=None, consulta=None, aprovado=False):
    """#420 (dono, 28/10: *"ela tem que operar, editar, mudar o que for preciso ... fazer tudo ali dentro"*): a IA do
    painel (AI Command) opera como a pessoa que fez o pedido, pela MESMA rota do botão — papel, cargo, validação,
    travas e auditoria da rota valem iguais. A credencial é uma sessão interna que vale só esta chamada e é revogada
    no fim. O que vai para fora ou cobra (`confirma`) só roda com `aprovado=True`, isto é, depois do clique de uma
    pessoa no cartão de aprovar (motor → acoes_painel.painel_api)."""
    import secrets as _s
    metodo = str(metodo or "").upper()
    if metodo not in METODOS:
        raise ValueError(f"método inválido: use um de {', '.join(METODOS)}")
    caminho = caminho_seguro(caminho)
    if FORA.match(caminho):
        raise ValueError("login, chaves, cofre e área do cliente não são operados pela IA")
    op = _operacao(metodo, caminho)
    if not op:
        raise ValueError(f"{metodo} {caminho} não existe no painel (veja painel_operacoes)")
    if SO_GENTE.match(op["caminho"]):                # debug 29/10: nem pelo cartão de aprovar
        raise ValueError("aprovar ou recusar o que a IA propõe e mudar a política são decisão de uma pessoa no "
                         "painel: a IA não faz isso")
    if tipo_para_ia(metodo, caminho, corpo) == "aprovar" and not aprovado:
        raise ValueError("isto sai para fora, cobra ou apaga: só roda depois do aprovar de uma pessoa")
    con = conectar()
    try:
        quem = _quem_pelo_id(con, user_id)
        if not pode(quem, op["papel"]):
            raise ValueError(f"isto é do papel {op['papel']} ou acima; quem pediu é {quem['role']}")
        token, _ = auth.abrir_sessao(con, quem["id"], False, "127.0.0.1", "ai-command (interna)")
        con.commit()
    finally:
        con.close()
    csrf = _s.token_urlsafe(24)
    ctx = {"base_url": "http://127.0.0.1",
           "cabecalhos": {"cookie": f"{auth.COOKIE_SESSAO}={token}; {auth.COOKIE_CSRF}={csrf}", "x-csrf": csrf,
                          "user-agent": "ai-command (interna)"}}
    status = None
    try:
        status, resposta = _requisicao(ctx, metodo, caminho, corpo, consulta)
    finally:
        con = conectar()
        try:
            auth.revogar_sessao(con, token)
            if metodo != "GET":
                auditar(con, "ai.painel_api", f"user:{quem['id']}", user_id=quem["id"], entity_type="mcp",
                        detail={"metodo": metodo, "caminho": caminho, "status": status, "aprovado": bool(aprovado)})
            con.commit()
        finally:
            con.close()
    return {"status": status, "ok": 200 <= status < 300, "resposta": resposta}


def _requisicao(ctx, metodo, caminho, corpo, consulta):
    """A requisição de verdade, para o próprio app (ASGI), com a credencial de quem chamou.
    Roda num laço de eventos próprio: quem chama já está fora do laço do servidor."""
    import httpx
    from command_center.api.main import app

    async def _vai():
        transporte = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transporte, base_url=ctx["base_url"]) as c:
            return await c.request(metodo, caminho, params=consulta or None,
                                   json=corpo if corpo is not None and metodo != "GET" else None,
                                   headers=ctx["cabecalhos"], timeout=120)
    r = asyncio.run(_vai())
    try:
        resposta = r.json()
    except (ValueError, json.JSONDecodeError):
        resposta = r.text[:4000]
    return r.status_code, resposta
