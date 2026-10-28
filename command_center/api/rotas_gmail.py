"""Rotas do Gmail (#436: saíram do rotas.py, sem mudar rota): marcadores, thread ao vivo,
mover, triagem e classificação; manual dos marcadores; filtros nativos.
"""
import json
import os
import re
import sqlite3
import threading
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from command_center.api import auth
from command_center.api.rotas import BASE
from command_center.db import agora, atualizar, auditar, conectar, get_db, inserir, todos, um

r = APIRouter(prefix=BASE)


# ================================================================ Gmail
# Caixa de entrada por dentro: marcadores, corpo da thread ao vivo, mover
# (clique humano: aplica o marcador E tira da inbox), classificar com a IA.
from command_center.providers import NaoConectado, modulo, chamar  # noqa: E402
from command_center.providers import classificar  # noqa: E402


def _thread_id(con, eid):
    l = um(con, "SELECT external_id FROM entity_links WHERE entity_type='email' AND entity_id=? AND system='gmail'", (eid,))
    return l["external_id"] if l else None


@r.get("/gmail/labels")
def gmail_labels(mailbox: str = "urace", u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    """Marcadores reais da caixa + quantas threads da inbox espelhada têm cada um."""
    contagem = {}
    for e in todos(con, "SELECT labels, suggested_label FROM emails WHERE mailbox=? AND is_inbox=1", (mailbox,)):
        for l in json.loads(e["labels"] or "[]"):
            contagem[l] = contagem.get(l, 0) + 1
    try:
        nomes = chamar("gmail", "gmail_marcadores", conta=mailbox)
        return {"connected": True, "labels": [{"name": m["nome"], "id": m["id"], "type": m.get("tipo"), "inbox_count": contagem.get(m["nome"], 0)} for m in nomes]}
    except NaoConectado as e:
        return {"connected": False, "reason": str(e), "labels": [{"name": k, "id": None, "type": "user", "inbox_count": v} for k, v in sorted(contagem.items())
                                                                 if k.upper() not in classificar.SISTEMA and not k.startswith("CATEGORY_")]}
    except Exception as e:
        return {"connected": False, "reason": f"{type(e).__name__}: {str(e)[:200]}", "labels": []}


@r.get("/emails/{eid}/thread")
def email_thread(eid: int, u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    """Corpo da thread, ao vivo do Gmail (não fica no banco)."""
    e = um(con, "SELECT * FROM emails WHERE id=?", (eid,))
    if not e:
        raise HTTPException(404, "Email not found.")
    tid = _thread_id(con, eid)
    if not tid:
        return {"connected": False, "reason": "thread sem vínculo com o Gmail", "messages": []}
    try:
        t = chamar("gmail", "gmail_thread", conta=e["mailbox"], thread_id=tid)
        return {"connected": True, "thread_id": tid, "messages": t.get("mensagens", [])}
    except NaoConectado as ex:
        return {"connected": False, "reason": str(ex), "messages": []}
    except Exception as ex:
        raise HTTPException(502, f"Gmail: {str(ex)[:300]}")


@r.get("/emails/{eid}/html/{message_id}")
def email_html(eid: int, message_id: str, u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    """A mensagem como o Gmail mostra (HTML + imagens inline), limpa e com CSP
    própria, para o iframe com sandbox do painel. Sem HTML, cai para o texto."""
    from fastapi.responses import HTMLResponse
    from command_center.api import html_seguro
    e = um(con, "SELECT * FROM emails WHERE id=?", (eid,))
    if not e or not re.fullmatch(r"[A-Za-z0-9_-]{4,40}", message_id or ""):
        raise HTTPException(404, "Email not found.")
    try:
        r_ = modulo("gmail").mensagem_html(e["mailbox"], message_id)
    except NaoConectado as ex:
        raise HTTPException(503, f"Gmail não conectado: {ex}")
    except Exception as ex:
        raise HTTPException(502, f"Gmail: {str(ex)[:300]}")
    html = r_.get("html") or ("<pre style='white-space:pre-wrap'>%s</pre>" % (r_.get("texto") or "").replace("&", "&amp;").replace("<", "&lt;"))
    resp = HTMLResponse(html_seguro.pagina(html, r_.get("assunto") or e["subject"] or ""))
    resp.headers["Content-Security-Policy"] = html_seguro.CSP
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    return resp


class RotularIn(BaseModel):
    add: list[str] = []


@r.post("/emails/{eid}/labels")
def email_labels(eid: int, dados: RotularIn, request: Request, u=Depends(auth.exige("OPERATOR")),
                 con: sqlite3.Connection = Depends(get_db)):
    """Clique humano: ADICIONA marcadores (não tira da inbox). Mover é o clique no marcador."""
    e = um(con, "SELECT * FROM emails WHERE id=?", (eid,))
    if not e:
        raise HTTPException(404, "Email not found.")
    add = [l.strip() for l in dados.add if l and l.strip() and l.strip().upper() not in ("INBOX", "TRASH", "SPAM", "UNREAD", "STARRED")]
    if not add:
        raise HTTPException(400, "Escolha um marcador.")
    tid = _thread_id(con, eid)
    if not tid:
        raise HTTPException(409, "Thread sem vínculo com o Gmail.")
    try:
        res = modulo("gmail").rotular_humano(e["mailbox"], tid, add)
    except NaoConectado as ex:
        raise HTTPException(503, f"Gmail não conectado: {ex}")
    except Exception as ex:
        raise HTTPException(502, str(ex)[:300])
    labels = json.loads(e["labels"] or "[]")
    for l in add:
        if l not in labels:
            labels.append(l)
    con.execute("UPDATE emails SET labels=?, synced_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?", (json.dumps(labels, ensure_ascii=False), eid))
    auditar(con, "email.label", f"user:{u['id']}", user_id=u["id"], entity_type="email", entity_id=eid,
            detail={"add": add, "thread": tid, "mailbox": e["mailbox"]}, ip=auth._ip(request))
    return {"ok": True, "labels": labels, **res}


_TRIAGEM = {"running": False, "started_at": None, "finished_at": None, "result": None}


def _triagem_thread(user_id, mailboxes):
    from command_center.api import agenda, ia, motor
    from command_center.providers import triagem
    con = conectar()
    try:
        with ia._PARALELO:
            _TRIAGEM["result"] = triagem.rodar(con, ia.runner_email, f"agent:{ia.AGENTE}:triagem-{date.today().isoformat()}",
                                               mailboxes=mailboxes, aprendizados=motor.aprendizados(con), por=f"user:{user_id}")
        _ = agenda   # a rotina automática usa o mesmo caminho
    except Exception as e:
        _TRIAGEM["result"] = {"erros": [f"{type(e).__name__}: {str(e)[:300]}"]}
    finally:
        _TRIAGEM["running"] = False; _TRIAGEM["finished_at"] = agora(); con.close()


class TriagemIn(BaseModel):
    mailbox: str | None = None


@r.post("/gmail/triage", status_code=202)
def gmail_triage(dados: TriagemIn, request: Request, u=Depends(auth.exige("OPERATOR"))):
    """Triagem agora (a automática roda 07:00, 13:00 e 21:00): a IA lê cada thread,
    aplica os marcadores e move para o principal. Só ficam na inbox as que ela não decidiu."""
    if _TRIAGEM["running"]:
        return {"started": False, "running": True}
    from command_center.providers import triagem
    caixas = tuple([dados.mailbox]) if dados.mailbox in triagem.CAIXAS else triagem.CAIXAS
    _TRIAGEM.update(running=True, started_at=agora(), finished_at=None, result=None)
    threading.Thread(target=_triagem_thread, args=(u["id"], caixas), daemon=True).start()
    return {"started": True, "running": True}


@r.get("/gmail/triage")
def gmail_triage_status(u=Depends(auth.usuario_atual), con: sqlite3.Connection = Depends(get_db)):
    regra = um(con, "SELECT enabled, schedule, last_run_at, last_result FROM automation_rules WHERE name='gmail_triagem'")
    return {**_TRIAGEM, "rule": regra}


class MoverIn(BaseModel):
    label: str


@r.post("/emails/{eid}/move")
def email_move(eid: int, dados: MoverIn, request: Request, u=Depends(auth.exige("OPERATOR")),
               con: sqlite3.Connection = Depends(get_db)):
    """Clique humano: aplica o marcador e tira da caixa de entrada (decisão do dono, 04/09)."""
    e = um(con, "SELECT * FROM emails WHERE id=?", (eid,))
    if not e:
        raise HTTPException(404, "Email not found.")
    label = (dados.label or "").strip()
    if not label or label.upper() in ("INBOX", "TRASH", "SPAM", "UNREAD", "STARRED"):
        raise HTTPException(400, "Escolha um marcador de destino.")
    tid = _thread_id(con, eid)
    if not tid:
        raise HTTPException(409, "Thread sem vínculo com o Gmail.")
    try:
        res = modulo("gmail").mover_humano(e["mailbox"], tid, label)
    except NaoConectado as ex:
        raise HTTPException(503, f"Gmail não conectado: {ex}")
    except Exception as ex:
        raise HTTPException(502, str(ex)[:300])
    labels = [l for l in json.loads(e["labels"] or "[]") if l != "INBOX"]
    if label not in labels:
        labels.append(label)
    con.execute("UPDATE emails SET labels=?, is_inbox=0, handled=1, handled_by=?, handled_reason=?, synced_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
                (json.dumps(labels, ensure_ascii=False), f"user:{u['id']}", f"movido para {label}", eid))
    auditar(con, "email.move", f"user:{u['id']}", user_id=u["id"], entity_type="email", entity_id=eid,
            detail={"label": label, "thread": tid, "mailbox": e["mailbox"]}, ip=auth._ip(request))
    return {"ok": True, **res}


_CLASSIF = {"running": False, "started_at": None, "finished_at": None, "result": None}


def _classificar_thread(user_id, mailbox, ids):
    from command_center.api import ia
    con = conectar()
    try:
        saida = {"classificados": 0, "sem_marcador": 0, "erro": None}
        where = "mailbox=? AND is_inbox=1" + (" AND id IN (%s)" % ",".join("?" * len(ids)) if ids else " AND suggested_label IS NULL")
        emails = todos(con, f"SELECT * FROM emails WHERE {where}", (mailbox, *ids))
        if not emails:
            _CLASSIF["result"] = saida; return
        nomes = [m["nome"] for m in chamar("gmail", "gmail_marcadores", conta=mailbox)]
        nomes = [n for n in nomes if n.upper() not in classificar.SISTEMA and not n.startswith("CATEGORY_")]
        for i in range(0, len(emails), 25):
            lote = emails[i:i + 25]
            ok, texto, erro = ia.runner_email(classificar.prompt_ia(lote, nomes, mailbox), f"agent:{ia.AGENTE}:classificar-{mailbox}")
            if not ok:
                saida["erro"] = erro; break
            res = classificar.parse_ia(texto, nomes)
            for e in lote:
                lab, motivo = res.get(e["id"], (None, "sem resposta da IA"))
                atualizar(con, "emails", e["id"], suggested_label=lab, suggested_reason=motivo, suggested_by="ia", suggested_at=agora())
                saida["classificados" if lab else "sem_marcador"] += 1
        auditar(con, "gmail.classify", f"user:{user_id}", user_id=user_id, detail={"mailbox": mailbox, **saida})
        _CLASSIF["result"] = saida
    except Exception as e:
        _CLASSIF["result"] = {"erro": f"{type(e).__name__}: {str(e)[:300]}"}
    finally:
        _CLASSIF["running"] = False; _CLASSIF["finished_at"] = agora(); con.close()


class ClassificarIn(BaseModel):
    mailbox: str = "urace"
    ids: list[int] = []


@r.post("/gmail/classify", status_code=202)
def gmail_classify(dados: ClassificarIn, u=Depends(auth.exige("OPERATOR"))):
    """Manda as threads sem sugestão (ou as escolhidas) para o agente classificar. Só sugere; mover é clique."""
    if _CLASSIF["running"]:
        return {"started": False, "running": True}
    _CLASSIF.update(running=True, started_at=agora(), finished_at=None, result=None)
    threading.Thread(target=_classificar_thread, args=(u["id"], dados.mailbox, dados.ids[:200]), daemon=True).start()
    return {"started": True, "running": True}


@r.get("/gmail/classify")
def gmail_classify_status(u=Depends(auth.usuario_atual)):
    return _CLASSIF


# ------------------------------------------- manual dos marcadores do Gmail
@r.get("/gmail/manual")
def gmail_manual(mailbox: str | None = None, u=Depends(auth.usuario_atual),
                 con: sqlite3.Connection = Depends(get_db)):
    """O manual: marcador por marcador, o que vai em cada um, e o estado da confirmação.
    A triagem só usa o que estiver 'confirmado' — sem nada confirmado, ela não roda.

    `mailbox` filtra pela caixa: a support@ tem taxonomia própria e misturar as duas
    numa lista só esconde que uma delas está sem manual."""
    from command_center.providers.taxonomia_gmail import EXEMPLOS
    from command_center.providers.triagem import DA_CAIXA
    sql, p = "SELECT * FROM gmail_labels", []
    if mailbox:
        sql += " WHERE 1=1 " + DA_CAIXA
        p.append(mailbox)
    linhas = todos(con, sql + " ORDER BY family, name", p)
    contagem = {}
    for l in linhas:
        contagem[l["status"]] = contagem.get(l["status"], 0) + 1
    return {"labels": linhas, "resumo": contagem, "exemplos": [{"chega": a, "vai_para": b} for a, b in EXEMPLOS],
            "confirmado": contagem.get("confirmado", 0) > 0,
            "confirmado_em": (um(con, "SELECT MAX(confirmed_at) AS q FROM gmail_labels WHERE status='confirmado'") or {}).get("q")}


class MarcadorIn(BaseModel):
    what: str | None = None
    status: str | None = None          # pendente | confirmado | fora


@r.patch("/gmail/manual/{lid}")
def gmail_manual_editar(lid: int, dados: MarcadorIn, request: Request, u=Depends(auth.exige("MANAGER")),
                        con: sqlite3.Connection = Depends(get_db)):
    """O dono corrige o que vai num marcador, ou tira o marcador do manual."""
    l = um(con, "SELECT * FROM gmail_labels WHERE id=?", (lid,))
    if not l:
        raise HTTPException(404, "Marcador não está no manual.")
    campos = {}
    if dados.what is not None:
        campos["what"] = dados.what.strip()[:500]
    if dados.status:
        if dados.status not in ("pendente", "confirmado", "fora"):
            raise HTTPException(400, "status inválido")
        campos["status"] = dados.status
        campos["confirmed_by"] = f"user:{u['id']}" if dados.status == "confirmado" else None
        campos["confirmed_at"] = agora() if dados.status == "confirmado" else None
    if campos:
        atualizar(con, "gmail_labels", lid, **campos)
        auditar(con, "gmail.manual.editado", f"user:{u['id']}", user_id=u["id"], entity_type="gmail_label", entity_id=lid,
                detail={"marcador": l["name"], **{k: v for k, v in campos.items() if k in ("what", "status")}}, ip=auth._ip(request))
        con.commit()
    return um(con, "SELECT * FROM gmail_labels WHERE id=?", (lid,))


class ConfirmarIn(BaseModel):
    familia: str | None = None         # confirma só uma família; sem ela, tudo que está pendente
    mailbox: str | None = None         # e só desta caixa: a tela é por caixa, a confirmação também


@r.post("/gmail/manual/confirm")
def gmail_manual_confirmar(dados: ConfirmarIn, request: Request, u=Depends(auth.exige("MANAGER")),
                           con: sqlite3.Connection = Depends(get_db)):
    """Confirmação do dono: a partir daqui a IA pode classificar — e SÓ com estes marcadores."""
    from command_center.providers.triagem import DA_CAIXA
    sql = "UPDATE gmail_labels SET status='confirmado', confirmed_by=?, confirmed_at=? WHERE status='pendente'"
    p = [f"user:{u['id']}", agora()]
    if dados.familia:
        sql += " AND family=?"
        p.append(dados.familia)
    if dados.mailbox:
        # a tela é por caixa; "confirmar tudo" olhando a urace@ não pode confirmar
        # marcador da support@ que o dono nem viu
        sql += " " + DA_CAIXA.replace("gmail_labels.mailboxes", "mailboxes")
        p.append(dados.mailbox)
    n = con.execute(sql, p).rowcount
    auditar(con, "gmail.manual.confirmado", f"user:{u['id']}", user_id=u["id"],
            detail={"familia": dados.familia or "todas", "caixa": dados.mailbox or "todas",
                    "marcadores": n}, ip=auth._ip(request))
    con.commit()
    return {"ok": True, "confirmados": n}


@r.post("/gmail/manual/refresh")
def gmail_manual_atualizar(mailbox: str = "urace", u=Depends(auth.exige("MANAGER")),
                           con: sqlite3.Connection = Depends(get_db)):
    """Relê os marcadores da caixa (só leitura): marcador novo entra como PENDENTE,
    marcador que sumiu fica anotado. Nada é criado no Gmail."""
    try:
        nomes = chamar("gmail", "gmail_marcadores", conta=mailbox)
    except NaoConectado as e:
        raise HTTPException(503, f"Gmail não conectado: {e}")
    except Exception as e:
        raise HTTPException(502, str(e)[:300])
    vivos = {m["nome"] for m in nomes if (m.get("tipo") or "user") == "user"}
    novos, saiu = [], []
    # A presença é POR CAIXA. Antes isto era um flag só: reler a support@ marcava todos
    # os marcadores da urace@ como inexistentes, porque não estavam na lista daquela caixa.
    for l in todos(con, "SELECT id, name, mailboxes, origin FROM gmail_labels"):
        try:
            caixas = json.loads(l["mailboxes"] or '["urace"]')
        except ValueError:
            caixas = ["urace"]
        tinha = mailbox in caixas
        if l["name"] in vivos and not tinha:
            caixas.append(mailbox)
        elif l["name"] not in vivos and tinha:
            caixas.remove(mailbox)
            saiu.append(l["name"])
        else:
            continue
        atualizar(con, "gmail_labels", l["id"], mailboxes=json.dumps(sorted(set(caixas))),
                  in_gmail=1 if caixas else 0)
    for nome in sorted(vivos):
        if not um(con, "SELECT 1 AS x FROM gmail_labels WHERE name=?", (nome,)):
            inserir(con, "gmail_labels", name=nome, family=nome.split("/")[0], what=None,
                    status="pendente", mailboxes=json.dumps([mailbox]), origin="caixa")
            novos.append(nome)
    if novos or saiu:
        auditar(con, "gmail.manual.novos", f"user:{u['id']}", user_id=u["id"],
                detail={"caixa": mailbox, "marcadores": novos[:20], "sairam": saiu[:20]})
    con.commit()
    return {"ok": True, "novos": novos, "sairam": saiu, "caixa": mailbox, "total_na_caixa": len(vivos)}


# ============================================================ filtros nativos do Gmail (15/09)
# O gerador (adminai/gerar_filtros_gmail.py) roda no VPS e grava em ~/.urace. O dono
# precisava de `scp` para levar o arquivo ao navegador — e o scp falhou. Agora o painel
# gera, mostra o relatório e entrega o XML: a extensão baixa e importa no Gmail.
import subprocess  # noqa: E402
import sys  # noqa: E402

REPO_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILTROS_DIR = os.environ.get("URACE_DIR", os.path.expanduser("~/.urace"))
CAIXAS_FILTRO = ("urace", "support")
_filtros_rodando: dict[str, bool] = {}


def _caminhos_filtros(conta):
    if conta not in CAIXAS_FILTRO:
        raise HTTPException(404, "Caixa desconhecida.")
    return (os.path.join(FILTROS_DIR, f"mailFilters-{conta}.xml"),
            os.path.join(FILTROS_DIR, f"filtros-{conta}.md"),
            os.path.join(FILTROS_DIR, f"filtros-{conta}.log"))


def _gerar_filtros_thread(conta, user_id):
    xml, _md, log = _caminhos_filtros(conta)
    _filtros_rodando[conta] = True
    try:
        with open(log, "w", encoding="utf-8") as f:
            p = subprocess.run([sys.executable, os.path.join(REPO_DIR, "adminai", "gerar_filtros_gmail.py"),
                                "--conta", conta, "--saida", FILTROS_DIR],
                               cwd=REPO_DIR, stdout=f, stderr=subprocess.STDOUT, timeout=3600)
        ok = p.returncode == 0 and os.path.isfile(xml)
    except Exception as e:                                   # timeout, permissão: nunca derruba o serviço
        ok = False
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"\nERRO: {type(e).__name__}: {e}\n")
    finally:
        _filtros_rodando[conta] = False
    con = conectar()
    try:
        auditar(con, "gmail.filtros.gerados" if ok else "gmail.filtros.falhou", f"user:{user_id}", user_id=user_id,
                detail={"caixa": conta, "log": log})
        con.commit()
    finally:
        con.close()


@r.get("/gmail/filtros/{conta}")
def gmail_filtros_estado(conta: str, u=Depends(auth.usuario_atual)):
    """O que existe gerado para a caixa: quantos filtros, quando, e o relatório para revisar."""
    xml, md, log = _caminhos_filtros(conta)
    saida = {"caixa": conta, "rodando": bool(_filtros_rodando.get(conta)), "existe": os.path.isfile(xml),
             "gerado_em": None, "filtros": 0, "relatorio": None, "log": None}
    if saida["existe"]:
        from datetime import datetime, timezone
        saida["gerado_em"] = datetime.fromtimestamp(os.path.getmtime(xml), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(xml, encoding="utf-8") as f:
            saida["filtros"] = f.read().count("<entry>")
    if os.path.isfile(md):
        with open(md, encoding="utf-8") as f:
            saida["relatorio"] = f.read()
    if os.path.isfile(log):
        with open(log, encoding="utf-8") as f:
            saida["log"] = f.read()[-1500:]
    return saida


@r.post("/gmail/filtros/{conta}/gerar")
def gmail_filtros_gerar(conta: str, request: Request, u=Depends(auth.exige("MANAGER"))):
    """Gera os filtros em segundo plano (leva minutos: lê milhares de mensagens).
    Só leitura no Gmail; o resultado é um arquivo que o dono revisa e importa."""
    _caminhos_filtros(conta)
    if _filtros_rodando.get(conta):
        return {"started": False, "motivo": "já está rodando"}
    threading.Thread(target=_gerar_filtros_thread, args=(conta, u["id"]), daemon=True).start()
    return {"started": True}


def _regras_do_xml(caminho):
    """As regras do arquivo que o dono revisou. Ler o XML (e não recalcular) garante que
    o que entra no Gmail é exatamente o que ele viu no relatório."""
    import xml.etree.ElementTree as ET
    ns = {"a": "http://www.w3.org/2005/Atom", "apps": "http://schemas.google.com/apps/2006"}
    regras = []
    for entry in ET.parse(caminho).getroot().findall("a:entry", ns):
        p = {e.get("name"): e.get("value") for e in entry.findall("apps:property", ns)}
        criterio = {k: p[k] for k in ("from", "to", "subject", "hasTheWord") if p.get(k)}
        if criterio and p.get("label"):
            regras.append({"criterio": criterio, "marcador": p["label"],
                           "arquivar": p.get("shouldArchive") == "true"})
    return regras


@r.post("/gmail/filtros/{conta}/aplicar")
def gmail_filtros_aplicar(conta: str, request: Request, u=Depends(auth.exige("MANAGER")),
                          con: sqlite3.Connection = Depends(get_db)):
    """Cria no Gmail os filtros do arquivo gerado, pela API (16/09).

    Nasceu de um problema real: pela tela, a conta delegada não consegue importar
    (o Google pede reautenticação) e um clique a mais dispara a criação em dobro.
    Pela API não há nem um nem outro — e filtro que já existe igual é pulado.
    Nunca apaga nem edita filtro: só cria o que falta."""
    xml, _md, _log = _caminhos_filtros(conta)
    if not os.path.isfile(xml):
        raise HTTPException(404, "Ainda não há filtros gerados para esta caixa.")
    try:
        g = modulo("gmail")
    except NaoConectado as e:
        raise HTTPException(503, f"Gmail não conectado: {e}")
    if not hasattr(g, "criar_filtro_humano"):
        raise HTTPException(503, "O servidor ainda não tem a porta de filtros; rode o deploy.")
    criados, pulados, erros = [], [], []
    for reg in _regras_do_xml(xml):
        try:
            ok, det = g.criar_filtro_humano(conta, reg["criterio"], reg["marcador"], reg["arquivar"])
            (criados if ok else pulados).append({"marcador": reg["marcador"], **det})
        except Exception as e:
            erros.append({"marcador": reg["marcador"], "erro": f"{type(e).__name__}: {str(e)[:200]}"})
    auditar(con, "gmail.filtros.aplicados", f"user:{u['id']}", user_id=u["id"],
            detail={"caixa": conta, "criados": len(criados), "pulados": len(pulados),
                    "erros": erros[:10]}, ip=auth._ip(request))
    con.commit()
    return {"ok": True, "caixa": conta, "criados": len(criados), "pulados": len(pulados),
            "erros": erros, "detalhe_criados": criados[:50]}


@r.get("/gmail/filtros/{conta}/download")
def gmail_filtros_download(conta: str, u=Depends(auth.exige("MANAGER"))):
    """O XML que o Gmail importa (Configurações → Filtros → Importar filtros)."""
    from fastapi.responses import FileResponse
    xml, _md, _log = _caminhos_filtros(conta)
    if not os.path.isfile(xml):
        raise HTTPException(404, "Ainda não há filtros gerados para esta caixa.")
    return FileResponse(xml, filename=f"mailFilters-{conta}.xml", media_type="application/xml",
                        headers={"Cache-Control": "no-store"})
