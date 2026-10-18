"""Pacote de prova da waiver nativa, para o advogado e o tribunal (#115, lacunas G-1 e G-2).

Para autenticar a waiver num tribunal são precisos uma explicação **específica** de como a assinatura foi parar no
documento (*Ruiz v. Moss Bros.*) e a certificação de uma "qualified person" (FRE 902(11)/(13); Fla. Stat. §90.902(11)).
Este módulo junta, num ZIP só, tudo o que o sistema guardou da waiver `wid`, assinada aqui:

| Arquivo | O que é |
|---|---|
| `signed.pdf` | o PDF assinado e selado, byte a byte (o hash é o `doc_sha256`) |
| `audit.json` | a trilha gravada na linha da waiver, exatamente como está no banco |
| `waiver.json` | a linha da waiver (sem a trilha) e a anulação, se houver |
| `events.json` e `events.csv` | os eventos da T8 (#111), com o hash de cada um refeito e a cadeia inteira conferida |
| `audit_logs.json` | as linhas do `audit_logs` da waiver e da conta (ou do convite), sem segredo |
| `template.pdf` e `template.json` | a versão do modelo que valia (#116) |
| `timestamp.tst`, `timestamp.json` | o carimbo de tempo RFC 3161 (#110), como está em `waiver_timestamps` |
| `seal-cert.pem`, `seal-root.pem`, `tsa/tsa-root.pem` | o certificado do selo, a raiz da URACE e a raiz da TSA (públicos) |
| `certificate-of-completion.pdf` | o certificado avulso, com todos os eventos, inclusive os de depois de assinar |
| `system-description.md` | `docs/waiver-esign-system.md`, com o commit em execução |
| `declaration-DRAFT.md` | a declaração FRE 902(11)/(13) e §90.902(11) preenchida, **rascunho para o advogado** |
| `VERIFY.md`, `verify_events.py` e `SHA256SUMS` | o passo a passo, o conferidor dos eventos e o hash de cada arquivo |

- **Nunca** vai a chave do selo, cookie, token, senha, link do convite, corpo de e-mail ou caminho de pasta do servidor
  (`_limpo`).
- **A âncora da trilha** (revisão do #115): o hash de cada evento se refaz com o próprio conteúdo; quem mexe numa linha
  e refaz o hash dela passaria. Por isso os eventos de antes e o `signed` são comparados com o gravado na assinatura
  (`audit.json`) e os de depois com o registro de cada um (`_conferir`). O que não bate vai, com destaque, para o
  `events.json`, o certificado avulso, o VERIFY.md e a declaração.
- **Determinístico**: datas fixas no ZIP, ordem fixa, certificado com `invariant` do reportlab e nenhuma hora "de
  agora" dentro dos arquivos. O mesmo registro e a mesma versão do sistema (commit) dão os mesmos bytes; outro commit
  muda a descrição do sistema e a declaração (e o hash do ZIP), não os registros. Por isso o pacote **não lista as exportações
  anteriores** (`evidence_exported` e `waiver.evidence_export`): elas ficam no sistema, com o hash do ZIP de cada uma,
  e exportar de novo o mesmo registro dá o mesmo hash.
- Cada exportação grava o evento `evidence_exported` (trilha, #111) e a auditoria `waiver.evidence_export`, com o
  hash do ZIP (`exportar`).
"""
import csv
import hashlib
import io
import json
import os
import re
import zipfile
from datetime import datetime, timezone

from command_center.db import todos, um

# dono, 06/10 (#115): o custodiante dos registros
CUSTODIANTE = "Italo Jorge da Silveira"
EMPRESA = "URACE.US INC"
DATA_FIXA = (1980, 1, 1, 0, 0, 0)               # a data de todo arquivo no ZIP: o mesmo registro, os mesmos bytes
NIVEL_ZIP = 9
DOC_SISTEMA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                           "docs", "waiver-esign-system.md")
NAO_LISTA = ("evidence_exported",)              # a exportação não entra no pacote (determinístico)

# O que da conta entra no audit_logs.json: o que mostra quem é a pessoa e como ela chegou a assinar. O cadastro e a
# confirmação do e-mail entram sempre (até a assinatura); o resto, só na janela desta assinatura (`_janela_da_conta`).
SEMPRE_DA_CONTA = ("portal.signup", "portal.email.verified")
JANELA_HORAS = 24
EVENTOS_DA_CONTA = ("portal.login", "portal.code.sent", "portal.password",
                    "portal.password.reset.sent", "portal.password.reset", "portal.account.update",
                    "portal.waiver.document_view", "waiver.seal_failed")
EVENTOS_DO_PILOTO = ("portal.driver.create", "portal.driver.update", "portal.driver.birth_date_locked")

# Nada disto sai do sistema dentro do pacote, em nenhum arquivo (revisão do #115: o ZIP vai para fora).
CHAVES_PROIBIDAS = {"token", "token_hash", "cookie", "cookies", "password", "senha", "pw_hash", "pw_salt", "secret",
                    "csrf", "session", "session_id", "link", "invite_link", "url_do_convite", "body", "html", "text",
                    "code", "sign_code", "code_hash", "authorization"}
_LINK_CONVITE = re.compile(r"\S*/portal/invite/[A-Za-z0-9_.~-]+\S*")
# revisão do #115: o motivo de `waiver.seal_failed` diz em que pasta do servidor faltou o selo; o caminho não sai
_CAMINHO = re.compile(r"(?<![\w/:.])(?:~|/(?:home|root|var|opt|tmp|srv|etc|usr|mnt|private|Users))(?:/[^\s,;:()'\"]*)?")


# O conferidor dos eventos que vai no pacote (`verify_events.py`) e no VERIFY.md: só a biblioteca padrão do Python.
# Revisão do #115: além do hash de cada evento, o elo entre ids seguidos, os eventos de antes e o `signed` contra o que
# foi gravado na assinatura (audit.json) e a anulação contra o registro dela (waiver.json).
SCRIPT_EVENTOS = """import hashlib, json, sys
pkg = json.load(open('events.json', encoding='utf-8'))
sealed = json.load(open('audit.json', encoding='utf-8'))
record = json.load(open('waiver.json', encoding='utf-8'))
fields = pkg['chain']['fields']
by_id = {e['id']: e for e in pkg['events']}
problems, prev = [], None
for e in pkg['events']:
    canon = json.dumps({k: e[k] for k in fields}, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    if hashlib.sha256(f"{e['prev_hash'] or ''}|{canon}".encode('utf-8')).hexdigest() != e['hash']:
        problems.append(f"event #{e['id']} ({e['event']}): its hash does not match its content")
    if prev is not None and e['id'] == prev['id'] + 1 and e['prev_hash'] != prev['hash']:
        problems.append(f"chain broken between #{prev['id']} and #{e['id']}")
    prev = e
groups = sealed.get('events') or []
covered = [i for g in groups for i in (g.get('ids') or [g.get('id')])]
for g in groups:
    ids = g.get('ids') or [g.get('id')]
    for i in ids:
        e = by_id.get(i)
        if e is None:
            problems.append(f"event #{i}, recorded at signing, is missing")
        elif (e['event'], e['source'], e['ip'], e['user_agent']) != (g['event'], g['source'], g['ip'], g['user_agent']):
            problems.append(f"event #{i} ({e['event']}) differs from the record made at signing (audit.json)")
    last = by_id.get(ids[-1])
    if last is not None and last['hash'] != g['hash']:
        problems.append(f"event #{ids[-1]} ({last['event']}): hash differs from the record made at signing (audit.json)")
if covered and sealed.get('events_chain_hash') and (by_id.get(covered[-1]) or {}).get('hash') != sealed['events_chain_hash']:
    problems.append('the last event before signing does not match events_chain_hash in audit.json')
for e in pkg['events']:
    d = json.loads(e['detail']) if e['detail'] else {}
    if e['event'] == 'signed' and (d.get('document_sha256') != sealed.get('document_sha256')
                                   or (groups and list(d.get('covers') or []) != covered)):
        problems.append(f"event #{e['id']} (signed) differs from the record made at signing (audit.json)")
    if e['event'] == 'voided' and (record.get('voided') or {}).get('reason') != d.get('reason'):
        problems.append(f"event #{e['id']} (voided) differs from the void record in waiver.json")
for p in problems:
    print('PROBLEM:', p)
print('ALL EVENTS CHECK OUT' if not problems else f'{len(problems)} PROBLEM(S) FOUND')
sys.exit(1 if problems else 0)
"""


# As mensagens dos 409 (a tela mostra com tr(): estão no en.json, test_waiver_prova.py trava)
SO_NATIVA = ("Só a waiver assinada no próprio sistema tem pacote de prova. A do DocuSign se prova pelo certificado do "
             "DocuSign.")
SEM_PDF = "O PDF desta waiver não está no servidor: o pacote não sai sem ele."
PDF_MUDOU = ("O PDF desta waiver no servidor não bate com o hash gravado na assinatura: o pacote não sai. Restaure o "
             "arquivo do backup (Biblioteca) e tente de novo.")
MENSAGENS = (SO_NATIVA, SEM_PDF, PDF_MUDOU)


class NaoExporta(Exception):
    """Não é waiver assinada aqui (a do DocuSign se prova pelo certificado do DocuSign): a rota devolve 409."""


class SemArquivo(Exception):
    """O PDF assinado sumiu do servidor ou não bate mais com o hash gravado: a rota devolve 409 e nada sai."""


# ------------------------------------------------------------------ ajudas
def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _json(dados):
    return (json.dumps(dados, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _limpo(v):
    """O valor sem segredo: tira as chaves proibidas e o link do convite (em qualquer texto)."""
    if isinstance(v, dict):
        return {k: _limpo(x) for k, x in v.items() if str(k).lower() not in CHAVES_PROIBIDAS}
    if isinstance(v, list):
        return [_limpo(x) for x in v]
    if isinstance(v, str):
        return _CAMINHO.sub("[server path]", _LINK_CONVITE.sub("[invitation link removed]", v))
    return v


def _detalhe(texto):
    if not texto:
        return None
    try:
        return json.loads(texto)
    except (TypeError, ValueError):
        return texto


def _horas(iso):
    """(UTC, Flórida) de uma hora ISO do banco."""
    from command_center.providers import portal
    if not iso:
        return None, None
    t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), t.astimezone(portal.FUSO).strftime("%Y-%m-%d %H:%M:%S %Z")


def _commit():
    from command_center.api import sistema
    v = sistema.versao()
    return {"commit": v.get("commit"), "commit_date": v.get("quando")}


# ------------------------------------------------------------------ o que vai no pacote
def _waiver(con, wid):
    w = um(con, "SELECT * FROM waivers WHERE id=?", (wid,))
    if not w:
        raise LookupError("waiver")
    if w.get("source") != "urace" or w.get("status") != "completed":
        raise NaoExporta(SO_NATIVA)
    return w


def _pdf_assinado(w):
    try:
        with open(w["pdf_path"], "rb") as f:
            pdf = f.read()
    except (OSError, TypeError):
        raise SemArquivo(SEM_PDF)
    if _sha(pdf) != w["doc_sha256"]:
        raise SemArquivo(PDF_MUDOU)
    return pdf


def _eventos(con, wid):
    """Os eventos da T8 desta waiver, crus (as colunas que o hash cobre): os de antes que o `signed` cobre, o próprio
    `signed` e os de depois, menos as exportações do pacote."""
    from command_center.providers import trilha_waiver as tw
    s = um(con, "SELECT * FROM waiver_events WHERE waiver_id=? AND event='signed' ORDER BY id LIMIT 1", (wid,))
    antes = []
    if s:
        ids = (json.loads(s["detail"] or "{}").get("covers") or [])
        if ids:
            antes = todos(con, f"SELECT * FROM waiver_events WHERE id IN ({','.join('?' * len(ids))}) ORDER BY id", tuple(ids))
    marcas = ",".join("?" * len(NAO_LISTA))
    depois = todos(con, f"SELECT * FROM waiver_events WHERE waiver_id=? AND event<>'signed' AND event NOT IN ({marcas}) ORDER BY id",
                   (wid, *NAO_LISTA))
    saida = []
    for fase, lista in (("before", antes), ("signed", [s] if s else []), ("after", depois)):
        for e in lista:
            utc, local = _horas(e["at"])
            saida.append({**{k: e[k] for k in ("id", *tw._CAMPOS, "prev_hash", "hash")}, "phase": fase,
                          "label": tw.EVENTOS.get(e["event"], e["event"]), "at_utc": utc, "at_florida": local,
                          "hash_recomputes": tw._hash(e["prev_hash"], e) == e["hash"]})
    return saida


def _do_audit(con, wid, evento):
    return [(r, _detalhe(r["detail"]) or {}) for r in
            todos(con, "SELECT * FROM audit_logs WHERE entity_type='waiver' AND entity_id=? AND event=? ORDER BY id",
                  (str(wid), evento))]


def _conferir(con, w, trilha, eventos, anulacao):
    """Revisão do #115: o hash de cada evento se refaz com o próprio conteúdo, então quem mexe numa linha e refaz o hash
    dela passa nessa conta. A âncora é o que foi gravado na hora da assinatura (`audit.json`, na linha imutável da waiver
    e na página selada do PDF): os eventos de antes e o `signed` são comparados com ela; os de depois, com o registro
    próprio de cada um (`waiver_voids`, a auditoria do balcão e da cópia). Marca cada evento e devolve os problemas."""
    problemas = []
    grupos = trilha.get("events") or []
    do_grupo = {i: g for g in grupos for i in (g.get("ids") or [g.get("id")])}
    cobertos = [i for g in grupos for i in (g.get("ids") or [g.get("id")])]
    por_id = {e["id"]: e for e in eventos}
    ant = None
    for e in eventos:
        if not e["hash_recomputes"]:
            problemas.append(f"event #{e['id']} ({e['event']}): its hash does not match its content")
        if ant is not None and e["id"] == ant["id"] + 1 and e["prev_hash"] != ant["hash"]:
            problemas.append(f"chain broken between #{ant['id']} and #{e['id']}: event #{ant['id']} was changed after it "
                             "was recorded")
        ant = e
        e["matches_sealed_record"] = None
        e["matches_independent_record"] = None
        if e["phase"] == "before" and grupos:
            g = do_grupo.get(e["id"])
            ok = bool(g) and (e["event"], e["source"], e["ip"], e["user_agent"]) == \
                (g.get("event"), g.get("source"), g.get("ip"), g.get("user_agent"))
            ids = (g.get("ids") or [g.get("id")]) if g else []
            if ok and ids and e["id"] == ids[0]:
                ok = e["at_utc"] == g.get("at_utc")
            if ok and ids and e["id"] == ids[-1]:
                ok = e["hash"] == g.get("hash") and (e["at_utc"] == g.get("last_at_utc", g.get("at_utc")))
            if ok and cobertos and e["id"] == cobertos[-1] and trilha.get("events_chain_hash"):
                ok = e["hash"] == trilha["events_chain_hash"]
            e["matches_sealed_record"] = ok
            if not ok:
                problemas.append(f"event #{e['id']} ({e['event']}) differs from the record made at signing (audit.json)")
        elif e["phase"] == "signed":
            d = _detalhe(e["detail"]) or {}
            ok = (d.get("document_sha256") == w["doc_sha256"] == trilha.get("document_sha256")
                  and d.get("template_sha256") == trilha.get("template_sha256")
                  and e["signature_id"] == trilha.get("signature_id")
                  and (not grupos or list(d.get("covers") or []) == cobertos))
            e["matches_sealed_record"] = ok
            if not ok:
                problemas.append(f"event #{e['id']} (signed) differs from the record made at signing (audit.json)")
        elif e["event"] == "voided":
            d = _detalhe(e["detail"]) or {}
            ok = bool(anulacao) and d.get("reason") == anulacao["reason"] and d.get("by") == anulacao["by_name"]
            e["matches_independent_record"] = ok
            if not ok:
                problemas.append(f"event #{e['id']} (voided) differs from the void record (waiver_voids, in waiver.json)")
        elif e["event"] in ("id_checked", "id_check_failed"):
            d = _detalhe(e["detail"]) or {}
            a = next((x for _r, x in _do_audit(con, w["id"], "waiver.id_check") if x.get("event_id") == e["id"]), None)
            ok = a is not None and all(a.get(k) == d.get(k) for k in ("document_type", "name_matches", "minor_age_matches"))
            e["matches_independent_record"] = ok
            if not ok:
                problemas.append(f"event #{e['id']} ({e['event']}) differs from its audit-log row (waiver.id_check)")
        elif e["event"] == "copy_emailed":
            d = _detalhe(e["detail"]) or {}
            ok = any(x.get("message_id") == d.get("message_id") for _r, x in _do_audit(con, w["id"], "waiver.copy.emailed"))
            e["matches_independent_record"] = ok
            if not ok:
                problemas.append(f"event #{e['id']} (copy_emailed) differs from its audit-log row (waiver.copy.emailed)")
    for i in cobertos:
        if i not in por_id:
            problemas.append(f"event #{i}, recorded at signing (audit.json), is missing from the event trail")
    return problemas


def _cadeia_toda(con):
    """A tabela inteira de eventos, elo por elo: o primeiro problema, dito com os dois ids (revisão do #115: o evento
    mexido e com o hash refeito aparece como o elo quebrado entre ele e o seguinte)."""
    from command_center.providers import trilha_waiver as tw
    anterior, ant_id = None, None
    for r in con.execute(f"SELECT id, prev_hash, hash, {', '.join(tw._CAMPOS)} FROM waiver_events ORDER BY id"):
        r = dict(r)
        if tw._hash(r["prev_hash"], r) != r["hash"]:
            return {"ok": False, "first_broken_event_id": r["id"], "previous_event_id": ant_id,
                    "problem": f"event #{r['id']} does not match its own hash: it was changed after it was recorded"}
        if r["prev_hash"] != anterior:
            return {"ok": False, "first_broken_event_id": r["id"], "previous_event_id": ant_id,
                    "problem": f"chain broken between #{ant_id} and #{r['id']}: event #{ant_id} was changed after it was "
                               "recorded, or events between them were removed"}
        anterior, ant_id = r["hash"], r["id"]
    return {"ok": True, "first_broken_event_id": None, "previous_event_id": None, "problem": None}


def _cadeia(con, eventos, problemas):
    from command_center.providers import trilha_waiver as tw
    v = _cadeia_toda(con)
    if not v["ok"] and v["problem"] not in problemas:
        problemas.append(f"whole event table: {v['problem']}")
    return {"algorithm": "hash = SHA-256( prev_hash + '|' + canonical JSON of the event fields ); canonical JSON = "
                         "json.dumps({field: value for the fields listed}, sort_keys=True, separators=(',', ':'), "
                         "ensure_ascii=False); prev_hash is empty for the first event of the whole table",
            "fields": list(tw._CAMPOS), "events_in_package": len(eventos),
            "all_event_hashes_recompute": all(e["hash_recomputes"] for e in eventos),
            "whole_event_table_chain_intact_when_exported": v["ok"],
            "first_broken_event_id": v["first_broken_event_id"], "previous_event_id": v["previous_event_id"],
            "whole_table_problem": v["problem"],
            "note": "A hash that recomputes only shows the event matches itself. The anchors are the record made at signing "
                    "(audit.json: the events before the signature, their hashes and events_chain_hash, also printed on the "
                    "sealed PDF) and, for the events after signing, their own records (waiver.json, audit_logs.json). Each "
                    "event's prev_hash is the hash of the event recorded just before it in URACE's whole event table (which "
                    "also holds other people's waivers, not included here); the whole table was re-verified, link by link, "
                    "when this package was exported."}


def _csv(eventos):
    buf = io.StringIO()
    cols = ("id", "phase", "event", "label", "at_utc", "at_florida", "flow", "source", "ip", "user_agent", "account_id",
            "invite_id", "pilot_id", "client_id", "kind", "template_version_id", "waiver_id", "signature_id", "detail",
            "prev_hash", "hash", "hash_recomputes", "matches_sealed_record", "matches_independent_record")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    for e in eventos:
        w.writerow(["" if e.get(c) is None else e.get(c) for c in cols])
    return buf.getvalue().encode("utf-8")


def _auditoria(con, w, trilha):
    """As linhas do `audit_logs` que contam esta waiver: as da própria waiver; da conta, o que veio até assinar
    (cadastro, login, e-mail confirmado, código, entrega do PDF) mais a assinatura desta waiver e o nascimento do
    piloto; ou, pelo convite, as do convite. Sem a exportação do pacote e sem segredo."""
    wid, linhas = w["id"], []
    linhas += todos(con, """SELECT * FROM audit_logs WHERE entity_type='waiver' AND entity_id=?
                            AND event<>'waiver.evidence_export'""", (str(wid),))
    conta = trilha.get("account_id")
    if conta:
        m0, m1, m2 = (",".join("?" * len(x)) for x in (SEMPRE_DA_CONTA, EVENTOS_DA_CONTA, EVENTOS_DO_PILOTO))
        desde = _janela_da_conta(con, w, trilha)
        linhas += todos(con, f"""SELECT * FROM audit_logs WHERE entity_type='portal_account' AND entity_id=? AND (
                                   (event IN ({m0}) AND at <= ?)
                                   OR (event IN ({m1}) AND at > ? AND at <= ?)
                                   OR (event='portal.waiver.sign' AND json_extract(detail, '$.waiver') = ?)
                                   OR (event IN ({m2}) AND json_extract(detail, '$.piloto') = ?))""",
                        (str(conta), *SEMPRE_DA_CONTA, w["completed_at"], *EVENTOS_DA_CONTA, desde, w["completed_at"], wid,
                         *EVENTOS_DO_PILOTO, trilha.get("driver_id")))
    convite = trilha.get("invitation_id")
    if convite:
        linhas += todos(con, """SELECT * FROM audit_logs WHERE (entity_type='waiver_invite' AND entity_id=?)
                                OR (event LIKE 'waiver.invite.%' AND json_extract(detail, '$.invite') = ?)""",
                        (str(convite), convite))
    vistos, saida = set(), []
    for r in sorted(linhas, key=lambda x: x["id"]):
        if r["id"] in vistos:
            continue
        vistos.add(r["id"])
        utc, local = _horas(r["at"])
        saida.append(_limpo({"id": r["id"], "at": r["at"], "at_florida": local, "event": r["event"], "actor": r["actor"],
                             "user_id": r["user_id"], "entity_type": r["entity_type"], "entity_id": r["entity_id"],
                             "ip": r["ip"], "detail": _detalhe(r["detail"])}))
    return saida


def _janela_da_conta(con, w, trilha):
    """Desde quando a parte da conta conta esta assinatura (revisão do #115): o mais tarde entre a assinatura anterior
    da conta (a sessão da waiver do irmão não entra na deste) e 24 h antes do primeiro passo que esta assinatura cobre
    (conta antiga não traz anos de login)."""
    from datetime import timedelta
    ant = um(con, """SELECT MAX(at) AS at FROM audit_logs WHERE entity_type='portal_account' AND entity_id=?
                     AND event='portal.waiver.sign' AND at < ?""", (str(trilha.get("account_id")), w["completed_at"]))["at"]
    grupos = trilha.get("events") or []
    primeiro = min((g.get("at_utc") for g in grupos if g.get("at_utc")), default=None) or w["completed_at"]
    t = datetime.fromisoformat(str(primeiro).replace("Z", "+00:00")) - timedelta(hours=JANELA_HORAS)
    inicio = t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return max(inicio, ant) if ant else inicio


def _modelo(con, w, trilha):
    """(json da versão, PDF da versão ou None). Só o que não muda com o tempo (sem "atual" nem contagem)."""
    from command_center.providers import waiver_nativa as wn
    v = wn.versao_por_hash(con, w["template"], trilha.get("template_sha256"))
    if not v:
        return {"kind": w["template"], "sha256": trilha.get("template_sha256"), "name": trilha.get("template_name"),
                "pages": trilha.get("template_pages"), "version_id": trilha.get("template_version_id"),
                "pdf_included": False, "note": "This template version is not in the version table (signed before #116)."}, None
    pdf = None
    try:
        with open(v["pdf_path"], "rb") as f:
            pdf = f.read()
        if _sha(pdf) != v["sha256"]:
            pdf = None
    except (OSError, TypeError):
        pdf = None
    info = {"version_id": v["id"], "kind": v["kind"], "version_number": v["number"], "sha256": v["sha256"], "name": v["name"],
            "pages": v["pages"], "source": v["source"], "imported_at": v["imported_at"], "imported_by": v["imported_by"],
            "imported_by_name": v["imported_by_name"], "notice_744_check_at_import": v["notice_744"],
            "pdf_included": pdf is not None, "matches_signature": v["sha256"] == trilha.get("template_sha256")}
    if pdf is None:
        info["note"] = "The PDF of this version is missing on the server or does not match its SHA-256."
    return info, pdf


def _pem(der):
    import base64
    b = base64.encodebytes(der).decode("ascii").replace("\n", "")
    return ("-----BEGIN CERTIFICATE-----\n" + "\n".join(b[i:i + 64] for i in range(0, len(b), 64))
            + "\n-----END CERTIFICATE-----\n").encode("ascii")


def _do_selo(pdf, trilha):
    """(cert do selo, raiz da URACE, valor da assinatura) do PDF selado. A raiz é a da pasta do selo quando a impressão
    bate com a gravada na assinatura; senão (selo trocado depois), a cópia que vai dentro do próprio PDF."""
    from asn1crypto import x509 as ax509
    from pyhanko.pdf_utils.reader import PdfFileReader
    from command_center.providers import selo_waiver as sw
    sigs = PdfFileReader(io.BytesIO(pdf)).embedded_signatures
    if len(sigs) != 1:
        return None, None, None
    s = sigs[0]
    selo = s.signer_cert
    raiz_sha = (trilha.get("seal") or {}).get("root_cert_sha256")
    raiz = None
    guardada = sw._raiz_guardada()
    if guardada is not None and sw._sha_der(guardada) == raiz_sha:
        from cryptography.hazmat.primitives import serialization
        raiz = ax509.Certificate.load(guardada.public_bytes(serialization.Encoding.DER))
    if raiz is None:
        raiz = next((c.chosen for c in s.signed_data["certificates"] if c.chosen.sha256.hex() == raiz_sha), None)
    return selo, raiz, s.signer_info["signature"].native


def _raiz_da_tsa(token):
    """A raiz de TSA aceita (`selo_waiver.raizes_tsa`) que fecha a cadeia do certificado da TSA de dentro do token."""
    from asn1crypto import cms
    from command_center.providers import selo_waiver as sw
    tok = cms.ContentInfo.load(token)
    certs = [c.chosen for c in (tok["content"]["certificates"] or [])]
    atual = sw._cert_da_tsa(tok)
    raizes = sw.raizes_tsa()
    for _ in range(8):
        if atual is None:
            return None
        achou = next((r for r in raizes if r.sha256 == atual.sha256 or r.subject == atual.issuer), None)
        if achou is not None:
            return achou
        atual = next((c for c in certs if c.subject == atual.issuer and c.sha256 != atual.sha256), None)
    return None


def _carimbo(con, w, assinatura):
    t = um(con, "SELECT * FROM waiver_timestamps WHERE waiver_id=?", (w["id"],))
    if not t:
        return None, None
    from asn1crypto import cms
    tok = bytes(t["token"])
    tst = cms.ContentInfo.load(tok)["content"]["encap_content_info"]["content"].parsed
    mi = tst["message_imprint"]
    info = {"tsa_url": t["tsa_url"], "gen_time": t["gen_time"], "serial": t["serial"], "policy": t["policy"],
            "token_sha256": t["token_sha256"], "token_sha256_recomputed": _sha(tok), "seal_cert_sha256": t["seal_cert_sha256"],
            "document_sha256": t["document_sha256"], "signature_id": t["signature_id"],
            "message_imprint_algorithm": mi["hash_algorithm"]["algorithm"].native,
            "message_imprint": mi["hashed_message"].native.hex(),
            "seal_signature_value_sha256": _sha(assinatura) if assinatura else None,
            "what_is_time_stamped": "PAdES signature time-stamp: the TSA signed the SHA-256 of the seal's signature value "
                                    "(the CMS SignerInfo signature inside signed.pdf), which in turn covers the whole PDF."}
    return info, tok


# ------------------------------------------------------------------ o certificado avulso
def _certificado(w, trilha, eventos, cadeia, anulacao, carimbo, modelo, problemas):
    """O certificado de conclusão avulso (inglês: vai para o tribunal), com todos os eventos, inclusive os de depois de
    assinar. `invariant=1`: o mesmo registro dá o mesmo PDF (sem data de criação nem id aleatório)."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from command_center.providers.waiver_nativa import MARGEM_PE, _quebra
    buf = io.BytesIO()
    cv = canvas.Canvas(buf, pagesize=letter, invariant=1)
    cv.setTitle(f"Certificate of completion — waiver record {w['id']}")
    cv.setAuthor(EMPRESA)
    _larg, alt = letter
    x, y = 54, alt - 64

    def nova():
        nonlocal y
        cv.showPage()
        y = alt - 64
        cv.setFont("Helvetica-Oblique", 8)
        cv.drawString(x, y + 22, f"Certificate of completion (continued) · Waiver record {w['id']} · Signature ID "
                                 f"{trilha.get('signature_id')}")

    def cabe(h):
        if y - h < MARGEM_PE:
            nova()

    def linha(txt, tam=9, fonte="Helvetica", passo=12):
        nonlocal y
        for pedaco in _quebra(txt, 100 if tam <= 9 else 80 if tam <= 11 else 62) or [""]:
            cabe(passo)
            cv.setFont(fonte, tam)
            cv.drawString(x, y, pedaco)
            y -= passo

    def titulo(txt):
        nonlocal y
        y -= 6
        cabe(16 + 24)
        linha(txt, 11, "Helvetica-Bold", 16)

    linha("Certificate of completion and event history", 15, "Helvetica-Bold", 22)
    linha(f"{EMPRESA} · Orlando, FL · Electronic waiver record {w['id']} · Signature ID {trilha.get('signature_id')}")
    linha("Generated from URACE's records for the evidence package. It is separate from the sealed PDF (signed.pdf), which "
          "cannot change after signing; this certificate also lists what happened after the signature.", 8,
          "Helvetica-Oblique", 11)
    if problemas:                                     # revisão do #115: o que não bate aparece antes de tudo
        titulo("INTEGRITY WARNING: THE RECORDS DO NOT ALL MATCH")
        for p in problemas:
            linha(f"- {p}", 10, "Helvetica-Bold", 14)
        linha("These checks compare the event trail with the record made at signing (audit.json, kept in the waiver's "
              "unchangeable row and summarized on the sealed PDF) and with the independent records of each later event. "
              "See VERIFY.md, step 5.", 8, "Helvetica-Oblique", 11)
    if anulacao:
        s_utc, s_local = _horas(anulacao["at"])
        titulo("STATUS: VOIDED BY URACE")
        linha(f"Voided {s_local} ({s_utc} UTC) by {anulacao['by_name']}. Reason: {anulacao['reason']}", 10, "Helvetica-Bold", 14)
        linha("A voided waiver is kept unchanged in URACE's records; it is no longer in force.", 9)
    titulo("Document")
    linha(f"Template: {trilha.get('template_name')} · {trilha.get('template_pages')} page(s) · "
          f"version {modelo.get('version_number') or '—'} (ID {modelo.get('version_id') or trilha.get('template_version_id') or '—'})")
    linha(f"Template SHA-256: {trilha.get('template_sha256')}")
    linha(f"Signed PDF SHA-256 (signed.pdf): {w['doc_sha256']}")
    titulo("Signature")
    rotulo = "Parent (natural guardian)" if w["template"] == "parental" else "Participant"
    linha(f"{rotulo}: {trilha.get('signer_name')} · {trilha.get('email_label') or 'Account'} email: {trilha.get('account_email')}")
    if w["template"] == "parental":
        linha(f"Minor participant: {trilha.get('driver_name')} · Date of birth: {trilha.get('driver_birth_date')} · "
              f"Relationship: {trilha.get('signer_relationship') or '—'}")
    else:
        linha(f"Participant date of birth: {trilha.get('driver_birth_date')}")
    linha(f"Typed name: {trilha.get('typed_name')} · Signature image SHA-256: {trilha.get('signature_png_sha256')}")
    linha(f"Signed: {trilha.get('signed_at_local')} ({trilha.get('signed_at_utc')} UTC) · Valid until: {trilha.get('valid_until')} "
          f"({trilha.get('valid_until_reason') or 'one year'})")
    linha(f"IP address: {trilha.get('ip') or '—'} · Device: {(trilha.get('user_agent') or '—')[:200]}")
    linha(f"Authentication: {trilha.get('authentication')}")
    if carimbo:
        titulo("Digital seal and time-stamp")
        selo = trilha.get("seal") or {}
        linha(f"Seal: {selo.get('standard') or 'PAdES'} · field {selo.get('field') or '—'} · {selo.get('certification') or '—'} · "
              f"seal certificate SHA-256 {carimbo['seal_cert_sha256']} · URACE root SHA-256 {selo.get('root_cert_sha256') or '—'}")
        linha(f"RFC 3161 time-stamp: {carimbo['tsa_url']} · time {carimbo['gen_time']} · serial {carimbo['serial']} · "
              f"token SHA-256 {carimbo['token_sha256']}")
    titulo("Event history (Florida time, America/New_York, and UTC)")
    fases = {"before": "before signing", "signed": "signature", "after": "after signing"}
    for e in eventos:
        quem = "reported by the signer's browser" if e["source"] == "client" else "recorded by URACE's server"
        topo = f"#{e['id']} · {e['at_florida']} ({e['at_utc']} UTC) · {e['label']} · {fases[e['phase']]} · {quem}"
        aparelho = f"IP {e.get('ip') or '—'} · Device: {(e.get('user_agent') or '—')[:160]}"
        det = _detalhe(e.get("detail"))
        det = {k: v for k, v in det.items() if k not in ("covers", "user_id")} if isinstance(det, dict) else det
        extra = "; ".join(f"{k}: {v}" for k, v in sorted(det.items())) if isinstance(det, dict) else (str(det) if det else "")
        if e["event"] == "signed" and isinstance(_detalhe(e.get("detail")), dict):
            extra = (f"covers events {', '.join('#' + str(i) for i in (_detalhe(e['detail']).get('covers') or []))}; " + extra).strip()
        partes = [(topo, 9, "Helvetica-Bold", 12), (aparelho, 8, "Helvetica", 11)]
        if extra:
            partes.append((f"Details: {extra}", 8, "Helvetica", 11))
        partes.append((f"Event hash: {e['hash']}", 7, "Helvetica-Oblique", 10))
        if e.get("matches_sealed_record") is False:
            partes.append(("DOES NOT MATCH THE RECORD MADE AT SIGNING (audit.json)", 9, "Helvetica-Bold", 12))
        if e.get("matches_independent_record") is False:
            partes.append(("DOES NOT MATCH THIS EVENT'S OWN RECORD (waiver.json / audit_logs.json)", 9, "Helvetica-Bold", 12))
        cabe(sum(p[3] * len(_quebra(p[0], 100)) for p in partes))
        for p in partes:
            linha(*p)
    if not eventos:
        linha("No events: this waiver was signed before the event trail (#111).")
    titulo("Integrity of the event trail")
    linha(f"{cadeia['events_in_package']} event(s) listed; every event hash recomputes from its content: "
          f"{'yes' if cadeia['all_event_hashes_recompute'] else 'NO'}. Whole event table hash chain intact when exported: "
          f"{'yes' if cadeia['whole_event_table_chain_intact_when_exported'] else 'NO: ' + str(cadeia['whole_table_problem'])}. "
          f"Events before signing match the record made at signing, and later events match their own records: "
          f"{'yes' if not problemas else 'NO (see the warning at the top)'}.")
    y -= 6
    linha("Exports of this evidence package are logged by URACE (audit event waiver.evidence_export, with the package "
          "SHA-256) and are not listed here, so the same record, exported by the same version of the system (commit), "
          "always produces the same package. How to check every file: VERIFY.md.", 8, "Helvetica-Oblique", 11)
    cv.showPage()
    cv.save()
    return buf.getvalue()


# ------------------------------------------------------------------ textos
def _descricao(commit):
    try:
        with open(DOC_SISTEMA, encoding="utf-8") as f:
            corpo = f.read()
    except OSError:
        corpo = "(docs/waiver-esign-system.md was not found on the server.)\n"
    return (f"<!-- Generated for the evidence package from docs/waiver-esign-system.md. Running commit: "
            f"{commit.get('commit') or 'unknown'} ({commit.get('commit_date') or 'date unknown'}). -->\n\n"
            f"> **Running code:** commit `{commit.get('commit') or 'unknown'}` of the URACE Command Center "
            f"(committed {commit.get('commit_date') or '—'}). This description is versioned with the code: "
            f"the same commit has the same text.\n\n" + corpo).encode("utf-8")


def _verificar_md(w, trilha, carimbo, tem, problemas):
    raiz = (trilha.get("seal") or {}).get("root_cert_sha256") or "—"
    t = [f"# How to verify this evidence package — waiver record {w['id']}", "",
         f"Signature ID `{trilha.get('signature_id')}` · signed {trilha.get('signed_at_local')} "
         f"({trilha.get('signed_at_utc')} UTC) · {EMPRESA}, Orlando, FL.", ""]
    if problemas:
        t += ["> **INTEGRITY WARNING.** When this package was exported, URACE's system found records that do not match:", ">",
              *[f"> - {p}" for p in problemas], ">",
              "> The details are in `events.json` (`integrity`), at the top of `certificate-of-completion.pdf` and in step 5.", ""]
    else:
        t += ["When this package was exported, URACE's system checked the event trail against the record made at signing "
              "and against each later event's own record: **no problem found**. Every step below repeats a check "
              "independently.", ""]
    t += [
         "Every step below only reads the files. None needs access to URACE's systems, except step 4 (run on URACE's server).", "",
         "## 1. Every file is intact (SHA-256)", "",
         "In the folder where the ZIP was extracted:", "", "```", "sha256sum -c SHA256SUMS", "```", "",
         "Every line must say `OK`. On macOS: `shasum -a 256 -c SHA256SUMS`. On Windows (PowerShell): "
         "`Get-FileHash -Algorithm SHA256 signed.pdf` and compare with the line in `SHA256SUMS`.", "",
         f"The SHA-256 of `signed.pdf` must be `{w['doc_sha256']}`: the same value recorded at the moment of signing "
         "(`doc_sha256` in `waiver.json`, `document_sha256` in `audit.json` and in the `waiver.signed.trail` row of "
         "`audit_logs.json`).", "",
         "## 2. The digital seal and the time-stamp (Adobe or pyHanko)", "",
         "- **Adobe Acrobat Reader**: open `signed.pdf` and the Signatures panel. It shows that the document was not "
         "modified since it was certified and shows the time-stamp. The seal's identity shows as unknown because the "
         "certificate is URACE's own (not on Adobe's list); to trust it, import `seal-root.pem` as a trusted certificate "
         "and compare its SHA-256 fingerprint first (below).",
         f"- **SHA-256 fingerprint of URACE's seal root** (`seal-root.pem`): `{raiz}`. Compare it with the fingerprint "
         "URACE recorded when the seal was created (shown in the Command Center, Site › Waiver › Digital seal) before "
         "trusting it: `openssl x509 -in seal-root.pem -noout -fingerprint -sha256`.",
         "- **pyHanko** (open source): `pip install pyhanko-cli` and then", "", "```",
         "pyhanko sign validate --no-revocation-check --trust-replace --trust seal-root.pem --trust tsa/tsa-root.pem --pretty-print signed.pdf",
         "```", "",
         "  The report must say \"The signer's certificate is trusted\", \"The timestamp token is cryptographically sound\", "
         "\"The TSA certificate is trusted\", \"The signature covers the entire file\" and, at the bottom, \"The signature "
         "is judged VALID\". `--trust-replace` makes pyHanko trust only these two roots, not the computer's list.", "",
         "## 3. The RFC 3161 time-stamp, on its own (OpenSSL)", ""]
    if carimbo and tem.get("tsa/tsa-root.pem"):
        t += ["```", f"openssl ts -verify -in timestamp.tst -token_in -digest {carimbo['message_imprint']} -CAfile tsa/tsa-root.pem",
              "openssl ts -reply -in timestamp.tst -token_in -text", "```", "",
              f"The first command must print `Verification: OK`. The second shows the time ({carimbo['gen_time']}), the "
              f"serial number ({carimbo['serial']}) and the authority. The digest is the SHA-256 of the seal's signature "
              "value inside `signed.pdf` (`seal_signature_value_sha256` in `timestamp.json`): pyHanko (step 2) checks that "
              "link. `timestamp.tst` is byte-for-byte the token stored in URACE's append-only `waiver_timestamps` table "
              f"(SHA-256 `{carimbo['token_sha256']}`).", ""]
    elif carimbo:
        t += ["`timestamp.tst` is the token stored in `waiver_timestamps`. The root of its time-stamping authority is not "
              "among the roots this server accepts, so `tsa/tsa-root.pem` is not included: get the authority's public root "
              "from its website and run `openssl ts -verify -in timestamp.tst -token_in -digest "
              f"{carimbo['message_imprint']} -CAfile <root.pem>`.", ""]
    else:
        t += ["This waiver has no time-stamp token (signed before #110).", ""]
    t += ["## 4. On URACE's server (the same check the system runs)", "", "```",
          "~/.urace/cc-venv/bin/python -m command_center.manage selo-waiver conferir signed.pdf --raiz seal-root.pem", "```", "",
          "It must end with `selo e carimbo conferem: o arquivo não mudou desde a assinatura` (seal and time-stamp check "
          "out: the file has not changed since signing). On a computer whose list of TSA roots does not have this "
          "package's TSA, add `CC_WAIVER_TSA_ROOTS=tsa` before the command (in the extracted folder).", "",
          "## 5. The event trail (hash chain and the record made at signing)", "",
          "`events.json` lists each event with the exact fields its hash covers. A hash that recomputes only shows that "
          "an event matches itself, so the check also uses two anchors: the record made at signing (`audit.json`, kept in "
          "the waiver's unchangeable row, with the hash of each event before the signature and `events_chain_hash`, the "
          "hash of the last one, also printed on the sealed PDF) and, for the void, its own record (`waiver.json`). The "
          "same check is in `verify_events.py` (Python 3, standard library only): `python3 verify_events.py` in the "
          "extracted folder must print `ALL EVENTS CHECK OUT`.", "", "```python", *SCRIPT_EVENTOS.rstrip("\n").split("\n"),
          "```", "",
          "It checks: every hash recomputes; for events with consecutive ids, each `prev_hash` is the previous event's hash "
          "(otherwise it prints `chain broken between #a and #b`); each event before the signature matches `audit.json`; "
          "the `signed` event covers exactly those events and the document's SHA-256; the `voided` event matches the void "
          "record.", "",
          "The `signed` event lists, in `detail.covers`, the ids of the events before the signature that it covers. "
          "`certificate-of-completion.pdf` prints the same events, in Florida time and UTC, including the ones after "
          "signing (copy emailed, ID checked at the track, voided, downloaded).", "",
          "## 6. The template", "",
          "`template.pdf` is the exact template version that was signed: its SHA-256 equals `template_sha256` in "
          "`audit.json`, and the first pages of `signed.pdf` are that template unchanged.", "",
          "## What is not in this package", "",
          "No private key, password, session cookie, token, invitation link, email body or server folder path. Exports of "
          "this package are logged by URACE (`waiver.evidence_export`, with the ZIP's SHA-256) and are left out of the "
          "package, so the same record, exported by the same version of the system (the commit in "
          "`system-description.md`), produces byte-identical files. A new version of the system changes "
          "`system-description.md` and `declaration-DRAFT.md` (and with them the ZIP's SHA-256), not the records.", ""]
    return "\n".join(t).encode("utf-8")


def _declaracao(w, trilha, carimbo, commit, anulacao, nomes, problemas):
    selo = trilha.get("seal") or {}
    t = ["# DRAFT — FOR ATTORNEY REVIEW — NOT TO BE SIGNED", "",
         "> **DRAFT — for attorney review — not to be signed.** This text was filled in automatically by URACE's system "
         "from the record in this package. The final wording depends on URACE's attorney (FRE 902(11) and 902(13); Fla. "
         "Stat. §90.902(11) and §90.803(6)). Items in [brackets] are for the attorney to decide or complete.", "",
         "## Declaration of custodian of records and qualified person", "",
         "### Fed. R. Evid. 803(6), 902(11) and 902(13) · Fla. Stat. §90.803(6) and §90.902(11)", "",
         f"I, **{CUSTODIANTE}**, declare as follows:", "",
         f"1. I am the [title — ATTORNEY: confirm] of **{EMPRESA}** (\"URACE\"), Orlando, Florida, and a custodian of "
         "URACE's records. I am familiar with the manner in which URACE's electronic waiver records are created and "
         "kept, including the system described in `system-description.md`, and I am qualified to make this declaration. "
         "[ATTORNEY: whether a technical declarant should also sign for FRE 902(13).]",
         f"2. Attached is the evidence package for electronic waiver record **{w['id']}** (Signature ID "
         f"`{trilha.get('signature_id')}`): the files listed in `SHA256SUMS`, which are: {', '.join(nomes)}.",
         f"3. The record shows that **{trilha.get('signer_name')}** "
         + (f"signed, as {trilha.get('signer_relationship') or 'parent'} (natural guardian) of the minor participant "
            f"**{trilha.get('driver_name')}**, " if w["template"] == "parental" else "signed, as the participant, ")
         + f"the document \"{trilha.get('template_name')}\" on {trilha.get('signed_at_local')} "
           f"({trilha.get('signed_at_utc')} UTC), from IP address {trilha.get('ip') or '—'}.",
         "4. **Business records.** These records were made at or near the time of the acts and events they record, by — or "
         "from information transmitted by — a person with knowledge of those matters or by URACE's system as each event "
         "occurred; they were kept in the course of URACE's regularly conducted business activity; and making and keeping "
         "them is a regular practice of that activity.",
         "5. **Electronic process.** The records were generated by an electronic process or system that produces an "
         f"accurate result, described in `system-description.md` (running code: commit `{commit.get('commit') or 'unknown'}`). "
         "In summary: the signer authenticated with "
         + ("a personal one-time invitation link that URACE emailed to the address on the client's file"
            if trilha.get("invitation_id") else "a URACE client account (email and password, with the email confirmed by code)")
         + ", was shown the whole document, confirmed "
         "two consents, reviewed a summary, received a one-time code by email and signed; each step was logged with the "
         "time, IP address and device in an append-only, hash-chained event table.",
         f"6. **Integrity.** The SHA-256 of `signed.pdf` is `{w['doc_sha256']}`, the value recorded at the moment of "
         "signing. The file carries URACE's digital seal (PAdES, certification with no changes allowed)"
         + (f" and an RFC 3161 time-stamp from {carimbo['tsa_url']} dated {carimbo['gen_time']} (serial {carimbo['serial']})"
            if carimbo else "") + ". Changing any byte of the file breaks the seal. "
         f"The SHA-256 fingerprint of URACE's seal root is `{selo.get('root_cert_sha256') or '—'}`.",
         "7. The files in this package are true and accurate copies of URACE's records, exported from URACE's system on "
         "[date of export] by [name of the person who exported]. URACE's database refuses (by database triggers) any "
         "change to the signed waiver's content — signer, dates, document hash, trail and file — and refuses to delete it; "
         "only two administrative fields of the record can change: its link to a client card (each change is recorded in "
         "the audit log) and a flag that hides it from lists (the system refuses to hide a signed waiver). The event "
         "trail, the time-stamp token, the template versions, the void record and the audit log accept new rows only.",
         ]
    if problemas:
        t.append("[ATTORNEY: when this package was exported, URACE's system found records that do not match: "
                 + "; ".join(problemas) + ". Do not use item 6 or 7 as written before this is explained.]")
    if anulacao:
        t.append(f"8. The record shows that URACE voided this waiver on {_horas(anulacao['at'])[1]} "
                 f"(by {anulacao['by_name']}; reason: \"{anulacao['reason']}\"). The voided record is kept unchanged. "
                 "[ATTORNEY: whether to address the void here.]")
    t += ["", "[ATTORNEY: notice to the adverse party and making the record available for inspection, as FRE 902(11) "
          "and Fla. Stat. §90.803(6)(c) / §90.902(11) require.]", "",
          "I declare under penalty of perjury under the laws of the United States of America that the foregoing is true "
          "and correct. [ATTORNEY: 28 U.S.C. §1746 for federal court; for a Florida court, \"Under penalties of perjury, I "
          "declare that I have read the foregoing declaration and that the facts stated in it are true\" (Fla. Stat. "
          "§92.525), or a notarized affidavit.]", "",
          "Executed on [date] at [city, state].", "", "", "______________________________", CUSTODIANTE,
          f"[title], {EMPRESA}", "", "---", "",
          "### Questions for the attorney (from URACE's system, #115)", "",
          "1. The final wording, the court (federal or Florida) and whether this is a declaration or a notarized affidavit.",
          f"2. {CUSTODIANTE}'s title, and whether a second, technical declarant should certify the electronic process (FRE 902(13)).",
          "3. Whether the self-issued seal certificate (shown as \"unknown identity\" in Adobe) needs any additional explanation.",
          "4. Notice and inspection requirements before trial.",
          "5. Whether the record of events after signing (copy emailed, photo ID checked at the track, void) should be "
          "attached as a separate exhibit (it is in `certificate-of-completion.pdf`).", ""]
    return "\n".join(t).encode("utf-8")


# ------------------------------------------------------------------ montar e exportar
def _zip(arquivos):
    """O ZIP com a ordem dada, data fixa e permissões fixas: os mesmos arquivos dão os mesmos bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for nome, dados in arquivos:
            zi = zipfile.ZipInfo(nome, date_time=DATA_FIXA)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.create_system = 3
            zi.external_attr = 0o100444 << 16           # arquivo comum, só leitura
            z.writestr(zi, dados, compress_type=zipfile.ZIP_DEFLATED, compresslevel=NIVEL_ZIP)
    return buf.getvalue()


def montar(con, wid, commit=None):
    """O pacote de prova da waiver `wid`: (bytes do ZIP, info). Só lê: quem registra a exportação é `exportar`."""
    w = _waiver(con, wid)
    pdf = _pdf_assinado(w)
    trilha = json.loads(w["audit"] or "{}")
    commit = commit or _commit()
    anulacao = um(con, "SELECT * FROM waiver_voids WHERE waiver_id=?", (wid,))
    eventos = _eventos(con, wid)
    problemas = _conferir(con, w, trilha, eventos, anulacao)
    cadeia = _cadeia(con, eventos, problemas)
    modelo, pdf_modelo = _modelo(con, w, trilha)
    selo, raiz, assinatura = _do_selo(pdf, trilha)
    carimbo, token = _carimbo(con, w, assinatura)
    raiz_tsa = _raiz_da_tsa(token) if token else None

    registro = {k: v for k, v in w.items() if k not in ("audit", "pdf_path")}
    registro["audit_sha256"] = _sha((w["audit"] or "").encode("utf-8"))
    registro["voided"] = _limpo(dict(anulacao)) if anulacao else None
    arquivos = [("signed.pdf", pdf), ("audit.json", (w["audit"] or "").encode("utf-8")), ("waiver.json", _json(registro)),
                ("events.json", _json({"waiver_id": wid, "signature_id": trilha.get("signature_id"), "chain": cadeia,
                                       "integrity": {"ok": not problemas, "problems": problemas}, "events": eventos})),
                ("events.csv", _csv(eventos)),
                ("audit_logs.json", _json({"waiver_id": wid, "note": "Rows of URACE's append-only audit_logs about this "
                                           "waiver, the signer's account (until signing) or the invitation. Passwords, "
                                           "cookies, tokens, invitation links and email bodies are never stored or "
                                           "included.", "rows": _auditoria(con, w, trilha)})),
                ("template.json", _json(modelo))]
    if pdf_modelo is not None:
        arquivos.append(("template.pdf", pdf_modelo))
    if token:
        arquivos += [("timestamp.tst", token), ("timestamp.json", _json(carimbo))]
    if selo is not None:
        arquivos.append(("seal-cert.pem", _pem(selo.dump())))
    if raiz is not None:
        arquivos.append(("seal-root.pem", _pem(raiz.dump())))
    if raiz_tsa is not None:
        arquivos.append(("tsa/tsa-root.pem", _pem(raiz_tsa.dump())))
    arquivos.append(("certificate-of-completion.pdf", _certificado(w, trilha, eventos, cadeia, anulacao, carimbo, modelo,
                                                                   problemas)))
    arquivos.append(("system-description.md", _descricao(commit)))
    tem = {n: True for n, _ in arquivos}
    nomes = [n for n, _ in arquivos] + ["declaration-DRAFT.md", "VERIFY.md", "verify_events.py"]
    arquivos.append(("declaration-DRAFT.md", _declaracao(w, trilha, carimbo, commit, anulacao, nomes, problemas)))
    arquivos.append(("VERIFY.md", _verificar_md(w, trilha, carimbo, tem, problemas)))
    arquivos.append(("verify_events.py", SCRIPT_EVENTOS.encode("utf-8")))
    arquivos.append(("SHA256SUMS", "".join(f"{_sha(d)}  {n}\n" for n, d in arquivos).encode("ascii")))
    for n, d in arquivos:                                  # a trava: a chave do selo nunca sai, em arquivo nenhum
        if b"PRIVATE KEY" in d:
            raise RuntimeError(f"o pacote de prova ia levar uma chave privada em {n}")
    z = _zip(arquivos)
    return z, {"sha256": _sha(z), "bytes": len(z), "files": [n for n, _ in arquivos], "commit": commit.get("commit"),
               "integrity_ok": not problemas, "problems": problemas, "waiver": w}


def exportar(con, wid, usuario, ip=None, user_agent=None):
    """Monta o pacote e registra a exportação: o evento `evidence_exported` (trilha, #111) e a auditoria
    `waiver.evidence_export`, com o hash do ZIP, na mesma transação. Devolve (bytes, info)."""
    from command_center.db import auditar, transacao
    from command_center.providers import trilha_waiver as tw
    z, info = montar(con, wid)
    w = info.pop("waiver")
    detalhe = {"zip_sha256": info["sha256"], "zip_bytes": info["bytes"], "by": usuario.get("name"), "user_id": usuario.get("id"),
               "integrity_ok": info["integrity_ok"]}
    def gravar():
        e = tw.registrar(con, "evidence_exported", "staff", ip=ip, user_agent=user_agent, detail=detalhe, waiver_id=wid,
                         client_id=w["client_id"], pilot_id=w["pilot_id"], kind=w["template"])
        auditar(con, "waiver.evidence_export", f"user:{usuario.get('id')}", user_id=usuario.get("id"), entity_type="waiver",
                entity_id=wid, detail={**detalhe, "files": info["files"], "commit": info["commit"], "event_id": e["id"]}, ip=ip)

    if con.in_transaction:
        gravar()
    else:
        with transacao(con, imediata=True):
            gravar()
    return z, info
