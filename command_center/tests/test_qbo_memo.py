"""Nota ao cliente da invoice (#402).

Dono, 27/10: *"o Command Center enviou uma invoice e não tinha nada escrito nela ... se forem de
partes, colocar que são de partes ... se for um training day, ela lê o que está nos itens da invoice
e coloca no memo e no payment instructions do que é, qual a data"*. Nenhuma invoice, estimate ou
recorrência sai com "Note to customer" vazio.
"""
import os
import sys

import pytest

os.environ["URACE_ENV"] = "/nao/existe"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "adminai", "mcp"))

import quickbooks_mcp as q  # noqa: E402

PECAS = [{"item_id": "1", "unitario": 37.27, "descricao": "Parolin tie rod"},
         {"item_id": "2", "quantidade": 2, "unitario": 23.38, "descricao": "Parolin tie rod end"},
         {"item_id": "3", "unitario": 183.25, "descricao": "Parolin cadet spindle - 2026-10-24"}]
TREINO = [{"item_id": "9", "unitario": 719, "descricao": "Urace Training Day - Cadet 4T"}]


def test_memo_de_pecas_diz_que_e_peca_com_data_e_vencimento():
    m = q.memo_das_linhas(PECAS, vence_em="2026-10-29", data_servico="2026-10-24", piloto="Robin")
    cabeca, instrucao = m.split("\n")
    assert cabeca == ("Parts | Parolin tie rod, Parolin tie rod end, Parolin cadet spindle | Robin "
                      "| Service date: 10/24/2026")
    assert instrucao == "Parts used on the service date above. Payment due by 10/29/2026."


def test_memo_de_servico_nao_vira_peca():
    m = q.memo_das_linhas(TREINO, vence_em="2026-10-31", data_servico="2026-11-02", piloto="Robin")
    assert m.startswith("Urace Training Day - Cadet 4T | Robin | Service date: 11/02/2026\n")
    assert "Parts" not in m and m.endswith("Payment due by 10/31/2026.")


def test_memo_nunca_sai_vazio():
    assert q.memo_das_linhas([]).startswith("Urace service\n")
    assert q.memo_das_linhas([{"item_id": "1", "unitario": 10}]).startswith("Urace service\n")


def test_piloto_nao_repete_quando_ja_esta_na_descricao():
    m = q.memo_das_linhas([{"descricao": "Coaching Robin"}], piloto="Robin")
    assert m.count("Robin") == 1


@pytest.fixture
def qbo_falso(monkeypatch):
    corpos = []
    monkeypatch.setattr(q, "_aplicar", lambda: True)
    monkeypatch.setattr(q, "_proximo_doc_number", lambda: "URACE-0999")
    monkeypatch.setattr(q, "_realm", lambda: "9341453113046421")
    monkeypatch.setattr(q, "_req", lambda c, m="GET", corpo=None, params=None: (
        corpos.append(corpo) or {"Invoice": {"Id": "9999", "DocNumber": "URACE-0999", "TotalAmt": 267.28, "Line": []},
                                 "Estimate": {"Id": "77", "DocNumber": "E-1", "TotalAmt": 719}}))
    return corpos


def test_invoice_sem_memo_de_quem_chamou_sai_preenchida(qbo_falso):
    q.qbo_criar_invoice("677", PECAS, vence_em="2026-10-29", data_servico="2026-10-24", piloto="Robin")
    corpo = qbo_falso[-1]
    memo = corpo["CustomerMemo"]["value"]
    assert memo.startswith("Parts | Parolin tie rod")
    assert "Service date: 10/24/2026" in memo and "Payment due by 10/29/2026." in memo
    assert corpo["PrivateNote"] == memo                      # "Memo on statement" igual à nota


def test_memo_de_quem_chamou_continua_mandando(qbo_falso):
    q.qbo_criar_invoice("677", PECAS, vence_em="2026-10-29", memo="Texto do dono")
    assert qbo_falso[-1]["CustomerMemo"]["value"] == "Texto do dono"


def test_estimate_tambem_sai_preenchido(qbo_falso):
    q.qbo_criar_estimate("677", TREINO, data_servico="2026-11-02")
    assert qbo_falso[-1]["CustomerMemo"]["value"].startswith("Urace Training Day - Cadet 4T | Service date: 11/02/2026")
