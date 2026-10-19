"""O CI do GitHub já passou neste commit? (#277)

Dono, 15/10: *"a partir de agora você rode os testes ... no seu ambiente virtual, porque os testes
estão demorando de 15 a 20 minutos, isso querendo ou não acarreta tempo na nossa produção"*.

O deploy (`servir_command_center.sh`) pergunta à API pública do GitHub pelos check runs do commit que
vai subir e passa o JSON para cá. Responde `ok` só quando os TRÊS jobs do CI — Python, frontend e
end-to-end — terminaram e passaram. Desde #344 o Python e o end-to-end rodam em partes paralelas
("… (1/3)", "… (2/3)", "… (3/3)"): todas as partes verdes = verde; uma vermelha, rodando ou faltando = não. Qualquer outra coisa (algum vermelho, algum ainda rodando, algum
faltando, JSON quebrado, GitHub fora do ar) responde o motivo, e o deploy roda a bateria na VPS como
antes. Nunca sobe código sem prova: a dúvida sempre cai no lado de testar.

Uso:  curl … /commits/<sha>/check-runs | python ci_verde.py
"""
import json
import re
import sys

# o começo do nome de cada job em .github/workflows/ci.yml
JOBS = ("Python", "Frontend", "End-to-end")

# #344: o pytest e o end-to-end rodam em partes paralelas, cada uma um check com "(K/N)" no fim do nome
PARTE = re.compile(r"\((\d+)/(\d+)\)\s*$")


def _job(runs, job):
    """'' quando o job (inteiro ou TODAS as suas partes) terminou verde; senão o motivo."""
    deste = [r for r in runs if str(r.get("name", "")).startswith(job)]
    if not deste:
        return f"o job {job} não rodou neste commit"
    por_nome = {}
    for r in deste:
        por_nome.setdefault(str(r.get("name")), []).append(r)
    # em partes: todas as K de 1 a N precisam estar lá (uma que nem começou não é verde)
    partes = {PARTE.search(nome).groups() for nome in por_nome if PARTE.search(nome)}
    for n in {int(n) for _, n in partes}:
        faltam = sorted(set(range(1, n + 1)) - {int(k) for k, m in partes if int(m) == n})
        if faltam:
            return f"o job {job} não tem a parte {faltam[0]}/{n} neste commit"
    for nome, checks in sorted(por_nome.items()):
        # re-run cria outro check com o mesmo nome: vale o mais recente
        ultimo = max(checks, key=lambda r: str(r.get("started_at") or ""))
        rotulo = job + (f" ({'/'.join(PARTE.search(nome).groups())})" if PARTE.search(nome) else "")
        if ultimo.get("status") != "completed":
            return f"o job {rotulo} ainda está rodando"
        if ultimo.get("conclusion") != "success":
            return f"o job {rotulo} terminou {ultimo.get('conclusion')}"
    return ""


def veredito(dados):
    """('ok', '') quando os três jobs — com todas as partes — passaram; senão ('', motivo)."""
    runs = (dados or {}).get("check_runs") if isinstance(dados, dict) else None
    if not isinstance(runs, list):
        return "", "o GitHub não devolveu os checks deste commit"
    for job in JOBS:
        motivo = _job(runs, job)
        if motivo:
            return "", motivo
    return "ok", ""


def main():
    try:
        dados = json.load(sys.stdin)
    except ValueError:
        dados = None
    ok, motivo = veredito(dados)
    print(ok or motivo)


if __name__ == "__main__":
    main()
