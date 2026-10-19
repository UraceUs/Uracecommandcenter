"""O CI em partes paralelas não tira nenhum teste (#344).

Dono, 19/10: o CI levava ~20 min; aprovou dividir em máquinas paralelas *"sem tirar nenhum teste"*.
O `conftest.py` da raiz (`--parte K/N`) reparte por arquivo (arquivo grande demais, em blocos seguidos).
Aqui a prova: as partes juntas são a suíte inteira, nenhum teste cai em duas, um arquivo não se espalha
(teste que depende do anterior no mesmo arquivo segue com ele), e o ci.yml usa as partes todas da matriz.
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


def _suite(sorteio, arquivos):
    return [f"t/test_{a}.py::t{i}" for a in range(arquivos) for i in range(sorteio.randrange(1, 40))]


def test_as_partes_juntas_sao_tudo_e_nenhum_teste_se_repete():
    sorteio = random.Random(344)
    for arquivos in (0, 1, 2, 7, 150):
        ids = _suite(sorteio, arquivos)
        for n in (1, 2, 3, 4):
            cada = [partes.da_parte(ids, k, n) for k in range(1, n + 1)]
            assert set().union(*cada) == set(ids), (arquivos, n)
            assert sum(len(c) for c in cada) == len(ids), "nenhum teste em duas partes"


def test_arquivo_pequeno_fica_inteiro_numa_parte_e_o_grande_vai_em_blocos_seguidos():
    sorteio = random.Random(19)
    ids = _suite(sorteio, 60)
    cada = [partes.da_parte(ids, k, 2) for k in (1, 2)]
    for a in {i.split("::")[0] for i in ids}:
        assert sum(any(i.startswith(a + "::") for i in c) for c in cada) == 1, a
    assert abs(len(cada[0]) - len(cada[1])) <= 40, "equilibradas pelo número de testes"
    # o e2e: um arquivo com 160 testes e outro com 1, em 3 partes
    grande = [f"e2e/test_navegador.py::t{i:03d}" for i in range(160)] + ["e2e/test_pacote.py::t"]
    cada = [partes.da_parte(grande, k, 3) for k in (1, 2, 3)]
    assert sorted(map(len, cada)) == [53, 54, 54]
    for c in cada:
        nav = sorted(int(i[-3:]) for i in c if "navegador" in i)
        assert nav == list(range(nav[0], nav[-1] + 1)), "bloco seguido, na ordem do arquivo"


def test_a_divisao_nao_depende_da_ordem_dos_arquivos():
    ids = [f"{a}.py::t{i}" for a in "abcdef" for i in range(7)]
    outra = [f"{a}.py::t{i}" for a in "fedcba" for i in range(7)]
    for k in (1, 2, 3):
        assert partes.da_parte(ids, k, 3) == partes.da_parte(outra, k, 3)


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
