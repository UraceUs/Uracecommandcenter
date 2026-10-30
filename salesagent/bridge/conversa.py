"""O robô lê a conversa antes de responder (dono, 30/10, #533).

Caso real: alguém do time pediu fotos a um fotógrafo parceiro pelo Instagram; ele respondeu "Deixa comigo" e o
robô entrou com a triagem de venda, e no dia seguinte com a call. O Kommo não entrega o texto do que sai no chat
de canal nativo, mas entrega o momento (`outgoing_chat_message`). O que saiu e não foi a ponte que mandou é do
time, ou de outro bot: a conversa é deles, e o robô fica quieto.

A conversa que a ponte viu (lead e robô) vai para o modelo: as últimas 10 falas, ou 30 quando a conversa já é
de venda, com a regra de ler antes de responder e não vender em conversa amigável.
"""
import time

import kommo_client as kommo
import state
from config import SDR_EQUIPE_JANELA_H

TAGS_FORA_DE_VENDA = {"supplier", "suppliers", "fornecedor", "parceiro", "partner", "equipe", "staff", "team",
                      "nao_e_lead", "não é lead"}
_FOLGA_S = 180                     # o Kommo registra a nossa entrega alguns segundos depois do log da ponte
_cache: dict[int, tuple[float, int | None]] = {}


def fora_de_venda(tags) -> bool:
    return bool({str(t).strip().lower() for t in tags or ()} & TAGS_FORA_DE_VENDA)


def equipe_falando(lead_id: int, agora: float | None = None) -> int | None:
    """Momento (epoch) da última mensagem que saiu para a pessoa nas últimas SDR_EQUIPE_JANELA_H horas e que
    não foi a ponte que mandou. None: ninguém além do robô falou (ou o Kommo não respondeu: segue como antes)."""
    if not SDR_EQUIPE_JANELA_H:
        return None
    agora = agora or time.time()
    guardado = _cache.get(lead_id)
    if guardado and agora - guardado[0] < 60:
        return guardado[1]
    desde = int(agora) - SDR_EQUIPE_JANELA_H * 3600
    try:
        saidas = kommo.saidas_do_chat(lead_id, desde)
    except Exception:                                     # noqa: BLE001
        return None
    nossas = state.envios_da_ponte(lead_id, desde - _FOLGA_S)
    alheias = [t for t in saidas if not any(abs(t - n) <= _FOLGA_S for n in nossas)]
    resultado = max(alheias) if alheias else None
    _cache[lead_id] = (agora, resultado)
    return resultado


def potencial_de_venda(falas) -> bool:
    """Alguma fala da pessoa nas últimas 10 tem sinal comercial (preço, aula, agenda, piloto, decisão)?"""
    import sdr
    from sdr import regras
    texto = "\n".join(t for _ts, quem, t in falas if quem == "lead")
    if not texto:
        return False
    a = sdr.avaliar(texto)["analise"]
    return bool(a.get("intencoes") or a.get("conversao") or a.get("compete") or a.get("score", 0) >= regras.LIMIAR)


def contexto(lead_id: int, de_venda: bool = False) -> str:
    """Dono, 30/10 (#533), a regra em três passos: 1) ler as últimas 10 mensagens; 1-A) se houve conversa de
    venda, ler o histórico inteiro e agir pelas diretrizes; 1-B) se foi só interação amigável, seguir e
    identificar se é lead ou não, sem vender."""
    ultimas = state.historico(lead_id, 10)
    if not ultimas:
        return ""
    venda = de_venda or potencial_de_venda(ultimas)
    falas = state.historico(lead_id, 100) if venda else ultimas
    linhas = [f"- {'person' if quem == 'lead' else 'Chase'}: {texto[:300]}" for _ts, quem, texto in falas]
    passo = ("1-A. THIS IS A POTENTIAL SALE CONVERSATION. Above is the full history: get the full context and act "
             "according to your guidelines. Never ask again what was already answered."
             if venda else
             "1-B. THIS WAS A FRIENDLY INTERACTION SO FAR. Carry on naturally and identify if the person is a lead "
             "or not a lead. DO NOT BE SALESY: no triage, no price, no link, unless the person shows interest in "
             "racing. Act according to your guidelines.")
    return (f"1. READ THE CONVERSATION BEFORE ANSWERING ({'full history' if venda else 'last 10 messages'}; the "
            "person's last line is the message below):\n" + "\n".join(linhas) + "\n" + passo + "\n")
