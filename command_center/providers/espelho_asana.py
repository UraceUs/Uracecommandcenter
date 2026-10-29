"""#455 — o espelho completo do Asana. Dono, 29/10: "eu preciso ver mais pelo Command Center do que pelo Asana.
E as informações que estiverem no Asana serão as mesmas que estarão no Command Center, sempre. Seja de
comentários…" e, no plano aprovado: "pode seguir com o espelho completo do Asana".

Cada tarefa do quadro U-RACE (menos "Matt tasks", que nem entra na sincronia) guarda no banco a descrição, as
datas, as subtarefas, os comentários e os anexos como estão no Asana:

- a sincronia de 15 min já lê a tarefa inteira nas colunas de cliente: a descrição e as subtarefas vão para o
  espelho sem chamada a mais;
- comentários e anexos (e a tarefa inteira, nas colunas que só leem o resumo) são relidos só quando o
  `modified_at` do Asana mudou, com teto por rodada (`MAX_RODADA`): o que não coube fica para a próxima, das
  abertas e mais perto de hoje para as antigas;
- o detalhe da tarefa lê daqui; "Atualizar do Asana" relê na hora (`espelhar`);
- nada se apaga: o que sumiu do Asana fica com `gone_at`;
- o link de download do anexo expira no Asana, então ele não é guardado: a rota do painel pede um novo.
"""
import json
from datetime import date

from command_center.db import agora, atualizar, inserir, todos, um
from command_center.providers import NaoConectado, chamar

MAX_RODADA = 40          # tarefas relidas por inteiro por rodada: cada uma são até 5 chamadas ao Asana
TETO_LISTA = 1000        # a leitura do Asana para nessa quantidade: lista que bateu no teto não marca nada como sumido


def gid_da_tarefa(con, tid):
    l = um(con, "SELECT external_id FROM entity_links WHERE entity_type='task' AND entity_id=? AND system='asana'", (tid,))
    return l["external_id"] if l else None


def _gravar_lista(con, tabela, tid, linhas):
    """Grava as linhas que vieram do Asana (pelo gid) e marca `gone_at` nas que sumiram de lá. Nada se apaga."""
    vistos = set()
    for ln in linhas:
        gid = str(ln.get("gid") or "")
        if not gid:
            continue
        vistos.add(gid)
        campos = {k: v for k, v in ln.items() if k != "gid"}
        ja = um(con, f"SELECT id FROM {tabela} WHERE gid=?", (gid,))
        if ja:
            atualizar(con, tabela, ja["id"], task_id=tid, gone_at=None, synced_at=agora(), **campos)
        else:
            inserir(con, tabela, task_id=tid, gid=gid, **campos)
    if len(linhas) >= TETO_LISTA:
        return
    for x in todos(con, f"SELECT id, gid FROM {tabela} WHERE task_id=? AND gone_at IS NULL", (tid,)):
        if x["gid"] not in vistos:
            con.execute(f"UPDATE {tabela} SET gone_at=? WHERE id=?", (agora(), x["id"]))


def gravar(con, tid, full, comentarios=None, anexos=None):
    """Grava a tarefa lida no Asana (`asana_tarefa`): descrição, datas e subtarefas. Comentários e anexos só
    quando foram lidos nesta vez (None mantém o que já havia)."""
    atualizar(con, "tasks", tid, notes=full.get("notas"), asana_created_at=full.get("criada_em"),
              asana_completed_at=full.get("concluida_em"))
    subs = full.get("subtarefas_lista")
    if subs is not None:
        _gravar_lista(con, "task_subtasks", tid, [
            dict(gid=s.get("gid"), name=s.get("nome"), completed=1 if s.get("concluida") else 0,
                 completed_at=s.get("concluida_em"), due_on=s.get("vence_em"), assignee=s.get("responsavel"), sort=i)
            for i, s in enumerate(subs)])
    if comentarios is not None:
        _gravar_lista(con, "task_comments", tid, [
            dict(gid=c.get("gid"), author=c.get("quem"), text=c.get("texto"), created_at=c.get("quando")) for c in comentarios])
    if anexos is not None:
        _gravar_lista(con, "task_attachments", tid, [
            dict(gid=a.get("gid"), name=a.get("nome"), host=a.get("origem"), size=a.get("tamanho"), created_at=a.get("quando"))
            for a in anexos])


def _completo(con, tid, full, comentarios, anexos):
    gravar(con, tid, full, comentarios, anexos)
    extra = {}
    subs = full.get("subtarefas_lista")
    if subs is not None:                      # a contagem do card acompanha a lista lida (a do resumo não sabe as feitas)
        extra = dict(subtasks_total=len(subs), subtasks_done=sum(1 for s in subs if s.get("concluida")))
    atualizar(con, "tasks", tid, asana_modified_at=full.get("modificada_em"), mirrored_at=agora(), mirror_error=None, **extra)


def espelhar(con, tid, gid=None, chamar_fn=None):
    """Relê a tarefa inteira no Asana agora e grava ("Atualizar do Asana", e o detalhe da tarefa nunca espelhada).
    Também atualiza o resumo (título, status, data, responsável, campos) — nunca o cliente."""
    ch = chamar_fn or chamar
    gid = gid or gid_da_tarefa(con, tid)
    if not gid:
        raise LookupError("tarefa sem vínculo com o Asana")
    full = ch("asana", "asana_tarefa", gid=gid)
    comentarios = ch("asana", "asana_comentarios", gid=gid)
    anexos = ch("asana", "asana_anexos", gid=gid)
    resumo = dict(title=full.get("nome"), due_on=full.get("vence_em"), assignee=full.get("responsavel"),
                  fields=json.dumps(full.get("campos"), ensure_ascii=False) if full.get("campos") else None,
                  synced_at=agora())
    if full.get("concluida") is not None:
        resumo["status"] = "completed" if full.get("concluida") else "open"
    atualizar(con, "tasks", tid, **{k: v for k, v in resumo.items() if v is not None or k == "fields"})
    _completo(con, tid, full, comentarios, anexos)
    return full


def precisa(con, tid, modificada_em):
    """A tarefa entra na fila do espelho completo? Nunca espelhada, ou mudou no Asana desde o último espelho."""
    t = um(con, "SELECT mirrored_at, asana_modified_at FROM tasks WHERE id=?", (tid,))
    if not t:
        return False
    return not t["mirrored_at"] or (bool(modificada_em) and modificada_em != t["asana_modified_at"])


def _prioridade(t, hoje):
    try:
        dist = abs((date.fromisoformat(t["due_on"][:10]) - hoje).days) if t["due_on"] else 10 ** 6
    except ValueError:
        dist = 10 ** 6
    return (0 if t["status"] == "open" else 1, dist, -t["id"])


def rodada(con, fila, limite=None, chamar_fn=None, hoje=None):
    """Relê por inteiro as tarefas da fila, das abertas e mais perto de hoje para as antigas, até o teto.
    `fila` = [(tid, gid, full_ou_None)]: com `full` (a sincronia já leu a tarefa) faltam só comentários e anexos.
    O que não coube fica para a próxima rodada (o `modified_at` continua diferente do espelhado).
    Erro numa tarefa fica nela (`mirror_error`) e a rodada segue; limite da API (HTTP 429) ou Asana fora param."""
    ch = chamar_fn or chamar
    limite = MAX_RODADA if limite is None else limite
    hoje = hoje or date.today()
    por_id = {f[0]: f for f in fila}
    linhas = todos(con, "SELECT id, status, due_on FROM tasks WHERE id IN (%s)" % ",".join("?" * len(por_id)),
                   tuple(por_id)) if por_id else []
    ordem = sorted(linhas, key=lambda t: _prioridade(t, hoje))
    feitas = erros = 0
    parou = None
    for t in ordem:
        if feitas >= limite:
            break
        tid, gid, full = por_id[t["id"]]
        try:
            if full is None:
                full = ch("asana", "asana_tarefa", gid=gid)
            comentarios = ch("asana", "asana_comentarios", gid=gid)
            anexos = ch("asana", "asana_anexos", gid=gid)
        except NaoConectado:
            parou = "Asana não conectado"
            break
        except Exception as e:
            txt = str(e)
            if "HTTP 429" in txt:
                parou = "limite da API do Asana (429): o resto fica para a próxima rodada"
                break
            if "HTTP 404" not in txt:                  # 404: excluída no Asana — quem decide é a conferência das sumidas
                atualizar(con, "tasks", tid, mirror_error=f"{type(e).__name__}: {txt[:300]}")
                erros += 1
            continue
        _completo(con, tid, full, comentarios, anexos)
        feitas += 1
        if feitas % 10 == 0:
            con.commit()
    return {"espelhadas": feitas, "na_fila": max(0, len(fila) - feitas), "erros": erros, "parou": parou}


def _json(v):
    try:
        return json.loads(v) if v else None
    except ValueError:
        return None


def detalhe(con, tid, base_anexo):
    """O detalhe da tarefa no formato que o painel já desenha (antes vinha ao vivo do Asana)."""
    t = um(con, "SELECT * FROM tasks WHERE id=?", (tid,))
    link = um(con, "SELECT external_id, deep_link FROM entity_links WHERE entity_type='task' AND entity_id=? AND system='asana'", (tid,))
    subs = todos(con, "SELECT * FROM task_subtasks WHERE task_id=? AND gone_at IS NULL ORDER BY sort, id", (tid,))
    coms = todos(con, "SELECT * FROM task_comments WHERE task_id=? AND gone_at IS NULL ORDER BY created_at, id", (tid,))
    anexos = todos(con, "SELECT * FROM task_attachments WHERE task_id=? AND gone_at IS NULL ORDER BY created_at, id", (tid,))
    task = {
        "gid": link["external_id"] if link else None, "nome": t["title"], "concluida": t["status"] == "completed",
        "vence_em": t["due_on"], "responsavel": t["assignee"], "secao": t["section"], "campos": _json(t["fields"]),
        "notas": t["notes"], "link": link["deep_link"] if link else None,
        "criada_em": t["asana_created_at"], "modificada_em": t["asana_modified_at"], "concluida_em": t["asana_completed_at"],
        "subtarefas": len(subs),
        "subtarefas_lista": [{"gid": s["gid"], "nome": s["name"], "concluida": bool(s["completed"]), "vence_em": s["due_on"],
                              "concluida_em": s["completed_at"], "responsavel": s["assignee"]} for s in subs],
    }
    return {
        "connected": True, "gid": task["gid"], "task": task,
        "comments": [{"gid": c["gid"], "quando": c["created_at"], "quem": c["author"], "texto": c["text"]} for c in coms],
        "attachments": [{"gid": a["gid"], "nome": a["name"], "origem": a["host"], "quando": a["created_at"], "tamanho": a["size"],
                         "download": f"{base_anexo}/tasks/{tid}/anexos/{a['gid']}"} for a in anexos],
        "espelho": {"em": t["mirrored_at"], "erro": t["mirror_error"]},
    }
