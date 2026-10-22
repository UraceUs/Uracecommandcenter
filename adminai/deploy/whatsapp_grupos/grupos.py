"""Ajudante do configurar_whatsapp_grupos.sh (#383): o env dos grupos e a config do OpenClaw.

    python3 grupos.py token   <env>               cria WA_GRUPOS_TOKEN se faltar (nunca imprime o valor)
    python3 grupos.py resolver <env> <lista.json> preenche WA_GRUPO_<PAPEL>_JID pelo NOME do grupo, a partir
                                                  de `openclaw directory groups list --channel whatsapp --json`
    python3 grupos.py groups  <env>               o mapa channels.whatsapp.groups (só os JIDs da lista,
                                                  requireMention false: o agente do ateliê lê tudo do grupo)
    python3 grupos.py faltam  <env>               os papéis ainda sem JID (vazio = pronto)

Só biblioteca padrão. O nome casa sem acento, sem caixa e sem espaço repetido; dois grupos com o mesmo nome
não são escolhidos (ambíguo: o dono resolve, nunca o script).
"""
import json
import os
import re
import secrets
import sys
import unicodedata


def ler(caminho):
    linhas, valores = [], {}
    with open(caminho, encoding="utf-8") as f:
        for linha in f.read().splitlines():
            linhas.append(linha)
            s = linha.strip()
            if s and not s.startswith("#") and "=" in s:
                k, v = s.split("=", 1)
                v = v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                    v = v[1:-1]
                valores[k.strip()] = v
    return linhas, valores


def gravar(caminho, linhas, novos):
    """Troca o valor das chaves em `novos` (ou acrescenta) sem mexer no resto; arquivo 600."""
    feitos, saida = set(), []
    for linha in linhas:
        k = linha.split("=", 1)[0].strip() if "=" in linha and not linha.strip().startswith("#") else None
        if k in novos:
            saida.append(f"{k}={novos[k]}")
            feitos.add(k)
        else:
            saida.append(linha)
    saida += [f"{k}={v}" for k, v in novos.items() if k not in feitos]
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(saida) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, caminho)


def papeis(valores):
    return [p for p in re.split(r"[,\s]+", valores.get("WA_GRUPOS", "design,fornecedor").strip().lower())
            if re.fullmatch(r"[a-z_]{2,30}", p or "")]


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    return re.sub(r"\s+", " ", "".join(c for c in s if not unicodedata.combining(c))).strip().lower()


def grupos_da_lista(dados):
    """[(jid, nome)] de qualquer formato razoável da saída do OpenClaw (lista ou {groups|items|results: []})."""
    if isinstance(dados, dict):
        for k in ("groups", "items", "results", "entries", "data"):
            if isinstance(dados.get(k), list):
                dados = dados[k]
                break
    saida = []
    for g in dados if isinstance(dados, list) else []:
        if not isinstance(g, dict):
            continue
        jid = next((g[k] for k in ("id", "jid", "groupId", "target") if isinstance(g.get(k), str) and g[k].endswith("@g.us")), None)
        nome = next((g[k] for k in ("name", "subject", "title", "displayName", "label") if isinstance(g.get(k), str)), "")
        if jid:
            saida.append((jid, nome))
    return saida


def resolver(caminho, lista):
    linhas, valores = ler(caminho)
    with open(lista, encoding="utf-8") as f:
        texto = f.read()
    try:
        dados = json.loads(texto[min([i for i in (texto.find("["), texto.find("{")) if i >= 0] or [0]):])
    except ValueError:
        dados = []
    achados = grupos_da_lista(dados)
    novos, relato = {}, []
    for p in papeis(valores):
        P = p.upper()
        nome = valores.get(f"WA_GRUPO_{P}_NOME", "")
        atual = valores.get(f"WA_GRUPO_{P}_JID", "")
        if atual.endswith("@g.us"):
            relato.append(f"{p}: já configurado")
            continue
        iguais = [j for j, n in achados if norm(n) == norm(nome)] if nome else []
        if len(iguais) == 1:
            novos[f"WA_GRUPO_{P}_JID"] = iguais[0]
            relato.append(f"{p}: achado pelo nome \"{nome}\"")
        elif len(iguais) > 1:
            relato.append(f"{p}: {len(iguais)} grupos com o nome \"{nome}\" — ponha o JID certo à mão")
        else:
            relato.append(f"{p}: nenhum grupo com o nome \"{nome}\" (o número logado está no grupo?)")
    if novos:
        gravar(caminho, linhas, novos)
    print("\n".join(relato))


def token(caminho):
    linhas, valores = ler(caminho)
    if valores.get("WA_GRUPOS_TOKEN"):
        print("segredo: já existe (mantido)")
        return
    gravar(caminho, linhas, {"WA_GRUPOS_TOKEN": secrets.token_urlsafe(32)})
    print("segredo: criado (fica só no env, 600)")


def groups(caminho):
    _, valores = ler(caminho)
    mapa = {}
    for p in papeis(valores):
        jid = valores.get(f"WA_GRUPO_{p.upper()}_JID", "")
        if jid.endswith("@g.us"):
            mapa[jid] = {"requireMention": False}
    print(json.dumps(mapa))


def faltam(caminho):
    _, valores = ler(caminho)
    print(" ".join(p for p in papeis(valores) if not valores.get(f"WA_GRUPO_{p.upper()}_JID", "").endswith("@g.us")))


if __name__ == "__main__":
    acao, *args = sys.argv[1:] or ["?"]
    {"token": token, "resolver": resolver, "groups": groups, "faltam": faltam}.get(
        acao, lambda *a: sys.exit(__doc__))(*args)
