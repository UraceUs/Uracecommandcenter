"""Selo e TSA de TESTE para a waiver nativa (#110). Nada daqui vai para produção nem fica no repositório: as chaves
são geradas na hora, em pasta temporária.

- `criar_selo(pasta)`: a raiz e o selo pelo próprio `selo_waiver.criar` (o mesmo caminho do `manage.py`).
- `tsa()`: a TSA falsa do pyHanko (`DummyTimeStamper`, só aceita chave RSA), com raiz própria de teste.
- `TsaFalsa`: a mesma TSA atrás de um servidor HTTP local (RFC 3161 por POST), para o end-to-end e para o
  caminho de verdade do `requests`. O CI não tem rede: nada aqui fala com TSA real.
"""
import threading
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def carimbadores_reais():
    """O `_carimbadores` de verdade (o conftest troca pela TSA falsa em todo teste): para o teste do caminho HTTP."""
    from command_center.providers import selo_waiver
    return _REAL.get("f") or selo_waiver._carimbadores


_REAL = {}


def guardar_o_real():
    from command_center.providers import selo_waiver
    _REAL.setdefault("f", selo_waiver._carimbadores)


def criar_selo(pasta):
    from command_center.providers import selo_waiver
    return selo_waiver.criar(str(pasta))


@lru_cache(maxsize=1)
def _material_tsa():
    """(raiz da TSA, certificado da TSA, chave RSA da TSA): uma vez por execução (gerar RSA custa)."""
    from cryptography.hazmat.primitives.asymmetric import ec, rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID
    from command_center.providers import selo_waiver as sw
    k_raiz = ec.generate_private_key(ec.SECP256R1())
    raiz = sw.emitir(sw._nome("URACE TEST TSA Root"), sw._nome("URACE TEST TSA Root"), k_raiz.public_key(), k_raiz, 1, ca=True)
    k_tsa = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = sw.emitir(sw._nome("URACE TEST Time Stamping Authority"), raiz.subject, k_tsa.public_key(), k_raiz, 1,
                     eku=[ExtendedKeyUsageOID.TIME_STAMPING], emissor_cert=raiz)
    return raiz, cert, k_tsa


def raiz_tsa():
    return _material_tsa()[0]


def tsa():
    from pyhanko.sign.timestamps.dummy_client import DummyTimeStamper
    from pyhanko_certvalidator.registry import SimpleCertificateStore
    from command_center.providers import selo_waiver as sw
    raiz, cert, chave = _material_tsa()
    return DummyTimeStamper(tsa_cert=sw._asn1(cert), tsa_key=sw._asn1(chave=chave),
                            certs_to_embed=SimpleCertificateStore.from_certs([sw._asn1(raiz)]))


class TsaQueFalha:
    """Uma TSA fora do ar (o pedido nunca volta)."""

    def __init__(self):
        from pyhanko.sign.timestamps.api import TimeStamper
        from pyhanko.sign.timestamps.common_utils import TimestampRequestError

        class _Fora(TimeStamper):
            async def async_request_tsa_response(self, req):
                raise TimestampRequestError("TSA de teste fora do ar")
        self.carimbador = _Fora()


class TsaFalsa:
    """A TSA falsa num servidor HTTP local: `url` vai para `CC_WAIVER_TSA`."""

    def __init__(self):
        from asn1crypto import tsp
        dummy = tsa()
        self.pedidos = 0
        fake = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                corpo = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                resp = dummy.request_tsa_response(tsp.TimeStampReq.load(corpo)).dump()
                fake.pedidos += 1
                self.send_response(200)
                self.send_header("Content-Type", "application/timestamp-reply")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)

            def log_message(self, *a):
                pass

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}/tsr"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def parar(self):
        self.srv.shutdown()
        self.srv.server_close()
