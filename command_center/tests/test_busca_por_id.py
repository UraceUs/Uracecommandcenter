"""#430 (dono, 28/10): "deixe a opção de pesquisar clientes tb pelo id" e "preciso que seja possível puxar as
informações e abrir o card pesquisando com o id do cliente". Um número (621, #621, id 621) também é o Client ID,
e esse card vem primeiro — na lista de Clientes (e no Vincular ao cliente), na busca do topo e no MCP."""
import os
import tempfile

import pytest

os.environ["URACE_ENV"] = "/nao/existe"

from fastapi.testclient import TestClient  # noqa: E402

from command_center.api import auth, mcp_http  # noqa: E402
from command_center.api.main import app  # noqa: E402
from command_center.db import aplicar_schema, conectar, inserir  # noqa: E402
from command_center.providers import identidade  # noqa: E402

B = "/ops/api"
SENHA = "senha-forte-123"
IDS = {}


@pytest.fixture(scope="module")
def cli():
    os.environ["CC_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "cc.sqlite")
    con = conectar(); aplicar_schema(con)
    auth.criar_usuario(con, "admin@urace.us", "Admin", "ADMIN", SENHA)
    IDS["a"] = inserir(con, "clients", name="Rosa Fictícia", email="rosa.ficticia@example.com", pilot_name="Tito Fictício",
                       status="ACTIVE", source="manual")
    IDS["b"] = inserir(con, "clients", name="Card 7 Racing Fictício", email="sete@example.com", status="ACTIVE", source="manual")
    con.commit(); con.close()
    with TestClient(app, base_url="https://cc.test") as c:
        assert c.post(B + "/auth/login", json={"email": "admin@urace.us", "password": SENHA}).status_code == 200
        yield c


@pytest.mark.parametrize("texto", ["{a}", "#{a}", "id {a}", "ID:{a}", " {a} "])
def test_lista_de_clientes_acha_pelo_client_id(cli, texto):
    r = cli.get(B + "/clients", params={"q": texto.format(a=IDS["a"])})
    assert r.status_code == 200
    assert r.json()[0]["id"] == IDS["a"]                       # o card daquele ID vem primeiro


def test_o_card_do_id_vem_antes_de_quem_tem_o_numero_no_nome(cli):
    """O número é o Client ID de um card e também aparece no nome de outro: o do ID vem primeiro, o outro continua."""
    alvo = IDS["b"]
    con = conectar()
    outro = inserir(con, "clients", name=f"Equipe {alvo} Fictícia", status="ACTIVE", source="manual")
    con.commit(); con.close()
    r = [c["id"] for c in cli.get(B + "/clients", params={"q": str(alvo)}).json()]
    assert r[0] == alvo and outro in r


def test_busca_do_topo_acha_pelo_id_com_um_digito(cli):
    alvo = IDS["a"]
    r = cli.get(B + "/search", params={"q": str(alvo)}).json()
    assert r["clients"] and r["clients"][0]["id"] == alvo
    assert cli.get(B + "/search", params={"q": "x"}).json()["clients"] == []     # 1 letra continua sem buscar


def test_busca_por_nome_continua_igual(cli):
    r = cli.get(B + "/clients", params={"q": "Tito Fict"}).json()
    assert [c["id"] for c in r] == [IDS["a"]]


def test_mcp_urace_clientes_acha_pelo_id(cli):
    con = conectar()
    try:
        r = mcp_http._f_clientes(con, busca=f"#{IDS['a']}")
    finally:
        con.close()
    assert r["clientes"][0]["id"] == IDS["a"]


def test_filtro_reconhece_o_id_so_quando_e_numero():
    assert identidade.RX_CLIENT_ID.match("621") and identidade.RX_CLIENT_ID.match("#621")
    assert identidade.RX_CLIENT_ID.match("id 621") and identidade.RX_CLIENT_ID.match("Id:621")
    for nao in ("621a", "Jayden", "555-0101", "6 21", ""):
        assert not identidade.RX_CLIENT_ID.match(nao), nao
