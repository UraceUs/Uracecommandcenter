#!/usr/bin/env bash
# WhatsApp dos grupos do ateliê (#383): liga o OpenClaw SÓ como transporte dos grupos da lista.
#
# Idempotente. Lê ~/.urace/whatsapp-grupos.env (sem o arquivo, não faz nada) e:
#   1. cria o segredo WA_GRUPOS_TOKEN se faltar (nunca mostra)
#   2. confere que o canal WhatsApp do OpenClaw está logado (o login por QR é do dono, à parte)
#   3. acha o JID de cada grupo pelo NOME (openclaw directory groups list) e grava no env
#   4. com WA_GRUPOS_APLICAR=1: instala o plugin urace-atelie e aplica a allowlist
#        dmPolicy "disabled" · groupPolicy "allowlist" + groupAllowFrom ["*"] · groups só com os JIDs da lista,
#        requireMention false · pluginHooks.messageReceived true · reactionLevel "off" · sendReadReceipts false
#      sem ela (0, o padrão): mostra o que faria e não muda nada no OpenClaw
#   5. prova: channels status --probe e o que ficou na config
#
# Uso (na VPS):  bash adminai/deploy/whatsapp_grupos/configurar_whatsapp_grupos.sh
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
URACE_DIR="${URACE_DIR:-$HOME/.urace}"
ENVF="${CC_WA_GRUPOS_ENV:-$URACE_DIR/whatsapp-grupos.env}"
AJUDA="$REPO/adminai/deploy/whatsapp_grupos/grupos.py"
PLUGIN="$REPO/adminai/openclaw/urace-atelie"
OC="${OPENCLAW_BIN:-openclaw}"
PY="$(command -v python3)"

echo "== WhatsApp dos grupos do ateliê (#383) =="
if [ ! -f "$ENVF" ]; then
    echo "-- sem $ENVF: nada a fazer (copie o .example de adminai/deploy/whatsapp_grupos/ para começar)"
    exit 0
fi
chmod 600 "$ENVF"
_v() { "$PY" - "$ENVF" "$1" <<'PY'
import sys
k = sys.argv[2]
for l in open(sys.argv[1], encoding="utf-8"):
    l = l.strip()
    if l.startswith(k + "="):
        v = l.split("=", 1)[1].strip()
        print(v[1:-1] if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'" else v)
        break
PY
}
APLICAR="$(_v WA_GRUPOS_APLICAR)"
CONTA="$(_v WA_GRUPOS_CONTA)"
ACC=(); [ -n "$CONTA" ] && ACC=(--account "$CONTA")

# 1. segredo
"$PY" "$AJUDA" token "$ENVF"

# 2. OpenClaw e o login
if ! command -v "$OC" >/dev/null 2>&1; then
    echo "!! openclaw não está no PATH: instale ou ponha OPENCLAW_BIN no adminai.env"; exit 1
fi
LIMPA() { sed -e 's/\x1b\[[0-9;]*[a-zA-Z]//g' -e 's/\r/\n/g'; }
STATUS="$("$OC" channels status --channel whatsapp --probe 2>&1 | LIMPA | tail -n 15)"
echo "-- canal WhatsApp:"; echo "$STATUS" | sed 's/^/   /'
if echo "$STATUS" | grep -qiE 'not linked|qr required|não vinculad|no whatsapp'; then
    echo "!! o WhatsApp ainda não está logado. O dono faz o login por QR:"
    echo "     openclaw channels login --channel whatsapp ${CONTA:+--account $CONTA}"
    echo "   e roda este script de novo."
    exit 0
fi

# 3. JIDs pelo nome
LISTA="$(mktemp)"; trap 'rm -f "$LISTA"' EXIT
if "$OC" directory groups list --channel whatsapp "${ACC[@]}" --json > "$LISTA" 2>/dev/null; then
    "$PY" "$AJUDA" resolver "$ENVF" "$LISTA" | sed 's/^/-- /'
else
    echo "!! não deu para listar os grupos (o gateway está de pé? openclaw gateway status)"
fi
FALTAM="$("$PY" "$AJUDA" faltam "$ENVF")"
[ -n "$FALTAM" ] && echo "-- ainda sem JID: $FALTAM (só esses ficam de fora)"
GRUPOS="$("$PY" "$AJUDA" groups "$ENVF")"
if [ "$GRUPOS" = "{}" ]; then
    echo "!! nenhum grupo da lista achado: confira os nomes no env e se o número está nos grupos"; exit 0
fi

# 4. aplicar
CFG=(
  "channels.whatsapp.dmPolicy|\"disabled\""
  "channels.whatsapp.groupPolicy|\"allowlist\""
  "channels.whatsapp.groupAllowFrom|[\"*\"]"
  "channels.whatsapp.groups|$GRUPOS"
  "channels.whatsapp.pluginHooks|{\"messageReceived\":true}"
  "channels.whatsapp.reactionLevel|\"off\""
  "channels.whatsapp.sendReadReceipts|false"
  "plugins.entries.urace-atelie.enabled|true"
)
if [ "$APLICAR" != "1" ]; then
    echo "-- SIMULAÇÃO (WA_GRUPOS_APLICAR=0): nada mudou no OpenClaw. Com 1, este script faria:"
    echo "     $OC plugins install --link $PLUGIN --force && $OC plugins enable urace-atelie"
    for kv in "${CFG[@]}"; do echo "     $OC config set ${kv%%|*} '${kv#*|}' --strict-json"; done
    echo "   Os grupos: $(echo "$GRUPOS" | "$PY" -c 'import json,sys; print(len(json.load(sys.stdin)))') na allowlist."
    exit 0
fi
echo "-- aplicando no OpenClaw"
"$OC" plugins install --link "$PLUGIN" --force >/dev/null 2>&1 || "$OC" plugins install --link "$PLUGIN" --force
"$OC" plugins enable urace-atelie >/dev/null 2>&1 || true
for kv in "${CFG[@]}"; do
    "$OC" config set "${kv%%|*}" "${kv#*|}" --strict-json >/dev/null || { echo "!! config set ${kv%%|*} falhou"; exit 1; }
done
"$OC" config validate >/dev/null 2>&1 || { echo "!! openclaw config validate reclamou: rode-o para ver"; exit 1; }
# o plugin novo só carrega com o gateway reiniciado (a config o hot-reload já aplica)
"$OC" gateway restart >/dev/null 2>&1 || echo "!! não reiniciei o gateway: rode  openclaw gateway restart"
sleep 5

# 5. prova
echo; echo "================= PROVA ================="
echo "   dmPolicy      -> $("$OC" config get channels.whatsapp.dmPolicy 2>/dev/null | LIMPA)  (tem que ser disabled)"
echo "   groupPolicy   -> $("$OC" config get channels.whatsapp.groupPolicy 2>/dev/null | LIMPA)  (allowlist)"
echo "   grupos        -> $("$OC" config get channels.whatsapp.groups --json 2>/dev/null | "$PY" -c 'import json,sys
try: print(len(json.load(sys.stdin)))
except Exception: print("?")')  (só os da lista)"
echo "   plugin        -> $("$OC" plugins inspect urace-atelie --runtime --json 2>/dev/null | grep -c '"urace-atelie"')  (1 = carregado)"
"$OC" channels status --channel whatsapp --probe 2>&1 | LIMPA | tail -n 5 | sed 's/^/   /'
echo "✅ grupos do ateliê ligados. Mande uma mensagem de teste num dos grupos e veja em Suits › WhatsApp."
