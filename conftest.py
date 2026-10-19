"""Divide a suíte em partes para o CI rodar em várias máquinas ao mesmo tempo (#344).

Dono, 19/10: o CI levava ~20 min por rodada; aprovou dividir em máquinas paralelas *sem tirar nenhum
teste*. `python -m pytest --parte 2/3` roda só a parte 2 de 3. Sem `--parte`, roda tudo (VPS, dev, local).

A divisão é por ARQUIVO: há testes que dependem do que um teste anterior do mesmo arquivo deixou no
banco (19/10: repartir teste a teste quebrou 15 no backend), então um arquivo inteiro fica numa parte só,
na ordem de sempre. Os arquivos são distribuídos pelo número de testes, do maior para o menor, sempre na
parte mais leve (desempate pelo nome) — igual em toda máquina. Um arquivo maior que a cota de uma parte
(o e2e tem um com ~160 testes) é cortado em blocos SEGUIDOS, que mantêm a ordem do arquivo.
Cada teste cai em exatamente uma parte e a união das partes é a suíte inteira.

Fica na raiz do repositório para valer tanto em `python -m pytest -q` (backend) quanto em
`pytest command_center/tests/e2e`. Não importa nada da aplicação (o conftest dos testes isola o ambiente
antes de qualquer import).
"""
import pytest


def _ler_parte(texto):
    """'2/3' -> (2, 3). Erro claro em qualquer outra coisa: parte errada não pode virar 'rodou zero'."""
    try:
        k, n = (int(x) for x in str(texto).split("/"))
    except ValueError:
        raise pytest.UsageError(f"--parte espera K/N (ex.: 1/3), veio {texto!r}") from None
    if n < 1 or not 1 <= k <= n:
        raise pytest.UsageError(f"--parte {texto}: K precisa estar entre 1 e N")
    return k, n


def dividir(nodeids, n):
    """Lista de n conjuntos de nodeids. Determinístico, sem sobra nem repetição, arquivo inteiro junto."""
    arquivos = {}
    for nid in nodeids:                       # mantém a ordem da coleta dentro de cada arquivo
        arquivos.setdefault(nid.split("::", 1)[0], []).append(nid)
    cota = max(1, -(-len(nodeids) // n))      # teto de total/n
    blocos = []
    for nome in sorted(arquivos):
        ids = arquivos[nome]
        blocos += [ids[i:i + cota] for i in range(0, len(ids), cota)]
    partes = [[] for _ in range(n)]
    for bloco in sorted(blocos, key=lambda b: (-len(b), b[0])):
        min(partes, key=len).extend(bloco)    # min() devolve a primeira mais leve: desempate estável
    return [set(p) for p in partes]


def da_parte(nodeids, k, n):
    """Os nodeids da parte k de n."""
    return dividir(nodeids, n)[k - 1]


def pytest_addoption(parser):
    parser.addoption("--parte", default=None, metavar="K/N",
                     help="roda só a parte K de N da suíte (CI em paralelo, #344)")


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    texto = config.getoption("--parte")
    if not texto:
        return
    k, n = _ler_parte(texto)
    total = len(items)
    escolhidos = da_parte([i.nodeid for i in items], k, n)
    ficam = [i for i in items if i.nodeid in escolhidos]
    fora = [i for i in items if i.nodeid not in escolhidos]
    if fora:
        config.hook.pytest_deselected(items=fora)
    items[:] = ficam
    config._parte_resumo = f"parte {k}/{n}: {len(ficam)} de {total} testes coletados"


def pytest_report_collectionfinish(config):
    return getattr(config, "_parte_resumo", None)


def pytest_terminal_summary(terminalreporter, config):
    resumo = getattr(config, "_parte_resumo", None)
    if resumo:
        terminalreporter.write_line(resumo)
