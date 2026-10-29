"""Serviços no card do cliente: levar para o cliente certo e trocar o nome.

Dono, 29/09, no card do Enzo Kartian: *"esse Levi Gridzik não é desse cliente… consigo
vincular ao cliente correto"*, e *"alterar o nome dos serviços que estão lá no Asana…
por aqui, para deixar tudo mais organizado… e selecionar quais outros eu quero deixar com
esse mesmo nome"*.

- **Vincular** grava o carimbo `client_by='human'`: a sincronia do Asana não devolve mais o
  serviço para o card de onde ele saiu (antes, uma tarefa aberta era relida a cada rodada
  e o cliente era decidido de novo pela descrição).
- **Renomear** troca o nome **no Asana** primeiro — o painel é espelho, e um nome trocado só
  aqui voltaria ao antigo na próxima sincronia. Se o Asana não confirmar (modo simulação,
  tarefa protegida, rede), o nome do painel não muda e a resposta diz por quê.
"""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from command_center.api import auth
from command_center.db import agora, auditar, get_db, status_da_waiver, um

r = APIRouter(prefix="/ops/api/tasks", tags=["servicos"])


def _tarefa(con, tid):
    t = um(con, "SELECT * FROM tasks WHERE id=?", (tid,))
    if not t:
        raise HTTPException(404, "Serviço não encontrado.")
    return t


def _gid(con, tid):
    l = um(con, "SELECT external_id FROM entity_links WHERE entity_type='task' AND entity_id=? AND system='asana'", (tid,))
    return l["external_id"] if l else None


class VincularIn(BaseModel):
    client_id: int


@r.post("/{tid}/cliente")
def vincular(tid: int, dados: VincularIn, request: Request, con: sqlite3.Connection = Depends(get_db),
             u=Depends(auth.exige("MANAGER"))):
    """Leva o serviço para o card do cliente certo — e a sincronia não desfaz. É de gerente,
    como unir cards: serviço no card errado é o erro que o dono mais cobra."""
    t = _tarefa(con, tid)
    c = um(con, "SELECT id, name, pilot_name FROM clients WHERE id=?", (dados.client_id,))
    if not c:
        raise HTTPException(404, "Cliente não encontrado.")
    con.execute("UPDATE tasks SET client_id=?, client_by='human', client_at=? WHERE id=?", (c["id"], agora(), tid))
    auditar(con, "task.client", f"user:{u['id']}", user_id=u["id"], entity_type="task", entity_id=tid,
            detail={"titulo": t["title"], "de": t["client_id"], "para": c["id"], "por": "card do cliente"},
            ip=auth._ip(request))
    con.commit()
    return {"ok": True, "task_id": tid, "client_id": c["id"], "cliente": c["pilot_name"] or c["name"]}


class RenomearIn(BaseModel):
    task_ids: list[int]
    nome: str


@r.post("/renomear")
def renomear(dados: RenomearIn, request: Request, con: sqlite3.Connection = Depends(get_db),
             u=Depends(auth.exige("OPERATOR"))):
    """Um nome para um ou vários serviços. Cada um é tentado no Asana; o que o Asana não
    confirmar fica como estava, com o motivo na resposta."""
    from command_center import providers
    nome = (dados.nome or "").strip()
    if not nome:
        raise HTTPException(400, "O nome não pode ficar vazio.")
    if len(nome) > 250:
        raise HTTPException(400, "Nome longo demais (máximo 250).")
    ids = list(dict.fromkeys(dados.task_ids))
    if not ids or len(ids) > 100:
        raise HTTPException(400, "Escolha de 1 a 100 serviços.")
    tarefas = [_tarefa(con, i) for i in ids]
    feitos, falhas = [], []
    for t in tarefas:
        gid = _gid(con, t["id"])
        if gid:
            try:
                res = providers.chamar("asana", "asana_renomear", gid=gid, nome=nome)
            except providers.NaoConectado:
                falhas.append({"task_id": t["id"], "titulo": t["title"], "motivo": "Asana não está conectado"})
                continue
            except Exception as e:                                # noqa: BLE001 - uma falha não para as outras
                falhas.append({"task_id": t["id"], "titulo": t["title"], "motivo": str(e)[:200]})
                continue
            if not res.get("aplicado") and res.get("motivo") != "já tem esse nome":
                falhas.append({"task_id": t["id"], "titulo": t["title"],
                               "motivo": "o Asana está em modo simulação: nada mudou lá, então nada mudou aqui"})
                continue
        # Quem renomeia olhando o card confirma de quem é o serviço: sem o carimbo, um nome
        # novo sem o nome da pessoa faria a sincronia decidir o cliente de novo.
        carimbo = ", client_by='human', client_at=?" if t["client_id"] and t["client_by"] != "human" else ""
        con.execute(f"UPDATE tasks SET title=?{carimbo} WHERE id=?",
                    (nome, *( [agora()] if carimbo else [] ), t["id"]))
        auditar(con, "task.rename", f"user:{u['id']}", user_id=u["id"], entity_type="task", entity_id=t["id"],
                detail={"antes": t["title"], "depois": nome, "asana": bool(gid)}, ip=auth._ip(request))
        feitos.append({"task_id": t["id"], "antes": t["title"]})
    con.commit()
    if not feitos and falhas:
        raise HTTPException(502, "Nenhum serviço foi renomeado: " + "; ".join(f["motivo"] for f in falhas[:3]))
    return {"renomeados": feitos, "falhas": falhas, "nome": nome}


# ------------------------------------------------------------------ excluir e restaurar (#219)
# Dono, 13/10: "somente o acesso livre e o gerente tenham a possibilidade de excluir uma tarefa
# facilmente. Ela exclui, deixa de ser mostrada, mas lá no histórico de serviço ela continua sendo
# armazenada como uma tarefa excluída, com todo o histórico de logs para auditoria."
# Excluir é uma marca: a linha fica no banco, a tarefa fica no Asana (a sincronia só atualiza os
# campos que lê, e a marca sobrevive), e o serviço some do Calendário, do balcão, dos contadores,
# de Precisa de atenção e do que a IA faz sozinha. No card, continua no histórico, como excluído.
class ExcluirIn(BaseModel):
    motivo: str | None = None


@r.post("/{tid}/excluir")
def excluir(tid: int, dados: ExcluirIn, request: Request, con: sqlite3.Connection = Depends(get_db),
            u=Depends(auth.exige("MANAGER"))):
    t = _tarefa(con, tid)
    if t["deleted_at"]:
        raise HTTPException(409, "Este serviço já foi excluído.")
    motivo = (dados.motivo or "").strip()[:300] or None
    con.execute("UPDATE tasks SET deleted_at=?, deleted_by=?, deleted_reason=? WHERE id=?", (agora(), u["id"], motivo, tid))
    auditar(con, "task.deleted", f"user:{u['id']}", user_id=u["id"], entity_type="task", entity_id=tid,
            detail={"titulo": t["title"], "data": t["due_on"], "client_id": t["client_id"], "motivo": motivo,
                    "asana": _gid(con, tid)}, ip=auth._ip(request))
    con.commit()
    return {"ok": True, "task_id": tid}


@r.post("/{tid}/restaurar")
def restaurar(tid: int, request: Request, con: sqlite3.Connection = Depends(get_db), u=Depends(auth.exige("MANAGER"))):
    t = _tarefa(con, tid)
    if not t["deleted_at"]:
        raise HTTPException(409, "Este serviço não está excluído.")
    con.execute("UPDATE tasks SET deleted_at=NULL, deleted_by=NULL, deleted_reason=NULL WHERE id=?", (tid,))
    auditar(con, "task.restored", f"user:{u['id']}", user_id=u["id"], entity_type="task", entity_id=tid,
            detail={"titulo": t["title"], "data": t["due_on"], "excluido_em": t["deleted_at"], "motivo": t["deleted_reason"]},
            ip=auth._ip(request))
    con.commit()
    return {"ok": True, "task_id": tid}


# ------------------------------------------------------------------ o card do serviço (#460)
# Dono, 29/10: "eu preciso ver mais pelo Command Center do que pelo Asana". O card lê o espelho (#456); comentar
# e concluir subtarefa vão primeiro ao Asana (o painel é espelho) e, confirmados lá, o espelho é relido.
class ComentarIn(BaseModel):
    texto: str


def _erro_asana(e):
    from command_center import providers
    if isinstance(e, providers.NaoConectado):
        return HTTPException(503, f"Asana não conectado: {e}")
    txt = str(e)
    if "RECUSADO" in txt:
        return HTTPException(409, txt[:300])
    return HTTPException(502, f"Asana: {txt[:300]}")


def _relido(con, tid, gid):
    """Relê o espelho depois de escrever no Asana; se a releitura falhar, a escrita já valeu e o aviso diz."""
    from command_center.api.rotas import BASE
    from command_center.providers import espelho_asana
    aviso = None
    try:
        espelho_asana.espelhar(con, tid, gid)
    except Exception as e:                                        # noqa: BLE001 - a escrita no Asana já aconteceu
        aviso = f"gravado no Asana; o espelho atualiza na próxima sincronia ({str(e)[:120]})"
    con.commit()
    saida = espelho_asana.detalhe(con, tid, BASE)
    saida["espelho"]["aviso"] = aviso
    return saida


@r.post("/{tid}/comentar")
def comentar(tid: int, dados: ComentarIn, request: Request, con: sqlite3.Connection = Depends(get_db),
             u=Depends(auth.exige("OPERATOR"))):
    """Comenta no Asana com o nome de quem escreveu na frente (lá o autor aparece como a conta da integração)."""
    from command_center import providers
    texto = (dados.texto or "").strip()
    if not texto:
        raise HTTPException(400, "Escreva o comentário.")
    if len(texto) > 4000:
        raise HTTPException(400, "Comentário longo demais (máximo 4000).")
    _tarefa(con, tid)
    gid = _gid(con, tid)
    if not gid:
        raise HTTPException(409, "Este serviço não está ligado a uma tarefa do Asana.")
    try:
        res = providers.chamar("asana", "comentar_humano", gid=gid, texto=f"{u.get('name') or u['email']} (Command Center): {texto}")
    except Exception as e:                                        # noqa: BLE001 - vira o código certo
        raise _erro_asana(e)
    if not res.get("aplicado"):
        raise HTTPException(502, "O Asana não confirmou o comentário: nada foi gravado.")
    auditar(con, "task.comment", f"user:{u['id']}", user_id=u["id"], entity_type="task", entity_id=tid,
            detail={"asana": gid, "story": res.get("story_gid"), "tamanho": len(texto)}, ip=auth._ip(request))
    return _relido(con, tid, gid)


@r.post("/{tid}/subtarefas/{sgid}/concluir")
def concluir_subtarefa(tid: int, sgid: str, request: Request, con: sqlite3.Connection = Depends(get_db),
                       u=Depends(auth.exige("OPERATOR"))):
    """Conclui a subtarefa no Asana. Já concluída: 409 (não existe desconcluir, regra do dono)."""
    from command_center import providers
    _tarefa(con, tid)
    gid = _gid(con, tid)
    s = um(con, "SELECT name, completed FROM task_subtasks WHERE task_id=? AND gid=? AND gone_at IS NULL", (tid, sgid))
    if not gid or not s:
        raise HTTPException(404, "Subtarefa não encontrada neste serviço.")
    if s["completed"]:
        raise HTTPException(409, "A subtarefa já está concluída (no Asana não se desconclui por aqui).")
    try:
        res = providers.chamar("asana", "concluir_subtarefa_humano", gid_tarefa=gid, gid_subtarefa=sgid)
    except Exception as e:                                        # noqa: BLE001
        raise _erro_asana(e)
    if not res.get("aplicado") and res.get("motivo") != "já estava concluída":
        raise HTTPException(502, "O Asana não confirmou: nada mudou.")
    auditar(con, "task.subtask.complete", f"user:{u['id']}", user_id=u["id"], entity_type="task", entity_id=tid,
            detail={"asana": gid, "subtarefa": sgid, "nome": s["name"]}, ip=auth._ip(request))
    return _relido(con, tid, gid)


@r.get("/{tid}/servico")
def servico(tid: int, u=Depends(auth.exige("OPERATOR")), con: sqlite3.Connection = Depends(get_db)):
    """O card do serviço: o detalhe do espelho e, ao lado, o cliente (com os tamanhos), as peças do balcão do dia
    e o checklist do box. O valor das peças só para quem vê o financeiro."""
    from command_center.api import rotas_clientes, rotas_qbo
    from command_center.db import todos
    t = _tarefa(con, tid)
    det = rotas_qbo.task_detail(tid, False, u, con)
    fin = auth.pode(u["role"], "MANAGER")
    cliente = None
    if t["client_id"]:
        c = um(con, "SELECT * FROM clients WHERE id=?", (t["client_id"],))
        if c:
            dados = rotas_clientes.dados_do_cliente(con, c)
            # a assinada que vale (não anulada) vem primeiro, como no card do cliente; a anulada aparece como `voided`
            sv = status_da_waiver("w")
            w = um(con, f"""SELECT {sv} AS status, w.expires_at FROM waivers w WHERE w.client_id=?
                            ORDER BY ({sv} = 'completed') DESC, COALESCE(w.completed_at, w.sent_at) DESC LIMIT 1""", (c["id"],))
            m = dados["medidas"]
            cliente = {"id": c["id"], "nome": c["name"], "piloto": c["pilot_name"], "nascimento": c["pilot_dob"], "vip": bool(c["vip"]),
                       "classe": dados["classe"], "waiver": dict(w) if w else None,
                       "tamanhos": {k: m[k] for k in ("suit_size", "helmet_size", "glove_size", "shoe_size") if m.get(k)}}
    pecas = []
    if t["client_id"] and t["due_on"]:
        for pi in todos(con, """SELECT id, status, doc_number, total FROM parts_invoices WHERE client_id=? AND service_date=? AND status!='anulada'""",
                        (t["client_id"], t["due_on"][:10])):
            itens = todos(con, """SELECT COALESCE(i.name, 'peça') AS nome, SUM(sc.qty) AS qtd FROM stock_charges sc
                                  LEFT JOIN stock_items i ON i.id=sc.item_id WHERE sc.parts_invoice_id=? GROUP BY nome ORDER BY nome""", (pi["id"],))
            pecas.append({"id": pi["id"], "status": pi["status"], "doc": pi["doc_number"], "total": pi["total"] if fin else None, "itens": itens})
    checklists = todos(con, """SELECT r.id, r.title, r.status, (SELECT COUNT(*) FROM checklist_run_items x WHERE x.run_id=r.id) AS total,
                                      (SELECT COUNT(*) FROM checklist_run_items x WHERE x.run_id=r.id AND x.done=1) AS feitos
                               FROM checklist_runs r WHERE r.task_id=? ORDER BY r.id""", (tid,))
    return {"servico": det, "tarefa": {"id": t["id"], "titulo": t["title"], "data": t["due_on"], "status": t["status"], "secao": t["section"],
                                        "responsavel": t["assignee"], "client_id": t["client_id"], "excluida": bool(t["deleted_at"])},
            "cliente": cliente, "pecas_do_dia": pecas, "checklists": checklists}
