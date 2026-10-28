"""#436: o rotas.py (~2.800 linhas) virou módulos por assunto sem mudar rota nenhuma.

Trava contra rota perdida: a lista abaixo é a do rotas.py ANTES da divisão (método, caminho,
na ordem do arquivo). Toda ela tem de estar no app, uma vez só; nenhuma rota de outro
módulo pode pegar a mesma URL antes dela; e o catch-all da SPA continua depois de todas.
"""
from fastapi.routing import APIRoute

from command_center.api.main import app

MODULOS = ("rotas", "rotas_clientes", "rotas_gmail", "rotas_docusign", "rotas_qbo", "rotas_ia")

ESPERADAS = [
    ('GET', '/ops/api/integrations'),
    ('POST', '/ops/api/integrations/check'),
    ('POST', '/ops/api/sync'),
    ('GET', '/ops/api/sync'),
    ('GET', '/ops/api/dashboard'),
    ('GET', '/ops/api/needs-attention'),
    ('POST', '/ops/api/needs-attention/dismiss'),
    ('POST', '/ops/api/needs-attention/restore'),
    ('GET', '/ops/api/clients'),
    ('GET', '/ops/api/clients/{cid}'),
    ('PATCH', '/ops/api/clients/{cid}'),
    ('GET', '/ops/api/search'),
    ('GET', '/ops/api/tasks'),
    ('GET', '/ops/api/waivers'),
    ('GET', '/ops/api/emails'),
    ('PATCH', '/ops/api/emails/{eid}'),
    ('GET', '/ops/api/docusign/templates'),
    ('GET', '/ops/api/docusign/templates/{tid}'),
    ('GET', '/ops/api/docusign/templates/{tid}/documents/{did}'),
    ('PATCH', '/ops/api/docusign/templates/{tid}'),
    ('POST', '/ops/api/docusign/templates/{tid}/documents/{did}'),
    ('GET', '/ops/api/policies'),
    ('PUT', '/ops/api/policies/{action}'),
    ('GET', '/ops/api/gmail/labels'),
    ('GET', '/ops/api/emails/{eid}/thread'),
    ('GET', '/ops/api/emails/{eid}/html/{message_id}'),
    ('POST', '/ops/api/emails/{eid}/labels'),
    ('POST', '/ops/api/gmail/triage'),
    ('GET', '/ops/api/gmail/triage'),
    ('POST', '/ops/api/emails/{eid}/move'),
    ('POST', '/ops/api/gmail/classify'),
    ('GET', '/ops/api/gmail/classify'),
    ('GET', '/ops/api/gmail/manual'),
    ('PATCH', '/ops/api/gmail/manual/{lid}'),
    ('POST', '/ops/api/gmail/manual/confirm'),
    ('POST', '/ops/api/gmail/manual/refresh'),
    ('GET', '/ops/api/waivers/{wid}/download'),
    ('GET', '/ops/api/waivers/{wid}/evidence.zip'),
    ('POST', '/ops/api/waivers/{wid}/trash'),
    ('POST', '/ops/api/waivers/{wid}/restore'),
    ('POST', '/ops/api/waivers/{wid}/void'),
    ('POST', '/ops/api/waivers/{wid}/copy'),
    ('POST', '/ops/api/waivers/{wid}/resend'),
    ('POST', '/ops/api/waivers/{wid}/link'),
    ('GET', '/ops/api/clients/{cid}/waiver-flow'),
    ('PUT', '/ops/api/clients/{cid}/waiver-flow'),
    ('GET', '/ops/api/clients/{cid}/waiver-invite'),
    ('POST', '/ops/api/clients/{cid}/waiver-invite'),
    ('POST', '/ops/api/sync/full'),
    ('GET', '/ops/api/sync/full'),
    ('GET', '/ops/api/service-attribution'),
    ('POST', '/ops/api/service-attribution'),
    ('GET', '/ops/api/clients/{cid}/duplicates'),
    ('GET', '/ops/api/client-duplicates'),
    ('POST', '/ops/api/client-merge'),
    ('POST', '/ops/api/client-duplicates/ai'),
    ('GET', '/ops/api/client-duplicates/ai'),
    ('POST', '/ops/api/clients/{cid}/scan'),
    ('POST', '/ops/api/client-scan-all'),
    ('GET', '/ops/api/client-scan-all'),
    ('GET', '/ops/api/tasks/{tid}/detail'),
    ('POST', '/ops/api/needs-attention/instruct'),
    ('POST', '/ops/api/tasks/{tid}/instruct'),
    ('GET', '/ops/api/ai/capabilities'),
    ('GET', '/ops/api/ai/learnings'),
    ('POST', '/ops/api/ai/learnings'),
    ('POST', '/ops/api/ai/learnings/{lid}/toggle'),
    ('GET', '/ops/api/ai/events'),
    ('POST', '/ops/api/ai/events/process'),
    ('GET', '/ops/api/automation/rules'),
    ('PUT', '/ops/api/automation/rules/{name}'),
    ('GET', '/ops/api/invoices'),
    ('GET', '/ops/api/invoice-reminders'),
    ('PUT', '/ops/api/invoice-reminders'),
    ('PATCH', '/ops/api/invoice-reminders/{rid}'),
    ('POST', '/ops/api/invoice-reminders/send-now'),
    ('GET', '/ops/api/qbo/summary'),
    ('POST', '/ops/api/clients'),
    ('POST', '/ops/api/tasks'),
    ('POST', '/ops/api/waivers/send'),
    ('GET', '/ops/api/rate-card/check'),
    ('GET', '/ops/api/context'),
    ('POST', '/ops/api/context/sheet'),
    ('POST', '/ops/api/context/link'),
    ('POST', '/ops/api/context/file'),
    ('POST', '/ops/api/context/{cid}/check'),
    ('POST', '/ops/api/context/{cid}/toggle'),
    ('GET', '/ops/api/context/{cid}/download'),
    ('GET', '/ops/api/clients/{cid}/monthly'),
    ('PATCH', '/ops/api/clients/{cid}/profile'),
    ('GET', '/ops/api/clients/{cid}/equipment'),
    ('POST', '/ops/api/clients/{cid}/contract'),
    ('GET', '/ops/api/contracts/{kid}/download'),
    ('GET', '/ops/api/catalog'),
    ('POST', '/ops/api/catalog/chassis'),
    ('PATCH', '/ops/api/catalog/chassis/{cid}'),
    ('POST', '/ops/api/catalog/engines'),
    ('PATCH', '/ops/api/catalog/engines/{cid}'),
    ('POST', '/ops/api/catalog/parts'),
    ('PATCH', '/ops/api/catalog/parts/{cid}'),
    ('POST', '/ops/api/catalog/{kind}/{cid}/image'),
    ('GET', '/ops/api/catalog/{kind}/{cid}/image'),
    ('GET', '/ops/api/races'),
    ('POST', '/ops/api/races'),
    ('PATCH', '/ops/api/races/{rid}'),
    ('POST', '/ops/api/races/{rid}/invite'),
    ('PATCH', '/ops/api/invites/{iid}'),
    ('POST', '/ops/api/invites/{iid}/estimate'),
    ('GET', '/ops/api/gmail/filtros/{conta}'),
    ('POST', '/ops/api/gmail/filtros/{conta}/gerar'),
    ('POST', '/ops/api/gmail/filtros/{conta}/aplicar'),
    ('GET', '/ops/api/gmail/filtros/{conta}/download'),
]


def _planas():
    """(método, caminho) na ordem em que o app testa as rotas. O FastAPI novo guarda o roteador
    incluído inteiro (`_IncludedRouter`); o antigo copia as rotas para o app."""
    saida = []
    for rota in app.routes:
        if hasattr(rota, "effective_route_contexts"):
            itens = [(ctx.path or ctx.original_route.path, ctx.original_route) for ctx in rota.effective_route_contexts()]
        else:
            itens = [(getattr(rota, "path", None), rota)]
        for caminho, orig in itens:
            for metodo in sorted(getattr(orig, "methods", None) or ()):
                saida.append((metodo, caminho))
    return saida


def _cruzam(a, b):
    """Dois caminhos podem casar a mesma URL? Segmento a segmento; {x} casa qualquer um."""
    sa, sb = a.strip("/").split("/"), b.strip("/").split("/")
    if len(sa) != len(sb):
        return False
    return all(x == y or x.startswith("{") or y.startswith("{") for x, y in zip(sa, sb))


def test_nenhuma_rota_do_rotas_py_sumiu():
    assert len(ESPERADAS) == 112 and len(set(ESPERADAS)) == 112
    rotas = _planas()
    faltam = [e for e in ESPERADAS if e not in rotas]
    assert not faltam, f"rota perdida na divisão: {faltam}"
    dobradas = [e for e in ESPERADAS if rotas.count(e) != 1]
    assert not dobradas, f"rota registrada duas vezes: {dobradas}"


def test_precedencia_entre_caminhos_preservada():
    rotas = _planas()
    pos = {k: i for i, k in reversed(list(enumerate(rotas)))}
    for metodo, caminho in ESPERADAS:
        i = pos[(metodo, caminho)]
        # antes da divisão nenhuma outra rota casava a mesma URL que estas: continua assim
        rivais = [k for k in pos if k != (metodo, caminho) and k[0] == metodo and ":path}" not in k[1] and _cruzam(k[1], caminho)]
        assert not rivais, f"{metodo} {caminho} agora disputa a URL com {rivais}"
        # o catch-all da SPA (/ops/{caminho:path}, /{caminho:path}) fica depois de todas
        spa = [j for (m, c), j in pos.items() if m == metodo and ":path}" in c]
        assert all(i < j for j in spa), f"{metodo} {caminho} ficou depois do catch-all"


def test_cada_modulo_tem_o_seu_r_e_o_mcp_enxerga():
    """mcp_operar.catalogo() acha as rotas pelo atributo `r` de cada módulo de command_center.api."""
    import importlib
    vistas = set()
    for nome in MODULOS:
        mod = importlib.import_module(f"command_center.api.{nome}")
        assert mod.r.prefix == "/ops/api" and not mod.r.dependencies
        for rota in mod.r.routes:
            if isinstance(rota, APIRoute):
                vistas |= {(m, rota.path) for m in rota.methods}
    assert vistas == set(ESPERADAS)
