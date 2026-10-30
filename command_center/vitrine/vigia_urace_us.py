"""#529: vigia o que muda no urace.us (o WordPress de hoje) até a troca do DNS.

Dono, 30/10: *"monitore o que for alterado lá, muita gente mexe, então não tem como dizer quem foi"*. Tudo o que mudar lá
antes da troca precisa vir para o site novo, senão se perde. O workflow `.github/workflows/vigia-urace-us.yml` roda isto a
cada 3 horas: lê a data de alteração de cada página, post e produto pela API pública do WordPress,
compara com `docs/site-publico/urace-us-conferido.json` (o que já foi trazido) e abre ou completa a issue
"urace.us mudou". Trouxe a mudança? Rode `python -m command_center.vitrine.vigia_urace_us --conferir` e comite o arquivo.

Só leitura pública do urace.us: nada de senha, e nada é escrito lá.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

API = "https://urace.us/wp-json/wp/v2/"
# pilotos e depoimentos ficam de fora: o link tem o nome da pessoa e o repositório é público (#244)
TIPOS = ("pages", "posts", "product")
CONFERIDO = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "site-publico", "urace-us-conferido.json")
TITULO = "urace.us mudou: trazer para o site novo"
MARCA = "<!-- vigia-urace-us:{} -->"


def _get(url, token=None, dados=None, metodo=None):
    h = {"User-Agent": "urace-vigia/1 (+https://github.com/UraceUs/Uracecommandcenter)", "Accept": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    corpo = json.dumps(dados).encode() if dados is not None else None
    if corpo:
        h["Content-Type"] = "application/json"
    with urllib.request.urlopen(urllib.request.Request(url, data=corpo, headers=h, method=metodo), timeout=60) as r:
        return json.loads(r.read() or b"null"), r.headers


def ler_site(get=_get):
    """{tipo: {link: modified_gmt}} de hoje no urace.us; um tipo que não respondeu fica de fora (e não acusa mudança)."""
    atual = {}
    for tipo in TIPOS:
        itens, pagina = {}, 1
        try:
            while True:
                q = urllib.parse.urlencode({"per_page": 100, "page": pagina, "_fields": "link,modified_gmt"})
                lista, cab = get(f"{API}{tipo}?{q}")
                itens.update({x["link"]: x["modified_gmt"] for x in lista})
                if pagina >= int(cab.get("X-WP-TotalPages") or 1):
                    break
                pagina += 1
        except Exception as e:                          # noqa: BLE001 — o tipo fica de fora desta rodada
            print(f"aviso: {tipo} não respondeu ({e})", file=sys.stderr)
            continue
        atual[tipo] = itens
    return atual


def mudancas(conferido, atual):
    """O que está diferente do conferido: [(tipo, link, antes, agora)] — `antes` None é novo, `agora` None saiu do ar."""
    out = []
    for tipo, itens in atual.items():
        velhos = conferido.get(tipo, {})
        for link, quando in sorted(itens.items()):
            if velhos.get(link) != quando:
                out.append((tipo, link, velhos.get(link), quando))
        out += [(tipo, link, quando, None) for link, quando in sorted(velhos.items()) if link not in itens]
    return out


def _linha(m):
    tipo, link, antes, agora = m
    marca = MARCA.format(f"{link}@{agora}")
    if antes is None:
        return f"- [ ] **novo** ({tipo}): {link}, publicado ou alterado em {agora} GMT {marca}"
    if agora is None:
        return f"- [ ] **saiu do ar** ({tipo}): {link} (a última alteração conferida era de {antes} GMT) {marca}"
    return f"- [ ] **mudou** ({tipo}): {link}, em {agora} GMT (o conferido era de {antes} GMT) {marca}"


def avisar(lista, repo, token, get=_get):
    """Abre a issue (ou comenta na aberta) só com o que ainda não foi avisado. Devolve quantas linhas saíram."""
    base = f"https://api.github.com/repos/{repo}"
    abertas, _ = get(f"{base}/issues?state=open&creator=github-actions%5Bbot%5D&per_page=100", token)
    issue = next((i for i in abertas if i["title"] == TITULO and "pull_request" not in i), None)
    ja = ""
    if issue:
        comentarios, _ = get(f"{base}/issues/{issue['number']}/comments?per_page=100", token)
        ja = (issue.get("body") or "") + "".join(c.get("body") or "" for c in comentarios)
    novas = [_linha(m) for m in lista if MARCA.format(f"{m[1]}@{m[3]}") not in ja]
    if not novas:
        return 0
    texto = "\n".join(novas)
    if issue:
        get(f"{base}/issues/{issue['number']}/comments", token, {"body": "Mudou mais no urace.us:\n\n" + texto}, "POST")
    else:
        corpo = ("Alguém mudou o urace.us (o WordPress de hoje). Até a troca do DNS, cada mudança precisa vir para o site "
                 "novo, senão se perde na troca (dono, 30/10, #529).\n\n" + texto +
                 "\n\nTrouxe? Rode `python -m command_center.vitrine.vigia_urace_us --conferir`, comite "
                 "`docs/site-publico/urace-us-conferido.json` no mesmo PR e feche esta issue.")
        get(f"{base}/issues", token, {"title": TITULO, "body": corpo}, "POST")
    return len(novas)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    conferido = {}
    if os.path.exists(CONFERIDO):
        with open(CONFERIDO, encoding="utf-8") as f:
            conferido = json.load(f)
    atual = ler_site()
    if "--conferir" in argv:                           # trouxe tudo: o de hoje vira o conferido
        with open(CONFERIDO, "w", encoding="utf-8") as f:
            json.dump({**conferido, **atual}, f, indent=1, sort_keys=True)
            f.write("\n")
        print(f"conferido: {sum(len(v) for v in atual.values())} itens")
        return 0
    lista = mudancas(conferido, atual)
    for m in lista:
        print(_linha(m))
    repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if lista and repo and token:
        print(f"avisadas: {avisar(lista, repo, token)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
