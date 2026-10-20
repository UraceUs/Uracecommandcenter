#!/usr/bin/env python3
"""Assinatura de SMS do Dialpad apontando para o VPS (o robô SDR atende por SMS, dono 20/10).

O Heroku antigo não existe mais: o SMS passa a chegar no mesmo webhook das ligações
(`https://ops.urace.us/ops/api/dialpad/webhook?key=…`). Este script só lê `~/.urace/dialpad.env`,
fala com a API do Dialpad e **nunca imprime chave**: a `key=` da URL e o segredo aparecem mascarados.

Uso, no VPS:
    python3 adminai/deploy/dialpad_sms.py              ver: webhooks e assinaturas de SMS (só leitura)
    python3 adminai/deploy/dialpad_sms.py --criar      cria a assinatura de SMS (as duas direções) no nosso webhook;
                                                      se ela já existe, não faz nada
    python3 adminai/deploy/dialpad_sms.py --apagar ID  apaga a assinatura de SMS com esse id (voltar atrás)

Se a API responder 404/400, o caminho mudou: cole a resposta para ajustar
(referência: developers.dialpad.com, "SMS Event Subscription").
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

API = "https://dialpad.com/api/v2"
ENV = os.path.expanduser(os.environ.get("DIALPAD_ENV", "~/.urace/dialpad.env"))
NOSSO = "ops.urace.us/ops/api/dialpad/webhook"


def carregar_env():
    valores = {}
    try:
        with open(ENV, encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if linha and not linha.startswith("#") and "=" in linha:
                    k, v = linha.split("=", 1)
                    valores[k.strip()] = v.strip().strip("'\"")
    except OSError:
        sys.exit(f"FALHA: não achei {ENV}")
    if not valores.get("DIALPAD_API_KEY"):
        sys.exit(f"FALHA: DIALPAD_API_KEY não está em {ENV}")
    return valores


def mascarar(texto):
    """Tira chave e segredo de qualquer coisa que vá para a tela."""
    texto = re.sub(r"(key=)[^&\s\"']+", r"\1***", str(texto))
    return re.sub(r'("secret"\s*:\s*")[^"]*', r"\1***", texto)


def chamar(chave, metodo, caminho, corpo=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(API + caminho, data=dados, method=metodo,
                                 headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            bruto = r.read().decode("utf-8", "replace")
            return json.loads(bruto) if bruto.strip() else {}
    except urllib.error.HTTPError as e:
        sys.exit(f"FALHA: Dialpad respondeu {e.code} em {metodo} {caminho}: {mascarar(e.read().decode('utf-8', 'replace')[:400])}")
    except OSError as e:
        sys.exit(f"FALHA: Dialpad fora de alcance ({type(e).__name__})")


def itens(r):
    return r.get("items", r if isinstance(r, list) else []) if isinstance(r, (dict, list)) else []


def nosso_webhook(chave):
    for w in itens(chamar(chave, "GET", "/webhooks")):
        if NOSSO in str(w.get("hook_url", "")):
            return w
    return None


def ver(chave):
    print("Webhooks:")
    for w in itens(chamar(chave, "GET", "/webhooks")):
        print(f"  id={w.get('id')}  {mascarar(w.get('hook_url'))}" + ("   <- o do painel" if NOSSO in str(w.get('hook_url', '')) else ""))
    print("Assinaturas de SMS:")
    subs = itens(chamar(chave, "GET", "/subscriptions/sms"))
    for s in subs:
        wh = s.get("webhook") or {}
        print(f"  id={s.get('id')}  direção={s.get('direction')}  ligada={s.get('enabled')}  "
              f"webhook={wh.get('id') or s.get('webhook_id')}")
    if not subs:
        print("  nenhuma")


def criar(chave):
    w = nosso_webhook(chave)
    if not w:
        sys.exit("FALHA: não achei o webhook do painel no Dialpad. Ele é criado pelo passo 3 de "
                 "docs/adminai/dialpad-conexao.md (o mesmo das ligações).")
    for s in itens(chamar(chave, "GET", "/subscriptions/sms")):
        wid = (s.get("webhook") or {}).get("id") or s.get("webhook_id")
        if str(wid) == str(w.get("id")):
            print(f"OK: a assinatura de SMS já existe (id={s.get('id')}, direção={s.get('direction')}). Nada a fazer.")
            return
    r = chamar(chave, "POST", "/subscriptions/sms", {"webhook_id": w["id"], "direction": "all", "enabled": True})
    print(f"OK: assinatura de SMS criada (id={r.get('id')}, direção={r.get('direction')}) no webhook {w['id']}.")
    print("Agora mande um SMS de teste para o número da empresa e confira: "
          "sudo journalctl -u urace-command-center -n 30 --no-pager | grep -i sms")


def apagar(chave, sid):
    chamar(chave, "DELETE", f"/subscriptions/sms/{sid}")
    print(f"OK: assinatura de SMS {sid} apagada.")


if __name__ == "__main__":
    chave = carregar_env()["DIALPAD_API_KEY"]
    if "--criar" in sys.argv:
        criar(chave)
    elif "--apagar" in sys.argv:
        i = sys.argv.index("--apagar")
        if i + 1 >= len(sys.argv):
            sys.exit("uso: --apagar ID")
        apagar(chave, sys.argv[i + 1])
    else:
        ver(chave)
