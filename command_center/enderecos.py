"""Os endereços da URACE, num lugar só (#79).

Dono, 04/10: *"somente as urls dos paineis de logins ficaram com a url nova preciso que todas
tenham a url urace.us"*.

- `ops.urace.us` é o endereço do sistema: painel da equipe, login do MCP (OAuth), páginas
  legais, webhooks. É o que o painel MOSTRA e manda colar nos outros sistemas.
- `my.urace.us` é o do cliente (área do cliente e o app).
- `urace-bridge.duckdns.org` é o endereço antigo. **Continua respondendo**: Kommo, Dialpad,
  Intuit e os conectores já ligados apontam para ele até alguém trocar lá. Quem entra por
  ele recebe as respostas com o próprio endereço, para o login não se perder no meio.

Um `Host` que não é nosso nunca vira link (injeção de cabeçalho): cai no principal.

O site público (#148) tem os nomes de `CC_SITE_HOSTS`, hoje `novo.urace.us` (a prévia). Na troca do
domínio (#462) entram `urace.us` e `www.urace.us`, e `CC_SITE_PRINCIPAL=urace.us` diz qual deles vai
nos links e para onde os outros levam (301).
"""
import os
from urllib.parse import urlsplit

PAINEL = "ops.urace.us"
CLIENTE = "my.urace.us"
ANTIGO = "urace-bridge.duckdns.org"
SITE_PREVIA = "novo.urace.us"


def _host(valor):
    valor = (valor or "").strip()
    if not valor:
        return ""
    return (urlsplit(valor if "://" in valor else "https://" + valor).hostname or "").lower()


def principal():
    """`https://ops.urace.us`, ou o que `CC_PUBLIC_URL` disser."""
    return (os.environ.get("CC_PUBLIC_URL") or f"https://{PAINEL}").rstrip("/")


def host_principal():
    return _host(principal()) or PAINEL


def cliente():
    return f"https://{CLIENTE}"


def nossos():
    """Os nomes que este servidor atende."""
    nomes = {PAINEL, CLIENTE, ANTIGO, host_principal()}
    for v in (os.environ.get("CC_PUBLIC_HOST"),):
        if _host(v):
            nomes.add(_host(v))
    nomes.update(_host(d) for d in os.environ.get("CC_DOMINIOS_EXTRAS", "").split() if _host(d))
    return nomes


def host_da_requisicao(request):
    """O nome por onde a pessoa entrou, se for nosso; senão, o principal."""
    if request is None:
        return host_principal()
    h = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0]
    h = h.split(":")[0].strip().lower()
    return h if h in nossos() else host_principal()


def base_da_requisicao(request):
    return f"https://{host_da_requisicao(request)}"


def site_hosts():
    """Os nomes do site público, na ordem de `CC_SITE_HOSTS` (por padrão, a prévia)."""
    nomes = [_host(h) for h in os.environ.get("CC_SITE_HOSTS", SITE_PREVIA).split(",")]
    return [h for i, h in enumerate(nomes) if h and h not in nomes[:i]] or [SITE_PREVIA]


def site_redireciona():
    """#462: o nome para onde os outros nomes do site levam (301), quando `CC_SITE_PRINCIPAL` é um deles."""
    p = _host(os.environ.get("CC_SITE_PRINCIPAL"))
    return p if p in site_hosts() else None


def site_principal():
    """O nome do site que vai nos links: o de `CC_SITE_PRINCIPAL`; sem ele, o primeiro de `CC_SITE_HOSTS`."""
    return site_redireciona() or site_hosts()[0]
