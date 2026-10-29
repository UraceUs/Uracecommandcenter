"""#491 (dono, 29/10: "quem nao tem plano assinado paga normalmente"): sem plano, a conta não segura mais que 3 vagas
futuras esperando pagamento pela área do cliente. Antes, uma conta marcava todos os turnos sem pagar e travava a agenda."""
from command_center.db import inserir, um
from command_center.tests.test_agenda_sessoes import proximo
from command_center.tests.test_carrinho import _csrf, _entrar, loja  # noqa: F401
from command_center.tests.test_stripe_loja import amb  # noqa: F401

P = "/ops/api/portal"


def _marcar(cli, sid, pid, dias):
    return cli.post(f"{P}/bookings", headers=_csrf(cli), json={"date": proximo(dias).isoformat(), "period": "manha",
                                                                "service_id": sid, "driver_id": pid})


def test_sem_plano_a_conta_nao_segura_mais_que_3_vagas_sem_pagar(loja):  # noqa: F811
    cli, con, st, qbo, tmp, sid = loja
    conta, pid = _entrar(cli, con)
    assert [_marcar(cli, sid, pid, d).status_code for d in (2, 3, 4)] == [201, 201, 201]
    r = _marcar(cli, sid, pid, 5)
    assert r.status_code == 429 and "waiting for payment" in r.json()["detail"]
    # outro piloto da mesma conta também não passa (o teto é da conta)
    outro = inserir(con, "portal_pilots", account_id=conta, name="Bia Souza")
    con.commit()
    assert _marcar(cli, sid, outro, 6).status_code == 429
    # paga uma: abre espaço para outra
    con.execute("UPDATE bookings SET paid_at='2026-10-29T12:00:00Z' WHERE id=(SELECT MIN(id) FROM bookings)")
    con.commit()
    assert _marcar(cli, sid, pid, 5).status_code == 201
    assert um(con, "SELECT COUNT(*) AS n FROM bookings WHERE account_id=?", (conta,))["n"] == 4


def test_com_plano_assinado_marca_sem_teto(loja):  # noqa: F811
    cli, con, st, qbo, tmp, sid = loja
    conta, pid = _entrar(cli, con)
    card = inserir(con, "clients", name="Theo Souza", plan_type="monthly", monthly_sessions=8)
    con.execute("UPDATE portal_pilots SET client_id=? WHERE id=?", (card, pid))
    con.commit()
    assert all(_marcar(cli, sid, pid, d).status_code == 201 for d in (2, 3, 4, 5, 6))
