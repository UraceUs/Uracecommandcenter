"""O CI em partes paralelas não tira nenhum teste (#344).

Dono, 19/10: o CI levava ~20 min; aprovou dividir em máquinas paralelas *"sem tirar nenhum teste"*.
O `conftest.py` da raiz (`--parte K/N`) ordena os testes coletados pelo nodeid e reparte em rodízio.
Aqui a prova: as partes juntas são a suíte inteira, nenhum teste cai em duas, e o ci.yml usa as partes
todas da matriz.
"""
import random
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
WORKFLOW = RAIZ / ".github" / "workflows" / "ci.yml"
sys.path.insert(0, str(RAIZ))
import conftest as partes  # noqa: E402  (o conftest da raiz, com a divisão)


def test_as_partes_juntas_sao_tudo_e_nenhum_teste_se_repete():
    sorteio = random.Random(344)
    for total in (0, 1, 2, 5, 161, 2624):
        ids = [f"t/test_{sorteio.randrange(10**6)}.py::t{i}" for i in range(total)]
        for n in (1, 2, 3, 4):
            cada = [partes.da_parte(ids, k, n) for k in range(1, n + 1)]
            assert set().union(*cada) == set(ids), (total, n)
            assert sum(len(c) for c in cada) == len(set(ids)), "nenhum teste em duas partes"
            assert max(map(len, cada)) - min(map(len, cada)) <= 1, "partes do mesmo tamanho"


def test_a_divisao_nao_depende_da_ordem_da_coleta():
    ids = [f"a.py::t{i}" for i in range(50)]
    embaralhado = ids[::-1]
    for k in (1, 2, 3):
        assert partes.da_parte(ids, k, 3) == partes.da_parte(embaralhado, k, 3)


def _coletados(*args):
    r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *args],
                       cwd=RAIZ, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    return [linha for linha in r.stdout.splitlines() if "::" in linha], r.stdout


def test_na_coleta_de_verdade_as_tres_partes_do_e2e_somam_a_suite():
    tudo, _ = _coletados("command_center/tests/e2e")
    assert len(tudo) > 100
    juntas = []
    for k in (1, 2, 3):
        ids, saida = _coletados("command_center/tests/e2e", "--parte", f"{k}/3")
        assert f"parte {k}/3: {len(ids)} de {len(tudo)} testes coletados" in saida, "cada parte diz quantos rodou"
        juntas += ids
    assert sorted(juntas) == sorted(tudo)


def test_parte_errada_e_erro_e_nao_zero_testes():
    for ruim in ("0/3", "4/3", "1-3", "x"):
        r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
                            "command_center/tests/e2e", "--parte", ruim], cwd=RAIZ, capture_output=True, text=True)
        assert r.returncode != 0, ruim


@pytest.mark.parametrize("job", ["python", "e2e"])
def test_o_ci_roda_cada_parte_da_matriz_com_o_total_da_matriz(job):
    jobs = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]
    matriz = jobs[job]["strategy"]["matrix"]["parte"]
    assert matriz == list(range(1, len(matriz) + 1)), "partes 1..N, sem pular"
    assert jobs[job]["strategy"]["fail-fast"] is False
    comandos = [p.get("run", "") for p in jobs[job]["steps"] if "-m pytest" in p.get("run", "")]
    principal = comandos[0]
    assert "--parte ${{ matrix.parte }}/${{ strategy.job-total }}" in principal
    # nenhum outro pytest da suíte inteira escondido: só a prova com fotos (que roda numa parte só)
    for outro in comandos[1:]:
        assert "test_pacote_de_provas.py" in outro


def test_a_tag_ci_verde_espera_todas_as_partes():
    jobs = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]
    assert {"python", "e2e"} <= set(jobs["verde"]["needs"]), "needs de um job em matriz espera todas as partes"
