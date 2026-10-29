"""Debug de 29/10 — o e-mail de waiver do DocuSign que a triagem do Gmail marca vai para o card CERTO.

`waiver_do_email` acha de quem é a waiver pelo nome do signatário (ou do menor) no e-mail. O nome tem de aparecer
como nome, não como pedaço de outro: "Lia Fictícia" não é "Amelia Fictícia". Errar o card leva o e-mail, o PDF
anexado e a subtarefa do Asana para o cliente errado (a waiver de um no card do outro). Só dados fictícios."""
import pytest

from command_center.db import aplicar_schema, conectar, inserir, um


@pytest.fixture()
def con(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_DB_PATH", str(tmp_path / "waiver-email.sqlite"))
    c = conectar(); aplicar_schema(c)
    yield c
    c.close()


@pytest.fixture()
def externos(monkeypatch, tmp_path):
    """DocuSign fora do ar (o PDF sai do anexo do e-mail), Gmail e Asana de mentira: nada sai da máquina."""
    import command_center.providers as prov
    from command_center.api import motor
    monkeypatch.setattr(motor, "PASTA_WAIVERS", str(tmp_path / "w"))
    anexados = []

    class Docusign:
        def baixar_documento_humano(self, env):
            raise RuntimeError("DocuSign fora")

    class Gmail:
        def anexos_da_thread(self, conta, tid):
            return [{"message_id": "m1", "attachment_id": "a1", "nome": "waiver_assinada.pdf"}]

        def baixar_anexo_bytes(self, conta, mid, aid):
            return b"%PDF-1.4 waiver da Amelia"

    class Asana:
        def asana_anexar_arquivo(self, gid, caminho):
            anexados.append(gid)
            return {"aplicado": True, "anexo_gid": "a"}

        def concluir_subtarefa_sistema(self, gid, padrao=None):
            return {"aplicado": True, "subtarefa": "Signed waiver?"}
    monkeypatch.setattr(prov, "modulo", lambda s: {"docusign": Docusign(), "gmail": Gmail(), "asana": Asana()}[s])
    return anexados


def _cliente_com_waiver(con, nome, completed_at, gid):
    cid = inserir(con, "clients", name=nome, email=f"{nome.split()[0].lower()}@example.com", status="ACTIVE")
    wid = inserir(con, "waivers", client_id=cid, signer_name=nome, signer_email=f"{nome.split()[0].lower()}@example.com",
                  template="adult", status="completed", sent_at=completed_at, completed_at=completed_at)
    inserir(con, "entity_links", entity_type="waiver", entity_id=wid, system="docusign", external_id=f"env-{wid}")
    tid = inserir(con, "tasks", client_id=cid, title=f"{nome}_Urace Daily", status="open", due_on="2026-11-02")
    inserir(con, "entity_links", entity_type="task", entity_id=tid, system="asana", external_id=gid)
    return cid, wid


def test_nome_dentro_de_outro_nome_nao_leva_a_waiver_para_o_card_errado(con, externos):
    from command_center.api import motor
    amelia, w_amelia = _cliente_com_waiver(con, "Amelia Fictícia", "2026-10-27T15:00:00.000Z", "g-amelia")
    lia, w_lia = _cliente_com_waiver(con, "Lia Fictícia", "2026-10-28T15:00:00.000Z", "g-lia")      # a mais recente
    eid = inserir(con, "emails", mailbox="support", subject="Completed: URACE Release and Waiver of Liability",
                  sender="dse@docusign.example.com", is_inbox=1, labels='["INBOX","Waivers"]')
    r = motor.waiver_do_email(con, eid, "support", "th-1", "Completed: URACE Release and Waiver of Liability. "
                                                       "Amelia Fictícia completed the document.")
    assert r["ok"] and r["client_id"] == amelia and r["waiver_id"] == w_amelia
    assert um(con, "SELECT client_id FROM emails WHERE id=?", (eid,))["client_id"] == amelia
    assert um(con, "SELECT pdf_path FROM waivers WHERE id=?", (w_lia,))["pdf_path"] is None, "o PDF da Amelia não vai para a Lia"
    assert externos == ["g-amelia"], "só a tarefa da Amelia recebe a waiver dela"


def test_o_nome_inteiro_continua_casando(con, externos):
    from command_center.api import motor
    lia, w_lia = _cliente_com_waiver(con, "Lia Fictícia", "2026-10-28T15:00:00.000Z", "g-lia")
    eid = inserir(con, "emails", mailbox="support", subject="Completed", sender="dse@docusign.example.com", is_inbox=1)
    r = motor.waiver_do_email(con, eid, "support", "th-2", "Completed: Lia Fictícia, Waiver of Liability")
    assert r["ok"] and r["client_id"] == lia and r["waiver_id"] == w_lia
